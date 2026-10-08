"use client";

import { useEffect, useId, useRef, useState } from "react";
import type WaveSurfer from "wavesurfer.js";
import { formatDuration } from "@/lib/format";
import { getSoloId, setSoloId, subscribeSolo } from "@/lib/soloBus";

interface Props {
  src: string;
  label?: string;
}

/** Waveform player with play/pause, seek, time, volume, mute and solo. */
export function WaveformPlayer({ src, label }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const pid = useId();
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [muted, setMuted] = useState(false);
  const [isSolo, setIsSolo] = useState(false);
  const [otherSolo, setOtherSolo] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let ws: WaveSurfer | null = null;

    (async () => {
      try {
        const mod = await import("wavesurfer.js");
        if (cancelled || !containerRef.current) return;
        ws = mod.default.create({
          container: containerRef.current,
          url: src,
          waveColor: "#52525b",
          progressColor: "#a855f7",
          cursorColor: "#e9d5ff",
          barWidth: 2,
          barGap: 2,
          barRadius: 2,
          height: 72,
          normalize: true,
        });
        wsRef.current = ws;
        ws.on("ready", () => {
          if (cancelled) return;
          setReady(true);
          setDuration(ws?.getDuration() ?? 0);
          ws?.setVolume(volume);
        });
        ws.on("audioprocess", (t: number) => setTime(t));
        ws.on("seeking", (t: number) => setTime(t));
        ws.on("play", () => setPlaying(true));
        ws.on("pause", () => setPlaying(false));
        ws.on("finish", () => setPlaying(false));
        ws.on("error", () => {
          if (!cancelled) setError(true);
        });
      } catch {
        if (!cancelled) setError(true);
      }
    })();

    return () => {
      cancelled = true;
      ws?.destroy();
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  // Solo coordination: another player's solo mutes this one.
  useEffect(() => {
    const update = () => {
      const s = getSoloId();
      setIsSolo(s === pid);
      setOtherSolo(s !== null && s !== pid);
    };
    update();
    return subscribeSolo(update);
  }, [pid]);

  // Apply mute state to the engine.
  useEffect(() => {
    wsRef.current?.setMuted(muted || otherSolo);
  }, [muted, otherSolo]);

  // Apply volume.
  useEffect(() => {
    if (wsRef.current && !muted) wsRef.current.setVolume(volume);
  }, [volume, muted]);

  const togglePlay = () => {
    if (!ready || !wsRef.current) return;
    void wsRef.current.playPause();
  };

  const toggleSolo = () => {
    setSoloId(isSolo ? null : pid);
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={togglePlay}
          disabled={!ready}
          aria-label={playing ? "Pause" : "Play"}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-violet-600 text-white transition-colors hover:bg-violet-500 disabled:opacity-40"
        >
          {playing ? (
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <rect x="6" y="5" width="4" height="14" rx="1" />
              <rect x="14" y="5" width="4" height="14" rx="1" />
            </svg>
          ) : (
            <svg className="h-5 w-5 translate-x-0.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M8 5.5v13l11-6.5-11-6.5z" />
            </svg>
          )}
        </button>

        <div className="min-w-0 flex-1">
          {label && <p className="truncate text-xs font-medium text-zinc-400">{label}</p>}
          <div ref={containerRef} className="mt-1 w-full" aria-hidden="true" />
        </div>

        <div className="shrink-0 text-right text-xs tabular-nums text-zinc-400">
          <div>{formatDuration(time)}</div>
          <div className="text-zinc-600">{formatDuration(duration)}</div>
        </div>
      </div>

      {!ready && !error && (
        <p className="mt-2 text-xs text-zinc-500" role="status">
          Loading waveform…
        </p>
      )}
      {error && (
        <p className="mt-2 text-xs text-red-300" role="alert">
          Couldn&apos;t load this audio preview. The file itself may still be fine — try downloading it.
        </p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setMuted((v) => !v)}
          aria-pressed={muted}
          className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
            muted ? "bg-red-900 text-red-200" : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
          }`}
        >
          {muted ? "Unmute" : "Mute"}
        </button>
        <button
          type="button"
          onClick={toggleSolo}
          aria-pressed={isSolo}
          className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
            isSolo ? "bg-amber-800 text-amber-100" : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
          }`}
        >
          {isSolo ? "Solo: ON" : "Solo"}
        </button>
        {otherSolo && <span className="text-xs text-zinc-500">Muted — another track is soloed</span>}
        <label className="ml-auto flex items-center gap-2 text-xs text-zinc-400">
          Volume
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(volume * 100)}
            onChange={(e) => {
              setVolume(Number(e.target.value) / 100);
              setMuted(false);
            }}
            className="w-24"
            aria-label="Volume"
          />
        </label>
      </div>
    </div>
  );
}
