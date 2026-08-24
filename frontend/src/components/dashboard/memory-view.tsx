"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Plus,
  Trash2,
  Loader2,
  AlertCircle,
  Search,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogFooter,
  Field,
  textareaCls,
} from "@/components/dashboard/dialog";
import { cn } from "@/lib/utils";
import { memoryApi, type Memory } from "@/lib/backend";
import { Select } from "@/components/ui/select";

const KIND_TONE: Record<string, string> = {
  preference: "bg-blue-50 text-blue-700",
  fact: "bg-slate-50 text-slate-700",
  event: "bg-amber-50 text-amber-700",
  relationship: "bg-purple-50 text-purple-700",
  goal: "bg-emerald-50 text-emerald-700",
  habit: "bg-orange-50 text-orange-700",
};

const KINDS = Object.keys(KIND_TONE);

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function MemoryView() {
  const t = useTranslations("dashboard.memory");
  const [memories, setMemories] = useState<Memory[] | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<string>("all");
  const [addOpen, setAddOpen] = useState(false);
  const [wipeOpen, setWipeOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const res = await memoryApi.list();
      setMemories(res.memories);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError"));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = useMemo(() => {
    if (!memories) return null;
    const lower = q.trim().toLowerCase();
    return memories.filter((m) => {
      if (filter !== "all" && m.kind !== filter) return false;
      if (lower && !m.content.toLowerCase().includes(lower)) return false;
      return true;
    });
  }, [memories, q, filter]);

  async function remove(id: string) {
    if (!confirm(t("forgetConfirm"))) return;
    const prev = memories;
    setMemories((m) => (m ? m.filter((x) => x.id !== id) : m));
    try {
      await memoryApi.delete(id);
    } catch (e) {
      setMemories(prev);
      setError(e instanceof Error ? e.message : t("deleteFailed"));
    }
  }

  async function wipe() {
    setBusy(true);
    try {
      await memoryApi.wipe();
      setMemories([]);
      setWipeOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("wipeFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="w-full h-9 pl-9 pr-3 bg-card border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setWipeOpen(true)}
            disabled={!memories || memories.length === 0}
            className="h-9 px-3 cursor-pointer text-destructive border-destructive/30 hover:bg-destructive/5"
          >
            <Trash2 className="size-3.5" />
            {t("forgetAll")}
          </Button>
          <Button onClick={() => setAddOpen(true)} className="h-9 px-3 cursor-pointer">
            <Plus className="size-3.5" />
            {t("addMemory")}
          </Button>
        </div>
      </div>

      <div className="relative max-w-full">
        <div className="flex rounded-lg border border-border bg-card p-0.5 overflow-x-auto max-w-full [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {(["all", ...KINDS] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0",
                filter === f
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {f === "all" ? t("all") : t(`kinds.${f}` as "kinds.fact")}
            </button>
          ))}
        </div>
        {/* Fade hints that the row scrolls — the row itself has no visible
            scrollbar, so without this it just looks cut off. */}
        <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-background to-transparent rounded-r-lg" />
      </div>

      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive text-xs px-3 py-2 flex items-start gap-2">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {memories === null ? (
        <div className="rounded-xl border border-border bg-card p-12 grid place-items-center text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      ) : visible && visible.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
            <Brain className="size-5" />
          </div>
          <h3 className="mt-4 text-sm font-semibold">
            {memories.length === 0 ? t("nothingYet") : t("noMatches")}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground max-w-sm mx-auto">
            {memories.length === 0 ? t("nothingYetSub") : t("tryDifferent")}
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          <AnimatePresence initial={false}>
            {(visible ?? []).map((m) => {
              const kind = m.kind ?? "fact";
              const tone = KIND_TONE[kind] ?? KIND_TONE.fact;
              return (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-start gap-3 p-4 hover:bg-muted/40 transition-colors group"
                >
                  <div className="size-7 shrink-0 rounded-lg bg-muted text-muted-foreground grid place-items-center">
                    <Sparkles className="size-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider",
                          tone,
                        )}
                      >
                        {t(`kinds.${kind}` as "kinds.fact")}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        {t("addedOn", { date: fmtDate(m.created_at) })}
                      </span>
                    </div>
                    <p className="mt-1 text-sm break-words">{m.content}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => remove(m.id)}
                    aria-label={t("forget")}
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      <AddMemoryDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={() => {
          setAddOpen(false);
          refresh();
        }}
      />
      <WipeDialog
        open={wipeOpen}
        onClose={() => setWipeOpen(false)}
        onConfirm={wipe}
        busy={busy}
      />
    </>
  );
}

function AddMemoryDialog({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const t = useTranslations("dashboard.memory");
  const td = useTranslations("dashboard.memory.addDialog");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("fact");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setContent("");
      setKind("fact");
      setErr(null);
    }
  }, [open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!content.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await memoryApi.add(content.trim(), kind);
      onAdded();
    } catch (e) {
      setErr(e instanceof Error ? e.message : td("addFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={td("title")}
      description={td("description")}
    >
      <form onSubmit={submit}>
        <Field label={td("memoryLabel")}>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            required
            autoFocus
            className={textareaCls}
            placeholder={td("memoryPlaceholder")}
          />
        </Field>
        <Field label={td("kindLabel")}>
          <Select
            value={kind}
            onChange={setKind}
            options={KINDS.map((k) => ({ value: k, label: t(`kinds.${k}` as "kinds.fact") }))}
          />
        </Field>
        {err && (
          <p className="text-xs text-destructive flex items-start gap-1.5">
            <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
            {err}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} className="cursor-pointer">
            {td("cancel")}
          </Button>
          <Button type="submit" disabled={!content.trim() || busy} className="cursor-pointer">
            {busy && <Loader2 className="size-3.5 animate-spin" />}
            {td("rememberThis")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

function WipeDialog({
  open,
  onClose,
  onConfirm,
  busy,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  busy: boolean;
}) {
  const t = useTranslations("dashboard.memory.wipeDialog");
  return (
    <Dialog open={open} onClose={onClose} title={t("title")}>
      <p className="text-sm text-muted-foreground">
        {t("body")}
      </p>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} className="cursor-pointer">
          {t("cancel")}
        </Button>
        <Button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive/20 cursor-pointer"
        >
          {busy && <Loader2 className="size-3.5 animate-spin" />}
          {t("confirm")}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
