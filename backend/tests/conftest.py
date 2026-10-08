"""Shared fixtures and helpers for the audioapp test suite.

IMPORTANT: the app reads its AUDIOAPP_* settings at import time, so the
test environment is configured here BEFORE `audioapp.main` is imported.
Unit tests never touch torch: the FakeAdapter below writes stems with the
stdlib `wave` module only (the real Demucs path is gated separately in
test_integration_real_model.py).
"""

from __future__ import annotations

import array
import math
import os
import sys
import tempfile
import time
import wave
from pathlib import Path

# Make `audioapp` importable (src layout) regardless of the CWD pytest runs from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# --- test-only environment (must precede the audioapp import) ------------
# NOTE: tmp_path_factory is unavailable at import time, so an isolated
# mkdtemp dir is used instead; every run gets a fresh data dir.
os.environ.setdefault("AUDIOAPP_DATA_DIR", tempfile.mkdtemp(prefix="audioapp-test-data-"))
os.environ["AUDIOAPP_MAX_UPLOAD_MB"] = "10"
os.environ["AUDIOAPP_MAX_DURATION_S"] = "60"
os.environ["AUDIOAPP_RESULTS_TTL_HOURS"] = "1"
os.environ["AUDIOAPP_UPLOAD_TTL_HOURS"] = "1"
os.environ["AUDIOAPP_SEPARATOR_WORKERS"] = "1"
os.environ["AUDIOAPP_MAX_RETRIES"] = "1"
os.environ["AUDIOAPP_RETENTION_SWEEP_S"] = "3600"
os.environ["AUDIOAPP_LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from audioapp.main import app  # noqa: E402
from audioapp.models.base import SeparatorAdapter  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "realmodel: gated test that downloads + runs the real Demucs checkpoint"
    )


# --- Fake separator (stdlib wave only, no torch) --------------------------

TERMINAL_STATES = {"completed", "failed", "cancelled", "expired"}


def attenuate_frames(frames: bytes, factor: float) -> bytes:
    """Scale 16-bit PCM frames by `factor` (clipped)."""
    n = len(frames) // 2
    src = array.array("h")
    src.frombytes(frames[: n * 2])
    dst = array.array(
        "h", (max(-32768, min(32767, int(s * factor))) for s in src)
    )
    return dst.tobytes()


class FakeAdapter(SeparatorAdapter):
    """Test double: copies the input WAV per requested stem, slightly attenuated."""

    name = "fake"

    def __init__(self, factor: float = 0.9):
        self.factor = factor

    @property
    def stems(self) -> list[str]:
        return ["drums", "bass", "other", "vocals"]

    def separate(self, input_wav, out_dir, stems=None, is_cancelled=None, on_stage=None):
        if on_stage:
            on_stage("Fake separating…")
        want = list(stems or self.stems)
        out_dir.mkdir(parents=True, exist_ok=True)
        with wave.open(str(input_wav), "rb") as r:
            params = r.getparams()
            frames = r.readframes(r.getnframes())
        scaled = attenuate_frames(frames, self.factor)
        result = {}
        for stem in want:
            dst = out_dir / f"{stem}.wav"
            with wave.open(str(dst), "wb") as w:
                w.setparams(params)
                w.writeframes(scaled)
            result[stem] = dst
        return result


@pytest.fixture(autouse=True)
def _use_fake_adapter(monkeypatch):
    """Route every job through the FakeAdapter unless a test overrides it."""
    monkeypatch.setattr(
        app.state.app_state, "get_adapter", lambda model_id: FakeAdapter()
    )


@pytest.fixture(scope="session")
def client():
    """TestClient with the app lifespan (retention sweeper, worker queue) active."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def app_state():
    return app.state.app_state


# --- helpers --------------------------------------------------------------

def make_wav(path, seconds: float = 3.0, sr: int = 44100,
             channels: int = 2, freq: float = 440.0) -> Path:
    """Write a PCM sine WAV with the stdlib `wave` module."""
    path = Path(path)
    nframes = int(seconds * sr)
    period = max(1, int(sr / freq))
    one = array.array(
        "h", (int(16000 * math.sin(2 * math.pi * freq * i / sr)) for i in range(period))
    )
    data = array.array("h")
    while len(data) < nframes:
        data.extend(one)
    raw = data[:nframes].tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(raw * channels)  # duplicate mono tone across channels
    return path


def upload_file(client, path, filename: str | None = None,
                rights_confirmed: str | None = "true"):
    """POST a file to /api/v1/uploads. rights_confirmed=None omits the field."""
    path = Path(path)
    data = {}
    if rights_confirmed is not None:
        data["rights_confirmed"] = rights_confirmed
    with open(path, "rb") as f:
        return client.post(
            "/api/v1/uploads",
            files={"file": (filename or path.name, f, "application/octet-stream")},
            data=data,
        )


def create_job(client, upload_id: str, mode: str = "vocal_instrumental",
               export: dict | None = None, **kwargs):
    payload: dict = {"upload_id": upload_id, "mode": mode}
    if export is not None:
        payload["export"] = export
    payload.update(kwargs)
    return client.post("/api/v1/jobs", json=payload)


def wait_for_job(client, job_id: str, timeout: float = 90) -> dict:
    """Poll GET /jobs/{id} until a terminal state (raises on timeout)."""
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        r = client.get(f"/api/v1/jobs/{job_id}")
        assert r.status_code == 200, r.text
        last = r.json()
        if last["status"] in TERMINAL_STATES:
            return last
        time.sleep(0.25)
    status = last["status"] if last else None
    raise AssertionError(f"job {job_id} not terminal within {timeout}s (last={status})")


def error_code(response) -> str | None:
    try:
        return response.json()["detail"]["code"]
    except Exception:
        return None
