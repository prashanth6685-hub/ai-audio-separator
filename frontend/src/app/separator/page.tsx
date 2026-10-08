"use client";

import { SeparationFlow } from "@/components/SeparationFlow";

export default function SeparatorPage() {
  return (
    <SeparationFlow
      title="AI Audio Separator"
      subtitle="Upload a song and split it into vocals, drums, bass, and more — pick exactly what you need below."
      submitLabel="Start separation"
    />
  );
}
