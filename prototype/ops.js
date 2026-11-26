/* 运营页面（原型 · MOCK）：一键运行、新公司接入、数据源健康、任务与告警
 * 字段名对应 DATA_CONTRACT.md §3.10（contract-0.7）。全部为模拟数据与模拟流程。 */
(function () {
  "use strict";

  // ---------------- mock data ----------------
  const STEPS = [
    ["collect_evidence", "增量采集证据"], ["verify_dedupe", "核验与去重"], ["analyze_events", "事件分析"], ["build_snapshot", "行情快照"],
    ["readiness_check", "预测交接检查"], ["infer", "模型推断"], ["publish", "原子发布"], ["schedule_settlement", "排程结算"]
  ];
  const SCEN = {
    fresh: { label: "有新证据（正常）", detail: { collect_evidence: "新文档 2 份（SEC 8-K 1、IR 1）", verify_dedupe: "去重 1 份转载；原始来源确认 1", analyze_events: "事件 evt_… 新增分析 v3（flash）", build_snapshot: "snap 水位：证据 11:29:41 / 行情 11:29:59", readiness_check: "stock_reaction=ready（market_baseline）", infer: "regular_60m: 跑赢 33% / 平 31% / 跑输 36%；move p80 0.61pp", publish: "2 条预测已锁定（on_demand）", schedule_settlement: "起算等待首组同步合格报价；结算 12:31 ET" } },
    reuse: { label: "输入无变化（复用）", detail: { collect_evidence: "无新文档", verify_dedupe: "—", analyze_events: "无新事件", build_snapshot: "水位与 11:25 快照相同 → 复用", readiness_check: "沿用", infer: "跳过（复用）", publish: "跳过：返回现有有效预测", schedule_settlement: "跳过" }, skip: ["analyze_events", "infer", "publish", "schedule_settlement"], reused: true },
    retry: { label: "步骤失败后重试", detail: { collect_evidence: "IR 源超时 → 退避 15s 重试成功", verify_dedupe: "去重 0", analyze_events: "无新事件", build_snapshot: "新快照", readiness_check: "ready", infer: "完成", publish: "1 条预测已锁定", schedule_settlement: "已排程" }, failOnce: "collect_evidence" },
    partial: { label: "部分弃预测", detail: { collect_evidence: "新文档 1", verify_dedupe: "去重 0", analyze_events: "分析 v1（flash）", build_snapshot: "篮子缺 2 个成分同步报价", readiness_check: "stock_reaction=missing_inputs", infer: "regular_60m 弃预测（benchmark_unavailable）；move 照常", publish: "1 条已锁定，1 条弃预测", schedule_settlement: "已排程 1 条" }, partial: true }
  };
  const runs = [
    { pipeline_run_id: "pr_20261202_1101_evt", security_ids: ["NVDA", "AMD", "MU"], target_ids: ["regular_60m", "regular_60m_move", "regular_to_close"], trigger_type: "event", requested_by: null, mode: "live", status: "succeeded", reused: false, started: "11:00:41", secs: 24 },
    { pipeline_run_id: "pr_20261202_1125_sched", security_ids: ["NVDA", "AMD", "AVGO", "MU"], target_ids: ["regular_60m", "regular_60m_move"], trigger_type: "scheduled", requested_by: null, mode: "live", status: "partial", reused: false, started: "11:25:00", secs: 31 },
    { pipeline_run_id: "pr_20261202_1127_user", security_ids: ["AVGO"], target_ids: ["regular_60m"], trigger_type: "on_demand", requested_by: "researcher_demo", mode: "live", status: "succeeded", reused: true, started: "11:27:12", secs: 2 },
    { pipeline_run_id: "pr_replay_20261202", security_ids: ["NVDA"], target_ids: ["regular_60m", "regular_60m_move"], trigger_type: "on_demand", requested_by: "researcher_demo", mode: "replay", status: "succeeded", reused: false, started: "10:05:00", secs: 48 }
  ];
  const ONB_STAGES = [
    ["draft", "输入代码"], ["profile_review", "公司档案"], ["sources_configured", "来源与基准"], ["backfilling", "历史回填"],
    ["data_validated", "数据校验"], ["training", "训练"], ["shadow", "影子测试"], ["active", "上线"]
  ];
  function checklist(doneUpto, failItem) {
    const items = [
      ["identifiers", "标识解析（CIK、交易所、代码有效期）", 0], ["profile", "公司档案审核（指标、敞口、监管机构）", 1],
      ["benchmark", "同行篮子版本（剔除自身）", 2], ["sources", "事件来源（SEC / IR / 新闻 / 政策）", 2],
      ["backfill_quotes", "历史行情回填与覆盖率", 3], ["news_time", "新闻时间精度审计（≥ 90% 已知）", 4],
      ["llm_spotcheck", "事件回填 + LLM 提取抽检（D-32）", 4], ["dataset", "训练数据集版本", 5],
      ["model_eval", "市场 + 行业层模型评估", 5], ["shadow_days", "影子 ≥ 20 个交易日", 6], ["approval", "审批", 7]
    ];
    return items.map(([item, label, st]) => ({ item, label, stage: st, status: item === failItem ? "failed" : st < doneUpto ? "done" : "todo" }));
  }
  const onboarding = [
    { onboarding_id: "onb_tsm", ticker: "TSM", name: "Taiwan Semiconductor (ADR)", cik: "0001046179", primary_exchange: "XNYS", target_tier: "batch2", stage: 3, blocked_reason: null, param_policy: "market_sector_only", checklist: checklist(3), backfill_report: { years: 3.0, coverage_pct: 64, qualifying_quote_pct: null, sync_success_pct: null, news_time_known_pct: null }, note: "ADR：台湾公告与美股交易时段传导需单独标注" },
    { onboarding_id: "onb_mrvl", ticker: "MRVL", name: "Marvell Technology", cik: "0001835632", primary_exchange: "XNAS", target_tier: "batch2", stage: 1, blocked_reason: null, param_policy: "market_sector_only", checklist: checklist(1), backfill_report: null, note: "" },
    { onboarding_id: "onb_intc", ticker: "INTC", name: "Intel", cik: "0000050863", primary_exchange: "XNAS", target_tier: "peer_only", stage: 4, blocked_reason: "新闻时间精度已知仅 81%（门槛 90%，D-35）", param_policy: "market_sector_only", checklist: checklist(4, "news_time"), backfill_report: { years: 5, coverage_pct: 99.2, qualifying_quote_pct: 97.8, sync_success_pct: 96.4, news_time_known_pct: 81 }, note: "可先作为训练池同行（peer_only）" },
    { onboarding_id: "onb_qcom", ticker: "QCOM", name: "Qualcomm", cik: "0000804328", primary_exchange: "XNAS", target_tier: "peer_only", stage: 7, blocked_reason: null, param_policy: "market_sector_only", checklist: checklist(8), backfill_report: { years: 5, coverage_pct: 99.5, qualifying_quote_pct: 98.6, sync_success_pct: 97.9, news_time_known_pct: 93 }, note: "已作为篮子成分与训练池" }
  ];
  const sources = [
    { source_id: "src_md_primary", kind: "market_data", provider: "行情供应商（拟选）", status: "healthy", p50: 180, p95: 620, last: "11:29:59", err: 0.0, license_scope: "licensed_internal", verification_status: "sample_verified" },
    { source_id: "src_sec_edgar", kind: "filing", provider: "SEC EDGAR", status: "healthy", p50: 2100, p95: 8400, last: "11:29:40", err: 0.0, license_scope: "public", verification_status: "contracted" },
    { source_id: "src_ir_rss", kind: "company_ir", provider: "公司 IR RSS（4 家）", status: "degraded", p50: 9000, p95: 64000, last: "11:28:10", err: 0.08, license_scope: "public", verification_status: "sample_verified" },
    { source_id: "src_fedreg", kind: "policy", provider: "Federal Register / BIS", status: "healthy", p50: 3500, p95: 12000, last: "11:29:30", err: 0.0, license_scope: "public", verification_status: "sample_verified" },
    { source_id: "src_news_lic", kind: "news", provider: "授权新闻快讯（拟选）", status: "healthy", p50: 900, p95: 2600, last: "11:29:58", err: 0.01, license_scope: "licensed_internal", verification_status: "proposed" },
    { source_id: "src_consensus", kind: "expectation", provider: "共识预期（未采购）", status: "down", p50: null, p95: null, last: "—", err: null, license_scope: "restricted", verification_status: "proposed" },
    { source_id: "src_llm", kind: "llm", provider: "LLM 提供商", status: "healthy", p50: 2400, p95: 7100, last: "11:29:45", err: 0.0, license_scope: "licensed_internal", verification_status: "contracted" }
  ];
  const jobs = { queued: 3, running: 2, retry_wait: 1, failed: 0, dead: 1, succeeded_1h: 412 };
  const jobList = [
    ["job_…a91", "build_snapshot", "running", "AVGO · scheduled", "11:30:00"], ["job_…a92", "run_forecast", "queued", "AVGO · regular_60m", "11:30:00"],
    ["job_…a7f", "ingest_doc", "retry_wait", "src_ir_rss · attempt 2/5 · 退避 30s", "11:29:12"], ["job_…a60", "settle_due", "running", "11 条到期", "11:30:00"],
    ["job_…9c2", "onboarding_step", "queued", "onb_tsm · backfilling 第 2/3 年", "11:20:00"], ["job_…8e0", "pipeline_step", "dead", "pr_…1012 · collect_evidence · 5 次失败", "10:12:44"]
  ];
  const alerts = [
    { alert_id: "al_1", severity: "warning", kind: "source_latency", ref: "src_ir_rss", opened: "11:21", message: "IR RSS p95 延迟 64s > 60s（D-37）", ack: null },
    { alert_id: "al_2", severity: "critical", kind: "source_down", ref: "src_consensus", opened: "09:00", message: "共识预期源未接入：expectation_comparison 将为空（预期内，未采购）", ack: "admin_demo" },
    { alert_id: "al_3", severity: "warning", kind: "onboarding_blocked", ref: "onb_intc", opened: "昨日", message: "INTC 接入受阻：新闻时间精度 81% < 90%", ack: null },
    { alert_id: "al_4", severity: "info", kind: "pipeline_failed", ref: "pr_…1012", opened: "10:12", message: "一次运行 collect_evidence 5 次失败后进入死信；后续运行正常", ack: null }
  ];

  // ---------------- module ----------------
  window.OPS = function (ctx) {
    const { esc, badge, withState, tickers } = ctx;
    const st = { run: null, timer: null, newOnb: 0 };
    const RS = { queued: ["已排队", "neutral"], running: ["运行中", "info"], succeeded: ["成功", "good"], partial: ["部分完成", "warn"], failed: ["失败", "crit"], cancelled: ["已取消", "neutral"], skipped: ["跳过（复用）", "neutral"], retry_wait: ["重试等待", "warn"], pending: ["待执行", "neutral"], dead: ["死信", "crit"] };
    const SH = { healthy: ["正常", "good", "✓"], degraded: ["降级", "warn", "!"], down: ["中断", "crit", "✕"] };
    const SEV = { info: ["信息", "info"], warning: ["警告", "warn"], critical: ["严重", "crit"] };

    function nav(tab) {
      const T = [["run", "一键运行"], ["onboarding", "新公司接入"], ["sources", "数据源健康"], ["jobs", "任务与告警"]];
      return `<nav class="sidenav">${T.map(([k, l]) => `<a href="#/ops/${k}" class="${k === tab ? "active" : ""}">${l}</a>`).join("")}<p class="small muted" style="padding:8px">运营页面（researcher / admin）。全部为模拟流程。</p></nav>`;
    }

    // ---- one-click run ----
    function pageRun(q) {
      const r = st.run;
      const tk = r ? r.tk : tickers.includes(q.tk) ? q.tk : "NVDA";
      const stepRows = r ? r.steps.map((s, i) => `<tr><td>${i + 1}</td><td>${STEPS[i][1]} <code class="small">${STEPS[i][0]}</code></td><td>${badge(RS, s.status)}${s.attempt > 1 ? ` <span class="small muted">attempt ${s.attempt}</span>` : ""}</td><td class="small">${esc(s.detail || "")}</td></tr>`).join("") : "";
      const result = r && r.done ? `<div class="notice ${r.status === "partial" ? "" : "info"}">运行 <code>${r.id}</code> ${badge(RS, r.status)} · 用时 ${r.secs}s${r.reused ? " · 输入无实质变化，已返回现有有效预测（不进主评分的新记录未产生）" : ""}。
        <a href="#/forecast/${r.tk}/regular_60m">查看预测 →</a> · <a href="#/stock/${r.tk}">查看股票详情 →</a></div>` : "";
      return `<div class="card"><h2>一键运行：采集 → 分析 → 预测 <span class="muted small">pipeline_runs</span></h2>
        <div class="row small">
          <label>证券 <select data-ops="tk">${tickers.map((t) => `<option ${t === tk ? "selected" : ""}>${t}</option>`).join("")}</select></label>
          <label>目标 <select data-ops="targets"><option value="a">60 分钟方向 + 预期波动</option><option value="b">+ 到收盘</option></select></label>
          <label>模式 <select data-ops="mode">${[["live", "live 实时"], ["replay", "replay 历史时点"], ["dry_run", "dry_run 不发布"]].map(([v, l]) => `<option value="${v}" ${r && r.mode === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label>复用 <select data-ops="reuse"><option value="reuse_if_unchanged">输入不变则复用（默认）</option><option value="force_recompute">强制重算（researcher+）</option></select></label>
          <label>演示场景 <select data-ops="scen">${Object.entries(SCEN).map(([k, v]) => `<option value="${k}" ${r && r.scenKey === k ? "selected" : ""}>${v.label}</option>`).join("")}</select></label>
          <button class="btn" data-ops="start" ${r && !r.done ? "disabled" : ""}>▶ 运行</button>
          ${r && !r.done ? '<button class="btn ghost" data-ops="cancel">取消</button>' : ""}
        </div>
        <p class="small muted">规则（D-34）：新预测一律从发布后的首组同步合格报价起算；按需运行的预测标 <code>sampling_rule=on_demand</code>，与定时主样本分开计分；1 分钟内重复点击返回同一运行。</p>
        ${r ? `<div class="steps">${r.steps.map((s, i) => `<span class="step ${s.status === "succeeded" ? "done" : s.status === "running" || s.status === "retry_wait" ? "cur" : s.status === "failed" ? "fail" : ""}">${i + 1}. ${STEPS[i][1]}</span>`).join("")}</div>
          <div class="tablewrap"><table><tr><th>#</th><th>步骤</th><th>状态</th><th>详情</th></tr>${stepRows}</table></div>${result}` : '<p class="muted">选择参数后点击"运行"。股票详情页的"运行"按钮会带上该证券跳到这里。</p>'}
      </div>
      <div class="card" style="margin-top:14px"><h2>运行历史（今日）</h2><div class="tablewrap"><table><tr><th>pipeline_run_id</th><th>证券</th><th>目标</th><th>触发</th><th>模式</th><th>状态</th><th>开始 ET</th><th>用时</th></tr>
        ${(st.history || []).concat(runs).map((x) => `<tr><td><code class="small">${x.pipeline_run_id}</code></td><td>${x.security_ids.join(", ")}</td><td class="small">${x.target_ids.join(", ")}</td><td><code>${x.trigger_type}</code>${x.requested_by ? ` <span class="small muted">${x.requested_by}</span>` : ""}</td><td>${x.mode}</td><td>${badge(RS, x.status)}${x.reused ? ' <span class="badge neutral">复用</span>' : ""}</td><td>${x.started}</td><td class="num">${x.secs}s</td></tr>`).join("")}</table></div></div>`;
    }
    function startRun(view) {
      const g = (k) => view.querySelector(`[data-ops="${k}"]`).value;
      const tk = g("tk"), scenKey = g("scen"), mode = g("mode"), sc = SCEN[scenKey];
      const reuse = g("reuse");
      const effective = reuse === "force_recompute" && scenKey === "reuse" ? SCEN.fresh : sc;
      st.run = { id: "pr_demo_" + Date.now().toString(36), tk, scenKey, scen: effective, mode, done: false, status: "running", secs: 0, reused: !!effective.reused,
        steps: STEPS.map(() => ({ status: "pending", attempt: 1, detail: "" })) };
      let i = 0, failed = false;
      const tick = () => {
        const r = st.run; if (!r || r.done) return;
        const key = STEPS[i][0];
        const s = r.steps[i];
        if (s.status === "pending") { s.status = "running"; ctx.render(); st.timer = setTimeout(tick, 450); return; }
        if (r.scen.failOnce === key && !failed) { failed = true; s.status = "retry_wait"; s.attempt = 2; s.detail = "超时，指数退避后重试…"; ctx.render(); st.timer = setTimeout(() => { s.status = "running"; ctx.render(); st.timer = setTimeout(tick, 600); }, 900); return; }
        s.status = (r.scen.skip || []).includes(key) ? "skipped" : "succeeded";
        s.detail = (mode === "dry_run" && key === "publish") ? "dry_run：不写入 predictions，只生成报告" : r.scen.detail[key];
        i++;
        if (i >= STEPS.length) {
          r.done = true; r.status = r.scen.partial ? "partial" : "succeeded"; r.secs = r.scen.reused ? 2 : 18 + Math.round(Math.random() * 10);
          st.history = [{ pipeline_run_id: r.id, security_ids: [tk], target_ids: ["regular_60m", "regular_60m_move"], trigger_type: "on_demand", requested_by: "you (demo)", mode, status: r.status, reused: r.reused, started: "11:30:05", secs: r.secs }].concat(st.history || []);
          ctx.render(); return;
        }
        ctx.render(); st.timer = setTimeout(tick, 350);
      };
      ctx.render(); st.timer = setTimeout(tick, 300);
    }

    // ---- onboarding ----
    function pageOnboarding() {
      return `<div class="card"><div class="row"><h2 style="margin:0">新公司接入 <span class="muted small">onboarding_requests</span></h2><span class="spacer"></span>
        <input data-ops="newTicker" placeholder="输入代码，如 ARM" style="border:1px solid var(--border);border-radius:6px;padding:5px 8px;background:var(--surface);width:150px">
        <select data-ops="newTier"><option value="pilot">pilot（上线预测）</option><option value="batch2" selected>batch2</option><option value="peer_only">peer_only（仅训练池/篮子）</option></select>
        <button class="btn" data-ops="newOnb">新建接入</button></div>
        <p class="small muted">流程：输入代码 → LLM 起草公司档案（带原文定位）并人工审核 → 来源与基准 → 历史回填 → 数据校验 → 训练（先用市场 + 行业参数）→ 影子 ≥ 20 个交易日 → 审批上线（D-35、D-36）。</p>
        <div class="tablewrap"><table><tr><th>代码</th><th>公司</th><th>目标层级</th><th>阶段</th><th>进度</th><th>状态</th></tr>
        ${onboarding.map((o) => `<tr class="clickable" data-go="#/ops/onboarding/${o.onboarding_id}"><td><b>${o.ticker}</b></td><td>${esc(o.name)}</td><td><code>${o.target_tier}</code></td><td>${ONB_STAGES[o.stage][1]} <code class="small">${ONB_STAGES[o.stage][0]}</code></td><td class="small">${o.stage + 1}/8</td><td>${o.blocked_reason ? `<span class="badge crit">✕ blocked</span> <span class="small">${esc(o.blocked_reason)}</span>` : o.stage === 7 ? '<span class="badge good">✓ active</span>' : '<span class="badge info">进行中</span>'}</td></tr>`).join("")}</table></div></div>`;
    }
    function pageOnbDetail(id) {
      const o = onboarding.find((x) => x.onboarding_id === id);
      if (!o) return `<div class="card state"><h2>未找到接入记录</h2><a href="#/ops/onboarding">返回</a></div>`;
      const CS = { done: ["完成", "good", "✓"], todo: ["待办", "neutral", "○"], failed: ["未通过", "crit", "✕"], waived: ["已豁免", "warn", "!"] };
      const br = o.backfill_report;
      const profile = o.stage >= 1 ? `<h3>公司档案草稿（LLM 起草 · 需人工审核）</h3>
        <dl class="kv small"><dt>关键指标</dt><dd><input value="${o.ticker === "TSM" ? "先进制程营收占比、CoWoS 产能、毛利率、月营收" : "数据中心营收、定制芯片营收、毛利率"}" style="width:100%"> <span class="muted">来源：10-K/20-F §业务（原文定位）</span></dd>
        <dt>主要客户/供应商</dt><dd><input value="${o.ticker === "TSM" ? "NVDA、AMD、AVGO、AAPL（客户）" : "云厂商（客户）、TSM（代工）"}" style="width:100%"></dd>
        <dt>主管机构</dt><dd><input value="${o.ticker === "TSM" ? "SEC（ADR 申报）、BIS、台湾主管机关" : "SEC、BIS"}" style="width:100%"></dd>
        <dt>同行篮子</dt><dd><code>bm_semis_peer_ex_${o.ticker.toLowerCase()}</code> v1（12 只剔除自身，等权）</dd></dl>` : "";
      return `<div class="card"><div class="row"><h2 style="margin:0">${o.ticker} · ${esc(o.name)}</h2><span class="spacer"></span><a href="#/ops/onboarding">← 接入列表</a></div>
        <div class="small muted">onboarding_id <code>${o.onboarding_id}</code> · CIK ${o.cik} · ${o.primary_exchange} · param_policy <code>${o.param_policy}</code>${o.note ? " · " + esc(o.note) : ""}</div>
        <div class="steps">${ONB_STAGES.map((s, i) => `<span class="step ${i < o.stage ? "done" : i === o.stage ? (o.blocked_reason ? "fail" : "cur") : ""}">${i + 1}. ${s[1]}</span>`).join("")}</div>
        ${o.blocked_reason ? `<div class="notice crit">阶段受阻：${esc(o.blocked_reason)}。可补数据后重试、降级为 <code>peer_only</code>，或由 admin 豁免（留痕）。</div>` : ""}
        <div class="row"><button class="btn" data-ops="advance" data-id="${o.onboarding_id}" ${o.stage >= 7 || o.blocked_reason || o.busy ? "disabled" : ""}>${o.busy ? "执行中…" : o.stage >= 7 ? "已上线" : "执行并推进到：" + ONB_STAGES[o.stage + 1][1]}</button>
          ${o.blocked_reason ? `<button class="btn ghost" data-ops="waive" data-id="${o.onboarding_id}">admin 豁免并继续</button><button class="btn ghost" data-ops="downgrade" data-id="${o.onboarding_id}">降级为 peer_only</button>` : ""}</div>
        ${profile}
        ${br ? `<h3>回填报告 <span class="muted small">backfill_report</span></h3><div class="grid g4">${[["回填年数", br.years], ["行情覆盖率", br.coverage_pct != null ? br.coverage_pct + "%" : "进行中"], ["合格报价率", br.qualifying_quote_pct != null ? br.qualifying_quote_pct + "%" : "—"], ["新闻时间已知", br.news_time_known_pct != null ? br.news_time_known_pct + "%" : "—"]].map(([l, v]) => `<div class="card tile"><div class="v num">${v}</div><div class="l">${l}</div></div>`).join("")}</div>` : ""}
        <h3>Checklist</h3><table><tr><th>项</th><th>阶段</th><th>状态</th></tr>${o.checklist.map((c) => `<tr><td>${esc(c.label)}</td><td class="small">${ONB_STAGES[c.stage][1]}</td><td>${badge(CS, c.status)}</td></tr>`).join("")}</table>
        <p class="small muted">新公司先用市场 + 行业参数；公司专属偏移只在留出与影子都改善后启用（S3§8.2）。</p></div>`;
    }
    function advance(id) {
      const o = onboarding.find((x) => x.onboarding_id === id); if (!o) return;
      o.busy = true; ctx.render();
      setTimeout(() => {
        o.busy = false;
        const next = o.stage + 1;
        o.checklist.forEach((c) => { if (c.stage <= o.stage && c.status === "todo") c.status = "done"; });
        if (next === 4 && !o.br_done) { o.backfill_report = { years: 3, coverage_pct: 98.7, qualifying_quote_pct: 97.1, sync_success_pct: 95.8, news_time_known_pct: null }; }
        if (next === 5) { o.backfill_report = Object.assign({}, o.backfill_report, { news_time_known_pct: 92 }); }
        o.stage = Math.min(7, next);
        ctx.render();
      }, 1200);
    }

    // ---- sources ----
    function pageSources() {
      const ms = (v) => (v == null ? "—" : v >= 1000 ? (v / 1000).toFixed(1) + "s" : v + "ms");
      return `<div class="card"><div class="row"><h2 style="margin:0">数据源健康 <span class="muted small">data_source_health</span></h2><span class="spacer"></span><button class="btn sm" data-ops="check">立即检查</button></div>
        <p class="small muted">"拟选/未验证"的来源需在 Phase 0 采购验证后改为 sample_verified 或 contracted。延迟告警阈值见 D-37。</p>
        <div class="tablewrap"><table><tr><th>来源</th><th>类型</th><th>状态</th><th>p50</th><th>p95</th><th>最近成功 ET</th><th>1h 错误率</th><th>授权</th><th>验证状态</th></tr>
        ${sources.map((x) => `<tr><td>${esc(x.provider)} <div class="small muted"><code>${x.source_id}</code></div></td><td><code>${x.kind}</code></td><td>${badge(SH, x.status)}</td><td class="num">${ms(x.p50)}</td><td class="num">${ms(x.p95)}</td><td>${x.last}</td><td class="num">${x.err == null ? "—" : (x.err * 100).toFixed(0) + "%"}</td><td><code class="small">${x.license_scope}</code></td><td><code class="small">${x.verification_status}</code></td></tr>`).join("")}</table></div></div>`;
    }
    // ---- jobs & alerts ----
    function pageJobs() {
      return `<div class="grid g4">${[["排队", jobs.queued], ["运行中", jobs.running], ["重试等待", jobs.retry_wait], ["死信", jobs.dead]].map(([l, v]) => `<div class="card tile"><div class="v num">${v}</div><div class="l">${l}</div></div>`).join("")}</div>
        <div class="card" style="margin-top:14px"><h2>告警 <span class="muted small">alerts</span></h2><table><tr><th>级别</th><th>类型</th><th>对象</th><th>开始</th><th>说明</th><th></th></tr>
        ${alerts.map((a) => `<tr><td>${badge(SEV, a.severity)}</td><td><code>${a.kind}</code></td><td><code class="small">${a.ref}</code></td><td>${a.opened}</td><td>${esc(a.message)}</td><td>${a.ack ? `<span class="small muted">已确认 · ${a.ack}</span>` : `<button class="btn sm ghost" data-ops="ack" data-id="${a.alert_id}">确认</button>`}</td></tr>`).join("")}</table></div>
        <div class="card" style="margin-top:14px"><h2>最近任务 <span class="muted small">jobs · 1 小时成功 ${jobs.succeeded_1h}</span></h2><table><tr><th>job_id</th><th>类型</th><th>状态</th><th>说明</th><th>run_after ET</th><th></th></tr>
        ${jobList.map((j) => `<tr><td><code class="small">${j[0]}</code></td><td><code>${j[1]}</code></td><td>${badge(RS, j[2])}</td><td class="small">${esc(j[3])}</td><td>${j[4]}</td><td>${j[2] === "dead" ? `<button class="btn sm ghost" data-ops="requeue" data-id="${j[0]}">重新入队</button>` : ""}</td></tr>`).join("")}</table>
        <p class="small muted">运维手册见 DEVELOPMENT_PHASES 附录 B。</p></div>`;
    }

    function render(parts, q) {
      const tab = parts[1] || "run";
      let body;
      if (tab === "onboarding" && parts[2]) body = () => pageOnbDetail(parts[2]);
      else body = { run: () => pageRun(q), onboarding: pageOnboarding, sources: pageSources, jobs: pageJobs }[tab] || (() => pageRun(q));
      return `<div class="pagehead"><div><h1>运营</h1><div class="muted small">一键运行、新公司接入、数据源与任务监控（模拟流程，不连接真实系统）</div></div></div>
        <div class="admin">${nav(tab)}<div>${withState(body, { empty: "暂无记录。" })}</div></div>`;
    }

    function onClick(e, view) {
      const b = e.target.closest("[data-ops]");
      if (!b || b.tagName === "SELECT" || b.tagName === "INPUT") return false;
      const a = b.dataset.ops;
      if (a === "start") { clearTimeout(st.timer); startRun(view); }
      if (a === "cancel") { clearTimeout(st.timer); if (st.run) { st.run.done = true; st.run.status = "cancelled"; st.run.steps.forEach((s) => { if (s.status === "pending" || s.status === "running") s.status = "cancelled"; }); } ctx.render(); }
      if (a === "advance") advance(b.dataset.id);
      if (a === "waive" || a === "downgrade") {
        const o = onboarding.find((x) => x.onboarding_id === b.dataset.id);
        o.checklist.forEach((c) => { if (c.status === "failed") c.status = "waived"; });
        o.blocked_reason = null;
        if (a === "downgrade") { o.target_tier = "peer_only"; o.note = "已降级为 peer_only：只进训练池与篮子，不发布预测"; }
        else o.note = "admin_demo 豁免 news_time（审计已记录）";
        ctx.render();
      }
      if (a === "newOnb") {
        const inp = view.querySelector('[data-ops="newTicker"]');
        const tk = (inp.value || "").trim().toUpperCase().replace(/[^A-Z.]/g, "").slice(0, 6);
        if (!tk) { inp.focus(); return true; }
        const id = "onb_" + tk.toLowerCase() + (++st.newOnb);
        onboarding.unshift({ onboarding_id: id, ticker: tk, name: tk + "（待解析）", cik: "解析中…", primary_exchange: "—", target_tier: view.querySelector('[data-ops="newTier"]').value, stage: 0, blocked_reason: null, param_policy: "market_sector_only", checklist: checklist(0), backfill_report: null, note: "演示：代码解析为模拟" });
        location.hash = "#/ops/onboarding/" + id;
      }
      if (a === "check") { sources.forEach((x) => { if (x.status === "degraded") { x.status = "healthy"; x.p95 = 11000; x.err = 0.0; x.last = "11:30:04"; } }); ctx.render(); }
      if (a === "ack") { const al = alerts.find((x) => x.alert_id === b.dataset.id); al.ack = "you (demo)"; ctx.render(); }
      if (a === "requeue") { const j = jobList.find((x) => x[0] === b.dataset.id); j[2] = "queued"; j[3] += " · 已重新入队"; jobs.dead = 0; jobs.queued++; ctx.render(); }
      return true;
    }
    return { render, onClick };
  };
})();
