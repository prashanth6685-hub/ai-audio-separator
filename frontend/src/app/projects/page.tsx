"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError, deleteJob, getModels, listJobs } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { JobSummary, ModeInfo } from "@/lib/types";

export default function ProjectsPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [modes, setModes] = useState<Record<string, ModeInfo>>({});
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [j, m] = await Promise.all([listJobs(), getModels()]);
      setJobs(j);
      setModes(m.modes);
      setError(null);
    } catch (e) {
      setError((e as ApiError).message);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleDelete = async (job: JobSummary) => {
    if (
      !window.confirm(
        `Delete "${job.filename}"? This permanently removes the job and all its files. This can't be undone.`
      )
    ) {
      return;
    }
    setDeleting(job.job_id);
    try {
      await deleteJob(job.job_id);
      setJobs((prev) => prev?.filter((j) => j.job_id !== job.job_id) ?? prev);
    } catch (e) {
      window.alert(`Couldn't delete the job: ${(e as ApiError).message}`);
    } finally {
      setDeleting(null);
    }
  };

  const modeName = (id: string) => modes[id]?.name ?? id;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Projects</h1>
          <p className="mt-2 text-zinc-400">Every separation and conversion you&apos;ve run. Files are kept for 24 hours.</p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="shrink-0 rounded-lg border border-zinc-700 px-3 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
        >
          ↻ Refresh
        </button>
      </div>

      {error && (
        <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-6" role="alert">
          <p className="font-semibold text-red-200">Couldn&apos;t load your projects</p>
          <p className="mt-1 text-sm text-zinc-400">{error}</p>
        </div>
      )}

      {jobs === null && !error && (
        <p className="mt-6 text-sm text-zinc-400" role="status">
          Loading…
        </p>
      )}

      {jobs !== null && jobs.length === 0 && (
        <div className="mt-6 rounded-2xl border border-dashed border-zinc-700 p-10 text-center">
          <p className="text-4xl" aria-hidden="true">
            🎧
          </p>
          <p className="mt-3 font-semibold text-zinc-200">No projects yet</p>
          <p className="mt-1 text-sm text-zinc-400">Upload a track and the results will show up here.</p>
          <Link
            href="/separator"
            className="mt-5 inline-block rounded-xl bg-violet-600 px-6 py-2.5 font-semibold text-white hover:bg-violet-500"
          >
            Start separating
          </Link>
        </div>
      )}

      {jobs !== null && jobs.length > 0 && (
        <ul className="mt-6 space-y-3">
          {jobs.map((job) => (
            <li
              key={job.job_id}
              className="flex flex-col gap-3 rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate font-semibold text-zinc-100">{job.filename}</p>
                  <StatusBadge status={job.status} />
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  {modeName(job.mode)} · {formatDateTime(job.created_at)}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Link
                  href={`/projects/${encodeURIComponent(job.job_id)}`}
                  className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500"
                >
                  View
                </Link>
                <button
                  type="button"
                  onClick={() => void handleDelete(job)}
                  disabled={deleting === job.job_id}
                  className="rounded-lg border border-red-900 px-4 py-2 text-sm font-medium text-red-300 hover:bg-red-950/50 disabled:opacity-50"
                >
                  {deleting === job.job_id ? "Deleting…" : "Delete"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
