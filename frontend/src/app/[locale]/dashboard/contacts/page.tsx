import { ContactsView, type Contact } from "@/components/dashboard/contacts-view";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function ContactsPage() {
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const { data } = await supabase
    .from("contacts")
    .select("id, name, email, phone, company, notes, updated_at")
    .eq("user_id", kin.id)
    .order("name", { ascending: true });

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-5">
        <ContactsView initial={(data ?? []) as Contact[]} userId={kin.id} />
      </div>
    </main>
  );
}
