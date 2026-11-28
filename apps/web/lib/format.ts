// Display helpers. Storage is UTC; pages show America/New_York (CLAUDE.md 时间规则).
const ET = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const ET_TIME = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false });

export function etDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : `${ET.format(d).replace(",", "")} ET`;
}

export function etTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : `${ET_TIME.format(d)} ET`;
}

export function pct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function pp(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}pp`;
}

export const QUALITY_LABEL: Record<string, string> = { ok: "正常", partial: "部分", stale: "陈旧", failed: "失败" };
export const STATUS_LABEL: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  succeeded: "已完成",
  partial: "部分完成",
  failed: "失败",
  cancelled: "已取消",
  pending: "等待",
  skipped: "跳过",
  retry_wait: "等待重试",
  published: "已发布",
  settled: "已结算",
  abstained: "弃预测",
  unsettleable: "无法结算",
  awaiting_settlement: "待结算",
};
export const CLASS_LABEL: Record<string, string> = { outperform: "跑赢", flat: "持平", underperform: "跑输" };
export const TARGET_LABEL: Record<string, string> = {
  tgt_regular_60m_v1: "60 分钟方向",
  tgt_regular_60m_move_v1: "60 分钟幅度",
  tgt_regular_to_close_v1: "至收盘",
  tgt_next_regular_session_v1: "下一交易时段",
  regular_60m: "60 分钟方向",
  regular_60m_move: "60 分钟幅度",
  regular_to_close: "至收盘",
  next_regular_session: "下一交易时段",
};

export const label = (m: Record<string, string>, k: string | null | undefined): string => (k ? (m[k] ?? k) : "—");
