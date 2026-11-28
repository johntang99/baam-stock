import Link from "next/link";

import { DataError } from "@/lib/data/types";

export function Loading({ what = "数据" }: { what?: string }) {
  return (
    <div className="state loading" role="status" aria-live="polite" data-testid="state-loading">
      <span className="spinner" aria-hidden /> 正在加载{what}…
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="state empty" data-testid="state-empty">
      {children}
    </div>
  );
}

/** Timeout and failure are shown differently: a timeout says the source was slow and offers a retry. */
export function Failed({ error, retry }: { error: unknown; retry: string }) {
  const timeout = error instanceof DataError && error.kind === "timeout";
  const forbidden = error instanceof DataError && error.kind === "forbidden";
  return (
    <div className="state failed" role="alert" data-testid={timeout ? "state-timeout" : "state-error"}>
      <strong>{timeout ? "加载超时" : forbidden ? "没有权限" : "加载失败"}</strong>
      <p>
        {timeout
          ? "数据服务在规定时间内没有响应。已发布的数据不受影响。"
          : forbidden
            ? "当前账号的角色不能查看这部分内容。"
            : "读取数据时出错，请稍后重试；问题持续时查看运营页的告警。"}
      </p>
      {!forbidden && (
        <Link href={retry} className="button">
          重试
        </Link>
      )}
    </div>
  );
}

export async function attempt<T>(fn: () => Promise<T>): Promise<{ ok: true; data: T } | { ok: false; error: unknown }> {
  try {
    return { ok: true, data: await fn() };
  } catch (error) {
    return { ok: false, error };
  }
}
