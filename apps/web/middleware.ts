// Keeps the Supabase session cookie fresh (Supabase mode only; the fixture mode has no session).
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(req: NextRequest) {
  const res = NextResponse.next({ request: req });
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (process.env.DATA_SOURCE === "fixture" || !url || !key) return res;
  const { createServerClient } = await import("@supabase/ssr");
  const sb = createServerClient(url, key, {
    cookies: {
      getAll: () => req.cookies.getAll(),
      setAll: (list) => {
        for (const c of list) res.cookies.set(c.name, c.value, c.options);
      },
    },
  });
  await sb.auth.getUser();
  return res;
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
