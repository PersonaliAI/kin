import { getTranslations, getLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { CheckCircle2, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UpgradeButton } from "@/components/dashboard/upgrade-modal";
import { UsageMeter } from "@/components/dashboard/usage-meter";
import { AccountManagerCard } from "@/components/dashboard/account-manager-card";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

const PLAN_IDS = ["free", "basic", "pro", "executive"] as const;

const CUSTOMER_PORTAL = process.env.NEXT_PUBLIC_LEMON_PORTAL_URL ?? "";

export default async function BillingPage() {
  const t = await getTranslations("dashboard.billing");
  const locale = await getLocale();
  const { authEmail, kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const { data } = await supabase
    .from("users")
    .select("plan, subscription_status, subscription_renews_at, lemon_customer_id")
    .eq("id", kin.id)
    .single();

  const plan = (data?.plan as string) ?? "free";
  const status = (data?.subscription_status as string) ?? null;
  const renewsAt = data?.subscription_renews_at as string | null;
  const isPaid = ["active", "on_trial", "paused"].includes(status ?? "");
  const features = (PLAN_IDS as readonly string[]).includes(plan)
    ? (t.raw(`planFeatures.${plan}`) as string[])
    : (t.raw("planFeatures.free") as string[]);

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-3xl w-full mx-auto space-y-5">
        <UsageMeter />

        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                {t("currentPlan")}
              </div>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-xl font-semibold capitalize">{plan}</span>
                {status && (
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                      isPaid
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <span
                      className={`size-1.5 rounded-full ${
                        isPaid ? "bg-emerald-500" : "bg-muted-foreground/50"
                      }`}
                    />
                    {status}
                  </span>
                )}
              </div>
              {renewsAt && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t("renews", {
                    date: new Date(renewsAt).toLocaleDateString(locale, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    }),
                  })}
                </div>
              )}
            </div>
            <div className="shrink-0 flex items-center gap-2">
              {isPaid && CUSTOMER_PORTAL ? (
                <Button
                  variant="outline"
                  className="cursor-pointer"
                  render={<Link href={CUSTOMER_PORTAL} target="_blank" />}
                >
                  {t("manageSubscription")} <ArrowUpRight className="size-3.5" />
                </Button>
              ) : (
                <UpgradeButton currentPlan={plan} label={plan === "free" ? t("upgrade") : t("changePlan")} />
              )}
            </div>
          </div>

          <ul className="mt-5 grid sm:grid-cols-2 gap-2">
            {features.map((f) => (
              <li key={f} className="flex items-start gap-2 text-xs text-foreground/80">
                <CheckCircle2 className="size-3.5 text-emerald-600 mt-0.5 shrink-0" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {plan === "executive" && <AccountManagerCard />}

        <p className="text-xs text-muted-foreground px-1">
          {t.rich("billingNotice", { email: authEmail, b: (chunks) => <b>{chunks}</b> })}
        </p>
      </div>
    </main>
  );
}
