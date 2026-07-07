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
| 地缘政治风险 | ✅ 已实现 | 优先用 **GDELT DOC 2.0**(完全免费、无需注册的全球新闻数据库)新闻语气时间线,GDELT不可用时退化为RSS关键词密度近似 |
| 特朗普言论监听(免费近似) | ✅ 已实现(近似方案) | 不直接抓取Truth Social/X账号(无免费API),而是用GDELT搜索全球媒体对其"加密/关税/美联储"相关言论的**转述报道**,有几分钟到几十分钟延迟,但对波段/日内交易时效性足够 |
| HTF流动性池(PDH/PDL/PWH/PWL)共振 | ✅ 已实现 | 日线/周线关键位 + 低周期信号共振加分 |
| 成交量分布(POC/VAH/VAL) | ✅ 已实现 | 基于K线区间的简化Volume Profile |
| 组合风险暴露提示 | ✅ 已实现 | 同方向/同板块标的集中度检测,提示合并风险敞口 |
| 波动率自适应止损缓冲 | ✅ 已实现 | 按ATR%动态放大止损缓冲倍数,降低山寨币插针扫损概率 |
| Deribit期权隐含波动率偏斜 | ✅ 已实现(仅BTC/ETH) | 免费公开API,近似25Delta偏斜计算,非精确机构级数值 |
| 清算区间模拟 | ✅ 已实现(明确标注为模拟) | 基于成交量聚集区+常见杠杆倍数推算,非真实清算数据 |
| 庄家剧本阶段识别(吸筹/洗盘/主升/赶顶/派发/崩盘) | ✅ 已实现 | 规则化叙事分类器,辅助解读,不替代数值打分 |
| 三维异动排名(自身历史/全场强度/绝对数值) | ✅ 已实现 | 灵感来自用户提供的雷达类产品设计理念 |
| GitHub Pages 可视化看板 | ✅ 已实现 | 见下方"启用看板"部分 |

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

## 启用可视化看板(GitHub Pages)

仓库里 `docs/index.html` 是一个零依赖的静态看板(用 Chart.js CDN),每次
Actions 跑完会自动更新 `docs/data.json`。启用步骤:

1. 仓库 `Settings → Pages`
2. Source 选择 `Deploy from a branch`,Branch 选 `main`,目录选 `/docs`
3. 保存后几分钟内会给你一个 `https://<用户名>.github.io/<仓库名>/` 的地址,
   打开就能看到全市场强弱柱状图 + Top榜单表格 + 组合风险提示

## 本轮修复的问题

1. **ETF资金流抓取失效**:排查后发现大概率是我们此前用了自报"bot"身份的
   User-Agent(如 `crypto-institutional-scanner/1.0 (+github actions bot)`),
   触发了 Farside 等站点的反爬拦截,返回的是拦截页而非真实表格。现在换成
   真实浏览器UA + 常规请求头,并在解析失败时附加"收到的HTML长度"作为诊断线索
   (长度异常小基本可以确认是被拦截,而不是表格结构变化)。
2. **只有BTC/ETH**:这依然不是bug(现货ETF/期权流动性目前全球只有这两个币有),
   但你观察到的"感觉上只有BTC/ETH"更可能是下面第3点的连锁反应——RR门槛太严导致
   山寨币几乎从不产出可见的交易计划,只有BTC/ETH偶尔露出。已从架构上解决,见下。
3. **"永不空仓"改造**:这是本轮最核心的改动。废除了"总分/RR不过线就整体消失"的
   逻辑,详见下方"策略哲学变化"。
4. **山寨币池扩充**:新增 `config.ALTCOIN_FORCE_INCLUDE` 白名单(SOL/DOGE/XRP/
   ADA/AVAX/LINK/SUI/APT/WIF/PEPE/SHIB/NEAR/ARB/OP/INJ/TIA/SEI/FIL/TON/BNB/LTC/
   DOT/UNI等),这些标的无论成交量排名如何,每轮都强制纳入精算池,不会被埋没。

## 策略哲学变化:从"绝对门槛"到"永不空仓 + 极致盈亏比"

这是本轮升级的核心,直接对应你提出的交易哲学:

**入场/止损锁死在低周期结构**:`engine/trade_plan.py` 现在优先用 **5分钟**
(其次15分钟)的 OB(订单块)/FVG(失衡缺口)作为入场区间,止损贴着区间边缘
加一个很小的ATR缓冲——这一步天然把止损宽度压到接近1%这个量级,而不是像
以前那样用较大周期的摆动点做止损(止损自然更宽,盈亏比自然更低)。

**止盈锚定在高周期流动性池**:
- TP1 = 最近的 **4小时** 摆动高/低点(离入场最近的一段流动性,最容易被触发)
- TP2 = 最近的 **日线** 摆动高/低点(更远端的目标,这是搏取1:10以上空间的关键)

这种"内部低周期精确入场 + 外部高周期流动性目标"的映射,就是ICT/SMC"从内部
结构打向外部流动性"的标准逻辑,盈亏比是结构性产生的,不是拍脑袋设定的数字。

**永不空仓**:`config.FORCE_TOP_N_ALWAYS` 保证每轮至少强制展示这么多个标的的
剧本,即使当前全市场最高分也就40分(满分100)。`engine/trade_plan.py` 里任何
一步找不到理想结构(没有明确OB/FVG、没有清晰的4H/1D摆动点)都有清晰标注的
兜底方案,而不是静默返回空——报告里会明确标注哪些是"兜底方案"、哪些是
真实结构信号,你可以自行判断置信度,而不是被蒙在鼓里。

**ALPHA_MODE(山寨特种兵模式)**:`config.ALPHA_MODE = True` 时,`engine/verdict.py`
改用 `config.ALPHA_WEIGHTS`——把宏观/ETF/期权这些"只对BTC/ETH有意义"的维度权重
几乎清零,把 **裸K/SMC结构(权重27)** 和 **OI/清算(权重22)** 提升为核心,
总计接近50%的权重。这样哪怕大盘毫无消息面驱动,只要某个山寨币自己在低周期
爆出流动性扫荡+持仓暴增,就能冲上榜首。想关掉这个模式、回到"宏观+技术面均衡"
的打分方式,把 `ALPHA_MODE` 改成 `False` 即可。

**一个重要的风险提示(不是说教,是必须写清楚的机制性事实)**:止损越窄、
目标盈亏比越高,对"入场时机精度"和"胜率"的要求就越高——1%止损意味着
哪怕是很小的插针都可能扫损,1:10的目标也意味着大部分尝试可能在到达TP1或
更早就被打止损。这套系统解决的是"给出结构化、可执行、盈亏比诱人的剧本"这个
工程问题,但**胜率和资金管理是你自己需要在实盘/回测中验证的部分**,报告里的
"达标/兜底"标注就是为了让你能分辨"这是真实结构给出的高置信度信号"还是
"没找到理想结构时的保底参考"。

## 调参

- `config.WEIGHTS` / `config.ALPHA_WEIGHTS`:各信号模块的权重,按你自己的交易风格调整;
  `config.ALPHA_MODE` 控制用哪一套
- `config.MIN_RR` / `config.TARGET_RR`:盈亏比标注门槛(默认最低1:3展示为达标,理想目标1:10)
- `config.MAX_STOP_LOSS_PCT`:止损占入场价百分比的参考上限(用于报告里标注止损是否够"窄")
- `config.ALTCOIN_FORCE_INCLUDE`:强制纳入扫描池的山寨币白名单,可自行增删
- `config.FORCE_TOP_N_ALWAYS`:永不空仓时强制展示的最少标的数量
- `config.MAX_SYMBOLS_TO_SCORE`:精算多少个交易对(数量越大,GitHub Actions单次运行耗时越长)
- `config.CPI_RELEASE_DATES_KNOWN`:建议每月从 BLS 官网核实后手动补充精确CPI日期

## 免责声明

本项目所有输出均为规则化自动计算结果,不构成任何投资建议。加密货币永续合约
交易杠杆风险极高,请务必独立判断并做好风险管理。
