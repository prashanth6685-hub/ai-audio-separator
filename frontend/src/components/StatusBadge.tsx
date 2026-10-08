"use client";

import type { JobStatus } from "@/lib/types";

const STYLES: Record<JobStatus, string> = {
  uploaded: "bg-zinc-700 text-zinc-200",
  validating: "bg-sky-900 text-sky-200",
  queued: "bg-amber-900 text-amber-200",
  processing: "bg-violet-900 text-violet-200",
  encoding: "bg-indigo-900 text-indigo-200",
  completed: "bg-emerald-900 text-emerald-200",
  failed: "bg-red-900 text-red-200",
  cancelled: "bg-zinc-800 text-zinc-400",
  expired: "bg-zinc-800 text-zinc-400",
};

const LABELS: Record<JobStatus, string> = {
  uploaded: "Uploaded",
  validating: "Validating",
  queued: "Queued",
  processing: "Processing",
  encoding: "Encoding",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  expired: "Expired",
};

export function StatusBadge({ status, pulsing = false }: { status: JobStatus; pulsing?: boolean }) {
  const active = pulsing && (status === "queued" || status === "processing" || status === "encoding" || status === "validating");
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[status] ?? STYLES.uploaded}`}
    >
      {active && <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />}
      {LABELS[status] ?? status}
    </span>
  );
}
