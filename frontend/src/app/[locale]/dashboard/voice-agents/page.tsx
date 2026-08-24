import { Suspense } from "react";
import { VoiceAgentsView } from "@/components/dashboard/voice-agents-view";

export const dynamic = "force-dynamic";

export default async function VoiceAgentsPage() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-4">
        <Suspense fallback={null}>
          <VoiceAgentsView />
        </Suspense>
      </div>
    </main>
  );
}
