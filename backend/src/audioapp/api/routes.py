"""REST API: /api/v1/uploads, /jobs, /models, /health."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from audioapp.api.schemas import (
    AudioMetaOut, ExportSettingsIn, HealthOut, JobCreateIn, JobCreateOut,
    JobOut, JobSummaryOut, JobUploadInfo, ModelOut, ModelsOut, OutputOut,
    ProgressOut, ResultsOut, UploadOut,
)
from audioapp.audio.ffmpeg import FFMPEG, sanitize_filename
from audioapp.audio.validate import ValidationError, validate_upload
from audioapp.core.state import AppState
from audioapp.core.store import TERMINAL_STATES, utcnow
from audioapp.models.registry import MODELS, MODES
from audioapp.workers.pipeline import (
    _set, run_job, validate_export_settings, validate_job_request,
)

log = logging.getLogger(__name__)
router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.app_state


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


# -- uploads -----------------------------------------------------------

@router.post("/uploads", response_model=UploadOut, status_code=201)
async def create_upload(
    request: Request,
    file: UploadFile = File(...),
    rights_confirmed: bool | None = Form(None),
):
    state = get_state(request)
    settings = state.settings
    if not rights_confirmed:
        raise _err(400, "rights_not_confirmed",
                   "Please confirm you have the rights to process this audio.")
    if not file.filename:
        raise _err(400, "no_file", "No file was provided.")

    from audioapp.core.store import new_id
    upload_tmp_id = new_id("upl")
    dest = state.uploads_dir / f"{upload_tmp_id}.bin"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    try:
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise _err(413, "file_too_large",
                               f"This file exceeds the {settings.max_upload_mb} MB limit.")
                f.write(chunk)
    finally:
        await file.close()

    try:
        meta, warnings = validate_upload(dest, file.filename, size, settings)
    except ValidationError as e:
        dest.unlink(missing_ok=True)
        status = 413 if e.code == "file_too_large" else 400
        raise _err(status, e.code, e.message)

    expires_at = utcnow() + timedelta(hours=settings.upload_ttl_hours)
    rec = state.store.create_upload(
        filename=file.filename, size_bytes=size,
        meta=meta.__dict__, path=str(dest), expires_at=expires_at,
    )
    log.info("upload %s ok: %s codec=%s dur=%.1fs", rec["id"], file.filename,
             meta.codec_name, meta.duration_s)
    return UploadOut(
        upload_id=rec["id"], filename=rec["filename"], size_bytes=size,
        meta=AudioMetaOut(**meta.__dict__), warnings=warnings,
    )


# -- jobs --------------------------------------------------------------

@router.post("/jobs", response_model=JobCreateOut, status_code=201)
def create_job(body: JobCreateIn, request: Request):
    state = get_state(request)
    upload = state.store.get_upload(body.upload_id)
    if upload is None:
        raise _err(404, "upload_not_found", "Upload not found or expired.")
    try:
        export = validate_export_settings(body.export.model_dump())
        model_id, stems = validate_job_request(
            mode=body.mode, model=body.model, stems=body.stems, settings=state.settings)
    except ValidationError as e:
        raise _err(400, e.code, e.message)

    expires_at = utcnow() + timedelta(hours=state.settings.results_ttl_hours)
    job = state.store.create_job(
        upload_id=body.upload_id, mode=body.mode, model=model_id,
        stems=stems, export=export, expires_at=expires_at,
    )
    _set(state, job["id"], "queued")
    state.queue.submit(job["id"], lambda cancel_event: run_job(state, job["id"], cancel_event))
    log.info("job %s created: mode=%s model=%s", job["id"], body.mode, model_id)
    return JobCreateOut(job_id=job["id"], status="queued")


def _job_out(state: AppState, job: dict) -> JobOut:
    upload = state.store.get_upload(job["upload_id"]) or {}
    meta = (upload.get("meta") or {})
    return JobOut(
        job_id=job["id"], status=job["status"], mode=job["mode"], model=job["model"],
        stage_detail=job.get("stage_detail") or "",
        progress=ProgressOut(**(job.get("progress") or {})),
        created_at=job["created_at"], updated_at=job["updated_at"],
        expires_at=job["expires_at"], error=job.get("error"),
        upload=JobUploadInfo(
            filename=upload.get("filename", "unknown"),
            meta=AudioMetaOut(
                format_name=meta.get("format_name", "?"),
                codec_name=meta.get("codec_name", "?"),
                duration_s=meta.get("duration_s", 0),
                sample_rate=meta.get("sample_rate", 0),
                channels=meta.get("channels", 0),
                bit_depth=meta.get("bit_depth"),
            ),
        ),
    )


@router.get("/jobs", response_model=list[JobSummaryOut])
def list_jobs(request: Request, limit: int = 50):
    state = get_state(request)
    out = []
    for job in state.store.list_jobs(limit=min(limit, 100)):
        upload = state.store.get_upload(job["upload_id"]) or {}
        out.append(JobSummaryOut(
            job_id=job["id"], status=job["status"], mode=job["mode"],
            filename=upload.get("filename", "unknown"),
            created_at=job["created_at"], expires_at=job["expires_at"],
        ))
    return out


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request):
    state = get_state(request)
    job = state.store.get_job(job_id)
    if job is None:
        raise _err(404, "job_not_found", "Job not found.")
    return _job_out(state, job)


@router.get("/jobs/{job_id}/results", response_model=ResultsOut)
def get_results(job_id: str, request: Request):
    state = get_state(request)
    job = state.store.get_job(job_id)
    if job is None:
        raise _err(404, "job_not_found", "Job not found.")
    outputs = [
        OutputOut(
            output_id=o["output_id"], kind=o["kind"], stem=o["stem"], label=o["label"],
            format=o["format"], size_bytes=o["size_bytes"], duration_s=o["duration_s"],
            sample_rate=o["sample_rate"], channels=o["channels"],
            bitrate_kbps=o["bitrate_kbps"],
            download_url=f"/api/v1/jobs/{job_id}/download/{o['output_id']}",
        )
        for o in state.store.get_outputs(job_id)
    ]
    return ResultsOut(job_id=job_id, status=job["status"], outputs=outputs)


@router.get("/jobs/{job_id}/download/{output_id}")
def download_output(job_id: str, output_id: str, request: Request):
    state = get_state(request)
    job = state.store.get_job(job_id)
    if job is None:
        raise _err(404, "job_not_found", "Job not found.")
    if job["status"] == "expired":
        raise _err(410, "expired", "Your download has expired. You can process the file again.")
    out = state.store.get_output(job_id, output_id)
    if out is None:
        raise _err(404, "output_not_found", "Output not found.")
    path = Path(out["path"])
    if not path.exists():
        raise _err(410, "expired", "Your download has expired. You can process the file again.")
    upload = state.store.get_upload(job["upload_id"]) or {}
    base = sanitize_filename(upload.get("filename", "audio"))
    filename = f"{base}-{out['stem']}.{out['format']}"
    return FileResponse(path, filename=filename,
                        media_type="application/octet-stream")


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request):
    state = get_state(request)
    job = state.store.get_job(job_id)
    if job is None:
        raise _err(404, "job_not_found", "Job not found.")
    if job["status"] in TERMINAL_STATES:
        raise _err(409, "already_terminal",
                   f"Job is already {job['status']}; it cannot be cancelled.")
    state.queue.cancel(job_id)
    state.store.update_job(job_id, status="cancelled",
                           stage_detail="The job was cancelled.")
    return {"job_id": job_id, "status": "cancelled"}


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, request: Request):
    state = get_state(request)
    job = state.store.get_job(job_id)
    if job is None:
        raise _err(404, "job_not_found", "Job not found.")
    if job["status"] not in TERMINAL_STATES:
        state.queue.cancel(job_id)
    import shutil
    job_dir = state.jobs_dir / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    state.store.delete_job(job_id)
    return None


# -- models / health ----------------------------------------------------

@router.get("/models", response_model=ModelsOut)
def list_models():
    return ModelsOut(
        models=[ModelOut(id=mid, **{k: v for k, v in m.items() if k != "default"},
                         default=m.get("default", False))
                for mid, m in MODELS.items()],
        modes=MODES,
    )


@router.get("/health", response_model=HealthOut)
def health(request: Request):
    state = get_state(request)
    return HealthOut(
        status="ok",
        ffmpeg=bool(FFMPEG),
        models_cached=_cached_models(),
        queue=state.queue.stats(),
        retention_hours=state.settings.results_ttl_hours,
    )


# filename prefixes of official Demucs checkpoints in the torch hub cache
_CHECKPOINT_PREFIXES = {
    "htdemucs": ["955717e8"],
    "htdemucs_ft": ["f7e0c4bc", "d12395a8", "92cfc3b6", "04573f0d"],
    "htdemucs_6s": ["5c90dfd2"],
}


def _cached_models() -> list[str]:
    """Report which Demucs checkpoints are actually on disk (no downloading)."""
    try:
        import torch
        cache = Path(torch.hub.get_dir()) / "checkpoints"
    except Exception:
        return []
    if not cache.is_dir():
        return []
    names = {p.name for p in cache.iterdir() if p.suffix == ".th"}
    cached = []
    for model_id, prefixes in _CHECKPOINT_PREFIXES.items():
        if all(any(n.startswith(px) for n in names) for px in prefixes):
            cached.append(model_id)
    return cached
