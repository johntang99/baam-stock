import { etTime, label, QUALITY_LABEL } from "@/lib/format";

// Minimal quality marker; the full quality / validity view is DP 2.22.
export function QualityBadge({ quality, lastValidAt }: { quality: string; lastValidAt?: string | null }) {
  const cls = quality === "ok" ? "ok" : quality === "failed" ? "bad" : "warn";
  return (
    <span className={`badge ${cls}`} data-testid={`quality-${quality}`}>
      数据质量：{label(QUALITY_LABEL, quality)}
      {quality !== "ok" && lastValidAt ? ` · 最近有效 ${etTime(lastValidAt)}` : ""}
    </span>
  );
}
