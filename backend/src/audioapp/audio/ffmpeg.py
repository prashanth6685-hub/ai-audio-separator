"""Safe ffmpeg/ffprobe wrappers.

Security rules enforced here:
- subprocess is NEVER run with shell=True.
- Command lines are built as argument lists from constants + internally
  generated paths (uuid hex names). User-supplied filenames are never
  interpolated into commands; they are only used for display / output naming
  after strict sanitization.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


class FFmpegError(RuntimeError):
    pass


class ProbeError(RuntimeError):
    pass


@dataclass
class AudioMeta:
    format_name: str
    codec_name: str
    duration_s: float
    sample_rate: int
    channels: int
    bit_depth: int | None = None
    bit_rate: int | None = None


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    if not cmd or not cmd[0]:
        raise FFmpegError("ffmpeg/ffprobe binary not found on PATH")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise FFmpegError(f"media tool timed out: {' '.join(cmd[:2])}") from e
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-2000:]
        raise FFmpegError(f"media tool failed ({' '.join(cmd[:2])}): {tail}")
    return proc


def probe_audio(path: Path) -> AudioMeta:
    """Inspect the ACTUAL container/codec with ffprobe (not the extension)."""
    if FFPROBE is None:
        raise ProbeError("ffprobe not found on PATH")
    cmd = [
        FFPROBE, "-v", "error",
        "-show_entries", "format=format_name,duration,bit_rate",
        "-show_entries", "stream=index,codec_name,codec_type,sample_rate,channels,bits_per_sample",
        "-of", "json", str(path),
    ]
    proc = _run(cmd, timeout=60)
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ProbeError("could not parse media metadata") from e
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        raise ProbeError("no audio stream found in file")
    s = streams[0]
    fmt = info.get("format", {})
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise ProbeError("could not determine audio duration (file may be corrupted)")
    try:
        sample_rate = int(s.get("sample_rate") or 0)
        channels = int(s.get("channels") or 0)
    except (TypeError, ValueError):
        sample_rate, channels = 0, 0
    if sample_rate <= 0 or channels <= 0:
        raise ProbeError("invalid audio stream parameters")
    bits = s.get("bits_per_sample")
    bit_depth = int(bits) if bits else None
    bit_rate = int(fmt["bit_rate"]) if fmt.get("bit_rate") else None
    return AudioMeta(
        format_name=str(fmt.get("format_name") or "unknown"),
        codec_name=str(s.get("codec_name") or "unknown"),
        duration_s=duration,
        sample_rate=sample_rate,
        channels=channels,
        bit_depth=bit_depth,
        bit_rate=bit_rate,
    )


def decode_to_wav(src: Path, dst: Path, sample_rate: int = 44100, channels: int = 2) -> Path:
    """Decode any supported input to PCM WAV for the model. Overwrites dst."""
    cmd = [
        FFMPEG, "-v", "error", "-y",
        "-i", str(src),
        "-ar", str(sample_rate), "-ac", str(channels),
        "-c:a", "pcm_s16le",
        str(dst),
    ]
    _run(cmd, timeout=600)
    return dst


def mix_stems(inputs: list[Path], dst: Path) -> Path:
    """Mix N stem WAVs into one (used for karaoke/instrumental mixes).

    Uses amix with normalize=0 so levels are preserved, not auto-normalized.
    """
    if not inputs:
        raise FFmpegError("no stems to mix")
    if len(inputs) == 1:
        # plain copy re-encode to keep pipeline uniform
        cmd = [FFMPEG, "-v", "error", "-y", "-i", str(inputs[0]), "-c:a", "pcm_s16le", str(dst)]
        _run(cmd, timeout=600)
        return dst
    cmd = [FFMPEG, "-v", "error", "-y"]
    for p in inputs:
        cmd += ["-i", str(p)]
    cmd += [
        "-filter_complex",
        f"amix=inputs={len(inputs)}:duration=longest:dropout_transition=0:normalize=0",
        "-c:a", "pcm_s16le",
        str(dst),
    ]
    _run(cmd, timeout=600)
    return dst


# Export format → ffmpeg encoder + extension
EXPORT_FORMATS: dict[str, dict] = {
    "mp3": {"encoder": "libmp3lame", "ext": "mp3", "kind": "lossy"},
    "wav": {"encoder": "pcm_s16le", "ext": "wav", "kind": "lossless"},
    "flac": {"encoder": "flac", "ext": "flac", "kind": "lossless"},
    "ogg": {"encoder": "libvorbis", "ext": "ogg", "kind": "lossy"},
    "m4a": {"encoder": "aac", "ext": "m4a", "kind": "lossy"},
}

MP3_BITRATES = (128, 192, 320)
OGG_QUALITIES = tuple(range(0, 11))  # q0..q10


def encode_audio(
    src: Path,
    dst: Path,
    fmt: str,
    bitrate_kbps: int | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    ogg_quality: int | None = None,
) -> Path:
    """Encode a WAV stem to the requested export format. Overwrites dst."""
    spec = EXPORT_FORMATS.get(fmt)
    if spec is None:
        raise FFmpegError(f"unsupported export format: {fmt}")
    cmd = [FFMPEG, "-v", "error", "-y", "-i", str(src)]
    if sample_rate:
        cmd += ["-ar", str(int(sample_rate))]
    if channels:
        cmd += ["-ac", str(int(channels))]
    cmd += ["-c:a", spec["encoder"]]
    if fmt == "mp3":
        cmd += ["-b:a", f"{int(bitrate_kbps or 192)}k"]
    elif fmt == "ogg":
        q = int(ogg_quality if ogg_quality is not None else 5)
        cmd += ["-q:a", str(max(0, min(10, q)))]
    elif fmt == "m4a":
        cmd += ["-b:a", f"{int(bitrate_kbps or 192)}k"]
    elif fmt == "flac":
        cmd += ["-compression_level", "5"]
    cmd.append(str(dst))
    _run(cmd, timeout=900)
    return dst


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Make a user-supplied name safe for download filenames (display only)."""
    base = Path(name).stem  # strip any directories / extension games
    safe = "".join(c if (c.isalnum() or c in ("-", "_", " ", ".")) else "_" for c in base)
    safe = "_".join(safe.split())  # collapse whitespace
    return (safe or "audio")[:max_len]
