import Link from "next/link";
import { notFound } from "next/navigation";

import { fmt, loadReport } from "@/lib/replay";

import { redirect } from "next/navigation";

import { getViewer } from "@/lib/data";

export const dynamic = "force-dynamic";

const LOCKED = [
  "target_definition_version",
  "quote_rule_version",
  "benchmark_version_id",
  "calendar_version",
  "model_version_id",
  "calibration_version",
  "schema_version",
  "sigma_model_version",
  "sigma_hat_pp",
  "threshold_k",
  "threshold_pp",
  "feature_set_version",
] as const;

export default async function ReplayPrediction({ params }: { params: Promise<{ prediction_id: string }> }) {
  if (!(await getViewer())) redirect("/login");
  const { prediction_id } = await params;
  const r = await loadReport(prediction_id);
  if (!r) notFound();
  const p = r.prediction;
  const s = r.settlement;
  const locked = (p.locked ?? {}) as Record<string, unknown>;
  const fails = r.checks.filter((c) => c.result === "FAIL").length;
  return (
    <main>
      <p>
        <Link href="/replay">← 回放报告</Link>
      </p>
      <h1>
        {p.prediction_id} · {p.target_row_id}
      </h1>
      {r.synthetic && (
        <p>
          <strong>合成数据（synthetic / 虚构）</strong>，不代表实际行情。
        </p>
      )}
      <p>
        {p.security_id} · 状态 <strong>{p.status}</strong>
        {p.abstain_reason ? `（${p.abstain_reason}）` : ""} · 抽样 {p.sampling_rule}
        {p.schedule_slot_id ? ` / ${p.schedule_slot_id}` : ""} · 发布 {fmt(p.published_at)} · 核验{" "}
        {fails === 0 ? "全部通过" : `${fails} 项未通过`}
      </p>

      <h2>预测</h2>
      {p.probabilities ? (
        <p>
          {Object.entries(p.probabilities as Record<string, number>)
            .map(([k, v]) => `${k} ${v.toFixed(3)}`)
            .join(" · ")}{" "}
          → <strong>{p.predicted_class}</strong>；阈值 ±{fmt(p.threshold_pp)}pp（σ̂ {fmt(p.sigma_hat_pp)}）
        </p>
      ) : p.move_quantiles ? (
        <p>
          预期波动{" "}
          {Object.entries(p.move_quantiles as Record<string, unknown>)
            .filter(([k]) => k !== "unit")
            .map(([k, v]) => `${k} ${fmt(v)}`)
            .join(" · ")}{" "}
          pp
        </p>
      ) : (
        <p>弃预测，无概率。</p>
      )}

      <h2>快照</h2>
      <p>
        {fmt(r.snapshot.snapshot_id)} · as_of {fmt(r.snapshot.analysis_as_of)} · {fmt(r.snapshot.market_state)} · 质量{" "}
        {fmt(r.snapshot.data_quality)} · 当日 {fmt(r.snapshot.day_return_pct)}% · 相对 {fmt(r.snapshot.day_relative_pp)}pp
      </p>
      <p>{fmt(r.snapshot.explanation_summary)}</p>

      <h2>锁定输入</h2>
      <table>
        <tbody>
          {LOCKED.map((k) => (
            <tr key={k}>
              <td>
                <code>{k}</code>
              </td>
              <td>{fmt(locked[k])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        模型 {fmt(r.model.model_version_id)}（{fmt(r.model.model_family)}，{fmt(r.model.status)}）
      </p>

      <h2>起算 / 结算报价</h2>
      <table>
        <thead>
          <tr>
            <th />
            <th>quote_id</th>
            <th>quote_ts</th>
            <th>mid</th>
          </tr>
        </thead>
        <tbody>
          {(
            [
              ["t0", r.t0_quote],
              ["end", r.end_quote],
            ] as const
          ).map(([name, q]) => (
            <tr key={name}>
              <td>{name}</td>
              <td>{fmt(q?.quote_id)}</td>
              <td>{fmt(q?.quote_ts)}</td>
              <td>{fmt(q?.mid)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>结算</h2>
      {s ? (
        <>
          <p>
            个股 {fmt(s.stock_return_pct)}% · 篮子 {fmt(s.benchmark_return_pct)}% · 相对 {fmt(s.relative_return_pp)}pp · 类别{" "}
            {fmt(s.outcome_class)} · 命中 {fmt(s.hit)} · Brier {fmt(s.brier)}
            {s.abs_relative_move_pp !== null && s.abs_relative_move_pp !== undefined
              ? ` · |move| ${fmt(s.abs_relative_move_pp)} · pinball ${fmt(s.pinball_loss)}`
              : ""}
          </p>
          <p>
            理由：{s.reason_text}（v{fmt(s.settlement_version)}，共 {r.settlement_versions} 版）
          </p>
        </>
      ) : (
        <p>{p.status === "abstained" ? "弃预测，不结算。" : "尚未结算。"}</p>
      )}

      <h2>核验</h2>
      <table>
        <tbody>
          {r.checks.map((c) => (
            <tr key={c.check}>
              <td>{c.check}</td>
              <td>{c.result}</td>
              <td>{c.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <small>仅用于研究与验证，不构成投资建议。</small>
      </p>
    </main>
  );
}
