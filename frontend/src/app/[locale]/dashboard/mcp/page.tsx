import { Suspense } from "react";
import { McpView } from "@/components/dashboard/mcp-view";

export const dynamic = "force-dynamic";

export default async function McpPage() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-3xl w-full mx-auto space-y-4">
        <Suspense fallback={null}>
          <McpView />
        </Suspense>
      </div>
    </main>
  );
}
