"""
多周期共振 (Multi-Timeframe Resonance)。

逻辑:对每个周期分别计算一个简单趋势方向(EMA20 vs EMA60 + 收盘价相对位置),
再看三个周期是否指向同一方向。全部同向 => 高分共振;出现分歧 => 分数被拉低,
提示"周期打架,建议观望或降低仓位"。
"""
from __future__ import annotations
from analysis.indicators import ema, closes


def timeframe_trend(klines: list[dict]) -> dict:
    """返回单一周期的趋势方向 [-1,1] 以及简要描述。"""
    c = closes(klines)
    if len(c) < 60:
        return {"direction": 0.0, "label": "数据不足"}

    ema20 = ema(c, 20)[-1]
    ema60 = ema(c, 60)[-1]
    last_close = c[-1]

    trend_strength = (ema20 - ema60) / ema60 if ema60 else 0
    position_bias = 1 if last_close > ema20 else -1

    # 归一化: trend_strength 一般在 -0.05~0.05 量级,乘20放大到接近[-1,1]
    direction = max(-1.0, min(1.0, trend_strength * 20)) * 0.7 + position_bias * 0.3
    direction = max(-1.0, min(1.0, direction))

    if direction > 0.25:
        label = "多头趋势"
    elif direction < -0.25:
        label = "空头趋势"
    else:
        label = "震荡/趋势不明"
    return {"direction": round(direction, 3), "label": label}


def resonance_score(per_tf_klines: dict[str, list[dict]]) -> dict:
    """
    per_tf_klines: {"15m": [...], "1h": [...], "4h": [...]}
    返回汇总的共振分数和各周期明细。
    """
    trends = {tf: timeframe_trend(kl) for tf, kl in per_tf_klines.items()}
    directions = [t["direction"] for t in trends.values()]
    if not directions:
        return {"score": 0.0, "trends": trends, "aligned": False}

    avg = sum(directions) / len(directions)
    # 一致性惩罚:如果各周期方向符号不一致,拉低整体分数
    signs = set(1 if d > 0.1 else (-1 if d < -0.1 else 0) for d in directions)
    aligned = len(signs - {0}) <= 1  # 除了中性0以外,只有一种符号

    score = avg if aligned else avg * 0.4
    return {"score": round(max(-1.0, min(1.0, score)), 3), "trends": trends, "aligned": aligned}
