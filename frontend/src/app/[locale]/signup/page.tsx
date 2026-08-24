"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Loader2, AlertCircle, Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthShell, GoogleIcon, MicrosoftIcon } from "@/components/auth/auth-shell";
import { createClient } from "@/lib/supabase/client";

type BusyKey = "password" | "google" | "microsoft" | null;

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupPageInner />
    </Suspense>
  );
}

function SignupPageInner() {
  const t = useTranslations("auth.signup");
  const supabase = createClient();
  const searchParams = useSearchParams();
  const rawNext = searchParams.get("next");
  // The ultimate destination once auth (+ onboarding, if needed) is done —
  // defaults to /dashboard. /auth/callback detours through /onboarding on
  // its own when required and forwards this same value onward from there.
  const finalNext = rawNext && rawNext.startsWith("/") ? rawNext : "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [busy, setBusy] = useState<BusyKey>(null);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  function redirect(): string {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    return `${origin}/auth/callback?next=${encodeURIComponent(finalNext)}`;
  }

  async function handlePassword(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password || busy) return;
    if (password.length < 8) {
      setError(t("errors.passwordTooShort"));
      return;
    }
    setBusy("password");
    setError(null);
    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: { emailRedirectTo: redirect() },
    });
    setBusy(null);
    if (error) {
      setError(humanizeAuthError(error.message, t));
      return;
    }
    // If email confirmation is disabled in Supabase, the session is returned
    // immediately — new users always need onboarding, so send them there
    // and carry the final destination (e.g. checkout) along for after.
    if (data.session) {
      window.location.href = `/onboarding?next=${encodeURIComponent(finalNext)}`;
      return;
    }
    setSent(true);
  }

  async function handleOAuth(provider: "google" | "azure") {
    if (busy) return;
    setBusy(provider === "azure" ? "microsoft" : "google");
    setError(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: redirect(),
        queryParams:
          provider === "google"
            ? { access_type: "offline", prompt: "consent" }
            : { prompt: "select_account" },
        scopes: provider === "azure" ? "email openid profile" : undefined,
      },
    });
    if (error) {
      setError(error.message);
      setBusy(null);
    }
  }

  if (sent) {
    return (
      <AuthShell title={t("almostThere")} subtitle={t("confirmEmailSubtitle")}>
        <div className="text-center py-4">
          <div className="size-12 mx-auto rounded-full bg-emerald-50 grid place-items-center text-emerald-600 mb-3">
            <CheckCircle2 className="size-6" />
          </div>
          <h3 className="text-sm font-semibold">{t("checkYourEmail")}</h3>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
            {t("confirmationSentPrefix")} <b>{email}</b>.<br />
            {t("clickToVerify")}
          </p>
          <Link
            href={rawNext ? `/login?next=${encodeURIComponent(rawNext)}` : "/login"}
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
          {t("haveAccount")}{" "}
          <Link
            href={rawNext ? `/login?next=${encodeURIComponent(rawNext)}` : "/login"}
            className="font-medium text-foreground hover:underline"
          >
            {t("signIn")}
          </Link>
        </>
      }
    >
      <form onSubmit={handlePassword} className="space-y-3">
        <div className="space-y-1.5">
          <label htmlFor="email" className="text-xs font-medium text-foreground/80">
            {t("emailLabel")}
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@example.com"
            required
            disabled={busy !== null}
            className="w-full h-10 px-3 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 disabled:opacity-60"
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="password" className="text-xs font-medium text-foreground/80">
            {t("passwordLabel")}
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPwd ? "text" : "password"}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("passwordPlaceholder")}
              required
              minLength={8}
              disabled={busy !== null}
              className="w-full h-10 pl-3 pr-10 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={() => setShowPwd((s) => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground rounded"
              aria-label={showPwd ? "Hide password" : "Show password"}
            >
              {showPwd ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>
        <Button
          type="submit"
          className="w-full h-10 font-medium cursor-pointer mt-4"
          disabled={!email.trim() || password.length < 8 || busy !== null}
        >
          {busy === "password" && <Loader2 className="size-4 animate-spin" />}
          {t("createAccount")}
        </Button>
      </form>

      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">{t("or")}</span>
        </div>
      </div>

      <div className="space-y-2">
        <Button
          variant="outline"
          type="button"
          className="w-full h-10 font-medium flex items-center justify-center gap-2 cursor-pointer"
          disabled={busy !== null}
          onClick={() => handleOAuth("google")}
        >
          {busy === "google" ? <Loader2 className="size-4 animate-spin" /> : <GoogleIcon />}
          {t("continueGoogle")}
        </Button>
        <Button
          variant="outline"
          type="button"
          className="w-full h-10 font-medium flex items-center justify-center gap-2 cursor-pointer"
          disabled={busy !== null}
          onClick={() => handleOAuth("azure")}
        >
          {busy === "microsoft" ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <MicrosoftIcon />
          )}
          {t("continueMicrosoft")}
        </Button>
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-2 text-xs text-destructive">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </AuthShell>
  );
}

function humanizeAuthError(msg: string, t: (key: string) => string): string {
  const m = msg.toLowerCase();
  if (m.includes("user already registered") || m.includes("already been registered")) {
    return t("errors.alreadyRegistered");
  }
  if (m.includes("password should be")) {
    return t("errors.passwordTooShort");
  }
  if (m.includes("rate limit")) {
    return t("errors.rateLimit");
  }
  return msg;
}
