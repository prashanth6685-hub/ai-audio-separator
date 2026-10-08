"use client";

import { SeparationFlow } from "@/components/SeparationFlow";

export default function ConvertPage() {
  return (
    <SeparationFlow
      title="Music Converter"
      subtitle="Convert your audio to MP3, WAV, FLAC, OGG or M4A — no AI separation, just fast format conversion."
      convertOnly
      submitLabel="Convert file"
    />
  );
}
