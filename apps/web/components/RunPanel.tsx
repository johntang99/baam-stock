"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { RUN_TARGETS } from "@/lib/data/types";
import { TARGET_LABEL } from "@/lib/format";

/** Operations run panel (DP 2.08): securities, targets, mode. Viewers get live + reuse only (DC §6). */
export function RunPanel({ securities, canReplay }: { securities: { security_id: string; ticker: string }[]; canReplay: boolean }) {
  const router = useRouter();
  const [secs, setSecs] = useState<string[]>(securities.slice(0, 1).map((s) => s.security_id));
  const [tgts, setTgts] = useState<string[]>(["regular_60m", "regular_60m_move"]);
  const [mode, setMode] = useState("live");
  const [asOf, setAsOf] = useState("");
  const [reuse, setReuse] = useState("reuse_if_unchanged");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toggle = (xs: string[], x: string) => (xs.includes(x) ? xs.filter((y) => y !== x) : [...xs, x]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/pipeline-runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          security_ids: secs,
          target_ids: tgts,
          mode,
          reuse_policy: reuse,
          as_of: mode === "live" ? null : asOf ? new Date(asOf).toISOString() : null,
        }),
      });
      const b = await r.json();
      if (!r.ok) throw new Error(b.error?.message ?? "提交失败");
      router.push(`/ops/run/${b.pipeline_run_id}`);
    } catch (x) {
      setErr(x instanceof Error ? x.message : "提交失败");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="panel" data-testid="run-panel">
      <fieldset>
        <legend>证券</legend>
        {securities.map((s) => (
          <label key={s.security_id}>
            <input type="checkbox" checked={secs.includes(s.security_id)} onChange={() => setSecs(toggle(secs, s.security_id))} />{" "}
            {s.ticker}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>目标</legend>
        {RUN_TARGETS.map((t) => (
          <label key={t}>
            <input type="checkbox" checked={tgts.includes(t)} onChange={() => setTgts(toggle(tgts, t))} /> {TARGET_LABEL[t]}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>模式</legend>
        <label>
          <input type="radio" name="mode" checked={mode === "live"} onChange={() => setMode("live")} /> 实时（live）
        </label>
        <label title={canReplay ? "" : "需要研究员角色"}>
          <input type="radio" name="mode" disabled={!canReplay} checked={mode === "replay"} onChange={() => setMode("replay")} /> 回放（replay）
        </label>
        <label title={canReplay ? "" : "需要研究员角色"}>
          <input type="radio" name="mode" disabled={!canReplay} checked={mode === "dry_run"} onChange={() => setMode("dry_run")} /> 试运行（dry_run，不写预测）
        </label>
        {mode !== "live" && (
          <label>
            as_of（本地时间）<input type="datetime-local" value={asOf} onChange={(e) => setAsOf(e.target.value)} required />
          </label>
        )}
        <label title={canReplay ? "" : "需要研究员角色"}>
          <input
            type="checkbox"
            disabled={!canReplay}
            checked={reuse === "force_recompute"}
            onChange={(e) => setReuse(e.target.checked ? "force_recompute" : "reuse_if_unchanged")}
          />{" "}
          强制重算（force_recompute，产生单独的按需预测）
        </label>
      </fieldset>
      {err && <p className="error" role="alert">{err}</p>}
      <button type="submit" disabled={busy || secs.length === 0 || tgts.length === 0} data-testid="run-submit">
        {busy ? "提交中…" : "运行"}
      </button>
    </form>
  );
}
