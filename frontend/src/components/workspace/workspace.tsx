"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Skeleton } from "@/components/ui/skeleton";
import { useRunStream } from "@/hooks/use-run-stream";
import {
  api,
  type CaseDetail,
  type EvidenceInfo,
  type ModelOption,
  type RunSummary,
} from "@/lib/api";
import { citedIds } from "@/lib/format";
import { DocumentsPanel, type DocTab } from "./documents-panel";
import { DraftPanel } from "./draft-panel";
import { FindingsPanel } from "./findings-panel";
import { RunPanel } from "./run-panel";

function Box({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border bg-background p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function Workspace({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [evidence, setEvidence] = useState<Map<string, EvidenceInfo>>(new Map());
  const [liveEnabled, setLiveEnabled] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [streamOpts, setStreamOpts] = useState({ replay: false, speed: 1, nonce: 0 });
  const stream = useRunStream(runId, streamOpts);

  const [tab, setTab] = useState<DocTab>("letter");
  const [focus, setFocus] = useState<{ chunkId: string; n: number } | null>(null);
  const [draftText, setDraftText] = useState("");

  const refreshRuns = useCallback(
    () =>
      api.caseRuns(caseId).then(setRuns, (e: Error) => toast.error(e.message)),
    [caseId],
  );

  useEffect(() => {
    api.case(caseId).then(setDetail, (e: Error) => setLoadError(e.message));
    api.caseRuns(caseId).then((list) => {
      setRuns(list);
      setRunId((current) => current ?? list[0]?.id ?? null);
    }, () => {});
    api.models().then(setModels, () => {});
    api.evidence().then((list) => setEvidence(new Map(list.map((e) => [e.id, e]))), () => {});
    api.health().then((h) => setLiveEnabled(h.live_runs), () => {});
  }, [caseId]);

  // Refresh run statuses when a stream finishes (e.g. a live run completed).
  useEffect(() => {
    if (stream.status === "done") void refreshRuns();
  }, [stream.status, refreshRuns]);

  const onCite = useCallback((chunkId: string) => {
    setTab("plan");
    setFocus((f) => ({ chunkId, n: (f?.n ?? 0) + 1 }));
  }, []);

  const onCitedChange = useCallback((text: string) => setDraftText(text), []);

  async function startLive(model: string) {
    try {
      const { run_id } = await api.startRun(caseId, model);
      setRunId(run_id);
      setStreamOpts((o) => ({ replay: false, speed: o.speed, nonce: o.nonce + 1 }));
      void refreshRuns();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const finished = stream.status === "done" ? stream.run : null;
  const findings = finished?.findings ?? null;
  const citedInLetter = useMemo(
    () => (finished?.letter ? citedIds(draftText) : []),
    [finished?.letter, draftText],
  );

  if (loadError) {
    return (
      <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
        {loadError}
      </p>
    );
  }
  if (!detail) return <Skeleton className="h-[70vh] w-full" />;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Link href="/" className="text-muted-foreground hover:text-foreground" aria-label="Back to cases">
          <ArrowLeftIcon className="size-4" />
        </Link>
        <h1 className="text-lg font-semibold tracking-tight">{detail.title}</h1>
        <span className="font-mono text-xs text-muted-foreground">{detail.case_id}</span>
        <span className="text-xs text-muted-foreground">{detail.plan_name}</span>
      </div>

      <div className="grid gap-3 lg:h-[calc(100vh-8.5rem)] lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)_minmax(0,3.5fr)]">
        <div className="min-h-[60vh] lg:min-h-0">
          <DocumentsPanel
            detail={detail}
            findings={findings}
            retrieved={finished?.retrieved ?? []}
            citedInLetter={citedInLetter}
            tab={tab}
            onTab={setTab}
            focus={focus}
            onCite={onCite}
          />
        </div>

        <div className="min-h-0 space-y-3 overflow-y-auto pr-1">
          {!runId && (
            <Box title="Findings">
              <p className="text-sm text-muted-foreground">
                No runs yet. Start a live run to watch the agent work through this case.
              </p>
            </Box>
          )}
          {runId && !finished && (
            <Box title="Findings">
              <p className="text-sm text-muted-foreground">
                {stream.status === "error"
                  ? "The run did not finish."
                  : "The agent's findings appear here when the run finishes."}
              </p>
            </Box>
          )}
          {finished && !findings && (
            <Box title="Findings">
              <p className="text-sm text-muted-foreground">
                This run ended without findings ({finished.status}
                {finished.error ? `: ${finished.error}` : ""}).
              </p>
            </Box>
          )}
          {findings && (
            <Box title="Findings">
              <FindingsPanel findings={findings} evidence={evidence} onCite={onCite} />
            </Box>
          )}
          {finished?.letter && (
            <Box title="Appeal letter">
              <DraftPanel
                key={finished.id}
                runId={finished.id}
                caseId={caseId}
                onCite={onCite}
                onCitedChange={onCitedChange}
              />
            </Box>
          )}
          {findings && !finished?.letter && (
            <Box title="Appeal letter">
              <p className="text-sm text-muted-foreground">
                No letter: the agent judged this appeal unlikely to succeed. See the findings for
                why.
              </p>
            </Box>
          )}
        </div>

        <div className="min-h-[50vh] lg:min-h-0">
          <RunPanel
            runs={runs}
            selectedRunId={runId}
            onSelect={(id) => {
              setRunId(id);
              setStreamOpts((o) => ({ replay: false, speed: o.speed, nonce: o.nonce + 1 }));
            }}
            stream={stream}
            replaying={streamOpts.replay}
            models={models}
            liveEnabled={liveEnabled}
            onStartLive={startLive}
            onReplay={(speed) => setStreamOpts((o) => ({ replay: true, speed, nonce: o.nonce + 1 }))}
          />
        </div>
      </div>
    </div>
  );
}
