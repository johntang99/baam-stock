import Link from "next/link";
import { notFound } from "next/navigation";

import { attempt, Failed } from "@/components/States";
import { etDateTime } from "@/lib/format";
import { first, pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

interface Stmt {
  text: string;
}

// Event detail (DC §6 GET /api/events/{id}?version=n): per security, the latest (or requested) analysis version.
export default async function EventPage({ params, searchParams }: { params: Promise<{ event_id: string }>; searchParams: SearchParams }) {
  const { event_id } = await params;
  const sp = await searchParams;
  const v = first(sp.version);
  const { db } = await pageContext(Promise.resolve(sp));
  const r = await attempt(() => db.event(event_id, v ? Number(v) : undefined));
  if (!r.ok) return <Failed error={r.error} retry={`/events/${event_id}`} />;
  if (!r.data) notFound();
  const { event: e, links, selected, versions } = r.data;
  return (
    <main>
      <h1>{e.identity_key}</h1>
      <p className="row">
        <span className="badge">{e.category}</span>
        <span className="badge">进展 {e.progress_status}</span>
        <span className="badge">证据 {e.evidence_status}</span>
        <small className="muted">首次发现 {etDateTime(e.first_seen_at)}</small>
      </p>
      <h2>相关证券</h2>
      <ul>
        {links.map((l) => (
          <li key={l.security_id}>
            {l.security_id} · {l.relation}
            {l.exposure_note ? ` · ${l.exposure_note}` : ""}
          </li>
        ))}
      </ul>
      <h2>分析版本</h2>
      <p>
        {[...new Set(versions.map((a) => a.analysis_version))].map((n) => (
          <Link key={n} href={`/events/${event_id}?version=${n}`} style={{ marginRight: "0.6rem" }}>
            v{n}
          </Link>
        ))}
      </p>
      {selected.map((a) => {
        const ex = (a.market_explanation ?? {}) as { status?: string; observed_facts?: Stmt[]; unexplained?: Stmt[] };
        return (
          <article className="card" key={a.analysis_id} style={{ marginBottom: "0.6rem" }}>
            <h3>
              {a.security_id} · v{a.analysis_version} · {a.analysis_kind}
              <small className="muted">{etDateTime(a.published_at ?? null)}</small>
            </h3>
            <p>解释状态：{ex.status ?? "—"}</p>
            <ul>
              {(ex.observed_facts ?? []).map((s, i) => (
                <li key={`f${i}`}>{s.text}</li>
              ))}
              {(ex.unexplained ?? []).map((s, i) => (
                <li key={`u${i}`} className="muted">
                  {s.text}
                </li>
              ))}
            </ul>
          </article>
        );
      })}
    </main>
  );
}
