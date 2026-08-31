"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Copy,
  Check,
  Loader2,
  Plus,
  Trash2,
  AlertCircle,
  Webhook as WebhookIcon,
  KeyRound,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, inputCls } from "@/components/dashboard/dialog";
import {
  BACKEND_URL,
  kinApiKeysApi,
  kinWebhooksApi,
  type KinApiKey,
  type KinWebhook,
} from "@/lib/backend";

// Free on every plan (was Executive-only) — usage is capped, not gated by
// plan: MAX_KIN_API_KEYS/MAX_KIN_WEBHOOKS on count (enforced backend-side —
// keep these two in sync with main.py's MAX_KIN_API_KEYS/MAX_KIN_WEBHOOKS,
// they're only display copy here, the real limit lives server-side), and
// the normal per-plan token quota + existing per-key/per-IP rate limits on
// actual request volume through /api/v1/messages.
const MAX_KIN_API_KEYS = 5;
const MAX_KIN_WEBHOOKS = 5;

export function DeveloperView() {
  return (
    <div className="space-y-5">
      <ApiKeysSection />
      <WebhooksSection />
    </div>
  );
}

function CopyableSecret({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2 mt-2">
      <code className="flex-1 text-[11px] bg-muted rounded-md px-2.5 py-2 overflow-x-auto whitespace-nowrap">
        {value}
      </code>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="cursor-pointer shrink-0"
        onClick={() => {
          navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </Button>
    </div>
  );
}

function ApiKeysSection() {
  const t = useTranslations("dashboard.developer.apiKeys");
  const [keys, setKeys] = useState<KinApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const { api_keys } = await kinApiKeysApi.list();
      setKeys(api_keys);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError"));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function create() {
    setCreating(true);
    setError(null);
    try {
      const created = await kinApiKeysApi.create(name.trim() || "API key");
      setRevealedKey(created.key);
      setName("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("createError"));
    } finally {
      setCreating(false);
    }
  }

  async function revoke(id: string) {
    try {
      await kinApiKeysApi.revoke(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("revokeError"));
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <KeyRound className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">{t("title")}</h2>
      </div>
      <p className="text-xs text-muted-foreground mt-1 mb-4">
        {t.rich("description", {
          endpoint: () => (
            <code className="text-[10px] bg-muted rounded px-1 py-0.5">
              {`POST ${BACKEND_URL}/api/v1/messages`}
            </code>
          ),
          header: () => (
            <code className="text-[10px] bg-muted rounded px-1 py-0.5">
              Authorization: Bearer &lt;key&gt;
            </code>
          ),
          max: MAX_KIN_API_KEYS,
        })}
      </p>

      {revealedKey && (
        <div className="mb-4 rounded-lg border border-amber-300/50 bg-amber-50 dark:bg-amber-950/30 p-3">
          <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
            {t("revealNotice")}
          </p>
          <CopyableSecret value={revealedKey} />
          <button
            type="button"
            onClick={() => setRevealedKey(null)}
            className="text-[11px] text-muted-foreground hover:text-foreground underline underline-offset-2 mt-2"
          >
            {t("dismiss")}
          </button>
        </div>
      )}

      {error && (
        <p className="mb-3 flex items-center gap-1.5 text-xs text-destructive">
          <AlertCircle className="size-3.5" /> {error}
        </p>
      )}

      <div className="flex items-end gap-2 mb-4">
        <div className="flex-1">
          <Field label={t("nameLabel")}>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("namePlaceholder")}
              className={inputCls}
            />
          </Field>
        </div>
        <Button
          type="button"
          className="cursor-pointer mb-[1px]"
          disabled={creating}
          onClick={create}
        >
          {creating ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
          {t("createKey")}
        </Button>
      </div>

      <ul className="divide-y divide-border">
        {(keys ?? []).map((k) => (
          <li key={k.id} className="py-2.5 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm truncate">{k.name}</p>
              <p className="text-[11px] text-muted-foreground">
                <code>{k.key_prefix}…</code>
                {" · "}
                {t("requests", { count: k.request_count })}
                {" · "}
                {k.last_used_at
                  ? t("lastUsed", { date: new Date(k.last_used_at).toLocaleDateString() })
                  : t("neverUsed")}
                {k.revoked && ` · ${t("revoked")}`}
              </p>
            </div>
            {!k.revoked && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/5 shrink-0"
                onClick={() => revoke(k.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            )}
          </li>
        ))}
        {keys && keys.length === 0 && (
          <li className="py-3 text-xs text-muted-foreground">{t("empty")}</li>
        )}
      </ul>
    </section>
  );
}

function WebhooksSection() {
  const t = useTranslations("dashboard.developer.webhooks");
  const [hooks, setHooks] = useState<KinWebhook[] | null>(null);
  const [url, setUrl] = useState("");
  const [creating, setCreating] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const { webhooks } = await kinWebhooksApi.list();
      setHooks(webhooks);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError"));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function create() {
    setCreating(true);
    setError(null);
    try {
      const created = await kinWebhooksApi.create(url.trim());
      setRevealedSecret(created.secret);
      setUrl("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("createError"));
    } finally {
      setCreating(false);
    }
  }

  async function toggle(id: string, active: boolean) {
    try {
      await kinWebhooksApi.setActive(id, active);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("updateError"));
    }
  }

  async function remove(id: string) {
    try {
      await kinWebhooksApi.delete(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("deleteError"));
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <WebhookIcon className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">{t("title")}</h2>
      </div>
      <p className="text-xs text-muted-foreground mt-1 mb-4">
        {t.rich("description", {
          post: () => <code className="text-[10px] bg-muted rounded px-1 py-0.5">POST</code>,
          header: () => (
            <code className="text-[10px] bg-muted rounded px-1 py-0.5">X-Kin-Signature</code>
          ),
          max: MAX_KIN_WEBHOOKS,
        })}
      </p>

      {revealedSecret && (
        <div className="mb-4 rounded-lg border border-amber-300/50 bg-amber-50 dark:bg-amber-950/30 p-3">
          <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
            {t("revealNotice")}
          </p>
          <CopyableSecret value={revealedSecret} />
          <button
            type="button"
            onClick={() => setRevealedSecret(null)}
            className="text-[11px] text-muted-foreground hover:text-foreground underline underline-offset-2 mt-2"
          >
            {t("dismiss")}
          </button>
        </div>
      )}

      {error && (
        <p className="mb-3 flex items-center gap-1.5 text-xs text-destructive">
          <AlertCircle className="size-3.5" /> {error}
        </p>
      )}

      <div className="flex items-end gap-2 mb-4">
        <div className="flex-1">
          <Field label={t("urlLabel")} hint={t("urlHint")}>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={t("urlPlaceholder")}
              className={inputCls}
            />
          </Field>
        </div>
        <Button
          type="button"
          className="cursor-pointer mb-[1px]"
          disabled={creating || !url.trim()}
          onClick={create}
        >
          {creating ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
          {t("addWebhook")}
        </Button>
      </div>

      <ul className="divide-y divide-border">
        {(hooks ?? []).map((h) => (
          <li key={h.id} className="py-2.5 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm truncate">{h.url}</p>
              <p className="text-[11px] text-muted-foreground">
                {h.events.join(", ")} · {t("addedOn", { date: new Date(h.created_at).toLocaleDateString() })}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => toggle(h.id, !h.active)}
                className="relative shrink-0"
                aria-label={h.active ? t("disable") : t("enable")}
              >
                <span
                  className={`block w-9 h-5 rounded-full transition-colors ${h.active ? "bg-foreground" : "bg-muted"}`}
                />
                <span
                  className={`absolute left-0.5 top-0.5 size-4 rounded-full bg-background shadow transition-transform ${h.active ? "translate-x-4" : ""}`}
                />
              </button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/5"
                onClick={() => remove(h.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </li>
        ))}
        {hooks && hooks.length === 0 && (
          <li className="py-3 text-xs text-muted-foreground">{t("empty")}</li>
        )}
      </ul>
    </section>
  );
}
