"""
高周期(HTF)关键位 与 流动性池映射。

Institutional 剧本的核心假设:大资金的入场/离场,大概率发生在
"散户止损/止盈密集的价格区域"附近——也就是前一日高低点(PDH/PDL)、
前一周高低点(PWH/PWL)这些"所有人都看得到"的水平线上方/下方一点点。

本模块做两件事:
1. 计算 PDH/PDL(Previous Day High/Low)、PWH/PWL(Previous Week High/Low)
2. 判断当前(低周期)是否正好发生在这些高周期关键位附近的流动性扫荡——
   如果是,这是一个"低周期信号 + 高周期剧本"共振的强证据,应该提升置信度。
"""
from __future__ import annotations
from fetchers import binance_futures as bf


def get_htf_key_levels(symbol: str) -> dict:
    """拉取日线和周线K线,计算前一日/前一周的高低点。"""
    daily = bf.get_klines(symbol, "1d", limit=10)
    weekly = bf.get_klines(symbol, "1w", limit=6)

    levels = {}
    if len(daily) >= 2:
        prev_day = daily[-2]  # 最后一根通常是"当前未走完"的日线,取前一根
        levels["PDH"] = prev_day["high"]
        levels["PDL"] = prev_day["low"]
    if len(weekly) >= 2:
        prev_week = weekly[-2]
        levels["PWH"] = prev_week["high"]
        levels["PWL"] = prev_week["low"]
    return levels


def check_liquidity_pool_confluence(current_price: float, key_levels: dict, tolerance_pct: float = 0.3) -> dict:
    """
    判断当前价格是否处于某个高周期关键位附近(±tolerance_pct%),
    这代表"流动性池"就在附近,低周期的扫荡/反转信号如果发生在这里,可信度更高。
    返回命中的关键位列表 + 一个可加到主控判定的置信度加成分数。
    """
    hits = []
    for name, level in key_levels.items():
        if level <= 0:
            continue
        distance_pct = abs(current_price - level) / level * 100
        if distance_pct <= tolerance_pct:
            hits.append({"level_name": name, "level_price": level, "distance_pct": round(distance_pct, 3)})

    # 命中越多重关键位(比如同时接近PDH和PWH),置信度加成越高,封顶0.4
    confidence_boost = min(0.4, 0.2 * len(hits))
    return {"hits": hits, "confidence_boost": confidence_boost}


def analyze(symbol: str, current_price: float) -> dict:
    key_levels = get_htf_key_levels(symbol)
    if not key_levels:
        return {"available": False}
    confluence = check_liquidity_pool_confluence(current_price, key_levels)
    return {
        "available": True,
        "key_levels": key_levels,
        "confluence": confluence,
    }
