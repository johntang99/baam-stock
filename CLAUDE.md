# CLAUDE.md · baam-stock 项目规则

每次会话都遵守以下规则。

## 项目
- 项目名 **baam-stock**；用途：美股短期研究与预测（首批 NVDA、AMD、AVGO、MU；第二批 TSM、MRVL）。**仅研究与验证，不做交易执行**，不构成投资建议。
- 设计文档：`docs/BUILDING_MASTER_PLAN.md`（MP，plan-0.7）、`docs/DATA_CONTRACT.md`（DC，contract-0.7）、`docs/DEVELOPMENT_PHASES.md`（DP，phases-0.7）。`prototype/` 只作 UI 与字段参考，不修改。

## 技术栈
- Next.js（`apps/web`）+ Supabase（Postgres、Auth、RLS、Realtime）+ Python 3.12（`services/py`，包名 `sr`，uv 管理）；pnpm workspace。

## 规则
- **单一事实来源**：`docs/DATA_CONTRACT.md` 与 `packages/contracts/schemas`。字段名、枚举值必须与 DC 完全一致；改契约时先改 DC 和 JSON Schema，并升 `schema_version`（当前 `contract-0.7`）。
- **未定事项**一律采用 MP §9 决策表默认值；参数放 `config/*.yaml`，不硬编码；发现矛盾记入 `docs/OPEN_QUESTIONS.md`，不要自行发明语义。
- **时间**：一律存 UTC（`timestamptz`），显示 `America/New_York`；任何涉及时间的函数都要有"读取 as_of 之后的数据即报错"的负向测试。
- **不可覆盖**：预测、分析、结算、数据快照只追加新版本。
- 不接入真实付费 API，不提交任何密钥；需要密钥的适配器只留接口与 `.env.example`。所有示例数据标注 synthetic / 虚构。
- 每个阶段按 DP 的验收用例（AC-xx）写自动化测试；完成定义见 DP「每项任务的完成定义」。改动后更新 `docs/CHANGELOG.md`。

## 常用命令
```bash
pnpm install                                   # JS 依赖
pnpm -r build                                  # contracts 生成 TS + web 构建
pnpm --filter contracts test                    # examples/*.json 通过 schema 校验
uv sync                                        # Python 依赖（根目录 uv 项目，引用 services/py）
TEST_DATABASE_URL=postgresql://… uv run pytest services/py/tests -q   # Python 测试（含数据库测试）
uv run ruff check . && uv run mypy services/py/sr
uv run python scripts/make_fixture.py          # 生成合成 fixture（synthetic）
uv run python scripts/validate_sample.py --fixture data/fixtures/nvda_2026-12-01_1s.parquet
supabase start && supabase db reset            # 迁移 + seed（需 Docker）
make check                                     # 以上检查一次跑完
```

## 当前进度
- Phase 0 完成（CI 绿）。**Phase 1 进行中**：已完成 DP 1.03–1.08、1.22、1.27–1.28（历史类比、证据入库、LLM 接口、事件与版本、财报提取与预期对比、政策事件模板、采集记录、推理链与引用校验）；行情相关任务（1.01、1.02 等）等待 D-13 供应商样本。
- 数据库测试：设置 `TEST_DATABASE_URL`（管理员连接串，测试会建临时库）后运行 pytest；CI 自带 postgres:17。
