# 机构级永续合约扫描报告
生成时间(UTC): 2026-11-12T18:42:31.561263+00:00

## 宏观背景
- 最近宏观风险事件: **非农就业数据(NFP)**,距离约 536.5 小时
- CPI 预计发布窗口(粗略): 2026-11-10 ~ 2026-11-15  _(CPI精确日期未在config.CPI_RELEASE_DATES_KNOWN中维护,建议核对BLS官网后补充)_
- BTC现货ETF最近一日净流入: -1113.7M USD(Minimum)
- BTC现货ETF累计净流入: 55171.0M USD
- ETH现货ETF最近一日净流入: -465.1M USD(Minimum)

> 说明:目前只有 BTC/ETH 有现货ETF与足够流动性的期权市场,这是市场现实而非抓取限制;若未来其他币种ETF/期权上市,只需在config.py扩展即可复用同一套逻辑。

- 地缘政治风险信号(来源: RSS关键词近似(GDELT不可用时的备用方案)): **中**,相关标题示例: Ethereum researchers drop faster blocks to race toward quantum defenses in 2027; Bitcoin slides toward $71K as Nvidia stock tumbles after Huang steps down

**特朗普相关言论监听(免费近似,来源GDELT全球媒体转述,非直接抓取其社交账号)**:
- [ria.ru] Как и обещали : США вернули Венесуэле миллиарды долларов (20261112T070000Z)
- [fnnews.com] 美 민주 , 미시시피 승리로 상원 55석 ... 마지막 알래스카 언제 ?  (20261112T064500Z)
- [postregister.com] AI data centers face new scrutiny after midterm elections (20261112T053000Z)
- [afr.com] Bitcoin price slumps after record US spot ETF outflows as post - election rally fades (20261112T053000Z)
- [riotimesonline.com] Russia Ambassador Alexander Darchiev Dies at 66 (20261112T053000Z)
> 说明:这是新闻媒体对相关言论的转述报道,通常有几分钟到几十分钟延迟,无法做到社交媒体秒级抢跑,但对波段/日内交易时效性足够。

## 交易计划
本轮扫描未发现任何标的满足最低分析门槛。

---
**免责声明**:本报告由自动化脚本生成,所有信号均为规则化近似计算,不构成投资建议。ICT/SMC结构判定、资金费率拥挤度、新闻情绪打分、清算区间模拟等均有其局限性,务必结合自身风险承受能力独立判断。
