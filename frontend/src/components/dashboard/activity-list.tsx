"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { MessageSquare, Send, Sun, AlertCircle, Sparkles, RefreshCw } from "lucide-react";
import { LocalTime, localDayKey } from "@/components/local-time";
import { Markdown } from "@/components/markdown";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";

export type ActivityRow = {
  id: string;
  role: "user" | "assistant" | string;
  content: string | null;
  source: string;
  session_id: string | null;
  latency_ms: number | null;
  model: string | null;
  error: string | null;
  created_at: string;
};

const SOURCE_ICON: Record<string, { icon: typeof MessageSquare; tone: string }> = {
  web: { icon: MessageSquare, tone: "bg-blue-50 text-blue-600" },
  telegram: { icon: Send, tone: "bg-sky-50 text-sky-600" },
  cron: { icon: Sun, tone: "bg-amber-50 text-amber-600" },
};

const FILTER_IDS = ["all", "web", "telegram", "cron"] as const;
type FilterId = (typeof FILTER_IDS)[number];

export function ActivityList({ initialRows }: { initialRows: ActivityRow[] }) {
  const t = useTranslations("dashboard.activity");
  const [rows, setRows] = useState(initialRows);
  const [filter, setFilter] = useState<FilterId>("all");
  const [polling, setPolling] = useState(false);
  const supabase = createClient();

  useEffect(() => {
    const interval = setInterval(async () => {
      setPolling(true);
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        const { data } = await supabase
          .from("messages")
          .select("id, role, content, source, session_id, latency_ms, model, error, created_at")
          .eq("user_id", user.id)
          .order("created_at", { ascending: false })
          .limit(200);
        if (data) setRows(data as ActivityRow[]);
      } catch (e) {
        console.error("Activity poll failed", e);
      } finally {
        setPolling(false);
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [supabase]);

  const filtered = useMemo(
    () => (filter === "all" ? rows : rows.filter((r) => r.source === filter)),
    [rows, filter],
  );

  // Group by *user-local* day. Server can't do this safely because Cloud Run
  // runs UTC.
  const groups = useMemo(() => {
    const map = new Map<string, ActivityRow[]>();
    for (const r of filtered) {
      const key = localDayKey(r.created_at);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(r);
    }
    return Array.from(map.entries()).map(([key, items]) => ({
      key,
      iso: items[0]?.created_at ?? new Date().toISOString(),
      items,
    }));
  }, [filtered]);

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
          {FILTER_IDS.map((id) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                filter === id
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t(`filters.${id}`)}
            </button>
          ))}
        </div>
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          {polling && <RefreshCw className="size-3 animate-spin" />}
          {t("events", { count: filtered.length })}
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
            <Sparkles className="size-5" />
          </div>
          <h3 className="mt-4 text-sm font-semibold">{t("emptyFilterTitle")}</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("emptyFilterSub")}
          </p>
        </div>
      ) : (
      <>{groups.map((g) => (
        <section key={g.key}>
          <h3 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-2 px-1">
            <LocalTime iso={g.iso} mode="day" />
          </h3>
          <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
            {g.items.map((m) => {
              const meta = SOURCE_ICON[m.source] ?? SOURCE_ICON.web;
              const Icon = meta.icon;
              const sourceLabel = t.has(`filters.${m.source}`) ? t(`filters.${m.source}` as "filters.web") : m.source;
              const errored = !!m.error;
              return (
                <div key={m.id} className="flex items-start gap-4 p-4">
                  <div
                    className={`size-7 shrink-0 rounded-lg grid place-items-center ${meta.tone}`}
                  >
                    <Icon className="size-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span
                        className={`px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider text-[9px] ${
                          m.role === "user"
                            ? "bg-muted text-muted-foreground"
                            : "bg-orange-50 text-orange-600"
                        }`}
                      >
                        {m.role}
                      </span>
                      <span>{sourceLabel}</span>
                      <span>·</span>
                      <LocalTime iso={m.created_at} mode="datetime" />
                      {m.latency_ms != null && (
                        <>
                          <span>·</span>
                          <span>{Math.round(m.latency_ms)}ms</span>
                        </>
                      )}
                    </div>
                    <div className={`mt-1 ${errored ? "text-destructive" : ""}`}>
                      {errored ? (
                        <span className="text-sm flex items-start gap-1.5">
                          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
                          {m.error}
                        </span>
                      ) : m.content ? (
                        m.role === "assistant" ? (
                          <Markdown>{m.content}</Markdown>
                        ) : (
                          <div className="text-sm whitespace-pre-wrap break-words">
                            {m.content}
                          </div>
                        )
                      ) : (
                        <span className="text-sm text-muted-foreground italic">
                          {t("noText")}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}</>)}
    </>
  );
}
