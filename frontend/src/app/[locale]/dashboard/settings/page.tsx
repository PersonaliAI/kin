import { SettingsView } from "@/components/dashboard/settings-view";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const { authName, kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const { data } = await supabase
    .from("users")
    .select(
      "display_name, timezone, country, system_prompt, briefing_enabled, briefing_time, marketing_opt_in, memory_enabled, confirm_before_write, email_followups_enabled, email_signature_enabled, email_signature_name, email_signature_title, email_signature_phone, email_signature_links, plan",
    )
    .eq("id", kin.id)
    .single();

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-2xl w-full mx-auto">
        <SettingsView
          plan={(data?.plan as string) ?? "free"}
          initial={{
            display_name: (data?.display_name as string) ?? authName,
            timezone: (data?.timezone as string) ?? "UTC",
            country: (data?.country as string) ?? null,
            system_prompt: (data?.system_prompt as string) ?? null,
            briefing_enabled: (data?.briefing_enabled as boolean) ?? false,
            briefing_time: ((data?.briefing_time as string) ?? "08:00:00").toString(),
            marketing_opt_in: (data?.marketing_opt_in as boolean) ?? false,
            memory_enabled: (data?.memory_enabled as boolean) ?? true,
            confirm_before_write: (data?.confirm_before_write as boolean) ?? true,
            email_followups_enabled: (data?.email_followups_enabled as boolean) ?? true,
            email_signature_enabled: (data?.email_signature_enabled as boolean) ?? false,
            email_signature_name: (data?.email_signature_name as string) ?? "",
            email_signature_title: (data?.email_signature_title as string) ?? "",
            email_signature_phone: (data?.email_signature_phone as string) ?? "",
            email_signature_links:
              (data?.email_signature_links as { label?: string; url: string }[]) ?? [],
          }}
        />
      </div>
    </main>
  );
}
