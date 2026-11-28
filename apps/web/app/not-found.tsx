import Link from "next/link";

export default function NotFound() {
  return (
    <main className="state empty" data-testid="not-found">
      <strong>找不到这个页面</strong>
      <p>证券、预测或事件不存在，或当前账号无权查看。</p>
      <Link href="/">回到监控</Link>
    </main>
  );
}
