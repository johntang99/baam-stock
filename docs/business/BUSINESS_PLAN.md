# Short Business Plan: Semiconductor Short-Term Forecast Research System

Version 0.1, 2026-11-26. Companion to [DATA_COST_COMPARISON.md](DATA_COST_COMPARISON.md).

## 1. What it is

A research tool for US semiconductor stocks (NVDA, AMD, AVGO, MU first; TSM, MRVL next) that:
- explains why a stock just moved (news, filings, peers, sector),
- forecasts the next 60 minutes, the rest of the day, and the next session,
- **settles every forecast against real prices** and keeps a public-to-us scorecard.

The honest, auto-settled track record is the product's core. Most retail "AI stock picks" never show their misses; this one would.

## 2. Phased plan

| Stage | Users | Goal | Gate to move on | Data tier | Monthly cost |
|---|---|---|---|---|---|
| **A. Build** (Phase 0-1) | Team only | Pipelines, snapshots, settlement working | Settlement runs clean for 20 sessions | T0 | ~$0-60 |
| **B. Internal research** (Phase 2-3) | Team only | Train, validate, run live paper forecasts | 3 months of live settled forecasts beat naive baselines (e.g. "no move", "follow SOXX") on hit rate and calibration | T1 | ~$185-245 incl. hosting |
| **C. Closed beta** | 5-20 invited users | Learn what users value; collect feedback | Users return weekly; no licence issues; track record holds | T2 + legal check | ~$420-550 |
| **D. Paid, selected users** | 20-200 | Cover costs, then profit | Break-even | T3 | ~$2,000-4,000+ |

Do not skip the stage B gate. If the model does not beat simple baselines after settlement, the business case does not exist, and it is cheap to learn that at ~$200/month.

## 3. Costs

- **Data:** see tiers in the comparison file. The big step is T2 to T3 (personal licence to commercial licence), roughly $400 to $2,000-4,000 per month.
- **Hosting:** Supabase + Vercel + one Python worker, ~$55-85/month (Unverified list prices).
- **AI / LLM for explanations:** usage-based; for 6-18 symbols and a few hundred event summaries a day, plan $30-150/month (estimate).
- **Legal:** one-time review before stage C/D, budget ~$1,000-3,000 (estimate).

## 4. Pricing for outside users (stage D)

Show **derived outputs only** (forecast, probability, explanation, track record), not raw quotes or news text, to keep licensing manageable.

| Plan | Price | Includes |
|---|---|---|
| Beta (stage C) | Free, invite-only | Pilot names, daily digest, scorecard |
| Standard | $29-49/month | 6 names, next-session forecasts, event explanations, 15-min delayed intraday view |
| Pro | $99-149/month | All names, live 60m forecasts, alerts, full forecast history export |

**Break-even** (T3 data ~$3,000 + other ~$300/month):
- at $39 average, about **85 paying users**;
- at $99 average, about **34 paying users**.

Staying at stage C (free beta on T2 data, derived outputs only, after vendor confirmation) keeps monthly cost under ~$550 while proving demand.

## 5. Key risks

| Risk | Mitigation |
|---|---|
| Model shows no real edge | Stage B gate with settled baselines; stop or pivot cheaply |
| Data licence breach when sharing | Personal plans for internal use only; written vendor confirmation; commercial plan before outside access |
| Regulatory (seen as investment advice) | Position as research and education, general (not personalised) content, clear disclaimers; get a US securities lawyer's view before charging (Investment Advisers Act "publisher" exclusion is the usual route; not legal advice) |
| Look-ahead bias inflates backtests | Point-in-time snapshots, first-publish timestamps, own consensus archive |
| Vendor price changes | Keep the data layer vendor-neutral (contract-0.1 already does this); keep a second feed |

## 6. Next steps

1. Run stage A on free data (T0) now.
2. Start the daily consensus snapshot job immediately; history cannot be bought back cheaply later.
3. Confirm the items in section 6 of the comparison file, then move to T1 (~$128-158/month data) when training starts.
4. Revisit pricing and licensing at the stage B gate.
