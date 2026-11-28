"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Stock-detail "运行": live run of the 60-minute targets for this security (DC §6 POST /api/pipeline-runs). */
export function RunButton({ securityId }: { securityId: string }) {
  const router = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/api/pipeline-runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          security_ids: [securityId],
          target_ids: ["regular_60m", "regular_60m_move"],
          mode: "live",
          reuse_policy: "reuse_if_unchanged",
        }),
      });
      const b = await r.json();
      if (!r.ok) throw new Error(b.error?.message ?? "运行失败");
      router.push(`/ops/run/${b.pipeline_run_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "运行失败");
      setBusy(false);
    }
  }
  return (
    <span>
      <button type="button" onClick={go} disabled={busy} data-testid="run-button">
        {busy ? "提交中…" : "运行"}
      </button>
      {err && <small className="error"> {err}</small>}
    </span>
  );
}
