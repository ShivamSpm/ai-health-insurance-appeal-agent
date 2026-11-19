"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CaseDetail, Findings, PlanSection } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Markdown } from "./markdown";

export type DocTab = "letter" | "note" | "plan";

interface Props {
  detail: CaseDetail;
  findings: Findings | null;
  retrieved: string[];
  citedInLetter: string[];
  tab: DocTab;
  onTab: (tab: DocTab) => void;
  focus: { chunkId: string; n: number } | null; // n changes on every click, to re-trigger
  onCite: (chunkId: string) => void;
}

function SectionCard({
  section,
  tags,
  focused,
  onCite,
}: {
  section: PlanSection;
  tags: string[];
  focused: boolean;
  onCite: (chunkId: string) => void;
}) {
  const highlighted = tags.includes("Governing") || tags.includes("Cited in letter");
  return (
    <section
      id={`sec-${section.chunk_id}`}
      data-chunk={section.chunk_id}
      className={cn(
        "scroll-mt-2 rounded-lg border p-3",
        highlighted && "border-blue-300 bg-blue-50/60 dark:border-blue-800 dark:bg-blue-950/40",
        tags.includes("Denial basis") && !highlighted && "border-amber-300 bg-amber-50/60",
        focused && "flash",
      )}
    >
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <h3 className="text-sm font-semibold">
          {section.number} {section.title}
        </h3>
        <span className="font-mono text-[11px] text-muted-foreground">
          {section.chunk_id} · p.{section.page}
        </span>
        {tags.map((t) => (
          <Badge
            key={t}
            variant={t === "Retrieved" ? "outline" : "secondary"}
            className={cn(
              "h-5 text-[11px]",
              t === "Denial basis" && "bg-amber-100 text-amber-900",
              (t === "Governing" || t === "Cited in letter") && "bg-blue-100 text-blue-900",
            )}
          >
            {t}
          </Badge>
        ))}
      </div>
      <Markdown text={section.text} onCite={onCite} className="text-[13px]" />
    </section>
  );
}

export function DocumentsPanel({
  detail,
  findings,
  retrieved,
  citedInLetter,
  tab,
  onTab,
  focus,
  onCite,
}: Props) {
  const [relevantOnly, setRelevantOnly] = useState(false);

  const tagsFor = useMemo(() => {
    const governing = new Set(findings?.governing_clause_ids ?? []);
    const basis = new Set(findings?.denial_basis_clause_ids ?? []);
    const cited = new Set(citedInLetter);
    const got = new Set(retrieved);
    return (id: string) =>
      [
        governing.has(id) && "Governing",
        basis.has(id) && "Denial basis",
        cited.has(id) && "Cited in letter",
        got.has(id) && "Retrieved",
      ].filter(Boolean) as string[];
  }, [findings, citedInLetter, retrieved]);

  // The section the user just jumped to stays visible even when filtering.
  const sections = detail.plan_sections.filter(
    (s) => !relevantOnly || tagsFor(s.chunk_id).length > 0 || s.chunk_id === focus?.chunkId,
  );

  useEffect(() => {
    if (!focus) return;
    // Wait for the plan tab to render before scrolling.
    const t = setTimeout(() => {
      document.getElementById(`sec-${focus.chunkId}`)?.scrollIntoView({ behavior: "smooth" });
    }, 50);
    return () => clearTimeout(t);
  }, [focus]);

  return (
    <Tabs
      value={tab}
      onValueChange={(v) => onTab(v as DocTab)}
      className="flex h-full min-h-0 flex-col"
    >
      <div className="flex items-center justify-between gap-2">
        <TabsList>
          <TabsTrigger value="letter">Denial letter</TabsTrigger>
          <TabsTrigger value="note">Member note</TabsTrigger>
          <TabsTrigger value="plan">Plan</TabsTrigger>
        </TabsList>
        {tab === "plan" && (
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={relevantOnly}
              onChange={(e) => setRelevantOnly(e.target.checked)}
            />
            Only sections the agent used
          </label>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border bg-background p-4">
        <TabsContent value="letter">
          <Markdown text={detail.denial_letter} />
        </TabsContent>
        <TabsContent value="note">
          <Markdown text={detail.member_note || "_No note._"} />
        </TabsContent>
        <TabsContent value="plan" className="space-y-2">
          <p className="text-xs text-muted-foreground">{detail.plan_name}</p>
          {sections.map((s) => (
            <SectionCard
              // A new key on each jump restarts the highlight animation.
              key={focus?.chunkId === s.chunk_id ? `${s.chunk_id}-${focus.n}` : s.chunk_id}
              section={s}
              tags={tagsFor(s.chunk_id)}
              focused={focus?.chunkId === s.chunk_id}
              onCite={onCite}
            />
          ))}
        </TabsContent>
      </div>
    </Tabs>
  );
}
