/* =====================================================================
 * MOCK DATA · 模拟数据 —— 全部为虚构，不代表真实行情、事件或模型成绩
 * 字段名与 DATA_CONTRACT.md (contract-0.5) 对应
 * ===================================================================== */
window.MOCK = (function () {
  "use strict";
  const SCHEMA_VERSION = "contract-0.7";

  // ---- deterministic PRNG ----
  function rng(seed) {
    let s = seed >>> 0;
    return function () {
      s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }
  function gauss(r) {
    const u = Math.max(r(), 1e-9), v = r();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  // ---- clocks ----
  // 盘中演示：2026-12-02（周三）11:30 ET = 16:30Z（EST, UTC-5）
  // 休市演示：2026-11-26（周四，感恩节休市）
  const CLOCKS = {
    intraday: { now: "2026-12-02T16:30:00.000Z", session_date: "2026-12-02", market_state: "regular", label: "2026-12-02 周三 11:30 ET（盘中）" },
    closed: { now: "2026-11-26T15:00:00.000Z", session_date: "2026-11-26", market_state: "closed", label: "2026-11-26 周四 10:00 ET（感恩节休市）" }
  };
  const SESSION_OPEN_MS = Date.UTC(2026, 11, 2, 14, 30); // 09:30 ET
  const NOW_IDX = 120; // 11:30 ET
  const FULL_IDX = 390; // 16:00 ET
  const tsAt = (i) => new Date(SESSION_OPEN_MS + i * 60000).toISOString();

  // ---- benchmark versions (D-08) ----
  const BASKET_ALL = ["NVDA", "AMD", "AVGO", "MU", "QCOM", "TXN", "INTC", "ADI", "MRVL", "AMAT", "LRCX", "KLAC"];
  function basketFor(tk) {
    const cons = BASKET_ALL.filter((x) => x !== tk);
    return {
      benchmark_id: "bm_semis_peer_ex_" + tk.toLowerCase(),
      benchmark_version_id: "bmv_semis_peer_ex_" + tk.toLowerCase() + "_v1",
      kind: "peer_basket",
      methodology: "equal_weight_ex_target",
      effective_from: "2026-10-01",
      sync_tolerance_ms: 2000,
      constituents: cons.map((c) => ({ security_id: "sec_" + c.toLowerCase(), weight: +(1 / cons.length).toFixed(4) }))
    };
  }

  // ---- securities ----
  const SEC_META = [
    { ticker: "NVDA", name: "NVIDIA", base: 182.4, beta: 1.25, seed: 11, chain: "AI GPU、整机柜、数据中心网络" },
    { ticker: "AMD", name: "AMD", base: 214.1, beta: 1.3, seed: 23, chain: "Instinct AI GPU、EPYC CPU" },
    { ticker: "AVGO", name: "Broadcom", base: 352.8, beta: 1.05, seed: 37, chain: "定制 AI 加速器、数据中心网络" },
    { ticker: "MU", name: "Micron", base: 118.6, beta: 1.4, seed: 41, chain: "HBM 及其他内存" }
  ];

  // shared basket path (sector factor)
  const rb = rng(7);
  const sector = [0];
  for (let i = 1; i <= FULL_IDX; i++) {
    let d = gauss(rb) * 0.045;
    if (i >= 89 && i <= 96) d -= 0.11; // 10:59–11:06 sector reaction to (fictional) policy doc
    sector.push(sector[i - 1] + d);
  }
  const rx = rng(19);
  const soxx = [0];
  for (let i = 1; i <= FULL_IDX; i++) soxx.push(soxx[i - 1] + (sector[i] - sector[i - 1]) * 1.1 + gauss(rx) * 0.03);

  const securities = {};
  SEC_META.forEach((m) => {
    const r = rng(m.seed);
    const pathPct = [0];
    for (let i = 1; i <= FULL_IDX; i++) {
      let idio = gauss(r) * 0.05;
      if (m.ticker === "NVDA" && i >= 89 && i <= 97) idio -= 0.13;
      if (m.ticker === "AMD" && i >= 89 && i <= 95) idio -= 0.06;
      if (m.ticker === "AVGO" && i >= 40 && i <= 44) idio += 0.05;
      const sd = sector[i] - sector[i - 1];
      pathPct.push(pathPct[i - 1] + m.beta * sd + idio);
    }
    const prevClose = m.base;
    const bars = pathPct.map((p, i) => ({
      bar_start: tsAt(i),
      close: +(prevClose * (1 + p / 100)).toFixed(2),
      benchmark_index: +(100 * (1 + sector[i] / 100)).toFixed(4),
      soxx_index: +(100 * (1 + soxx[i] / 100)).toFixed(4)
    }));
    securities[m.ticker] = {
      security_id: "sec_" + m.ticker.toLowerCase(),
      company_id: "co_" + m.name.toLowerCase(),
      ticker: m.ticker,
      name: m.name,
      chain: m.chain,
      primary_exchange: "XNAS",
      coverage_tier: "pilot",
      prev_close: prevClose,
      bars: bars,
      benchmark: basketFor(m.ticker),
      reference_benchmark_id: "bm_soxx_ref"
    };
  });

  const ret = (a, b) => +(((b / a) - 1) * 100).toFixed(2);
  function windowReturns(tk, i0, i1) {
    const b = securities[tk].bars;
    const s = ret(b[i0].close, b[i1].close);
    const bm = ret(b[i0].benchmark_index, b[i1].benchmark_index);
    return { stock_return_pct: s, benchmark_return_pct: bm, relative_return_pp: +(s - bm).toFixed(2) };
  }
  // D-09：阈值 = k × sigma_hat_pp（sigma-0.1）；以下 sigma 为虚构
  const K = 0.25;
  const SIGMA = { NVDA: { regular_60m: 0.6, regular_to_close: 1.6, next_regular_session: 2.4 }, AMD: { regular_60m: 0.7, regular_to_close: 1.8, next_regular_session: 2.6 }, AVGO: { regular_60m: 0.55, regular_to_close: 1.5, next_regular_session: 2.2 }, MU: { regular_60m: 0.8, regular_to_close: 2.0, next_regular_session: 2.9 } };
  const thr = (tk, t) => +(K * SIGMA[tk][t]).toFixed(3);
  const THRESH = { regular_60m: 0.15, regular_to_close: 0.4, next_regular_session: 0.6 }; // 仅作 sigma 缺失时的展示回退
  const classify = (pp, t) => (pp > t ? "outperform" : pp < -t ? "underperform" : "flat");
  function brier(p, cls) {
    return +["outperform", "flat", "underperform"].reduce((a, k) => a + Math.pow((p[k] || 0) - (k === cls ? 1 : 0), 2), 0).toFixed(4);
  }

  // ---- predictions ----
  function lockedFor(tk, mdl, t) {
    return {
      schema_version: SCHEMA_VERSION,
      target_definition_version: "td-0.2",
      quote_rule_version: "qr-0.1",
      benchmark_version_id: securities[tk].benchmark.benchmark_version_id,
      calendar_version: "cal-2026.11",
      model_version_id: mdl || "mdl_regular_60m_market_logit_v3",
      calibration_version: "cal_iso_v3",
      sigma_model_version: "sigma-0.1",
      sigma_hat_pp: SIGMA[tk][t],
      threshold_k: K,
      threshold_pp: thr(tk, t),
      feature_set_version: "fs-0.2"
    };
  }
  function mkPred(o) {
    const tk = o.ticker;
    const sec = securities[tk];
    const p = {
      prediction_id: o.id,
      run_id: o.id.replace("pred_", "run_"),
      target_id: o.target_id,
      target_row_id: "tgt_" + o.target_id + "_v1",
      security_id: sec.security_id,
      ticker: tk,
      event_id: o.event_id || null,
      status: o.status,
      probabilities: o.probabilities || null,
      predicted_class: o.probabilities ? Object.entries(o.probabilities).sort((a, b) => b[1] - a[1])[0][0] : null,
      interval: o.interval || null,
      display_tier: o.display_tier || "validated_public",
      abstain_reason: o.abstain_reason || null,
      // D-23（0.5 修订）：槽位预测为主评分样本；整 5 分钟定时预测只作内部样本
      is_primary: o.is_primary !== false && (o.sampling_rule || "scheduled_5m") !== "scheduled_5m",
      schedule_slot_id: o.slot || null,
      schedule_version: o.slot ? "sched-0.1" : null,
      sampling_rule: o.sampling_rule || "scheduled_5m",
      trigger_type: o.trigger_type || "scheduled",
      snapshot_id: "snap_" + tk.toLowerCase() + "_20261202_" + (o.pubIdx != null ? String(o.pubIdx) : "x"),
      locked: lockedFor(tk, o.model, o.target_id),
      sigma_hat_pp: SIGMA[tk][o.target_id],
      threshold_pp: thr(tk, o.target_id),
      move_quantiles: o.target_id === "regular_60m" && o.probabilities ? { p50: +(SIGMA[tk].regular_60m * 0.52).toFixed(2), p80: +(SIGMA[tk].regular_60m * 0.97).toFixed(2), p90: +(SIGMA[tk].regular_60m * 1.28).toFixed(2), unit: "abs_relative_pp" } : null,
      published_idx: o.pubIdx,
      published_at: o.pubIdx != null ? new Date(SESSION_OPEN_MS + o.pubIdx * 60000 + 800).toISOString() : null,
      t0_idx: o.t0Idx != null ? o.t0Idx : null,
      t0_quote_ts: o.t0Idx != null ? new Date(SESSION_OPEN_MS + o.t0Idx * 60000 + 2000).toISOString() : null,
      t0_quote_id: o.t0Idx != null ? "rq_" + tk.toLowerCase() + "_" + o.t0Idx : null,
      target_end_idx: o.endIdx != null ? o.endIdx : null,
      target_end_at: o.endIdx != null ? new Date(SESSION_OPEN_MS + o.endIdx * 60000 + 2000).toISOString() : null,
      note: o.note || null,
      supersedes_prediction_id: o.supersedes || null,
      // D-41：valid_until = target_end_at；无终点（弃预测/评估中）时为空
      valid_until: o.endIdx != null ? new Date(SESSION_OPEN_MS + o.endIdx * 60000 + 2000).toISOString() : null,
      settlement: null
    };
    if (o.status === "settled") {
      const w = windowReturns(tk, o.t0Idx, o.endIdx);
      const cls = classify(w.relative_return_pp, thr(tk, o.target_id));
      p.settlement = Object.assign({
        settlement_id: o.id.replace("pred_", "stl_") + "_v1",
        settlement_version: 1,
        start_quote_id: p.t0_quote_id,
        end_quote_id: "rq_" + tk.toLowerCase() + "_" + o.endIdx,
        outcome_class: cls,
        hit: cls === p.predicted_class,
        brier: brier(p.probabilities, cls),
        invalid_reason: null,
        settled_at: new Date(SESSION_OPEN_MS + o.endIdx * 60000 + 60000).toISOString(),
        is_reporting_version: true,
        reason_text: "起算为发布后首组同步合格报价；结算为目标时点后 30s 容差内首组同步合格报价。相对收益与阈值 ±" + thr(tk, o.target_id) + "pp（k " + K + " × σ̂ " + SIGMA[tk][o.target_id] + "pp）比较。"
      }, w);
    }
    if (o.status === "unsettleable") {
      p.settlement = {
        settlement_id: o.id.replace("pred_", "stl_") + "_v1",
        settlement_version: 1,
        start_quote_id: p.t0_quote_id,
        end_quote_id: null,
        stock_return_pct: null, benchmark_return_pct: null, relative_return_pp: null,
        outcome_class: null, hit: null, brier: null,
        invalid_reason: o.invalid_reason || "halted",
        settled_at: new Date(SESSION_OPEN_MS + o.endIdx * 60000 + 60000).toISOString(),
        is_reporting_version: true,
        reason_text: o.reason_text || "目标时点后 30s 容差内无同步合格报价（个股停牌），按 qr-0.1 标记无法结算；不计入命中率分母。"
      };
    }
    return p;
  }

  const predictions = [
    // NVDA
    mkPred({ id: "pred_nvda_20261202_1001_60m", ticker: "NVDA", target_id: "regular_60m", status: "settled", pubIdx: 31, t0Idx: 31, endIdx: 91, probabilities: { outperform: 0.36, flat: 0.36, underperform: 0.28 }, interval: { quantiles: { p10: -0.4, p50: 0.03, p90: 0.45 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_nvda_20261202_1101_60m", ticker: "NVDA", target_id: "regular_60m", status: "awaiting_settlement", event_id: "evt_policy_export_demo_001", trigger_type: "event", sampling_rule: "event_first", pubIdx: 91, t0Idx: 91, endIdx: 151, probabilities: { outperform: 0.3, flat: 0.31, underperform: 0.39 }, interval: { quantiles: { p10: -0.85, p50: -0.12, p90: 0.55 }, unit: "relative_pp", validated: false }, note: "事件增强模型未对 policy_export 验证，仅放行行情基线" }),
    mkPred({ id: "pred_nvda_20261202_1000_close", ticker: "NVDA", target_id: "regular_to_close", status: "awaiting_settlement", pubIdx: 30, t0Idx: 30, endIdx: 390, probabilities: { outperform: 0.34, flat: 0.33, underperform: 0.33 }, interval: { quantiles: { p10: -1.5, p50: 0.02, p90: 1.5 }, unit: "relative_pp", validated: false }, note: "政策文件公开后已由 11:01 版本替代（修订链，演示）" }),
    mkPred({ id: "pred_nvda_20261202_1101_close", supersedes: "pred_nvda_20261202_1000_close", ticker: "NVDA", target_id: "regular_to_close", status: "awaiting_settlement", event_id: "evt_policy_export_demo_001", trigger_type: "event", sampling_rule: "event_first", pubIdx: 91, t0Idx: 91, endIdx: 390, probabilities: { outperform: 0.31, flat: 0.29, underperform: 0.4 }, interval: { quantiles: { p10: -1.6, p50: -0.2, p90: 1.1 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_nvda_20261202_next", ticker: "NVDA", target_id: "next_regular_session", status: "abstained", abstain_reason: "model_not_validated", display_tier: "internal_shadow", pubIdx: 120, note: "下一时段模型仍在影子测试，仅展示行情与证据" }),
    // AMD
    mkPred({ id: "pred_amd_20261202_0930_60m", ticker: "AMD", target_id: "regular_60m", status: "settled", pubIdx: 30, t0Idx: 30, endIdx: 90, probabilities: { outperform: 0.33, flat: 0.34, underperform: 0.33 }, interval: { quantiles: { p10: -0.5, p50: 0.0, p90: 0.5 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_amd_20261202_1025_60m", ticker: "AMD", target_id: "regular_60m", status: "awaiting_settlement", pubIdx: 55, t0Idx: 55, endIdx: 115, probabilities: { outperform: 0.35, flat: 0.34, underperform: 0.31 }, interval: { quantiles: { p10: -0.55, p50: 0.03, p90: 0.6 }, unit: "relative_pp", validated: false }, note: "已过有效期、结算任务积压（演示 settlement_backlog）" }),
    mkPred({ id: "pred_amd_20261202_1101_60m", ticker: "AMD", target_id: "regular_60m", status: "awaiting_settlement", event_id: "evt_policy_export_demo_001", trigger_type: "event", sampling_rule: "event_first", pubIdx: 91, t0Idx: 91, endIdx: 151, probabilities: { outperform: 0.33, flat: 0.33, underperform: 0.34 }, interval: { quantiles: { p10: -0.7, p50: -0.02, p90: 0.62 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_amd_20261202_1130_close", ticker: "AMD", target_id: "regular_to_close", status: "pending_evaluation", pubIdx: 120, note: "评估中：等待本轮 5 分钟快照" }),
    mkPred({ id: "pred_amd_20261202_next", ticker: "AMD", target_id: "next_regular_session", status: "abstained", abstain_reason: "model_not_validated", display_tier: "internal_shadow", pubIdx: 120 }),
    // AVGO
    mkPred({ id: "pred_avgo_20261202_1125_60m", ticker: "AVGO", target_id: "regular_60m", status: "abstained", abstain_reason: "benchmark_unavailable", pubIdx: 115, note: "同行篮子缺 2 个成分同步报价（> 1 个上限），按事前规则弃预测" }),
    mkPred({ id: "pred_avgo_20261202_0945_60m", ticker: "AVGO", target_id: "regular_60m", status: "settled", pubIdx: 15, t0Idx: 15, endIdx: 75, probabilities: { outperform: 0.41, flat: 0.33, underperform: 0.26 }, interval: { quantiles: { p10: -0.3, p50: 0.08, p90: 0.5 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_avgo_20261202_close", ticker: "AVGO", target_id: "regular_to_close", status: "abstained", abstain_reason: "insufficient_data", pubIdx: 115 }),
    mkPred({ id: "pred_avgo_20261202_next", ticker: "AVGO", target_id: "next_regular_session", status: "abstained", abstain_reason: "model_not_validated", display_tier: "internal_shadow", pubIdx: 120 }),
    // MU
    mkPred({ id: "pred_mu_20261202_0950_60m", ticker: "MU", target_id: "regular_60m", status: "unsettleable", pubIdx: 20, t0Idx: 20, endIdx: 80, probabilities: { outperform: 0.35, flat: 0.32, underperform: 0.33 }, invalid_reason: "halted" }),
    mkPred({ id: "pred_mu_20261202_1105_60m", ticker: "MU", target_id: "regular_60m", status: "awaiting_settlement", trigger_type: "market_move", sampling_rule: "market_move_first", pubIdx: 95, t0Idx: 95, endIdx: 155, probabilities: { outperform: 0.29, flat: 0.33, underperform: 0.38 }, interval: { quantiles: { p10: -0.9, p50: -0.1, p90: 0.7 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_mu_20261202_close", ticker: "MU", target_id: "regular_to_close", status: "awaiting_settlement", pubIdx: 95, t0Idx: 95, endIdx: 390, probabilities: { outperform: 0.32, flat: 0.3, underperform: 0.38 }, interval: { quantiles: { p10: -1.8, p50: -0.15, p90: 1.3 }, unit: "relative_pp", validated: false } }),
    mkPred({ id: "pred_mu_20261202_next", ticker: "MU", target_id: "next_regular_session", status: "abstained", abstain_reason: "model_not_validated", display_tier: "internal_shadow", pubIdx: 120 })
  ];

  // ---- 0.5：每日预测时刻表（D-43）与槽位预测 ----
  const SCHEDULE = {
    schedule_id: "sched_us_regular_v1", schedule_version: "sched-0.1",
    slots: [
      { slot_id: "s0830_pre_open", time_et: "08:30", idx: -60, kind: "盘前展望", targets: ["next_regular_session"] },
      { slot_id: "s1000", time_et: "10:00", idx: 30, kind: "盘中", targets: ["regular_60m", "regular_60m_move"] },
      { slot_id: "s1130", time_et: "11:30", idx: 120, kind: "盘中", targets: ["regular_60m", "regular_60m_move"] },
      { slot_id: "s1300", time_et: "13:00", idx: 210, kind: "盘中", targets: ["regular_60m", "regular_60m_move"] },
      { slot_id: "s1430", time_et: "14:30", idx: 300, kind: "盘中", targets: ["regular_60m", "regular_60m_move", "regular_to_close"] },
      { slot_id: "s1630_next", time_et: "16:30", idx: 420, kind: "盘后展望", targets: ["next_regular_session"] }
    ],
    half_day_example: { date: "2026-11-27", slots: ["08:30 盘前展望", "10:00 60 分钟", "11:30 60 分钟 + 至收盘", "13:30 盘后展望"], skipped: ["13:00", "14:30（窗口超过 13:00 收盘）"] },
    holiday_example: { date: "2026-11-26", note: "休市：不发；11-25 16:30 的盘后展望覆盖 11-27 半日市" }
  };
  // 槽位预测（虚构）：10:00 已结算，11:30 刚发布，其余未到时刻
  const SLOT_PROBS = {
    NVDA: [{ outperform: 0.37, flat: 0.35, underperform: 0.28 }, { outperform: 0.3, flat: 0.33, underperform: 0.37 }],
    AMD: [{ outperform: 0.34, flat: 0.35, underperform: 0.31 }, { outperform: 0.33, flat: 0.34, underperform: 0.33 }],
    AVGO: [{ outperform: 0.4, flat: 0.34, underperform: 0.26 }, { outperform: 0.35, flat: 0.36, underperform: 0.29 }],
    MU: [{ outperform: 0.31, flat: 0.33, underperform: 0.36 }, { outperform: 0.29, flat: 0.34, underperform: 0.37 }]
  };
  const SLOT_P50 = { NVDA: [0.05, -0.08], AMD: [0.02, 0.0], AVGO: [0.09, 0.04], MU: [-0.04, -0.07] };
  const slotInterval = (tk, p50) => { const sg = SIGMA[tk].regular_60m; return { quantiles: { p10: +(p50 - 1.28 * sg).toFixed(2), p50, p90: +(p50 + 1.28 * sg).toFixed(2) }, unit: "relative_pp", validated: false }; };
  SEC_META.forEach((m) => {
    const tk = m.ticker;
    predictions.push(mkPred({ id: "pred_" + tk.toLowerCase() + "_20261202_s1000_60m", slot: "s1000", ticker: tk, target_id: "regular_60m", status: "settled", sampling_rule: "schedule_slot", trigger_type: "scheduled", pubIdx: 30, t0Idx: 30, endIdx: 90, probabilities: SLOT_PROBS[tk][0], interval: slotInterval(tk, SLOT_P50[tk][0]) }));
    predictions.push(mkPred({ id: "pred_" + tk.toLowerCase() + "_20261202_s1130_60m", slot: "s1130", ticker: tk, target_id: "regular_60m", status: "awaiting_settlement", sampling_rule: "schedule_slot", trigger_type: "scheduled", pubIdx: 120, t0Idx: 120, endIdx: 180, probabilities: SLOT_PROBS[tk][1], interval: slotInterval(tk, SLOT_P50[tk][1]) }));
  });

  // ---- 0.5：预测与实际对照（D-44）：展示路径 sqrt_time_v1 + 实际分钟路径 ----
  function relPath(tk, i0, i1) {
    const b = securities[tk].bars, out = [];
    for (let i = i0; i <= Math.min(i1, NOW_IDX); i++) out.push({ min: i - i0, relative_pp: +((ret(b[i0].close, b[i].close) - ret(b[i0].benchmark_index, b[i].benchmark_index))).toFixed(3) });
    return out;
  }
  function fcPath(q, T) {
    const pts = [];
    for (let m = 0; m <= T; m += 5) { const f = Math.sqrt(m / T); pts.push({ min: m, p10: +(q.p10 * f).toFixed(3), p50: +(q.p50 * f).toFixed(3), p90: +(q.p90 * f).toFixed(3) }); }
    return { method: "sqrt_time_v1", unit: "relative_pp", points: pts };
  }
  const fva = {};
  SEC_META.forEach((m) => {
    const tk = m.ticker;
    fva[tk] = predictions.filter((p) => p.ticker === tk && p.schedule_slot_id).map((p) => {
      const q = p.interval.quantiles, T = p.target_end_idx - p.t0_idx;
      const actual = relPath(tk, p.t0_idx, p.target_end_idx);
      const st = p.settlement;
      const rel = st ? st.relative_return_pp : null;
      return {
        prediction_id: p.prediction_id, security_id: p.security_id, session_date: "2026-12-02", target_id: p.target_id, schedule_slot_id: p.schedule_slot_id,
        t0_idx: p.t0_idx, end_idx: p.target_end_idx, t0_at: p.t0_quote_ts, target_end_at: p.target_end_at, status: p.status,
        predicted_class: p.predicted_class, probabilities: p.probabilities,
        forecast_path: fcPath(q, T), actual_path: actual,
        outcome_class: st ? st.outcome_class : null, hit: st ? st.hit : null, brier: st ? st.brier : null,
        inside_p80: rel == null ? null : rel >= q.p10 && rel <= q.p90, // p10–p90 即 80% 中央区间
        inside_p90: rel == null ? null : Math.abs(rel - q.p50) <= 1.645 * SIGMA[tk].regular_60m,
        residual_pp: rel == null ? null : +(rel - q.p50).toFixed(2)
      };
    });
  });
  // 滚动准确率（虚构）：n < 30 时界面标"样本不足"
  const fvaRollups = {
    NVDA: { rolling_20d: { n_published: 80, n_settled: 76, n_abstained: 3, n_unsettleable: 1, hit_rate: 0.41, brier: 0.647, bss_class_frequency: 0.022, coverage_p80: 0.79, mean_abs_residual_pp: 0.44 }, since_live: { n_published: 212, n_settled: 201, n_abstained: 8, n_unsettleable: 3, hit_rate: 0.4, brier: 0.651, bss_class_frequency: 0.016, coverage_p80: 0.81, mean_abs_residual_pp: 0.46 } },
    AMD: { rolling_20d: { n_published: 80, n_settled: 75, n_abstained: 4, n_unsettleable: 1, hit_rate: 0.39, brier: 0.655, bss_class_frequency: 0.011, coverage_p80: 0.76, mean_abs_residual_pp: 0.52 }, since_live: { n_published: 212, n_settled: 199, n_abstained: 10, n_unsettleable: 3, hit_rate: 0.39, brier: 0.657, bss_class_frequency: 0.009, coverage_p80: 0.78, mean_abs_residual_pp: 0.53 } },
    AVGO: { rolling_20d: { n_published: 80, n_settled: 72, n_abstained: 7, n_unsettleable: 1, hit_rate: 0.42, brier: 0.644, bss_class_frequency: 0.027, coverage_p80: 0.82, mean_abs_residual_pp: 0.4 }, since_live: { n_published: 212, n_settled: 194, n_abstained: 15, n_unsettleable: 3, hit_rate: 0.41, brier: 0.649, bss_class_frequency: 0.019, coverage_p80: 0.8, mean_abs_residual_pp: 0.41 } },
    MU: { rolling_20d: { n_published: 80, n_settled: 74, n_abstained: 2, n_unsettleable: 4, hit_rate: 0.37, brier: 0.664, bss_class_frequency: -0.004, coverage_p80: 0.74, mean_abs_residual_pp: 0.61 }, since_live: { n_published: 212, n_settled: 197, n_abstained: 6, n_unsettleable: 9, hit_rate: 0.38, brier: 0.66, bss_class_frequency: 0.002, coverage_p80: 0.77, mean_abs_residual_pp: 0.6 } }
  };
  // 后台：按槽位汇总（四家合计，近 60 个交易日，虚构）
  const fvaBySlot = [
    { slot: "s1000", n: 228, hit_rate: 0.37, brier: 0.672, bss: -0.006, coverage_p80: 0.71, width_p80: 1.21, mean_residual: 0.07, calib_gap: 0.06, flag: "开盘后波动偏大：区间覆盖 71% 低于名义 80%，概率偏自信" },
    { slot: "s1130", n: 231, hit_rate: 0.41, brier: 0.648, bss: 0.021, coverage_p80: 0.8, width_p80: 0.98, mean_residual: 0.01, calib_gap: 0.02, flag: null },
    { slot: "s1300", n: 230, hit_rate: 0.4, brier: 0.651, bss: 0.017, coverage_p80: 0.81, width_p80: 0.92, mean_residual: -0.02, calib_gap: 0.02, flag: null },
    { slot: "s1430", n: 229, hit_rate: 0.42, brier: 0.645, bss: 0.025, coverage_p80: 0.83, width_p80: 0.95, mean_residual: 0.0, calib_gap: 0.03, flag: null },
    { slot: "s0830_pre_open", n: 58, hit_rate: 0.36, brier: 0.676, bss: -0.012, coverage_p80: 0.77, width_p80: 3.1, mean_residual: 0.12, calib_gap: 0.05, flag: "内部影子：模型验证中，不对外" },
    { slot: "s1630_next", n: 57, hit_rate: 0.38, brier: 0.669, bss: -0.003, coverage_p80: 0.79, width_p80: 3.3, mean_residual: 0.05, calib_gap: 0.04, flag: "内部影子：模型验证中，不对外" }
  ];
  const fvaCalib = { s1000: [[0.25, 0.3, 61, 0.22], [0.3, 0.35, 142, 0.27], [0.35, 0.4, 167, 0.3], [0.4, 0.45, 88, 0.33], [0.45, 0.55, 26, 0.35]], s1430: [[0.25, 0.3, 58, 0.27], [0.3, 0.35, 150, 0.33], [0.35, 0.4, 161, 0.37], [0.4, 0.45, 92, 0.43], [0.45, 0.55, 24, 0.49]] };
  const fvaReview = [
    { prediction_id: "pred_mu_20261124_s1000_60m", slot: "s1000", residual_pp: -1.9, cause: "同行业竞争对手盘中预告（新闻 9 分钟后才入库）", action: "新闻源延迟 → 来源健康告警阈值复核" },
    { prediction_id: "pred_nvda_20261120_s1300_60m", slot: "s1300", residual_pp: 1.6, cause: "指数调仓资金流（已在 fs-0.2 日历特征中，但权重日期有误）", action: "修正调仓日历；加入下一版数据集" },
    { prediction_id: "pred_amd_20261118_s1000_60m", slot: "s1000", residual_pp: -1.4, cause: "真正意外：无可得信息", action: "仅记录，不改模型" }
  ];

  // ---- evidence / events ----
  const evidence = [
    { evidence_id: "evd_fr_demo_1", event_id: "evt_policy_export_demo_001", doc_version_id: "docv_fr_demo_2026_12345_v1", source: "Federal Register（演示）", claim: "公开先进计算产品许可要求更新（虚构文本）", claimant: "BIS（演示）", verification_status: "primary_confirmed", source_published_at: "2026-12-02T15:58:30.000Z", source_published_precision: "s", received_at: "2026-12-02T15:58:41.200Z", available_at: "2026-12-02T15:59:05.000Z", visibility: "public" },
    { evidence_id: "evd_news_demo_2", event_id: "evt_policy_export_demo_001", doc_version_id: "docv_wire_demo_88_v1", source: "授权快讯（演示）", claim: "媒体报道规则可能覆盖部分数据中心 GPU（待公司确认）", claimant: "新闻机构（演示）", verification_status: "media_report", source_published_at: "2026-12-02T16:02:10.000Z", source_published_precision: "s", received_at: "2026-12-02T16:02:12.000Z", available_at: "2026-12-02T16:02:20.000Z", visibility: "public" },
    { evidence_id: "evd_ir_demo_3", event_id: "evt_policy_export_demo_001", doc_version_id: "docv_ir_demo_3_v1", source: "公司 IR（演示）", claim: "公司表示正在评估规则影响（虚构）", claimant: "公司（演示）", verification_status: "primary_confirmed", source_published_at: "2026-12-02T16:20:00.000Z", source_published_precision: "minute", received_at: "2026-12-02T16:20:31.000Z", available_at: "2026-12-02T16:20:40.000Z", visibility: "public" },
    { evidence_id: "evd_leak_demo_4", event_id: "evt_policy_export_demo_001", doc_version_id: "docv_unk_demo_4_v1", source: "来源不明文件（演示）", claim: "疑似未公开材料 —— 已暂停使用", claimant: "未知", verification_status: "pending", source_published_at: null, source_published_precision: "unknown", received_at: "2026-12-02T16:10:00.000Z", available_at: "2026-12-02T16:10:05.000Z", visibility: "restricted_review" },
    { evidence_id: "evd_deal_demo_5", event_id: "evt_deal_demo_002", doc_version_id: "docv_8k_demo_5_v1", source: "SEC 8-K（演示）", claim: "签署收购协议，最晚交割日 2027-03-31（虚构）", claimant: "公司（演示）", verification_status: "primary_confirmed", source_published_at: "2026-10-14T20:05:00.000Z", source_published_precision: "s", received_at: "2026-10-14T20:05:20.000Z", available_at: "2026-10-14T20:06:00.000Z", visibility: "public" },
    { evidence_id: "evd_deal_demo_6", event_id: "evt_deal_demo_002", doc_version_id: "docv_ftc_demo_6_v1", source: "监管公告（演示）", claim: "等待期届满（虚构）", claimant: "监管机构（演示）", verification_status: "primary_confirmed", source_published_at: "2026-11-20T14:00:00.000Z", source_published_precision: "minute", received_at: "2026-11-20T14:03:00.000Z", available_at: "2026-11-20T14:04:00.000Z", visibility: "public" },
    { evidence_id: "evd_mu_earn_7", event_id: "evt_mu_earnings_demo_003", doc_version_id: "docv_mu_pr_demo_7_v1", source: "公司财报新闻稿（演示）", claim: "下季营收指引中值高于事前共识（虚构）", claimant: "公司（演示）", verification_status: "primary_confirmed", source_published_at: "2026-12-01T21:05:00.000Z", source_published_precision: "s", received_at: "2026-12-01T21:05:04.000Z", available_at: "2026-12-01T21:05:40.000Z", visibility: "public" },
    { evidence_id: "evd_amd_cust_8", event_id: "evt_amd_customer_demo_004", doc_version_id: "docv_blog_demo_8_v1", source: "客户公开博客（演示）", claim: "某云客户宣布扩大 GPU 部署（供应商未明确，虚构）", claimant: "客户（演示）", verification_status: "media_report", source_published_at: "2026-12-02T14:50:00.000Z", source_published_precision: "minute", received_at: "2026-12-02T14:52:00.000Z", available_at: "2026-12-02T14:52:30.000Z", visibility: "public" }
  ];

  const events = [
    {
      event_id: "evt_policy_export_demo_001", category: "policy_export", identity_key: "policy:BIS:demo-2026-12345",
      title: "出口许可规则更新（演示事件）", tickers: ["NVDA", "AMD", "MU"],
      progress_status: "effective", evidence_status: "primary_confirmed", analysis_status: "partial", current_analysis_version: 2,
      question: "截止 2026-12-31 23:59 ET 前，公司是否公开确认指定型号获得出口许可？",
      outcomes: [
        { outcome: "license_confirmed", label: "截止前公开确认获得许可" },
        { outcome: "denial_confirmed", label: "截止前公开确认被拒" },
        { outcome: "no_confirmation", label: "截止前无公开确认" }
      ],
      outcome_prediction: { status: "published", display_tier: "scenario_only", abstain_reason: "model_not_validated", note: "该子类未通过验证：只展示情景与证据，不给数值概率" },
      linked_stock_predictions: ["pred_nvda_20261202_1101_60m", "pred_nvda_20261202_1101_close", "pred_amd_20261202_1101_60m"],
      // D-38 历史类比（虚构数字）
      historical_cases: { query_version: "hc-0.1", match_keys: { event_type: "policy_export", subtype: "rule_published", industry_template: "semiconductor", market_state: "regular" }, n: 11, period: "2022-10 至 2026-09", median_relative_pp: -0.9, iqr_pp: [-2.1, 0.3], hit_share_positive: 0.27, fallback_applied: false, fallback_level: "none", insufficient: false, target_id: "regular_to_close" },
      // D-39 事件结果结算规则
      outcome_resolution: { resolving_milestones: ["license_granted", "license_denied"], confirm_sources: ["company_8k", "regulator_release"], min_confirmations: 1, decision_body: "BIS（演示）", public_confirmation_rule: "首个官方公开确认时刻", legal_effective_rule: "许可生效日（可晚于公开确认）", outcome_conflict_rule: "官方来源冲突 → manual_review", no_result_rule: "截止无解决里程碑 → no_confirmation；来源不可核实 → unsettleable" },
      cross_industry: [{ template: "semiconductor", ticker: "NVDA", exposure: "收入敞口：受限型号出货（演示）" }, { template: "bank", ticker: "BANK_TEST（测试公司）", exposure: "无直接敞口；仅关注半导体客户信用（演示）" }],
      milestones: [
        { milestone_type: "rule_published", decision_body: "BIS（演示）", actual_at: "2026-12-02T15:58:30.000Z", status: "occurred", evidence_ids: ["evd_fr_demo_1"] },
        { milestone_type: "company_statement", decision_body: "公司", actual_at: "2026-12-02T16:20:00.000Z", status: "occurred", evidence_ids: ["evd_ir_demo_3"] },
        { milestone_type: "license_applied", decision_body: "公司", expected_at: "2026-12-10T21:00:00.000Z", status: "scheduled", evidence_ids: [] },
        { milestone_type: "license_granted", decision_body: "BIS（演示）", expected_at: "2027-01-01T04:59:00.000Z", status: "scheduled", evidence_ids: [] },
        { milestone_type: "shipment_confirmed", decision_body: "公司", expected_at: "2027-01-31T21:00:00.000Z", status: "scheduled", evidence_ids: [] }
      ],
      versions: [
        { analysis_version: 1, analysis_kind: "flash", analysis_as_of: "2026-12-02T16:00:30.000Z", published_at: "2026-12-02T16:00:41.000Z", summary: "核实快报：规则原文已公开，影响范围待公司确认" },
        { analysis_version: 2, analysis_kind: "full", analysis_as_of: "2026-12-02T16:25:00.000Z", published_at: "2026-12-02T16:26:10.000Z", summary: "完整分析：加入公司声明；解释状态 partial" }
      ]
    },
    {
      event_id: "evt_deal_demo_002", category: "m_and_a", identity_key: "deal:AVGO:demo-target:2026-10-14",
      title: "收购交割（演示事件）", tickers: ["AVGO"],
      progress_status: "pending", evidence_status: "primary_confirmed", analysis_status: "complete", current_analysis_version: 3,
      question: "交易双方是否在 2027-03-31 23:59 ET 前公开确认完成交割？",
      outcomes: [
        { outcome: "closing_confirmed", label: "截止前公开确认交割" },
        { outcome: "termination_confirmed", label: "截止前公开确认终止" },
        { outcome: "no_confirmation", label: "截止前无两类确认" }
      ],
      outcome_prediction: { status: "published", display_tier: "scenario_only", abstain_reason: "model_not_validated", note: "并购交割子类样本不足：展示同阶段历史参照（虚构 n=14）" },
      linked_stock_predictions: [],
      historical_cases: { query_version: "hc-0.1", match_keys: { event_type: "m_and_a", subtype: "post_clearance_pre_vote", industry_template: "semiconductor", market_state: "regular" }, n: 14, period: "2015-01 至 2026-06", median_relative_pp: 0.2, iqr_pp: [-0.6, 1.1], hit_share_positive: 0.57, fallback_applied: true, fallback_level: "peer_group", insufficient: false, target_id: "regular_to_close", fallback_note: "同公司同子类仅 5 例 < 8，已放宽到同模板公司" },
      outcome_resolution: { resolving_milestones: ["closing", "termination"], confirm_sources: ["company_8k", "official_registry"], min_confirmations: 1, decision_body: "双方 + 监管机构（演示）", public_confirmation_rule: "首个官方公开确认时刻（8-K 或新闻稿）", legal_effective_rule: "交割生效时刻（可晚于公告）", outcome_conflict_rule: "官方来源冲突 → manual_review", no_result_rule: "截止无交割/终止确认 → no_confirmation", clearance_note: "监管放行（regulatory_clearance）≠ 交割完成（closing），不会据此结算为 closing_confirmed" },
      conditional_forecasts: [{ prediction_id: "pred_avgo_cond_termination_close", status: "awaiting_trigger", condition_outcome: "termination_confirmed", condition_label: "若公开确认交易终止", inner_target_id: "regular_to_close", trigger_deadline_at: "2027-04-01T03:59:00.000Z", quote_rule_after_trigger: "触发后首个同步合格报价起算，至当场官方收盘", display_tier: "scenario_only", note: "未触发前不计分；截止仍未触发 → not_triggered，只计入 trigger_rate" }],
      milestones: [
        { milestone_type: "agreement_signed", decision_body: "双方董事会", actual_at: "2026-10-14T20:05:00.000Z", status: "occurred", evidence_ids: ["evd_deal_demo_5"] },
        { milestone_type: "regulatory_clearance", decision_body: "监管机构（演示）", actual_at: "2026-11-20T14:00:00.000Z", status: "occurred", evidence_ids: ["evd_deal_demo_6"] },
        { milestone_type: "shareholder_vote", decision_body: "目标公司股东", expected_at: "2027-01-15T15:00:00.000Z", status: "scheduled", evidence_ids: [] },
        { milestone_type: "closing", decision_body: "双方", expected_at: "2027-04-01T03:59:00.000Z", status: "scheduled", evidence_ids: [] }
      ],
      versions: [
        { analysis_version: 1, analysis_kind: "full", analysis_as_of: "2026-10-14T20:30:00.000Z", published_at: "2026-10-14T20:31:00.000Z", summary: "协议签署" },
        { analysis_version: 2, analysis_kind: "full", analysis_as_of: "2026-11-20T14:30:00.000Z", published_at: "2026-11-20T14:31:00.000Z", summary: "新增监管放行节点；交割仍待决" },
        { analysis_version: 3, analysis_kind: "full", analysis_as_of: "2026-11-25T15:00:00.000Z", published_at: "2026-11-25T15:01:00.000Z", summary: "补充股东投票日程" }
      ]
    },
    {
      event_id: "evt_mu_earnings_demo_003", category: "earnings_guidance", identity_key: "earnings:co_micron:FY2027Q1",
      title: "季度财报与指引（演示事件）", tickers: ["MU"],
      progress_status: "outcome_confirmed", evidence_status: "primary_confirmed", analysis_status: "complete", current_analysis_version: 2,
      question: null, outcomes: [], outcome_prediction: { status: "not_applicable", note: "无开放的事件结果问题" },
      linked_stock_predictions: ["pred_mu_20261202_1105_60m"],
      historical_cases: { query_version: "hc-0.1", match_keys: { event_type: "earnings_guidance", subtype: "guide_above", industry_template: "semiconductor", market_state: "post_market", surprise_bucket: "above" }, n: 6, period: "2019-01 至 2026-09", median_relative_pp: null, iqr_pp: null, hit_share_positive: null, fallback_applied: true, fallback_level: "sector_wide", insufficient: true, target_id: "next_regular_session", fallback_note: "放宽到 sector_wide 仍只有 6 例 < 8" },
      milestones: [{ milestone_type: "earnings_release", decision_body: "公司", actual_at: "2026-12-01T21:05:00.000Z", status: "occurred", evidence_ids: ["evd_mu_earn_7"] }],
      versions: [
        { analysis_version: 1, analysis_kind: "flash", analysis_as_of: "2026-12-01T21:10:00.000Z", published_at: "2026-12-01T21:11:00.000Z", summary: "核实快报：已确认财务数据；共识尚未到达" },
        { analysis_version: 2, analysis_kind: "full", analysis_as_of: "2026-12-01T22:30:00.000Z", published_at: "2026-12-01T22:31:00.000Z", summary: "完整分析：营收指引中值较共识 +4.3%（虚构）" }
      ]
    },
    {
      event_id: "evt_amd_customer_demo_004", category: "customer_demand", identity_key: "customer:demo-cloud:2026-12-02",
      title: "云客户扩大部署（演示事件）", tickers: ["AMD", "NVDA"],
      progress_status: "pending", evidence_status: "media_report", analysis_status: "needs_review", current_analysis_version: 1,
      question: null, outcomes: [], outcome_prediction: { status: "not_applicable", note: "供应商未明确，进入人工复核" },
      linked_stock_predictions: [],
      milestones: [{ milestone_type: "customer_statement", decision_body: "客户", actual_at: "2026-12-02T14:50:00.000Z", status: "occurred", evidence_ids: ["evd_amd_cust_8"] }],
      versions: [{ analysis_version: 1, analysis_kind: "flash", analysis_as_of: "2026-12-02T15:00:00.000Z", published_at: "2026-12-02T15:01:00.000Z", summary: "待证实：未指明供应商，暂不分配到单一公司" }]
    }
  ];

  // ---- 0.6：第 1 步信息采集（D-45）与第 2 步推理链（D-46），全部虚构 ----
  const CHANNEL_LABEL = { filing: "SEC 文件", insider_filing: "Form 4", company_ir: "公司 IR", news_wire: "新闻快讯", policy: "政策/监管", court: "法院案卷", macro: "宏观", expectation: "预期/共识", peer_company: "同行/客户", market_data: "行情", user_submission: "用户提交" };
  const CATEGORY_LABEL = { policy_export: "出口政策", earnings_guidance: "财报与指引", customer_demand: "客户需求", supply_chain: "供应链", m_and_a: "并购", litigation: "诉讼", management: "管理层", product: "产品", capital_return: "回购分红", macro: "宏观", analyst_rating: "分析师评级", insider_trade: "内部人交易", market_data: "行情", other: "其他" };
  const DISPOSITION_LABEL = { kept: ["保留 · 进入分析", "good"], duplicate: ["重复/转载", "neutral"], excluded_irrelevant: ["排除 · 不相关", "neutral"], excluded_after_asof: ["排除 · 晚于分析截止", "warn"], excluded_restricted: ["排除 · 受限复核", "crit"], pending_review: ["待人工复核", "warn"], fetch_failed: ["抓取失败", "serious"] };
  // ET 时刻 → UTC ISO（2026-12-01/02 均为 EST，UTC−5）
  const et = (d, hms) => { const [h, m, s] = hms.split(":").map(Number); return new Date(Date.UTC(2026, 11, d, h + 5, m, s || 0)).toISOString(); };
  let ITEM_SEQ = 0;
  function item(tk, ch, cat, title, disp, d, pub, o) {
    o = o || {};
    const pubIso = pub ? et(d, pub) : null;
    const rec = new Date(Date.parse(pubIso || et(d, o.rec || "00:00:00")) + (o.recLag != null ? o.recLag : 12) * 1000).toISOString();
    const av = new Date(Date.parse(rec) + (o.avLag != null ? o.avLag : 20) * 1000).toISOString();
    ITEM_SEQ++;
    return Object.assign({
      item_id: "itm_" + tk.toLowerCase() + "_" + String(ITEM_SEQ).padStart(3, "0"), channel: ch, category: cat, title,
      disposition: disp, exclusion_reason: null, duplicate_of: null, relevance: disp === "excluded_irrelevant" ? 0.3 : 0.85,
      occurred_at: o.occ ? et(d, o.occ) : pubIso, source_published_at: pubIso, source_published_precision: o.prec || "s", received_at: rec, available_at: av,
      linked_event_id: null, linked_evidence_ids: [], source: o.source || CHANNEL_LABEL[ch] + "（演示）", new_in_run: false
    }, o.x || {});
  }
  function baseItems(tk) {
    const L = tk.toLowerCase();
    const policyTk = ["NVDA", "AMD", "MU"].includes(tk);
    const a = [];
    // 行情：汇总项（不逐条存储每秒报价）
    a.push(item(tk, "market_data", "market_data", tk + " 与同行篮子 11 只 1 秒 NBBO：报价 7,1xx 条，合格率 98.9%，同步成功率 97.2%（汇总项）", "kept", 2, "11:29:59", { recLag: 0, avLag: 1, source: "行情供应商（拟选）", x: { quote_summary: true, new_in_run: true } }));
    // 宏观
    a.push(item(tk, "macro", "macro", "ISM 制造业 PMI 发布（10:00 ET，虚构数值）", "kept", 2, "10:00:00", { source: "宏观日历（演示）" }));
    a.push(item(tk, "macro", "macro", "联储官员公开讲话（未涉及利率路径，虚构）", "excluded_irrelevant", 2, "09:40:00", { prec: "minute", x: { exclusion_reason: "未涉及货币政策或行业，relevance 0.22" } }));
    // 政策
    if (policyTk) {
      a.push(item(tk, "policy", "policy_export", "Federal Register：先进计算产品许可要求更新（虚构文本）", "kept", 2, "10:58:30", { recLag: 11, avLag: 24, source: "Federal Register（演示）", x: { linked_event_id: "evt_policy_export_demo_001", linked_evidence_ids: ["evd_fr_demo_1"] } }));
      a.push(item(tk, "policy", "policy_export", "BIS 新闻稿：同一规则的说明（虚构）", "kept", 2, "11:01:00", { prec: "minute", source: "BIS（演示）", x: { linked_event_id: "evt_policy_export_demo_001" } }));
      a.push(item(tk, "policy", "other", "白宫简报提及\"芯片\"一词（未点名受影响产品，虚构）", "excluded_irrelevant", 2, "09:15:00", { prec: "minute", x: { exclusion_reason: "只顺带提及，未涉及规则或公司" } }));
      a.push(item(tk, "news_wire", "policy_export", "快讯：规则可能覆盖部分数据中心 GPU（待公司确认）", "kept", 2, "11:02:10", { recLag: 2, avLag: 8, source: "授权快讯（演示）", x: { linked_event_id: "evt_policy_export_demo_001", linked_evidence_ids: ["evd_news_demo_2"] } }));
      const orig = a[a.length - 1].item_id;
      a.push(item(tk, "news_wire", "policy_export", "转载：规则可能覆盖部分数据中心 GPU（媒体 B）", "duplicate", 2, "11:03:40", { x: { duplicate_of: orig, exclusion_reason: "同源转载（independent_origin_key 相同），不计为独立来源" } }));
      a.push(item(tk, "news_wire", "policy_export", "转载：规则可能覆盖部分数据中心 GPU（媒体 C）", "duplicate", 2, "11:05:15", { x: { duplicate_of: orig, exclusion_reason: "同源转载" } }));
      a.push(item(tk, "news_wire", "policy_export", "转载：同一快讯重复投递（content_hash 相同）", "duplicate", 2, "11:02:10", { recLag: 95, x: { duplicate_of: orig, exclusion_reason: "重复投递，幂等合并" } }));
      a.push(item(tk, "news_wire", "other", "来源不明文件（疑似未公开材料）", "excluded_restricted", 2, null, { rec: "11:10:00", recLag: 0, prec: "unknown", source: "来源不明（演示）", x: { exclusion_reason: "受限复核：暂停使用，从界面与预测输入排除", linked_evidence_ids: ["evd_leak_demo_4"] } }));
      a.push(item(tk, "news_wire", "policy_export", "快讯：行业协会回应新规（11:31 才可用）", "excluded_after_asof", 2, "11:31:05", { x: { exclusion_reason: "available_at 晚于本次分析截止 11:30:00，留给下一次运行", new_in_run: true } }));
    }
    // 常见新闻噪声
    a.push(item(tk, "news_wire", "other", "盘前涨跌幅榜（自动生成稿件）", "excluded_irrelevant", 2, "08:45:00", { x: { exclusion_reason: "行情汇总类稿件，无新信息" } }));
    a.push(item(tk, "news_wire", "product", "AI 服务器需求综述文章（未含新数据）", "excluded_irrelevant", 2, "07:30:00", { prec: "minute", x: { exclusion_reason: "无新事实，relevance 0.31" } }));
    a.push(item(tk, "news_wire", "analyst_rating", "券商维持评级与目标价（虚构）", "kept", 2, "07:05:00", { prec: "minute", source: "授权快讯（演示）" }));
    a.push(item(tk, "filing", "other", "13F-HR：某机构季度持仓（含 " + tk + "，虚构）", "excluded_irrelevant", 1, "17:20:00", { x: { exclusion_reason: "季度持仓、滞后 45 天，不作盘中驱动" } }));
    a.push(item(tk, "insider_filing", "insider_trade", "Form 4：董事出售（10b5-1 计划，虚构）", "kept", 1, "18:02:00", { source: "SEC EDGAR（演示）", x: { exclusion_reason: "10b5-1：只展示，不进特征（AC-48）" } }));
    a.push(item(tk, "insider_filing", "insider_trade", "Form 4：限制性股票归属扣税（代码 F，虚构）", "kept", 1, "18:05:00", { source: "SEC EDGAR（演示）", x: { exclusion_reason: "代码 F：只展示" } }));
    a.push(item(tk, "expectation", "earnings_guidance", "共识快照更新：下季营收共识（point-in-time，虚构）", "kept", 2, "06:00:00", { source: "共识供应商（拟选）" }));
    a.push(item(tk, "company_ir", "other", "IR 活动日程更新（例行会议安排）", "excluded_irrelevant", 1, "20:00:00", { prec: "minute", x: { exclusion_reason: "例行日程，无新信息" } }));
    a.push(item(tk, "news_wire", "other", "新闻源 B：抓取超时（3 次重试后放弃，演示）", "fetch_failed", 2, null, { rec: "11:29:30", recLag: 0, prec: "unknown", source: "新闻源 B（演示）", x: { exclusion_reason: "source_timeout：已记录到数据源健康，不视为\"无新闻\"" } }));
    a.push(item(tk, "peer_company", "earnings_guidance", "MU 昨日盘后财报：指引高于共识（同行，虚构）", tk === "MU" ? "kept" : "kept", 1, "16:05:00", { source: "MU 新闻稿（演示）", x: { linked_event_id: "evt_mu_earnings_demo_003", linked_evidence_ids: tk === "MU" ? ["evd_mu_earn_7"] : [] } }));
    return a;
  }
  const extraItems = {
    NVDA: (tk) => [
      item(tk, "company_ir", "policy_export", "公司 IR：正在评估规则影响（虚构）", "kept", 2, "11:20:00", { prec: "minute", recLag: 31, avLag: 9, source: "NVIDIA IR（演示）", x: { linked_event_id: "evt_policy_export_demo_001", linked_evidence_ids: ["evd_ir_demo_3"] } }),
      item(tk, "peer_company", "policy_export", "AMD 公司就同一规则发表评估（同行，虚构）", "kept", 2, "11:12:00", { prec: "minute", source: "AMD IR（演示）", x: { linked_event_id: "evt_policy_export_demo_001" } }),
      item(tk, "peer_company", "customer_demand", "云客户博客：扩大 GPU 部署（供应商未明确，虚构）", "pending_review", 2, "09:50:00", { prec: "minute", source: "客户公开博客（演示）", x: { linked_event_id: "evt_amd_customer_demo_004", linked_evidence_ids: ["evd_amd_cust_8"], exclusion_reason: "未指明供应商，人工复核中，暂不归因到 NVDA" } }),
      item(tk, "court", "litigation", "法院案卷：专利案（无新条目）", "kept", 2, "06:00:00", { source: "CourtListener（演示）", x: { title_note: "轮询成功，0 条新案卷" } }),
      item(tk, "news_wire", "supply_chain", "供应链报道：封装产能扩张（未提及新订单，虚构）", "excluded_irrelevant", 2, "08:10:00", { prec: "minute", x: { exclusion_reason: "无新事实，relevance 0.35" } })
    ],
    AMD: (tk) => [
      item(tk, "company_ir", "policy_export", "AMD IR：正在评估规则影响（虚构）", "kept", 2, "11:12:00", { prec: "minute", source: "AMD IR（演示）", x: { linked_event_id: "evt_policy_export_demo_001" } }),
      item(tk, "peer_company", "customer_demand", "云客户博客：扩大 GPU 部署（供应商未明确，虚构）", "pending_review", 2, "09:50:00", { prec: "minute", source: "客户公开博客（演示）", x: { linked_event_id: "evt_amd_customer_demo_004", linked_evidence_ids: ["evd_amd_cust_8"], exclusion_reason: "未指明供应商，人工复核中" } })
    ],
    AVGO: (tk) => [
      item(tk, "filing", "m_and_a", "8-K：收购交割时间表（10-14 签署，虚构，历史条目）", "kept", 2, "06:00:00", { source: "SEC EDGAR（演示）", x: { linked_event_id: "evt_deal_demo_002", linked_evidence_ids: ["evd_deal_demo_5"], title_note: "待决事件的已有证据，今日无新节点" } }),
      item(tk, "news_wire", "m_and_a", "快讯：交易进展评论（无新事实，虚构）", "excluded_irrelevant", 2, "09:20:00", { prec: "minute", x: { exclusion_reason: "评论稿，无新节点" } })
    ],
    MU: (tk) => [
      item(tk, "company_ir", "earnings_guidance", "MU 电话会文字稿（昨日盘后，虚构）", "kept", 1, "18:30:00", { prec: "minute", source: "MU IR（演示）", x: { linked_event_id: "evt_mu_earnings_demo_003" } }),
      item(tk, "news_wire", "earnings_guidance", "转载：MU 指引高于共识（媒体 B）", "duplicate", 1, "16:09:00", { x: { exclusion_reason: "同源转载" } }),
      item(tk, "market_data", "market_data", "MU 10:00 前后停牌 3 分钟（LULD，演示）", "kept", 2, "10:01:00", { source: "交易所状态（演示）" })
    ]
  };
  const collections = {};
  SEC_META.forEach((m) => {
    const tk = m.ticker; ITEM_SEQ = 0;
    const items = baseItems(tk).concat(extraItems[tk](tk)).sort((a, b) => Date.parse(b.available_at) - Date.parse(a.available_at));
    const count = (k, v) => items.filter((i) => i[k] === v).length;
    const by = (k) => items.reduce((o, i) => ((o[i[k]] = (o[i[k]] || 0) + 1), o), {});
    collections[tk] = {
      run: {
        collection_run_id: "col_" + tk.toLowerCase() + "_20261202_1129", pipeline_run_id: "plr_" + tk.toLowerCase() + "_20261202_1129", snapshot_id: "snap_" + tk.toLowerCase() + "_20261202_120",
        window_from: et(1, "16:00:00"), window_to: et(2, "11:30:00"), started_at: et(2, "11:29:12"), finished_at: et(2, "11:29:41"),
        sources_polled: [
          { source_id: "src_md_primary", channel: "market_data", status: "ok", items_fetched: 1, latency_ms: 620 },
          { source_id: "src_sec_edgar", channel: "filing", status: "ok", items_fetched: count("channel", "filing") + count("channel", "insider_filing"), latency_ms: 1840 },
          { source_id: "src_company_ir", channel: "company_ir", status: "ok", items_fetched: count("channel", "company_ir"), latency_ms: 2100 },
          { source_id: "src_news_a", channel: "news_wire", status: "ok", items_fetched: count("channel", "news_wire") - 1, latency_ms: 900 },
          { source_id: "src_news_b", channel: "news_wire", status: "timeout", items_fetched: 0, latency_ms: 15000 },
          { source_id: "src_fedreg", channel: "policy", status: "ok", items_fetched: count("channel", "policy"), latency_ms: 1300 },
          { source_id: "src_courtlistener", channel: "court", status: "ok", items_fetched: count("channel", "court"), latency_ms: 2600 },
          { source_id: "src_macro_cal", channel: "macro", status: "ok", items_fetched: count("channel", "macro"), latency_ms: 400 },
          { source_id: "src_consensus", channel: "expectation", status: "ok", items_fetched: count("channel", "expectation"), latency_ms: 700 }
        ],
        counts: { fetched: items.length, kept: count("disposition", "kept"), duplicate: count("disposition", "duplicate"), excluded: items.filter((i) => i.disposition.startsWith("excluded")).length, pending_review: count("disposition", "pending_review"), failed: count("disposition", "fetch_failed"), new_in_run: items.filter((i) => i.new_in_run || Date.parse(i.available_at) >= Date.parse(et(2, "11:25:00"))).length, by_channel: by("channel"), by_category: by("category") }
      },
      items
    };
  });
  // 第 2 步推理链（D-46）：确定性步骤用行情数字自动生成，其余为演示文本
  const findItem = (tk, pred) => (collections[tk].items.find(pred) || {}).item_id;
  function reasoningFor(tk) {
    const b = securities[tk].bars, now = NOW_IDX, pc = securities[tk].prev_close;
    const day = ret(pc, b[now].close), bm = +((b[now].benchmark_index / 100 - 1) * 100).toFixed(2), rel = +(day - bm).toFixed(2);
    const fr = findItem(tk, (i) => i.title.startsWith("Federal Register")), news = findItem(tk, (i) => i.title.startsWith("快讯：规则")), ir = findItem(tk, (i) => i.channel === "company_ir" && i.category === "policy_export");
    const md = findItem(tk, (i) => i.quote_summary), pend = findItem(tk, (i) => i.disposition === "pending_review"), late = findItem(tk, (i) => i.disposition === "excluded_after_asof");
    const peer = findItem(tk, (i) => i.title.startsWith("AMD 公司就")), macro = findItem(tk, (i) => i.title.startsWith("ISM")), mu = findItem(tk, (i) => i.title.startsWith("MU 昨日"));
    const step1 = { kind: "market_fact", rule: "相对收益 = 个股相对前收 − 同行篮子（剔除自身等权）", conclusion: `11:29:59 ${tk} ${day >= 0 ? "+" : ""}${day}%，同行篮子 ${bm >= 0 ? "+" : ""}${bm}%，相对 ${rel >= 0 ? "+" : ""}${rel}pp`, refs: { quote_ids: ["rq_" + tk.toLowerCase() + "_119"], item_ids: [md] }, confidence: "high", by: "code" };
    if (tk === "NVDA" || tk === "AMD") {
      const d0 = ret(b[89].close, b[now].close), m0 = ret(b[89].benchmark_index, b[now].benchmark_index);
      return [step1,
        { kind: "timing_check", rule: "证据可用时间必须早于异动开始，才可作为原因候选", conclusion: `规则原文 10:59:05 可用；明显下跌从 11:00 开始 → 时间顺序允许作为原因候选。11:31 才可用的协会回应不纳入。`, refs: { item_ids: [fr, late], quote_ids: ["rq_" + tk.toLowerCase() + "_89"] }, confidence: "high", by: "code" },
        { kind: "evidence_fact", rule: "只陈述来源原文与核验状态", conclusion: "规则原文与 BIS 说明为原始来源确认；快讯（含 3 条转载，计 1 个独立来源）为媒体报道。", refs: { item_ids: [fr, news] }, confidence: "high", by: "code" },
        { kind: "evidence_fact", rule: "公司表态", conclusion: tk === "NVDA" ? "公司 11:20 表示正在评估影响，未确认受影响型号。" : "AMD 11:12 表示正在评估影响。", refs: { item_ids: [ir] }, confidence: "high", by: "code" },
        { kind: "attribution", rule: "条件表述；必须引用", conclusion: "许可范围可能影响部分数据中心出货（待公司确认）——作为可能驱动，非已证实原因。", refs: { item_ids: [fr, news, ir] }, confidence: "medium", by: "llm_draft · reviewed" },
        { kind: "counter_check", rule: "拆分行业同步部分", conclusion: d0 < m0 ? `11:00 以来个股 ${d0}%、篮子 ${m0}% → 约 ${Math.round((m0 / d0) * 100)}% 的跌幅与行业同步，其余为公司特有部分，不能全部归因于规则。` : `11:00 以来个股 ${d0}%、篮子 ${m0}% → 个股跌幅不大于行业，下跌主要与行业同步，公司特有影响不明显。`, refs: { quote_ids: ["rq_" + tk.toLowerCase() + "_89", "rq_" + tk.toLowerCase() + "_119"], item_ids: [peer].filter(Boolean) }, confidence: "high", by: "code" },
        { kind: "analogue", rule: "历史类比 hc-0.1，只作参考", conclusion: "同类出口规则发布日 11 例，至收盘相对篮子中位 −0.9pp（虚构）。", refs: { analysis_ids: ["evt_policy_export_demo_001"] }, confidence: "low", by: "code" },
        { kind: "gap", rule: "列出未解释与未使用的信息", conclusion: (tk === "NVDA" ? "NVDA 相对 AMD 的额外跌幅未解释。" : "早盘相对走强原因未解释。") + "云客户博客未指明供应商，复核中，未使用。新闻源 B 超时，不能视为\"无新闻\"。", refs: { item_ids: [pend, findItem(tk, (i) => i.disposition === "fetch_failed")] }, confidence: "medium", by: "code" },
        { kind: "conclusion", rule: "解释状态与预测交接", conclusion: "解释状态：部分解释（partial）。交接：股价反应 ready，仅放行行情基线（事件增强模型未对 policy_export 验证）。", refs: { analysis_ids: ["eav_policy_demo_001_" + tk.toLowerCase() + "_v2"] }, confidence: "high", by: "code" }
      ];
    }
    if (tk === "MU") return [step1,
      { kind: "evidence_fact", rule: "只陈述来源原文", conclusion: "昨日 16:05 财报：下季营收指引中值高于事前共识（虚构）；电话会文字稿已入库。", refs: { item_ids: [mu, findItem(tk, (i) => i.title.startsWith("MU 电话会"))] }, confidence: "high", by: "code" },
      { kind: "timing_check", rule: "盘后信息影响次日", conclusion: "财报在盘后发布，今日开盘表现属于事件后反应；盘后涨幅是过去行情，不是预测命中。", refs: { item_ids: [mu] }, confidence: "high", by: "code" },
      { kind: "counter_check", rule: "行业同步", conclusion: `同行篮子今日 ${bm}%，MU 相对篮子 ${rel >= 0 ? "+" : ""}${rel}pp：财报后走势未延续，相对弱势原因列为未解释。10:00 前后停牌 3 分钟，该时段报价不合格。`, refs: { item_ids: [md, findItem(tk, (i) => i.title.startsWith("MU 10:00"))] }, confidence: "high", by: "code" },
      { kind: "conclusion", rule: "解释状态与交接", conclusion: "解释状态：事件已确认（supported），但今日相对弱势未解释。交接：股价反应 ready。", refs: { analysis_ids: ["eav_mu_earnings_demo_003_v2"] }, confidence: "high", by: "code" }];
    return [step1,
      { kind: "evidence_fact", rule: "检查监测范围内新信息", conclusion: "本交易日 AVGO 无新催化剂；并购事件待决，今日无新节点。宏观 10:00 有 PMI 发布。", refs: { item_ids: [findItem(tk, (i) => i.title.startsWith("8-K")), macro] }, confidence: "high", by: "code" },
      { kind: "gap", rule: "列出缺口", conclusion: "10:10 前后相对上行原因未解释；新闻源 B 超时；11:25 时篮子 2 个成分同步报价缺失 → 当时的 60 分钟预测弃预测（11:30 已恢复）。", refs: { item_ids: [findItem(tk, (i) => i.disposition === "fetch_failed"), md] }, confidence: "medium", by: "code" },
      { kind: "conclusion", rule: "解释状态与交接", conclusion: "解释状态：证据不足（insufficient）。交接：股价反应 missing_inputs（11:25 基准不可用，下一槽位重新检查）。", refs: { analysis_ids: [] }, confidence: "high", by: "code" }];
  }
  const reasoning = {};
  SEC_META.forEach((m) => { reasoning[m.ticker] = reasoningFor(m.ticker).map((s, i) => Object.assign({ step: i + 1 }, s)); });

  // ---- current explanations (snapshot-level) ----
  const explanations = {
    NVDA: { explanation_status: "partial", new_catalyst_found: true, event_analysis_ids: ["eav_policy_demo_001_nvda_v2"], trigger_type: "event",
      data_quality: "ok", run_state: "complete", quality_issues: [], last_valid_at: "2026-12-02T16:30:00.000Z", valid_until: "2026-12-02T16:40:00.000Z",
      valuation_context: { as_of: "2026-12-01", fwd_pe: 31.5, fwd_pe_pctile_3y: 0.42, peer_median_fwd_pe: 24.0, note: "远期市盈率处于近 3 年 42 分位（虚构）" },
      observed_facts: ["10:58:30 ET 规则原文公开（演示）", "同行篮子同时段下跌"], possible_drivers: ["许可范围可能影响部分数据中心出货（待确认）"],
      counter_evidence: ["约三分之一跌幅与行业同步（见推理第 6 步）"], unexplained: ["NVDA 相对 AMD 的额外跌幅"], concurrent: ["同时段无宏观数据发布（监测范围内）"] },
    AMD: { explanation_status: "partial", new_catalyst_found: true, event_analysis_ids: ["eav_policy_demo_001_amd_v2"], trigger_type: "event",
      data_quality: "ok", run_state: "complete", quality_issues: [], last_valid_at: "2026-12-02T16:30:00.000Z", valid_until: "2026-12-02T16:40:00.000Z",
      valuation_context: { as_of: "2026-12-01", fwd_pe: 28.0, fwd_pe_pctile_3y: 0.35, peer_median_fwd_pe: 24.0, note: "远期市盈率处于近 3 年 35 分位（虚构）" },
      observed_facts: ["同一规则涉及 AMD（演示）"], possible_drivers: ["规则影响范围"], counter_evidence: ["云客户扩大部署报道（待证实，供应商不明）"], unexplained: ["早盘相对走强原因"], concurrent: [] },
    AVGO: { explanation_status: "insufficient", new_catalyst_found: false, event_analysis_ids: [], trigger_type: "scheduled",
      data_quality: "partial", run_state: "degraded", quality_issues: [{ source_id: "src_md_primary", issue: "篮子 2 个成分同步报价缺失" }, { source_id: "src_news_a", issue: "延迟", lag_s: 540 }], last_valid_at: "2026-12-02T16:20:00.000Z", valid_until: "2026-12-02T16:40:00.000Z",
      valuation_context: null,
      observed_facts: ["监测来源范围内暂未发现新催化剂"], possible_drivers: [], counter_evidence: [], unexplained: ["10:10 ET 前后相对上行"], concurrent: ["并购事件处于待决阶段，今日无新节点"] },
    MU: { explanation_status: "supported", new_catalyst_found: false, event_analysis_ids: ["eav_mu_earnings_demo_003_v2"], trigger_type: "market_move",
      data_quality: "ok", run_state: "complete", quality_issues: [], last_valid_at: "2026-12-02T16:30:00.000Z", valid_until: "2026-12-02T16:40:00.000Z",
      valuation_context: { as_of: "2026-12-01", fwd_pe: 11.2, fwd_pe_pctile_3y: 0.18, peer_median_fwd_pe: 24.0, note: "周期股：远期市盈率处于近 3 年 18 分位（虚构）" },
      observed_facts: ["昨日盘后财报指引高于共识（演示）", "今日行业下跌"], possible_drivers: ["财报后延续"], counter_evidence: ["10:00 前后短暂停牌 3 分钟"], unexplained: [], concurrent: [] }
  };

  // ---- admin: training ----
  const trainingRuns = [
    { training_run_id: "tr_20261206_event_v1", target_id: "regular_60m", model_family: "market_event_logit", param_layers: "market_sector", dataset_version_id: "ds_regular_60m_20261206_v1", trigger: "scheduled_weekly", status: "completed", stage: "evaluating", started_at: "2026-12-07T11:00:00Z", finished_at: "2026-12-07T11:47:00Z", code_version: "a1b2c3d", random_seed: 7, error: null, scope: "NVDA, AMD, AVGO, MU（训练池：半导体 12 只）" },
    { training_run_id: "tr_20261206_company_v1", target_id: "regular_60m", model_family: "market_logit", param_layers: "market_sector_company", dataset_version_id: "ds_regular_60m_20261206_v1", trigger: "manual", status: "completed", stage: "evaluating", started_at: "2026-12-07T12:00:00Z", finished_at: "2026-12-07T12:31:00Z", code_version: "a1b2c3d", random_seed: 7, error: null, scope: "NVDA, AMD, AVGO, MU" },
    { training_run_id: "tr_20261206_close_v0", target_id: "regular_to_close", model_family: "market_logit", param_layers: "market", dataset_version_id: "ds_regular_to_close_20261206_v1", trigger: "manual", status: "failed", stage: "building_dataset", started_at: "2026-12-07T13:00:00Z", finished_at: "2026-12-07T13:04:00Z", code_version: "a1b2c3d", random_seed: 7, error: { code: "AVAILABILITY_CHECK_FAILED", message: "3,304 条新闻样本 source_published_precision=day，无法用于盘中训练（演示）" }, scope: "NVDA, AMD, AVGO, MU" },
    { training_run_id: "tr_20261129_base_v3", target_id: "regular_60m", model_family: "market_logit", param_layers: "market", dataset_version_id: "ds_regular_60m_20261129_v1", trigger: "scheduled_weekly", status: "completed", stage: "evaluating", started_at: "2026-11-30T11:00:00Z", finished_at: "2026-11-30T11:38:00Z", code_version: "9f8e7d6", random_seed: 7, error: null, scope: "NVDA, AMD, AVGO, MU" },
    { training_run_id: "tr_sim_new", target_id: "regular_60m", model_family: "market_event_logit", param_layers: "market_sector_company", dataset_version_id: "ds_regular_60m_20261206_v1", trigger: "manual", status: "queued", stage: "queued", started_at: null, finished_at: null, code_version: "a1b2c3d", random_seed: 11, error: null, scope: "NVDA, AMD, AVGO, MU" }
  ];
  const STAGES = ["queued", "building_dataset", "training", "calibrating", "evaluating", "completed"];

  // loss curves per run (iterations) — only for solvers that report iterations
  function lossCurve(seed, n, start, end) {
    const r = rng(seed); const tr = [], va = [];
    for (let i = 0; i < n; i++) {
      const base = end + (start - end) * Math.exp(-i / (n / 5));
      tr.push(+(base - 0.004 + gauss(r) * 0.0008).toFixed(4));
      va.push(+(base + 0.003 + (i / n) * 0.002 + gauss(r) * 0.001).toFixed(4));
    }
    return { train: tr, validation: va };
  }
  const runMetrics = {
    tr_20261206_event_v1: { curve: lossCurve(3, 40, 1.11, 1.072), holdout: { brier: 0.641, hit_rate: 0.58, coverage: 0.5, n_effective_days: 41, n_event_clusters: 9 } },
    tr_20261206_company_v1: { curve: lossCurve(5, 40, 1.11, 1.069), holdout: { brier: 0.652, hit_rate: 0.55, coverage: 0.88, n_effective_days: 41, n_event_clusters: 9 } },
    tr_20261129_base_v3: { curve: lossCurve(9, 40, 1.11, 1.074), holdout: { brier: 0.648, hit_rate: 0.58, coverage: 0.9, n_effective_days: 38, n_event_clusters: 8 } }
  };

  const datasets = [
    { dataset_version_id: "ds_regular_60m_20261129_v1", target_id: "regular_60m", feature_set_version: "fs-0.2", label_version: "lbl-0.1", time_range: { start: "2021-01-04", end: "2026-11-27" }, n_rows: 1176400, n_trading_days: 1483, n_event_clusters: 409, class_balance: { outperform: 0.34, flat: 0.31, underperform: 0.35 }, exclusions: { no_sync_quote: 18120, news_time_unknown: 3290, crosses_split_boundary: 9560 }, availability_check_passed: true },
    { dataset_version_id: "ds_regular_60m_20261206_v1", target_id: "regular_60m", feature_set_version: "fs-0.2", label_version: "lbl-0.1", time_range: { start: "2021-01-04", end: "2026-12-04" }, n_rows: 1184220, n_trading_days: 1488, n_event_clusters: 412, class_balance: { outperform: 0.34, flat: 0.31, underperform: 0.35 }, exclusions: { no_sync_quote: 18210, news_time_unknown: 3304, crosses_split_boundary: 9600 }, availability_check_passed: true, parent_dataset_version_id: "ds_regular_60m_20261129_v1",
      diff: { added: 7900, removed: 0, corrected: 12, filtered: 140, corrected_examples: ["pred_amd_20261125_1405_60m：结算报价更正（迟到报价）→ settlement_version 2", "pred_nvda_20261124_1010_60m：篮子成分官方收盘价更正"] } }
  ];
  // coverage per week (for data-over-time chart)
  const coverageWeekly = (function () {
    const r = rng(99), out = [];
    for (let w = 0; w < 20; w++) {
      out.push({ week: "W" + (29 + w), settled: Math.round(1450 + gauss(r) * 40), eligible: 1560, missing_rate: +(0.04 + Math.abs(gauss(r)) * 0.012).toFixed(3) });
    }
    return out;
  })();

  const features = [
    ["ret_5m", 0.112, 0.108], ["ret_30m", 0.084, 0.079], ["rel_ret_30m_vs_basket", 0.151, 0.139], ["realized_vol_30m", -0.042, -0.040],
    ["volume_z_30m", 0.031, 0.029], ["spread_bp", -0.018, -0.019], ["minutes_to_close", 0.009, 0.010], ["basket_ret_30m", -0.061, -0.058],
    ["soxx_ret_30m", -0.012, -0.010], ["gap_open_pct", 0.022, 0.021], ["event_flag", null, 0.047], ["surprise_pct", null, 0.066],
    ["evidence_primary_confirmed", null, 0.038], ["initial_rel_reaction_pp", null, -0.054]
  ].map(([name, live, cand]) => ({ name, live, candidate: cand }));
  const companyOffsets = [
    { security: "NVDA", n_effective_days: 1488, live: 0.0, candidate: 0.021, holdout_delta_brier: -0.002 },
    { security: "AMD", n_effective_days: 1488, live: 0.0, candidate: -0.012, holdout_delta_brier: 0.004 },
    { security: "AVGO", n_effective_days: 1488, live: 0.0, candidate: 0.006, holdout_delta_brier: 0.001 },
    { security: "MU", n_effective_days: 1488, live: 0.0, candidate: -0.018, holdout_delta_brier: 0.006 }
  ];

  const models = [
    { model_version_id: "mdl_regular_60m_market_logit_v3", target_id: "regular_60m", model_family: "market_logit", param_layers: "market", status: "live", training_run_id: "tr_20261129_base_v3" },
    { model_version_id: "mdl_regular_60m_market_event_logit_v1", target_id: "regular_60m", model_family: "market_event_logit", param_layers: "market_sector", status: "shadow", training_run_id: "tr_20261206_event_v1" },
    { model_version_id: "mdl_regular_60m_company_v1", target_id: "regular_60m", model_family: "market_logit", param_layers: "market_sector_company", status: "rejected", training_run_id: "tr_20261206_company_v1" }
  ];

  const evaluation = {
    evaluation_id: "eval_20261206_event_v1_vs_live_v3",
    candidate_model_version_id: "mdl_regular_60m_market_event_logit_v1",
    comparator_model_version_id: "mdl_regular_60m_market_logit_v3",
    common_coverage: { n_eligible: 200, n_candidate: 100, n_comparator: 180, n_common: 100 },
    metrics: {
      hit_rate: { candidate: 0.58, comparator: 0.58, paired_diff: 0.0, ci95: [-0.06, 0.06] },
      brier: { candidate: 0.641, comparator: 0.648, paired_diff: -0.007, ci95: [-0.019, 0.005] },
      coverage: { candidate: 0.5, comparator: 0.9 }
    },
    full_coverage_hit_rate: { candidate: 0.58, comparator: 0.54 },
    n_independent_days: 41, n_event_clusters: 9, gate_config_version: "gate-0.1", gate_result: "fail",
    failed_conditions: ["coverage_drop_gt_10pp", "brier_ci_upper_not_below_0", "holdout_days_lt_60"],
    calibration: [ // bins: predicted prob of the predicted class vs observed freq
      { bin: 0.3, live: 0.31, candidate: 0.29, n: 22 }, { bin: 0.35, live: 0.34, candidate: 0.37, n: 31 }, { bin: 0.4, live: 0.42, candidate: 0.4, n: 28 },
      { bin: 0.45, live: 0.43, candidate: 0.47, n: 12 }, { bin: 0.5, live: 0.47, candidate: 0.53, n: 7 }
    ],
    confusion: { // rows actual, cols predicted (candidate, common set)
      labels: ["outperform", "flat", "underperform"],
      candidate: [[21, 8, 5], [7, 16, 8], [6, 8, 21]],
      comparator: [[19, 10, 5], [6, 17, 8], [6, 7, 22]]
    },
    groups: [
      { group: "NVDA", n: 27, brier_live: 0.646, brier_cand: 0.637 }, { group: "AMD", n: 26, brier_live: 0.651, brier_cand: 0.649 },
      { group: "AVGO", n: 24, brier_live: 0.644, brier_cand: 0.642 }, { group: "MU", n: 23, brier_live: 0.652, brier_cand: 0.638 },
      { group: "有新消息", n: 18, brier_live: 0.659, brier_cand: 0.633 }, { group: "无新消息", n: 82, brier_live: 0.646, brier_cand: 0.643 },
      { group: "财报窗口", n: 6, brier_live: 0.668, brier_cand: 0.641 }
    ]
  };

  const shadowDaily = (function () {
    const r = rng(1234), out = [];
    const days = ["11-09", "11-10", "11-11", "11-12", "11-13", "11-16", "11-17", "11-18", "11-19", "11-20", "11-23", "11-24", "11-25", "11-27", "11-30", "12-01", "12-02"];
    let a = 0.648, b = 0.646;
    days.forEach((d) => { a += gauss(r) * 0.004; b += gauss(r) * 0.004 - 0.0006; out.push({ day: "2026-" + d, live_brier: +a.toFixed(4), candidate_brier: +b.toFixed(4), n: 300 + Math.round(gauss(r) * 20) }); });
    return out;
  })();

  const approvals = [
    { at: "2026-11-30T15:00:00Z", action: "approve", model_version_id: "mdl_regular_60m_market_logit_v3", from: "mdl_regular_60m_market_logit_v2", by: "reviewer_demo_a", scope: "regular_60m · NVDA/AMD/AVGO/MU", gate: "pass", note: "留出与影子均达标（虚构）" },
    { at: "2026-12-07T14:00:00Z", action: "reject", model_version_id: "mdl_regular_60m_company_v1", from: null, by: "reviewer_demo_b", scope: "regular_60m · 公司参数层", gate: "fail", note: "训练期改善、留出期 AMD/MU 退化" },
    { at: "2026-11-18T16:00:00Z", action: "rollback", model_version_id: "mdl_regular_60m_market_logit_v2", from: "mdl_regular_60m_market_logit_v2b", by: "reviewer_demo_a", scope: "regular_60m", gate: "—", note: "上线后数据事故：篮子成分报价延迟（演示）" }
  ];

  return {
    SCHEMA_VERSION, CLOCKS, NOW_IDX, FULL_IDX, SESSION_OPEN_MS, THRESH, tsAt,
    tickers: SEC_META.map((m) => m.ticker), securities, predictions, evidence, events, explanations,
    trainingRuns, STAGES, runMetrics, datasets, coverageWeekly, features, companyOffsets, models, evaluation, shadowDaily, approvals,
    windowReturns, SCHEDULE, fva, fvaRollups, fvaBySlot, fvaCalib, fvaReview,
    collections, reasoning, CHANNEL_LABEL, CATEGORY_LABEL, DISPOSITION_LABEL
  };
})();
