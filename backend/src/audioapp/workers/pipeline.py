"""Job pipeline: validating -> queued -> processing -> encoding -> completed.

Runs inside the worker thread. All stage updates go through the JobStore so
the frontend can poll without holding an HTTP request open.

Honesty rules: progress is stage-based (measurable=false) unless the model
reports real fractions; errors carry stable codes + human messages.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

from audioapp.audio.ffmpeg import (
    EXPORT_FORMATS,
    FFmpegError,
    decode_to_wav,
    encode_audio,
    mix_stems,
    probe_audio,
    sanitize_filename,
)
from audioapp.audio.validate import ValidationError
from audioapp.core.state import AppState
from audioapp.core.store import TERMINAL_STATES
from audioapp.models.base import SeparatorAdapter
from audioapp.models.demucs_adapter import _Cancelled
from audioapp.models.registry import MODES, output_plan, stems_for_mode

log = logging.getLogger(__name__)

STAGE_MESSAGES = {
    "validating": "Your audio is being validated.",
    "queued": "Your file is waiting for an available processor.",
    "processing": "Separating vocals and instruments…",
    "encoding": "Preparing your download.",
}


def _set(state: AppState, job_id: str, status: str, message: str = "") -> None:
    state.store.update_job(
        job_id,
        status=status,
        stage_detail=message or STAGE_MESSAGES.get(status, ""),
        progress_json={"measurable": False, "message": message or STAGE_MESSAGES.get(status, "")},
    )


def _fail(state: AppState, job_id: str, code: str, message: str) -> None:
    log.warning("job %s failed: %s: %s", job_id, code, message)
    state.store.update_job(
        job_id,
        status="failed",
        stage_detail=message,
        error_json={"code": code, "message": message},
    )


def _cancelled(cancel_event: threading.Event) -> bool:
    return cancel_event.is_set()


def _cleanup_workdir(workdir: Path, keep: set[Path]) -> None:
    for p in workdir.iterdir():
        if p not in keep and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def run_job(state: AppState, job_id: str, cancel_event: threading.Event) -> None:
    settings = state.settings
    attempt = 0
    while True:
        attempt += 1
        try:
            _run_once(state, job_id, cancel_event)
            return
        except _Cancelled:
            _cleanup_job_dir(state, job_id)
            state.store.update_job(job_id, status="cancelled",
                                   stage_detail="The job was cancelled.")
            log.info("job %s cancelled", job_id)
            return
        except ValidationError as e:
            _fail(state, job_id, e.code, e.message)
            return
        except Exception as e:  # noqa: BLE001 - pipeline must never die silently
            if _cancelled(cancel_event):
                _cleanup_job_dir(state, job_id)
                state.store.update_job(job_id, status="cancelled",
                                       stage_detail="The job was cancelled.")
                return
            if attempt <= settings.max_retries:
                log.warning("job %s attempt %d failed, retrying: %s", job_id, attempt, e)
                _set(state, job_id, "queued", "Retrying after a processing hiccup…")
                continue
            _fail(state, job_id, "processing_failed",
                  "The audio could not be processed. Please try another file.")
            return


def _cleanup_job_dir(state: AppState, job_id: str) -> None:
    job_dir = state.jobs_dir / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)


def _run_once(state: AppState, job_id: str, cancel_event: threading.Event) -> None:
    settings = state.settings
    store = state.store
    job = store.get_job(job_id)
    if job is None:
        log.error("job %s not found in store", job_id)
        return
    if job["status"] in TERMINAL_STATES:
        return

    job_dir = state.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    workdir = job_dir / "work"
    workdir.mkdir(exist_ok=True)

    upload = store.get_upload(job["upload_id"])
    if upload is None or not Path(upload["path"]).exists():
        raise ValidationError("upload_missing",
                              "The uploaded file is no longer available. Please upload it again.")

    mode: str = job["mode"]
    export: dict = job["export"]
    fmt: str = export["format"]

    # ---- validating -------------------------------------------------
    _set(state, job_id, "validating")
    if _cancelled(cancel_event):
        raise _Cancelled()
    normalized = workdir / "normalized.wav"
    try:
        decode_to_wav(Path(upload["path"]), normalized)
        probe_audio(normalized)
    except Exception as e:
        raise ValidationError("unreadable_file",
                              "This file could not be decoded. It may be corrupted.") from e

    # ---- processing (separation) ------------------------------------
    final_wavs: dict[str, Path] = {}  # output key -> wav path
    if mode == "convert":
        _set(state, job_id, "processing", "Converting audio (no AI separation)…")
        final_wavs["converted"] = normalized
        plans = [{"stem": "converted", "label": "Converted audio", "source_stems": []}]
    else:
        model_id = job["model"] or settings.demucs_model
        stems, _needs = stems_for_mode(mode, model_id, job.get("stems"))
        _set(state, job_id, "processing")
        adapter: SeparatorAdapter = state.get_adapter(model_id)
        separated = adapter.separate(
            normalized, workdir / "stems", stems,
            is_cancelled=cancel_event.is_set,
            on_stage=lambda msg: _set(state, job_id, "processing", msg),
        )
        plans = output_plan(mode, model_id, {s: s for s in separated})
        for plan in plans:
            key = plan["stem"]
            if len(plan["source_stems"]) == 1:
                final_wavs[key] = separated[plan["source_stems"][0]]
            else:
                mix_path = workdir / f"{key}.wav"
                mix_stems([separated[s] for s in plan["source_stems"]], mix_path)
                final_wavs[key] = mix_path

    if _cancelled(cancel_event):
        raise _Cancelled()

    # ---- encoding ----------------------------------------------------
    _set(state, job_id, "encoding")
    ext = EXPORT_FORMATS[fmt]["ext"]
    bitrate = export.get("bitrate_kbps")
    if fmt in ("mp3", "m4a") and not bitrate:
        bitrate = 192
    keep: set[Path] = set()
    for plan in plans:
        if _cancelled(cancel_event):
            raise _Cancelled()
        key = plan["stem"]
        out_path = job_dir / f"{key}.{ext}"
        _set(state, job_id, "encoding", f"Encoding {plan['label']}…")
        try:
            encode_audio(
                final_wavs[key], out_path, fmt,
                bitrate_kbps=bitrate,
                sample_rate=export.get("sample_rate"),
                channels=export.get("channels"),
                ogg_quality=export.get("ogg_quality"),
            )
        except FFmpegError as e:
            raise RuntimeError(f"encoding failed for {plan['label']}") from e
        meta = probe_audio(out_path)
        output_id = f"out_{key}"
        store.add_output(
            job_id, output_id=output_id, kind="mix" if key in ("instrumental", "converted") else "stem",
            stem=key, label=plan["label"], fmt=fmt, path=str(out_path),
            size_bytes=out_path.stat().st_size, duration_s=meta.duration_s,
            sample_rate=meta.sample_rate, channels=meta.channels,
            bitrate_kbps=bitrate if fmt in ("mp3", "m4a") else None,
        )
        keep.add(out_path)

    _cleanup_workdir(workdir, keep=set())
    # keep final outputs; drop intermediate wavs
    _set(state, job_id, "completed", "Done — your files are ready.")
    log.info("job %s completed: mode=%s outputs=%d", job_id, mode, len(plans))


def validate_export_settings(export: dict) -> dict:
    """Validate + normalize export settings. Raises ValidationError."""
    fmt = str(export.get("format", "")).lower()
    if fmt not in EXPORT_FORMATS:
        raise ValidationError("invalid_format",
                              f"Unsupported export format '{export.get('format')}'. "
                              f"Choose from: {', '.join(sorted(EXPORT_FORMATS))}.")
    out = {"format": fmt}
    bitrate = export.get("bitrate_kbps")
    if fmt in ("mp3", "m4a"):
        b = int(bitrate or 192)
        if b not in (128, 192, 320):
            raise ValidationError("invalid_bitrate", "Bitrate must be 128, 192, or 320 kbps.")
        out["bitrate_kbps"] = b
    sr = export.get("sample_rate")
    if sr is not None:
        sr = int(sr)
        if sr not in (22050, 32000, 44100, 48000):
            raise ValidationError("invalid_sample_rate",
                                  "Sample rate must be 22050, 32000, 44100, or 48000 Hz.")
        out["sample_rate"] = sr
    ch = export.get("channels")
    if ch is not None:
        ch = int(ch)
        if ch not in (1, 2):
            raise ValidationError("invalid_channels", "Channels must be 1 (mono) or 2 (stereo).")
        out["channels"] = ch
    q = export.get("ogg_quality")
    if q is not None:
        q = int(q)
        if not 0 <= q <= 10:
            raise ValidationError("invalid_quality", "OGG quality must be 0–10.")
        out["ogg_quality"] = q
    name = export.get("filename")
    if name:
        out["filename"] = sanitize_filename(str(name))
    return out


def validate_job_request(*, mode: str, model: str | None, stems: list[str] | None,
                         settings) -> tuple[str, list[str] | None]:
    if mode not in MODES:
        raise ValidationError("invalid_mode", f"Unknown mode '{mode}'.")
    model_id = model or settings.demucs_model
    from audioapp.models.registry import MODELS
    if mode != "convert" and model_id not in MODELS:
        raise ValidationError("invalid_model", f"Unknown model '{model}'.")
    if mode == "custom":
        stems_for_mode(mode, model_id, stems)  # validates
        return model_id, list(dict.fromkeys(stems or []))
    if stems:
        raise ValidationError("invalid_stems", "Stems can only be chosen in Custom mode.")
    return model_id, None
