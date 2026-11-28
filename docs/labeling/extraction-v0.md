# 提取评估集审核指南 · extract-labels-v0

给审核员：本指南说明如何把 Claude 生成的草稿标注逐份核对成"标准答案"（gold label）。

## 1. 你在做什么，为什么要细

系统用 LLM 从财报新闻稿、8-K 等文件里提取数值事实（营收、毛利率、EPS……）。提取结果要进入模型之前，必须先在**至少 100 份已审核文档**上通过两道门槛（D-32）：

- 数值事实 **precision ≥ 0.98**：模型提出的事实，98% 以上必须能在你的标准答案里找到完全一致的一条；
- 方向（上升/下降）**F1 ≥ 0.85**。

你的文件就是标准答案。两种错误都会让评估失真：

- **漏标**：原文写了、属于范围内的事实你没标 → 模型找对了也会被判错（precision 被冤枉地拉低）。所以**范围内的事实要标全**，不只标"重要的"。
- **错标**：数值、期间、分部写错 → 模型对的被判错，或错的被判对。

一条事实与模型输出"对上"，需要 **指标名 + 分部 + 期间 + 数值** 四项全部一致。这四项是审核的重点。

语料共 357 份：291 份 SEC 文件（财报新闻稿附件、8-K 正文）、40 份 Federal Register 政策文件、26 份公司新闻稿（见第 6a 节）。SEC 文件的草稿由 Claude extract-0.3 生成，程序已核对过数字确实出现在引文中。草稿**不计入**评估，只有你改成 `reviewed` 的文件才计入。

## 2. 一次性准备

```bash
uv sync
# 下载原文到 data/corpus/（不提交到 git）。需要先在 .env.local 设 SEC_EDGAR_USER_AGENT（SEC 要求）
uv run python scripts/fetch_sec_corpus.py
uv run python scripts/fetch_public_corpus.py   # 政策（Federal Register）与公司新闻稿
```

用任意编辑器（推荐 VS Code）编辑 JSON。

## 3. 每份文档的流程

1. **领下一份**：`uv run python scripts/check_labels.py --queue 10` 按推荐顺序列出未审核文档，并给出 SEC 原文链接。多人同时审核时，先在团队里认领，避免重复。
2. **读原文**：在浏览器打开 SEC 链接看排版好的原文（表格看得清）。
3. **取可搜索文本**：`uv run python scripts/check_labels.py --text "<doc key>" > /tmp/doc.txt`。这是程序实际使用的文本（表格被压成一行）。`quote` 必须从这里**逐字**复制。
4. **打开标注文件**：`data/labels/extraction-v0/labels/<文档>.json`（文件名是 doc key 中的 `:` 换成 `_`）。逐条核对、改正、删除、补充（规则见第 4–6 节）。
5. **查漏**：打开 `data/labels/extraction-v0/candidates/<文档>.json`。`candidates` 是模型找到的全部候选，`dropped` 是程序剔除的及原因。被剔除但其实正确的事实（见第 6 节）请手工补进标注文件——注意候选里的数值和期间是**原文写法**，要按第 4 节换算后再填。
   - 改到一半的草稿也安全：程序重跑核对（`--recheck`）时，凡是被人改过的草稿都会跳过，不会被覆盖。
6. **标记完成**：`"label_status": "reviewed"`，`"labeled_by": "<你的名字>"`。
7. **自检**：`uv run python scripts/check_labels.py --keys "<doc key>"`，必须 **0 error**；warning 逐条看一眼，确认无误即可保留。
8. **提交**：提交改动的 JSON（建议一批 10–20 份一个 PR），PR 说明里写下拿不准的地方。

**不要改** `doc_key`、`text_sha256`、`doc_kind`。已标为 `reviewed` 的文件，任何脚本都不会覆盖。

## 4. 字段规则

| 字段 | 规则 |
|---|---|
| `metric` | 只能用下面 15 个规范名之一（见第 5 节）。不在列表里的数字不标。 |
| `value` | **归一化数值**。金额一律换成美元整数值：`$13.4 billion` → `13400000000`；`($ in millions)` 表里的 `3,296` → `3296000000`。百分比写数字：`74.6%` → `74.6`。EPS 写美元：`$0.81` → `0.81`。亏损、下降写负数：`operating loss of $134 million` → `-134000000`；`down 8%` 的增长率 → `-8`。 |
| `unit` | 只用 `USD`、`pct`、`USD_per_share`（已归一化，不要写 `USD_billion`）。 |
| `period` | `FY2027Q3`（季度）或 `FY2027`（全年），用**公司自己的财年**：NVIDIA 2026 年 10 月结束的季度是 `FY2027Q3`；AMD 按自然年，`third quarter of 2026` → `FY2026Q3`。展望写它预测的那个期间。**不能留空**（空期间会与任何期间匹配，抬高分数）；判断不了就删掉这条。 |
| `segment` | 分部/产品线/地区/被收购业务的名字，**照原文写**（如 `Data Center`、`Client`、`United States`）。全公司数字填 `null`。大小写不影响匹配，但措辞要一致。 |
| `scope` | 与 `segment` 对应：`company`（segment 为 null）/ `segment` / `product` / `geography` / `other`（如被收购公司）。 |
| `basis` | 原文或所在表格/列标明 GAAP 或 non-GAAP 时填 `gaap` / `non_gaap`；公司自定义口径填 `company_defined`；没写留 `null`。EPS 的口径体现在指标名里（`eps_gaap` / `eps_non_gaap`），原文没写口径的 EPS 不标。 |
| `quote` | 从 `--text` 输出中**逐字**复制的句子、短语或表格行，必须包含这个数字。 |
| `direction` | 原文对这个数字写明的变化：`increase` / `decrease` / `unchanged`；没写变化用 `none`。增长率按正负号：`up 20%` → `increase`，`down 8%` → `decrease`。 |
| `certainty` | `reported`（已发生的实际结果）/ `guidance`（公司自己的展望）/ `expectation`（分析师等他人的预期）/ `hypothetical`（假设情景）。 |

### 示例（虚构 · synthetic）

原文："Synthetic Corp reported third quarter fiscal 2027 revenue of $13.4 billion, up 12% from a year ago. Data Center revenue was $10.1 billion."

```json
[
  {"metric": "revenue", "value": 13400000000.0, "unit": "USD", "period": "FY2027Q3", "basis": null,
   "quote": "revenue of $13.4 billion, up 12% from a year ago", "direction": "increase",
   "scope": "company", "certainty": "reported", "segment": null},
  {"metric": "revenue_growth_yoy_pct", "value": 12.0, "unit": "pct", "period": "FY2027Q3", "basis": null,
   "quote": "revenue of $13.4 billion, up 12% from a year ago", "direction": "increase",
   "scope": "company", "certainty": "reported", "segment": null},
  {"metric": "data_center_revenue", "value": 10100000000.0, "unit": "USD", "period": "FY2027Q3", "basis": null,
   "quote": "Data Center revenue was $10.1 billion", "direction": "none",
   "scope": "segment", "certainty": "reported", "segment": "Data Center"}
]
```

注意：同一句话里有营收和增长率两个事实，就标两条。

## 5. 标什么、不标什么

**15 个规范指标**

| 指标 | 含义与注意 |
|---|---|
| `revenue` | 营收（total / net revenue、sales）。分部或产品线营收也用它，并填 `segment`。 |
| `data_center_revenue` | **数据中心分部的总营收**，`segment` 照原文填（如 `Data Center`）。数据中心下的子项（如 `Data Center Compute`）用 `revenue` + 对应 segment。 |
| `net_income` | 净利润（亏损为负）。 |
| `eps_gaap` / `eps_non_gaap` | 每股收益，必须分口径。 |
| `gross_profit` | 毛利**金额**。注意：Broadcom 等公司把毛利金额也叫 "Gross margin"（如 `Gross margin 12,249`，单位百万美元）——这是 `gross_profit`，不是百分比。 |
| `gross_margin_pct` | 毛利**率**（%）。 |
| `operating_income` | 营业利润 / income from operations（亏损为负）。 |
| `operating_expenses` | 营业费用总额。 |
| `operating_margin_pct` | 营业利润率（%）。 |
| `operating_cash_flow` | 经营活动现金流。 |
| `free_cash_flow` | 自由现金流。 |
| `revenue_outlook` | **公司对营收的展望**（`certainty: guidance`）。其他指标的展望（毛利率、费用、EPS）用原指标名 + `certainty: guidance`。 |
| `revenue_growth_yoy_pct` / `revenue_growth_qoq_pct` | 营收同比 / 环比增长率（%），可超过 100。 |

**要标**
- 范围内、期间明确的每一个数字，包括表格里的**上年同期、上季度**等对比列——只要能确定这一列是哪个期间（如 `FY2026Q3`）。
- 展望："Revenue ~$9.6 billion, +/- $300 million" → `revenue_outlook` = `9600000000`（原文写出的中心值），期间为被预测的季度。
- 没有数字但写明方向的展望（如 "expected to be accretive to non-GAAP EPS"）：`value: null`，`direction` 按原文填。

**不标**（OQ-40 默认规则）
- 不在 15 个指标里的数字：股本、员工数、高管薪酬、股息、回购、资本开支、库存等。
- **年初至今、六个月、九个月**等非单季、非全年的期间（期间格式表达不了）。
- **区间型展望**（"between $X and $Y"），以及原文没写出的中点——不要自己计算。
- 对账表的中间调整列（如 GAAP→non-GAAP 的逐项调整、并购 pro forma 调整列）。
- **新台币（NT$）等非美元金额**（TSMC）：暂不标，等 TSMC 接入后再处理。百分比（毛利率、增长率）照常标。
- 同一事实（指标 + 口径 + 期间 + 分部相同）只标一条，选最清楚的那处引文；自检会报 duplicate。

## 6. 草稿里常见的问题（来自 291 份草稿的实际情况）

1. **期间为空（101 条）**：模型写了 "three months ended March 29, 2025" 之类，程序没能换算。请按原文判断财季并填上（如 AMD 的这个就是 `FY2025Q1`）；如果是九个月/年初至今，删掉。`check_labels.py --all` 可以列出全部。
2. **多列表格取错列**：表格行如 `Operating income 2,169 1,773 719 2,490 2,007 941` 同时列出本季、上季、去年同期、年初至今等多列，列的顺序因表而异，压成一行后看不出表头。模型有时把别的列的数字标成本季。在浏览器里对照原文表头，逐条核对 `value` 与 `period` 是否对应同一列。
3. **GAAP 与 non-GAAP 并列**：同一张表常有两套数字，确认 `basis` 对应的是那一套。
4. **被剔除但正确的候选**：candidates 文件里 `conflicting_values`（90 条，多为同一指标模型取了不同列）和 `value_not_in_quote`（62 条）值得逐条看；判断正确的补进去。`unknown_metric`（951 条）基本是范围外数字，不用补；`currency_not_supported`（99 条）是新台币金额，不标。
5. **8-K 正文**（`doc_kind: 8k_other`，180 份）多数没有范围内事实，草稿为空列表。确认原文确实没有（例如高管任命、协议签署）后直接标 `reviewed` 即可——空列表也是有效的标准答案。
6. **财报附件为空**（34 份）：有些是投资者演示稿或股息公告，确实没有；也有可能是模型漏了，请打开 candidates 和原文确认。

## 6a. 政策文件与公司新闻稿

本版提取只覆盖第 5 节的 15 个**公司财务指标**，所以这两类文档的标准答案多数是空列表。它们的作用是检验模型**不乱提**：把关税税率、补贴金额、收购价格误当成营收之类的错误，会直接拉低 precision。

- **政策文件**（`doc_kind: policy`，40 份）：BIS 出口管制规则与实体清单、总统公告（如半导体进口关税）、USTR 301 调查、NIST CHIPS 补贴、ITA 通知。CHIPS 补贴金额、关税税率、罚款、贸易额都**不是**这 15 个指标，不标。只有当文件明确写出某家公司的营收、利润等财务数字时才标（很少见），`segment` 照常填，公司写在 PR 说明里。
- **公司新闻稿**（`doc_kind: news`，26 份，来自 NVIDIA、AMD、Marvell 官网新闻室）：多为产品发布、合作、收购、高管变动。收购价格、投资额、市场规模预测、客户订单金额都不标；但新闻稿若写了公司自己的财务数字或展望（如"预计本季营收约 $X"、"该业务营收同比增长 Y%"），按第 4–5 节照常标。
- 新闻稿页面里有网站导航、页脚等文字，不用理会；`quote` 只从正文复制。
- 第三方媒体报道要等新闻授权（D-15）落定后才加入（OQ-41）。

## 7. 进度与顺序

- 目标：先完成 **100 份**已审核（批准门槛），之后补到约 300 份（D-32）。`check_labels.py` 每次运行都会显示 `Reviewed N/100`。
- 按 `--queue` 的顺序做：它在公司（NVDA、AMD、AVGO、MU、TSM、MRVL）和文件类型（财报附件 / 8-K 正文 / 政策 / 新闻稿）之间轮换，保证前 100 份就覆盖各家公司和各类文档（D-32 要求各类都有）。
- 财报新闻稿事实多（有内容的草稿中位数 28 条，最多 59 条），要留足时间；空的 8-K 正文很快。

## 8. 拿不准时

- 规则覆盖不到、两种理解都说得通：**删掉这条事实**（宁缺勿错），并在 PR 说明里写下文档和原因。
- 同类问题反复出现时，提给维护者，记入 `docs/OPEN_QUESTIONS.md` 后统一规则，不要各人自定。
- 所有文档都是 SEC 公开文件；标注只用于内部评估。

## 附：常用命令

```bash
uv run python scripts/check_labels.py --queue 10           # 下一批待审核文档 + 原文链接
uv run python scripts/check_labels.py --text "<doc key>"   # 程序使用的原文文本（复制 quote 用）
uv run python scripts/check_labels.py --keys "<doc key>"   # 自检单份（草稿也可以）
uv run python scripts/check_labels.py                      # 自检全部已审核文件 + 进度
uv run python scripts/check_labels.py --all                # 连草稿一起检查
uv run python scripts/run_extraction_eval.py --provider anthropic --allow-spend --save   # 维护者：≥100 份后计分（付费调用，需批准）
```
