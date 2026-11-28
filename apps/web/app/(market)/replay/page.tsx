import Link from "next/link";

import { fmt, listReports } from "@/lib/replay";

import { redirect } from "next/navigation";

import { getViewer } from "@/lib/data";

export const dynamic = "force-dynamic"; // reports are read at request time

export default async function ReplayIndex() {
  if (!(await getViewer())) redirect("/login");
  const reports = await listReports();
  return (
    <main>
      <h1>回放报告 · replay reports</h1>
      <p>
        <small>只读页面（DP 1.19）。由 <code>sr replay</code> 生成；数据为合成（synthetic / 虚构）时页面会注明。</small>
      </p>
      {reports.length === 0 ? (
        <p>暂无报告。先运行 <code>uv run sr replay --security sec_nvda --date … --fixture …</code>。</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>预测</th>
              <th>目标</th>
              <th>发布</th>
              <th>状态</th>
              <th>结果</th>
              <th>检查</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => {
              const fails = r.checks.filter((c) => c.result === "FAIL").length;
              const s = r.settlement;
              return (
                <tr key={r.prediction.prediction_id}>
                  <td>
                    <Link href={`/replay/${r.prediction.prediction_id}`}>{r.prediction.prediction_id}</Link>
                  </td>
                  <td>{r.prediction.target_row_id}</td>
                  <td>{fmt(r.prediction.published_at)}</td>
                  <td>{r.prediction.status}</td>
                  <td>{s ? fmt(s.outcome_class ?? s.abs_relative_move_pp ?? s.invalid_reason) : "—"}</td>
                  <td>{fails === 0 ? "✅" : `❌ ${fails}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}
