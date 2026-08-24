import { Suspense } from "react";
import { IntegrationsView } from "@/components/dashboard/integrations-view";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function IntegrationsPage() {
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const { data } = await supabase
    .from("users")
    .select("google_email, microsoft_email, telegram_id, plan")
    .eq("id", kin.id)
    .single();

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-3xl w-full mx-auto space-y-4">
        <Suspense fallback={null}>
          <IntegrationsView
            initialGoogleEmail={(data?.google_email as string) ?? null}
            initialMicrosoftEmail={(data?.microsoft_email as string) ?? null}

            plan={(data?.plan as string) ?? "free"}
          />
        </Suspense>
      </div>
    </main>
  );
}
