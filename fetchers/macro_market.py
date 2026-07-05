"""
宏观市场数据:
- DXY 美元指数 (Stooq 免费 CSV)
- 美国10年期国债收益率 (FRED 免费 CSV)
- BTC/ETH 现货 ETF 净流入 (Farside Investors 免费公开表格, HTML结构可能变化,已做容错)
"""
from __future__ import annotations
import csv
import io
import re

from config import STOOQ_DXY_CSV, FRED_DGS10_CSV, FARSIDE_BTC_URL, FARSIDE_ETH_URL
from fetchers.http_client import get_text


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
    极简、容错优先的 Farside 表格解析:只尝试抓取"Total"行的最近一次净流入数值(百万美元)。
    Farside 的 HTML 结构可能随时调整,这里不做强依赖,解析失败就返回 available: False,
    报告中会明确标注"ETF资金流数据暂不可用",而不是编造数字。
    """
    if not html:
        return {"available": False}
    # 尝试用简单正则找到形如 Total ... 的一行里最后一个数字(百万美元, 可能带负号/逗号)
    match = re.search(r"Total[^\n<]*?(-?[\d,]+\.?\d*)\s*</td>\s*</tr>", html, re.IGNORECASE)
    if not match:
        return {"available": False}
    try:
        value = float(match.group(1).replace(",", ""))
        return {"available": True, "latest_total_flow_musd": value}
    except ValueError:
        return {"available": False}


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
