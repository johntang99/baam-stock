"use client";

export default function MarketError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="state failed" role="alert" data-testid="state-error">
      <strong>页面出错</strong>
      <p>页面渲染时出错。已发布的数据不受影响。</p>
      <button type="button" onClick={reset}>
        重试
      </button>
    </div>
  );
}
