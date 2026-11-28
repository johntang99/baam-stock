import Link from "next/link";

import type { Viewer } from "@/lib/data/types";

export function Nav({ viewer, synthetic }: { viewer: Viewer | null; synthetic: boolean }) {
  return (
    <header className="nav">
      <Link href="/" className="brand">
        baam-stock
      </Link>
      <nav>
        <Link href="/">监控</Link>
        <Link href="/predictions">预测</Link>
        <Link href="/events">事件</Link>
        <Link href="/replay">回放</Link>
        <Link href="/ops/run">运行</Link>
      </nav>
      <span className="who">
        {synthetic && <span className="badge warn" data-testid="synthetic-banner">合成数据 · 虚构</span>}
        {viewer ? <span className="badge">{viewer.role}</span> : <Link href="/login">登录</Link>}
      </span>
    </header>
  );
}
