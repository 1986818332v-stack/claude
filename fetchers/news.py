"""
新闻与公告抓取。

重要说明(版权/合规):本模块只提取标题 + 发布时间 + 链接,用于生成一个
"新闻情绪打分",绝不缓存或转载正文。报告中展示新闻时只显示标题和原文链接。

数据源:
- Binance 公告(官方 CMS 接口,非公开文档化但长期稳定使用的公开数据)
- CoinDesk RSS
- Cointelegraph RSS
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from config import BINANCE_ANN_API, COINDESK_RSS, COINTELEGRAPH_RSS
from fetchers.http_client import get_json, get_text

# 极简关键词情绪词典。这不是严格的 NLP 模型,只是一个可解释、可调整的粗筛信号,
# 真正的决策权重很低(见 config.WEIGHTS["news_sentiment"]),仅作为风险提示辅助。
BULLISH_KEYWORDS = [
    "approval", "approved", "etf inflow", "adoption", "partnership", "upgrade",
    "listing", "integration", "institutional buy", "rate cut", "dovish",
    "上线", "利好", "批准", "合作", "机构增持", "降息",
]
BEARISH_KEYWORDS = [
    "hack", "exploit", "lawsuit", "ban", "delist", "delisting", "outflow",
    "investigation", "rate hike", "hawkish", "liquidation", "collapse",
    "黑客", "起诉", "禁止", "下架", "调查", "加息", "清算", "崩盘",
]


@dataclass
class NewsItem:
    source: str
    title: str
    link: str
    published: str = ""


def _score_text(text: str) -> int:
    t = text.lower()
    score = 0
    for kw in BULLISH_KEYWORDS:
        if kw in t:
            score += 1
    for kw in BEARISH_KEYWORDS:
        if kw in t:
            score -= 1
    return score


def fetch_binance_announcements(limit: int = 15) -> list[NewsItem]:
    data = get_json(BINANCE_ANN_API)
    items: list[NewsItem] = []
    if not data:
        return items
    try:
        catalogs = data["data"]["catalogs"]
        for cat in catalogs:
            for art in cat.get("articles", [])[:limit]:
                items.append(
                    NewsItem(
                        source="Binance公告",
                        title=art.get("title", ""),
                        link=f"https://www.binance.com/en/support/announcement/{art.get('code','')}",
                        published=str(art.get("releaseDate", "")),
                    )
                )
    except (KeyError, TypeError, IndexError):
        pass
    return items[:limit]


def _parse_rss(xml_text: str, source_name: str, limit: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    if not xml_text:
        return items
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            published = date_el.text if date_el is not None else ""
            if title:
                items.append(NewsItem(source=source_name, title=title.strip(),
                                       link=(link or "").strip(), published=published or ""))
            if len(items) >= limit:
                break
    except ET.ParseError:
        pass
    return items


def fetch_coindesk(limit: int = 15) -> list[NewsItem]:
    text = get_text(COINDESK_RSS)
    return _parse_rss(text, "CoinDesk", limit)


def fetch_cointelegraph(limit: int = 15) -> list[NewsItem]:
    text = get_text(COINTELEGRAPH_RSS)
    return _parse_rss(text, "Cointelegraph", limit)


def fetch_all_news(limit_per_source: int = 15) -> list[NewsItem]:
    news: list[NewsItem] = []
    news += fetch_binance_announcements(limit_per_source)
    news += fetch_coindesk(limit_per_source)
    news += fetch_cointelegraph(limit_per_source)
    return news


def compute_news_sentiment_score(news_items: list[NewsItem], symbol_keywords: list[str]) -> dict:
    """
    针对某个 symbol(比如 BTC 传入 ['btc','bitcoin']),在新闻标题中做关键词命中 + 情绪打分。
    返回 {"score": -1..1, "matched": [NewsItem,...]}
    """
    matched = []
    raw_score = 0
    for item in news_items:
        title_lower = item.title.lower()
        if any(re.search(rf"\b{re.escape(kw)}\b", title_lower) for kw in symbol_keywords):
            matched.append(item)
            raw_score += _score_text(item.title)
        elif any(kw in title_lower for kw in ("crypto", "bitcoin", "regulation", "sec", "加密")):
            # 全市场级新闻,权重减半
            raw_score += _score_text(item.title) * 0.5

    normalized = max(-1.0, min(1.0, raw_score / 5.0))
    return {"score": normalized, "matched": matched}
