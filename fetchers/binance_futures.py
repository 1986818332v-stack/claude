"""
Binance USDT-M 永续合约数据抓取。
全部使用公开(无需 API Key)的 REST 端点:
- /fapi/v1/exchangeInfo      全市场合约信息
- /fapi/v1/ticker/24hr       24h 行情(用于按成交量粗排)
- /fapi/v1/klines            K线
- /fapi/v1/premiumIndex      标记价格 + 资金费率(实时预测值)
- /fapi/v1/fundingRate       历史资金费率
- /fapi/v1/openInterest      当前持仓量
- /fapi/v1/depth             订单簿深度
"""
from __future__ import annotations
from config import BINANCE_FUTURES_BASE, QUOTE_ASSET, MIN_24H_QUOTE_VOLUME, KLINE_LIMIT
from fetchers.http_client import get_json

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]


def get_all_usdt_perpetual_symbols() -> list[str]:
    """返回所有状态为 TRADING 的 USDT 本位永续合约 symbol 列表。"""
    data = get_json(f"{BINANCE_FUTURES_BASE}/fapi/v1/exchangeInfo")
    if not data:
        return []
    symbols = []
    for s in data.get("symbols", []):
        if (
            s.get("quoteAsset") == QUOTE_ASSET
            and s.get("contractType") == "PERPETUAL"
            and s.get("status") == "TRADING"
        ):
            symbols.append(s["symbol"])
    return symbols


def get_24h_tickers() -> dict[str, dict]:
    """返回 {symbol: ticker_dict},用于按成交量粗排。"""
    data = get_json(f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/24hr")
    if not data:
        return {}
    return {d["symbol"]: d for d in data if "symbol" in d}


def rank_symbols_by_volume(symbols: list[str], tickers: dict[str, dict], top_n: int) -> list[str]:
    """按 quoteVolume 过滤并排序,返回前 top_n 个交易对。"""
    scored = []
    for sym in symbols:
        t = tickers.get(sym)
        if not t:
            continue
        try:
            qv = float(t.get("quoteVolume", 0))
        except (TypeError, ValueError):
            continue
        if qv >= MIN_24H_QUOTE_VOLUME:
            scored.append((sym, qv))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in scored[:top_n]]


def get_klines(symbol: str, interval: str, limit: int = KLINE_LIMIT) -> list[dict]:
    """返回该 symbol/周期的K线,已转成 dict 列表(数值字段转 float)。"""
    raw = get_json(
        f"{BINANCE_FUTURES_BASE}/fapi/v1/klines",
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


def get_premium_index(symbol: str) -> dict | None:
    """标记价格 + 实时预测资金费率。"""
    return get_json(f"{BINANCE_FUTURES_BASE}/fapi/v1/premiumIndex", params={"symbol": symbol})


def get_funding_rate_history(symbol: str, limit: int = 8) -> list[dict]:
    """最近若干期历史资金费率(每8小时一期),用于判断趋势而非单点。"""
    data = get_json(
        f"{BINANCE_FUTURES_BASE}/fapi/v1/fundingRate",
        params={"symbol": symbol, "limit": limit},
    )
    return data or []


def get_open_interest(symbol: str) -> dict | None:
    return get_json(f"{BINANCE_FUTURES_BASE}/fapi/v1/openInterest", params={"symbol": symbol})


def get_order_book(symbol: str, limit: int = 500) -> dict | None:
    return get_json(f"{BINANCE_FUTURES_BASE}/fapi/v1/depth", params={"symbol": symbol, "limit": limit})
