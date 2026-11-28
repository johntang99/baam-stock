import Link from "next/link";

import { attempt, Empty, Failed } from "@/components/States";
import { CLASS_LABEL, etDateTime, label, STATUS_LABEL, TARGET_LABEL } from "@/lib/format";
import { first, pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// Predictions list (DP 2.07): filter by target and status; viewers see only the displayable tiers (RLS).
export default async function Predictions({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const { db } = await pageContext(Promise.resolve(sp));
  const target = first(sp.target_id);
  const status = first(sp.status);
  const r = await attempt(() => db.predictions({ target_id: target, status, limit: 100 }));
  return (
    <main>
      <h1>预测</h1>
      <form className="row" method="get">
        <select name="target_id" defaultValue={target ?? ""} aria-label="目标">
          <option value="">全部目标</option>
          {["regular_60m", "regular_60m_move", "regular_to_close", "next_regular_session"].map((t) => (
            <option key={t} value={t}>
              {TARGET_LABEL[t]}
            </option>
          ))}
        </select>
        <select name="status" defaultValue={status ?? ""} aria-label="状态">
          <option value="">全部状态</option>
          {["published", "settled", "abstained", "unsettleable"].map((x) => (
            <option key={x} value={x}>
              {STATUS_LABEL[x]}
            </option>
          ))}
        </select>
        <button type="submit" className="small">
          筛选
        </button>
      </form>
      {!r.ok ? (
        <Failed error={r.error} retry="/predictions" />
      ) : r.data.length === 0 ? (
        <Empty>没有符合条件的预测。</Empty>
      ) : (
        <div className="table-wrap">
          <table data-testid="predictions-table">
            <thead>
              <tr>
                <th>预测</th>
                <th>证券</th>
                <th>目标</th>
                <th>发布</th>
                <th>状态</th>
                <th>判断</th>
                <th>主评分</th>
              </tr>
            </thead>
            <tbody>
              {r.data.map((p) => (
                <tr key={p.prediction_id}>
                  <td>
                    <Link href={`/predictions/${p.prediction_id}`}>{p.prediction_id}</Link>
                  </td>
                  <td>{p.security_id}</td>
                  <td>{label(TARGET_LABEL, p.target_row_id)}</td>
                  <td>{etDateTime(p.published_at ?? null)}</td>
                  <td>{label(STATUS_LABEL, p.status)}</td>
                  <td>{p.predicted_class ? label(CLASS_LABEL, p.predicted_class) : (p.abstain_reason ?? "—")}</td>
                  <td>{p.is_primary ? "是" : "否"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
