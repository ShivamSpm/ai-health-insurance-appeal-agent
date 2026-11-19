import type { RunStatus } from "./api";

// Plan citations look like [hmo-4.1]; the agent may only cite sections it retrieved.
export const CITATION_RE = /\[([a-z]+-\d+\.\d+)\]/g;

export function citedIds(text: string | null | undefined): string[] {
  return [...new Set([...(text ?? "").matchAll(CITATION_RE)].map((m) => m[1]))];
}

export function sectionNumber(chunkId: string): string {
  return chunkId.slice(chunkId.indexOf("-") + 1);
}

export function money(usd: number | null | undefined, digits = 3): string {
  return usd == null ? "n/a" : `$${usd.toFixed(digits)}`;
}

export function seconds(ms: number | null | undefined): string {
  return ms == null ? "" : `${(ms / 1000).toFixed(1)}s`;
}

export function tokens(n: number | null | undefined): string {
  if (n == null) return "0";
  return n >= 10_000 ? `${(n / 1000).toFixed(0)}k` : n.toLocaleString();
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortModel(id: string): string {
  return id.split("/").pop() ?? id;
}

export const STATUS_LABEL: Record<RunStatus, string> = {
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  step_limit: "Step limit",
  error: "Error",
};

export function longDate(isoDate: string): string {
  // A plain date (YYYY-MM-DD): format it without shifting it into the local time zone.
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}
