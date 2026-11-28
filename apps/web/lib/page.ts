// Page helpers: the signed-in viewer (else /login) and the data source with the fixture-only state parameter.
import { redirect } from "next/navigation";

import { getData, getViewer, isFixture } from "./data/index.ts";
import type { DataSource, Viewer } from "./data/types.ts";

export type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export async function pageContext(sp?: SearchParams): Promise<{ viewer: Viewer; db: DataSource; state: string | undefined }> {
  const viewer = await getViewer();
  if (!viewer) redirect("/login");
  const p = sp ? await sp : {};
  const state = isFixture() && typeof p.state === "string" ? p.state : undefined;
  return { viewer, db: await getData(state), state };
}

export function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}
