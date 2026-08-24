"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import Image from "next/image";
import { motion } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  Check,
  Loader2,
  Sparkles,
  User,
  Globe,
  Shield,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SearchSelect, type SelectOption } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";
import { COUNTRIES, detectCountryFromTimezone } from "@/lib/countries";
import {
  detectTimezone,
  listTimezones,
  formatTimezone,
  offsetLabel,
} from "@/lib/timezones";
import { logSignUpOnce } from "@/lib/analytics";

const STEP_ICONS = [User, Globe, Shield] as const;

export default function OnboardingPage() {
  return (
    <Suspense fallback={null}>
      <OnboardingPageInner />
    </Suspense>
  );
}

function OnboardingPageInner() {
  const t = useTranslations("auth.onboarding");
  const STEPS = [
    { id: 1, title: t("steps.profile"), icon: STEP_ICONS[0] },
    { id: 2, title: t("steps.location"), icon: STEP_ICONS[1] },
    { id: 3, title: t("steps.terms"), icon: STEP_ICONS[2] },
  ] as const;
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const supabase = createClient();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [country, setCountry] = useState("");
  const [marketingOk, setMarketingOk] = useState(true);
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  // Detect once on mount + prefill from existing user row
  useEffect(() => {
    const tz = detectTimezone();
    setTimezone(tz);
    setCountry(detectCountryFromTimezone(tz) ?? "");
    (async () => {
      const { data } = await supabase.auth.getUser();
      const meta = (data.user?.user_metadata ?? {}) as Record<string, unknown>;
      const name =
        (meta.full_name as string) ||
        (meta.name as string) ||
        (data.user?.email?.split("@")[0] ?? "");
      setDisplayName(name);
    })();
  }, [supabase]);

  const timezoneOptions: SelectOption[] = useMemo(() => {
    return listTimezones().map((tz) => ({
      value: tz,
      label: formatTimezone(tz),
      trailing: offsetLabel(tz),
    }));
  }, []);

  const countryOptions: SelectOption[] = useMemo(() => {
    return COUNTRIES.map((c) => ({
      value: c.code,
      label: c.name,
      leading: <span className="text-base leading-none">{c.flag}</span>,
    }));
  }, []);

  const canContinue =
    (step === 1 && displayName.trim().length >= 2) ||
    (step === 2 && !!timezone && !!country) ||
    (step === 3 && acceptedTerms);

  function next() {
    if (!canContinue) return;
    if (step < STEPS.length) setStep((s) => s + 1);
    else finish();
  }
  function prev() {
    if (step > 1) setStep((s) => s - 1);
  }

  async function finish() {
    setBusy(true);
    setError(null);
    const { data: auth } = await supabase.auth.getUser();
    if (!auth.user) {
      setError(t("sessionExpired"));
      setBusy(false);
      router.push("/login");
      return;
    }
    const { error } = await supabase
      .from("users")
      .update({
        display_name: displayName.trim(),
        timezone,
        country,
        marketing_opt_in: marketingOk,
        terms_accepted_at: new Date().toISOString(),
        onboarding_completed: true,
      })
      .eq("auth_user_id", auth.user.id);
    if (error) {
      setError(error.message);
      setBusy(false);
      return;
    }
    const provider = auth.user.app_metadata?.provider;
    const method = provider === "google" ? "google" : provider === "azure" ? "microsoft" : "password";
    await logSignUpOnce(method);
    window.location.href = nextPath && nextPath.startsWith("/") ? nextPath : "/dashboard";
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 relative overflow-hidden">
      <div
        className="absolute inset-0 z-0 pointer-events-none opacity-50"
        style={{
          backgroundImage:
            "radial-gradient(circle, #d4d4d4 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />

      <div className="w-full max-w-xl z-10">
        <div className="flex justify-center mb-6">
          <Link href="/" className="flex items-center">
            <Image
              src="/logo.webp"
              alt="PersonaliAI"
              width={140}
              height={28}
              className="h-6 w-auto dark:invert dark:hue-rotate-180"
            />
          </Link>
        </div>

        <div className="bg-card border border-border rounded-2xl p-6 md:p-8 shadow-sm">
          {/* Progress */}
          <div className="flex items-center justify-between mb-6">
            {STEPS.map((s, i) => {
              const reached = step >= s.id;
              const active = step === s.id;
              return (
                <div
                  key={s.id}
                  className="flex items-center gap-3 flex-1 last:flex-none"
                >
                  <div
                    className={cn(
                      "size-7 rounded-full grid place-items-center text-[11px] font-semibold transition-colors",
                      active
                        ? "bg-foreground text-background"
                        : reached
                          ? "bg-foreground/80 text-background"
                          : "bg-muted text-muted-foreground",
                    )}
                  >
                    {step > s.id ? <Check className="size-3.5" /> : s.id}
                  </div>
                  <div className="hidden sm:block">
                    <div
                      className={cn(
                        "text-[11px] font-medium whitespace-nowrap",
                        reached ? "text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {s.title}
                    </div>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className="hidden sm:block flex-1 h-px bg-border" />
                  )}
                </div>
              );
            })}
          </div>

          {/* Content */}
          <div className="min-h-[280px]">
            {/* Keyed by `step`, deliberately WITHOUT AnimatePresence: that
                was tried first (single child, key={step}, mode="wait") and
                still got stuck — the exit transition never completed
                (element left mounted at opacity:0 indefinitely), so the
                content pane silently stayed on step 1 forever while the
                progress indicator and buttons (which read `step` directly,
                no animation involved) had already moved on. Same failure
                mode as the landing page's hero chat demo. Dropping
                AnimatePresence removes the dependency on exit-completion
                entirely: React swaps the subtree by key unconditionally,
                and the mount (`initial`/`animate`) animation still plays
                without needing an exit phase to coordinate with. */}
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.18 }}
                className="space-y-5"
              >
                {step === 1 && (
                  <>
                    <Heading
                      icon={<Sparkles className="size-4" />}
                      eyebrow={t("step1.eyebrow")}
                      title={t("step1.title")}
                      sub={t("step1.sub")}
                    />
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-foreground/80">
                        {t("step1.displayNameLabel")}
                      </label>
                      <input
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder={t("step1.displayNamePlaceholder")}
                        autoFocus
                        className="w-full h-10 px-3 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20"
                      />
                      <p className="text-[11px] text-muted-foreground">
                        {t("step1.displayNameHint")}
                      </p>
                    </div>
                  </>
                )}

                {step === 2 && (
                  <>
                    <Heading
                      icon={<Globe className="size-4" />}
                      eyebrow={t("step2.eyebrow")}
                      title={t("step2.title")}
                      sub={t("step2.sub")}
                    />
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-foreground/80">
                        {t("step2.timezoneLabel")}
                      </label>
                      <SearchSelect
                        value={timezone}
                        onChange={setTimezone}
                        options={timezoneOptions}
                        placeholder={t("step2.timezonePlaceholder")}
                      />
                      <p className="text-[11px] text-muted-foreground">
                        {t("step2.timezoneHint")}
                      </p>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-foreground/80">
                        {t("step2.countryLabel")}
                      </label>
                      <SearchSelect
                        value={country}
                        onChange={setCountry}
                        options={countryOptions}
                        placeholder={t("step2.countryPlaceholder")}
                      />
                    </div>
                  </>
                )}

                {step === 3 && (
                  <>
                    <Heading
                      icon={<Shield className="size-4" />}
                      eyebrow={t("step3.eyebrow")}
                      title={t("step3.title")}
                      sub={t("step3.sub")}
                    />

                    <div className="bg-background border border-border rounded-xl p-4 h-44 overflow-y-auto text-[11px] text-muted-foreground leading-relaxed space-y-3">
                      <p>
                        <b className="text-foreground">{t("step3.dataRulesTitle")}</b>{" "}
                        {t("step3.dataRulesBody")}
                      </p>
                      <p>
                        <b className="text-foreground">{t("step3.securityTitle")}</b>{" "}
                        {t("step3.securityBody")}
                      </p>
                      <p>
                        <b className="text-foreground">{t("step3.aiTitle")}</b>{" "}
                        {t("step3.aiBodyPrefix")}{" "}
                        <a
                          href="https://personaliai.com/privacy"
                          target="_blank"
                          rel="noreferrer"
                          className="text-foreground underline underline-offset-2"
                        >
                          {t("step3.privacyLink")}
                        </a>
                        .
                      </p>
                      <p>
                        <b className="text-foreground">{t("step3.leaveTitle")}</b>{" "}
                        {t("step3.leaveBody")}
                      </p>
                    </div>

                    <div className="space-y-3">
                      <Toggle
                        checked={acceptedTerms}
                        onChange={setAcceptedTerms}
                        label={
                          <>
                            {t("step3.agreePrefix")}{" "}
                            <a
                              href="https://personaliai.com/terms"
                              target="_blank"
                              rel="noreferrer"
                              className="text-[#f97316] font-semibold underline underline-offset-2"
                            >
                              {t("step3.termsLink")}
                            </a>{" "}
                            {t("step3.and")}{" "}
                            <a
                              href="https://personaliai.com/privacy"
                              target="_blank"
                              rel="noreferrer"
                              className="text-[#f97316] font-semibold underline underline-offset-2"
                            >
                              {t("step3.privacyLink")}
                            </a>
                            .
                          </>
                        }
                      />
                      <Toggle
                        checked={marketingOk}
                        onChange={setMarketingOk}
                        label={t("step3.marketingOptIn")}
                      />
                    </div>
                  </>
                )}
              </motion.div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 flex items-start gap-2 text-xs text-destructive">
              <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between pt-6 mt-2 border-t border-border">
            <Button
              variant="outline"
              type="button"
              onClick={prev}
              disabled={step === 1 || busy}
              className="h-10 px-5 gap-1.5 cursor-pointer"
            >
              <ChevronLeft className="size-4" />
              {t("back")}
            </Button>
            <Button
              type="button"
              onClick={next}
              disabled={!canContinue || busy}
              className="h-10 px-5 gap-1.5 cursor-pointer"
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : null}
              {step === STEPS.length ? t("finishSetup") : t("continueBtn")}
              {step !== STEPS.length && <ChevronRight className="size-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Heading({
  icon,
  eyebrow,
  title,
  sub,
}: {
  icon: React.ReactNode;
  eyebrow: string;
  title: string;
  sub: string;
}) {
  return (
    <div>
      <div className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[#f97316] mb-2">
        <span className="size-5 rounded-md bg-orange-50 grid place-items-center">
          {icon}
        </span>
        {eyebrow}
      </div>
      <h2 className="text-xl md:text-2xl font-bold tracking-tight">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{sub}</p>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: React.ReactNode;
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <span className="relative shrink-0 mt-0.5">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <span className="block size-5 rounded border border-border bg-background peer-checked:bg-foreground peer-checked:border-foreground transition-colors" />
        <Check className="absolute inset-0 m-auto size-3 text-background opacity-0 peer-has-[input:checked]:opacity-100 pointer-events-none" />
      </span>
      <span className="text-xs leading-relaxed">{label}</span>
    </label>
  );
}
