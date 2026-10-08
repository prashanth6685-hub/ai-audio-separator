"use client";

import Link from "next/link";

const FEATURES = [
  {
    icon: "🎙️",
    title: "AI vocal isolation",
    blurb: "Pull the lead vocal out of a full mix — or pull everything else out and keep the instruments.",
    href: "/separator",
    cta: "Separate a track",
  },
  {
    icon: "🎤",
    title: "Karaoke maker",
    blurb: "Remove the lead vocal and keep the instrumental backing, ready for your next sing-along.",
    href: "/karaoke",
    cta: "Make a karaoke track",
  },
  {
    icon: "🥁",
    title: "Instrument extractor",
    blurb: "Split a song into drums, bass, guitar, piano and more — the real stems the model hears.",
    href: "/extract",
    cta: "Extract instruments",
  },
  {
    icon: "🔄",
    title: "Format converter",
    blurb: "Convert between MP3, WAV, FLAC, OGG and M4A, with control over quality, sample rate and channels.",
    href: "/convert",
    cta: "Convert audio",
  },
];

const STEPS = [
  { n: "1", title: "Upload", blurb: "Drop in an MP3, WAV, FLAC, OGG, M4A — whatever you have." },
  { n: "2", title: "AI separates", blurb: "A real neural network (Demucs) splits vocals from instruments." },
  { n: "3", title: "Preview & download", blurb: "Listen to each stem in the browser, then grab the files." },
];

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-5xl px-4 pb-10 pt-12 text-center sm:pt-16">
        <p className="text-sm font-semibold uppercase tracking-widest text-violet-400">
          AI audio toolkit
        </p>
        <h1 className="mx-auto mt-3 max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">
          Split any song into{" "}
          <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
            vocals & instruments
          </span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-zinc-400">
          Upload a track, let AI separate the stems, make karaoke versions, or convert formats — right in your
          browser, no account needed.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/separator"
            className="w-full rounded-xl bg-violet-600 px-8 py-3.5 text-base font-semibold text-white hover:bg-violet-500 sm:w-auto"
          >
            ⬆ Upload Audio
          </Link>
          <Link
            href="/karaoke"
            className="w-full rounded-xl border border-zinc-700 px-8 py-3.5 text-base font-semibold text-zinc-200 hover:bg-zinc-800 sm:w-auto"
          >
            Make a karaoke track
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-4 py-8" aria-label="How it works">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-600 text-sm font-bold text-white">
                {s.n}
              </span>
              <h2 className="mt-3 font-semibold text-zinc-100">{s.title}</h2>
              <p className="mt-1 text-sm text-zinc-400">{s.blurb}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Feature cards */}
      <section className="mx-auto max-w-5xl px-4 py-8" aria-label="Features">
        <h2 className="text-xl font-bold tracking-tight">What you can do</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <div key={f.title} className="flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
              <span className="text-3xl" aria-hidden="true">
                {f.icon}
              </span>
              <h3 className="mt-3 text-lg font-semibold text-zinc-100">{f.title}</h3>
              <p className="mt-1 flex-1 text-sm text-zinc-400">{f.blurb}</p>
              <Link
                href={f.href}
                className="mt-4 inline-block rounded-lg bg-zinc-800 px-4 py-2 text-center text-sm font-semibold text-zinc-100 hover:bg-zinc-700"
              >
                {f.cta} →
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Honest notes */}
      <section className="mx-auto max-w-5xl px-4 py-8" aria-label="Good to know">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
          <h2 className="font-semibold text-zinc-200">Good to know</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-zinc-400">
            <li>
              Separation runs on the server&apos;s CPU, not a GPU — a full song takes several minutes. You can
              leave the page open or check back under Projects.
            </li>
            <li>
              Results are kept for 24 hours, then automatically deleted. Your uploads are never used to train
              models.
            </li>
            <li>
              The AI is powerful but not magic: dense mixes can leave faint traces of vocals in the
              instrumental, and vice versa.
            </li>
            <li>
              Only process audio you own or have permission to use. The Demucs model code is MIT-licensed;
              the official weights are provided by the author for research purposes.
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
