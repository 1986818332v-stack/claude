"""
主编排脚本 —— "山寨特种兵/永不空仓"版本。

运行方式: python main.py
(GitHub Actions 会按 .github/workflows/scan.yml 里的 cron 定时调用)
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone

from config import (
    MAX_SYMBOLS_TO_SCORE, TOP_N_REPORT, TIMEFRAMES, ALTCOIN_FORCE_INCLUDE,
    ALPHA_MODE, ALPHA_WEIGHTS, FORCE_TOP_N_ALWAYS,
)
from fetchers import binance_futures as bf
from fetchers import binance_spot as bs
from fetchers import okx
from fetchers import news as news_fetcher
from fetchers import macro_calendar
from fetchers import macro_market
from fetchers import deribit
from fetchers import geopolitical

from analysis import multi_timeframe, ict_smc, price_action, microstructure
from analysis import liquidity_pools, volume_profile, phase_classifier, anomaly_rank
from analysis.ict_smc import find_swing_points
from analysis.liquidation_map import simulate_liquidation_clusters

from engine.verdict import compute_master_verdict
from engine.trade_plan import build_trade_plan
from engine.state import load_state, save_state
from engine.report import write_reports
from engine.notifier import notify_all
from engine.portfolio_risk import analyze_portfolio_risk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scanner.main")

OPTIONS_ENABLED_SYMBOLS = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}


def symbol_keywords(symbol: str) -> list[str]:
    base = symbol.replace("USDT", "").lower()
    aliases = {
        "btc": ["btc", "bitcoin"], "eth": ["eth", "ethereum"], "sol": ["sol", "solana"],
        "bnb": ["bnb", "binance coin"], "xrp": ["xrp", "ripple"], "doge": ["doge", "dogecoin"],
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


def build_scan_pool(max_symbols: int) -> list[str]:
    """全市场symbol按成交量粗排 + 强制纳入山寨特种兵白名单,去重后返回最终扫描池。"""
    symbols = bf.get_all_usdt_perpetual_symbols()
    tickers = bf.get_24h_tickers()
    top_by_volume = bf.rank_symbols_by_volume(symbols, tickers, max_symbols)

    available = set(symbols)
    forced = [s for s in ALTCOIN_FORCE_INCLUDE if s in available]

    pool = list(dict.fromkeys(top_by_volume + forced))  # 保序去重
    return pool


def analyze_symbol(symbol: str, macro_ctx: dict, all_news: list, geo_risk: dict, trump_score: float | None,
                    prev_state: dict, oi_change_pct_pool: dict) -> dict | None:
    logger.info("分析 %s ...", symbol)

    per_tf_klines = {}
    for tf in TIMEFRAMES:
        kl = bf.get_klines(symbol, tf)
        if kl:
            per_tf_klines[tf] = kl
        time.sleep(0.08)

    if "1h" not in per_tf_klines or len(per_tf_klines["1h"]) < 60:
        logger.warning("%s 数据不足,跳过", symbol)
        return None

    resonance = multi_timeframe.resonance_score(per_tf_klines)
    ict_result = ict_smc.analyze(per_tf_klines["1h"])  # 1h结构用于主控打分方向
    naked_k = price_action.naked_k_score(per_tf_klines.get("15m", per_tf_klines["1h"]))

    premium = bf.get_premium_index(symbol)
    current_funding = float(premium["lastFundingRate"]) if premium and "lastFundingRate" in premium else None
    funding_history = bf.get_funding_rate_history(symbol)
    funding_sig = microstructure.funding_rate_signal(current_funding, funding_history)

    oi_data = bf.get_open_interest(symbol)
    oi_now = float(oi_data["openInterest"]) if oi_data and "openInterest" in oi_data else None
    oi_prev = prev_state.get(symbol, {}).get("last_oi")
    oi_sig = microstructure.oi_divergence_signal(per_tf_klines["1h"], oi_now, oi_prev)
    if oi_sig.get("oi_change_pct") is not None:
        oi_change_pct_pool[symbol] = oi_sig["oi_change_pct"]

    spot_klines = bs.get_spot_klines(symbol, "1h")
    spot_perp_sig = microstructure.spot_perp_signal(spot_klines, per_tf_klines["1h"])

    binance_depth = bf.get_order_book(symbol, limit=100)
    okx_depth = okx.get_order_book(symbol)
    obi_sig = microstructure.order_book_imbalance_signal(binance_depth, okx_depth)

    news_sig = news_fetcher.compute_news_sentiment_score(all_news, symbol_keywords(symbol))
    macro_score = macro_market_score(macro_ctx)

    current_price = per_tf_klines["1h"][-1]["close"]
    htf = liquidity_pools.analyze(symbol, current_price)
    htf_score = None
    if htf.get("available"):
        boost = htf["confluence"]["confidence_boost"]
        htf_score = boost if ict_result["score"] >= 0 else -boost

    options_score = None
    options_detail = None
    if symbol in OPTIONS_ENABLED_SYMBOLS:
        options_detail = deribit.compute_options_sentiment(OPTIONS_ENABLED_SYMBOLS[symbol])
        options_score = deribit.options_sentiment_score(options_detail)

    signal_scores = {
        "multi_tf_resonance": resonance["score"],
        "ict_smc_structure": ict_result["score"],
        "price_action_naked_k": naked_k["score"],
        "funding_rate": funding_sig.get("score"),
        "open_interest": oi_sig.get("score"),
        "spot_perp_basis": spot_perp_sig.get("score"),
        "order_book_imbalance": obi_sig.get("score"),
        "news_sentiment": news_sig.get("score"),
        "macro_calendar": None,
        "macro_market": macro_score,
        "etf_flow": None,
        "geopolitical_risk": geo_risk.get("score"),
        "trump_crypto_sentiment": trump_score,
        "htf_liquidity_confluence": htf_score,
        "options_skew": options_score,
    }

    weights = ALPHA_WEIGHTS if ALPHA_MODE else None
    verdict = compute_master_verdict(signal_scores, weights=weights)

    direction = "long" if verdict["total_score"] >= 0 else "short"

    # ---- 永不空仓:无条件生成交易计划,达标与否只是标注,不作为生杀开关 ----
    entry_tf_label = "5m" if per_tf_klines.get("5m") else "15m"
    entry_klines = per_tf_klines.get("5m") or per_tf_klines.get("15m") or per_tf_klines["1h"]
    entry_ict = ict_smc.analyze(entry_klines)

    swings_4h = find_swing_points(per_tf_klines.get("4h", per_tf_klines["1h"]))
    swings_1d = find_swing_points(per_tf_klines.get("1d", per_tf_klines.get("4h", per_tf_klines["1h"])))

    plan = build_trade_plan(symbol, entry_klines, entry_ict["detail"], direction,
                            swings_4h, swings_1d, entry_tf_label)
    plans = [plan] if plan and plan["meets_rr_threshold"] else []
    watchlist = [plan] if plan and not plan["meets_rr_threshold"] else []

    vp = volume_profile.compute_volume_profile(per_tf_klines["1h"])
    vp_note = volume_profile.classify_price_vs_profile(current_price, vp) if vp else None

    phase = phase_classifier.classify_phase(
        per_tf_klines["1h"], oi_sig.get("oi_change_pct"),
        spot_perp_sig.get("notes", []), naked_k.get("patterns", []),
    )

    liq_sim = None
    if vp:
        liq_sim = simulate_liquidation_clusters([vp["poc"], vp["vah"], vp["val"]])

    self_pct = None
    if oi_sig.get("oi_change_pct") is not None:
        self_pct = anomaly_rank.update_history_and_get_percentile(
            prev_state, symbol, "oi_change_pct", oi_sig["oi_change_pct"])

    prev_state[symbol] = {"last_oi": oi_now, "updated_at": datetime.now(timezone.utc).isoformat()}

    return {
        "symbol": symbol,
        "verdict": verdict,
        "plans": plans,
        "watchlist": watchlist,
        "phase": phase,
        "volume_profile": vp,
        "volume_profile_note": vp_note,
        "liquidation_simulation": liq_sim,
        "htf_liquidity": htf,
        "options_sentiment": options_detail,
        "anomaly_self_history_pct": self_pct,
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
    logger.info("=== 扫描开始 %s (ALPHA_MODE=%s) ===", scan_time, ALPHA_MODE)

    prev_state = load_state()

    top_symbols = build_scan_pool(MAX_SYMBOLS_TO_SCORE)
    logger.info("本轮扫描池共 %d 个标的(含强制纳入的山寨特种兵白名单)", len(top_symbols))

    macro_ctx = gather_macro_context()
    all_news = news_fetcher.fetch_all_news()

    geo_risk = geopolitical.get_geopolitical_risk()
    if not geo_risk.get("available"):
        logger.warning("GDELT地缘政治信号不可用,退化为RSS关键词密度近似")
        geo_risk = news_fetcher.compute_geopolitical_risk_score(all_news)
        geo_risk["source"] = "RSS关键词近似(GDELT不可用时的备用方案)"
    else:
        geo_risk["source"] = "GDELT新闻语气时间线"

    trump_headlines = geopolitical.get_trump_crypto_headlines()
    trump_score = None
    if trump_headlines.get("available") and trump_headlines.get("headlines"):
        trump_score = geopolitical.trump_headline_score(trump_headlines["headlines"])

    logger.info("拉取到 %d 条新闻/公告,地缘政治风险来源: %s", len(all_news), geo_risk.get("source"))

    results = []
    oi_change_pct_pool: dict[str, float] = {}
    for sym in top_symbols:
        try:
            r = analyze_symbol(sym, macro_ctx, all_news, geo_risk, trump_score, prev_state, oi_change_pct_pool)
            if r:
                results.append(r)
        except Exception:  # noqa: BLE001
            logger.exception("分析 %s 时出错,已跳过", sym)

    for r in results:
        sym = r["symbol"]
        market_pct = anomaly_rank.cross_sectional_percentile(oi_change_pct_pool, sym)
        r["anomaly_market_pct"] = market_pct
        r["anomaly_note"] = anomaly_rank.build_anomaly_note(
            r.get("anomaly_self_history_pct"), market_pct,
            r["raw_signals"]["open_interest"].get("oi_change"), "OI变化量(张)",
        )

    results.sort(key=lambda r: abs(r["verdict"]["total_score"]), reverse=True)

    # ---- 永不空仓:即使全市场分数都很低,也强制保留至少 FORCE_TOP_N_ALWAYS 个标的 ----
    n_report = max(TOP_N_REPORT, FORCE_TOP_N_ALWAYS) if results else 0
    top_results = results[:n_report]
    weak_market = bool(top_results) and abs(top_results[0]["verdict"]["total_score"]) < 40

    portfolio_risk = analyze_portfolio_risk(top_results)

    paths = write_reports(scan_time, macro_ctx, top_results, portfolio_risk, geo_risk, trump_headlines,
                          weak_market, out_dir="reports")
    logger.info("报告已生成: %s", paths)

    save_state(prev_state)

    summary_lines = [f"*机构级永续合约扫描* {scan_time}\n"]
    if weak_market:
        summary_lines.append("(市场整体评分偏低,以下为相对最优局部剧本)")
    if portfolio_risk.get("warning"):
        summary_lines.append(portfolio_risk["warning"])
    for r in top_results[:5]:
        v = r["verdict"]
        summary_lines.append(f"{r['symbol']}: {v['direction']} ({v['total_score']}分, 置信度{v['confidence']})")
    notify_result = notify_all("\n".join(summary_lines))
    logger.info("推送结果: %s", notify_result)

    logger.info("=== 扫描结束,共产出 %d 个交易计划标的 ===", len(top_results))


if __name__ == "__main__":
    main()
