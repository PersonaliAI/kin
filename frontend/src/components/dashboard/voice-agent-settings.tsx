"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, CheckCircle2, Trash2, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { inputCls } from "./dialog";
import { flowCredentials, voiceAgentsApi } from "@/lib/backend";

type TwilioForm = {
  account_sid: string;
  auth_token: string;
  trunk_sid: string;
};

const EMPTY_TWILIO_FORM: TwilioForm = { account_sid: "", auth_token: "", trunk_sid: "" };

/** Account-level Voice Agents settings — currently just the Twilio BYOK
 * connection. Embedded (not its own Dialog) inside the New/Edit Voice
 * Agent dialog, so creating an agent and connecting a Twilio account both
 * live in one place instead of a separate popup. Bring-your-own Twilio
 * account for phone numbers, an alternative to Kin's shared/free Twilio
 * option (twilio_managed). Saving these 3 fields is enough —
 * voiceAgentsApi.saveTwilioByok has the backend auto-provision the matching
 * LiveKit SIP trunks server-side, so there's no LiveKit trunk id for the
 * user to look up or paste in here.
 *
 * Deliberately NOT nested inside the agent form's own <form> element (a
 * <form> inside a <form> is invalid HTML and browsers silently break it) —
 * this has its own independent <form>/save action, so the caller must
 * render it as a sibling of the agent form, not a child. */
export function TwilioByokSection() {
  const t = useTranslations("dashboard.voiceAgents.settingsDialog");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<TwilioForm>(EMPTY_TWILIO_FORM);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    flowCredentials
      .list()
      .then((res) => setSaved(res.credentials.some((c) => c.integration_slug === "twilio")))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form.account_sid.trim() || !form.auth_token.trim() || !form.trunk_sid.trim()) return;
    setSaving(true);
    setSaveError(null);
    setJustSaved(false);
    try {
      await voiceAgentsApi.saveTwilioByok(form.account_sid.trim(), form.auth_token.trim(), form.trunk_sid.trim());
      setSaved(true);
      setForm(EMPTY_TWILIO_FORM);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2500);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : t("saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      await flowCredentials.delete("twilio");
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
        <h3 className="text-xs font-semibold text-foreground/80">{t("title")}</h3>
        {!loading && saved && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30">
            <CheckCircle2 className="size-3" /> {t("connected")}
          </span>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground">{t("description")}</p>

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
            <span className="text-xs">{t("savedNote")}</span>
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
            <input
              value={form.account_sid}
              onChange={(e) => setForm((f) => ({ ...f, account_sid: e.target.value }))}
              placeholder={t("accountSidPlaceholder")}
              disabled={saving}
              autoComplete="off"
              className={inputCls}
            />
            <input
              type="password"
              value={form.auth_token}
              onChange={(e) => setForm((f) => ({ ...f, auth_token: e.target.value }))}
              placeholder={t("authTokenPlaceholder")}
              disabled={saving}
              autoComplete="off"
              className={inputCls}
            />
            <input
              value={form.trunk_sid}
              onChange={(e) => setForm((f) => ({ ...f, trunk_sid: e.target.value }))}
              placeholder={t("trunkSidPlaceholder")}
              disabled={saving}
              autoComplete="off"
              className={`${inputCls} sm:col-span-2`}
            />
          </div>
          <p className="text-[11px] text-muted-foreground">{t("setupHint")}</p>
          {saveError && <p className="text-[11px] text-destructive">{saveError}</p>}
          <div className="flex items-center gap-2">
            <Button
              type="submit"
              size="sm"
              disabled={saving || !form.account_sid.trim() || !form.auth_token.trim() || !form.trunk_sid.trim()}
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
      )}
    </div>
  );
}
