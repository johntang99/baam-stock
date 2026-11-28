# AI 产业两年展望（2026 年底 – 2028 年底）：谁会涨，谁会被压

> 版本：2026-11-28 · 用途：内部讨论，配合 baam-stock 预测系统选股与特征设计
> **不构成投资建议。** 以下观点基于公开报道（多为二手媒体对财报的整理），数字以原始财报 / SEC 文件为准；部分数据带"二手/未核实"标记。

---

## 0. 一句话结论

**AI 的钱还在往"卡脖子"的环节流：GPU/定制芯片、HBM 内存、先进制程与封装、电力和机房设备。** 2027 年大厂资本开支仍会明显增长（分析师估计约 1.2–1.3 万亿美元）。但 2026 年 11 月出现了一个新变量：**AI 基建的融资成本和信用风险正在快速上升**（CoreWeave、Oracle 信用违约互换创新高，Alphabet/Amazon/Meta 自由现金流转负）。所以未来两年的主线是"需求仍强，但资金链决定节奏"。

被压的一方主要是三类：**按座位收费的 SaaS 软件、可被 AI 代理绕过的信息/中介平台、被内存涨价挤压利润的 PC/手机硬件**，以及**高杠杆的新兴云（neocloud）**。

**政治因素（第 7 节）**：反对数据中心耗电的力量在两党选民中都有，2026 年 11 月选举后得州、俄亥俄、佐治亚换上主张限制的州长。它主要推迟和抬高新建成本，不改变总需求方向，利好自带电源和已通电的一方。

---

## 1. 现在站在什么位置（截至 2026-11-28 的关键事实）

| 事实 | 数字 | 来源/日期 |
|---|---|---|
| NVIDIA Q3 FY27 营收 | 1158 亿美元，同比 +103%；数据中心 1076 亿；毛利率 74.9% | NVIDIA 新闻稿，2026-11-17 |
| NVIDIA Q4 指引 | 1300 亿 ±3%（含额外一周，不含中国数据中心收入）；毛利率降至 71–72%（Rubin 爬坡） | 同上 |
| NVIDIA 管理层风波 | 黄仁勋 11 月 11/12 日辞任 CEO，11 月 23 日在白宫施压下被董事会恢复职位，当天股价 +31.5%（多家来源一致）；独立董事会调查仍在进行，S&P 已将其 AA 评级列入负面观察，12 月 1 日、3 日需赴国会作证 | 8-K 链接 / ROIC 2026-11-25 / Glass Desk 2026-11-27 |
| 五大云厂 2026 资本开支 | 约 7800–8000 亿美元，较 2025 年（约 3970 亿）翻倍 | Alcapital 汇总，2026-11-02 |
| 2027 资本开支预估 | 高盛约 1.2 万亿，美银 1.32 万亿（含 neocloud），大摩 1.58 万亿（含租赁）；**公司尚未给具体数字**，Alphabet 说"显著增加"，Amazon 说"meaningfully more" | 同上 / Yield Theory，2026-11-25 |
| 已签未交付的订单 | 微软商业 RPO 6770 亿（+73%）、Google Cloud 积压约 5610 亿、Amazon 积压约 5780 亿 | Luminix，2026-10-30 |
| 大厂现金流 | Alphabet Q3 FCF −91 亿（停止回购、增发股票）；Amazon 近 12 月 FCF −424 亿；Meta Q3 FCF −21 亿；微软仍为正 | Luminix，2026-10-30 |
| 信用压力 | CoreWeave 5 年 CDS 约 1330bp（隐含约 68% 五年违约概率），2031 年到期债收益率约 17.9%；Oracle CDS 约 356bp 创纪录；软银 CDS 501bp | ROIC，2026-11-25/27 |
| 宏观 | 市场担心美联储加息，MUFG 认为"风险从 AI 估值转向融资成本和可得性" | ROIC，2026-11-25 |

---

## 2. 七大趋势

### 2.1 算力资本开支：2027 年继续涨，但增速开始看融资脸色
- 2026 年翻倍之后，2027 年市场预期再涨约 50%。微软称 FY27 下半年（2027 年 1–6 月）资本开支"加速"，Amazon CEO 称对 2027、2028 年"可见度很好"。
- 但除微软外，大厂已靠发债、增发股票来支撑开支（Meta 计划最多约 950 亿美元股票融资，数字在不同来源间有出入）。若利率上行，**2027 下半年到 2028 年是增速可能放缓的窗口**。
- 有一个容易被忽略的细节：UBS 估计 2025–27 年资本开支增量中很大一部分来自内存涨价（Alcapital 转引，需谨慎看待）。也就是说"开支涨"不完全等于"算力等比例涨"。

### 2.2 推理需求取代训练成为主引擎
- Azure 同比 +48%（需求"超过供给"），AWS +39% 且管理层预期 2027–28 年 >40%（后者为摘要信息）。AI 代理、编码代理消耗的 token 远多于聊天，推理量成为持续性需求。
- 推理更看重性价比，**利好定制 ASIC（Broadcom、Marvell 的 Google TPU / OpenAI / Anthropic 芯片）和 AMD**，NVIDIA 份额会被稀释但总量仍涨。

### 2.3 电力和数据中心：最硬的瓶颈
- 北美托管机房空置率约 1.4%（CBRE，2026 上半年）；PJM 容量拍卖连续三年触顶 325 美元/MW·天，仍缺 6831MW。
- 燃气轮机全球订单 >100GW，年产能只有 60–70GW，美国新机交付约 6 年（Reuters 转引，2026-11-09）。GE Vernova 燃机积压 + 预留槽位 116–122GW，槽位排到 2032 年。
- 大摩估算 2026–28 年美国数据中心电力净缺口约 32GW。**这条线 2028 年前很难缓解，确定性最高。**

### 2.4 内存 / HBM：超级周期，但市场已按"周期顶"定价
- 美光 FQ4 2026 营收 542 亿（+379%），毛利率 87%；FQ1 2027 指引 615 亿。CEO 称 2027 年产出 75% 以上已锁定，价格"远高于 2026"。
- 但股价从 1255 高点回撤约 38%，远期市盈率仅约 4.5 倍（theinference，2026-11-14），说明市场在赌 2028 年供给追上来。另外约 320 亿美元长约带价格上限，会封住上行弹性。
- 副作用：内存涨价让手机、PC 成本暴涨（低端机内存占物料成本从 20% 升到 54%），2026 Q3 全球手机出货 −22%，PC −20%。

### 2.5 网络与互连：从"附属"变成独立大市场
- Marvell 投资者日（2026-10-06）把 2030 年 TAM 上调到 4000 亿美元，FY2031 营收目标 700–900 亿，其中网络/互连约 375 亿。Credo 营收 +114.7%。
- 规模化集群（scale-up / scale-out）、光模块、有源电缆是 Rubin 时代的必需品。

### 2.6 AI 代理冲击软件和信息服务
- 软件 ETF（IGV）较 2026 上半年高点跌超 30%，2 月第一周就蒸发超 1 万亿市值。逻辑是：代理减少员工 → 减少软件座位数；代理直接调用数据 → 绕过数据平台和中介。
- 反方：摩根大通认为软件估值处于 25–30 年低位、部分抛售是机械性的；Salesforce Agentforce ARR 已超 15 亿（+240%）。**2027 年是"能不能转成按结果/用量收费"的验证年**（Dan Ives 也称 2027 是 AI 变现拐点年）。

### 2.7 信用与融资风险上升
- 新兴云约 85% 靠负债融资（堪萨斯城联储），CoreWeave Q3 营业利润 2.07 亿，利息支出 8.46 亿。
- NVIDIA 自身承担了最多 1180 亿美元担保（其中约 1050 亿与租给 OpenAI 的园区相关），以及约 5180 亿未来采购/租赁承诺（二手转述 8-K）。**AI 供应链之间的"循环融资"是未来两年最大的系统性风险。**

---

## 3. 可能的赢家（16 家）

排序大致按"确定性 × 当前证据强度"。⭐ = 本项目观察名单。

| # | 公司 | 代码 | 为什么会赢（具体依据） | 主要风险 |
|---|---|---|---|---|
| 1 | ⭐ NVIDIA | NVDA | Q3 营收 1158 亿（+103%），Q4 指引 1300 亿；Vera Rubin NVL72 已量产出货，是"史上最快爬坡"；CoWoS 2027 分配约 54–56%（Nomura） | 管理层风波和董事会调查；毛利率降到 71–72%；担保和承诺规模巨大；前三大客户占 36% |
| 2 | ⭐ 台积电 | TSM | Q3 营收 467 亿美元（+41%），毛利率 66.4%；全年增长上调至约 44%；2nm 产能 2027 年翻倍以上；CoWoS 2027 年 +80%；2026–28 资本开支"显著高于"前三年；高端 AI 加速器 85.8% 用其封装 | 台海地缘；海外厂稀释毛利 3–4 个百分点 |
| 3 | ⭐ Broadcom | AVGO | AI 半导体季收入 167 亿（+221%），Q4 指引 217 亿；AI 收入目标 FY26 约 580 亿 → FY27 约 1150 亿 → FY28 约 2300 亿；客户 Google TPU、Anthropic、OpenAI；季度 FCF 137 亿 | 交付节奏受电力和 HBM 拖累；近 30 天 26 次下调盈利预测；客户集中 |
| 4 | ⭐ 美光 | MU | 营收 +379%、毛利率 87%；2027 产出 75%+ 已锁定，有 26 份照付不议长约、约 320 亿预付款 | 周期股，市场按顶部定价（约 4.5 倍远期 PE）；长约价格上限；2028 供给增加 |
| 5 | ⭐ AMD | AMD | Q3 营收 134 亿（+45%），数据中心 85 亿（+97%）；Q4 指引约 170 亿（+66%）；Anthropic、Meta、微软、OpenAI、Oracle 已在跑 MI450/Helios 机柜 | CoWoS 只分到约 8–9%；CUDA 生态差距；估值偏高（约 29 倍） |
| 6 | ⭐ Marvell | MRVL | FY28 营收目标上调到约 200 亿，FY31 目标 700–900 亿；与 Google 签约（认股权证对应最多约 1200 亿累计订单）；数据中心占 79% | 弹性最大也最脆弱：截至 11-19 一个月跌约 39%；定制芯片 FY27 下半年才放量，兑现风险高 |
| 7 | Credo | CRDO | 营收 +114.7% 至 4.79 亿，连续 8 次超预期；有源电缆是机柜内互连刚需 | 最大客户占 33% |
| 8 | GE Vernova | GEV | Q3 订单 293 亿（有机 +96%），积压 1970 亿；燃机槽位排到 2032 年；2026 FCF 指引上调到 160–170 亿 | 风电业务亏损 4–5 亿；关税 |
| 9 | Vertiv | VRT | Q3 销售 43 亿（+61%）；递延收入 41 亿（年初 18 亿）；全年有机增长 37–39%；液冷/电源是 Rubin 机柜必需 | 已停止披露订单和积压，透明度下降 |
| 10 | Constellation Energy | CEG | 2026 年签了约 8500MW 长期购电协议（含 Amazon 690MW、20 年）；核电增容 890MW | 并网/同址规则 2027 上半年才定 |
| 11 | Vistra | VST | 收购 Cogentrix 约 5500MW；2027 EBITDA 指引 77–85 亿 | ERCOT 电价敞口 |
| 12 | Talen Energy | TLN | 2027 EBITDA 指引 25–28.5 亿；PJM 容量价触顶；15 亿加速回购 | 负债从 68 亿升到 95 亿 |
| 13 | Quanta Services | PWR | Q3 营收 120 亿（去年 76 亿），积压 637 亿；电网和数据中心施工 | 劳动力和项目执行 |
| 14 | Bloom Energy | BE | 现场燃料电池绕开电网排队：NTT DATA 900MW（2027 起交付）、Oracle 最多 2.8GW | 订单是否为确定订单未披露；估值波动大 |
| 15 | Palantir | PLTR | Q3 营收 +96%，美国商业 +148%，全年指引上调至 +91%（新闻稿标题） | 估值极高，AI 交易回调时跌幅大 |
| 16 | 微软 | MSFT | 大厂中唯一 FCF 仍为正（Q1 +186 亿）；Azure +48%，供不应求；RPO 6770 亿 | Copilot 变现节奏；资本开支 2027 加速 |

非美股但值得一提：SK 海力士、三星（HBM/DRAM 超级周期，三星年内 +283%，截至 2026-08）。

---

## 4. 可能被压 / 受损的一方（15 家/组）

| # | 公司 | 代码 | 为什么承压（具体依据） | 什么会让它翻身 |
|---|---|---|---|---|
| 1 | Salesforce | CRM | 截至 4 月底年内 −31%；FY27 营收增长指引只有 10–11%；座位制收费被代理侵蚀 | Agentforce（ARR 超 15 亿，+240%）规模化，转为按结果收费 |
| 2 | Adobe | ADBE | 截至 4 月底年内 −31%；Mizuho 降级，预计未来 2–3 年有机增长"最多高个位数"；生成式图像/视频工具替代 | AI-first ARR 已翻三倍，若能持续 |
| 3 | ServiceNow | NOW | 截至 4 月底年内 −40%；Q1 中东本地部署订单滑单 | 订阅增长仍有 21%，Now Assist 目标 15 亿 ACV |
| 4 | Thomson Reuters | TRI | 信息服务一个月跌 15–35%（ABN AMRO）：代理可直接检索法律/税务资料 | 自有数据被 AI 厂商授权使用 |
| 5 | S&P Global / Moody's | SPGI / MCO | 同上，数据平台被代理绕过的担忧 | 评级业务护城河仍在；AI 发债潮反而带来评级收入 |
| 6 | RELX（ADR） | RELX | 同上（学术/法律数据库） | 同上 |
| 7 | Booking | BKNG | 派杰：AI 购物/出行代理绕过中介（Meta Muse 代理购物已屏蔽 Amazon） | 与代理平台达成分发合作 |
| 8 | HP Inc | HPQ | 毛利率仅约 22%，内存涨价缓冲最薄；Q3 2026 出货 −30.9%（IDC） | 内存价格 2028 年回落 |
| 9 | 苹果 | AAPL | 每年 2 亿+ iPhone 吃内存成本；Counterpoint 预计 2027 年 iPhone 出货约 −4% | 涨价转嫁成功；端侧 AI 换机潮 |
| 10 | 英特尔 | INTC | 10-30 因 Q4 指引疲弱单日跌超 30%，为 1979 年以来最差一天；在 AI 加速器中份额边缘化 | 代工（18A/14A）拿到大客户 |
| 11 | CoreWeave | CRWV | CDS 约 1330bp（隐含五年违约概率约 68%）；Q3 利息支出 8.46 亿 > 营业利润 2.07 亿；负债 469 亿；年内约 −42%；高管 11-20 卖股 | 12 月初 45 亿美元贷款顺利出售；积压 1325 亿逐步变现 |
| 12 | Oracle | ORCL | 2026-07 被下调至 BBB-；CDS 创纪录；FCF 为负；2880 亿未起租的数据中心租约；新墨西哥 2.45GW 项目出现不可抗力通知 | OpenAI 合同如期付款（Oracle 称资金已到位） |
| 13 | Nebius / IREN | NBIS / IREN | 与 CoreWeave 同类的高负债 neocloud，11-24 分别跌 13%、15% | 融资成本回落 |
| 14 | Accenture / Cognizant | ACN / CTSH | （推断为主，证据较弱）摩根大通称 AI 支出在挤占传统 IT 项目预算；代码代理压缩外包人天 | 成为企业部署 AI 代理的集成商 |
| 15 | Xiaomi 等安卓手机（非美股） | — | Q3 出货 −29%；三星 Galaxy A 明年涨价最多 19% 并减产约 20% | 内存价格回落 |

### 两面性公司（不归入任一边，但最值得跟踪）
- **Alphabet、Amazon、Meta**：云和广告业务很强（AWS +39%，Google Cloud 营业利润率升至 36.2%），但 FCF 转负、靠发债/增发，Alphabet 财报后单日跌约 12%。它们是 AI 需求的来源，**它们的资本开支指引就是整个链条的"总开关"**（2027 年 1–2 月 Q4 财报给出 2027 数字）。
- **Dell**：AI 服务器积压 950 亿创纪录，但内存涨价打击消费端（消费收入 −15%），一个月回撤约 30%。

---

## 5. 对观察名单的含义（NVDA、AMD、AVGO、MU、TSM、MRVL）

| 代码 | 两年趋势看法 | 短期（本系统 60 分钟/收盘/次日）最需要的驱动特征 |
|---|---|---|
| NVDA | 偏正面，但个股事件风险上升 | 管理层/董事会调查新闻、出口管制、大客户资本开支指引、neocloud 信用事件 |
| TSM | 正面，确定性最高 | 每月 10 日左右月营收、CoWoS 产能报道、台海新闻 |
| AVGO | 正面 | 客户（Google/OpenAI/Anthropic）芯片交付节奏、盈利预测修正方向 |
| MU | 基本面强，股价看周期预期 | DRAM/HBM 合约价、下次财报（预计 2026-12-16）、三星/海力士扩产新闻 |
| AMD | 正面，份额提升 | Helios 出货进度、OpenAI 等客户认股权证相关公告 |
| MRVL | 弹性最大、波动最大 | 定制芯片放量证据、Google 订单兑现 |

**对系统设计的建议**（可作为后续特征，不改现有数据合同，按路线图另开文档）：
1. 加入"AI 信用压力"因子：CoreWeave/Oracle CDS 或债券收益率、HY 利差，这是 2026-11 影响整个板块的新驱动。
2. 加入"大厂资本开支事件"：MSFT/GOOGL/AMZN/META/ORCL 财报日对六只观察股的联动。
3. 加入内存价格（DRAM 合约价）作为 MU 的外生变量。
4. 美联储利率预期（加息担忧）对高估值、高负债 AI 股的敏感度。

---

## 6. 什么会让这个判断翻转

**看空方向（赢家变输家）：**
1. 2027 年 1–2 月大厂 Q4 财报给出的 2027 资本开支低于约 1.2 万亿共识，或出现"砍单/延期"。
2. CoreWeave 等 neocloud 违约或再融资失败（关注 12 月初 45 亿美元贷款出售），引发信用连锁，NVIDIA 担保敞口暴露。
3. 美联储加息、长端利率上行，融资驱动的建设放缓。
4. 内存供给 2028 年追上来，HBM/DRAM 价格下跌，美光利润快速回落。
5. AI 应用收入跟不上（Damodaran 估计 AI 产品收入约 2500 亿，与万亿级开支差距大），市场重新质疑投资回报。
6. 台海或出口管制升级。
7. 得州、俄亥俄、佐治亚新州长 2027 年真的推出全州暂停令，或各州要求数据中心承担全部发电成本（见第 7 节）。

**看多方向（输家翻身）：**
1. SaaS 公司成功从座位制转为用量/结果制，2027 年财报出现增长重新加速。
2. 内存价格回落，PC/手机厂毛利修复。
3. 利率下降，neocloud 融资压力解除。

---

## 7. 政治与监管阻力：反对 AI 数据中心和电力扩张的力量有多大？（2026-11-28 补充）

### 7.1 先说结论
- **这是真实且正在变大的因素，但它主要影响"节奏、地点和成本分摊"，不太可能在两年内掐断 AI 算力总需求。** 我把它的权重排在"融资/信用风险"之后、与"电力设备短缺"同级。
- **反对力量不是某一个党派独有的。** 民主党确实借这个议题赢了 2026 年中期选举，但反对的基层群众里有大量共和党选民和农村社区，第一个按下暂停键的大州是共和党州长治下的得州。
- 对股票来说，它的作用是**把赢家从"建在哪里都行"转向"已经拿到电、或能自己发电的公司"**。

### 7.2 证据：反对来自两党，而且已经落地
| 事实 | 数字/细节 | 来源 |
|---|---|---|
| 民调 | 65% 反对在自己社区建数据中心：民主党 76%、独立选民 67%、**共和党 52%**（UMass，2026-08）；Gallup 2026-03 约 7 成反对 | The Conversation 2026-11-25；Stateline 2026-05-28 |
| 反对项目的政客 | 共和党 55%、民主党 45%；全美 40 个州有 188 个反对团体（2026-02） | Introl 2026-02 |
| 2026-11-03 地方公投 | 41 项限制数据中心的地方投票，**40 项获通过**；俄亥俄小镇 Defiance 64.7%、Pataskala 73.6%、Granville 82.5% 支持限制（多为偏共和党的小城镇/郊区） | Fox Business 2026-11-05（引 Ballotpedia） |
| 州长选举（非官方计票） | **得州**：民主党 Gina Hinojosa 以 57% 对 41% 击败 Abbott，竞选承诺包括暂停新建数据中心、取消税收优惠、冻结电价；**俄亥俄**：民主党 Amy Acton 当选，支持"有条件暂停"（数据中心须自付全部电网成本）；**佐治亚**：民主党 Keisha Lance Bottoms 当选，主张全州暂停研究影响 | Scripps 2026-11-04；Fox Business 2026-11-05 |
| 选前已有的州级动作 | 得州 Abbott（共和党）9 月下令暂停数据中心环境许可并审计 474GW 并网申请；纽约 Hochul（民主党）7 月暂停 50MW 以上项目环境许可最长一年；宾州 Shapiro（民主党）要求 25MW 以上须先获地方批准，并须"自建、自带或自购"电力 | Capacity 2026-09；Scripps |
| 城市/县 | 丹佛、西雅图、俄克拉荷马城（红州）、印第安纳 13 个县（红州）、密歇根约 20 个社区、犹他 Box Elder 县（红州）、北卡多个县等已暂停 | Stateline；Resilience 2026-07-23 |
| 被拖延的项目 | 2026 年一季度至少 75 个大项目、超 1300 亿美元被推迟或取消；截至 2026-08 超 145 个项目受影响；QTS（黑石）放弃弗吉尼亚 300 亿美元项目，Amazon 撤回马里兰申请 | Capacity（引 Data Center Watch）；Fox Business（引 S&P Global） |
| 反例 | 怀俄明州夏延拒绝暂停；北达科他 Harwood 约 3/4 选民否决限制；得州 Hood 县 3:2 否决暂停 | Stateline；Fox Business；Introl |

**核心动因是电费，不是意识形态。** 美国居民电价自 2024 年初涨约 10%；俄亥俄部分地区两年涨 20–33%；PJM 容量拍卖让俄亥俄家庭每月多付约 16 美元，市场监察机构估计今年因数据中心多出 73 亿美元容量费用、明年再加 65 亿。其次是用水（四成以上争议项目涉及）、噪音、柴油发电机排放和土地。

### 7.3 联邦层面：方向是"让数据中心自己付钱"，而不是禁止
- **BAAJA 法案（S. 5653）**：共和党 Capito、Lee 与民主党 Whitehouse、Heinrich 联合提出，2026-11-19 参院以 62:33 通过，白宫支持；众院预计 11-30 当周表决。要求 FERC 改规则让新数据中心承担输电成本：估计 10 年约 550 亿美元，每年比现在多约 35 亿；若各州同样处理发电成本，10 年最多约 1360 亿（Grid Strategies 粗估，不含得州）。
- **FERC 2025-12-18 一致裁定** PJM 必须为"同址负载"（数据中心直接接电厂）提供明确的输电服务选项，同时收紧旧的表后（behind-the-meter）净额规则，各州仍保留零售电价和电厂选址权。
- 特朗普政府支持建设，并威胁惩罚把数据中心建到海外的公司；但同时也支持"谁造成成本谁付钱"。
- OpenAI 已公开承诺为自建数据中心支付全部电力成本，Google 出资 1080 万美元给俄亥俄线路升级。**"自付成本"正在成为行业拿许可证的新门票。**

### 7.4 影响有多大？（我的估算，带推断成分）
| 维度 | 估计 | 理由 |
|---|---|---|
| 直接成本 | **小**：每年多付 35 亿美元级别的输电费，相对 2027 年约 1.2 万亿资本开支不到 0.5% | BAAJA 估算 |
| 项目延迟 | **中**：仅 2026 一季度就有超 1300 亿被推迟，相当于年度资本开支的一成以上；电力本来就紧，政治阻力会把交付再往后推 6–18 个月 | Data Center Watch；Broadcom CEO 已提示电力会推迟收入确认 |
| 地理转移 | **中到大**：得州占全美规划容量约 27%（Wells Fargo），新州长 2027 年 1 月上任；若得州真推暂停，是对 2027–28 年节奏影响最大的单一政治变量 | Scripps |
| 总需求 | **小**：已签约的 2.6 万亿积压订单和在建项目不受影响；需求会转向已有电力的园区、亲商州（如怀俄明、北达科他）和海外（但联邦反对外迁） | Yield Theory；Fox Business |

**一句话：政治阻力不会让 AI 资本开支掉头，但会让"电"变得更贵、更稀缺，从而放大第 2.3 节的电力瓶颈。** 这对已经拿到电的一方是利好。

### 7.5 谁更受益、谁更受损
**相对受益：**
- **自带电源/表后发电**：Bloom Energy（BE，现场燃料电池绕开电网排队）、GE Vernova（GEV，航改型燃机已售罄）、Caterpillar 等发电机组厂商（未核实具体订单）。
- **已有核电/燃气机组、可同址供电的独立发电商**：Constellation（CEG）、Vistra（VST）、Talen（TLN）。电力越稀缺，存量电厂越值钱；FERC 同址规则明确后，签约路径更清晰。
- **已经通电的存量机房**：Equinix（EQIX）、Digital Realty（DLR）的现有容量会因新建困难而更稀缺（推断）；微软等手握大量已通电容量的大厂也相对占优。
- **电网设备和施工**：Quanta（PWR）、Vertiv（VRT）。"数据中心自付电网升级"意味着升级工程照做，只是谁买单变了。

**相对受损：**
- **依赖在得州、佐治亚、俄亥俄、弗吉尼亚新拿地新并网的开发商和 neocloud**：CoreWeave（CRWV）、IREN（得州大量布局）、Oracle（ORCL，Stargate 项目）；它们本来就有融资压力，再叠加许可延迟，风险最大。
- **受监管的公用事业公司**：Dominion（D）、AEP、Southern（SO）等的资本开支计划建立在数据中心负荷增长上；新当选州长将任命电力监管者，费率审批会更严、可获批回报率可能下降（推断）。
- **芯片厂的时间风险**：NVDA、AVGO、AMD 的需求不变，但如果机房通不了电，出货和收入确认会延后（Broadcom 已在财报会上提示）。

### 7.6 2027 年需要盯的时间点
1. 2026-11-30 当周：众院对 BAAJA 表决。
2. 2027-01：得州、俄亥俄、佐治亚新州长就职，看第一份行政令或立法提案是"暂停"还是"自付成本 + 继续批"。
3. 2027 上半年：PJM 同址规则落地；宾州、纽约暂停令到期与否。
4. 2027 年 1–2 月大厂财报：留意是否有"因许可/电力延迟"下调交付节奏的表述。

### 7.7 对本系统的建议
- 新增一个"政策事件"标签类型：州级暂停令、电力监管决定、BAAJA 等联邦法案节点。2026 年 11 月 3 日选举夜 AI 数据中心股普遍下跌，说明这类事件有短期价格冲击，适合放进事件解释模块。
- 对 CRWV、ORCL、公用事业这类"受地点影响大"的股票，可在后续阶段加入"项目所在州"维度（按路线图另开文档，不改现有数据合同）。

---

## 8. 10 月 9 日以来为什么跌？（2026-11-28 补充）

### 8.1 一句话
**这次下跌不是一件事造成的，而是三波接连发生。** 10 月是"利率、油价加上对 AI 收入的质疑"。10 月底是"大厂财报暴露现金流压力"。11 月中是"NVIDIA 掌门人危机、AI 信用恐慌，再加上通胀升温推高加息预期"。标普 500 从高点最多跌了约 11.6%（11 月 20 日低点），AI 和半导体股跌得更深。

### 8.2 时间线
| 日期 | 发生了什么 | 市场反应 |
|---|---|---|
| 10-02 | 9 月非农只增加 2.9 万（预期约 8.4 万），失业率 4.2% | — |
| 10-05~07 | 10 年期美债收益率升到约 5.3%，是 2002 年以来最高（两个来源的日期和点位略有出入） | 高估值股承压 |
| **10-06** | **标普 500 收在纪录高点 7819，纳指和 NVIDIA（239 美元）同一天见顶** | 这次下跌的起点 |
| **10-09** | ① 金融时报报道 **OpenAI 的年化收入比此前透露的低约 200 亿美元**，打击了市场对 AI 需求的预期；② 有报道称海湾和霍尔木兹海峡的航运遇袭（背景是伊朗冲突），布伦特油价涨 3.5%，到约 104 美元；③ 30 年期美债拍卖利率 5.62%，美联储官员暗示可能继续加息 | 费城半导体指数 −3.4%，纳指 −1.25%。Arm −6.5%、Oracle −5.8%、英特尔 −5.3%、美光 −4.8%、Broadcom −4.4%。能源和必需消费上涨 |
| 10 月中 | 9 月 CPI 3.7%，是 5 月以来最高，汽油环比涨 9.1%；布伦特油价一度到约 106 美元 | 资金从科技股转向能源、公用事业、医疗和必需消费 |
| 10-28 | 美联储维持利率不变，但 12 人投票中有 2 人主张加息 | 市场开始押注 12 月加息 |
| 10-28~30 | 大厂财报：**Alphabet 自由现金流转负、停止回购，单日跌约 12%**；Amazon 过去 12 个月的自由现金流为 −424 亿美元；Meta 宣布大规模发股融资；**英特尔因四季度指引疲弱单日跌约 30%，是 1979 年以来最差的一天** | 10 月全月 Alphabet 约 −19%、Meta 约 −15%；VIX 升到 20 以上 |
| **10 月全月** | 纳指约 −5.2%，标普约 −1%，道指 +1.5%。**半导体 ETF（SOXX）约 −17%**，通信服务 −15%，科技 −8%。能源 +14%、必需消费 +11%、公用事业 +10% | 典型的"撤出 AI、躲进防御板块" |
| 11-03 | 中期选举民主党大胜，多个州选出了主张限制数据中心的州长（见第 7 节） | 选举夜 AI 数据中心股普遍下跌 |
| 11-08~12 | 黄仁勋承认婚外情。**另有报道称他曾被中国情报人员接近，这一点目前只是指控，董事会称没有理由认为国家安全受损。** FBI、国会和公司都在调查。11 月 12 日，NVIDIA 宣布他辞去 CEO | NVIDIA 盘中一度 −14%，市值跌破 4 万亿美元 |
| 11-10 | 10 月 CPI 环比 +0.4%，核心 CPI 环比 +0.3%，都高于预期 | 市场定价的 12 月加息概率升到约 89% |
| 11-17 | NVIDIA 财报很强（营收 1158 亿美元，下季度指引 1300 亿），但毛利率指引下降，约 1180 亿美元的对外担保也引发担忧。董事会主席在电话会上表示**不打算让黄仁勋回来** | 好财报没能推动股价上涨 |
| **11-16~20** | AI 信用恐慌：CoreWeave 的违约保险（CDS）价格飙升，Oracle 的 CDS 创纪录；Anthropic 股价跌破 IPO 价；散户和量化基金集中抛售 | **标普一周跌 8.6%，市值蒸发约 6 万亿美元，是 2025 年 4 月以来最差的一周。** 11 月 20 日的低点：标普 6910、纳指 22618、NVIDIA 125.5 美元，VIX 升到 35.9 |
| 11-23 | 在白宫施压下，NVIDIA 董事会恢复黄仁勋的 CEO 职位 | NVIDIA 单日 +31.5%，标普 +4.7% |
| 11-24~25 | CoreWeave 又跌约 12%；10 月 PCE 3.8%、核心 PCE 3.3%，都超预期；白宫提出对 14 个贸易伙伴加征关税（对中国最高 20%，1 月 25 日听证前不生效） | 纳指 100 盘中一度接近比高点低 20%，收盘时跌幅收窄 |
| 11-27 | 半天交易，芯片股领涨（美光 +7.6%、Marvell +7.3%） | 标普当周 +5.6%，收在 7297 |

### 8.3 哪些跌得最多，哪些已经修复
| 类别 | 从高点的跌幅 | 修复情况 |
|---|---|---|
| 标普 500 | 最深约 −11.6%（11 月 20 日），现在约 −6.7% | 已收回约四成跌幅 |
| 纳斯达克 | 最深约 −18%，现在约 −12.6% | 部分修复 |
| NVIDIA | 最深约 −48%（125.5 美元），现在约 −37% | 黄仁勋复职后反弹，但治理问题和国会作证的风险还没解决 |
| 美光 / Marvell / 半导体 | 美光约 −38%；Marvell 一个月内约 −39% | 最近一周反弹最猛，但离高点还远 |
| Alphabet / Meta / 英特尔 | 财报后大跌 | 修复有限，现金流问题还在 |
| CoreWeave 等 neocloud | 一个月 −36% 以上 | **没有修复**，信用状况还在恶化 |
| 能源、公用事业、必需消费、医疗 | 10 月大涨（能源 +14%） | 是这次下跌中的赢家 |

### 8.4 对本系统的启示
- 这次下跌几乎都是**外部事件**推动的：媒体爆料、宏观数据、治理丑闻、信用市场价格，而不是公司订单变了。所以系统的事件解释模块必须覆盖这几类：媒体报道、利率和通胀数据发布日、信用市场（CDS 和债券收益率）、管理层变动。
- 10 月 9 日这种"一条报道带崩一个板块"的情况，很适合用来回测第一步（信息收集）和第二步（推理）的视图，看系统能不能及时抓到消息并给出解释。

**本节来源**：[HDFC Sky 10-09 美股收盘](https://hdfcsky.com/news/nasdaq-tumbles-345-points-as-oil-surge-and-chip-selloff-drive-us-markets-lower-october-9-2026)（2026-10-09，券商资讯页，部分截断）；[Halo Investing 10 月回顾](https://haloinvesting.com/journal/october-2026-market-recap-ai-stocks-defensive-rally/)（2026-11-12）；[Defiant Capital 10 月市场更新](https://www.defiantcap.com/october-2026-market-update-tech-selloff-sector-rotation/)（2026-11-01）；[Alain Guillot 10 月回顾](https://www.alainguillot.com/stock-market-recap-october-2026-the-ai-trade-crashes-while-the-dow-holds-strong/)（2026-11-01，个人博客）；[Al Jazeera：黄仁勋为何辞职](https://www.aljazeera.com/news/2026/11/12/why-did-nvidia-ceo-jensen-huang-resign-and-who-is-colette-kress)（2026-11-12）；[Al Jazeera：黄仁勋卸任](https://www.aljazeera.com/news/2026/11/12/ai-titan-jensen-huang-out-as-nvidia-ceo)（2026-11-12）。11 月的市场数据见第 10 节"市场与宏观"的来源。部分数字在不同来源间有小差异，这里取多数来源一致的数值；10 月以后的数据多来自二手整理，CNBC 11 月 20 日的"五大因素"一文没能读取。

---

## 9. 现在是买入时机，还是再等等？（2026-11-28 补充）

> **不构成投资建议。** 下面是框架和事实，不是择时预测。没有人能稳定地猜中底部。

### 9.1 先校准一下："市场很低"其实分两层
| 指标（2026-11-27 收盘） | 数值 | 离高点 |
|---|---|---|
| 标普 500 | 7297 | 较 10-06 纪录 7819 低约 **6.7%**；11 月 −3.7% |
| 纳斯达克综合 | 24130 | 较纪录低约 **12.6%**；11 月 −5.1% |
| NVIDIA | 150.5 美元 | 较 10-06 纪录 239 低约 **37%** |
| 美光 | — | 较高点低约 38%（11 月中） |
| VIX | 23.8 | 11-20 峰值 35.9，10 月底 19.4 |
| 10 年期美债 | 约 4.93% | — |
| 高收益债利差（FRED） | 3.77% | 基本没扩大 |

**大盘只是正常回调，并不便宜；真正跌得深的是 AI 芯片和 AI 基建股（30–40%）。** 11-16 到 11-20 那一周标普跌约 8.6%，市值蒸发约 6 万亿美元，是 2025 年 4 月以来最差的一周；随后一周反弹 5.6%，已经收复约六成跌幅。

### 9.2 支持现在（分批）买入的理由
1. **AI 龙头的基本面没有坏**：NVIDIA Q4 指引 1300 亿，美光 2027 年产出 75% 已锁定，台积电全年增长约 44%。股价跌主要是因为治理风波和融资担忧，不是因为订单消失。
2. **恐慌已经释放过一轮**：VIX 从 35.9 回落；散户 11-23 创下 2020 年 3 月以来最大的单日净卖出（Vanda），这类极端情绪常出现在阶段性低点附近（是规律，不是保证）。
3. **经济本身不弱**：三季度 GDP 修正为年化 4.3%，失业率 4.1%，纽约联储模型显示一年内衰退概率只有约 12–17%。
4. **季节性**：历史上 12 月和"圣诞行情"整体偏正面（统计规律，样本外不一定成立）。
5. **大盘信用市场仍平稳**：压力集中在 CoreWeave、Oracle 这类个体，高收益债整体利差没有失控。

### 9.3 支持再等等的理由
1. **美联储在加息，不是降息**：现在利率是 3.75–4.00%，市场对 12 月 9 日加息 25bp 的定价约 97%，1 月再加的概率约 66%，Waller 甚至主张 12 月加 50bp。10 月 PCE 3.8%、核心 PCE 3.3%，通胀在升温。**加息周期里高估值科技股通常承压。**
2. **大盘估值仍高**：标普只比纪录低 6.7%，10 年期美债接近 5%，股票相对债券的吸引力不高。
3. **AI 信用风险还没结束**：CoreWeave 债券收益率约 18%，12 月初有 45 亿美元贷款出售作为压力测试；NVIDIA 评级有被下调一档的可能。
4. **政策事件很密集**：新关税方案（中国最高 20%、欧盟 15%）在 1 月 25 日听证后才可能生效；NVIDIA 12 月 1 日、3 日国会作证；得州、俄亥俄、佐治亚新州长 1 月上任（第 7 节）；特朗普质疑 GDP 数据。
5. **反弹可能只是空头回补**：高盛提示过还有约 1000 亿美元的系统性卖盘；11 月仍可能是 2008 年以来最差的 11 月。

### 9.4 可执行的做法：按日程分批，而不是一次性押注
**思路：把打算投入的资金分成 4–6 份，在未来 3–4 个月里按关键事件逐步投入。** 每过一个事件，不管涨跌都按计划执行，避免被情绪带着走。

| 时间 | 事件 | 分批建议（举例） |
|---|---|---|
| 现在 | 已经从低点反弹一部分 | 投入第 1 份（例如 15–20%） |
| 12-01 | Marvell 财报、NVIDIA 国会闭门问询、ISM | 观察 |
| 12-04 | 11 月非农（共识约 9 万，失业率 4.1%） | — |
| 12-09 / 12-10 | **FOMC 决议 + 点阵图**；11 月 CPI | 事件落地后投入第 2 份 |
| 12-16 左右 | 美光财报（预计） | — |
| 2027-01 上旬 | CoreWeave 融资结果、新州长就职 | 投入第 3 份 |
| 01-25 / 01-26–27 | 关税听证；1 月 FOMC | — |
| 1 月底–2 月初 | **大厂 Q4 财报，给出 2027 资本开支数字**（全链条总开关） | 投入第 4 份，并根据资本开支数字决定剩余部分 |
| 2–3 月 | 视情况投入剩余部分 | — |

**配合原则：**
- **先选"现金流硬"的**：台积电、Broadcom、微软这类，再考虑弹性大的（Marvell、美光），高负债的 neocloud 先不碰或只放很小仓位。
- **提前写好退出/加仓规则**：比如标普跌破 11-20 低点 6910，或者高收益债利差明显扩大（例如超过 4.5%），就暂停后续批次。这个阈值只是示例，需要自己定。
- **留现金**：加息周期里短期国债和货币基金本身就有约 4% 收益，等待的机会成本不高。
- **和本项目的结合**：按 roadmap-0.2，2027 年 1–3 月是模拟交易期，第 5 个月才开始小额真钱。可以把上面这个分批计划也放进系统里做"影子跟踪"，用系统的信号来检验每一批的时机，而不是凭感觉。

### 9.5 一句话
**大盘不算便宜、利率在上行，所以不适合一次性重仓；但 AI 龙头已经回调 30–40%、基本面仍强，适合用 3–4 个月、按事件分批建仓，并且优先选现金流强的公司。** 最关键的两个时间点是 **12 月 9 日 FOMC** 和 **1 月底大厂公布 2027 资本开支**。

### 9.6 示例：10 万美元怎么分（核心 / 卫星 / 1–5 天自动交易）
> 示例框架，不构成投资建议；比例应按自己的风险承受能力、收入稳定性和税务情况调整。

**稳健版（默认）**
| 部分 | 金额 | 放什么 | 规则 |
|---|---|---|---|
| 核心 | 6.5 万（65%） | 标普 500 指数基金，长期持有 | 按 9.4 节的日程分批买入，买完后基本不动 |
| 卫星 | 2 万（20%） | 4–5 只个股，**单只最多 5000 美元**；例如 TSM、AVGO、NVDA、MSFT，再加一只电力股（GEV 或 CEG） | 同样分批；单只亏损或仓位超限时按事先定好的规则处理 |
| 自动交易（1–5 天） | 1 万（10%） | 系统通过验收门槛前，先放货币基金（约 4%） | 先用 2000–3000 美元小额自动交易，稳定运行 1 个月以上再逐步加到 1 万 |
| 备用现金 | 5000（5%） | 货币基金 | 应急或极端下跌时补核心仓 |

**进取版**：核心 50%、卫星 30%（单只上限仍为 5000 美元）、自动交易 10%、现金 10%。

### 9.7 什么时候开始
| 部分 | 时间表 |
|---|---|
| 核心 + 卫星 | **现在就可以开始分批**：现在约 15–20%，12-09/10 FOMC 和 CPI 之后第 2 份，2027 年 1 月上旬第 3 份，1 月底大厂公布 2027 资本开支后投入剩余部分；预计 2027 年 2–3 月建仓完成 |
| 自动交易 | **不早于 2027 年 4 月**，按 roadmap-0.2 的 6 个月快速通道：2027 年 1–3 月模拟交易 → 4 月人工确认的小额真钱（7b）→ 5 月小额自动（7c）。**只有通过验收门槛才启动**；不通过的话，这 1 万继续放货币基金，或转入核心仓 |

### 9.8 1 万美元自动交易：一个月大概能赚多少？
- **现实区间（系统训练得好的情况下）：每月约 0.5%–2%，也就是 50–200 美元。** 年化大约 6%–25%，上限已经是很优秀的水平。
- **亏损月份会很常见。** 即使是好系统，一年里有 3–5 个月亏钱也很正常，要看的是 6–12 个月的累计结果和最大回撤。
- **持续每月 5% 以上不现实。** 回测里出现这种数字，通常意味着过拟合、未计交易成本，或者承担了没被发现的尾部风险。
- **要扣掉的成本**：买卖价差和滑点（1–5 天持有、交易频繁时影响很大）；短期资本利得按普通收入税率纳税；还有数据和 LLM 等运行成本。按 1 万美元本金算，每月 50–200 美元的毛收益很可能被数据、API 费用吃掉一大块。
- **对照基准**：同样 1 万放货币基金每月约 33 美元（约 4% 年化），放标普指数长期平均每月约 60–80 美元（历史均值，波动很大）。**自动交易必须稳定跑赢这两个基准，才值得放大。**
- **小资金阶段的真正价值**是验证系统（信号是否有效、执行是否可靠、风控和熔断开关是否起作用），而不是赚钱。等验证充分后，收益才和本金规模成正比。

---

## 10. 来源（按主题，括号内为发布日期）

**芯片与财报**
- [NVIDIA Q3 FY27 新闻稿](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2027)（2026-11-17）
- [CrowdfundedWealth：NVIDIA Q3 8-K 解读（5180 亿承诺、担保）](https://www.crowdfundedwealth.com/articles/nvidia-q3-fiscal-2027-results-8-k-what-the-filing-says)（2026-11-17，二手）
- [AMD Q3 2026 财报新闻稿](https://newsroom.amd.com/news/amd-reports-third-quarter-2026-earnings/)（2026-11-03）
- [ainvesting：TSMC 2026 展望（引 Q3 财报）](https://ainvesting.org/research-lab/research-lab-2026-11-02/)（2026-11-02）
- [BigGo：Nomura 上调 AI 服务器预期，CoWoS 2027 +80%](https://finance.biggo.com/news/391f8bdd-7513-473c-97e2-2f0a76ce8bad)（2026-11-27）
- [Yahoo/24/7 Wall St：美光超预期](https://finance.yahoo.com/markets/stocks/articles/micron-blew-past-estimates-says-112008821.html)（2026-10-01）
- [The Inference：美光 2027 HBM 售罄与价格上限](https://theinference.org/article/micron-sold-most-of-its-2027-hbm-at-higher-prices-and-32-billion-of-contracts-carry-price-ceilings)（2026-11-14）
- [Gokhshtein：美光回撤 34%](https://gokhshtein.com/news/2026-11-08-microns-hbm-sold-out-through-2027-34-pullback-creates-entry)（2026-11-08）
- [24/7 Wall St：Broadcom vs Marvell](https://247wallst.com/investing/2026/11/19/broadcoms-13-67b-quarterly-fcf-beats-marvells-scaling-story-plain-and-simple/)（2026-11-19）
- [BigGo：Marvell 投资者日目标](https://finance.biggo.com/news/ce7a54e6-9865-48c6-a196-613ea76d6425)（2026-10-06）
- [Finviz：Palantir Q3 2026 新闻稿标题](https://finviz.com/news/413533/palantir-reports-q3-2026-us-comm-revenue-growth-of-148-yy-and-revenue-growth-of-96-yy-raises-fy-2026-revenue-guidance-to-91-yy-growth-and-us-comm-revenue-guidance-to-143-yy-crushing-consensus-expectations)（2026-11）

**资本开支与融资**
- [Yield Theory：2027 大厂资本开支预测](https://www.yieldtheory.app/research/hyperscaler-capex-2027-forecast)（2026-10-04，更新 11-25）
- [Luminix：Q3 2026 大厂资本开支](https://www.useluminix.com/reports/industry-analysis/hyperscaler-capex-q3-2026)（2026-10-30）
- [Alcapital：2027 AI 资本开支周期与信用风险](https://alcapitaladvisory.com/research/intelligence/ai-infrastructure.html)（2026-11-02，单一作者研究）
- [ROIC：AI 债务担忧盖过 NVIDIA 管理层反转](https://www.roic.ai/news/ai-debt-worries-overtake-nvidias-leadership-reversal-as-credit-costs-surge-11-25-2026)（2026-11-25）
- [ROIC：CoreWeave 债务担忧加剧](https://www.roic.ai/news/coreweave-shares-extend-slide-as-debt-concerns-mount-11-27-2026)（2026-11-27）
- [Yahoo/GuruFocus：Oracle、CoreWeave 信用市场警告](https://finance.yahoo.com/markets/stocks/articles/oracle-coreweave-face-stark-warning-162922864.html)（2026-11-25）

**电力与数据中心**
- [StockTitan：数据中心电力供应商积压与指引](https://www.stocktitan.net/news/BE/data-center-power-suppliers-post-backlog-and-guidance-updates-31yl9gqc9n4d.html)（2026-11-12）
- [24/7 Wall St：燃机短缺](https://247wallst.com/investing/2026/11/09/shortage-of-turbines-drives-market-for-second-hand-market-for-ai-data-centers/)（2026-11-09）
- [Yahoo：GE Vernova 积压](https://finance.yahoo.com/technology/ai/articles/ge-vernova-gev-176-billion-065504214.html)（2026-07）

**软件冲击与终端**
- [Business Insider/Yahoo：AI 代理经济的赢家与输家](https://finance.yahoo.com/markets/stocks/articles/stock-markets-winners-losers-ai-175001731.html)（2026-09-22）
- [24/7 Wall St/Yahoo：Adobe、Salesforce、ServiceNow 2026 表现](https://finance.yahoo.com/markets/stocks/articles/software-stock-worst-performer-2026-174209348.html)（2026-04-27）
- [Tech Insider：AI 代理抹去 2 万亿 SaaS 市值](https://tech-insider.org/saas-stock-crash-ai-agents-2-trillion-2026/)（2026-04-12，更新 11-16）
- [Stocktwits/Yahoo：Dan Ives 称 2027 是拐点年](https://finance.yahoo.com/technology/ai/articles/dan-ives-says-ai-disruption-140757006.html)（2026-10-30）
- [24/7 Wall St：AI 新赢家（Dell、Credo、Broadcom、Intel）](https://247wallst.com/investing/2026/11/06/the-ai-boom-is-creating-a-new-set-of-winners-these-stocks-stand-out/)（2026-11-06）
- [Investing.com：内存涨价的赢家与输家](https://www.investing.com/news/stock-market-news/memory-chip-price-surge-winners-and-losers-across-the-tech-supply-chain-93CH-4864290)（2026-08-18）
- [VLSI Korea：内存挤压 PC 与手机价格](https://www.vlsi.kr/en/memory-squeeze-pc-smartphone-prices-en/)（2026-11-28，AI 辅助整理）

**政治与监管（第 7 节）**
- [Scripps：选民选出要限制数据中心的州长](https://www.scrippsnews.com/politics/america-votes/voters-elected-governors-to-curb-data-centers-lowering-bills-for-gas-and-groceries-is-harder)（2026-11-04，非官方计票）
- [The Conversation/The News Minute：反数据中心情绪帮助民主党赢得中期选举](https://thenewsminute.com/news/backlash-against-data-centers-helped-democrats-win-the-midterms)（2026-11-25）
- [Fox Business：选民在投票中否决数据中心扩张](https://www.foxbusiness.com/politics/data-centers-ballot-voters-sent-unmistakable-message)（2026-11-05）
- [Daily Caller：BAAJA 参院通过，数据中心或付 550 亿输电费](https://dailycaller.com/2026/11/25/data-centers-transmission-costs-baaja-grid-strategies-sheldon-whitehouse-shelley-moore-capito)（2026-11-25）
- [Forbes：数据中心成为中期选举摇摆州议题](https://www.forbes.com/sites/maryroeloffs/2026/11/02/data-centers-are-key-issue-in-midterm-battleground-states-as-household-electric-rates-soar/)（2026-11-02）
- [NatLawReview：FERC 为 PJM 同址负载开新路径](https://natlawreview.com/article/ferc-opens-new-paths-co-located-loads-pjm-what-data-center-and-power-generation)（2025-12-23）
- [Stateline：更多城市暂停数据中心](https://stateline.org/2026/05/28/more-cities-are-pressing-pause-on-data-centers-as-local-backlash-grows/)（2026-05-28）
- [Capacity：至少 14 个州考虑暂停令](https://capacityglobal.com/news/at-least-14-us-states-weighing-data-centre-moratoriums/)（2026-09）
- [Resilience：团结全美的数据中心反对潮](https://www.resilience.org/stories/2026-07-23/the-data-center-backlash-thats-uniting-america/)（2026-07-23）
- [Rockefeller Institute：更多数据中心暂停令](https://www.rockinst.org/blog/updates-on-the-cloud-more-moratoriums-on-data-centers/)（2026-06）
- [Introl：数据中心社区反对的 640 亿美元风险](https://introl.com/blog/data-center-community-opposition-64-billion-backlash)（2026-02）

**市场与宏观（第 9 节）**
- [The Company Chronicle：11-27 收盘](https://thecompanychronicle.com/story/stocks-close-sp500-up-1-6-percent-nasdaq-up-2-3-percent-vix-24-half-day-november-27-2026)（2026-11-27）
- [The Glass Desk：周度市场回顾](https://theglassdesk.substack.com/p/weekly-market-review-nov-27-2026)（2026-11-27）
- [Yahoo Finance：6 万亿蒸发到 3.5 万亿反弹](https://finance.yahoo.com/markets/article/stocks-snap-from-a-6-trillion-washout-to-a-3-trillion-surge-as-nvidia-micron-and-spacex-bounce-back-151218930.html)（2026-11）
- [Vista Partners：感恩节周市场总结](https://vistapglobal.com/weekly-market-summary-stocks-stage-a-sharp-rebound-in-a-thanksgiving-holiday-shortened-week-ending-november-27-2026-ant-bby-eprx-gap-googl-ko-modd-mo-nvda-ser-sndk-skhy-spcx-wmt/)（2026-11-27）
- [Investrade：11-27 市场回顾](https://investrade.com/market-review-november-27-2026/)（2026-11-27）
- [Bitrue：12 月加息概率（引 CME FedWatch）](https://www.bitrue.com/blog/fed-rate-hike-december-2026)（2026-11-26，二手）
- [WEEX：12 月 FOMC 前瞻](https://www.weex.com/learn/articles/december-fomc-meeting-2026-dec-8-9-rate-hike-25-or-50-bps-i6ixftznd22gq8cq0uymsaf2)（2026-11 中，二手）
- [gov.house：利率、CPI、失业率与衰退概率预测](https://gov.house/forecast/expectations/)（2026-11-26，含自有模型）

**数据说明**：软件股的年内跌幅是 2026 年 4 月底的数据，之后有反弹/再跌，需更新；Google Cloud 增速、Amazon 积压、Meta 融资额来自摘要，未与原始财报核对。
