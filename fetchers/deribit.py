"""
Deribit 期权市场数据(免费公开API,无需Key)。

用于近似计算 BTC/ETH 的期权市场情绪:
- Put/Call 未平仓量比例(PCR):>1 表示看跌期权持仓更多,通常代表对冲/看跌情绪升温
- 简化版 25Delta偏斜近似:由于精确计算25Delta需要完整的期权定价模型(Black-Scholes
  + 无风险利率 + 正确的delta反推),这里做一个更容易验证、更透明的近似——
  取最近到期日、行权价在现价 ±15% 范围内的期权,比较看跌期权与看涨期权的平均
  隐含波动率(mark_iv),差值为正代表看跌期权更贵(市场为下跌风险支付更高保费,
  即传统意义上的"负偏斜/看跌偏斜"存在且在加剧)。
  这不是机构级精确的25D risk reversal,但方向性参考有效,且计算过程完全透明可核对。
"""
from __future__ import annotations
from fetchers.http_client import get_json

DERIBIT_BASE = "https://www.deribit.com/api/v2"


def get_index_price(currency: str) -> float | None:
    data = get_json(f"{DERIBIT_BASE}/public/get_index_price", params={"index_name": f"{currency.lower()}_usd"})
    if not data or "result" not in data:
        return None
    return data["result"].get("index_price")


def get_option_book_summary(currency: str) -> list[dict]:
    data = get_json(f"{DERIBIT_BASE}/public/get_book_summary_by_currency",
                     params={"currency": currency, "kind": "option"})
    if not data or "result" not in data:
        return []
    return data["result"]


def _parse_instrument_name(name: str) -> dict | None:
    # Deribit期权命名格式: BTC-27JUN26-70000-C
    parts = name.split("-")
    if len(parts) != 4:
        return None
    try:
        strike = float(parts[2])
    except ValueError:
        return None
    return {"expiry": parts[1], "strike": strike, "option_type": parts[3]}


def compute_options_sentiment(currency: str, strike_range_pct: float = 15.0) -> dict:
    index_price = get_index_price(currency)
    summary = get_option_book_summary(currency)
    if not index_price or not summary:
        return {"available": False, "reason": "Deribit数据获取失败或期权链为空"}

    # 找到最近到期日(样本量最大的一个到期日,近似"最活跃的近月合约")
    expiry_counts: dict[str, int] = {}
    parsed_rows = []
    for row in summary:
        info = _parse_instrument_name(row.get("instrument_name", ""))
        if not info:
            continue
        parsed_rows.append({**info, **row})
        expiry_counts[info["expiry"]] = expiry_counts.get(info["expiry"], 0) + 1

    if not parsed_rows:
        return {"available": False, "reason": "期权合约名称解析失败"}

    nearest_expiry = max(expiry_counts, key=expiry_counts.get)
    lo = index_price * (1 - strike_range_pct / 100)
    hi = index_price * (1 + strike_range_pct / 100)

    near_money = [r for r in parsed_rows
                  if r["expiry"] == nearest_expiry and lo <= r["strike"] <= hi
                  and r.get("mark_iv") is not None]

    puts = [r for r in near_money if r["option_type"] == "P"]
    calls = [r for r in near_money if r["option_type"] == "C"]

    if not puts or not calls:
        return {"available": False, "reason": "该到期日附近的put/call样本不足"}

    avg_put_iv = sum(r["mark_iv"] for r in puts) / len(puts)
    avg_call_iv = sum(r["mark_iv"] for r in calls) / len(calls)
    skew = avg_put_iv - avg_call_iv  # 正值 = 看跌偏斜(put更贵)

    total_put_oi = sum(r.get("open_interest", 0) or 0 for r in parsed_rows if r["option_type"] == "P")
    total_call_oi = sum(r.get("open_interest", 0) or 0 for r in parsed_rows if r["option_type"] == "C")
    pcr = (total_put_oi / total_call_oi) if total_call_oi else None

    return {
        "available": True,
        "nearest_expiry": nearest_expiry,
        "index_price": index_price,
        "iv_skew_approx": round(skew, 3),
        "avg_put_iv": round(avg_put_iv, 3),
        "avg_call_iv": round(avg_call_iv, 3),
        "put_call_oi_ratio": round(pcr, 3) if pcr is not None else None,
        "sample_size": {"puts": len(puts), "calls": len(calls)},
    }


def options_sentiment_score(sentiment: dict) -> float | None:
    """把偏斜/PCR转换为 [-1,1] 的方向性分数,供 verdict 引擎使用。"""
    if not sentiment.get("available"):
        return None
    score = 0.0
    skew = sentiment.get("iv_skew_approx", 0)
    # 偏斜越正(看跌期权IV显著更贵),情绪越谨慎/偏空;偏斜为负则偏多
    score -= max(-0.5, min(0.5, skew / 10))

    pcr = sentiment.get("put_call_oi_ratio")
    if pcr is not None:
        if pcr > 1.3:
            score -= 0.3
        elif pcr < 0.7:
            score += 0.3
    return max(-1.0, min(1.0, score))
