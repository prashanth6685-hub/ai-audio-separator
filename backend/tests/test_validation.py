"""Upload validation tests via POST /api/v1/uploads."""

from __future__ import annotations

import os
import subprocess

import pytest

from tests.conftest import error_code, make_wav, upload_file

# (label, ffmpeg encoder or None for raw wav, filename ext, expected ffprobe codec)
FORMATS = [
    ("wav", None, ".wav", "pcm_s16le"),
    ("mp3", "libmp3lame", ".mp3", "mp3"),
    ("flac", "flac", ".flac", "flac"),
    ("ogg", "libvorbis", ".ogg", "vorbis"),
    ("opus", "libopus", ".opus", "opus"),
    ("m4a", "aac", ".m4a", "aac"),
]


@pytest.mark.parametrize("label,encoder,ext,codec", FORMATS)
def test_supported_format_accepted(client, tmp_path, label, encoder, ext, codec):
    """Every supported container/codec uploads with 201 (encoder-dependent skips)."""
    src = make_wav(tmp_path / "base.wav", seconds=2.0)
    if encoder is None:
        target, name = src, f"tone{ext}"
    else:
        target = tmp_path / f"tone{ext}"
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:a", encoder, str(target)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            pytest.skip(f"ffmpeg encoder '{encoder}' unavailable: {proc.stderr[-200:]}")
        name = f"tone{ext}"
    r = upload_file(client, target, filename=name)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["meta"]["codec_name"] == codec
    assert body["meta"]["duration_s"] == pytest.approx(2.0, abs=0.2)


def test_unsupported_text_file_rejected(client, tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("this is plain text, not audio")
    r = upload_file(client, p)
    assert r.status_code == 400
    assert error_code(r) in {"unsupported_codec", "unreadable_file"}


def test_corrupted_wav_rejected(client, tmp_path):
    src = make_wav(tmp_path / "tone.wav", seconds=2.0)
    bad = tmp_path / "bad.wav"
    data = bytearray(src.read_bytes())
    data[0:4] = b"XXXX"  # smash the RIFF magic: genuinely unreadable
    bad.write_bytes(bytes(data))
    r = upload_file(client, bad)
    assert r.status_code == 400
    assert error_code(r) in {"unsupported_codec", "unreadable_file"}


@pytest.mark.xfail(
    strict=True,
    reason="BY DESIGN: a header-intact truncated file passes ffprobe (it trusts the "
           "header duration), so upload accepts it; the pipeline then fails the job "
           "gracefully at decode time. Rejecting it at upload would require a full "
           "decode of every file.",
)
def test_truncated_wav_rejected(client, tmp_path):
    src = make_wav(tmp_path / "tone.wav", seconds=5.0)
    trunc = tmp_path / "trunc.wav"
    trunc.write_bytes(src.read_bytes()[:200])  # valid header, missing data
    r = upload_file(client, trunc)
    assert r.status_code == 400


def test_zero_byte_rejected(client, tmp_path):
    p = tmp_path / "empty.wav"
    p.write_bytes(b"")
    r = upload_file(client, p)
    assert r.status_code == 400
    assert error_code(r) == "empty_file"


def test_oversized_rejected(client, tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(os.urandom(11 * 1024 * 1024))  # over the 10 MB test limit
    r = upload_file(client, p)
    assert r.status_code == 413
    assert error_code(r) == "file_too_large"


def test_too_long_rejected(client, tmp_path, app_state):
    p = make_wav(tmp_path / "long.wav", seconds=5.0)
    settings = app_state.settings
    old = settings.max_duration_s
    settings.max_duration_s = 2
    try:
        r = upload_file(client, p)
    finally:
        settings.max_duration_s = old
    assert r.status_code == 400
    assert error_code(r) == "too_long"


@pytest.mark.parametrize("rights", ["false", None])
def test_rights_not_confirmed(client, tmp_path, rights):
    p = make_wav(tmp_path / "tone.wav", seconds=2.0)
    r = upload_file(client, p, rights_confirmed=rights)
    assert r.status_code == 400
    assert error_code(r) == "rights_not_confirmed"


def test_wrong_extension_warns(client, tmp_path):
    """The real codec must win over the extension (and ideally warn)."""
    p = make_wav(tmp_path / "tone.wav", seconds=2.0)
    r = upload_file(client, p, filename="song.mp3")
    assert r.status_code == 201
    body = r.json()
    assert body["meta"]["codec_name"] == "pcm_s16le"  # real codec, not the .mp3 hint
    assert body["warnings"], "expected a warning that the extension mismatches the codec"


def test_unrecognized_extension_warns(client, tmp_path):
    p = make_wav(tmp_path / "tone.wav", seconds=2.0)
    r = upload_file(client, p, filename="song.zzz9")
    assert r.status_code == 201
    assert r.json()["warnings"], "expected a warning for the unknown extension"
