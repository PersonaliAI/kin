"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Check, Lock, Cpu, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { llmModelsApi, settings, type LlmProvider } from "@/lib/backend";

export function ModelSelector({
  initialProvider,
  initialModel,
}: {
  initialProvider?: string | null;
  initialModel?: string | null;
}) {
  const t = useTranslations("dashboard.modelSelector");
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [provider, setProvider] = useState(initialProvider || "google");
  const [model, setModel] = useState<string | null>(initialModel ?? null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    llmModelsApi
      .list()
      .then((res) => {
        // Gemini (byok_required: false) first, then BYOK providers in the order returned.
        const sorted = [...res.providers].sort(
          (a, b) => Number(a.byok_required) - Number(b.byok_required),
        );
        setProviders(sorted);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const currentProvider = providers.find((p) => p.id === provider);
  const currentModel =
    currentProvider?.models.find((m) => m.id === model) ?? currentProvider?.models[0];

  async function pick(p: LlmProvider, modelId: string | null) {
    const prevProvider = provider;
    const prevModel = model;
    setProvider(p.id);
    setModel(modelId);
    setOpen(false);
    setSaving(true);
    try {
      await settings.update({ preferred_provider: p.id, preferred_model: modelId });
    } catch {
      setProvider(prevProvider);
      setModel(prevModel);
    } finally {
      setSaving(false);
    }
  }

  const triggerLabel = loading
    ? t("loading")
    : (currentModel?.label ?? t("selectModel"));

  const triggerSub =
    currentProvider && currentProvider.byok_required && currentProvider.has_key
      ? t("yourKey")
      : null;

  if (loadError) return null;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        disabled={loading}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={t("trigger")}
        className={cn(
          "flex items-center gap-1.5 h-8 pl-2.5 pr-2 rounded-full border bg-card text-xs font-medium transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed",
          open ? "border-foreground/30 ring-1 ring-foreground/10" : "border-border hover:border-foreground/20",
        )}
      >
        <Cpu className="size-3.5 text-muted-foreground shrink-0" />
        <span className="truncate max-w-[140px]">{triggerLabel}</span>
        {triggerSub && (
          <span className="text-[10px] text-muted-foreground shrink-0">({triggerSub})</span>
        )}
        {saving ? (
          <Loader2 className="size-3 animate-spin text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown
            className={cn(
              "size-3.5 text-muted-foreground shrink-0 transition-transform",
              open && "rotate-180",
            )}
          />
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 z-30 mt-1.5 w-max min-w-[14rem] max-w-xs rounded-xl border border-border bg-card shadow-xl overflow-hidden max-h-96 overflow-y-auto custom-scrollbar"
            role="listbox"
          >
            {providers.map((p) => {
              const providerDisabled = p.byok_required && !p.has_key;
              return (
                <div key={p.id} className="py-1 border-b border-border/50 last:border-b-0">
                  <div className="px-3 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <span>{p.label}</span>
                    {providerDisabled && (
                      <span className="normal-case font-normal text-muted-foreground/70">
                        — {t("noKeyYet")}
                      </span>
                    )}
                  </div>
                  {p.models.map((m) => {
                    const isSelected = provider === p.id && model === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        disabled={providerDisabled}
                        title={providerDisabled ? t("addKeyHint", { provider: p.label }) : undefined}
                        onClick={() => pick(p, m.id)}
                        role="option"
                        aria-selected={isSelected}
                        className={cn(
                          "w-full flex items-start gap-2 px-3 py-2 text-left transition-colors",
                          providerDisabled
                            ? "opacity-50 cursor-not-allowed"
                            : "hover:bg-muted cursor-pointer",
                          isSelected && "bg-muted",
                        )}
                      >
                        {providerDisabled && (
                          <Lock className="size-3 mt-0.5 text-muted-foreground shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className={cn("text-sm truncate", isSelected && "font-medium")}>
                            {m.label}
                          </div>
                          {providerDisabled && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              {t("addKeyHint", { provider: p.label })}
                            </div>
                          )}
                        </div>
                        {isSelected && <Check className="size-3.5 shrink-0 mt-0.5" />}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
