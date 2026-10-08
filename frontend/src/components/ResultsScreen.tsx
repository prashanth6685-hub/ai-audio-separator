"use client";

import { useEffect, useState } from "react";
import { ApiError, getJob, getResults } from "@/lib/api";
import { formatBytes, formatDuration, stemDisplayName } from "@/lib/format";
import type { JobOut, JobOutput } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { WaveformPlayer } from "./WaveformPlayer";

interface Props {
  jobId: string;
  /** Local object URL of the original upload (only available right after upload). */
  originalUrl?: string;
  originalName: string;
  onRestart?: () => void;
}

function encodingSummary(o: JobOutput): string {
  const parts = [o.format.toUpperCase()];
  if (o.bitrate_kbps) parts.push(`${o.bitrate_kbps} kbps`);
  parts.push(`${o.sample_rate} Hz`);
  parts.push(o.channels === 1 ? "Mono" : o.channels === 2 ? "Stereo" : `${o.channels} ch`);
  return parts.join(" · ");
}

export function ResultsScreen({ jobId, originalUrl, originalName, onRestart }: Props) {
  const [job, setJob] = useState<JobOut | null>(null);
  const [outputs, setOutputs] = useState<JobOutput[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    (async () => {
      try {
        const [j, r] = await Promise.all([getJob(jobId), getResults(jobId)]);
        if (stop) return;
        setJob(j);
        setOutputs(r.outputs);
      } catch (e) {
        if (!stop) setError((e as ApiError).message);
      }
    })();
    return () => {
      stop = true;
    };
  }, [jobId]);

  const downloadAll = () => {
    if (!outputs) return;
    outputs.forEach((o, i) => {
      setTimeout(() => {
        const a = document.createElement("a");
        a.href = o.download_url;
        a.download = `${stemDisplayName(o.stem)}.${o.format}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }, i * 600);
    });
  };

  if (error) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6" role="alert">
        <p className="font-semibold text-red-200">Couldn&apos;t load the results</p>
        <p className="mt-1 text-sm text-zinc-400">{error}</p>
        <p className="mt-2 text-sm text-zinc-500">
          Your files are still on the server — find this job again under Projects.
        </p>
      </div>
    );
  }

  if (!job || !outputs) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6" role="status">
        <p className="text-sm text-zinc-400">Loading your results…</p>
      </div>
    );
  }

  const expired = job.status === "expired";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-zinc-100">Your results are ready 🎉</h3>
          <p className="mt-0.5 text-sm text-zinc-400">
            {job.upload.filename}
            {job.model ? ` · ${job.model}` : ""}
          </p>
        </div>
        <StatusBadge status={job.status} />
      </div>

      {expired && (
        <p className="rounded-lg bg-amber-950/60 p-3 text-sm text-amber-200" role="note">
          These files have expired (results are kept for 24 hours), so downloads may no longer work. Run the
          job again to get fresh files.
        </p>
      )}

      {/* Original */}
      {originalUrl && (
        <section aria-label="Original audio" className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:p-5">
          <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">Original</h4>
          <WaveformPlayer src={originalUrl} label={originalName} />
        </section>
      )}

      {/* Step 1 — AI separation */}
      <section aria-label="AI separation results" className="rounded-2xl border border-violet-900/60 bg-violet-950/20 p-4 sm:p-5">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-violet-300">
          Step 1 · AI separation
        </h4>
        <p className="mt-1 text-xs text-zinc-400">
          These tracks were separated by the AI model from your original.
        </p>

        {outputs.length === 0 ? (
          <p className="mt-4 rounded-lg bg-zinc-900 p-4 text-sm text-zinc-400" role="status">
            No output files were produced for this job.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            {outputs.map((o) => (
              <div key={o.output_id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-zinc-100">{o.label}</p>
                    <p className="mt-0.5 text-xs text-zinc-400">
                      {formatDuration(o.duration_s)} · {formatBytes(o.size_bytes)} · {encodingSummary(o)}
                    </p>
                  </div>
                  <a
                    href={o.download_url}
                    download={`${stemDisplayName(o.stem)}.${o.format}`}
                    className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-500"
                  >
                    Download
                  </a>
                </div>
                <div className="mt-3">
                  <WaveformPlayer src={o.download_url} label={o.label} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Step 2 — Export / encoding */}
      {outputs.length > 0 && (
        <section aria-label="Export and encoding" className="rounded-2xl border border-indigo-900/60 bg-indigo-950/20 p-4 sm:p-5">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-indigo-300">
            Step 2 · Export / encoding
          </h4>
          <p className="mt-1 text-xs text-zinc-400">
            Each separated track was then encoded for download:
          </p>
          <ul className="mt-3 space-y-1.5 text-sm text-zinc-300">
            {outputs.map((o) => (
              <li key={o.output_id} className="flex flex-wrap justify-between gap-2 rounded-lg bg-zinc-900 px-3 py-2">
                <span className="font-medium">{o.label}</span>
                <span className="text-zinc-400">{encodingSummary(o)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        {outputs.length > 0 && (
          <button
            type="button"
            onClick={downloadAll}
            className="flex-1 rounded-xl bg-violet-600 px-4 py-3 font-semibold text-white hover:bg-violet-500"
          >
            Download all ({outputs.length})
          </button>
        )}
        {onRestart && (
          <button
            type="button"
            onClick={onRestart}
            className="flex-1 rounded-xl border border-zinc-700 px-4 py-3 font-semibold text-zinc-200 hover:bg-zinc-800"
          >
            Start over with a new file
          </button>
        )}
      </div>
    </div>
  );
}
