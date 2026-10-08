"""Worker pipeline tests: retry, permanent failure, queue stats.

All adapters here are FakeAdapter subclasses (no torch).
"""

from __future__ import annotations

import pytest

from tests.conftest import FakeAdapter, create_job, make_wav, upload_file, wait_for_job


def _upload(client, tmp_path, name: str = "mix.wav", seconds: float = 3.0) -> str:
    p = make_wav(tmp_path / name, seconds=seconds)
    r = upload_file(client, p)
    assert r.status_code == 201, r.text
    return r.json()["upload_id"]


def test_retry_then_success(client, tmp_path, monkeypatch, app_state):
    calls = {"n": 0}

    class Flaky(FakeAdapter):
        def separate(self, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("simulated transient failure")
            return super().separate(*a, **k)

    monkeypatch.setattr(app_state, "get_adapter", lambda model_id: Flaky())
    upload_id = _upload(client, tmp_path)

    r = create_job(client, upload_id, mode="vocal_instrumental")
    assert r.status_code == 201, r.text
    job = wait_for_job(client, r.json()["job_id"])

    assert job["status"] == "completed"
    assert calls["n"] == 2  # first attempt failed, retried once (MAX_RETRIES=1)


def test_permanent_failure(client, tmp_path, monkeypatch, app_state):
    class AlwaysFail(FakeAdapter):
        def separate(self, *a, **k):
            raise RuntimeError("simulated permanent failure")

    monkeypatch.setattr(app_state, "get_adapter", lambda model_id: AlwaysFail())
    upload_id = _upload(client, tmp_path)

    r = create_job(client, upload_id, mode="vocal_instrumental")
    assert r.status_code == 201, r.text
    job = wait_for_job(client, r.json()["job_id"])

    assert job["status"] == "failed"
    assert job["error"]["code"] == "processing_failed"
    assert "could not be processed" in job["error"]["message"]  # human-readable


def test_queue_stats(client):
    queue = client.get("/api/v1/health").json()["queue"]
    assert queue["max_workers"] == 1
