"""
全局配置文件
所有可调参数集中在这里,方便迭代而不用改动业务逻辑代码。
"""

# ---------- 市场扫描范围 ----------
QUOTE_ASSET = "USDT"                 # 只扫描 USDT 本位永续合约
MIN_24H_QUOTE_VOLUME = 20_000_000    # 过滤掉流动性太差的合约(USDT),避免滑点陷阱
MAX_SYMBOLS_TO_SCORE = 40            # 出于 API 速率限制,先按成交量粗排,再精算前 N 个
TOP_N_REPORT = 10                    # 最终报告里展示的交易计划数量

# ---------- 多周期 ----------
TIMEFRAMES = ["15m", "1h", "4h"]
KLINE_LIMIT = 300                    # 每个周期拉取的K线数量,足够计算 ATR/BBW/结构

# ---------- 权重(全局主控判定 / 100分制,可自行调整) ----------
# 各模块最终会被归一化到 [-1, 1] 或 [0,1],再乘以下面权重求和
WEIGHTS = {
    "multi_tf_resonance": 16,       # 三周期趋势是否共振
    "ict_smc_structure": 17,        # ICT/SMC 结构信号 (OB/FVG/liquidity sweep/BOS-CHoCH)
    "price_action_naked_k": 8,      # 裸K形态(吞没、insidebar、pinbar等)
    "funding_rate": 7,              # 资金费率极值/趋势
    "open_interest": 9,             # OI 变化 vs 价格背离
    "spot_perp_basis": 7,           # 现货/永续基差、CVD背离
    "order_book_imbalance": 5,      # 多空盘口失衡(如可用)
    "news_sentiment": 6,            # Binance公告 + CoinDesk/Cointelegraph 新闻
    "macro_calendar": 0,            # 仅用于风险提示,不参与方向打分(权重恒为0)
    "macro_market": 5,              # DXY、美债收益率联动
    "etf_flow": 0,                  # 默认关闭:仅对 BTC/ETH 有意义,由 main.py 针对性启用
    "geopolitical_risk": 5,         # 免费近似:新闻关键词密度代理地缘政治风险(替代付费Trump/X监听)
    "htf_liquidity_confluence": 8,  # 低周期信号是否与高周期流动性池(PDH/PDL/PWH/PWL)共振
    "options_skew": 0,              # 默认关闭:仅对 BTC/ETH 有意义(Deribit流动性集中在这两个币),由main.py针对性启用
}

# ---------- 风险 ----------
MIN_RR = 3.0            # 最低风险回报比(用户偏好: 最低1:3, 目标1:5+)
TARGET_RR = 5.0
ATR_SL_MULTIPLIER = 1.5  # 止损 = ATR * 此倍数,用于确定结构性止损宽度参考

# ---------- 宏观日历(手动维护,来源:federalreserve.gov,请定期核对更新) ----------
# 格式: (开始日期, 结束日期, 是否含经济预测/点阵图 SEP)
FOMC_MEETINGS_2026 = [
    ("2026-01-27", "2026-01-28", False),
    ("2026-03-17", "2026-03-18", True),
    ("2026-04-28", "2026-04-29", False),
    ("2026-06-16", "2026-06-17", True),
    ("2026-07-28", "2026-07-29", False),
    ("2026-09-15", "2026-09-16", True),
    ("2026-10-27", "2026-10-28", False),
    ("2026-12-08", "2026-12-09", True),
]
FOMC_MEETINGS_2027 = [
    ("2027-01-26", "2027-01-27", False),
    ("2027-03-16", "2027-03-17", True),
    ("2027-04-27", "2027-04-28", False),
    ("2027-06-08", "2027-06-09", True),
    ("2027-07-27", "2027-07-28", False),
    ("2027-09-14", "2027-09-15", True),
    ("2027-10-26", "2027-10-27", False),
    ("2027-12-07", "2027-12-08", True),
]

# CPI / 非农没有像 FOMC 一样早早公布的精确日期表,通常规则是:
# - 非农 (NFP): 每月第一个周五 (美国劳工部 BLS)
# - CPI: 通常在每月 10-15 号之间发布,由 BLS 官网逐月公布,建议定期从
#   https://www.bls.gov/schedule/news_release/cpi.htm 核对并更新下方列表
# 这里给出规则近似 + 一个可手动覆盖的精确列表(优先使用精确列表)
CPI_RELEASE_DATES_KNOWN = {
    # "2026-07": "2026-07-14",  # 示例:请从 BLS 官网核实后按月补充
}

# ---------- 数据源 ----------
BINANCE_FUTURES_BASE = "https://fapi.binance.com"
BINANCE_SPOT_BASE = "https://api.binance.com"
OKX_BASE = "https://www.okx.com"

COINDESK_RSS = "https://www.coindesk.com/arc/outboundfeeds/rss/"
COINTELEGRAPH_RSS = "https://cointelegraph.com/rss"
BINANCE_ANN_API = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
    "?type=1&catalogId=48&pageNo=1&pageSize=15"
)

# DXY 与美债收益率 (免费, 无需 key)
STOOQ_DXY_CSV = "https://stooq.com/q/d/l/?s=dxy&i=d"
FRED_DGS10_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"

# ETF 资金流 (免费公开表格, 结构可能变化,做了容错)
FARSIDE_BTC_URL = "https://farside.co.uk/btc/"
FARSIDE_ETH_URL = "https://farside.co.uk/eth/"

# ---------- 推送(可选) ----------
# 通过 GitHub Actions secrets 注入环境变量,留空则跳过推送,只生成报告文件
TELEGRAM_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "TELEGRAM_CHAT_ID"
DISCORD_WEBHOOK_URL_ENV = "DISCORD_WEBHOOK_URL"

# ---------- HTTP ----------
REQUEST_TIMEOUT = 15
USER_AGENT = "crypto-institutional-scanner/1.0 (+github actions bot)"
