import { InboxView } from "@/components/dashboard/inbox-view";

export const dynamic = "force-dynamic";

export default function InboxPage() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-5">
        <InboxView />
      </div>
    </main>
  );
}
