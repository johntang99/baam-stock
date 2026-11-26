/* 原型交互逻辑 · 全部数据来自 data.js（MOCK） */
(function () {
  "use strict";
  const M = window.MOCK;
  const $ = (s, el) => (el || document).querySelector(s);
  const view = $("#view");
  const tip = $("#tooltip");

  const S = {
    clock: "intraday",
    demo: "normal",
    simRun: null,
    approvals: M.approvals.slice(),
    adminModel: "candidate",
    adminSec: "ALL",
    dsA: M.datasets[0].dataset_version_id,
    dsB: M.datasets[1].dataset_version_id,
    selRun: "tr_20261206_event_v1",
    refreshing: {},
    colf: { channel: "", category: "", disposition: "", q: "" },
    addOpen: {}, subs: {}, supp: {}, addForm: { kind: "link", scenario: "primary", cats: [] }
  };

  // ---------- formatting ----------
  const etFmt = new Intl.DateTimeFormat("zh-CN", { timeZone: "America/New_York", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  const etHM = new Intl.DateTimeFormat("zh-CN", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false });
  const fmtET = (iso) => (iso ? etFmt.format(new Date(iso)) + " ET" : "—");
  const hm = (iso) => (iso ? etHM.format(new Date(iso)) : "—");
  const idxHM = (i) => hm(M.tsAt(i));
  const sgn = (v, d, u) => (v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d == null ? 2 : d) + (u || ""));
  const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const TARGETS = [
    { id: "regular_60m", label: "未来 60 分钟" },
    { id: "regular_to_close", label: "到收盘" },
    { id: "next_regular_session", label: "下一正常时段" }
  ];
  const TARGET_LABEL = Object.fromEntries(TARGETS.map((t) => [t.id, t.label]));
  const CLASS_LABEL = { outperform: "跑赢", flat: "接近平盘", underperform: "跑输" };
  const STATUS = {
    pending_evaluation: ["评估中", "neutral", "◌"],
    published: ["已发布", "info", "●"],
    awaiting_trigger: ["待触发", "info", "◔"],
    awaiting_settlement: ["待结算", "warn", "◔"],
    settled: ["已结算", "good", "✓"],
    abstained: ["弃预测", "serious", "⊘"],
    not_triggered: ["未触发", "neutral", "—"],
    unsettleable: ["无法结算", "crit", "✕"],
    market_closed: ["休市", "neutral", "☾"]
  };
  const ABSTAIN = {
    insufficient_data: "数据不足", stale_quote: "报价陈旧", halted: "停牌", benchmark_unavailable: "基准不可计算",
    conflicting_facts: "关键事实冲突", window_insufficient: "窗口不足", market_closed: "休市", model_not_validated: "模型验证中", manual_review: "人工复核"
  };
  const MARKET_STATE = { pre_market: ["盘前", "neutral"], regular: ["盘中", "good"], post_market: ["盘后", "neutral"], closed: ["休市", "neutral"], halted: ["停牌", "crit"] };
  const EXPL = { supported: ["解释充分", "good"], partial: ["部分解释", "warn"], insufficient: ["证据不足", "serious"] };
  const VERIF = { pending: ["待核", "neutral"], media_report: ["媒体报道", "warn"], primary_confirmed: ["原始来源确认", "good"], conflicting: ["冲突", "crit"], retracted: ["撤回", "crit"] };

  function badge(map, key, extra) {
    const v = map[key] || [key, "neutral", ""];
    return `<span class="badge ${v[1]}">${v[2] ? v[2] + " " : ""}${esc(v[0])}${extra ? " · " + esc(extra) : ""}</span>`;
  }
  function statusBadge(p) {
    if (!p) return badge(STATUS, "pending_evaluation");
    if (p.status === "abstained" && p.abstain_reason === "market_closed") return badge(STATUS, "market_closed");
    return badge(STATUS, p.status, p.status === "abstained" ? ABSTAIN[p.abstain_reason] : p.status === "unsettleable" && p.settlement ? p.settlement.invalid_reason : "");
  }
  const tag = (k) => ({ hist: '<span class="kind-tag hist">历史行情</span>', expl: '<span class="kind-tag">当前解释</span>', scen: '<span class="kind-tag">情景 · 未验证</span>', pred: '<span class="kind-tag pred">事前预测 · 已锁定</span>' }[k]);

  // ---------- 0.4: data quality, validity, display_state (D-41) ----------
  const DQ = { ok: ["数据正常", "good"], stale: ["数据陈旧", "serious"], partial: ["部分缺失", "warn"], failed: ["数据失败", "crit"] };
  const RUNST = { running: ["运行中", "info"], complete: ["完成", "good"], degraded: ["降级（部分来源缺失）", "warn"], failed: ["失败", "crit"] };
  const DISP = { current: ["当前", "info"], superseded: ["已被替代", "neutral"], expired: ["已过期，待结算", "warn"], settled: ["已结算", "good"] };
  function qualityLine(tk, full) {
    const ex = M.explanations[tk];
    if (!ex || !ex.data_quality) return "";
    if (isClosed()) return `<div class="small muted">休市：显示最近有效快照 ${fmtET(ex.last_valid_at)}</div>`;
    const dq = S.demo === "timeout" ? "stale" : ex.data_quality;
    const rs = S.demo === "timeout" ? "degraded" : ex.run_state;
    const expired = Date.parse(clock().now) > Date.parse(ex.valid_until);
    const issues = (ex.quality_issues || []).map((q) => esc(q.issue) + (q.lag_s ? `（${Math.round(q.lag_s / 60)} 分钟）` : ""));
    return `<div class="row small qline" style="margin-top:6px">${badge(DQ, dq)} ${badge(RUNST, rs)} ${expired ? '<span class="badge warn">快照已过期</span>' : ""}</div>` +
      (dq !== "ok" ? `<div class="small muted">最近有效：${fmtET(ex.last_valid_at)}${issues.length ? " · " + issues.join("；") : ""}</div>` : "") +
      (full ? `<div class="small muted">快照有效至 ${fmtET(ex.valid_until)}（D-41）</div>` : "");
  }
  function displayState(p) {
    if (!p || !p.prediction_id) return null;
    if (p.status === "settled") return "settled";
    if (M.predictions.some((q) => q.supersedes_prediction_id === p.prediction_id && (q.published_idx == null || q.published_idx <= M.NOW_IDX))) return "superseded";
    if (p.valid_until && !isClosed() && Date.parse(clock().now) > Date.parse(p.valid_until) && p.status !== "unsettleable" && p.status !== "abstained") return "expired";
    return "current";
  }

  // ---------- clock helpers ----------
  const clock = () => M.CLOCKS[S.clock];
  const isClosed = () => S.clock === "closed";
  function lastIdx() { return M.NOW_IDX; }
  function secView(tk) {
    const sec = M.securities[tk];
    const i = lastIdx();
    const bar = sec.bars[i];
    const dayRet = +(((bar.close / sec.prev_close) - 1) * 100).toFixed(2);
    const bmRet = +((bar.benchmark_index / 100 - 1) * 100).toFixed(2);
    if (isClosed()) return { sec, bar, price: sec.prev_close, dayRet: null, bmRet: null, rel: null, quote_ts: "2026-11-25T21:00:00.000Z", market_state: "closed" };
    return {
      sec, bar, price: bar.close, dayRet, bmRet, rel: +(dayRet - bmRet).toFixed(2),
      quote_ts: isClosed() ? "2026-11-25T21:00:00.000Z" : new Date(Date.parse(bar.bar_start) - 1000).toISOString(),
      market_state: isClosed() ? "closed" : "regular"
    };
  }
  function predsFor(tk, target) {
    return M.predictions.filter((p) => p.ticker === tk && (!target || p.target_id === target));
  }
  function currentPred(tk, target) {
    if (isClosed() && target !== "next_regular_session") {
      return { prediction_id: null, ticker: tk, target_id: target, status: "abstained", abstain_reason: "market_closed", probabilities: null, display_tier: "validated_public", locked: null, settlement: null };
    }
    const list = predsFor(tk, target).filter((p) => p.published_idx == null || p.published_idx <= M.NOW_IDX);
    list.sort((a, b) => (b.published_idx || 0) - (a.published_idx || 0));
    let p = list[0] || null;
    if (p && S.demo === "unsettleable" && target !== "next_regular_session") {
      p = Object.assign({}, p, { status: "unsettleable", settlement: { invalid_reason: "no_sync_end_quote", reason_text: "演示：目标时点后 30s 容差内无个股与篮子的同步合格报价，按 qr-0.1 标记无法结算；不计入命中率分母。", stock_return_pct: null, benchmark_return_pct: null, relative_return_pp: null } });
    }
    return p;
  }

  // ---------- state wrapper ----------
  function withState(renderFn, opts) {
    opts = opts || {};
    const st = S.demo;
    if (st === "loading") return `<div class="card">${'<div class="skeleton" style="width:40%"></div><div class="skeleton"></div><div class="skeleton" style="width:80%"></div><div class="skeleton" style="height:160px"></div>'}<p class="muted small">正在加载最新有效状态…（演示）</p></div>`;
    if (st === "empty") return `<div class="card state"><div class="icon">∅</div><h2>暂无数据</h2><p class="muted">${esc(opts.empty || "当前筛选条件下没有记录。")}</p></div>`;
    if (st === "timeout") return `<div class="notice">⏱ 数据源超时：显示最后有效状态（${fmtET(clock().now)} 之前），状态标为 <code>data_quality = stale</code>。</div>` + renderFn();
    if (st === "failed") return `<div class="card state"><div class="icon">⚠</div><h2>加载失败</h2><p class="muted">错误码 <code>UPSTREAM_FAILED</code>：上游任务失败，已进入重试队列（attempt 2/5，退避 30s）。</p><button class="btn" data-act="retry">重试</button></div>`;
    return renderFn();
  }

  // ---------- chart engine (SVG + hover) ----------
  const charts = {};
  let chartSeq = 0;
  function lineChart(o) {
    const id = "c" + ++chartSeq;
    const W = o.width || (window.innerWidth < 720 ? 440 : 760), H = o.height || 260;
    const P = { l: 52, r: 16, t: 14, b: 28 };
    const [x0, x1] = o.xDomain;
    let ys = [];
    o.series.forEach((s) => s.values.forEach((v) => v != null && ys.push(v)));
    if (o.band) ys.push(o.band.lo, o.band.hi);
    (o.extraY || []).forEach((v) => ys.push(v));
    let y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    if (o.yDomain) { y0 = o.yDomain[0]; y1 = o.yDomain[1]; }
    const pad = (y1 - y0) * 0.08 || 1; y0 -= pad; y1 += pad;
    const X = (x) => P.l + ((x - x0) / (x1 - x0)) * (W - P.l - P.r);
    const Y = (y) => P.t + (1 - (y - y0) / (y1 - y0)) * (H - P.t - P.b);
    let g = "";
    // grid
    g += '<g class="grid">';
    for (let k = 0; k <= 4; k++) {
      const yv = y0 + ((y1 - y0) * k) / 4;
      g += `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(yv)}" y2="${Y(yv)}"/><text x="${P.l - 6}" y="${Y(yv) + 4}" text-anchor="end">${esc(o.yFmt ? o.yFmt(yv) : yv.toFixed(2))}</text>`;
    }
    g += "</g>";
    (o.xTicks || []).forEach((t) => { g += `<text x="${X(t)}" y="${H - 8}" text-anchor="middle">${esc(o.xFmt(t))}</text>`; });
    g += `<line class="axis" x1="${P.l}" x2="${W - P.r}" y1="${H - P.b}" y2="${H - P.b}"/>`;
    // band (prediction interval at endpoint)
    if (o.band) {
      const bx = X(o.band.x);
      g += `<rect x="${bx - 7}" y="${Y(o.band.hi)}" width="14" height="${Math.max(2, Y(o.band.lo) - Y(o.band.hi))}" rx="4" fill="var(--band)" stroke="var(--series-1)" stroke-width="1"/>`;
      g += `<line x1="${bx - 10}" x2="${bx + 10}" y1="${Y(o.band.mid)}" y2="${Y(o.band.mid)}" stroke="var(--series-1)" stroke-width="2"/>`;
      g += `<text x="${bx - 12}" y="${Y(o.band.hi) - 4}" text-anchor="end">预测区间 p10–p90</text>`;
    }
    // vertical markers
    (o.vlines || []).forEach((v) => {
      g += `<line x1="${X(v.x)}" x2="${X(v.x)}" y1="${P.t}" y2="${H - P.b}" stroke="${v.color || "var(--text-2)"}" stroke-dasharray="${v.dash || "3 3"}" stroke-width="1"/>`;
      const nearR = X(v.x) > W - P.r - 90;
      g += `<text x="${X(v.x) + (nearR ? -4 : 4)}" y="${P.t + 10 + (v.row || 0) * 13}" text-anchor="${nearR ? "end" : "start"}">${esc(v.label)}</text>`;
    });
    // series
    o.series.forEach((s) => {
      let d = "", started = false;
      s.values.forEach((v, i) => {
        if (v == null) { started = false; return; }
        const x = o.xs[i];
        if (x < x0 || x > x1) return;
        d += (started ? "L" : "M") + X(x).toFixed(1) + "," + Y(v).toFixed(1);
        started = true;
      });
      g += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" ${s.dash ? 'stroke-dasharray="5 4"' : ""}/>`;
    });
    // points
    (o.points || []).forEach((p) => {
      g += `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="5" fill="${p.fill || "var(--surface)"}" stroke="${p.color || "var(--series-1)"}" stroke-width="2"><title>${esc(p.label)}</title></circle>`;
      if (p.text) { const nr = X(p.x) > W - P.r - 90; g += `<text x="${X(p.x) + (nr ? -8 : 8)}" y="${Y(p.y) + (p.dy || -8)}" text-anchor="${nr ? "end" : "start"}">${esc(p.text)}</text>`; }
    });
    g += `<line class="xh" x1="0" x2="0" y1="${P.t}" y2="${H - P.b}" stroke="var(--text-2)" stroke-width="1" visibility="hidden"/>`;
    g += `<rect class="hit" x="${P.l}" y="${P.t}" width="${W - P.l - P.r}" height="${H - P.t - P.b}" fill="transparent"/>`;
    charts[id] = { o, X, Y, P, W, H, x0, x1 };
    const legend = o.series.length > 1 || o.legendAlways ? `<div class="legend">${o.series.map((s) => `<span><i class="${s.dash ? "dash" : ""}" style="background:${s.color};color:${s.color}"></i>${esc(s.name)}</span>`).join("")}${(o.legendExtra || []).join("")}</div>` : "";
    const table = o.table ? `<details><summary>表格视图</summary><div class="tablewrap">${o.table}</div></details>` : "";
    return `${legend}<svg class="chart" id="${id}" data-chart="${id}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria || "图表")}">${g}</svg>${table}`;
  }
  function bindCharts() {
    document.querySelectorAll("svg[data-chart]").forEach((svg) => {
      const c = charts[svg.dataset.chart];
      if (!c) return;
      const hit = svg.querySelector(".hit"), xh = svg.querySelector(".xh");
      hit.addEventListener("mousemove", (e) => {
        const r = svg.getBoundingClientRect();
        const sx = ((e.clientX - r.left) / r.width) * c.W;
        const xv = c.x0 + ((sx - c.P.l) / (c.W - c.P.l - c.P.r)) * (c.x1 - c.x0);
        let best = 0, bd = Infinity;
        c.o.xs.forEach((x, i) => { const d = Math.abs(x - xv); if (d < bd) { bd = d; best = i; } });
        const rows = c.o.series.filter((s) => s.values[best] != null).map((s) => `<div><span style="color:${s.color}">■</span> ${esc(s.name)}：<b class="num">${esc(c.o.yFmt ? c.o.yFmt(s.values[best]) : s.values[best])}</b></div>`).join("");
        if (!rows) { tip.style.display = "none"; xh.setAttribute("visibility", "hidden"); return; }
        xh.setAttribute("x1", c.X(c.o.xs[best])); xh.setAttribute("x2", c.X(c.o.xs[best])); xh.setAttribute("visibility", "visible");
        tip.innerHTML = `<div class="muted">${esc(c.o.xFmt(c.o.xs[best]))}</div>${rows}`;
        tip.style.display = "block";
        tip.style.left = Math.min(window.innerWidth - 220, e.clientX + 14) + "px";
        tip.style.top = e.clientY + 14 + "px";
      });
      hit.addEventListener("mouseleave", () => { tip.style.display = "none"; xh.setAttribute("visibility", "hidden"); });
    });
  }

  // ---------- shared bits ----------
  function tickerSwitch(base, tk, suffix) {
    return `<div class="tickers">${M.tickers.map((t) => `<a href="#/${base}/${t}${suffix || ""}" class="${t === tk ? "active" : ""}">${t}</a>`).join("")}</div>`;
  }
  function sparkline(tk) {
    const b = M.securities[tk].bars.slice(0, lastIdx() + 1).map((x) => x.close);
    const lo = Math.min.apply(null, b), hi = Math.max.apply(null, b);
    const W = 220, H = 44;
    const d = b.map((v, i) => (i ? "L" : "M") + ((i / (b.length - 1)) * W).toFixed(1) + "," + (H - 3 - ((v - lo) / (hi - lo || 1)) * (H - 6)).toFixed(1)).join("");
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" aria-label="${tk} 当日走势"><path d="${d}" fill="none" stroke="var(--series-1)" stroke-width="2"/></svg>`;
  }

  // ======================= PAGES =======================
  function pageMonitor() {
    return `<div class="pagehead"><div><h1>公司监控</h1><div class="muted">首批 AI 半导体 · 主基准 <code>semis_peer_v1</code>（剔除目标等权）· SOXX 仅作参考</div></div>
      <div class="muted small">第二批候选：TSM、MRVL（评估中，未接入）</div></div>` +
      withState(() => `<div class="grid g4">${M.tickers.map((tk) => {
        const v = secView(tk), ex = M.explanations[tk], p = currentPred(tk, "regular_60m");
        return `<div class="card mcard" data-go="#/stock/${tk}" tabindex="0" role="link" aria-label="${tk} 详情">
          <div class="mrow"><div><b style="font-size:16px">${tk}</b> <span class="muted small">${esc(v.sec.name)}</span></div>${badge(MARKET_STATE, v.market_state)}</div>
          <div class="mrow" style="margin-top:6px"><span class="price num">${v.price.toFixed(2)}</span><span class="num ${cls(v.dayRet)}">${sgn(v.dayRet, 2, "%")}</span></div>
          <div class="small muted">报价时间 ${fmtET(v.quote_ts)}</div>
          ${isClosed() ? "" : sparkline(tk)}
          <div class="small">相对同行篮子 <b class="num ${cls(v.rel)}">${sgn(v.rel, 2, "pp")}</b></div>
          <div class="row small" style="margin-top:6px">${badge(EXPL, ex.explanation_status)} ${ex.new_catalyst_found ? '<span class="badge info">新催化剂</span>' : '<span class="badge neutral">无新催化剂</span>'}</div>
          <div class="row small" style="margin-top:6px"><span class="muted">60 分钟预测</span> ${statusBadge(p)}</div>
          ${qualityLine(tk)}
          <div class="small" style="margin-top:8px"><a href="#/forecast/${tk}/regular_60m">预测</a> · <a href="#/events/${tk}">事件</a></div>
        </div>`;
      }).join("")}</div>
      <div class="card" style="margin-top:14px"><h2>状态说明</h2><div class="row small">
        ${["settled", "awaiting_settlement", "abstained", "unsettleable", "market_closed", "pending_evaluation"].map((k) => badge(STATUS, k)).join(" ")}
      </div><p class="small muted">用户端区分四类信息：${tag("hist")} ${tag("expl")} ${tag("scen")} ${tag("pred")}</p></div>`, { empty: "监测名单为空：请在公司档案中启用证券（coverage_tier = pilot）。" });
  }

  // ---------- 0.6: step 1 collection, step 2 reasoning, run stepper (D-45, D-46) ----------
  const KIND = { user_info: ["用户补充", "warn"], market_fact: ["行情事实", "info"], timing_check: ["时间对齐", "info"], evidence_fact: ["证据事实", "good"], attribution: ["归因（条件）", "warn"], counter_check: ["反向检查", "neutral"], analogue: ["历史类比", "neutral"], gap: ["缺口", "serious"], conclusion: ["结论", "good"] };
  function countsOf(tk) {
    const items = M.collections[tk].items, by = (k) => items.reduce((o, i) => ((o[i[k]] = (o[i[k]] || 0) + 1), o), {});
    const n = (f) => items.filter(f).length;
    return { fetched: items.length, kept: n((i) => i.disposition === "kept"), duplicate: n((i) => i.disposition === "duplicate"), excluded: n((i) => i.disposition.startsWith("excluded")), pending_review: n((i) => i.disposition === "pending_review"), failed: n((i) => i.disposition === "fetch_failed"), new_in_run: n((i) => i.new_in_run || Date.parse(i.available_at) >= Date.parse("2026-12-02T16:25:00Z")), by_channel: by("channel"), by_category: by("category") };
  }
  // ---------- 0.7: user submissions (D-47) and supplement run (D-48) ----------
  const SUB_ST = { received: ["已接收", "info"], fetching: ["正在打开链接", "info"], verifying: ["正在核验", "info"], verified_primary: ["已核实 · 原始来源", "good"], media_level: ["仅媒体来源", "warn"], unverified: ["无法核实", "serious"], duplicate: ["重复 · 已在系统中", "neutral"], rejected_restricted: ["受限 · 转合规复核", "crit"], fetch_failed: ["链接无法打开", "serious"] };
  const SCEN = {
    primary: { label: "可追溯到原始来源（演示：公司 8-K）", final: "verified_primary", sys: [["customer_demand", 0.82], ["supply_chain", 0.64]], origin: "SEC 8-K（演示）· 11:05:00 ET", missed: true, checks: [["link_reachable", "pass"], ["domain_reputation", "pass"], ["origin_traced", "pass", "找到公司 8-K 原文"], ["content_matches_origin", "pass"], ["timestamp_consistent", "pass"], ["duplicate_check", "pass", "系统中无相同内容"], ["mnpi_screen", "pass"]] },
    media: { label: "只有媒体报道（演示）", final: "media_level", sys: [["customer_demand", 0.71]], origin: "媒体网站（演示），未找到官方原文", checks: [["link_reachable", "pass"], ["domain_reputation", "pass", "授权媒体"], ["origin_traced", "fail", "只找到媒体报道，无公司或监管原文"], ["content_matches_origin", "n_a"], ["timestamp_consistent", "pass"], ["duplicate_check", "pass"], ["mnpi_screen", "pass"]] },
    unverified: { label: "无法核实（演示：论坛帖子）", final: "unverified", sys: [["product", 0.58], ["other", 0.4]], origin: "无", checks: [["link_reachable", "pass"], ["domain_reputation", "fail", "匿名论坛"], ["origin_traced", "fail", "找不到任何可核对来源"], ["content_matches_origin", "fail"], ["timestamp_consistent", "n_a"], ["duplicate_check", "pass"], ["mnpi_screen", "pass"]] },
    duplicate: { label: "已在系统中（演示：重复）", final: "duplicate", sys: [], origin: "—", checks: [["link_reachable", "pass"], ["duplicate_check", "fail", "与已有条目内容哈希相同"]] },
    restricted: { label: "疑似未公开材料（演示）", final: "rejected_restricted", sys: [], origin: "—", checks: [["link_reachable", "pass"], ["mnpi_screen", "fail", "疑似内部文件，暂停使用并转合规"]] }
  };
  const CHECK_LABEL = { link_reachable: "链接可打开", domain_reputation: "来源信誉", origin_traced: "追溯原始来源", content_matches_origin: "内容与原文一致", timestamp_consistent: "时间一致", duplicate_check: "查重", mnpi_screen: "未公开材料筛查" };
  function submitInfo(tk) {
    const F = S.addForm, sc = SCEN[F.scenario], list = (S.subs[tk] = S.subs[tk] || []);
    const val = ($("#addVal") || {}).value || "", note = ($("#addNote") || {}).value || "";
    const subm = { submission_id: "sub_" + tk.toLowerCase() + "_" + String(list.length + 1).padStart(3, "0"), kind: F.kind, value: val || (F.kind === "link" ? "https://example.com/demo-article" : F.kind === "file" ? "demo.pdf" : "（用户输入的文本）"), note, user_categories: F.cats.slice(), scenario: F.scenario, status: "received", checks: [], system_categories: [], final_categories: [], submitted_at: "2026-12-02T16:32:40.000Z" };
    list.unshift(subm); S.addOpen[tk] = false; S.addForm.cats = []; render();
    const seq = ["fetching", "verifying", sc.final];
    seq.forEach((st, i) => setTimeout(() => {
      subm.status = st;
      if (st === "verifying") { subm.system_categories = sc.sys; }
      if (i === seq.length - 1) {
        subm.checks = sc.checks; subm.origin = sc.origin; subm.missed_by_system = !!sc.missed;
        subm.final_categories = Array.from(new Set(subm.user_categories.concat(sc.sys.filter((x) => x[1] >= 0.6).map((x) => x[0])))); if (!subm.final_categories.length) subm.final_categories = ["other"];
        const C = M.collections[tk];
        const dupOf = (C.items.find((x) => x.disposition === "kept" && x.channel !== "market_data") || {}).item_id;
        const disp = { verified_primary: "kept", media_level: "kept", unverified: "pending_review", duplicate: "duplicate", rejected_restricted: "excluded_restricted" }[st];
        const it = { item_id: "itm_" + tk.toLowerCase() + "_u" + String(list.length).padStart(2, "0"), channel: "user_submission", category: subm.final_categories[0], title: (st === "rejected_restricted" ? "用户提交（受限）" : "用户补充：" + (subm.kind === "text" ? subm.value.slice(0, 30) : subm.value)) + (subm.final_categories.length > 1 ? `（另属：${subm.final_categories.slice(1).map((c) => M.CATEGORY_LABEL[c]).join("、")}）` : ""),
          disposition: disp, exclusion_reason: { verified_primary: "原始来源已核实：" + sc.origin + (sc.missed ? "；系统此前漏采 → 记为来源覆盖缺口" : ""), media_level: "仅媒体来源，等同媒体报道", unverified: "用户提供，无法核实：不进入模型输入", duplicate: "与已有条目重复", rejected_restricted: "疑似未公开材料：暂停使用，转合规复核" }[st],
          duplicate_of: st === "duplicate" ? dupOf : null, occurred_at: null, source_published_at: st === "verified_primary" ? "2026-12-02T16:05:00.000Z" : null, source_published_precision: st === "verified_primary" ? "s" : "unknown",
          received_at: subm.submitted_at, available_at: subm.submitted_at, linked_event_id: null, linked_evidence_ids: [], source: "用户提交（" + subm.submission_id + "）", new_in_run: true, submission_id: subm.submission_id };
        C.items.unshift(it); subm.item_id = it.item_id;
      }
      render();
    }, 700 * (i + 1)));
  }
  function runSupplement(tk, subm) {
    const steps = ["复用本次运行的 " + countsOf(tk).fetched + " 条采集项（不重新检索）", "行情快速刷新（至 11:33:05 ET）", "增量检索 11:29:41 以来的新条目：+0", "带入用户条目 " + subm.item_id, "重跑第 2 步分析与推理（新版本）", "重跑第 3 步预测（user_supplement，单独计分）"];
    const run = (S.supp[tk] = { id: "plr_" + tk.toLowerCase() + "_supp_" + subm.submission_id.slice(-3), subm, steps, done: 0, finished: false });
    render();
    steps.forEach((_, i) => setTimeout(() => {
      run.done = i + 1;
      if (i === steps.length - 1) {
        run.finished = true;
        const before = currentPred(tk, "regular_60m");
        const verified = subm.status === "verified_primary" || subm.status === "media_level";
        const shift = subm.status === "verified_primary" ? 0.05 : subm.status === "media_level" ? 0.02 : 0;
        const pb = before && before.probabilities ? before.probabilities : { outperform: 0.33, flat: 0.34, underperform: 0.33 };
        const pa = { outperform: +(pb.outperform + shift).toFixed(2), flat: +(pb.flat).toFixed(2), underperform: +(pb.underperform - shift).toFixed(2) };
        const np = Object.assign({}, before, { prediction_id: "pred_" + tk.toLowerCase() + "_20261202_supp_" + subm.submission_id.slice(-3), probabilities: pa, predicted_class: Object.entries(pa).sort((a, b) => b[1] - a[1])[0][0], sampling_rule: "user_supplement", trigger_type: "user_supplement", is_primary: false, schedule_slot_id: null, published_idx: 123, published_at: "2026-12-02T16:33:10.000Z", supersedes_prediction_id: null, status: "awaiting_settlement", settlement: null, note: "用户补充后的增量运行；单独计分，不影响槽位预测", t0_idx: 124, t0_quote_ts: "2026-12-02T16:34:02.000Z", target_end_idx: 184, target_end_at: "2026-12-02T17:34:02.000Z", valid_until: "2026-12-02T17:34:02.000Z" });
        M.predictions.push(np);
        run.before = pb; run.after = pa; run.pred_id = np.prediction_id;
        const R = M.reasoning[tk], concl = R.pop();
        R.push({ kind: "user_info", rule: verified ? "用户补充信息经核验后按证据处理" : "未证实的用户信息只列出，不进入模型输入", conclusion: subm.status === "verified_primary" ? "用户补充的信息已追溯到原始来源（演示：8-K），作为新的证据事实纳入；它支持\"客户需求\"方向的可能驱动，概率小幅调整（虚构）。" : subm.status === "media_level" ? "用户补充的媒体报道纳入为媒体级证据，不能单独构成已观察事实；概率微调（虚构）。" : "用户提供的信息无法核实：仅在此列出，不改变解释与预测。", refs: { item_ids: [subm.item_id] }, confidence: verified ? "medium" : "low", by: "code" });
        R.push(Object.assign({}, concl, { conclusion: concl.conclusion + "（补充版本 v" + (R.filter((x) => x.kind === "user_info").length + 1) + "，原版本保留）" }));
        R.forEach((st, k) => (st.step = k + 1));
      }
      render();
    }, 600 * (i + 1)));
  }
  function addInfoPanel(tk) {
    const F = S.addForm, list = S.subs[tk] || [], run = S.supp[tk];
    const catBoxes = Object.keys(M.CATEGORY_LABEL).filter((k) => k !== "market_data").map((k) => `<label class="small chk"><input type="checkbox" data-act="addCat" value="${k}" ${F.cats.includes(k) ? "checked" : ""}> ${M.CATEGORY_LABEL[k]}</label>`).join("");
    const form = S.addOpen[tk] ? `<div class="addform">
        <div class="row small">${["link", "text", "file"].map((k) => `<label class="chk"><input type="radio" name="addKind" data-act="addKind" value="${k}" ${F.kind === k ? "checked" : ""}> ${{ link: "链接", text: "文本", file: "文件" }[k]}</label>`).join("")}</div>
        ${F.kind === "file" ? '<input id="addVal" type="file" aria-label="上传文件（PDF、图片、文档 ≤ 20MB）">' : F.kind === "text" ? '<textarea id="addVal" rows="3" placeholder="粘贴你认为重要的信息"></textarea>' : '<input id="addVal" type="url" placeholder="https://…（新闻、公告、监管文件等链接）">'}
        <div class="small" style="margin-top:6px"><b>类别</b>（可多选；不选则由系统分配，系统也可能追加类别）</div><div class="cats">${catBoxes}</div>
        <input id="addNote" type="text" placeholder="说明：为什么这条信息重要（可选）">
        <div class="row small" style="margin-top:6px">演示核验结果 <select data-act="addScen">${Object.entries(SCEN).map(([k, v]) => `<option value="${k}" ${F.scenario === k ? "selected" : ""}>${v.label}</option>`).join("")}</select></div>
        <div class="row" style="margin-top:8px"><button class="btn sm" data-act="addSubmit" data-tk="${tk}">提交并核验</button><button class="btn sm ghost" data-act="addToggle" data-tk="${tk}">取消</button></div>
        <p class="small muted">用户提交不默认可信：系统会打开链接、追溯原始来源、核对内容与时间、查重并筛查未公开材料。条目的"可用时间"= 提交时间，不会回溯。</p></div>` : "";
    const subRows = list.map((sb) => {
      const fin = !["received", "fetching", "verifying"].includes(sb.status);
      const canGo = fin && !["duplicate", "rejected_restricted", "fetch_failed"].includes(sb.status);
      const goNote = sb.status === "duplicate" ? `已在系统中 → <a href="#/stock/${tk}/collect?item=${(M.collections[tk].items.find((x) => x.item_id === sb.item_id) || {}).duplicate_of}">原条目</a>，无需重新分析` : sb.status === "rejected_restricted" ? "不可继续：已转合规复核" : sb.status === "unverified" ? "可继续：将作为\"用户提供，未证实\"列出，不进入模型输入" : "";
      return `<div class="subm"><div class="mrow"><span><code>${sb.submission_id}</code> ${badge(SUB_ST, sb.status)} <span class="small muted">${{ link: "链接", text: "文本", file: "文件" }[sb.kind]} · 提交于 ${fmtET(sb.submitted_at)}</span></span>
        ${canGo ? `<button class="btn sm" data-act="suppGo" data-tk="${tk}" data-sub="${sb.submission_id}" ${run && !run.finished ? "disabled" : ""}>继续分析 →</button>` : ""}</div>
        <div class="small">${esc(sb.value)}${sb.note ? ` <span class="muted">· ${esc(sb.note)}</span>` : ""}</div>
        <div class="small">类别：用户选 ${sb.user_categories.length ? sb.user_categories.map((c) => M.CATEGORY_LABEL[c]).join("、") : "（未选，交给系统）"}${sb.system_categories.length ? ` · 系统建议 ${sb.system_categories.map((x) => M.CATEGORY_LABEL[x[0]] + " " + Math.round(x[1] * 100) + "%").join("、")}` : ""}${sb.final_categories.length ? ` → <b>最终 ${sb.final_categories.map((c) => M.CATEGORY_LABEL[c]).join("、")}</b>` : ""}</div>
        ${sb.checks.length ? `<div class="refs" style="margin-top:4px">${sb.checks.map(([k, r, n]) => `<span class="chip" title="${esc(n || "")}">${r === "pass" ? "✓" : r === "fail" ? "✕" : "–"} ${CHECK_LABEL[k]}${n ? "：" + esc(n) : ""}</span>`).join("")}</div>` : ""}
        ${sb.item_id ? `<div class="small">已写入第 1 步：<a href="#/stock/${tk}/collect?item=${sb.item_id}"><code>${sb.item_id}</code></a>${sb.missed_by_system ? ' · <span class="badge warn">系统此前漏采 → 来源覆盖复盘</span>' : ""}</div>` : ""}
        ${goNote ? `<div class="small muted">${goNote}</div>` : ""}</div>`;
    }).join("");
    const runBox = run ? `<div class="supp"><h3>增量补充运行 <code class="small">${run.id}</code> <span class="small muted">mode = supplement · trigger_type = user_supplement</span></h3>
      <ol class="list small">${run.steps.map((t, i) => `<li>${i < run.done ? "✓" : i === run.done ? "…" : "○"} ${esc(t)}</li>`).join("")}</ol>
      ${run.finished ? `<div class="grid g2"><div><b>补充前</b>（11:30 槽位预测，主评分）<div class="small">${["outperform", "flat", "underperform"].map((k) => CLASS_LABEL[k] + " " + Math.round(run.before[k] * 100) + "%").join(" · ")}</div></div><div><b>补充后</b>（新版本，单独计分）<div class="small">${["outperform", "flat", "underperform"].map((k) => CLASS_LABEL[k] + " " + Math.round(run.after[k] * 100) + "%").join(" · ")}</div></div></div>
        <p class="small">原分析与 11:30 槽位预测保留不变；新预测 <code>${run.pred_id}</code> 起算于补充后首组同步合格报价。${["verified_primary", "media_level"].includes(run.subm.status) ? "" : "用户条目未核实，结论与概率不变。"}结果先只对你和研究员可见，标"含用户补充"。<a href="#/stock/${tk}/reason">查看新的推理链 →</a> · <a href="#/forecast/${tk}/regular_60m">预测记录 →</a></p>` : ""}</div>` : "";
    return `<div class="card" style="grid-column:1/-1" id="addinfo"><div class="mrow"><h2 style="margin:0">用户补充信息 <span class="muted small">user_submissions</span></h2><button class="btn sm" data-act="addToggle" data-tk="${tk}">${S.addOpen[tk] ? "收起" : "＋ 添加信息"}</button></div>
      <p class="small muted">你认为重要但系统没有采集到的信息，可以在这里补充。核验后点"继续分析"，系统在本次运行基础上增量补充：保留已有信息，只刷新行情、补查新条目、加入你的条目，再重新分析与预测（MP §7.2）。</p>
      ${form}${subRows || (S.addOpen[tk] ? "" : '<p class="small muted">暂无补充。</p>')}${runBox}</div>`;
  }
  function stockNav(tk, sub) {
    const C = M.collections[tk], c = countsOf(tk), R = M.reasoning[tk], ex = M.explanations[tk];
    const p = currentPred(tk, "regular_60m");
    const pred = p && p.probabilities ? `${p.schedule_slot_id ? SLOT_LABEL[p.schedule_slot_id] + " 槽位 · " : ""}60 分钟：${CLASS_LABEL[p.predicted_class]} ${Math.round(p.probabilities[p.predicted_class] * 100)}%` : p ? statusBadge(p) : "—";
    const nCited = new Set(R.flatMap((st) => st.refs.item_ids || []).filter(Boolean)).size;
    const box = (n, title, href, body, active) => `<a class="stepbox ${active ? "active" : ""}" href="${href}"><div class="small muted">${n}</div><b>${title}</b><div class="small">${body}</div></a>`;
    return `<div class="runbar"><div class="small muted">本次运行 <code>${C.run.pipeline_run_id}</code> · 采集 ${hm(C.run.started_at)}–${hm(C.run.finished_at)} ET · 分析截止 11:30:00 ET · <a href="#/ops/run?tk=${tk}">一键运行</a></div>
      <div class="stepflow">
        ${box("第 1 步", "信息采集", `#/stock/${tk}/collect`, `检索 <b>${c.fetched}</b> 条（${Object.keys(c.by_channel).length} 个渠道）· 保留 ${c.kept} · 去重 ${c.duplicate} · 排除 ${c.excluded} · 待核 ${c.pending_review}${c.failed ? ` · <span class="serious-ink">失败 ${c.failed}</span>` : ""} · 本次新增 ${c.new_in_run}`, sub === "collect")}
        <span class="arrow" aria-hidden="true">→</span>
        ${box("第 2 步", "分析与推理", `#/stock/${tk}/reason`, `${R.length} 步推理 · 引用 ${nCited} 条采集项 · ${badge(EXPL, ex.explanation_status)}`, sub === "reason")}
        <span class="arrow" aria-hidden="true">→</span>
        ${box("第 3 步", "预测", `#/forecast/${tk}/regular_60m`, pred, false)}
      </div>
      <div class="tabs" style="margin-top:10px"><a href="#/stock/${tk}" class="${!sub ? "active" : ""}">概览</a><a href="#/stock/${tk}/collect" class="${sub === "collect" ? "active" : ""}">① 信息采集</a><a href="#/stock/${tk}/reason" class="${sub === "reason" ? "active" : ""}">② 分析与推理</a><a href="#/forecast/${tk}/regular_60m">③ 预测 →</a></div></div>`;
  }
  function itemTitle(tk, id) { const it = M.collections[tk].items.find((x) => x.item_id === id); return it ? it.title : id; }
  function collectView(tk, q) {
    const C = M.collections[tk], c = countsOf(tk), F = S.colf;
    const items = C.items.filter((i) => (!F.channel || i.channel === F.channel) && (!F.category || i.category === F.category) && (!F.disposition || (F.disposition === "excluded" ? i.disposition.startsWith("excluded") : i.disposition === F.disposition)) && (!F.q || (i.title + i.source).toLowerCase().includes(F.q.toLowerCase())));
    const chans = Object.keys(c.by_channel), cats = Object.keys(c.by_category);
    const cell = (ch, cat) => C.items.filter((i) => i.channel === ch && i.category === cat);
    const matrix = `<table class="matrix small"><tr><th>渠道 \\ 类别</th>${cats.map((k) => `<th>${M.CATEGORY_LABEL[k]}</th>`).join("")}<th>合计</th></tr>
      ${chans.map((ch) => `<tr><th>${M.CHANNEL_LABEL[ch]}</th>${cats.map((cat) => { const l = cell(ch, cat); const k = l.filter((i) => i.disposition === "kept").length; return `<td class="num">${l.length ? `<b>${l.length}</b>${k !== l.length ? ` <span class="muted">(${k})</span>` : ""}` : '<span class="muted">·</span>'}</td>`; }).join("")}<td class="num"><b>${c.by_channel[ch]}</b></td></tr>`).join("")}
      <tr><th>合计</th>${cats.map((k) => `<td class="num"><b>${c.by_category[k]}</b></td>`).join("")}<td class="num"><b>${c.fetched}</b></td></tr></table>`;
    const tile = (label, n, cls2, f) => `<button class="tile ${F.disposition === f ? "on" : ""}" data-act="colDisp" data-v="${f}"><span class="num big ${cls2 || ""}">${n}</span><span class="small muted">${label}</span></button>`;
    const sel = (k, map, label) => `<label class="small">${label} <select data-act="colf" data-k="${k}"><option value="">全部</option>${Object.keys(map).map((v) => `<option value="${v}" ${F[k] === v ? "selected" : ""}>${Array.isArray(map[v]) ? map[v][0] : map[v]}</option>`).join("")}${k === "disposition" ? `<option value="excluded" ${F.disposition === "excluded" ? "selected" : ""}>全部排除项</option>` : ""}</select></label>`;
    const rows = items.map((i) => {
      const hl = q && q.item === i.item_id;
      const restricted = i.disposition === "excluded_restricted";
      return `<tr id="${i.item_id}" class="${hl ? "hl" : ""} ${restricted ? "restricted" : ""}"><td class="small"><code>${i.item_id}</code>${i.new_in_run || Date.parse(i.available_at) >= Date.parse("2026-12-02T16:25:00Z") ? ' <span class="badge info">本次新增</span>' : ""}</td>
        <td class="small">${M.CHANNEL_LABEL[i.channel]}<div class="muted">${esc(i.source)}</div></td><td class="small nowrap">${M.CATEGORY_LABEL[i.category]}</td>
        <td>${restricted ? "🔒 受限复核：内容不显示" : esc(i.title)}${i.title_note ? `<div class="small muted">${esc(i.title_note)}</div>` : ""}${i.linked_event_id ? `<div class="small"><a href="#/events/${tk}?e=${i.linked_event_id}"><code>${i.linked_event_id}</code></a></div>` : ""}</td>
        <td>${badge(Object.fromEntries(Object.entries(M.DISPOSITION_LABEL)), i.disposition)}${i.exclusion_reason ? `<div class="small muted">${esc(i.exclusion_reason)}</div>` : ""}${i.duplicate_of ? `<div class="small">→ <a href="#/stock/${tk}/collect?item=${i.duplicate_of}"><code>${i.duplicate_of}</code></a></div>` : ""}</td>
        <td class="small nowrap">${i.occurred_at ? fmtET(i.occurred_at) : "—"}</td><td class="small nowrap">${i.source_published_at ? fmtET(i.source_published_at) + ` <span class="muted">(${i.source_published_precision})</span>` : '— <span class="muted">(unknown)</span>'}</td><td class="small nowrap">${fmtET(i.received_at)}</td><td class="small nowrap">${restricted ? "—" : fmtET(i.available_at)}</td></tr>`;
    }).join("");
    return `<div class="grid g3">${addInfoPanel(tk)}
      <div class="card span2"><h2>第 1 步 · 信息采集 <span class="muted small">collection_runs · ${esc(C.run.collection_run_id)}</span></h2>
        <p class="small muted">检索范围：${tk} 本身 + 公司档案中的客户、供应商、监管机构与同行；时间窗 ${fmtET(C.run.window_from)} 至 ${fmtET(C.run.window_to)}（按"可用时间"）。每一条检索到的内容都记录下来，包括没被使用的，并写明原因。</p>
        <div class="tiles">${tile("全部检索", c.fetched, "", "")}${tile("保留 · 进入分析", c.kept, "good-ink", "kept")}${tile("重复/转载", c.duplicate, "", "duplicate")}${tile("排除", c.excluded, "", "excluded")}${tile("待人工复核", c.pending_review, "warn-ink", "pending_review")}${tile("抓取失败", c.failed, "serious-ink", "fetch_failed")}</div>
        <h3>按渠道 × 类别</h3><div class="tablewrap">${matrix}</div><p class="small muted">格内为检索条数，括号内为其中保留进入分析的条数。</p></div>
      <div class="card"><h2>本次轮询的来源</h2><table class="small"><tr><th>来源</th><th>状态</th><th>条数</th><th>耗时</th></tr>${C.run.sources_polled.map((sp) => `<tr><td><code>${sp.source_id}</code><div class="muted">${M.CHANNEL_LABEL[sp.channel]}</div></td><td>${sp.status === "ok" ? '<span class="badge good">正常</span>' : '<span class="badge serious">超时</span>'}</td><td class="num">${sp.items_fetched}</td><td class="num">${(sp.latency_ms / 1000).toFixed(1)}s</td></tr>`).join("")}</table>
        <p class="small muted">来源超时 ≠ 没有新闻：会在推理的"缺口"步骤中列出，并触发数据源告警。</p></div>
      <div class="card" style="grid-column:1/-1"><div class="mrow"><h2 style="margin:0">条目列表 <span class="muted small">显示 ${items.length} / ${c.fetched} 条 · 按可用时间倒序</span></h2>
        <div class="row filters">${sel("channel", M.CHANNEL_LABEL, "渠道")}${sel("category", M.CATEGORY_LABEL, "类别")}${sel("disposition", M.DISPOSITION_LABEL, "处置")}<label class="small">搜索 <input type="search" data-act="colf" data-k="q" value="${esc(F.q)}" placeholder="标题或来源"></label>${F.channel || F.category || F.disposition || F.q ? '<button class="btn sm ghost" data-act="colReset">清除筛选</button>' : ""}</div></div>
        <div class="tablewrap"><table class="collect"><tr><th>ID</th><th>渠道 / 来源</th><th>类别</th><th>标题</th><th>处置</th><th>发生</th><th>首次公开</th><th>系统收到</th><th>可用</th></tr>${rows || '<tr><td colspan="9" class="muted">没有符合筛选条件的条目。</td></tr>'}</table></div>
        <p class="small muted">真实系统分页加载（每页 100 条），本原型为全部模拟条目。行情以汇总项记录，不逐条显示每秒报价。四类时间均以美东时间显示、UTC 存储。</p></div></div>`;
  }
  function reasonView(tk) {
    const R = M.reasoning[tk], ex = M.explanations[tk];
    const chip = (id) => `<a class="chip" href="#/stock/${tk}/collect?item=${id}" title="${esc(itemTitle(tk, id))}"><code>${id}</code> ${esc(itemTitle(tk, id).slice(0, 22))}${itemTitle(tk, id).length > 22 ? "…" : ""}</a>`;
    const steps = R.map((st) => `<li class="rstep"><div class="mrow"><span><b>第 ${st.step} 步</b> ${badge(KIND, st.kind)} <span class="small muted">${st.by === "code" ? "规则计算" : "LLM 起草 · 已核对引用"}</span></span>${st.confidence ? `<span class="small muted">把握：${{ high: "高", medium: "中", low: "低" }[st.confidence]}</span>` : ""}</div>
      <div class="small muted">规则：${esc(st.rule)}</div><div style="margin:4px 0">${esc(st.conclusion)}</div>
      <div class="refs">${(st.refs.item_ids || []).filter(Boolean).map(chip).join("")}${(st.refs.quote_ids || []).map((qid) => `<span class="chip"><code>${qid}</code> 参考报价</span>`).join("")}${(st.refs.analysis_ids || []).map((a) => `<a class="chip" href="#/events/${tk}"><code>${a}</code></a>`).join("")}</div></li>`).join("");
    return `<div class="grid g3">
      <div class="card span2"><h2>第 2 步 · 分析与推理 <span class="muted small">reasoning_trace · 截至 11:30:00 ET</span></h2>
        <p class="small muted">从第 1 步保留的条目和行情出发，逐步得出当前解释。每一步都写明规则和引用；点击引用可跳到第 1 步中的原始条目。没有引用的说法不会出现在"已观察事实"或"可能驱动"中。</p>
        <ol class="rtrace">${steps}</ol></div>
      <div class="card"><div class="mrow"><h2 style="margin:0">得出的当前解释</h2>${badge(EXPL, ex.explanation_status)}</div>
        <h3>已观察事实</h3><ul class="list small">${ex.observed_facts.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
        <h3>可能驱动</h3><ul class="list small">${ex.possible_drivers.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
        <h3>反向证据</h3><ul class="list small">${ex.counter_evidence.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
        <h3>未解释部分</h3><ul class="list small">${ex.unexplained.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
        <p class="small muted">交给第 3 步：<a href="#/forecast/${tk}/regular_60m">查看本槽位预测 →</a></p></div></div>`;
  }
  function pageStock(tk, sub, q) {
    if (sub === "collect" || sub === "reason") {
      const sec = M.securities[tk];
      return `<div class="pagehead"><div><h1>${tk} <span class="muted" style="font-size:15px">${esc(sec.name)}</span></h1><div class="muted small">${sub === "collect" ? "第 1 步：系统采集了哪些信息、来自哪里、哪些被使用" : "第 2 步：如何从信息和行情得出当前解释"}</div></div>${tickerSwitch("stock", tk, "/" + sub)}</div>` +
        stockNav(tk, sub) + withState(() => (sub === "collect" ? collectView(tk, q) : reasonView(tk)), { empty: "本次运行没有采集到条目。" });
    }
    const v = secView(tk), ex = M.explanations[tk];
    const evs = M.evidence.filter((e) => M.events.find((x) => x.event_id === e.event_id && x.tickers.includes(tk)));
    const refreshing = S.refreshing[tk];
    const bars = v.sec.bars.slice(0, lastIdx() + 1);
    const xs = bars.map((_, i) => i);
    const pctS = bars.map((b) => +(((b.close / v.sec.prev_close) - 1) * 100).toFixed(3));
    const pctB = bars.map((b) => +((b.benchmark_index / 100 - 1) * 100).toFixed(3));
    const pctX = bars.map((b) => +((b.soxx_index / 100 - 1) * 100).toFixed(3));
    const tableRows = [0, 30, 60, 90, 120].map((i) => `<tr><td>${idxHM(i)}</td><td class="num">${sgn(pctS[i], 2, "%")}</td><td class="num">${sgn(pctB[i], 2, "%")}</td><td class="num">${sgn(pctX[i], 2, "%")}</td></tr>`).join("");
    const chart = lineChart({
      xs, xDomain: [0, lastIdx()], xTicks: [0, 30, 60, 90, 120], xFmt: (i) => idxHM(i) + " ET", yFmt: (y) => sgn(y, 2, "%"),
      series: [
        { name: tk + "（相对前收）", color: "var(--series-1)", values: pctS },
        { name: "同行篮子 ex-" + tk, color: "var(--series-2)", values: pctB },
        { name: "SOXX（参考）", color: "var(--series-3)", values: pctX, dash: true }
      ],
      vlines: tk === "NVDA" || tk === "AMD" || tk === "MU" ? [{ x: 88.5, label: "政策文件公开 10:58:30" }] : [],
      height: 230, aria: "个股与行业表现",
      table: `<table><tr><th>时间 ET</th><th>${tk}</th><th>同行篮子</th><th>SOXX</th></tr>${tableRows}</table>`
    });
    const rd = tk === "NVDA" || tk === "AMD"
      ? { eo: ["ready", "已定义许可问题"], sr: ["ready", "仅放行 market_baseline（事件增强未验证）"] }
      : tk === "AVGO" ? { eo: ["not_applicable", "今日无开放问题"], sr: ["missing_inputs", "篮子成分同步报价缺失"] } : { eo: ["not_applicable", "无开放问题"], sr: ["ready", "行情有效"] };
    const RD = { ready: ["ready", "good"], missing_inputs: ["missing_inputs", "serious"], manual_review: ["manual_review", "warn"], not_applicable: ["not_applicable", "neutral"] };
    return `<div class="pagehead"><div><h1>${tk} <span class="muted" style="font-size:15px">${esc(v.sec.name)} · ${esc(v.sec.chain)}</span></h1>
      <div class="muted small">security_id <code>${v.sec.security_id}</code> · benchmark_version_id <code>${v.sec.benchmark.benchmark_version_id}</code></div></div>
      ${tickerSwitch("stock", tk)}</div>` + stockNav(tk, "") +
      withState(() => `<div class="grid g3">
        <div class="card"><div class="mrow">${tag("hist")} ${badge(MARKET_STATE, v.market_state)}</div>
          <div class="mrow" style="margin-top:8px"><span class="price num">${v.price.toFixed(2)}</span><span class="num ${cls(v.dayRet)}">${sgn(v.dayRet, 2, "%")} 相对前收</span></div>
          <dl class="kv" style="margin-top:8px"><dt>报价时间</dt><dd>${fmtET(v.quote_ts)}（NBBO mid）</dd><dt>同行篮子</dt><dd class="num">${sgn(v.bmRet, 2, "%")}</dd><dt>相对收益</dt><dd class="num ${cls(v.rel)}">${sgn(v.rel, 2, "pp")}</dd>
          <dt>快照触发</dt><dd><code>${ex.trigger_type}</code></dd><dt>分析截止</dt><dd>${fmtET(clock().now)}</dd></dl>
          ${qualityLine(tk, true)}
          <div class="row" style="margin-top:10px"><button class="btn sm" data-act="refresh" data-tk="${tk}" ${refreshing ? "disabled" : ""}>${refreshing ? "正在更新…" : "主动刷新"}</button><a class="btn sm ghost" href="#/ops/run?tk=${tk}">▶ 一键运行（采集→分析→预测）</a><span class="small muted">${refreshing ? "已入队 build_snapshot(on_demand)" : "有效快照未过期时复用"}</span></div>
        </div>
        <div class="card span2"><div class="mrow"><h2 style="margin:0">当前解释 <span class="muted small">截至 ${hm(clock().now)} ET</span></h2>${tag("expl")} ${badge(EXPL, ex.explanation_status)}</div>
          <div class="grid g2" style="margin-top:8px">
            <div><h3>已观察事实</h3><ul class="list">${ex.observed_facts.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
              <h3>可能驱动（条件表述）</h3><ul class="list">${ex.possible_drivers.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul></div>
            <div><h3>反向证据</h3><ul class="list">${ex.counter_evidence.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
              <h3>未解释部分</h3><ul class="list">${ex.unexplained.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul>
              <h3>与此同时</h3><ul class="list">${ex.concurrent.map((x) => `<li>${esc(x)}</li>`).join("") || "<li class='muted'>无</li>"}</ul></div>
          </div>
          <p class="small muted">相对收益只是描述，不能单独证明哪条消息造成波动。<a href="#/stock/${tk}/reason">查看推理过程（${M.reasoning[tk].length} 步，带引用）→</a></p>
          ${ex.valuation_context ? `<div class="small valuation"><b>估值背景</b>（${esc(ex.valuation_context.as_of)}）：远期 PE ${ex.valuation_context.fwd_pe} · 同行中位 ${ex.valuation_context.peer_median_fwd_pe} · ${esc(ex.valuation_context.note)} <span class="muted">只作背景，不进入短线模型。</span></div>` : `<div class="small muted">估值背景：无授权来源，暂不显示（valuation_context = null）。</div>`}
        </div>
        <div class="card span2"><h2>行业表现</h2>${chart}</div>
        <div class="card"><h2>预测交接 <span class="muted small">prediction_readiness</span></h2>
          <dl class="kv"><dt>事件结果</dt><dd>${badge(RD, rd.eo[0])}<div class="small muted">${esc(rd.eo[1])}</div></dd>
          <dt>股价反应</dt><dd>${badge(RD, rd.sr[0])}<div class="small muted">${esc(rd.sr[1])}</div></dd></dl>
          <div class="small" style="margin-top:10px"><a href="#/forecast/${tk}/regular_60m">→ 查看短期预测</a><br><a href="#/events/${tk}">→ 查看待决事件</a></div></div>
        ${fvaCard(tk)}
        <div class="card" style="grid-column:1/-1"><div class="mrow"><h2 style="margin:0">证据摘要 <span class="muted small">event_evidence · 四类时间</span></h2><a class="small" href="#/stock/${tk}/collect">查看第 1 步全部 ${countsOf(tk).fetched} 条采集项 →</a></div>
          ${evs.length ? `<div class="tablewrap"><table><tr><th>来源</th><th>主张</th><th>核验</th><th>首次公开</th><th>系统收到</th><th>可用</th><th>事件</th></tr>
          ${evs.map((e) => e.visibility === "restricted_review" ? `<tr class="restricted"><td>${esc(e.source)}</td><td>🔒 受限复核：已从公开界面与预测输入排除</td><td>${badge(VERIF, e.verification_status)}</td><td>—（精度 unknown）</td><td>${fmtET(e.received_at)}</td><td>—</td><td><code>${e.event_id}</code></td></tr>` :
            `<tr><td>${esc(e.source)}</td><td>${esc(e.claim)}</td><td>${badge(VERIF, e.verification_status)}</td><td>${fmtET(e.source_published_at)} <span class="muted small">(${e.source_published_precision})</span></td><td>${fmtET(e.received_at)}</td><td>${fmtET(e.available_at)}</td><td><a href="#/events/${tk}?e=${e.event_id}"><code>${e.event_id}</code></a></td></tr>`).join("")}</table></div>`
            : `<p class="muted">监测来源范围内暂未发现新催化剂。快照仍按行情与日程更新（event_id 为空）。</p>`}
        </div></div>`, { empty: "该证券暂无有效快照：等待首个定时快照（每 5 分钟）。" });
  }

  function pageForecast(tk, target) {
    target = target || "regular_60m";
    const p = currentPred(tk, target);
    const sec = M.securities[tk];
    const tabs = `<div class="tabs">${TARGETS.map((t) => `<a href="#/forecast/${tk}/${t.id}" class="${t.id === target ? "active" : ""}">${t.label} <code class="small">${t.id}</code></a>`).join("")}</div>`;
    const body = () => {
      if (!p) return `<div class="card state"><div class="icon">∅</div><h2>尚无预测</h2></div>`;
      // closed / next session special
      if (target === "next_regular_session") {
        const nextS = isClosed() ? "2026-11-27（周五，半日市 09:30–13:00 ET）" : "2026-12-03（周四，09:30–16:00 ET）";
        return `<div class="grid g2"><div class="card"><div class="mrow"><h2 style="margin:0">下一正常交易时段</h2>${statusBadge(p)}</div>
          <dl class="kv" style="margin-top:8px"><dt>适用时段</dt><dd>${nextS}</dd><dt>起算规则</dt><dd>不早于 09:31:00 ET 的首组同步合格报价（D-10），至该场官方收盘价</dd><dt>display_tier</dt><dd><code>${p.display_tier}</code></dd></dl>
          <div class="notice info">模型验证中：<code>next_regular_session</code> 模型处于影子测试，用户端仅展示行情、证据与下列条件展望，不展示数值概率。</div></div>
          <div class="card scenario"><div class="mrow"><h2 style="margin:0">条件展望</h2>${tag("scen")}</div>
          <ul class="list"><li>若规则影响范围经公司确认扩大：关注开盘后相对篮子表现（情景，非预测）</li><li>若无新增信息：沿用行情基线（内部影子）</li></ul>
          <p class="small muted">隔夜跳空 <code>overnight_gap</code> 为独立可选目标，不等于发布后可执行收益。</p></div></div>`;
      }
      if (p.status === "abstained" && p.abstain_reason === "market_closed") {
        return `<div class="card state"><div class="icon">☾</div><h2>休市</h2><p class="muted">${fmtET(clock().now)}：交易所休市（trading_sessions.status = closed）。盘中目标 <code>${target}</code> 不发布。</p><a class="btn" href="#/forecast/${tk}/next_regular_session">查看下一正常时段</a></div>`;
      }
      const hasLine = p.t0_idx != null;
      const endIdx = p.target_end_idx;
      const showTo = p.status === "settled" || p.status === "unsettleable" ? Math.max(endIdx || 0, M.NOW_IDX) : M.NOW_IDX;
      const xMax = Math.max(showTo, endIdx || 0, M.NOW_IDX) + 4;
      const xMin = Math.max(0, (p.published_idx || 60) - 60);
      const bars = sec.bars.slice(0, showTo + 1);
      const xs = bars.map((_, i) => i);
      const vals = bars.map((b) => b.close);
      let band = null, points = [], vlines = [];
      if (hasLine) {
        const t0p = sec.bars[p.t0_idx].close;
        vlines.push({ x: p.published_idx - 0.4, label: "发布 " + hm(p.published_at), color: "var(--text-2)" });
        points.push({ x: p.t0_idx, y: t0p, label: "起算报价 " + hm(p.t0_quote_ts) + " · " + t0p.toFixed(2), text: "起算 " + t0p.toFixed(2), color: "var(--series-1)", dy: 18 });
        if (p.interval && endIdx != null) {
          const q = p.interval.quantiles;
          band = { x: endIdx, lo: t0p * (1 + q.p10 / 100), hi: t0p * (1 + q.p90 / 100), mid: t0p * (1 + q.p50 / 100) };
        }
        if (p.status !== "settled" && p.status !== "unsettleable") vlines.push({ x: M.NOW_IDX, label: "现在 " + idxHM(M.NOW_IDX), row: 1 });
        if (p.status === "settled") points.push({ x: endIdx, y: sec.bars[endIdx].close, fill: "var(--series-1)", label: "结算报价 " + sec.bars[endIdx].close.toFixed(2), text: "结算", dy: 18 });
        if (endIdx != null) vlines.push({ x: endIdx, label: "目标终点 " + idxHM(endIdx), color: "var(--series-1)", dash: "1 3", row: 2 });
      }
      const chart = lineChart({
        xs, xDomain: [xMin, Math.min(390, xMax)], xTicks: niceTicks(xMin, Math.min(390, xMax)), xFmt: (i) => idxHM(i) + " ET", yFmt: (y) => y.toFixed(2),
        series: [{ name: tk + " 历史行情（NBBO mid，1 分钟）", color: "var(--series-1)", values: vals }], legendAlways: true,
        legendExtra: band ? ['<span><i style="background:var(--band);height:10px;border:1px solid var(--series-1)"></i>预测终点 p50 与 p10–p90 区间（未验证，示意）</span>'] : [],
        vlines, points, band, height: 280, aria: "短期预测图",
        table: hasLine ? `<table><tr><th>项</th><th>时间 ET</th><th>价格</th></tr><tr><td>发布</td><td>${fmtET(p.published_at)}</td><td>—</td></tr><tr><td>起算报价</td><td>${fmtET(p.t0_quote_ts)}</td><td class="num">${sec.bars[p.t0_idx].close.toFixed(2)}</td></tr><tr><td>目标终点</td><td>${fmtET(p.target_end_at)}</td><td class="num">${p.status === "settled" ? sec.bars[endIdx].close.toFixed(2) : "—"}</td></tr></table>` : ""
      });
      const probs = p.probabilities && p.display_tier === "validated_public"
        ? ["outperform", "flat", "underperform"].map((k) => `<div class="probbar"><span>${CLASS_LABEL[k]}</span><div class="track"><div class="fill" style="width:${(p.probabilities[k] * 100).toFixed(0)}%"></div></div><span class="num">${(p.probabilities[k] * 100).toFixed(0)}%</span></div>`).join("") +
          `<p class="small muted">类别按相对同行篮子收益：阈值 ±${p.threshold_pp}pp = k 0.25 × σ̂ ${p.sigma_hat_pp}pp（D-09 波动缩放，发布时锁定）。同时报告绝对收益。</p>` +
          (p.move_quantiles ? `<h3>预期波动幅度 <code class="small">regular_60m_move</code></h3><dl class="kv"><dt>|相对收益| 中位</dt><dd class="num">${p.move_quantiles.p50}pp</dd><dt>80% 分位</dt><dd class="num">${p.move_quantiles.p80}pp</dd><dt>90% 分位</dt><dd class="num">${p.move_quantiles.p90}pp</dd></dl><p class="small muted">波动幅度比方向更可预测；内部影子阶段，通过门槛后作为精选用户 v1 的首个输出（MP §12）。</p>` : "")
        : `<div class="notice">${p.status === "abstained" ? "弃预测：" + esc(ABSTAIN[p.abstain_reason] || p.abstain_reason) : "无可展示概率"}${p.note ? "。" + esc(p.note) : ""}</div>`;
      const st = p.settlement;
      const settleBox = p.status === "settled" ? `<dl class="kv"><dt>个股</dt><dd class="num ${cls(st.stock_return_pct)}">${sgn(st.stock_return_pct, 2, "%")}</dd><dt>同行篮子</dt><dd class="num">${sgn(st.benchmark_return_pct, 2, "%")}</dd><dt>相对</dt><dd class="num ${cls(st.relative_return_pp)}">${sgn(st.relative_return_pp, 2, "pp")} → ${CLASS_LABEL[st.outcome_class]}</dd><dt>命中</dt><dd>${st.hit ? badge(STATUS, "settled", "命中") : '<span class="badge serious">未命中</span>'}</dd><dt>Brier</dt><dd class="num">${st.brier}</dd></dl>`
        : p.status === "unsettleable" ? `<div class="notice crit">✕ 无法结算（<code>${esc(st.invalid_reason)}</code>）：${esc(st.reason_text)}</div>`
        : p.status === "awaiting_settlement" ? `<p>待结算：目标终点 ${fmtET(p.target_end_at)}，结算任务在终点后 30s 容差内取同步合格报价。</p>`
        : `<p class="muted">—</p>`;
      const list = predsFor(tk, target);
      return `<div class="grid g3">
        <div class="card span2"><div class="mrow"><h2 style="margin:0">${TARGET_LABEL[target]}</h2><span class="row">${tag("hist")} ${tag("pred")} ${statusBadge(p)}</span></div>${chart}
          <p class="small muted">区间按相对收益分位数换算到起算价（假设篮子持平，示意）。未有多时间点模型时，只画预测终点与区间。</p></div>
        <div class="card"><h2>事前预测 ${p.prediction_id ? `<a class="small" href="#/replay/${p.prediction_id}">回放 →</a>` : ""}</h2>${probs}
          ${p.prediction_id && p.valid_until ? `<p class="small">有效至 ${fmtET(p.valid_until)} ${badge(DISP, displayState(p))}</p>` : ""}
          ${p.supersedes_prediction_id ? `<p class="small muted">修订自 <a href="#/replay/${p.supersedes_prediction_id}"><code>${p.supersedes_prediction_id}</code></a>（旧版保留，灰显）</p>` : ""}
          <h3>结算</h3>${settleBox}
          <h3>锁定版本</h3>${p.locked ? `<dl class="kv small">${Object.entries(p.locked).map(([k, v]) => `<dt>${k}</dt><dd><code>${esc(v)}</code></dd>`).join("")}</dl>` : '<p class="muted small">—</p>'}</div>
        <div class="card" style="grid-column:1/-1"><h2>今日 ${tk} · ${TARGET_LABEL[target]} 预测记录</h2>
          ${list.length ? `<div class="tablewrap"><table><tr><th>prediction_id</th><th>触发</th><th>发布</th><th>状态</th><th>显示</th><th>预测</th><th>相对收益</th><th></th></tr>${list.map((q) => { const ds = displayState(q); return `<tr class="${ds === "superseded" ? "superseded" : ""}"><td><code>${q.prediction_id}</code></td><td><code>${q.trigger_type}</code> <span class="muted small">${q.sampling_rule}${q.schedule_slot_id ? " · 槽位 " + SLOT_LABEL[q.schedule_slot_id] : ""}${q.is_primary ? "" : " · 非主评分"}</span></td><td>${fmtET(q.published_at)}</td><td>${statusBadge(q)}</td><td>${ds ? badge(DISP, ds) : "—"}</td><td>${q.predicted_class ? CLASS_LABEL[q.predicted_class] : "—"}</td><td class="num">${q.settlement && q.settlement.relative_return_pp != null ? sgn(q.settlement.relative_return_pp, 2, "pp") : "—"}</td><td>${q.t0_idx != null ? `<a href="#/replay/${q.prediction_id}">回放</a>` : ""}</td></tr>`; }).join("")}</table></div>` : '<p class="muted">无记录</p>'}
        </div></div>`;
    };
    return `<div class="pagehead"><div><h1>短期预测</h1><div class="muted small">股价预测从公开预测后的首组同步合格报价起算 · 主基准 <code>${sec.benchmark.benchmark_version_id}</code></div></div>${tickerSwitch("forecast", tk, "/" + target)}</div>${tabs}` + withState(body, { empty: "该目标今日尚无预测记录。" });
  }
  function niceTicks(a, b) {
    const out = []; const step = b - a > 200 ? 60 : 30;
    for (let x = Math.ceil(a / step) * step; x <= b; x += step) out.push(x);
    return out;
  }

  function pageEvents(tk, q) {
    const evs = M.events.filter((e) => e.tickers.includes(tk));
    const sel = (q && q.e && evs.find((e) => e.event_id === q.e)) || evs[0];
    const PROG = { pending: ["待决", "warn"], outcome_confirmed: ["结果已确认", "good"], effective: ["已生效", "info"], terminated: ["终止", "neutral"] };
    const body = () => {
      if (!sel) return `<div class="card state"><div class="icon">∅</div><h2>暂无事件</h2><p class="muted">监测来源范围内暂未发现与 ${tk} 关联的事件。</p></div>`;
      const evd = M.evidence.filter((e) => e.event_id === sel.event_id);
      const linked = sel.linked_stock_predictions.map((id) => M.predictions.find((p) => p.prediction_id === id)).filter(Boolean);
      return `<div class="grid g3">
        <div class="card"><h2>事件列表</h2>${evs.map((e) => `<div style="padding:8px 0;border-bottom:1px solid var(--border)"><a href="#/events/${tk}?e=${e.event_id}"><b>${esc(e.title)}</b></a>${e === sel ? " ◀" : ""}<div class="row small" style="margin-top:4px">${badge(PROG, e.progress_status)} ${badge(VERIF, e.evidence_status)}</div><div class="small muted"><code>${e.category}</code></div></div>`).join("")}</div>
        <div class="card span2"><div class="mrow"><h2 style="margin:0">${esc(sel.title)}</h2><span class="row">${badge(PROG, sel.progress_status)} ${badge(VERIF, sel.evidence_status)}</span></div>
          <div class="small muted">event_id <code>${sel.event_id}</code> · identity_key <code>${esc(sel.identity_key)}</code> · 涉及 ${sel.tickers.join(", ")}</div>
          <h3>时间线（节点与证据）</h3><div class="timeline">${sel.milestones.map((m) => `<div class="tl-item ${m.status}"><b>${esc(m.milestone_type)}</b> <span class="muted small">${esc(m.decision_body)}</span> ${m.status === "occurred" ? `<span class="badge good">✓ ${fmtET(m.actual_at)}</span>` : `<span class="badge neutral">预计 ${fmtET(m.expected_at)}</span>`}
            ${m.evidence_ids.map((id) => { const e = evd.find((x) => x.evidence_id === id); return e ? `<div class="small">↳ ${esc(e.source)}：${esc(e.claim)} ${badge(VERIF, e.verification_status)}</div>` : ""; }).join("")}</div>`).join("")}</div>
        </div>
        <div class="card"><div class="mrow"><h2 style="margin:0">事件结果</h2>${tag("scen")}</div>
          ${sel.question ? `<p><b>问题：</b>${esc(sel.question)}</p><div class="scenario">${sel.outcomes.map((o) => `<div>○ ${esc(o.label)} <code class="small">${o.outcome}</code></div>`).join("")}</div>
          <div class="notice info">${esc(sel.outcome_prediction.note)}</div><p class="small muted">事件结果与股价反应独立预测、独立计分。到期仅能确认"未公开证实"时按预设规则结算或标记无法核验。</p>`
            : `<p class="muted">${esc(sel.outcome_prediction.note)}</p>`}</div>
        <div class="card"><div class="mrow"><h2 style="margin:0">对应股价预测</h2>${tag("pred")}</div>
          ${linked.length ? linked.map((p) => `<div style="padding:6px 0;border-bottom:1px solid var(--border)"><b>${p.ticker}</b> · ${TARGET_LABEL[p.target_id]} ${statusBadge(p)}<div class="small">预测 ${p.predicted_class ? CLASS_LABEL[p.predicted_class] : "—"} · 发布 ${fmtET(p.published_at)} · <a href="#/replay/${p.prediction_id}">回放</a></div></div>`).join("") : '<p class="muted">该事件没有关联的已锁定股价预测。</p>'}</div>
        ${analoguesCard(sel)}
        ${resolutionCard(sel)}
        ${conditionalCard(sel)}
        ${crossIndustryCard(sel)}
        <div class="card"><h2>分析版本</h2><table><tr><th>版本</th><th>类型</th><th>截止</th><th>摘要</th></tr>${sel.versions.map((v) => `<tr class="${v.analysis_version === sel.current_analysis_version ? "sel" : ""}"><td>v${v.analysis_version}${v.analysis_version === sel.current_analysis_version ? " · 当前" : ""}</td><td><code>${v.analysis_kind}</code></td><td>${fmtET(v.analysis_as_of)}</td><td>${esc(v.summary)}</td></tr>`).join("")}</table><p class="small muted">已发出的判断继续引用当时锁定的版本。</p></div>
      </div>`;
    };
    return `<div class="pagehead"><div><h1>待决事件</h1><div class="muted small">事件阶段、证据与两条独立预测轨道</div></div>${tickerSwitch("events", tk)}</div>` + withState(body, { empty: "暂无与该证券关联的事件。" });
  }

  // ---------- 0.5: forecast vs actual (D-43, D-44) ----------
  const SLOT_LABEL = { s0830_pre_open: "08:30 盘前展望", s1000: "10:00", s1130: "11:30", s1300: "13:00", s1430: "14:30", s1630_next: "16:30 盘后展望" };
  function fvaChart(tk) {
    const rows = M.fva[tk];
    const W = window.innerWidth < 720 ? 440 : 1000, H = 300, P = { l: 56, r: 16, t: 24, b: 30 };
    const x0 = 0, x1 = 390;
    let ys = [0];
    rows.forEach((r) => { r.forecast_path.points.forEach((q) => ys.push(q.p10, q.p90)); r.actual_path.forEach((a) => ys.push(a.relative_pp)); });
    let y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys); const pad = (y1 - y0) * 0.1 || 0.5; y0 -= pad; y1 += pad;
    const X = (x) => P.l + ((x - x0) / (x1 - x0)) * (W - P.l - P.r);
    const Y = (y) => P.t + (1 - (y - y0) / (y1 - y0)) * (H - P.t - P.b);
    let g = '<g class="grid">';
    for (let k = 0; k <= 4; k++) { const yv = y0 + ((y1 - y0) * k) / 4; g += `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(yv)}" y2="${Y(yv)}"/><text x="${P.l - 6}" y="${Y(yv) + 4}" text-anchor="end">${sgn(yv, 2, "pp")}</text>`; }
    g += "</g>";
    [0, 60, 120, 180, 240, 300, 390].forEach((t) => { g += `<text class="tick" x="${X(t)}" y="${H - 10}" text-anchor="${t === 390 ? "end" : t === 0 ? "start" : "middle"}">${idxHM(t)}</text>`; });
    g += `<line class="axis" x1="${P.l}" x2="${W - P.r}" y1="${Y(0)}" y2="${Y(0)}" stroke-dasharray="2 3"/>`;
    // slot markers
    M.SCHEDULE.slots.filter((sl) => sl.idx >= 0 && sl.idx <= 390).forEach((sl) => {
      const done = sl.idx <= M.NOW_IDX;
      g += `<line x1="${X(sl.idx)}" x2="${X(sl.idx)}" y1="${P.t - 6}" y2="${H - P.b}" stroke="var(--border)" stroke-dasharray="${done ? "0" : "3 3"}"/><text x="${X(sl.idx) + 3}" y="${P.t - 9}" class="small" fill="var(--text-2)">${sl.time_et}${done ? "" : " 待发布"}</text>`;
    });
    rows.forEach((r) => {
      const fp = r.forecast_path.points;
      const up = fp.map((q) => `${X(r.t0_idx + q.min).toFixed(1)},${Y(q.p90).toFixed(1)}`);
      const lo = fp.slice().reverse().map((q) => `${X(r.t0_idx + q.min).toFixed(1)},${Y(q.p10).toFixed(1)}`);
      g += `<polygon points="${up.concat(lo).join(" ")}" fill="var(--band)" stroke="none"><title>${SLOT_LABEL[r.schedule_slot_id]} 预测区间 p10–p90</title></polygon>`;
      g += `<path d="${fp.map((q, i) => (i ? "L" : "M") + X(r.t0_idx + q.min).toFixed(1) + "," + Y(q.p50).toFixed(1)).join("")}" fill="none" stroke="var(--series-2)" stroke-width="2" stroke-dasharray="5 3"/>`;
      if (r.actual_path.length > 1) g += `<path d="${r.actual_path.map((a, i) => (i ? "L" : "M") + X(r.t0_idx + a.min).toFixed(1) + "," + Y(a.relative_pp).toFixed(1)).join("")}" fill="none" stroke="var(--series-1)" stroke-width="2"/>`;
      if (r.status === "settled") { const e = r.actual_path[r.actual_path.length - 1]; g += `<circle cx="${X(r.t0_idx + e.min)}" cy="${Y(e.relative_pp)}" r="4" fill="${r.inside_p80 ? "var(--series-1)" : "var(--critical)"}"><title>结算 ${sgn(e.relative_pp, 2, "pp")}${r.inside_p80 ? "（区间内）" : "（区间外）"}</title></circle>`; }
    });
    g += `<line x1="${X(M.NOW_IDX)}" x2="${X(M.NOW_IDX)}" y1="${P.t}" y2="${H - P.b}" stroke="var(--text-2)" stroke-width="1"/><text x="${X(M.NOW_IDX) - 3}" y="${H - P.b - 4}" text-anchor="end" class="small" fill="var(--text-2)">现在 ${idxHM(M.NOW_IDX)}</text>`;
    const legend = `<div class="legend small"><span><i style="background:var(--series-1)"></i>实际（相对同行篮子，起算后）</span><span><i style="background:var(--series-2)"></i>预测中位路径（虚线）</span><span><i style="background:var(--band);border:1px solid var(--series-2)"></i>预测区间 p10–p90</span><span><i style="background:var(--critical);border-radius:50%"></i>结算落在区间外</span></div>`;
    return `<svg class="chart fva" viewBox="0 0 ${W} ${H}" role="img" aria-label="${tk} 今日槽位预测与实际对照">${g}</svg>${legend}`;
  }
  function rollupCell(r) {
    if (!r) return "<td colspan='5' class='muted'>—</td>";
    const few = r.n_settled < 30;
    return few ? `<td class="num">${r.n_settled}</td><td colspan="4" class="muted small">样本不足（n &lt; 30），只显示计数</td>`
      : `<td class="num">${r.n_settled}</td><td class="num">${Math.round(r.hit_rate * 100)}%</td><td class="num">${r.brier.toFixed(3)}</td><td class="num">${sgn(r.bss_class_frequency, 3, "")}</td><td class="num">${Math.round(r.coverage_p80 * 100)}%</td>`;
  }
  function fvaCard(tk) {
    if (isClosed()) return `<div class="card" style="grid-column:1/-1"><h2>预测与实际</h2><p class="muted">休市日没有槽位（sched-0.1 holiday_rule = skip_all）。上一交易日 16:30 的盘后展望覆盖下一交易时段。</p></div>`;
    const rows = M.fva[tk];
    const settled = rows.filter((r) => r.status === "settled");
    const today = { n_settled: settled.length, hit_rate: settled.filter((r) => r.hit).length / (settled.length || 1), brier: 0, bss_class_frequency: 0, coverage_p80: 0 };
    const R = M.fvaRollups[tk];
    const slotRows = M.SCHEDULE.slots.map((sl) => {
      const r = rows.find((x) => x.schedule_slot_id === sl.slot_id);
      if (!r) {
        const future = sl.idx > M.NOW_IDX;
        const note = sl.slot_id === "s0830_pre_open" ? "盘前展望：模型验证中（内部影子），收盘后结算" : future ? "未到时刻" : "—";
        return `<tr><td>${SLOT_LABEL[sl.slot_id]}</td><td>${sl.targets.map((t) => `<code class="small">${t}</code>`).join(" ")}</td><td colspan="5" class="muted small">${note}</td></tr>`;
      }
      const q = r.forecast_path.points[r.forecast_path.points.length - 1];
      const a = r.actual_path[r.actual_path.length - 1];
      return `<tr><td>${SLOT_LABEL[sl.slot_id]}</td><td><code class="small">${r.target_id}</code></td><td>${statusBadge({ status: r.status })}</td><td>${CLASS_LABEL[r.predicted_class]} · p50 ${sgn(q.p50, 2, "pp")} <span class="muted small">[${sgn(q.p10, 2, "")}, ${sgn(q.p90, 2, "")}]</span></td>
        <td class="num">${r.status === "settled" ? sgn(a.relative_pp, 2, "pp") + " → " + CLASS_LABEL[r.outcome_class] : `至今 ${sgn(a.relative_pp, 2, "pp")}`}</td>
        <td>${r.status === "settled" ? (r.hit ? '<span class="badge good">命中</span>' : '<span class="badge serious">未命中</span>') + (r.inside_p80 ? ' <span class="badge neutral">区间内</span>' : ' <span class="badge crit">区间外</span>') : "—"}</td>
        <td class="num">${r.brier != null ? r.brier : "—"}</td></tr>`;
    }).join("");
    return `<div class="card" style="grid-column:1/-1" id="fva"><div class="mrow"><h2 style="margin:0">预测与实际 <span class="muted small">今日槽位 · sched-0.1 · 美东时间</span></h2><span class="row">${tag("hist")} ${tag("pred")}</span></div>
      <p class="small muted">每到新槽位（10:00、11:30、13:00、14:30）先结算并展示上一批预测，再发布新预测。每个窗口从起算报价开始画：实线为实际相对收益，虚线和阴影为发布时锁定的预测（中间路径按 √时间缩放，仅示意；只有终点是模型输出）。</p>
      ${fvaChart(tk)}
      <div class="tablewrap"><table><tr><th>槽位</th><th>目标</th><th>状态</th><th>事前预测（相对 pp）</th><th>实际</th><th>结果</th><th>Brier</th></tr>${slotRows}</table></div>
      <h3>准确率（槽位预测，主评分样本）</h3>
      <div class="tablewrap"><table><tr><th>窗口</th><th>已结算 n</th><th>命中率</th><th>Brier</th><th>BSS（对历史频率）</th><th>80% 区间覆盖</th></tr>
        <tr><td>今日</td>${rollupCell(today)}</tr><tr><td>近 20 个交易日</td>${rollupCell(R.rolling_20d)}</tr><tr><td>上线以来</td>${rollupCell(R.since_live)}</tr></table></div>
      <p class="small muted">分母公开：近 20 日发布 ${R.rolling_20d.n_published} 条，弃预测 ${R.rolling_20d.n_abstained}、无法结算 ${R.rolling_20d.n_unsettleable}。这些对照每周进入训练复盘（<a href="#/admin/fva">研发后台 · 预测对照</a>），不会逐条调参。数字为虚构。</p></div>`;
  }

  // ---------- 0.4 event cards ----------
  const FB = { none: "未放宽", drop_subtype: "放宽子类", peer_group: "放宽到同模板公司", sector_wide: "放宽到全行业" };
  function analoguesCard(e) {
    const h = e.historical_cases;
    if (!h) return "";
    const body = h.insufficient
      ? `<div class="notice">历史样本不足：n = ${h.n} &lt; 8（${esc(FB[h.fallback_level])}后仍不足），不显示中位数。</div>`
      : `<dl class="kv"><dt>同类案例</dt><dd>n = ${h.n} · ${esc(h.period)}</dd><dt>相对篮子中位数</dt><dd class="num">${sgn(h.median_relative_pp, 1, "pp")}</dd><dt>四分位距</dt><dd class="num">${sgn(h.iqr_pp[0], 1, "pp")} ～ ${sgn(h.iqr_pp[1], 1, "pp")}</dd><dt>正收益占比</dt><dd class="num">${Math.round(h.hit_share_positive * 100)}%</dd></dl>`;
    return `<div class="card"><div class="mrow"><h2 style="margin:0">历史类比</h2>${tag("hist")}</div>
      <div class="small muted">${esc(h.query_version)} · 目标 <code>${h.target_id}</code> · 匹配：${Object.values(h.match_keys).map(esc).join(" / ")}</div>${body}
      <p class="small">${badge({ x: [FB[h.fallback_level], h.fallback_applied ? "warn" : "good"] }, "x")} ${h.fallback_note ? esc(h.fallback_note) : ""}</p>
      <p class="small muted">只用过去且不自匹配；只作参考，不是方向信号（D-38）。数字为虚构。</p></div>`;
  }
  function resolutionCard(e) {
    const r = e.outcome_resolution;
    if (!r) return "";
    return `<div class="card"><h2>事件结算规则 <span class="muted small">outcome_resolution</span></h2>
      <dl class="kv small"><dt>解决里程碑</dt><dd>${r.resolving_milestones.map((m) => `<code>${m}</code>`).join("、")}</dd><dt>确认来源</dt><dd>${r.confirm_sources.map((m) => `<code>${m}</code>`).join("、")}</dd>
      <dt>决定机构</dt><dd>${esc(r.decision_body)}</dd><dt>公开确认时间</dt><dd>${esc(r.public_confirmation_rule)}</dd><dt>法律生效时间</dt><dd>${esc(r.legal_effective_rule)}</dd>
      <dt>来源冲突</dt><dd>${esc(r.outcome_conflict_rule)}</dd><dt>截止无结果</dt><dd>${esc(r.no_result_rule)}</dd></dl>
      ${r.clearance_note ? `<div class="notice info">${esc(r.clearance_note)}</div>` : ""}<p class="small muted">报表按公开确认时间判定是否在截止前（D-39）。</p></div>`;
  }
  function conditionalCard(e) {
    const list = e.conditional_forecasts || [];
    if (!list.length) return "";
    const CS = { awaiting_trigger: ["等待触发", "info"], not_triggered: ["未触发", "neutral"], awaiting_settlement: ["已触发，待结算", "warn"], settled: ["已结算", "good"] };
    return `<div class="card scenario"><div class="mrow"><h2 style="margin:0">条件预测</h2>${tag("scen")}</div>${list.map((c) => `
      <div style="padding:6px 0"><b>${esc(c.condition_label)}</b> → ${TARGET_LABEL[c.inner_target_id]} ${badge(CS, c.status)}
      <dl class="kv small"><dt>触发条件</dt><dd><code>${c.condition_outcome}</code></dd><dt>触发截止</dt><dd>${fmtET(c.trigger_deadline_at)}</dd><dt>起算</dt><dd>${esc(c.quote_rule_after_trigger)}</dd></dl>
      <p class="small muted">${esc(c.note)}</p></div>`).join("")}</div>`;
  }
  function crossIndustryCard(e) {
    if (!e.cross_industry) return "";
    return `<div class="card"><h2>跨行业解读 <span class="muted small">industry_template（D-42）</span></h2><table><tr><th>模板</th><th>公司</th><th>影响</th></tr>${e.cross_industry.map((c) => `<tr><td><code>${c.template}</code></td><td>${esc(c.ticker)}</td><td>${esc(c.exposure)}</td></tr>`).join("")}</table><p class="small muted">银行模板公司仅用于测试，不在首版名单与评分中。</p></div>`;
  }

  let replayTimer = null;
  function pageReplay(pid, q) {
    const replayable = M.predictions.filter((p) => p.t0_idx != null);
    let p = M.predictions.find((x) => x.prediction_id === pid) || replayable[0];
    if (S.demo === "unsettleable") p = M.predictions.find((x) => x.status === "unsettleable");
    const step = Math.min(5, +(q && q.step) || 5);
    const sec = M.securities[p.ticker];
    const STEPS = ["锁定输入", "发布", "起算报价", "窗口行情", "结算"];
    const body = () => {
      if (p.t0_idx == null) return `<div class="card state"><h2>该预测未发布起算报价</h2><p class="muted">弃预测记录没有可回放的窗口。</p></div>`;
      const endIdx = p.target_end_idx;
      const visibleTo = step >= 4 ? Math.min(endIdx, p.status === "settled" || p.status === "unsettleable" ? endIdx : M.NOW_IDX) : step >= 3 ? p.t0_idx : p.published_idx;
      const xs = [], vals = [];
      for (let i = Math.max(0, p.t0_idx - 30); i <= Math.max(visibleTo, p.t0_idx - 30); i++) { xs.push(i); vals.push(sec.bars[i].close); }
      const pts = [];
      if (step >= 3) pts.push({ x: p.t0_idx, y: sec.bars[p.t0_idx].close, label: "起算", text: "起算 " + sec.bars[p.t0_idx].close.toFixed(2), dy: 18 });
      if (step >= 5 && p.status === "settled") pts.push({ x: endIdx, y: sec.bars[endIdx].close, fill: "var(--series-1)", label: "结算", text: "结算 " + sec.bars[endIdx].close.toFixed(2), dy: 18 });
      let band = null;
      if (step >= 2 && p.interval) { const t0p = sec.bars[p.t0_idx].close, qq = p.interval.quantiles; band = { x: endIdx, lo: t0p * (1 + qq.p10 / 100), hi: t0p * (1 + qq.p90 / 100), mid: t0p * (1 + qq.p50 / 100) }; }
      const xMin = Math.max(0, p.t0_idx - 30), xMax = Math.min(390, endIdx + 4);
      const allY = sec.bars.slice(xMin, Math.min(endIdx, 390) + 1).map((b) => b.close);
      const chart = lineChart({ xs, xDomain: [xMin, xMax], xTicks: niceTicks(xMin, xMax), xFmt: (i) => idxHM(i) + " ET", yFmt: (y) => y.toFixed(2),
        series: [{ name: p.ticker + " 历史行情", color: "var(--series-1)", values: vals }], legendAlways: true, extraY: allY,
        vlines: step >= 2 ? [{ x: p.published_idx - 0.4, label: "发布 " + hm(p.published_at) }, { x: endIdx, label: "目标终点", dash: "1 3", color: "var(--series-1)", row: 1 }] : [],
        points: pts, band, height: 260, aria: "预测回放" });
      const st = p.settlement;
      const raw = { prediction: Object.assign({}, p, { settlement: undefined, published_idx: undefined, t0_idx: undefined, target_end_idx: undefined }), settlement: step >= 5 ? st : "（第 5 步显示）" };
      return `<div class="grid g3">
        <div class="card span2"><div class="row"><b>回放步骤</b><span class="spacer"></span><button class="btn sm" data-act="play" data-pid="${p.prediction_id}">▶ 播放</button><button class="btn sm ghost" data-act="step" data-pid="${p.prediction_id}" data-step="${Math.max(1, step - 1)}">上一步</button><button class="btn sm ghost" data-act="step" data-pid="${p.prediction_id}" data-step="${Math.min(5, step + 1)}">下一步</button></div>
          <div class="steps">${STEPS.map((s, i) => `<span class="step ${i + 1 < step ? "done" : i + 1 === step ? (i === 4 && p.status === "unsettleable" ? "fail" : "cur") : ""}">${i + 1}. ${s}</span>`).join("")}</div>
          ${chart}</div>
        <div class="card"><h2>预测 vs 真实</h2><dl class="kv"><dt>证券 / 目标</dt><dd>${p.ticker} · ${TARGET_LABEL[p.target_id]}</dd><dt>触发</dt><dd><code>${p.trigger_type}</code>${p.event_id ? ` · <code>${p.event_id}</code>` : " · 无事件（event_id 为空）"}</dd>
          <dt>发布</dt><dd>${fmtET(p.published_at)}</dd><dt>起算报价</dt><dd>${step >= 3 ? fmtET(p.t0_quote_ts) + " · " + sec.bars[p.t0_idx].close.toFixed(2) : "—"}</dd><dt>目标终点</dt><dd>${fmtET(p.target_end_at)}</dd>
          <dt>预测概率</dt><dd>${p.probabilities ? ["outperform", "flat", "underperform"].map((k) => CLASS_LABEL[k] + " " + Math.round(p.probabilities[k] * 100) + "%").join(" / ") : "—"}</dd>
          <dt>预测类别</dt><dd>${p.predicted_class ? CLASS_LABEL[p.predicted_class] : "—"}</dd>
          <dt>真实结果</dt><dd>${step < 5 ? '<span class="muted">（第 5 步揭示）</span>' : p.status === "settled" ? `个股 ${sgn(st.stock_return_pct, 2, "%")} · 篮子 ${sgn(st.benchmark_return_pct, 2, "%")} · 相对 <b>${sgn(st.relative_return_pp, 2, "pp")}</b> → ${CLASS_LABEL[st.outcome_class]} ${st.hit ? badge(STATUS, "settled", "命中") : '<span class="badge serious">未命中</span>'}` : p.status === "unsettleable" ? badge(STATUS, "unsettleable", st.invalid_reason) : badge(STATUS, p.status)}</dd>
          <dt>结算理由</dt><dd class="small">${step >= 5 && st ? esc(st.reason_text) : "—"}</dd></dl>
          <h3>选择已锁定预测</h3><select data-act="pick" style="width:100%">${replayable.map((x) => `<option value="${x.prediction_id}" ${x === p ? "selected" : ""}>${x.prediction_id} · ${STATUS[x.status][0]}</option>`).join("")}</select></div>
        <div class="card" style="grid-column:1/-1"><h2>原始数据 <span class="muted small">锁定输入与结算记录（JSON）</span></h2><pre class="json">${esc(JSON.stringify(raw, null, 2))}</pre></div></div>`;
    };
    return `<div class="pagehead"><div><h1>预测回放</h1><div class="muted small">逐步重放一条已锁定预测：只使用发布时可得数据；结果在第 5 步揭示</div></div></div>` + withState(body, { empty: "没有可回放的已锁定预测。" });
  }

  // ---------- ADMIN ----------
  const ADMIN_TABS = [["runs", "训练任务"], ["datasets", "数据快照"], ["params", "模型参数对比"], ["validation", "验证总览"], ["fva", "预测对照"], ["shadow", "影子测试"], ["approvals", "发布审批"]];
  function pageAdmin(tab) {
    tab = tab || "runs";
    const nav = `<nav class="sidenav">${ADMIN_TABS.map(([k, l]) => `<a href="#/admin/${k}" class="${k === tab ? "active" : ""}">${l}</a>`).join("")}<p class="small muted" style="padding:8px">仅限 researcher / reviewer 角色。示例指标为虚构。</p></nav>`;
    const fn = { runs: adminRuns, datasets: adminDatasets, params: adminParams, validation: adminValidation, fva: adminFva, shadow: adminShadow, approvals: adminApprovals }[tab];
    return `<div class="pagehead"><div><h1>训练与验证后台</h1><div class="muted small">线上：<code>mdl_regular_60m_market_logit_v3</code> · 候选：<code>mdl_regular_60m_market_event_logit_v1</code>（影子）</div></div></div><div class="admin">${nav}<div>${withState(fn, { empty: "没有训练任务。" })}</div></div>`;
  }
  const RUN_ST = { queued: ["已排队", "neutral"], building_dataset: ["构建数据", "info"], training: ["训练", "info"], calibrating: ["校准", "info"], evaluating: ["评估", "info"], completed: ["完成", "good"], failed: ["失败", "crit"], cancelled: ["取消", "neutral"] };
  function adminRuns() {
    const runs = M.trainingRuns.map((r) => (r.training_run_id === "tr_sim_new" && S.simRun ? Object.assign({}, r, S.simRun) : r));
    const sel = runs.find((r) => r.training_run_id === S.selRun) || runs[0];
    const stageIdx = M.STAGES.indexOf(sel.status === "failed" ? sel.stage : sel.status === "completed" ? "completed" : sel.stage);
    const met = M.runMetrics[sel.training_run_id];
    let curve = "";
    if (met) {
      const n = met.curve.train.length, xs = Array.from({ length: n }, (_, i) => i + 1);
      curve = lineChart({ xs, xDomain: [1, n], xTicks: [1, 10, 20, 30, 40], xFmt: (i) => "迭代 " + i, yFmt: (y) => y.toFixed(3),
        series: [{ name: "训练 log loss（train）", color: "var(--series-1)", values: met.curve.train }, { name: "验证 log loss（validation）", color: "var(--series-2)", values: met.curve.validation }], height: 220, aria: "训练与验证损失" });
    }
    return `<div class="card"><div class="row"><h2 style="margin:0">训练任务列表</h2><span class="spacer"></span><button class="btn sm" data-act="simrun" ${S.simRun && S.simRun.status !== "completed" ? "disabled" : ""}>模拟一次手动训练</button></div>
      <div class="tablewrap"><table><tr><th>任务 ID</th><th>目标</th><th>模型 / 参数层</th><th>数据快照</th><th>触发</th><th>阶段</th><th>耗时</th></tr>
      ${runs.map((r) => `<tr class="clickable ${r === sel ? "sel" : ""}" data-run="${r.training_run_id}"><td><code>${r.training_run_id}</code></td><td><code>${r.target_id}</code></td><td>${r.model_family} / ${r.param_layers}</td><td><code class="small">${r.dataset_version_id}</code></td><td>${r.trigger}</td><td>${badge(RUN_ST, r.status)}</td><td class="num">${r.started_at && r.finished_at ? Math.round((Date.parse(r.finished_at) - Date.parse(r.started_at)) / 60000) + " 分" : "—"}</td></tr>`).join("")}</table></div></div>
      <div class="card" style="margin-top:14px"><h2>任务详情 · <code>${sel.training_run_id}</code></h2>
        <div class="steps">${M.STAGES.map((s, i) => `<span class="step ${sel.status === "failed" && i === stageIdx ? "fail" : i < stageIdx || sel.status === "completed" ? "done" : i === stageIdx ? "cur" : ""}">${RUN_ST[s][0]}</span>`).join("")}</div>
        <p class="small muted">按阶段显示完成状态；算法没有逐轮指标时只显示阶段结果，不显示虚构百分比。</p>
        ${sel.error ? `<div class="notice crit">失败原因 <code>${esc(sel.error.code)}</code>：${esc(sel.error.message)}。线上版本不受影响，仍可正常读取。</div>` : ""}
        <dl class="kv small"><dt>范围</dt><dd>${esc(sel.scope)}</dd><dt>code_version</dt><dd><code>${sel.code_version}</code></dd><dt>random_seed</dt><dd>${sel.random_seed}</dd><dt>开始 / 结束</dt><dd>${fmtET(sel.started_at)} / ${fmtET(sel.finished_at)}</dd></dl>
        ${met ? `<h3>训练过程（逐迭代，指标集：train / validation）</h3>${curve}<h3>留出期指标</h3><div class="grid g4">${[["Brier", met.holdout.brier], ["命中率", (met.holdout.hit_rate * 100).toFixed(0) + "%"], ["覆盖率", (met.holdout.coverage * 100).toFixed(0) + "%"], ["有效独立交易日", met.holdout.n_effective_days]].map(([l, v]) => `<div class="card tile"><div class="v num">${v}</div><div class="l">${l}</div></div>`).join("")}</div>` : sel.status !== "failed" ? (sel.status === "completed" ? '<p class="muted">演示任务：阶段已全部完成（模拟运行不生成指标曲线）。</p>' : '<p class="muted">尚无指标（任务未完成）。</p>') : ""}
      </div>`;
  }
  function adminDatasets() {
    const A = M.datasets.find((d) => d.dataset_version_id === S.dsA), B = M.datasets.find((d) => d.dataset_version_id === S.dsB);
    const opt = (cur) => M.datasets.map((d) => `<option ${d.dataset_version_id === cur ? "selected" : ""}>${d.dataset_version_id}</option>`).join("");
    const rows = [["n_rows", "样本总数"], ["n_trading_days", "交易日"], ["n_event_clusters", "独立事件簇"]].map(([k, l]) => `<tr><td>${l} <code class="small">${k}</code></td><td class="num">${A[k].toLocaleString()}</td><td class="num">${B[k].toLocaleString()}</td><td class="num">${sgn(B[k] - A[k], 0)}</td></tr>`).join("") +
      Object.keys(B.exclusions).map((k) => `<tr><td>排除：<code class="small">${k}</code></td><td class="num">${A.exclusions[k].toLocaleString()}</td><td class="num">${B.exclusions[k].toLocaleString()}</td><td class="num">${sgn(B.exclusions[k] - A.exclusions[k], 0)}</td></tr>`).join("");
    const cw = M.coverageWeekly, xs = cw.map((_, i) => i);
    const chart = lineChart({ xs, xDomain: [0, xs.length - 1], xTicks: [0, 5, 10, 15, 19], xFmt: (i) => cw[i].week, yFmt: (y) => (y * 100).toFixed(1) + "%",
      series: [{ name: "有效结算率（有效结算 / 合格机会）", color: "var(--series-1)", values: cw.map((w) => +(w.settled / w.eligible).toFixed(4)) }], legendAlways: true, height: 200, aria: "数据覆盖随时间",
      table: `<table><tr><th>周</th><th>有效结算</th><th>合格机会</th><th>缺失率</th></tr>${cw.map((w) => `<tr><td>${w.week}</td><td class="num">${w.settled}</td><td class="num">${w.eligible}</td><td class="num">${(w.missing_rate * 100).toFixed(1)}%</td></tr>`).join("")}</table>` });
    return `<div class="card"><h2>数据快照对比</h2><div class="row small"><label>A <select data-act="dsA">${opt(S.dsA)}</select></label><label>B <select data-act="dsB">${opt(S.dsB)}</select></label></div>
      <div class="tablewrap" style="margin-top:8px"><table><tr><th>项</th><th>A</th><th>B</th><th>变化</th></tr>${rows}</table></div>
      ${B.diff && A !== B ? `<h3>样本变化（B 相对 A）</h3><div class="grid g4">${[["新增", B.diff.added], ["删除", B.diff.removed], ["更正", B.diff.corrected], ["新过滤", B.diff.filtered]].map(([l, v]) => `<div class="card tile"><div class="v num">${v.toLocaleString()}</div><div class="l">${l}</div></div>`).join("")}</div><h3>更正示例</h3><ul class="list small">${B.diff.corrected_examples.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><p class="small muted">旧模型可用旧版快照 <code>${A.dataset_version_id}</code> 复现。</p>` : '<p class="muted small">选择两个不同快照以查看差异。</p>'}
      <dl class="kv small" style="margin-top:8px"><dt>时间范围（B）</dt><dd>${B.time_range.start} → ${B.time_range.end}</dd><dt>可用时间校验</dt><dd>${B.availability_check_passed ? badge(RUN_ST, "completed", "通过") : "失败"}</dd><dt>类别比例</dt><dd>${Object.entries(B.class_balance).map(([k, v]) => CLASS_LABEL[k] + " " + (v * 100).toFixed(0) + "%").join(" / ")}</dd></dl></div>
      <div class="card" style="margin-top:14px"><h2>数据随时间变化</h2>${chart}</div>`;
  }
  function adminParams() {
    const maxAbs = Math.max.apply(null, M.features.map((f) => Math.max(Math.abs(f.live || 0), Math.abs(f.candidate || 0))));
    const bar = (v) => (v == null ? '<span class="muted">—（不含）</span>' : `<span class="bar-diff ${v < 0 ? "neg" : ""}" style="width:${(Math.abs(v) / maxAbs) * 80}px"></span> <span class="num">${v.toFixed(3)}</span>`);
    const offs = M.companyOffsets.filter((o) => S.adminSec === "ALL" || o.security === S.adminSec);
    return `<div class="card"><div class="row"><h2 style="margin:0">模型参数对比</h2><span class="spacer"></span>
      <label class="small">证券 <select data-act="adminSec">${["ALL"].concat(M.tickers).map((t) => `<option ${t === S.adminSec ? "selected" : ""}>${t}</option>`).join("")}</select></label>
      <label class="small">对照 <select data-act="adminModel"><option value="candidate" ${S.adminModel === "candidate" ? "selected" : ""}>线上 v3 vs 候选 event_v1</option><option value="company" ${S.adminModel === "company" ? "selected" : ""}>线上 v3 vs 公司参数 company_v1</option></select></label></div>
      <p class="small muted">系数仅在特征定义与缩放一致时可直接比较（标准化特征，fs-0.2）。正值 = 提高"跑赢"类对数几率。</p>
      <div class="tablewrap"><table><tr><th>特征</th><th>线上 market_logit_v3</th><th>${S.adminModel === "candidate" ? "候选 market_event_logit_v1" : "company_v1"}</th><th>差</th></tr>
      ${M.features.map((f) => { const c = S.adminModel === "candidate" ? f.candidate : f.live == null ? null : +(f.live * 1.02).toFixed(3); return `<tr><td><code>${f.name}</code></td><td>${bar(f.live)}</td><td>${bar(c)}</td><td class="num">${f.live != null && c != null ? sgn(c - f.live, 3) : "新增"}</td></tr>`; }).join("")}</table></div></div>
      <div class="card" style="margin-top:14px"><h2>行业与公司偏移 <span class="muted small">正则化收缩向行业/市场</span></h2>
      <table><tr><th>证券</th><th>有效交易日</th><th>线上偏移</th><th>候选偏移</th><th>留出期 ΔBrier（候选−线上，负为改善）</th></tr>${offs.map((o) => `<tr><td>${o.security}</td><td class="num">${o.n_effective_days}</td><td class="num">${o.live.toFixed(3)}</td><td class="num">${o.candidate.toFixed(3)}</td><td class="num ${o.holdout_delta_brier < 0 ? "up" : "down"}">${sgn(o.holdout_delta_brier, 3)}</td></tr>`).join("")}</table>
      <h3>三层消融（同一共同覆盖集合，留出期 Brier，虚构）</h3><table><tr><th>参数层</th><th>Brier</th><th>相对市场共用</th><th>结论</th></tr>
      <tr><td>market</td><td class="num">0.648</td><td>—</td><td>线上</td></tr><tr><td>market + sector</td><td class="num">0.645</td><td class="num">−0.003</td><td>不确定区间跨 0</td></tr><tr><td>market + sector + company</td><td class="num">0.652</td><td class="num">+0.004</td><td>${badge(RUN_ST, "failed", "留出期退化")}</td></tr></table></div>`;
  }
  function adminFva() {
    const rows = M.fvaBySlot.map((r) => `<tr class="${r.flag && r.slot === "s1000" ? "sel" : ""}"><td>${SLOT_LABEL[r.slot]}</td><td class="num">${r.n}</td><td class="num">${Math.round(r.hit_rate * 100)}%</td><td class="num">${r.brier.toFixed(3)}</td><td class="num">${sgn(r.bss, 3, "")}</td><td class="num">${Math.round(r.coverage_p80 * 100)}%</td><td class="num">${r.width_p80.toFixed(2)}pp</td><td class="num">${sgn(r.mean_residual, 2, "pp")}</td><td class="small">${r.flag ? esc(r.flag) : '<span class="muted">—</span>'}</td></tr>`).join("");
    const calib = (slot) => `<table class="small"><tr><th>预测概率</th><th>n</th><th>实际发生率</th><th></th></tr>${M.fvaCalib[slot].map(([a, b, n, o]) => { const mid = (a + b) / 2, gap = o - mid; return `<tr><td>${Math.round(a * 100)}–${Math.round(b * 100)}%</td><td class="num">${n}</td><td class="num">${Math.round(o * 100)}%</td><td><div class="track" style="width:120px;position:relative;height:8px;background:var(--surface-2);border-radius:4px"><div style="position:absolute;left:${mid * 200}px;top:-2px;width:2px;height:12px;background:var(--text-2)"></div><div style="position:absolute;left:${o * 200}px;top:0;width:8px;height:8px;border-radius:50%;background:${Math.abs(gap) > 0.05 ? "var(--critical)" : "var(--series-1)"}"></div></div></td></tr>`; }).join("")}</table>`;
    return `<div class="card"><h2>按槽位的预测与实际（四家合计，近 60 个交易日）</h2>
      <div class="tablewrap"><table><tr><th>槽位</th><th>n</th><th>命中率</th><th>Brier</th><th>BSS</th><th>80% 覆盖</th><th>区间宽度</th><th>平均残差</th><th>发现</th></tr>${rows}</table></div>
      <p class="small muted">"平均残差" = 实际相对收益 − 预测中位数；正值表示系统性低估。示例指标为虚构。</p></div>
      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h2>校准：10:00 槽位</h2>${calib("s1000")}<p class="small muted">竖线 = 预测概率，圆点 = 实际发生率。10:00 的高概率分箱实际偏低 → 概率过于自信。</p></div>
        <div class="card"><h2>校准：14:30 槽位</h2>${calib("s1430")}<p class="small muted">基本贴合对角线。</p></div>
      </div>
      <div class="grid g2" style="margin-top:14px">
        <div class="card"><h2>漂移检查</h2><dl class="kv"><dt>近 20 日 Brier（四家）</dt><dd class="num">0.653 vs 参照 0.662</dd><dt>配对差 95% CI</dt><dd class="num">[−0.021, +0.004]（含 0）</dd><dt>状态</dt><dd><span class="badge good">无漂移</span></dd><dt>10:00 槽位覆盖率</dt><dd><span class="badge warn">71% &lt; 80% − 5pp → 已开训练复盘</span></dd></dl></div>
        <div class="card"><h2>大误差复盘队列 <span class="muted small">结算落在 p10–p90 外</span></h2><table class="small"><tr><th>预测</th><th>残差</th><th>原因</th><th>处理</th></tr>${M.fvaReview.map((r) => `<tr><td><code>${r.prediction_id}</code></td><td class="num">${sgn(r.residual_pp, 1, "pp")}</td><td>${esc(r.cause)}</td><td>${esc(r.action)}</td></tr>`).join("")}</table></div>
      </div>
      <div class="card" style="margin-top:14px"><h2>这些对照如何改进模型（MP §7.1）</h2>
        <ol class="list small"><li><b>结算即标签</b>：每条结算后的槽位预测进入下一版训练数据集（每周一检查，D-22）。</li>
        <li><b>残差分析</b>：按槽位、行情状态、事件类型、公司找系统性偏差 → 新特征或新模型候选（例：10:00 偏差 → 加开盘区间与隔夜跳空特征）。</li>
        <li><b>校准与区间</b>：概率分箱与覆盖率偏离 → 新 <code>calibration_version</code> 或调整 σ̂ / 分位数模型。</li>
        <li><b>漂移触发</b>：近 20 日恶化且 CI 不含 0 → <code>drift</code> 告警 → 训练复盘。</li>
        <li><b>大误差复盘</b>：区分数据问题（可修）与真正意外（只记录）。</li>
        <li><b>上线门槛</b>：任何改动都是新版本 → 影子 ≥ 20 个交易日 → 同口径对照 → 审批。</li></ol>
        <div class="notice">不会因为单次结果自动调参，也不会修改已发布的预测与结算。<button class="btn sm" style="margin-left:8px" data-act="fvaReview">开训练复盘（演示）</button></div></div>`;
  }
  function adminValidation() {
    const E = M.evaluation, m = E.metrics;
    const cal = E.calibration, xs = cal.map((c) => c.bin);
    const calChart = lineChart({ xs, xDomain: [0.28, 0.52], xTicks: xs, xFmt: (x) => "预测 " + Math.round(x * 100) + "%", yFmt: (y) => Math.round(y * 100) + "%", yDomain: [0.25, 0.56],
      series: [{ name: "线上 v3 实测频率", color: "var(--series-1)", values: cal.map((c) => c.live) }, { name: "候选 event_v1 实测频率", color: "var(--series-2)", values: cal.map((c) => c.candidate) }, { name: "完美校准", color: "var(--text-2)", values: xs, dash: true }],
      width: 520, height: 260, aria: "校准图", table: `<table><tr><th>预测概率</th><th>线上</th><th>候选</th><th>n</th></tr>${cal.map((c) => `<tr><td>${Math.round(c.bin * 100)}%</td><td>${Math.round(c.live * 100)}%</td><td>${Math.round(c.candidate * 100)}%</td><td>${c.n}</td></tr>`).join("")}</table>` });
    const cm = (mat, title) => { const mx = Math.max.apply(null, mat.flat()); return `<div><h3>${title}</h3><table class="cm"><tr><td></td>${E.confusion.labels.map((l) => `<td class="small muted">预测<br>${CLASS_LABEL[l]}</td>`).join("")}</tr>${mat.map((row, i) => `<tr><td class="small muted">实际 ${CLASS_LABEL[E.confusion.labels[i]]}</td>${row.map((v) => `<td title="${v}" style="background:rgba(37,125,224,${(0.1 + 0.6 * v / mx).toFixed(2)})">${v}</td>`).join("")}</tr>`).join("")}</table></div>`; };
    return `<div class="card"><h2>验证总览 · <code>${E.evaluation_id}</code></h2>
      <div class="notice">虚构判例（对应 S3§8.4）：200 个合格时点，线上发布 180 条、候选只发布 100 条。候选全量命中 ${Math.round(E.full_coverage_hit_rate.candidate * 100)}% 与线上全量 ${Math.round(E.full_coverage_hit_rate.comparator * 100)}% <b>不能直接比较</b>，以下指标均在共同覆盖的 ${E.common_coverage.n_common} 条上计算。</div>
      <div class="grid g4">${[["合格机会", E.common_coverage.n_eligible], ["共同覆盖", E.common_coverage.n_common], ["有效独立交易日", E.n_independent_days], ["独立事件簇", E.n_event_clusters]].map(([l, v]) => `<div class="card tile"><div class="v num">${v}</div><div class="l">${l}</div></div>`).join("")}</div>
      <div class="tablewrap" style="margin-top:10px"><table><tr><th>指标</th><th>候选</th><th>线上</th><th>配对差</th><th>95% CI（按交易日 bootstrap）</th></tr>
      <tr><td>命中率</td><td class="num">${(m.hit_rate.candidate * 100).toFixed(0)}%</td><td class="num">${(m.hit_rate.comparator * 100).toFixed(0)}%</td><td class="num">${sgn(m.hit_rate.paired_diff * 100, 1, "pp")}</td><td class="num">[${m.hit_rate.ci95.map((x) => (x * 100).toFixed(0) + "pp").join(", ")}]</td></tr>
      <tr><td>Brier（越低越好）</td><td class="num">${m.brier.candidate}</td><td class="num">${m.brier.comparator}</td><td class="num">${sgn(m.brier.paired_diff, 3)}</td><td class="num">[${m.brier.ci95.join(", ")}]</td></tr>
      <tr><td>覆盖率</td><td class="num">${m.coverage.candidate * 100}%</td><td class="num">${m.coverage.comparator * 100}%</td><td class="num">${sgn((m.coverage.candidate - m.coverage.comparator) * 100, 0, "pp")}</td><td>—</td></tr></table></div></div>
      <div class="grid g2" style="margin-top:14px"><div class="card"><h2>概率校准</h2>${calChart}</div><div class="card"><h2>混淆矩阵（共同覆盖集）</h2><div class="row" style="align-items:flex-start;gap:20px">${cm(E.confusion.candidate, "候选")}${cm(E.confusion.comparator, "线上")}</div></div></div>
      <div class="card" style="margin-top:14px"><h2>分组拆解</h2><table><tr><th>分组</th><th>n</th><th>线上 Brier</th><th>候选 Brier</th><th>差</th></tr>${E.groups.map((g) => `<tr><td>${g.group}</td><td class="num">${g.n}</td><td class="num">${g.brier_live}</td><td class="num">${g.brier_cand}</td><td class="num ${g.brier_cand < g.brier_live ? "up" : "down"}">${sgn(+(g.brier_cand - g.brier_live).toFixed(3), 3)}</td></tr>`).join("")}</table><p class="small muted">小样本分组（如财报窗口 n=6）只作观察，不单独作为审批依据。</p></div>`;
  }
  function adminShadow() {
    const d = M.shadowDaily, xs = d.map((_, i) => i);
    const chart = lineChart({ xs, xDomain: [0, xs.length - 1], xTicks: [0, 4, 8, 12, 16], xFmt: (i) => d[i].day, yFmt: (y) => y.toFixed(3),
      series: [{ name: "线上 v3 日均 Brier", color: "var(--series-1)", values: d.map((x) => x.live_brier) }, { name: "候选 event_v1 日均 Brier（影子）", color: "var(--series-2)", values: d.map((x) => x.candidate_brier) }],
      height: 240, aria: "影子测试", table: `<table><tr><th>日期</th><th>线上</th><th>候选</th><th>n</th></tr>${d.map((x) => `<tr><td>${x.day}</td><td>${x.live_brier}</td><td>${x.candidate_brier}</td><td>${x.n}</td></tr>`).join("")}</table>` });
    return `<div class="card"><h2>实时影子测试 · regular_60m</h2><p class="small muted">候选与线上在同一时点、同一窗口并行；发布前锁定，窗口结束后才评分。影子结果仅内部可见。</p>${chart}
      <div class="grid g4" style="margin-top:10px">${[["影子交易日", d.length], ["目标门槛", "≥ 20 日"], ["共同样本", d.reduce((a, x) => a + x.n, 0).toLocaleString()], ["状态", "进行中"]].map(([l, v]) => `<div class="card tile"><div class="v num">${v}</div><div class="l">${l}</div></div>`).join("")}</div></div>`;
  }
  function adminApprovals() {
    const E = M.evaluation;
    const conds = [
      ["留出期独立交易日 ≥ 60", E.n_independent_days >= 60, E.n_independent_days + " 日"],
      ["影子测试 ≥ 20 个交易日", M.shadowDaily.length >= 20, M.shadowDaily.length + " 日"],
      ["Brier 配对改善 CI 上界 < 0", E.metrics.brier.ci95[1] < 0, "上界 " + E.metrics.brier.ci95[1]],
      ["覆盖率下降 ≤ 10pp", (E.metrics.coverage.comparator - E.metrics.coverage.candidate) <= 0.1, sgn((E.metrics.coverage.candidate - E.metrics.coverage.comparator) * 100, 0, "pp")],
      ["关键分组 Brier 退化 ≤ 0.005", true, "最大 +0.000"]
    ];
    const pass = conds.every((c) => c[1]);
    return `<div class="card"><h2>发布审批 · 候选 <code>${E.candidate_model_version_id}</code></h2><p class="small muted">门槛 <code>${E.gate_config_version}</code>（D-21，测试结束前锁定）</p>
      <table><tr><th>条件</th><th>结果</th><th>实测</th></tr>${conds.map((c) => `<tr><td>${c[0]}</td><td>${c[1] ? '<span class="badge good">✓ 达标</span>' : '<span class="badge crit">✕ 未达标</span>'}</td><td class="num">${esc(c[2])}</td></tr>`).join("")}</table>
      <div class="row" style="margin-top:10px"><button class="btn" data-act="approve" ${pass ? "" : "disabled"}>批准上线</button><button class="btn ghost" data-act="reject">驳回</button><button class="btn ghost" data-act="rollback">回滚演练（线上 v3 → v2）</button>
      <span class="small muted">${pass ? "" : "未达标条件存在，批准按钮不可用；线上继续使用当前已验证版本。"}</span></div></div>
      <div class="card" style="margin-top:14px"><h2>审批与部署历史 <span class="muted small">model_deployments</span></h2><table><tr><th>时间</th><th>动作</th><th>版本</th><th>原版本</th><th>审批人</th><th>范围</th><th>门槛</th><th>说明</th></tr>
      ${S.approvals.slice().sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).map((a) => `<tr><td>${fmtET(a.at)}</td><td>${{ approve: '<span class="badge good">批准</span>', reject: '<span class="badge serious">驳回</span>', rollback: '<span class="badge warn">回滚</span>' }[a.action]}</td><td><code class="small">${a.model_version_id}</code></td><td><code class="small">${a.from || "—"}</code></td><td>${a.by}</td><td>${esc(a.scope)}</td><td>${a.gate}</td><td>${esc(a.note)}</td></tr>`).join("")}</table>
      <p class="small muted">已发出的预测和结算继续关联各自的 model_version_id。</p></div>`;
  }

  const ops = window.OPS({ esc, badge, withState, tickers: M.tickers, render: () => render() });

  // ======================= ROUTER =======================
  function parse() {
    const h = location.hash.replace(/^#\/?/, "") || "monitor";
    const [path, qs] = h.split("?");
    const parts = path.split("/");
    const q = {};
    (qs || "").split("&").forEach((kv) => { if (kv) { const [k, v] = kv.split("="); q[k] = decodeURIComponent(v || ""); } });
    return { parts, q };
  }
  function render() {
    const { parts, q } = parse();
    const page = parts[0];
    const tk = M.tickers.includes(parts[1]) ? parts[1] : "NVDA";
    let html;
    if (page === "stock") html = pageStock(tk, parts[2], q);
    else if (page === "forecast") html = pageForecast(tk, TARGET_LABEL[parts[2]] ? parts[2] : "regular_60m");
    else if (page === "events") html = pageEvents(tk, q);
    else if (page === "replay") html = pageReplay(parts[1], q);
    else if (page === "admin") html = pageAdmin(parts[1]);
    else if (page === "ops") html = ops.render(parts, q);
    else html = pageMonitor();
    tip.style.display = "none";
    view.innerHTML = html;
    document.querySelectorAll("#mainnav a").forEach((a) => {
      a.classList.toggle("active", a.dataset.nav === (page || "monitor"));
      if (["stock", "forecast", "events"].includes(a.dataset.nav) && ["stock", "forecast", "events", "monitor"].includes(page)) {
        a.setAttribute("href", "#/" + a.dataset.nav + "/" + tk + (a.dataset.nav === "forecast" ? "/" + (parts[2] && page === "forecast" ? parts[2] : "regular_60m") : ""));
      }
    });
    $("#clockbar").innerHTML = `<span>演示时钟：<b>${esc(clock().label)}</b></span><span>存储 UTC：<code>${clock().now}</code></span><span>交易日历：<code>cal-2026.11</code></span><span>schema_version：<code>${M.SCHEMA_VERSION}</code></span>`;
    bindCharts();
    if (q.item) { const el = document.getElementById(q.item); if (el) el.scrollIntoView({ block: "center" }); }
  }

  // ---------- events ----------
  view.addEventListener("click", (e) => {
    const go = e.target.closest("[data-go]");
    if (go && !e.target.closest("a")) { location.hash = go.dataset.go; return; }
    if (ops.onClick(e, view)) return;
    const run = e.target.closest("tr[data-run]");
    if (run) { S.selRun = run.dataset.run; render(); return; }
    const b = e.target.closest("[data-act]");
    if (!b || b.tagName === "SELECT") return;
    const act = b.dataset.act;
    if (act === "retry") { $("#stateSel").value = "normal"; S.demo = "normal"; render(); }
    if (act === "refresh") {
      const tk = b.dataset.tk; S.refreshing[tk] = true; render();
      setTimeout(() => { S.refreshing[tk] = false; render(); }, 1500);
    }
    if (act === "addToggle") { S.addOpen[b.dataset.tk] = !S.addOpen[b.dataset.tk]; render(); return; }
    if (act === "addSubmit") { submitInfo(b.dataset.tk); return; }
    if (act === "suppGo") { const tk = b.dataset.tk; runSupplement(tk, (S.subs[tk] || []).find((x) => x.submission_id === b.dataset.sub)); return; }
    if (act === "colDisp") { S.colf.disposition = b.dataset.v; render(); return; }
    if (act === "colReset") { S.colf = { channel: "", category: "", disposition: "", q: "" }; render(); return; }
    if (act === "fvaReview") { b.disabled = true; b.textContent = "已创建训练复盘：review_s1000_calibration（演示，候选需经影子与审批）"; return; }
    if (act === "step") location.hash = "#/replay/" + b.dataset.pid + "?step=" + b.dataset.step;
    if (act === "play") {
      clearInterval(replayTimer); let s = 1; location.hash = "#/replay/" + b.dataset.pid + "?step=1";
      replayTimer = setInterval(() => { s++; location.hash = "#/replay/" + b.dataset.pid + "?step=" + s; if (s >= 5) clearInterval(replayTimer); }, 900);
    }
    if (act === "simrun") {
      S.selRun = "tr_sim_new"; let i = 0;
      const now = Date.parse("2026-12-07T15:00:00Z");
      S.simRun = { status: "queued", stage: "queued", started_at: new Date(now).toISOString(), finished_at: null };
      render();
      const tickF = () => {
        i++;
        const st = M.STAGES[i];
        S.simRun = { status: st, stage: st === "completed" ? "evaluating" : st, started_at: new Date(now).toISOString(), finished_at: st === "completed" ? new Date(now + 41 * 60000).toISOString() : null };
        if (location.hash.startsWith("#/admin/runs") || location.hash === "#/admin") render();
        if (st !== "completed") setTimeout(tickF, 1000);
      };
      setTimeout(tickF, 1000);
    }
    if (act === "approve" || act === "reject" || act === "rollback") {
      const E = M.evaluation;
      S.approvals.push(act === "rollback"
        ? { at: "2026-12-08T15:00:00Z", action: "rollback", model_version_id: "mdl_regular_60m_market_logit_v2", from: "mdl_regular_60m_market_logit_v3", by: "you (demo)", scope: "regular_60m", gate: "—", note: "回滚演练（模拟）" }
        : { at: "2026-12-08T15:00:00Z", action: act, model_version_id: E.candidate_model_version_id, from: null, by: "you (demo)", scope: "regular_60m · NVDA/AMD/AVGO/MU", gate: E.gate_result, note: act === "reject" ? "未达门槛：" + E.failed_conditions.join(", ") : "批准（模拟）" });
      render();
    }
  });
  view.addEventListener("change", (e) => {
    const a = e.target.dataset.act;
    if (a === "pick") location.hash = "#/replay/" + e.target.value;
    if (a === "dsA") { S.dsA = e.target.value; render(); }
    if (a === "dsB") { S.dsB = e.target.value; render(); }
    if (a === "adminSec") { S.adminSec = e.target.value; render(); }
    if (a === "adminModel") { S.adminModel = e.target.value; render(); }
    if (a === "colf") { S.colf[e.target.dataset.k] = e.target.value; render(); }
    if (a === "addKind") { S.addForm.kind = e.target.value; render(); }
    if (a === "addScen") { S.addForm.scenario = e.target.value; }
    if (a === "addCat") { const v = e.target.value; S.addForm.cats = e.target.checked ? S.addForm.cats.concat(v) : S.addForm.cats.filter((x) => x !== v); }
  });
  view.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.dataset && e.target.dataset.go) location.hash = e.target.dataset.go; });
  $("#stateSel").addEventListener("change", (e) => { S.demo = e.target.value; render(); });
  $("#clockSel").addEventListener("change", (e) => { S.clock = e.target.value; render(); });
  $("#themeBtn").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
  });
  window.addEventListener("hashchange", render);
  render();
})();
