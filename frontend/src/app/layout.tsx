import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Audio Separator, Karaoke Maker & Music Converter",
  description:
    "Upload audio, separate vocals and instruments with AI, make karaoke tracks, and convert between formats.",
};

// Rendered at request time, NOT build time. Render injects the blueprint env
// vars when the container runs, but NEXT_PUBLIC_* values are only inlined
// into the client JS bundle during the Docker *build* — when they don't exist
// yet. Without this, the browser bundle would see an empty backend URL and
// silently fall back to the same-origin /api proxy.
export const dynamic = "force-dynamic";

const RUNTIME_API_URL =
  process.env.NEXT_PUBLIC_API_URL || process.env.API_PROXY_TARGET || "";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <script
        dangerouslySetInnerHTML={{
          __html: `window.__AAS_API_URL=${JSON.stringify(RUNTIME_API_URL).replace(
            /</g,
            "\\u003c"
          )};`,
        }}
      />
      <body className="flex min-h-screen flex-col">
        <Nav />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-zinc-800">
          <div className="mx-auto max-w-5xl px-4 py-6 text-center text-xs text-zinc-500">
            <p>
              Process only audio you own or have permission to use. Files are automatically deleted from the
              server — results are kept for 24 hours.
            </p>
            <p className="mt-1">
              Separation uses Demucs (code: MIT; official weights are research-licensed by the author).
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
