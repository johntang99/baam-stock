# CLAUDE.md · baam-stock 项目规则

每次会话都遵守以下规则。

## 项目
- 项目名 **baam-stock**；用途：美股研究与预测（首批 NVDA、AMD、AVGO、MU；第二批 TSM、MRVL）：**研究与验证**（Phase 0–5），以及门槛通过后用**自有资金**做**系统执行交易**（Phase 6 买卖信号、Phase 7 执行，规则见下方「交易执行」）。仅限内部团队使用，不对外开放，不对第三方提供信号、建议或代客交易；不构成投资建议。
- 设计文档：`docs/BUILDING_MASTER_PLAN.md`（MP，plan-0.7）、`docs/DATA_CONTRACT.md`（DC，contract-0.7.4）、`docs/DEVELOPMENT_PHASES.md`（DP，phases-0.7）、`docs/roadmap/ROADMAP_EXTENSIONS_CN.md`（**roadmap-0.2，当前计划**：6 个月快速路线，Phase 5–7）。roadmap-0.2 与 MP/DP 中"无交易执行""Phase 5–7 仅规划"等说法冲突时，以 roadmap-0.2 为准。`prototype/` 只作 UI 与字段参考，不修改。

## 技术栈
- Next.js（`apps/web`）+ Supabase（Postgres、Auth、RLS、Realtime）+ Python 3.12（`services/py`，包名 `sr`，uv 管理）；pnpm workspace。

## 规则
- **单一事实来源**：`docs/DATA_CONTRACT.md` 与 `packages/contracts/schemas`。字段名、枚举值必须与 DC 完全一致；改契约时先改 DC 和 JSON Schema，并升 `schema_version`（当前 `contract-0.7.4`；Phase 5–7 的新表进入 `contract-1.0`，只追加，不改现有列与枚举含义）。
- **未定事项**一律采用 MP §9 决策表默认值；参数放 `config/*.yaml`，不硬编码；发现矛盾记入 `docs/OPEN_QUESTIONS.md`，不要自行发明语义。
- **时间**：一律存 UTC（`timestamptz`），显示 `America/New_York`；任何涉及时间的函数都要有"读取 as_of 之后的数据即报错"的负向测试。
- **不可覆盖**：预测、分析、结算、数据快照只追加新版本。
- 不接入真实付费 API，不提交任何密钥；需要密钥的适配器只留接口与 `.env.example`。所有示例数据标注 synthetic / 虚构。
- 每个阶段按 DP 的验收用例（AC-xx）写自动化测试；完成定义见 DP「每项任务的完成定义」。改动后更新 `docs/CHANGELOG.md`。
- 窗口长度一律通过 `target_id` 与配置读取，不要写死 60 分钟。

## 交易执行（Phase 6–7，roadmap-0.2）
- **门槛管"开启使用"，不管"编码"**：代码可以提前写完，但每个新功能放在功能开关之后，默认关闭；门槛数值不变。
- **真实下单默认关闭，不写任何自动启用逻辑**（不因门槛达标而自动打开）。开启 7b、7c 或提高额度，须研究员与审核人书面签字后由人手动打开，并写入 `kill_switch_events` / 审计日志；kill switch 触发后的恢复同样只能人工操作。
- **Claude 不得**打开真实下单开关、发送真实订单、提高风控额度或绕过风控与对账；只实现并测试代码与模拟版。
- 交易服务 `services/trader/` 独立部署，使用独立 schema `trading`；只读研究系统发布的信号，不修改任何研究数据。
- 券商经 `BrokerAdapter` 接入：先实现模拟版（paper）；真实券商实现默认关闭。仓库、CI 与开发环境不存放任何券商生产密钥（只留接口与 `.env.example`）。
- 风控在交易服务内强制执行，不依赖研究系统：额度上限、白名单（首批股票与指定 ETF、仅正常交易时段、停牌/LULD 不下单）、数据前提（行情陈旧、质量降级、模型回滚、漂移 → 暂停新开仓）、kill switch（人工 + 自动）、每日对账、全链路不可修改的审计。
- 实时观察期（第 2–4 个月）冻结模型与信号版本，只修 bug、不调参数；改版会让对应时钟重新计时（roadmap §0A.3）。

## 常用命令
```bash
pnpm install                                   # JS 依赖
pnpm -r build                                  # contracts 生成 TS + web 构建
pnpm --filter contracts test                    # examples/*.json 通过 schema 校验
pnpm --filter web test                          # 网页测试（Node 22 内置测试，--experimental-strip-types）
uv sync                                        # Python 依赖（根目录 uv 项目，引用 services/py）
TEST_DATABASE_URL=postgresql://… uv run pytest services/py/tests -q   # Python 测试（含数据库测试）
uv run ruff check . && uv run mypy services/py/sr scripts   # CI 同样检查 scripts/
uv run python scripts/make_fixture.py          # 生成合成 fixture（synthetic）
uv run python scripts/validate_sample.py --fixture data/fixtures/nvda_2026-12-01_1s.parquet
supabase start && supabase db reset            # 迁移 + seed（需 Docker）
make check                                     # 以上检查一次跑完
uv run python scripts/check_labels.py --queue 10   # 标注审核：下一批文档；--keys 自检；--text 取原文
```

## 当前进度
- Phase 0 完成（CI 绿）。**Phase 1 在合成数据上验收通过**（`docs/acceptance/phase1.md`，2026-11-28）；真实数据复验待 D-13 样本（1.01 / 1.02）与 1.18 人工审核 + 付费评估（需批准）。已完成 DP 1.03–1.17、1.19、1.21–1.28（历史类比、证据入库、LLM 接口、事件与版本、财报提取与预期对比、政策事件模板、市场反应与当前解释、证券快照与同水位合并、数据集构建、首次训练与校准、HAR 波动基线与分位数模型、推断与原子发布（契约 contract-0.7.3：`model_versions` 建表）、结算与版本追加、一键运行编排与 `sr run` CLI、日回放与逐条核验报告（`sr replay` / `sr report`）、只读回放网页 `/replay`、运行状态与 display_state 视图、估值背景（只进解释）、场景测试 AC-39～41、公司行为与复权结算、时刻表回放与预测—实际对照（contract-0.7.4）（均为合成数据）、采集记录、推理链与引用校验）。常规默认值由 Claude 自行决定并记入 OPEN_QUESTIONS（用户 2026-11-28 授权），付费调用与真实资金仍需用户批准。1.18：语料 357 份（SEC 291、Federal Register 政策 40、公司新闻稿 26，OQ-41）；全部已有 Claude（extract-0.3）草稿、核对规则 earnings-0.5（OQ-39、OQ-42）、审核指南 `docs/labeling/extraction-v0.md` 与 `scripts/check_labels.py` 已就绪，**等待人工审核满 100 份**后跑评估（付费，需批准）；第三方新闻待 D-15 授权。
- **编码顺序（roadmap-0.2 快速路线，2026-11-28 起）**：不再等 D-13，行情相关任务先用合成 fixture（synthetic）实现与测试，供应商样本到后只换 `MarketDataProvider` 实现并重跑验收。
  1. Phase 1：开发项全部完成（合成数据）；1.01 / 1.02 待 D-13 样本，1.18 待审核；真实数据到位后重跑 `docs/acceptance/phase1.md`。
  2. DP Phase 2、Phase 3（合成数据）。
  3. 契约升 `contract-1.0`（只追加）→ Phase 5 中期目标（`sr/horizon/`）→ Phase 6 信号定义、含成本回测、模拟盘（`sr/signals/`、`sr/backtest/`）→ Phase 7 `services/trader/` + `trading` schema：模拟版 `BrokerAdapter`、风控、对账、审计、kill switch（真实下单默认关闭）。
  - 需要用户并行推进：D-13 行情样本（含历史 NBBO 与 ≥ 10 年日线）、D-15 新闻授权、D-16 共识数据、券商候选与模拟账户、法律 / 税务 / 内部授权确认。
- 数据库测试：设置 `TEST_DATABASE_URL`（管理员连接串，测试会建临时库）后运行 pytest；CI 自带 postgres:17。
