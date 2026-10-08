import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Audio Separator, Karaoke Maker & Music Converter",
  description:
    "Upload audio, separate vocals and instruments with AI, make karaoke tracks, and convert between formats.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
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
