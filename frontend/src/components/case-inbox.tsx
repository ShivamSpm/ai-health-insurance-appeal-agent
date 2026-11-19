"use client";

import { SearchIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { NewCaseDialog } from "@/components/new-case-dialog";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type CaseSummary } from "@/lib/api";

export function CaseInbox() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.cases().then(setCases, (e: Error) => setError(e.message));
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = [...(cases ?? [])].sort(
      // Newest user cases first, then the dataset in order.
      (a, b) =>
        Number(b.source === "user") - Number(a.source === "user") ||
        a.case_id.localeCompare(b.case_id),
    );
    if (!q) return list;
    return list.filter((c) =>
      [c.case_id, c.title, c.plan_name].some((s) => s.toLowerCase().includes(q)),
    );
  }, [cases, query]);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Cases</h1>
          <p className="text-sm text-muted-foreground">
            Open a case to watch the agent work, replay a stored run, or review its draft.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <SearchIcon className="absolute top-2 left-2 size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter cases"
              aria-label="Filter cases"
              className="w-56 pl-8"
            />
          </div>
          <NewCaseDialog />
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded-xl border bg-background">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Case</th>
              <th className="px-3 py-2 font-medium">Service</th>
              <th className="hidden px-3 py-2 font-medium md:table-cell">Plan</th>
              <th className="px-3 py-2 text-right font-medium">Runs</th>
              <th className="px-3 py-2 font-medium">Latest run</th>
            </tr>
          </thead>
          <tbody>
            {!cases &&
              !error &&
              Array.from({ length: 8 }, (_, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td colSpan={5} className="px-3 py-2">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </tr>
              ))}
            {shown.map((c) => (
              <tr key={c.case_id} className="border-b last:border-0 hover:bg-muted/40">
                <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                  <Link href={`/cases/${c.case_id}`} className="hover:underline">
                    {c.case_id}
                  </Link>
                  {c.source === "user" && (
                    <Badge variant="outline" className="ml-2">
                      yours
                    </Badge>
                  )}
                </td>
                <td className="px-3 py-2">
                  <Link href={`/cases/${c.case_id}`} className="hover:underline">
                    {c.title}
                  </Link>
                </td>
                <td className="hidden px-3 py-2 text-muted-foreground md:table-cell">
                  {c.plan_name}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{c.run_count}</td>
                <td className="px-3 py-2">
                  {c.latest_status ? (
                    <StatusBadge status={c.latest_status} />
                  ) : (
                    <span className="text-xs text-muted-foreground">Not run yet</span>
                  )}
                </td>
              </tr>
            ))}
            {cases && shown.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                  {`No cases match "${query}".`}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
