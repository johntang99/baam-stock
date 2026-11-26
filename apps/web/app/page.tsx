import { SCHEMA_VERSION } from "@/lib/contracts";

export default function Home() {
  return (
    <main>
      <h1>baam-stock</h1>
      <p>美股短期研究与预测系统 · Phase 0 空壳页面。页面功能从 Phase 2 开始实现。</p>
      <p>
        契约版本 <code>{SCHEMA_VERSION}</code>
      </p>
      <p>
        <small>仅用于研究与验证，不接入交易执行，不构成投资建议。</small>
      </p>
    </main>
  );
}
