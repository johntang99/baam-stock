# DATA CONTRACT · 美股短期研究与预测系统

**契约版本** `schema_version = "contract-0.7.2"` · 2026-11-26（0.7.2：Phase 1 第 1 组（DP 1.03–1.06）——证据与事件实体建表（`source_documents`、`source_document_versions`、`event_evidence`、`events`、`event_security_links`、`event_milestones`、`event_analysis_versions`）；新增 `llm_calls`（§3.4b，LLM 调用留痕）；`source_document_versions` 明确 `missing_reason`、`simulated_available_at` 列（§1.1 已有语义）；待人确认（OPEN_QUESTIONS OQ-23）；0.7.1：实现 Phase 0 时的增量补丁——`securities.security_type` 增 `etf`、`index`，`primary_exchange` 增 `ARCX`（NYSE Arca，SPY）、`XCBO`（Cboe，^VIX），以容纳 D-31 参考品种与 SOXX；`predictions` 增 `scenarios`（§8.2 事件结果示例已使用）；已由用户 2026-11-26 确认（OQ-01）；0.7：用户补充信息 `user_submissions`（链接/文本/文件、类别建议、核验状态）与增量补充运行 `mode=supplement`、`trigger_type=user_supplement`；0.6：第 1 步信息采集可见——`collection_runs`、`collection_items`（每条采集项的渠道、类别、处置状态与四类时间，含被去重/排除/待核的）；第 2 步推理可追溯——`market_explanation` 每条陈述带引用、新增 `reasoning_trace`；0.5：每日固定预测时刻表 `forecast_schedules`（主评分点）、预测槽位字段、预测与实际对照视图 `forecast_vs_actual` 与滚动准确率 `forecast_accuracy_rollups`；0.4：补齐 PPT 蓝图缺口——公司行为、行业模板、宏观首发值、Form 4、法院案卷、期权快照占位、估值背景、历史类比规则、运行状态与有效期、事件结果结算规则、条件预测触发、`interval_width`/`trigger_rate` 指标；0.3：运营实体——一键流水线运行、新公司接入、数据源健康、告警；0.2：波动缩放阈值、`regular_60m_move`、BSS 参照模型、参考品种、LLM 提取评估、对外开放范围）
**适用**：Supabase Postgres（表）、Python worker（pydantic 模型）、Next.js（生成的 TS 类型）、原型 `prototype/data.js`（字段名一致）。
**单一事实来源**：实现时把本文表格落成 `packages/contracts/schemas/*.schema.json`，再生成 SQL 迁移、pydantic、TS。

---

## 1. 通用约定

| 项 | 规则 |
|---|---|
| 主键 | 文本 ID，带前缀：`co_`、`sec_`、`doc_`、`docv_`、`evd_`、`evt_`、`eav_`、`snap_`、`bm_`、`bmv_`、`tgt_`、`run_`、`pred_`、`stl_`、`rq_`、`ds_`、`tr_`、`mdl_`、`eval_`、`dep_`、`job_`、`llm_`（0.7.2）。新记录用 ULID（时间有序）：`pred_01JF…`；种子数据可用可读 ID（`sec_nvda`） |
| 时间 | 全部 `timestamptz`，以 UTC ISO-8601 传输（`2026-12-01T15:20:02.000Z`），毫秒精度；页面显示 `America/New_York`。仅日期用 `date` + `*_precision` 字段 |
| 时间精度 | `time_precision ∈ {ms, s, minute, hour, day, unknown}`；`day`/`unknown` 的来源时间不得用于盘中先后判定 |
| 金额/价格 | `numeric(20,6)`；JSON 中用数字；币种 `currency` ISO-4217 |
| 收益 | `*_return_pct`：百分比数值（+0.42 表示 +0.42%）；`relative_return_pp`：百分点 |
| 概率 | `probabilities` 对象，键为类别枚举，和 = 1 ± 1e-6 |
| 空值 | 可空字段为 `null` 时必须有对应 `*_reason`（`missing_reason`、`abstain_reason`、`invalid_reason`）；数值 0 是有效值不得用作缺失 |
| 版本 | 追加式。可变"当前指针"只在父表（如 `events.current_analysis_version`），由乐观锁更新 |
| 乐观锁 | 父表含 `row_version int`；更新写 `WHERE row_version = :expected`，失败即放弃（防旧任务覆盖新版本） |
| 幂等 | 所有写入任务带 `idempotency_key`（唯一约束）；重复投递返回已有记录 |
| 软删除 | 禁止删除已发布记录；撤回用新版本 + `status=retracted` |
| 错误 | API 错误体 `{ "error": { "code": "…", "message": "…", "details": {} } }`；code 枚举见 §9 |

### 1.1 时间语义（五元组 + 发布）

| 字段 | 含义 | 可空 |
|---|---|---|
| `occurred_at` | 事件实际发生（如法院签发时刻、交割生效） | 是 |
| `source_published_at` + `source_published_precision` | 来源首次公开 | 是（需 `missing_reason`） |
| `received_at` | 系统收到 | 否 |
| `available_at` | 系统可用于分析的时刻（解析/核验完成） | 否 |
| `analysis_as_of` | 分析/快照的数据截止 | 否 |
| `published_at` | 对用户发布（入库 ≠ 发布；`created_at` 为入库时间） | 发布后非空 |
| `effective_at` | 法律或业务生效 | 是 |

**回放规则**：时点 T 的回放只读取 `available_at ≤ T`（历史存档）或 `simulated_available_at ≤ T`（模拟到达，标 `arrival_mode = simulated`）的记录；预期快照还需 `snapshot_as_of < 相关披露的 source_published_at`，只有日期精度且无法证明早于披露者排除。

---

## 2. 实体关系

```
companies 1─* securities 1─* security_identifiers(ticker 有效期)
companies 1─* company_profile_versions ──> benchmark_definitions
benchmark_definitions 1─* benchmark_versions(constituents, weights, effective_from)
trading_sessions (exchange, session_date)

data_sources 1─* source_documents 1─* source_document_versions 1─* event_evidence *─1 events
events 1─* event_security_links *─1 securities
events 1─* event_milestones
events 1─* event_analysis_versions(per security) ── prediction_readiness(内嵌)
expectation_snapshots *─1 companies

reference_quotes / market_bars_1m *─1 securities
security_state_snapshots *─1 securities, ─> event_analysis_versions[](可空), ─> benchmark_versions

prediction_targets(定义, 版本化) 1─* predictions
prediction_runs 1─* predictions ─> security_state_snapshots, model_versions, feature_snapshots
predictions 1─* prediction_settlements(版本)

training_dataset_versions 1─* training_runs 1─* training_run_metrics
training_runs 1─* model_versions 1─* model_evaluations
model_deployments ─> model_versions(prev, next)
jobs (队列, idempotency_key)
```

---

## 3. 字段表

记法：**PK** 主键，**UQ** 唯一，**FK→** 引用，`?` 可空。

### 3.1 公司与证券配置

**`companies`**

| 字段 | 类型 | 说明 |
|---|---|---|
| company_id **PK** | text | `co_nvidia` |
| legal_name | text | |
| cik | text? UQ | SEC CIK，10 位补零 |
| sector / industry | text | GICS 风格文本，配置用 |
| fiscal_calendar | jsonb | `{ "fy_end_month": 1, "week_based": true }` |
| row_version | int | 乐观锁 |

**`securities`**

| 字段 | 类型 | 说明 |
|---|---|---|
| security_id **PK** | text | `sec_nvda` |
| company_id FK→companies | text | |
| security_type | enum | `common`, `adr`, `etf`, `index`（0.7.1：参考品种） |
| primary_exchange | enum | `XNAS`, `XNYS`, `ARCX`, `XCBO`（0.7.1） |
| currency | char(3) | `USD` |
| coverage_tier | enum | `pilot`（首批）, `batch2`, `peer_only`, `reference`（仅作特征：QQQ、SPY、SMH、^VIX，D-31）, `inactive` |
| primary_benchmark_id FK→benchmark_definitions | text | `bm_semis_peer_ex_nvda` |
| reference_benchmark_id FK→ | text? | `bm_soxx_ref` |

**`security_identifiers`**：`(security_id, id_type ∈ {ticker, figi, cusip, vendor:<name>}, value, valid_from date, valid_to date?)`；UQ `(id_type, value, valid_from)`；按时点解析代码（代码变更、并股）。

**`corporate_actions`**（D-40）：`action_id PK`、`security_id FK`、`action_type ∈ {split, reverse_split, cash_dividend, special_dividend, spin_off, ticker_change, merger_delisting}`、`announced_at`、`ex_date date`、`effective_at timestamptz?`、`ratio numeric?`（拆股比，例 10 表示 1→10）、`cash_amount numeric?`、`source_id`、`available_at`。规则：① 复权价只在研究库生成，`reference_quotes` 永远存原始价；② 预测窗口跨越 `ex_date`/`effective_at` 时，结算按比例调整起算价，`cash_dividend` 低于前收 0.5% 时忽略；③ 无法确定比例 → `invalid_reason = corporate_action`；④ `ticker_change` 同步写入 `security_identifiers` 新行。

**`company_profile_versions`**：`profile_version_id PK`、`company_id FK`、`version int`、`effective_from timestamptz`、`key_metrics text[]`、`exposures jsonb`（客户/供应商/地区/监管机构及权重标签）、`official_sources jsonb`、`priority_rules_version text`、`industry_template ∈ {semiconductor, bank, biotech, generic}`（D-42；决定 key_metrics 默认值、来源优先级与可用的事件类型）、`valuation_peers text[]`（估值背景比较组）。UQ `(company_id, version)`。

**`industry_templates`**（D-42）：`template_id PK`、`version`、`key_metrics_default text[]`（半导体：`revenue, gross_margin_pct, datacenter_revenue, inventory_days`；银行：`net_interest_income, nim_pct, cet1_ratio, provision_for_credit_losses`；生物医药：`pipeline_milestones, cash_runway_quarters, pdufa_dates`）、`event_types_enabled text[]`、`official_sources_default jsonb`（银行加 Fed/FDIC/OCC；生物医药加 FDA/ClinicalTrials.gov）、`exposure_dimensions text[]`（半导体：出口管制/客户集中；银行：利率/资本规则/信用；生物医药：审批/专利）。同一政策事件通过 `event_security_links.exposure_note` + 模板 `exposure_dimensions` 分别解读不同行业的影响方向。

**`trading_sessions`**

| 字段 | 类型 | 说明 |
|---|---|---|
| exchange + session_date **PK** | enum + date | |
| status | enum | `open`, `early_close`, `closed` |
| open_at / close_at | timestamptz? | 正常 14:30Z/21:00Z（EST）；半日市 close 18:00Z |
| source | text | `exchange_calendars:XNYS@ver` 或 `override:<ticket>` |
| calendar_version | text | 覆盖表变更即升版 |

### 3.2 来源与证据

**`data_sources`**：`source_id PK`、`kind ∈ {market_data, filing, insider_filing, company_ir, news, policy, court, expectation, macro, options, llm}`、`provider`、`license_scope ∈ {public, licensed_internal, licensed_display, restricted}`、`verification_status ∈ {proposed, sample_verified, contracted, retired}`、`time_precision_default`、`notes`。

**`source_documents`**：`doc_id PK`、`source_id FK`、`canonical_url text?`、`external_ref text?`（如 SEC accession no.）、`origin_doc_id FK→source_documents?`（转载指向原始出处）、`subject_company_ids text[]`。UQ `(source_id, external_ref)`。

**`source_document_versions`**

| 字段 | 类型 | 说明 |
|---|---|---|
| doc_version_id **PK** | text | |
| doc_id FK | text | |
| version | int | UQ `(doc_id, version)` |
| content_hash | char(64) | SHA-256；UQ `(doc_id, content_hash)`（重复投递幂等） |
| storage_path | text? | 原文位置；授权不允许保存时为空并填 `locator` |
| locator | text? | 来源定位 |
| source_published_at / _precision | timestamptz? / enum | |
| received_at / available_at | timestamptz | |
| arrival_mode | enum | `live`, `archived`, `simulated` |
| is_correction_of | text? FK→doc_version_id | 来源更正 |
| visibility | enum | `public`, `internal`, `restricted_review` |
| missing_reason / simulated_available_at | text? / timestamptz? | 0.7.2 明确列出：`source_published_at` 为空时 `missing_reason` 必填（§1 空值规则、AC-06）；`arrival_mode=simulated` 时的模拟到达时刻（§1.1） |

**`collection_runs`**（第 1 步：信息采集，D-45）

| 字段 | 类型 | 说明 |
|---|---|---|
| collection_run_id **PK** | text | `col_nvda_20261202_1129` |
| pipeline_run_id FK? / snapshot_id FK? | text | 一键运行或定时快照触发 |
| security_id FK | text | 采集范围：目标公司 + 档案中的客户/供应商/监管机构/同行（`company_profile_versions.exposures`） |
| window_from / window_to | timestamptz | 本次检索的 `available_at` 区间（增量：上次水位 → 本次 as_of） |
| sources_polled | jsonb | `[{source_id, channel, status ∈ {ok, timeout, error, skipped}, items_fetched, latency_ms}]` |
| counts | jsonb | `{fetched, kept, duplicate, excluded, pending_review, failed, by_channel:{…}, by_category:{…}}`（由 `collection_items` 汇总，不手填） |
| started_at / finished_at | timestamptz | |

**`collection_items`**（每条被检索到的条目一行，**包括没有进入分析的**）

| 字段 | 类型 | 说明 |
|---|---|---|
| item_id **PK** | text | |
| collection_run_id FK | text | |
| source_id FK / channel | text / enum | `channel ∈ {filing, insider_filing, company_ir, news_wire, policy, court, macro, expectation, market_data, peer_company, user_submission}` |
| submission_id FK? / submitted_by | text? | 仅 `user_submission`：来自哪次用户提交、哪位用户 |
| category | enum | `earnings_guidance, policy_export, customer_demand, supply_chain, m_and_a, litigation, management, product, capital_return, macro, analyst_rating, insider_trade, market_data, other`（规则 + LLM 分类，带 `category_confidence`） |
| title / snippet | text / text? | 新闻类按授权只存标题与定位（D-15 授权范围） |
| doc_version_id FK? | text | 进入证据库后才有 |
| mentions | text[] | 命中的公司/代码 |
| disposition | enum | `kept`（进入分析）, `duplicate`（同源转载/重复投递，`duplicate_of` 指向保留项）, `excluded_irrelevant`（只顺带提及等，`exclusion_reason`）, `excluded_after_asof`（`available_at > analysis_as_of`，下一次运行再用）, `excluded_restricted`（疑似未公开材料，界面只显示占位）, `pending_review`（人工复核中）, `fetch_failed` |
| duplicate_of / exclusion_reason | text? / text? | |
| relevance | numeric? | 0–1，规则 + 模型打分；低于阈值 → `excluded_irrelevant` |
| linked_event_id / linked_evidence_ids | text? / text[] | 被用到哪个事件、哪些证据 |
| occurred_at / source_published_at / received_at / available_at | timestamptz? | 四类时间（S1「四项时间」），精度字段同 §3.2 |

**`user_submissions`**（用户补充信息，D-47）

| 字段 | 类型 | 说明 |
|---|---|---|
| submission_id **PK** | text | `sub_…` |
| submitted_by | text | 用户 ID |
| security_ids | text[] | 用户指定的相关证券（系统可追加建议，需用户确认） |
| input_kind | enum | `link`, `text`, `file`（PDF/图片/文档，≤ 20MB；病毒扫描后入对象存储） |
| url / text / file_path | text? | 三选一 |
| user_note | text? | 用户说明"为什么重要" |
| user_categories | text[] | 用户选择的类别（可多选，可留空） |
| system_categories | jsonb | `[{category, confidence}]`：规则 + LLM 建议；`final_categories` = 用户选择 ∪ 置信度 ≥ 0.6 的系统建议（可多类别），研究员可改 |
| final_categories | text[] | |
| submitted_at | timestamptz | = 该条目的 `received_at` 与 `available_at`（**不得回溯**到原文发布时间） |
| status | enum | `received → fetching → verifying →` 终态之一：`verified_primary`（找到并核对原始来源，如 SEC/IR/监管原文）, `media_level`（只有媒体来源，等同 `media_report`）, `unverified`（链接打不开、无可核对来源、或仅有用户文本）, `duplicate`（已在系统中，`duplicate_of_item_id`）, `rejected_restricted`（疑似未公开材料 → 合规复核）, `fetch_failed` |
| verification | jsonb | `{fetched_ok, http_status?, canonical_url?, origin_source_id?, origin_url?, origin_published_at?, independent_origin_key?, content_hash, duplicate_of_item_id?, checks:[{check ∈ {link_reachable, domain_reputation, origin_traced, content_matches_origin, timestamp_consistent, duplicate_check, mnpi_screen}, result ∈ {pass, fail, n_a}, note}]}` |
| item_id FK? | text | 核验后写入的 `collection_items` 行（`channel=user_submission`，`disposition` 依状态：`verified_primary`/`media_level` → `kept`；`unverified` → `pending_review`；`duplicate` → `duplicate`；`rejected_restricted` → `excluded_restricted`） |
| missed_by_system | bool? | 原始来源早于本次运行却未被系统采集 → 记为来源覆盖缺口，进入数据源复盘 |
| supplement_run_id FK? | text | 用户点击"继续分析"后的补充运行 |
| visibility | enum | `submitter_and_reviewers`（默认）, `shared`（核验为 `verified_primary`/`media_level` 后自动共享） |

规则：用户提交**不默认可信**；`unverified` 条目不进入模型特征、不能作为"已观察事实"，只在推理链中以"用户提供，未证实"列出；同一用户对同一 URL/内容哈希重复提交 → 幂等返回原提交；限流：每用户每证券每 2 分钟 1 次补充运行。

约束：`collection_items` 只追加；同一 `content_hash` 再次出现记为 `duplicate`，不新建证据。行情不按条存（每秒报价过多），以 `channel=market_data` 的汇总项记录：`{quotes_received, qualifying_rate, sync_success_rate, last_quote_ts}`。

**`event_evidence`**：`evidence_id PK`、`event_id FK`、`doc_version_id FK`、`claim text`（谁说了什么）、`claimant`、`span jsonb`（原文定位：页/段/字符区间）、`verification_status ∈ {pending, media_report, primary_confirmed, conflicting, retracted}`、`available_at`、`visibility`、`independent_origin_key`（同源转载相同，用于计独立来源数）。

### 3.3 行情

**`reference_quotes`**（被预测/结算/快照引用的报价；1 秒层全量在 Parquet，同 schema）

| 字段 | 类型 | 说明 |
|---|---|---|
| quote_id **PK** | text | `rq_…` |
| security_id FK | text | 基准成分同样入表 |
| quote_ts | timestamptz | 交易所/SIP 时间戳 |
| received_at | timestamptz | 系统收到 |
| session_type | enum | `pre_market`, `regular`, `post_market` |
| bid / ask / mid / last | numeric | |
| spread_bp | numeric | |
| price_type | enum | `nbbo_mid`, `official_close`, `official_open`, `last_trade` |
| quality_flags | text[] | `stale`, `wide_spread`, `halted`, `luld_pause`, `crossed`, `delayed` |
| is_qualifying | bool | 按 `quote_rule_version` 判定 |
| quote_rule_version | text | `qr-0.1` |
| vendor_source_id FK→data_sources | text | |
| adjustment_basis | text | `raw_intraday`（盘中不复权） |

UQ `(security_id, quote_ts, price_type, vendor_source_id)`。迟到报价（`received_at - quote_ts > 5s`）标 `delayed`；用于结算时仅当 `received_at` 早于结算任务执行时间。

**`market_bars_1m`**：`(security_id, bar_start) PK`、`open/high/low/close numeric`、`volume bigint`、`vwap`、`trade_count`、`session_type`、`bar_version int`（更正追加）。

### 3.4 预期与事件

**`expectation_snapshots`**：`exp_id PK`、`company_id`、`metric`（如 `revenue`, `eps_non_gaap`, `gross_margin_pct`）、`fiscal_period`（`FY2027Q3`）、`value numeric?`、`range_low/high?`、`unit`（`USD`, `pct`, `USD_per_share`）、`accounting_basis ∈ {gaap, non_gaap, company_defined}`、`expectation_type ∈ {company_guidance, analyst_consensus, other_public}`、`snapshot_as_of`、`snapshot_precision`、`available_at`、`source_id`、`revision_of_exp_id?`（预期修正链：同一 metric/fiscal_period 的新快照指向上一版，用于"预期修正"特征）。

**`macro_releases`**（D-15）：`release_id PK`、`series_id`（例 `CPIAUCSL`、`PAYEMS`、`FEDFUNDS`）、`reference_period`（`2026-10`）、`vintage_date date`、`value numeric`、`is_first_release bool`、`release_at timestamptz`（官方发布时刻，ET 08:30 等）、`consensus_value numeric?`（若有授权来源；否则空）、`source_id`、`available_at`。规则：回放与训练只用 `available_at ≤ T` 的 vintage；首发值从 ALFRED（圣路易斯联储历史 vintage 库）回填，后续修订值另存新行，**不得**用修订后数值替代当时首发值。

**`insider_transactions`**（Form 4）：`txn_id PK`、`security_id`、`insider_name`、`insider_role`（CEO/CFO/Director/10% owner）、`transaction_code`（P 买入、S 卖出、A 授予、M 行权、F 扣税…）、`is_10b5_1 bool?`、`shares numeric`、`price numeric?`、`transaction_date date`、`filed_at timestamptz`（EDGAR 接收时间）、`accession_no`、`available_at`。特征只用 P/S 且非 10b5-1 的公开市场交易；A/M/F 仅展示。

**`docket_entries`**（法院案卷）：`docket_entry_id PK`、`event_id FK?`、`court`（例 `D.Del.`、`CAFC`、`ITC`）、`case_number`、`entry_no int`、`entry_type ∈ {complaint, motion, order, opinion, judgment, verdict, appeal_notice, settlement, other}`、`filed_at timestamptz`、`entered_at timestamptz?`、`title`、`doc_version_id FK?`、`source_id`（CourtListener/RECAP 或 PACER）、`available_at`。`order`/`judgment`/`verdict` 自动生成 `event_milestones` 候选，需人工确认。

**`options_snapshots`**（Phase 4 占位，D-15）：`opt_snap_id PK`、`security_id`、`snapshot_at`、`expiry date`、`atm_iv numeric?`、`iv_25d_put/call numeric?`、`implied_move_pct numeric?`（最近到期跨式价 / 现价）、`put_call_volume_ratio numeric?`、`source_id`、`available_at`。来源未核实前不进入任何模型特征；只在 Phase 4 作为 `regular_60m_move` 与财报事件的候选特征评估。

**`events`**

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id **PK** | text | |
| category | enum | `earnings_guidance`, `customer_demand`, `policy_export`, `executive_change`, `accounting_audit`, `product_supply`, `macro_rates`, `competition`, `litigation_regulatory`, `capital_estimates`, `trading_structure`, `m_and_a`, `investment_contract`, `license_policy` |
| subtype | text? | |
| identity_key | text UQ | 稳定识别键：`case:<court>:<docket>`、`deal:<acq>:<tgt>:<agreement_date>`、`earnings:<co>:<fiscal_period>`、`policy:<agency>:<fr_doc_no>` |
| progress_status | enum | `pending`, `outcome_confirmed`, `effective`, `terminated` |
| evidence_status | enum | `pending`, `media_report`, `primary_confirmed`, `conflicting`, `retracted` |
| analysis_status | enum | `partial`, `complete`, `needs_review` |
| current_analysis_version | int? | 指针 |
| row_version | int | 乐观锁 |
| first_seen_at | timestamptz | |

**`event_security_links`**：`(event_id, security_id) PK`、`relation ∈ {subject, acquirer, target, supplier, customer, competitor, regulated_party, sector_wide}`、`exposure_note`。

**`event_milestones`**：`milestone_id PK`、`event_id`、`milestone_type`（并购：`agreement_signed`, `shareholder_vote`, `regulatory_filing`, `regulatory_clearance`, `closing`, `termination`；诉讼：`complaint_filed`, `hearing`, `order`, `verdict`, `appeal`, `settlement`；政策：`official_statement`, `proposed_rule`, `comment_period_end`, `rule_published`, `rule_effective`, `enforcement_action`；许可与出口：`license_applied`, `license_granted`, `license_denied`, `shipment_confirmed`；公司：`board_announcement`, `guidance_update`）、`decision_body`、`expected_at?`、`actual_at?`、`status ∈ {scheduled, occurred, delayed, cancelled}`、`evidence_ids text[]`。

**`event_analysis_versions`**（S2§4；每个证券一套）

| 字段 | 类型 | 说明 |
|---|---|---|
| analysis_id **PK** | text | `eav_…` |
| event_id FK / security_id FK | text | |
| analysis_version | int | UQ `(event_id, security_id, analysis_version)` |
| analysis_kind | enum | `flash`（核实快报）, `full` |
| analysis_as_of / published_at | timestamptz | |
| evidence_ids | text[] | |
| facts | jsonb | `[{metric, value, unit, currency, period, basis, evidence_ids, null_reason?}]` |
| expectation_comparison | jsonb? | `{consensus_value, consensus_as_of, difference, difference_pct | difference_pp, comparison_basis}` 或 `null` + `missing_reason` |
| impact | jsonb | `[{fact → exposure → channel, direction ∈ {positive,negative,mixed,unknown}, horizon, evidence_ids}]` |
| priority | jsonb | `{potential_impact, expectation_gap, urgency, evidence_credibility}` 各 `high|medium|low|unknown`，`rule_version` |
| market_reaction | jsonb | `{ref_before_quote_id, ref_asof_quote_id, stock_return_pct, benchmark_return_pct?, relative_return_pp?, missing_reason?}` |
| market_explanation | jsonb | `{status ∈ {supported, partial, insufficient}, observed_facts[], possible_drivers[], counter_evidence[], unexplained[], concurrent_events[], valuation_context?}`。0.6 起每条陈述为对象 `{text, evidence_ids[], quote_ids[], item_ids[], trace_step}`（D-46）：`observed_facts`、`possible_drivers`、`counter_evidence` 至少引用 1 个证据或报价，无引用的陈述被校验拒绝并改放 `unexplained`。`valuation_context`：`{as_of, fwd_pe, fwd_pe_pctile_3y, peer_median_fwd_pe, ev_sales_ntm?, source_id, note}`——只作背景说明（例"远期市盈率处于近 3 年 85 分位"），不进入短线模型特征，无授权来源时为空 |
| reasoning_trace | jsonb | 第 2 步推理链（D-46），有序步骤：`[{step:1, kind ∈ {market_fact, timing_check, evidence_fact, attribution, counter_check, analogue, gap, conclusion}, inputs:{quote_ids[], evidence_ids[], item_ids[], analysis_ids[]}, rule?（如 "相对收益 = 个股 − 篮子"、"证据可用时间早于异动开始"）, conclusion, confidence ∈ {high, medium, low}?}]`；确定性规则步骤（行情、时间对齐）由代码生成，归因与反向证据可由 LLM 起草但必须引用；回放时整条链锁定在分析版本中 |
| historical_cases | jsonb | `{query_version, match_keys{event_type, subtype, industry_template, market_state, surprise_bucket?}, n, period, case_ids[], median_relative_pp, iqr_pp, hit_share_positive, fallback_applied, fallback_level ∈ {none, drop_subtype, peer_group, sector_wide}, insufficient}`，规则见 §3.4a |
| scenarios | jsonb? | 待决事件情景 |
| data_gaps | text[] | |
| rule_version / model_versions | text / jsonb | 含 LLM provider/model/prompt_version |
| prediction_readiness | jsonb | 见 §3.5 |
| supersedes_analysis_id | text? | |

### 3.4b LLM 调用留痕（0.7.2）

**`llm_calls`**（只追加；每次 LLM 调用一行，MP §3.2）：`call_id PK`（`llm_…`）、`purpose ∈ {extract_facts, draft_explanation}`、`provider`、`model`、`prompt_version`、`prompt_hash`（渲染后提示词 SHA-256）、`input_hash`（输入原文 SHA-256）、`output_hash?`、`doc_version_id?`、`mode ∈ {live, replay}`、`request_params jsonb`（effort、max_tokens、输出 schema；`tools` 必须为空——回放与提取禁止联网搜索）、`usage jsonb`（输入/输出 token）、`stop_reason?`、`status ∈ {succeeded, rejected_validation, refused, failed}`、`error?`、`latency_ms?`、`created_at`。规则：每条提取的事实必须带原文定位且引用文本能在原文中逐字找到，否则整次调用 `rejected_validation`，结果不得进入事件或特征（禁止用模型记忆补结果，S3§6）。

### 3.4a 历史类比检索规则（D-38，`query_version = hc-0.1`）

1. **只用过去**：候选案例的 `available_at` 与结算时间都必须 ≤ 当前 `analysis_as_of`；同一事件链（含修订、转载）不得自匹配。
2. **匹配键**：`event_type` + `subtype` + `industry_template` + `market_state`（盘前/盘中/盘后）；财报再加 `surprise_bucket`（低于/符合/高于预期）。
3. **度量**：每个案例取同一目标窗口的相对基准收益（pp）；输出中位数、四分位距、正收益占比。
4. **样本门槛**：`min_cases = 8`。不足时按 `drop_subtype → peer_group（同模板公司）→ sector_wide` 逐级放宽，每放宽一级记录 `fallback_level`；放宽到 `sector_wide` 仍不足 → `insufficient = true`，界面写"历史样本不足"，不显示中位数。
5. **展示约束**：类比只作参考，必须同时展示 n、期间和放宽级别；不得作为单独的方向信号。
6. **回放一致**：回放时用当时可得的案例集重新检索，`case_ids[]` 锁进分析版本。

### 3.5 预测交接与证券快照

**`prediction_readiness`**（内嵌于分析版本与快照）

```json
{
  "event_outcome":  {"status": "ready|missing_inputs|manual_review|not_applicable", "reason": "…", "analysis_id": "eav_…"},
  "stock_reaction": {"status": "ready|missing_inputs|manual_review|not_applicable", "reason": "…", "analysis_id": "eav_…", "allowed_models": ["market_baseline"]}
}
```

**`security_state_snapshots`**

| 字段 | 类型 | 说明 |
|---|---|---|
| snapshot_id **PK** | text | |
| security_id FK | text | |
| trigger_type | enum | `scheduled`, `event`, `market_move`, `on_demand`, `session_check`, `user_supplement` |
| trigger_ref | text? | 事件 ID / 异动规则 ID / 请求 ID |
| analysis_as_of | timestamptz | |
| evidence_watermark | timestamptz | 已纳入的最大 `available_at` |
| market_watermark | timestamptz | 已纳入的最新合格报价 `quote_ts` |
| market_state | enum | `pre_market`, `regular`, `post_market`, `closed`, `halted` |
| session_date | date | 适用交易时段 |
| last_quote_id FK→reference_quotes | text? | |
| benchmark_version_id FK | text | |
| day_return_pct / day_relative_pp | numeric? | 相对前收 |
| event_analysis_ids | text[] | 可为空数组（无新消息日） |
| new_catalyst_found | bool | |
| explanation_status | enum | `supported`, `partial`, `insufficient` |
| explanation_summary | text | 无新闻："监测来源范围内暂未发现新催化剂" |
| data_quality | enum | `ok`, `stale`, `partial`, `failed` |
| run_state | enum | `running`, `complete`, `degraded`, `failed`（对应 PPT "运行状态"）；`degraded` = 有结果但部分来源缺失 |
| quality_issues | jsonb | 例 `[{"source_id":"src_news_a","issue":"latency","lag_s":540}]`，界面逐条显示 |
| last_valid_at | timestamptz? | 最近一次 `data_quality = ok` 的快照时间；当前快照非 ok 时界面显示"最近有效：…" |
| valid_until | timestamptz | 本快照解释的有效期（D-41）：盘中 = 下一次定时快照 + 5 分钟；盘后 = 次日盘前首个快照；过期后界面标"已过期" |
| prediction_readiness | jsonb | |
| dedupe_key | text UQ | `security_id + evidence_watermark + market_watermark(取整至 1s)` 同水位合并 |
| published_at | timestamptz | |

### 3.6 基准

**`benchmark_definitions`**：`benchmark_id PK`（`bm_semis_peer_ex_nvda`、`bm_soxx_ref`）、`kind ∈ {peer_basket, etf_reference}`、`target_security_id?`、`methodology`（`equal_weight_ex_target`）、`missing_rule`（`max_missing_constituents=1; else unavailable`）。

**`benchmark_versions`**

| 字段 | 类型 | 说明 |
|---|---|---|
| benchmark_version_id **PK** | text | `bmv_semis_peer_ex_nvda_v1` |
| benchmark_id FK | text | |
| version | int | UQ `(benchmark_id, version)` |
| effective_from / effective_to | date / date? | |
| constituents | jsonb | `[{"security_id":"sec_amd","weight":0.0909}, …]` |
| sync_tolerance_ms | int | 2000 |
| defined_at | timestamptz | 必须早于首次使用 |

### 3.7 预测目标、预测与结算

**`prediction_targets`**（定义，版本化；一条预测引用一个具体 target 行）

| 字段 | 类型 | 说明 |
|---|---|---|
| target_row_id **PK** | text | `tgt_regular_60m_v1` |
| target_id | enum | `regular_60m`, `regular_60m_move`, `regular_to_close`, `next_regular_session`, `overnight_gap`, `event_outcome` |
| target_definition_version | text | `td-0.2` |
| track | enum | `stock_reaction`, `event_outcome`, `conditional_scenario` |
| classes | text[] | 股价：`["outperform","flat","underperform"]`；事件：例 `["closing_confirmed","termination_confirmed","no_confirmation"]` |
| threshold_rule | jsonb? | 方向目标：`{"type":"vol_scaled","k":0.25,"sigma_model":"sigma-0.1","on_missing_sigma":"abstain"}`（D-09）；`regular_60m_move` 为空 |
| output_kind | enum | `class_probs`（方向）、`quantiles`（`regular_60m_move`：`abs_relative_move_pp` 的 p50/p80/p90）、`scenarios`（事件） |
| window_rule | jsonb | `{start:"first_sync_qualifying_after_publish", duration_min:60, settle_tolerance_s:30, must_end_before_close:true}` |
| min_remaining_min | int? | 至收盘 15 |
| event_id / question / deadline_at / deadline_tz / confirm_sources | | 事件轨道专用 |
| outcome_resolution | jsonb? | 事件轨道（D-39）：`{resolving_milestones[]（例 ["closing","termination"]）, confirm_sources[]（`official_registry`, `company_8k`, `regulator_release`, `court_order`）, min_confirmations:1, decision_body, public_confirmation_rule: "首个官方公开确认时刻", legal_effective_rule: "法律生效时刻（可晚于公开确认）", outcome_conflict_rule: "官方来源冲突 → manual_review"}` |
| no_result_rule | text? | 截止时未出现任何解决里程碑 → 结算为 `no_confirmation`（不是 `unsettleable`）；来源不可核实 → `unsettleable` |
| condition | jsonb? | `conditional_scenario` 专用（D-39）：`{condition_event_id, condition_outcome（例 "termination_confirmed"）, trigger_deadline_at, quote_rule_after_trigger: "触发后首个同步合格报价起算", inner_target_id（例 regular_to_close）}` |
| invalid_rules_version | text | |

**`prediction_runs`**

| 字段 | 类型 | 说明 |
|---|---|---|
| run_id **PK** | text | |
| trigger_type / trigger_ref | enum / text? | 同快照 |
| snapshot_id FK | text | |
| event_analysis_ids | text[] | 锁定的分析版本 |
| feature_snapshot_id | text | Parquet 中特征行的指针 |
| model_version_id / calibration_version | text | |
| baseline_model_version_id | text | 同时生成基线（内部） |
| evidence_gaps | text[] | |
| publish_deadline / published_at | timestamptz | |
| idempotency_key | text UQ | `security + snapshot + target + model` |

**`predictions`**

| 字段 | 类型 | 说明 |
|---|---|---|
| prediction_id **PK** | text | |
| run_id FK / target_row_id FK / security_id FK | text | |
| event_id | text? | 无新闻日为空 |
| status | enum | §5 |
| probabilities | jsonb? | `{outperform:0.38, flat:0.35, underperform:0.27}`；弃预测为空 |
| predicted_class | text? | argmax |
| interval | jsonb? | `{"quantiles":{"p10":-0.35,"p50":0.06,"p90":0.48},"unit":"relative_pp","validated":false}` |
| sigma_hat_pp | numeric? | 发布时对同窗口相对收益标准差的预测（sigma-0.1）；方向目标必填 |
| threshold_pp | numeric? | = k × sigma_hat_pp，发布时计算并锁定 |
| move_quantiles | jsonb? | 仅 `regular_60m_move`：`{"p50":0.31,"p80":0.58,"p90":0.77,"unit":"abs_relative_pp"}` |
| scenarios | jsonb? | 仅事件轨道（0.7.1）：`[{outcome, label, evidence_direction?}]`，`display_tier=scenario_only` 时只给情景不给概率 |
| edge_vs_baseline | numeric? | 模型对基线的预期 Brier 优势（选择性发布用；低于发布阈值 → `abstained/low_edge`，内部阶段只记录不弃） |
| display_tier | enum | `validated_public`, `internal_shadow`, `scenario_only` |
| abstain_reason | enum? | `insufficient_data`, `stale_quote`, `halted`, `benchmark_unavailable`, `conflicting_facts`, `window_insufficient`, `market_closed`, `model_not_validated`, `manual_review`, `low_edge`, `slot_missed` |
| is_primary | bool | 主评分样本 |
| sampling_rule | text | `user_supplement`（用户补充后的增量重跑，单独计分，不进主评分，D-48）, `schedule_slot`（主评分，D-43）, `scheduled_5m`（内部，不进主评分）, `event_first`, `market_move_first`, `on_demand`, `revision` |
| schedule_slot_id / schedule_version / scheduled_for | text? / text? / timestamptz? | 槽位预测专用（§3.7a） |
| supersedes_prediction_id | text? | 修订链 |
| valid_until | timestamptz | 预测有效期（D-41）：= `target_end_at`；条件预测 = `trigger_deadline_at`；事件轨道 = `deadline_at` |
| display_state | enum | 派生（视图计算，不存储）：`current`, `superseded`（有更新版本，旧版灰显并链接新版）, `expired`（now > valid_until 且未结算，标"已过期，待结算"）, `settled` |
| locked | jsonb | `{target_definition_version, quote_rule_version, benchmark_version_id, calendar_version, model_version_id, calibration_version, schema_version, sigma_model_version, sigma_hat_pp, threshold_k, threshold_pp, feature_set_version}`。0.7.1 约定（OQ-03，已确认）：无模型的情景型事件预测 `model_version_id = "scenario_only"`；不适用的字段（`calibration_version`、`sigma_*`、`threshold_*`）为 `null`，但键必须存在 |
| t0_quote_id / t0_benchmark_quote_ids | text? / text[] | 起算 |
| target_end_at | timestamptz? | t0 + 60m 或收盘 |
| published_at | timestamptz | |

约束：`published` 之后 `probabilities`、`locked`、`target_row_id` 由触发器禁止更新。

**`prediction_settlements`**

| 字段 | 类型 | 说明 |
|---|---|---|
| settlement_id **PK** | text | |
| prediction_id FK | text | |
| settlement_version | int | UQ `(prediction_id, settlement_version)` |
| start_quote_id / end_quote_id | text? | |
| benchmark_start/end_quote_ids | text[] | |
| stock_return_pct / benchmark_return_pct / relative_return_pp | numeric? | |
| outcome_class | text? | |
| hit | bool? | 仅 `settled` |
| brier | numeric? | 三类平方差和（方向目标） |
| abs_relative_move_pp | numeric? | `abs(relative_return_pp)`（`regular_60m_move`） |
| pinball_loss | jsonb? | 各分位数的 pinball loss（`regular_60m_move`） |
| quantile_hits | jsonb? | 例 `{"p80":true,"p90":true}`，用于实测覆盖率 |
| event_outcome / settlement_evidence_ids | text? / text[] | 事件轨道 |
| public_confirmation_at / legal_effective_at | timestamptz? | 事件轨道：两者分别记录；报表默认按 `public_confirmation_at` 判定是否在截止前（D-39） |
| triggered / triggered_at | bool? / timestamptz? | 条件预测：未触发 → 状态 `not_triggered`，不计入命中率，单独计 `trigger_rate` |
| invalid_reason | enum? | `no_sync_start_quote`, `no_sync_end_quote`, `halted`, `benchmark_unavailable`, `corporate_action`, `source_unverifiable` |
| settled_at | timestamptz | |
| is_reporting_version | bool | 报表使用哪一版 |
| reason_text | text | 人读结算理由 |

### 3.7a 每日预测时刻表与预测—实际对照（D-43、D-44）

**`forecast_schedules`**（版本化；`schedule_version = sched-0.1`）

| 字段 | 类型 | 说明 |
|---|---|---|
| schedule_id **PK** | text | `sched_us_regular_v1` |
| schedule_version | text | `sched-0.1` |
| effective_from / effective_to | date / date? | |
| slots | jsonb | 见下表 |
| half_day_rule | jsonb | `{skip_if_window_exceeds_close: true, to_close_moves_to: "last_60m_slot", post_close_outlook_offset_min: 30}` |
| holiday_rule | text | `skip_all`（休市日不发；上一交易日 16:30 展望覆盖下一交易时段） |
| miss_rule | jsonb | `{grace_s: 180, on_miss: "abstained/slot_missed"}`：槽位时刻 + 180s 内未发布 → 记为弃预测，不补发 |

`sched-0.1` 槽位（美东时间，正常交易日）：

| slot_id | 时间 ET | 种类 | 目标 | 起算 |
|---|---|---|---|---|
| `s0830_pre_open` | 08:30 | 盘前展望 | `next_regular_session`（当日时段） | 不早于 09:31:00 的首组同步合格报价（D-10） |
| `s1000` | 10:00 | 盘中 | `regular_60m` + `regular_60m_move` | 发布后首组同步合格报价 |
| `s1130` | 11:30 | 盘中 | `regular_60m` + `regular_60m_move` | 同上 |
| `s1300` | 13:00 | 盘中 | `regular_60m` + `regular_60m_move` | 同上 |
| `s1430` | 14:30 | 盘中 | `regular_60m` + `regular_60m_move` + `regular_to_close` | 同上；至收盘结算用官方收盘价（D-11） |
| `s1630_next` | 16:30 | 盘后展望 | `next_regular_session`（下一交易时段） | 同 `s0830_pre_open` |

半日市（13:00 收盘）：`s1000`、`s1130` 照常；`s1130` 另加 `regular_to_close`；`s1300`、`s1430` 跳过（窗口超过收盘，记 `not_scheduled`，不算弃预测）；`s1630_next` 改为 13:30。DST 切换由日历按 ET 计算，存储一律 UTC。

**槽位预测字段**（`predictions` 增列）：`schedule_slot_id text?`（例 `s1000`）、`schedule_version text?`、`scheduled_for timestamptz?`（槽位时刻 UTC）。槽位预测 `sampling_rule = 'schedule_slot'` 且 `is_primary = true`；事件/异动触发与按需预测保持各自 `sampling_rule`，单独分组评分（D-23 修订）。

**`forecast_vs_actual`**（物化视图，结算后刷新；每条已发布预测一行）

| 字段 | 类型 | 说明 |
|---|---|---|
| prediction_id **PK** | text | |
| security_id / session_date / target_id / schedule_slot_id | | |
| t0_at / target_end_at | timestamptz | 起算报价时间、目标终点 |
| forecast_path | jsonb | `{"method":"sqrt_time_v1","unit":"relative_pp","points":[{"min":0,"p10":0,"p50":0,"p90":0},…,{"min":60,"p10":-0.38,"p50":0.04,"p90":0.47}]}`：只用于展示的路径；终点 = 发布时锁定的分位数，中间点按 √(t/T) 缩放，**不是**多时间点模型 |
| actual_path | jsonb | `[{"min":0,"relative_pp":0},…]`：起算后每分钟同步合格报价的相对篮子收益；只含 `available_at ≤ now` 的点 |
| status | enum | 同 `predictions.status` |
| outcome_class / hit / brier | | 来自报表版结算（`is_reporting_version`） |
| inside_p80 / inside_p90 | bool? | 实际相对收益是否落在对应区间 |
| residual_pp | numeric? | `relative_return_pp − forecast p50` |
| abs_move_error_pp | numeric? | `regular_60m_move`：`abs_relative_move_pp − move p50` |

**`forecast_accuracy_rollups`**（每次结算批次后增量更新）

| 字段 | 类型 | 说明 |
|---|---|---|
| (security_id, target_id, group_key, window) **PK** | | `group_key`：`all`、`slot:s1000`…；`window ∈ {session, rolling_20d, rolling_60d, since_live}` |
| n_published / n_settled / n_abstained / n_unsettleable | int | 分母公开 |
| hit_rate / brier / bss_class_frequency | numeric? | `n_settled < 30` 时界面标"样本不足"，只显示计数 |
| coverage_p80 / coverage_p90 / mean_interval_width_pp | numeric? | |
| mean_residual_pp / mean_abs_residual_pp | numeric? | 偏差与误差幅度 |
| calibration_bins | jsonb | `[{"p_low":0.3,"p_high":0.4,"n":41,"observed":0.37}, …]` |
| model_version_ids | text[] | 窗口内涉及的模型版本（换版后另起 `since_live`） |
| computed_at | timestamptz | |

规则：对照数据**只读**，不得回写或修改任何已发布预测；它们进入训练只通过下一版 `training_dataset_versions`（D-22 每周检查、D-19 切分），见 MP §7.1。

### 3.8 训练与部署

| 表 | 关键字段 |
|---|---|
| `training_dataset_versions` | `dataset_version_id PK`、`target_id`、`feature_set_version`、`label_version`、`source_versions jsonb`、`time_range {start,end}`、`splits [{name: train|calibration|validation|holdout, start, end, embargo_days}]`、`availability_check_passed bool`、`n_rows`、`n_trading_days`、`n_event_clusters`、`class_balance jsonb`、`exclusions jsonb {reason: count}`、`parent_dataset_version_id?`、`manifest_path`、`created_at` |
| `training_runs` | `training_run_id PK`、`dataset_version_id FK`、`trigger ∈ {scheduled_weekly, manual, drift}`、`parent_model_version_id?`、`code_version`（git sha）、`config_hash`、`random_seed`、`status`（§5）、`stage`、`started_at/finished_at`、`error {code,message}?`、`artifact_paths jsonb`、`idempotency_key UQ` |
| `training_run_metrics` | `(training_run_id, seq) PK`、`stage`、`iteration int?`、`subset ∈ {train, calibration, validation, holdout, shadow}`、`target_id`、`group_key`（`all`、`security:sec_nvda`、`trigger:event`…）、`metric ∈ {log_loss, brier, brier_skill_score, hit_rate, coverage, ece, n_effective, pinball_loss, interval_coverage, interval_width, trigger_rate}`、`reference_model ∈ {class_frequency, always_flat, persistence, har_vol}?`（BSS 与 pinball 对照用，D-30）、`ci95_low?`、`ci95_high?`（按交易日分块 bootstrap，2,000 次）、`value`、`denominator`、`recorded_at` |
| `model_versions` | `model_version_id PK`、`training_run_id FK`、`target_id`、`model_family ∈ {class_frequency, always_flat, persistence, har_vol, market_logit, market_event_logit, gbdt, two_stage}`、`param_layers ∈ {market, market_sector, market_sector_company}`、`scope {securities[], sectors[]}`、`features text[]`、`hyperparams jsonb`、`coefficients_path`、`calibration_version`、`publish_threshold jsonb`、`artifact_sha256`、`status`（§5） |
| `model_evaluations` | `evaluation_id PK`、`candidate_model_version_id`、`comparator_model_version_id`、`eval_subset`、`common_coverage {n_eligible, n_candidate, n_comparator, n_common}`、`metrics jsonb`（每项含 candidate/comparator/paired_diff/ci95）、`n_independent_days`、`n_event_clusters`、`gate_config_version`、`gate_result ∈ {pass, fail, inconclusive}`、`failed_conditions text[]` |
| `model_deployments` | `deployment_id PK`、`target_id`、`scope`、`from_model_version_id?`、`to_model_version_id`、`approved_by`、`approval_note`、`effective_at`、`audience ∈ {internal, selected_v1, selected_v2, selected_v3}`（D-33）、`slices jsonb?`（v2 起只对通过的切片开放）、`state ∈ {active, rolled_back, superseded}`、`rollback_reason?` |
| `extraction_eval_runs` | `eval_run_id PK`、`label_set_version`（约 300 份标注文档）、`llm_provider`、`llm_model`、`prompt_version`、`field_group ∈ {numeric_fact, direction, scope, certainty}`、`precision`、`recall`、`f1`、`n_docs`、`passed bool`（D-32 门槛）、`created_at`。`prompt_version` 未通过不得用于特征 |

### 3.9 任务队列

**`jobs`**：`job_id PK`、`job_type ∈ {ingest_doc, analyze_event, build_snapshot, run_forecast, settle_due, replay_day, build_dataset, train, evaluate, shadow_score, pipeline_step, onboarding_step, source_healthcheck}`、`pipeline_run_id?`、`onboarding_id?`、`payload jsonb`、`idempotency_key UQ`、`status ∈ {queued, running, succeeded, failed, retry_wait, dead}`、`attempts`、`max_attempts=5`、`run_after`（指数退避 2^n × 15s）、`locked_by`、`locked_at`、`last_error`。消费：`SELECT … FOR UPDATE SKIP LOCKED`；锁超时 5 分钟回收。

### 3.10 运营：一键流水线、新公司接入、数据源健康、告警

**`pipeline_runs`**（用户点击"运行"或定时/事件触发的一次端到端运行：采集 → 核验 → 分析 → 快照 → 交接 → 推断 → 发布 → 排程结算）

| 字段 | 类型 | 说明 |
|---|---|---|
| pipeline_run_id **PK** | text | `pr_…` |
| security_ids | text[] | 一次可选多只（默认单只） |
| target_ids | text[] | 例 `["regular_60m","regular_60m_move","regular_to_close"]` |
| trigger_type | enum | `on_demand`（用户点击）, `scheduled`, `event`, `market_move`, `user_supplement` |
| requested_by | text? | 用户 ID（`on_demand`） |
| mode | enum | `live`（实时）, `replay`（指定历史时点 `as_of`，只读当时可得数据）, `dry_run`（不发布，只出报告）, `supplement`（D-48 增量补充：复用 `base_run_id` 的采集结果，只做行情快速刷新 + 自基准水位以来的增量采集 + 用户条目，然后重跑分析、快照、推断与发布） |
| base_run_id / submission_ids | text? / text[] | 仅 `supplement`：在哪次运行基础上补充、带入哪些用户提交 |
| as_of | timestamptz | live 为请求时刻 |
| status | enum | `queued`, `running`, `succeeded`, `partial`（部分证券/目标弃预测）, `failed`, `cancelled` |
| reuse_policy | enum | `reuse_if_unchanged`（默认：输入水位无实质变化 → 复用有效快照与预测，S3§2）, `force_recompute`（`researcher+`，结果标 `sampling_rule=on_demand`，不进主评分） |
| outputs | jsonb | `{snapshot_ids[], prediction_ids[], abstained[{security_id,target_id,reason}], reused bool}` |
| started_at / finished_at | timestamptz | |
| sla_ms | int | 目标：live 单只 p95 ≤ 90s（不含等待起算报价） |
| idempotency_key | text UQ | `security_ids + target_ids + as_of(取整到 1 分钟) + mode + requested_by` |

**`pipeline_run_steps`**：`(pipeline_run_id, step_no) PK`、`step ∈ {collect_evidence, verify_dedupe, analyze_events, build_snapshot, readiness_check, infer, publish, schedule_settlement}`、`security_id`、`status ∈ {pending, running, succeeded, skipped, failed, retry_wait}`、`attempt`、`started_at`、`finished_at`、`detail jsonb`（例：新证据数、合并数、已发布版本、弃预测原因；`collect_evidence` 步骤写 `collection_run_id` 与 `counts`，`analyze_events`/`build_snapshot` 写 `analysis_ids` 与 `snapshot_id`，界面据此串起 ① 采集 → ② 分析 → ③ 预测）、`error {code,message}?`、`job_id FK→jobs`。步骤失败按 jobs 退避重试；超过上限 → 整体 `failed` 或 `partial`，已发布的部分保持不可覆盖。

**`onboarding_requests`**（新公司接入工作流）

| 字段 | 类型 | 说明 |
|---|---|---|
| onboarding_id **PK** | text | `onb_…` |
| ticker / cik / primary_exchange | text | 输入后自动解析，生成 `companies`/`securities` 草稿 |
| requested_by / approved_by | text | |
| target_tier | enum | `pilot`, `batch2`, `peer_only`, `reference` |
| stage | enum | `draft → profile_review → sources_configured → backfilling → data_validated → training → shadow → active`；分支 `blocked`、`rejected`、`paused` |
| checklist | jsonb | 每项 `{item, status ∈ {todo, done, failed, waived}, evidence}`：标识解析、公司档案（指标/敞口/监管机构）、基准篮子版本（剔除自身）、事件来源（SEC/IR/新闻/政策）、历史行情回填与覆盖率、新闻时间精度审计、事件回填与 LLM 提取抽检、训练数据集版本、市场+行业层模型评估、影子 ≥ N 日、审批 |
| backfill_report | jsonb | `{years, coverage_pct, qualifying_quote_pct, sync_success_pct, news_time_known_pct}` |
| param_policy | enum | `market_sector_only`（默认：新公司先用市场+行业参数，S3§8.2）, `company_offset_candidate`（仅当公司层在留出与影子中通过） |
| profile_version_id / benchmark_version_id / dataset_version_id / model_version_id | text? | 每步产物引用 |
| blocked_reason | text? | |

**`data_source_health`**：`(source_id, checked_at) PK`、`status ∈ {healthy, degraded, down}`、`latency_p50_ms`、`latency_p95_ms`、`last_success_at`、`error_rate_1h`、`license_scope`、`verification_status`、`note`。

**`alerts`**：`alert_id PK`、`severity ∈ {info, warning, critical}`、`kind ∈ {source_down, source_latency, quote_stale, pipeline_failed, settlement_backlog, drift, gate_regression, onboarding_blocked}`、`ref`、`opened_at`、`acknowledged_by?`、`resolved_at?`、`message`。

---

## 4. 校验与错误处理

| 校验 | 失败处理 |
|---|---|
| 概率和 ≠ 1 | 拒绝发布，`VALIDATION_FAILED` |
| `published_at` 不在交易日历的正常时段且目标为盘中 | `abstained / market_closed` |
| t0 + 60m + 30s > 收盘 | 不发布 60m，`abstained / window_insufficient`（仍可发至收盘） |
| 起算报价与篮子任一成分时差 > 2s，或缺失成分 > 1 | 等待至 30s；仍无 → `unsettleable / no_sync_start_quote` |
| 快照引用的分析版本 `published_at > analysis_as_of` | 拒绝（时间穿越），`TIME_TRAVEL` |
| 回放读取 `available_at > T` | 抛错并终止回放任务 |
| 同一事件被两个 worker 并发更新 | 乐观锁失败方重新读取；若其输入水位更旧则丢弃 |
| 来源更正 | 新 `source_document_versions` → 新分析版本；已发布预测不改，结算若受影响生成新 `settlement_version` 并标 `is_reporting_version` |
| 行情迟到 | 结算任务执行时未到达的报价不使用；若后来到达且改变结果，生成新结算版本，报表默认仍用首版并记录差异 |
| 疑似泄露/授权不明 | `visibility = restricted_review`，从公开 API 与特征中排除 |

---

## 5. 状态转换

**预测 `predictions.status`**

```
pending_evaluation ──(通过放行)──► published ──► awaiting_settlement ──(到期取得报价)──► settled
        │                            │                     └──────────(无合格报价/停牌)──► unsettleable
        │                            └──(条件情景)──► awaiting_trigger ──(触发)──► awaiting_settlement
        │                                                     └──(期限内未触发)──► not_triggered
        └──(不满足条件)──► abstained
```

用户端显示映射：`settled`=已结算、`awaiting_settlement`=待结算、`abstained/market_closed`=休市、`abstained/insufficient_data`=数据不足、`unsettleable`=无法结算、`display_tier=internal_shadow`=模型验证中。

**训练 `training_runs.status`**：`queued → building_dataset → training → calibrating → evaluating → completed`；任意阶段可 `failed`、`cancelled`；重试生成新 `training_run_id` 且 `parent` 指回。

**模型 `model_versions.status`**：`candidate → shadow → pending_approval → live → retired`；分支 `rejected`、`rolled_back`。

**一键流水线 `pipeline_runs.status`**：`queued → running → succeeded | partial | failed`；任意时刻可 `cancelled`（已发布部分保留）。步骤：`pending → running → succeeded | skipped | failed`，`failed` 可进入 `retry_wait → running`。

**新公司接入 `onboarding_requests.stage`**：`draft → profile_review → sources_configured → backfilling → data_validated → training → shadow → active`；任一阶段可 `blocked`（附原因，修复后回到原阶段）或 `rejected`；`active` 后可 `paused`。进入 `active` 前 `checklist` 必须全部 `done` 或经 `admin` 标记 `waived`。

**事件**：`progress_status` `pending → outcome_confirmed → effective` 或 `→ terminated`；`evidence_status` `pending → media_report → primary_confirmed`，任意时刻可 `conflicting` / `retracted`。

---

## 6. API（Next.js Route Handlers，只读 + 入队）

| 方法 路径 | 说明 | 返回 |
|---|---|---|
| `GET /api/securities?tier=pilot` | 监控列表 + 最新快照摘要 | `SecuritySummary[]` |
| `GET /api/securities/{security_id}/snapshot?as_of=` | 最新（或时点）有效快照 | `SecurityStateSnapshot` |
| `POST /api/securities/{security_id}/refresh` | 按需刷新：入队 `build_snapshot(on_demand)`，返回 `202 {job_id}`；有效快照未过期则 `200` 复用 | |
| `GET /api/securities/{id}/predictions?target_id=&status=&limit=` | 预测列表 | `Prediction[]` |
| `GET /api/predictions/{prediction_id}` | 含 run、锁定输入、结算全部版本 | `PredictionDetail` |
| `GET /api/events?security_id=&progress_status=` | 事件列表 | `Event[]` |
| `GET /api/events/{event_id}` | 最新发布版；`?version=n` 读旧版 | `EventDetail` |
| `GET /api/calendar?exchange=XNAS&from=&to=` | 交易时段 | `TradingSession[]` |
| `GET /api/schedule?date=` | 当日槽位（已按半日市/休市展开）与各槽位状态 | `ScheduleDay` |
| `GET /api/securities/{id}/forecast-vs-actual?session_date=&target_id=` | 预测与实际两条曲线 + 当日与滚动准确率 | `{rows: ForecastVsActual[], rollups: ForecastAccuracyRollup[]}` |
| `GET /api/admin/forecast-accuracy?group_by=slot|security|regime&window=` | 后台：按槽位/证券/行情状态的准确率、残差、校准、漂移（`researcher+`） | |
| `GET /api/benchmarks/{benchmark_id}/versions` | 成分与生效日 | |
| `GET /api/admin/training-runs` / `{id}` / `{id}/metrics` | 后台（`researcher+`） | |
| `GET /api/admin/datasets/{a}/diff/{b}` | 快照对比：added/removed/corrected/filtered 计数与样本 | |
| `GET /api/admin/models/{id}/compare/{other}` | 参数对比 | |
| `GET /api/admin/evaluations?candidate=` | 验证总览 | |
| `POST /api/admin/training-runs` | 手动触发（入队） | `202` |
| `POST /api/admin/deployments` | 审批上线（`reviewer`）；`{to_model_version_id, scope, note}` | |
| `POST /api/admin/deployments/{id}/rollback` | 回滚（`reviewer`） | |
| `POST /api/pipeline-runs` | 一键运行：`{security_ids, target_ids, mode, as_of?, reuse_policy?}`；`viewer` 仅可 `live + reuse_if_unchanged` | `202 {pipeline_run_id}`；相同幂等键返回已有运行 |
| `POST /api/securities/{id}/submissions` | 用户补充信息：`{input_kind, url?|text?|file?, user_categories[], user_note}` → 立即返回 `submission_id`，核验异步进行（Realtime 推送状态） | `UserSubmission` |
| `GET /api/submissions/{id}` | 提交与核验详情 | `UserSubmission` |
| `POST /api/pipeline-runs` + `{mode:"supplement", base_run_id, submission_ids}` | "继续分析"：增量补充运行（同一用户同一证券 2 分钟内重复点击返回同一运行） | `PipelineRun` |
| `GET /api/pipeline-runs/{id}` | 运行与步骤进度（前端 Realtime 订阅 `pipeline_run_steps`） | `PipelineRunDetail` |
| `GET /api/securities/{id}/collection?as_of=&channel=&category=&disposition=&q=&cursor=` | 第 1 步：采集汇总（按渠道 × 类别计数）+ 条目长列表（分页，含被去重/排除/待核项） | `{run: CollectionRun, items: CollectionItem[], next_cursor}` |
| `GET /api/snapshots/{snapshot_id}/reasoning` | 第 2 步：推理链与每条陈述的引用，引用展开为证据/报价/采集项 | `{reasoning_trace, market_explanation, refs}` |
| `POST /api/pipeline-runs/{id}/cancel` | 取消（已发布部分保留） | |
| `GET /api/ops/onboarding` / `POST /api/ops/onboarding` | 接入列表 / 新建（`researcher+`）：`{ticker, target_tier}` | `OnboardingRequest` |
| `POST /api/ops/onboarding/{id}/advance` | 推进到下一阶段（校验 checklist）；`/block`、`/waive-item`（`admin`） | |
| `GET /api/ops/sources` | 数据源健康 | `DataSourceHealth[]` |
| `GET /api/ops/jobs?status=` / `GET /api/ops/alerts?open=true` | 队列与告警；`POST /api/ops/alerts/{id}/ack` | |

### 6.1 Python 任务接口（`sr.jobs`）

```python
def build_snapshot(security_id: str, trigger_type: TriggerType, trigger_ref: str | None, as_of: datetime) -> SnapshotId
def run_forecast(snapshot_id: str, target_ids: list[TargetId]) -> list[PredictionId]   # 原子发布
def settle_due(now: datetime) -> SettleReport                                         # 幂等，可重复跑
def replay_day(security_id: str, session_date: date, mode: Literal["archived","simulated"]) -> ReplayReport
def build_dataset(target_id: str, spec: DatasetSpec) -> DatasetVersionId
def train(dataset_version_id: str, model_family: str, param_layers: str, seed: int) -> TrainingRunId
def evaluate(candidate: str, comparator: str, subset: str, gate_config_version: str) -> EvaluationId
def run_pipeline(pipeline_run_id: str) -> PipelineRunResult      # 编排 8 个步骤；每步一个 job，可断点续跑
def advance_onboarding(onboarding_id: str) -> OnboardingStage   # 执行当前阶段的自动任务并校验 checklist
def check_sources(now: datetime) -> list[DataSourceHealth]
```

CLI：`uv run sr replay --security sec_nvda --date 2026-12-01 --target regular_60m`、`uv run sr settle --now …`、`uv run sr train --dataset ds_… --family market_logit`。

---

## 7. 幂等与版本策略汇总

| 场景 | 策略 |
|---|---|
| 重试 | 同 `idempotency_key` 返回已有结果；任务内部按"读水位→计算→条件写入"执行 |
| 重复消息 | 文档：`(doc_id, content_hash)` 唯一；转载：`independent_origin_key` 相同不增加独立来源数 |
| 并发更新 | 父表 `row_version` 乐观锁；发布写入与交接消息同事务 |
| 行情迟到 | 见 §4；结算只用执行时已到达的报价，更正追加版本 |
| 来源更正 | 新文档版本 → 新分析版本；旧版本可回放 |
| 预测修订 | 新 `prediction_id` + `supersedes_prediction_id`，`is_primary=false`（除非是首条合格版） |
| 模型/数据 | 每个训练运行引用不可变 `dataset_version_id`；结算标签更正 → 新数据快照 |

---

## 8. 三个连贯示例（虚构数据，仅示意）

> 所有价格、收益、概率、成绩均为**虚构**，不代表实际行情或验证结果。

### 8.1 普通无消息交易日（NVDA，2026-12-01 周二，`regular_60m`）

```json
{
  "security_state_snapshot": {
    "schema_version": "contract-0.7",
    "snapshot_id": "snap_nvda_20261201_1520",
    "security_id": "sec_nvda",
    "trigger_type": "scheduled",
    "trigger_ref": "sched_5m",
    "analysis_as_of": "2026-12-01T15:20:00.000Z",
    "evidence_watermark": "2026-12-01T15:18:44.000Z",
    "market_watermark": "2026-12-01T15:19:59.000Z",
    "market_state": "regular",
    "session_date": "2026-12-01",
    "benchmark_version_id": "bmv_semis_peer_ex_nvda_v1",
    "day_return_pct": 0.61,
    "day_relative_pp": 0.22,
    "event_analysis_ids": [],
    "new_catalyst_found": false,
    "explanation_status": "partial",
    "explanation_summary": "监测来源范围内暂未发现新催化剂；个股与同行篮子同向上涨，相对 +0.22pp 未找到专属原因。",
    "data_quality": "ok",
    "prediction_readiness": {
      "event_outcome": {"status": "not_applicable", "reason": "no_open_outcome_question"},
      "stock_reaction": {"status": "ready", "reason": "market_inputs_valid", "allowed_models": ["market_baseline"]}
    },
    "published_at": "2026-12-01T15:20:00.600Z"
  },
  "prediction": {
    "prediction_id": "pred_nvda_20261201_1520_60m",
    "run_id": "run_nvda_20261201_1520",
    "target_row_id": "tgt_regular_60m_v1",
    "security_id": "sec_nvda",
    "event_id": null,
    "status": "settled",
    "probabilities": {"outperform": 0.38, "flat": 0.35, "underperform": 0.27},
    "predicted_class": "outperform",
    "interval": {"quantiles": {"p10": -0.35, "p50": 0.06, "p90": 0.48}, "unit": "relative_pp", "validated": false},
    "display_tier": "validated_public",
    "is_primary": true,
    "sampling_rule": "scheduled_5m",
    "sigma_hat_pp": 0.60,
    "threshold_pp": 0.15,
    "edge_vs_baseline": 0.006,
    "locked": {"target_definition_version": "td-0.2", "quote_rule_version": "qr-0.1", "benchmark_version_id": "bmv_semis_peer_ex_nvda_v1", "calendar_version": "cal-2026.11", "model_version_id": "mdl_regular_60m_market_logit_v3", "calibration_version": "cal_iso_v3", "schema_version": "contract-0.7", "sigma_model_version": "sigma-0.1", "sigma_hat_pp": 0.60, "threshold_k": 0.25, "threshold_pp": 0.15, "feature_set_version": "fs-0.2"},
    "published_at": "2026-12-01T15:20:00.800Z",
    "t0_quote_id": "rq_nvda_20261201_152002",
    "target_end_at": "2026-12-01T16:20:02.000Z"
  },
  "settlement": {
    "settlement_id": "stl_nvda_20261201_1520_60m_v1",
    "prediction_id": "pred_nvda_20261201_1520_60m",
    "settlement_version": 1,
    "start_quote_id": "rq_nvda_20261201_152002",
    "end_quote_id": "rq_nvda_20261201_162003",
    "stock_return_pct": 0.42,
    "benchmark_return_pct": 0.18,
    "relative_return_pp": 0.24,
    "outcome_class": "outperform",
    "hit": true,
    "brier": 0.5798,
    "invalid_reason": null,
    "settled_at": "2026-12-01T16:21:00.000Z",
    "is_reporting_version": true,
    "reason_text": "起算 10:20:02 ET 同步合格报价，结算 11:20:03 ET（容差内）。相对 +0.24pp > 阈值 0.25 × σ̂ 0.60pp = 0.15pp → 跑赢。"
  }
}
```

Brier 自检：(1−0.38)² + 0.35² + 0.27² = 0.3844 + 0.1225 + 0.0729 = **0.5798**（实现的单元测试须使用此算例；均匀猜测 1/3 时 Brier = 0.6667）。

同一快照同时发布预期波动目标（共享起算与结算报价）：

```json
{
  "prediction_id": "pred_nvda_20261201_1520_60m_move",
  "target_row_id": "tgt_regular_60m_move_v1",
  "status": "settled",
  "move_quantiles": {"p50": 0.31, "p80": 0.58, "p90": 0.77, "unit": "abs_relative_pp"},
  "display_tier": "internal_shadow",
  "settlement": {
    "abs_relative_move_pp": 0.24,
    "quantile_hits": {"p50": true, "p80": true, "p90": true},
    "pinball_loss": {"p50": 0.035, "p80": 0.068, "p90": 0.053},
    "reason_text": "|+0.24pp| ≤ p50 0.31pp。评分以 pinball loss 与区间实测覆盖率为准。"
  }
}
```

Pinball 自检：分位 τ、预测 q、实际 y，loss = max(τ(y−q), (τ−1)(y−q))。p50：0.5×0.07 = 0.035；p80：0.2×0.34 = 0.068；p90：0.1×0.53 = 0.053。

### 8.2 盘中突发政策事件（2026-12-02 周三，虚构出口规则）

```json
{
  "source_document_version": {
    "doc_version_id": "docv_fr_demo_2026_12345_v1",
    "doc_id": "doc_fr_demo_2026_12345",
    "content_hash": "9f2c…(sha256)",
    "source_published_at": "2026-12-02T15:58:30.000Z",
    "source_published_precision": "s",
    "received_at": "2026-12-02T15:58:41.200Z",
    "available_at": "2026-12-02T15:59:05.000Z",
    "arrival_mode": "live",
    "visibility": "public"
  },
  "event": {
    "event_id": "evt_policy_export_demo_001",
    "category": "policy_export",
    "identity_key": "policy:BIS:demo-2026-12345",
    "progress_status": "effective",
    "evidence_status": "primary_confirmed",
    "analysis_status": "partial",
    "current_analysis_version": 1,
    "row_version": 3
  },
  "event_security_links": [
    {"event_id": "evt_policy_export_demo_001", "security_id": "sec_nvda", "relation": "regulated_party"},
    {"event_id": "evt_policy_export_demo_001", "security_id": "sec_amd", "relation": "regulated_party"},
    {"event_id": "evt_policy_export_demo_001", "security_id": "sec_mu", "relation": "sector_wide"}
  ],
  "event_analysis_version": {
    "analysis_id": "eav_policy_demo_001_nvda_v1",
    "event_id": "evt_policy_export_demo_001",
    "security_id": "sec_nvda",
    "analysis_version": 1,
    "analysis_kind": "flash",
    "analysis_as_of": "2026-12-02T16:00:30.000Z",
    "published_at": "2026-12-02T16:00:41.000Z",
    "market_reaction": {"ref_before_quote_id": "rq_nvda_20261202_155829", "ref_asof_quote_id": "rq_nvda_20261202_160029", "stock_return_pct": -1.90, "benchmark_return_pct": -0.80, "relative_return_pp": -1.10, "missing_reason": null},
    "market_explanation": {
      "status": "partial",
      "observed_facts": ["规则文本于 10:58:30 ET 公开，涉及指定先进计算产品的许可要求（虚构）"],
      "possible_drivers": ["许可范围可能覆盖部分数据中心 GPU 出货（待公司披露确认）"],
      "counter_evidence": ["同行篮子同时下跌 0.80%，部分跌幅属行业共同波动"],
      "unexplained": ["NVDA 与 AMD 相对跌幅差异的原因"],
      "concurrent_events": []
    },
    "prediction_readiness": {
      "event_outcome": {"status": "ready", "reason": "license_question_defined", "analysis_id": "eav_policy_demo_001_nvda_v1"},
      "stock_reaction": {"status": "ready", "reason": "event_enhanced_not_validated_for_policy_export", "allowed_models": ["market_baseline"]}
    }
  },
  "prediction_stock": {
    "prediction_id": "pred_nvda_20261202_1601_60m",
    "target_row_id": "tgt_regular_60m_v1",
    "event_id": "evt_policy_export_demo_001",
    "status": "awaiting_settlement",
    "probabilities": {"outperform": 0.30, "flat": 0.31, "underperform": 0.39},
    "predicted_class": "underperform",
    "display_tier": "validated_public",
    "sampling_rule": "event_first",
    "is_primary": true,
    "published_at": "2026-12-02T16:01:05.000Z",
    "t0_quote_id": "rq_nvda_20261202_160107",
    "target_end_at": "2026-12-02T17:01:07.000Z"
  },
  "prediction_event_outcome": {
    "prediction_id": "pred_evt_policy_demo_001_license",
    "target_row_id": "tgt_event_policy_demo_001_v1",
    "status": "published",
    "probabilities": null,
    "display_tier": "scenario_only",
    "abstain_reason": "model_not_validated",
    "scenarios": [
      {"outcome": "license_confirmed", "label": "截止 2026-12-31 23:59 ET 前公开确认获得许可", "evidence_direction": "unknown"},
      {"outcome": "denial_confirmed", "label": "截止前公开确认被拒"},
      {"outcome": "no_confirmation", "label": "截止前无公开确认"}
    ]
  }
}
```

要点：事件增强模型未对 `policy_export` 独立验证 → 只放行行情基线；事件结果轨道只给情景、不给概率；两者独立结算。

### 8.3 训练候选上线前的对照评估（`regular_60m`）

```json
{
  "training_dataset_version": {
    "dataset_version_id": "ds_regular_60m_20261206_v1",
    "target_id": "regular_60m",
    "feature_set_version": "fs-0.2",
    "label_version": "lbl-0.1",
    "time_range": {"start": "2021-01-04", "end": "2026-12-04"},
    "splits": [
      {"name": "train", "start": "2021-01-04", "end": "2025-06-30", "embargo_days": 1},
      {"name": "calibration", "start": "2025-07-02", "end": "2025-12-31", "embargo_days": 1},
      {"name": "validation", "start": "2026-01-05", "end": "2026-06-30", "embargo_days": 1},
      {"name": "holdout", "start": "2026-07-02", "end": "2026-12-04", "embargo_days": 0}
    ],
    "availability_check_passed": true,
    "n_rows": 1184220,
    "n_trading_days": 1488,
    "n_event_clusters": 412,
    "class_balance": {"outperform": 0.34, "flat": 0.31, "underperform": 0.35},
    "exclusions": {"no_sync_quote": 18210, "news_time_unknown": 3304, "crosses_split_boundary": 9600},
    "parent_dataset_version_id": "ds_regular_60m_20261129_v1"
  },
  "model_evaluation": {
    "evaluation_id": "eval_20261206_event_v1_vs_live_v3",
    "candidate_model_version_id": "mdl_regular_60m_market_event_logit_v1",
    "comparator_model_version_id": "mdl_regular_60m_market_logit_v3",
    "eval_subset": "holdout+shadow",
    "common_coverage": {"n_eligible": 200, "n_candidate": 100, "n_comparator": 180, "n_common": 100},
    "metrics": {
      "hit_rate": {"candidate": 0.58, "comparator": 0.58, "paired_diff": 0.00, "ci95": [-0.06, 0.06]},
      "brier":    {"candidate": 0.641, "comparator": 0.648, "paired_diff": -0.007, "ci95": [-0.019, 0.005]},
      "coverage": {"candidate": 0.50, "comparator": 0.90},
      "brier_skill_score": {"reference_model": "class_frequency", "reference_brier": 0.666, "candidate": 0.038, "comparator": 0.027, "paired_diff": 0.011, "ci95": [-0.008, 0.029]}
    },
    "n_independent_days": 41,
    "n_event_clusters": 9,
    "gate_config_version": "gate-0.1",
    "gate_result": "fail",
    "failed_conditions": ["coverage_drop_gt_10pp", "brier_ci_upper_not_below_0", "holdout_days_lt_60"]
  },
  "model_deployment": null
}
```

要点（对应 S3§8.4 虚构判例）：全量命中率不可直接比较；共同覆盖上持平、覆盖率大降、Brier 改善不显著 → 不批准，线上继续使用 `market_logit_v3`。

---

## 9. 错误码

`VALIDATION_FAILED`、`NOT_FOUND`、`CONFLICT_STALE_VERSION`（乐观锁）、`DUPLICATE_IDEMPOTENCY_KEY`（返回已有）、`TIME_TRAVEL`、`MARKET_CLOSED`、`WINDOW_INSUFFICIENT`、`BENCHMARK_UNAVAILABLE`、`SOURCE_TIMEOUT`、`UPSTREAM_FAILED`、`FORBIDDEN`、`RESTRICTED_CONTENT`。

## 10. 访问控制（RLS）

| 角色 | 可读 | 可写 |
|---|---|---|
| `viewer` | 公开快照、`display_tier ∈ {validated_public, scenario_only}` 的预测、`visibility=public` 证据；自己的 `user_submissions` 及其补充运行结果 | `POST refresh`、`POST submissions`、补充运行 |
| `researcher` | + `internal_shadow`、后台全部只读、`internal` 证据 | 手动训练 |
| `reviewer` | 同上 + 审批 | `model_deployments` |
| `admin` | 全部（含 `restricted_review`） | 配置 |
| service role（Python） | 全部 | 全部（受触发器保护的不可变字段除外） |
