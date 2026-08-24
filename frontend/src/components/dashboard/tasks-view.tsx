"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckSquare,
  Plus,
  Trash2,
  Pencil,
  Loader2,
  CheckCircle2,
  Circle,
  CircleDashed,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, Field, inputCls, textareaCls } from "./dialog";
import { Select } from "@/components/ui/select";
import { DatePicker } from "@/components/ui/date-picker";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";

import { integrations, type Task } from "@/lib/backend";

const STATUS_OPTS: Task["status"][] = ["todo", "in_progress", "done"];
const PRIORITY_OPTS: Task["priority"][] = ["low", "medium", "high"];

const STATUS_ICON: Record<Task["status"], typeof Circle> = {
  todo: Circle,
  in_progress: CircleDashed,
  done: CheckCircle2,
};

const STATUS_TONE: Record<Task["status"], string> = {
  todo: "text-muted-foreground",
  in_progress: "text-blue-600",
  done: "text-emerald-600",
};

const PRIORITY_TONE: Record<Task["priority"], string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-amber-50 text-amber-700",
  high: "bg-orange-50 text-orange-700",
};

type UnifiedTask = Task & {
  source: "kin" | "google" | "microsoft";
  external_id?: string;
  list_id?: string;
};

function SourceIcon({ source, label }: { source: UnifiedTask["source"]; label: string }) {
  if (source === "google") {
    return (
      <span className="text-[9px] px-1 py-0.5 rounded bg-red-50 text-red-600 font-bold uppercase tracking-tighter">
        G
      </span>
    );
  }
  if (source === "microsoft") {
    return (
      <span className="text-[9px] px-1 py-0.5 rounded bg-blue-50 text-blue-600 font-bold uppercase tracking-tighter">
        MS
      </span>
    );
  }
  return (
    <span className="text-[9px] px-1 py-0.5 rounded bg-orange-50 text-orange-600 font-bold uppercase tracking-tighter">
      {label}
    </span>
  );
}

export function TasksView({ initial, userId }: { initial: Task[]; userId: string }) {
  const t = useTranslations("dashboard.tasks");
  const [tasks, setTasks] = useState<UnifiedTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState<"all" | Task["status"]>("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | UnifiedTask["source"]>("all");
  const [connected, setConnected] = useState({ google: false, microsoft: false });
  const supabase = createClient();

  async function load(isInitial = false) {
    if (isInitial) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await integrations.tasks();
      setTasks(res.tasks);
      setConnected(res.connected);
    } catch (e) {
      console.error("Failed to load tasks", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = tasks.filter((t) => {
    const statusMatch = filter === "all" ? true : t.status === filter;
    const sourceMatch = sourceFilter === "all" ? true : t.source === sourceFilter;
    return statusMatch && sourceMatch;
  });

  const cycle = (task: Task): Task["status"] => {
    if (task.status === "todo") return "in_progress";
    if (task.status === "in_progress") return "done";
    return "todo";
  };

  // Google Tasks and Microsoft ToDo only have a done/not-done concept on
  // the provider side (no "in progress" state to round-trip), so external
  // tasks toggle between todo and done rather than cycling through all three.
  const nextStatusFor = (task: UnifiedTask): Task["status"] =>
    task.source === "kin" ? cycle(task) : task.status === "done" ? "todo" : "done";

  async function toggle(task: UnifiedTask) {
    const next = nextStatusFor(task);
    const prev = tasks;
    setTasks((tt) => tt.map((x) => (x.id === task.id ? { ...x, status: next } : x)));

    if (task.source === "kin") {
      const { error } = await supabase
        .from("tasks")
        .update({ status: next })
        .eq("id", task.id.replace("kin-", ""));
      if (error) load();
      return;
    }

    if (!task.external_id) {
      setTasks(prev);
      return;
    }
    try {
      await integrations.toggleExternalTask(
        task.source,
        task.external_id,
        next === "done",
        task.list_id,
      );
    } catch (e) {
      console.error("Failed to toggle external task", e);
      setTasks(prev);
    }
  }

  async function remove(task: UnifiedTask) {
    if (task.source !== "kin") return;
    if (!confirm(t("deleteConfirm", { title: task.title }))) return;
    const prev = tasks;
    setTasks((tt) => tt.filter((x) => x.id !== task.id));
    const { error } = await supabase.from("tasks").delete().eq("id", task.id);
    if (error) setTasks(prev);
  }

  async function save(values: Omit<Task, "id" | "updated_at">, editingId?: string) {
    if (editingId) {
      const { data, error } = await supabase
        .from("tasks")
        .update(values)
        .eq("id", editingId)
        .select("*")
        .single();
      if (!error && data) {
        load();
      }
      return;
    }
    const { data, error } = await supabase
      .from("tasks")
      .insert({ ...values, user_id: userId })
      .select("*")
      .single();
    if (!error && data) load();
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-12 grid place-items-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
              {(["all", ...STATUS_OPTS] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    "px-3 py-1 text-xs font-medium rounded-md transition-colors capitalize",
                    filter === f
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {f === "all" ? t("all") : t(`status.${f}` as "status.todo")}
                </button>
              ))}
            </div>

            <div className="inline-flex rounded-lg border border-border bg-card p-0.5">
              {(["all", "kin", "google", "microsoft"] as const).map((s) => {
                if (s === "google" && !connected.google) return null;
                if (s === "microsoft" && !connected.microsoft) return null;
                return (
                  <button
                    key={s}
                    onClick={() => setSourceFilter(s)}
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-md transition-colors capitalize",
                      sourceFilter === s
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {s === "all" ? t("all") : t(`sources.${s}` as "sources.kin")}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => load()}
              disabled={refreshing}
              className="cursor-pointer"
            >
              <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </Button>
            <Button onClick={() => setCreating(true)} className="h-9 px-3 cursor-pointer">
              <Plus className="size-3.5" />
              {t("newTask")}
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          {visible.length === 0 ? (
            <div className="p-12 text-center">
              <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
                <CheckSquare className="size-5" />
              </div>
              <h3 className="mt-4 text-sm font-semibold">
                {filter === "all"
                  ? t("noTasksYet")
                  : t("noStatusTasks", { status: t(`status.${filter}` as "status.todo") })}
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("emptyHint")}
              </p>
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {visible.map((task) => {
                const Icon = STATUS_ICON[task.status];
                return (
                  <motion.div
                    key={task.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex items-start gap-3 p-4 hover:bg-muted/40 transition-colors group"
                  >
                    <button
                      onClick={() => toggle(task)}
                      className={cn(
                        "mt-0.5 shrink-0 transition-transform active:scale-90 cursor-pointer",
                        STATUS_TONE[task.status],
                      )}
                      aria-label={t("markStatus", { status: t(`status.${nextStatusFor(task)}` as "status.todo") })}
                    >
                      <Icon className="size-5" />
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={cn(
                            "text-sm font-medium",
                            task.status === "done" && "line-through text-muted-foreground",
                          )}
                        >
                          {task.title}
                        </span>
                        <SourceIcon source={task.source} label={t("sources.kin")} />
                        <span
                          className={cn(
                            "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider",
                            PRIORITY_TONE[task.priority],
                          )}
                        >
                          {t(`priority.${task.priority}` as "priority.low")}
                        </span>
                        {task.due_date && (
                          <span className="text-[11px] text-muted-foreground">
                            {t("due", {
                              date: new Date(task.due_date).toLocaleDateString(undefined, {
                                month: "short",
                                day: "numeric",
                              }),
                            })}
                          </span>
                        )}
                      </div>
                      {task.description && (
                        <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                          {task.description}
                        </p>
                      )}
                    </div>
                    {task.source === "kin" && (
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setEditing(task)}
                          aria-label={t("edit")}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => remove(task)}
                          aria-label={t("delete")}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}
        </div>
      </div>

      <TaskDialog
        open={creating || !!editing}
        editing={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
        onSave={(v) => save(v, editing?.id)}
      />
    </>
  );
}

function TaskDialog({
  open,
  editing,
  onClose,
  onSave,
}: {
  open: boolean;
  editing: Task | null;
  onClose: () => void;
  onSave: (v: Omit<Task, "id" | "updated_at">) => Promise<void>;
}) {
  const t = useTranslations("dashboard.tasks");
  const td = useTranslations("dashboard.tasks.dialog");
  const [title, setTitle] = useState(editing?.title ?? "");
  const [description, setDescription] = useState(editing?.description ?? "");
  const [status, setStatus] = useState<Task["status"]>(editing?.status ?? "todo");
  const [priority, setPriority] = useState<Task["priority"]>(editing?.priority ?? "medium");
  const [dueDate, setDueDate] = useState(editing?.due_date ?? "");
  const [saving, setSaving] = useState(false);

  const key = editing?.id ?? "new";
  useEffectOnKey(key, () => {
    setTitle(editing?.title ?? "");
    setDescription(editing?.description ?? "");
    setStatus(editing?.status ?? "todo");
    setPriority(editing?.priority ?? "medium");
    setDueDate(editing?.due_date ?? "");
  });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    try {
      await onSave({
        title: title.trim(),
        description: description.trim() || null,
        status,
        priority,
        due_date: dueDate || null,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing ? td("editTitle") : td("newTitle")}
      description={td("description")}
    >
      <form onSubmit={submit}>
        <Field label={td("titleLabel")}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            autoFocus
            className={inputCls}
            placeholder={td("titlePlaceholder")}
          />
        </Field>
        <Field label={td("descriptionLabel")}>
          <textarea
            value={description ?? ""}
            onChange={(e) => setDescription(e.target.value)}
            className={textareaCls}
            placeholder={td("descriptionPlaceholder")}
          />
        </Field>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={td("statusLabel")}>
            <Select
              value={status}
              onChange={(val) => setStatus(val as Task["status"])}
              options={STATUS_OPTS.map((s) => ({
                value: s,
                label: t(`status.${s}` as "status.todo"),
              }))}
            />
          </Field>
          <Field label={td("priorityLabel")}>
            <Select
              value={priority}
              onChange={(val) => setPriority(val as Task["priority"])}
              options={PRIORITY_OPTS.map((p) => ({
                value: p,
                label: t(`priority.${p}` as "priority.low"),
              }))}
            />
          </Field>
          <Field label={td("dueDateLabel")}>
            <DatePicker
              value={dueDate}
              onChange={setDueDate}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} className="cursor-pointer">
            {td("cancel")}
          </Button>
          <Button type="submit" disabled={!title.trim() || saving} className="cursor-pointer">
            {saving && <Loader2 className="size-3.5 animate-spin" />}
            {editing ? td("saveChanges") : td("createTask")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

function useEffectOnKey(key: string, fn: () => void) {
  useEffect(fn, [key]);
}
