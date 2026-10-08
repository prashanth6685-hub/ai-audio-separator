"use client";

/**
 * Tiny solo bus: when a player is soloed, every other WaveformPlayer on the
 * page effectively mutes itself until solo is released.
 */

let soloId: string | null = null;
const listeners = new Set<() => void>();

export function setSoloId(id: string | null): void {
  soloId = id;
  listeners.forEach((fn) => fn());
}

export function getSoloId(): string | null {
  return soloId;
}

export function subscribeSolo(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}
