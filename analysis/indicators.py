"""
基础技术指标计算,纯 Python 实现(不依赖 ta-lib,方便 GitHub Actions 环境直接跑)。
输入统一为 fetchers 返回的 K线 dict 列表(字段: open/high/low/close/volume/...)。
"""
from __future__ import annotations
import math


def closes(klines: list[dict]) -> list[float]:
    return [k["close"] for k in klines]


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def atr(klines: list[dict], period: int = 14) -> float | None:
    if len(klines) < period + 1:
        return None
    trs = []
    for i in range(1, len(klines)):
        h, l, prev_c = klines[i]["high"], klines[i]["low"], klines[i - 1]["close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    recent = trs[-period:]
    return sum(recent) / len(recent)


def bollinger_band_width(klines: list[dict], period: int = 20, num_std: float = 2.0) -> dict | None:
    """返回 {'width': ..., 'width_pct': ..., 'is_squeeze': bool} width_pct 相对当前价格归一化。"""
    c = closes(klines)
    if len(c) < period:
        return None
    window = c[-period:]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = mean + num_std * std
    lower = mean - num_std * std
    width = upper - lower
    width_pct = width / mean * 100 if mean else 0
    return {"width": width, "width_pct": width_pct, "mid": mean, "upper": upper, "lower": lower}


def bbw_percentile(klines: list[dict], period: int = 20, lookback: int = 120) -> float | None:
    """当前BBW相对过去lookback根K线BBW历史的百分位,用于判断"挤压/极端扩张"四档。"""
    if len(klines) < period + lookback:
        lookback = max(20, len(klines) - period)
    widths = []
    for end in range(period, len(klines) + 1):
        window = klines[max(0, end - period):end]
        bb = bollinger_band_width(window, period=min(period, len(window)))
        if bb:
            widths.append(bb["width_pct"])
    if not widths:
        return None
    current = widths[-1]
    history = widths[-lookback:]
    rank = sum(1 for w in history if w <= current) / len(history)
    return rank  # 0~1, 越低代表越"挤压"


def approximate_cvd(klines: list[dict]) -> list[float]:
    """
    近似累计成交量差(CVD),因为公开K线接口没有真实的逐笔主动买卖方向,
    用 taker_buy_base 与总量的关系做近似:
        delta = 2*taker_buy_base - volume  (即 买方主动量 - 卖方主动量)
    这是业内常见的近似做法,精度不如逐笔tick data,但方向性参考有效。
    """
    cvd = []
    running = 0.0
    for k in klines:
        delta = 2 * k["taker_buy_base"] - k["volume"]
        running += delta
        cvd.append(running)
    return cvd


def linreg_slope(values: list[float]) -> float:
    """简单线性回归斜率,用于判断CVD/价格的短期方向。"""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    return num / den if den else 0.0
