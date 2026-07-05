"""
动态斐波那契回撤区间。

区别于固定的 0.382/0.5/0.618 三线,这里按照当前波动状态(用 BBW 百分位近似代表)
在四档回撤深度之间切换,波动越大,允许的回撤区间越深(避免在强趋势中too tight的
回撤位被直接打穿而"过早入场"):

- 极窄震荡 (BBW百分位 < 20%):  0.382 ~ 0.5   (挤压后动能弱,浅回撤即可)
- 正常 (20%~60%):              0.5   ~ 0.618 (标准回撤区)
- 强趋势 (60%~85%):            0.618 ~ 0.705 (黄金回撤深水区)
- 极端扩张 (>85%):             0.705 ~ 0.786 (追单风险大,更深回撤才考虑入场;
                                              另给出"突破追单"分支,见下方)
"""
from __future__ import annotations
from analysis.indicators import bbw_percentile

TIERS = [
    (0.0, 0.20, "弱/挤压", 0.382, 0.5),
    (0.20, 0.60, "正常", 0.5, 0.618),
    (0.60, 0.85, "强趋势", 0.618, 0.705),
    (0.85, 1.01, "极端扩张", 0.705, 0.786),
]


def classify_volatility_tier(klines: list[dict]) -> dict:
    pct = bbw_percentile(klines)
    if pct is None:
        return {"tier": "正常", "percentile": None, "low_ratio": 0.5, "high_ratio": 0.618}
    for lo, hi, name, low_r, high_r in TIERS:
        if lo <= pct < hi:
            return {"tier": name, "percentile": round(pct, 3), "low_ratio": low_r, "high_ratio": high_r}
    return {"tier": "正常", "percentile": round(pct, 3), "low_ratio": 0.5, "high_ratio": 0.618}


def dynamic_fib_zone(swing_high: float, swing_low: float, direction: str, klines: list[dict]) -> dict:
    """
    direction: 'long' 表示预期从回撤低点做多(即回撤发生在上升趋势中,回踩买入);
               'short' 表示预期从回撤高点做空(下降趋势中反弹卖出)。
    返回一个价格区间 (zone_low, zone_high) + 使用的回撤比例 + 波动分档信息。
    另外提供"突破追单分支"字段:在极端扩张档位下,给出如果价格不回撤、直接突破结构位的替代入场逻辑。
    """
    tier_info = classify_volatility_tier(klines)
    diff = swing_high - swing_low
    low_r, high_r = tier_info["low_ratio"], tier_info["high_ratio"]

    if direction == "long":
        zone_high = swing_high - diff * low_r
        zone_low = swing_high - diff * high_r
        breakout_chase_level = swing_high  # 若不回撤,等待突破前高企稳后反手做多
    else:
        zone_low = swing_low + diff * low_r
        zone_high = swing_low + diff * high_r
        breakout_chase_level = swing_low  # 若不回撤,等待跌破前低企稳后反手做空

    return {
        "zone_low": round(min(zone_low, zone_high), 6),
        "zone_high": round(max(zone_low, zone_high), 6),
        "retracement_ratios": (low_r, high_r),
        "volatility_tier": tier_info,
        "breakout_chase_branch": {
            "condition": f"若价格不回撤至上述区间,{'放量突破并回踩确认' if direction=='long' else '放量跌破并反抽确认'}"
                         f" {breakout_chase_level:.6g} 后可作为追单入场替代方案",
            "level": breakout_chase_level,
        },
    }
