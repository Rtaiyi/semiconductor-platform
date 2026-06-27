#!/usr/bin/env python3
"""
抓取市场基准数据和半导体行业数据
- 基准指数：沪深300、科创50、标普500、纳斯达克（东方财富API）
- 半导体行业数据：从已有 market_data.json 读取（WSTS/SIA 手动维护）
- 费城半导体指数(SOX)：东方财富暂不支持，使用缓存值

输出：data/benchmarks.json (基准指数实时数据)
      data/market_data.json 已包含行业基础数据，此脚本仅更新时间戳
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BENCHMARKS_FILE = DATA_DIR / "benchmarks.json"
MARKET_DATA_FILE = DATA_DIR / "market_data.json"

EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
FIELDS = "f2,f3,f4,f12,f14,f20,f5,f6"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

TZ_BEIJING = timezone(timedelta(hours=8))

# 基准指数配置
BENCHMARK_INDICES = [
    # A股指数
    {"secid": "1.000300", "code": "000300", "name": "沪深300", "region": "中国", "type": "大盘"},
    {"secid": "1.000688", "code": "000688", "name": "科创50", "region": "中国", "type": "科技"},
    {"secid": "1.000001", "code": "000001", "name": "上证指数", "region": "中国", "type": "大盘"},
    {"secid": "0.399001", "code": "399001", "name": "深证成指", "region": "中国", "type": "大盘"},
    {"secid": "0.399006", "code": "399006", "name": "创业板指", "region": "中国", "type": "成长"},
    # 美股指数
    {"secid": "100.SPX", "code": "SPX", "name": "标普500", "region": "美国", "type": "大盘"},
    {"secid": "100.NDX", "code": "NDX", "name": "纳斯达克", "region": "美国", "type": "科技"},
    {"secid": "100.DJI", "code": "DJI", "name": "道琼斯", "region": "美国", "type": "大盘"},
]

# SOX 指数（东方财富不支持，使用手动缓存）
SOX_CACHED = {
    "code": "SOX",
    "name": "费城半导体指数",
    "region": "美国",
    "type": "半导体",
    "note": "东方财富API暂不支持SOX指数，当前为缓存值。可通过Yahoo Finance手动更新。",
}


def fetch_benchmarks() -> dict:
    """获取基准指数行情"""
    secids = [idx["secid"] for idx in BENCHMARK_INDICES]
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": FIELDS,
        "secids": ",".join(secids),
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
    }

    indices = []
    errors = []

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                EASTMONEY_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("rc") != 0:
                logger.warning(f"API返回错误: rc={data.get('rc')}")
                break

            diff_list = data.get("data", {}).get("diff", [])
            if not diff_list:
                break

            config_map = {idx["secid"]: idx for idx in BENCHMARK_INDICES}

            for item in diff_list:
                code = item.get("f12", "")
                config = None
                for idx in BENCHMARK_INDICES:
                    if idx["code"] == code:
                        config = idx
                        break

                indices.append({
                    "code": code,
                    "name": item.get("f14", ""),
                    "price": item.get("f2"),
                    "change_pct": item.get("f3"),
                    "change_amt": item.get("f4"),
                    "region": config["region"] if config else "",
                    "type": config["type"] if config else "",
                })

            break

        except requests.exceptions.Timeout:
            logger.warning(f"请求超时 (attempt {attempt + 1}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败 (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"数据解析错误: {e}")
            break

    # 检查遗漏
    fetched_codes = {idx["code"] for idx in indices}
    for idx in BENCHMARK_INDICES:
        if idx["code"] not in fetched_codes:
            errors.append({"code": idx["code"], "name": idx["name"], "error": "API未返回数据"})

    # 添加 SOX 缓存数据
    indices.append(SOX_CACHED)

    return {"indices": indices, "errors": errors}


def update_market_data_timestamp() -> dict:
    """更新 market_data.json 的时间戳"""
    if not MARKET_DATA_FILE.exists():
        logger.warning(f"market_data.json 不存在: {MARKET_DATA_FILE}")
        return {"status": "skipped", "reason": "file not found"}

    try:
        with open(MARKET_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = datetime.now(TZ_BEIJING)
        data["last_updated"] = now.isoformat()
        data["update_note"] = (
            f"自动更新时间戳 ({now.strftime('%Y-%m-%d %H:%M:%S')})。"
            "WSTS/SIA行业数据需手动从官方PDF/网页更新，每年发布2-3次。"
        )

        with open(MARKET_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"已更新 market_data.json 时间戳")
        return {"status": "updated", "file": str(MARKET_DATA_FILE)}
    except Exception as e:
        logger.error(f"更新 market_data.json 失败: {e}")
        return {"status": "error", "reason": str(e)}


def save_benchmarks(data: dict) -> None:
    """保存基准指数数据"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ_BEIJING)

    output = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "total": len(data["indices"]),
        "errors": data["errors"],
        "indices": data["indices"],
    }

    with open(BENCHMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info(f"基准指数数据已保存到 {BENCHMARKS_FILE}")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始抓取市场基准数据")
    logger.info("=" * 50)

    start_time = time.time()

    # 抓取基准指数
    logger.info("抓取基准指数行情...")
    result = fetch_benchmarks()

    # 保存基准指数
    save_benchmarks(result)

    # 更新 market_data.json 时间戳
    logger.info("更新行业市场数据时间戳...")
    md_result = update_market_data_timestamp()

    elapsed = time.time() - start_time
    logger.info(
        f"完成: {result['indices']} 个指数, "
        f"market_data: {md_result['status']}, "
        f"耗时 {elapsed:.1f}s"
    )

    if result["errors"]:
        logger.warning(f"指数获取错误: {result['errors']}")

    return result


if __name__ == "__main__":
    main()
