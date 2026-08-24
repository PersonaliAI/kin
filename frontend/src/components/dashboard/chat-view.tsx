"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mic,
  Send,
  Square,
  Sparkles,
  AlertCircle,
  Plus,
  MessageSquare,
  Trash2,
  Loader2,
  Clock,
  Paperclip,
  ChevronDown,
  Brain,
  Search,
  PanelLeftClose,
  Play,
  Pause,
  X,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { sendChat, chatSessions, uploadDocument, flowCredentials, type ChatSession } from "@/lib/backend";
import { Markdown } from "@/components/markdown";
import { createClient } from "@/lib/supabase/client";
import { ModelSelector } from "@/components/dashboard/model-selector";

type Msg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  kind?: "voice" | "text";
  pending?: boolean;
  error?: string;
  thinking?: string;
  audioUrl?: string;
};

type DateGroupKey = "today" | "yesterday" | "previous7Days" | "older";

function groupSessionsByDate(sessions: ChatSession[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const sevenDaysAgo = new Date(startOfToday);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const buckets: Record<DateGroupKey, ChatSession[]> = {
    today: [],
    yesterday: [],
    previous7Days: [],
    older: [],
  };

  for (const s of sessions) {
    const d = new Date(s.last_at);
    if (d >= startOfToday) buckets.today.push(s);
    else if (d >= startOfYesterday) buckets.yesterday.push(s);
    else if (d >= sevenDaysAgo) buckets.previous7Days.push(s);
    else buckets.older.push(s);
  }

  return (Object.keys(buckets) as DateGroupKey[]).map((key) => ({
    key,
    items: buckets[key],
  }));
}

export function ChatView({
  initial,
  initialSessionId,
  voiceFirst,
  initialProvider,
  initialModel,
}: {
  initial: Msg[];
  initialSessionId: string;
  voiceFirst: boolean;
  initialProvider?: string | null;
  initialModel?: string | null;
}) {
  const t = useTranslations("dashboard.chat");
  const [messages, setMessages] = useState<Msg[]>(initial);
  const [sessionId, setSessionId] = useState(initialSessionId);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [draftAttachments, setDraftAttachments] = useState<{ id: string; file: File }[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const [showCmds, setShowCmds] = useState(false);
  const [selectedCmdIndex, setSelectedCmdIndex] = useState(0);

  const COMMANDS = useMemo(
    () => [
      {
        cmd: "/schedule",
        example: t("commands.scheduleExample"),
        desc: t("commands.scheduleDesc"),
      },
    ],
    [t],
  );

  const SUGGESTIONS = useMemo(
    () => [
      t("suggestions.calendar"),
      t("suggestions.emails"),
      t("suggestions.task"),
      t("suggestions.reply"),
    ],
    [t],
  );

  const isCommandQuery = text.startsWith("/") && !text.includes(" ");
  const filteredCommands = useMemo(() => {
    if (!isCommandQuery) return [];
    const query = text.toLowerCase();
    return COMMANDS.filter((c) => c.cmd.toLowerCase().startsWith(query));
  }, [text, isCommandQuery, COMMANDS]);

  const showCommandsDropdown = showCmds && filteredCommands.length > 0;

  const selectCommand = (cmd: string) => {
    setText(cmd + " ");
    setShowCmds(false);
    taRef.current?.focus();
  };

  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const supabase = createClient();
  const [recordingStream, setRecordingStream] = useState<MediaStream | null>(null);

  const refreshSessions = useCallback(() => {
    chatSessions.list().then((res) => setSessions(res.sessions)).catch(() => {});
  }, []);

  useEffect(() => {
    refreshSessions();
    const channel = supabase
      .channel("chat-sessions")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "messages" },
        () => refreshSessions(),
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadSession(id: string) {
    if (id === sessionId) return;
    setLoadingHistory(true);
    setSessionId(id);
    setShowHistory(false);
    try {
      const { data: rows } = await supabase
        .from("messages")
        .select("id, role, content, audio_url, created_at")
        .eq("session_id", id)
        .order("created_at", { ascending: true })
        .limit(100);
      setMessages(
        (rows ?? []).map((r) => ({
          id: r.id,
          role: r.role,
          content: r.content || "",
          ...(r.audio_url ? { kind: "voice" as const, audioUrl: r.audio_url } : {}),
        })),
      );
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingHistory(false);
    }
  }

  function startNewChat() {
    const newId = `web-${crypto.randomUUID()}`;
    setSessionId(newId);
    setMessages([]);
    setShowHistory(false);
  }

  async function deleteSession(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm(t("deleteChatConfirm"))) return;
    try {
      await chatSessions.delete(id);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (id === sessionId) startNewChat();
    } catch (e) {
      console.error(e);
    }
  }

  useEffect(() => {
    scrollerRef.current?.scrollTo({
      top: scrollerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "0px";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [text]);

  useEffect(() => {
    if (voiceFirst && !recording) startRecording();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitText = useCallback(
    async (raw: string) => {
      const value = raw.trim();
      if (!value && draftAttachments.length === 0) return;
      if (busy) return;
      
      setError(null);
      setText("");
      
      const currentAttachments = [...draftAttachments];
      setDraftAttachments([]);
      
      setBusy(true);
      
      if (currentAttachments.length > 0) {
        setUploading(true);
        try {
          await Promise.all(
            currentAttachments.map(async (att) => {
              const pendingId = crypto.randomUUID();
              setMessages((m) => [
                ...m,
                {
                  id: pendingId,
                  role: "user",
                  content: t("uploading", { name: att.file.name }),
                  kind: "text",
                  pending: true,
                },
              ]);
              
              try {
                const res = await uploadDocument(att.file);
                const ok = res.status === "indexed";
                setMessages((m) =>
                  m.map((x) =>
                    x.id === pendingId
                      ? {
                          ...x,
                          pending: false,
                          content: ok
                            ? t("indexed", { name: res.file_name, count: res.chunk_count })
                            : t("indexFailed", { name: res.file_name, error: res.error ?? t("unknownError") }),
                        }
                      : x,
                  ),
                );
              } catch (err) {
                const msg = err instanceof Error ? err.message : t("uploadFailedGeneric");
                setMessages((m) =>
                  m.map((x) =>
                    x.id === pendingId
                      ? { ...x, pending: false, content: t("uploadFailed", { error: msg }) }
                      : x,
                  ),
                );
              }
            })
          );
        } finally {
          setUploading(false);
        }
      }
      
      if (value) {
        const tempId = crypto.randomUUID();
        const replyId = crypto.randomUUID();
        setMessages((m) => [
          ...m,
          { id: tempId, role: "user", content: value, kind: "text" },
          { id: replyId, role: "assistant", content: "", pending: true },
        ]);
        try {
          const res = await sendChat({ text: value, sessionId });
          setMessages((m) =>
            m.map((x) =>
              x.id === replyId
                ? { ...x, content: res.reply, pending: false, thinking: res.thinking || undefined }
                : x,
            ),
          );
          refreshSessions();
        } catch (e) {
          const msg = e instanceof Error ? e.message : t("somethingWrong");
          const quotaHit = /429/.test(msg) || /monthly limit|used all/i.test(msg);
          setMessages((m) =>
            m.map((x) =>
              x.id === replyId
                ? { ...x, pending: false, error: quotaHit ? "QUOTA" : msg, content: "" }
                : x,
            ),
          );
          setError(quotaHit ? null : msg);
        }
      }
      
      setBusy(false);
    },
    [busy, sessionId, refreshSessions, t, draftAttachments],
  );

  const submitAudio = useCallback(
    async (blob: Blob) => {
      setError(null);
      const tempId = crypto.randomUUID();
      const replyId = crypto.randomUUID();
      const audioUrl = URL.createObjectURL(blob);
      setMessages((m) => [
        ...m,
        { id: tempId, role: "user", content: "Voice message", kind: "voice", audioUrl },
        { id: replyId, role: "assistant", content: "", pending: true },
      ]);
      setBusy(true);
      try {
        const res = await sendChat({ text: "", audio: blob, sessionId });
        setMessages((m) =>
          m.map((x) =>
            x.id === replyId
              ? { ...x, content: res.reply, pending: false }
              : x,
          ),
        );
        refreshSessions();
      } catch (e) {
        const msg = e instanceof Error ? e.message : t("voiceProcessingFailed");
        setMessages((m) =>
          m.map((x) =>
            x.id === replyId ? { ...x, pending: false, error: msg } : x,
          ),
        );
        setError(msg);
      } finally {
        setBusy(false);
      }
    },
    [sessionId, refreshSessions, t],
  );

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setRecordingStream(null);
        const blob = new Blob(chunksRef.current, { type: mime });
        if (blob.size > 500) submitAudio(blob);
      };
      rec.start();
      recRef.current = rec;
      setRecordingStream(stream);
      setRecording(true);
    } catch {
      setError(t("micDenied"));
    }
  }

  function stopRecording() {
    recRef.current?.stop();
    recRef.current = null;
    setRecording(false);
  }

  const removeAttachment = (id: string) => {
    setDraftAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files).map((file) => ({
        id: crypto.randomUUID(),
        file,
      }));
      setDraftAttachments((prev) => [...prev, ...droppedFiles]);
    }
  };

  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    
    const filesToAttach: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          filesToAttach.push(file);
        }
      }
    }
    
    if (filesToAttach.length > 0) {
      e.preventDefault();
      setDraftAttachments((prev) => [
        ...prev,
        ...filesToAttach.map((file) => ({
          id: crypto.randomUUID(),
          file,
        })),
      ]);
    }
  }, []);

  async function handleFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    
    const filesArray = Array.from(fileList);
    e.target.value = "";
    
    const newAttachments = filesArray.map((file) => ({
      id: crypto.randomUUID(),
      file,
    }));
    
    setDraftAttachments((prev) => [...prev, ...newAttachments]);
  }

  const showWelcome = messages.length === 0;

  const [showHistory, setShowHistory] = useState(false);
  const [historyQuery, setHistoryQuery] = useState("");

  const filteredSessions = useMemo(() => {
    const q = historyQuery.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => (s.title || t("untitledSession")).toLowerCase().includes(q));
  }, [sessions, historyQuery, t]);

  const sessionGroups = useMemo(() => groupSessionsByDate(filteredSessions), [filteredSessions]);

  return (
    <>
      <div className="flex-1 min-h-0 flex flex-col min-w-0 bg-background relative">
        <header className="h-16 border-b border-border flex items-center px-4 md:px-8 justify-between bg-background/80 backdrop-blur-md z-10 shrink-0">
          <div className="flex items-center gap-4 min-w-0">
            <Button
              variant="ghost"
              size="icon"
              className="cursor-pointer shrink-0 rounded-full hover:bg-muted"
              onClick={() => setShowHistory(!showHistory)}
              aria-label={t("toggleHistory")}
              aria-expanded={showHistory}
            >
              <Clock className="size-5" />
            </Button>
            <div className="flex flex-col min-w-0">
              <h1 className="text-sm font-bold truncate">
                {sessions.find((s) => s.session_id === sessionId)?.title || t("currentChat")}
              </h1>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-medium">
                {t("messagesCount", { count: messages.length })}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {loadingHistory && <Loader2 className="size-4 animate-spin text-primary" />}
            <ModelSelector initialProvider={initialProvider} initialModel={initialModel} />
            <Button
              variant="default"
              size="sm"
              onClick={startNewChat}
              className="cursor-pointer whitespace-nowrap shadow-sm"
            >
              <Plus className="size-4 mr-2" /> {t("newChat")}
            </Button>
          </div>
        </header>

        <AnimatePresence>
          {showHistory && (
            <motion.div
              key="history-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={() => setShowHistory(false)}
              className="absolute inset-0 z-30 bg-foreground/10 backdrop-blur-[1px]"
            />
          )}
        </AnimatePresence>
        <AnimatePresence>
          {showHistory && (
            <motion.aside
              key="history-panel"
              initial={{ x: -16, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -16, opacity: 0 }}
              transition={{ type: "spring", damping: 32, stiffness: 340 }}
              className="absolute inset-y-0 left-0 z-40 w-full sm:w-[340px] bg-card border-r border-border shadow-2xl flex flex-col"
            >
              <div className="h-16 border-b border-border flex items-center justify-between px-4 shrink-0">
                <h2 className="text-sm font-bold">{t("chatHistory")}</h2>
                <button
                  onClick={() => setShowHistory(false)}
                  className="p-1.5 -mr-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted cursor-pointer"
                  aria-label={t("closeHistory")}
                >
                  <PanelLeftClose className="size-4" />
                </button>
              </div>

              <div className="p-3 border-b border-border shrink-0 space-y-2">
                <Button
                  onClick={startNewChat}
                  size="sm"
                  className="w-full justify-center cursor-pointer"
                >
                  <Plus className="size-4 mr-1.5" /> {t("newChat")}
                </Button>
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
                  <input
                    value={historyQuery}
                    onChange={(e) => setHistoryQuery(e.target.value)}
                    placeholder={t("searchChatsPlaceholder")}
                    className="w-full h-8 pl-8 pr-2.5 text-xs bg-muted/50 border border-transparent rounded-lg focus:outline-none focus:border-border focus:bg-background transition-colors"
                  />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
                {filteredSessions.length === 0 ? (
                  <div className="py-12 text-center px-6">
                    <div className="size-12 rounded-2xl bg-muted/50 grid place-items-center mx-auto mb-3">
                      <MessageSquare className="size-5 text-muted-foreground/40" />
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {historyQuery ? t("noSearchMatches") : t("noChatsYet")}
                    </p>
                  </div>
                ) : (
                  sessionGroups.map(
                    ({ key, items }) =>
                      items.length > 0 && (
                        <div key={key}>
                          <div className="px-4 pt-3 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            {t(`dateGroups.${key}`)}
                          </div>
                          <div className="px-2 space-y-0.5">
                            {items.map((s) => {
                              const active = sessionId === s.session_id;
                              return (
                                <button
                                  key={s.session_id}
                                  onClick={() => loadSession(s.session_id)}
                                  className={cn(
                                    "group w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors cursor-pointer",
                                    active ? "bg-foreground text-background" : "hover:bg-muted",
                                  )}
                                >
                                  <MessageSquare
                                    className={cn(
                                      "size-3.5 shrink-0",
                                      active ? "opacity-70" : "text-muted-foreground",
                                    )}
                                  />
                                  <div className="min-w-0 flex-1">
                                    <div className="text-xs font-medium truncate">
                                      {s.title || t("untitledSession")}
                                    </div>
                                    <div
                                      className={cn(
                                        "text-[10px] truncate",
                                        active ? "opacity-60" : "text-muted-foreground",
                                      )}
                                    >
                                      {t("messagesCount", { count: s.message_count })}
                                    </div>
                                  </div>
                                  <span
                                    role="button"
                                    tabIndex={-1}
                                    onClick={(e) => deleteSession(s.session_id, e)}
                                    title={t("deleteChat")}
                                    className={cn(
                                      "opacity-0 group-hover:opacity-100 p-1 rounded-md transition-all shrink-0 cursor-pointer",
                                      active
                                        ? "hover:bg-background/20"
                                        : "hover:bg-destructive/10 hover:text-destructive",
                                    )}
                                  >
                                    <Trash2 className="size-3" />
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ),
                  )
                )}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <div
          ref={scrollerRef}
          className="flex-1 min-h-0 overflow-y-auto scroll-smooth"
        >
          <div className="max-w-3xl mx-auto px-5 md:px-8 py-10 space-y-8">
            {showWelcome ? (
              <Welcome onPick={submitText} suggestions={SUGGESTIONS} />
            ) : (
              messages.map((m) => <Bubble key={m.id} msg={m} onKeySaved={(provider) => submitText(`[API Key for ${provider} saved securely]`)} />)
            )}
          </div>
        </div>

        <div className="border-t border-border bg-background/80 backdrop-blur-sm">
          <div className="max-w-3xl mx-auto px-5 md:px-8 py-4 relative">
            {showCommandsDropdown && (
              <div className="absolute bottom-full left-5 right-5 md:left-8 md:right-8 mb-2 bg-card/95 border border-border rounded-xl shadow-lg backdrop-blur-md overflow-hidden z-50">
                <div className="px-3 py-2 border-b border-border/50 text-[10px] font-bold uppercase tracking-wider text-muted-foreground bg-muted/30">
                  {t("commandsLabel")}
                </div>
                <div className="p-1.5 max-h-[200px] overflow-y-auto space-y-0.5 custom-scrollbar">
                  {filteredCommands.map((c, i) => (
                    <button
                      key={c.cmd}
                      type="button"
                      onClick={() => selectCommand(c.cmd)}
                      onMouseEnter={() => setSelectedCmdIndex(i)}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-lg transition-colors flex flex-col gap-0.5 cursor-pointer",
                        i === selectedCmdIndex
                          ? "bg-primary/10 text-primary"
                          : "hover:bg-muted text-foreground"
                      )}
                    >
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span>{c.example}</span>
                        {i === selectedCmdIndex && (
                          <span className="text-[10px] text-muted-foreground font-normal bg-muted px-1.5 py-0.5 rounded">
                            {t("pressEnter")}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        {c.desc}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <div className="mb-2 flex items-start gap-2 text-xs text-destructive">
                <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                submitText(text);
              }}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              className={cn(
                "rounded-2xl border bg-card transition-colors relative",
                recording ? "border-orange-300 ring-2 ring-orange-100" : "border-border",
                dragActive && "border-orange-500 bg-orange-50/5 dark:bg-orange-950/5 ring-2 ring-orange-200/50",
              )}
            >
              {/* Attachments Preview */}
              {draftAttachments.length > 0 && (
                <div className="flex flex-wrap gap-2 px-4 pt-3 pb-1 border-b border-border/50 max-h-40 overflow-y-auto">
                  {draftAttachments.map((att) => {
                    const isImage = att.file.type.startsWith("image/");
                    return (
                      <div
                        key={att.id}
                        className="relative flex items-center gap-2 rounded-lg border border-border bg-muted/50 p-1.5 pr-2 text-xs group"
                      >
                        {isImage ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={URL.createObjectURL(att.file)}
                            alt={att.file.name}
                            className="size-8 rounded object-cover shrink-0"
                          />
                        ) : (
                          <div className="size-8 rounded bg-orange-100 dark:bg-orange-950/30 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
                            <FileText className="size-4" />
                          </div>
                        )}
                        <div className="flex flex-col min-w-0 max-w-[120px]">
                          <span className="truncate font-medium text-foreground text-[11px]">{att.file.name}</span>
                          <span className="text-[10px] text-muted-foreground">
                            {(att.file.size / 1024).toFixed(1)} KB
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeAttachment(att.id)}
                          className="absolute -top-1.5 -right-1.5 size-4 rounded-full bg-neutral-900 dark:bg-neutral-800 text-white flex items-center justify-center cursor-pointer hover:bg-neutral-800 dark:hover:bg-neutral-700 transition-colors"
                        >
                          <X className="size-2.5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {recording ? (
                <div className="flex items-center gap-3 px-4 pt-3 pb-2 h-[42px]">
                  <span className="relative flex size-2 shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                    <span className="relative inline-flex rounded-full size-2 bg-orange-500" />
                  </span>
                  <span className="text-sm text-muted-foreground shrink-0">{t("listening")}</span>
                  {recordingStream && <RecordingWaveform stream={recordingStream} />}
                </div>
              ) : (
              <textarea
                ref={taRef}
                value={text}
                onPaste={handlePaste}
                onFocus={() => {
                  if (text.startsWith("/") && !text.includes(" ")) {
                    setShowCmds(true);
                  }
                }}
                onClick={() => {
                  if (text.startsWith("/") && !text.includes(" ")) {
                    setShowCmds(true);
                  }
                }}
                onChange={(e) => {
                  const val = e.target.value;
                  setText(val);
                  if (val.startsWith("/") && !val.includes(" ")) {
                    setShowCmds(true);
                    setSelectedCmdIndex(0);
                  } else {
                    setShowCmds(false);
                  }
                }}
                onKeyDown={(e) => {
                  if (showCommandsDropdown) {
                    if (e.key === "ArrowDown") {
                      e.preventDefault();
                      setSelectedCmdIndex((prev) => (prev + 1) % filteredCommands.length);
                    } else if (e.key === "ArrowUp") {
                      e.preventDefault();
                      setSelectedCmdIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
                    } else if (e.key === "Enter" || e.key === "Tab") {
                      e.preventDefault();
                      selectCommand(filteredCommands[selectedCmdIndex].cmd);
                    } else if (e.key === "Escape") {
                      e.preventDefault();
                      setShowCmds(false);
                    }
                  } else if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submitText(text);
                  }
                }}
                placeholder={t("messagePlaceholder")}
                rows={1}
                disabled={recording}
                className="w-full resize-none bg-transparent px-4 pt-3 pb-2 text-sm placeholder:text-muted-foreground focus:outline-none disabled:opacity-60 text-foreground"
              />
              )}
              <div className="flex items-center justify-between px-2 pb-2">
                <div className="text-[11px] text-muted-foreground px-2">
                  {t("shiftEnterHint")}
                </div>
                <div className="flex items-center gap-1.5">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.doc,.txt,.md,.markdown,.csv,image/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/csv"
                    onChange={handleFilePicked}
                    className="hidden"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={busy || uploading || recording}
                    aria-label={t("uploadDocument")}
                    title={t("uploadDocumentTitle")}
                    className={cn(
                      "cursor-pointer group transition-colors",
                      uploading && "text-orange-600",
                    )}
                  >
                    {uploading ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <motion.span
                        whileHover={{ rotate: -18, scale: 1.1 }}
                        whileTap={{ scale: 0.9, rotate: 0 }}
                        transition={{ type: "spring", stiffness: 400, damping: 14 }}
                        className="inline-flex"
                      >
                        <Paperclip className="size-3.5" />
                      </motion.span>
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant={recording ? "destructive" : "ghost"}
                    size="icon-sm"
                    onClick={recording ? stopRecording : startRecording}
                    disabled={busy || uploading}
                    aria-label={recording ? t("stopRecording") : t("recordVoice")}
                    className="cursor-pointer"
                  >
                    {recording ? <Square className="size-3.5" /> : <Mic className="size-3.5" />}
                  </Button>
                  <Button
                    type="submit"
                    size="icon-sm"
                    disabled={busy || (!text.trim() && draftAttachments.length === 0) || recording || uploading}
                    aria-label={t("send")}
                    className="cursor-pointer"
                  >
                    <Send className="size-3.5" />
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
}

const Bubble = memo(function Bubble({ msg, onKeySaved }: { msg: Msg; onKeySaved?: (provider: string) => void }) {
  const t = useTranslations("dashboard.chat");
  const isUser = msg.role === "user";
  const [showThinking, setShowThinking] = useState(false);

  const asksForKey = useMemo(() => {
    if (isUser || !msg.content) return false;
    const contentLower = msg.content.toLowerCase();
    return (
      (contentLower.includes("api key") ||
        contentLower.includes("api_key") ||
        contentLower.includes("openai key") ||
        contentLower.includes("anthropic key") ||
        contentLower.includes("elevenlabs key") ||
        contentLower.includes("deepgram key") ||
        contentLower.includes("cartesia key") ||
        contentLower.includes("provider key")) &&
      !contentLower.includes("saved securely")
    );
  }, [isUser, msg.content]);

  const [keyInput, setKeyInput] = useState("");
  const [selectedProvider, setSelectedProvider] = useState(() => {
    const contentLower = msg.content?.toLowerCase() || "";
    if (contentLower.includes("openai")) return "openai";
    if (contentLower.includes("anthropic")) return "anthropic";
    if (contentLower.includes("elevenlabs")) return "elevenlabs";
    if (contentLower.includes("deepgram")) return "deepgram";
    if (contentLower.includes("cartesia")) return "cartesia";
    if (contentLower.includes("groq")) return "groq";
    if (contentLower.includes("google") || contentLower.includes("gemini")) return "google";
    return "openai";
  });
  const [savingKey, setSavingKey] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

  const handleSaveKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyInput.trim()) return;
    setSavingKey(true);
    try {
      await flowCredentials.save(selectedProvider, { api_key: keyInput.trim() });
      setSaveStatus("success");
      onKeySaved?.(selectedProvider);
    } catch (err) {
      setSaveStatus("error");
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="size-7 shrink-0 rounded-full bg-orange-50 text-orange-600 grid place-items-center">
          <Sparkles className="size-3.5" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-foreground text-background rounded-br-md"
            : "bg-card border border-border rounded-bl-md",
        )}
      >
        {!isUser && msg.thinking && (
          <div className="mb-2">
            <button
              type="button"
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer select-none py-1"
            >
              <Brain className="size-3" />
              <span>{t("thinking")}</span>
              <ChevronDown
                className={cn(
                  "size-3 transition-transform duration-200",
                  showThinking && "rotate-180",
                )}
              />
            </button>
            <AnimatePresence>
              {showThinking && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="text-[11px] text-muted-foreground/70 bg-muted/30 rounded-lg px-3 py-2 mt-1 whitespace-pre-wrap leading-relaxed border border-border/50 max-h-[300px] overflow-y-auto custom-scrollbar">
                    {msg.thinking}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {!isUser && msg.pending ? (
          <span className="inline-flex gap-1 py-1">
            <Dot delay={0} />
            <Dot delay={0.15} />
            <Dot delay={0.3} />
          </span>
        ) : msg.error === "QUOTA" ? (
          <div className="text-sm">
            <p className="font-medium">{t("quotaExceeded")}</p>
            <p className="text-muted-foreground text-xs mt-1">
              {t("upgradeToKeepChatting")}
            </p>
            <a
              href="/dashboard/billing"
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-foreground underline underline-offset-2"
            >
              {t("seePlans")}
            </a>
          </div>
        ) : msg.error ? (
          <span className="text-destructive">⚠ {msg.error}</span>
        ) : isUser && msg.kind === "voice" && msg.audioUrl ? (
          <div className="flex items-center gap-2 min-w-[240px]">
            <Mic className="size-3.5 shrink-0 opacity-70" />
            <VoicePlayer src={msg.audioUrl} />
          </div>
        ) : isUser && msg.content.startsWith("📎") ? (
          (() => {
            const content = msg.content;
            const isFailed = content.includes("failed") || 
                            content.includes("Couldn't") || 
                            content.includes("failed") || 
                            content.includes("pudo") || 
                            content.includes("stato") || 
                            content.includes("impossible");
            
            const isIndexed = !isFailed && (
              content.includes("Indexed") || 
              content.includes("Indexado") || 
              content.includes("Indicizzato") || 
              content.includes("Indexé")
            );

            let fileTitle = "";
            const match = content.match(/\*\*(.*?)\*\*/);
            if (match) {
              fileTitle = match[1];
            } else {
              const uploadMatch = content.match(/(?:Uploading|Subiendo|Caricamento|Chargement)\s+(.*?)(?:…|\.\.\.|$)/i);
              if (uploadMatch) {
                fileTitle = uploadMatch[1].trim();
              } else {
                const cleaned = content.replace(/^[📎⏳⚡❌]\s*/, "");
                const words = cleaned.split(" ");
                fileTitle = words.find(w => w.includes(".")) || words[1] || words[0] || "Document";
                fileTitle = fileTitle.replace(/\.$/, "");
              }
            }
            return (
              <div className="flex items-center gap-3 bg-muted/20 dark:bg-muted/10 border border-border/80 rounded-xl p-3 min-w-[240px] max-w-sm mt-1">
                <div className="size-10 rounded-lg bg-orange-100 dark:bg-orange-950/40 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0 shadow-sm">
                  <FileText className="size-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-foreground truncate" title={fileTitle}>
                    {fileTitle}
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1">
                    {isIndexed ? (
                      <>
                        <span className="size-1.5 rounded-full bg-emerald-500 inline-block" />
                        <span>Indexed & Ready</span>
                      </>
                    ) : isFailed ? (
                      <>
                        <span className="size-1.5 rounded-full bg-red-500 inline-block" />
                        <span className="text-red-500">Failed to Index</span>
                      </>
                    ) : (
                      <>
                        <Loader2 className="size-2.5 animate-spin text-orange-500" />
                        <span>Indexing document...</span>
                      </>
                    )}
                  </p>
                </div>
              </div>
            );
          })()
        ) : isUser ? (
          <span className="whitespace-pre-wrap break-words">{msg.content}</span>
        ) : !msg.content || msg.content === "(no reply)" ? (
          <span className="text-muted-foreground/50 italic text-xs">
            {t("noReply")}
          </span>
        ) : (
          <div>
            <Markdown>{msg.content}</Markdown>
            {asksForKey && saveStatus !== "success" && (
              <form onSubmit={handleSaveKey} className="mt-4 p-3 bg-muted/40 dark:bg-muted/10 border border-border/80 rounded-xl space-y-3 max-w-sm">
                <p className="text-xs font-semibold text-foreground/80 flex items-center gap-1">
                  <Sparkles className="size-3.5 text-orange-500" />
                  Secure API Key Input
                </p>
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground block">Select Provider</label>
                  <select
                    value={selectedProvider}
                    onChange={(e) => setSelectedProvider(e.target.value)}
                    className="w-full h-8 px-2 bg-background border border-border rounded text-xs focus:outline-none"
                    disabled={savingKey}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="elevenlabs">ElevenLabs</option>
                    <option value="deepgram">Deepgram</option>
                    <option value="cartesia">Cartesia</option>
                    <option value="google">Google Gemini</option>
                    <option value="groq">Groq</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground block">API Key</label>
                  <input
                    type="password"
                    value={keyInput}
                    onChange={(e) => setKeyInput(e.target.value)}
                    placeholder="Paste your key here..."
                    className="w-full h-8 px-2 bg-background border border-border rounded text-xs focus:outline-none"
                    disabled={savingKey}
                    required
                  />
                </div>
                {saveStatus === "error" && (
                  <p className="text-[10px] text-destructive">Failed to save key. Try again.</p>
                )}
                <Button
                  type="submit"
                  disabled={savingKey || !keyInput.trim()}
                  className="w-full h-8 text-xs cursor-pointer gap-1.5"
                >
                  {savingKey && <Loader2 className="size-3 animate-spin" />}
                  Save Key Securely
                </Button>
              </form>
            )}
            {saveStatus === "success" && (
              <div className="mt-3 p-2.5 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30 rounded-xl text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2 max-w-sm">
                <span className="size-1.5 rounded-full bg-emerald-500" />
                <span>API Key for {selectedProvider} saved securely!</span>
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
});

function Dot({ delay }: { delay: number }) {
  return (
    <motion.span
      className="size-1.5 rounded-full bg-muted-foreground/60"
      animate={{ y: [0, -3, 0] }}
      transition={{ duration: 0.7, repeat: Infinity, delay }}
    />
  );
}

const WAVEFORM_BARS = 24;

function RecordingWaveform({ stream }: { stream: MediaStream }) {
  const [levels, setLevels] = useState<number[]>(() => Array(WAVEFORM_BARS).fill(3));

  useEffect(() => {
    const AudioContextCls =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioContextCls();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 64;
    analyser.smoothingTimeConstant = 0.6;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const step = Math.max(1, Math.floor(data.length / WAVEFORM_BARS));
    let raf: number;

    const tick = () => {
      analyser.getByteFrequencyData(data);
      setLevels(
        Array.from({ length: WAVEFORM_BARS }, (_, i) => {
          const v = data[i * step] || 0;
          return Math.max(3, Math.round((v / 255) * 26));
        }),
      );
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      source.disconnect();
      ctx.close().catch(() => {});
    };
  }, [stream]);

  return (
    <div className="flex items-center gap-[3px] h-8 flex-1 min-w-0 overflow-hidden">
      {levels.map((h, i) => (
        <span
          key={i}
          className="w-[3px] rounded-full bg-orange-500 shrink-0 transition-[height] duration-75"
          style={{ height: `${h}px` }}
        />
      ))}
    </div>
  );
}

function Welcome({ onPick, suggestions }: { onPick: (t: string) => void; suggestions: string[] }) {
  const t = useTranslations("dashboard.chat.welcome");
  return (
    <div className="pt-10 md:pt-16 flex flex-col items-center text-center">
      <div className="size-10 rounded-2xl bg-orange-50 text-orange-600 grid place-items-center">
        <Sparkles className="size-5" />
      </div>
      <h2 className="mt-5 text-2xl md:text-3xl font-bold tracking-tight">
        {t("title")}
      </h2>
      <p className="mt-2 text-sm text-muted-foreground max-w-md">
        {t("body")}
      </p>
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
        <AnimatePresence>
          {suggestions.map((s, i) => (
            <motion.button
              key={s}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
              onClick={() => onPick(s)}
              className="text-left text-xs px-4 py-3 rounded-xl border border-border bg-card hover:border-foreground/20 hover:-translate-y-0.5 transition-all"
            >
              {s}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function VoicePlayer({ src }: { src: string }) {
  const t = useTranslations("dashboard.chat");
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => {
      if (audio.duration && isFinite(audio.duration)) {
        setDuration(audio.duration);
      }
    };
    const onEnded = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("ended", onEnded);

    if (audio.readyState >= 1 && audio.duration && isFinite(audio.duration)) {
      setDuration(audio.duration);
    }

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("ended", onEnded);
    };
  }, [src]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      audio.play().catch((err) => console.error("Audio play failed", err));
      setIsPlaying(true);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio) return;
    const val = parseFloat(e.target.value);
    audio.currentTime = val;
    setCurrentTime(val);
  };

  const formatTime = (time: number) => {
    if (isNaN(time) || !isFinite(time)) return "0:00";
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex items-center gap-3 w-full max-w-[280px] py-1 select-none text-current">
      <audio ref={audioRef} src={src} preload="metadata" />

      <button
        type="button"
        onClick={togglePlay}
        className="size-7 rounded-full flex items-center justify-center bg-background/25 hover:bg-background/35 active:scale-95 transition-all text-current shrink-0 cursor-pointer"
        aria-label={isPlaying ? t("pause") : t("play")}
      >
        {isPlaying ? (
          <Pause className="size-3.5 fill-current text-current" />
        ) : (
          <Play className="size-3.5 fill-current text-current translate-x-0.5" />
        )}
      </button>

      <div className="flex-1 min-w-0 flex items-center gap-2">
        <input
          type="range"
          min={0}
          max={duration || 100}
          value={currentTime}
          onChange={handleSeek}
          className="flex-1 h-1 rounded-lg appearance-none cursor-pointer accent-current bg-background/20"
          style={{
            background: `linear-gradient(to right, currentColor 0%, currentColor ${
              duration ? (currentTime / duration) * 100 : 0
            }%, rgba(255,255,255,0.15) ${
              duration ? (currentTime / duration) * 100 : 0
            }%, rgba(255,255,255,0.15) 100%)`
          }}
        />
        <span className="text-[10px] opacity-80 font-mono shrink-0 whitespace-nowrap">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>
    </div>
  );
}
