import { notFound } from "next/navigation";

import { attempt, Failed } from "@/components/States";
import { CLASS_LABEL, etDateTime, label, pp, STATUS_LABEL, TARGET_LABEL } from "@/lib/format";
import { pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// Prediction detail (DC §6 GET /api/predictions/{id}): locked inputs and every settlement version.
export default async function PredictionPage({
  params,
  searchParams,
}: {
  params: Promise<{ prediction_id: string }>;
  searchParams: SearchParams;
}) {
  const { prediction_id } = await params;
  const { db } = await pageContext(searchParams);
  const r = await attempt(() => db.prediction(prediction_id));
  if (!r.ok) return <Failed error={r.error} retry={`/predictions/${prediction_id}`} />;
  if (!r.data) notFound();
  const { prediction: p, settlements } = r.data;
  const probs = (p.probabilities ?? null) as Record<string, number> | null;
  return (
    <main>
      <h1>
        {label(TARGET_LABEL, p.target_row_id)} <small className="muted">{p.prediction_id}</small>
      </h1>
      <section className="card">
        <dl className="kv">
          <dt>证券</dt>
          <dd>{p.security_id}</dd>
          <dt>状态</dt>
          <dd>
            {label(STATUS_LABEL, p.status)}
            {p.abstain_reason ? `（${p.abstain_reason}）` : ""}
          </dd>
          <dt>发布 / 窗口结束</dt>
          <dd>
            {etDateTime(p.published_at ?? null)} → {etDateTime(p.target_end_at ?? null)}
          </dd>
          <dt>抽样</dt>
          <dd>
            {p.sampling_rule} · {p.is_primary ? "主评分" : "非主评分"} · {p.display_tier}
          </dd>
          {probs && (
            <>
              <dt>概率</dt>
              <dd>
                {Object.entries(probs)
                  .map(([k, v]) => `${label(CLASS_LABEL, k)} ${(v * 100).toFixed(0)}%`)
                  .join(" · ")}
              </dd>
            </>
          )}
        </dl>
      </section>
      <h2>锁定输入</h2>
      <pre className="card" style={{ overflowX: "auto" }}>
        {JSON.stringify(p.locked, null, 2)}
      </pre>
      <h2>结算版本</h2>
      {settlements.length === 0 ? (
        <p className="muted">尚未结算。</p>
      ) : (
        <ul>
          {settlements.map((s) => (
            <li key={s.settlement_id}>
              v{s.settlement_version}
              {s.is_reporting_version ? "（报告版）" : ""}：{s.outcome_class ? label(CLASS_LABEL, s.outcome_class) : (s.invalid_reason ?? "—")}，
              相对 {pp(s.relative_return_pp ?? null)} · {etDateTime(s.settled_at)}
              <br />
              <small className="muted">{s.reason_text}</small>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
