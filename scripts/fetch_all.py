#!/usr/bin/env python3
"""
半导体产业数据自动化抓取主入口

调用所有子模块：
  1. fetch_a_hk_stocks.py   — A股+港股半导体龙头实时行情
  2. fetch_global_stocks.py  — 全球半导体龙头股价
  3. fetch_market_data.py   — 市场基准指数 + 行业数据时间戳

特性：
  - 各模块独立运行，单个失败不影响其他
  - 带重试和错误处理
  - 生成汇总日志和状态文件
  - 输出：data/status.json (整体运行状态)
"""

import json
import logging
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"
STATUS_FILE = DATA_DIR / "status.json"

TZ_BEIJING = timezone(timedelta(hours=8))

# 子模块配置
MODULES = [
    {
        "name": "fetch_a_hk_stocks",
        "script": "fetch_a_hk_stocks.py",
        "description": "A股+港股半导体龙头实时行情",
        "output_file": "realtime_quotes.json",
        "enabled": True,
    },
    {
        "name": "fetch_global_stocks",
        "script": "fetch_global_stocks.py",
        "description": "全球半导体龙头股价",
        "output_file": "global_stocks.json",
        "enabled": True,
    },
    {
        "name": "fetch_market_data",
        "script": "fetch_market_data.py",
        "description": "市场基准指数 + 行业数据",
        "output_file": "benchmarks.json",
        "enabled": True,
    },
]


def run_module(module: dict) -> dict:
    """运行单个子模块并返回结果"""
    script_path = SCRIPTS_DIR / module["script"]
    name = module["name"]

    if not script_path.exists():
        return {
            "module": name,
            "status": "error",
            "error": f"脚本不存在: {script_path}",
            "elapsed": 0,
        }

    logger.info(f"[{name}] 开始执行...")
    start = time.time()

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120,  # 2分钟超时
            cwd=str(BASE_DIR),
        )

        elapsed = time.time() - start

        if result.returncode == 0:
            logger.info(f"[{name}] 执行成功 ({elapsed:.1f}s)")
            status = "success"
        else:
            logger.warning(f"[{name}] 执行失败 (exit={result.returncode}, {elapsed:.1f}s)")
            status = "failed"

        # 截取关键日志
        stderr_lines = result.stderr.strip().split("\n")
        key_errors = [l for l in stderr_lines if "ERROR" in l or "Error" in l or "error" in l]

        return {
            "module": name,
            "description": module["description"],
            "status": status,
            "exit_code": result.returncode,
            "elapsed": round(elapsed, 2),
            "stdout_tail": result.stdout.strip()[-500:] if result.stdout else "",
            "stderr_errors": key_errors[-5:] if key_errors else [],
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        logger.error(f"[{name}] 执行超时")
        return {
            "module": name,
            "status": "timeout",
            "error": "执行超时 (>120s)",
            "elapsed": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"[{name}] 异常: {e}")
        return {
            "module": name,
            "status": "error",
            "error": str(e),
            "elapsed": round(elapsed, 2),
        }


def check_output_files() -> dict:
    """检查各模块输出文件"""
    files_status = {}
    for module in MODULES:
        output_file = DATA_DIR / module["output_file"]
        if output_file.exists():
            stat = output_file.stat()
            files_status[module["output_file"]] = {
                "exists": True,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=TZ_BEIJING).isoformat(),
            }
        else:
            files_status[module["output_file"]] = {"exists": False, "size_bytes": 0}
    return files_status


def save_status(results: list, files_status: dict, total_elapsed: float) -> None:
    """保存运行状态"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(TZ_BEIJING)
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] != "success")

    status = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "overall": "success" if failed_count == 0 else "partial" if success_count > 0 else "failed",
        "total_modules": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "total_elapsed": round(total_elapsed, 2),
        "modules": results,
        "output_files": files_status,
    }

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    logger.info(f"运行状态已保存到 {STATUS_FILE}")


def main():
    """主入口"""
    logger.info("=" * 60)
    logger.info("半导体产业数据自动化抓取 - 开始执行")
    logger.info(f"时间: {datetime.now(TZ_BEIJING).isoformat()}")
    logger.info(f"模块数: {len(MODULES)}")
    logger.info("=" * 60)

    total_start = time.time()
    all_results = []
    enabled_modules = [m for m in MODULES if m.get("enabled", True)]

    # 并行执行所有启用的子模块
    with ThreadPoolExecutor(max_workers=len(enabled_modules)) as executor:
        future_map = {executor.submit(run_module, m): m for m in enabled_modules}
        for future in as_completed(future_map):
            result = future.result()
            all_results.append(result)

    # 保持模块顺序
    all_results.sort(key=lambda r: [m["name"] for m in MODULES].index(r["module"]))

    total_elapsed = time.time() - total_start

    # 检查输出文件
    files_status = check_output_files()

    # 保存状态
    save_status(all_results, files_status, total_elapsed)

    # 打印汇总
    logger.info("=" * 60)
    logger.info("执行汇总")
    logger.info("=" * 60)
    for r in all_results:
        status_icon = "[OK]" if r["status"] == "success" else "[FAIL]" if r["status"] != "skipped" else "[SKIP]"
        elapsed = r.get("elapsed", 0)
        logger.info(f"  {status_icon} {r['module']}: {r['status']} ({elapsed:.1f}s)")
        if r.get("stderr_errors"):
            for err in r["stderr_errors"]:
                logger.info(f"       {err}")

    logger.info(f"总耗时: {total_elapsed:.1f}s")
    logger.info(f"成功: {sum(1 for r in all_results if r['status'] == 'success')}/{len(all_results)}")

    # 返回退出码：只有全部模块失败才 exit(1)，部分成功允许提交已获取的数据
    success_count = sum(1 for r in all_results if r["status"] == "success")
    failed = [r for r in all_results if r["status"] not in ("success", "skipped")]
    if success_count == 0:
        logger.error(f"所有 {len(MODULES)} 个模块均失败，退出")
        sys.exit(1)
    elif failed:
        logger.warning(f"部分成功: {success_count}/{len(MODULES)}，{len(failed)} 个模块失败")
        logger.info("继续提交已获取的数据")
    else:
        logger.info("所有模块执行成功")


if __name__ == "__main__":
    main()
