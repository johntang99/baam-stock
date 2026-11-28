# 美股短期研究与预测系统 · 设计交付包（plan-0.7 / contract-0.7 / phases-0.7）

交给 VS Code 中 Claude Code 的完整资料。阅读顺序：

1. `BUILDING_MASTER_PLAN.md` — 每日预测时刻表与"预测与实际对照如何改进模型"（§2.1、§7.1）、版本核对、冲突与缺项、架构、存储选型、**决策表（§9）**、**追溯表（§10）**、一致性核对（§11）
2. `DATA_CONTRACT.md` — 实体关系、字段表、状态转换、API/任务接口、幂等与版本、三个连贯 JSON 示例
3. `DEVELOPMENT_PHASES.md` — Phase 0–4 的工作项、文件、验证命令、验收用例 AC-01～AC-61，**结尾为首轮 Claude Code 执行指令（仅 Phase 0）**
4. `prototype/` — 可交互原型（模拟数据），打开方式见 `prototype/README.md`
5. `MODEL_IMPROVEMENT_MEMO.md` — 模型改进建议（§5 六项已并入上述文档）
6. `USER_GUIDE.md` — 用户使用指南与产品命名候选
7. `PPT_COVERAGE_REVIEW.md` — PPT 蓝图逐项覆盖核对（0.4 起 96 项全部覆盖）

## 文件清单
| 路径 | 用途 |
|---|---|
| `README.md` | 本文件 |
| `CLAUDE_CODE_START.md` | **开工说明**：可否开始的核对、你的准备步骤、粘贴给 Claude Code 的首轮指令（项目 baam-stock，根目录 clients/baam-stock） |
| `BUILDING_MASTER_PLAN.md` | 总体方案 |
| `DATA_CONTRACT.md` | 数据契约 |
| `DEVELOPMENT_PHASES.md` | 开发阶段 + 首轮指令 |
| `MODEL_IMPROVEMENT_MEMO.md` | 模型改进建议 |
| `TRAINING_AND_USAGE_GUIDE_CN.md` | **训练与使用指南（中文）**：数据快照、周检训练、基线与事件模型、校准、影子测试步骤、审批与回滚、预测对照改进；每日使用、读数、何时可信、补充信息、复盘 |
| `roadmap/ROADMAP_EXTENSIONS_CN.md` | **路线图扩展（中文）**：Phase 5 中长期预测、Phase 6 买卖信号、Phase 7 自有资金系统执行交易；进入门槛、新数据、新表、模块边界；如何不打断当前编码合并 |
| `USER_GUIDE.md` | 用户指南（英文，早期版）与命名候选 |
| `PPT_COVERAGE_REVIEW.md` | PPT 蓝图覆盖核对 |
| `business/` | 商业计划与数据成本对比（另一条工作线产出） |
| `prototype/index.html` | 原型入口 |
| `prototype/styles.css` | 样式 |
| `prototype/data.js` | 共享模拟数据 |
| `prototype/app.js` | 原型逻辑（市场页面与研发后台） |
| `prototype/ops.js` | 运营页面（一键运行、新公司接入、数据源、任务与告警） |
| `prototype/README.md` | 原型说明 |

## 交给 Claude Code 的方式
按 `CLAUDE_CODE_START.md` 操作（推荐）。或：新建空仓库 → 把本包放到 `docs/`（原型放到仓库根 `prototype/`）→ 将 `DEVELOPMENT_PHASES.md` 末尾「首轮 Claude Code 执行指令」整段粘贴给 Claude Code。

所有示例数值、模型成绩均为虚构，不代表实际行情或验证结果；本系统面向研究与验证，不接入交易执行。
