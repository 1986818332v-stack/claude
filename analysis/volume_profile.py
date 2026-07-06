"""
成交量分布 (Volume Profile / Market Profile),纯Python实现。

概念:
- POC (Point of Control): 成交量最集中的价格区间(筹码密集位)
- VAH/VAL (Value Area High/Low): 包含 70% 成交量的价格区间上下边界

实现方式:把K线的价格范围切成若干个价格桶(bin),每根K线的成交量
按其 high-low 范围均匀分摊到经过的桶里(简化假设,真实tick级别分布会更精确,
但对于免费的公开K线数据,这是常见且够用的近似方法)。
"""
from __future__ import annotations


def compute_volume_profile(klines: list[dict], num_bins: int = 50) -> dict | None:
    if not klines:
        return None

    price_min = min(k["low"] for k in klines)
    price_max = max(k["high"] for k in klines)
    if price_max <= price_min:
        return None

    bin_size = (price_max - price_min) / num_bins
    bins = [0.0] * num_bins

    def bin_index(price: float) -> int:
        idx = int((price - price_min) / bin_size)
        return max(0, min(num_bins - 1, idx))

    for k in klines:
        lo_idx, hi_idx = bin_index(k["low"]), bin_index(k["high"])
        span = max(1, hi_idx - lo_idx + 1)
        vol_per_bin = k["volume"] / span
        for i in range(lo_idx, hi_idx + 1):
            bins[i] += vol_per_bin

    total_volume = sum(bins)
    if total_volume <= 0:
        return None

    poc_idx = max(range(num_bins), key=lambda i: bins[i])
    poc_price = price_min + (poc_idx + 0.5) * bin_size

    # 从POC向两边扩展,累计到70%成交量为止,得到 Value Area
    target = total_volume * 0.7
    accumulated = bins[poc_idx]
    lo, hi = poc_idx, poc_idx
    while accumulated < target and (lo > 0 or hi < num_bins - 1):
        left_val = bins[lo - 1] if lo > 0 else -1
        right_val = bins[hi + 1] if hi < num_bins - 1 else -1
        if right_val >= left_val:
            hi += 1
            accumulated += bins[hi]
        else:
            lo -= 1
            accumulated += bins[lo]

    vah = price_min + (hi + 1) * bin_size
    val = price_min + lo * bin_size

    return {
        "poc": round(poc_price, 6),
        "vah": round(vah, 6),
        "val": round(val, 6),
        "bin_size": round(bin_size, 6),
    }


def classify_price_vs_profile(current_price: float, profile: dict) -> str:
    """当前价格相对Value Area的位置,便于生成叙述性解读。"""
    if current_price > profile["vah"]:
        return "价格高于价值区(VAH以上),追高风险较大"
    if current_price < profile["val"]:
        return "价格低于价值区(VAL以下),存在均值回归/筹码真空区机会,也可能是趋势延续的开端"
    return "价格处于价值区(VAH~VAL)内,属于公允价值区间,双向都有交易者认可"
