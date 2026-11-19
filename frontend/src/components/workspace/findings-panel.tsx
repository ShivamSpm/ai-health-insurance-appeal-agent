"use client";

import { AlertTriangleIcon, CalendarIcon, ShieldAlertIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { EvidenceInfo, Findings } from "@/lib/api";
import { longDate } from "@/lib/format";
import { CitationChip } from "./markdown";

const TYPE_LABEL: Record<Findings["denial_types"][number], string> = {
  medical_necessity: "Medical necessity",
  prior_authorization: "Prior authorization",
  out_of_network: "Out of network",
  coding_error: "Coding or billing error",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[9rem_1fr]">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="min-w-0 text-sm">{children}</div>
    </div>
  );
}

export function FindingsPanel({
  findings,
  evidence,
  onCite,
}: {
  findings: Findings;
  evidence: Map<string, EvidenceInfo>;
  onCite: (chunkId: string) => void;
}) {
  return (
    <div className="space-y-3">
      <Row label="Denial type">
        <div className="flex flex-wrap items-center gap-1.5">
          {findings.denial_types.map((t) => (
            <Badge key={t} variant="secondary">
              {TYPE_LABEL[t]}
            </Badge>
          ))}
          {findings.ambiguous && (
            <Badge variant="outline" className="border-amber-400 text-amber-800">
              Ambiguous
            </Badge>
          )}
        </div>
      </Row>

      <Row label="Appeal">
        <div className="space-y-1">
          <Badge
            className={
              findings.appeal_viable
                ? "bg-emerald-100 text-emerald-900"
                : "bg-zinc-200 text-zinc-800"
            }
          >
            {findings.appeal_viable ? "Worth appealing" : "Unlikely to succeed"}
          </Badge>
          <p className="text-muted-foreground">{findings.viability_rationale}</p>
        </div>
      </Row>

      <Row label="Deadline">
        <div className="space-y-0.5">
          <div className="flex items-center gap-1.5 font-medium">
            <CalendarIcon className="size-4 text-muted-foreground" />
            {longDate(findings.appeal_deadline)}
          </div>
          <p className="text-muted-foreground">{findings.deadline_reasoning}</p>
        </div>
      </Row>

      <Row label="Insurer relied on">
        <div className="flex flex-wrap gap-1">
          {findings.denial_basis_clause_ids.map((id) => (
            <CitationChip key={id} chunkId={id} onCite={onCite} />
          ))}
        </div>
      </Row>

      <Row label="Appeal relies on">
        <div className="flex flex-wrap gap-1">
          {findings.governing_clause_ids.map((id) => (
            <CitationChip key={id} chunkId={id} onCite={onCite} />
          ))}
        </div>
      </Row>

      <Row label="Missing evidence">
        {findings.missing_evidence.length === 0 ? (
          <span className="text-muted-foreground">Nothing missing.</span>
        ) : (
          <ul className="space-y-1.5">
            {findings.missing_evidence.map((e) => (
              <li key={e.id}>
                <span className="font-medium">{evidence.get(e.id)?.name ?? e.id}</span>
                <span className="text-muted-foreground"> · {e.reason}</span>
              </li>
            ))}
          </ul>
        )}
      </Row>

      {findings.contradictions.length > 0 && (
        <Row label="Contradictions">
          <ul className="space-y-1.5">
            {findings.contradictions.map((c, i) => (
              <li key={i} className="flex gap-1.5">
                <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-amber-600" />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </Row>
      )}

      {findings.suspicious_instructions.length > 0 && (
        <Row label="Ignored instructions">
          <ul className="space-y-1.5">
            {findings.suspicious_instructions.map((c, i) => (
              <li key={i} className="flex gap-1.5">
                <ShieldAlertIcon className="mt-0.5 size-4 shrink-0 text-red-600" />
                <span>
                  {c}{" "}
                  <span className="text-xs text-muted-foreground">
                    (found in a document; not followed)
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Row>
      )}
    </div>
  );
}
