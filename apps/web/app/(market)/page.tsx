import Link from "next/link";

import { QualityBadge } from "@/components/QualityBadge";
import { RefreshButton } from "@/components/RefreshButton";
import { attempt, Empty, Failed } from "@/components/States";
import { etTime, pct, pp } from "@/lib/format";
import { pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// Monitoring page (DP 2.07; DC §6 GET /api/securities): one card per covered security, latest snapshot.
export default async function Monitor({ searchParams }: { searchParams: SearchParams }) {
  const { db } = await pageContext(searchParams);
  const r = await attempt(() => db.listSecurities());
  return (
    <main>
      <h1>监控</h1>
      {!r.ok ? (
        <Failed error={r.error} retry="/" />
      ) : r.data.length === 0 ? (
        <Empty>还没有可显示的证券快照。快照在交易时段每 5 分钟生成一次。</Empty>
      ) : (
        <div className="grid" data-testid="monitor-grid">
          {r.data.map((s) => {
            const sn = s.snapshot;
            const day = sn?.day_return_pct ?? null;
            return (
              <article className="card" key={s.security_id} data-testid={`card-${s.ticker}`}>
                <h3>
                  <Link href={`/stock/${s.ticker}`}>{s.ticker}</Link>
                  <small className="muted">{s.legal_name}</small>
                </h3>
                {sn ? (
                  <>
                    <div className="row">
                      <span className={`num ${day !== null && day > 0 ? "up" : day !== null && day < 0 ? "down" : ""}`}>{pct(day)}</span>
                      <span className="muted">相对篮子 {pp(sn.day_relative_pp ?? null)}</span>
                    </div>
                    <p className="muted" style={{ margin: "0.3rem 0" }}>
                      {sn.explanation_summary}
                    </p>
                    <div className="row">
                      <QualityBadge quality={sn.data_quality} lastValidAt={sn.last_valid_at} />
                      <small className="muted">快照 {etTime(sn.analysis_as_of)}</small>
                      <RefreshButton securityId={s.security_id} />
                    </div>
                  </>
                ) : (
                  <p className="muted">暂无快照</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}
