"use client";

import { useState } from "react";

export function RefreshButton({ securityId }: { securityId: string }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    try {
      const r = await fetch(`/api/securities/${securityId}/refresh`, { method: "POST" });
      const b = await r.json();
      setMsg(r.status === 202 ? "已排队刷新" : r.ok ? "快照仍有效，无需刷新" : (b.error?.message ?? "刷新失败"));
    } catch {
      setMsg("刷新失败");
    } finally {
      setBusy(false);
    }
  }
  return (
    <span>
      <button type="button" onClick={go} disabled={busy} className="small">
        刷新
      </button>
      {msg && <small className="muted"> {msg}</small>}
    </span>
  );
}
