#!/usr/bin/env python3
"""
公共模块：统一 API 调用、数据保存、日志、时区等
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

# ── 基础配置 ──
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TZ_BEIJING = timezone(timedelta(hours=8))

# ── 东方财富 API 配置 ──
EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
FIELDS_FULL = "f2,f3,f4,f12,f14,f15,f16,f17,f18,f20,f21,f23,f8,f9,f5,f6,f62,f115"
FIELDS_BRIEF = "f2,f3,f4,f12,f14,f20,f5,f6"

# ── 请求头 ──
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

# ── 日志 ──
def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """配置统一的日志格式"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name or __name__)


# ── API 调用 ──
def fetch_eastmoney(secids: list[str], fields: str = FIELDS_FULL) -> list[dict]:
    """统一的东方财富 API 调用，带重试机制"""
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": fields,
        "secids": ",".join(secids),
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                EASTMONEY_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("rc") != 0:
                raise ValueError(f"API 返回错误: rc={data.get('rc')}")

            diff_list = data.get("data", {}).get("diff", [])
            if not diff_list and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue

            return diff_list

        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            last_error = e
            break

    raise last_error or RuntimeError("API 调用失败")


# ── 原子写入 ──
def save_json_atomic(filepath: Path, data: dict, min_items_key: Optional[str] = None) -> bool:
    """原子写入 JSON 文件（先写临时文件，成功后再替换）
    
    Args:
        filepath: 目标文件路径
        data: 要写入的数据
        min_items_key: 数据中数组字段名，如果该字段为空则不覆盖旧文件
    
    Returns:
        True 表示写入成功，False 表示数据为空被跳过
    """
    if min_items_key:
        items = data.get(min_items_key, [])
        if not items:
            logging.getLogger(__name__).warning(
                f"数据为空 (key={min_items_key})，跳过写入以保留旧数据: {filepath}"
            )
            return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = filepath.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_file.replace(filepath)
    return True


# ── 美股时区判断 ──
def is_us_market_open() -> bool:
    """判断美股是否在交易时段（自动处理夏令时/冬令时）"""
    try:
        from zoneinfo import ZoneInfo
        now_et = datetime.now(ZoneInfo("America/New_York"))
    except ImportError:
        now_utc = datetime.now(timezone.utc)
        year = now_utc.year
        mar = datetime(year, 3, 1, tzinfo=timezone.utc)
        nov = datetime(year, 11, 1, tzinfo=timezone.utc)
        dst_start = mar + timedelta(days=(6 - mar.weekday() + 7) % 7 + 7)
        dst_end = nov + timedelta(days=(6 - nov.weekday() + 7) % 7)
        is_dst = dst_start <= now_utc.replace(tzinfo=timezone.utc) < dst_end
        et_offset = timedelta(hours=-4 if is_dst else -5)
        now_et = now_utc + et_offset
    if now_et.weekday() >= 5:
        return False
    t = now_et.time()
    return t.hour >= 9 and (t.hour < 16 or (t.hour == 16 and t.minute == 0))
