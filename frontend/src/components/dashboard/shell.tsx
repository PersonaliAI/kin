"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { KinMark } from "@/components/kin-mark";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  MessageSquare,
  Share2,
  Activity,
  CheckSquare,
  Users,
  Calendar,
  Mail,
  Plug,
  Settings,
  CreditCard,
  LogOut,
  ChevronDown,
  Brain,
  FileText,
  Clock,
  Cpu,
  Code2,
  Phone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";

// `usePathname` here is next-intl's locale-aware version (from
// @/i18n/navigation), which strips any /it prefix — so comparing against
// these plain, unprefixed hrefs still works correctly for both locales.
// Using plain next/navigation's usePathname here was a real bug: on the
// Italian site every route is prefixed (/it/dashboard/chat), which broke
// both the TITLES lookup and the active-nav-item highlighting.
type NavKey = "overview" | "chat" | "activity" | "memory" | "tasks" | "contacts" | "calendar" | "inbox" | "documents" | "integrations" | "mcp" | "voiceAgents" | "schedule" | "developer" | "settings" | "billing" | "social";

const NAV: { section: "workspace" | "data" | "account"; items: { href: string; key: NavKey; icon: typeof LayoutDashboard }[] }[] = [
  {
    section: "workspace",
    items: [
      { href: "/dashboard", key: "overview", icon: LayoutDashboard },
      { href: "/dashboard/chat", key: "chat", icon: MessageSquare },
      // Social Copilot is still in development (OAuth flows, composer UI
      // bugs) — hidden from nav until it's ready. The route/page itself
      // still works if visited directly; just re-add this line to relink it.
      // { href: "/dashboard/social", key: "social", icon: Share2 },
      { href: "/dashboard/activity", key: "activity", icon: Activity },
      { href: "/dashboard/memory", key: "memory", icon: Brain },
    ],
  },
  {
    section: "data",
    items: [
      { href: "/dashboard/tasks", key: "tasks", icon: CheckSquare },
      { href: "/dashboard/contacts", key: "contacts", icon: Users },
      { href: "/dashboard/calendar", key: "calendar", icon: Calendar },
      { href: "/dashboard/inbox", key: "inbox", icon: Mail },
      { href: "/dashboard/documents", key: "documents", icon: FileText },
    ],
  },
  {
    section: "account",
    items: [
      { href: "/dashboard/integrations", key: "integrations", icon: Plug },
      { href: "/dashboard/mcp", key: "mcp", icon: Cpu },
      { href: "/dashboard/voice-agents", key: "voiceAgents", icon: Phone },
      { href: "/dashboard/schedule", key: "schedule", icon: Clock },
      { href: "/dashboard/developer", key: "developer", icon: Code2 },
      { href: "/dashboard/settings", key: "settings", icon: Settings },
      { href: "/dashboard/billing", key: "billing", icon: CreditCard },
    ],
  },
];

const TITLE_KEY_BY_PATH: Record<string, NavKey> = {
  "/dashboard": "overview",
  "/dashboard/chat": "chat",
  "/dashboard/activity": "activity",
  "/dashboard/memory": "memory",
  "/dashboard/documents": "documents",
  "/dashboard/tasks": "tasks",
  "/dashboard/contacts": "contacts",
  "/dashboard/calendar": "calendar",
  "/dashboard/inbox": "inbox",
  "/dashboard/integrations": "integrations",
  "/dashboard/mcp": "mcp",
  "/dashboard/voice-agents": "voiceAgents",
  "/dashboard/schedule": "schedule",
  "/dashboard/developer": "developer",
  "/dashboard/settings": "settings",
  "/dashboard/billing": "billing",
  "/dashboard/social": "social",
};

function TwoLineIcon({ className }: { className?: string }) {
  return (
    <svg
      width="18"
      height="14"
      viewBox="0 0 18 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <line x1="0" y1="3" x2="18" y2="3" stroke="currentColor" strokeWidth="1.5" />
      <line x1="0" y1="11" x2="18" y2="11" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <line x1="2" y1="2" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" />
      <line x1="14" y1="2" x2="2" y2="14" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function DashboardShell({
  user,
  children,
}: {
  user: {
    authEmail: string;
    authName: string;
    authAvatar: string | null;
  };
  children: React.ReactNode;
}) {
  const t = useTranslations("dashboard.shell");
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close drawer when route changes
  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [pathname]);

  // Lock body scroll while mobile drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  // Close user menu on outside click
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  const titleKey = TITLE_KEY_BY_PATH[pathname];
  const isOverview = pathname === "/dashboard";
  const firstName = user.authName.split(" ")[0] || user.authName;
  const title = isOverview
    ? t("greeting", { name: firstName })
    : titleKey
      ? t(`titles.${titleKey}.title`)
      : t("titles.default.title");
  const description = titleKey ? t(`titles.${titleKey}.description`) : "";

  const initials =
    user.authName
      .split(" ")
      .map((n) => n[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "K";

  return (
    <div className="h-screen flex bg-background text-foreground overflow-hidden">
      <DesktopSidebar pathname={pathname} />
      <MobileSidebar
        pathname={pathname}
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <header className="h-14 border-b border-border bg-background flex items-center justify-between px-4 md:px-8 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-2 -ml-2 rounded-md hover:bg-muted cursor-pointer"
              aria-label={t("openMenu")}
            >
              <TwoLineIcon />
            </button>
            <div className="min-w-0">
              <h1 className="text-base font-semibold tracking-tight truncate">
                {title}
              </h1>
              {description && (
                <p className="text-xs text-muted-foreground truncate hidden sm:block">
                  {description}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3" ref={menuRef}>
            <LanguageSwitcher className="hidden sm:inline-flex" />
            <ThemeToggle className="hidden sm:inline-flex" />
            <button
              onClick={() => setMenuOpen((s) => !s)}
              className="flex items-center gap-2 rounded-full pl-1 pr-2 py-1 hover:bg-muted transition-colors cursor-pointer"
            >
              {user.authAvatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.authAvatar}
                  alt={user.authName}
                  className="size-7 rounded-full object-cover"
                />
              ) : (
                <span className="size-7 rounded-full bg-foreground text-background grid place-items-center text-[11px] font-semibold">
                  {initials}
                </span>
              )}
              <ChevronDown className="size-3.5 text-muted-foreground" />
            </button>

            {menuOpen && (
              <div className="absolute right-4 md:right-8 top-12 w-60 rounded-xl border border-border bg-card shadow-lg z-40 overflow-x-hidden">
                {/* No overflow-y-hidden here (unlike most menu panels) —
                    the language dropdown row below needs its popover to
                    extend past this panel's bottom edge rather than being
                    clipped invisible. */}
                <div className="px-4 py-3 border-b border-border">
                  <div className="text-sm font-semibold truncate">{user.authName}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {user.authEmail}
                  </div>
                </div>
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border sm:hidden">
                  <span className="text-xs text-muted-foreground">{t("language")}</span>
                  <LanguageSwitcher />
                </div>
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border sm:hidden">
                  <span className="text-xs text-muted-foreground">{t("theme")}</span>
                  <ThemeToggle />
                </div>
                <div className="p-1.5">
                  <Button
                    variant="ghost"
                    className="w-full justify-start h-8 px-2 text-sm font-normal cursor-pointer"
                    onClick={signOut}
                  >
                    <LogOut className="size-4" />
                    {t("signOut")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </header>

        {children}
      </div>
    </div>
  );
}

function DesktopSidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 border-r border-border bg-background h-screen sticky top-0">
      <SidebarHeader />
      <SidebarNav pathname={pathname} />
      <SidebarFooter />
    </aside>
  );
}

function MobileSidebar({
  pathname,
  open,
  onClose,
}: {
  pathname: string;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="md:hidden fixed inset-0 z-50 bg-foreground/30 backdrop-blur-sm"
            aria-hidden
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="md:hidden fixed left-0 top-0 bottom-0 z-50 w-72 max-w-[85vw] bg-background border-r border-border flex flex-col shadow-xl"
          >
            <div className="h-14 flex items-center justify-between px-4 border-b border-border">
              <Link href="/dashboard" className="flex items-center">
                <KinMark size={28} showLabel />
              </Link>
              <button
                onClick={onClose}
                className="p-2 -mr-2 rounded-md hover:bg-muted text-muted-foreground cursor-pointer"
                aria-label="Close menu"
              >
                <CloseIcon />
              </button>
            </div>
            <SidebarNav pathname={pathname} />
            <SidebarFooter />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function SidebarHeader() {
  return (
    <div className="h-14 flex items-center px-5 border-b border-border">
      <Link href="/dashboard" className="flex items-center">
        <KinMark size={28} showLabel />
      </Link>
    </div>
  );
}

function SidebarNav({ pathname }: { pathname: string }) {
  const t = useTranslations("dashboard.shell");
  return (
    <nav className="flex-1 overflow-y-auto px-3 py-5 space-y-6">
      {NAV.map((group) => (
        <div key={group.section}>
          <div className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            {t(`sections.${group.section}`)}
          </div>
          <ul className="space-y-0.5">
            {group.items.map((item) => {
              const active =
                item.href === "/dashboard"
                  ? pathname === "/dashboard"
                  : pathname.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    prefetch
                    className={cn(
                      "group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                      active
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <item.icon className="size-4" />
                    <span className="flex-1">{t(`nav.${item.key}`)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SidebarFooter() {
  const t = useTranslations("dashboard.shell");
  return (
    <div className="border-t border-border p-3 text-[10px] text-muted-foreground">
      <div className="flex items-center gap-2 px-1.5">
        <span className="size-1.5 rounded-full bg-emerald-500" />
        {t("kinOnline")}
      </div>
    </div>
  );
}
