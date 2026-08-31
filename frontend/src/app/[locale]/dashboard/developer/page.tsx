import { Suspense } from "react";
import { DeveloperView } from "@/components/dashboard/developer-view";

export const dynamic = "force-dynamic";

export default async function DeveloperPage() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-3xl w-full mx-auto space-y-5">
        <Suspense fallback={null}>
          <DeveloperView />
        </Suspense>
      </div>
    </main>
  );
}
