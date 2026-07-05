"""
ICT (Inner Circle Trader) / SMC (Smart Money Concepts) 结构分析。

实现的核心概念:
1. 摆动高低点 (Swing High/Low) —— 用简单分形 (fractal) 方法识别
2. BOS (Break of Structure) / CHoCH (Change of Character) —— 趋势延续 vs 反转信号
3. FVG (Fair Value Gap / 失衡缺口) —— 三根K线的价格跳空
4. Order Block (订单块) —— 造成结构突破前的最后一根反向K线
5. Liquidity Sweep (流动性扫荡 / 止损猎杀) —— 刺破前高/前低后迅速收回

说明:这是规则化的近似实现,不是 ICT 官方"标准答案"(ICT概念本身也没有
唯一权威量化定义),用于生成可解释、可回测迭代的结构信号,而不是玄学黑箱。
"""
from __future__ import annotations


def find_swing_points(klines: list[dict], left: int = 2, right: int = 2) -> dict:
    """
    分形摆动点:第 i 根K线的 high 大于左右各 `left`/`right` 根的 high => 摆动高点。
    返回 {'highs': [(index, price), ...], 'lows': [(index, price), ...]}
    """
    highs, lows = [], []
    n = len(klines)
    for i in range(left, n - right):
        window = klines[i - left:i + right + 1]
        h = klines[i]["high"]
        l = klines[i]["low"]
        if h == max(k["high"] for k in window):
            highs.append((i, h))
        if l == min(k["low"] for k in window):
            lows.append((i, l))
    return {"highs": highs, "lows": lows}


def detect_bos_choch(klines: list[dict], swings: dict) -> dict:
    """
    简化的 BOS/CHoCH 判定:
    - 取最近两个摆动高点、两个摆动低点
    - 若价格收盘突破最近一个摆动高点 且此前趋势是上升 -> BOS(看涨延续)
    - 若在下降趋势中突破摆动高点 -> CHoCH(看涨反转信号)
    - 对称地处理向下突破
    """
    highs, lows = swings["highs"], swings["lows"]
    if len(highs) < 2 or len(lows) < 2 or not klines:
        return {"signal": None}

    last_close = klines[-1]["close"]
    last_two_highs = [h[1] for h in highs[-2:]]
    last_two_lows = [l[1] for l in lows[-2:]]

    # 用最近两个摆动高/低点的相对高低,推断当前趋势方向(简化)
    uptrend = last_two_highs[-1] > last_two_highs[-2] and last_two_lows[-1] > last_two_lows[-2]
    downtrend = last_two_highs[-1] < last_two_highs[-2] and last_two_lows[-1] < last_two_lows[-2]

    recent_high = last_two_highs[-1]
    recent_low = last_two_lows[-1]

    if last_close > recent_high:
        signal = "BOS_看涨延续" if uptrend else ("CHoCH_看涨反转" if downtrend else "突破前高_趋势不明")
        return {"signal": signal, "direction": "long", "level": recent_high}
    if last_close < recent_low:
        signal = "BOS_看跌延续" if downtrend else ("CHoCH_看跌反转" if uptrend else "突破前低_趋势不明")
        return {"signal": signal, "direction": "short", "level": recent_low}
    return {"signal": None, "trend_guess": "up" if uptrend else ("down" if downtrend else "range")}


def detect_fvg(klines: list[dict], lookback: int = 50) -> list[dict]:
    """
    Fair Value Gap: 三根连续K线中,
    - 看涨FVG: candle[i-2].high < candle[i].low  (中间那根强势上冲留下的缺口)
    - 看跌FVG: candle[i-2].low  > candle[i].high
    只返回最近 lookback 根K线范围内、且尚未被完全回补的缺口。
    """
    gaps = []
    start = max(2, len(klines) - lookback)
    for i in range(start, len(klines)):
        c0, c2 = klines[i - 2], klines[i]
        if c0["high"] < c2["low"]:
            gap_low, gap_high = c0["high"], c2["low"]
            filled = any(k["low"] <= gap_low for k in klines[i + 1:])
            gaps.append({
                "type": "看涨FVG", "direction": "long",
                "zone_low": gap_low, "zone_high": gap_high,
                "index": i, "filled": filled,
            })
        elif c0["low"] > c2["high"]:
            gap_low, gap_high = c2["high"], c0["low"]
            filled = any(k["high"] >= gap_high for k in klines[i + 1:])
            gaps.append({
                "type": "看跌FVG", "direction": "short",
                "zone_low": gap_low, "zone_high": gap_high,
                "index": i, "filled": filled,
            })
    return [g for g in gaps if not g["filled"]]


def detect_order_blocks(klines: list[dict], swings: dict, lookahead: int = 10) -> list[dict]:
    """
    简化订单块识别:在导致 BOS 的那次突破之前,找到"最后一根反向K线"作为订单块。
    - 看涨订单块:上涨突破前的最后一根阴线
    - 看跌订单块:下跌突破前的最后一根阳线
    只扫描最近的摆动点附近,避免全历史扫描的噪音。
    """
    obs = []
    highs = swings["highs"]
    lows = swings["lows"]

    for idx, level in highs[-5:]:
        window_end = min(idx + lookahead, len(klines))
        for j in range(idx, window_end):
            if klines[j]["close"] > level:  # 向上突破该摆动高点
                for k in range(j - 1, max(idx - 1, j - 6), -1):
                    if klines[k]["close"] < klines[k]["open"]:  # 最后一根阴线
                        obs.append({
                            "type": "看涨订单块", "direction": "long",
                            "zone_low": klines[k]["low"], "zone_high": klines[k]["open"],
                            "break_index": j,
                        })
                        break
                break

    for idx, level in lows[-5:]:
        window_end = min(idx + lookahead, len(klines))
        for j in range(idx, window_end):
            if klines[j]["close"] < level:  # 向下突破该摆动低点
                for k in range(j - 1, max(idx - 1, j - 6), -1):
                    if klines[k]["close"] > klines[k]["open"]:  # 最后一根阳线
                        obs.append({
                            "type": "看跌订单块", "direction": "short",
                            "zone_low": klines[k]["open"], "zone_high": klines[k]["high"],
                            "break_index": j,
                        })
                        break
                break
    return obs


def detect_liquidity_sweep(klines: list[dict], swings: dict, wick_ratio: float = 0.6) -> dict | None:
    """
    流动性扫荡(止损猎杀):最后一根K线的影线刺破近期摆动高/低点，
    但收盘价收回到该水平内侧,且影线占K线总波幅的比例 >= wick_ratio。
    """
    if not klines or not swings["highs"] or not swings["lows"]:
        return None
    last = klines[-1]
    total_range = (last["high"] - last["low"]) or 1e-9

    recent_high = max(h[1] for h in swings["highs"][-3:])
    recent_low = min(l[1] for l in swings["lows"][-3:])

    upper_wick = last["high"] - max(last["open"], last["close"])
    lower_wick = min(last["open"], last["close"]) - last["low"]

    if last["high"] > recent_high and last["close"] < recent_high and upper_wick / total_range >= wick_ratio:
        return {"type": "上方流动性扫荡(诱多后反转)", "direction": "short", "swept_level": recent_high}
    if last["low"] < recent_low and last["close"] > recent_low and lower_wick / total_range >= wick_ratio:
        return {"type": "下方流动性扫荡(诱空后反转)", "direction": "long", "swept_level": recent_low}
    return None


def analyze(klines: list[dict]) -> dict:
    """汇总以上所有 ICT/SMC 子模块,并给出一个 [-1,1] 方向性分数。"""
    if len(klines) < 20:
        return {"score": 0.0, "detail": {}, "note": "K线数量不足,跳过ICT/SMC分析"}

    swings = find_swing_points(klines)
    bos_choch = detect_bos_choch(klines, swings)
    fvgs = detect_fvg(klines)
    obs = detect_order_blocks(klines, swings)
    sweep = detect_liquidity_sweep(klines, swings)

    score = 0.0
    if bos_choch.get("direction") == "long":
        score += 0.4 if "CHoCH" in bos_choch["signal"] else 0.3
    elif bos_choch.get("direction") == "short":
        score -= 0.4 if "CHoCH" in bos_choch["signal"] else 0.3

    bullish_fvg = [g for g in fvgs if g["direction"] == "long"]
    bearish_fvg = [g for g in fvgs if g["direction"] == "short"]
    score += 0.1 * min(2, len(bullish_fvg))
    score -= 0.1 * min(2, len(bearish_fvg))

    if sweep:
        score += 0.3 if sweep["direction"] == "long" else -0.3

    score = max(-1.0, min(1.0, score))

    return {
        "score": round(score, 3),
        "detail": {
            "bos_choch": bos_choch,
            "fair_value_gaps": fvgs[-5:],
            "order_blocks": obs[-5:],
            "liquidity_sweep": sweep,
        },
    }
