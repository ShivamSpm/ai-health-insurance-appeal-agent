"""FastAPI app for the review UI.

Run it with `uv run appeal-agent serve` (or `uvicorn appeal_agent.api.app:create_app --factory`).

Live runs execute in a small thread pool and write their steps to SQLite, exactly
like CLI and eval runs. The event stream tails SQLite, so live runs and replays of
stored runs share one code path, a reload resumes the stream (Last-Event-ID), and
nothing is lost if the browser disconnects.
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from appeal_agent import cases
from appeal_agent.agent.loop import Complete, new_run_id, openai_complete, run_case
from appeal_agent.agent.policy import parse_plan
from appeal_agent.agent.scripted import scripted_model
from appeal_agent.api.models import (
    CaseDetail,
    CaseSummary,
    DraftVersion,
    EvidenceInfo,
    ModelOption,
    NewCase,
    NewDraft,
    PlanSection,
    RunDetail,
    RunSummary,
    StartRun,
    Step,
)
from appeal_agent.config import model, settings
from appeal_agent.dataset.plans import PLANS
from appeal_agent.domain import EVIDENCE
from appeal_agent.store import Store

log = logging.getLogger(__name__)


def _sse(event: str, data: dict, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(
    store_path: Path | None = None,
    complete: Complete | None = None,
    live_runs: bool | None = None,
) -> FastAPI:
    cfg = settings()["api"]
    # APPEAL_FAKE_MODEL=1 swaps in the scripted model (no LLM calls), for UI tests.
    fake_model = complete is None and os.environ.get("APPEAL_FAKE_MODEL") == "1"
    if complete is None:
        complete = scripted_model() if fake_model else openai_complete
    live_runs = cfg["live_runs"] if live_runs is None else live_runs
    origins = os.environ.get("APPEAL_CORS_ORIGINS")
    executor = ThreadPoolExecutor(max_workers=cfg["run_workers"], thread_name_prefix="run")

    app = FastAPI(title="Appeal Agent API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins.split(",") if origins else cfg["cors_origins"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    def get_store() -> Iterator[Store]:
        store = Store(store_path)
        try:
            yield store
        finally:
            store.close()

    StoreDep = Annotated[Store, Depends(get_store)]

    def case_or_404(case_id: str):
        try:
            return cases.load_case(case_id)
        except cases.UnknownCase:
            raise HTTPException(404, f"No case {case_id}") from None

    def run_or_404(store: Store, run_id: str):
        row = store.get_run(run_id)
        if row is None:
            raise HTTPException(404, f"No run {run_id}")
        return row

    def models() -> list[ModelOption]:
        priced = settings().get("pricing", {})
        return [
            ModelOption(id=model(role), role=role, priced=model(role) in priced)
            for role in ("agent", "agent_cheap")
        ]

    # ---------------- Cases ----------------

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "live_runs": live_runs, "fake_model": fake_model}

    @app.get("/api/evidence")
    def list_evidence() -> list[EvidenceInfo]:
        return [EvidenceInfo(id=e.id, name=e.name, description=e.description) for e in EVIDENCE]

    @app.get("/api/models")
    def list_models() -> list[ModelOption]:
        return models()

    @app.get("/api/cases")
    def list_cases(store: StoreDep) -> list[CaseSummary]:
        counts = store.run_counts()
        out = []
        for case_id in cases.dataset_case_ids() + cases.user_case_ids():
            case = cases.load_case(case_id)
            letter, _, _ = cases.read_inputs(case)
            n, latest = counts.get(case_id, (0, None))
            out.append(
                CaseSummary(
                    case_id=case_id,
                    source=cases.source(case_id),
                    plan_id=case.plan_id,
                    plan_name=PLANS[case.plan_id].name,
                    title=cases.title(case_id, letter),
                    run_count=n,
                    latest_status=latest,
                )
            )
        return out

    @app.post("/api/cases", status_code=201)
    def create_case(body: NewCase) -> CaseSummary:
        case_id = cases.create_user_case(
            body.plan_id, body.denial_letter, body.member_note, body.title
        )
        return CaseSummary(
            case_id=case_id,
            source="user",
            plan_id=body.plan_id,
            plan_name=PLANS[body.plan_id].name,
            title=cases.title(case_id, body.denial_letter),
            run_count=0,
            latest_status=None,
        )

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str) -> CaseDetail:
        case = case_or_404(case_id)
        letter, note, plan_md = cases.read_inputs(case)
        return CaseDetail(
            case_id=case_id,
            source=cases.source(case_id),
            plan_id=case.plan_id,
            plan_name=PLANS[case.plan_id].name,
            title=cases.title(case_id, letter),
            denial_letter=letter,
            member_note=note,
            plan_sections=[
                PlanSection(
                    chunk_id=s.chunk_id, number=s.number, title=s.title, page=s.page, text=s.text
                )
                for s in parse_plan(plan_md, case.plan_id)
            ],
        )

    # ---------------- Runs ----------------

    @app.get("/api/cases/{case_id}/runs")
    def list_case_runs(case_id: str, store: StoreDep) -> list[RunSummary]:
        case_or_404(case_id)
        return [RunSummary.from_row(r) for r in store.runs_for_case(case_id)]

    def _work(case_id: str, model_id: str, run_id: str) -> None:
        store = Store(store_path)
        try:
            run_case(case_id, model_id, store, complete=complete, run_id=run_id)
        except Exception:  # run_case already recorded the error on the run
            log.exception("run %s failed", run_id)
        finally:
            store.close()

    @app.post("/api/cases/{case_id}/runs", status_code=202)
    def start_run(case_id: str, body: StartRun) -> dict:
        if not live_runs:
            raise HTTPException(403, "Live runs are disabled; replay a stored run instead.")
        case_or_404(case_id)
        allowed = {m.id for m in models()}
        model_id = body.model or model("agent")
        if model_id not in allowed:
            raise HTTPException(400, f"Model must be one of {sorted(allowed)}")
        run_id = new_run_id(case_id)
        executor.submit(_work, case_id, model_id, run_id)
        return {"run_id": run_id}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, store: StoreDep) -> RunDetail:
        row = run_or_404(store, run_id)
        return RunDetail(
            **RunSummary.from_row(row).model_dump(),
            steps=[Step.from_row(s) for s in store.get_steps(run_id)],
        )

    @app.get(
        "/api/runs/{run_id}/events",
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {}}}},
    )
    async def run_events(
        run_id: str,
        replay: bool = Query(False, description="Replay a finished run at its recorded pace."),
        speed: float = Query(1.0, gt=0, le=100, description="Replay speed multiplier."),
        last_event_id: Annotated[int | None, Header()] = None,
    ) -> StreamingResponse:
        """Server-sent events: `run` (summary), `step` (one per step, id = step index),
        then `done` (final summary with findings and letter) or `stream_error`.
        (Not `error`: EventSource uses that name for its own connection errors.)"""
        return StreamingResponse(
            _events(run_id, replay, speed, last_event_id or 0),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _events(run_id: str, replay: bool, speed: float, after: int) -> AsyncIterator[str]:
        store = Store(store_path)
        try:
            # A live run's row appears once its worker starts.
            row = store.get_run(run_id)
            for _ in range(int(30 / cfg["poll_s"])):
                if row is not None:
                    break
                await asyncio.sleep(cfg["poll_s"])
                row = store.get_run(run_id)
            if row is None:
                yield _sse("stream_error", {"message": f"No run {run_id}"})
                return
            yield _sse("run", RunSummary.from_row(row).model_dump(mode="json"))

            if replay and row["status"] != "running":
                for s in store.steps_after(run_id, after):
                    pause = (s["latency_ms"] or 0) / 1000 if s["kind"] == "llm" else 0.15
                    await asyncio.sleep(min(pause, cfg["replay_max_step_s"]) / speed)
                    yield _sse("step", Step.from_row(s).model_dump(mode="json"), s["idx"])
                yield _sse("done", RunSummary.from_row(row).model_dump(mode="json"))
                return

            last, last_change, last_ping = after, time.monotonic(), time.monotonic()
            while True:
                new = store.steps_after(run_id, last)
                for s in new:
                    yield _sse("step", Step.from_row(s).model_dump(mode="json"), s["idx"])
                    last = s["idx"]
                row = store.get_run(run_id)
                if row["status"] != "running":
                    for s in store.steps_after(run_id, last):  # written just before finishing
                        yield _sse("step", Step.from_row(s).model_dump(mode="json"), s["idx"])
                    yield _sse("done", RunSummary.from_row(row).model_dump(mode="json"))
                    return
                now = time.monotonic()
                if new:
                    last_change = now
                elif now - last_change > cfg["stale_after_s"]:
                    yield _sse("stream_error", {"message": "The run stopped making progress."})
                    return
                if now - last_ping > 15:  # keep proxies from closing an idle stream
                    yield ": ping\n\n"
                    last_ping = now
                await asyncio.sleep(cfg["poll_s"])
        finally:
            store.close()

    # ---------------- Draft versions ----------------

    @app.get("/api/runs/{run_id}/drafts")
    def list_drafts(run_id: str, store: StoreDep) -> list[DraftVersion]:
        row = run_or_404(store, run_id)
        out = []
        if row["letter"]:
            out.append(
                DraftVersion(
                    version=0, source="agent", text=row["letter"], created_at=row["finished_at"]
                )
            )
        out += [
            DraftVersion(
                version=d["version"], source="user", text=d["text"], created_at=d["created_at"]
            )
            for d in store.drafts(run_id)
        ]
        return out

    @app.post("/api/runs/{run_id}/drafts", status_code=201)
    def save_draft(run_id: str, body: NewDraft, store: StoreDep) -> DraftVersion:
        row = run_or_404(store, run_id)
        if not row["letter"]:
            raise HTTPException(409, "This run has no appeal letter to edit.")
        d = store.add_draft(run_id, body.text)
        return DraftVersion(
            version=d["version"], source="user", text=d["text"], created_at=d["created_at"]
        )

    return app
