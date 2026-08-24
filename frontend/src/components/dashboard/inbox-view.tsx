"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Mail, Loader2, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NotConnected } from "./not-connected";
import { integrations, type GmailMessage } from "@/lib/backend";
import { cn } from "@/lib/utils";

function fmtWhen(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function senderName(from: string): string {
  // "Alex Rivera <alex@example.com>" → "Alex Rivera"
  const m = from.match(/^"?([^"<]+?)"?\s*</);
  return (m ? m[1] : from).trim() || from;
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

export function InboxView() {
  const t = useTranslations("dashboard.inbox");
  const tNotConnected = useTranslations("dashboard.notConnected");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [messages, setMessages] = useState<GmailMessage[]>([]);
  const [sourceFilter, setSourceFilter] = useState<"all" | "google" | "microsoft">("all");
  const [connected, setConnected] = useState<{ google: boolean; microsoft: boolean }>({
    google: false,
    microsoft: false,
  });
  const [error, setError] = useState<string | null>(null);

  async function load(initial = false) {
    if (initial) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await integrations.gmail();
      setConnected(res.connected);
      setMessages(res.messages);
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

  const visible = messages.filter((m) =>
    sourceFilter === "all" ? true : m.source === sourceFilter,
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-12 grid place-items-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  if (!connected.google && !connected.microsoft) return <NotConnected what={tNotConnected("nouns.inbox")} />;

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

        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          {visible.length === 0 ? (
            <div className="p-12 text-center">
              <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
                <Mail className="size-5" />
              </div>
              <h3 className="mt-4 text-sm font-semibold">
                {sourceFilter === "all" ? t("inboxZero") : t("noSourceMessages", { source: t(`filters.${sourceFilter}`) })}
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("nothingNew")}
              </p>
            </div>
          ) : (
            visible.map((m) => (
              <a
                key={m.id}
                href={m.url}
                target="_blank"
                rel="noreferrer"
                className="flex items-start gap-3 p-4 hover:bg-muted/40 transition-colors group"
              >
                <div className="size-1.5 mt-2 rounded-full shrink-0">
                  {m.unread ? (
                    <span className="block size-1.5 rounded-full bg-orange-500" />
                  ) : (
                    <span className="block size-1.5 rounded-full bg-transparent" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-sm">
                    <span
                      className={`truncate ${m.unread ? "font-semibold" : "font-medium"}`}
                    >
                      {senderName(m.from)}
                    </span>
                    <SourceIcon source={m.source} />
                    <span className="text-[11px] text-muted-foreground shrink-0">
                      {fmtWhen(m.received_at)}
                    </span>
                  </div>
                  <div className="text-sm truncate text-foreground/90">{m.subject}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground line-clamp-1">
                    {m.snippet}
                  </div>
                </div>
                <ExternalLink className="size-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </a>
            ))
          )}
        </div>
      </div>
    </>
  );
}
