"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  const t = useTranslations("dashboard.common");
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-foreground/20 backdrop-blur-sm"
          />
          <div className="fixed inset-0 z-50 overflow-y-auto p-4 pointer-events-none">
            <div className="min-h-full grid place-items-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.96, y: 8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96, y: 8 }}
                transition={{ duration: 0.15 }}
                className={cn(
                  "pointer-events-auto w-full max-h-[90vh] flex flex-col bg-card border border-border rounded-2xl shadow-xl",
                  size === "sm" && "max-w-sm",
                  size === "md" && "max-w-md",
                  size === "lg" && "max-w-2xl",
                )}
              >
                <div className="flex items-start justify-between px-5 pt-5 pb-3 shrink-0">
                  <div>
                    <h3 className="text-base font-semibold">{title}</h3>
                    {description && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {description}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={onClose}
                    className="p-1 -m-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
                    aria-label={t("close")}
                  >
                    <X className="size-4" />
                  </button>
                </div>
                <div className="px-5 pb-5 overflow-y-auto">{children}</div>
              </motion.div>
            </div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}

export function DialogFooter({ children }: { children: React.ReactNode }) {
  return <div className="mt-5 flex items-center justify-end gap-2">{children}</div>;
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: React.ReactNode;
}) {
  return (
    <label className="block mb-3">
      <span className="text-xs font-medium text-foreground/80 block mb-1.5">
        {label}
      </span>
      {children}
      {hint && (
        <span className="text-[11px] text-muted-foreground mt-1 block">{hint}</span>
      )}
    </label>
  );
}

export const inputCls =
  "w-full h-9 px-3 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20";

export const textareaCls =
  "w-full px-3 py-2 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 resize-y min-h-[80px]";
