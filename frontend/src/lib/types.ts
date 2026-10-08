/** Wire types mirroring backend /api/v1 schemas. */

export type JobStatus =
  | "uploaded"
  | "validating"
  | "queued"
  | "processing"
  | "encoding"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired";

export type ModeId =
  | "vocal_isolation"
  | "karaoke"
  | "vocal_instrumental"
  | "acapella"
  | "instruments"
  | "custom"
  | "convert";

export type ExportFormat = "mp3" | "wav" | "flac" | "ogg" | "m4a";

export interface AudioMeta {
  format_name: string;
  codec_name: string;
  duration_s: number;
  sample_rate: number;
  channels: number;
  bit_depth: number | null;
}

export interface UploadOut {
  upload_id: string;
  filename: string;
  size_bytes: number;
  meta: AudioMeta;
  warnings: string[];
}

export interface ExportSettingsIn {
  format: ExportFormat;
  bitrate_kbps?: number | null;
  sample_rate?: number | null;
  channels?: number | null;
  ogg_quality?: number | null;
  filename?: string | null;
}

export interface JobCreateIn {
  upload_id: string;
  mode: string;
  model?: string | null;
  stems?: string[] | null;
  export: ExportSettingsIn;
}

export interface JobCreateOut {
  job_id: string;
  status: string;
}

export interface JobProgress {
  measurable: boolean;
  fraction?: number | null;
  message: string;
}

export interface JobError {
  code: string;
  message: string;
}

export interface JobOut {
  job_id: string;
  status: JobStatus;
  mode: string;
  model: string | null;
  stage_detail: string;
  progress: JobProgress;
  created_at: string;
  updated_at: string;
  expires_at: string;
  error: JobError | null;
  upload: { filename: string; meta: AudioMeta };
}

export interface JobSummary {
  job_id: string;
  status: JobStatus;
  mode: string;
  filename: string;
  created_at: string;
  expires_at: string;
}

export interface JobOutput {
  output_id: string;
  kind: string;
  stem: string;
  label: string;
  format: string;
  size_bytes: number;
  duration_s: number;
  sample_rate: number;
  channels: number;
  bitrate_kbps: number | null;
  download_url: string;
}

export interface ResultsOut {
  job_id: string;
  status: JobStatus;
  outputs: JobOutput[];
}

export interface AiModel {
  id: string;
  name: string;
  description: string;
  stems: string[];
  license_note: string;
  maintenance_note: string;
  default: boolean;
}

export interface ModeInfo {
  name: string;
  description: string;
}

export interface ModelsOut {
  models: AiModel[];
  modes: Record<string, ModeInfo>;
}

export interface HealthOut {
  status: string;
  ffmpeg: boolean;
  models_cached: string[];
  queue: Record<string, unknown>;
  retention_hours: number;
}
