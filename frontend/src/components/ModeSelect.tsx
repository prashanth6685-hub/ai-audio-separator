"use client";

import { stemDisplayName } from "@/lib/format";
import type { AiModel, ModeInfo } from "@/lib/types";

export interface ModeSelection {
  mode: string;
  model: string;
  stems: string[];
}

interface Props {
  models: AiModel[];
  modes: Record<string, ModeInfo>;
  /** When set, the mode is fixed and only shown as an info banner. */
  fixedMode?: string;
  /** When set (and no fixedMode), only these modes are offered. */
  allowedModes?: string[];
  value: ModeSelection;
  onChange: (v: ModeSelection) => void;
}

export function ModeSelect({ models, modes, fixedMode, allowedModes, value, onChange }: Props) {
  const activeModes = allowedModes ?? Object.keys(modes).filter((m) => m !== "convert");
  const selectedModel = models.find((m) => m.id === value.model) ?? models[0];

  const set = (patch: Partial<ModeSelection>) => onChange({ ...value, ...patch });

  const toggleStem = (stem: string) => {
    const has = value.stems.includes(stem);
    const stems = has ? value.stems.filter((s) => s !== stem) : [...value.stems, stem];
    set({ stems });
  };

  const modeCard = (modeId: string) => {
    const info = modes[modeId];
    if (!info) return null;
    const selected = value.mode === modeId;
    return (
      <button
        key={modeId}
        type="button"
        onClick={() => set({ mode: modeId, stems: modeId === "custom" ? value.stems : [] })}
        aria-pressed={selected}
        className={`rounded-xl border p-4 text-left transition-colors ${
          selected
            ? "border-violet-500 bg-violet-950/40"
            : "border-zinc-700 bg-zinc-900 hover:border-zinc-500"
        }`}
      >
        <p className="font-semibold text-zinc-100">{info.name}</p>
        <p className="mt-1 text-sm text-zinc-400">{info.description}</p>
      </button>
    );
  };

  return (
    <div className="space-y-4">
      {fixedMode ? (
        <div className="rounded-xl border border-violet-800 bg-violet-950/40 p-4">
          <p className="font-semibold text-violet-100">{modes[fixedMode]?.name ?? fixedMode}</p>
          <p className="mt-1 text-sm text-violet-200/80">{modes[fixedMode]?.description}</p>
        </div>
      ) : allowedModes ? (
        <div role="radiogroup" aria-label="Separation mode" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {allowedModes.map((m) => modeCard(m))}
        </div>
      ) : (
        <div role="radiogroup" aria-label="Separation mode" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {activeModes.map((m) => modeCard(m))}
        </div>
      )}

      <div>
        <label htmlFor="model-select" className="mb-1.5 block text-sm font-medium text-zinc-300">
          AI model
        </label>
        <select
          id="model-select"
          value={value.model}
          onChange={(e) => set({ model: e.target.value })}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 focus:border-violet-500 focus:outline-none"
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        {selectedModel && <p className="mt-1.5 text-xs text-zinc-500">{selectedModel.description}</p>}
      </div>

      {value.mode === "custom" && selectedModel && (
        <fieldset className="rounded-xl border border-zinc-700 bg-zinc-900 p-4">
          <legend className="px-1 text-sm font-medium text-zinc-300">
            Which stems should the model separate?
          </legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {selectedModel.stems.map((stem) => {
              const checked = value.stems.includes(stem);
              return (
                <label
                  key={stem}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition-colors ${
                    checked ? "border-violet-500 bg-violet-950/40 text-violet-100" : "border-zinc-700 text-zinc-300 hover:border-zinc-500"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleStem(stem)}
                    className="h-4 w-4 accent-violet-500"
                  />
                  {stemDisplayName(stem)}
                </label>
              );
            })}
          </div>
          {value.stems.length === 0 && (
            <p className="mt-2 text-sm text-amber-300">Pick at least one stem to separate.</p>
          )}
        </fieldset>
      )}
    </div>
  );
}
