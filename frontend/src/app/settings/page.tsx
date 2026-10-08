"use client";

import { useEffect, useState } from "react";
import { ApiError, getHealth, getModels } from "@/lib/api";
import { DEFAULT_DEFAULTS, loadDefaults, saveDefaults, type UserDefaults } from "@/lib/settings";
import type { AiModel, HealthOut } from "@/lib/types";

const FORMATS = [
  { id: "mp3", name: "MP3" },
  { id: "wav", name: "WAV" },
  { id: "flac", name: "FLAC" },
  { id: "ogg", name: "OGG" },
  { id: "m4a", name: "M4A" },
] as const;

export default function SettingsPage() {
  const [defaults, setDefaults] = useState<UserDefaults>({ ...DEFAULT_DEFAULTS });
  const [models, setModels] = useState<AiModel[]>([]);
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [apiBase, setApiBase] = useState("/api/v1");

  useEffect(() => {
    setDefaults(loadDefaults());
    setApiBase(`${window.location.origin}/api/v1`);
    (async () => {
      try {
        const m = await getModels();
        setModels(m.models);
      } catch {
        /* models list is optional here */
      }
      try {
        setHealth(await getHealth());
      } catch (e) {
        setHealthError((e as ApiError).message);
      }
    })();
  }, []);

  const update = (patch: Partial<UserDefaults>) => {
    setDefaults((d) => ({ ...d, ...patch }));
    setSaved(false);
  };

  const save = () => {
    saveDefaults(defaults);
    setSaved(true);
  };

  const reset = () => {
    const d = { ...DEFAULT_DEFAULTS };
    setDefaults(d);
    saveDefaults(d);
    setSaved(true);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Settings</h1>
      <p className="mt-2 text-zinc-400">Your preferences live in this browser only — nothing is sent to the server.</p>

      {/* Defaults */}
      <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900 p-5" aria-label="Default settings">
        <h2 className="font-semibold text-zinc-100">Your defaults</h2>
        <p className="mt-1 text-sm text-zinc-400">
          These are pre-filled on the Separator, Karaoke, Extract and Convert pages.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="def-format" className="mb-1.5 block text-sm font-medium text-zinc-300">
              Default output format
            </label>
            <select
              id="def-format"
              value={defaults.format}
              onChange={(e) => update({ format: e.target.value as UserDefaults["format"] })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
            >
              {FORMATS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="def-bitrate" className="mb-1.5 block text-sm font-medium text-zinc-300">
              Default MP3/M4A bitrate
            </label>
            <select
              id="def-bitrate"
              value={defaults.bitrateKbps}
              onChange={(e) => update({ bitrateKbps: Number(e.target.value) })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
            >
              {[128, 192, 320].map((b) => (
                <option key={b} value={b}>
                  {b} kbps
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="def-model" className="mb-1.5 block text-sm font-medium text-zinc-300">
              Default AI model
            </label>
            <select
              id="def-model"
              value={defaults.model}
              onChange={(e) => update({ model: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
            >
              {models.length === 0 && <option value={defaults.model}>{defaults.model}</option>}
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={save}
            className="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-500"
          >
            Save defaults
          </button>
          <button
            type="button"
            onClick={reset}
            className="rounded-lg border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
          >
            Reset to beginner defaults
          </button>
          {saved && (
            <span className="text-sm text-emerald-300" role="status">
              ✓ Saved
            </span>
          )}
        </div>
      </section>

      {/* Server status */}
      <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-5" aria-label="Server status">
        <h2 className="font-semibold text-zinc-100">Server status</h2>
        {healthError && (
          <p className="mt-2 text-sm text-red-300" role="alert">
            Couldn&apos;t reach the backend: {healthError}
          </p>
        )}
        {health && (
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Status</dt>
              <dd className="text-emerald-300">● {health.status}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Audio engine (ffmpeg)</dt>
              <dd className="text-zinc-200">{health.ffmpeg ? "Available" : "Not detected"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Models already downloaded</dt>
              <dd className="text-zinc-200">
                {health.models_cached.length > 0 ? health.models_cached.join(", ") : "None yet — first run downloads one"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Results kept for</dt>
              <dd className="text-zinc-200">{health.retention_hours} hours</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">API base</dt>
              <dd className="break-all text-right font-mono text-xs text-zinc-300">{apiBase}</dd>
            </div>
          </dl>
        )}
      </section>

      {/* Data & privacy */}
      <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-5" aria-label="Data and privacy">
        <h2 className="font-semibold text-zinc-100">Data & privacy</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-zinc-400">
          <li>Your uploads and results are automatically deleted from the server after 24 hours.</li>
          <li>Deleting a project removes its files immediately.</li>
          <li>Your audio is never used to train AI models.</li>
          <li>Only process audio you own or have permission to use.</li>
        </ul>
      </section>

      {/* License note */}
      <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900 p-5" aria-label="Model licensing">
        <h2 className="font-semibold text-zinc-100">Model licensing</h2>
        <p className="mt-3 text-sm text-zinc-400">
          Separation is powered by Demucs. The Demucs <em>code</em> is MIT-licensed. The official pretrained{" "}
          <em>weights</em> are stated by the author to be provided only for scientific purposes, with no
          commercial grant — fine for personal and prototype use; resolve the rights before any commercial
          deployment.
        </p>
        <p className="mt-2 text-sm text-zinc-500">
          The original facebookresearch/demucs repository was archived in January 2025; the community fork
          adefossez/demucs continues maintenance. This app uses the inference-only demucs-infer package.
        </p>
      </section>
    </div>
  );
}
