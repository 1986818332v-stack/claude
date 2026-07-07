"""
交易计划生成器 v2 —— "永不空仓,极致盈亏比"版本。

核心设计变化(相较v1):
1. 不再因为风险回报比不达标就丢弃计划——只要能找到结构(OB/FVG/摆动点),
   就必须输出一个可执行的剧本,达标与否只作为标注,而不是生杀开关。
2. 入场与止损锁死在低周期(5m优先,其次15m)的 OB/FVG 区间上,止损贴着
   区间边缘 + 很小的ATR缓冲,目的是把止损宽度压到接近1%这个量级。
3. 止盈锚定在高周期流动性池:
   - TP1 = 4小时摆动高/低点(离入场最近的一个,即"最容易被触发的第一段流动性")
   - TP2 = 日线摆动高/低点或未回补的日线级别缺口(更远端的流动性目标)
   这种"窄止损 + 远端流动性目标"的映射结构性地制造出高盈亏比,
   而不是玄学地把目标拍脑袋定在1:10——它就是SMC"从内部结构打向外部流动性"的标准逻辑。
4. 任何一步找不到理想结构时,都有清晰标注的兜底方案(而不是静默返回None),
   保证"只要该标的进入了本轮强制Top N,就一定有点位可看"。
"""
from __future__ import annotations
from config import MIN_RR, TARGET_RR, ATR_SL_MULTIPLIER, MAX_STOP_LOSS_PCT
from analysis.indicators import atr, dynamic_atr_multiplier


def _risk_reward(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    return reward / risk if risk else 0.0


def _nearest_zone(zones: list[dict], current_price: float, direction: str) -> dict | None:
    """从候选OB/FVG区间里选离现价最近的一个(同方向)。"""
    candidates = [z for z in zones if z.get("direction") == direction]
    if not candidates:
        return None
    candidates.sort(key=lambda z: min(abs(current_price - z["zone_low"]), abs(current_price - z["zone_high"])))
    return candidates[0]


def _entry_zone_from_ict(entry_klines: list[dict], ict_detail: dict, direction: str, current_price: float) -> dict:
    """
    找精确入场区间(优先OB,其次FVG)。找不到就退化为"最近一根同方向K线实体区间"
    的兜底方案(明确标注是兜底,而不是伪装成真实结构信号)。
    """
    zones = list(ict_detail.get("order_blocks", [])) + list(ict_detail.get("fair_value_gaps", []))
    zone = _nearest_zone(zones, current_price, direction)
    if zone:
        zone_type = "订单块(OB)" if zone in ict_detail.get("order_blocks", []) else "失衡缺口(FVG)"
        return {"zone_low": zone["zone_low"], "zone_high": zone["zone_high"],
                "zone_type": zone_type, "is_fallback": False}

    # 兜底:用最近3根K线的实体范围模拟一个"临时观察区间"
    recent = entry_klines[-3:] if len(entry_klines) >= 3 else entry_klines
    lows = [min(k["open"], k["close"]) for k in recent]
    highs = [max(k["open"], k["close"]) for k in recent]
    return {"zone_low": min(lows), "zone_high": max(highs),
            "zone_type": "临时观察区间(未找到明确OB/FVG,兜底方案)", "is_fallback": True}


def _htf_target(swings: dict, current_price: float, direction: str, beyond_entry_only: bool = True) -> dict | None:
    """从摆动点里找离现价最近的、且在交易方向一侧的高周期流动性目标。"""
    pool = swings.get("highs", []) if direction == "long" else swings.get("lows", [])
    if not pool:
        return None
    if direction == "long":
        candidates = [p for _, p in pool if p > current_price] if beyond_entry_only else [p for _, p in pool]
        return {"price": min(candidates)} if candidates else None
    else:
        candidates = [p for _, p in pool if p < current_price] if beyond_entry_only else [p for _, p in pool]
        return {"price": max(candidates)} if candidates else None


def build_trade_plan(
    symbol: str,
    entry_klines: list[dict],
    entry_ict_detail: dict,
    direction: str,
    swings_4h: dict,
    swings_1d: dict,
    entry_timeframe_label: str,
) -> dict | None:
    """
    生成"永不空仓"版交易计划。只有在连current_price都拿不到(数据完全缺失)时才返回None。
    """
    if not entry_klines:
        return None
    current_price = entry_klines[-1]["close"]

    entry_zone = _entry_zone_from_ict(entry_klines, entry_ict_detail, direction, current_price)
    zone_low, zone_high = entry_zone["zone_low"], entry_zone["zone_high"]
    entry_mid = (zone_low + zone_high) / 2

    a = atr(entry_klines, period=14) or (current_price * 0.003)
    sl_multiplier = dynamic_atr_multiplier(entry_klines, ATR_SL_MULTIPLIER)

    if direction == "long":
        stop = zone_low - a * sl_multiplier
        confirm = (f"价格进入 {zone_low:.6g} ~ {zone_high:.6g}({entry_zone['zone_type']})后,"
                   f"出现收盘价高于区间上沿的看涨确认K线,或该区间放量至近20根均量1.3倍以上")
    else:
        stop = zone_high + a * sl_multiplier
        confirm = (f"价格进入 {zone_low:.6g} ~ {zone_high:.6g}({entry_zone['zone_type']})后,"
                   f"出现收盘价低于区间下沿的看跌确认K线,或该区间放量至近20根均量1.3倍以上")

    stop_pct = abs(entry_mid - stop) / entry_mid * 100 if entry_mid else 0

    # ---- TP1: 4小时流动性池(最近的一段) ----
    tp1_target = _htf_target(swings_4h, entry_mid, direction)
    risk = abs(entry_mid - stop) or (entry_mid * 0.01)
    if tp1_target:
        tp1 = tp1_target["price"]
        tp1_is_fallback = False
    else:
        tp1 = entry_mid + risk * MIN_RR if direction == "long" else entry_mid - risk * MIN_RR
        tp1_is_fallback = True

    # ---- TP2: 日线流动性池(更远端目标) ----
    tp2_target = _htf_target(swings_1d, entry_mid, direction)
    if tp2_target and abs(tp2_target["price"] - entry_mid) > abs(tp1 - entry_mid):
        tp2 = tp2_target["price"]
        tp2_is_fallback = False
    else:
        tp2 = entry_mid + risk * TARGET_RR if direction == "long" else entry_mid - risk * TARGET_RR
        tp2_is_fallback = True

    rr1 = _risk_reward(entry_mid, stop, tp1)
    rr2 = _risk_reward(entry_mid, stop, tp2)

    return {
        "symbol": symbol,
        "line": f"SMC精确入场({entry_timeframe_label}结构 → HTF流动性目标)",
        "timeframe_basis": entry_timeframe_label,
        "zone_type": entry_zone["zone_type"],
        "direction": "做多" if direction == "long" else "做空",
        "entry_zone": [round(zone_low, 6), round(zone_high, 6)],
        "confirmation": confirm,
        "stop_loss": round(stop, 6),
        "stop_loss_pct": round(stop_pct, 3),
        "stop_within_target_range": stop_pct <= MAX_STOP_LOSS_PCT,
        "tp1": round(tp1, 6),
        "tp1_is_fallback": tp1_is_fallback,
        "tp1_risk_reward": round(rr1, 2),
        "tp2": round(tp2, 6),
        "tp2_is_fallback": tp2_is_fallback,
        "tp2_risk_reward": round(rr2, 2),
        "meets_rr_threshold": rr1 >= MIN_RR,
        "extreme_rr_achieved": rr2 >= TARGET_RR,
        "entry_zone_is_fallback": entry_zone["is_fallback"],
        "volatility_sl_note": f"止损缓冲已按波动率修正(ATR倍数={sl_multiplier})",
    }
