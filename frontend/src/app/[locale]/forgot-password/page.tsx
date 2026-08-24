"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthShell } from "@/components/auth/auth-shell";
import { createClient } from "@/lib/supabase/client";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth.forgotPassword");
  const supabase = createClient();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handle(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    setError(null);
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${origin}/reset-password`,
    });
    setBusy(false);
    if (error) {
      setError(error.message);
      return;
    }
    setSent(true);
  }

  if (sent) {
    return (
      <AuthShell title={t("checkEmailTitle")} subtitle={t("checkEmailSubtitle")}>
        <div className="text-center py-4">
          <div className="size-12 mx-auto rounded-full bg-emerald-50 grid place-items-center text-emerald-600 mb-3">
            <CheckCircle2 className="size-6" />
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t("resetSentPrefix")} <b>{email}</b>, {t("resetSentSuffix")}
            <br />
            {t("clickToSetNew")}
          </p>
          <Link
            href="/login"
            className="mt-4 inline-block text-[11px] text-muted-foreground hover:text-foreground underline underline-offset-4"
          >
            {t("backToSignIn")}
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={t("title")}
      subtitle={t("subtitle")}
      footer={
        <>
          {t("rememberedIt")}{" "}
          <Link href="/login" className="font-medium text-foreground hover:underline">
            {t("backToSignIn")}
          </Link>
        </>
      }
    >
      <form onSubmit={handle} className="space-y-3">
        <div className="space-y-1.5">
          <label htmlFor="email" className="text-xs font-medium text-foreground/80">
            {t("emailLabel")}
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={busy}
            placeholder="name@example.com"
            className="w-full h-10 px-3 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 disabled:opacity-60"
          />
        </div>
        <Button
          type="submit"
          className="w-full h-10 font-medium cursor-pointer mt-2"
          disabled={!email.trim() || busy}
        >
          {busy && <Loader2 className="size-4 animate-spin" />}
          {t("sendLink")}
        </Button>
        {error && (
          <div className="flex items-start gap-2 text-xs text-destructive">
            <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </form>
    </AuthShell>
  );
}
