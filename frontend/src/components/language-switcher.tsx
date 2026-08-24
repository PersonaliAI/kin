"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { Globe, Check, ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, usePathname } from "@/i18n/navigation";
import { routing, type AppLocale } from "@/i18n/routing";
import { cn } from "@/lib/utils";

const CODE: Record<AppLocale, string> = {
  en: "EN",
  it: "IT",
  fr: "FR",
  es: "ES",
};

const NATIVE_NAME: Record<AppLocale, string> = {
  en: "English",
  it: "Italiano",
  fr: "Français",
  es: "Español",
};

type Variant = "dark" | "themed";

// Locale dropdown used on the marketing landing page, inside the dashboard
// header, in the dashboard's mobile account menu, and on auth pages.
//
// variant="dark" is fixed-palette for the marketing landing page, which is
// always dark regardless of the user's theme preference. variant="themed"
// (default) uses the shadcn-style CSS variable tokens so it matches
// light/dark mode inside the dashboard/auth pages.
export function LanguageSwitcher({
  className,
  variant = "themed",
}: {
  className?: string;
  variant?: Variant;
}) {
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function pick(loc: AppLocale) {
    setOpen(false);
    router.replace(pathname, { locale: loc });
  }

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors cursor-pointer",
          variant === "dark"
            ? "border border-white/10 bg-white/5 text-white/70 hover:text-white"
            : "border border-border bg-muted text-muted-foreground hover:text-foreground",
        )}
      >
        <Globe className="size-3" />
        {CODE[locale] ?? locale.toUpperCase()}
        <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12 }}
            role="listbox"
            className={cn(
              "absolute right-0 z-50 mt-1.5 w-40 rounded-xl border shadow-xl overflow-hidden py-1",
              variant === "dark"
                ? "border-white/10 bg-neutral-900"
                : "border-border bg-card",
            )}
          >
            {routing.locales.map((loc) => {
              const active = loc === locale;
              return (
                <button
                  key={loc}
                  type="button"
                  onClick={() => pick(loc)}
                  role="option"
                  aria-selected={active}
                  className={cn(
                    "w-full flex items-center gap-2 px-3 py-2 text-sm text-left cursor-pointer transition-colors",
                    variant === "dark"
                      ? active
                        ? "bg-white/10 text-white"
                        : "text-white/70 hover:bg-white/5 hover:text-white"
                      : active
                        ? "bg-muted font-medium"
                        : "hover:bg-muted",
                  )}
                >
                  <span className="flex-1 truncate">{NATIVE_NAME[loc]}</span>
                  {active && <Check className="size-3.5 shrink-0" />}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
