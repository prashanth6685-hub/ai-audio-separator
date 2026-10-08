"""Job lifecycle API tests (FakeAdapter: fast, no torch)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest

from tests.conftest import (
    FakeAdapter,
    create_job,
    error_code,
    make_wav,
    upload_file,
    wait_for_job,
)


@pytest.fixture()
def uploaded(client, tmp_path):
    """A fresh 5s upload per test."""
    p = make_wav(tmp_path / "mix.wav", seconds=5.0)
    r = upload_file(client, p)
    assert r.status_code == 201, r.text
    return r.json()


def _complete_job(client, upload_id, **kwargs) -> str:
    r = create_job(client, upload_id, **kwargs)
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]
    job = wait_for_job(client, job_id)
    assert job["status"] == "completed", job.get("error")
    return job_id


def _results(client, job_id) -> list[dict]:
    r = client.get(f"/api/v1/jobs/{job_id}/results")
    assert r.status_code == 200, r.text
    return r.json()["outputs"]


# --- full transition ----------------------------------------------------

def test_full_flow_vocal_instrumental_mp3(client, uploaded):
    r = create_job(client, uploaded["upload_id"],
                   mode="vocal_instrumental", export={"format": "mp3"})
    assert r.status_code == 201, r.text
    job_id = r.json()["job_id"]

    job = wait_for_job(client, job_id, timeout=90)
    assert job["status"] == "completed"

    outputs = _results(client, job_id)
    assert len(outputs) == 2
    assert {o["stem"] for o in outputs} == {"vocals", "instrumental"}

    for o in outputs:
        assert o["download_url"].startswith(f"/api/v1/jobs/{job_id}/download/")
        d = client.get(o["download_url"])
        assert d.status_code == 200
        assert int(d.headers["content-length"]) > 0
        assert abs(o["duration_s"] - 5.0) < 0.5  # duration preserved end-to-end


# --- modes ---------------------------------------------------------------

@pytest.mark.parametrize(
    "mode,expected",
    [
        ("karaoke", {"instrumental"}),
        ("instruments", {"drums", "bass", "other"}),
        ("convert", {"converted"}),
    ],
)
def test_modes_output_sets(client, uploaded, mode, expected):
    job_id = _complete_job(client, uploaded["upload_id"], mode=mode)
    assert {o["stem"] for o in _results(client, job_id)} == expected


def test_custom_stems(client, uploaded):
    job_id = _complete_job(
        client, uploaded["upload_id"], mode="custom", stems=["vocals", "drums"]
    )
    assert {o["stem"] for o in _results(client, job_id)} == {"vocals", "drums"}


def test_custom_bogus_stem_rejected(client, uploaded):
    r = create_job(client, uploaded["upload_id"],
                   mode="custom", stems=["vocals", "guitar"])
    assert r.status_code == 400


# --- invalid requests -----------------------------------------------------

def test_invalid_mode(client, uploaded):
    r = create_job(client, uploaded["upload_id"], mode="nope")
    assert r.status_code == 400
    assert error_code(r) == "invalid_mode"


@pytest.mark.parametrize(
    "export,code",
    [
        ({"format": "xyz"}, "invalid_format"),
        ({"format": "mp3", "bitrate_kbps": 999}, "invalid_bitrate"),
        ({"format": "wav", "sample_rate": 12345}, "invalid_sample_rate"),
    ],
)
def test_invalid_export_settings(client, uploaded, export, code):
    r = create_job(client, uploaded["upload_id"],
                   mode="vocal_instrumental", export=export)
    assert r.status_code == 400
    assert error_code(r) == code


def test_unknown_upload_id(client):
    r = create_job(client, "upl_doesnotexist", mode="vocal_instrumental")
    assert r.status_code == 404
    assert error_code(r) == "upload_not_found"


def test_unknown_job(client):
    r = client.get("/api/v1/jobs/job_doesnotexist")
    assert r.status_code == 404
    assert error_code(r) == "job_not_found"


# --- cancel / delete -------------------------------------------------------

def test_cancel_processing_job(client, tmp_path, monkeypatch, app_state):
    class SlowFake(FakeAdapter):
        def separate(self, *a, **k):
            time.sleep(5)
            return super().separate(*a, **k)

    monkeypatch.setattr(app_state, "get_adapter", lambda model_id: SlowFake())
    p = make_wav(tmp_path / "mix.wav", seconds=3.0)
    r = upload_file(client, p)
    assert r.status_code == 201, r.text
    r = create_job(client, r.json()["upload_id"], mode="vocal_instrumental")
    job_id = r.json()["job_id"]

    # wait until the worker is actually inside separate()
    deadline = time.time() + 30
    while time.time() < deadline:
        st = client.get(f"/api/v1/jobs/{job_id}").json()["status"]
        if st == "processing":
            break
        time.sleep(0.2)
    else:
        pytest.fail("job never reached processing state")

    r = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    job = wait_for_job(client, job_id)
    assert job["status"] == "cancelled"

    # let the worker thread drain so it cannot block the 1-worker queue
    handle = app_state.queue.get_handle(job_id)
    assert handle is not None
    handle.future.result(timeout=20)


def test_delete_job(client, uploaded, app_state):
    job_id = _complete_job(client, uploaded["upload_id"])
    job_dir = app_state.jobs_dir / job_id
    assert job_dir.exists()

    r = client.delete(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert not job_dir.exists()


# --- downloads --------------------------------------------------------------

def test_download_unknown_output_404(client, uploaded):
    job_id = _complete_job(client, uploaded["upload_id"])
    r = client.get(f"/api/v1/jobs/{job_id}/download/out_nope")
    assert r.status_code == 404


def test_download_missing_file_410(client, uploaded, app_state):
    job_id = _complete_job(client, uploaded["upload_id"])
    output_id = _results(client, job_id)[0]["output_id"]
    rec = app_state.store.get_output(job_id, output_id)
    assert rec is not None
    Path(rec["path"]).unlink()  # simulate the file being gone from disk

    r = client.get(f"/api/v1/jobs/{job_id}/download/{output_id}")
    assert r.status_code == 410


# --- retention ---------------------------------------------------------------

def test_retention_sweep_expires_upload(client, tmp_path, app_state):
    from audioapp.core import retention
    from audioapp.core.store import utcnow

    p = make_wav(tmp_path / "mix.wav", seconds=2.0)
    r = upload_file(client, p)
    assert r.status_code == 201, r.text
    upload_id = r.json()["upload_id"]
    rec = app_state.store.get_upload(upload_id)
    assert rec is not None

    # white-box: backdate the expiry
    past = (utcnow() - timedelta(hours=2)).isoformat()
    app_state.store._conn.execute(
        "UPDATE uploads SET expires_at=? WHERE id=?", (past, upload_id)
    )
    app_state.store._conn.commit()

    res = retention.sweep_once(app_state.store, app_state.jobs_dir, app_state.uploads_dir)
    assert res["expired_uploads"] == 1
    assert not Path(rec["path"]).exists()
    assert app_state.store.get_upload(upload_id) is None


# --- concurrency / listing / meta --------------------------------------------

def test_concurrent_uploads(client, tmp_path):
    paths = [make_wav(tmp_path / f"c{i}.wav", seconds=2.0) for i in range(5)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(lambda p: upload_file(client, p), paths))
    assert all(r.status_code == 201 for r in results), \
        [r.status_code for r in results]


def test_jobs_list_contains_created(client, uploaded):
    job_id = _complete_job(client, uploaded["upload_id"], mode="karaoke")
    ids = [j["job_id"] for j in client.get("/api/v1/jobs").json()]
    assert job_id in ids


def test_models_lists_htdemucs(client):
    models = {m["id"]: m for m in client.get("/api/v1/models").json()["models"]}
    assert set(models["htdemucs"]["stems"]) == {"drums", "bass", "other", "vocals"}


def test_health(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok"
    assert h["ffmpeg"] is True
    assert h["queue"]["max_workers"] == 1
