"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Mail, CalendarClock, UserRound } from "lucide-react";
import { accountManagerApi, type AccountManager } from "@/lib/backend";

export function AccountManagerCard() {
  const t = useTranslations("dashboard.accountManager");
  const [mgr, setMgr] = useState<AccountManager | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    accountManagerApi
      .get()
      .then(setMgr)
      .catch((e) => setErr(e instanceof Error ? e.message : "Could not load"));
  }, []);

  if (err) return null;
  if (!mgr) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" /> {t("loading")}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">
        {t("heading")}
      </div>
      <div className="flex items-center gap-3">
        <div className="size-9 rounded-full bg-muted flex items-center justify-center shrink-0">
          <UserRound className="size-4 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold truncate">{mgr.name}</p>
          {!mgr.assigned && (
            <p className="text-[11px] text-muted-foreground">{t("sharedDesk")}</p>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <a
          href={`mailto:${mgr.email}`}
          className="inline-flex items-center gap-1.5 text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted transition-colors"
        >
          <Mail className="size-3.5" /> {mgr.email}
        </a>
        {mgr.calendly_url && (
          <a
            href={mgr.calendly_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs rounded-lg border border-border px-3 py-1.5 hover:bg-muted transition-colors"
          >
            <CalendarClock className="size-3.5" /> {t("bookTime")}
          </a>
        )}
      </div>
    </div>
  );
}
