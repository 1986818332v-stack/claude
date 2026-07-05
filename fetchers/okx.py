"""
OKX 公开数据(无需 key),用于多交易所订单簿墙对比。
symbol 需要从 Binance 的 'BTCUSDT' 转换成 OKX 的 'BTC-USDT-SWAP' 格式,
转换规则做了尽力而为的处理,失败就返回 None,不影响主流程。
"""
from __future__ import annotations
from config import OKX_BASE
from fetchers.http_client import get_json


def binance_symbol_to_okx_instid(binance_symbol: str) -> str | None:
    """'BTCUSDT' -> 'BTC-USDT-SWAP'。仅支持 USDT 本位。"""
    if not binance_symbol.endswith("USDT"):
        return None
    base = binance_symbol[:-4]
    return f"{base}-USDT-SWAP"


def get_order_book(binance_symbol: str, depth: int = 100) -> dict | None:
    inst_id = binance_symbol_to_okx_instid(binance_symbol)
    if not inst_id:
        return None
    data = get_json(
        f"{OKX_BASE}/api/v5/market/books",
        params={"instId": inst_id, "sz": depth},
    )
    if not data or data.get("code") != "0":
        return None
    return data.get("data", [None])[0]


def get_funding_rate(binance_symbol: str) -> dict | None:
    inst_id = binance_symbol_to_okx_instid(binance_symbol)
    if not inst_id:
        return None
    data = get_json(
        f"{OKX_BASE}/api/v5/public/funding-rate",
        params={"instId": inst_id},
    )
    if not data or data.get("code") != "0":
        return None
    items = data.get("data", [])
    return items[0] if items else None
