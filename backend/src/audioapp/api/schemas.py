"""Pydantic schemas for /api/v1. These are the wire contract."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AudioMetaOut(BaseModel):
    format_name: str
    codec_name: str
    duration_s: float
    sample_rate: int
    channels: int
    bit_depth: int | None = None


class UploadOut(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int
    meta: AudioMetaOut
    warnings: list[str] = []


class ExportSettingsIn(BaseModel):
    format: str = "mp3"
    bitrate_kbps: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    ogg_quality: int | None = None
    filename: str | None = None


class JobCreateIn(BaseModel):
    upload_id: str
    mode: str
    model: str | None = None
    stems: list[str] | None = None
    export: ExportSettingsIn = Field(default_factory=ExportSettingsIn)


class JobCreateOut(BaseModel):
    job_id: str
    status: str


class ProgressOut(BaseModel):
    measurable: bool = False
    fraction: float | None = None
    message: str = ""


class ErrorOut(BaseModel):
    code: str
    message: str


class JobUploadInfo(BaseModel):
    filename: str
    meta: AudioMetaOut


class JobOut(BaseModel):
    job_id: str
    status: str
    mode: str
    model: str | None = None
    stage_detail: str = ""
    progress: ProgressOut = Field(default_factory=ProgressOut)
    created_at: str
    updated_at: str
    expires_at: str
    error: ErrorOut | None = None
    upload: JobUploadInfo


class JobSummaryOut(BaseModel):
    job_id: str
    status: str
    mode: str
    filename: str
    created_at: str
    expires_at: str


class OutputOut(BaseModel):
    output_id: str
    kind: str
    stem: str
    label: str
    format: str
    size_bytes: int
    duration_s: float
    sample_rate: int
    channels: int
    bitrate_kbps: int | None = None
    download_url: str


class ResultsOut(BaseModel):
    job_id: str
    status: str
    outputs: list[OutputOut]


class ModelOut(BaseModel):
    id: str
    name: str
    description: str
    stems: list[str]
    license_note: str
    maintenance_note: str
    default: bool


class ModelsOut(BaseModel):
    models: list[ModelOut]
    modes: dict[str, dict]


class HealthOut(BaseModel):
    status: str
    ffmpeg: bool
    models_cached: list[str]
    queue: dict
    retention_hours: float
