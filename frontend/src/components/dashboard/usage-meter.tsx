"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { LocalTime } from "@/components/local-time";
import { cn } from "@/lib/utils";
import { usageApi, type Usage } from "@/lib/backend";

// Mirrors main.py's _fmt_tokens exactly — 1,000,000 -> "1M", 3,500,000 -> "3.5M".
export function formatTokens(n: number): string {
  if (n >= 1_000_000) {
    const v = n / 1_000_000;
    return `${v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)}M`;
  }
  if (n >= 1_000) return `${Math.floor(n / 1_000)}K`;
  return String(n);
}

export function UsageMeter({ compact = false }: { compact?: boolean }) {
  const t = useTranslations("dashboard.usageMeter");
  const [u, setU] = useState<Usage | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    usageApi
      .current()
      .then(setU)
      .catch((e) => setErr(e instanceof Error ? e.message : "Could not load usage"));
  }, []);

  if (err) {
    return (
      <div className="text-xs text-destructive">{err}</div>
    );
  }
  if (!u) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" />
        {t("loading")}
      </div>
    );
  }

  const pct = u.limit > 0 ? Math.min(100, (u.used / u.limit) * 100) : 0;
  const tone =
    pct >= 95
      ? "bg-destructive"
      : pct >= 80
        ? "bg-orange-500"
        : "bg-foreground";
  const labelTone =
    pct >= 95 ? "text-destructive" : pct >= 80 ? "text-orange-600" : "text-foreground";

  if (compact) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between text-xs">
          <span className={cn("font-medium", labelTone)}>
            {formatTokens(u.used)} / {formatTokens(u.limit)} tokens
          </span>
          <span className="text-muted-foreground">
            {t("resetsLower")} <LocalTime iso={u.resets_at} mode="datetime" />
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className={cn("h-full transition-all", tone)}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {t("tokensThisMonth")}
          </div>
          <div className={cn("mt-1 text-2xl font-semibold tracking-tight", labelTone)}>
            {formatTokens(u.used)}
            <span className="text-base text-muted-foreground font-normal">
              {" "}
              / {formatTokens(u.limit)}
            </span>
          </div>
        </div>
        <div className="text-right text-[11px] text-muted-foreground">
          {t("resets")} <LocalTime iso={u.resets_at} mode="datetime" />
        </div>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full transition-all", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {pct >= 80 && pct < 100 && (
        <p className="mt-2 text-[11px] text-orange-700">
          {t("nearLimit")}
        </p>
      )}
      {pct >= 100 && (
        <p className="mt-2 text-[11px] text-destructive">
          {t("atLimit")}
        </p>
      )}
    </div>
  );
}
