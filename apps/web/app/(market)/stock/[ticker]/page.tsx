import Link from "next/link";
import { notFound } from "next/navigation";

import { QualityBadge } from "@/components/QualityBadge";
import { RunButton } from "@/components/RunButton";
import { attempt, Empty, Failed } from "@/components/States";
import { CLASS_LABEL, etDateTime, label, pct, pp, STATUS_LABEL, TARGET_LABEL } from "@/lib/format";
import { pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// Stock detail (DP 2.07): snapshot, latest predictions, events; the "运行" button starts a live run (DP 2.08).
export default async function Stock({ params, searchParams }: { params: Promise<{ ticker: string }>; searchParams: SearchParams }) {
  const { ticker } = await params;
  const { db } = await pageContext(searchParams);
  const sr = await attempt(() => db.security(ticker));
  if (!sr.ok) return <Failed error={sr.error} retry={`/stock/${ticker}`} />;
  const s = sr.data;
  if (!s) notFound();
  const [pr, er] = await Promise.all([
    attempt(() => db.predictions({ security_id: s.security_id, limit: 20 })),
    attempt(() => db.events({ security_id: s.security_id })),
  ]);
  const sn = s.snapshot;
  return (
    <main>
      <div className="row">
        <h1>
          {s.ticker} <small className="muted">{s.legal_name}</small>
        </h1>
        <RunButton securityId={s.security_id} />
      </div>
      {sn ? (
        <section className="card">
          <dl className="kv">
            <dt>当日涨跌</dt>
            <dd className="num">{pct(sn.day_return_pct ?? null)}</dd>
            <dt>相对篮子</dt>
            <dd>{pp(sn.day_relative_pp ?? null)}</dd>
            <dt>市场状态</dt>
            <dd>{sn.market_state}</dd>
            <dt>解释</dt>
            <dd>{sn.explanation_summary}</dd>
            <dt>数据</dt>
            <dd>
              <QualityBadge quality={sn.data_quality} lastValidAt={sn.last_valid_at} />
            </dd>
            <dt>快照时点</dt>
            <dd>
              {etDateTime(sn.analysis_as_of)} · 有效至 {etDateTime(sn.valid_until)}
            </dd>
          </dl>
        </section>
      ) : (
        <Empty>暂无快照。</Empty>
      )}
      <h2>最近预测</h2>
      {!pr.ok ? (
        <Failed error={pr.error} retry={`/stock/${ticker}`} />
      ) : pr.data.length === 0 ? (
        <Empty>暂无可显示的预测。</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>目标</th>
                <th>发布</th>
                <th>状态</th>
                <th>判断</th>
              </tr>
            </thead>
            <tbody>
              {pr.data.map((p) => (
                <tr key={p.prediction_id}>
                  <td>
                    <Link href={`/predictions/${p.prediction_id}`}>{label(TARGET_LABEL, p.target_row_id)}</Link>
                  </td>
                  <td>{etDateTime(p.published_at ?? null)}</td>
                  <td>{label(STATUS_LABEL, p.status)}</td>
                  <td>{p.predicted_class ? label(CLASS_LABEL, p.predicted_class) : p.abstain_reason ?? "幅度区间"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h2>相关事件</h2>
      {!er.ok ? (
        <Failed error={er.error} retry={`/stock/${ticker}`} />
      ) : er.data.length === 0 ? (
        <Empty>监测来源范围内暂无相关事件。</Empty>
      ) : (
        <ul>
          {er.data.map((e) => (
            <li key={e.event.event_id}>
              <Link href={`/events/${e.event.event_id}`}>{e.event.identity_key}</Link> <span className="badge">{e.event.progress_status}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
