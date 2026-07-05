"""
报告生成:输出 Markdown(人类阅读)+ JSON(供其他工具/前端消费)。
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone


def _fmt_num(x):
    if x is None:
        return "N/A"
    return f"{x:,.6g}"


def render_markdown(scan_time: str, macro_ctx: dict, results: list[dict]) -> str:
    lines = []
    lines.append(f"# 机构级永续合约扫描报告\n")
    lines.append(f"生成时间(UTC): {scan_time}\n")

    lines.append("## 宏观背景\n")
    fomc = macro_ctx.get("macro_risk", {})
    lines.append(f"- 最近宏观风险事件: **{fomc.get('nearest_event','N/A')}**"
                 f",距离约 {fomc.get('hours_until','N/A')} 小时\n")
    cpi = fomc.get("cpi", {})
    if cpi.get("precise"):
        lines.append(f"- CPI 预计发布日期: {cpi.get('date')}\n")
    else:
        lines.append(f"- CPI 预计发布窗口(粗略): {cpi.get('window')}  "
                     f"_({cpi.get('note','')})_\n")
    dxy = macro_ctx.get("dxy", {})
    if dxy.get("available"):
        lines.append(f"- DXY 美元指数 10日变化: {dxy['change_pct_10d']}% → 对加密偏向: **{dxy['bias_for_crypto']}**\n")
    us10y = macro_ctx.get("us10y", {})
    if us10y.get("available"):
        lines.append(f"- 美债10年期收益率 10日变化: {us10y['change_bp_10d']}bp → 对加密偏向: **{us10y['bias_for_crypto']}**\n")
    btc_etf = macro_ctx.get("btc_etf", {})
    if btc_etf.get("available"):
        lines.append(f"- BTC现货ETF最近净流入: {btc_etf['latest_total_flow_musd']}M USD\n")
    else:
        lines.append("- BTC现货ETF资金流: 数据暂不可用(源页面结构可能已变化,未编造数字)\n")
    lines.append("\n> 注:特朗普社交媒体言论与地缘政治事件模块本轮**未启用**"
                 "(免费数据源无法可靠覆盖,已按用户要求跳过,避免用低质量近似误导决策)。\n")

    lines.append("\n## 交易计划\n")
    if not results:
        lines.append("本轮扫描未发现满足最低风险回报比(≥ 用户设定阈值)的高质量方案。\n")

    for r in results:
        symbol = r["symbol"]
        verdict = r["verdict"]
        lines.append(f"\n### {symbol}\n")
        lines.append(f"- 全局主控判定: **{verdict['direction']}**"
                     f"(综合分数 {verdict['total_score']} / 100,置信度: {verdict['confidence']},"
                     f"数据覆盖率 {verdict['weight_coverage_pct']}%)\n")
        if verdict.get("missing_modules"):
            lines.append(f"- 缺失数据模块: {', '.join(verdict['missing_modules'])}\n")

        for plan in r.get("plans", []):
            lines.append(f"\n**{plan['line']}** ({plan['zone_type']}, 基于{plan['timeframe_basis']})\n")
            lines.append(f"- 方向: {plan['direction']}\n")
            lines.append(f"- 入场区间: {_fmt_num(plan['entry_zone'][0])} ~ {_fmt_num(plan['entry_zone'][1])}\n")
            lines.append(f"- 确认条件: {plan['confirmation']}\n")
            lines.append(f"- 止损: {_fmt_num(plan['stop_loss'])}\n")
            lines.append(f"- 目标: {_fmt_num(plan['target'])}\n")
            lines.append(f"- 风险回报比: 1 : {plan['risk_reward']}\n")
            if plan.get("breakout_chase_branch"):
                lines.append(f"- 备选(突破追单分支): {plan['breakout_chase_branch']['condition']}\n")

        if not r.get("plans"):
            lines.append("- 暂无满足风险回报比阈值的入场方案(结构不够清晰或距离现价过远)\n")

    lines.append("\n---\n")
    lines.append("**免责声明**:本报告由自动化脚本生成,所有信号均为规则化近似计算,"
                 "不构成投资建议。ICT/SMC结构判定、资金费率拥挤度、新闻情绪打分等均有其局限性,"
                 "务必结合自身风险承受能力独立判断。\n")

    return "".join(lines)


def write_reports(scan_time: str, macro_ctx: dict, results: list[dict], out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    md = render_markdown(scan_time, macro_ctx, results)

    md_path = os.path.join(out_dir, "latest.md")
    json_path = os.path.join(out_dir, "latest.json")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"scan_time": scan_time, "macro_context": macro_ctx, "results": results},
                   f, ensure_ascii=False, indent=2)

    # 额外保留一份按时间戳命名的历史归档,方便复盘
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = os.path.join(out_dir, "history")
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, f"{ts}.md")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(md)

    return {"markdown_path": md_path, "json_path": json_path, "archive_path": archive_path}
