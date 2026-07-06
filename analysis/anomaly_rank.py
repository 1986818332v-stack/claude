"""
三维异动排名 (Anomaly Rank)。

灵感来源于用户提供的参考产品理念:同一个异动数值,应该同时从三个维度看:
1. 自身历史排名:这次变化在该标的自己的历史里排第几(它是否在做自己没做过的事)
2. 全场强度排名:同一时刻,全市场所有标的里,它的变化幅度排第几(是否是最独立/最强的)
3. 绝对数值排名:变化的绝对金额有多大(避免只看百分比而忽略大盘蓝筹的真实体量)

核心洞察(用户原话的重点):数值上不起眼(比如OI只增加了500万美元),但如果
自身历史排名和全场强度排名都很高,反而可能是主力在大盘还没注意到的时候悄悄建仓,
这类"低数值、高排名"的标的值得单独标注出来,而不是被绝对数值过滤掉。
"""
from __future__ import annotations

MAX_HISTORY_LEN = 20


def update_history_and_get_percentile(state: dict, symbol: str, metric_name: str, value: float) -> float | None:
    """
    把最新值追加进 state[metric_name][symbol] 的滚动历史(最多保留 MAX_HISTORY_LEN 个),
    并返回该值在历史序列里的百分位(0~1,1代表这是历史最高值)。
    state 由调用方从 engine.state.load_state() 拿到,函数会原地修改它,
    调用方需要在流程结束时自行 save_state(state)。
    """
    bucket = state.setdefault("anomaly_history", {}).setdefault(metric_name, {})
    history = bucket.setdefault(symbol, [])
    history.append(value)
    if len(history) > MAX_HISTORY_LEN:
        del history[0]

    if len(history) < 3:
        return None  # 历史数据不足,暂不给出百分位(避免用1-2个点算出虚假的"历史新高")
    rank = sum(1 for v in history if v <= value) / len(history)
    return round(rank, 3)


def cross_sectional_percentile(symbol_values: dict[str, float], symbol: str) -> float | None:
    """全场强度排名:symbol_values 是本轮所有标的的 {symbol: value},返回该symbol的百分位。"""
    if symbol not in symbol_values or len(symbol_values) < 3:
        return None
    target = symbol_values[symbol]
    values = list(symbol_values.values())
    rank = sum(1 for v in values if v <= target) / len(values)
    return round(rank, 3)


def build_anomaly_note(self_pct: float | None, market_pct: float | None, abs_value: float | None,
                        abs_value_label: str = "变化量") -> str:
    """生成一句可读的三维排名解读,用于报告展示。"""
    parts = []
    if self_pct is not None:
        parts.append(f"自身历史排名前{round((1-self_pct)*100)}%" if self_pct >= 0.5
                     else f"自身历史排名后{round(self_pct*100)}%(不算突出)")
    if market_pct is not None:
        parts.append(f"全场强度排名前{round((1-market_pct)*100)}%" if market_pct >= 0.5
                     else "全场强度排名靠后")
    if abs_value is not None:
        parts.append(f"{abs_value_label}约{abs_value:,.2f}")

    note = "、".join(parts) if parts else "样本不足,暂无排名参考"

    # 关键洞察:数值不大但双高排名 => 特别标注
    if (self_pct is not None and self_pct >= 0.85) and (market_pct is not None and market_pct >= 0.85):
        note += " ——【关注】自身与全场排名均处高位,即便绝对数值不大,也可能是主力悄悄建仓的早期信号"
    return note
