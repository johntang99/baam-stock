# User Guide: How to Get the Most Out of the Tool

**Version** `guide-0.1` · 2026-11-26 · Matches plan-0.2 / contract-0.2 and the prototype pages.
This is a research tool. It is not a trading signal or investment advice.

> **Chinese, more complete version:** `TRAINING_AND_USAGE_GUIDE_CN.md` (guide-cn-0.1, matches plan/contract/phases 0.7) covers model training, shadow testing, approval and rollback, plus daily use, adding information and review. Where the two differ, follow the Chinese guide. This file is kept for the product name ideas.

---

## 1. Name ideas

I haven't run trademark or domain checks on any of these. Please check them before you commit to one.

| Name | Chinese | Why it fits |
|---|---|---|
| **NextHour** | 下一小时 | Says exactly what the core product does: the next 60 minutes |
| **Catalyst Lens** | 催化镜 | It shows what moved the stock and how much the news explains |
| **Tapewise** | 观盘 | "Reading the tape" with discipline; short and memorable |
| **Driftwatch** | 势察 | It watches drift relative to peers and flags when it's unexplained |
| **Hourglass Research** | 沙漏研究 | Fixed time windows, locked before they start, settled when they end |
| **SettleSure** | 结算有据 | Highlights the main trust feature: every forecast is settled honestly |

**My pick:** **NextHour** if you want the product to be about forecasts, or **Catalyst Lens** if you want it to be about explanation. Explanation is what selected users will see first, before direction probabilities pass their gates.

---

## 2. The four kinds of information (learn these first)

Every page labels what you're looking at:

| Label | What it means | How to use it |
|---|---|---|
| **History** (历史行情) | Prices that already happened | Fact. Check the quote time |
| **Current explanation** (当前解释) | What the evidence says about the move so far, as of a stated time | Read "unexplained part" and "counter-evidence" as carefully as the drivers |
| **Scenario, unverified** (情景 · 未验证) | Possible outcomes of a pending event, with no number attached | A way to think through outcomes, not a prediction |
| **Prior forecast, locked** (事前预测 · 已锁定) | A probability published *before* the window started. It can't be edited | The only thing that's scored |

If something has no "locked" label, it's not a forecast.

---

## 3. A daily routine (about 15 minutes in total)

**Pre-market (5 min), Monitor page**
1. Scan the four cards for a **"new catalyst"** badge and for overnight events.
2. Open **Pending Events** for anything with a milestone due today (court date, vote, rule deadline).
3. Check the **next-session outlook**. Until that model passes validation, treat it as context only.

**During the session (a few 1-minute checks), Monitor → Stock Detail**
1. Look at **relative to basket**, not only the raw move. A stock down 3% while peers fall 5% is *outperforming*.
2. Look at the **explanation status**:
   - `supported`: the evidence covers most of the move.
   - `partial`: something is unexplained, so stay curious.
   - `insufficient`: no confirmed cause yet, so don't invent one.
3. Look at the **expected move** first. It tells you whether the next hour is likely to be quiet or volatile, and it's the most reliable number in the system.
4. Only then look at **direction probabilities**. A spread like 38/35/27 is a mild lean, not a call.

**When news breaks, Stock Detail → Evidence → Event**
1. Check the **verification badge**. A media report is not the same as primary-source confirmation.
2. Compare **first-public time** with when the price started moving. News that came *after* the drop didn't cause it.
3. See whether the event-enhanced model is allowed for this case. Often only the market baseline is, and the page says so.

**After the close (5 min), Replay + Scorecard**
1. Replay one **miss** and one **hit**. Ask what was knowable at publish time.
2. Use **flag** on any explanation you think is wrong (planned for Phase 3, memo E-6; until then, note the `prediction_id`). Flags feed the weekly error review, which is the cheapest way to improve accuracy.

---

### Fixed forecast times (Eastern Time)

Every trading day the system runs at the same six times: **8:30** pre-market outlook, then 60-minute forecasts at **10:00, 11:30, 13:00 and 14:30** (14:30 also gives a to-close forecast), and a **16:30** outlook for the next session. On half-days it runs at 8:30, 10:00 and 11:30 (with to-close), then 13:30. It does not run on market holidays.

At each run, open the stock page and look at **Forecast vs actual** first. The solid line is what really happened, relative to the peer basket. The dashed line with the shaded band is what was forecast before the window started. A red dot means the result landed outside the band. Below the chart you'll see today's results and the running accuracy for today, the last 20 days and since launch. When fewer than 30 forecasts have settled, it shows counts only.

These comparisons are how the model gets better. Each week the settled results feed the next training round. Patterns such as "10:00 forecasts are too confident" lead to a new model or calibration, which must pass a shadow test before it goes live. The model is never tuned on single results.

## 4. Reading the numbers correctly

| You see | It means | It does **not** mean |
|---|---|---|
| Outperform 40% | In similar past situations, about 4 in 10 outperformed by more than the threshold | The stock will go up |
| Threshold ±0.15pp | k 0.25 × expected volatility 0.60pp, locked at publish time | A fixed rule for every day |
| Expected move p80 0.58pp | 8 in 10 similar hours moved less than 0.58pp versus peers | A price target |
| **Abstained** (弃预测) | The data or model wasn't good enough, so the system stayed silent | An error. Silence is a feature |
| **Unsettleable** (无法结算) | No clean quote at the window's start or end (for example, a halt) | A loss. It's excluded from the hit rate |
| Brier Skill Score > 0 | Better than the naive baseline | High accuracy. Check the confidence interval |

---

## 5. Habits that make it most effective

1. **Trust slices, not averages.** The scorecard shows where the model works (stock × time of day × news or no news). Lean on it only there.
2. **Use volatility for attention and direction for curiosity.** Expected move tells you *when* to watch; direction tells you *what to investigate*.
3. **Never act on an unlocked number.** Anything on screen without a lock is description, not forecast.
4. **Separate event outcome from price reaction.** A deal can close and the stock can still underperform because the outcome was already priced in. The tool scores these two separately; you should think about them separately too.
5. **Write down disagreements.** If you'd have predicted differently, note it in the flag. After a few weeks, compare your calls with the model's on the same windows.

---

## 6. Access stages

> Update 2026-11-26: the system is for the internal team only; there is no plan to open it to outside users. The "Selected users" rows below are now internal visibility tiers for the day-to-day view.

| Stage | You'll see |
|---|---|
| Internal team (now) | Everything, including shadow models and the R&D console |
| Selected users v1 | Evidence, explanations, scenarios, expected move |
| Selected users v2 | Direction probabilities, only for slices that pass the gates |
| Selected users v3 | To-close and next-session forecasts, intervals |

The gates are defined in BUILDING_MASTER_PLAN §12 and must be met on both historical holdout data and live shadow testing.
