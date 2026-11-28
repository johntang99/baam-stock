# DEVELOPMENT PHASES · 美股短期研究与预测系统

**版本** `phases-0.7` · 2026-11-26（0.7：用户补充信息与"继续分析"增量补充运行，AC-59～AC-61，WBS 约 242 人日；0.6：第 1 步采集与第 2 步推理可见，AC-56～AC-58；0.5：每日预测时刻表与预测—实际对照，AC-52～AC-55；0.4：补齐 PPT 蓝图审查的 19 项缺口，AC-37～AC-51） · 引用：`BUILDING_MASTER_PLAN.md`（plan-0.7，决策 D-xx）、`DATA_CONTRACT.md`（契约 `contract-0.7`）、`MODEL_IMPROVEMENT_MEMO.md`（§5 已并入）

> **路线图扩展**：Phase 5～7（中长期预测、买卖信号、自有资金系统执行交易）见 `roadmap/ROADMAP_EXTENSIONS_CN.md`，仅规划，不改变 Phase 0～4 的任务、验收与当前契约。

**0.3 更新**：补充总览（周期、工作线、环境、完成定义）、基础设施与 CI、新公司接入工作流、一键端到端运行、数据源健康与告警、运维手册，以及附录 A 工作分解（约 80 项任务、估算与依赖）和附录 C 各阶段 Claude Code 指令模板。

**工具链约定**：Node 20 + pnpm、Next.js（App Router, TS）、Supabase CLI（本地 `supabase start`）、Python 3.12 + uv、pytest、DuckDB + PyArrow、scikit-learn。所有时间以 UTC 存储。

**依赖图**

```
P0 ──► P1 ──► P2 ──► P3 ──► P4(后续)
 │      └── P1 内：日历/报价/基准(P0产物) → 快照 → 预测 → 结算 → 基础训练 → 一键运行 CLI
 └── P0 内可并行：[A]契约+迁移  [B]日历  [C]合格报价+基准  [D]数据采购验证  [E]原型对齐  [F]阈值/评分  [G]特征定义  [H]基础设施/CI
```

## 总览

### 周期与里程碑（粗估）

假设团队：1 名全栈工程师 + 1 名量化/数据工程师，均使用 Claude Code；数据供应商在 Phase 0 结束前签约。估算为日历周，含评审与返工，**不含**等待数据采购的时间。

| 阶段 | 周期 | 里程碑（可演示） | 对外 |
|---|---|---|---|
| Phase 0 | 2–3 周 | 契约、日历、报价规则、阈值与评分函数全部有测试；CI 绿；数据样本验证报告 | — |
| Phase 1 | 6–7 周 | NVDA 三类历史日完整回放 + 自动结算 + 基础训练与指标 + `sr run --mode replay` 一键回放；公司行为、历史类比、运行状态与有效期、估值背景；盘后异动与传闻→确认场景；每日时刻表回放与预测—实际对照视图 | — |
| Phase 2 | 7–8 周 | 四家实时运行；网页上线（内部）；点击"运行"端到端；新公司接入 1–5 阶段；数据源健康与告警；staging 环境；事件结果结算与条件预测；宏观首发值、法院案卷、Form 4 来源；行业模板（芯片 + 银行测试）；时刻表实时运行与股票详情"预测与实际"两条曲线 | 内部团队 |
| Phase 3 | 4–5 周 | 研发后台完整；影子测试；审批/回滚；接入 6–8 阶段（训练→影子→上线）；TSM/MRVL 走完接入 | 内部层级 v1（若门槛通过） |
| Phase 4+ | 持续 | 至收盘/下一时段、区间、更多事件子类与行业；期权隐含波动（来源验证后） | 内部层级 v2/v3 |

合计到"内部完整可用"约 4–5 个月（附录 A 合计约 242 人日，2 名工程师）；到内部层级 v1 取决于影子测试时长（≥ 20 个交易日）与门槛结果。

### 工作线（贯穿各阶段）

| 工作线 | 内容 | 主要阶段 |
|---|---|---|
| T1 数据 | 供应商适配器、行情 1 秒层、证据采集、回填、数据质量 | P0–P2 |
| T2 分析 | 事件归并与版本、提取、市场反应、解释、交接 | P1–P2 |
| T3 预测与结算 | 快照、推断、发布、结算、按需运行 | P1–P2 |
| T4 训练与评估 | 数据集、训练、校准、评估、影子、审批 | P1–P3 |
| T5 网页 | 市场页面、研发后台、运营页面 | P2–P3 |
| T6 运营与基础设施 | 环境、CI/CD、队列、调度、监控、告警、备份、运维手册 | P0–P3 |
| T7 合规与权限 | RLS、授权范围、受限复核、审计日志、内部可见层级 | P1–P3 |

### 环境

| 环境 | 用途 | 数据 |
|---|---|---|
| `local` | 开发；`supabase start` + 本地 Parquet | 合成 fixture + 小样本 |
| `staging` | 集成测试、回放、影子运行 | 授权历史数据 + 实时行情（延迟可接受） |
| `prod` | 仅限内部团队研究使用（不对外开放） | 授权实时数据 |

Python worker 部署为容器（单机起步，可横向扩展），Next.js 部署到 Vercel 或同类平台，Supabase 各环境独立项目；密钥只放平台 Secret，不入库。

### 每项任务的完成定义（Definition of Done）

1. 代码与迁移合并到主干，CI 全绿（lint、类型检查、单元测试、契约示例校验）。
2. 字段与枚举与 DATA_CONTRACT 一致；如需改契约，先改文档与 JSON Schema 并升 `schema_version`。
3. 有对应验收用例（AC-xx）的自动化测试或可复现脚本。
4. 涉及时间的逻辑有"读取未来数据即报错"的负向测试。
5. 更新 `docs/CHANGELOG.md`；涉及运维的更新运维手册（附录 B）。

---

## Phase 0 · 数据源验证与最小契约锁定

**目标**：选定（拟选）数据源并用样本证明可得性；锁定最小契约、交易日历、基准与合格报价规则；所有规则有可执行的单元测试。

| 工作项 | 先/并行 | 预期文件 |
|---|---|---|
| P0-A 仓库骨架与契约：JSON Schema（§3 中 P0/P1 所需实体）、生成 pydantic 与 TS、SQL 迁移、seed | 先 | `packages/contracts/schemas/*.schema.json`、`packages/contracts/examples/*.json`、`supabase/migrations/0001_core.sql`、`supabase/seed/0001_pilot.sql`、`services/py/sr/contracts/*.py` |
| P0-B 交易日历与窗口可用性 | 并行 | `services/py/sr/calendar/{calendar.py,windows.py}`、`config/calendar_overrides.yaml`、`tests/test_calendar.py` |
| P0-C 合格报价规则、同步、同行篮子收益 | 并行 | `services/py/sr/marketdata/{quote_rules.py,sync.py}`、`services/py/sr/benchmark/basket.py`、`config/{quote_rules.yaml,benchmarks.yaml,targets.yaml}`、对应测试 |
| P0-F 波动缩放阈值与评分函数：`sigma-0.1` 估计器（D-09）、`threshold_pp = k × sigma_hat_pp`、三分类 Brier、BSS（三条参照）、pinball loss、按交易日分块 bootstrap（D-30） | 并行 | `services/py/sr/labels/{sigma.py,thresholds.py}`、`services/py/sr/eval/{metrics.py,bootstrap.py}`、`config/sigma.yaml` |
| P0-G 免费特征 fs-0.2 的**定义**（只写规格与单元测试用的纯函数，不训练）：时段/日历、QQQ/SPY/^VIX 代理、篮子领先滞后、波动状态（D-31）；seed 参考品种 `coverage_tier='reference'` | 并行 | `config/features/fs-0.2.yaml`、`services/py/sr/features/{calendar_feats.py,cross_asset.py,lead_lag.py,vol_regime.py}` |
| P0-H 基础设施与 CI：GitHub Actions（ruff、mypy、pytest、tsc、eslint、契约示例校验、迁移可重放）、pre-commit、`.env.example`、`docs/CHANGELOG.md`、`docs/OPEN_QUESTIONS.md` | 先 | `.github/workflows/ci.yml`、`.pre-commit-config.yaml`、`Makefile` |
| P0-D 数据采购验证：供应商对比表、样本下载脚本、可得性报告（真实样本可用则用，否则用固定 fixture 并标 `verification_status=proposed`） | 并行 | `docs/data_procurement.md`、`services/py/sr/marketdata/providers/{base.py,fixture.py}`、`scripts/validate_sample.py`、`data/fixtures/nvda_2026-12-01_1s.parquet`（合成） |
| P0-I 新增 P0/P1 实体的契约（0.4）：`corporate_actions`、`industry_templates` 与 `company_profile_versions.industry_template`、快照 `run_state`/`quality_issues`/`last_valid_at`/`valid_until`、预测 `valid_until`；seed 首批公司 `industry_template=semiconductor` | 并行 | `packages/contracts/schemas/{corporate_actions,industry_templates}.schema.json`、`supabase/seed/0001_templates.sql` |
| P0-E 决策表镜像与原型字段对齐 | 并行 | `config/decisions.yaml`、`prototype/`（复制交付物） |

**演示数据**：合成的 NVDA + 篮子 11 只 2026-12-01 秒级报价（含 1 段宽价差、1 次停牌 3 分钟），2026-11-26（休市）、2026-11-27（半日市）。

**验证命令**

```bash
pnpm install && pnpm -r build
supabase start && supabase db reset          # 迁移 + seed 成功
uv run pytest services/py/tests -q
uv run python scripts/validate_sample.py --fixture data/fixtures/nvda_2026-12-01_1s.parquet
pnpm --filter contracts test                  # examples/*.json 通过 schema 校验
```

**验收标准（可判定）**

- AC-01 seed 后 `securities` 有 4 条 `coverage_tier='pilot'`、2 条 `batch2`；每只首批证券的 `primary_benchmark_id` 指向剔除自身的 `semis_peer_v1` 版本（11 个成分、权重和 = 1）。
- AC-02 日历：2026-11-26 `closed`；2026-11-27 与 2026-12-24 `early_close` 收盘 13:00 ET（与官方日历核对，覆盖表可改）；DST 切换日 UTC 偏移正确。
- AC-03 窗口：正常日 14:59:00 ET 发布 → `regular_60m` 可用；14:59:45 ET 不可用（`window_insufficient`）；15:44 ET 发布 → `regular_to_close` 可用（剩余 16 分钟）；15:46 ET 发布 → 不可用（剩余 < 15 分钟）；半日市 12:30 ET 发布 → 60m 不可用；周六发布 → `next_regular_session` 指向下周一。
- AC-04 合格报价：fixture 中宽价差、停牌、报价年龄 > 5s 的秒被判为不合格；起算取发布后首组"个股 + ≥10 个成分"时差 ≤ 2s 的报价；30s 内无 → 返回 `no_sync_start_quote`。
- AC-05 篮子收益：手算 3 组例子与函数输出误差 < 1e-9；缺 2 个成分 → `benchmark_unavailable`。
- `docs/data_procurement.md` 列出 D-13/D-15/D-16 每项：覆盖、时间精度、历史年限、延迟、授权展示范围、价格，标注 `已验证`/`拟选`。
- `examples/` 中 DATA_CONTRACT §8 示例（含 `regular_60m_move`）全部通过 schema；Brier 算例 = 0.5798；pinball 算例 p50/p80/p90 = 0.035/0.068/0.053。
- AC-26 波动缩放阈值：sigma_hat 0.60pp、k 0.25 → 阈值 0.15pp；相对 +0.24pp → `outperform`，+0.15pp（含阈值本身）→ `flat`；sigma 不可得 → `abstained/insufficient_data`；`locked` 含 `sigma_hat_pp/threshold_k/threshold_pp/sigma_model_version`。sigma 估计器只用发布时点之前的数据（负向测试：注入未来数据时报错）。
- AC-28（P0 部分）BSS：Brier 0.641 对参照 0.666 → BSS ≈ 0.0375；分块 bootstrap 在固定 seed 下可复现，且同一交易日的样本整块重采样。
- AC-52（P0 部分）`schedule_slots(date)`：2026-12-01 返回 6 个槽位（UTC 正确）；2026-11-27 半日市返回 08:30、10:00、11:30（含至收盘）、13:30，`s1300`/`s1430` 为 `not_scheduled`；2026-11-26 休市返回空；DST 切换前后 10:00 ET 对应的 UTC 不同。
- AC-29（P0 部分）fs-0.2 每个特征函数对合成 fixture 给出确定值，且只读取 `ts ≤ as_of` 的数据。

---

## Phase 1 · NVDA 60 分钟历史回放端到端

**目标**：在 NVDA 历史日上，从证据和行情 → 证券快照 → 预测 → 自动结算 → 逐条核验跑通；覆盖 **普通无新闻日、财报、突发政策** 三类场景；并完成**基础训练运行与指标记录**（Brief 要求首个可验证交付即含此项）。

| 工作项 | 依赖 | 预期文件 |
|---|---|---|
| P1-1 证据入库：SEC EDGAR + IR 适配器（回放读存档），内容哈希去重、四类时间 | P0-A | `sr/evidence/{sources/sec.py,sources/ir.py,ingest.py}` |
| P1-2 事件：归并、identity_key、版本、节点、乐观锁；财报提取（LLM 接口 + 确定性核对）；政策事件模板 | P1-1 | `sr/events/{merge.py,versions.py,earnings.py,policy.py}`、`sr/llm/{base.py,anthropic.py,fake.py}` |
| P1-3 市场反应与当前解释（含"新闻晚于下跌"时间顺序校验） | P0-C, P1-2 | `sr/events/reaction.py`、`sr/events/explain.py` |
| P1-4 证券快照（scheduled/event），同水位合并 | P1-3 | `sr/snapshot/builder.py` |
| P1-5 预测：历史频率基线 + 行情基线 `market_logit`；原子发布；不可变触发器 | P1-4, P1-7 | `sr/forecast/{features.py,run.py,publish.py}`、`supabase/migrations/0002_forecast.sql` |
| P1-6 结算：起算/结算报价、收益、类别、Brier、无法结算；版本追加 | P0-B/C | `sr/settle/settle.py` |
| P1-7 基础训练：数据集版本（含切分与 embargo）、训练、校准（isotonic/Platt）、指标写入 `training_run_metrics` | P0 | `sr/train/{dataset.py,train.py,calibrate.py}`、`sr/eval/metrics.py` |
| P1-8 回放 CLI 与逐条核验报告（HTML/Markdown） | 以上 | `sr/replay/{runner.py,report.py}`、`apps/web/app/(market)/replay/[prediction_id]/page.tsx`（最小版） |
| P1-9 预期波动目标 `regular_60m_move`：HAR 式基线 + 分位数模型（分位数回归或 GBDT quantile），与方向目标共享起算/结算报价 | P0-F, P1-6 | `sr/forecast/move.py`、`sr/train/models/har_vol.py` |
| P1-10 LLM 提取评估集：约 300 份标注文档、评估脚本、门槛（D-32） | P1-2 | `data/labels/extraction-v0/`、`sr/llm/eval_extraction.py` |
| P1-12 公司行为：`corporate_actions` 采集（行情商接口 + 8-K 核对）、研究库复权、跨除权日结算调整、比例未知 → `unsettleable/corporate_action`（D-40） | P0-I, P1-6 | `sr/marketdata/corporate_actions.py`、`sr/settle/adjust.py` |
| P1-13 历史类比检索 `hc-0.1`：匹配键、`min_cases=8`、逐级放宽、无自匹配、`case_ids` 锁定（DC §3.4a，D-38） | P1-2, P1-6 | `sr/events/analogues.py`、`config/analogues/hc-0.1.yaml` |
| P1-14 运行状态与有效期：快照 `run_state`、`quality_issues`、`last_valid_at`、`valid_until`；预测 `valid_until` 与派生 `display_state` 视图（D-41） | P1-4, P1-5 | `sr/snapshot/quality.py`、`supabase/migrations/0002b_validity_views.sql` |
| P1-15 估值背景：`valuation_context`（远期 PE 与 3 年分位、同行中位数），只进解释不进特征；无授权来源时为空 | P1-3 | `sr/events/valuation.py` |
| P1-16 场景测试：盘后 +8% 异动、盘后基准缺失、CEO 传闻 → 官方确认（AC-39～AC-41） | P1-3, P1-4 | `services/py/tests/scenarios/{after_hours_move,rumor_to_confirm}.py` |
| P1-17 每日预测时刻表与预测—实际对照（后端）：`forecast_schedules` seed `sched-0.1`；回放按槽位生成预测（`sampling_rule=schedule_slot`）；`forecast_vs_actual` 物化视图（展示路径 `sqrt_time_v1` + 实际分钟路径）与 `forecast_accuracy_rollups`；`slot_missed` 处理（D-43、D-44） | P1-5, P1-6 | `sr/schedule/{slots.py,runner.py}`、`sr/eval/{fva.py,rollups.py}`、`supabase/migrations/0005_schedule_fva.sql` |
| P1-18 采集记录与推理链：每次运行写 `collection_runs` / `collection_items`（含去重、排除、待核、抓取失败与原因）；渠道与类别分类器；`market_explanation` 引用校验（无引用 → 拒绝）；`reasoning_trace` 生成（确定性步骤 + LLM 起草步骤）（D-45、D-46） | P1-1, P1-2, P1-3 | `sr/evidence/collection_log.py`、`sr/evidence/classify.py`、`sr/events/{reasoning.py,citations.py}`、`supabase/migrations/0006_collection.sql` |
| P1-11 一键运行编排（后端 + CLI）：`pipeline_runs` / `pipeline_run_steps` 迁移；8 步编排、断点续跑、复用策略；`replay` 与 `dry_run` 模式 | P1-1～P1-6 | `sr/pipeline/{orchestrator.py,steps.py,reuse.py}`、`supabase/migrations/0003_pipeline.sql` |

**可并行**：P1-1/P1-2 与 P1-6/P1-7 两条线并行；P1-5 等 P1-7 至少产出一个模型版本。

**演示数据**：NVDA 三个历史日（需实际数据；无授权时用合成 fixture 并在报告标 `synthetic`）：①无新闻普通日；②财报日（盘后发布 → 次日 `next_regular_session` 起算只作标签示例，60m 预测取次日盘中）；③盘中政策文件日。

**验证命令**

```bash
uv run sr replay --security sec_nvda --date <plain_day>  --target regular_60m --mode archived
uv run sr replay --security sec_nvda --date <earnings_day> --target regular_60m --mode archived
uv run sr replay --security sec_nvda --date <policy_day>  --target regular_60m --mode simulated
uv run sr train --dataset-spec config/datasets/regular_60m_semis.yaml --family market_logit --seed 7
uv run sr report --replay-run <id> --out reports/
uv run pytest services/py/tests -q -k "replay or settle or train"
```

**验收标准**

- AC-06 每条证据有 `received_at`、`available_at`；`source_published_at` 缺失时有 `missing_reason`。
- AC-07 同一新闻重复投递 3 次 → 1 个 `source_document_versions`、0 个新分析版本。
- AC-08 两个并发任务更新同一事件，旧水位任务不能覆盖新版（测试用例）。
- AC-09 财报：GAAP 与 non-GAAP EPS 分字段；唯一共识快照晚于披露 → `expectation_comparison=null` 且 `missing_reason='no_pre_event_consensus'`。
- AC-10 个股 −1%、篮子 −3% → 显示绝对 −1%、相对 +2pp；新闻晚于下跌开始 → 解释中不得标为此前下跌的已证实原因。
- AC-11 无新闻日每 5 分钟生成快照，`event_analysis_ids=[]`、`new_catalyst_found=false`。
- AC-12 政策日：事件增强模型未验证 → `allowed_models=['market_baseline']`。
- AC-27 每条 `regular_60m` 预测同时生成 `regular_60m_move` 预测（同 snapshot、同起算报价）；结算写 `abs_relative_move_pp`、`pinball_loss`、`quantile_hits`；训练指标含 `pinball_loss` 与 `interval_coverage`（对 `har_vol` 参照）。
- AC-30 `extraction_eval_runs` 至少 1 次运行；未达 D-32 门槛的 `prompt_version` 被特征构建拒绝（负向测试）。
- AC-34（P1 部分）`uv run sr run --security sec_nvda --targets regular_60m,regular_60m_move --mode replay --as-of <ts>` 走完 8 步并生成与逐步回放一致的结果；`--mode dry_run` 不写 `predictions`。
- AC-37 公司行为：fixture 中 10:1 拆股在 `ex_date` 生效 → `reference_quotes` 保留原始价；跨除权日的 `next_regular_session` 结算按比例调整后与手算一致；比例字段为空 → `unsettleable/corporate_action`；`ticker_change` 后旧代码按时点仍可解析。
- AC-38 历史类比：财报事件在 ≥ 8 个同类过去案例时输出 n、期间、中位数、四分位距与 `fallback_level=none`；只有 5 个时逐级放宽并记录级别；放宽到 `sector_wide` 仍不足 → `insufficient=true` 且界面不显示中位数；候选案例中 `available_at` 晚于 `analysis_as_of` 或属于同一事件链的被排除（负向测试）。
- AC-39 盘后 +8%：16:20 ET 发布财报、个股盘后 +8% → 生成 `trigger_type=market_move`、`market_state=post_market` 的快照与分析；**不**发布 `regular_60m`（D-28）；`next_regular_session` 起算不早于次日 09:31:00 ET（D-10）。
- AC-40 盘后篮子成分报价不足（> 1 只缺失）→ `day_relative_pp = null`、界面显示"盘后基准不可计算"，绝对涨跌仍显示。
- AC-41 CEO 变动：媒体传闻（`verification_status=media_report`）→ 分析版本 1 标"未经证实"；公司 8-K 确认 → 分析版本 2，`supersedes_analysis_id` 指向版本 1，证据状态升为 `primary_confirmed`；两版都可回放，旧版不被覆盖。
- AC-42 估值背景：有来源时 `valuation_context` 字段齐全并显示 `as_of`；无来源时为空且界面不显示该行；特征构建读取该字段时报错（负向测试，确保不进模型）。
- AC-49（P1 部分）每个快照有 `run_state` 与 `valid_until`；当前快照 `data_quality≠ok` 时 `last_valid_at` 指向最近一次 ok；`display_state` 视图对被修订、过期、已结算预测分别返回 `superseded`、`expired`、`settled`。
- AC-52 时刻表回放：NVDA 一个正常日回放产生 08:30、10:00、11:30、13:00、14:30、16:30 六个槽位预测（14:30 含至收盘，共 4 个 `regular_60m`），全部 `is_primary=true`；同日事件触发预测 `is_primary` 按事件规则、5 分钟预测 `is_primary=false`；故意让 11:30 槽位延迟 200s → `abstained/slot_missed`，不补发；半日市回放只产生 D-43 规定的槽位。
- AC-53 对照视图：任一已结算槽位预测，`forecast_vs_actual.forecast_path` 终点等于锁定分位数，`actual_path` 终点等于结算 `relative_return_pp`（误差 < 1e-9）；`residual_pp`、`inside_p80` 与手算一致；`actual_path` 不含 `available_at > now` 的点；`forecast_accuracy_rollups` 的 n 与结算表计数一致，n < 30 时标样本不足；重算视图不改变任何 `predictions` 行（只读测试）。
- AC-56 采集记录：政策日 NVDA 11:30 运行的 `collection_items` 覆盖本次检索的每一条（含同一快讯的 3 次转载 → 1 条 `kept` + 2 条 `duplicate`；11:31 才可用的文档 → `excluded_after_asof`；受限材料 → `excluded_restricted`）；`counts` 与条目逐项汇总一致；按渠道 × 类别的计数可由 API 重现；回放同一时点得到相同条目集。
- AC-57 推理链：`market_explanation` 中每条已观察事实、可能驱动、反向证据至少引用 1 个证据或报价；人为去掉引用的陈述被校验拒绝并移入"未解释"；`reasoning_trace` 的时间对齐步骤在"新闻晚于下跌开始"时给出"不能作为此前下跌原因"（对应 AC-10）；引用的每个 ID 都能在 `collection_items` 或 `reference_quotes` 找到。
- AC-13 每条预测 `published_at < t0 quote_ts`；`locked` 七个版本字段非空；发布后更新 `probabilities` 被数据库拒绝。
- AC-14 结算可重复运行 3 次结果一致（幂等）；手算 5 条结算与系统一致。
- AC-15 停牌窗口内的预测 → `unsettleable/halted`，计入质量报表，不计入命中率分母。
- AC-16 至少 1 次 `training_runs.status=completed`，`training_run_metrics` 含 train/calibration/validation 的 `brier`、`brier_skill_score`（对 `class_frequency`、`always_flat`、`persistence` 三条参照各一行，带分块 bootstrap `ci95_low/high`）、`hit_rate`、`coverage`、`n_effective`（按交易日计）；同模型同 seed 重跑指标一致；回放中任一读取 `available_at > T` 时任务失败（负向测试）。
- 逐条核验报告：任取一条预测能列出锁定输入、起算/结算报价、收益、类别与结算理由。

---

## Phase 2 · 首批四家 + 实时定期与事件触发

**目标**：扩展到 NVDA、AMD、AVGO、MU；实时行情常驻、定时 5 分钟、事件与异动触发；记录数据缺失与弃预测；用户页面上线（内部）。

| 工作项 | 依赖 | 预期文件 |
|---|---|---|
| P2-1 实时 `md-ingest`（供应商适配器、1 秒层、Parquet 刷写、延迟指标） | P0-D 选定供应商 | `sr/marketdata/live.py`、`sr/marketdata/providers/<vendor>.py` |
| P2-2 scheduler 与 jobs 队列消费者（SKIP LOCKED、退避、死信） | P1 | `sr/jobs/{queue.py,worker.py,scheduler.py}` |
| P2-3 异动触发规则（价格/成交量/相对行业阈值，版本化） | P2-1 | `config/market_move_rules.yaml` |
| P2-4 四家公司档案与敞口配置；同一事件多公司独立影响 | P1-2 | `supabase/seed/0002_profiles.sql` |
| P2-5 弃预测与缺失：质量报表（按原因分布） | P1-5/6 | `sr/eval/quality_report.py` |
| P2-6 Next.js 市场页面：监控、详情、预测、事件、回放；Realtime 订阅；按需刷新入队 | P0-A | `apps/web/app/(market)/**` |
| P2-7 运行监控：从一手数据到快报/完整分析时延的 p50/p95，来源超时告警 | P2-2 | `sr/ops/latency.py` |
| P2-8 一键运行页面：股票详情"运行"按钮、运营页运行面板（选证券/目标/模式）、Realtime 步骤进度、取消、运行历史 | P1-11, P2-6 | `apps/web/app/ops/run/**`、`apps/web/app/api/pipeline-runs/**` |
| P2-9 新公司接入 1–5 阶段：代码解析、LLM 起草公司档案（带原文定位）+ 人工审核、来源与篮子配置、历史回填、数据校验报告、checklist 推进/阻塞/豁免 | P2-1, P1-2 | `sr/onboarding/{resolve.py,profile_draft.py,backfill.py,validate.py}`、`apps/web/app/ops/onboarding/**`、`supabase/migrations/0004_onboarding.sql` |
| P2-10 数据源健康与告警：健康检查任务、`data_source_health`、`alerts`、通知（邮件或 Slack Webhook，可配置）、告警确认 | P2-2 | `sr/ops/{health.py,alerts.py,notify.py}`、`apps/web/app/ops/{sources,jobs}/**` |
| P2-11 部署与环境：staging/prod Supabase 项目、worker 容器镜像、Next.js 部署、迁移流水线、每日数据库备份与 Parquet 备份校验 | P0-H | `infra/{docker/worker.Dockerfile,deploy.md}`、`.github/workflows/deploy.yml` |
| P2-13 事件结果结算：`outcome_resolution`、`no_result_rule`、公开确认时间与法律生效时间分记、官方来源冲突 → `manual_review`（D-39） | P1-6, P1-2 | `sr/settle/event_outcome.py` |
| P2-14 条件预测：`condition`（触发结果 + 截止）、触发后首个同步合格报价起算、`not_triggered`、`trigger_rate` 指标 | P2-13 | `sr/forecast/conditional.py`、`sr/settle/conditional.py` |
| P2-15 新来源适配器：`MacroProvider`（官方发布 + FRED/ALFRED vintage 首发值）、`DocketSource`（CourtListener/RECAP，关键案件 PACER）、`InsiderFilingSource`（EDGAR Form 4）、预期修正链 `revision_of_exp_id` | P1-1 | `sr/evidence/sources/{macro.py,courts.py,form4.py}`、`sr/expectations/revisions.py` |
| P2-16 数据质量与有效期界面：监控页与详情页显示 `run_state`、问题列表、"最近有效"时间、"已过期"与"已被替代"状态 | P1-14, P2-6 | `apps/web/components/{QualityBadge,ValidityTag}.tsx` |
| P2-17 行业模板：`industry_templates`（semiconductor / bank / biotech / generic）、接入时选择模板、同一政策事件按模板分别解读；银行与生物医药各配 1 家**测试公司**（只进测试，不进首版名单） | P2-4, P2-9 | `config/industry_templates/*.yaml`、`sr/events/exposure.py` |
| P2-18 时刻表实时运行与"预测与实际"界面：调度器按 `sched-0.1` 在槽位时刻入队完整流水线（提前 2 分钟预热数据）；股票详情新增"预测与实际"卡片（两条曲线叠加：预测中位路径 + p10–p90 区间 vs 实际路径；当日/20 日/上线以来准确率与样本数）；预测页标注槽位 | P1-17, P2-2, P2-6 | `sr/schedule/live.py`、`apps/web/components/ForecastVsActual.tsx`、`apps/web/app/(market)/stock/[ticker]/page.tsx` |
| P2-19 股票详情三步视图：顶部运行三步条（① 采集计数 → ② 推理结论 → ③ 本槽位预测，链接到 `pipeline_run_steps`）；① 信息采集页（渠道 × 类别矩阵、筛选、搜索、分页长列表、处置原因、四类时间）；② 分析与推理页（推理链 + 引用跳转高亮） | P1-18, P2-6 | `apps/web/app/(market)/stock/[ticker]/{collect,reasoning}/page.tsx`、`apps/web/components/{RunStepper,CollectionMatrix,ReasoningTrace}.tsx` |
| P2-20 用户补充信息：提交接口（链接/文本/文件，病毒扫描）、类别建议（规则 + LLM，多类别）、核验流水线（链接可达、来源信誉、原始来源追溯、内容与时间一致、查重、未公开材料筛查）、状态推送；"系统漏采"记录（D-47） | P1-18, P2-2 | `sr/submissions/{intake.py,classify.py,verify.py}`、`apps/web/app/api/securities/[id]/submissions/route.ts`、`supabase/migrations/0007_submissions.sql` |
| P2-21 增量补充运行 `mode=supplement`：复用 `base_run_id` 采集结果、行情快速刷新、增量检索、重跑分析/快照/推断/发布，新版本并排对比；`user_supplement` 单独计分；可见范围与限流（D-48） | P1-11, P2-20 | `sr/pipeline/supplement.py` |
| P2-22 界面："＋ 添加信息"表单、核验进度与结果、"继续分析 →"按钮、补充前/补充后对比 | P2-19, P2-21 | `apps/web/components/{AddInfoDialog,SubmissionStatus,SupplementCompare}.tsx` |
| P2-12 运维手册（附录 B）初版与一次演练：来源中断、行情陈旧、结算积压、worker 崩溃恢复 | P2-10, P2-11 | `docs/runbooks/*.md` |

**并行**：P2-1/P2-3 ∥ P2-4 ∥ P2-6/P2-8（前端可先用 contracts examples）∥ P2-9 ∥ P2-10/P2-11。

**验证命令**：`uv run sr live --symbols NVDA,AMD,AVGO,MU --dry-run`；`uv run sr worker`；`pnpm --filter web dev` + `pnpm --filter web test:e2e`（Playwright，`--trace off`）。

**验收标准**

- AC-17 一个完整交易日四家各产生 ≥ 70 条定时快照（09:35–15:55 每 5 分钟），事件触发在 `available_at` 后 p95 ≤ 60s 产生快照。
- AC-18 行情中断 2 分钟 → 快照 `data_quality='stale'`，预测 `abstained/stale_quote`；质量报表显示原因计数。
- 单一供应商消息（如仅指向 AMD 的订单）→ NVDA 与 AMD 生成不同影响记录。
- 用户页面五类状态（正常、加载、空、超时、失败）有 e2e 截图测试。
- AC-32 接入 TSM 到 `data_validated`：回填报告字段齐全；任一指标低于 D-35 门槛时阶段为 `blocked` 并显示原因；`admin` 豁免会写审计记录。
- AC-34 点击"运行"（NVDA，`regular_60m` + `regular_60m_move`）：8 个步骤全部写入 `pipeline_run_steps`；输入无变化时 `outputs.reused=true` 且不产生新预测；有新证据时产生新快照与预测，`published_at < t0 quote_ts`。
- AC-35 同一用户 1 分钟内连点 3 次 → 同一 `pipeline_run_id`；某步骤注入失败 → 自动重试后成功，或标 `partial` 并保留已发布部分；按需预测 `sampling_rule='on_demand'` 不进入主评分。live 单只 p95 ≤ 90s（不含等待起算报价）。
- AC-43 事件结果结算：并购事件截止前公司 8-K 宣布交割 → `closing_confirmed`，`public_confirmation_at` 与 `legal_effective_at` 分别记录；截止前无任何解决里程碑 → `no_confirmation`（非 `unsettleable`）；两个官方来源冲突 → `manual_review`，不自动结算。
- AC-44 监管批准 ≠ 交割：只出现 `regulatory_clearance` 里程碑时，问题"截止前完成交割"不得结算为 `closing_confirmed`；界面把"已获批准"与"已完成交割"显示为两个独立里程碑。
- AC-45 条件预测"若交割终止，则至收盘相对表现"：条件未出现 → 截止后 `not_triggered`，不计入命中率分母，`trigger_rate` 计 0/1；条件出现 → 状态 `awaiting_trigger → awaiting_settlement`，起算为触发后首个同步合格报价。
- AC-46 宏观首发值：回放 CPI 发布日时，特征读取的是当时首发值（ALFRED vintage），而不是后来修订值；修订值另存新行；读取 `available_at > T` 的 vintage 时报错。
- AC-47 法院案卷：对一个测试案件轮询 → 新 `docket_entries` 去重入库；`order`/`verdict` 生成里程碑候选，需人工确认后才写入 `event_milestones`；来源不可达时记录 `source_down` 而不是"无新进展"。
- AC-48 Form 4：P/S 且非 10b5-1 的交易进入证据与特征；A/M/F 只展示；`filed_at` 用 EDGAR 接收时间。预期修正：同一 metric/period 的新快照通过 `revision_of_exp_id` 串成链，可按时点取回当时版本。
- AC-49（P2 部分）行情中断 → 监控页对应卡片显示"数据质量：陈旧"与"最近有效 hh:mm ET"；超过 `valid_until` 的快照标"已过期"；被修订的预测灰显并链接新版（e2e 截图）。
- AC-50 跨行业：同一出口管制政策事件 → 芯片公司（semiconductor 模板）生成"收入敞口"影响记录；银行测试公司（bank 模板）生成"无直接敞口"记录；两者影响方向与说明独立，且银行测试公司不出现在首版名单与评分中。
- AC-54 实时一个完整交易日：四家各在 6 个槽位按时发布（发布时刻 p95 ≤ 槽位 + 90s），未按时的记 `slot_missed` 并告警；10:00 槽位结算后，11:30 运行时股票详情"预测与实际"卡片显示 10:00 预测的两条曲线、结算结果与更新后的当日准确率；图表有表格视图（无障碍）与 e2e 截图测试。
- AC-58 界面：股票详情顶部三步条显示与 `collection_runs.counts` 一致的数字；在 ① 页按渠道、类别、处置状态筛选后条目数与矩阵一致；点击 ② 页任一引用跳到对应条目并高亮；受限条目只显示占位；e2e 覆盖 500 条以上的长列表分页与 390px 手机宽度。
- AC-59 提交与分类：提交一个链接并只选"客户需求"→ 系统建议追加"供应链"（置信度 ≥ 0.6）并写入 `final_categories`；提交纯文本无链接 → 状态 `unverified`；提交与已有条目内容哈希相同 → `duplicate` 且 `duplicate_of_item_id` 正确；同一用户重复提交同一 URL → 返回原 `submission_id`。
- AC-60 核验：媒体链接能追溯到公司 8-K → `verified_primary`，`origin_published_at` 早于本次运行且系统未采集 → `missed_by_system=true`；链接 404 → `fetch_failed`；疑似未公开材料 → `rejected_restricted`，不可继续分析；用户条目 `available_at` = 提交时间（回放中提交前不可见）。
- AC-61 继续分析：点击后 `pipeline_runs.mode=supplement`，不重新检索已覆盖的来源（请求日志验证），p95 ≤ 30s；生成新分析版本（`supersedes_analysis_id` 指向原版）与新预测（`sampling_rule=user_supplement`、`is_primary=false`），原版本与槽位预测不变；`unverified` 条目只出现在推理缺口中，不进入特征；结果在核验通过前只对提交者与研究员可见；2 分钟内重复点击返回同一运行。
- AC-36 停掉一个来源 5 分钟 → `warning` 告警；15 分钟 → `critical`；恢复后自动关闭；告警可确认并留痕。

---

## Phase 3 · 训练后台、同批对照与实时影子测试

**目标**：完善研发后台；在同一批样本上比较行情基线 vs 事件增强；验证行业与公司参数增量；实时影子测试；审批与回滚演练。

| 工作项 | 预期文件 |
|---|---|
| P3-1 数据快照对比（新增/删除/更正/过滤） | `sr/train/dataset_diff.py`、`apps/web/app/admin/datasets/**` |
| P3-2 `market_event_logit` 候选；三层参数（market / +sector / +company，正则化收缩） | `sr/train/models/{market_event.py,hierarchical.py}` |
| P3-3 评估：共同覆盖集合、配对差异、按交易日/事件簇 bootstrap CI、校准图、混淆矩阵、分组拆解；`regular_60m_move` 的 `interval_width`（p80/p90 平均宽度）与覆盖率同表报告 | `sr/eval/{compare.py,bootstrap.py,calibration.py}` |
| P3-4 影子运行：候选与线上同点同窗并行、锁定后评分 | `sr/forecast/shadow.py` |
| P3-5 门槛 `gate_config`（D-21）与审批、部署、回滚 API 与页面 | `config/gates/gate-0.1.yaml`、`apps/web/app/admin/{runs,models,evaluations,approvals}/**` |
| P3-6 内部可见层级：`model_deployments.audience` 与切片、各层级门槛（MP §12，D-33）、内部邀请制账号 | `config/gates/audience-0.1.yaml`、`supabase/migrations/000x_audience.sql` |
| P3-8 研发后台"预测对照"页：按槽位/证券/行情状态的命中率、Brier、BSS、区间覆盖与宽度、残差均值；按槽位校准曲线；大误差复盘队列（区间外预测）；漂移检查（近 20 日 vs 参照，分块 bootstrap）→ `drift` 告警与训练复盘入口（MP §7.1） | `sr/eval/{residuals.py,drift.py}`、`apps/web/app/admin/fva/**` |
| P3-7 新公司接入 6–8 阶段：自动加入训练池（`market_sector_only`）、影子运行、按公司出成绩、审批上线；用 TSM、MRVL 走完全流程 | `sr/onboarding/{train_stage.py,shadow_stage.py}`、`apps/web/app/ops/onboarding/[id]/**` |

**验收标准**

- AC-19 S3§8.4 虚构判例（200 / 180 / 100）作为测试：评估输出 `gate_result='fail'` 且列出覆盖率下降条件。
- AC-20 影子预测在窗口结束前不可见于评分表；影子 ≥ 20 个交易日后才可提交审批。
- AC-21 公司参数训练期改善、留出期退化 → 审批条件不通过，部署保持旧版。
- AC-22 上线后人为注入退化 → 回滚成功；已发预测仍引用原 `model_version_id`。
- AC-31 `audience=selected_v1` 的用户只能读取证据、解释、情景与 `regular_60m_move`；方向概率在未通过的切片上对其不可见（RLS 测试）。
- AC-33 TSM 从 `training` 走到 `active`：模型使用 `market_sector_only`；公司偏移未通过时不启用；影子 ≥ 20 个交易日前无法提交审批；上线后出现在公司监控页。
- 两家公司相隔数分钟受同一宏观冲击 → 评估 `n_event_clusters` 只计 1。
- AC-55 预测对照闭环：fixture 中人为让 10:00 槽位概率系统性偏高 → 后台按槽位校准曲线显示偏离、残差分组突出 `s1000`；近 20 日 Brier 恶化且 CI 不含 0 → `drift` 告警；由此重拟合的校准只能作为新 `calibration_version` 进入影子，不得直接替换线上；已发布预测与结算不变（负向测试）。
- AC-28（P3 扩展）验证总览对 `regular_60m_move` 同时显示 `interval_coverage` 与 `interval_width`；覆盖率达标但宽度高于 `har_vol` 参照 20% 以上时标"区间过宽"。

---

## Phase 4+ · 后续阶段

- AC-24 `regular_to_close`、`next_regular_session` 独立标签、训练与评估，达标后逐项开放；`overnight_gap` 可选目标并标注"跳空非可执行收益"。
- 经验证的预测区间（分位数覆盖率与宽度）、15/30/45/60 分钟多点曲线。
- AC-23 待决事件子类数值概率（同类、同阶段历史发生率基线）；条件情景独立计分。
- 第二批 TSM、MRVL；银行、生技行业配置；延长时段预测；1–5 日窗口（S1，并入 `roadmap/ROADMAP_EXTENSIONS_CN.md` Phase 5）。
- AC-25 合规：`restricted_review` 证据不进入公开 API 与特征（P1 起即测试）。
- AC-51 期权（来源验证后）：`OptionsProvider` 样本验证通过（`verification_status=sample_verified`）前，任何模型特征读取 `options_snapshots` 时报错；通过后只作为 `regular_60m_move` 与财报事件的候选特征，按 D-21 同口径对照后决定是否启用。

---

## 附录 A · 工作分解（WBS）与估算

估算单位：人日（含测试与评审）。"依赖"为必须先完成的任务；同一阶段内无依赖关系的任务可并行。估算为粗估，Phase 0 结束时按实际速度校准一次。

### Phase 0（约 26 人日）

| ID | 任务 | 线 | 人日 | 依赖 |
|---|---|---|---|---|
| 0.01 | monorepo 骨架、pnpm workspace、uv 项目、Makefile | T6 | 1 | — |
| 0.02 | CI：lint、类型、pytest、契约校验、迁移重放；pre-commit | T6 | 1.5 | 0.01 |
| 0.03 | JSON Schema（P0/P1 实体，contract-0.4）+ 生成 TS/pydantic | T3 | 3 | 0.01 |
| 0.04 | 迁移 0001_core：表、枚举、约束、不可变触发器、jobs 表 | T3 | 2 | 0.03 |
| 0.05 | seed：pilot/batch2/peer/reference、篮子 v1、目标定义 td-0.2 | T1 | 1 | 0.04 |
| 0.06 | 交易日历 + 覆盖表 + 窗口可用性 | T3 | 2 | 0.01 |
| 0.07 | 合格报价规则 qr-0.1 | T1 | 1.5 | 0.01 |
| 0.08 | 同步报价查找 + 篮子收益 + 缺失规则 | T1 | 1.5 | 0.07 |
| 0.09 | sigma-0.1 + 波动缩放阈值 | T4 | 1.5 | 0.08 |
| 0.10 | 评分：Brier、BSS、pinball、分块 bootstrap | T4 | 1.5 | 0.01 |
| 0.11 | fs-0.2 特征纯函数 + 测试 | T4 | 2 | 0.08 |
| 0.12 | 合成 fixture 生成器 + 样本验证脚本 | T1 | 1.5 | 0.07 |
| 0.13 | 数据采购对比模板 + 供应商样本验证（真实样本到手后补跑） | T1 | 2 | 0.12 |
| 0.14 | decisions.yaml（D-01～D-48）、OPEN_QUESTIONS、CHANGELOG | T6 | 0.5 | — |
| 0.17 | `forecast_schedules` schema + seed `sched-0.1` + `schedule_slots(date)`（半日市、休市、DST） | T3 | 1 | 0.06 |
| 0.16 | contract-0.4 新增 P0/P1 实体（公司行为、行业模板、有效期字段）Schema + 迁移 + seed | T3 | 1 | 0.04 |
| 0.15 | Phase 0 验收演示与速度校准 | — | 0.5 | 全部 |

### Phase 1（约 76.5 人日）

| ID | 任务 | 线 | 人日 | 依赖 |
|---|---|---|---|---|
| 1.01 | MarketDataProvider 历史实现（选定供应商）+ Parquet 1 秒层 | T1 | 4 | 0.13 |
| 1.02 | NVDA 与篮子历史回填（3 个场景日 + 训练窗口） | T1 | 3 | 1.01 |
| 1.03 | EvidenceSource：SEC EDGAR、IR RSS（存档读取）| T1 | 3 | 0.04 |
| 1.04 | 文档版本、哈希去重、四类时间、受限复核 | T2 | 2 | 1.03 |
| 1.05 | LLMProvider 接口 + fake 实现 + Claude 实现，调用留痕 | T2 | 2 | 0.01 |
| 1.06 | 事件归并、identity_key、节点、乐观锁、版本 | T2 | 4 | 1.04 |
| 1.07 | 财报提取 + 确定性核对 + 预期对比 | T2 | 4 | 1.05, 1.06 |
| 1.08 | 政策事件模板 | T2 | 2 | 1.06 |
| 1.09 | 市场反应 + 当前解释 + 时间顺序校验 | T2 | 3 | 0.08, 1.06 |
| 1.10 | 证券快照（scheduled/event）+ 同水位合并 | T3 | 2 | 1.09 |
| 1.11 | 数据集构建（切分、embargo、事件簇、排除统计） | T4 | 4 | 1.02, 0.11 |
| 1.12 | 训练：频率/恒平盘/持续性基线 + market_logit + 校准 | T4 | 4 | 1.11 |
| 1.13 | HAR 波动基线 + 分位数模型（regular_60m_move） | T4 | 3 | 1.11 |
| 1.14 | 推断、原子发布、不可变约束 | T3 | 3 | 1.10, 1.12 |
| 1.15 | 结算（方向 + 波动目标）、幂等、版本追加 | T3 | 3 | 0.08, 1.14 |
| 1.16 | 一键运行编排 + CLI（replay/dry_run） | T3 | 4 | 1.10, 1.14, 1.15 |
| 1.17 | 回放报告（逐条核验） | T3 | 2 | 1.16 |
| 1.18 | LLM 提取评估集（标注约 300 份 + 脚本） | T2 | 4 | 1.07 |
| 1.19 | 最小回放网页（只读） | T5 | 2 | 1.17 |
| 1.21 | 公司行为采集、复权、结算调整 | T1/T3 | 2 | 1.02, 1.15 |
| 1.22 | 历史类比检索 hc-0.1 | T2 | 3 | 1.06, 1.15 |
| 1.23 | 运行状态、有效期字段与 display_state 视图 | T3 | 1.5 | 1.10, 1.14 |
| 1.24 | 估值背景（只进解释） | T2 | 1 | 1.09 |
| 1.25 | 场景测试：盘后 +8%、盘后基准缺失、传闻→确认 | T2/T3 | 2 | 1.09, 1.10 |
| 1.26 | 时刻表回放 + `forecast_vs_actual` 视图 + 准确率滚动统计 | T3/T4 | 3 | 1.14, 1.15, 0.17 |
| 1.27 | 采集记录 `collection_runs/items` + 渠道/类别分类 + 处置原因 | T1/T2 | 2.5 | 1.04 |
| 1.28 | 推理链 `reasoning_trace` + 陈述引用校验 | T2 | 2.5 | 1.09, 1.27 |
| 1.20 | Phase 1 验收（AC-06～AC-16、AC-27、AC-30、AC-34 P1 部分、AC-37～AC-42、AC-49 P1 部分、AC-52、AC-53、AC-56、AC-57） | — | 1 | 全部 |

### Phase 2（约 90.5 人日）

| ID | 任务 | 线 | 人日 | 依赖 |
|---|---|---|---|---|
| 2.01 | 实时行情 md-ingest + 延迟指标 | T1 | 5 | 1.01 |
| 2.02 | jobs 队列 worker、调度器、退避、死信 | T6 | 3 | 0.04 |
| 2.03 | 异动触发规则 | T3 | 2 | 2.01 |
| 2.04 | 实时证据采集（SEC 实时、IR、政策源、授权新闻） | T1 | 4 | 1.03 |
| 2.05 | AMD/AVGO/MU 档案与敞口、多公司独立影响 | T2 | 3 | 1.06 |
| 2.06 | 质量报表（弃预测与无法结算原因） | T4 | 2 | 1.15 |
| 2.07 | 网页：监控、详情、预测、事件、回放；Auth/RLS；Realtime | T5 | 8 | 1.19 |
| 2.08 | 一键运行页面 + 运行历史 + 取消 | T5 | 3 | 1.16, 2.07 |
| 2.09 | 接入 1–2：代码解析、LLM 起草档案 + 审核页面 | T2/T5 | 4 | 1.05 |
| 2.10 | 接入 3–5：来源/篮子配置、回填任务、校验报告、checklist | T1/T5 | 5 | 2.09, 1.02 |
| 2.11 | 数据源健康、告警、通知、确认 | T6 | 3 | 2.02 |
| 2.12 | 运营页面：数据源、任务队列、告警 | T5 | 3 | 2.11 |
| 2.13 | 部署：staging/prod、容器、迁移流水线、备份 | T6 | 4 | 0.02 |
| 2.14 | 运维手册 + 故障演练 | T6 | 2 | 2.11, 2.13 |
| 2.15 | e2e 测试（五类状态、一键运行、接入） | T5 | 3 | 2.07～2.12 |
| 2.17 | 事件结果结算（公开确认/法律生效、无结果、冲突） | T3 | 3 | 1.15 |
| 2.18 | 条件预测（触发、起算、not_triggered、trigger_rate） | T3/T4 | 2.5 | 2.17 |
| 2.19 | 宏观适配器 + ALFRED 首发值回填 | T1 | 2 | 1.03 |
| 2.20 | 法院案卷适配器 + 里程碑候选审核 | T1/T2 | 2.5 | 1.06 |
| 2.21 | Form 4 适配器 + 预期修正链 | T1 | 2 | 1.03, 1.07 |
| 2.22 | 数据质量、有效期、被替代/过期界面 | T5 | 2 | 1.23, 2.07 |
| 2.23 | 行业模板 + 银行/生物医药测试公司 + 跨行业政策测试 | T2 | 3 | 2.05, 2.09 |
| 2.24 | 时刻表实时调度、预热、slot_missed 告警 | T6 | 2 | 2.02, 1.26 |
| 2.25 | 股票详情"预测与实际"卡片（两条曲线 + 准确率）+ e2e | T5 | 3 | 2.07, 1.26 |
| 2.26 | 股票详情三步条 + ① 信息采集页 + ② 分析与推理页 + e2e | T5 | 4 | 2.07, 1.28 |
| 2.27 | 用户补充：提交、类别建议、核验流水线 | T1/T2 | 4 | 1.27, 2.02 |
| 2.28 | 增量补充运行 + 版本对比 + 单独计分 + 限流 | T3 | 2.5 | 1.16, 2.27 |
| 2.29 | 添加信息表单、核验进度、继续分析按钮、补充前后对比 + e2e | T5 | 3 | 2.26, 2.28 |
| 2.16 | Phase 2 验收（AC-17、AC-18、AC-32、AC-34～AC-36、AC-43～AC-50、AC-54、AC-58～AC-61） | — | 1 | 全部 |

### Phase 3（约 48.5 人日）

| ID | 任务 | 线 | 人日 | 依赖 |
|---|---|---|---|---|
| 3.01 | 数据快照对比（后端 + 页面） | T4/T5 | 3 | 1.11 |
| 3.02 | market_event_logit 候选 + GBDT 对照 | T4 | 4 | 1.12 |
| 3.03 | 三层参数（市场/行业/公司）+ 消融 | T4 | 4 | 3.02 |
| 3.04 | 评估：共同覆盖、配对差、bootstrap、校准、混淆矩阵、分组、`interval_width` | T4 | 4.5 | 0.10 |
| 3.05 | 影子运行 + 锁定后评分 | T4 | 3 | 1.14 |
| 3.06 | 门槛 gate_config、审批、部署、回滚（后端 + 页面） | T4/T5 | 4 | 3.04 |
| 3.07 | 研发后台页面：任务、指标曲线、参数对比、验证总览、影子 | T5 | 6 | 3.01～3.06 |
| 3.08 | 接入 6–8：训练池、影子、审批联动 | T4 | 3 | 2.10, 3.05, 3.06 |
| 3.09 | TSM、MRVL 走完接入 | T1/T4 | 3 | 3.08 |
| 3.10 | 分步开放：audience、切片、邀请制账号、RLS 测试 | T7 | 3 | 3.06 |
| 3.11 | 错误复盘队列与标记（MEMO E-6） | T5 | 2 | 2.07 |
| 3.12 | 漂移监控与滚动再校准 | T4 | 2 | 1.12 |
| 3.13 | 审计日志与合规检查（受限内容、授权展示） | T7 | 2 | 2.07 |
| 3.15 | 研发后台"预测对照"：分组准确率、校准、残差、复盘队列、漂移触发 | T4/T5 | 3 | 1.26, 3.04 |
| 3.14 | Phase 3 验收（AC-19～AC-22、AC-28 P3 扩展、AC-31、AC-33、AC-55） | — | 1 | 全部 |

**合计**：Phase 0～3 约 26 + 76.5 + 90.5 + 48.5 = **241.5 人日**（0.3 版约 183；0.4 加 PPT 蓝图缺口约 28；0.5 加时刻表与预测—实际对照约 12；0.6 加采集与推理可见约 9；0.7 加用户补充信息与增量补充运行约 9.5）。Phase 4 的期权与其他目标另行估算。

## 附录 B · 运维手册清单（`docs/runbooks/`）

| 手册 | 触发 | 首要动作 |
|---|---|---|
| 行情源中断 | `source_down` / `quote_stale` | 确认供应商状态；快照自动标 `stale`、预测自动弃；恢复后检查补数与结算积压 |
| 新闻/公告源延迟 | `source_latency` | 检查轮询任务与限流；必要时切备用来源；记录受影响时段（训练时排除） |
| 结算积压 | `settlement_backlog` | 检查 settler 与报价到达；幂等重跑 `sr settle --now`；不得手改结算记录 |
| worker 崩溃或卡死 | 任务锁超时 | 锁 5 分钟自动回收；查看 `last_error`；必要时把死信任务重新入队 |
| 一键运行失败率升高 | `pipeline_failed` | 按步骤定位；LLM 提供商故障时切 fake/备用或只发布行情基线 |
| 模型退化 | `gate_regression` / `drift` | `reviewer` 回滚到上一个 `live` 版本；开训练复盘 |
| 来源更正 / 行情更正 | 人工或自动发现 | 生成新版本；核对受影响结算的 `settlement_version` 与报表口径 |
| 疑似泄露材料 | `restricted_review` | 暂停使用与转发，交合规；从特征与公开界面排除 |
| 新公司接入受阻 | `onboarding_blocked` | 查看 checklist 失败项：补数据、降级为 `peer_only`，或 `admin` 豁免并留痕 |
| 公司行为未入库 | 结算出现 `corporate_action` 或价格跳变 > 30% | 核对 8-K/IR 与行情商公告；补 `corporate_actions` 后重跑受影响结算（追加 `settlement_version`） |
| 数据库/Parquet 恢复 | 演练或事故 | 每日备份；每月一次恢复演练并记录用时 |

## 附录 C · 后续阶段 Claude Code 指令模板

每个阶段开始时，把对应模板连同"上一阶段验收结果"和 `OPEN_QUESTIONS.md` 一起交给 Claude Code。每阶段可再按附录 A 拆成 2–4 次会话（每次 5–10 个任务）。

**Phase 1 模板**
```text
阅读 docs/ 下 MP / DC / DP（plan-0.7 / contract-0.7 / phases-0.7）与上一阶段验收结果。本轮实现 DP「Phase 1」中附录 A 的 1.01～1.10
（数据与分析线）。不实现训练、推断、页面。字段与枚举严格按 DC；新增字段先改 DC 与 JSON Schema 并升 schema_version。
验收：AC-06～AC-12 与 AC-30 的数据部分；回放读取 available_at > T 必须报错。输出变更清单、命令与结果、OPEN_QUESTIONS 更新。
```
第二次会话：1.11～1.17（训练、推断、结算、一键运行 CLI），验收 AC-13～AC-16、AC-27、AC-34（P1 部分：`sr run --mode replay|dry_run`）。第三次会话：1.18～1.19、1.21～1.25（公司行为、历史类比、有效期、估值背景、场景测试，验收 AC-37～AC-42、AC-49 P1 部分），1.26（时刻表与对照视图，验收 AC-52、AC-53），1.27～1.28（采集记录与推理链，验收 AC-56、AC-57），最后 1.20。

**Phase 2 模板**
```text
本轮实现 DP「Phase 2」附录 A 的 2.01～2.06（实时数据与调度）。不改动已发布预测的不可变约束。
验收 AC-17、AC-18。提供 staging 运行说明。
```
后续会话：2.07～2.08 + 2.15（网页与一键运行，验收 AC-34、AC-35）；2.09～2.10（新公司接入 1–5 阶段，验收 AC-32）；2.11～2.14（运营、部署、手册，验收 AC-36）；2.17～2.18（事件结果结算与条件预测，验收 AC-43～AC-45）；2.19～2.21（宏观、法院、Form 4 来源，验收 AC-46～AC-48）；2.22～2.23（质量界面与行业模板，验收 AC-49 P2 部分、AC-50）；2.24～2.25（时刻表实时与"预测与实际"卡片，验收 AC-54）；2.26（股票详情三步视图，验收 AC-58）；2.27～2.29（用户补充信息与继续分析，验收 AC-59～AC-61）。

**Phase 3 模板**
```text
本轮实现 DP「Phase 3」附录 A 的 3.01～3.07（训练后台、评估、影子、审批）。门槛读取 config/gates，不在代码里硬编码。
验收 AC-19～AC-22。所有示例指标仍为测试数据，不得写入"已验证"状态。
```
后续会话：3.08～3.09（接入 6–8 与 TSM/MRVL，验收 AC-33）；3.10～3.13、3.15（分步开放、合规与预测对照后台，验收 AC-31、AC-55），最后 3.14。

---

## 首轮 Claude Code 执行指令（复制到 VS Code 中的 Claude Code）

> 下面是给 Claude Code 的第一轮任务，**只做 Phase 0**。

```text
你是本仓库的实现工程师。请先完整阅读 docs/BUILDING_MASTER_PLAN.md、docs/DATA_CONTRACT.md、docs/DEVELOPMENT_PHASES.md（以下简称 MP / DC / DP），
以及 prototype/（只作 UI 与字段参考）。本轮只实现 DP 的「Phase 0」，不要开始 Phase 1 的任何功能。

范围（全部必须完成）：
1. 建立 monorepo 骨架（MP §6 目录）：pnpm workspace（apps/web 仅放 Next.js 空壳首页即可）、packages/contracts、services/py（uv 项目，包名 sr）、
   supabase/、config/、data/（gitignore）、docs/（放入三份文档）。
2. packages/contracts：按 DC §3.1、3.3、3.5、3.6、3.7 写 JSON Schema（schema_version="contract-0.7"）：companies, securities,
   security_identifiers, corporate_actions, industry_templates, company_profile_versions（含 industry_template）, forecast_schedules（seed sched-0.1，DC §3.7a）, collection_runs, collection_items（DC §3.2，只建表不实现采集）, trading_sessions, reference_quotes, benchmark_definitions, benchmark_versions, security_state_snapshots,
   prediction_targets, prediction_runs, predictions, prediction_settlements；以及 training_dataset_versions、training_runs、
   training_run_metrics、extraction_eval_runs，以及运营实体 pipeline_runs、pipeline_run_steps、onboarding_requests、data_source_health、alerts（Phase 1–2 会用）。把 DC §8 的示例（含 regular_60m_move）拆成 examples/*.json 并全部通过校验。生成 TS 类型与 pydantic 模型。
3. supabase/migrations/0001_core.sql：上面实体的表、enum、主键/唯一约束、外键；predictions 发布后不可改 probabilities/locked/target_row_id 的触发器；
   jobs 表（DC §3.9）。seed：4 只 pilot（NVDA, AMD, AVGO, MU）+ 2 只 batch2（TSM, MRVL）+ 篮子其余成分（peer_only）、
   每只 pilot 的 bm_semis_peer_ex_<ticker> v1（MP D-08，等权剔除自身）、bm_soxx_ref、参考品种 QQQ/SPY/SMH/^VIX（coverage_tier='reference'）、
   tgt_regular_60m_v1（threshold_rule = vol_scaled, k=0.25）/ tgt_regular_60m_move_v1（output_kind=quantiles）/ tgt_regular_to_close_v1 / tgt_next_regular_session_v1，td-0.2。
4. services/py/sr/calendar：基于 exchange_calendars XNYS + config/calendar_overrides.yaml；实现 session(date)、
   is_target_available(target_id, published_at)、next_regular_session(published_at) 与 schedule_slots(date)（按 sched-0.1 展开当日槽位，处理半日市/休市/DST）。规则见 MP D-04、D-10、D-18、D-43 与 DC §4、§3.7a。
5. services/py/sr/marketdata：quote_rules.py（MP D-05、D-06、D-12，参数读 config/quote_rules.yaml，版本 qr-0.1）、
   sync.py（find_first_sync_qualifying(after_ts, security, basket, tolerance_ms=2000, max_wait_s=30)）、
   providers/base.py（MarketDataProvider 接口，MP §3.2）与 providers/fixture.py（读 Parquet）。
   services/py/sr/benchmark/basket.py：等权篮子收益与缺失规则（max_missing_constituents=1）。
   services/py/sr/eval/metrics.py：三分类 Brier、命中率、BSS（参照 class_frequency / always_flat / persistence）、pinball loss（DC §8.1 算例：Brier 0.5798；pinball 0.035/0.068/0.053）；
   services/py/sr/eval/bootstrap.py：按交易日分块 bootstrap（固定 seed，2,000 次）。
5b. services/py/sr/labels：sigma.py（sigma-0.1：近 20 个交易日、同一时段桶 EWMA，半衰期 10 日，只用 as_of 之前数据）与 thresholds.py（threshold_pp = k × sigma_hat_pp，边界含阈值本身为 flat；sigma 缺失 → abstain insufficient_data）。见 MP D-09、DC §3.7。
5c. config/features/fs-0.2.yaml 与 services/py/sr/features/*：按 MP D-31 实现时段/日历、跨资产代理、篮子领先滞后、波动状态的纯函数（只读 ts ≤ as_of），只做单元测试，不训练模型。
6. scripts/make_fixture.py 生成合成 fixture：NVDA + 11 个篮子成分，2026-12-01 09:30–16:00 ET 秒级 NBBO，含一段宽价差、一次 3 分钟停牌；
   scripts/validate_sample.py 输出覆盖率、合格率、同步成功率报告。明确标注为 synthetic。
7. docs/data_procurement.md：按 MP 决策表 D-13、D-15、D-16 建供应商对比模板（覆盖、时间精度、历史年限、实时延迟、授权展示、价格、验证状态），
   全部初始标「拟选/未验证」，不要编造价格或授权条款。
8. config/decisions.yaml：MP §9 决策表（D-01～D-48）的机器可读镜像。
9. 基础设施（DP P0-H / 附录 A 0.01、0.02、0.14）：GitHub Actions CI（ruff、mypy、pytest、tsc、eslint、契约示例校验、迁移重放）、pre-commit、.env.example、docs/CHANGELOG.md。
   pipeline_runs、onboarding_requests、data_source_health、alerts 只需写入 JSON Schema 与迁移（DC §3.10），不实现逻辑（Phase 1–2）。
   security_state_snapshots 与 predictions 的 0.4 字段（run_state、quality_issues、last_valid_at、valid_until）照 DC 建列；macro_releases、insider_transactions、
   docket_entries、options_snapshots 本轮只写 JSON Schema，不建表（Phase 2/4）。seed 首批公司 industry_template=semiconductor。

验收（DP Phase 0 的 AC-01～AC-05、AC-26，AC-28/AC-29 的 P0 部分，以及该节列出的其余条件）：
- supabase db reset 成功；uv run pytest 全绿；pnpm -r build 成功；contracts examples 校验通过。
- 测试必须覆盖：2026-11-26 休市、2026-11-27 与 2026-12-24 半日市 13:00 ET、DST 切换、14:59:00 vs 14:59:45 ET 的 60m 可用性、
  15:44 / 15:46 ET 的至收盘可用性、2026-12-01 与 2026-11-27 的槽位展开、半日市 12:30 发布 60m 不可用、周六发布的下一时段、宽价差/停牌/陈旧报价、30s 内无同步报价、缺 2 个成分的篮子、
  波动缩放阈值边界（+0.15pp 判 flat）、sigma 缺失弃预测、sigma 与特征函数读取未来数据时报错、BSS 与 pinball 算例、bootstrap 固定 seed 可复现。

约束：
- 时间一律 UTC 存储（timestamptz），测试用 ET 输入时显式转换。不要用本地时区。
- 不接入任何真实付费 API，不写入任何密钥；需要密钥的适配器只留接口与 .env.example。
- 字段名、枚举值必须与 DC 完全一致；若发现 DC 有矛盾或缺字段，在 docs/OPEN_QUESTIONS.md 记录并采用 MP 决策表默认值，不要自行发明新语义。
- 不实现 LLM 调用、事件分析、预测模型、模型训练或页面（Phase 1+）；P0 只交付阈值、评分与特征的纯函数及测试。
完成后输出：变更文件清单、每条验收的命令与结果、OPEN_QUESTIONS.md 内容摘要。
```
