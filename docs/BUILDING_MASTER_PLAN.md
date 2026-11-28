# BUILDING MASTER PLAN · 美股短期研究与预测系统

**文档版本** `plan-0.7` · 2026-11-26（0.7：用户补充信息（添加、分类、核验）与"继续分析"增量补充运行（D-47、D-48、§7.2）；0.6：股票详情按 ① 信息采集 → ② 分析与推理 → ③ 预测 三步展示，采集条目全量可查、推理每步带引用（D-45、D-46）；0.5：每日固定预测时刻表 08:30/10:00/11:30/13:00/14:30/16:30 ET 作为主评分点（D-43）；预测与实际对照（两条曲线 + 滚动准确率）及其进入模型改进的受控闭环（D-44、§7.1）；0.4：补齐 PPT 蓝图审查的 15 项部分覆盖与 4 项缺失——来源扩展（法院案卷、宏观首发值、Form 4、期权占位）、公司行为、行业模板、历史类比、事件结果结算、条件预测、有效期与运行状态、估值背景；决策 D-38～D-42；追溯表加"状态/优先级"列；0.3：补充运营流程——新公司接入、一键端到端运行、数据源与任务监控；0.2：并入 `MODEL_IMPROVEMENT_MEMO.md` §5） · 作者：架构/原型设计（Claude）
**依据**：项目交接说明（Brief）+ 三份规格（见 §0）。配套文件：`DATA_CONTRACT.md`（契约 `contract-0.7`）、`DEVELOPMENT_PHASES.md`、`prototype/`。

> 本系统面向研究与验证，不接入交易执行，不构成投资建议。所有示例数值、模型成绩均为虚构。
> **路线图扩展**：Phase 5（中长期预测）、Phase 6（买卖信号）、Phase 7（自有资金系统执行交易）见独立文档 `roadmap/ROADMAP_EXTENSIONS_CN.md`（roadmap-0.3，含"6 个月快速路线"；不改变本文件与 `DATA_CONTRACT.md` 当前范围）。下行风险预警与下跌监测（市场与个股下跌概率、下跌类型、熔断 / LULD 暂停等监测与报告、减仓 / 卖出建议）见 `roadmap/DOWNSIDE_RISK_WARNING_CN.md`（risk-0.2）。

---

## 0. 附件读取结果与版本核对

| 文件 | Brief 要求版本 | 文件内标注 | 日期 | 交叉引用 | 结论 |
|---|---|---|---|---|---|
| `Stock_Drivers_and_Pending_Events_CN.docx`（研究框架，下称 **S1**） | V1.1 | V1.1（版本记录含 V1.0、V1.1） | 2026-11-25 | — | ✅ 吻合 |
| `Stock_Event_Analysis_Engineering_Spec_CN.md`（第二步，**S2**） | V1.2 | V1.2，「对应主文件 V1.1」 | 2026-11-25 | 指向 S1 V1.1 ✅ | ✅ 吻合 |
| `Stock_Forecast_and_Settlement_Engineering_Spec_CN.md`（第三步，**S3**） | V1.3 | V1.3，「对应第二步事件分析规格 V1.2」 | 2026-11-26 | 指向 S2 V1.2 ✅ | ✅ 吻合 |

三份文件均完整读取（S1 共 11 类驱动因素 + 待决事件 + 合规章节 + 12 组来源；S2 共 7 章；S3 共 10 章）。**冲突裁决顺序**按 Brief：预测窗口、结算、研发后台、试点名单 → **S3**；证券快照、事件分析、上下游交接 → **S2**；其余 → **S1**。

本文档引用格式：`S3§3.1` 表示 S3 第 3.1 节。外部链接（IR、SEC、BIS 等）仅作为来源指引，本轮未逐一联网核验，相关事实（如 S1 中 2026-11-12/11-23 的 CEO 变动示例）按"附件提供的材料"处理。

### 0.1 影响实施的冲突与缺项（摘要，详见 §9 决策表）

| # | 条款 | 问题 | 影响 | 推荐默认（本次提出，可调整） |
|---|---|---|---|---|
| C1 | S1「预测结算」"股价预测覆盖 1–5 个交易日窗口"、"第一版可固定在…下一正常交易时段…起算，到该交易日收盘" vs S3§3.1 盘中 60 分钟 / 至收盘 / 下一时段 | 窗口定义冲突 | 目标表、标签、结算任务 | **以 S3 为准**；1–5 日窗口列为后续阶段候选目标（D-02） |
| C2 | S2§1「起步公司：半导体、银行、生物科技各至少一家」 vs S3§1.1 / Brief 首批 NVDA/AMD/AVGO/MU | 试点名单冲突 | 公司档案、种子数据 | **以 S3 为准**；银行/生技仅保留配置样例，不进首版验收（D-03） |
| G1 | S3§3.1 "首组同步合格报价"、"同步容差"未给数值 | 缺阈值 | 起算/结算无法实现 | NBBO 中间价；个股与篮子所有成分的报价时差 ≤ 2s；结算容差 30s（D-06、D-07） |
| G2 | S3§1.2 同行篮子"预先定义且排除被预测公司"未给成分与权重 | 缺定义 | 相对收益、标签 | `semis_peer_v1` 等权 12 只、剔除目标后 11 只，季度生效（D-08） |
| G3 | S3§3.1(3) 三分类阈值未给数值 | 缺阈值 | 标签、Brier | **按波动缩放**：`±k × σ̂`（σ̂ 为发布时预测的同窗口相对收益波动），初始 k = 0.25，随 `target_definition_version` 冻结（D-09） |
| G4 | S3§3.1 "下一正常交易时段开盘后参考价"未定义开盘后何时 | 缺定义 | next_regular_session 标签 | 不早于 09:31:00 ET 的首组同步合格报价；10 分钟内无则 `unsettleable`（D-10） |
| G5 | 收盘价"预先约定的同场收盘价格"未定 | 缺定义 | to_close 结算 | 上市交易所官方收盘价（Nasdaq Official Closing Price / NYSE 收盘拍卖价）（D-11） |
| G6 | 合格报价质量规则（价差、陈旧、停牌、LULD）未量化 | 缺阈值 | 弃预测、无法结算比例 | 价差 ≤ 20bp 且 ≤ 近 20 分钟中位价差 ×5，报价年龄 ≤ 5s，非停牌/非 LULD 暂停（D-12） |
| G7 | 数据供应商未定（S1 列 Massive、FactSet/LSEG 为示例） | 采购未定 | Phase 0 阻塞项 | 全部标"拟选/未验证"，Phase 0 以样本验证（D-13～D-16） |
| G8 | 训练切分隔离（embargo）时长未给 | 缺阈值 | 评估有效性 | 训练/校准/验证/留出之间留 ≥ 1 个完整交易日；同事件簇同组（D-19） |
| G9 | 上线门槛（样本量、改善幅度）S3§6 明确"暂不承诺" | 有意留空 | 审批无法自动判定 | 登记为版本化 `gate_config`，Phase 3 前锁定（D-21） |
| G10 | 60 分钟窗口发布截止时间 | 隐含 | 发布判定 | t0 + 60m + 结算容差 ≤ 当场收盘（正常日约 14:59:30 ET 后不发） |
| G11 | S2 版本记录无 V1.0 条目；S1 参考文献编号有重复（[2][3][6][7][8][9][10][11] 各对应多条） | 文档细节 | 引用追溯 | 引用时附链接标题，不只靠编号 |

---

## 1. 产品目标与首版范围

**一句话**：用户随时打开一只美股，看到 ①近期发生了什么（证据与版本）②已有信息能解释多少已发生的波动（相对行业、未解释部分）③从现在起在指定窗口内可能怎么走（事前锁定、事后自动结算的预测）。

### 1.1 首版（MVP = Phase 0–3）范围

| 维度 | 首版包含 | 首版不包含 |
|---|---|---|
| 证券 | NVDA、AMD、AVGO、MU（首批）；TSM、MRVL 作为第二批评估 | 其他行业上线（只保留档案样例） |
| 预测目标 | `regular_60m`（方向，首个里程碑）+ `regular_60m_move`（预期波动幅度，同期）→ `regular_to_close` → `next_regular_session` | `overnight_gap`、1–5 日窗口、多点曲线（后续阶段） |
| 预测轨道 | 股价反应（三分类：跑赢/接近平盘/跑输行业篮子，同时报告绝对收益）；待决事件结果以**情景+证据**为主 | 未验证子类的事件结果数值概率 |
| 触发 | 定时（盘中每 5 分钟评估）、事件、行情异动、用户按需 | 逐笔成交触发 |
| 模型 | 历史频率 / 恒判平盘 / 持续性三条基线、行情基线（正则化多项逻辑回归）、HAR 式波动模型、事件增强候选 | 深度模型、LLM 直接出概率 |
| 后台 | 训练任务、数据快照对比、参数对比、验证总览、逐条回放、影子测试、审批与回滚 | 自动无人审批上线 |
| 用户端 | 公司监控、股票详情、短期预测、待决事件、预测回放 | 交易下单、组合管理、推送到外部 |

### 1.2 用户端必须区分的四类信息（全局视觉规范）

| 类别 | 标签 | 来源 | 视觉 |
|---|---|---|---|
| 历史走势 | `历史行情` | `market_bars` / 参考报价 | 实线 |
| 当前解释 | `当前解释（截至 hh:mm ET）` | `event_analysis_versions.market_explanation` + 快照 | 卡片，带 `supported/partial/insufficient` 徽标 |
| 尚待验证的情景 | `情景 · 未验证` | 待决事件情景、条件情景 | 虚线框、灰底 |
| 事前预测 | `事前预测 · 已锁定` | `predictions`（已发布、不可覆盖） | 起算点标记 + 终点区间；未通过验证的模型显示"内部影子，不展示概率" |

---

## 2. 用户流程

### 2.1 研究用户（市场页面）

1. **公司监控**：首批四家卡片 → 每张显示 `market_state`、最新参考报价与报价时间、当日绝对/相对收益、解释状态、最新预测状态。
2. **股票详情**：顶部是本次运行的三步条——**① 信息采集**（本次检索了多少条、来自哪些渠道、保留/去重/排除/待核各多少）→ **② 分析与推理**（行情事实、时间对齐、证据、归因、反向证据、未解释部分，逐步列出并引用所用条目）→ **③ 预测**（本槽位发布的预测）。三步各有独立视图：
   - 概览：当前解释（已观察事实 / 可能驱动 / 反向证据 / 未解释部分，每条带引用）、行业表现（同行篮子 + SOXX 参考）、预测与实际、证据摘要。
   - ① 信息采集：按渠道（SEC 文件、Form 4、公司 IR、新闻快讯、政策、法院、宏观、预期、同行公司、行情）× 类别（财报指引、出口政策、客户需求、供应链、并购、诉讼、管理层、宏观等）的计数矩阵；可筛选、可搜索的完整条目长列表，每条显示处置状态、原因与四类时间；被排除的条目也保留，可以看到"为什么没用"。
   - ② 分析与推理：推理链逐步展示输入、规则与结论，点击引用跳到对应采集条目或报价。
   - **用户补充信息**（D-47）：在 ① 信息采集页点"＋ 添加信息"，提交链接、文本或文件，选择类别（可多选，也可交给系统分配；系统给出建议并可追加类别）。系统走与第 1 步相同的核验：打开链接、追溯原始来源、核对内容与时间、查重、筛查疑似未公开材料，给出状态（原始来源已核实 / 仅媒体来源 / 无法核实 / 重复 / 受限）。核验完成后出现"继续分析 →"按钮，按 §7.2 做增量补充运行。
3. **短期预测**：切换 `regular_60m` / `regular_to_close` / `next_regular_session`；查看预测状态（已结算、待结算、休市、数据不足/弃预测、无法结算）；图表区分历史行情、发布时间、起算报价、预测终点与区间。
4. **待决事件**：时间线显示节点、证据、事件结果预测（或情景）与对应股价预测——两者分栏、分别计分。
5. **预测回放**：选择一条已锁定预测，查看锁定输入、预测值、实际行情、结算报价和结算理由。
6. **每日时刻表**（D-43）：每个交易日固定 6 个槽位（美东时间）——08:30 盘前展望（当日时段）；10:00、11:30、13:00、14:30 发布 60 分钟预测（14:30 另加至收盘）；16:30 盘后展望（下一时段）。半日市与休市按日历自动展开。
7. **预测与实际对照**（D-44）：每次新槽位运行时，股票详情页先显示上一批预测的结算结果——两条曲线叠加（预测路径：中位数 + p10–p90 区间；实际路径：起算后相对篮子收益），以及当日、近 20 日、上线以来的命中率、Brier、区间覆盖率与样本数。

### 2.2 研发/审核人员（研发后台，桌面优先）

训练任务列表 → 任务详情（阶段、日志、指标）→ 数据快照对比（新增/删除/更正/过滤）→ 参数对比（线上 vs 候选，市场/行业/公司层）→ 验证总览（命中率、Brier、覆盖、有效独立样本、校准、混淆矩阵）→ 影子测试 → 审批（达标/未达标条件、审批人、生效范围）→ 部署与回滚。

---

### 2.3 运营人员（研究员 / 管理员）

**A. 新公司接入**（`onboarding_requests`，§9 D-35）

| 阶段 | 自动完成 | 需要人做 | 产物 |
|---|---|---|---|
| 1 `draft` 输入代码 | 解析 CIK、交易所、代码有效期、行业 | 确认是同一家公司 | `companies`、`securities` 草稿 |
| 2 `profile_review` 公司档案 | LLM 从 10-K/IR 起草关键指标、客户/供应商、监管机构、地理敞口（带原文定位） | 审核并修改；选择 `target_tier` | `company_profile_versions` v1 |
| 3 `sources_configured` 来源与基准 | 自动挂接 SEC、IR RSS、政策源；按行业生成剔除自身的同行篮子 | 补充公司专属来源；确认篮子 | `benchmark_versions`、来源配置 |
| 4 `backfilling` 历史回填 | 下载行情（秒级/分钟级）、历史证据与事件；生成回填报告 | — | `backfill_report` |
| 5 `data_validated` 数据校验 | 覆盖率、合格报价率、同步成功率、新闻时间精度、LLM 抽检 | 低于门槛时决定补数据或降级为 `peer_only` | checklist 打勾 |
| 6 `training` 训练 | 把新公司加入训练池；先只用**市场 + 行业参数**（S3§8.2），公司偏移只作候选 | — | `dataset_version`、`model_version` |
| 7 `shadow` 影子 | 实时影子预测 ≥ 20 个交易日，按公司出成绩 | — | 评估记录 |
| 8 `active` 上线 | — | `reviewer` 审批 | `model_deployments`（含 audience） |

**B. 一键运行"采集 → 分析 → 预测"**（`pipeline_runs`，D-34）

用户在股票详情或运营页点击 **运行**，选择证券与目标。系统依次执行：① 增量采集证据（从上次水位起）② 核验去重 ③ 事件分析（快报/完整版）④ 行情快照 ⑤ 预测交接检查 ⑥ 模型推断 ⑦ 原子发布 ⑧ 排程结算。每步写 `pipeline_run_steps`，页面实时显示进度、复用、跳过、重试和弃预测原因。

两条规则保证点击不会破坏评分：
- **默认复用**：输入水位无实质变化时直接返回当前有效快照与预测（S3§2"输入无实质变化时复用结果"）。
- **起算永远在发布之后**：新发布的预测从发布后的首组同步合格报价起算；按需运行的预测标 `sampling_rule=on_demand`，与定时主样本分开计分（S3§4(5)）。

另有 `replay` 模式（选任意历史时点，只用当时可得数据重跑全流程）和 `dry_run` 模式（不发布，只出报告），供研究和验收使用。

**C. 日常运维**：数据源健康（延迟、失败率、授权状态）、任务队列、告警（来源中断、报价陈旧、流水线失败、结算积压、漂移、门槛退化、接入受阻），见 `data_source_health`、`alerts`。

## 3. 系统拓扑

```
                       ┌────────────────────────── 外部数据（均为可替换适配器）─────────────────────────┐
                       │ 行情WS/REST  历史分钟/秒级  公司披露(SEC EDGAR/IR)  新闻/快讯  政策/监管  共识预期  │
                       └───────┬───────────┬──────────────┬──────────────┬──────────────┬─────────────┘
                               │           │              │              │              │
                  ┌────────────▼──┐  ┌─────▼──────┐  ┌────▼──────────────▼──────────────▼────┐
                  │ md-ingest     │  │ md-backfill│  │ evidence-ingest（拉取/订阅/去重/存原文）│
                  │ (Py, 常驻)    │  │ (Py, 批)   │  └────┬──────────────────────────────────┘
                  └──┬─────────┬──┘  └─────┬──────┘       │ source_document_versions（Storage 原文 + PG 元数据）
   1s 参考报价/1m bar│         │原始流      │Parquet       ▼
                     ▼         ▼            ▼        ┌──────────────────────────────┐
             ┌──────────────┐ ┌──────────────────┐   │ event-analysis worker (Py)   │◄── LLM Provider 接口
             │ Supabase PG  │ │ 对象存储 Parquet │   │ 提取→核验→归并→版本→影响      │   （提取事实/辅助解释）
             │ (应用数据)   │ │ (行情湖, DuckDB) │   └──────────┬───────────────────┘
             └──┬───────────┘ └────────┬─────────┘              │ events / event_analysis_versions
                │                      │                        ▼
                │          ┌───────────▼──────────┐   ┌──────────────────────────────┐
                │          │ replay / train / eval│   │ snapshot-builder (Py)        │ 定时/事件/异动/按需
                │          │ (Py 批, 离线)         │   │ security_state_snapshots     │
                │          └───────────┬──────────┘   └──────────┬───────────────────┘
                │      model_versions  │ 产物(Storage)            ▼
                │                      │              ┌──────────────────────────────┐
                │                      └─────────────►│ forecaster (Py)              │ 只读 线上已批准模型
                │                                     │ prediction_runs/predictions  │ 原子发布、不可覆盖
                │                                     └──────────┬───────────────────┘
                │                                                ▼
                │                                     ┌──────────────────────────────┐
                │                                     │ settler (Py, 定时, 幂等)      │ prediction_settlements
                │                                     └──────────────────────────────┘
                ▼
   ┌────────────────────────────────────┐
   │ Next.js（apps/web）                 │  市场页面（响应式） + 研发后台（/admin，RLS 角色）
   │ Route Handlers = 只读 API + 按需刷新│  Supabase Auth / RLS / Realtime 订阅状态变化
   └────────────────────────────────────┘
```

### 3.1 服务边界与职责

| 组件 | 技术 | 职责 | 不做什么 |
|---|---|---|---|
| `apps/web` | Next.js（App Router, TS） | 用户页与研发后台；读 API；"按需刷新"只**入队** `jobs`，不在请求内计算 | 不跑模型、不连行情 WS、不写预测 |
| Supabase Postgres | Supabase | 应用数据、契约表、任务队列（`jobs` 表 + `FOR UPDATE SKIP LOCKED`，或 pgmq）、RLS、审计 | 不存原始逐笔行情 |
| Supabase Storage（或 S3 兼容） | — | 来源原文（PDF/HTML/JSON）、行情 Parquet、模型产物、数据集快照清单 | — |
| `md-ingest` | Python asyncio 常驻 | 订阅实时行情；生成 1 秒参考报价（NBBO mid/bid/ask/last/质量标记）与 1 分钟 bar；异动阈值检测→入队 | 不做分析 |
| `md-backfill` | Python 批 | 历史分钟/秒级/报价下载→Parquet；可得性审计 | — |
| `evidence-ingest` | Python | 来源适配器；内容哈希去重；保存原文与版本；记录四类时间 | 不判断重大性 |
| `event-analysis` | Python + LLM 接口 | S2 全流程：提取、核验、去重归并、节点、预期对比、影响、优先级、市场反应、解释、交接 | 不生成数值概率 |
| `snapshot-builder` | Python | 按触发生成 `security_state_snapshots`，合并同水位请求 | — |
| `forecaster` | Python | 读快照 + 线上模型 → `prediction_runs` / `predictions`，原子发布；弃预测记录原因 | 不训练 |
| `settler` | Python 定时 | 到期取结算报价、计算收益与类别、写结算版本；更正时追加版本 | 不改原预测 |
| `replay/train/eval` | Python 批 | 历史时点重放、数据快照、训练、校准、评估、影子对照；写 `training_*`、`model_*` | 不影响线上（只通过 `model_deployments` 切换） |
| `scheduler` | Python APScheduler（或 pg_cron 入队） | 盘中每 5 分钟、开盘后/收盘前检查、结算扫描、每周训练检查 | — |

**职责要点**：网页服务只读+入队；异步任务（Python worker）承担所有计算；行情处理是独立常驻进程，与分析解耦；历史数据走对象存储 + DuckDB 列式查询，PG 只存"被预测/结算引用的报价"和分钟级聚合。

### 3.2 可替换接口（Provider / Adapter）

```python
class MarketDataProvider(Protocol):   # 实时 + 历史
    def stream_quotes(self, symbols: list[str]) -> AsyncIterator[QuoteTick]: ...
    def get_bars(self, symbol, start_utc, end_utc, interval: Literal["1s","1m"]) -> pa.Table: ...
    def get_official_close(self, symbol, session_date) -> OfficialClose | None: ...
class EvidenceSource(Protocol):       # SEC / IR / 新闻 / 政策 各一实现
    def poll(self, since_utc) -> list[RawDocument]: ...
class ExpectationProvider(Protocol):  # 共识快照（point-in-time）
    def get_snapshots(self, company_id, metric, as_of_utc) -> list[ExpectationSnapshot]: ...
class MacroProvider(Protocol):       # FRED/ALFRED：按 vintage 取首发值（D-15）
    def get_vintages(self, series_id, start, end) -> list[MacroRelease]: ...
class DocketSource(Protocol):        # CourtListener/RECAP（免费）或 PACER（按页计费）
    def poll_cases(self, case_refs: list[str], since_utc) -> list[DocketEntry]: ...
class InsiderFilingSource(Protocol): # EDGAR Form 4 XML
    def poll(self, ciks: list[str], since_utc) -> list[InsiderTransaction]: ...
class CorporateActionSource(Protocol):  # 行情商公司行为接口 + 8-K/IR 交叉核对
    def get_actions(self, security_id, start, end) -> list[CorporateAction]: ...
class OptionsProvider(Protocol):     # Phase 4 占位，来源未核实
    def get_snapshot(self, symbol, at_utc) -> OptionsSnapshot | None: ...
class LLMProvider(Protocol):          # 只做提取与辅助解释，输出必须带原文定位
    def extract_facts(self, doc: SourceDocumentVersion, schema: dict) -> ExtractionResult: ...
    def draft_explanation(self, inputs: ExplanationInputs) -> ExplanationDraft: ...
class TradingCalendar(Protocol):
    def session(self, exchange, date) -> Session | None: ...  # open/close/early_close
```

每个实现登记在 `data_sources`（含 `license_scope`、`verification_status = proposed|sample_verified|contracted`）。LLM 提供商与模型 ID 作为配置（`LLM_PROVIDER`、`LLM_MODEL`），每次调用记录 `provider/model/prompt_version/hash`，回放时禁止联网搜索、禁止用模型记忆补结果（S3§6）。

---

## 4. 数据流（一次盘中定时预测）

1. `md-ingest` 持续写 1 秒参考报价到内存环形缓冲 + 每分钟刷写 Parquet；被引用的报价落 PG `reference_quotes`。
2. `scheduler` 10:20:00 ET 为每只证券入队 `build_snapshot(trigger=scheduled)`。
3. `snapshot-builder` 取证据水位、行情水位、已发布事件版本 → 写 `security_state_snapshots`（`event_id` 可空，`new_catalyst_found=false`）。
4. `forecaster` 检查 `prediction_readiness` 与窗口可用性（交易日历、剩余时间）→ 读线上 `model_deployments` → 生成 `prediction_runs` + `predictions`，**同一事务**写 `status=published` 并锁定 `target_definition_version`、`benchmark_version_id`、`quote_rule_version`。
5. `published_at` 之后，`settler` 取首组同步合格报价写 `t0_quote_id`（→ `awaiting_settlement`），到 t0+60m 后取结算报价 → `prediction_settlements` → `settled` 或 `unsettleable`。
6. 前端通过 Realtime 订阅 `predictions` 状态变化刷新。

事件路径：`evidence-ingest` 收到出口政策文件 → `event-analysis` 快报（`flash`）→ 对受影响证券入队 `build_snapshot(trigger=event)` → 同上 4–5。

---

## 5. 行情原始数据：容量与存储选型

**覆盖**：4 只目标 + 同行篮子 12 只（含目标）+ SOXX + 第二批 2 只 + 特征用参考品种 QQQ、SPY、SMH、^VIX（D-31）≈ **22 个代码**（下表按 18 估算，增量约 +20%）。

| 数据层 | 粒度 | 估算量 | 存储 | 理由 |
|---|---|---|---|---|
| 原始报价/成交（若采购 TAQ 级） | 逐笔 | NVDA 等大盘股单日报价可达数百万～千万条；18 代码 × 5 年 ≈ 数 TB | 只在对象存储保留供应商原始文件（Parquet/zstd），按 `symbol/date` 分区 | 主要用于审计与重建 1 秒层；不进 PG |
| 1 秒参考报价层 | 每秒 1 行（bid/ask/mid/last/size/flags） | 23,400 行/日/代码 × 18 × 252 ≈ **1.06 亿行/年**；Parquet 约 3–6 GB/年 | 对象存储 Parquet + DuckDB 查询 | 起算/结算/同步容差都基于秒级；列式压缩查询快、成本低 |
| 1 分钟 bar | 每分钟 1 行 | 390 × 18 × 252 ≈ 177 万行/年 | PG `market_bars_1m`（近 2 年）+ Parquet 全量 | 页面图表、特征计算 |
| 被引用报价 | 每条预测 2–3 行 | 每日 < 2 万行 | PG `reference_quotes` | 预测与结算必须可在 PG 内外键追溯 |

**选型结论**：PG（Supabase）不承担行情湖；Parquet + DuckDB 本地/worker 查询，后期量增可换 ClickHouse/TimescaleDB 而不改契约（契约以 `reference_quotes` 和 `MarketDataProvider` 为界）。实时性：盘中参考报价从交易所时间到入缓冲 p95 目标 < 1s（需供应商验证，D-14）。

---

## 6. 目录结构（monorepo）

```
stock-research/
├─ apps/web/                      # Next.js：市场页面 + /admin
│  ├─ app/(market)/monitor/ …     # 公司监控、股票详情、预测、事件、回放
│  ├─ app/admin/ …                # 训练与验证后台
│  └─ lib/contracts.ts            # 由 packages/contracts 生成
├─ packages/contracts/            # 单一事实来源：JSON Schema（schema_version=contract-0.7）
│  ├─ schemas/*.schema.json
│  ├─ examples/*.json             # DATA_CONTRACT §8 三个连贯示例
│  └─ scripts/gen-ts.mjs, gen-py.sh
├─ services/py/                   # Python 包 sr（uv 管理）
│  ├─ sr/calendar/                # 交易日历、窗口可用性
│  ├─ sr/marketdata/              # provider 接口、参考报价、合格报价规则、同步
│  ├─ sr/benchmark/               # 同行篮子版本与收益
│  ├─ sr/evidence/  sr/events/    # 第二步
│  ├─ sr/snapshot/  sr/forecast/  sr/settle/
│  ├─ sr/replay/    sr/train/     sr/eval/
│  ├─ sr/jobs/                    # 队列消费者、幂等键
│  └─ tests/
├─ supabase/
│  ├─ migrations/*.sql            # 表、枚举、约束、RLS
│  └─ seed/*.sql                  # 公司、证券、基准 v1、目标定义
├─ config/
│  ├─ targets.yaml                # 目标定义（版本化）
│  ├─ quote_rules.yaml            # 合格报价/同步容差（版本化）
│  ├─ benchmarks.yaml             # semis_peer_v1
│  └─ decisions.yaml              # 决策表的机器可读镜像
├─ data/                          # 本地 Parquet（gitignore）
├─ prototype/                     # 本次交付的可交互原型（参考）
└─ docs/  BUILDING_MASTER_PLAN.md DATA_CONTRACT.md DEVELOPMENT_PHASES.md
```

---

## 7. 关键设计决定

1. **两类模型分工**：LLM 只做"原文事实提取 + 解释草稿"，每条输出必须带 `evidence_id` 与原文定位；**数值概率只来自可回放、经校准的统计模型**，且只有 `model_deployments` 中状态为 `live` 且该目标通过门槛的版本可对外展示（S3§2、§6）。
2. **不可覆盖 + 版本追加**：预测、分析、结算、数据快照全部追加式；更正生成新版本，报表记录用哪一版统计。
3. **时间五元组**：`occurred_at`、`source_published_at`、`received_at`、`available_at`、`analysis_as_of`/`published_at` 分别存储（S1「四项时间」+ S2§2），回放只用 `available_at ≤ as_of` 的数据。
4. **基准冻结**：每条预测锁定 `benchmark_version_id`；同行篮子不可计算时按事前规则标记缺失，禁止事后换基准（Brief、S3§1.2）。
5. **训练与推断隔离**：线上只读已批准模型；训练失败不影响线上。
6. **队列在 PG 内**：首版吞吐低（每 5 分钟 ×18 代码），PG 队列足够且事务一致；后续可换 Redis/云队列。
7. **以目标为部署单位**：`regular_60m` 可单独升级（S3§8.3）。
8. **固定时刻表是主评分样本**（D-43）：每天同样的 6 个时点让各日、各模型版本可直接比较，避免"挑时机"偏差；5 分钟快照与事件/按需预测照常运行，但单独分组，不进主评分。

### 7.1 预测与实际对照如何改进模型（D-44）

**可以，而且这是模型改进的主要依据**，但必须走受控闭环，不能"每看到一次结果就调一次参数"——那样会追逐噪声、让历史成绩失真，也让回放无法复现。

| 环节 | 用对照数据做什么 | 产出 | 频率 / 触发 |
|---|---|---|---|
| ① 结算即标签 | 每条已结算的槽位预测成为一条带标签样本（起算/结算报价、相对收益、类别） | 下一版 `training_dataset_versions` | D-22 每周一检查 |
| ② 残差分析 | 按槽位（10:00 vs 14:30）、行情状态、事件类型、公司拆解 `residual_pp` 与命中率；找出系统性偏差（例：10:00 槽位误差偏大 → 开盘波动特征不足） | 特征/模型候选（新 `model_version`） | 每周；研发后台"预测对照"页 |
| ③ 校准检查 | 各概率分箱的实际发生率（校准曲线）、p80/p90 实际覆盖率与区间宽度 | 新 `calibration_version`（重拟合 isotonic/Platt）或 σ̂/分位数模型调整 | 每周；覆盖率偏离名义值 > 10pp 触发 |
| ④ 漂移触发 | 近 20 日 Brier / BSS 相对参照恶化且分块 bootstrap CI 不含 0 | `drift` 告警（D-37）→ 开训练复盘 | 每日结算后 |
| ⑤ 大误差复盘 | 实际落在 p10–p90 区间外的预测进入复盘队列，标注原因（新闻漏抓、时间错位、基准问题、真正意外） | 数据/提取修复、事件分类补充、LLM 评估集新样本 | 每日 |
| ⑥ 上线门槛 | 任何改动都以新版本进入影子测试 ≥ 20 个交易日，按 D-21 同口径对照后审批 | `model_deployments` | 每次候选 |

护栏：已发布预测与结算永不修改；训练只用 `available_at ≤ T` 的数据并按 D-19 切分；样本数 < 30 的切片只报计数不下结论；同一天的样本按交易日整块 bootstrap，避免把一天的行情当成很多个独立证据。

**作用边界**：对照能发现"哪里系统性地错了"并据此改特征、改校准、改区间，但不能保证提高方向命中率——短期方向本身噪声很大，最可能改善的是概率校准与波动区间。


### 7.2 用户补充信息后"继续分析"：重新采集还是增量补充？（D-48）

| | A. 当作新运行，全部重新采集 | **B. 增量补充（推荐）** |
|---|---|---|
| 做法 | 丢弃当前结果，从头检索所有来源，再分析、预测 | 复用本次运行已采集、已核验的全部条目；只做行情快速刷新 + 自上次水位以来的增量检索 + 用户条目，然后重跑第 2 步分析与第 3 步预测 |
| 速度 | 慢（完整采集 30–60s+，受来源限流影响） | 快（目标 p95 ≤ 30s，不含等待起算报价） |
| 一致性 | 两次结果差异可能来自其他来源的变化，分不清是不是用户信息带来的 | 差异基本只来自用户条目与这段时间的新行情/新条目，界面可直接对比"补充前 vs 补充后" |
| 来源负载 | 每次用户提交都打满所有来源 | 只增量请求 |
| 结果 | 与定时运行没有区别 | 新的分析版本与预测版本，`trigger_type = user_supplement` |

**选择 B。** 具体规则：
1. **不覆盖**：原分析版本与原预测保留；补充运行生成新版本（`supersedes_analysis_id` 指向原版），界面并排显示"补充前 / 补充后"。
2. **不影响评分**：补充运行的预测 `sampling_rule = user_supplement`、`is_primary = false`，单独计分；固定时刻表的槽位预测不变，下一槽位仍按计划完整运行（会自然纳入已核实的用户条目）。这样用户无法通过反复补充来"刷"准确率。
3. **时间不回溯**：用户条目的 `available_at` = 提交时间；回放中它只在提交之后可见。
4. **按核验结果处理**：`verified_primary` / `media_level` → 作为证据参与分析（媒体级不能单独构成"已观察事实"）；`unverified` → 可以继续，但只在推理链中以"用户提供，未证实"列出，不进入模型输入，结论不变时会明确说明；`duplicate` → 提示"已在系统中"，链接到原条目，默认不重跑（可选"仍要重新分析"）；`rejected_restricted` → 不可继续，转合规复核。
5. **晚于窗口**：若提交时某条预测的起算报价已取得，该预测不变，补充只影响新的预测；收盘后提交只影响盘后分析与下一时段展望；休市日提交在下一交易日首个槽位纳入。
6. **可见范围**：补充运行结果先只对提交者与研究员可见，标"含用户补充"；用户条目核验为原始来源或媒体级后，才进入所有人看到的共享分析。
7. **限流与幂等**：同一用户同一证券 2 分钟内只触发 1 次补充运行；同一内容重复提交返回原提交。

---

## 8. 实施风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 历史秒级报价与新闻**首次公开时间**的可得性/精度不足 | 盘中回放和训练无法成立 | Phase 0 采购验证任务；不能确认时点的新闻不进盘中训练（S3§8.1） |
| 共识数据 point-in-time 授权昂贵 | 财报预期差缺失 | 首版允许 `expectation_comparison = null` + "无可核验的事前共识"；先用公司旧指引 |
| LLM 回放泄漏未来（训练记忆） | 回测虚高 | 回放禁搜索；最终用实时影子样本检验（S3§6） |
| 60 分钟重叠样本导致有效样本被高估 | 误批准模型 | 按交易日/事件簇报告有效独立样本，配对差异按簇 bootstrap |
| 事件样本稀少（出口政策、CEO 复任） | 事件增强模型无法验证 | 只给情景+行情基线；单列样本数与不确定性 |
| 数据授权展示限制 | 原文不能对外显示 | `visibility` 字段；页面按权限显示来源定位而非全文 |
| MNPI/疑似泄露材料混入 | 合规 | `restricted_review` 状态，先从公开界面与预测输入排除（S1 合规章节、S2§3.2） |
| 半日市/临时休市处理错误 | 结算错误 | 日历覆盖表 + 边界测试（Phase 0 验收） |

---

## 9. 决策表（未确定事项的统一假设）

状态：`proposed`（本次提出，可调）/ `from_spec`（规格已定）/ `to_verify`（需外部验证）/ `confirmed`（已由人确认，2026-11-26：D-05～D-12）。机器可读镜像：`config/decisions.yaml`。

| ID | 主题 | 决定 / 假设 | 来源 | 状态 | 锁定时点 |
|---|---|---|---|---|---|
| D-01 | 时间存储与显示 | 存 UTC（`timestamptz`），显示 `America/New_York` | S2§2 | from_spec | — |
| D-02 | 预测窗口 | `regular_60m`、`regular_to_close`、`next_regular_session`；`overnight_gap` 可选；S1 的 1–5 日窗口后续 | S3§3.1，C1 | from_spec + proposed | Phase 0 |
| D-03 | 首批与第二批 | 首批 NVDA/AMD/AVGO/MU；第二批 TSM/MRVL；银行/生技仅配置样例 | S3§1.1，C2 | from_spec | — |
| D-04 | 交易日历 | Python `exchange_calendars`（XNYS）为基础 + `trading_calendar_overrides` 覆盖表，对照 Nasdaq 官方日历 | S3§3.1 | proposed | Phase 0 |
| D-05 | 价格类型 | 起算/结算用合并 NBBO 中间价（mid）；无有效 NBBO 时不回退到最后成交 | G1 | confirmed（用户 2026-11-26） | Phase 0 |
| D-06 | 同步容差 | 个股与篮子每个成分的报价时间差 ≤ 2s；篮子成分缺失 > 1 只则基准不可计算 | G1 | confirmed（用户 2026-11-26） | Phase 0 |
| D-07 | 结算容差 | 目标时点后 30s 内首组同步合格报价；无则 `unsettleable` | G1 | confirmed（用户 2026-11-26） | Phase 0 |
| D-08 | 同行篮子 | `semis_peer_v1`：NVDA, AMD, AVGO, MU, QCOM, TXN, INTC, ADI, MRVL, AMAT, LRCX, KLAC；剔除目标后等权；按季度生效；SOXX 仅参考 | S3§1.2，G2 | confirmed（用户 2026-11-26） | Phase 0 |
| D-09 | 三分类阈值（波动缩放） | `threshold_pp = k × sigma_hat_pp`；`sigma_hat_pp` = 发布时对同窗口相对收益标准差的预测（`sigma-0.1`：近 20 个交易日、同一时段桶的 EWMA，半衰期 10 日）；初始 k = 0.25（所有目标）；σ̂ 不可得 → 弃预测 `insufficient_data`。`sigma_hat_pp` 与 k 写入 `predictions.locked`。参考：σ̂ = 0.60pp 时 60m 阈值 = 0.15pp | S3§3.1(3)、MEMO A-1 | confirmed（用户 2026-11-26） | Phase 0 |
| D-10 | 下一时段起算 | 不早于 09:31:00 ET 的首组同步合格报价；10 分钟内无则 `unsettleable` | G4 | confirmed（用户 2026-11-26） | Phase 0 |
| D-11 | 收盘价格 | 上市交易所官方收盘价（Nasdaq Official Closing Price 等）；篮子成分同样口径 | G5 | confirmed（用户 2026-11-26） | Phase 0 |
| D-12 | 合格报价 | bid>0、ask>bid、价差 ≤ 20bp 且 ≤ 近 20 分钟中位价差 ×5、报价年龄 ≤ 5s、非停牌/非 LULD 暂停 | G6 | confirmed（用户 2026-11-26） | Phase 0 |
| D-13 | 实时与历史行情供应商 | 候选：Massive（S1 例举）、Databento、交易所直连；需验证秒级 NBBO 历史回溯年限、官方收盘价、授权展示 | S1[10]，G7 | to_verify | Phase 0 |
| D-14 | 实时延迟指标 | 交易所时间→参考报价入缓冲 p95 < 1s；快报 p95 < 3 分钟（S2§6 只要求观测） | S2§6 | proposed | Phase 2 |
| D-15 | 新闻、政策与其他来源 | SEC EDGAR（免费，API，含 8-K 与 **Form 4**）、公司 IR RSS、Federal Register/BIS/白宫；**法院案卷**：CourtListener/RECAP（免费，覆盖不全）为主，关键案件按需 PACER；**宏观**：BLS/BEA/Fed 官方发布 + FRED/ALFRED 历史 vintage（首发值）；**期权**：Phase 4 前不采购，仅留接口；授权新闻快讯候选待选 | S1 来源、PPT 审查 | to_verify | Phase 0（法院/宏观/Form 4 在 Phase 2 前样本验证） |
| D-16 | 共识预期 | FactSet / LSEG point-in-time 候选；未采购前 `expectation_comparison` 允许为空 | S1[7] | to_verify | Phase 2 |
| D-17 | 定时刷新频率 | 正常时段每 5 分钟；另在 09:35、15:45 ET 检查；同水位合并 | S2§1，S3§2 | from_spec | — |
| D-18 | 60m 发布截止 | 要求 t0 + 60m + 30s ≤ 当场收盘；至收盘最短剩余 15 分钟 | S3§3.1 | from_spec + proposed | Phase 0 |
| D-19 | 数据切分 | 训练/校准/验证/留出按时间；边界前后各隔 ≥ 1 个完整交易日；同事件簇、同宏观冲击同组 | S3§8.1，G8 | proposed | Phase 1 |
| D-20 | 初始训练窗口 | 2021-01 起至最近已结算日（以可得数据为准）；半导体同行 12 只样本池 | S3§8.1 | proposed | Phase 1 |
| D-21 | 上线门槛 | `gate_config v0`：留出 ≥ 60 个独立交易日、影子 ≥ 20 个交易日；Brier 相对行情基线配对改善 CI 上界 < 0；覆盖率下降 ≤ 10pp；关键分组退化 ≤ 0.005 Brier | S3§6/§8.4，G9 | proposed | Phase 3 前 |
| D-22 | 训练检查节奏 | 每周一 06:00 ET 检查新结算样本；手动与漂移触发 | S3§8.3 | from_spec | — |
| D-23 | 主评分抽样 | **0.5 修订**：主评分样本 = 固定时刻表槽位预测（D-43）；事件触发取证券×事件节点×目标的首条合格发布，单独分组；5 分钟快照预测、按需与修订另计、不进主评分 | S3§4(5)、用户 2026-11-26 | from_spec + proposed（槽位替代整 5 分钟时点） | Phase 1 |
| D-24 | 行情基线模型 | L2 正则多项逻辑回归，约 20 个特征（S3§8.2）；树模型为对照 | S3§8.2 | from_spec | — |
| D-25 | LLM 提供商 | 接口化；默认候选 Anthropic Claude；回放禁联网与禁记忆补全 | Brief | proposed | Phase 1 |
| D-26 | 前端框架 | Next.js + Supabase Auth/RLS；角色 `viewer`、`researcher`、`reviewer`、`admin` | Brief | proposed | Phase 0 |
| D-27 | 行情存储 | 1 秒层与原始文件存 Parquet（对象存储），PG 存 1m bar 与被引用报价 | §5 | proposed | Phase 0 |
| D-28 | 延长时段预测 | 首版不发布盘前/盘后预测，仅展示分析与下一时段展望 | S3§3.1 | from_spec | — |
| D-29 | 预期波动目标 | 新增 `regular_60m_move`：预测同一 60 分钟窗口 `abs(relative_return_pp)` 的分位数（p50/p80/p90），基线为 HAR 式已实现波动模型；用 pinball loss 与区间覆盖率评分；与方向目标共享起算/结算报价 | MEMO A-2 | proposed | Phase 1 |
| D-30 | 评分基线与检验 | 方向目标报告 Brier Skill Score（BSS = 1 − Brier/Brier_ref），三条参照：`class_frequency`、`always_flat`、`persistence`（上一个 60 分钟相对收益方向延续）；候选 vs 线上用按交易日分块 bootstrap（2,000 次）求配对差 95% CI | MEMO E-1/E-2 | proposed | Phase 1 |
| D-31 | 免费特征（fs-0.2） | 时段/日历（距开盘、距收盘、星期、半日市、三巫日、指数调仓日）；跨资产代理（QQQ、SPY 30/60 分钟收益，^VIX 水平与变化）；篮子内领先滞后（各成分 5/15/30 分钟收益与 SMH）；波动状态（5/30/390 分钟已实现波动、隔夜跳空、开盘区间） | MEMO I-1～I-4 | proposed | Phase 0 定义 / Phase 1 实现 |
| D-32 | LLM 提取评估集 | 人工标注约 300 份文档（财报、政策、8-K、新闻各类），评估事实、方向、范围、确定性四类字段的 precision/recall；提示词版本冻结；低于门槛（初始：数值事实 precision ≥ 0.98、方向 F1 ≥ 0.85）的提示词版本不得进入特征 | MEMO A-11 | proposed | Phase 1 |
| D-33 | 内部可见层级门槛 | 见 §12：仅限内部团队，不对外开放；内部日常使用层级 v1（证据 + 预期波动）→ v2（方向概率，仅达标切片）→ v3（其他目标） | MEMO §4 | proposed | Phase 3 前锁定 |
| D-34 | 一键运行规则 | 默认 `reuse_if_unchanged`；`force_recompute` 仅 `researcher+`；同一用户同一证券 1 分钟内重复点击按幂等键返回同一运行；按需预测不进主评分；live 单只证券端到端 p95 ≤ 90s（不含等待起算报价） | S3§2、§4(5) | proposed | Phase 2 |
| D-35 | 新公司接入门槛 | 回填 ≥ 3 年分钟行情（秒级 ≥ 1 年）；合格报价率 ≥ 95%；同步成功率 ≥ 95%；盘中新闻时间精度已知 ≥ 90%；LLM 抽检通过 D-32；影子 ≥ 20 个交易日；不满足 → 只做 `peer_only`（训练池）或停在 `blocked` | S3§1.2、§8.1 | proposed | Phase 2 |
| D-36 | 新公司参数 | 先 `market_sector_only`；公司偏移只有在留出与影子都改善（D-21 同口径）后才启用 | S3§8.2 | from_spec | — |
| D-37 | 告警阈值 | 来源 p95 延迟 > 60s 或 5 分钟无成功 → warning；> 15 分钟 → critical；结算积压 > 50 条或 > 10 分钟 → warning；流水线失败率 1 小时 > 5% → critical | S2§6 | proposed | Phase 2 |
| D-38 | 历史类比 | `hc-0.1`：只用过去、同事件链不自匹配；匹配键 事件类型+子类型+行业模板+市场时段（财报加超预期分档）；`min_cases = 8`，不足逐级放宽并披露；仍不足显示"历史样本不足"；不作方向信号（DC §3.4a） | S1、S2§3.4、PPT | proposed | Phase 1 |
| D-39 | 事件结果结算与条件预测 | 事件轨道用 `outcome_resolution`：解决里程碑 + 官方确认来源；公开确认时间与法律生效时间分别记录，报表按公开确认；截止无结果 → `no_confirmation`；监管批准 ≠ 交割完成。条件预测：`condition_outcome` + `trigger_deadline_at`，触发后首个同步合格报价起算；未触发 → `not_triggered`，单独计 `trigger_rate`，不计命中率 | S1§11、S3§3.2、PPT | proposed | Phase 2 |
| D-40 | 公司行为 | `corporate_actions` 存拆股/分红/分拆/改代码；报价存原始价，研究库生成复权价；窗口跨除权日按比例调整，现金分红 < 0.5% 忽略；比例未知 → `unsettleable/corporate_action` | S3§5、PPT | proposed | Phase 1 |
| D-41 | 有效期与过期显示 | 快照 `valid_until`（盘中 = 下次定时 + 5 分钟；盘后 = 次日盘前首个快照）；预测 `valid_until = target_end_at`（条件预测 = 触发截止）；被修订的预测灰显并链接新版；过期未结算显示"已过期，待结算" | S2§5、PPT | proposed | Phase 1 |
| D-42 | 行业模板 | `industry_template ∈ {semiconductor, bank, biotech, generic}` 决定默认指标、来源与影响维度；同一政策事件按模板分别解读（例：出口管制对芯片 = 收入敞口，对银行 = 无直接敞口/客户信用）；银行与生物医药模板只做配置与测试，不进首版验收名单（与 D-03 一致） | S1「跨行业配置」、S2§1、PPT | proposed | Phase 2 |
| D-43 | 每日预测时刻表 | `sched-0.1`：08:30 盘前展望（`next_regular_session`，当日）；10:00、11:30、13:00、14:30 `regular_60m` + `regular_60m_move`（14:30 加 `regular_to_close`）；16:30 盘后展望（下一时段）。半日市：保留 10:00、11:30，11:30 加至收盘，跳过 13:00/14:30，盘后展望改 13:30；休市日不发；槽位 + 180s 未发布 → `abstained/slot_missed`，不补发 | 用户 2026-11-26、S3§3.1 | proposed | Phase 1 |
| D-44 | 预测与实际对照 | 每条预测一行 `forecast_vs_actual`：展示路径 = 锁定分位数按 √时间缩放（仅展示，`sqrt_time_v1`），实际路径 = 起算后每分钟同步相对收益；滚动准确率 `forecast_accuracy_rollups`（当日 / 20 日 / 60 日 / 上线以来，n < 30 标样本不足）。对照只通过 §7.1 闭环进入模型 | 用户 2026-11-26、S3§8 | proposed | Phase 1（后端）/ Phase 2（界面） |
| D-45 | 信息采集可见性 | 每次运行记录 `collection_runs` 与全部 `collection_items`（含去重、排除、待核、抓取失败），按渠道 × 类别汇总；受限材料只显示占位；授权新闻只显示标题与定位；行情以汇总项记录；条目保留 ≥ 2 年供回放 | 用户 2026-11-26、S1「四项时间」、S2§3.1–3.2 | proposed | Phase 1 |
| D-46 | 推理可追溯 | `market_explanation` 每条陈述必须引用证据/报价/采集项，无引用 → 校验拒绝并改放"未解释"；`reasoning_trace` 有序记录行情事实、时间对齐、证据、归因、反向检查、历史类比、缺口、结论；确定性步骤由代码生成，LLM 只起草归因与反向证据且必须引用 | 用户 2026-11-26、S2§3.5、MP §7-1 | proposed | Phase 1 |
| D-47 | 用户补充信息 | 入口在 ① 信息采集；链接/文本/文件；类别 = 用户选择 ∪ 系统建议（置信度 ≥ 0.6，可多类别）；走与采集相同的核验（链接可达、来源信誉、原始来源追溯、内容与时间一致、查重、未公开材料筛查）；状态 `verified_primary` / `media_level` / `unverified` / `duplicate` / `rejected_restricted` / `fetch_failed`；不默认可信；`available_at` = 提交时间；系统漏采的原始来源记为覆盖缺口 | 用户 2026-11-26、S1「四项时间」「内幕信息」、S2§3.2 | proposed | Phase 2 |
| D-48 | "继续分析"＝增量补充运行 | 见 §7.2：复用已有采集与核验，只刷新行情 + 增量检索 + 用户条目，重跑分析与预测生成新版本；`trigger_type = user_supplement`、`is_primary = false`、单独计分；槽位预测不变；先对提交者可见，核验后共享；每用户每证券 2 分钟 1 次 | 用户 2026-11-26、S3§2、§4(5) | proposed | Phase 2 |

---

## 10. 追溯表

列：主要功能 → 来源文件及章节 → Data Contract 字段/接口 → Phase → 原型页面 → 验收用例（编号见 `DEVELOPMENT_PHASES.md` §验收用例）→ 状态 → 优先级。

**状态**：`已设计`（契约、阶段任务、验收与原型都已有）/ `待验证来源`（设计已定，依赖 D-13～D-16 的外部来源样本验证）/ `占位`（只定义接口与字段，后续阶段启用）。**优先级**：`P-必需`（MVP 验收必须通过）/ `P-高`（MVP 内，可在阶段末补）/ `P-中`（MVP 后首批增强）/ `P-低`（后续阶段）。

| 功能 | 来源 | Data Contract | Phase | 原型页面 | 验收 | 状态 | 优先级 |
|---|---|---|---|---|---|---|---|
| 公司与证券配置（代码有效期、基准） | S2§2、S1「跨行业配置」 | `companies`、`securities`、`security_identifiers`、`company_profile_versions` | P0 | 公司监控 | AC-01 | 已设计 | P-必需 |
| 交易日历与窗口可用性 | S3§3.1 | `trading_sessions`、`GET /api/calendar` | P0 | 短期预测（休市/窗口不足态） | AC-02、AC-03 | 已设计 | P-必需 |
| 合格报价与同步 | S3§3.1、S2§3.5 | `reference_quotes`、`quote_rule_version` | P0 | 预测回放（起算报价） | AC-04 | 已设计 | P-必需 |
| 同行篮子与 SOXX 参考 | S3§1.2、Brief | `benchmark_definitions`、`benchmark_versions` | P0 | 股票详情（行业表现） | AC-05 | 已设计 | P-必需 |
| 原始证据与四类时间 | S1「四项时间」、S2§2 | `source_documents`、`source_document_versions`、`event_evidence` | P1 | 股票详情（证据） | AC-06 | 已设计 | P-必需 |
| 去重归并与事件版本 | S2§3.2 | `events`、`event_analysis_versions`、`event_milestones` | P1 | 待决事件 | AC-07、AC-08 | 已设计 | P-必需 |
| 预期对比 | S2§3.3 | `expectation_snapshots`、`expectation_comparison` | P1 | 股票详情（财报场景） | AC-09 | 待验证来源 | P-必需 |
| 市场反应与当前解释 | S2§3.5 | `market_reaction`、`market_explanation` | P1 | 股票详情 | AC-10 | 已设计 | P-必需 |
| 证券状态快照（含无新闻日） | S2§1、§5 | `security_state_snapshots` | P1 | 公司监控、股票详情 | AC-11 | 待验证来源 | P-必需 |
| 预测交接 | S2§4–5、S3§2 | `prediction_readiness` | P1 | 股票详情 / 短期预测 | AC-12 | 已设计 | P-必需 |
| 60 分钟预测与锁定 | S3§3.1、§4 | `prediction_targets`、`prediction_runs`、`predictions` | P1 | 短期预测 | AC-13 | 已设计 | P-必需 |
| 自动结算 | S3§3.1、§5 | `prediction_settlements` | P1 | 预测回放 | AC-14、AC-15 | 已设计 | P-必需 |
| 基础训练与指标记录 | S3§8、Brief | `training_dataset_versions`、`training_runs`、`training_run_metrics` | P1 | 研发后台·训练任务 | AC-16 | 已设计 | P-必需 |
| 首批四家 + 实时触发 | S3§1.1、§2 | `jobs`、`trigger_type` | P2 | 公司监控 | AC-17 | 已设计 | P-高 |
| 数据缺失与弃预测 | S3§2、§3.1(4) | `abstain_reason`、`invalid_reason` | P2 | 短期预测（数据不足/无法结算） | AC-18 | 已设计 | P-高 |
| 模型对照与影子测试 | S3§8.3–8.4 | `model_versions`、`model_evaluations` | P3 | 研发后台·验证/影子 | AC-19、AC-20 | 已设计 | P-高 |
| 行业/公司参数消融 | S3§8.2 | `model_versions.param_layers` | P3 | 研发后台·参数对比 | AC-21 | 已设计 | P-高 |
| 审批与回滚 | S3§8.3、§9 | `model_deployments` | P3 | 研发后台·审批 | AC-22 | 已设计 | P-高 |
| 待决事件结果预测（独立计分） | S1§11、S3§3.2 | `prediction_targets(track=event_outcome)` | P1(情景)/P4(概率) | 待决事件 | AC-23 | 已设计 | P-中 |
| 至收盘 / 下一时段 | S3§3.1 | `target_id` 枚举 | P4 | 短期预测（切换） | AC-24 | 已设计 | P-中 |
| 合规：疑似泄露 | S1「内幕信息」、S2§3.2 | `visibility=restricted_review` | P1 | 股票详情（证据受限态） | AC-25 | 已设计 | P-必需 |
| 波动缩放阈值 | S3§3.1(3)、MEMO A-1 | `prediction_targets.threshold_rule`、`predictions.locked.sigma_hat_pp` | P0 | 短期预测（阈值说明） | AC-26 | 已设计 | P-必需 |
| 预期波动目标 | MEMO A-2 | `target_id=regular_60m_move`、`predictions.move_quantiles`、`prediction_settlements.abs_relative_move_pp` | P1 | 短期预测（预期波动卡片） | AC-27 | 已设计 | P-必需 |
| BSS 与分块 bootstrap | MEMO E-1/E-2 | `training_run_metrics.metric ∈ {brier_skill_score, …}`、`reference_model` | P1 | 研发后台·验证总览 | AC-16、AC-28 | 已设计 | P-必需 |
| 免费特征 fs-0.2 | MEMO I-1～I-4 | `config/features/fs-0.2.yaml`、`securities.coverage_tier=reference` | P0/P1 | 研发后台·参数对比 | AC-29 | 已设计 | P-必需 |
| LLM 提取评估 | MEMO A-11 | `extraction_eval_runs` | P1 | 研发后台（后续） | AC-30 | 已设计 | P-高 |
| 对外开放门槛 | MEMO §4 | `model_deployments.audience` | P3 | 研发后台·发布审批 | AC-31 | 已设计 | P-高 |
| 新公司接入工作流 | Brief、S3§1.2、§8.2 | `onboarding_requests`、`POST /api/ops/onboarding/*` | P2（流程）/P3（训练与审批联动） | 运营·新公司接入 | AC-32、AC-33 | 已设计 | P-高 |
| 一键端到端运行 | Brief、S2§1、S3§2 | `pipeline_runs`、`pipeline_run_steps`、`POST /api/pipeline-runs` | P1（CLI/dry_run）/P2（页面与实时） | 运营·一键运行；股票详情"运行"按钮 | AC-34、AC-35 | 已设计 | P-必需 |
| 数据源健康与告警 | S2§6 | `data_source_health`、`alerts` | P2 | 运营·数据源、任务与告警 | AC-36 | 已设计 | P-高 |
| 公司行为（拆股、分红、改代码） | S3§5、PPT 审查 | `corporate_actions`、`invalid_reason=corporate_action`（D-40） | P1 | 股票详情（公司行为提示） | AC-37 | 已设计 | P-必需 |
| 历史类比 | S1、S2§3.4、PPT | `historical_cases`、DC §3.4a（D-38） | P1 | 待决事件（历史类比卡） | AC-38 | 已设计 | P-高 |
| 盘后大幅异动（+8%）分析 | S2§3.5、PPT 测试例 | `market_state=post_market`、`trigger_type=market_move` | P1 | 股票详情（盘后状态） | AC-39 | 已设计 | P-必需 |
| 盘后基准缺失 → 相对收益为空 | S3§3.1、PPT | `benchmark_unavailable`、`day_relative_pp=null` | P1 | 股票详情 | AC-40 | 已设计 | P-高 |
| 传闻 → 官方确认的版本化 | S2§3.2、PPT 测试例 | `event_evidence.verification_status`、`event_analysis_versions` | P1 | 待决事件（版本历史） | AC-41 | 已设计 | P-高 |
| 估值背景 | S1「估值」、PPT | `market_explanation.valuation_context`、`company_profile_versions.valuation_peers` | P1 | 股票详情（估值背景行） | AC-42 | 待验证来源 | P-中 |
| 事件结果结算（公开确认/法律生效） | S1§11、S3§3.2、PPT | `prediction_targets.outcome_resolution`、`no_result_rule`、`prediction_settlements.public_confirmation_at/legal_effective_at`（D-39） | P2 | 待决事件（结算规则） | AC-43 | 已设计 | P-高 |
| 监管批准 ≠ 交割完成 | S1§11、PPT 测试例 | `event_milestones.milestone_type ∈ {regulatory_clearance, closing}` | P2 | 待决事件（里程碑） | AC-44 | 已设计 | P-高 |
| 条件预测（触发与触发率） | S3§3.2、PPT | `prediction_targets.condition`、`prediction_settlements.triggered`、`metric=trigger_rate` | P2 | 待决事件（条件预测卡） | AC-45 | 已设计 | P-高 |
| 宏观首发值 | S1「宏观」、PPT | `macro_releases`（ALFRED vintage） | P2 | 研发后台·数据集 | AC-46 | 待验证来源 | P-高 |
| 法院案卷 | S1「诉讼」、PPT | `docket_entries`、`DocketSource` | P2 | 待决事件（诉讼里程碑） | AC-47 | 待验证来源 | P-高 |
| 内部人交易与预期修正 | S1「管理层/预期」、PPT | `insider_transactions`（Form 4）、`expectation_snapshots.revision_of_exp_id` | P2 | 股票详情（证据） | AC-48 | 已设计 | P-中 |
| 运行状态、有效期、过期/被替代显示 | S2§5、PPT | `run_state`、`quality_issues`、`last_valid_at`、`valid_until`、`display_state`（D-41） | P1（字段）/P2（界面） | 公司监控、股票详情、短期预测 | AC-49 | 已设计 | P-必需 |
| 行业模板与跨行业政策 | S1「跨行业配置」、S2§1、PPT | `industry_templates`、`company_profile_versions.industry_template`（D-42） | P2 | 运营·新公司接入（模板选择） | AC-50 | 已设计 | P-中 |
| 区间宽度指标 | S3§8.4、PPT | `metric=interval_width` | P3 | 研发后台·验证总览 | AC-28（扩展） | 已设计 | P-高 |
| 每日预测时刻表（主评分点） | 用户 2026-11-26、S3§3.1、§4(5) | `forecast_schedules`、`predictions.schedule_slot_id`、`sampling_rule=schedule_slot`（D-43） | P1（定义与回放）/P2（实时） | 短期预测（槽位标记）、运营·任务 | AC-52 | 已设计 | P-必需 |
| 预测与实际对照（两条曲线 + 滚动准确率） | 用户 2026-11-26、S3§5、§8 | `forecast_vs_actual`、`forecast_accuracy_rollups`、`GET /api/securities/{id}/forecast-vs-actual`（D-44） | P1（视图）/P2（股票详情）/P3（后台） | 股票详情·预测与实际；研发后台·预测对照 | AC-53、AC-54、AC-55 | 已设计 | P-必需 |
| 第 1 步信息采集可见（数量、渠道、类别、处置、四类时间） | 用户 2026-11-26、S1、S2§3.1–3.2 | `collection_runs`、`collection_items`、`GET /api/securities/{id}/collection`（D-45） | P1（记录）/P2（界面） | 股票详情·① 信息采集 | AC-56、AC-58 | 已设计 | P-必需 |
| 第 2 步推理可追溯（每条结论链接所用条目） | 用户 2026-11-26、S2§3.5 | `market_explanation` 引用对象、`reasoning_trace`、`GET /api/snapshots/{id}/reasoning`（D-46） | P1（记录）/P2（界面） | 股票详情·② 分析与推理 | AC-57、AC-58 | 已设计 | P-必需 |
| 用户补充信息（添加、分类、核验） | 用户 2026-11-26 | `user_submissions`、`collection_items.channel=user_submission`、`POST /api/securities/{id}/submissions`（D-47） | P2 | 股票详情·① 信息采集·添加信息 | AC-59、AC-60 | 已设计 | P-高 |
| "继续分析"增量补充运行 | 用户 2026-11-26 | `pipeline_runs.mode=supplement`、`base_run_id`、`trigger_type=user_supplement`（D-48） | P2 | 股票详情·继续分析 | AC-61 | 已设计 | P-高 |
| 期权隐含波动 | S1「市场预期」、PPT | `options_snapshots`、`OptionsProvider` | P4 | —（占位） | AC-51 | 占位 | P-低 |

---

## 11. 一致性核对（四项交付物）

| 项 | 统一定义 | 出现位置 |
|---|---|---|
| 交易时钟 | 存 UTC，显示 ET；正常 09:30–16:00 ET，半日市 09:30–13:00；`market_state ∈ {pre_market, regular, post_market, closed, halted}` | 本文 §9 D-01/D-04，DC §2，DP P0，原型顶栏 |
| 首批公司 | NVDA、AMD、AVGO、MU；第二批 TSM、MRVL | 本文 §1，DC seed，DP P2，原型切换器 |
| 基准 | 主：`semis_peer_v1`（剔除目标等权）；参考：SOXX | 本文 D-08，DC `benchmark_versions`，原型"行业表现" |
| 预测时刻表 | 08:30 / 10:00 / 11:30 / 13:00 / 14:30 / 16:30 ET（`sched-0.1`），槽位预测为主评分样本 | 本文 D-43/D-23，DC §3.7a，DP AC-52，原型股票详情与预测页 |
| 分类阈值 | `threshold_pp = k × sigma_hat_pp`（k=0.25，sigma-0.1），锁定在每条预测 | 本文 D-09，DC `threshold_rule` / `locked`，DP AC-26，原型预测卡说明 |
| 预测状态 | `pending_evaluation → published → awaiting_trigger|awaiting_settlement → settled`；终态另有 `abstained`、`not_triggered`、`unsettleable` | DC §5，原型状态徽标 |
| 版本字段 | `schema_version`、`analysis_version`、`target_definition_version`、`quote_rule_version`、`benchmark_version_id`、`model_version_id`、`calibration_version`、`settlement_version`、`dataset_version_id`、`feature_set_version`、`code_version` | DC §3，原型回放页"锁定输入" |

## 12. 上线边界与内部可见层级（D-33）

**使用范围（2026-11-26 确认）：仅限内部团队使用，不计划对外开放。** 下表的 v1～v3 是内部日常使用界面的可见层级（研发人员始终可看全部，包括影子模型），不是对外用户阶段。

首版"上线"= 内部研究环境，邀请制内部账户；日常使用界面仅展示证据、解释、情景和**已通过门槛**的目标概率；未通过门槛的目标在用户端显示"模型验证中，仅展示行情与证据"。无交易执行、无外部推送。

| 阶段 | 谁能看到什么 | 门槛（锁定于 `gate_config`） |
|---|---|---|
| 内部（现在 → Phase 3） | 全部，含影子模型 | — |
| 内部层级 v1 | 证据、当前解释、事件情景、**预期波动** `regular_60m_move` | 区间名义 80% 的实测覆盖率在 [77%, 83%] 内，留出 ≥ 60 个独立交易日 + 实时影子 ≥ 20 个交易日；pinball loss 优于 HAR 基线 |
| 内部层级 v2 | `regular_60m` 方向概率，仅限通过的切片（证券 × 时段 × 有无新闻），且只在模型相对基线的优势高于发布阈值时显示 | BSS（对 `class_frequency`）> 0 且分块 bootstrap 95% CI 下界 > 0，留出与实时影子均满足 |
| 内部层级 v3 | `regular_to_close`、`next_regular_session`、价格区间 | 每个目标同样门槛 |

`model_deployments.audience ∈ {internal, selected_v1, selected_v2, selected_v3}` 控制展示范围（枚举名保持不变以免影响已写代码，`selected_v*` 解释为内部可见层级）；日常使用账号为内部 `viewer` 角色。
