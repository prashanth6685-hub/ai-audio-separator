"use client";

import type { ExportFormat } from "./types";

/** Beginner-friendly defaults, persisted in localStorage. */

export interface UserDefaults {
  format: ExportFormat;
  bitrateKbps: number;
  model: string;
  sampleRate: number | null;
  channels: number | null;
}

const KEY = "aas-defaults";

export const DEFAULT_DEFAULTS: UserDefaults = {
  format: "mp3",
  bitrateKbps: 192,
  model: "htdemucs",
  sampleRate: null,
  channels: null,
};

export function loadDefaults(): UserDefaults {
  if (typeof window === "undefined") return { ...DEFAULT_DEFAULTS };
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<UserDefaults>;
    return { ...DEFAULT_DEFAULTS, ...parsed };
  } catch {
    return { ...DEFAULT_DEFAULTS };
  }
}

export function saveDefaults(d: UserDefaults): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(d));
  } catch {
    /* storage unavailable — ignore */
  }
}
