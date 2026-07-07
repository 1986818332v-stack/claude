"""
全局主控判定 (Master Verdict)。

把各分析模块产出的 [-1,1] 分数,按 config.WEIGHTS 加权求和,
输出一个 [-100,100] 的综合分数 + 方向 + 置信度标签。

设计原则(源自历史迭代经验教训):
- 任何单一模块数据缺失,只把该模块权重记为0(不参与本次计算),
  而不是当成0分强行拉低总分——避免"数据缺失"被误判成"看跌信号"。
- 输出必须同时包含:总分、每个子模块的原始贡献、缺失了哪些模块,
  方便复盘时定位问题,而不是黑箱。
"""
from __future__ import annotations
from config import WEIGHTS as DEFAULT_WEIGHTS


def compute_master_verdict(signal_scores: dict[str, float | None], weights: dict | None = None) -> dict:
    """
    signal_scores: {"multi_tf_resonance": 0.4, "ict_smc_structure": -0.2, ... }
    值为 None 表示该模块数据缺失,本次计算会跳过它的权重。
    weights: 可传入替代权重字典(比如 config.ALPHA_WEIGHTS),不传则用 config.WEIGHTS。
    """
    weights = weights or DEFAULT_WEIGHTS
    total_weight_used = 0
    weighted_sum = 0.0
    contributions = {}
    missing = []

    for key, weight in weights.items():
        score = signal_scores.get(key)
        if score is None or weight == 0:
            if score is None:
                missing.append(key)
            continue
        contributions[key] = {"score": round(score, 3), "weight": weight, "contribution": round(score * weight, 2)}
        weighted_sum += score * weight
        total_weight_used += weight

    if total_weight_used == 0:
        return {"total_score": 0.0, "direction": "数据不足", "confidence": "无",
                "contributions": {}, "missing_modules": missing, "weight_coverage_pct": 0}

    # 归一化到 [-100,100]:实际权重和可能小于满权重和(因缺失模块),按比例放大回100分制
    normalized = (weighted_sum / total_weight_used) * 100

    if normalized >= 40:
        direction, confidence = "看多", "高" if normalized >= 60 else "中"
    elif normalized <= -40:
        direction, confidence = "看空", "高" if normalized <= -60 else "中"
    elif -15 < normalized < 15:
        direction, confidence = "中性/观望", "低"
    else:
        direction = "偏多" if normalized > 0 else "偏空"
        confidence = "低"

    return {
        "total_score": round(normalized, 2),
        "direction": direction,
        "confidence": confidence,
        "contributions": contributions,
        "missing_modules": missing,
        "weight_coverage_pct": round(total_weight_used / sum(weights.values()) * 100, 1) if sum(weights.values()) else 0,
    }
