#!/usr/bin/env python3
"""
抓取A股+港股半导体龙头实时行情
数据源：东方财富 push2 API
输出：data/realtime_quotes.json
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STOCK_LIST_FILE = DATA_DIR / "stock_list.json"
OUTPUT_FILE = DATA_DIR / "realtime_quotes.json"

# 东方财富 API 配置
EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
FIELDS = "f2,f3,f4,f12,f14,f15,f16,f17,f18,f20,f21,f23,f8,f9,f5,f6,f62,f115"
BATCH_SIZE = 50  # 每批次最多请求数量
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

# 北京时区
TZ_BEIJING = timezone(timedelta(hours=8))

# A股交易时段: 9:30-11:30, 13:00-15:00 (工作日)
# 港股交易时段: 9:30-12:00, 13:00-16:00 (工作日)


def is_trading_time() -> bool:
    """判断当前是否在交易时段内（A股为主）"""
    now = datetime.now(TZ_BEIJING)
    # 周末不交易
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning_start = t.replace(hour=9, minute=30, second=0)
    morning_end = t.replace(hour=11, minute=30, second=0)
    afternoon_start = t.replace(hour=13, minute=0, second=0)
    afternoon_end = t.replace(hour=15, minute=0, second=0)
    return (morning_start <= t <= morning_end) or (afternoon_start <= t <= afternoon_end)


def market_to_secid(code: str, market: str) -> str:
    """将股票代码和市场转换为东方财富 secid 格式"""
    market_map = {
        "sh": "1",    # 沪市
        "sz": "0",    # 深市
        "hk": "116",  # 港股
    }
    prefix = market_map.get(market)
    if prefix is None:
        raise ValueError(f"未知市场: {market}")
    return f"{prefix}.{code}"


def load_stock_list() -> list:
    """从配置文件加载股票列表"""
    try:
        with open(STOCK_LIST_FILE, "r", encoding="utf-8") as f:
            stocks = json.load(f)
        logger.info(f"加载股票列表: {len(stocks)} 只")
        return stocks
    except FileNotFoundError:
        logger.error(f"股票列表文件不存在: {STOCK_LIST_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"股票列表文件格式错误: {e}")
        sys.exit(1)


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
                    "change_pct": item.get("f3"),       # 涨跌幅 %
                    "change_amt": item.get("f4"),        # 涨跌额
                    "open": item.get("f17"),
                    "high": item.get("f15"),
                    "low": item.get("f16"),
                    "prev_close": item.get("f18"),
                    "volume": item.get("f5"),            # 成交量(手)
                    "amount": item.get("f6"),            # 成交额(元)
                    "turnover": item.get("f8"),          # 换手率 %
                    "total_mcap": item.get("f20"),       # 总市值
                    "float_mcap": item.get("f21"),       # 流通市值
                    "pe_ttm": item.get("f9"),            # PE(TTM)
                    "pe_static": item.get("f115"),       # PE(静态)
                    "pb": item.get("f23"),               # PB
                    "main_net_inflow": item.get("f62"),  # 主力净流入
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

    logger.error(f"批次请求全部失败: {secids[:3]}...")
    return []


def fetch_all_stocks(stocks: list) -> dict:
    """批量获取所有股票行情"""
    all_quotes = []
    errors = []

    # 按 BATCH_SIZE 分批
    for i in range(0, len(stocks), BATCH_SIZE):
        batch = stocks[i : i + BATCH_SIZE]
        secids = []
        stock_map = {}  # secid -> stock_info

        for stock in batch:
            try:
                secid = market_to_secid(stock["code"], stock["market"])
                secids.append(secid)
                stock_map[secid] = stock
            except ValueError as e:
                logger.error(f"跳过无效股票 {stock.get('code')}: {e}")
                errors.append({"code": stock.get("code"), "error": str(e)})

        if not secids:
            continue

        logger.info(f"正在请求批次 {i // BATCH_SIZE + 1}: {len(secids)} 只股票")
        batch_results = fetch_batch(secids)

        for quote in batch_results:
            # 合并股票配置信息（sector等）
            code = quote["code"]
            # 查找匹配的股票配置
            for stock in batch:
                if stock["code"] == code:
                    quote["market"] = stock["market"]
                    quote["sector"] = stock.get("sector", "")
                    break
            all_quotes.append(quote)

        # 避免请求过快
        if i + BATCH_SIZE < len(stocks):
            time.sleep(0.3)

    now = datetime.now(TZ_BEIJING)
    trading = is_trading_time()

    return {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "trading": trading,
        "total": len(all_quotes),
        "errors": errors,
        "quotes": all_quotes,
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
    logger.info("开始抓取 A股+港股 半导体行情数据")
    logger.info("=" * 50)

    start_time = time.time()

    # 加载股票列表
    stocks = load_stock_list()
    if not stocks:
        logger.error("股票列表为空")
        sys.exit(1)

    # 抓取数据
    result = fetch_all_stocks(stocks)

    # 保存结果
    save_output(result)

    elapsed = time.time() - start_time
    logger.info(
        f"抓取完成: {result['total']} 只股票, "
        f"耗时 {elapsed:.1f}s, "
        f"交易时段: {'是' if result['trading'] else '否'}"
    )

    if result["errors"]:
        logger.warning(f"出现 {len(result['errors'])} 个错误: {result['errors']}")

    return result


if __name__ == "__main__":
    main()
