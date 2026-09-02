"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, CheckCircle2, Trash2, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { inputCls } from "./dialog";
import { flowCredentials, voiceAgentsApi } from "@/lib/backend";

type FieldSpec = {
  key: string;
  placeholder: string;
  type?: "text" | "password";
  span2?: boolean;
};

/** One BYOK provider's connect/connected card — shared shell for Twilio and
 * Telnyx below, since both are "enter N fields, save, we auto-provision the
 * matching LiveKit SIP trunks server-side" with only field count/labels
 * differing. */
function ByokCard({
  integrationSlug,
  title,
  description,
  fields,
  savedNote,
  setupHint,
  saveLabel,
  savedLabel,
  saveErrorFallback,
  onSave,
}: {
  integrationSlug: string;
  title: string;
  description: string;
  fields: FieldSpec[];
  savedNote: string;
  setupHint: string;
  saveLabel: string;
  savedLabel: string;
  saveErrorFallback: string;
  onSave: (values: Record<string, string>) => Promise<void>;
}) {
  const t = useTranslations("dashboard.voiceAgents.settingsDialog");
  const emptyForm = Object.fromEntries(fields.map((f) => [f.key, ""]));
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<Record<string, string>>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    flowCredentials
      .list()
      .then((res) => setSaved(res.credentials.some((c) => c.integration_slug === integrationSlug)))
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [integrationSlug]);

  const allFilled = fields.every((f) => form[f.key].trim());

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!allFilled) return;
    setSaving(true);
    setSaveError(null);
    setJustSaved(false);
    try {
      const trimmed = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim()]));
      await onSave(trimmed);
      setSaved(true);
      setForm(emptyForm);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2500);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : saveErrorFallback);
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      await flowCredentials.delete(integrationSlug);
      setSaved(false);
      setConfirmRemove(false);
    } catch {
      // leave `saved` as-is — the row was likely not removed
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-xs font-semibold text-foreground/80">{title}</h3>
        {!loading && saved && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30">
            <CheckCircle2 className="size-3" /> {t("connected")}
          </span>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground">{description}</p>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
        </div>
      ) : saved ? (
        <div className="rounded-lg border border-border p-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="size-7 rounded-md bg-muted grid place-items-center shrink-0">
              <KeyRound className="size-3.5 text-muted-foreground" />
            </div>
            <span className="text-xs">{savedNote}</span>
          </div>
          {confirmRemove ? (
            <div className="flex items-center gap-1.5 shrink-0">
              <Button type="button" variant="outline" size="sm" className="cursor-pointer h-7 px-2 text-xs" onClick={() => setConfirmRemove(false)} disabled={removing}>
                {t("cancel")}
              </Button>
              <Button
                type="button"
                size="sm"
                className="cursor-pointer h-7 px-2 text-xs bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive/20"
                onClick={handleRemove}
                disabled={removing}
              >
                {removing && <Loader2 className="size-3 animate-spin" />}
                {t("confirmRemove")}
              </Button>
            </div>
          ) : (
            <Button type="button" variant="outline" size="sm" className="cursor-pointer h-7 px-2 text-xs text-destructive border-destructive/30 hover:bg-destructive/5 shrink-0" onClick={() => setConfirmRemove(true)}>
              <Trash2 className="size-3" />
              {t("remove")}
            </Button>
          )}
        </div>
      ) : (
        <form onSubmit={handleSave} className="rounded-lg border border-border p-3 space-y-2.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {fields.map((f) => (
              <input
                key={f.key}
                type={f.type === "password" ? "password" : "text"}
                value={form[f.key]}
                onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                disabled={saving}
                autoComplete="off"
                className={f.span2 ? `${inputCls} sm:col-span-2` : inputCls}
              />
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">{setupHint}</p>
          {saveError && <p className="text-[11px] text-destructive">{saveError}</p>}
          <div className="flex items-center gap-2">
            <Button type="submit" size="sm" disabled={saving || !allFilled} className="cursor-pointer">
              {saving && <Loader2 className="size-3.5 animate-spin" />}
              {saveLabel}
            </Button>
            {justSaved && (
              <span className="flex items-center gap-1 text-xs text-emerald-700">
                <CheckCircle2 className="size-3.5" /> {savedLabel}
              </span>
            )}
          </div>
        </form>
      )}
    </div>
  );
}

/** Account-level Voice Agents settings — the Twilio and Telnyx BYOK
 * connections (the only way to get a phone number; there is no managed/
 * free option). Embedded (not its own Dialog) inside the New/Edit Voice
 * Agent dialog, so creating an agent and connecting a telephony account
 * both live in one place instead of a separate popup.
 *
 * Deliberately NOT nested inside the agent form's own <form> element (a
 * <form> inside a <form> is invalid HTML and browsers silently break it) —
 * each card below has its own independent <form>/save action, so the
 * caller must render this as a sibling of the agent form, not a child. */
export function TelephonyByokSection() {
  const t = useTranslations("dashboard.voiceAgents.settingsDialog");

  return (
    <div className="space-y-5">
      <ByokCard
        integrationSlug="twilio"
        title={t("twilio.title")}
        description={t("twilio.description")}
        savedNote={t("twilio.savedNote")}
        setupHint={t("twilio.setupHint")}
        saveLabel={t("twilio.save")}
        savedLabel={t("twilio.saved")}
        saveErrorFallback={t("twilio.saveError")}
        fields={[
          { key: "account_sid", placeholder: t("twilio.accountSidPlaceholder") },
          { key: "auth_token", placeholder: t("twilio.authTokenPlaceholder"), type: "password" },
          { key: "trunk_sid", placeholder: t("twilio.trunkSidPlaceholder"), span2: true },
        ]}
        onSave={(v) => voiceAgentsApi.saveTwilioByok(v.account_sid, v.auth_token, v.trunk_sid).then(() => undefined)}
      />

      <div className="border-t border-border" />

      <ByokCard
        integrationSlug="telnyx"
        title={t("telnyx.title")}
        description={t("telnyx.description")}
        savedNote={t("telnyx.savedNote")}
        setupHint={t("telnyx.setupHint")}
        saveLabel={t("telnyx.save")}
        savedLabel={t("telnyx.saved")}
        saveErrorFallback={t("telnyx.saveError")}
        fields={[
          { key: "api_key", placeholder: t("telnyx.apiKeyPlaceholder"), type: "password", span2: true },
          { key: "sip_connection_id", placeholder: t("telnyx.sipConnectionIdPlaceholder") },
          { key: "sip_username", placeholder: t("telnyx.sipUsernamePlaceholder") },
          { key: "sip_password", placeholder: t("telnyx.sipPasswordPlaceholder"), type: "password", span2: true },
        ]}
        onSave={(v) =>
          voiceAgentsApi
            .saveTelnyxByok(v.api_key, v.sip_connection_id, v.sip_username, v.sip_password)
            .then(() => undefined)
        }
      />
    </div>
  );
}
