"""
清算区间模拟 (Simulated Liquidation Map)。

重要声明:这不是真实的交易所清算数据(那需要付费的 Coinglass/CryptoQuant 等
API,且即便付费也是"估算"而非交易所内部真实持仓明细)。本模块用一种
可解释、可复现的方法自己模拟:

1. 用成交量分布(Volume Profile)的 POC/VAH/VAL 作为"大部分持仓大概率的
   建仓价格聚集区"的代理(假设:多数人在成交量最密集的价格区域建仓,
   这是一个合理但简化的假设)。
2. 对每个假设的建仓聚集区,按几个常见的杠杆倍数(10x/25x/50x/100x)
   分别计算多头和空头的近似强平价格:
       多头强平价 ≈ 建仓价 * (1 - 1/杠杆 + 维持保证金率)
       空头强平价 ≈ 建仓价 * (1 + 1/杠杆 - 维持保证金率)
   维持保证金率用 0.5% 的简化估计(不同交易所/仓位大小实际值有差异)。
3. 把所有算出来的强平价格排序,价格相近的聚集在一起,数量越多代表
   "理论上清算密度"越高——这只是一个基于假设的模拟推演,用于提示
   "价格可能被引导去扫荡的方向和大致区域",不是精确数值。
"""
from __future__ import annotations

LEVERAGE_TIERS = [10, 25, 50, 100]
MAINTENANCE_MARGIN_RATE = 0.005


def simulate_liquidation_clusters(entry_price_candidates: list[float], cluster_tolerance_pct: float = 0.5) -> dict:
    """
    entry_price_candidates: 假设的建仓聚集价格(比如 [POC, VAH, VAL]),
    也可以传入更多候选(比如最近几个摆动高低点)。
    """
    long_liqs = []
    short_liqs = []
    for entry in entry_price_candidates:
        for lev in LEVERAGE_TIERS:
            long_liq = entry * (1 - 1 / lev + MAINTENANCE_MARGIN_RATE)
            short_liq = entry * (1 + 1 / lev - MAINTENANCE_MARGIN_RATE)
            long_liqs.append({"entry_assumed": entry, "leverage": lev, "liq_price": round(long_liq, 6)})
            short_liqs.append({"entry_assumed": entry, "leverage": lev, "liq_price": round(short_liq, 6)})

    def cluster(levels: list[dict]) -> list[dict]:
        levels_sorted = sorted(levels, key=lambda x: x["liq_price"])
        clusters = []
        current = [levels_sorted[0]] if levels_sorted else []
        for item in levels_sorted[1:]:
            if abs(item["liq_price"] - current[-1]["liq_price"]) / current[-1]["liq_price"] * 100 <= cluster_tolerance_pct:
                current.append(item)
            else:
                clusters.append(current)
                current = [item]
        if current:
            clusters.append(current)
        return [
            {
                "price_level": round(sum(c["liq_price"] for c in cl) / len(cl), 6),
                "density": len(cl),
                "leverages_involved": sorted(set(c["leverage"] for c in cl)),
            }
            for cl in clusters
        ]

    long_clusters = sorted(cluster(long_liqs), key=lambda x: x["density"], reverse=True)
    short_clusters = sorted(cluster(short_liqs), key=lambda x: x["density"], reverse=True)

    return {
        "note": "本模拟基于成交量聚集区+常见杠杆倍数推算,非交易所真实清算数据,仅供剧本参考",
        "long_liquidation_clusters_top3": long_clusters[:3],
        "short_liquidation_clusters_top3": short_clusters[:3],
    }
