"""
组合风险暴露 (Portfolio Risk Exposure)。

问题场景:扫描器独立给 BTC、ETH、SOL 都输出"做空"计划,三个仓位各自看起来
风险回报比都合格,但它们高度相关——一旦发生空头挤压(Short Squeeze),
账户是同时三个仓位一起爆仓,而不是三个独立的1/3仓位风险。

本模块不做仓位管理本身(那是用户自己的资金曲线决定的),只做"共振风险提示":
统计本轮报告里最终展示的标的,同方向的比例是否过高,超过阈值就在报告顶部
加一条醒目警告,并建议对同板块/同方向标的降低单笔风险或合并看待。
"""
from __future__ import annotations

# 极简板块映射(可按需扩充)。不在列表里的默认归为"其他"。
SECTOR_MAP = {
    "BTCUSDT": "主流币", "ETHUSDT": "主流币",
    "SOLUSDT": "L1公链", "AVAXUSDT": "L1公链", "SUIUSDT": "L1公链", "APTUSDT": "L1公链",
    "BNBUSDT": "交易所生态",
    "DOGEUSDT": "Meme", "SHIBUSDT": "Meme", "PEPEUSDT": "Meme", "WIFUSDT": "Meme",
    "LINKUSDT": "预言机/基础设施", "OPUSDT": "L2", "ARBUSDT": "L2",
}


def sector_of(symbol: str) -> str:
    return SECTOR_MAP.get(symbol, "其他")


def analyze_portfolio_risk(results: list[dict], direction_threshold: float = 0.6) -> dict:
    """
    results: main.py 里已经生成好交易计划的标的列表(每个含 symbol + verdict.direction)
    只统计"有具体入场计划"(plans非空)的标的,忽略纯观察名单。
    """
    active = [r for r in results if r.get("plans")]
    if len(active) < 2:
        return {"warning": None, "long_count": 0, "short_count": 0, "sector_clusters": {}}

    long_syms = [r["symbol"] for r in active if r["verdict"]["direction"] in ("看多", "偏多")]
    short_syms = [r["symbol"] for r in active if r["verdict"]["direction"] in ("看空", "偏空")]

    total = len(active)
    long_ratio = len(long_syms) / total
    short_ratio = len(short_syms) / total

    sector_clusters: dict[str, list[str]] = {}
    for r in active:
        sec = sector_of(r["symbol"])
        sector_clusters.setdefault(sec, []).append(r["symbol"])

    warning = None
    if long_ratio >= direction_threshold and len(long_syms) >= 3:
        warning = (f"⚠️ 本轮 {len(long_syms)}/{total} 个标的同为看多方向({', '.join(long_syms)}),"
                   f"高度同质化仓位存在'多头挤压反转'时集中回撤的风险,建议对同板块标的合并计算总风险敞口"
                   f"(而非按每个标的独立的1倍风险叠加),或降低单笔仓位比例。")
    elif short_ratio >= direction_threshold and len(short_syms) >= 3:
        warning = (f"⚠️ 本轮 {len(short_syms)}/{total} 个标的同为看空方向({', '.join(short_syms)}),"
                   f"高度同质化仓位存在'空头挤压(Short Squeeze)'时集中爆仓的风险,建议对同板块标的合并计算总风险敞口"
                   f"(而非按每个标的独立的1倍风险叠加),或降低单笔仓位比例。")

    # 板块内部同向聚集提示(即便总体没超阈值,单个板块内部同向也值得提示)
    sector_warnings = []
    for sec, syms in sector_clusters.items():
        if len(syms) >= 2 and sec != "其他":
            sector_warnings.append(f"{sec}板块本轮同时有 {len(syms)} 个标的入选({', '.join(syms)}),注意板块联动风险")

    return {
        "warning": warning,
        "sector_warnings": sector_warnings,
        "long_count": len(long_syms),
        "short_count": len(short_syms),
        "sector_clusters": sector_clusters,
    }
