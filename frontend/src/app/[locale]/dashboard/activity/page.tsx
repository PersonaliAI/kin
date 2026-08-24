import {
  ActivityList,
  type ActivityRow,
} from "@/components/dashboard/activity-list";
import { Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function ActivityPage() {
  const t = await getTranslations("dashboard.activity");
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const { data } = await supabase
    .from("messages")
    .select(
      "id, role, content, source, session_id, latency_ms, model, error, created_at",
    )
    .eq("user_id", kin.id)
    .order("created_at", { ascending: false })
    .limit(200);

  const rows = (data ?? []) as ActivityRow[];

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-6">
        {rows.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-12 text-center">
            <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
              <Sparkles className="size-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold">{t("emptyTitle")}</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {t("emptySub")}
            </p>
          </div>
        ) : (
          <ActivityList initialRows={rows} />
        )}
      </div>
    </main>
  );
}
