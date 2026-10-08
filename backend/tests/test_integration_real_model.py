"""Real-model integration test (gated).

Proves the genuine DemucsAdapter runs end-to-end: 4 stems come out, each one
decodes, and duration/channels/integrity are preserved. Deliberately does NOT
assert separation quality.

Skipped by default. Run with:
    RUN_REAL_MODEL_TESTS=1 .venv/bin/python -m pytest -q tests/test_integration_real_model.py
"""

from __future__ import annotations

import array
import math
import os
import subprocess
import wave
from pathlib import Path

import pytest

from audioapp.audio.ffmpeg import decode_to_wav, probe_audio

pytestmark = [
    pytest.mark.realmodel,
    pytest.mark.skipif(
        os.environ.get("RUN_REAL_MODEL_TESTS") != "1",
        reason="gated: set RUN_REAL_MODEL_TESTS=1 to download + run the real Demucs model",
    ),
]


def _make_mix(path: Path, seconds: int = 8) -> Path:
    """Synthesize a license-clean 8s stereo mix: 110 Hz + 440 Hz + pink noise."""
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=110:duration={seconds}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}:sample_rate=44100",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={seconds}:sample_rate=44100:amplitude=0.12",
        "-filter_complex",
        "[0:a][1:a][2:a]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,volume=0.6[a]",
        "-map", "[a]", "-ac", "2", "-ar", "44100", str(path),
    ]
    subprocess.run(cmd, check=True)
    return path


def _rms(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
    a = array.array("h")
    a.frombytes(frames[: len(frames) // 2 * 2])
    if not a:
        return 0.0
    return math.sqrt(sum(s * s for s in a) / len(a))


def test_real_demucs_end_to_end(tmp_path):
    # torch-heavy import stays inside the gated test; unit tests never import it.
    from audioapp.models.demucs_adapter import DemucsAdapter

    mix = _make_mix(tmp_path / "mix.wav", seconds=8)
    normalized = tmp_path / "normalized.wav"
    decode_to_wav(mix, normalized)

    adapter = DemucsAdapter(model_id="htdemucs", device="cpu")
    stems = adapter.separate(normalized, tmp_path / "stems")

    assert set(stems) == {"drums", "bass", "other", "vocals"}

    src = probe_audio(normalized)
    rms_by_stem = {}
    for name, stem_path in stems.items():
        assert stem_path.exists() and stem_path.stat().st_size > 0, name
        meta = probe_audio(stem_path)
        assert abs(meta.duration_s - src.duration_s) < 0.5, (name, meta.duration_s)
        assert meta.channels == 2, name
        rms_by_stem[name] = _rms(stem_path)
    # Integrity, not quality: the mix's energy must survive end-to-end in at
    # least one stem. Individual stems may legitimately be near-silent (this
    # synthetic mix has no vocal-like content, so Demucs correctly leaves the
    # vocals stem ~empty) -- that is good separation, not a broken pipeline.
    assert max(rms_by_stem.values()) > 500, rms_by_stem
    # NOTE: separation quality is intentionally NOT asserted here.
