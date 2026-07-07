"""
宏观市场数据:
- DXY 美元指数 (Stooq 免费 CSV)
- 美国10年期国债收益率 (FRED 免费 CSV)
- BTC/ETH 现货 ETF 净流入 (Farside Investors 免费公开表格, HTML结构可能变化,已做容错)
"""
from __future__ import annotations
import csv
import io

from config import STOOQ_DXY_CSV, FRED_DGS10_CSV, FARSIDE_BTC_URL, FARSIDE_ETH_URL
from fetchers.http_client import get_text
from fetchers.html_table import extract_tables, last_numeric_cell


def _parse_stooq_csv(text: str) -> list[dict]:
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def get_dxy_series(lookback: int = 30) -> list[dict]:
    """返回最近 lookback 个交易日的 DXY 收盘价 [{'date':..., 'close':...}]"""
    text = get_text(STOOQ_DXY_CSV)
    rows = _parse_stooq_csv(text)
    out = []
    for r in rows[-lookback:]:
        try:
            out.append({"date": r["Date"], "close": float(r["Close"])})
        except (KeyError, ValueError):
            continue
    return out


def get_dxy_trend() -> dict:
    """简单判断DXY短期趋势:比较最近值与N日前的值。"""
    series = get_dxy_series(lookback=10)
    if len(series) < 2:
        return {"available": False}
    latest = series[-1]["close"]
    prior = series[0]["close"]
    change_pct = (latest - prior) / prior * 100 if prior else 0
    return {
        "available": True,
        "latest": latest,
        "change_pct_10d": round(change_pct, 3),
        # 美元走强通常对风险资产(含加密)偏空,反之偏多——仅作为宏观背景参考
        "bias_for_crypto": "偏空" if change_pct > 0.3 else ("偏多" if change_pct < -0.3 else "中性"),
    }


def get_us10y_yield_trend() -> dict:
    """美债10年期收益率趋势(FRED CSV: DATE,DGS10, 缺失值为 '.')"""
    text = get_text(FRED_DGS10_CSV)
    if not text:
        return {"available": False}
    reader = csv.DictReader(io.StringIO(text))
    rows = [r for r in reader if r.get("DGS10") not in (None, ".", "")]
    if len(rows) < 11:
        return {"available": False}
    recent = rows[-10:]
    try:
        latest = float(recent[-1]["DGS10"])
        prior = float(recent[0]["DGS10"])
    except (KeyError, ValueError):
        return {"available": False}
    change_bp = (latest - prior) * 100
    return {
        "available": True,
        "latest_pct": latest,
        "change_bp_10d": round(change_bp, 1),
        "bias_for_crypto": "偏空" if change_bp > 5 else ("偏多" if change_bp < -5 else "中性"),
    }


def _parse_farside_table(html: str) -> dict:
    """
    健壮版 Farside 表格解析(基于真实DOM结构解析,而非脆弱正则)。

    典型结构:第一行是表头(各ETF代码 + 最后一列 "Total"),之后每行是一个交易日,
    可能有一行首列是"Total"的全期合计行。策略:
    1. 取页面里行数最多的表格(大概率是数据主表)
    2. 表头里找到 "Total" 列 -> 取最近一个数据行的值 = 最近一日净流入
    3. 找首列含"Total"的行 -> 全期累计净流入(如果存在)
    4. 任何一步失败都返回 available: False,不编造数字。
    """
    tables = extract_tables(html)
    if not tables:
        html_len = len(html) if html else 0
        return {"available": False,
                "reason": f"页面未解析出任何<table>结构(收到HTML长度{html_len}字符,"
                         f"若长度异常小可能是被反爬机制拦截返回了挑战页,而非真实表格页面)"}

    main_table = max(tables, key=len, default=None)
    if not main_table or len(main_table) < 2:
        return {"available": False, "reason": "主表格行数不足"}

    header = [c.strip().lower() for c in main_table[0]]
    total_col_idx = None
    for i, cell in enumerate(header):
        if cell == "total" or cell.endswith("total"):
            total_col_idx = i
            break

    result: dict = {"available": False}

    cumulative_row = None
    for row in main_table[1:]:
        if row and "total" in row[0].strip().lower():
            cumulative_row = row
            break
    if cumulative_row and total_col_idx is not None and total_col_idx < len(cumulative_row):
        val = last_numeric_cell([cumulative_row[total_col_idx]])
        if val is not None:
            result["cumulative_total_flow_musd"] = val
            result["available"] = True

    if total_col_idx is not None:
        for row in reversed(main_table[1:]):
            if not row or "total" in row[0].strip().lower():
                continue
            if total_col_idx < len(row):
                val = last_numeric_cell([row[total_col_idx]])
                if val is not None:
                    result["latest_day_flow_musd"] = val
                    result["latest_day_label"] = row[0].strip()
                    result["available"] = True
            break

    if not result["available"]:
        result["reason"] = "解析出表格但未定位到Total列或有效数值,可能是页面结构调整"
    return result


def get_btc_etf_flow() -> dict:
    html = get_text(FARSIDE_BTC_URL)
    result = _parse_farside_table(html)
    result["source"] = FARSIDE_BTC_URL
    return result


def get_eth_etf_flow() -> dict:
    html = get_text(FARSIDE_ETH_URL)
    result = _parse_farside_table(html)
    result["source"] = FARSIDE_ETH_URL
    return result
