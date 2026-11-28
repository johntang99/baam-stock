import Link from "next/link";

import { RunPanel } from "@/components/RunPanel";
import { attempt, Empty, Failed } from "@/components/States";
import { ROLE_RANK } from "@/lib/data/types";
import { etDateTime, label, STATUS_LABEL } from "@/lib/format";
import { pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// Operations run panel + history (DP 2.08; DC §6 POST /api/pipeline-runs).
export default async function RunOps({ searchParams }: { searchParams: SearchParams }) {
  const { db, viewer } = await pageContext(searchParams);
  const [secs, runs] = await Promise.all([attempt(() => db.listSecurities()), attempt(() => db.runs(30))]);
  return (
    <main>
      <h1>一键运行</h1>
      {!secs.ok ? (
        <Failed error={secs.error} retry="/ops/run" />
      ) : (
        <RunPanel
          securities={secs.data.map((s) => ({ security_id: s.security_id, ticker: s.ticker }))}
          canReplay={ROLE_RANK[viewer.role] >= ROLE_RANK.researcher}
        />
      )}
      <h2>运行历史</h2>
      {!runs.ok ? (
        <Failed error={runs.error} retry="/ops/run" />
      ) : runs.data.length === 0 ? (
        <Empty>还没有运行记录。</Empty>
      ) : (
        <div className="table-wrap">
          <table data-testid="run-history">
            <thead>
              <tr>
                <th>运行</th>
                <th>证券</th>
                <th>目标</th>
                <th>模式</th>
                <th>as_of</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {runs.data.map((r) => (
                <tr key={r.pipeline_run_id}>
                  <td>
                    <Link href={`/ops/run/${r.pipeline_run_id}`}>{r.pipeline_run_id}</Link>
                  </td>
                  <td>{r.security_ids.join(", ")}</td>
                  <td>{r.target_ids.join(", ")}</td>
                  <td>{r.mode}</td>
                  <td>{etDateTime(r.as_of)}</td>
                  <td>{label(STATUS_LABEL, r.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
