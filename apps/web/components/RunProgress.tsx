"use client";

import { useCallback, useEffect, useState } from "react";

import type { RunDetail } from "@/lib/data/types";
import { STEP_LABELS } from "@/lib/data/types";
import { etDateTime, label, STATUS_LABEL } from "@/lib/format";

const ACTIVE = new Set(["queued", "running"]);

/** Step progress of one pipeline run: polls the API while active; with Supabase it also refetches on Realtime
 *  changes of pipeline_runs / pipeline_run_steps (migration 0007 adds them to the publication). */
export function RunProgress({
  initial,
  realtime,
}: {
  initial: RunDetail;
  realtime: { url: string; key: string } | null;
}) {
  const [d, setD] = useState<RunDetail>(initial);
  const [err, setErr] = useState<string | null>(null);
  const id = initial.run.pipeline_run_id;
  const active = ACTIVE.has(d.run.status);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/pipeline-runs/${id}`, { cache: "no-store" });
      if (r.ok) {
        setD(await r.json());
        setErr(null);
      } else setErr("进度读取失败，稍后自动重试");
    } catch {
      setErr("进度读取失败，稍后自动重试");
    }
  }, [id]);

  useEffect(() => {
    if (!active) return;
    const t = setInterval(load, 1000);
    return () => clearInterval(t);
  }, [active, load]);

  useEffect(() => {
    if (!realtime) return;
    let cleanup = () => {};
    void (async () => {
      const { createBrowserClient } = await import("@supabase/ssr");
      const sb = createBrowserClient(realtime.url, realtime.key);
      const ch = sb
        .channel(`run-${id}`)
        .on("postgres_changes", { event: "*", schema: "public", table: "pipeline_run_steps", filter: `pipeline_run_id=eq.${id}` }, () => void load())
        .on("postgres_changes", { event: "*", schema: "public", table: "pipeline_runs", filter: `pipeline_run_id=eq.${id}` }, () => void load())
        .subscribe();
      cleanup = () => void sb.removeChannel(ch);
    })();
    return () => cleanup();
  }, [realtime, id, load]);

  async function cancel() {
    const r = await fetch(`/api/pipeline-runs/${id}/cancel`, { method: "POST" });
    if (!r.ok) setErr("取消失败");
    await load();
  }

  const done = d.steps.filter((s) => s.status === "succeeded" || s.status === "skipped").length;
  const outputs = (d.run.outputs ?? {}) as { reused?: boolean; prediction_ids?: string[]; abstained?: unknown[] };
  return (
    <section data-testid="run-progress" data-status={d.run.status}>
      <p>
        状态：<strong data-testid="run-status">{label(STATUS_LABEL, d.run.status)}</strong> · 模式 {d.run.mode} ·{" "}
        as_of {etDateTime(d.run.as_of)} · 步骤 {done}/{d.steps.length || 8}
        {active && (
          <button type="button" className="small danger" onClick={cancel} data-testid="cancel-button">
            取消
          </button>
        )}
      </p>
      <progress max={d.steps.length || 8} value={done} aria-label="运行进度" />
      {err && <p className="error">{err}</p>}
      <ol className="steps">
        {(d.steps.length ? d.steps : []).map((s) => (
          <li key={s.step_no} className={`step ${s.status}`} data-testid={`step-${s.step_no}`} data-status={s.status}>
            <span>{label(STEP_LABELS, s.step)}</span> <small>{s.security_id}</small>{" "}
            <span className="badge">{label(STATUS_LABEL, s.status)}</span>
            {s.attempt > 1 && <small> · 第 {s.attempt} 次</small>}
          </li>
        ))}
      </ol>
      {!active && (
        <p data-testid="run-outputs">
          {d.run.status === "cancelled"
            ? "已取消：之后的步骤没有执行，已发布的部分保持不变。"
            : outputs.reused
              ? "输入没有变化：复用已有预测，没有发布新预测。"
              : `发布预测 ${outputs.prediction_ids?.length ?? 0} 条；弃预测 ${outputs.abstained?.length ?? 0} 条。`}
        </p>
      )}
    </section>
  );
}
