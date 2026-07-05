"""
Binance 现货数据抓取,主要用于:
- 现货 vs 永续 基差 (basis)
- 现货 CVD vs 永续 CVD 的背离对比
"""
from __future__ import annotations
from config import BINANCE_SPOT_BASE, KLINE_LIMIT
from fetchers.http_client import get_json
from fetchers.binance_futures import KLINE_COLUMNS


def get_spot_klines(symbol: str, interval: str, limit: int = KLINE_LIMIT) -> list[dict]:
    raw = get_json(
        f"{BINANCE_SPOT_BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
    )
    if not raw:
        return []
    out = []
    for row in raw:
        d = dict(zip(KLINE_COLUMNS, row))
        for k in ("open", "high", "low", "close", "volume", "quote_volume",
                   "taker_buy_base", "taker_buy_quote"):
            d[k] = float(d[k])
        d["trades"] = int(d["trades"])
        out.append(d)
    return out


def get_spot_price(symbol: str) -> float | None:
    data = get_json(f"{BINANCE_SPOT_BASE}/api/v3/ticker/price", params={"symbol": symbol})
    if not data:
        return None
    try:
        return float(data["price"])
    except (KeyError, TypeError, ValueError):
        return None
