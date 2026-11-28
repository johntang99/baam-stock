// Picks the data source and the signed-in viewer (server side). DATA_SOURCE=fixture serves SYNTHETIC data for
// development and e2e tests; anything else uses Supabase with the user's session (RLS).
import { cookies } from "next/headers";

import { fixtureSource } from "./fixture.ts";
import { DataError, ROLE_RANK } from "./types.ts";
import type { DataSource, Role, Viewer } from "./types.ts";
import { parseScenario, wrap } from "./wrap.ts";

export const isFixture = (): boolean => process.env.DATA_SOURCE === "fixture";
const timeoutMs = (): number => Number(process.env.DATA_TIMEOUT_MS ?? 8000);

async function supabaseClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new DataError("failure", "Supabase is not configured (NEXT_PUBLIC_SUPABASE_URL / ANON_KEY)");
  const { createServerClient } = await import("@supabase/ssr");
  const jar = await cookies();
  return createServerClient(url, key, {
    cookies: {
      getAll: () => jar.getAll(),
      setAll: (list) => {
        try {
          for (const c of list) jar.set(c.name, c.value, c.options);
        } catch {
          // called from a Server Component: the middleware refreshes the session instead
        }
      },
    },
  });
}

export async function getData(scenario?: unknown): Promise<DataSource> {
  if (isFixture()) return wrap(fixtureSource(), timeoutMs(), parseScenario(scenario));
  const { supabaseSource } = await import("./supabase.ts");
  return wrap(supabaseSource(await supabaseClient()), timeoutMs());
}

function asRole(v: unknown): Role | null {
  return typeof v === "string" && v in ROLE_RANK ? (v as Role) : null;
}

/** The signed-in user and role, or null (no session / no role: nothing is readable, DC §10). */
export async function getViewer(): Promise<Viewer | null> {
  if (isFixture()) {
    const jar = await cookies();
    const role = asRole(jar.get("fixture_role")?.value) ?? asRole(process.env.FIXTURE_ROLE) ?? "researcher";
    return { userId: `fixture-${role}`, role, email: null };
  }
  const db = await supabaseClient();
  const { data } = await db.auth.getUser();
  const role = asRole(data.user?.app_metadata?.app_role);
  return data.user && role ? { userId: data.user.id, role, email: data.user.email ?? null } : null;
}
