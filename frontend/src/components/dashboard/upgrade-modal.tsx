"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import { Check, ArrowUpRight, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const PLAN_IDS = ["free", "basic", "pro", "executive"] as const;
type PlanId = (typeof PLAN_IDS)[number];
const PLAN_META: Record<PlanId, { price: string; period: string; highlighted?: boolean }> = {
  free: { price: "$0", period: "" },
  basic: { price: "$5.99", period: "/mo" },
  pro: { price: "$19", period: "/mo", highlighted: true },
  executive: { price: "$59", period: "/mo" },
};

async function getCheckoutUrl(plan: string): Promise<string> {
  const res = await fetch("/api/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan }),
  });
  const json = await res.json();
  if (!res.ok || !json.url) throw new Error(json.error ?? "Checkout unavailable");
  return json.url;
}

export function UpgradeButton({
  currentPlan,
  label,
}: {
  currentPlan: string;
  label?: string;
}) {
  const t = useTranslations("dashboard.upgradeModal");
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button className="cursor-pointer" onClick={() => setOpen(true)}>
        {label ?? t("upgradeNow")} <ArrowUpRight className="size-3.5" />
      </Button>
      <UpgradeModal open={open} onClose={() => setOpen(false)} currentPlan={currentPlan} />
    </>
  );
}

function UpgradeModal({
  open,
  onClose,
  currentPlan,
}: {
  open: boolean;
  onClose: () => void;
  currentPlan: string;
}) {
  const t = useTranslations("dashboard.upgradeModal");
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function checkout(planId: string) {
    setLoading(planId);
    setError(null);
    try {
      const url = await getCheckoutUrl(planId);
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : t("checkoutUnavailable"));
      setLoading(null);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-foreground/20 backdrop-blur-sm"
          />
          <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-3 sm:p-4 pointer-events-none overflow-y-auto">
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.15 }}
              className="pointer-events-auto w-full max-w-5xl bg-card border border-border rounded-2xl shadow-xl overflow-hidden my-4 sm:my-8 max-h-[calc(100vh-2rem)] flex flex-col"
            >
              <div className="flex items-start justify-between px-5 sm:px-6 pt-5 sm:pt-6 pb-2 shrink-0">
                <div>
                  <h3 className="text-base sm:text-lg font-semibold">{t("heading")}</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t("sub")}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="p-1.5 -m-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted shrink-0"
                  aria-label={t("close")}
                >
                  <X className="size-4" />
                </button>
              </div>

              {error && (
                <p className="mx-4 sm:mx-6 mt-2 text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 p-4 sm:p-6 overflow-y-auto">
                {PLAN_IDS.map((planId) => {
                  const meta = PLAN_META[planId];
                  const features = t.raw(`plans.${planId}.features`) as string[];
                  const isCurrent = planId === currentPlan;
                  const isPaid = planId !== "free";
                  const isLoading = loading === planId;
                  return (
                    <div
                      key={planId}
                      className={`rounded-xl border p-4 sm:p-5 flex flex-col ${
                        meta.highlighted
                          ? "border-foreground/20 bg-card ring-1 ring-orange-100"
                          : "border-border bg-card"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-sm font-semibold">{t(`plans.${planId}.name`)}</h4>
                        {meta.highlighted && (
                          <span className="text-[10px] font-medium text-[#f97316] bg-[#f97316]/10 rounded px-1.5 py-0.5">
                            {t("mostPopular")}
                          </span>
                        )}
                      </div>
                      <div className="flex items-baseline gap-0.5 mb-4">
                        <span className="text-2xl font-bold tracking-tight">{meta.price}</span>
                        <span className="text-xs text-muted-foreground">{meta.period}</span>
                      </div>

                      {isCurrent ? (
                        <Button variant="outline" className="w-full mb-4 cursor-not-allowed opacity-70" disabled>
                          {t("currentPlan")}
                        </Button>
                      ) : isPaid ? (
                        <Button
                          variant={meta.highlighted ? "default" : "outline"}
                          className="w-full mb-4 cursor-pointer gap-1.5"
                          disabled={loading !== null}
                          onClick={() => checkout(planId)}
                        >
                          {isLoading && <Loader2 className="size-3.5 animate-spin" />}
                          {isLoading ? t("loading") : t("upgradeNow")}
                        </Button>
                      ) : (
                        <Button variant="outline" className="w-full mb-4 cursor-pointer" onClick={onClose}>
                          {t("stayFree")}
                        </Button>
                      )}

                      <ul className="space-y-2 text-xs text-muted-foreground">
                        {features.map((f) => (
                          <li key={f} className="flex items-start gap-2">
                            <Check className="size-3.5 mt-0.5 shrink-0 text-emerald-600" />
                            {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
