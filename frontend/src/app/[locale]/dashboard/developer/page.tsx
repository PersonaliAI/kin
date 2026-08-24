import { Suspense } from "react";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";
import { DeveloperView } from "@/components/dashboard/developer-view";

export const dynamic = "force-dynamic";

export default async function DeveloperPage() {
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();
  const { data } = await supabase.from("users").select("plan").eq("id", kin.id).single();
  const plan = (data?.plan as string) ?? "free";

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-3xl w-full mx-auto space-y-5">
        <Suspense fallback={null}>
          <DeveloperView plan={plan} />
        </Suspense>
      </div>
    </main>
  );
}
