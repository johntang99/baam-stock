import Link from "next/link";
import { notFound } from "next/navigation";

import { RunProgress } from "@/components/RunProgress";
import { attempt, Failed } from "@/components/States";
import { isFixture } from "@/lib/data";
import { pageContext, type SearchParams } from "@/lib/page";

export const dynamic = "force-dynamic";

// One run: step progress (polling + Realtime), cancel (DP 2.08).
export default async function RunPage({
  params,
  searchParams,
}: {
  params: Promise<{ pipeline_run_id: string }>;
  searchParams: SearchParams;
}) {
  const { pipeline_run_id } = await params;
  const { db } = await pageContext(searchParams);
  const r = await attempt(() => db.run(pipeline_run_id));
  if (!r.ok) return <Failed error={r.error} retry={`/ops/run/${pipeline_run_id}`} />;
  if (!r.data) notFound();
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return (
    <main>
      <p>
        <Link href="/ops/run">← 运行历史</Link>
      </p>
      <h1>
        运行 <small className="muted">{pipeline_run_id}</small>
      </h1>
      <p className="muted">证券 {r.data.run.security_ids.join(", ")} · 目标 {r.data.run.target_ids.join(", ")}</p>
      <RunProgress initial={r.data} realtime={!isFixture() && url && key ? { url, key } : null} />
    </main>
  );
}
