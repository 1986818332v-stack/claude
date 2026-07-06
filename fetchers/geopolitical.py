"""
GDELT DOC 2.0 API —— 完全免费、无需注册/无需Key的全球新闻数据库。

用途(替代方案说明,务必读):
- 我们没有 X/Truth Social 的免费实时API,所以"特朗普言论"这块不是直接抓他的账号,
  而是搜索全球新闻媒体对他"关于加密货币/关税/美联储/利率"相关言论的**转述报道**。
  重大言论通常几分钟到几十分钟内就会被大量媒体转述,时效性对波段/日内交易是够用的,
  但对"消息一出就秒级抢跑"的极端场景确实做不到。
- 地缘政治同理:用新闻语气(tone)时间线做一个粗粒度的"全球紧张度"指标,
  不是精确的事件分类,但方向性参考有效且完全免费。

API文档: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations
from fetchers.http_client import get_json

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

GEOPOLITICAL_QUERY = (
    '(war OR sanctions OR invasion OR conflict OR "military strike" OR tariff OR '
    '"trade war" OR ceasefire OR missile)'
)
TRUMP_CRYPTO_QUERY = (
    '"trump" (bitcoin OR crypto OR cryptocurrency OR tariff OR "federal reserve" OR '
    '"interest rate" OR "rate cut" OR "rate hike")'
)


def _fetch(query: str, mode: str, timespan: str = "24h", maxrecords: int = 20) -> dict | None:
    params = {
        "query": query,
        "mode": mode,
        "timespan": timespan,
        "format": "json",
    }
    if mode == "artlist":
        params["maxrecords"] = maxrecords
        params["sort"] = "datedesc"
    return get_json(GDELT_BASE, params=params)


def get_geopolitical_risk() -> dict:
    """
    用过去24h vs 过去48h相比的新闻语气均值变化,估计地缘政治紧张度是否在升级。
    GDELT tone 范围大致在 -10(极负面)到 +10(极正面),0附近为中性。
    紧张度上升(tone转负 且相关报道量增多) -> 风险提示,偏向"降低仓位/规避新开仓"，
    不作为方向性多空信号。
    """
    data = _fetch(GEOPOLITICAL_QUERY, mode="timelinetone", timespan="3d")
    if not data or "timeline" not in data:
        return {"available": False}

    try:
        points = data["timeline"][0]["data"]
        if len(points) < 2:
            return {"available": False}
        latest_tone = points[-1]["value"]
        avg_tone_prior = sum(p["value"] for p in points[:-1]) / len(points[:-1])
        tone_drop = avg_tone_prior - latest_tone  # 正数=情绪在恶化

        if tone_drop > 2:
            risk_level = "明显升级"
            score = -0.6
        elif tone_drop > 1:
            risk_level = "温和升级"
            score = -0.3
        else:
            risk_level = "平稳"
            score = 0.0

        return {
            "available": True,
            "latest_tone": round(latest_tone, 2),
            "tone_change": round(tone_drop, 2),
            "risk_level": risk_level,
            "score": score,  # 仅作为风险规避提示,不参与方向性打分主权重
        }
    except (KeyError, IndexError, TypeError, ZeroDivisionError):
        return {"available": False}


def get_trump_crypto_headlines(limit: int = 8) -> dict:
    """
    搜索全球新闻里"特朗普 + 加密货币/关税/美联储/利率"相关的最新报道标题。
    只返回标题+链接+来源+时间,不转载正文。
    """
    data = _fetch(TRUMP_CRYPTO_QUERY, mode="artlist", timespan="24h", maxrecords=limit)
    if not data or "articles" not in data:
        return {"available": False, "headlines": []}

    headlines = []
    for a in data["articles"][:limit]:
        headlines.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "domain": a.get("domain", ""),
            "seen_date": a.get("seendate", ""),
        })
    return {"available": True, "headlines": headlines, "count": len(headlines)}


def trump_headline_score(headlines: list[dict]) -> float:
    """
    极简规则打分:出现越多"降息/宽松/利好"字样偏多,出现越多"关税/加息/制裁"字样偏空。
    这不是精确的NLP情绪分析,只是一个可解释的粗筛,真正决策权重很低。
    """
    if not headlines:
        return 0.0
    bullish = ["rate cut", "dovish", "stimulus", "支持", "利好", "friendly"]
    bearish = ["tariff", "rate hike", "hawkish", "sanction", "ban", "crackdown", "关税", "制裁"]
    score = 0
    for h in headlines:
        t = h["title"].lower()
        score += sum(1 for kw in bullish if kw in t)
        score -= sum(1 for kw in bearish if kw in t)
    return max(-1.0, min(1.0, score / 5.0))
