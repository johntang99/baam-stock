import Link from "next/link";

import { SCHEMA_VERSION } from "@/lib/contracts";

export default function Home() {
  return (
    <main>
      <h1>baam-stock</h1>
      <p>美股研究与预测系统（内部）。完整页面从 Phase 2 开始实现。</p>
      <ul>
        <li>
          <Link href="/replay">回放报告（逐条核验，只读）</Link>
        </li>
      </ul>
      <p>
        契约版本 <code>{SCHEMA_VERSION}</code>
      </p>
      <p>
        <small>仅限内部团队使用，不对外开放，不构成投资建议。</small>
      </p>
    </main>
  );
}
