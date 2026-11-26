# 数据采购验证（D-13 / D-15 / D-16）

版本 0.1（2026-11-26，Phase 0 P0-D）。对应 `docs/BUILDING_MASTER_PLAN.md` §9 的 D-13、D-14、D-15、D-16、D-35，机器可读镜像见 `config/decisions.yaml`。

**用法**：这是供应商对比**模板**。表内价格、授权信息只转引 `docs/business/DATA_COST_COMPARISON.md`（下称 DCC）。DCC 是桌面调研，没有用样本核实过，所以所有行的「验证状态」一律为「拟选/未验证」。DCC 没写的内容填「待核实」，不要推测。拿到样本并通过 D-35 门槛后，才把对应行改为「样本已验证」；签约后改为「已签约」。

转引标注写法：「见 DCC（其标注: Verified / 3rd-party / Unverified，未经样本核实）」。

---

## 1. D-13 实时与历史行情

需求（D-05/D-06/D-11/D-12/D-14）：合并 NBBO 中间价；个股与篮子成分同步 ≤ 2s；上市交易所官方收盘价；报价入缓冲 p95 < 1s；目标与篮子约 18 只证券。MP 候选：Massive、Databento、交易所直连。DCC 另列 Alpaca，这里一并放入对比。

| 候选 | 覆盖 | 时间精度 | 历史年限 | 实时延迟 | 授权/展示范围 | 价格 | 验证状态 |
|---|---|---|---|---|---|---|---|
| Massive Advanced | 全美股，含 NBBO 报价（DCC） | 待核实（秒级 NBBO 是否完整需核实） | DCC 称 20+ 年（报价回溯至 2003） | DCC 称实时；p95 待测 | 见 DCC（其标注: 3rd-party，未经样本核实）：个人/非专业 | 见 DCC（其标注: 3rd-party，未经样本核实） | 拟选/未验证 |
| Massive Stocks Business | 同上 | 待核实 | DCC 称完整 | DCC 称实时；p95 待测 | 见 DCC（其标注: 3rd-party，未经样本核实）：商业用途 | 见 DCC（其标注: 3rd-party，未经样本核实） | 拟选/未验证 |
| Databento 按量计费 | 美股合并数据集，MBP-1 / BBO-1s/1m / TBBO / trades（DCC） | 待核实（BBO-1s 粒度需样本确认） | 按需购买，可得年限待核实 | 无实时 | 见 DCC（其标注: Verified，未经样本核实）：按数据集 | 见 DCC（其标注: Verified，未经样本核实）：按 GB 计；每 GB 单价待核实 | 拟选/未验证 |
| Databento Standard | 同上，含实时 | 待核实 | DCC 称 L1 仅近 12 个月，OHLCV 8+ 年 | DCC 称含实时；p95 待测 | 见 DCC（其标注: Verified，未经样本核实）：不含对外分发 | 见 DCC（其标注: Verified，未经样本核实） | 拟选/未验证 |
| Databento Plus | 同上 | 待核实 | DCC 称 L1 8+ 年 | DCC 称增强实时；p95 待测 | 见 DCC（其标注: Verified，未经样本核实）：含对外分发 | 见 DCC（其标注: Verified，未经样本核实）：年约 | 拟选/未验证 |
| Alpaca Algo Trader Plus | 全 SIP，含 SIP NBBO（DCC） | 待核实 | DCC 称自 2016 年起 | DCC 称实时；p95 待测 | 见 DCC（其标注: Verified，未经样本核实）：个人账户，未找到再分发条款 | 见 DCC（其标注: Verified，未经样本核实） | 拟选/未验证 |
| 交易所直连 | 待核实 | 待核实 | 待核实 | 待核实 | 待核实 | 待核实 | 拟选/未验证 |

每个候选都要额外确认：是否提供**官方收盘价**（D-11，例如 Nasdaq Official Closing Price）；停牌/LULD 标志（D-12）；拆股分红等公司行为（D-40）。

---

## 2. D-15 新闻、政策、法院、宏观、Form 4、期权

需求：首发时间（`available_at`）可追溯；盘中新闻时间精度已知 ≥ 90%（D-35）。法院、宏观、Form 4 在 Phase 2 前完成样本验证；期权在 Phase 4 前不采购，只留接口。

| 候选 | 覆盖 | 时间精度 | 历史年限 | 实时延迟 | 授权/展示范围 | 价格 | 验证状态 |
|---|---|---|---|---|---|---|---|
| SEC EDGAR（8-K、10-Q/10-K、Form 4） | 申报文件与内部人交易 | DCC 称有精确受理时间戳 | DCC 称全部历史 | 待核实 | 公开数据；DCC 注明 10 次/秒限速、需带 User-Agent（其标注: Unverified，未经样本核实） | 免费（MP D-15） | 拟选/未验证 |
| 公司 IR 新闻稿 RSS | 各公司自发公告 | DCC 称较好；逐家待核实 | DCC 称因公司而异 | 待核实 | 待核实 | 免费（MP D-15） | 拟选/未验证 |
| Federal Register / BIS / 白宫 | 政策、出口管制 | 待核实 | 待核实 | 待核实 | 公开数据（待核实各站条款） | 待核实 | 拟选/未验证 |
| CourtListener / RECAP | 法院案卷（MP 注明覆盖不全） | 待核实 | 待核实 | 待核实 | 待核实 | 免费（MP D-15） | 拟选/未验证 |
| PACER（关键案件按需） | 联邦法院案卷 | 待核实 | 待核实 | 待核实 | 待核实 | 待核实 | 拟选/未验证 |
| BLS / BEA / Fed 官方发布 | 宏观数据首发 | 待核实（需确认发布时间戳） | 待核实 | 待核实 | 公开数据 | 待核实 | 拟选/未验证 |
| FRED / ALFRED | 宏观历史 vintage（首发值） | 日级 vintage，待核实 | 待核实 | 不适用（历史） | 待核实 | 待核实 | 拟选/未验证 |
| Alpaca News API（Benzinga 内容） | 授权新闻快讯候选 | DCC 称实时；首发时间精度待核实 | DCC 称约 2015 年起 | 待核实 | 见 DCC（其标注: Unverified，未经样本核实）：供应方与条款未读 | 见 DCC（其标注: Unverified，未经样本核实）：随 Alpaca 账户 | 拟选/未验证 |
| Tiingo News | 授权新闻快讯候选 | DCC 称「发现即入库」 | DCC 称 Power 档仅 3 个月 | DCC 称实时 | 见 DCC（其标注: Verified，未经样本核实）：仅内部使用 | 见 DCC（其标注: Verified，未经样本核实） | 拟选/未验证 |
| Massive + Benzinga 附加包 | 授权新闻快讯候选 | 待核实 | DCC 称较长 | DCC 称实时 | 待核实 | 见 DCC（其标注: 3rd-party，未经样本核实） | 拟选/未验证 |
| FMP news | 授权新闻快讯候选 | 待核实 | DCC 称 Premium 档完整 | DCC 称实时 | 见 DCC（其标注: Verified，未经样本核实）：个人；展示需另签 | 见 DCC（其标注: Verified，未经样本核实） | 拟选/未验证 |
| GDELT | 全球网络新闻（非金融专用，噪声大） | DCC 称 15 分钟批次 | DCC 称 2015 年起 | 15 分钟批次 | 待核实 | 见 DCC（其标注: Unverified，未经样本核实） | 拟选/未验证 |
| 期权数据（`OptionsProvider`） | Phase 4 前不采购，仅留接口 | — | — | — | — | — | 拟选/未验证 |

授权新闻按 D-45 只显示标题与定位，不展示正文。

---

## 3. D-16 共识预期（point-in-time）

需求：每个时点「当时的」一致预期，用于财报超预期特征。未采购前 `expectation_comparison` 允许为空，相关特征标记为仅实时、不进回测。

| 候选 | 覆盖 | 时间精度 | 历史年限 | 实时延迟 | 授权/展示范围 | 价格 | 验证状态 |
|---|---|---|---|---|---|---|---|
| FactSet（PIT） | 待核实 | 待核实 | 待核实 | 待核实 | 待核实 | 见 DCC（其标注: Unverified，未经样本核实）：企业级定价 | 拟选/未验证 |
| LSEG I/B/E/S（PIT） | 待核实 | 待核实 | 待核实 | 待核实 | 待核实 | 见 DCC（其标注: Unverified，未经样本核实）：企业级定价 | 拟选/未验证 |
| FMP 当前预期 + 自建每日快照 | 当前预期与目标价共识；DCC 称无历史 PIT | 日级（自建快照） | 从开始快照起算 | 待核实 | 见 DCC（其标注: Verified，未经样本核实）：个人；展示需另签 | 见 DCC（其标注: Verified，未经样本核实） | 拟选/未验证 |

DCC 另提 S&P Capital IQ、Zacks，同为企业级定价（其标注: Unverified），可按需补行。

---

## 4. 样本验收门槛（D-35）与运行方法

新公司（以及供应商样本）接入门槛，取自 D-35：

| 项目 | 门槛 |
|---|---|
| 分钟行情回填 | ≥ 3 年 |
| 秒级行情回填 | ≥ 1 年 |
| 合格报价率（D-12 口径） | ≥ 95% |
| 同步成功率（D-06 口径，≤ 2s） | ≥ 95% |
| 盘中新闻时间精度已知 | ≥ 90% |
| LLM 抽检 | 通过 D-32（数值事实 precision ≥ 0.98、方向 F1 ≥ 0.85） |
| 影子运行 | ≥ 20 个交易日 |
| 不满足 | 只做 `peer_only`（训练池）或停在 `blocked` |

延迟另按 D-14 观测：交易所时间 → 参考报价入缓冲 p95 < 1s。

**运行**：把供应商样本转成与 fixture 相同的格式（参考合成样本 `data/fixtures/nvda_2026-12-01_1s.parquet`），然后：

```bash
uv run python scripts/validate_sample.py --fixture <样本文件>
```

脚本输出覆盖率、合格报价率、同步成功率。把结果与上表对照，记到对应候选行，并在本文件注明样本来源、日期范围与证券列表。合成 fixture 的结果只说明脚本能跑，不算供应商验证。

---

## 5. 付款前需确认事项（转录 DCC §6）

- [ ] Alpaca data agreement: allowed uses, and whether News API is included and who supplies it.
- [ ] Massive: official pricing page (prices above are from Nov 2026 compare pages and third-party trackers) and whether Advanced includes full NBBO quotes history.
- [ ] Databento: $/GB for BBO-1s and MBP-1 on the consolidated US equities dataset; estimate cost for 18 symbols x 5 years.
- [ ] Finnhub: official prices (page did not load).
- [ ] FMP: whether estimate history endpoints exist (would shortcut the PIT archive).

本项目补充（来自 D-13/D-15/D-16）：

- [ ] 各行情候选是否提供上市交易所官方收盘价、停牌/LULD 标志。
- [ ] 授权展示范围：对外用户（D-33）只看派生结果时，是否需要展示授权。须书面确认。
- [ ] 新闻候选的首发时间字段定义，以及历史数据是否保留原始首发时间。
- [ ] CourtListener/RECAP 对关键案件的覆盖率；需 PACER 补充的范围与费用。
- [ ] FRED/ALFRED vintage 能否还原首发值与发布时刻。

---

## 6. `data_sources.verification_status`

每个来源登记在 `data_sources`（DATA_CONTRACT），`verification_status ∈ {proposed, sample_verified, contracted, retired}`：

- 默认 **`proposed`**，包括目前所有候选，以及只用合成 fixture 跑过的来源。
- 真实样本通过第 4 节门槛后，改为 **`sample_verified`**。
- 签约完成、授权范围书面确认后，改为 **`contracted`**。
- 期权来源在 `sample_verified` 之前，模型特征不得读取 `options_snapshots`（AC-51）。
