"use client";

import { SeparationFlow } from "@/components/SeparationFlow";

export default function KaraokePage() {
  return (
    <SeparationFlow
      title="Karaoke Maker"
      subtitle="Removes the lead vocal as effectively as the model allows; keeps the instrumental backing. Perfect for sing-alongs and practice."
      fixedMode="karaoke"
      submitLabel="Make my karaoke track"
    />
  );
}
