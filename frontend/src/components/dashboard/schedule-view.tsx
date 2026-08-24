"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  Clock,
  Trash2,
  Play,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Calendar,
  Send,
  Globe,
  Settings,
  AlertTriangle,
  Info,
  Mail,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/markdown";
import { Dialog, DialogFooter, Field, inputCls, textareaCls } from "./dialog";
import { SearchSelect } from "@/components/ui/select";
import { scheduleApi, type ScheduledTask } from "@/lib/backend";
import { cn } from "@/lib/utils";
import { listTimezones, detectTimezone, formatTimezone, offsetLabel } from "@/lib/timezones";

function parseCronToTime(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length >= 2) {
    const min = parseInt(parts[0], 10);
    const hour = parseInt(parts[1], 10);
    if (!isNaN(min) && !isNaN(hour) && min >= 0 && min < 60 && hour >= 0 && hour < 24) {
      return `${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
    }
  }
  return "12:00";
}

function formatTimeToCron(time: string): string {
  const [hourStr, minStr] = time.split(":");
  const hour = parseInt(hourStr || "12", 10);
  const min = parseInt(minStr || "0", 10);
  return `${min} ${hour} * * *`;
}

export function ScheduleView() {
  const t = useTranslations("dashboard.schedule");
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [testingTaskId, setTestingTaskId] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ kind: "ok" | "err" | "info"; text: string } | null>(null);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null);
  const [editName, setEditName] = useState("");
  const [editPrompt, setEditPrompt] = useState("");
  const [editChannel, setEditChannel] = useState<"web" | "email">("web");
  const [editCron, setEditCron] = useState("");
  const [editTime, setEditTime] = useState("12:00");
  const [editTimezone, setEditTimezone] = useState("");
  const [showAdvancedCron, setShowAdvancedCron] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const promptTextareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = promptTextareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    }
  }, [editPrompt, isEditDialogOpen]);

  const [testResult, setTestResult] = useState<{ taskName: string; reply: string; detail?: string } | null>(null);

  const timezoneOptions = useMemo(() => {
    return listTimezones().map((tz) => ({
      value: tz,
      label: formatTimezone(tz),
      trailing: offsetLabel(tz),
    }));
  }, []);

  const channelOptions = useMemo(() => {
    return [
      { value: "web", label: t("channels.web"), leading: <Send className="size-3.5 text-indigo-500" /> },
      { value: "email", label: t("channels.email"), leading: <Mail className="size-3.5 text-emerald-500" /> },
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeTasks = useMemo(() => {
    return tasks.filter((task) => task.is_active);
  }, [tasks]);

  useEffect(() => {
    fetchTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchTasks() {
    setLoading(true);
    try {
      const data = await scheduleApi.list();
      setTasks(data);
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("loadError") });
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveDialogEdit() {
    if (!editingTask) return;
    if (!editName.trim()) {
      setEditError(t("nameRequired"));
      return;
    }
    if (!editPrompt.trim()) {
      setEditError(t("promptRequired"));
      return;
    }
    if (!editCron.trim()) {
      setEditError(t("cronRequired"));
      return;
    }

    setBusyTaskId(editingTask.id);
    setEditError(null);
    try {
      const updated = await scheduleApi.update(editingTask.id, {
        name: editName.trim(),
        prompt: editPrompt.trim(),
        channel: editChannel,
        cron_expression: editCron.trim(),
        timezone: editTimezone,
      });
      setTasks((prev) => prev.map((x) => (x.id === editingTask.id ? updated : x)));
      setIsEditDialogOpen(false);
      setEditingTask(null);
      setBanner({ kind: "ok", text: t("updated", { name: updated.name }) });
    } catch (e) {
      setEditError(e instanceof Error ? e.message : t("updateFailed"));
    } finally {
      setBusyTaskId(null);
    }
  }

  async function handleToggleActive(id: string, currentVal: boolean) {
    setBusyTaskId(id);
    setBanner(null);
    try {
      const updated = await scheduleApi.update(id, { is_active: !currentVal });
      setTasks((prev) => prev.map((x) => (x.id === id ? updated : x)));
      setBanner({
        kind: "ok",
        text: t("toggled", { name: updated.name, state: updated.is_active ? t("enabled") : t("disabled") }),
      });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("toggleFailed") });
    } finally {
      setBusyTaskId(null);
    }
  }

  async function handleTestTask(id: string, name: string) {
    setTestingTaskId(id);
    setBusyTaskId(id);
    setBanner(null);
    try {
      const res = await scheduleApi.test(id);
      setTestResult({
        taskName: name,
        reply: res.reply,
        detail: res.detail,
      });
      const refreshed = await scheduleApi.list();
      setTasks(refreshed);
    } catch (e) {
      setBanner({
        kind: "err",
        text: e instanceof Error ? e.message : t("testFailed"),
      });
    } finally {
      setTestingTaskId(null);
      setBusyTaskId(null);
    }
  }

  async function handleDeleteTask(id: string, name: string) {
    if (!confirm(t("deleteConfirm", { name }))) {
      return;
    }
    setBusyTaskId(id);
    setBanner(null);
    try {
      await scheduleApi.delete(id);
      setTasks((prev) => prev.filter((x) => x.id !== id));
      setBanner({ kind: "ok", text: t("deleted", { name }) });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("deleteFailed") });
    } finally {
      setBusyTaskId(null);
    }
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
                : banner.kind === "info"
                ? "bg-blue-50/80 border-blue-100 text-blue-800 dark:bg-blue-950/20 dark:border-blue-900/55 dark:text-blue-300"
                : "bg-destructive/10 border-destructive/25 text-destructive dark:border-destructive/40"
            }`}
          >
            {banner.kind === "ok" ? (
              <CheckCircle2 className="size-4 mt-0.5 shrink-0" />
            ) : banner.kind === "info" ? (
              <Info className="size-4 mt-0.5 shrink-0" />
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
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        </div>
      ) : activeTasks.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border p-12 text-center max-w-lg mx-auto">
          <div className="size-12 rounded-2xl bg-muted grid place-items-center mx-auto mb-4 text-muted-foreground">
            <Clock className="size-6" />
          </div>
          <h3 className="text-sm font-semibold">{t("empty.title")}</h3>
          <p className="mt-2 text-xs text-muted-foreground max-w-sm mx-auto">
            {t("empty.body")}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {activeTasks.map((task) => {
            const isBusy = busyTaskId === task.id;
            const isTesting = testingTaskId === task.id;
            const lastRunFormatted = task.last_run_at
              ? new Date(task.last_run_at).toLocaleString()
              : t("neverRun");

            return (
              <div
                key={task.id}
                className="rounded-2xl border border-border bg-card overflow-hidden transition-all opacity-100"
              >
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1 min-w-0">
                    <div className="size-10 rounded-xl bg-violet-50 dark:bg-violet-950/30 border border-violet-100/50 dark:border-violet-900/50 grid place-items-center shrink-0">
                      <Clock className="size-5 text-violet-600 dark:text-violet-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <h4 className="text-sm font-semibold tracking-tight text-foreground">
                          {task.name}
                        </h4>
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                          task.channel === "email"
                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400 border-emerald-100 dark:border-emerald-900/30"
                            : "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/20 dark:text-indigo-400 border-indigo-100 dark:border-indigo-900/30"
                        }`}>
                          {task.channel === "email" ? (
                            <Mail className="size-2.5" />
                          ) : (
                            <Send className="size-2.5" />
                          )}
                          {task.channel === "email" ? t("channels.email") : t("channels.web")}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-1 italic">
                        &quot;{task.prompt}&quot;
                      </p>

                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                        <span className="font-mono bg-muted px-1.5 py-0.5 rounded text-[11px] font-semibold text-foreground/80">
                          {task.cron_expression}
                        </span>
                        <span className="flex items-center gap-1">
                          <Globe className="size-3.5" />
                          {formatTimezone(task.timezone)} ({offsetLabel(task.timezone)})
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="size-3.5" />
                          {t("lastRun", { when: lastRunFormatted })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 self-end md:self-center">
                    <button
                      onClick={() => handleToggleActive(task.id, task.is_active)}
                      disabled={isBusy}
                      aria-label={task.is_active ? t("disableSchedule") : t("enableSchedule")}
                      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-foreground/20 ${
                        task.is_active ? "bg-violet-600" : "bg-muted-foreground/30"
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block size-5 transform rounded-full bg-background shadow ring-0 transition duration-200 ease-in-out ${
                          task.is_active ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditingTask(task);
                        setEditName(task.name);
                        setEditPrompt(task.prompt);
                        setEditChannel(task.channel);
                        setEditCron(task.cron_expression);
                        setEditTimezone(task.timezone);

                        const isDaily = /^\d+\s+\d+\s+\*\s+\*\s+\*$/.test(task.cron_expression.trim());
                        setEditTime(parseCronToTime(task.cron_expression));
                        setShowAdvancedCron(!isDaily);

                        setEditError(null);
                        setIsEditDialogOpen(true);
                      }}
                      disabled={isBusy}
                      className="cursor-pointer gap-1.5"
                    >
                      <Settings className="size-3.5" />
                      {t("editTask")}
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleTestTask(task.id, task.name)}
                      disabled={isBusy}
                      className="cursor-pointer gap-1.5 min-w-[95px] justify-center"
                    >
                      {isTesting ? (
                        <Loader2 className="size-3.5 animate-spin mr-1 shrink-0" />
                      ) : (
                        <Play className="size-3.5 fill-current mr-1 shrink-0" />
                      )}
                      {isTesting ? t("testing") : t("testRun")}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteTask(task.id, task.name)}
                      disabled={isBusy}
                      className="cursor-pointer text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog
        open={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        title={t("editDialog.title")}
        description={t("editDialog.description")}
        size="md"
      >
        <div className="max-h-[60vh] overflow-y-auto pr-2 -mr-2 space-y-4 py-2">
          <Field label={t("editDialog.nameLabel")}>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder={t("editDialog.namePlaceholder")}
              disabled={busyTaskId !== null}
              className={inputCls}
            />
          </Field>

          <Field label={t("editDialog.promptLabel")}>
            <textarea
              ref={promptTextareaRef}
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              placeholder={t("editDialog.promptPlaceholder")}
              disabled={busyTaskId !== null}
              className={cn(textareaCls, "resize-none overflow-hidden")}
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label={t("editDialog.channelLabel")}>
              <SearchSelect
                value={editChannel}
                onChange={(val) => setEditChannel(val as "web" | "email")}
                options={channelOptions}
                disabled={busyTaskId !== null}
                className="w-full"
              />
            </Field>

            <Field label={t("editDialog.timeLabel")} hint={t("editDialog.timeHint")}>
              <input
                type="time"
                value={editTime}
                onChange={(e) => {
                  setEditTime(e.target.value);
                  setEditCron(formatTimeToCron(e.target.value));
                }}
                disabled={busyTaskId !== null}
                className={inputCls}
              />
            </Field>
          </div>

          <Field label={t("editDialog.timezoneLabel")} hint={t("editDialog.timezoneHint")}>
            <SearchSelect
              value={editTimezone}
              onChange={setEditTimezone}
              options={timezoneOptions}
              disabled={busyTaskId !== null}
              placeholder={t("editDialog.timezonePlaceholder")}
              className="w-full"
            />
          </Field>

          <div className="pt-1">
            <button
              type="button"
              onClick={() => setShowAdvancedCron(!showAdvancedCron)}
              className="text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300 flex items-center gap-1 cursor-pointer"
            >
              {showAdvancedCron ? t("editDialog.hideCron") : t("editDialog.showCron")}
            </button>

            {showAdvancedCron && (
              <div className="mt-3 p-3.5 bg-muted/40 border border-border rounded-xl space-y-2 animate-in fade-in duration-200">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                  {t("editDialog.cronLabel")}
                </label>
                <input
                  value={editCron}
                  onChange={(e) => setEditCron(e.target.value)}
                  placeholder={t("editDialog.cronPlaceholder")}
                  disabled={busyTaskId !== null}
                  className={cn(inputCls, "font-mono text-xs")}
                />
                <p className="text-[10px] text-muted-foreground leading-normal">
                  {t("editDialog.cronHint")}
                </p>
              </div>
            )}
          </div>

          {editError && (
            <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-xl p-3 flex items-start gap-2 animate-in fade-in duration-200">
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span className="font-medium">{editError}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setIsEditDialogOpen(false)}
            disabled={busyTaskId !== null}
            className="cursor-pointer"
          >
            {t("editDialog.cancel")}
          </Button>
          <Button
            onClick={handleSaveDialogEdit}
            disabled={busyTaskId !== null}
            className="cursor-pointer min-w-[80px]"
          >
            {busyTaskId === editingTask?.id && (
              <Loader2 className="size-3.5 animate-spin mr-1.5" />
            )}
            {t("editDialog.saveChanges")}
          </Button>
        </DialogFooter>
      </Dialog>

      <Dialog
        open={testResult !== null}
        onClose={() => setTestResult(null)}
        title={t("resultDialog.title", { name: testResult?.taskName ?? "" })}
        description={t("resultDialog.description")}
        size="lg"
      >
        <div className="space-y-4">
          {testResult?.detail && (
            <div className="text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2 bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40 rounded-xl p-3">
              <AlertTriangle className="size-4 shrink-0 mt-0.5" />
              <span>{testResult.detail}</span>
            </div>
          )}

          <div className="bg-muted/40 border border-border rounded-xl p-5 max-h-[400px] overflow-y-auto">
            <Markdown>{testResult?.reply || t("resultDialog.noReply")}</Markdown>
          </div>

          <DialogFooter>
            <Button onClick={() => setTestResult(null)} className="cursor-pointer">
              {t("resultDialog.close")}
            </Button>
          </DialogFooter>
        </div>
      </Dialog>
    </div>
  );
}
