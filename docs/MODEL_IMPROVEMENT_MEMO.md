# Model Improvement Memo

**Version** `memo-0.1` · 2026-11-26 · Applies to: `BUILDING_MASTER_PLAN.md` (plan-0.1), `DATA_CONTRACT.md` (contract-0.1), `DEVELOPMENT_PHASES.md` (phases-0.1)
**Context**: The first users are the team itself. After the model matures, access opens to selected users step by step. This favors a strict-but-small model with honest, well-calibrated outputs over broad coverage.

---

## 0. Realistic expectations (read first)

- Predicting the **direction of a 60-minute return** for large, liquid stocks is close to a coin flip. A well-built system usually beats the base rate by only a few points. Success should be measured with **calibrated probabilities and a Brier Skill Score versus baselines**, not with a headline hit rate.
- **Volatility (how much the price will move) is far more predictable than direction.** A product that reliably says "expect a large move in the next hour" is more useful and easier to validate than one that guesses up or down.
- The best accuracy lever is often **knowing when not to predict**. Publish fewer predictions, but only where the model has shown measured skill.

---

## 1. Information: what to add

Items are ranked by expected value per unit of cost. "Data cost" is a rough tier: **Free**, **Low**, or **High**. Pricing is covered in a separate thread.

| # | Information | Why it helps | Data cost | Phase |
|---|---|---|---|---|
| I-1 | **Time-of-day and calendar features**: minutes since open, minutes to close, day of week, half-day, triple witching, index rebalance dates | Intraday volatility and drift follow strong daily patterns. These are the cheapest features with reliable signal | Free | P1 |
| I-2 | **Cross-asset leaders**: Nasdaq-100 and S&P 500 index futures (or QQQ/SPY as proxies), 10-year yield moves, the VIX level and its change | The market factor explains most of a single stock's 60-minute move. Use it for conditioning and for features | Low (ETF proxies) / High (futures) | P1 |
| I-3 | **Peer lead-lag inside the basket**: recent returns of NVDA/AMD/AVGO/MU and of TSM/SMH relative to each target | When news affects one chip name, related names often follow within minutes | Free (already in basket data) | P1 |
| I-4 | **Realized-volatility regime**: 5/30/390-minute realized vol, overnight gap size, and the opening-range size | This drives both the volatility target and the volatility-scaled labels in §2 | Free | P1 |
| I-5 | **Scheduled-event calendar**: peer and hyperscaler earnings dates, FOMC, CPI, jobs reports, NVDA GTC-type events, TSMC monthly revenue | Lets the model know that a big move is likely before any news arrives. It also stops event days from being mixed with ordinary days | Free (public calendars) | P2 |
| I-6 | **Supply-chain graph**: who supplies whom (TSMC → NVDA/AMD/AVGO, SK hynix/Samsung HBM ↔ MU and NVDA, hyperscalers → all) as edges on `event_security_links` | A capex cut at a cloud company or an HBM pricing note becomes a structured feature for every linked name, not only the subject company | Free (manual config) | P2 |
| I-7 | **Memory-cycle indicators for MU**: DRAM/NAND contract and spot price reports, Korea's 10- and 20-day export data | These are MU's most specific drivers and are published on known dates | Low–High | P2 |
| I-8 | **Analyst actions with timestamps**: rating and price-target changes, estimate revisions | These are common intraday catalysts, and they're missing from the current source list | High (licensed feed) | P3 |
| I-9 | **Options-implied information**: at-the-money implied volatility, skew, unusual volume | Gives the market's own volatility forecast. This is the strongest single input for the volatility target | High | P3+ |
| I-10 | **Order-flow imbalance** from top-of-book quotes and trade signs | It's the main short-horizon direction signal in research, but it needs tick-level data and careful engineering | High | P4 |
| I-11 | **News "novelty" and burst rate** rather than raw sentiment: is this headline new information or a repeat, and how fast are headlines arriving? | Raw sentiment scores carry little information at the 60-minute horizon. Novelty and surprise carry more | Free (derived from S2 dedupe) | P2 |

**Leave out for now**: social media sentiment, satellite and web-traffic alt data, and paid "AI sentiment" scores. Their value is unproven at this horizon, licensing is unclear (see the S1 compliance section), and they're expensive.

---

## 2. Analysis and modeling: what to change

| # | Change | Rationale | Design impact |
|---|---|---|---|
| A-1 | **Volatility-scaled class thresholds.** Replace the fixed ±0.15pp with `±k × σ̂_60m`, where σ̂ is the forecast relative-return volatility at publish time (start with k = 0.25, frozen per `target_definition_version`) | Fixed thresholds make "flat" dominate on calm days and almost disappear on volatile days. Scaled thresholds keep classes balanced and comparable across regimes | Change D-09, update `prediction_targets.threshold_rule`, add `sigma_hat` to `predictions.locked` |
| A-2 | **Add a volatility target `regular_60m_move`**: predict the absolute relative move magnitude (quantiles), using a HAR-style realized-vol model as the baseline | It's predictable, useful to users, and quick to validate. Use it as the first public "validated" output | New target row; new AC |
| A-3 | **Two-stage structure**: stage 1 forecasts volatility and stage 2 forecasts direction given that volatility. Stage 2 uses the scaled inputs | Separates "how much" from "which way", which improves calibration | `model_versions.model_family` gains `two_stage` |
| A-4 | **Cross-sectional framing**: alongside each stock versus its basket, rank the four pilot names against each other for the next 60 minutes | Relative ranking among close peers removes much of the common market noise, so the signal-to-noise ratio is higher | Optional target `pilot_rank_60m` (P3) |
| A-5 | **Event-time features**: minutes since the latest confirmed event, event category × decay, first-reaction size, and whether the reaction was already larger than history suggests ("priced in") | Turns S2 output into features that decay properly instead of fixed flags | Feature set `fs-0.3` |
| A-6 | **Pool training across a wider universe**: about 40–60 liquid semiconductor and large-cap tech names, with market/sector/company layers shrunk by regularization | Four stocks give too few independent events. Pooling multiplies samples while company offsets keep each name's specifics | Extend D-20; `coverage_tier = peer_only` used for training only |
| A-7 | **Selective prediction**: publish only when the model's edge over the baseline is above a cutoff. Report a coverage-versus-accuracy curve | Gives better accuracy where the system speaks and makes the trade-off visible to reviewers | Admin page: new curve; `abstain_reason = low_edge` |
| A-8 | **Conformal prediction for intervals**: split-conformal calibration on recent data gives distribution-free coverage guarantees | Replaces the "validated: false" intervals with intervals whose coverage is guaranteed by construction | P4 interval design |
| A-9 | **Rolling recalibration and drift monitoring**: weekly isotonic recalibration on the latest settled window, plus population-stability alerts on key features | Calibration decays as market regimes change. This is cheaper than retraining | `calibration_version` cadence; drift-triggered training (S3 §8.3 already allows this) |
| A-10 | **Gradient-boosted trees with monotone constraints** as the main challenger to the logistic baseline. Keep the model small and interpretable | Captures interactions such as "event × time of day" without overfitting as easily as deep models | Already allowed by D-24 |
| A-11 | **LLM extraction quality as a measured component**: a hand-labeled set of about 300 documents to score extraction precision/recall for facts, direction, scope and certainty, with prompts versioned and frozen | Event features are only as good as extraction. Errors there silently degrade the model | New AC in Phase 1 |

---

## 3. Accuracy and evaluation: what to add

| # | Addition | Why |
|---|---|---|
| E-1 | **Brier Skill Score (BSS)** versus three baselines: class frequency, "always flat", and persistence (the last 60-minute relative move continues) | Hit rate alone rewards guessing the majority class. BSS shows the real skill |
| E-2 | **Block bootstrap by trading day, plus a Diebold–Mariano-style paired test** for every candidate-versus-live comparison | Overlapping 60-minute windows inflate apparent significance |
| E-3 | **Power analysis before Phase 3**: estimate how many independent trading days are needed to detect the target Brier improvement, and set D-21 from that rather than a guess | Avoids approving noise or waiting forever |
| E-4 | **Purged and embargoed cross-validation** for model selection, alongside the existing walk-forward split | Uses limited history better without leakage |
| E-5 | **Experiment registry and a holdout budget**: log every candidate tried, and cap how many candidates may touch the final holdout per cycle | Prevents gradual overfitting to the holdout (S3 §8.1 already hints at this) |
| E-6 | **Error review queue**: each week, review the largest-confidence misses together with their explanation cards and tag the cause (data delay, wrong event attribution, regime shift) | Turns failures into feature and data fixes. This is the cheapest accuracy gain for a small internal team |
| E-7 | **Separate scorecards** for ordinary days, event days, earnings windows, the first and last 30 minutes, and high-volatility regimes | Average scores hide where the model actually works. Selected users should see only the slices that pass |

---

## 4. Rollout tied to accuracy (internal → selected users)

| Stage | Who sees what | Gate |
|---|---|---|
| **Internal** (now → Phase 3) | Everything, including shadow models | — |
| **Selected users v1** | Evidence, explanations, event scenarios, and the **volatility/expected-move** forecast (A-2) | Expected-move model passes conformal coverage on ≥ 60 independent days plus 20 live shadow days |
| **Selected users v2** | Direction probabilities for `regular_60m`, only for the slices that pass E-7, and only above the selective-prediction cutoff (A-7) | BSS > 0 with the bootstrap CI excluding 0, on holdout and live shadow |
| **Selected users v3** | `regular_to_close`, `next_regular_session`, intervals | Same gates, per target |

Every user-facing number keeps the "research, not investment advice" label, and access stays invite-only with RLS roles.

---

## 5. What I would fold into the design docs

> **Status 2026-11-26: items 1–6 below are folded in** (plan-0.2: D-09, D-29–D-33, §12; contract-0.2; phases-0.2: P0-F, P0-G, P1-9, P1-10, P3-6, AC-26–AC-31 and the first-round instructions).

**Recommended now (low cost, changes contracts, so better done before Phase 0 code):**

1. **A-1 volatility-scaled thresholds**: update D-09, `prediction_targets` (`threshold_rule`), and `predictions.locked` (`sigma_hat`). Affects the Phase 0 tests.
2. **A-2 volatility target `regular_60m_move`**: new target ID, contract enum, Phase 1 work item and acceptance case. Make it the first candidate for selected users.
3. **E-1 / E-2 metrics**: BSS with three baselines and day-block bootstrap. Add to `training_run_metrics.metric` and the Phase 1 acceptance criteria.
4. **I-1 to I-4 features**: fold into feature set `fs-0.2`. All are free or already in the basket data.
5. **A-11 LLM extraction eval set**: new Phase 1 acceptance case.
6. **§4 rollout gates**: add to the Master Plan §12 (launch boundary).

**Recommended for later phases (note in DEVELOPMENT_PHASES only):** A-5, A-6, A-7, A-9, I-5, I-6, I-11, E-3 to E-7 in Phase 2–3; A-8 in Phase 4.

**Leave out until data costs are known:** I-7 to I-10 (memory prices, analyst actions, options, order flow).
