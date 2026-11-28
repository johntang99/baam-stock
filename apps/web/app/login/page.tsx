"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

// Sign-in (Supabase Auth, email + password). Roles are assigned by an admin in app_metadata (DC §10).
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!url || !key) return setErr("Supabase 未配置");
    const { createBrowserClient } = await import("@supabase/ssr");
    const { error } = await createBrowserClient(url, key).auth.signInWithPassword({ email, password });
    if (error) return setErr("登录失败：邮箱或密码不正确");
    router.push("/");
    router.refresh();
  }

  return (
    <main style={{ maxWidth: 360 }}>
      <h1>登录</h1>
      <form onSubmit={submit} className="panel">
        <label>
          邮箱 <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          密码{" "}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </label>
        {err && <p className="error" role="alert">{err}</p>}
        <button type="submit">登录</button>
      </form>
      <p className="muted">
        <small>账号与角色由管理员开通；没有角色的账号看不到任何数据。</small>
      </p>
    </main>
  );
}
