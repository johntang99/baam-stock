# baam-stock · 开工说明与 Claude Code 首轮指令

2026-11-26 · 对应设计包 plan-0.7 / contract-0.7 / phases-0.7

---

## 1. 可以开始写代码了吗？

**可以开始 Phase 0。现在还不能完整进入 Phase 1。**

Phase 0 的设计就是"不依赖外部数据也能做完"：仓库骨架、契约（JSON Schema + 数据库迁移）、交易日历与时刻表、合格报价与篮子规则、阈值与评分函数、特征纯函数，全部用**合成数据**测试。设计文档里该有的都有了：字段表、状态、接口、决策表 D-01～D-48、验收用例 AC-01～AC-61、工作分解。

| 事项 | 状态 | 影响 |
|---|---|---|
| 设计文档（MP / DC / DP）与原型 | ✅ 齐全，版本互相一致（0.7） | — |
| 决策表中的 `proposed` 默认值（例：NBBO 中间价 D-05、同步容差 2s D-06、结算容差 30s D-07、同行篮子 D-08、阈值 k=0.25 D-09、合格报价规则 D-12） | ⚠️ 尚未由你正式确认 | **不阻塞 Phase 0**：全部写进 `config/*.yaml` 和 `config/decisions.yaml`，以后改配置即可。最好在 Phase 1 开始前确认一次 |
| 每日时刻表 D-43、预测对照 D-44、用户补充 D-47/D-48 | ✅ 你已在本轮对话中提出并认可方向 | — |
| 行情供应商（D-13：秒级 NBBO 历史与实时、官方收盘价） | ❌ 未选定、未拿到样本 | **阻塞 Phase 1** 的真实回填与回放。Phase 0 只留接口与样本验证脚本 |
| 新闻快讯授权（D-15）、共识预期（D-16） | ❌ 未选定 | 阻塞 Phase 1 的事件与财报部分（SEC、IR、Federal Register 是免费的，可先做） |
| LLM API 密钥（D-25） | ❌ 未配置 | 阻塞 Phase 1 的提取与解释（Phase 0 不调用 LLM） |
| Supabase 项目、GitHub 仓库 | ❌ 未建 | Phase 0 只用本地 `supabase start`；CI 在你建好 GitHub 仓库后生效 |
| 上线门槛 D-21 | ⚠️ 待定 | Phase 3 之前确认即可 |

**建议顺序**：现在让 Claude Code 做 Phase 0（约 26 人日，Claude Code 辅助下通常更快）；同时你这边按 `business/DATA_COST_COMPARISON.md` 选行情供应商并申请样本数据，配置 LLM 密钥。Phase 0 结束时用真实样本跑一次 `scripts/validate_sample.py`，再进入 Phase 1。

---

## 2. 你先做的准备（约 15 分钟）

1. 本机安装：Node.js 20+、pnpm 9+、Python 3.12、[uv](https://docs.astral.sh/uv/)、Docker Desktop（本地 Supabase 需要）、Supabase CLI、Git。
2. 创建项目根目录 `clients/baam-stock/`，在里面 `git init`。
3. 把设计包 `stock-forecast-design.zip` 解压到 `clients/baam-stock/_design_package/`，解压后应看到 `clients/baam-stock/_design_package/stock-forecast-design/BUILDING_MASTER_PLAN.md`。
4. 用 VS Code 打开 `clients/baam-stock/`，启动 Claude Code。
5. 把下面第 3 节代码块里的全部内容粘贴给 Claude Code。

---

## 3. 粘贴给 Claude Code 的首轮指令

```text
你是 baam-stock 项目的实现工程师。当前工作目录就是项目根目录 clients/baam-stock/。
这是一个美股短期研究与预测系统（只做研究与验证，不接入任何交易执行）。设计包已解压在 _design_package/stock-forecast-design/。
本轮只做「准备 + Phase 0」，不要开始 Phase 1 的任何功能。

== 第 0 步：放置设计文档 ==
1. 把 _design_package/stock-forecast-design/ 下的 BUILDING_MASTER_PLAN.md、DATA_CONTRACT.md、DEVELOPMENT_PHASES.md、
   MODEL_IMPROVEMENT_MEMO.md、USER_GUIDE.md、PPT_COVERAGE_REVIEW.md、README.md、CLAUDE_CODE_START.md 复制到 docs/；
   business/ 复制到 docs/business/；prototype/ 复制到项目根目录 prototype/（只作 UI 与字段参考，不修改）。
2. 把 _design_package/ 加入 .gitignore（不提交压缩包和重复副本）。
3. 完整阅读 docs/BUILDING_MASTER_PLAN.md、docs/DATA_CONTRACT.md、docs/DEVELOPMENT_PHASES.md（以下简称 MP / DC / DP），
   重点：MP §6 目录、§9 决策表；DC §1–§5、§3.7a；DP「总览」「Phase 0」「附录 A Phase 0」「首轮 Claude Code 执行指令」。
   MP §6 里的根目录名 stock-research/ 在本项目中就是当前目录 clients/baam-stock/。

== 第 1 步：创建 CLAUDE.md（项目根目录）==
写入以下项目规则（中文，简洁），以后每次会话都遵守：
- 项目名 baam-stock；用途：美股短期研究与预测（首批 NVDA、AMD、AVGO、MU；第二批 TSM、MRVL），研究与验证用途，不做交易执行。
- 技术栈：Next.js（apps/web）+ Supabase（Postgres、Auth、RLS、Realtime）+ Python 3.12（services/py，包名 sr，uv 管理）；pnpm workspace。
- 单一事实来源：docs/DATA_CONTRACT.md 与 packages/contracts/schemas。字段名、枚举值必须与 DC 完全一致；
  需要改契约时先改 DC 和 JSON Schema，并升 schema_version（当前 contract-0.7）。
- 未定事项一律采用 MP §9 决策表的默认值，参数放 config/*.yaml，不硬编码；发现矛盾记入 docs/OPEN_QUESTIONS.md，不要自行发明语义。
- 时间：一律存 UTC（timestamptz），显示 America/New_York；任何涉及时间的函数都要有"读取 as_of 之后的数据即报错"的负向测试。
- 不可覆盖：预测、分析、结算、数据快照只追加新版本。
- 不接入真实付费 API，不提交任何密钥；需要密钥的适配器只留接口与 .env.example。所有示例数据标注 synthetic / 虚构。
- 每个阶段按 DP 的验收用例（AC-xx）写自动化测试；完成定义见 DP「每项任务的完成定义」。
- 常用命令（随实现补全）：pnpm install、pnpm -r build、supabase start、supabase db reset、uv run pytest services/py/tests -q。
- 当前进度：Phase 0。下一阶段开始前，由人确认决策表与数据供应商。

== 第 2 步：实现 Phase 0（范围以 DP「首轮 Claude Code 执行指令」为准，摘要如下）==
1. monorepo 骨架（MP §6）：pnpm workspace（apps/web 只放 Next.js 空壳首页）、packages/contracts、services/py（uv，包名 sr）、
   supabase/、config/、scripts/、data/（gitignore）、docs/。
2. packages/contracts：按 DC 写 JSON Schema（schema_version="contract-0.7"）：companies、securities、security_identifiers、
   corporate_actions、industry_templates、company_profile_versions（含 industry_template）、forecast_schedules（seed sched-0.1）、
   collection_runs、collection_items、user_submissions、trading_sessions、reference_quotes、benchmark_definitions、benchmark_versions、
   security_state_snapshots（含 run_state、quality_issues、last_valid_at、valid_until）、prediction_targets、prediction_runs、
   predictions（含 schedule_slot_id、valid_until）、prediction_settlements、training_dataset_versions、training_runs、training_run_metrics、
   extraction_eval_runs、pipeline_runs、pipeline_run_steps、onboarding_requests、data_source_health、alerts；
   macro_releases、insider_transactions、docket_entries、options_snapshots 只写 Schema 不建表。
   把 DC §8 的示例拆成 examples/*.json 并全部通过校验；生成 TS 类型与 pydantic 模型。
3. supabase/migrations/0001_core.sql（及必要的后续迁移）：上述建表实体的表、enum、主键/唯一约束、外键；
   predictions 发布后禁止修改 probabilities/locked/target_row_id 的触发器；jobs 表（DC §3.9）。
   seed：4 只 pilot + 2 只 batch2 + 篮子其余成分（peer_only）、每只 pilot 的 bm_semis_peer_ex_<ticker> v1（D-08 等权剔除自身）、
   bm_soxx_ref、参考品种 QQQ/SPY/SMH/^VIX（coverage_tier='reference'）、目标定义 td-0.2（regular_60m、regular_60m_move、
   regular_to_close、next_regular_session）、industry_template=semiconductor、时刻表 sched-0.1。
4. services/py/sr/calendar：exchange_calendars XNYS + config/calendar_overrides.yaml；session(date)、
   is_target_available(target_id, published_at)、next_regular_session(published_at)、schedule_slots(date)（D-04、D-10、D-18、D-43）。
5. services/py/sr/marketdata：quote_rules.py（D-05、D-06、D-12，读 config/quote_rules.yaml，qr-0.1）、
   sync.py（find_first_sync_qualifying(after_ts, security, basket, tolerance_ms=2000, max_wait_s=30)）、
   providers/base.py（MarketDataProvider 接口，MP §3.2）、providers/fixture.py（读 Parquet）；
   sr/benchmark/basket.py（等权篮子收益，max_missing_constituents=1）。
6. sr/labels：sigma.py（sigma-0.1）、thresholds.py（threshold_pp = k × sigma_hat_pp，边界值判 flat；sigma 缺失 → insufficient_data）。
   sr/eval：metrics.py（三分类 Brier、命中率、BSS 三条参照、pinball loss；DC §8.1 算例 Brier 0.5798，pinball 0.035/0.068/0.053）、
   bootstrap.py（按交易日分块，固定 seed，2,000 次）。
7. config/features/fs-0.2.yaml 与 sr/features/*：D-31 的特征纯函数（只读 ts ≤ as_of），只做单元测试，不训练模型。
8. scripts/make_fixture.py（合成 NVDA + 11 个篮子成分，2026-12-01 09:30–16:00 ET 秒级 NBBO，含一段宽价差、一次 3 分钟停牌，标注 synthetic）；
   scripts/validate_sample.py（覆盖率、合格率、同步成功率报告；以后用真实供应商样本再跑）。
9. docs/data_procurement.md：D-13、D-15、D-16 的供应商对比模板，参考 docs/business/DATA_COST_COMPARISON.md，
   全部标「拟选/未验证」，不要编造价格或授权条款。
10. config/decisions.yaml：MP §9 决策表 D-01～D-48 的机器可读镜像（含状态 proposed / from_spec / to_verify）。
11. 基础设施：GitHub Actions CI（ruff、mypy、pytest、tsc、eslint、契约示例校验、迁移重放）、pre-commit、.env.example、
    docs/CHANGELOG.md、docs/OPEN_QUESTIONS.md。

== 验收（DP Phase 0：AC-01～AC-05、AC-26，AC-28 / AC-29 / AC-52 的 P0 部分）==
- supabase db reset 成功；uv run pytest 全绿；pnpm -r build 成功；contracts examples 全部通过校验。
- 测试必须覆盖：2026-11-26 休市；2026-11-27 与 2026-12-24 半日市 13:00 ET；DST 切换；14:59:00 vs 14:59:45 ET 的 60m 可用性；
  15:44 / 15:46 ET 的至收盘可用性；半日市 12:30 发布 60m 不可用；周六发布的下一时段；2026-12-01（6 个槽位）与 2026-11-27（半日市）的槽位展开；
  宽价差 / 停牌 / 陈旧报价；30s 内无同步报价；缺 2 个成分的篮子；阈值边界（+0.15pp 判 flat）；sigma 缺失弃预测；
  sigma 与特征函数读取未来数据时报错；BSS 与 pinball 算例；bootstrap 固定 seed 可复现。

== 工作方式 ==
- 先输出一份简短计划（按 DP 附录 A 的 0.01～0.17 排序），然后直接开始实现，不需要等我确认。
- 每完成一组任务就本地 git commit（信息写清任务编号，如 "P0 0.06 calendar + windows"）；不要 push，不要创建远程仓库。
- 不实现 LLM 调用、事件分析、预测模型、训练或页面（这些是 Phase 1+）。
- 遇到 DC 与 MP 矛盾或缺字段：记入 docs/OPEN_QUESTIONS.md，采用决策表默认值继续。
- 需要我做的事（安装软件、Docker 未启动、需要账号）直接停下来告诉我。

== 完成后输出 ==
1. 变更文件清单（按目录）；
2. 每条验收用例的命令与结果（通过 / 失败及原因）；
3. docs/OPEN_QUESTIONS.md 摘要；
4. 进入 Phase 1 之前需要我确认或提供的事项（决策表中仍为 proposed 的关键项、行情供应商样本、LLM 密钥等）。
```

---

## 4. Phase 0 之后

- 把 Claude Code 的验收结果和 `docs/OPEN_QUESTIONS.md` 发回这里，我们一起确认决策表并处理问题。
- 拿到行情供应商样本后：`uv run python scripts/validate_sample.py --fixture <样本文件>`，看合格率和同步成功率是否满足 D-35 的门槛。
- Phase 1 起，每个阶段开始时使用 `docs/DEVELOPMENT_PHASES.md` 附录 C 的指令模板（每阶段拆 2–4 次会话）。
