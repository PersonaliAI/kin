"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  Cpu,
  Globe,
  RefreshCw,
  Trash2,
  Plus,
  Key,
  ChevronDown,
  ChevronUp,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, Field, inputCls } from "./dialog";
import { mcpApi, type McpServer, type McpTool, BACKEND_URL } from "@/lib/backend";

export function McpView() {
  const t = useTranslations("dashboard.mcp");
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyServerId, setBusyServerId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [headers, setHeaders] = useState<{ key: string; value: string }[]>([{ key: "", value: "" }]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [oauthEnabled, setOauthEnabled] = useState(false);
  const [oauthClientId, setOauthClientId] = useState("");
  const [oauthClientSecret, setOauthClientSecret] = useState("");
  const [oauthAuthUrl, setOauthAuthUrl] = useState("");
  const [oauthTokenUrl, setOauthTokenUrl] = useState("");
  const [oauthScopes, setOauthScopes] = useState("");

  const [expandedServerId, setExpandedServerId] = useState<string | null>(null);

  useEffect(() => {
    fetchServers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") === "success") {
      setBanner({ kind: "ok", text: t("oauthSuccess") });
      const url = new URL(window.location.href);
      url.searchParams.delete("oauth");
      url.searchParams.delete("mcp_id");
      window.history.replaceState({}, document.title, url.pathname);
    } else if (params.get("oauth") === "error") {
      const detail = params.get("detail") || t("oauthErrorGeneric");
      setBanner({ kind: "err", text: t("oauthErrorPrefix", { detail }) });
      const url = new URL(window.location.href);
      url.searchParams.delete("oauth");
      url.searchParams.delete("detail");
      window.history.replaceState({}, document.title, url.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchServers() {
    setLoading(true);
    try {
      const data = await mcpApi.list();
      setServers(data);
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("loadError") });
    } finally {
      setLoading(false);
    }
  }

  async function handleAddServer(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg(t("nameRequired"));
      return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(name)) {
      setErrorMsg(t("nameInvalid"));
      return;
    }
    if (!url.trim()) {
      setErrorMsg(t("urlRequired"));
      return;
    }

    setActionLoading(true);
    setErrorMsg(null);

    const headersObj: Record<string, string> = {};
    headers.forEach((h) => {
      if (h.key.trim()) {
        headersObj[h.key.trim()] = h.value.trim();
      }
    });

    try {
      const newServer = await mcpApi.create(
        name.trim(),
        url.trim(),
        headersObj,
        oauthEnabled ? oauthClientId.trim() : undefined,
        oauthEnabled ? oauthClientSecret.trim() : undefined,
        oauthEnabled ? oauthAuthUrl.trim() : undefined,
        oauthEnabled ? oauthTokenUrl.trim() : undefined,
        oauthEnabled ? oauthScopes.trim() : undefined
      );
      setServers((prev) => [...prev, newServer]);
      setAddOpen(false);
      setName("");
      setUrl("");
      setHeaders([{ key: "", value: "" }]);
      setOauthEnabled(false);
      setOauthClientId("");
      setOauthClientSecret("");
      setOauthAuthUrl("");
      setOauthTokenUrl("");
      setOauthScopes("");
      if (newServer.oauth_flow_status === "awaiting_authorization") {
        setBanner({ kind: "ok", text: t("addedAwaitingAuth", { name: newServer.name }) });
      } else {
        setBanner({ kind: "ok", text: t("addedConnected", { name: newServer.name }) });
      }
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : t("connectFailed"));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleTestServer(id: string) {
    setBusyServerId(id);
    setBanner(null);
    try {
      const res = await mcpApi.test(id);
      setServers((prev) =>
        prev.map((s) => (s.id === id ? { ...s, tools: res.tools, updated_at: new Date().toISOString() } : s))
      );
      setExpandedServerId(id);
      setBanner({
        kind: "ok",
        text: t("testSuccess", { count: res.tools.length }),
      });
    } catch (e) {
      setBanner({
        kind: "err",
        text: e instanceof Error ? e.message : t("testFailed"),
      });
    } finally {
      setBusyServerId(null);
    }
  }

  async function handleAuthorizeServer(id: string) {
    setBusyServerId(id);
    setBanner(null);
    try {
      const redirectUri = `${BACKEND_URL}/auth/mcp/callback`;
      const res = await mcpApi.oauthStart(id, redirectUri);
      window.location.href = res.url;
    } catch (e) {
      setBanner({
        kind: "err",
        text: e instanceof Error ? e.message : t("authorizeFailed"),
      });
      setBusyServerId(null);
    }
  }

  async function handleDeleteServer(id: string, name: string) {
    if (!confirm(t("deleteConfirm", { name }))) {
      return;
    }
    setBusyServerId(id);
    setBanner(null);
    try {
      await mcpApi.delete(id);
      setServers((prev) => prev.filter((s) => s.id !== id));
      if (expandedServerId === id) setExpandedServerId(null);
      setBanner({ kind: "ok", text: t("deleted", { name }) });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("deleteFailed") });
    } finally {
      setBusyServerId(null);
    }
  }

  function addHeaderRow() {
    setHeaders((prev) => [...prev, { key: "", value: "" }]);
  }

  function updateHeaderRow(idx: number, field: "key" | "value", val: string) {
    setHeaders((prev) =>
      prev.map((h, i) => (i === idx ? { ...h, [field]: val } : h))
    );
  }

  function removeHeaderRow(idx: number) {
    setHeaders((prev) => prev.filter((_, i) => i !== idx));
  }

  return (
    <div className="space-y-6">
      <AnimatePresence>
        {banner && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`flex items-start gap-2 rounded-xl px-4 py-3 text-xs shadow-sm border ${
              banner.kind === "ok"
                ? "bg-emerald-50/80 border-emerald-100 text-emerald-800 dark:bg-emerald-950/20 dark:border-emerald-900/55 dark:text-emerald-300"
                : "bg-destructive/10 border-destructive/25 text-destructive dark:border-destructive/40"
            }`}
          >
            {banner.kind === "ok" ? (
              <CheckCircle2 className="size-4 mt-0.5 shrink-0" />
            ) : (
              <AlertCircle className="size-4 mt-0.5 shrink-0" />
            )}
            <span className="flex-1 font-medium">{banner.text}</span>
            <button onClick={() => setBanner(null)} aria-label={t("dismiss")} className="cursor-pointer opacity-70 hover:opacity-100">
              <X className="size-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-card border border-border p-6 rounded-2xl shadow-sm">
        <div>
          <h2 className="text-lg font-bold tracking-tight">{t("header.title")}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t("header.description")}
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)} className="cursor-pointer shrink-0 gap-2">
          <Plus className="size-4" />
          {t("header.addServer")}
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        </div>
      ) : servers.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border p-12 text-center max-w-lg mx-auto">
          <div className="size-12 rounded-2xl bg-muted grid place-items-center mx-auto mb-4 text-muted-foreground">
            <Cpu className="size-6" />
          </div>
          <h3 className="text-sm font-semibold">{t("empty.title")}</h3>
          <p className="mt-2 text-xs text-muted-foreground max-w-sm mx-auto">
            {t("empty.body")}
          </p>
          <Button onClick={() => setAddOpen(true)} variant="outline" className="mt-5 cursor-pointer">
            {t("empty.addServer")}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {servers.map((server) => {
            const isExpanded = expandedServerId === server.id;
            const isBusy = busyServerId === server.id;
            const headersCount = Object.keys(server.headers || {}).length;
            const toolsCount = Array.isArray(server.tools) ? server.tools.length : 0;

            return (
              <div
                key={server.id}
                className="rounded-2xl border border-border bg-card overflow-hidden transition-shadow hover:shadow-sm"
              >
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="size-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-100/50 dark:border-indigo-900/50 grid place-items-center shrink-0">
                      <Cpu className="size-5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2.5">
                        <h4 className="text-sm font-semibold tracking-tight text-foreground">
                          {server.name}
                        </h4>
                        {server.oauth_flow_status === "awaiting_authorization" ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/20 dark:text-amber-400 border border-amber-100 dark:border-amber-900/30 animate-pulse">
                            {t("awaitingAuth")}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30">
                            {t("active")}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Globe className="size-3.5" />
                          <code className="bg-muted px-1.5 py-0.5 rounded text-[11px] font-mono text-foreground/80 max-w-xs truncate">
                            {server.url}
                          </code>
                        </span>
                        {headersCount > 0 && (
                          <span className="flex items-center gap-1">
                            <Key className="size-3.5" />
                            {t("headersCount", { count: headersCount })}
                          </span>
                        )}
                        <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                          {t("toolsCount", { count: toolsCount })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center">
                    {server.oauth_flow_status === "awaiting_authorization" ? (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => handleAuthorizeServer(server.id)}
                        disabled={isBusy}
                        className="cursor-pointer bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5 font-semibold"
                      >
                        {isBusy ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Key className="size-3.5" />
                        )}
                        {t("authorize")}
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleTestServer(server.id)}
                        disabled={isBusy}
                        className="cursor-pointer gap-1.5"
                      >
                        <RefreshCw className={`size-3.5 ${isBusy ? "animate-spin" : ""}`} />
                        {t("testConnection")}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteServer(server.id, server.name)}
                      disabled={isBusy}
                      className="cursor-pointer text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpandedServerId(isExpanded ? null : server.id)}
                      className="cursor-pointer"
                    >
                      {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                    </Button>
                  </div>
                </div>

                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: "auto" }}
                      exit={{ height: 0 }}
                      className="overflow-hidden border-t border-border bg-muted/20"
                    >
                      <div className="p-5 space-y-4">
                        <div className="flex items-center justify-between">
                          <h5 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {t("discoveredTools")}
                          </h5>
                          <span className="text-xs text-muted-foreground">
                            {t("callableAs")} <code className="font-mono bg-muted px-1 py-0.5 rounded text-[11px] font-semibold text-foreground">{server.name}__&#123;tool_name&#125;</code>
                          </span>
                        </div>

                        {toolsCount === 0 ? (
                          <div className="text-xs text-muted-foreground py-2 italic">
                            {t("noToolsYet")}
                          </div>
                        ) : (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {server.tools.map((tool: McpTool, idx: number) => {
                              const properties = tool.inputSchema?.properties || {};
                              const requiredFields = tool.inputSchema?.required || [];

                              return (
                                <div
                                  key={idx}
                                  className="border border-border/60 bg-card rounded-xl p-4 flex flex-col justify-between"
                                >
                                  <div>
                                    <div className="flex items-center justify-between gap-2">
                                      <code className="text-xs font-semibold font-mono text-indigo-600 dark:text-indigo-400">
                                        {server.name}__{tool.name}
                                      </code>
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">
                                      {tool.description || t("noDescription")}
                                    </p>
                                  </div>

                                  {Object.keys(properties).length > 0 && (
                                    <div className="mt-3.5 pt-3.5 border-t border-border/40">
                                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-1.5">
                                        {t("parameters")}
                                      </span>
                                      <div className="flex flex-wrap gap-1.5">
                                        {Object.entries(properties).map(([pName, pVal]) => {
                                          const isRequired = requiredFields.includes(pName);
                                          return (
                                            <span
                                              key={pName}
                                              className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-mono border ${
                                                isRequired
                                                  ? "bg-indigo-50/50 border-indigo-100 text-indigo-800 dark:bg-indigo-950/20 dark:border-indigo-900/40 dark:text-indigo-300"
                                                  : "bg-muted border-border/80 text-foreground/75"
                                              }`}
                                            >
                                              {pName}
                                              {isRequired && <span className="text-red-500 ml-0.5">*</span>}
                                              <span className="opacity-50 ml-1">({pVal.type || "any"})</span>
                                            </span>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      )}

      <Dialog
        open={addOpen}
        onClose={() => !actionLoading && setAddOpen(false)}
        title={t("addDialog.title")}
        description={t("addDialog.description")}
        size="lg"
      >
        <form onSubmit={handleAddServer} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label={t("addDialog.nameLabel")}
              hint={t("addDialog.nameHint")}
            >
              <input
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                placeholder={t("addDialog.namePlaceholder")}
                disabled={actionLoading}
                className={inputCls}
                required
              />
            </Field>

            <Field
              label={t("addDialog.urlLabel")}
              hint={t("addDialog.urlHint")}
            >
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder={t("addDialog.urlPlaceholder")}
                type="url"
                disabled={actionLoading}
                className={inputCls}
                required
              />
            </Field>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-foreground/80 block">{t("addDialog.customHeaders")}</span>
              <button
                type="button"
                onClick={addHeaderRow}
                disabled={actionLoading}
                className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline flex items-center gap-1 cursor-pointer"
              >
                <Plus className="size-3" /> {t("addDialog.addHeader")}
              </button>
            </div>

            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {headers.map((h, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <input
                    value={h.key}
                    onChange={(e) => updateHeaderRow(idx, "key", e.target.value)}
                    placeholder={t("addDialog.headerKeyPlaceholder")}
                    disabled={actionLoading}
                    className={`${inputCls} flex-1`}
                  />
                  <input
                    value={h.value}
                    onChange={(e) => updateHeaderRow(idx, "value", e.target.value)}
                    placeholder={t("addDialog.headerValuePlaceholder")}
                    disabled={actionLoading}
                    className={`${inputCls} flex-1`}
                  />
                  <button
                    type="button"
                    onClick={() => removeHeaderRow(idx)}
                    disabled={actionLoading || headers.length === 1}
                    className="p-2 rounded text-muted-foreground hover:text-destructive hover:bg-muted cursor-pointer disabled:opacity-40"
                  >
                    <X className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-border/50">
            <button
              type="button"
              onClick={() => setOauthEnabled(!oauthEnabled)}
              className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 flex items-center gap-1.5 cursor-pointer"
            >
              {oauthEnabled ? t("addDialog.hideOauth") : t("addDialog.showOauth")}
              {oauthEnabled ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>
            {oauthEnabled && (
              <div className="mt-4 space-y-4 animate-in fade-in duration-200">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label={t("addDialog.clientIdLabel")} hint={t("addDialog.clientIdHint")}>
                    <input
                      value={oauthClientId}
                      onChange={(e) => setOauthClientId(e.target.value)}
                      placeholder={t("addDialog.clientIdPlaceholder")}
                      disabled={actionLoading}
                      className={inputCls}
                      required={oauthEnabled}
                    />
                  </Field>
                  <Field label={t("addDialog.clientSecretLabel")} hint={t("addDialog.clientSecretHint")}>
                    <input
                      value={oauthClientSecret}
                      onChange={(e) => setOauthClientSecret(e.target.value)}
                      placeholder={t("addDialog.clientSecretPlaceholder")}
                      disabled={actionLoading}
                      className={inputCls}
                    />
                  </Field>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label={t("addDialog.authUrlLabel")} hint={t("addDialog.authUrlHint")}>
                    <input
                      value={oauthAuthUrl}
                      onChange={(e) => setOauthAuthUrl(e.target.value)}
                      placeholder="https://auth.service.com/oauth/authorize"
                      type="url"
                      disabled={actionLoading}
                      className={inputCls}
                    />
                  </Field>
                  <Field label={t("addDialog.tokenUrlLabel")} hint={t("addDialog.tokenUrlHint")}>
                    <input
                      value={oauthTokenUrl}
                      onChange={(e) => setOauthTokenUrl(e.target.value)}
                      placeholder="https://auth.service.com/oauth/token"
                      type="url"
                      disabled={actionLoading}
                      className={inputCls}
                    />
                  </Field>
                </div>
                <Field label={t("addDialog.scopesLabel")} hint={t("addDialog.scopesHint")}>
                  <input
                    value={oauthScopes}
                    onChange={(e) => setOauthScopes(e.target.value)}
                    placeholder={t("addDialog.scopesPlaceholder")}
                    disabled={actionLoading}
                    className={inputCls}
                  />
                </Field>
              </div>
            )}
          </div>

          {errorMsg && (
            <div className="text-xs text-destructive flex items-start gap-1.5 bg-destructive/10 border border-destructive/20 rounded-xl p-3">
              <AlertCircle className="size-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setAddOpen(false)}
              disabled={actionLoading}
              className="cursor-pointer"
            >
              {t("addDialog.cancel")}
            </Button>
            <Button type="submit" disabled={actionLoading} className="cursor-pointer gap-1.5">
              {actionLoading && <Loader2 className="size-3.5 animate-spin" />}
              {t("addDialog.connectServer")}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
