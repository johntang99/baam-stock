// Timeouts and the fixture-only page states (DP 2.07 / 2.15: normal, loading, empty, timeout, failure).
import { DataError } from "./types.ts";
import type { DataSource } from "./types.ts";

export type Scenario = "normal" | "slow" | "empty" | "timeout" | "error";
export const SCENARIOS: Scenario[] = ["normal", "slow", "empty", "timeout", "error"];

export function parseScenario(v: unknown): Scenario {
  return typeof v === "string" && (SCENARIOS as string[]).includes(v) ? (v as Scenario) : "normal";
}

export async function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const t = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new DataError("timeout", `no answer within ${ms} ms`)), ms);
  });
  try {
    return await Promise.race([p, t]);
  } finally {
    clearTimeout(timer);
  }
}

const READS = ["listSecurities", "security", "predictions", "prediction", "events", "event", "run", "runs"] as const;
const LISTS = new Set(["listSecurities", "predictions", "events", "runs"]);

/** Every call gets the timeout; in fixture mode a scenario can force the empty / slow / timeout / error state. */
export function wrap(src: DataSource, timeoutMs: number, scenario: Scenario = "normal"): DataSource {
  const out = { ...src } as DataSource;
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
  for (const name of READS) {
    const fn = (src[name] as (...a: unknown[]) => Promise<unknown>).bind(src);
    (out as unknown as Record<string, unknown>)[name] = async (...a: unknown[]) => {
      if (src.kind === "fixture") {
        if (scenario === "error") throw new DataError("failure", "synthetic failure (scenario=error)");
        if (scenario === "timeout") return withTimeout(sleep(timeoutMs + 1000).then(() => null), timeoutMs);
        if (scenario === "slow") await sleep(1500);
        if (scenario === "empty") return LISTS.has(name) ? [] : null;
      }
      return withTimeout(fn(...a), timeoutMs);
    };
  }
  return out;
}
