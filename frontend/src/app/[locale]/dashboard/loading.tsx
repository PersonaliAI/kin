export default function Loading() {
  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-6xl w-full mx-auto space-y-5 animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl bg-card border border-border p-4 h-24" />
          ))}
        </div>
        <div className="rounded-xl border border-border bg-card h-64" />
      </div>
    </main>
  );
}
