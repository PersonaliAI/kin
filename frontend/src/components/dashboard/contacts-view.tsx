"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  Plus,
  Trash2,
  Pencil,
  Loader2,
  Mail,
  Phone,
  Building2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, Field, inputCls, textareaCls } from "./dialog";
import { createClient } from "@/lib/supabase/client";
import { integrations, googleContactsApi, microsoftContactsApi, type GoogleContact } from "@/lib/backend";
import { cn } from "@/lib/utils";

export type Contact = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  notes: string | null;
  updated_at: string | null;
};

type UnifiedContact = {
  id: string;
  source: "kin" | "google" | "microsoft";
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  notes: string | null;
  resource_name?: string;
};

function initials(name: string) {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function fromKin(c: Contact): UnifiedContact {
  return {
    id: `kin-${c.id}`,
    source: "kin",
    name: c.name,
    email: c.email,
    phone: c.phone,
    company: c.company,
    notes: c.notes,
  };
}

function fromIntegration(c: GoogleContact, noNameFallback: string): UnifiedContact {
  return {
    id: `${c.source || "google"}-${c.resource_name}`,
    source: (c.source as "google" | "microsoft") || "google",
    name: c.name || c.given_name || noNameFallback,
    email: c.emails[0] ?? null,
    phone: c.phones[0] ?? null,
    company: c.company || null,
    notes: c.notes || null,
    resource_name: c.resource_name,
  };
}

export function ContactsView({
  initial,
  userId,
}: {
  initial: Contact[];
  userId: string;
}) {
  const t = useTranslations("dashboard.contacts");
  const [kinContacts, setKinContacts] = useState<Contact[]>(initial);
  const [externalContacts, setExternalContacts] = useState<GoogleContact[]>([]);
  const [connected, setConnected] = useState<{ google: boolean; microsoft: boolean }>({
    google: false,
    microsoft: false,
  });
  const [editing, setEditing] = useState<Contact | null>(null);
  const [creating, setCreating] = useState(false);
  const [q, setQ] = useState("");
  const [source, setSource] = useState<"all" | "kin" | "google" | "microsoft">("all");
  const [loading, setLoading] = useState(true);
  const supabase = createClient();

  async function load() {
    setLoading(true);
    try {
      const res = await integrations.contacts();
      setKinContacts(res.kin);
      setExternalContacts(res.external);
      setConnected(res.connected);
    } catch (e) {
      console.error("Failed to load contacts", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const merged: UnifiedContact[] = useMemo(() => {
    const all: UnifiedContact[] = [
      ...kinContacts.map(fromKin),
      ...(externalContacts ?? []).map((c) => fromIntegration(c, t("noName"))),
    ];
    return all.sort((a, b) => a.name.localeCompare(b.name));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kinContacts, externalContacts]);

  const visible = useMemo(() => {
    return merged.filter((c) => {
      if (source !== "all" && c.source !== source) return false;
      if (!q) return true;
      const qq = q.toLowerCase();
      return (
        c.name.toLowerCase().includes(qq) ||
        (c.email ?? "").toLowerCase().includes(qq) ||
        (c.company ?? "").toLowerCase().includes(qq)
      );
    });
  }, [merged, q, source]);

  async function removeKin(c: Contact) {
    if (!confirm(t("deleteConfirm", { name: c.name }))) return;
    const prev = kinContacts;
    setKinContacts((cc) => cc.filter((x) => x.id !== c.id));
    const { error } = await supabase.from("contacts").delete().eq("id", c.id);
    if (error) setKinContacts(prev);
  }

  async function saveKin(values: Omit<Contact, "id" | "updated_at">, id?: string) {
    if (id) {
      const { data, error } = await supabase
        .from("contacts")
        .update(values)
        .eq("id", id)
        .select("*")
        .single();
      if (!error && data)
        setKinContacts((cc) => cc.map((x) => (x.id === id ? (data as Contact) : x)));
      return;
    }
    const { data, error } = await supabase
      .from("contacts")
      .insert({ ...values, user_id: userId })
      .select("*")
      .single();
    if (!error && data) setKinContacts((cc) => [data as Contact, ...cc]);
  }

  async function saveGoogle(values: Omit<Contact, "id" | "updated_at">) {
    const created = await googleContactsApi.create({
      name: values.name,
      email: values.email,
      phone: values.phone,
      company: values.company,
      notes: values.notes,
    });
    // Refresh external list
    setExternalContacts((prev) => [created, ...(prev ?? [])]);
  }

  async function saveMicrosoft(values: Omit<Contact, "id" | "updated_at">) {
    const created = await microsoftContactsApi.create({
      name: values.name,
      email: values.email,
      phone: values.phone,
      company: values.company,
    });
    setExternalContacts((prev) => [created, ...(prev ?? [])]);
  }

  const sourceTabs: {
    id: "all" | "kin" | "google" | "microsoft";
    count: number;
  }[] = [
    { id: "all", count: merged.length },
    { id: "kin", count: kinContacts.length },
    {
      id: "google",
      count: externalContacts?.filter((c) => c.source === "google").length ?? 0,
    },
    {
      id: "microsoft",
      count: externalContacts?.filter((c) => c.source === "microsoft").length ?? 0,
    },
  ];

  return (
    <>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("searchPlaceholder")}
          className={`${inputCls} max-w-xs`}
        />
        <Button onClick={() => setCreating(true)} className="h-9 px-3 cursor-pointer">
          <Plus className="size-3.5" />
          {t("addContact")}
        </Button>
      </div>

      <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
        {sourceTabs.map((tab) => {
          if (tab.id === "google" && !connected.google) return null;
          if (tab.id === "microsoft" && !connected.microsoft) return null;
          return (
            <button
              key={tab.id}
              onClick={() => setSource(tab.id)}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                source === tab.id
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t(`tabs.${tab.id}`)}
              <span className="ml-1.5 text-[10px] opacity-70">{tab.count}</span>
            </button>
          );
        })}
      </div>

      {(!connected.google || !connected.microsoft) && !loading && (
        <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground flex items-start gap-2">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>
            {!connected.google && !connected.microsoft
              ? t("connectBoth")
              : !connected.google
                ? t("connectGoogle")
                : t("connectMicrosoft")}{" "}
            {t("atIntegrations")}{" "}
            <Link
              href="/dashboard/integrations"
              className="text-foreground underline underline-offset-2"
            >
              {t("integrationsLink")}
            </Link>{" "}
            {t("toSeeMore")}
          </span>
        </div>
      )}

      <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
        {loading && externalContacts.length === 0 ? (
          <div className="p-12 grid place-items-center text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : visible.length === 0 ? (
          <div className="p-12 text-center">
            <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
              <Users className="size-5" />
            </div>
            <h3 className="mt-4 text-sm font-semibold">
              {q ? t("noMatches") : t("noContactsYet")}
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {q ? t("tryDifferentName") : t("addPeopleHint")}
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {visible.map((c) => (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-start gap-3 p-4 hover:bg-muted/40 transition-colors group"
              >
                <span className="size-9 shrink-0 rounded-full bg-foreground text-background grid place-items-center text-xs font-semibold">
                  {initials(c.name) || "?"}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {c.source === "kin" ? (
                      <button
                        onClick={() => {
                          const kin = kinContacts.find((x) => `kin-${x.id}` === c.id);
                          if (kin) setEditing(kin);
                        }}
                        className="text-sm font-medium hover:underline underline-offset-4"
                      >
                        {c.name}
                      </button>
                    ) : (
                      <span className="text-sm font-medium">{c.name}</span>
                    )}
                    <SourcePill source={c.source} />
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                    {c.email && (
                      <a
                        href={`mailto:${c.email}`}
                        className="flex items-center gap-1 hover:text-foreground"
                      >
                        <Mail className="size-3" /> {c.email}
                      </a>
                    )}
                    {c.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="size-3" /> {c.phone}
                      </span>
                    )}
                    {c.company && (
                      <span className="flex items-center gap-1">
                        <Building2 className="size-3" /> {c.company}
                      </span>
                    )}
                  </div>
                  {c.notes && (
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                      {c.notes}
                    </p>
                  )}
                </div>
                {c.source === "kin" && (
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => {
                        const kin = kinContacts.find((x) => `kin-${x.id}` === c.id);
                        if (kin) setEditing(kin);
                      }}
                      aria-label="Edit"
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => {
                        const kin = kinContacts.find((x) => `kin-${x.id}` === c.id);
                        if (kin) removeKin(kin);
                      }}
                      aria-label="Delete"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      <ContactDialog
        open={creating || !!editing}
        editing={editing}
        googleConnected={connected.google}
        microsoftConnected={connected.microsoft}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        onSave={async (v, target) => {
          if (target === "google") await saveGoogle(v);
          else if (target === "microsoft") await saveMicrosoft(v);
          else await saveKin(v, editing?.id);
        }}
      />
    </>
  );
}

function SourcePill({ source }: { source: "kin" | "google" | "microsoft" }) {
  const t = useTranslations("dashboard.contacts.sourcePills");
  if (source === "google") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-red-50 text-red-700">
        {t("google")}
      </span>
    );
  }
  if (source === "microsoft") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-blue-50 text-blue-700">
        {t("microsoft")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-orange-50 text-orange-700">
      {t("kin")}
    </span>
  );
}

function ContactDialog({
  open,
  editing,
  googleConnected,
  microsoftConnected,
  onClose,
  onSave,
}: {
  open: boolean;
  editing: Contact | null;
  googleConnected: boolean;
  microsoftConnected: boolean;
  onClose: () => void;
  onSave: (
    v: Omit<Contact, "id" | "updated_at">,
    target: "kin" | "google" | "microsoft",
  ) => Promise<void>;
}) {
  const t = useTranslations("dashboard.contacts.dialog");
  const [name, setName] = useState(editing?.name ?? "");
  const [email, setEmail] = useState(editing?.email ?? "");
  const [phone, setPhone] = useState(editing?.phone ?? "");
  const [company, setCompany] = useState(editing?.company ?? "");
  const [notes, setNotes] = useState(editing?.notes ?? "");
  const [target, setTarget] = useState<"kin" | "google" | "microsoft">("kin");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setName(editing?.name ?? "");
    setEmail(editing?.email ?? "");
    setPhone(editing?.phone ?? "");
    setCompany(editing?.company ?? "");
    setNotes(editing?.notes ?? "");
    setTarget("kin"); // editing always edits the kin row
    setErr(null);
  }, [editing?.id, open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setErr(null);
    try {
      await onSave(
        {
          name: name.trim(),
          email: email?.trim() || null,
          phone: phone?.trim() || null,
          company: company?.trim() || null,
          notes: notes?.trim() || null,
        },
        target,
      );
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing ? t("editTitle") : t("newTitle")}
      description={editing ? t("editDesc") : t("newDesc")}
    >
      <form onSubmit={submit}>
        {!editing && (googleConnected || microsoftConnected) && (
          <Field label={t("saveTo")}>
            <div className="inline-flex rounded-lg border border-border bg-background p-0.5 flex-wrap">
              <button
                type="button"
                onClick={() => setTarget("kin")}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                  target === "kin"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t("kinLocal")}
              </button>
              {googleConnected && (
                <button
                  type="button"
                  onClick={() => setTarget("google")}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                    target === "google"
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t("googleContacts")}
                </button>
              )}
              {microsoftConnected && (
                <button
                  type="button"
                  onClick={() => setTarget("microsoft")}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                    target === "microsoft"
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t("microsoftContacts")}
                </button>
              )}
            </div>
          </Field>
        )}
        <Field label={t("nameLabel")}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            className={inputCls}
            placeholder={t("namePlaceholder")}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("emailLabel")}>
            <input
              type="email"
              value={email ?? ""}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
              placeholder={t("emailPlaceholder")}
            />
          </Field>
          <Field label={t("phoneLabel")}>
            <input
              value={phone ?? ""}
              onChange={(e) => setPhone(e.target.value)}
              className={inputCls}
              placeholder={t("phonePlaceholder")}
            />
          </Field>
        </div>
        <Field label={t("companyLabel")}>
          <input
            value={company ?? ""}
            onChange={(e) => setCompany(e.target.value)}
            className={inputCls}
            placeholder={t("companyPlaceholder")}
          />
        </Field>
        <Field
          label={t("notesLabel")}
          hint={target === "microsoft" ? t("notesUnsupportedMicrosoft") : undefined}
        >
          <textarea
            value={notes ?? ""}
            onChange={(e) => setNotes(e.target.value)}
            disabled={target === "microsoft"}
            className={cn(textareaCls, target === "microsoft" && "opacity-50")}
            placeholder={t("notesPlaceholder")}
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
          <Button type="submit" disabled={!name.trim() || saving} className="cursor-pointer">
            {saving && <Loader2 className="size-3.5 animate-spin" />}
            {editing
              ? t("saveChanges")
              : target === "google"
                ? t("saveToGoogle")
                : target === "microsoft"
                  ? t("saveToMicrosoft")
                  : t("addToKin")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
