"""
全局配置文件
所有可调参数集中在这里,方便迭代而不用改动业务逻辑代码。
"""

# ---------- 市场扫描范围 ----------
QUOTE_ASSET = "USDT"                 # 只扫描 USDT 本位永续合约
MIN_24H_QUOTE_VOLUME = 20_000_000    # 过滤掉流动性太差的合约(USDT),避免滑点陷阱
MAX_SYMBOLS_TO_SCORE = 40            # 出于 API 速率限制,先按成交量粗排,再精算前 N 个
TOP_N_REPORT = 10                    # 最终报告里展示的交易计划数量

# 山寨特种兵模式:这些高波动标的无论成交量排名如何,一律强制纳入本轮精算池,
# 确保"当BTC/ETH死鱼盘时,山寨币的单边扫荡机会不会被埋没"。
# 可自行增删,建议保留那些流动性足够但波动率明显高于BTC/ETH的品种。
ALTCOIN_FORCE_INCLUDE = [
    "SOLUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "SUIUSDT", "APTUSDT", "WIFUSDT", "1000PEPEUSDT", "1000SHIBUSDT",
    "NEARUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "TIAUSDT", "SEIUSDT",
    "FILUSDT", "TONUSDT", "BNBUSDT", "LTCUSDT", "DOTUSDT", "UNIUSDT",
]

# ---------- 多周期 ----------
TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]  # 5m/15m用于精确入场,4h/1d用于流动性池目标位
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
    "geopolitical_risk": 5,         # 地缘政治风险(优先用GDELT新闻语气时间线,免费无需注册)
    "trump_crypto_sentiment": 4,    # 特朗普言论的免费近似:GDELT搜索全球媒体对其相关言论的转述报道
    "htf_liquidity_confluence": 8,  # 低周期信号是否与高周期流动性池(PDH/PDL/PWH/PWL)共振
    "options_skew": 0,              # 默认关闭:仅对 BTC/ETH 有意义(Deribit流动性集中在这两个币),由main.py针对性启用
}

# ---------- 山寨特种兵模式 (ALPHA_MODE) ----------
# 开启后:大幅降低宏观/ETF/期权这类"只对BTC/ETH有意义"的维度权重,
# 把裸K/SMC结构 与 OI/清算 提到核心地位——逻辑是:哪怕大盘(BTC)没有任何
# 消息面驱动,单个山寨币自己在低周期爆出流动性扫荡+持仓暴增,依然值得给出剧本。
ALPHA_MODE = True

ALPHA_WEIGHTS = {
    "multi_tf_resonance": 14,
    "ict_smc_structure": 27,        # 裸K/SMC结构权重大幅提升(核心)
    "price_action_naked_k": 13,
    "funding_rate": 8,
    "open_interest": 22,            # OI/清算维度大幅提升(核心)
    "spot_perp_basis": 8,
    "order_book_imbalance": 6,
    "news_sentiment": 2,
    "macro_calendar": 0,
    "macro_market": 0,              # ALPHA模式下不再用大盘宏观拖累山寨币打分
    "etf_flow": 0,
    "geopolitical_risk": 0,
    "trump_crypto_sentiment": 0,
    "htf_liquidity_confluence": 0,
    "options_skew": 0,
}
# 注: BTC/ETH 本身依然享受完整的宏观/ETF/期权数据(见 main.py 里的按symbol判断逻辑),
# ALPHA_WEIGHTS 主要影响的是"当宏观数据缺失时不要惩罚山寨币",而不是完全禁用宏观维度。

# ---------- 永不空仓:强制Top N输出 ----------
# 废除"总分不过线就全灭"的硬门槛。即使全市场今天最高分也就40分(满分100),
# 依然强制把排名最高的 FORCE_TOP_N 个标的筛出来,并在报告里如实标注
# "市场整体评分偏低,以下为弱势背景下的相对最优局部剧本"。
FORCE_TOP_N_ALWAYS = 3

# ---------- 风险:极致盈亏比 ----------
# 用户的核心诉求:用15m/5m级别的FVG/OB把止损卡到尽量窄(理想情况下浮动止损约1%附近),
# 用4H/1D级别的流动性池(摆动高低点、未回补缺口)做止盈目标,搏取1:5甚至1:10以上的空间。
# 这两个数字是"期望达到的高质量门槛"用于标注"达标/未达标",不再是硬性淘汰线——
# 只要有结构可循,不达标的方案依然会展示(见 engine/trade_plan.py 的 watchlist 逻辑),
# 只是标注清楚"未达到极致盈亏比目标"。
MIN_RR = 3.0             # 展示为"达标"所需的最低盈亏比
TARGET_RR = 10.0         # 理想目标盈亏比(用于TP2这类远端流动性池目标的定价参考)
ATR_SL_MULTIPLIER = 1.2  # 止损缓冲基础倍数(配合动态ATR%修正),盯紧15m结构做窄止损
MAX_STOP_LOSS_PCT = 1.5  # 止损占入场价的百分比上限参考值(用于报告里标注"止损是否落在极致区间")

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
# 用真实浏览器UA而不是自报"bot"身份——部分数据源(如Farside)对自称爬虫的UA
# 会走Cloudflare等防护策略,返回拦截页而不是真实内容,伪装成普通浏览器请求更稳定。
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

