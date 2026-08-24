import { DocumentsView } from "@/components/dashboard/documents-view";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function DocumentsPage() {
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();
  const { data } = await supabase
    .from("users")
    .select("google_email, microsoft_email")
    .eq("id", kin.id)
    .single();

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-5">
        <DocumentsView
          googleConnected={!!data?.google_email}
          microsoftConnected={!!data?.microsoft_email}
        />
      </div>
    </main>
  );
}
