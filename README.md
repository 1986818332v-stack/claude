# Crypto Institutional Perpetual Scanner

扫描 Binance 全市场 USDT 本位永续合约,融合 ICT/SMC 结构、裸K形态、多周期共振、
资金费率/OI/现货永续背离、订单簿失衡、新闻情绪、宏观日历(FOMC/CPI/非农)、
DXY、美债收益率、ETF资金流,输出"区间入场 + 确认条件"形式的机构级交易计划。
通过 GitHub Actions 定时运行,报告以 Markdown/JSON 形式提交回本仓库。

## 已知限制(务必先读)

这不是一个营销页面,而是诚实的能力边界说明:

| 模块 | 状态 | 说明 |
|---|---|---|
| 全市场永续扫描/K线/OI/资金费率/订单簿 | ✅ 免费稳定 | Binance 公开API,无需Key |
| ICT/SMC结构(OB/FVG/BOS/CHoCH/流动性扫荡) | ✅ 已实现 | 规则化近似,非"官方标准答案"(概念本身也无统一量化定义) |
| 裸K形态、多周期共振 | ✅ 已实现 | 纯OHLC规则 |
| 现货/永续CVD、基差背离 | ✅ 已实现 | CVD为近似值(用taker买卖比推算,非逐笔tick数据) |
| 多交易所订单簿(Binance+OKX) | ✅ 已实现 | 公开API,失败自动降级 |
| Binance公告 / CoinDesk / Cointelegraph | ✅ 已实现 | RSS/公开接口,只做标题级情绪打分,不转载正文 |
| FOMC会议日历 | ✅ 已实现 | 手动维护静态列表(2026/2027已核实),**每年需要更新一次** |
| 非农(NFP)日期 | ✅ 规则推算 | "每月第一个周五"的长期规律,极端情况请自行核对BLS官网 |
| CPI精确日期 | ⚠️ 部分实现 | 无固定规律,默认给"10-15号"粗略窗口,精确日期需手动在 `config.py` 里维护 |
| DXY / 美债10年期收益率 | ✅ 已实现 | Stooq / FRED 免费数据 |
| BTC/ETH 现货ETF资金流 | ⚠️ 尽力而为 | 解析 Farside 公开表格,页面结构变化可能导致解析失败(会明确标注"不可用",不编造数字) |
| **特朗普 Truth Social/X 言论** | ❌ 未实现 | 无可靠免费实时API(X搜索API已收费,Truth Social无公开API),按你的要求本轮跳过 |
| **地缘政治事件量化** | ❌ 未实现 | 无结构化免费信号源,按你的要求本轮跳过 |

如果未来想补齐最后两项,需要接入付费数据源(如 X API Basic/Pro 层级、GDELT 事件数据库等),
届时只需新增一个 `fetchers/` 模块并接入 `config.WEIGHTS`,架构已经预留好扩展位置。

## 架构

```
config.py              全局参数、权重、宏观日历
fetchers/               所有外部数据抓取(每个数据源一个文件,互不影响,单点失败自动降级)
analysis/               纯计算逻辑:技术指标、ICT/SMC、裸K、多周期共振、微观结构、动态斐波那契
engine/                 编排层:全局主控加权判定、交易计划生成、状态持久化、报告输出、推送
main.py                 入口:串联以上所有模块,跑一轮完整扫描
.github/workflows/      GitHub Actions 定时任务配置
reports/                每轮扫描生成的报告(latest.md / latest.json / history/ 归档 / state.json状态)
```

数据流:`main.py` → 拉取全市场symbol并按成交量粗排 → 对Top N逐个精算多维信号 →
`engine/verdict.py` 加权汇总为"全局主控判定" → `engine/trade_plan.py` 生成
Line1(短线)/ Line2(结构性波段)两条计划,**入场恒为区间+确认条件,不给单点价格** →
`engine/report.py` 输出报告 → GitHub Actions 把 `reports/` 目录 commit 回仓库。

## 本地运行

```bash
pip install -r requirements.txt
python main.py
```

运行后查看 `reports/latest.md`。

## 部署到 GitHub(把这个仓库变成你自己的开源项目)

我(Claude)没有你的 GitHub 账号权限,没法替你创建/推送仓库,以下步骤你自己执行:

```bash
# 1. 在 GitHub 网站上新建一个空仓库,例如 crypto-institutional-scanner

# 2. 在本地(下载这些文件后)执行:
cd crypto-institutional-scanner
git init
git add .
git commit -m "init: institutional perpetual scanner"
git branch -M main
git remote add origin https://github.com/<你的用户名>/crypto-institutional-scanner.git
git push -u origin main
```

推送后,GitHub Actions 会自动按 `.github/workflows/scan.yml` 里的 cron
(默认每30分钟)运行扫描并把报告提交回仓库的 `reports/` 目录。你可以在仓库的
Actions 页面手动点击 "Run workflow" 立即触发一次,不用等定时任务。

### 可选:配置推送通知

如果想在生成报告的同时收到 Telegram / Discord 推送,在仓库
`Settings → Secrets and variables → Actions` 里添加:

- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`(通过 @BotFather 创建bot获取token)
- 或 `DISCORD_WEBHOOK_URL`(Discord频道设置里创建Webhook)

不配置也完全没问题,报告依然会正常生成在 `reports/latest.md`。

## 调参

- `config.WEIGHTS`:各信号模块的权重,按你自己的交易风格调整
- `config.MIN_RR` / `config.TARGET_RR`:风险回报比门槛(默认最低1:3,目标1:5)
- `config.MAX_SYMBOLS_TO_SCORE`:精算多少个交易对(数量越大,GitHub Actions单次运行耗时越长)
- `config.CPI_RELEASE_DATES_KNOWN`:建议每月从 BLS 官网核实后手动补充精确CPI日期

## 免责声明

本项目所有输出均为规则化自动计算结果,不构成任何投资建议。加密货币永续合约
交易杠杆风险极高,请务必独立判断并做好风险管理。
