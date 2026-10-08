"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { JobProgress } from "@/components/JobProgress";
import { ResultsScreen } from "@/components/ResultsScreen";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError, deleteJob, getJob, getModels } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { JobOut, ModeInfo } from "@/lib/types";

const ACTIVE = new Set(["uploaded", "validating", "queued", "processing", "encoding"]);

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const jobId = decodeURIComponent(params.id);

  const [job, setJob] = useState<JobOut | null>(null);
  const [modes, setModes] = useState<Record<string, ModeInfo>>({});
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [j, m] = await Promise.all([getJob(jobId), getModels()]);
      setJob(j);
      setModes(m.modes);
      setError(null);
    } catch (e) {
      setError((e as ApiError).message);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = async () => {
    if (
      !window.confirm(
        "Delete this project? This permanently removes the job and all its files. This can't be undone."
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      await deleteJob(jobId);
      router.push("/projects");
    } catch (e) {
      window.alert(`Couldn't delete the job: ${(e as ApiError).message}`);
      setDeleting(false);
    }
  };

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6" role="alert">
          <p className="font-semibold text-red-200">Couldn&apos;t load this project</p>
          <p className="mt-1 text-sm text-zinc-400">{error}</p>
          <Link href="/projects" className="mt-4 inline-block text-sm font-medium text-violet-300 hover:text-violet-200">
            ← Back to Projects
          </Link>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <p className="text-sm text-zinc-400" role="status">
          Loading project…
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Link href="/projects" className="text-sm font-medium text-violet-300 hover:text-violet-200">
        ← Back to Projects
      </Link>

      <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold tracking-tight">{job.upload.filename}</h1>
            <p className="mt-1 text-sm text-zinc-400">
              {modes[job.mode]?.name ?? job.mode}
              {job.model ? ` · ${job.model}` : ""} · started {formatDateTime(job.created_at)}
            </p>
          </div>
          <StatusBadge status={job.status} pulsing={ACTIVE.has(job.status)} />
        </div>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-lg border border-red-900 px-4 py-2 text-sm font-medium text-red-300 hover:bg-red-950/50 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete project"}
          </button>
        </div>
      </div>

      <div className="mt-6">
        {ACTIVE.has(job.status) ? (
          <JobProgress jobId={jobId} onDone={(j) => setJob(j)} />
        ) : job.status === "completed" ? (
          // Original audio isn't available here — only fresh uploads have a local preview.
          <ResultsScreen jobId={jobId} originalName={job.upload.filename} />
        ) : (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
            {job.status === "failed" && (
              <div role="alert">
                <p className="font-semibold text-red-200">This job failed</p>
                <p className="mt-1 text-sm text-red-200/80">{job.error?.message ?? "The job failed."}</p>
                <p className="mt-2 text-sm text-zinc-400">
                  Try again from the Separator page with a different file or model.
                </p>
              </div>
            )}
            {job.status === "cancelled" && (
              <p className="text-sm text-zinc-300" role="status">
                This job was cancelled.
              </p>
            )}
            {job.status === "expired" && (
              <p className="text-sm text-zinc-300" role="status">
                This job&apos;s files have expired (results are kept for 24 hours). Run it again to get fresh
                files.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
