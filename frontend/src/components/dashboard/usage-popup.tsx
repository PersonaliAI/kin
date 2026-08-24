"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { BarChart3, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/dashboard/dialog";
import { formatTokens } from "@/components/dashboard/usage-meter";
import { cn } from "@/lib/utils";
import {
  llmUsageApi,
  type LlmUsage,
  type LlmUsagePeriod,
} from "@/lib/backend";

function formatCost(n: number): string {
  return `$${n.toFixed(2)}`;
}

export function UsageDetailsButton() {
  const t = useTranslations("dashboard.usagePopup");
  const [open, setOpen] = useState(false);
  const [usage, setUsage] = useState<LlmUsage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openDialog() {
    setOpen(true);
    if (!usage && !loading) {
      setLoading(true);
      setError(null);
      llmUsageApi
        .current()
        .then(setUsage)
        .catch((e) => setError(e instanceof Error ? e.message : t("loadError")))
        .finally(() => setLoading(false));
    }
  }

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="cursor-pointer"
        onClick={openDialog}
      >
        <BarChart3 className="size-3.5" />
        {t("trigger")}
      </Button>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={t("title")}
        description={t("description")}
        size="lg"
      >
        {loading && (
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground py-8">
            <Loader2 className="size-3.5 animate-spin" />
            {t("loading")}
          </div>
        )}
        {error && !loading && (
          <div className="flex items-center gap-2 text-xs text-destructive py-4">
            <AlertCircle className="size-3.5 shrink-0" />
            {error}
          </div>
        )}
        {usage && !loading && !error && (
          <div className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <PeriodSummary label={t("thisMonth")} period={usage.month} big />
              <PeriodSummary label={t("last7Days")} period={usage.last_7_days} />
            </div>
            <Breakdown
              title={t("byModel")}
              emptyLabel={t("noData")}
              rows={usage.month.by_model.map((r) => ({
                key: `${r.provider}/${r.model}`,
                name: r.model,
                sub: r.provider,
                cost: r.cost_usd,
                tokens: r.tokens,
                calls: r.calls,
              }))}
            />
            <Breakdown
              title={t("byFeature")}
              emptyLabel={t("noData")}
              rows={usage.month.by_feature.map((r) => ({
                key: r.feature,
                name: r.feature,
                cost: r.cost_usd,
                tokens: r.tokens,
                calls: r.calls,
              }))}
            />
          </div>
        )}
      </Dialog>
    </>
  );
}

function PeriodSummary({
  label,
  period,
  big,
}: {
  label: string;
  period: LlmUsagePeriod;
  big?: boolean;
}) {
  const t = useTranslations("dashboard.usagePopup");
  return (
    <div
      className={cn(
        "rounded-lg border border-border p-3",
        big ? "bg-muted/30" : "bg-transparent",
      )}
    >
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-baseline gap-2 flex-wrap">
        <span className={big ? "text-xl font-semibold" : "text-sm font-semibold"}>
          {formatCost(period.total_cost_usd)}
        </span>
        <span className="text-[11px] text-muted-foreground">
          {formatTokens(period.total_tokens)} {t("tokens")}
        </span>
      </div>
      {period.unknown_cost_calls > 0 && (
        <p className="mt-1 text-[10px] text-muted-foreground">
          {t("unknownCostNote", { count: period.unknown_cost_calls })}
        </p>
      )}
    </div>
  );
}

function Breakdown({
  title,
  rows,
  emptyLabel,
}: {
  title: string;
  emptyLabel: string;
  rows: { key: string; name: string; sub?: string; cost: number; tokens: number; calls: number }[];
}) {
  const t = useTranslations("dashboard.usagePopup");
  return (
    <div>
      <div className="text-xs font-semibold mb-2">{title}</div>
      {rows.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">{emptyLabel}</p>
      ) : (
        <div className="rounded-lg border border-border divide-y divide-border overflow-hidden">
          {rows.map((r) => (
            <div key={r.key} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
              <div className="min-w-0">
                <div className="font-medium truncate">{r.name}</div>
                {r.sub && <div className="text-[10px] text-muted-foreground truncate">{r.sub}</div>}
              </div>
              <div className="text-right shrink-0">
                <div className="font-medium">{formatCost(r.cost)}</div>
                <div className="text-[10px] text-muted-foreground">
                  {formatTokens(r.tokens)} · {t("callsCount", { count: r.calls })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
