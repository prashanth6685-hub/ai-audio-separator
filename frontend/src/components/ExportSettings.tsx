"use client";

import { useEffect, useState } from "react";
import { loadDefaults } from "@/lib/settings";
import type { ExportFormat } from "@/lib/types";

export interface ExportValues {
  format: ExportFormat;
  bitrateKbps: number | null;
  sampleRate: number | null;
  channels: number | null;
  oggQuality: number | null;
  filename: string;
}

interface Props {
  value: ExportValues;
  onChange: (v: ExportValues) => void;
}

const FORMATS: { id: ExportFormat; name: string; blurb: string }[] = [
  { id: "mp3", name: "MP3", blurb: "Small files, plays everywhere" },
  { id: "wav", name: "WAV", blurb: "Uncompressed, best quality" },
  { id: "flac", name: "FLAC", blurb: "Lossless but smaller than WAV" },
  { id: "ogg", name: "OGG", blurb: "Open format, great quality per MB" },
  { id: "m4a", name: "M4A", blurb: "Apple-friendly, good quality" },
];

const MP3_BITRATES = [128, 192, 320];
const M4A_BITRATES = [128, 192, 256, 320];
const SAMPLE_RATES = [22050, 32000, 44100, 48000];

export function defaultExportValues(): ExportValues {
  const d = loadDefaults();
  return {
    format: d.format,
    bitrateKbps: d.bitrateKbps,
    sampleRate: d.sampleRate,
    channels: d.channels,
    oggQuality: d.format === "ogg" ? 5 : null,
    filename: "",
  };
}

export function ExportSettings({ value, onChange }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const set = (patch: Partial<ExportValues>) => onChange({ ...value, ...patch });

  const bitrateOptions = value.format === "m4a" ? M4A_BITRATES : MP3_BITRATES;

  // Keep bitrate/quality fields consistent with the chosen format.
  useEffect(() => {
    if (value.format === "wav" || value.format === "flac") {
      if (value.bitrateKbps !== null || value.oggQuality !== null) {
        onChange({ ...value, bitrateKbps: null, oggQuality: null });
      }
    } else if (value.format === "ogg") {
      if (value.oggQuality === null || value.bitrateKbps !== null) {
        onChange({ ...value, bitrateKbps: null, oggQuality: value.oggQuality ?? 5 });
      }
    } else if ((value.format === "mp3" || value.format === "m4a") && value.bitrateKbps === null) {
      onChange({ ...value, bitrateKbps: 192, oggQuality: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.format]);

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium text-zinc-300">Output format</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Output format">
          {FORMATS.map((f) => {
            const selected = value.format === f.id;
            return (
              <button
                key={f.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => set({ format: f.id })}
                className={`rounded-xl border p-3 text-left transition-colors ${
                  selected
                    ? "border-violet-500 bg-violet-950/40"
                    : "border-zinc-700 bg-zinc-900 hover:border-zinc-500"
                }`}
              >
                <p className="font-semibold text-zinc-100">{f.name}</p>
                <p className="mt-0.5 text-xs text-zinc-400">{f.blurb}</p>
              </button>
            );
          })}
        </div>
      </fieldset>

      {(value.format === "mp3" || value.format === "m4a") && (
        <div>
          <label htmlFor="bitrate" className="mb-1.5 block text-sm font-medium text-zinc-300">
            Quality (bitrate)
          </label>
          <select
            id="bitrate"
            value={value.bitrateKbps ?? 192}
            onChange={(e) => set({ bitrateKbps: Number(e.target.value) })}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
          >
            {bitrateOptions.map((b) => (
              <option key={b} value={b}>
                {b} kbps{b === 192 ? " — recommended" : b === 320 ? " — best" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {value.format === "ogg" && (
        <div>
          <label htmlFor="ogg-quality" className="mb-1.5 block text-sm font-medium text-zinc-300">
            OGG quality: <span className="text-violet-300">{value.oggQuality ?? 5}</span>
            <span className="text-zinc-500"> (0 = smallest, 10 = best)</span>
          </label>
          <input
            id="ogg-quality"
            type="range"
            min={0}
            max={10}
            step={1}
            value={value.oggQuality ?? 5}
            onChange={(e) => set({ oggQuality: Number(e.target.value) })}
            className="w-full"
          />
        </div>
      )}

      <button
        type="button"
        onClick={() => setShowAdvanced((v) => !v)}
        aria-expanded={showAdvanced}
        className="text-sm font-medium text-violet-300 hover:text-violet-200"
      >
        {showAdvanced ? "− Hide advanced options" : "+ Advanced options (sample rate, channels, filename)"}
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="sample-rate" className="mb-1.5 block text-sm font-medium text-zinc-300">
              Sample rate
            </label>
            <select
              id="sample-rate"
              value={value.sampleRate ?? ""}
              onChange={(e) => set({ sampleRate: e.target.value ? Number(e.target.value) : null })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
            >
              <option value="">Keep original</option>
              {SAMPLE_RATES.map((r) => (
                <option key={r} value={r}>
                  {r.toLocaleString()} Hz
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="channels" className="mb-1.5 block text-sm font-medium text-zinc-300">
              Channels
            </label>
            <select
              id="channels"
              value={value.channels ?? ""}
              onChange={(e) => set({ channels: e.target.value ? Number(e.target.value) : null })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
            >
              <option value="">Keep original</option>
              <option value={2}>Stereo</option>
              <option value={1}>Mono</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="export-filename" className="mb-1.5 block text-sm font-medium text-zinc-300">
              Filename <span className="font-normal text-zinc-500">(optional — the stem name is added automatically)</span>
            </label>
            <input
              id="export-filename"
              type="text"
              value={value.filename}
              onChange={(e) => set({ filename: e.target.value })}
              placeholder="my-track"
              maxLength={80}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-violet-500 focus:outline-none"
            />
          </div>
        </div>
      )}
    </div>
  );
}
