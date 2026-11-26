# 提取评估集标注指南 · extract-labels-v0

用途：评估 LLM 事实提取的质量（D-32）。只有通过门槛（数值事实 precision ≥ 0.98、方向 F1 ≥ 0.85，且 ≥ 100 份已审核文档）的提示词版本，提取结果才能进入模型特征（AC-30）。

## 流程
1. `uv run python scripts/fetch_sec_corpus.py` 下载公开 SEC 文件（原文在 `data/corpus/`，不提交；清单 `data/labels/extraction-v0/manifest.jsonl` 提交）。
2. `uv run python scripts/prelabel_extraction.py --provider fake` 生成草稿（`label_status: draft`）。草稿**不计入**评估。
3. 打开 `data/labels/extraction-v0/labels/<文档>.json`，对照原文逐条核对、增删、改正，然后把 `label_status` 改为 `reviewed`，`labeled_by` 写你的名字。**不要改 `text_sha256`**（原文变了必须重新标注）。
4. `uv run python scripts/run_extraction_eval.py --provider <fake|anthropic> --save` 计分并写入 `extraction_eval_runs`。

## 标什么
每条明确写出的财务/业务数值事实一行；没有就留空列表。只标原文写了的，不推算、不补全。

| 字段 | 规则 |
|---|---|
| `metric` | 规范名：`revenue`、`data_center_revenue`、`net_income`、`eps_gaap`、`eps_non_gaap`（GAAP 与 non-GAAP EPS 必须分开，原文没写口径的 EPS 不标）、`gross_margin_pct`、`revenue_outlook` |
| `value` | 归一化数值：金额用美元（35.1 billion → 35100000000），百分比写数字（74.6），每股收益写美元（0.81） |
| `unit` | `USD` / `pct` / `USD_per_share` |
| `period` | `FY2027Q3` 形式（公司财年口径）；全年 `FY2027`；不确定留空 |
| `basis` | `gaap` / `non_gaap` / `company_defined`；原文未写留空 |
| `quote` | 从原文**逐字**复制的那句话或短语 |
| `direction` | 原文对该数值写明的变化：`increase` / `decrease` / `unchanged`；没写变化用 `none` |
| `scope` | `company`（全公司）/ `segment` / `product` / `geography` / `other` |
| `certainty` | `reported`（实际结果）/ `guidance`（公司展望）/ `expectation`（他人预期）/ `hypothetical` |

## 审核重点（来自首轮 Claude 草稿试运行）
- **多列表格行**（例 `Percent of revenue 86.8 % 84.6 % 44.7 % …`）：模型通常把第一列当作本季度，程序无法核对期间——请逐条确认 `period`，不确定就删掉该条。
- **口径**：同一行常并列 GAAP 与 non-GAAP（或本季/去年同期/年初至今），确认 `basis` 与 `period` 对应正确的那一列。
- **货币**：TSMC 等以新台币（NT$）报告的数字，当前单位表只有美元——这类事实不要标成 USD，暂不标注。
- `data/labels/extraction-v0/candidates/` 里有模型找到的全部候选与被程序剔除的原因（如 `other`、`value_not_in_quote`），可用来补漏，但候选本身不计入评估。

## 文档构成（目标约 300 份）
SEC 8-K 新闻稿附件（EX-99.1，财报为主）与 8-K 正文（管理层变动、协议等）先行；随后补 Federal Register 政策文件与新闻（D-32 各类均需覆盖）。所有文件均为公开资料；标注内容只用于内部评估。
