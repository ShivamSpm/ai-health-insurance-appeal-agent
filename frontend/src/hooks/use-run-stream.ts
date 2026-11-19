"use client";

import { useEffect, useState } from "react";

import { eventsUrl, type RunSummary, type Step } from "@/lib/api";

export type StreamStatus = "idle" | "connecting" | "streaming" | "done" | "error";

export interface RunStream {
  status: StreamStatus;
  run: RunSummary | null; // the final summary (findings, letter) arrives with `done`
  steps: Step[];
  error: string | null;
}

const IDLE: RunStream = { status: "idle", run: null, steps: [], error: null };
const CONNECTING: RunStream = { ...IDLE, status: "connecting" };

/**
 * Follow a run over server-sent events. The same stream serves a live run (tails
 * SQLite until the run finishes), a finished run (all steps at once) and a paced
 * replay. `nonce` restarts the stream, e.g. to replay again.
 */
export function useRunStream(
  runId: string | null,
  { replay, speed, nonce }: { replay: boolean; speed: number; nonce: number },
): RunStream {
  // State is tagged with the stream it belongs to, so a new stream starts fresh
  // without resetting state inside the effect.
  const key = runId ? `${runId}|${replay}|${speed}|${nonce}` : null;
  const [state, setState] = useState<{ key: string | null; stream: RunStream }>({
    key: null,
    stream: IDLE,
  });

  useEffect(() => {
    if (!runId || !key) return;
    const update = (fn: (s: RunStream) => RunStream) =>
      setState((prev) => ({ key, stream: fn(prev.key === key ? prev.stream : CONNECTING) }));
    const data = (e: Event) => JSON.parse((e as MessageEvent).data);
    const source = new EventSource(eventsUrl(runId, replay, speed));

    source.addEventListener("run", (e) => {
      const run = data(e) as RunSummary;
      // Findings and the letter are only shown once the stream reaches `done`.
      update((s) => ({ ...s, status: "streaming", run: { ...run, findings: null, letter: null } }));
    });
    source.addEventListener("step", (e) => {
      const step = data(e) as Step;
      update((s) =>
        s.steps.some((x) => x.idx === step.idx) ? s : { ...s, steps: [...s.steps, step] },
      );
    });
    source.addEventListener("done", (e) => {
      source.close();
      update((s) => ({ ...s, status: "done", run: data(e) as RunSummary }));
    });
    source.addEventListener("stream_error", (e) => {
      source.close();
      update((s) => ({ ...s, status: "error", error: (data(e) as { message: string }).message }));
    });
    // Connection problems: EventSource retries by itself (resuming with Last-Event-ID).
    // Only report an error once it has given up.
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        update((s) => ({ ...s, status: "error", error: "Lost the connection to the API." }));
      }
    };
    return () => source.close();
  }, [key, runId, replay, speed]);

  if (!key) return IDLE;
  return state.key === key ? state.stream : CONNECTING;
}
