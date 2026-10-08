"use client";

import { SeparationFlow } from "@/components/SeparationFlow";

export default function ExtractPage() {
  return (
    <SeparationFlow
      title="Instrument Extractor"
      subtitle="Split a track into its individual instruments — or pick exactly which stems you want with the custom option."
      allowedModes={["instruments", "custom"]}
      submitLabel="Extract instruments"
    />
  );
}
