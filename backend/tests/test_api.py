from datetime import datetime

import app.pipeline as pipeline_mod
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Segment, StoredNotes, Transcript
from app.storage import MeetingStorage
from tests.conftest import FakeLLM, FakeTranscriber


def _client(test_settings, monkeypatch):
    captured = {}

    def fake_run(meeting_id, store, transcriber, llm, llm_model, vad_trim, **kw):
        captured["ran"] = {"meeting_id": meeting_id, "vad_trim": vad_trim}

    monkeypatch.setattr("app.main.get_transcriber", lambda s: FakeTranscriber())
    monkeypatch.setattr("app.main.get_chat_model", lambda s: FakeLLM())
    monkeypatch.setattr("app.main.run_pipeline", fake_run)
    app = create_app(test_settings)
    return TestClient(app), captured


def _seed_done_meeting(test_settings):
    store = MeetingStorage(test_settings.data_dir)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)
    job = store.load_job(mid)
    job.status = job.status.__class__("done")
    job.percent = 100
    store.save_job(job)
    store.save_transcript(Transcript(
        meeting_id=mid, source_file="a.mp4", duration_sec=10, provider="fake",
        created_at=datetime(2026, 6, 15), speakers=["Speaker 1"],
        segments=[Segment(id=0, speaker="Speaker 1", start=0, end=4, text="Budget approved.")],
    ))
    store.save_notes(StoredNotes(
        summary="A summary.", meeting_id=mid, model="claude-test",
        generated_at=datetime(2026, 6, 15),
    ))
    store.save_notes_markdown(mid, "# a.mp4 — Notes\n")
    return store, mid


# --- upload ---

def test_upload_returns_meeting_id_and_schedules_pipeline(test_settings, monkeypatch):
    client, captured = _client(test_settings, monkeypatch)
    resp = client.post(
        "/meetings",
        files={"file": ("meeting.mp4", b"bytes", "video/mp4")},
        data={"vad_trim": "true"},
    )
    assert resp.status_code == 200
    mid = resp.json()["meeting_id"]
    assert mid
    assert captured["ran"]["meeting_id"] == mid
    assert captured["ran"]["vad_trim"] is True


def test_upload_rejects_unsupported_extension(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    resp = client.post(
        "/meetings",
        files={"file": ("notes.txt", b"bytes", "text/plain")},
        data={"vad_trim": "false"},
    )
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


# --- status and results ---

def test_status_404_for_unknown(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    assert client.get("/meetings/nope/status").status_code == 404


def test_get_meeting_returns_transcript_and_notes(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    resp = client.get(f"/meetings/{mid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"]["summary"] == "A summary."
    assert body["transcript"]["segments"][0]["text"] == "Budget approved."


def test_get_meeting_409_when_not_done(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    store = MeetingStorage(test_settings.data_dir)
    mid = store.create_meeting("a.mp4", b"x", vad_trim=False)  # still pending
    assert client.get(f"/meetings/{mid}").status_code == 409


# --- Q&A ---

def test_ask_appends_and_returns_answer(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    resp = client.post(f"/meetings/{mid}/ask", json={"question": "Was budget approved?"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "A fake answer."
    qa = client.get(f"/meetings/{mid}/qa").json()
    assert len(qa) == 1 and qa[0]["question"] == "Was budget approved?"


def test_ask_requires_question(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    assert client.post(f"/meetings/{mid}/ask", json={"question": "  "}).status_code == 400


def test_notes_markdown_endpoint(test_settings, monkeypatch):
    client, _ = _client(test_settings, monkeypatch)
    _store, mid = _seed_done_meeting(test_settings)
    resp = client.get(f"/meetings/{mid}/notes.md")
    assert resp.status_code == 200
    assert resp.text.startswith("# a.mp4 — Notes")
