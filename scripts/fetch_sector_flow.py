#!/usr/bin/env python3
"""
抓取行业板块资金流向数据
- 实时板块主力净流入 → data/sector_flow.json (groups)
- 日/周/月K线 → data/sector_flow.json (timeline)
数据源：东方财富 push2/push2his API
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "sector_flow.json"

EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
TZ_BEIJING = timezone(timedelta(hours=8))

# 板块大类分组
SECTOR_GROUPS = {
    "科技电子": ["BK0489", "BK0477", "BK0479", "BK0487", "BK0438", "BK0481", "BK0465"],
    "医药": ["BK0451", "BK0467", "BK0447", "BK0480"],
    "金融": ["BK0449", "BK0473", "BK0488"],
    "消费": ["BK0445", "BK0484", "BK0456", "BK0483"],
    "周期资源": ["BK0493", "BK0435", "BK0476", "BK0453", "BK0442", "BK0434"],
    "地产基建": ["BK0432", "BK0443"],
    "新能源": ["BK0440", "BK0448", "BK0494", "BK0495"],
}

# 各类代表板块（用于K线时间轴）
GROUP_REPS = {
    "科技电子": "BK0489", "医药": "BK0480", "金融": "BK0488",
    "消费": "BK0445", "周期资源": "BK0435", "地产基建": "BK0432", "新能源": "BK0494",
}

ALL_SECTORS = []
for codes in SECTOR_GROUPS.values():
    ALL_SECTORS.extend(codes)


def fetch_sector_inflow():
    """获取所有板块的主力净流入"""
    secids = ",".join(f"90.{c}" for c in ALL_SECTORS)
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f2,f3,f4,f6,f12,f14,f62",
        "secids": secids,
    }
    resp = requests.get(EASTMONEY_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("rc") != 0:
        raise ValueError(f"API error: rc={data.get('rc')}")

    diff = data.get("data", {}).get("diff", [])
    sector_map = {item["f12"]: item for item in diff}

    # 按大类汇总
    groups = []
    for group_name, codes in SECTOR_GROUPS.items():
        total_inflow = 0
        details = []
        for code in codes:
            item = sector_map.get(code)
            if item:
                inflow = item.get("f62", 0) or 0  # 主力净流入（元）
                total_inflow += inflow
                details.append({
                    "code": code,
                    "name": item.get("f14", ""),
                    "netInflow": round(inflow / 1e8, 2),  # 转为亿元
                    "changePct": item.get("f3", 0),
                })
        groups.append({
            "name": group_name,
            "netInflow": round(total_inflow / 1e8, 2),  # 转为亿元
            "details": sorted(details, key=lambda x: x["netInflow"], reverse=True),
        })

    return groups


def fetch_kline(secid, klt, lmt):
    """获取板块K线数据"""
    params = {
        "secid": secid,
        "klt": klt,  # 101日/102周/103月
        "fqt": "1",
        "end": "20500101",
        "lmt": str(lmt),
        "fields1": "f1,f2,f3",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    resp = requests.get(KLINE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("klines", [])


def build_timeline():
    """构建日/周/月/季/年的时间轴数据"""
    timeline = {}

    for klt_key, klt, lmt in [("101", "101", 30), ("102", "102", 26), ("103", "103", 60)]:
        dates = []
        series_data = {g: [] for g in GROUP_REPS.keys()}

        for group, code in GROUP_REPS.items():
            klines = fetch_kline(f"90.{code}", klt, lmt)
            parsed = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 6:
                    parsed.append({
                        "date": parts[0],
                        "close": float(parts[2]),
                        "volume": float(parts[5]),
                    })

            # 计算资金流向代理：成交量 * 涨跌幅
            flow_data = []
            for i, p in enumerate(parsed):
                if i == 0:
                    flow_data.append({"date": p["date"], "flow": 0})
                else:
                    prev = parsed[i - 1]
                    chg = (p["close"] - prev["close"]) / prev["close"] * 100 if prev["close"] > 0 else 0
                    flow = round(p["volume"] * chg / 1e8, 2)
                    flow_data.append({"date": p["date"], "flow": flow})

            if len(flow_data) > len(dates):
                dates = [p["date"] for p in flow_data]

            series_data[group] = flow_data

        # 对齐数据
        all_dates = dates
        for group in series_data:
            flow_map = {p["date"]: p["flow"] for p in series_data[group]}
            series_data[group] = [flow_map.get(d, 0) for d in all_dates]

        timeline[klt_key] = {"dates": all_dates, "series": series_data}
        time.sleep(0.3)  # 避免请求过快

    # 季度和年度：从月线聚合
    if "103" in timeline:
        monthly = timeline["103"]
        dates_m = monthly["dates"]
        series_m = monthly["series"]

        # 季度聚合
        quarter_dates = []
        quarter_series = {g: [] for g in series_m}
        for i in range(0, len(dates_m), 3):
            chunk = dates_m[i:i + 3]
            if not chunk:
                continue
            q = (int(chunk[0][5:7]) - 1) // 3 + 1
            label = f"{chunk[0][:4]}Q{q}"
            quarter_dates.append(label)
            for g in series_m:
                quarter_series[g].append(round(sum(series_m[g][i:i + 3]), 2))
        timeline["quarter"] = {"dates": quarter_dates, "series": quarter_series}

        # 年度聚合
        year_dates = []
        year_series = {g: [] for g in series_m}
        year_set = set()
        for i, d in enumerate(dates_m):
            year_set.add(d[:4])
        for y in sorted(year_set):
            year_dates.append(y)
            for g in series_m:
                year_series[g].append(round(sum(series_m[g][i] for i, d in enumerate(dates_m) if d[:4] == y), 2))
        timeline["year"] = {"dates": year_dates, "series": year_series}

    return timeline


def main():
    logger.info("=" * 50)
    logger.info("开始抓取行业板块资金流向数据")
    logger.info("=" * 50)

    start = time.time()
    now = datetime.now(TZ_BEIJING)

    # 1. 获取实时板块资金流向
    logger.info("抓取板块主力净流入...")
    groups = fetch_sector_inflow()
    logger.info(f"获取 {len(groups)} 个大类板块资金数据")

    # 2. 获取K线时间轴
    logger.info("抓取板块K线时间轴...")
    timeline = build_timeline()
    logger.info(f"获取 {len(timeline)} 个时间维度数据")

    # 3. 保存
    output = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "groups": groups,
        "timeline": timeline,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = OUTPUT_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp_file.replace(OUTPUT_FILE)

    elapsed = time.time() - start
    logger.info(f"数据已保存到 {OUTPUT_FILE} (耗时 {elapsed:.1f}s)")
    logger.info(f"  板块组数: {len(groups)}")
    logger.info(f"  时间维度: {list(timeline.keys())}")


if __name__ == "__main__":
    main()
