// Typed client for the FastAPI backend. Types come from the backend's OpenAPI
// schema (`npm run gen:api`), so a backend change that breaks the UI fails typecheck.
import type { components } from "./api-types";

type Schemas = components["schemas"];
export type CaseSummary = Schemas["CaseSummary"];
export type CaseDetail = Schemas["CaseDetail"];
export type PlanSection = Schemas["PlanSection"];
export type NewCase = Schemas["NewCase"];
export type RunSummary = Schemas["RunSummary"];
export type RunDetail = Schemas["RunDetail"];
export type Step = Schemas["Step"];
export type Findings = Schemas["Findings"];
export type DraftVersion = Schemas["DraftVersion"];
export type ModelOption = Schemas["ModelOption"];
export type EvidenceInfo = Schemas["EvidenceInfo"];
export type RunStatus = RunSummary["status"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(API_URL + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, `Can't reach the API at ${API_URL}. Is \`appeal-agent serve\` running?`);
  }
  if (!resp.ok) {
    let detail: unknown;
    try {
      detail = (await resp.json()).detail;
    } catch {}
    throw new ApiError(
      resp.status,
      typeof detail === "string" ? detail : `Request failed (${resp.status})`,
    );
  }
  return resp.json() as Promise<T>;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<{ ok: boolean; live_runs: boolean }>("/api/health"),
  models: () => request<ModelOption[]>("/api/models"),
  evidence: () => request<EvidenceInfo[]>("/api/evidence"),
  cases: () => request<CaseSummary[]>("/api/cases"),
  case: (caseId: string) => request<CaseDetail>(`/api/cases/${caseId}`),
  createCase: (body: NewCase) => request<CaseSummary>("/api/cases", post(body)),
  caseRuns: (caseId: string) => request<RunSummary[]>(`/api/cases/${caseId}/runs`),
  startRun: (caseId: string, model?: string) =>
    request<{ run_id: string }>(`/api/cases/${caseId}/runs`, post({ model })),
  run: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  drafts: (runId: string) => request<DraftVersion[]>(`/api/runs/${runId}/drafts`),
  saveDraft: (runId: string, text: string) =>
    request<DraftVersion>(`/api/runs/${runId}/drafts`, post({ text })),
};

export function eventsUrl(runId: string, replay: boolean, speed: number): string {
  const q = replay ? `?replay=true&speed=${speed}` : "";
  return `${API_URL}/api/runs/${runId}/events${q}`;
}
