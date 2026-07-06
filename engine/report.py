"""
报告生成:输出 Markdown(人类阅读)+ JSON(供其他工具/前端消费)+ docs/data.json(供GitHub Pages看板读取)。
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone


def _fmt_num(x):
    if x is None:
        return "N/A"
    return f"{x:,.6g}"


def _render_plan(plan: dict) -> list[str]:
    lines = []
    lines.append(f"\n**{plan['line']}** ({plan['zone_type']}, 基于{plan['timeframe_basis']})\n")
    lines.append(f"- 方向: {plan['direction']}\n")
    lines.append(f"- 入场区间: {_fmt_num(plan['entry_zone'][0])} ~ {_fmt_num(plan['entry_zone'][1])}\n")
    lines.append(f"- 确认条件: {plan['confirmation']}\n")
    lines.append(f"- 止损: {_fmt_num(plan['stop_loss'])}\n")
    lines.append(f"- 目标: {_fmt_num(plan['target'])}\n")
    lines.append(f"- 风险回报比: 1 : {plan['risk_reward']}\n")
    if plan.get("volatility_sl_note"):
        lines.append(f"- {plan['volatility_sl_note']}\n")
    if plan.get("breakout_chase_branch"):
        lines.append(f"- 备选(突破追单分支): {plan['breakout_chase_branch']['condition']}\n")
    return lines


def render_markdown(scan_time: str, macro_ctx: dict, results: list[dict],
                     portfolio_risk: dict, geo_risk: dict) -> str:
    lines = []
    lines.append("# 机构级永续合约扫描报告\n")
    lines.append(f"生成时间(UTC): {scan_time}\n")

    if portfolio_risk.get("warning"):
        lines.append(f"\n## 组合风险提示\n\n{portfolio_risk['warning']}\n")
    for sw in portfolio_risk.get("sector_warnings", []):
        lines.append(f"- {sw}\n")

    lines.append("\n## 宏观背景\n")
    risk_ctx = macro_ctx.get("macro_risk", {})
    lines.append(f"- 最近宏观风险事件: **{risk_ctx.get('nearest_event','N/A')}**"
                 f",距离约 {risk_ctx.get('hours_until','N/A')} 小时\n")
    cpi = risk_ctx.get("cpi", {})
    if cpi.get("precise"):
        lines.append(f"- CPI 预计发布日期: {cpi.get('date')}\n")
    else:
        lines.append(f"- CPI 预计发布窗口(粗略): {cpi.get('window')}  _({cpi.get('note','')})_\n")

    dxy = macro_ctx.get("dxy", {})
    if dxy.get("available"):
        lines.append(f"- DXY 美元指数 10日变化: {dxy['change_pct_10d']}% → 对加密偏向: **{dxy['bias_for_crypto']}**\n")
    us10y = macro_ctx.get("us10y", {})
    if us10y.get("available"):
        lines.append(f"- 美债10年期收益率 10日变化: {us10y['change_bp_10d']}bp → 对加密偏向: **{us10y['bias_for_crypto']}**\n")

    btc_etf = macro_ctx.get("btc_etf", {})
    if btc_etf.get("available") and "latest_day_flow_musd" in btc_etf:
        lines.append(f"- BTC现货ETF最近一日净流入: {btc_etf['latest_day_flow_musd']}M USD"
                     f"({btc_etf.get('latest_day_label','')})\n")
        if "cumulative_total_flow_musd" in btc_etf:
            lines.append(f"- BTC现货ETF累计净流入: {btc_etf['cumulative_total_flow_musd']}M USD\n")
    else:
        lines.append(f"- BTC现货ETF资金流: 数据暂不可用({btc_etf.get('reason','源页面结构可能已变化')},未编造数字)\n")

    eth_etf = macro_ctx.get("eth_etf", {})
    if eth_etf.get("available") and "latest_day_flow_musd" in eth_etf:
        lines.append(f"- ETH现货ETF最近一日净流入: {eth_etf['latest_day_flow_musd']}M USD"
                     f"({eth_etf.get('latest_day_label','')})\n")
    else:
        lines.append(f"- ETH现货ETF资金流: 数据暂不可用({eth_etf.get('reason','源页面结构可能已变化')})\n")

    lines.append("\n> 说明:目前只有 BTC/ETH 有现货ETF与足够流动性的期权市场,这是市场现实"
                 "而非抓取限制;若未来其他币种ETF/期权上市,只需在config.py扩展即可复用同一套逻辑。\n")

    if geo_risk.get("matched"):
        titles = "; ".join(n.title for n in geo_risk["matched"][:3])
        lines.append(f"\n- 地缘政治风险信号(免费近似,基于新闻标题关键词密度): "
                     f"**{geo_risk['risk_level']}**,相关标题示例: {titles}\n")
    else:
        lines.append("\n- 地缘政治风险信号: 本轮新闻流中未检测到密集的地缘政治关键词\n")
    lines.append("> 注:特朗普社交媒体言论监听仍**未启用**(无可靠免费实时API);"
                 "地缘政治风险已改为新闻关键词密度的免费近似方案(见上)。\n")

    lines.append("\n## 交易计划\n")
    if not results:
        lines.append("本轮扫描未发现任何标的满足最低分析门槛。\n")

    for r in results:
        symbol = r["symbol"]
        verdict = r["verdict"]
        lines.append(f"\n### {symbol}\n")
        lines.append(f"- 全局主控判定: **{verdict['direction']}**"
                     f"(综合分数 {verdict['total_score']} / 100,置信度: {verdict['confidence']},"
                     f"数据覆盖率 {verdict['weight_coverage_pct']}%)\n")
        if verdict.get("missing_modules"):
            lines.append(f"- 缺失数据模块: {', '.join(verdict['missing_modules'])}\n")

        phase = r.get("phase", {})
        if phase.get("phase") and phase["phase"] not in ("数据不足",):
            lines.append(f"- 阶段识别: **{phase['phase']}**(置信度 {phase.get('confidence','低')})"
                         f" {phase.get('suggestion','')}\n")

        vp = r.get("volume_profile")
        if vp:
            lines.append(f"- 成交量分布(1h): POC={_fmt_num(vp['poc'])}, "
                         f"价值区 {_fmt_num(vp['val'])}~{_fmt_num(vp['vah'])}"
                         f" → {r.get('volume_profile_note','')}\n")

        htf = r.get("htf_liquidity", {})
        if htf.get("available") and htf["confluence"]["hits"]:
            hit_desc = ", ".join(f"{h['level_name']}({_fmt_num(h['level_price'])}, 距现价{h['distance_pct']}%)"
                                 for h in htf["confluence"]["hits"])
            lines.append(f"- 高周期流动性池共振: {hit_desc}\n")

        opt = r.get("options_sentiment")
        if opt and opt.get("available"):
            lines.append(f"- 期权市场(Deribit近似): IV偏斜{opt['iv_skew_approx']} "
                         f"(看跌IV均值{opt['avg_put_iv']} vs 看涨IV均值{opt['avg_call_iv']}), "
                         f"Put/Call持仓比 {opt.get('put_call_oi_ratio','N/A')}\n")

        if r.get("anomaly_note"):
            lines.append(f"- OI异动三维排名: {r['anomaly_note']}\n")

        for plan in r.get("plans", []):
            lines.extend(_render_plan(plan))

        if r.get("watchlist"):
            lines.append("\n*以下为未达到最低风险回报比门槛的观察名单(不建议直接入场,仅供参考结构位置):*\n")
            for plan in r["watchlist"]:
                lines.extend(_render_plan(plan))

        if not r.get("plans") and not r.get("watchlist"):
            lines.append("- 暂无可识别的结构化入场区间(结构不够清晰)\n")

        liq = r.get("liquidation_simulation")
        if liq:
            lines.append(f"\n- 清算区间模拟({liq['note']}):\n")
            for c in liq["long_liquidation_clusters_top3"]:
                lines.append(f"  - 多头清算密集区(模拟): {_fmt_num(c['price_level'])}"
                             f" (聚集度{c['density']}, 涉及杠杆{c['leverages_involved']})\n")
            for c in liq["short_liquidation_clusters_top3"]:
                lines.append(f"  - 空头清算密集区(模拟): {_fmt_num(c['price_level'])}"
                             f" (聚集度{c['density']}, 涉及杠杆{c['leverages_involved']})\n")

    lines.append("\n---\n")
    lines.append("**免责声明**:本报告由自动化脚本生成,所有信号均为规则化近似计算,"
                 "不构成投资建议。ICT/SMC结构判定、资金费率拥挤度、新闻情绪打分、清算区间模拟等"
                 "均有其局限性,务必结合自身风险承受能力独立判断。\n")

    return "".join(lines)


def _build_dashboard_json(scan_time: str, results: list[dict], portfolio_risk: dict) -> dict:
    """给 docs/index.html 静态看板用的精简数据结构。"""
    items = []
    for r in results:
        v = r["verdict"]
        items.append({
            "symbol": r["symbol"],
            "direction": v["direction"],
            "score": v["total_score"],
            "confidence": v["confidence"],
            "phase": r.get("phase", {}).get("phase"),
            "num_plans": len(r.get("plans", [])),
        })
    return {
        "scan_time": scan_time,
        "portfolio_warning": portfolio_risk.get("warning"),
        "items": items,
    }


def write_reports(scan_time: str, macro_ctx: dict, results: list[dict],
                   portfolio_risk: dict, geo_risk: dict, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    md = render_markdown(scan_time, macro_ctx, results, portfolio_risk, geo_risk)

    md_path = os.path.join(out_dir, "latest.md")
    json_path = os.path.join(out_dir, "latest.json")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"scan_time": scan_time, "macro_context": macro_ctx,
                   "portfolio_risk": portfolio_risk, "geopolitical_risk": {
                       "score": geo_risk.get("score"), "risk_level": geo_risk.get("risk_level")},
                   "results": results}, f, ensure_ascii=False, indent=2, default=str)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = os.path.join(out_dir, "history")
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, f"{ts}.md")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(md)

    # 供 GitHub Pages 静态看板读取
    docs_dir = os.path.join(out_dir, "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)
    dashboard_path = os.path.join(docs_dir, "data.json")
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(_build_dashboard_json(scan_time, results, portfolio_risk), f, ensure_ascii=False, indent=2)

    return {"markdown_path": md_path, "json_path": json_path, "archive_path": archive_path,
            "dashboard_path": dashboard_path}
