"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Calendar, Clock, MapPin, Loader2, ExternalLink, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NotConnected } from "./not-connected";
import { integrations, type CalendarEvent } from "@/lib/backend";
import { cn } from "@/lib/utils";

function groupByDay(events: CalendarEvent[]): [string, CalendarEvent[]][] {
  const map = new Map<string, CalendarEvent[]>();
  for (const e of events) {
    if (!e.start) continue;
    const d = new Date(e.start);
    const key = d.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(e);
  }
  return Array.from(map.entries());
}

export function CalendarView() {
  const t = useTranslations("dashboard.calendar");
  const tNotConnected = useTranslations("dashboard.notConnected");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [sourceFilter, setSourceFilter] = useState<"all" | "google" | "microsoft">("all");
  const [connected, setConnected] = useState<{ google: boolean; microsoft: boolean }>({
    google: false,
    microsoft: false,
  });
  const [error, setError] = useState<string | null>(null);

  function fmtTime(s: string | null, allDay: boolean): string {
    if (!s) return "";
    if (allDay) return t("allDay");
    return new Date(s).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function SourceIcon({ source }: { source?: "google" | "microsoft" }) {
    if (source === "microsoft") {
      return (
        <span className="text-[9px] px-1 py-0.5 rounded bg-blue-50 text-blue-600 font-bold uppercase tracking-tighter">
          MS
        </span>
      );
    }
    return (
      <span className="text-[9px] px-1 py-0.5 rounded bg-red-50 text-red-600 font-bold uppercase tracking-tighter">
        G
      </span>
    );
  }

  async function load(initial = false) {
    if (initial) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await integrations.calendar();
      setConnected(res.connected);
      setEvents(res.events);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = events.filter((e) =>
    sourceFilter === "all" ? true : e.source === sourceFilter,
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-12 grid place-items-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  if (!connected.google && !connected.microsoft) return <NotConnected what={tNotConnected("nouns.calendar")} />;

  const groups = groupByDay(visible);

  return (
    <>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
              {(["all", "google", "microsoft"] as const).map((f) => {
                if (f === "google" && !connected.google) return null;
                if (f === "microsoft" && !connected.microsoft) return null;
                return (
                  <button
                    key={f}
                    onClick={() => setSourceFilter(f)}
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                      sourceFilter === f
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t(`filters.${f}`)}
                  </button>
                );
              })}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => load()}
            disabled={refreshing}
            className="cursor-pointer"
          >
            <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {t("refresh")}
          </Button>
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 text-destructive text-xs px-3 py-2">
            {error}
          </div>
        )}

        {groups.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-12 text-center">
            <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
              <Calendar className="size-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold">
              {sourceFilter === "all" ? t("emptyAllTitle") : t("emptyFilterTitle", { filter: t(`filters.${sourceFilter}`) })}
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {sourceFilter === "all" ? t("emptyAllSub") : t("emptyFilterSub")}
            </p>
          </div>
        ) : (
          groups.map(([day, items]) => (
            <section key={day} className="mb-6 last:mb-0">
              <h3 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-2 px-1">
                {day}
              </h3>
              <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
                {items.map((e) => (
                  <a
                    key={e.id}
                    href={e.html_link ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-start gap-4 p-4 hover:bg-muted/40 transition-colors group"
                  >
                    <div className="w-20 shrink-0">
                      <div className="text-xs font-medium text-foreground">
                        {fmtTime(e.start, e.all_day)}
                      </div>
                      {!e.all_day && e.end && (
                        <div className="text-[11px] text-muted-foreground">
                          {fmtTime(e.end, false)}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="text-sm font-medium truncate">{e.summary}</div>
                        <SourceIcon source={e.source} />
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                        {e.location && (
                          <span className="flex items-center gap-1 truncate">
                            <MapPin className="size-3 shrink-0" />
                            <span className="truncate">{e.location}</span>
                          </span>
                        )}
                        {e.attendees.length > 0 && (
                          <span className="flex items-center gap-1">
                            <Clock className="size-3" />
                            {t("attendee", { count: e.attendees.length })}
                          </span>
                        )}
                      </div>
                    </div>
                    <ExternalLink className="size-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </a>
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </>
  );
}
