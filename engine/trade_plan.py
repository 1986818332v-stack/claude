"""
交易计划生成器。

核心原则(源自用户已确立的交易哲学,必须严格遵守):
  入场永远表达为一个价格区间(有明确上下界)+ 一个确认条件(特定K线形态或成交量阈值),
  绝不是单一价格点。Line 1 = 短线抢短/剥头皮设置,Line 2 = 结构性波段设置。
  任何一条计划如果算出来的风险回报比 < config.MIN_RR,直接丢弃,不展示给用户
  (宁可"暂无合适方案"也不能硬凑一个低质量计划)。
"""
from __future__ import annotations
from config import MIN_RR, TARGET_RR, ATR_SL_MULTIPLIER
from analysis.indicators import atr
from analysis.fib_zones import dynamic_fib_zone


def _risk_reward(entry_mid: float, stop: float, target: float) -> float:
    risk = abs(entry_mid - stop)
    reward = abs(target - entry_mid)
    return reward / risk if risk else 0.0


def build_scalp_plan(symbol: str, klines_15m: list[dict], ict_detail: dict, direction: str) -> dict | None:
    """
    Line 1 短线计划:基于最近的 Order Block / FVG 区间(离现价最近的一个),
    止损放在结构区间之外 + ATR缓冲,确认条件用"该区间内出现与方向一致的收盘K线"。
    """
    if not klines_15m:
        return None
    last_price = klines_15m[-1]["close"]
    a = atr(klines_15m, period=14)
    if a is None:
        return None

    candidates = []
    for ob in ict_detail.get("order_blocks", []):
        if ob["direction"] == direction:
            candidates.append((ob["zone_low"], ob["zone_high"], "订单块(Order Block)"))
    for fvg in ict_detail.get("fair_value_gaps", []):
        if fvg["direction"] == direction:
            candidates.append((fvg["zone_low"], fvg["zone_high"], "失衡缺口(FVG)"))

    if not candidates:
        return None

    # 选离现价最近的一个区间(短线更看重"够近、能被打到")
    candidates.sort(key=lambda z: min(abs(last_price - z[0]), abs(last_price - z[1])))
    zone_low, zone_high, zone_type = candidates[0]

    if direction == "long":
        stop = zone_low - a * ATR_SL_MULTIPLIER
        entry_mid = (zone_low + zone_high) / 2
        target = entry_mid + (entry_mid - stop) * TARGET_RR
        confirm = f"价格进入 {zone_low:.6g} ~ {zone_high:.6g} 区间后,出现一根收盘价高于区间上沿的看涨确认K线,或该区间成交量放大至近20根均量的1.5倍以上"
    else:
        stop = zone_high + a * ATR_SL_MULTIPLIER
        entry_mid = (zone_low + zone_high) / 2
        target = entry_mid - (stop - entry_mid) * TARGET_RR
        confirm = f"价格进入 {zone_low:.6g} ~ {zone_high:.6g} 区间后,出现一根收盘价低于区间下沿的看跌确认K线,或该区间成交量放大至近20根均量的1.5倍以上"

    rr = _risk_reward(entry_mid, stop, target)
    if rr < MIN_RR:
        return None

    return {
        "line": "Line 1 (短线/剥头皮)",
        "timeframe_basis": "15m",
        "zone_type": zone_type,
        "direction": "做多" if direction == "long" else "做空",
        "entry_zone": [round(zone_low, 6), round(zone_high, 6)],
        "confirmation": confirm,
        "stop_loss": round(stop, 6),
        "target": round(target, 6),
        "risk_reward": round(rr, 2),
    }


def build_swing_plan(symbol: str, klines_4h: list[dict], swings: dict, direction: str) -> dict | None:
    """
    Line 2 结构性波段计划:基于4h最近一次摆动高低点之间的动态斐波那契回撤区间。
    止损放在结构摆动点之外, 确认条件用"放量企稳确认"而非单纯触及区间。
    """
    if not klines_4h or len(swings.get("highs", [])) < 1 or len(swings.get("lows", [])) < 1:
        return None
    last_price = klines_4h[-1]["close"]
    a = atr(klines_4h, period=14)
    if a is None:
        return None

    swing_high = swings["highs"][-1][1]
    swing_low = swings["lows"][-1][1]
    if swing_high <= swing_low:
        return None

    fib = dynamic_fib_zone(swing_high, swing_low, direction, klines_4h)
    zone_low, zone_high = fib["zone_low"], fib["zone_high"]
    entry_mid = (zone_low + zone_high) / 2

    if direction == "long":
        stop = swing_low - a * ATR_SL_MULTIPLIER
        target = entry_mid + (entry_mid - stop) * TARGET_RR
        confirm = (f"价格回撤至 {zone_low:.6g} ~ {zone_high:.6g}({fib['volatility_tier']['tier']}波动档位,"
                   f"{fib['retracement_ratios'][0]:.3f}~{fib['retracement_ratios'][1]:.3f}回撤区)后,"
                   f"出现4h级别看涨吞没或长下影线确认K线,且成交量不低于近10根均量")
    else:
        stop = swing_high + a * ATR_SL_MULTIPLIER
        target = entry_mid - (stop - entry_mid) * TARGET_RR
        confirm = (f"价格反弹至 {zone_low:.6g} ~ {zone_high:.6g}({fib['volatility_tier']['tier']}波动档位,"
                   f"{fib['retracement_ratios'][0]:.3f}~{fib['retracement_ratios'][1]:.3f}回撤区)后,"
                   f"出现4h级别看跌吞没或长上影线确认K线,且成交量不低于近10根均量")

    rr = _risk_reward(entry_mid, stop, target)
    if rr < MIN_RR:
        return None

    return {
        "line": "Line 2 (结构性波段)",
        "timeframe_basis": "4h",
        "zone_type": f"动态斐波那契回撤({fib['volatility_tier']['tier']})",
        "direction": "做多" if direction == "long" else "做空",
        "entry_zone": [round(zone_low, 6), round(zone_high, 6)],
        "confirmation": confirm,
        "stop_loss": round(stop, 6),
        "target": round(target, 6),
        "risk_reward": round(rr, 2),
        "breakout_chase_branch": fib["breakout_chase_branch"],
        "current_price": round(last_price, 6),
    }
