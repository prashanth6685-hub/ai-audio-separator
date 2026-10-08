"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, createJob, getModels } from "@/lib/api";
import type { AiModel, JobOut, ModeInfo } from "@/lib/types";
import { defaultExportValues, ExportSettings, type ExportValues } from "./ExportSettings";
import { JobProgress } from "./JobProgress";
import { ModeSelect, type ModeSelection } from "./ModeSelect";
import { ResultsScreen } from "./ResultsScreen";
import { UploadDropzone, type UploadedAudio } from "./UploadDropzone";

interface Props {
  title: string;
  subtitle: string;
  /** Fixed mode (karaoke page) — skips the mode picker. */
  fixedMode?: string;
  /** Restricted mode list (extract page: instruments + custom). */
  allowedModes?: string[];
  /** Convert page — no mode/model/stems at all. */
  convertOnly?: boolean;
  submitLabel: string;
}

const STEPS = ["Upload", "Options", "Export", "Process"];

export function SeparationFlow({ title, subtitle, fixedMode, allowedModes, convertOnly, submitLabel }: Props) {
  const [models, setModels] = useState<AiModel[]>([]);
  const [modes, setModes] = useState<Record<string, ModeInfo>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  const [upload, setUpload] = useState<UploadedAudio | null>(null);
  const [selection, setSelection] = useState<ModeSelection>({ mode: "", model: "", stems: [] });
  const [exportValues, setExportValues] = useState<ExportValues>(() => defaultExportValues());
  const [jobId, setJobId] = useState<string | null>(null);
  const [doneJob, setDoneJob] = useState<JobOut | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const m = await getModels();
        setModels(m.models);
        setModes(m.modes);
        const defaultModel = m.models.find((x) => x.default)?.id ?? m.models[0]?.id ?? "";
        const initialMode =
          fixedMode ?? allowedModes?.[0] ?? Object.keys(m.modes).find((k) => k !== "convert") ?? "";
        setSelection({ mode: initialMode, model: defaultModel, stems: [] });
      } catch (e) {
        setLoadError((e as ApiError).message);
      }
    })();
  }, [fixedMode, allowedModes]);

  const reset = useCallback(() => {
    setUpload(null);
    setJobId(null);
    setDoneJob(null);
    setSubmitError(null);
  }, []);

  const canSubmit =
    upload !== null &&
    (convertOnly || selection.mode !== "") &&
    (selection.mode !== "custom" || selection.stems.length > 0) &&
    !submitting &&
    !jobId;

  const handleSubmit = async () => {
    if (!upload || !canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await createJob({
        upload_id: upload.info.upload_id,
        mode: convertOnly ? "convert" : selection.mode,
        model: convertOnly ? null : selection.model || null,
        stems: !convertOnly && selection.mode === "custom" ? selection.stems : null,
        export: {
          format: exportValues.format,
          bitrate_kbps: exportValues.bitrateKbps,
          sample_rate: exportValues.sampleRate,
          channels: exportValues.channels,
          ogg_quality: exportValues.oggQuality,
          filename: exportValues.filename.trim() || null,
        },
      });
      setJobId(res.job_id);
    } catch (e) {
      setSubmitError((e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  const currentStep = doneJob ? 4 : jobId ? 3 : upload ? 2 : 1;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
      <p className="mt-2 text-zinc-400">{subtitle}</p>

      {/* Step indicator */}
      <ol className="mt-6 flex items-center gap-1 sm:gap-2" aria-label="Progress">
        {STEPS.map((label, i) => {
          const n = i + 1;
          const active = n === Math.min(currentStep, 4);
          const reached = n <= currentStep;
          return (
            <li key={label} className="flex flex-1 items-center gap-1 sm:gap-2">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  active
                    ? "bg-violet-600 text-white"
                    : reached
                      ? "bg-violet-900 text-violet-200"
                      : "bg-zinc-800 text-zinc-500"
                }`}
                aria-current={active ? "step" : undefined}
              >
                {n}
              </span>
              <span className={`text-xs font-medium sm:text-sm ${reached ? "text-zinc-200" : "text-zinc-500"}`}>
                {label}
              </span>
              {n < STEPS.length && <span className="mx-1 h-px flex-1 bg-zinc-800" aria-hidden="true" />}
            </li>
          );
        })}
      </ol>

      {loadError && (
        <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-6" role="alert">
          <p className="font-semibold text-red-200">Couldn&apos;t reach the server</p>
          <p className="mt-1 text-sm text-zinc-400">{loadError}</p>
          <p className="mt-2 text-sm text-zinc-500">
            Make sure the backend is running, then reload this page.
          </p>
        </div>
      )}

      {!loadError && (
        <div className="mt-6 space-y-8">
          {/* Step 1 — upload */}
          <section aria-label="Step 1: upload">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
              1 · Upload your audio
            </h2>
            <UploadDropzone value={upload} onChange={setUpload} />
          </section>

          {/* Step 2 — mode / model */}
          {upload && !convertOnly && models.length > 0 && (
            <section aria-label="Step 2: separation options">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                2 · What should the AI do?
              </h2>
              <ModeSelect
                models={models}
                modes={modes}
                fixedMode={fixedMode}
                allowedModes={allowedModes}
                value={selection}
                onChange={setSelection}
              />
            </section>
          )}

          {/* Step 3 — export */}
          {upload && (
            <section aria-label="Step 3: export settings">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                {convertOnly ? "2 · Choose the output format" : "3 · Choose the output format"}
              </h2>
              <ExportSettings value={exportValues} onChange={setExportValues} />

              <button
                type="button"
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="mt-6 w-full rounded-xl bg-violet-600 px-4 py-3.5 text-base font-semibold text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? (
                  <span className="inline-flex items-center gap-2">
                    <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                    Starting…
                  </span>
                ) : (
                  submitLabel
                )}
              </button>
              {selection.mode === "custom" && selection.stems.length === 0 && (
                <p className="mt-2 text-center text-sm text-amber-300">
                  Pick at least one stem above to start.
                </p>
              )}
              {submitError && (
                <p className="mt-3 rounded-lg bg-red-950/60 p-3 text-sm text-red-200" role="alert">
                  {submitError}
                </p>
              )}
            </section>
          )}

          {/* Step 4 — progress / results */}
          {jobId && !doneJob && (
            <section aria-label="Step 4: processing">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                {convertOnly ? "3 · Converting" : "4 · Processing"}
              </h2>
              <JobProgress jobId={jobId} onDone={setDoneJob} />
            </section>
          )}

          {doneJob && (
            <section aria-label="Results">
              <ResultsScreen
                jobId={doneJob.job_id}
                originalUrl={upload?.previewUrl}
                originalName={upload?.info.filename ?? "Original"}
                onRestart={reset}
              />
            </section>
          )}
        </div>
      )}
    </div>
  );
}
