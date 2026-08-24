import { CalendarView } from "@/components/dashboard/calendar-view";

export const dynamic = "force-dynamic";

export default function CalendarPage() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-4xl w-full mx-auto space-y-5">
        <CalendarView />
      </div>
    </main>
  );
}
