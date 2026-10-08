"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, uploadAudio } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/format";
import type { UploadOut } from "@/lib/types";
import { WaveformPlayer } from "./WaveformPlayer";

export interface UploadedAudio {
  info: UploadOut;
  /** Local object URL for previewing the original file. */
  previewUrl: string;
}

interface Props {
  value: UploadedAudio | null;
  onChange: (v: UploadedAudio | null) => void;
}

const ACCEPT = ".mp3,.wav,.flac,.ogg,.oga,.m4a,.aac,.wma,.aiff,.aif,.opus";

export function UploadDropzone({ value, onChange }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Revoke the local preview URL when it changes / on unmount.
  useEffect(() => {
    return () => {
      if (pendingUrl) URL.revokeObjectURL(pendingUrl);
    };
  }, [pendingUrl]);

  const pickFile = useCallback((file: File | undefined | null) => {
    setError(null);
    if (!file) return;
    if (pendingUrl) URL.revokeObjectURL(pendingUrl);
    setPendingFile(file);
    setPendingUrl(URL.createObjectURL(file));
    setRightsConfirmed(false);
  }, [pendingUrl]);

  const doUpload = useCallback(async () => {
    if (!pendingFile || !rightsConfirmed || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const info = await uploadAudio(pendingFile, true);
      onChange({ info, previewUrl: pendingUrl ?? "" });
      setPendingFile(null);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }, [pendingFile, rightsConfirmed, uploading, onChange, pendingUrl]);

  const remove = useCallback(() => {
    if (value?.previewUrl) URL.revokeObjectURL(value.previewUrl);
    onChange(null);
  }, [value, onChange]);

  const replace = useCallback(() => {
    remove();
    setPendingFile(null);
    setPendingUrl(null);
  }, [remove]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      pickFile(e.dataTransfer.files?.[0]);
    },
    [pickFile]
  );

  // ---- Uploaded state: show server metadata + preview + actions ----
  if (value) {
    const m = value.info.meta;
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold text-zinc-100">{value.info.filename}</p>
            <p className="mt-1 text-sm text-zinc-400">
              {formatBytes(value.info.size_bytes)} · {formatDuration(m.duration_s)} ·{" "}
              {m.format_name}/{m.codec_name} · {m.sample_rate} Hz ·{" "}
              {m.channels === 1 ? "Mono" : m.channels === 2 ? "Stereo" : `${m.channels} ch`}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-emerald-900 px-2.5 py-0.5 text-xs font-semibold text-emerald-200">
            Uploaded
          </span>
        </div>

        {value.info.warnings.length > 0 && (
          <ul className="mt-3 space-y-1 rounded-lg bg-amber-950/60 p-3 text-sm text-amber-200" role="note">
            {value.info.warnings.map((w, i) => (
              <li key={i}>⚠ {w}</li>
            ))}
          </ul>
        )}

        {value.previewUrl && (
          <div className="mt-4">
            <WaveformPlayer src={value.previewUrl} label="Original preview" />
          </div>
        )}

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={remove}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
          >
            Remove
          </button>
          <button
            type="button"
            onClick={replace}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
          >
            Replace file
          </button>
        </div>
      </div>
    );
  }

  // ---- Pick / pre-upload state ----
  return (
    <div>
      {!pendingFile ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          aria-label="Choose an audio file or drop it here"
          className={`flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
            dragOver ? "border-violet-500 bg-violet-950/30" : "border-zinc-700 bg-zinc-900 hover:border-zinc-500"
          }`}
        >
          <span className="text-4xl" aria-hidden="true">
            🎵
          </span>
          <span className="mt-3 font-semibold text-zinc-100">
            {dragOver ? "Drop it here" : "Drop an audio file here, or tap to choose"}
          </span>
          <span className="mt-1 text-sm text-zinc-400">MP3, WAV, FLAC, OGG, M4A and more</span>
        </button>
      ) : (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-semibold text-zinc-100">{pendingFile.name}</p>
              <p className="mt-1 text-sm text-zinc-400">{formatBytes(pendingFile.size)} · ready to upload</p>
            </div>
            <button
              type="button"
              onClick={() => {
                if (pendingUrl) URL.revokeObjectURL(pendingUrl);
                setPendingFile(null);
                setPendingUrl(null);
              }}
              className="shrink-0 rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Choose different
            </button>
          </div>

          {pendingUrl && (
            <div className="mt-4">
              <WaveformPlayer src={pendingUrl} label="Preview" />
            </div>
          )}

          <div className="mt-4 rounded-lg bg-zinc-800/70 p-3">
            <label className="flex cursor-pointer items-start gap-3 text-sm">
              <input
                type="checkbox"
                checked={rightsConfirmed}
                onChange={(e) => setRightsConfirmed(e.target.checked)}
                className="mt-1 h-4 w-4 shrink-0 accent-violet-500"
              />
              <span className="text-zinc-300">
                I confirm I have the right to process this audio — it&apos;s my own recording, or I have the
                owner&apos;s permission.
              </span>
            </label>
          </div>

          <button
            type="button"
            onClick={doUpload}
            disabled={!rightsConfirmed || uploading}
            className="mt-4 w-full rounded-xl bg-violet-600 px-4 py-3 font-semibold text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {uploading ? (
              <span className="inline-flex items-center gap-2">
                <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
                Uploading…
              </span>
            ) : (
              "Upload audio"
            )}
          </button>
          {!rightsConfirmed && !uploading && (
            <p className="mt-2 text-center text-xs text-zinc-500">Tick the checkbox above to enable upload.</p>
          )}
        </div>
      )}

      {error && (
        <p className="mt-3 rounded-lg bg-red-950/60 p-3 text-sm text-red-200" role="alert">
          {error}
        </p>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        aria-hidden="true"
        tabIndex={-1}
        onChange={(e) => pickFile(e.target.files?.[0])}
      />
    </div>
  );
}
