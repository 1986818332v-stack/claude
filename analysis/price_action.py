"""
裸K / Price Action 形态识别,只基于 OHLC,不依赖任何指标。
每个函数返回 None 或一个 dict(包含 pattern 名称 + 方向 + 强度)。
"""
from __future__ import annotations


def _body(k: dict) -> float:
    return abs(k["close"] - k["open"])


def _range(k: dict) -> float:
    return k["high"] - k["low"] or 1e-9


def detect_engulfing(klines: list[dict]) -> dict | None:
    """看涨/看跌吞没形态,检测最后两根K线。"""
    if len(klines) < 2:
        return None
    prev, cur = klines[-2], klines[-1]
    prev_bull = prev["close"] > prev["open"]
    cur_bull = cur["close"] > cur["open"]
    if prev_bull == cur_bull:
        return None
    engulfs = (cur["close"] > prev["open"] and cur["open"] < prev["close"]) if cur_bull else \
              (cur["open"] > prev["close"] and cur["close"] < prev["open"])
    if not engulfs:
        return None
    strength = min(1.0, _body(cur) / _range(cur))
    return {
        "pattern": "看涨吞没" if cur_bull else "看跌吞没",
        "direction": "long" if cur_bull else "short",
        "strength": round(strength, 2),
    }


def detect_pin_bar(klines: list[dict]) -> dict | None:
    """Pin Bar / 长下影线(锤子)或长上影线(射击之星)。"""
    if not klines:
        return None
    k = klines[-1]
    total_range = _range(k)
    body = _body(k)
    upper_wick = k["high"] - max(k["open"], k["close"])
    lower_wick = min(k["open"], k["close"]) - k["low"]

    if lower_wick > body * 2 and lower_wick > total_range * 0.5:
        return {"pattern": "长下影线(锤子/看涨拒绝)", "direction": "long",
                "strength": round(lower_wick / total_range, 2)}
    if upper_wick > body * 2 and upper_wick > total_range * 0.5:
        return {"pattern": "长上影线(射击之星/看跌拒绝)", "direction": "short",
                "strength": round(upper_wick / total_range, 2)}
    return None


def detect_inside_bar(klines: list[dict]) -> dict | None:
    """Inside Bar:当前K线完全被前一根K线包含,通常代表盘整/蓄势。"""
    if len(klines) < 2:
        return None
    prev, cur = klines[-2], klines[-1]
    if cur["high"] <= prev["high"] and cur["low"] >= prev["low"]:
        return {"pattern": "内包线(蓄势待变盘)", "direction": "neutral", "strength": 0.5}
    return None


def detect_all_patterns(klines: list[dict]) -> list[dict]:
    detectors = [detect_engulfing, detect_pin_bar, detect_inside_bar]
    results = []
    for fn in detectors:
        r = fn(klines)
        if r:
            results.append(r)
    return results


def naked_k_score(klines: list[dict]) -> dict:
    """
    汇总裸K信号为一个方向性分数 [-1,1]。
    多个看涨形态叠加会增强分数,看跌相反,中性(inside bar)不改变方向只降低置信度。
    """
    patterns = detect_all_patterns(klines)
    score = 0.0
    for p in patterns:
        if p["direction"] == "long":
            score += p["strength"]
        elif p["direction"] == "short":
            score -= p["strength"]
    score = max(-1.0, min(1.0, score))
    return {"score": score, "patterns": patterns}
