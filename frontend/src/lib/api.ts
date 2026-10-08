import type {
  HealthOut,
  JobCreateIn,
  JobCreateOut,
  JobOut,
  JobSummary,
  ModelsOut,
  ResultsOut,
  UploadOut,
} from "./types";

/** Error thrown for every failed API call. Carries the backend error code. */
export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const BASE = "/api/v1";

function extractMessage(data: unknown, status: number): { code: string; message: string } {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (detail && typeof detail === "object" && "code" in detail) {
      const d = detail as { code: unknown; message: unknown };
      return {
        code: typeof d.code === "string" ? d.code : "request_failed",
        message: typeof d.message === "string" ? d.message : `Request failed (${status}).`,
      };
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      return {
        code: "validation_error",
        message: typeof first?.msg === "string" ? first.msg : `Invalid request (${status}).`,
      };
    }
    if (typeof detail === "string") {
      return { code: "request_failed", message: detail };
    }
  }
  return { code: "request_failed", message: `Request failed (${status}).` };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Could not reach the server. Check your connection and make sure the backend is running, then try again."
    );
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const { code, message } = extractMessage(data, res.status);
    throw new ApiError(res.status, code, message);
  }
  return data as T;
}

/** POST /uploads — multipart with the audio file. */
export async function uploadAudio(file: File, rightsConfirmed: boolean): Promise<UploadOut> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("rights_confirmed", rightsConfirmed ? "true" : "false");
  return req<UploadOut>("/uploads", { method: "POST", body: fd });
}

/** POST /jobs — start a separation or conversion job. */
export async function createJob(body: JobCreateIn): Promise<JobCreateOut> {
  return req<JobCreateOut>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** GET /jobs/{id} — poll for status. */
export async function getJob(jobId: string): Promise<JobOut> {
  return req<JobOut>(`/jobs/${encodeURIComponent(jobId)}`);
}

/** GET /jobs/{id}/results — outputs for a completed job. */
export async function getResults(jobId: string): Promise<ResultsOut> {
  return req<ResultsOut>(`/jobs/${encodeURIComponent(jobId)}/results`);
}

/** GET /jobs — recent jobs. */
export async function listJobs(): Promise<JobSummary[]> {
  return req<JobSummary[]>("/jobs?limit=50");
}

/** POST /jobs/{id}/cancel — stop a running job. */
export async function cancelJob(jobId: string): Promise<{ job_id: string; status: string }> {
  return req(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
}

/** DELETE /jobs/{id} — permanently remove a job and its files. */
export async function deleteJob(jobId: string): Promise<void> {
  await req<void>(`/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
}

/** GET /models — available models and separation modes. */
export async function getModels(): Promise<ModelsOut> {
  return req<ModelsOut>("/models");
}

/** GET /health — backend status. */
export async function getHealth(): Promise<HealthOut> {
  return req<HealthOut>("/health");
}
