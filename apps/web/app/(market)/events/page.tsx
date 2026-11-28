import Link from "next/link";

import { attempt, Empty, Failed } from "@/components/States";
import { etDateTime } from "@/lib/format";
import { pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// Events list (DC §6 GET /api/events).
export default async function EventsPage({ searchParams }: { searchParams: SearchParams }) {
  const { db } = await pageContext(searchParams);
  const r = await attempt(() => db.events({}));
  return (
    <main>
      <h1>事件</h1>
      {!r.ok ? (
        <Failed error={r.error} retry="/events" />
      ) : r.data.length === 0 ? (
        <Empty>监测来源范围内暂无事件。</Empty>
      ) : (
        <div className="table-wrap">
          <table data-testid="events-table">
            <thead>
              <tr>
                <th>事件</th>
                <th>类别</th>
                <th>进展</th>
                <th>证据</th>
                <th>相关证券</th>
                <th>首次发现</th>
              </tr>
            </thead>
            <tbody>
              {r.data.map((e) => (
                <tr key={e.event.event_id}>
                  <td>
                    <Link href={`/events/${e.event.event_id}`}>{e.event.identity_key}</Link>
                  </td>
                  <td>{e.event.category}</td>
                  <td>{e.event.progress_status}</td>
                  <td>{e.event.evidence_status}</td>
                  <td>{e.security_ids.join(", ")}</td>
                  <td>{etDateTime(e.event.first_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
