"""Startup recovery: jobs stranded in active states become failed with a
clear, user-facing message instead of sitting "processing" forever (or
vanishing as "Job not found" after a restart wiped the database).

Uses an isolated SQLiteJobStore per test so the shared app state is untouched.
"""

from __future__ import annotations

from datetime import timedelta

from audioapp.core.store import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    SQLiteJobStore,
    recover_interrupted_jobs,
    utcnow,
)


def _make_store(tmp_path):
    return SQLiteJobStore(tmp_path / "jobs.db")


def _make_job(store, status: str) -> str:
    up = store.create_upload(
        filename="mix.wav", size_bytes=123, meta={}, path="/tmp/mix.wav",
        expires_at=utcnow() + timedelta(hours=1),
    )
    job = store.create_job(
        upload_id=up["id"], mode="convert", model=None, stems=None,
        export={"format": "mp3"}, expires_at=utcnow() + timedelta(hours=1),
    )
    store.update_job(job["id"], status=status)
    return job["id"]


def test_recovery_marks_every_active_state_failed(tmp_path):
    store = _make_store(tmp_path)
    ids = [_make_job(store, s) for s in ACTIVE_STATES]

    n = recover_interrupted_jobs(store)

    assert n == len(ACTIVE_STATES)
    for jid in ids:
        job = store.get_job(jid)
        assert job["status"] == "failed"
        assert job["error"]["code"] == "server_restarted"
        assert "restarted" in job["error"]["message"]
        assert job["stage_detail"] == job["error"]["message"]


def test_recovery_leaves_terminal_jobs_alone(tmp_path):
    store = _make_store(tmp_path)
    ids = [_make_job(store, s) for s in TERMINAL_STATES]

    n = recover_interrupted_jobs(store)

    assert n == 0
    for jid, status in zip(ids, TERMINAL_STATES):
        assert store.get_job(jid)["status"] == status


def test_recovery_empty_store_is_noop(tmp_path):
    assert recover_interrupted_jobs(_make_store(tmp_path)) == 0
