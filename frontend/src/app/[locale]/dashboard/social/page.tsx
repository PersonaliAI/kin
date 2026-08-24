import { Suspense } from "react";
import { SocialView } from "@/components/dashboard/social-view";

export const dynamic = "force-dynamic";

export default async function SocialPage() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-5xl w-full mx-auto space-y-6">
        <Suspense fallback={null}>
          <SocialView />
        </Suspense>
      </div>
    </main>
  );
}
