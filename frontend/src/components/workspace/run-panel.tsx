"use client";

import {
  BookOpenIcon,
  BrainIcon,
  CalculatorIcon,
  FileTextIcon,
  PlayIcon,
  RotateCcwIcon,
  SearchIcon,
  SendIcon,
  WrenchIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { RunStream } from "@/hooks/use-run-stream";
import type { ModelOption, RunSummary, Step } from "@/lib/api";
import { money, seconds, shortModel, tokens, when } from "@/lib/format";
import { cn } from "@/lib/utils";

const SPEEDS = [
  { value: 1, label: "1x" },
  { value: 4, label: "4x" },
  { value: 16, label: "16x" },
];

function parse(json: string | null): Record<string, unknown> {
  try {
    return JSON.parse(json ?? "{}");
  } catch {
    return {};
  }
}

/** One line describing what a tool call did, e.g. search_policy "prior authorization". */
function toolSummary(step: Step): string {
  const a = parse(step.input);
  switch (step.name) {
    case "load_skill":
      return String(a.name ?? "");
    case "read_skill_file":
      return `${a.name}/${a.path}`;
    case "search_policy":
      return `"${a.query}"`;
    case "get_section":
      return String(a.chunk_id ?? "");
    case "date_calc":
      return `${a.start_date} + ${a.add_days} days`;
    default:
      return "";
  }
}

const TOOL_ICON: Record<string, typeof WrenchIcon> = {
  load_skill: BookOpenIcon,
  read_skill_file: BookOpenIcon,
  search_policy: SearchIcon,
  get_section: FileTextIcon,
  get_denial_letter: FileTextIcon,
  get_member_note: FileTextIcon,
  date_calc: CalculatorIcon,
  submit_findings: SendIcon,
  submit_appeal_letter: SendIcon,
};

function StepRow({ step }: { step: Step }) {
  if (step.kind === "llm") {
    const out = parse(step.output) as {
      tool_calls?: { name: string }[];
      content?: string | null;
    };
    const calls = out.tool_calls?.map((c) => c.name) ?? [];
    return (
      <li className="flex gap-2 py-1.5">
        <BrainIcon className="mt-0.5 size-4 shrink-0 text-violet-600" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
            <span className="font-medium">Model</span>
            <span className="text-muted-foreground tabular-nums">
              {seconds(step.latency_ms)} · {tokens(step.prompt_tokens)} in (
              {tokens(step.cached_tokens)} cached) / {tokens(step.completion_tokens)} out ·{" "}
              {money(step.cost_usd, 4)}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            {calls.length ? `calls ${calls.join(", ")}` : out.content ? "replied with text" : ""}
          </div>
        </div>
      </li>
    );
  }
  const Icon = TOOL_ICON[step.name ?? ""] ?? WrenchIcon;
  return (
    <li className="py-1.5">
      <details className="group">
        <summary className="flex cursor-pointer list-none gap-2">
          <Icon className={cn("mt-0.5 size-4 shrink-0", step.invalid ? "text-red-600" : "text-sky-700")} />
          <div className="min-w-0 flex-1 text-xs">
            <span className="font-mono font-medium">{step.name}</span>{" "}
            <span className="text-muted-foreground">{toolSummary(step)}</span>
            {step.invalid && (
              <Badge variant="destructive" className="ml-1 h-4 text-[10px]">
                rejected
              </Badge>
            )}
          </div>
        </summary>
        <pre className="mt-1 ml-6 max-h-56 overflow-auto rounded-md bg-muted p-2 text-[11px] leading-4 whitespace-pre-wrap">
          {step.output}
        </pre>
      </details>
    </li>
  );
}

export function RunPanel({
  runs,
  selectedRunId,
  onSelect,
  stream,
  replaying,
  models,
  liveEnabled,
  onStartLive,
  onReplay,
}: {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  stream: RunStream;
  replaying: boolean;
  models: ModelOption[];
  liveEnabled: boolean;
  onStartLive: (model: string) => void;
  onReplay: (speed: number) => void;
}) {
  const [model, setModel] = useState<string | null>(null);
  const [speed, setSpeed] = useState(4);
  const list = useRef<HTMLOListElement>(null);
  const chosenModel = model ?? models[0]?.id ?? null;
  const busy = stream.status === "connecting" || stream.status === "streaming";
  const live = stream.run?.status === "running";

  const llm = stream.steps.filter((s) => s.kind === "llm");
  const total = (k: "prompt_tokens" | "cached_tokens" | "completion_tokens") =>
    llm.reduce((n, s) => n + (s[k] ?? 0), 0);
  const cost = llm.reduce((n, s) => n + (s.cost_usd ?? 0), 0);
  const modelMs = llm.reduce((n, s) => n + (s.latency_ms ?? 0), 0);
  // Follow the newest step while a run streams in.
  useEffect(() => {
    if (busy) list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [stream.steps.length, busy]);

  const skills = stream.steps
    .filter((s) => s.name === "load_skill" && !s.invalid)
    .map((s) => String(parse(s.input).name));

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="space-y-2 rounded-xl border bg-background p-3">
        <div className="text-xs font-medium text-muted-foreground">Run</div>
        {runs.length > 0 ? (
          <Select
            items={runs.map((r) => ({
              value: r.id,
              label: `${when(r.started_at)} · ${shortModel(r.model)}`,
            }))}
            value={selectedRunId}
            onValueChange={(v) => v && onSelect(String(v))}
          >
            <SelectTrigger className="w-full" aria-label="Run">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {runs.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {when(r.started_at)} · {shortModel(r.model)} · {r.status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <p className="text-sm text-muted-foreground">No runs yet for this case.</p>
        )}
        <div className="flex items-center gap-1.5">
          <Select
            items={SPEEDS}
            value={speed}
            onValueChange={(v) => v && setSpeed(Number(v))}
          >
            <SelectTrigger size="sm" aria-label="Replay speed">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SPEEDS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            variant="outline"
            disabled={!selectedRunId || live || busy}
            onClick={() => onReplay(speed)}
          >
            <RotateCcwIcon />
            Replay
          </Button>
        </div>
        <div className="flex items-center gap-1.5 border-t pt-2">
          <Select
            items={models.map((m) => ({ value: m.id, label: shortModel(m.id) }))}
            value={chosenModel}
            onValueChange={(v) => v && setModel(String(v))}
          >
            <SelectTrigger size="sm" className="min-w-0 flex-1" aria-label="Model">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {models.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {shortModel(m.id)} {m.role === "agent_cheap" ? "(cheaper)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            disabled={!liveEnabled || !chosenModel || busy}
            onClick={() => chosenModel && onStartLive(chosenModel)}
          >
            <PlayIcon />
            Run live
          </Button>
        </div>
        <p className="text-[11px] text-muted-foreground">
          {liveEnabled
            ? "A live run calls the model and costs a few cents."
            : "Live runs are turned off on this server; replay a stored run."}
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col rounded-xl border bg-background p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="text-xs font-medium text-muted-foreground">Timeline</div>
          {stream.run && (
            <StatusBadge
              status={busy ? "running" : stream.run.status}
              label={busy ? (live ? "Running" : replaying ? "Replaying" : "Loading") : undefined}
            />
          )}
        </div>
        {stream.steps.length > 0 && (
          <div className="mb-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs tabular-nums">
            <span className="text-muted-foreground">LLM calls</span>
            <span>{llm.length}</span>
            <span className="text-muted-foreground">Tokens in / out</span>
            <span>
              {tokens(total("prompt_tokens"))} / {tokens(total("completion_tokens"))}
            </span>
            <span className="text-muted-foreground">Cached input</span>
            <span>
              {total("prompt_tokens")
                ? `${Math.round((100 * total("cached_tokens")) / total("prompt_tokens"))}%`
                : "0%"}
            </span>
            <span className="text-muted-foreground">Cost</span>
            <span>{money(cost, 4)}</span>
            <span className="text-muted-foreground">Model time</span>
            <span>{seconds(modelMs)}</span>
          </div>
        )}
        {skills.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1">
            {skills.map((s) => (
              <Badge key={s} variant="outline" className="text-[11px]">
                {s}
              </Badge>
            ))}
          </div>
        )}
        {stream.error && <p className="mb-2 text-xs text-destructive">{stream.error}</p>}
        <ol
          ref={list}
          className="min-h-0 flex-1 divide-y overflow-y-auto pr-1"
          aria-label="Agent steps"
        >
          {stream.steps.map((s) => (
            <StepRow key={s.idx} step={s} />
          ))}
          {busy && (
            <li className="py-1.5 text-xs text-muted-foreground">
              {live ? "Waiting for the model..." : "..."}
            </li>
          )}
        </ol>
      </div>
    </div>
  );
}
