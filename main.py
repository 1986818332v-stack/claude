"""
主编排脚本。

运行方式: python main.py
(GitHub Actions 会按 .github/workflows/scan.yml 里的 cron 定时调用)
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone

from config import (
    MAX_SYMBOLS_TO_SCORE, TOP_N_REPORT, TIMEFRAMES,
)
from fetchers import binance_futures as bf
from fetchers import binance_spot as bs
from fetchers import okx
from fetchers import news as news_fetcher
from fetchers import macro_calendar
from fetchers import macro_market

from analysis import multi_timeframe, ict_smc, price_action, microstructure
from analysis.ict_smc import find_swing_points

from engine.verdict import compute_master_verdict
from engine.trade_plan import build_scalp_plan, build_swing_plan
from engine.state import load_state, save_state
from engine.report import write_reports
from engine.notifier import notify_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scanner.main")


def symbol_keywords(symbol: str) -> list[str]:
    base = symbol.replace("USDT", "").lower()
    aliases = {
        "btc": ["btc", "bitcoin"],
        "eth": ["eth", "ethereum"],
        "sol": ["sol", "solana"],
        "bnb": ["bnb", "binance coin"],
        "xrp": ["xrp", "ripple"],
        "doge": ["doge", "dogecoin"],
    }
    return aliases.get(base, [base])


def gather_macro_context() -> dict:
    logger.info("拉取宏观背景数据...")
    return {
        "macro_risk": macro_calendar.macro_risk_window_hours(),
        "dxy": macro_market.get_dxy_trend(),
        "us10y": macro_market.get_us10y_yield_trend(),
        "btc_etf": macro_market.get_btc_etf_flow(),
        "eth_etf": macro_market.get_eth_etf_flow(),
    }


def macro_market_score(macro_ctx: dict) -> float | None:
    """把DXY + 美债收益率趋势合并成一个 [-1,1] 的宏观联动分数。"""
    scores = []
    dxy = macro_ctx.get("dxy", {})
    us10y = macro_ctx.get("us10y", {})
    mapping = {"偏空": -0.6, "偏多": 0.6, "中性": 0.0}
    if dxy.get("available"):
        scores.append(mapping.get(dxy["bias_for_crypto"], 0.0))
    if us10y.get("available"):
        scores.append(mapping.get(us10y["bias_for_crypto"], 0.0))
    if not scores:
        return None
    return sum(scores) / len(scores)


def analyze_symbol(symbol: str, macro_ctx: dict, all_news: list, prev_state: dict) -> dict | None:
    logger.info("分析 %s ...", symbol)

    per_tf_klines = {}
    for tf in TIMEFRAMES:
        kl = bf.get_klines(symbol, tf)
        if kl:
            per_tf_klines[tf] = kl
        time.sleep(0.1)  # 简单限速,避免触发交易所速率限制

    if "1h" not in per_tf_klines or len(per_tf_klines["1h"]) < 60:
        logger.warning("%s 数据不足,跳过", symbol)
        return None

    # ---- 多周期共振 ----
    resonance = multi_timeframe.resonance_score(per_tf_klines)

    # ---- ICT/SMC (用1h作为主结构周期) ----
    ict_result = ict_smc.analyze(per_tf_klines["1h"])

    # ---- 裸K (用15m,更贴近短线入场时机) ----
    naked_k = price_action.naked_k_score(per_tf_klines.get("15m", per_tf_klines["1h"]))

    # ---- 资金费率 ----
    premium = bf.get_premium_index(symbol)
    current_funding = float(premium["lastFundingRate"]) if premium and "lastFundingRate" in premium else None
    funding_history = bf.get_funding_rate_history(symbol)
    funding_sig = microstructure.funding_rate_signal(current_funding, funding_history)

    # ---- OI 背离(需要跨运行状态) ----
    oi_data = bf.get_open_interest(symbol)
    oi_now = float(oi_data["openInterest"]) if oi_data and "openInterest" in oi_data else None
    oi_prev = prev_state.get(symbol, {}).get("last_oi")
    oi_sig = microstructure.oi_divergence_signal(per_tf_klines["1h"], oi_now, oi_prev)

    # ---- 现货/永续 基差 + CVD背离 ----
    spot_klines = bs.get_spot_klines(symbol, "1h")
    spot_perp_sig = microstructure.spot_perp_signal(spot_klines, per_tf_klines["1h"])

    # ---- 订单簿失衡(多交易所) ----
    binance_depth = bf.get_order_book(symbol, limit=100)
    okx_depth = okx.get_order_book(symbol)
    obi_sig = microstructure.order_book_imbalance_signal(binance_depth, okx_depth)

    # ---- 新闻情绪 ----
    news_sig = news_fetcher.compute_news_sentiment_score(all_news, symbol_keywords(symbol))

    # ---- 宏观联动 ----
    macro_score = macro_market_score(macro_ctx)

    signal_scores = {
        "multi_tf_resonance": resonance["score"],
        "ict_smc_structure": ict_result["score"],
        "price_action_naked_k": naked_k["score"],
        "funding_rate": funding_sig.get("score"),
        "open_interest": oi_sig.get("score") if "score" in oi_sig else None,
        "spot_perp_basis": spot_perp_sig.get("score"),
        "order_book_imbalance": obi_sig.get("score"),
        "news_sentiment": news_sig.get("score"),
        "macro_calendar": None,  # 宏观日历只用于风险提示,不参与方向打分(权重在config中默认置0处理)
        "macro_market": macro_score,
        "etf_flow": None,
    }

    verdict = compute_master_verdict(signal_scores)

    # ---- 生成交易计划(Line 1 短线 + Line 2 结构性波段) ----
    direction = "long" if verdict["total_score"] > 0 else "short"
    plans = []
    if abs(verdict["total_score"]) >= 15:  # 太中性就不给具体入场计划
        scalp = build_scalp_plan(symbol, per_tf_klines.get("15m", []), ict_result["detail"], direction)
        if scalp:
            plans.append(scalp)

        swings_4h = find_swing_points(per_tf_klines.get("4h", per_tf_klines["1h"]))
        swing = build_swing_plan(symbol, per_tf_klines.get("4h", per_tf_klines["1h"]), swings_4h, direction)
        if swing:
            plans.append(swing)

    # 更新状态供下一轮OI背离对比
    prev_state[symbol] = {"last_oi": oi_now, "updated_at": datetime.now(timezone.utc).isoformat()}

    return {
        "symbol": symbol,
        "verdict": verdict,
        "plans": plans,
        "raw_signals": {
            "resonance": resonance,
            "ict_smc": ict_result,
            "naked_k": naked_k,
            "funding": funding_sig,
            "open_interest": oi_sig,
            "spot_perp": spot_perp_sig,
            "order_book_imbalance": obi_sig,
            "news_sentiment": {"score": news_sig["score"],
                               "matched_titles": [n.title for n in news_sig["matched"][:5]]},
        },
    }


def main():
    scan_time = datetime.now(timezone.utc).isoformat()
    logger.info("=== 扫描开始 %s ===", scan_time)

    prev_state = load_state()

    symbols = bf.get_all_usdt_perpetual_symbols()
    tickers = bf.get_24h_tickers()
    top_symbols = bf.rank_symbols_by_volume(symbols, tickers, MAX_SYMBOLS_TO_SCORE)
    logger.info("全市场共 %d 个USDT永续合约,按成交量筛选出 %d 个进入精算", len(symbols), len(top_symbols))

    macro_ctx = gather_macro_context()
    all_news = news_fetcher.fetch_all_news()
    logger.info("拉取到 %d 条新闻/公告", len(all_news))

    results = []
    for sym in top_symbols:
        try:
            r = analyze_symbol(sym, macro_ctx, all_news, prev_state)
            if r:
                results.append(r)
        except Exception:  # noqa: BLE001 - 单个symbol失败不能拖垮整体扫描
            logger.exception("分析 %s 时出错,已跳过", sym)

    # 按|综合分数|排序,展示最有把握的机会在前面
    results.sort(key=lambda r: abs(r["verdict"]["total_score"]), reverse=True)
    top_results = results[:TOP_N_REPORT]

    paths = write_reports(scan_time, macro_ctx, top_results, out_dir="reports")
    logger.info("报告已生成: %s", paths)

    save_state(prev_state)

    # 推送摘要(如果配置了 secrets)
    summary_lines = [f"*机构级永续合约扫描* {scan_time}\n"]
    for r in top_results[:5]:
        v = r["verdict"]
        summary_lines.append(f"{r['symbol']}: {v['direction']} ({v['total_score']}分, 置信度{v['confidence']})")
    notify_result = notify_all("\n".join(summary_lines))
    logger.info("推送结果: %s", notify_result)

    logger.info("=== 扫描结束,共产出 %d 个交易计划标的 ===", len(top_results))


if __name__ == "__main__":
    main()
