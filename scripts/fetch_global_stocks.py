#!/usr/bin/env python3
"""
抓取全球半导体龙头股票实时行情
数据源：东方财富全球行情 API（美股 ADR + US 上市）
覆盖：美股、台积电(NYSE ADR)、SK海力士(NYSE ADR)、ASML(NASDAQ)
注意：台股/日股/韩股本地行情需 Yahoo Finance（当前环境受限），
     以 ADR 数据作为近似替代，并标注数据来源。

输出：data/global_stocks.json
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
OUTPUT_FILE = DATA_DIR / "global_stocks.json"

# 东方财富全球行情 API
EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
FIELDS = "f2,f3,f4,f12,f14,f15,f16,f17,f18,f20,f21,f23,f8,f9,f5,f6,f62,f115"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

TZ_BEIJING = timezone(timedelta(hours=8))

# 全球半导体龙头配置
# market: us=美股, tw_dr=台股ADR, kr_dr=韩股ADR, eu_us=欧股美股上市
GLOBAL_STOCKS = [
    # --- 设计/无晶圆厂 ---
    {"code": "NVDA", "market": "us", "secid": "105.NVDA", "name": "英伟达", "name_en": "NVIDIA", "region": "美国", "category": "设计-GPU/AI"},
    {"code": "AMD", "market": "us", "secid": "105.AMD", "name": "AMD", "name_en": "Advanced Micro Devices", "region": "美国", "category": "设计-CPU/GPU"},
    {"code": "AVGO", "market": "us", "secid": "105.AVGO", "name": "博通", "name_en": "Broadcom", "region": "美国", "category": "设计-网络/ASIC"},
    {"code": "QCOM", "market": "us", "secid": "105.QCOM", "name": "高通", "name_en": "Qualcomm", "region": "美国", "category": "设计-移动SoC"},
    {"code": "MRVL", "market": "us", "secid": "105.MRVL", "name": "迈威尔", "name_en": "Marvell Technology", "region": "美国", "category": "设计-数据中心"},
    {"code": "INTC", "market": "us", "secid": "105.INTC", "name": "英特尔", "name_en": "Intel", "region": "美国", "category": "IDM-CPU"},
    # --- 存储 ---
    {"code": "MU", "market": "us", "secid": "105.MU", "name": "美光科技", "name_en": "Micron Technology", "region": "美国", "category": "存储"},
    {"code": "SKHY", "market": "kr_dr", "secid": "105.SKHY", "name": "SK海力士(ADR)", "name_en": "SK Hynix (ADR)", "region": "韩国", "category": "存储", "note": "ADR替代韩股本行情"},
    # --- 制造 ---
    {"code": "TSM", "market": "tw_dr", "secid": "106.TSM", "name": "台积电(ADR)", "name_en": "TSMC (ADR)", "region": "台湾", "category": "制造-晶圆代工", "note": "ADR替代台股本行情"},
    # --- 设备 ---
    {"code": "ASML", "market": "eu_us", "secid": "105.ASML", "name": "阿斯麦", "name_en": "ASML", "region": "荷兰", "category": "设备-光刻"},
    {"code": "AMAT", "market": "us", "secid": "105.AMAT", "name": "应用材料", "name_en": "Applied Materials", "region": "美国", "category": "设备-沉积/刻蚀"},
    {"code": "LRCX", "market": "us", "secid": "105.LRCX", "name": "拉姆研究", "name_en": "Lam Research", "region": "美国", "category": "设备-刻蚀"},
    {"code": "KLAC", "market": "us", "secid": "105.KLAC", "name": "科磊", "name_en": "KLA", "region": "美国", "category": "设备-检测"},
]


def is_us_market_open() -> bool:
    """判断美股是否在交易时段（美东 9:30-16:00）"""
    now_utc = datetime.now(timezone.utc)
    et_offset = timedelta(hours=-4)  # EDT (夏令时)
    now_et = now_utc + et_offset
    if now_et.weekday() >= 5:
        return False
    t = now_et.time()
    return t.hour >= 9 and (t.hour < 16 or (t.hour == 16 and t.minute == 0))


def fetch_batch(secids: list[str]) -> list[dict]:
    """批量获取股票行情数据"""
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

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                EASTMONEY_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("rc") != 0:
                logger.warning(f"API返回错误: rc={data.get('rc')}")
                return []

            diff_list = data.get("data", {}).get("diff", [])
            if not diff_list:
                return []

            results = []
            for item in diff_list:
                results.append({
                    "code": item.get("f12", ""),
                    "name": item.get("f14", ""),
                    "price": item.get("f2"),
                    "change_pct": item.get("f3"),
                    "change_amt": item.get("f4"),
                    "open": item.get("f17"),
                    "high": item.get("f15"),
                    "low": item.get("f16"),
                    "prev_close": item.get("f18"),
                    "volume": item.get("f5"),
                    "amount": item.get("f6"),
                    "turnover": item.get("f8"),
                    "total_mcap": item.get("f20"),
                    "float_mcap": item.get("f21"),
                    "pe_ttm": item.get("f9"),
                    "pe_static": item.get("f115"),
                    "pb": item.get("f23"),
                    "main_net_inflow": item.get("f62"),
                })
            return results

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
            return []

    return []


def fetch_all_global() -> dict:
    """抓取所有全球龙头股票行情"""
    all_quotes = []
    errors = []

    # 提取所有 secid
    secids = [s["secid"] for s in GLOBAL_STOCKS]

    logger.info(f"正在请求 {len(secids)} 只全球半导体龙头股票")
    batch_results = fetch_batch(secids)

    # 创建 secid -> stock_config 映射
    config_map = {s["secid"]: s for s in GLOBAL_STOCKS}

    for quote in batch_results:
        code = quote["code"]
        # 查找配置
        config = None
        for stock in GLOBAL_STOCKS:
            if stock["code"] == code:
                config = stock
                break

        if config:
            quote["name_en"] = config["name_en"]
            quote["region"] = config["region"]
            quote["category"] = config["category"]
            quote["market_type"] = config["market"]
            if "note" in config:
                quote["note"] = config["note"]
        all_quotes.append(quote)

    # 检查遗漏
    fetched_codes = {q["code"] for q in all_quotes}
    for stock in GLOBAL_STOCKS:
        if stock["code"] not in fetched_codes:
            logger.warning(f"未获取到数据: {stock['name']} ({stock['code']})")
            errors.append({"code": stock["code"], "name": stock["name"], "error": "API未返回数据"})

    now = datetime.now(TZ_BEIJING)
    us_trading = is_us_market_open()

    return {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "us_market_open": us_trading,
        "trading": us_trading,
        "total": len(all_quotes),
        "errors": errors,
        "quotes": all_quotes,
        "data_source": "东方财富全球行情API",
        "disclaimer": "台积电/SK海力士为ADR价格，与本地股价存在差异。台湾/韩国/日本/欧洲本地行情暂不可用（Yahoo Finance受限）。",
    }


def save_output(data: dict) -> None:
    """保存输出到 JSON 文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"数据已保存到 {OUTPUT_FILE}")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始抓取全球半导体龙头股票行情")
    logger.info("=" * 50)

    start_time = time.time()
    result = fetch_all_global()
    save_output(result)

    elapsed = time.time() - start_time
    logger.info(
        f"抓取完成: {result['total']} 只股票, "
        f"耗时 {elapsed:.1f}s, "
        f"美股交易: {'是' if result['us_market_open'] else '否'}"
    )

    if result["errors"]:
        logger.warning(f"出现 {len(result['errors'])} 个错误: {result['errors']}")

    return result


if __name__ == "__main__":
    main()
