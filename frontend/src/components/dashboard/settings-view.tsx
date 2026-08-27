"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle2, Trash2, Sparkles, Plus, X, KeyRound, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, inputCls, textareaCls } from "@/components/dashboard/dialog";
import { SearchSelect, type SelectOption } from "@/components/ui/select";
import { LocalTime } from "@/components/local-time";
import {
  settings,
  exportMyData,
  promptTuningApi,
  llmKeysApi,
  type PromptTuningStatus,
  type SignatureLink,
  type LlmKey,
} from "@/lib/backend";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { COUNTRIES } from "@/lib/countries";
import {
  listTimezones,
  formatTimezone,
  offsetLabel,
  detectTimezone,
} from "@/lib/timezones";

const DEFAULT_PROMPT =
  "You are Kin, a calm and capable personal assistant. Be concise, kind, and decisive. Today's date is {today}. When the user asks about tasks, calendar, or email, prefer concrete answers with dates and times over generic advice.";

type Tone = "concise" | "friendly" | "formal";
type Length = "short" | "medium" | "long";
type SaveStatus = "idle" | "saving" | "saved" | "error";

type SettingsPatch = Parameters<typeof settings.update>[0];

export function SettingsView({
  initial,
  plan = "free",
}: {
  plan?: string;
  initial: {
    display_name: string;
    timezone: string;
    country: string | null;
    system_prompt: string | null;
    briefing_enabled: boolean;
    briefing_time: string;
    marketing_opt_in: boolean;
    memory_enabled: boolean;
    confirm_before_write: boolean;
    email_followups_enabled: boolean;
    email_signature_enabled: boolean;
    email_signature_name: string;
    email_signature_title: string;
    email_signature_phone: string;
    email_signature_links: SignatureLink[];
    tone?: Tone;
    response_length?: Length;
  };
}) {
  const t = useTranslations("dashboard.settings");
  const router = useRouter();
  const [displayName, setDisplayName] = useState(initial.display_name);
  const [tz, setTz] = useState(initial.timezone || "UTC");
  const [country, setCountry] = useState(initial.country ?? "");
  const [prompt, setPrompt] = useState(initial.system_prompt ?? "");
  const [briefingOn, setBriefingOn] = useState(initial.briefing_enabled);
  const [briefingTime, setBriefingTime] = useState(
    initial.briefing_time?.slice(0, 5) || "08:00",
  );
  const [marketingOk, setMarketingOk] = useState(initial.marketing_opt_in);
  const [memoryOn, setMemoryOn] = useState(initial.memory_enabled);
  const [confirmWriteOn, setConfirmWriteOn] = useState(initial.confirm_before_write);
  const [emailFollowupsOn, setEmailFollowupsOn] = useState(initial.email_followups_enabled);
  const [sigOn, setSigOn] = useState(initial.email_signature_enabled);
  const [sigName, setSigName] = useState(initial.email_signature_name);
  const [sigTitle, setSigTitle] = useState(initial.email_signature_title);
  const [sigPhone, setSigPhone] = useState(initial.email_signature_phone);
  const [sigLinks, setSigLinks] = useState<SignatureLink[]>(initial.email_signature_links);
  const [exporting, setExporting] = useState(false);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const savedTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const save = useCallback(async (patch: SettingsPatch, revert?: () => void) => {
    if (savedTimeout.current) clearTimeout(savedTimeout.current);
    setStatus("saving");
    setStatusMessage(null);
    try {
      await settings.update(patch);
      setStatus("saved");
      savedTimeout.current = setTimeout(() => setStatus("idle"), 1600);
    } catch (e) {
      setStatus("error");
      setStatusMessage(e instanceof Error ? e.message : t("saveError"));
      revert?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const debouncedSave = useCallback(
    (key: string, patch: SettingsPatch, delayMs = 700) => {
      const timers = debounceTimers.current;
      if (timers[key]) clearTimeout(timers[key]);
      timers[key] = setTimeout(() => save(patch), delayMs);
    },
    [save],
  );

  useEffect(() => {
    const timers = debounceTimers.current;
    return () => {
      Object.values(timers).forEach(clearTimeout);
      if (savedTimeout.current) clearTimeout(savedTimeout.current);
    };
  }, []);

  useEffect(() => {
    const detected = detectTimezone();
    if (detected && detected !== "UTC" && (!initial.timezone || initial.timezone === "UTC")) {
      setTz(detected);
      save({ timezone: detected });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial.timezone]);

  const timezoneOptions: SelectOption[] = useMemo(
    () =>
      listTimezones().map((z) => ({
        value: z,
        label: formatTimezone(z),
        trailing: offsetLabel(z),
      })),
    [],
  );

  const countryOptions: SelectOption[] = useMemo(
    () =>
      COUNTRIES.map((c) => ({
        value: c.code,
        label: c.name,
        leading: <span className="text-base leading-none">{c.flag}</span>,
      })),
    [],
  );

  async function deleteAccount() {
    setDeleting(true);
    try {
      const supabase = createClient();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) throw new Error("Not signed in");
      const { error } = await supabase
        .from("users")
        .update({
          display_name: "[deleted user]",
          email: null,
          avatar_url: null,
          country: null,
          
          google_access_token: null,
          google_refresh_token: null,
          google_token_expiry: null,
          google_email: null,
          system_prompt: null,
          briefing_enabled: false,
        })
        .eq("auth_user_id", auth.user.id);
      if (error) throw error;
      await supabase.auth.signOut();
      router.push("/");
    } catch (e) {
      setStatus("error");
      setStatusMessage(e instanceof Error ? e.message : t("deleteAccountError"));
      setDeleting(false);
      setShowDelete(false);
    }
  }

  return (
    <div className="space-y-6">
      <SaveIndicator status={status} message={statusMessage} />

      <Section title={t("profile.title")} sub={t("profile.sub")}>
        <Field label={t("profile.displayNameLabel")}>
          <input
            value={displayName}
            onChange={(e) => {
              const v = e.target.value;
              setDisplayName(v);
              debouncedSave("display_name", { display_name: v.trim() || undefined });
            }}
            className={inputCls}
            placeholder={t("profile.displayNamePlaceholder")}
          />
        </Field>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field
            label={t("profile.timezoneLabel")}
            hint={t("profile.timezoneHint")}
          >
            <SearchSelect
              value={tz}
              onChange={(v) => {
                setTz(v);
                save({ timezone: v });
              }}
              options={timezoneOptions}
              placeholder={t("profile.timezonePlaceholder")}
            />
          </Field>
          <Field label={t("profile.countryLabel")}>
            <SearchSelect
              value={country}
              onChange={(v) => {
                setCountry(v);
                save({ country: v || null });
              }}
              options={countryOptions}
              placeholder={t("profile.countryPlaceholder")}
            />
          </Field>
        </div>
      </Section>

      <Section
        title={t("personality.title")}
        sub={t.rich("personality.sub", { code: (chunks) => <code className="text-[10px]">{chunks}</code> })}
      >
        <Field label={t("personality.promptLabel")}>
          <textarea
            value={prompt}
            onChange={(e) => {
              const v = e.target.value;
              setPrompt(v);
              debouncedSave("system_prompt", { system_prompt: v.trim() ? v : "" });
            }}
            className={`${textareaCls} min-h-[140px] font-mono text-xs`}
            placeholder={DEFAULT_PROMPT}
          />
        </Field>
        <button
          type="button"
          onClick={() => {
            setPrompt(DEFAULT_PROMPT);
            save({ system_prompt: DEFAULT_PROMPT });
          }}
          className="text-[11px] text-muted-foreground hover:text-foreground underline underline-offset-4"
        >
          {t("personality.restoreDefault")}
        </button>
        {plan === "executive" && (
          <PromptTuning
            onApply={(suggested) => {
              setPrompt(suggested);
              save({ system_prompt: suggested });
            }}
          />
        )}
      </Section>

      <Section
        title={t("briefing.title")}
        sub={t("briefing.sub")}
      >
        <Toggle
          checked={briefingOn}
          onChange={(v) => {
            const prev = briefingOn;
            setBriefingOn(v);
            save({ briefing_enabled: v }, () => setBriefingOn(prev));
          }}
          label={t("briefing.toggle")}
        />
        {briefingOn && (
          <div className="mt-3">
            <Field label={t("briefing.timeLabel")} hint={t("briefing.timeHint")}>
              <input
                type="time"
                value={briefingTime}
                onChange={(e) => {
                  const v = e.target.value;
                  setBriefingTime(v);
                  save({ briefing_time: `${v}:00` });
                }}
                className={`${inputCls} max-w-[140px]`}
              />
            </Field>
          </div>
        )}
      </Section>

      <Section
        title={t("memory.title")}
        sub={t.rich("memory.sub", {
          link: (chunks) => (
            <a
              href="/dashboard/memory"
              className="underline underline-offset-2 hover:text-foreground"
            >
              {chunks}
            </a>
          ),
        })}
      >
        <Toggle
          checked={memoryOn}
          onChange={(v) => {
            setMemoryOn(v);
            save({ memory_enabled: v });
          }}
          label={t("memory.toggle")}
        />
      </Section>

      <Section
        title={t("confirmWrite.title")}
        sub={t("confirmWrite.sub")}
      >
        <Toggle
          checked={confirmWriteOn}
          onChange={(v) => {
            setConfirmWriteOn(v);
            save({ confirm_before_write: v });
          }}
          label={t("confirmWrite.toggle")}
        />
      </Section>

      <Section
        title={t("emailFollowups.title")}
        sub={t("emailFollowups.sub")}
      >
        <Toggle
          checked={emailFollowupsOn}
          onChange={(v) => {
            const prev = emailFollowupsOn;
            setEmailFollowupsOn(v);
            save({ email_followups_enabled: v }, () => setEmailFollowupsOn(prev));
          }}
          label={t("emailFollowups.toggle")}
        />
      </Section>

      <Section
        title={t("signature.title")}
        sub={t("signature.sub")}
      >
        <Toggle
          checked={sigOn}
          onChange={(v) => {
            setSigOn(v);
            save({ email_signature_enabled: v });
          }}
          label={t("signature.toggle")}
        />
        {sigOn && (
          <div className="mt-4 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label={t("signature.nameLabel")}>
                <input
                  value={sigName}
                  onChange={(e) => {
                    const v = e.target.value;
                    setSigName(v);
                    debouncedSave("sig_name", { email_signature_name: v });
                  }}
                  className={inputCls}
                  placeholder={t("signature.namePlaceholder")}
                />
              </Field>
              <Field label={t("signature.titleLabel")}>
                <input
                  value={sigTitle}
                  onChange={(e) => {
                    const v = e.target.value;
                    setSigTitle(v);
                    debouncedSave("sig_title", { email_signature_title: v });
                  }}
                  className={inputCls}
                  placeholder={t("signature.titlePlaceholder")}
                />
              </Field>
            </div>
            <Field label={t("signature.phoneLabel")}>
              <input
                value={sigPhone}
                onChange={(e) => {
                  const v = e.target.value;
                  setSigPhone(v);
                  debouncedSave("sig_phone", { email_signature_phone: v });
                }}
                className={inputCls}
                placeholder={t("signature.phonePlaceholder")}
              />
            </Field>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  {t("signature.linksLabel")}
                </label>
                {sigLinks.length < 5 && (
                  <button
                    type="button"
                    onClick={() => {
                      const next = [...sigLinks, { label: "", url: "" }];
                      setSigLinks(next);
                    }}
                    className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                  >
                    <Plus className="size-3" /> {t("signature.addLink")}
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {sigLinks.map((link, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      value={link.label ?? ""}
                      onChange={(e) => {
                        const next = sigLinks.map((l, j) =>
                          j === i ? { ...l, label: e.target.value } : l,
                        );
                        setSigLinks(next);
                        debouncedSave("sig_links", { email_signature_links: next });
                      }}
                      className="h-9 px-3 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 w-28 shrink-0"
                      placeholder={t("signature.linkLabelPlaceholder")}
                    />
                    <input
                      value={link.url}
                      onChange={(e) => {
                        const next = sigLinks.map((l, j) =>
                          j === i ? { ...l, url: e.target.value } : l,
                        );
                        setSigLinks(next);
                        debouncedSave("sig_links", { email_signature_links: next });
                      }}
                      className="h-9 px-3 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 flex-1 min-w-0"
                      placeholder={t("signature.linkUrlPlaceholder")}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const next = sigLinks.filter((_, j) => j !== i);
                        setSigLinks(next);
                        save({ email_signature_links: next });
                      }}
                      className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/5 shrink-0"
                      aria-label={t("signature.removeLink")}
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                ))}
                {sigLinks.length === 0 && (
                  <p className="text-[11px] text-muted-foreground">{t("signature.noLinks")}</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1.5">
                {t("signature.preview")}
              </p>
              <pre className="text-xs font-mono whitespace-pre-wrap text-foreground/80">
                {renderSignaturePreview(sigName, sigTitle, sigPhone, sigLinks, t("signature.previewEmpty"))}
              </pre>
            </div>
          </div>
        )}
      </Section>

      <Section
        title={t("exportData.title")}
        sub={t("exportData.sub")}
      >
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="cursor-pointer"
          disabled={exporting}
          onClick={async () => {
            setExporting(true);
            try {
              await exportMyData();
            } catch (e) {
              setStatus("error");
              setStatusMessage(e instanceof Error ? e.message : t("exportFailed"));
            } finally {
              setExporting(false);
            }
          }}
        >
          {exporting && <Loader2 className="size-3.5 animate-spin" />}
          {t("exportData.download")}
        </Button>
      </Section>

      <Section
        title={t("communication.title")}
        sub={t("communication.sub")}
      >
        <Toggle
          checked={marketingOk}
          onChange={(v) => {
            setMarketingOk(v);
            save({ marketing_opt_in: v });
          }}
          label={t("communication.toggle")}
        />
      </Section>

      <Section
        title={t("apiKeys.title")}
        sub={t("apiKeys.sub")}
      >
        <ApiKeysSection />
      </Section>

      <Section
        title={t("dangerZone.title")}
        sub={t("dangerZone.sub")}
        danger
      >
        {!showDelete ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => setShowDelete(true)}
            className="cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/5"
          >
            <Trash2 className="size-3.5" />
            {t("dangerZone.deleteAccount")}
          </Button>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-destructive">
              {t("dangerZone.confirmBody")}
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowDelete(false)}
                className="cursor-pointer"
              >
                {t("dangerZone.cancel")}
              </Button>
              <Button
                type="button"
                onClick={deleteAccount}
                disabled={deleting}
                className="bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive/20 cursor-pointer"
              >
                {deleting && <Loader2 className="size-3.5 animate-spin" />}
                {t("dangerZone.confirmDelete")}
              </Button>
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}

function SaveIndicator({
  status,
  message,
}: {
  status: SaveStatus;
  message: string | null;
}) {
  const t = useTranslations("dashboard.settings.saveIndicator");
  if (status === "idle") return null;
  return (
    <div className="sticky top-0 z-10 -mt-2 -mx-1 px-1 pt-2 pb-1">
      <div
        className={`rounded-lg border px-3 py-2 text-xs flex items-center gap-2 backdrop-blur-sm ${
          status === "error"
            ? "border-destructive/30 bg-destructive/10 text-destructive"
            : "border-border bg-card/95 text-muted-foreground"
        }`}
      >
        {status === "saving" && (
          <>
            <span className="relative h-1 flex-1 max-w-[80px] rounded-full bg-muted overflow-hidden">
              <motion.span
                className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-foreground/60"
                animate={{ x: ["-100%", "340%"] }}
                transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
              />
            </span>
            <span>{t("saving")}</span>
          </>
        )}
        {status === "saved" && (
          <span className="flex items-center gap-1.5 text-emerald-700">
            <CheckCircle2 className="size-3.5" /> {t("saved")}
          </span>
        )}
        {status === "error" && (
          <span className="flex items-center gap-1.5">
            <AlertCircle className="size-3.5 shrink-0" /> {message ?? t("genericError")}
          </span>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  sub,
  children,
  danger,
}: {
  title: string;
  sub?: React.ReactNode;
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <section
      className={`rounded-xl border bg-card p-5 ${
        danger ? "border-destructive/30" : "border-border"
      }`}
    >
      <h2 className={`text-sm font-semibold ${danger ? "text-destructive" : ""}`}>
        {title}
      </h2>
      {sub && <p className="text-xs text-muted-foreground mb-4">{sub}</p>}
      {!sub && <div className="mb-4" />}
      {children}
    </section>
  );
}

const BYOK_PROVIDERS = ["openai", "anthropic", "openrouter"] as const;

function ApiKeysSection() {
  const t = useTranslations("dashboard.settings.apiKeys");
  const [keys, setKeys] = useState<LlmKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [provider, setProvider] = useState<(typeof BYOK_PROVIDERS)[number]>("openai");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);
  const [confirmDeleteProvider, setConfirmDeleteProvider] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    llmKeysApi
      .list()
      .then((res) => setKeys(res.keys))
      .catch((e) => setLoadError(e instanceof Error ? e.message : t("loadError")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setSaving(true);
    setSaveError(null);
    setJustSaved(false);
    try {
      await llmKeysApi.save(provider, apiKey.trim());
      setApiKey("");
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2500);
      load();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(p: string) {
    setDeleting(true);
    setDeleteError(null);
    try {
      await llmKeysApi.delete(p);
      setKeys((prev) => prev.filter((k) => k.provider !== p));
      setConfirmDeleteProvider(null);
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : t("deleteError"));
    } finally {
      setDeleting(false);
    }
  }

  const providerOptions: SelectOption[] = BYOK_PROVIDERS.map((p) => ({
    value: p,
    label: t(`providers.${p}`),
  }));

  return (
    <div className="space-y-4">
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          {t("loading")}
        </div>
      ) : loadError ? (
        <p className="text-xs text-destructive">{loadError}</p>
      ) : keys.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("noKeys")}</p>
      ) : (
        <div className="rounded-lg border border-border divide-y divide-border overflow-hidden">
          {keys.map((k) => (
            <div key={k.provider} className="flex items-center justify-between gap-3 px-3 py-2.5">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="size-7 rounded-md bg-muted grid place-items-center shrink-0">
                  <KeyRound className="size-3.5 text-muted-foreground" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-medium">{t(`providers.${k.provider}`)}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {t("addedAgo")} <LocalTime iso={k.updated_at} mode="relative" />
                  </div>
                </div>
              </div>
              {confirmDeleteProvider === k.provider ? (
                <div className="flex items-center gap-1.5 shrink-0">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="cursor-pointer h-7 px-2 text-xs"
                    onClick={() => setConfirmDeleteProvider(null)}
                    disabled={deleting}
                  >
                    {t("cancel")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="cursor-pointer h-7 px-2 text-xs bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive/20"
                    onClick={() => handleDelete(k.provider)}
                    disabled={deleting}
                  >
                    {deleting && <Loader2 className="size-3 animate-spin" />}
                    {t("confirmRemove")}
                  </Button>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="cursor-pointer h-7 px-2 text-xs text-destructive border-destructive/30 hover:bg-destructive/5 shrink-0"
                  onClick={() => setConfirmDeleteProvider(k.provider)}
                >
                  <Trash2 className="size-3" />
                  {t("remove")}
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
      {deleteError && <p className="text-xs text-destructive">{deleteError}</p>}

      <form onSubmit={handleSave} className="rounded-lg border border-border p-3 space-y-2.5">
        <p className="text-xs font-medium text-foreground/80">{t("addKey")}</p>
        <div className="grid grid-cols-1 sm:grid-cols-[140px_1fr] gap-2">
          <SearchSelect
            value={provider}
            onChange={(v) => setProvider(v as (typeof BYOK_PROVIDERS)[number])}
            options={providerOptions}
            disabled={saving}
          />
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t("keyPlaceholder")}
            disabled={saving}
            autoComplete="off"
            className={inputCls}
          />
        </div>
        {saveError && <p className="text-[11px] text-destructive">{saveError}</p>}
        <div className="flex items-center gap-2">
          <Button
            type="submit"
            size="sm"
            disabled={saving || !apiKey.trim()}
            className="cursor-pointer"
          >
            {saving && <Loader2 className="size-3.5 animate-spin" />}
            {t("save")}
          </Button>
          {justSaved && (
            <span className="flex items-center gap-1 text-xs text-emerald-700">
              <CheckCircle2 className="size-3.5" /> {t("saved")}
            </span>
          )}
        </div>
      </form>

      <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
        <ShieldCheck className="size-3.5 mt-0.5 shrink-0" />
        {t("securityNote")}
      </p>
    </div>
  );
}

function PromptTuning({ onApply }: { onApply: (suggestedPrompt: string) => void }) {
  const t = useTranslations("dashboard.settings.promptTuning");
  const [status, setStatus] = useState<PromptTuningStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<{ suggested_prompt: string; rationale: string } | null>(
    null,
  );
  const [applied, setApplied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    promptTuningApi.status().then(setStatus).catch(() => setStatus(null));
  }, []);

  async function suggest() {
    setLoading(true);
    setError(null);
    try {
      setSuggestion(await promptTuningApi.suggest());
    } catch (e) {
      setError(e instanceof Error ? e.message : t("suggestFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function apply() {
    if (!suggestion) return;
    try {
      await promptTuningApi.apply(suggestion.suggested_prompt);
      onApply(suggestion.suggested_prompt);
      setApplied(true);
      setSuggestion(null);
      promptTuningApi.status().then(setStatus).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : t("applyFailed"));
    }
  }

  return (
    <div className="mt-4 pt-4 border-t border-border">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium flex items-center gap-1.5">
            <Sparkles className="size-3.5 text-muted-foreground" /> {t("title")}
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {t("sub")}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="cursor-pointer shrink-0"
          disabled={loading || (status ? !status.eligible : false)}
          onClick={suggest}
        >
          {loading && <Loader2 className="size-3.5 animate-spin" />}
          {t("tuneButton")}
        </Button>
      </div>

      {status && !status.eligible && status.next_eligible_at && (
        <p className="text-[11px] text-muted-foreground mt-2">
          {t("nextEligible", { date: new Date(status.next_eligible_at).toLocaleDateString() })}
        </p>
      )}
      {applied && (
        <p className="text-[11px] text-emerald-700 mt-2 flex items-center gap-1">
          <CheckCircle2 className="size-3.5" /> {t("applied")}
        </p>
      )}
      {error && (
        <p className="text-[11px] text-destructive mt-2 flex items-center gap-1">
          <AlertCircle className="size-3.5" /> {error}
        </p>
      )}

      {suggestion && (
        <div className="mt-3 rounded-lg border border-border bg-muted/40 p-3 space-y-2">
          <p className="text-[11px] text-muted-foreground">{suggestion.rationale}</p>
          <pre className="text-[11px] font-mono whitespace-pre-wrap bg-background rounded-md p-2.5 border border-border max-h-48 overflow-y-auto">
            {suggestion.suggested_prompt}
          </pre>
          <div className="flex items-center gap-2">
            <Button type="button" size="sm" className="cursor-pointer" onClick={apply}>
              {t("acceptApply")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="cursor-pointer"
              onClick={() => setSuggestion(null)}
            >
              {t("dismiss")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// Mirrors agent_tools.py's _render_signature exactly, so the preview here
// never drifts from what actually gets appended to a sent email.
function renderSignaturePreview(
  name: string,
  title: string,
  phone: string,
  links: SignatureLink[],
  emptyLabel: string,
): string {
  const lines: string[] = [];
  if (name.trim()) lines.push(name.trim());
  if (title.trim()) lines.push(title.trim());
  if (phone.trim()) lines.push(phone.trim());
  for (const link of links) {
    const url = (link.url ?? "").trim();
    if (!url) continue;
    const label = (link.label ?? "").trim();
    lines.push(label ? `${label}: ${url}` : url);
  }
  if (lines.length === 0) return emptyLabel;
  return "-- \n" + lines.join("\n");
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
    <label className="flex items-center gap-3 cursor-pointer">
      <span className="relative shrink-0">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <span className="block w-9 h-5 rounded-full bg-muted peer-checked:bg-foreground transition-colors" />
        <span className="absolute left-0.5 top-0.5 size-4 rounded-full bg-background shadow transition-transform peer-checked:translate-x-4" />
      </span>
      <span className="text-sm">{label}</span>
    </label>
  );
}
