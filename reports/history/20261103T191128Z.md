# 机构级永续合约扫描报告
生成时间(UTC): 2026-11-03T19:09:29.386291+00:00

## 宏观背景
- 最近宏观风险事件: **非农就业数据(NFP)**,距离约 80.5 小时
- CPI 预计发布窗口(粗略): 2026-11-10 ~ 2026-11-15  _(CPI精确日期未在config.CPI_RELEASE_DATES_KNOWN中维护,建议核对BLS官网后补充)_
- BTC现货ETF最近一日净流入: -1113.7M USD(Minimum)
- BTC现货ETF累计净流入: 56649.0M USD
- ETH现货ETF最近一日净流入: -465.1M USD(Minimum)

> 说明:目前只有 BTC/ETH 有现货ETF与足够流动性的期权市场,这是市场现实而非抓取限制;若未来其他币种ETF/期权上市,只需在config.py扩展即可复用同一套逻辑。

- 地缘政治风险信号(来源: RSS关键词近似(GDELT不可用时的备用方案)): **中**,相关标题示例: Justin Sun seeks sanctions against Trump-linked World Liberty Financial over UAE ties; CZ warns of more AI-driven hacks following Binance’s historic $6.3 billion heist

**特朗普相关言论监听(免费近似,来源GDELT全球媒体转述,非直接抓取其社交账号)**:
- [fnnews.com] 민주 , 상하원 장악땐 사법부 인준 제동 … 트럼프  조기 레임덕  [ 美 중간선거  운명의 날 ]  (20261103T111500Z)
- [texasguardian.com]   If our people vote , we win in a landslide : Trump urges Republicans to turn out ahead of US midterms (20261103T111500Z)
- [pasadenastarnews.com] Republicans deserve to lose control of the Congress (20261103T111500Z)
- [fnnews.com] 트럼프 운명의 날 … 5000弗 줄것  공언 [ 美 중간선거  운명의 날 ]  (20261103T111500Z)
- [brandonsun.com]   Screwed either way : Republican senator fights backlash over Trump tariffs in Maine – Brandon Sun (20261103T111500Z)
> 说明:这是新闻媒体对相关言论的转述报道,通常有几分钟到几十分钟延迟,无法做到社交媒体秒级抢跑,但对波段/日内交易时效性足够。

## 交易计划
本轮扫描未发现任何标的满足最低分析门槛。

---
**免责声明**:本报告由自动化脚本生成,所有信号均为规则化近似计算,不构成投资建议。ICT/SMC结构判定、资金费率拥挤度、新闻情绪打分、清算区间模拟等均有其局限性,务必结合自身风险承受能力独立判断。
