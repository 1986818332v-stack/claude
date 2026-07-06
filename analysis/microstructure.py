"""
微观结构信号模块:
- 资金费率极值/趋势 (funding_rate_signal)
- OI 变化 vs 价格背离 (oi_divergence_signal)
- 现货/永续 基差 + CVD 背离 (spot_perp_signal)
- 订单簿失衡 OBI (order_book_imbalance_signal)

这些都是"反身性/情绪拥挤度"信号,而非直接的方向预测——
例如资金费率极端为正,代表多头拥挤,统计上更容易发生多头挤压(信号偏空,反向操作逻辑)。
"""
from __future__ import annotations
from analysis.indicators import approximate_cvd, linreg_slope


def funding_rate_signal(current_funding: float | None, history: list[dict]) -> dict:
    """
    资金费率极值判断。经验阈值(可在迭代中按品种校准):
    |funding| > 0.05% (即0.0005) 单期就算偏高; > 0.1% 视为极端拥挤。
    正费率极端 -> 多头付费给空头,多头过度拥挤 -> 反向(偏空)提示
    负费率极端 -> 空头过度拥挤 -> 反向(偏多)提示
    """
    if current_funding is None:
        return {"score": 0.0, "note": "资金费率数据缺失"}

    if abs(current_funding) < 0.0005:
        base_score = 0.0
        crowding = "正常范围"
    elif abs(current_funding) < 0.001:
        base_score = -0.3 if current_funding > 0 else 0.3
        crowding = "偏高,存在拥挤风险"
    else:
        base_score = -0.6 if current_funding > 0 else 0.6
        crowding = "极端,挤压风险较高"

    # 用历史几期资金费率的趋势做微调:持续走高的正费率,拥挤程度在加剧
    trend_note = ""
    if history and len(history) >= 3:
        try:
            rates = [float(h["fundingRate"]) for h in history]
            slope = linreg_slope(rates)
            if slope > 0 and current_funding > 0:
                base_score -= 0.1
                trend_note = "费率持续走高,多头拥挤度上升"
            elif slope < 0 and current_funding < 0:
                base_score += 0.1
                trend_note = "费率持续走低,空头拥挤度上升"
        except (KeyError, ValueError, TypeError):
            pass

    return {
        "score": max(-1.0, min(1.0, base_score)),
        "current_funding_pct": round(current_funding * 100, 4),
        "crowding": crowding,
        "trend_note": trend_note,
    }


def oi_divergence_signal(klines: list[dict], oi_now: float | None, oi_prev_estimate: float | None) -> dict:
    """
    OI vs 价格背离(简化版,因公开API通常只给"当前OI快照",没有免费的历史OI序列,
    所以这里用"最近价格变化方向" x "本次调用与上次调用之间OI变化"做增量对比。
    oi_prev_estimate 由调用方传入上一轮跑批缓存的值,若无历史值则只做价格趋势提示。
    """
    if not klines or len(klines) < 2:
        return {"score": 0.0, "note": "K线不足"}

    price_change = klines[-1]["close"] - klines[-2]["close"]

    if oi_now is None or oi_prev_estimate is None:
        return {"score": 0.0, "note": "OI历史快照不足(需连续跑批才能计算背离),本轮仅记录当前OI用于下次对比",
                "oi_now": oi_now}

    oi_change = oi_now - oi_prev_estimate
    oi_change_pct = (oi_change / oi_prev_estimate * 100) if oi_prev_estimate else None
    # 价涨 + OI增 => 新多头进场,趋势健康(顺势加分)
    # 价涨 + OI减 => 空头平仓驱动上涨,持续性存疑(轻微反向)
    # 价跌 + OI增 => 新空头进场,趋势健康(顺势减分,即偏空)
    # 价跌 + OI减 => 多头平仓驱动下跌,持续性存疑(轻微反向)
    if price_change > 0 and oi_change > 0:
        score, note = 0.5, "价涨OI增:新多头进场,趋势健康"
    elif price_change > 0 and oi_change < 0:
        score, note = -0.2, "价涨OI减:空头平仓驱动,谨慎追高"
    elif price_change < 0 and oi_change > 0:
        score, note = -0.5, "价跌OI增:新空头进场,趋势健康(偏空)"
    elif price_change < 0 and oi_change < 0:
        score, note = 0.2, "价跌OI减:多头平仓驱动,可能接近企稳"
    else:
        score, note = 0.0, "价格/OI变化不明显"

    return {"score": score, "note": note, "oi_change": oi_change, "oi_change_pct": oi_change_pct}


def spot_perp_signal(spot_klines: list[dict], perp_klines: list[dict]) -> dict:
    """
    现货/永续基差 + CVD 背离。
    - 基差 = (永续价 - 现货价) / 现货价。持续正基差扩大 = 永续更贪婪(可能偏空反向);
      基差转负或收窄 = 情绪降温。
    - CVD背离:永续CVD上升但现货CVD走平/下降,说明上涨主要由杠杆驱动而非真实现货需求,
      持续性较弱(风险提示,而非直接反向做空信号)。
    """
    if not spot_klines or not perp_klines:
        return {"score": 0.0, "note": "现货或永续数据缺失"}

    spot_price = spot_klines[-1]["close"]
    perp_price = perp_klines[-1]["close"]
    basis_pct = (perp_price - spot_price) / spot_price * 100 if spot_price else 0

    spot_cvd = approximate_cvd(spot_klines)
    perp_cvd = approximate_cvd(perp_klines)
    spot_slope = linreg_slope(spot_cvd[-30:]) if len(spot_cvd) >= 30 else linreg_slope(spot_cvd)
    perp_slope = linreg_slope(perp_cvd[-30:]) if len(perp_cvd) >= 30 else linreg_slope(perp_cvd)

    score = 0.0
    notes = []

    if basis_pct > 0.15:
        score -= 0.3
        notes.append(f"永续对现货升水{basis_pct:.2f}%,杠杆情绪偏热")
    elif basis_pct < -0.1:
        score += 0.2
        notes.append(f"永续对现货贴水{basis_pct:.2f}%,情绪偏冷/存在恐慌")

    if perp_slope > 0 and spot_slope <= 0:
        score -= 0.3
        notes.append("永续CVD上升但现货CVD走平/下降:上涨由杠杆驱动,真实需求不足")
    elif perp_slope < 0 and spot_slope >= 0:
        score += 0.3
        notes.append("永续CVD下降但现货CVD走平/上升:下跌主要是杠杆挤压,非真实抛售")

    return {"score": max(-1.0, min(1.0, score)), "basis_pct": round(basis_pct, 4), "notes": notes}


def order_book_imbalance_signal(binance_depth: dict | None, okx_depth: dict | None) -> dict:
    """
    订单簿失衡 (OBI) = (买盘挂单量 - 卖盘挂单量) / (买盘 + 卖盘)。
    多交易所取平均,减少单一交易所盘口被"钓鱼单"影响的噪音。
    """
    def obi_from_depth(bids, asks, top_n=20):
        b = sum(float(x[1]) for x in bids[:top_n])
        a = sum(float(x[1]) for x in asks[:top_n])
        total = b + a
        return (b - a) / total if total else 0.0

    obis = []
    if binance_depth and binance_depth.get("bids") and binance_depth.get("asks"):
        obis.append(obi_from_depth(binance_depth["bids"], binance_depth["asks"]))
    if okx_depth and okx_depth.get("bids") and okx_depth.get("asks"):
        # OKX 深度格式: [price, size, liquidated_orders, num_orders]
        obis.append(obi_from_depth(okx_depth["bids"], okx_depth["asks"]))

    if not obis:
        return {"score": 0.0, "note": "订单簿数据不可用"}

    avg_obi = sum(obis) / len(obis)
    return {"score": round(max(-1.0, min(1.0, avg_obi * 2)), 3), "raw_obi": round(avg_obi, 4),
            "exchanges_used": len(obis)}
