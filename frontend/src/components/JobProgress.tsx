"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, cancelJob, getJob } from "@/lib/api";
import type { JobOut } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  jobId: string;
  onDone: (job: JobOut) => void;
}

const TERMINAL = new Set(["completed", "failed", "cancelled", "expired"]);

function WorkingIndicator() {
  return (
    <div className="flex h-10 items-end gap-1" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="eq-bar w-1.5 rounded-full bg-violet-400"
          style={{ height: "100%", animationDelay: `${i * 0.12}s` }}
        />
      ))}
    </div>
  );
}

/**
 * Polls the job every 2s. Shows the backend's own stage message + spinner.
 * NEVER invents a percentage — progress.measurable is always false.
 */
export function JobProgress({ jobId, onDone }: Props) {
  const [job, setJob] = useState<JobOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const doneRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    doneRef.current = false;
    let stop = false;

    const tick = async () => {
      try {
        const j = await getJob(jobId);
        if (stop) return;
        setJob(j);
        if (TERMINAL.has(j.status) && !doneRef.current) {
          doneRef.current = true;
          if (j.status === "completed") onDoneRef.current(j);
        }
      } catch (e) {
        if (stop) return;
        setError((e as ApiError).message);
      }
    };

    void tick();
    const id = setInterval(() => {
      if (!doneRef.current) void tick();
    }, 2000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [jobId]);

  const handleCancel = async () => {
    if (!window.confirm("Cancel this job? Any work done so far will be discarded.")) return;
    setCancelling(true);
    try {
      await cancelJob(jobId);
      const j = await getJob(jobId);
      setJob(j);
      doneRef.current = true;
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setCancelling(false);
    }
  };

  if (error && !job) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6" role="alert">
        <p className="font-semibold text-red-200">Couldn&apos;t check the job status</p>
        <p className="mt-1 text-sm text-zinc-400">{error}</p>
      </div>
    );
  }

  const status = job?.status ?? "queued";
  const isTerminal = TERMINAL.has(status);
  const message =
    job?.stage_detail ||
    job?.progress.message ||
    "Your job is in the queue — it will start shortly.";

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold text-zinc-100">Working on your audio</h3>
        <StatusBadge status={status} pulsing={!isTerminal} />
      </div>

      <div className="mt-6 flex flex-col items-center gap-4 text-center">
        {!isTerminal && <WorkingIndicator />}
        <p className="max-w-md text-sm text-zinc-300" role="status">
          {message}
        </p>
        {!isTerminal && (
          <p className="max-w-md text-xs text-zinc-500">
            Separation runs on the server&apos;s CPU, so a full song can take several minutes. Feel free to
            leave this page open — or check back from Projects.
          </p>
        )}
      </div>

      {status === "failed" && (
        <div className="mt-4 rounded-lg bg-red-950/60 p-4" role="alert">
          <p className="font-semibold text-red-200">Something went wrong</p>
          <p className="mt-1 text-sm text-red-200/80">{job?.error?.message ?? "The job failed."}</p>
          <p className="mt-2 text-sm text-zinc-400">
            Try again with a different file, or pick the faster default model. If it keeps failing, the file
            itself may be the problem.
          </p>
        </div>
      )}

      {status === "cancelled" && (
        <p className="mt-4 rounded-lg bg-zinc-800 p-4 text-sm text-zinc-300" role="status">
          This job was cancelled.
        </p>
      )}

      {status === "expired" && (
        <p className="mt-4 rounded-lg bg-zinc-800 p-4 text-sm text-zinc-300" role="status">
          This job&apos;s files have expired (results are kept for 24 hours). Start a new job to process the
          file again.
        </p>
      )}

      {!isTerminal && (
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          >
            {cancelling ? "Cancelling…" : "Cancel job"}
          </button>
        </div>
      )}

      {error && job && (
        <p className="mt-3 text-center text-xs text-amber-300" role="alert">
          Lost connection while checking status: {error}. Retrying…
        </p>
      )}
    </div>
  );
}
