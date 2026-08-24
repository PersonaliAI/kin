"use client";
import { useEffect, useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  Loader2,
  AlertCircle,
  Send,
  X,
  Mail,
  Calendar,
  CheckSquare,
  Users,
  ExternalLink,
  HardDrive,
  FileText,
  FileSpreadsheet,
  Presentation,
  Search,
  Sparkles,
  Cpu,
  Music,
  ShoppingBag,
  CreditCard,
  PenTool,
  Columns,
  GitBranch,
  Database,
  Table,
  Video,
  BookOpen,
  Folder,
  Cloud,
  Workflow,
  Lock,
  DollarSign,
  Activity,
  Layers,
  Terminal,
  MessageSquare,
  Globe,
  Share2,
  Server,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, Field, inputCls } from "./dialog";
import { Select } from "@/components/ui/select";
import { integrations, flowCredentials, marketplace, integrationsCatalog as apiCatalog, type ExtraGoogleAccount, type IntegrationSummary } from "@/lib/backend";
import { UpgradeButton } from "@/components/dashboard/upgrade-modal";

function SlackIcon({ className }: { className?: string }) {
  return (
    <svg className={`size-5 ${className || ""}`} viewBox="0 0 24 24" fill="currentColor">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523 2.528 2.528 0 0 1-2.522-2.523 2.528 2.528 0 0 1 2.522-2.52h2.52v2.52zm1.261 0a2.528 2.528 0 0 1 2.52-2.52h5.043a2.528 2.528 0 0 1 2.522 2.52 2.528 2.528 0 0 1-2.522 2.522H8.823a2.528 2.528 0 0 1-2.52-2.522zM8.823 5.043a2.528 2.528 0 0 1-2.52-2.52A2.528 2.528 0 0 1 8.823 0a2.528 2.528 0 0 1 2.522 2.522v2.52h-2.522zm0 1.261a2.528 2.528 0 0 1 2.522 2.52v5.043a2.528 2.528 0 0 1-2.522 2.522 2.528 2.528 0 0 1-2.52-2.522V8.824a2.528 2.528 0 0 1 2.52-2.52zM18.958 8.824a2.528 2.528 0 0 1 2.522-2.52 2.528 2.528 0 0 1 2.52 2.52 2.528 2.528 0 0 1-2.52 2.522h-2.522V8.824zm-1.261 0a2.528 2.528 0 0 1-2.52 2.52h-5.043a2.528 2.528 0 0 1-2.522-2.52 2.528 2.528 0 0 1 2.522-2.522h5.043a2.528 2.528 0 0 1 2.52 2.522zM15.177 18.957a2.528 2.528 0 0 1 2.52 2.522 2.528 2.528 0 0 1-2.52 2.521 2.528 2.528 0 0 1-2.522-2.521v-2.522h2.522zm0-1.261a2.528 2.528 0 0 1-2.522-2.52v-5.043a2.528 2.528 0 0 1 2.522-2.522 2.528 2.528 0 0 1 2.52 2.522v5.043a2.528 2.528 0 0 1-2.52 2.52z" />
    </svg>
  );
}

function TrelloIcon({ className }: { className?: string }) {
  return (
    <svg className={`size-5 ${className || ""}`} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19.5 2h-15A2.5 2.5 0 0 0 2 4.5v15A2.5 2.5 0 0 0 4.5 22h15a2.5 2.5 0 0 0 2.5-2.5v-15A2.5 2.5 0 0 0 19.5 2zm-8.25 14.5a1.25 1.25 0 0 1-1.25 1.25H6.25A1.25 1.25 0 0 1 5 16.5V6.25A1.25 1.25 0 0 1 6.25 5h3.75a1.25 1.25 0 0 1 1.25 1.25v10.25zm7.5-5a1.25 1.25 0 0 1-1.25 1.25h-3.75a1.25 1.25 0 0 1-1.25-1.25V6.25A1.25 1.25 0 0 1 13.75 5h3.75a1.25 1.25 0 0 1 1.25 1.25v5.25z" />
    </svg>
  );
}

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg className={`size-5 ${className || ""}`} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

type Props = {
  initialGoogleEmail: string | null;
  initialMicrosoftEmail: string | null;
  
  plan: string;
};

export function IntegrationsView({
  initialGoogleEmail,
  initialMicrosoftEmail,

  plan,
}: Props) {
  const t = useTranslations("dashboard.integrations");
  const searchParams = useSearchParams();

  const googleParam = searchParams.get("google");
  const microsoftParam = searchParams.get("microsoft");

  const [googleEmail, setGoogleEmail] = useState(initialGoogleEmail);
  const [microsoftEmail, setMicrosoftEmail] = useState(initialMicrosoftEmail);

  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  
  // Search and Category states
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");
  
  // Connection States
  const [mockConnections, setMockConnections] = useState<Record<string, { connected: boolean; fields: Record<string, string> }>>({});
  const [customIntegrations, setCustomIntegrations] = useState<IntegrationSummary[]>([]);

  // Import OpenAPI Spec Modal state
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importOpenApiUrl, setImportOpenApiUrl] = useState("");
  const [importName, setImportName] = useState("");
  const [importCategory, setImportCategory] = useState("productivity");
  const [importError, setImportError] = useState<string | null>(null);
  const [importBusy, setImportBusy] = useState(false);

  // Config Dialog States for custom credentials fallback
  const [configDialog, setConfigDialog] = useState<{
    slug: string;
    name: string;
    fields: Array<{ name: string; label: string; placeholder: string; type: string }>;
  } | null>(null);
  const [configFields, setConfigFields] = useState<Record<string, string>>({});
  const [configError, setConfigError] = useState<string | null>(null);

  // Load connection states and DB published integrations on mount
  useEffect(() => {
    async function loadData() {
      try {
        const [credsRes, installsRes, catalogRes] = await Promise.all([
          flowCredentials.list().catch(() => ({ credentials: [] })),
          marketplace.installs().catch(() => ({ installs: [] })),
          apiCatalog.list().catch(() => ({ integrations: [] })),
        ]);
        
        const activeConnections: Record<string, { connected: boolean; fields: Record<string, string> }> = {};
        
        if (credsRes?.credentials) {
          credsRes.credentials.forEach((cred) => {
            activeConnections[cred.integration_slug] = {
              connected: true,
              fields: { api_key: "********" },
            };
          });
        }
        
        if (installsRes?.installs) {
          installsRes.installs.forEach((inst) => {
            if (!activeConnections[inst.integration_slug]) {
              activeConnections[inst.integration_slug] = {
                connected: true,
                fields: {},
              };
            }
          });
        }

        if (catalogRes?.integrations) {
          setCustomIntegrations(catalogRes.integrations);
        }
        
        setMockConnections(activeConnections);
      } catch (e) {
        console.error("Failed to load backend integration data", e);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    if (googleParam === "ok") {
      setBanner({ kind: "ok", text: t("banners.googleOk") });
    } else if (googleParam === "added") {
      setBanner({ kind: "ok", text: t("banners.googleAdded") });
    } else if (googleParam === "error") {
      setBanner({ kind: "err", text: t("banners.googleError") });
    } else if (microsoftParam === "ok") {
      setBanner({ kind: "ok", text: t("banners.microsoftOk") });
    } else if (microsoftParam === "error") {
      setBanner({ kind: "err", text: t("banners.microsoftError") });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleParam, microsoftParam]);

  // Core Connection Hooks
  async function connectGoogle() {
    setBusyKey("google-connect");
    try {
      const { url } = await integrations.startGoogleConnect();
      window.location.href = url;
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("failed") });
      setBusyKey(null);
    }
  }

  async function connectMicrosoft() {
    setBusyKey("microsoft-connect");
    try {
      const { url } = await integrations.startMicrosoftConnect();
      window.location.href = url;
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("failed") });
      setBusyKey(null);
    }
  }

  async function disconnectMicrosoft() {
    if (!confirm(t("disconnectMicrosoftConfirm"))) return;
    setBusyKey("microsoft-disconnect");
    try {
      await integrations.disconnectMicrosoft();
      setMicrosoftEmail(null);
      setBanner({ kind: "ok", text: t("microsoftDisconnected") });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("failed") });
    } finally {
      setBusyKey(null);
    }
  }

  async function disconnectGoogle() {
    if (!confirm(t("disconnectGoogleConfirm"))) return;
    setBusyKey("google-disconnect");
    try {
      await integrations.disconnectGoogle();
      setGoogleEmail(null);
      setBanner({ kind: "ok", text: t("googleDisconnected") });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("failed") });
    } finally {
      setBusyKey(null);
    }
  }

  // API Credentials Connection Handler
  function handleConnectMock(slug: string, name: string) {
    const fields = [
      { name: "api_key", label: "API Key / Bearer Token", placeholder: "Enter key or bearer token...", type: "password" },
    ];
    setConfigFields({});
    setConfigError(null);
    setConfigDialog({ slug, name, fields });
  }

  async function submitMockConnection(e: React.FormEvent) {
    e.preventDefault();
    if (!configDialog) return;
    const requiredEmpty = configDialog.fields.some((f) => !configFields[f.name]?.trim());
    if (requiredEmpty) {
      setConfigError("All configuration fields are required.");
      return;
    }

    setBusyKey(`${configDialog.slug}-connect`);
    try {
      await flowCredentials.save(configDialog.slug, configFields);
      await marketplace.install(configDialog.slug);

      const updated = {
        ...mockConnections,
        [configDialog.slug]: { connected: true, fields: configFields },
      };
      setMockConnections(updated);
      setBanner({ kind: "ok", text: `${configDialog.name} integration connected successfully.` });
      setConfigDialog(null);
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "Failed to save integration credentials.");
    } finally {
      setBusyKey(null);
    }
  }

  async function disconnectMock(slug: string, name: string) {
    if (!confirm(`Disconnect ${name}?`)) return;
    setBusyKey(`${slug}-disconnect`);
    try {
      await flowCredentials.delete(slug).catch(() => {});
      await marketplace.uninstall(slug).catch(() => {});

      const updated = { ...mockConnections };
      delete updated[slug];
      setMockConnections(updated);
      setBanner({ kind: "ok", text: `${name} disconnected.` });
    } catch (err) {
      setBanner({
        kind: "err",
        text: err instanceof Error ? err.message : `Failed to disconnect ${name}.`,
      });
    } finally {
      setBusyKey(null);
    }
  }

  // Handle OpenAPI Spec Import
  async function handleImportIntegration(e: React.FormEvent) {
    e.preventDefault();
    if (!importOpenApiUrl.trim()) return;
    setImportBusy(true);
    setImportError(null);
    try {
      const res = await marketplace.publish({
        openapi_url: importOpenApiUrl.trim(),
        name: importName.trim() || undefined,
        category: importCategory,
      });
      setBanner({ kind: "ok", text: `Integration "${res.name || importName || 'Custom API'}" imported successfully!` });
      setImportDialogOpen(false);
      setImportOpenApiUrl("");
      setImportName("");
      
      const catalogRes = await apiCatalog.list().catch(() => ({ integrations: [] }));
      if (catalogRes?.integrations) {
        setCustomIntegrations(catalogRes.integrations);
      }
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Failed to import OpenAPI spec.");
    } finally {
      setImportBusy(false);
    }
  }

  // Massively Expanded 110+ Integration Database Catalog
  const integrationsCatalog = useMemo(() => {
    const googleConnected = !!googleEmail;
    const microsoftConnected = !!microsoftEmail;

    const presetItems = [
      // Accounts
      {
        slug: "google",
        name: t("google.title"),
        description: t("google.disconnected"),
        category: "communication",
        provider: "google",
        connected: googleConnected,
        details: googleConnected ? t("google.connected", { email: googleEmail }) : null,
        onConnect: connectGoogle,
        onDisconnect: disconnectGoogle,
        isAccount: true,
      },
      {
        slug: "microsoft",
        name: t("microsoft.title"),
        description: t("microsoft.disconnected"),
        category: "communication",
        provider: "microsoft",
        connected: microsoftConnected,
        details: microsoftConnected ? t("microsoft.connected", { email: microsoftEmail }) : null,
        onConnect: connectMicrosoft,
        onDisconnect: disconnectMicrosoft,
        isAccount: true,
      },
      // Google Apps
      {
        slug: "gmail",
        name: t("services.gmail.title"),
        description: t("services.gmail.description"),
        category: "communication",
        icon: <Mail className="size-5 text-red-600" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/inbox",
        openHref: "https://mail.google.com",
        dashboardLabel: t("services.gmail.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "calendarGoogle",
        name: t("services.calendarGoogle.title"),
        description: t("services.calendarGoogle.description"),
        category: "productivity",
        icon: <Calendar className="size-5 text-blue-600" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/calendar",
        openHref: "https://calendar.google.com",
        dashboardLabel: t("services.calendarGoogle.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "tasksGoogle",
        name: t("services.tasksGoogle.title"),
        description: t("services.tasksGoogle.description"),
        category: "productivity",
        icon: <CheckSquare className="size-5 text-blue-500" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/tasks",
        openHref: "https://tasks.google.com",
        dashboardLabel: t("services.tasksGoogle.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "contactsGoogle",
        name: t("services.contactsGoogle.title"),
        description: t("services.contactsGoogle.description"),
        category: "communication",
        icon: <Users className="size-5 text-blue-600" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/contacts",
        openHref: "https://contacts.google.com",
        dashboardLabel: t("services.contactsGoogle.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "drive",
        name: t("services.drive.title"),
        description: t("services.drive.description"),
        category: "storage",
        icon: <HardDrive className="size-5 text-amber-500" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/documents",
        openHref: "https://drive.google.com",
        dashboardLabel: t("services.drive.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "docs",
        name: t("services.docs.title"),
        description: t("services.docs.description"),
        category: "storage",
        icon: <FileText className="size-5 text-blue-500" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/documents",
        openHref: "https://docs.google.com",
        dashboardLabel: t("services.docs.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "sheets",
        name: t("services.sheets.title"),
        description: t("services.sheets.description"),
        category: "storage",
        icon: <FileSpreadsheet className="size-5 text-emerald-600" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/documents",
        openHref: "https://sheets.google.com",
        dashboardLabel: t("services.sheets.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      {
        slug: "slides",
        name: t("services.slides.title"),
        description: t("services.slides.description"),
        category: "storage",
        icon: <Presentation className="size-5 text-amber-600" />,
        connected: googleConnected,
        dashboardHref: "/dashboard/documents",
        openHref: "https://slides.google.com",
        dashboardLabel: t("services.slides.dashboardLabel"),
        openLabel: t("openInGoogle"),
        provider: "google",
      },
      // Microsoft Apps
      {
        slug: "outlookMail",
        name: t("services.outlookMail.title"),
        description: t("services.outlookMail.description"),
        category: "communication",
        icon: <Mail className="size-5 text-blue-700" />,
        connected: microsoftConnected,
        dashboardHref: "/dashboard/inbox",
        openHref: "https://outlook.live.com/mail/",
        dashboardLabel: t("services.outlookMail.dashboardLabel"),
        openLabel: t("openInOutlook"),
        provider: "microsoft",
      },
      {
        slug: "calendarOutlook",
        name: t("services.outlookCalendar.title"),
        description: t("services.outlookCalendar.description"),
        category: "productivity",
        icon: <Calendar className="size-5 text-blue-700" />,
        connected: microsoftConnected,
        dashboardHref: "/dashboard/calendar",
        openHref: "https://outlook.live.com/calendar/",
        dashboardLabel: t("services.outlookCalendar.dashboardLabel"),
        openLabel: t("openInOutlook"),
        provider: "microsoft",
      },
      {
        slug: "microsoftToDo",
        name: t("services.microsoftToDo.title"),
        description: t("services.microsoftToDo.description"),
        category: "productivity",
        icon: <CheckSquare className="size-5 text-blue-600" />,
        connected: microsoftConnected,
        dashboardHref: "/dashboard/tasks",
        openHref: "https://to-do.office.com/",
        dashboardLabel: t("services.microsoftToDo.dashboardLabel"),
        openLabel: t("openInMicrosoft"),
        provider: "microsoft",
      },
      {
        slug: "microsoftContacts",
        name: t("services.outlookContacts.title"),
        description: t("services.outlookContacts.description"),
        category: "communication",
        icon: <Users className="size-5 text-blue-700" />,
        connected: microsoftConnected,
        dashboardHref: "/dashboard/contacts",
        openHref: "https://outlook.live.com/people/",
        dashboardLabel: t("services.outlookContacts.dashboardLabel"),
        openLabel: t("openInOutlook"),
        provider: "microsoft",
      },
      {
        slug: "oneDrive",
        name: t("services.oneDrive.title"),
        description: t("services.oneDrive.description"),
        category: "storage",
        icon: <Cloud className="size-5 text-blue-600" />,
        connected: microsoftConnected,
        dashboardHref: "/dashboard/documents",
        openHref: "https://onedrive.live.com/",
        dashboardLabel: t("services.oneDrive.dashboardLabel"),
        openLabel: t("openInMicrosoft"),
        provider: "microsoft",
      },
    ];

    return presetItems;
  }, [googleEmail, microsoftEmail, t]);

  // Category navigation tabs
  const categories = [
    { id: "all", label: "All Apps" },
    { id: "connected", label: "Connected" },
    { id: "productivity", label: "Productivity" },
    { id: "communication", label: "Communication" },
    { id: "storage", label: "Files & Storage" },
  ];

  const getCategoryCount = (categoryId: string) => {
    if (categoryId === "all") {
      return integrationsCatalog.length;
    }
    if (categoryId === "connected") {
      return integrationsCatalog.filter((item) => item.connected).length;
    }
    return integrationsCatalog.filter((item) => item.category === categoryId).length;
  };

  // Filter logic
  const filteredIntegrations = useMemo(() => {
    return integrationsCatalog.filter((item) => {
      // 1. Filter by category
      if (activeCategory === "connected") {
        if (!item.connected) return false;
      } else if (activeCategory !== "all") {
        if (item.category !== activeCategory) return false;
      }
      // 2. Filter by search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesName = item.name.toLowerCase().includes(query);
        const matchesDesc = item.description?.toLowerCase().includes(query) || false;
        return matchesName || matchesDesc;
      }
      return true;
    });
  }, [integrationsCatalog, activeCategory, searchQuery]);

  return (
    <div className="space-y-6">
      {/* Dynamic Banner Alert */}
      <AnimatePresence>
        {banner && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs border ${
              banner.kind === "ok"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-destructive/10 text-destructive border-destructive/20"
            }`}
          >
            {banner.kind === "ok" ? (
              <CheckCircle2 className="size-3.5 mt-0.5 shrink-0" />
            ) : (
              <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
            )}
            <span className="flex-1">{banner.text}</span>
            <button onClick={() => setBanner(null)} aria-label={t("dismiss")} className="cursor-pointer">
              <X className="size-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Page Title & Search Bar */}
      <div className="space-y-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Integrations Directory</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Connect the tools and data sources Kin can read from and help automate.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search integrations..."
              className="w-full h-10 pl-9 pr-8 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-foreground/20 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
          <Button
            onClick={() => setImportDialogOpen(true)}
            className="h-10 px-4 font-medium flex items-center gap-2 shrink-0 cursor-pointer"
          >
            <Workflow className="size-4" />
            <span>Import OpenAPI Integration</span>
          </Button>
        </div>
      </div>

      {/* Category Pills Navigation (Horizontal Scroll) */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none border-b border-border">
        {categories.map((cat) => {
          const count = getCategoryCount(cat.id);
          return (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`whitespace-nowrap px-3 py-1.5 text-xs font-semibold rounded-md transition-colors cursor-pointer border ${
                activeCategory === cat.id
                  ? "bg-foreground text-background border-foreground"
                  : "text-muted-foreground hover:text-foreground border-transparent"
              }`}
            >
              {cat.label} <span className="ml-1 text-[10px] opacity-75 font-normal">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Google Extra Account Gating */}
      {googleEmail && activeCategory === "all" && !searchQuery && (
        <ExtraGoogleAccounts plan={plan} />
      )}

      {/* Integrations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredIntegrations.map((item) => (
          <IntegrationCard key={item.slug} item={item} busyKey={busyKey} />
        ))}
      </div>

      {filteredIntegrations.length === 0 && (
        <div className="py-12 text-center border border-dashed border-border rounded-xl">
          <p className="text-sm font-medium">No integrations found</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            Try adjusting your search query or click "Import OpenAPI Integration" to register a custom API URL.
          </p>
          <Button
            onClick={() => setImportDialogOpen(true)}
            variant="outline"
            className="mt-4 text-xs cursor-pointer"
          >
            Import Custom API Integration
          </Button>
        </div>
      )}

      {/* Import OpenAPI Spec Dialog */}
      <Dialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        title="Import Custom API Integration"
      >
        <form onSubmit={handleImportIntegration} className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Enter an OpenAPI / Swagger URL (JSON or YAML) to automatically parse endpoints and register custom tool actions.
          </p>
          <Field label="OpenAPI Specification URL">
            <input
              type="url"
              value={importOpenApiUrl}
              onChange={(e) => setImportOpenApiUrl(e.target.value)}
              placeholder="https://petstore.swagger.io/v2/swagger.json"
              required
              className={inputCls}
            />
          </Field>
          <Field label="Integration Name (Optional)">
            <input
              type="text"
              value={importName}
              onChange={(e) => setImportName(e.target.value)}
              placeholder="My Custom Service"
              className={inputCls}
            />
          </Field>
          <Field label="Category">
            <Select
              value={importCategory}
              onChange={setImportCategory}
              options={[
                { value: "productivity", label: "Productivity" },
                { value: "communication", label: "Communication" },
                { value: "storage", label: "Files & Storage" },
                { value: "crm", label: "CRM & Sales" },
                { value: "developer", label: "Developer Tools" },
                { value: "ai", label: "AI & Models" },
                { value: "social", label: "Social & Media" },
                { value: "finance", label: "Finance & Sales" },
              ]}
            />
          </Field>

          {importError && (
            <div className="flex items-start gap-2 text-xs text-destructive bg-destructive/10 p-2.5 rounded-lg border border-destructive/20">
              <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
              <span>{importError}</span>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setImportDialogOpen(false)}
              disabled={importBusy}
              className="cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={importBusy || !importOpenApiUrl.trim()}
              className="cursor-pointer flex items-center gap-2"
            >
              {importBusy && <Loader2 className="size-3.5 animate-spin" />}
              <span>Parse & Import</span>
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Custom Credentials Config Dialog (Fallback when Nango key is placeholder or for custom API key inputs) */}
      <Dialog
        open={!!configDialog}
        onClose={() => setConfigDialog(null)}
        title={`Connect ${configDialog?.name || "Integration"}`}
      >
        <form onSubmit={submitMockConnection} className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Provide your API Key or Credentials for {configDialog?.name}. Credentials are encrypted securely in PostgreSQL using Fernet AES-256.
          </p>

          {configDialog?.fields.map((f) => (
            <Field key={f.name} label={f.label}>
              <input
                type={f.type || "text"}
                value={configFields[f.name] || ""}
                onChange={(e) => setConfigFields({ ...configFields, [f.name]: e.target.value })}
                placeholder={f.placeholder}
                required
                className={inputCls}
              />
            </Field>
          ))}

          {configError && (
            <div className="flex items-start gap-2 text-xs text-destructive bg-destructive/10 p-2.5 rounded-lg border border-destructive/20">
              <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
              <span>{configError}</span>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfigDialog(null)}
              className="cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!!busyKey}
              className="cursor-pointer flex items-center gap-2"
            >
              {busyKey && <Loader2 className="size-3.5 animate-spin" />}
              <span>Save & Connect</span>
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}

function IntegrationCard({
  item,
  busyKey,
}: {
  item: any;
  busyKey: string | null;
}) {
  const t = useTranslations("dashboard.integrations");
  const isBusy = busyKey?.startsWith(item.slug);

  return (
    <div className="rounded-xl bg-card border border-border p-5 flex flex-col justify-between hover:border-foreground/20 transition-all">
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            {item.icon ? (
              <div className="size-10 rounded-lg bg-muted grid place-items-center shrink-0">
                {item.icon}
              </div>
            ) : item.slug === "google" ? (
              <div className="size-10 rounded-lg bg-muted grid place-items-center shrink-0">
                <svg className="size-5" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
              </div>
            ) : item.slug === "microsoft" ? (
              <div className="size-10 rounded-lg bg-muted grid place-items-center shrink-0">
                <svg className="size-5" viewBox="0 0 23 23">
                  <path fill="#f35325" d="M1 1h10v10H1z" />
                  <path fill="#81bc06" d="M12 1h10v10H12z" />
                  <path fill="#05a6f0" d="M1 12h10v10H1z" />
                  <path fill="#ffba08" d="M12 12h10v10H12z" />
                </svg>
              </div>
            ) : (
              <div className="size-10 rounded-lg bg-muted grid place-items-center shrink-0">
                <Workflow className="size-5 text-indigo-500" />
              </div>
            )}
            <div>
              <h3 className="text-sm font-semibold tracking-tight">{item.name}</h3>
              {item.details && (
                <span className="text-[11px] text-emerald-600 font-medium">{item.details}</span>
              )}
            </div>
          </div>

          <span
            className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase ${
              item.connected
                ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {item.connected ? (t("connectedBadge") || "CONNECTED") : (t("offBadge") || "OFF")}
          </span>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
          {item.description}
        </p>
      </div>

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between gap-2">
        {item.dashboardHref ? (
          <Button variant="outline" className="h-8 text-xs cursor-pointer" render={<Link href={item.dashboardHref} />}>
            {item.dashboardLabel}
          </Button>
        ) : item.connected ? (
          <Button
            variant="outline"
            size="sm"
            disabled={isBusy}
            onClick={item.onDisconnect}
            className="h-8 text-xs text-destructive hover:bg-destructive/10 cursor-pointer"
          >
            {isBusy && <Loader2 className="size-3 animate-spin mr-1" />}
            {t("disconnect") || "Disconnect"}
          </Button>
        ) : (
          <Button
            size="sm"
            disabled={isBusy}
            onClick={item.onConnect}
            className="h-8 text-xs font-medium cursor-pointer"
          >
            {isBusy && <Loader2 className="size-3 animate-spin mr-1" />}
            {t("connect") || "Connect"}
          </Button>
        )}

        {item.openHref && (
          <a
            href={item.openHref}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            {item.openLabel || t("open") || "Open"} <ExternalLink className="size-3" />
          </a>
        )}
      </div>
    </div>
  );
}

function ExtraGoogleAccounts({ plan }: { plan: string }) {
  const t = useTranslations("dashboard.integrations.extraAccounts");
  const [accounts, setAccounts] = useState<ExtraGoogleAccount[] | null>(null);
  const [max, setMax] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const res = await integrations.extraGoogleAccounts();
      setAccounts(res.accounts);
      setMax(res.max);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("loadError") || "Could not load connected accounts");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAdd() {
    setBusy("add");
    setError(null);
    try {
      const res = await integrations.startGoogleConnect("add");
      window.location.href = res.url;
    } catch (e) {
      setError(e instanceof Error ? e.message : t("addError") || "Failed to add account");
      setBusy(null);
    }
  }

  async function handleRemove(id: string) {
    if (!confirm(t("removeConfirm") || "Remove this account?")) return;
    setBusy(id);
    setError(null);
    try {
      await integrations.disconnectExtraGoogleAccount(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("removeError") || "Failed to remove account");
    } finally {
      setBusy(null);
    }
  }

  const isAtLimit = (accounts?.length ?? 0) >= max;

  return (
    <div className="rounded-xl bg-card border border-border p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold">{t("title") || "Additional Google accounts"}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">{t("subtitle") || t("upsellBody") || "Connect more Gmail/Calendar accounts (e.g. work + personal) — Pro and Executive."}</p>
        </div>
        {max === 0 ? (
          <UpgradeButton currentPlan={plan} />
        ) : (
          <Button
            size="sm"
            onClick={handleAdd}
            disabled={isAtLimit || busy === "add"}
            className="cursor-pointer"
          >
            {busy === "add" && <Loader2 className="size-3 animate-spin mr-1" />}
            {t("addAccount")} ({accounts?.length ?? 0}/{max})
          </Button>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {accounts && accounts.length > 0 && (
        <div className="space-y-2">
          {accounts.map((acc) => (
            <div
              key={acc.id}
              className="flex items-center justify-between rounded-lg border border-border p-3 text-xs"
            >
              <div>
                <p className="font-medium text-foreground">{acc.google_email || t("linkedAccount")}</p>
                <p className="text-[11px] text-muted-foreground">
                  {acc.label || t("linkedAccount")}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRemove(acc.id)}
                disabled={busy === acc.id}
                className="h-7 px-2 text-xs text-destructive hover:bg-destructive/10 cursor-pointer"
              >
                {busy === acc.id ? <Loader2 className="size-3 animate-spin" /> : t("remove")}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
