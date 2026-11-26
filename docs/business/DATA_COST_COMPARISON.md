# Data Source and Cost Comparison

Version 0.1, researched 2026-11-26. All prices in USD per month unless noted.

**How to read the status column**
- **Verified**: read on the vendor's own page or docs during this research (page dates noted).
- **3rd-party**: read on a price-tracking site, not the vendor's own page. Confirm before paying.
- **Unverified**: from general knowledge, not re-checked this session.

Nothing was signed up for. Prices change often; recheck the vendor page on the day you subscribe.

---

## 1. What the system needs (from DATA_CONTRACT contract-0.1)

| Need | Used for | Hardest part |
|---|---|---|
| Intraday quotes for NVDA, AMD, AVGO, MU (later TSM, MRVL) | Snapshots, 60m and to-close targets, settlement | NBBO mid at 2s sync, live and historical |
| Peer basket (semis_peer_v1, 12 names) and SOXX | Relative-move features | Same as above, ~18 symbols total |
| Timestamped news with first-publish time | Event analysis, "why did it move" | Reliable first-seen timestamps in history |
| SEC filings (8-K, 10-Q, 10-K, Form 4) | Events, fundamentals | Free and easy |
| Point-in-time analyst consensus | Earnings surprise features | Almost nobody sells PIT history cheaply |
| Trading calendar, corporate actions | Session logic, splits | Free and easy |

---

## 2. Vendor comparison

### 2.1 Market data (prices, quotes)

| Vendor / plan | Price | Live feed | History | NBBO / quotes | Licence | Status |
|---|---|---|---|---|---|---|
| **Alpaca Basic** | $0 | IEX only (one venue, small share of volume) | 1-min bars and trades since 2016, but last 15 min blocked | IEX quotes live; SIP history | Individual trading account; data terms not read | Verified (docs, 2026-11-24) |
| **Alpaca Algo Trader Plus** | $99 | Full SIP (all US exchanges) | Since 2016, no delay limit | SIP NBBO live and historical | Individual; no redistribution statement found | Verified |
| **Massive (ex-Polygon) Basic** | $0 | End of day | 2 years | No | Personal | 3rd-party + vendor compare page (Nov 2026) |
| **Massive Starter** | $29 | 15-min delayed | 5 years | No quotes; minute and second bars, flat files, websocket | Personal, non-professional | Same |
| **Massive Developer** | $79 | 15-min delayed | 10 years | Trades, no quotes | Personal | Same |
| **Massive Advanced** | $199 | Real-time | 20+ years (trades and quotes back to 2003) | Yes, NBBO quotes | Personal, non-professional | Same |
| **Massive Stocks Business** | $2,499 | Real-time | Full | Yes | Commercial, monthly, no annual contract | Same |
| **Databento usage-based** | Pay per GB, no fee; $125 free credits on signup (6-month expiry) | None | Bought per request | MBP-1, BBO-1s/1m, TBBO, trades | Per dataset | Verified (FAQ) |
| **Databento Standard** | $199 | Live included | OHLCV 8+ yrs; L1 (BBO, trades) last 12 months; L2/L3 last 1 month | Yes | "No license fees"; distribution not included | Verified (catalog, blog 2026-05-29) |
| **Databento Plus** | $1,500, annual contract | Enhanced live | L1 8+ years | Yes | Adds "External distribution" | Verified |
| **Tiingo Free / Power / Commercial** | $0 / $30 / $50 | IEX real-time | IEX intraday since Aug 2017 | IEX top-of-book only | All "Internal Use Only"; redistribution $250-500+ quoted | Verified |
| **FMP Starter / Premium / Ultimate** | $29 / $69 / $139 (annual ~$19 / $49 / $99) | Real-time | 5 yrs / 30+ yrs / 30+ yrs | No NBBO; 5-min bars on Starter, 1-min on Premium | Personal; display needs separate agreement | Verified (pricing page) |
| **Finnhub Free / All-in-One** | $0 / ~$3,500 (annual) | US real-time on free | Unknown | Unknown | Free is personal only | 3rd-party only; official page did not render |
| **yfinance (Yahoo)** | $0 | Delayed, unofficial | 1-min bars for only ~7-30 days | No | Yahoo terms forbid commercial use; scraping can break any day | Unverified |
| **Alpha Vantage** | $0 (25 calls/day) to ~$50-250 | Delayed / real-time on paid | Intraday 20+ yrs | No | Personal | Unverified |

**Takeaway:** For NBBO-quality data the realistic cheap choices are **Alpaca Algo Trader Plus ($99)** for live plus 10 years of SIP history, **Massive Advanced ($199)** for 20+ years of quotes and S3 flat files, or **Databento** for exact, research-grade history bought one time.

### 2.2 News

| Source | Price | First-publish time | History | Status |
|---|---|---|---|---|
| **GDELT** | $0 | 15-minute batches, global web news | 2015+ | Unverified; noisy, not finance-specific |
| **SEC EDGAR RSS / feeds** | $0 | Exact acceptance timestamp | All | Unverified (well known, free; 10 requests/sec fair-use limit, must send a User-Agent) |
| **Company IR press releases (RSS)** | $0 | Good | Varies | Unverified |
| **Alpaca News API** (Benzinga content) | Included with Alpaca account | Real-time | Back to ~2015 | Unverified; docs list "Real-time News" and "Historical News" but provider and terms not read |
| **Tiingo News** | Included in $30 Power | Real-time, "added as discovered" | Only 3 months on Power; 20+ yrs on enterprise quote | Verified |
| **Massive + Benzinga add-on** | +$99 | Real-time | Long | 3rd-party / vendor compare page |
| **FMP news** | In Premium $69 | Real-time | Full on Premium | Verified |

**Takeaway:** Alpaca's news feed is the best value if its terms allow our use, because it comes with the $99 data plan. Check first.

### 2.3 Filings, fundamentals, calendar

| Need | Free source | Status |
|---|---|---|
| Filings and Form 4 | SEC EDGAR full-text and submissions API | Unverified, but long-standing and free |
| Financial statements | SEC XBRL "companyfacts" API | Unverified, free |
| Trading calendar | `pandas_market_calendars` / `exchange_calendars` Python libraries | Unverified, free, open source |
| Corporate actions | Alpaca / Massive / Tiingo include them | Verified for Tiingo and Massive |
| Earnings dates | FMP (Starter+), Finnhub free | Verified for FMP |

### 2.4 Point-in-time analyst consensus (the real gap)

- **FMP** Starter/Premium give current estimates and price-target consensus (Verified), but not a dated history of what consensus was at each moment.
- True PIT history (LSEG I/B/E/S, FactSet, S&P Capital IQ, Zacks) is enterprise-priced, usually thousands per month (Unverified).
- **Recommendation:** start saving our own daily snapshot of FMP consensus today. After 2-4 earnings seasons we own a PIT archive for our 6-18 names at near-zero cost. Until then, mark consensus features as "live-only" and leave them out of backtests.

---

## 3. Recommended starter stack

| Layer | Pick | Why |
|---|---|---|
| Live quotes and 1-min bars | **Alpaca Algo Trader Plus, $99** | Full SIP, unlimited websocket symbols, 10,000 calls/min, history since 2016. Cheapest full-market feed found. |
| Deep training history (NBBO) | **Databento usage-based, one-off, using $125 free credit first** | Buy exact BBO-1s / MBP-1 for the ~18 symbols only for the windows we train on. No monthly fee. |
| News | **Alpaca News** (if terms fit) + **SEC EDGAR** + **GDELT** | $0 extra. Add Tiingo Power ($30) as a second timestamp source if Alpaca's gaps show up. |
| Fundamentals, estimates, earnings calendar | **FMP Starter, $29** (or annual ~$19) | Estimates, price targets, earnings dates. Snapshot daily for PIT. |
| Filings, calendar | EDGAR, `exchange_calendars` | Free |
| Prototyping only | yfinance | Never in production or settlement |

**Starter monthly cost: about $128-158**, plus a one-time Databento history purchase (covered first by the $125 credit).

---

## 4. Monthly budget tiers

| Tier | When | Stack | Monthly |
|---|---|---|---|
| **T0 Free** | Phase 0-1, building pipelines | Alpaca Basic (IEX live, delayed SIP history), EDGAR, GDELT, FMP free, Tiingo free | **$0** |
| **T1 Internal research** | Training + live paper forecasts for 4-6 names | Alpaca Algo Trader Plus $99 + FMP Starter $29 (+ Tiingo Power $30 optional) + Databento one-off | **$128-158** |
| **T2 Serious internal** | More symbols, 20-year quote history, second news source | Massive Advanced $199 + Benzinga add-on $99 + FMP Premium $69, keep Alpaca $99 as backup feed | **$367-466** |
| **T3 Selected outside users** | Showing forecasts and data to people outside the team | Commercial licences: Massive Stocks Business $2,499 or Databento Plus $1,500 (annual), news redistribution quote (Tiingo starts ~$250-500), FMP display agreement (quote) | **~$2,000-4,000+** |

Hosting (Supabase Pro ~$25, Vercel Pro ~$20, a small Python worker ~$10-40) adds about **$55-85** to every tier above T0 (Unverified, typical list prices).

---

## 5. Licensing warning for later sharing

Every cheap plan found is **personal / internal use only** (Alpaca individual, Massive non-professional, Tiingo "Internal Use Only", FMP "Licence - Personal"). This is fine while the team uses the system for itself.

Before letting outside users see it:
1. Show only **our own derived outputs** (probabilities, direction, explanations), not raw quotes or news text. Many vendors treat derived data more leniently, but confirm in writing with each vendor.
2. Users who are "professional" under exchange rules cost much more per seat for real-time data.
3. Budget the jump from T2 to T3 before opening access.

---

## 6. Items to confirm before paying

- [ ] Alpaca data agreement: allowed uses, and whether News API is included and who supplies it.
- [ ] Massive: official pricing page (prices above are from Nov 2026 compare pages and third-party trackers) and whether Advanced includes full NBBO quotes history.
- [ ] Databento: $/GB for BBO-1s and MBP-1 on the consolidated US equities dataset; estimate cost for 18 symbols x 5 years.
- [ ] Finnhub: official prices (page did not load).
- [ ] FMP: whether estimate history endpoints exist (would shortcut the PIT archive).

## Sources

- Alpaca market data docs: https://docs.alpaca.markets/docs/about-market-data-api ; https://pricingsaas.com/companies/alpaca
- Massive: https://massive.com/compare/massive-vs-alpaca.md ; https://massive.com/compare/massive-vs-databento.md ; https://apicostcalc.com/blog/polygon-massive-rebrand-api-pricing.html ; https://qveris.ai/guides/polygon-pricing-optimized
- Databento: https://databento.com/catalog/us-equities ; https://databento.com/blog/updates-to-subscription-pricing ; https://databento.com/docs/faqs/usage-pricing-and-data-credits.md
- Tiingo: https://www.tiingo.com/products/iex-api ; https://www.tiingo.com/products/news-api
- FMP: https://site.financialmodelingprep.com/api/pricing-md ; https://site.financialmodelingprep.com/pricing-plans?planType=commercial
- Finnhub: https://finnhub.io/pricing (did not render) ; https://apicostcalc.com/finnhub.html
