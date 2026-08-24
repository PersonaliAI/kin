"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText,
  FileSpreadsheet,
  FileType2,
  Loader2,
  Plus,
  Trash2,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  FolderInput,
  Search,
  X,
  Eraser,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogFooter,
  Field,
  inputCls,
} from "@/components/dashboard/dialog";
import { LocalTime } from "@/components/local-time";
import { cn } from "@/lib/utils";
import { documentsApi, type DriveDocument } from "@/lib/backend";

function mimeIcon(mime: string | null) {
  const m = (mime ?? "").toLowerCase();
  if (m.includes("spreadsheet") || m.includes("csv"))
    return <FileSpreadsheet className="size-4 text-emerald-600" />;
  if (m.includes("presentation"))
    return <FileType2 className="size-4 text-orange-600" />;
  if (m.includes("pdf")) return <FileText className="size-4 text-red-600" />;
  if (m.includes("document") || m.includes("wordprocessing"))
    return <FileText className="size-4 text-blue-600" />;
  return <FileText className="size-4 text-muted-foreground" />;
}

function mimeLabel(
  mime: string | null,
  t: ReturnType<typeof useTranslations<"dashboard.documents">>,
): string {
  const m = (mime ?? "").toLowerCase();
  if (m.includes("vnd.google-apps.document")) return t("mimeLabels.googleDoc");
  if (m.includes("vnd.google-apps.spreadsheet")) return t("mimeLabels.googleSheet");
  if (m.includes("vnd.google-apps.presentation")) return t("mimeLabels.googleSlides");
  if (m.includes("pdf")) return t("mimeLabels.pdf");
  if (m.includes("wordprocessing")) return t("mimeLabels.wordDoc");
  if (m.startsWith("text/")) return t("mimeLabels.text");
  return mime ?? t("mimeLabels.file");
}

export function DocumentsView({
  googleConnected = true,
  microsoftConnected = false,
}: {
  googleConnected?: boolean;
  microsoftConnected?: boolean;
}) {
  const t = useTranslations("dashboard.documents");
  const [docs, setDocs] = useState<DriveDocument[] | null>(null);
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [bulkBusy, setBulkBusy] = useState<"failed" | "all" | null>(null);
  const [lastSubmitAt, setLastSubmitAt] = useState<number>(0);

  async function refresh(initial = false) {
    if (!initial) setRefreshing(true);
    try {
      const res = await documentsApi.list();
      setDocs(res.documents);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("loadError"));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    refresh(true);
    const interval = setInterval(() => {
      const recentSubmit = Date.now() - lastSubmitAt < 60_000;
      setDocs((current) => {
        const hasPending = current?.some((d) => d.status === "pending");
        if (hasPending || recentSubmit) {
          documentsApi
            .list()
            .then((res) => setDocs(res.documents))
            .catch(() => undefined);
        }
        return current;
      });
    }, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastSubmitAt]);

  const visible = (docs ?? []).filter((d) => {
    if (!search.trim()) return true;
    return d.file_name.toLowerCase().includes(search.trim().toLowerCase());
  });

  async function remove(doc: DriveDocument) {
    if (!confirm(t("removeConfirm", { name: doc.file_name }))) return;
    const prev = docs;
    setDocs((d) => (d ? d.filter((x) => x.id !== doc.id) : d));
    try {
      await documentsApi.delete(doc.id);
    } catch (e) {
      setDocs(prev);
      setErr(e instanceof Error ? e.message : t("deleteFailed"));
    }
  }

  async function bulkDelete(status?: "failed") {
    const confirmMsg = status === "failed" ? t("bulkConfirmFailed") : t("bulkConfirmAll");
    if (!confirm(confirmMsg)) return;
    setBulkBusy(status ?? "all");
    try {
      await documentsApi.wipe(status);
      await refresh(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("bulkDeleteFailed"));
    } finally {
      setBulkBusy(null);
    }
  }

  const pending = (docs ?? []).filter((d) => d.status === "pending").length;
  const indexedTotal = (docs ?? []).filter((d) => d.status === "indexed").length;
  const chunkTotal = (docs ?? []).reduce(
    (s, d) => s + (d.chunk_count || 0),
    0,
  );

  return (
    <>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("filterPlaceholder")}
              className="w-full h-9 pl-9 pr-3 bg-card border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20"
            />
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            onClick={() => refresh(false)}
            disabled={refreshing}
            className="h-9 px-3 cursor-pointer"
          >
            <RefreshCw className={cn("size-3.5", refreshing && "animate-spin")} />
            {t("refresh")}
          </Button>
          {(docs ?? []).some((d) => d.status === "failed") && (
            <Button
              variant="outline"
              onClick={() => bulkDelete("failed")}
              disabled={bulkBusy !== null}
              className="h-9 px-3 cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/5"
            >
              {bulkBusy === "failed" ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <X className="size-3.5" />
              )}
              {t("deleteFailedBtn")}
            </Button>
          )}
          {(docs ?? []).length > 0 && (
            <Button
              variant="outline"
              onClick={() => bulkDelete()}
              disabled={bulkBusy !== null}
              className="h-9 px-3 cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/5"
            >
              {bulkBusy === "all" ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Eraser className="size-3.5" />
              )}
              {t("wipeAll")}
            </Button>
          )}
          <Button onClick={() => setAddOpen(true)} className="h-9 px-3 cursor-pointer">
            <Plus className="size-3.5" />
            {t("indexFolder")}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label={t("stats.indexed")} value={indexedTotal} />
        <Stat label={t("stats.pending")} value={pending} tone={pending > 0 ? "warn" : undefined} />
        <Stat label={t("stats.chunks")} value={chunkTotal} />
      </div>

      <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
        <b className="text-foreground">{t("supportedTypes.label")}</b>{" "}
        {t("supportedTypes.body")}
      </div>

      {err && (
        <div className="rounded-lg bg-destructive/10 text-destructive text-xs px-3 py-2 flex items-start gap-2">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>{err}</span>
        </div>
      )}

      {docs === null ? (
        <div className="rounded-xl border border-border bg-card p-12 grid place-items-center text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      ) : visible.length === 0 ? (
        <EmptyState onAdd={() => setAddOpen(true)} hasDocs={(docs?.length ?? 0) > 0} />
      ) : (
        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          <AnimatePresence initial={false}>
            {visible.map((d) => (
              <motion.div
                key={d.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-start gap-3 p-4 hover:bg-muted/40 transition-colors group"
              >
                <div className="size-7 shrink-0 rounded-lg bg-muted grid place-items-center">
                  {mimeIcon(d.mime_type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link
                      href={d.web_view_link ?? "#"}
                      target="_blank"
                      className="text-sm font-medium truncate hover:underline underline-offset-4"
                    >
                      {d.file_name}
                    </Link>
                    <StatusPill status={d.status} indexingLabel={t("status.indexing")} />
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                    <span>{mimeLabel(d.mime_type, t)}</span>
                    <span>·</span>
                    <span>{t("chunkCount", { count: d.chunk_count })}</span>
                    <span>·</span>
                    <span>
                      {t("indexedRelative")} <LocalTime iso={d.indexed_at} mode="relative" />
                    </span>
                  </div>
                  {d.status === "failed" && d.error && (
                    <p className="mt-1 text-[11px] text-destructive line-clamp-2">
                      {d.error}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {d.web_view_link && (
                    <Link
                      href={d.web_view_link}
                      target="_blank"
                      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-label={t("openInDrive")}
                    >
                      <ExternalLink className="size-3.5" />
                    </Link>
                  )}
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => remove(d)}
                    aria-label={t("removeFromIndex")}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      <AddDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        googleConnected={googleConnected}
        microsoftConnected={microsoftConnected}
        onStarted={() => {
          setAddOpen(false);
          setLastSubmitAt(Date.now());
          refresh(false);
        }}
      />
    </>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "warn";
}) {
  return (
    <div className="rounded-xl bg-card border border-border p-4">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-2 text-2xl font-semibold tracking-tight",
          tone === "warn" && "text-orange-600",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function StatusPill({
  status,
  indexingLabel,
}: {
  status: DriveDocument["status"];
  indexingLabel: string;
}) {
  const tone =
    status === "indexed"
      ? "bg-emerald-50 text-emerald-700"
      : status === "pending"
        ? "bg-amber-50 text-amber-700"
        : "bg-destructive/10 text-destructive";
  return (
    <span
      className={cn(
        "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider",
        tone,
      )}
    >
      {status === "pending" ? indexingLabel : status}
    </span>
  );
}

function EmptyState({
  onAdd,
  hasDocs,
}: {
  onAdd: () => void;
  hasDocs: boolean;
}) {
  const t = useTranslations("dashboard.documents.emptyState");
  return (
    <div className="rounded-xl border border-border bg-card p-12 text-center">
      <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
        <FolderInput className="size-5" />
      </div>
      <h3 className="mt-4 text-sm font-semibold">
        {hasDocs ? t("noMatches") : t("noneYet")}
      </h3>
      <p className="mt-1 text-xs text-muted-foreground max-w-sm mx-auto">
        {hasDocs ? t("tryDifferent") : t("explainer")}
      </p>
      <Button className="mt-4 cursor-pointer" onClick={onAdd}>
        <Plus className="size-3.5" />
        {t("indexFolder")}
      </Button>
    </div>
  );
}

function AddDialog({
  open,
  onClose,
  onStarted,
  googleConnected,
  microsoftConnected,
}: {
  open: boolean;
  onClose: () => void;
  onStarted: () => void;
  googleConnected: boolean;
  microsoftConnected: boolean;
}) {
  const t = useTranslations("dashboard.documents.addDialog");
  const defaultSource: "gdrive" | "onedrive" =
    googleConnected ? "gdrive" : microsoftConnected ? "onedrive" : "gdrive";
  const [folderInput, setFolderInput] = useState("");
  const [maxFiles, setMaxFiles] = useState(50);
  const [source, setSource] = useState<"gdrive" | "onedrive">(defaultSource);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setFolderInput("");
      setMaxFiles(50);
      setSource(defaultSource);
      setErr(null);
    }
  }, [open, defaultSource]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!folderInput.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await documentsApi.indexFolder(folderInput.trim(), maxFiles, source);
      onStarted();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("indexFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("title")}
      description={t("description")}
    >
      <form onSubmit={submit}>
        {(googleConnected || microsoftConnected) && (
          <Field
            label={t("sourceLabel")}
            hint={
              !googleConnected
                ? t("connectGoogleHint")
                : !microsoftConnected
                  ? t("connectMicrosoftHint")
                  : undefined
            }
          >
            <div className="inline-flex rounded-lg border border-border bg-background p-0.5">
              <button
                type="button"
                onClick={() => setSource("gdrive")}
                disabled={!googleConnected}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                  source === "gdrive"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                  !googleConnected && "opacity-40 cursor-not-allowed hover:text-muted-foreground",
                )}
              >
                {t("googleDrive")}
              </button>
              <button
                type="button"
                onClick={() => setSource("onedrive")}
                disabled={!microsoftConnected}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                  source === "onedrive"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                  !microsoftConnected && "opacity-40 cursor-not-allowed hover:text-muted-foreground",
                )}
              >
                {t("oneDrive")}
              </button>
            </div>
          </Field>
        )}
        {!googleConnected && !microsoftConnected && (
          <div className="rounded-lg bg-amber-50 border border-amber-100 text-amber-800 p-3 text-xs flex items-start gap-2 mb-3">
            <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
            <span>
              {t.rich("connectPrompt", {
                link: () => (
                  <a
                    href="/dashboard/integrations"
                    className="underline underline-offset-2 font-medium"
                  >
                    /dashboard/integrations
                  </a>
                ),
              })}
            </span>
          </div>
        )}
        <Field
          label={t("folderLabel")}
          hint={source === "gdrive" ? t("folderHintGoogle") : t("folderHintMicrosoft")}
        >
          <input
            value={folderInput}
            onChange={(e) => setFolderInput(e.target.value)}
            placeholder={
              source === "gdrive" ? t("folderPlaceholderGoogle") : t("folderPlaceholderMicrosoft")
            }
            autoFocus
            className={inputCls}
          />
        </Field>
        <Field label={t("maxFilesLabel")} hint={t("maxFilesHint")}>
          <input
            type="number"
            min={1}
            max={200}
            value={maxFiles}
            onChange={(e) =>
              setMaxFiles(
                Math.min(200, Math.max(1, parseInt(e.target.value, 10) || 50)),
              )
            }
            className={`${inputCls} max-w-[120px]`}
          />
        </Field>
        {err && (
          <p className="text-xs text-destructive flex items-start gap-1.5 mb-3">
            <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
            {err}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} className="cursor-pointer">
            {t("cancel")}
          </Button>
          <Button
            type="submit"
            disabled={!folderInput.trim() || busy}
            className="cursor-pointer"
          >
            {busy && <Loader2 className="size-3.5 animate-spin" />}
            {t("startIndexing")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
