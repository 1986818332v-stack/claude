"""
阶段识别 (Phase Classifier),规则来源:用户提供的《山寨币庄家异动数据库》
框架——把 OI变化 + 成交量变化 + 价格行为 + 现货支撑 组合成六个阶段:
吸筹期 / 洗盘期 / 主升期 / 赶顶期 / 派发期 / 出货崩盘期。

这是一个"叙事分类器",目的是给交易计划配一句"当前处于什么剧本阶段"的
可解释描述,而不是替代 verdict 的数值打分。分类逻辑基于经验规则,
必然有边界模糊的情况——所以每个分类结果都带一个"匹配度"而非绝对判定。
"""
from __future__ import annotations
from analysis.indicators import closes, linreg_slope


def _pct_change(vals: list[float]) -> float:
    if len(vals) < 2 or vals[0] == 0:
        return 0.0
    return (vals[-1] - vals[0]) / abs(vals[0]) * 100


def classify_phase(
    klines: list[dict],
    oi_change_pct: float | None,
    spot_perp_notes: list[str],
    naked_k_patterns: list[dict],
) -> dict:
    """
    klines: 用于判断价格/成交量趋势的K线(建议用1h,近30-50根)
    oi_change_pct: 来自 microstructure.oi_divergence_signal 的 oi_change 换算成百分比(可为None)
    spot_perp_notes: spot_perp_signal 返回的 notes 列表,用于判断"现货托底/流出"
    naked_k_patterns: naked_k_score 返回的 patterns,用于判断"高陷阱"频率(上影线/看跌吞没多)
    """
    if len(klines) < 20:
        return {"phase": "数据不足", "confidence": "低", "reasoning": []}

    c = closes(klines)
    recent_price_change = _pct_change(c[-20:])
    volumes = [k["volume"] for k in klines[-20:]]
    avg_vol_early = sum(volumes[:10]) / 10
    avg_vol_late = sum(volumes[10:]) / 10
    vol_expansion = (avg_vol_late - avg_vol_early) / avg_vol_early * 100 if avg_vol_early else 0

    spot_support = any("贴水" in n or "恐慌" in n or "现货CVD走平/上升" in n for n in spot_perp_notes)
    spot_outflow = any("升水" in n or "杠杆驱动" in n for n in spot_perp_notes)

    upper_wick_traps = sum(1 for p in naked_k_patterns if "上影线" in p.get("pattern", ""))

    reasoning = []
    oi_up = (oi_change_pct or 0) > 3
    oi_down = (oi_change_pct or 0) < -3

    price_flat = abs(recent_price_change) < 3
    price_up_strong = recent_price_change > 8
    price_up_mild = 0 < recent_price_change <= 8
    price_down = recent_price_change < -3

    vol_expanding = vol_expansion > 20

    # ---- 1. 吸筹期:底部横盘 + OI小幅涨 + Vol温和放大 + 价格不怎么涨 ----
    if price_flat and oi_up and not vol_expanding:
        reasoning.append("价格横盘、OI小幅上升、成交量未剧烈放大 → 疑似底部吸筹")
        return {"phase": "吸筹期", "confidence": "中", "reasoning": reasoning,
                "suggestion": "可重点观察,不代表立即入场信号"}

    # ---- 2. 洗盘期:OI暴跌 + 价格不破支撑 + 现货托底 + Vol放大但不持续下跌 ----
    if oi_down and not price_down and spot_support:
        reasoning.append("OI下降、价格未破位、现货端呈现托底特征 → 疑似洗盘")
        return {"phase": "洗盘期", "confidence": "中", "reasoning": reasoning,
                "suggestion": "若关键支撑不破,可视为低吸区域,但需自行确认支撑有效性"}

    # ---- 3. 主升期:多头共振 + OI暴涨 + Vol爆发 + 现货托底 + 突破平台 ----
    if price_up_strong and oi_up and vol_expanding and spot_support:
        reasoning.append("价格强势上涨、OI与成交量同步暴涨、现货有支撑 → 疑似主升浪")
        return {"phase": "主升期", "confidence": "高", "reasoning": reasoning,
                "suggestion": "右侧确认特征明显,但追涨仍需注意风险回报比"}

    # ---- 4. 赶顶期:高陷阱连续 + OI继续暴涨 + 价格快速远离均线 + Vol极端放大 ----
    if price_up_strong and oi_up and vol_expansion > 50 and upper_wick_traps >= 2:
        reasoning.append("价格远离均线、上影线陷阱频繁出现、OI与成交量均处极端值 → 疑似赶顶")
        return {"phase": "赶顶期", "confidence": "中", "reasoning": reasoning,
                "suggestion": "不建议追高,若已有仓位可考虑分批减仓"}

    # ---- 5. 派发期:顶部横盘 + OI背离(价格新高但OI不创新高/或反向) + 现货流出 + 反弹不创新高 ----
    if price_flat and (oi_down or (oi_change_pct is not None and -3 <= oi_change_pct <= 3)) and spot_outflow:
        reasoning.append("高位横盘、OI与价格出现背离、现货端呈流出特征 → 疑似派发")
        return {"phase": "派发期", "confidence": "低", "reasoning": reasoning,
                "suggestion": "不建议在此阶段接多单(不接飞刀)"}

    # ---- 6. 出货崩盘期:OI暴跌 + 现货流出 + 价格持续下跌 ----
    if oi_down and spot_outflow and price_down:
        reasoning.append("OI暴跌、现货流出、价格持续下跌 → 疑似出货崩盘")
        return {"phase": "出货崩盘期", "confidence": "中", "reasoning": reasoning,
                "suggestion": "反弹多为出货反抽,不建议轻易抄底"}

    return {"phase": "阶段特征不明显", "confidence": "低",
            "reasoning": ["未匹配到六个典型阶段组合中的任何一个,可能处于过渡状态"]}
