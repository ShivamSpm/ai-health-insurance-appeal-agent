"""API tests with a scripted model. No LLM calls."""

import json
import threading
import time

import pytest
from fakes import perfect_model
from fastapi.testclient import TestClient

from appeal_agent.api.app import create_app
from appeal_agent.config import model

LETTER = (
    "**Re: Notice of Adverse Benefit Determination**\n\n"
    "| | |\n|---|---|\n| Service | Knee MRI (CPT 73721) |\n\n"
    "The MRI is denied because prior authorization was not obtained."
)


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APPEAL_USER_CASES_DIR", str(tmp_path / "user_cases"))

    def make(complete=None, **kwargs) -> TestClient:
        app = create_app(tmp_path / "runs.db", complete=complete or perfect_model([]), **kwargs)
        return TestClient(app)

    return make


def events(client: TestClient, url: str, headers: dict | None = None) -> list[tuple[str, dict]]:
    """Read a whole SSE stream into (event, data) pairs."""
    out, event = [], None
    with client.stream("GET", url, headers=headers or {}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        for line in resp.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                out.append((event, json.loads(line[6:])))
    return out


def wait_done(client: TestClient, run_id: str, timeout: float = 20) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        if resp.status_code == 200 and resp.json()["status"] != "running":
            return resp.json()
        time.sleep(0.05)
    raise TimeoutError(run_id)


# ---------------- Cases ----------------


def test_list_and_get_dataset_cases_without_labels(make_client):
    client = make_client()
    listed = client.get("/api/cases").json()
    assert len(listed) == 40 and listed[0]["case_id"] == "case-001"
    assert listed[0]["source"] == "dataset" and listed[0]["run_count"] == 0
    assert "labels" not in json.dumps(listed) and "hard_kind" not in json.dumps(listed)

    case = client.get("/api/cases/case-013").json()
    assert case["plan_name"] == "Halcyon Ridge Bronze HMO"
    assert case["title"] == "Colonoscopy with polyp removal (CPT 45385)"
    assert "screening" in case["denial_letter"]
    assert any(s["chunk_id"] == "hmo-4.1" for s in case["plan_sections"])


def test_unknown_or_unsafe_case_ids_are_404(make_client):
    client = make_client()
    for case_id in ["case-999", "..%2F..%2Fsecrets", "user-zz", "case-01"]:
        assert client.get(f"/api/cases/{case_id}").status_code == 404, case_id


def test_create_user_case(make_client):
    client = make_client()
    resp = client.post(
        "/api/cases", json={"plan_id": "ppo", "denial_letter": LETTER, "member_note": "Hi."}
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["case_id"].startswith("user-") and created["source"] == "user"
    assert created["title"] == "Knee MRI (CPT 73721)"

    case = client.get(f"/api/cases/{created['case_id']}").json()
    assert case["denial_letter"] == LETTER and case["member_note"] == "Hi."
    assert case["plan_sections"][0]["chunk_id"].startswith("ppo-")
    assert len(client.get("/api/cases").json()) == 41

    titled = client.post(
        "/api/cases", json={"plan_id": "epo", "denial_letter": LETTER, "title": "My MRI"}
    ).json()
    assert titled["title"] == "My MRI"


def test_create_user_case_validates_input(make_client):
    client = make_client()
    assert (
        client.post("/api/cases", json={"plan_id": "xyz", "denial_letter": LETTER}).status_code
        == 422
    )
    assert (
        client.post("/api/cases", json={"plan_id": "ppo", "denial_letter": "short"}).status_code
        == 422
    )


# ---------------- Runs ----------------


def test_live_run_end_to_end(make_client):
    client = make_client()
    resp = client.post("/api/cases/case-031/runs", json={})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    run = wait_done(client, run_id)
    assert run["status"] == "completed" and run["model"] == model("agent")
    assert run["findings"]["denial_types"] == ["prior_authorization"]
    assert run["letter"] and run["steps"][0]["kind"] == "llm"
    assert "denial-triage" in run["loaded_skills"]

    listed = client.get("/api/cases/case-031/runs").json()
    assert [r["id"] for r in listed] == [run_id]
    case = next(c for c in client.get("/api/cases").json() if c["case_id"] == "case-031")
    assert case["run_count"] == 1 and case["latest_status"] == "completed"


def test_runs_check_model_and_live_switch(make_client):
    client = make_client()
    assert client.post("/api/cases/case-031/runs", json={"model": "other/model"}).status_code == 400
    assert client.post("/api/cases/case-999/runs", json={}).status_code == 404
    cheap = client.post("/api/cases/case-031/runs", json={"model": model("agent_cheap")})
    assert cheap.status_code == 202
    wait_done(client, cheap.json()["run_id"])
    assert make_client(live_runs=False).post("/api/cases/case-031/runs", json={}).status_code == 403


def test_event_stream_tails_a_live_run(make_client):
    gate = threading.Event()
    script = perfect_model([])

    def gated(*args):
        gate.wait(10)  # hold the run until the stream is open
        return script(*args)

    client = make_client(complete=gated)
    run_id = client.post("/api/cases/case-031/runs", json={}).json()["run_id"]
    threading.Timer(0.5, gate.set).start()
    got = events(client, f"/api/runs/{run_id}/events")

    kinds = [e for e, _ in got]
    assert kinds[0] == "run" and got[0][1]["status"] == "running"
    assert kinds[-1] == "done" and got[-1][1]["status"] == "completed"
    steps = [d for e, d in got if e == "step"]
    assert [s["idx"] for s in steps] == list(range(1, len(steps) + 1))
    assert len(steps) == len(client.get(f"/api/runs/{run_id}").json()["steps"])
    assert got[-1][1]["findings"]["appeal_viable"] is True


def test_replay_and_resume_of_a_finished_run(make_client):
    client = make_client()
    run_id = client.post("/api/cases/case-040/runs", json={}).json()["run_id"]
    stored = wait_done(client, run_id)["steps"]

    replayed = events(client, f"/api/runs/{run_id}/events?replay=true&speed=100")
    assert [d["idx"] for e, d in replayed if e == "step"] == [s["idx"] for s in stored]
    assert replayed[-1][0] == "done" and replayed[-1][1]["letter"]

    # A reconnecting browser sends Last-Event-ID and gets only the steps after it.
    resumed = events(client, f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "3"})
    assert [d["idx"] for e, d in resumed if e == "step"][0] == 4


def test_unknown_run(make_client):
    client = make_client()
    assert client.get("/api/runs/nope").status_code == 404


def test_evidence_vocabulary(make_client):
    vocab = make_client().get("/api/evidence").json()
    assert len(vocab) == 16
    assert {"id": "eob", "name": "Explanation of Benefits"}.items() <= next(
        v for v in vocab if v["id"] == "eob"
    ).items()


# ---------------- Drafts ----------------


def test_draft_versions(make_client):
    client = make_client()
    run_id = client.post("/api/cases/case-031/runs", json={}).json()["run_id"]
    agent_letter = wait_done(client, run_id)["letter"]

    drafts = client.get(f"/api/runs/{run_id}/drafts").json()
    assert drafts == [
        {
            "version": 0,
            "source": "agent",
            "text": agent_letter,
            "created_at": drafts[0]["created_at"],
        }
    ]
    for text in ["Edited once.", "Edited twice."]:
        saved = client.post(f"/api/runs/{run_id}/drafts", json={"text": text})
        assert saved.status_code == 201
    drafts = client.get(f"/api/runs/{run_id}/drafts").json()
    assert [(d["version"], d["source"]) for d in drafts] == [(0, "agent"), (1, "user"), (2, "user")]
    assert drafts[-1]["text"] == "Edited twice."
    assert client.post(f"/api/runs/{run_id}/drafts", json={"text": ""}).status_code == 422


def test_cors_allows_the_frontend(make_client):
    client = make_client()
    resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    resp = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
