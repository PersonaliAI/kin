import { TasksView } from "@/components/dashboard/tasks-view";
import { type Task } from "@/lib/backend";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function TasksPage() {
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const { data } = await supabase
    .from("tasks")
    .select("id, title, description, status, priority, due_date, updated_at")
    .eq("user_id", kin.id)
    .order("created_at", { ascending: false });

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-5">
        <TasksView initial={(data ?? []) as Task[]} userId={kin.id} />
      </div>
    </main>
  );
}
