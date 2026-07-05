"""
纯离线单元测试:用合成的K线数据(不依赖任何网络请求)验证各分析模块
能正确运行并返回结构合理的结果。这弥补了沙盒环境无法访问 Binance/OKX
等外部API进行端到端测试的限制。
"""
import math
import random
import unittest

from analysis import indicators, price_action, ict_smc, multi_timeframe, fib_zones
from engine.verdict import compute_master_verdict
from engine.trade_plan import build_scalp_plan, build_swing_plan


def make_trending_klines(n=200, start=100.0, drift=0.15, noise=0.6, seed=42):
    random.seed(seed)
    klines = []
    price = start
    for i in range(n):
        o = price
        price += drift + random.uniform(-noise, noise)
        c = price
        h = max(o, c) + random.uniform(0, noise)
        l = min(o, c) - random.uniform(0, noise)
        vol = random.uniform(100, 1000)
        taker_buy = vol * random.uniform(0.4, 0.7)
        klines.append({
            "open": o, "high": h, "low": l, "close": c, "volume": vol,
            "quote_volume": vol * c, "trades": int(vol),
            "taker_buy_base": taker_buy, "taker_buy_quote": taker_buy * c,
            "open_time": i, "close_time": i + 1,
        })
    return klines


class TestIndicators(unittest.TestCase):
    def test_atr_and_bbw(self):
        kl = make_trending_klines()
        a = indicators.atr(kl)
        self.assertIsNotNone(a)
        self.assertGreater(a, 0)
        bb = indicators.bollinger_band_width(kl)
        self.assertIsNotNone(bb)
        pct = indicators.bbw_percentile(kl)
        self.assertTrue(0 <= pct <= 1)

    def test_cvd(self):
        kl = make_trending_klines()
        cvd = indicators.approximate_cvd(kl)
        self.assertEqual(len(cvd), len(kl))


class TestPriceAction(unittest.TestCase):
    def test_naked_k_score_range(self):
        kl = make_trending_klines()
        result = price_action.naked_k_score(kl)
        self.assertTrue(-1.0 <= result["score"] <= 1.0)


class TestICTSMC(unittest.TestCase):
    def test_analyze_structure(self):
        kl = make_trending_klines(n=150, drift=0.3)
        result = ict_smc.analyze(kl)
        self.assertTrue(-1.0 <= result["score"] <= 1.0)
        self.assertIn("bos_choch", result["detail"])

    def test_fvg_and_order_blocks_dont_crash(self):
        kl = make_trending_klines(n=150, drift=-0.3)
        swings = ict_smc.find_swing_points(kl)
        fvgs = ict_smc.detect_fvg(kl)
        obs = ict_smc.detect_order_blocks(kl, swings)
        self.assertIsInstance(fvgs, list)
        self.assertIsInstance(obs, list)


class TestMultiTimeframe(unittest.TestCase):
    def test_resonance(self):
        up = make_trending_klines(drift=0.3, seed=1)
        per_tf = {"15m": up, "1h": up, "4h": up}
        r = multi_timeframe.resonance_score(per_tf)
        self.assertTrue(-1.0 <= r["score"] <= 1.0)
        self.assertTrue(r["aligned"])


class TestFibZones(unittest.TestCase):
    def test_dynamic_fib_zone_long(self):
        kl = make_trending_klines(n=150, drift=0.3)
        zone = fib_zones.dynamic_fib_zone(swing_high=150, swing_low=100, direction="long", klines=kl)
        self.assertLess(zone["zone_low"], zone["zone_high"])


class TestVerdictAndPlans(unittest.TestCase):
    def test_master_verdict_handles_missing(self):
        scores = {
            "multi_tf_resonance": 0.5, "ict_smc_structure": 0.3, "price_action_naked_k": 0.2,
            "funding_rate": None, "open_interest": None, "spot_perp_basis": 0.1,
            "order_book_imbalance": None, "news_sentiment": 0.0, "macro_calendar": None,
            "macro_market": None, "etf_flow": None,
        }
        v = compute_master_verdict(scores)
        self.assertIn(v["direction"], ["看多", "看空", "偏多", "偏空", "中性/观望"])
        self.assertTrue(len(v["missing_modules"]) > 0)

    def test_scalp_plan_none_when_no_zones(self):
        kl = make_trending_klines(n=50)
        plan = build_scalp_plan("TESTUSDT", kl, {"order_blocks": [], "fair_value_gaps": []}, "long")
        self.assertIsNone(plan)

    def test_swing_plan_structure(self):
        kl = make_trending_klines(n=150, drift=0.3)
        swings = ict_smc.find_swing_points(kl)
        plan = build_swing_plan("TESTUSDT", kl, swings, "long")
        if plan is not None:
            self.assertIn("entry_zone", plan)
            self.assertLessEqual(plan["entry_zone"][0], plan["entry_zone"][1])
            self.assertGreaterEqual(plan["risk_reward"], 3.0)


if __name__ == "__main__":
    unittest.main()
