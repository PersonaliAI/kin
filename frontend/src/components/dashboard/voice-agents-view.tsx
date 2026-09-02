"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  Phone,
  PhoneCall,
  PhoneOff,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
  Pencil,
  Settings,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, type SelectOption } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Dialog, DialogFooter, Field, inputCls, textareaCls } from "./dialog";
import { VoiceAgentTestCallDialog, TestInBrowserButton } from "./voice-agent-test-call";
import { TelephonyByokSection } from "./voice-agent-settings";
import {
  voiceAgentsApi,
  type VoiceAgent,
  type VoiceAgentCall,
  type VoiceAgentLlmProvider,
  type VoiceAgentSttProvider,
  type VoiceAgentTtsProvider,
  type VoiceAgentMode,
  type VoiceAgentRealtimeProvider,
  type VoiceAgentUseCase,
} from "@/lib/backend";

const LLM_PROVIDERS: VoiceAgentLlmProvider[] = ["openai", "anthropic", "google", "xai"];
const STT_PROVIDERS: VoiceAgentSttProvider[] = ["deepgram", "google", "azure", "assemblyai", "openai"];
const TTS_PROVIDERS: VoiceAgentTtsProvider[] = ["elevenlabs", "cartesia", "rime", "lmnt", "azure", "google"];
const MODES: VoiceAgentMode[] = ["pipeline", "realtime"];
const REALTIME_PROVIDERS: VoiceAgentRealtimeProvider[] = ["google", "openai"];
const USE_CASES: VoiceAgentUseCase[] = ["sales", "receptionist", "custom"];
const AVAILABLE_TOOLS = [
  "create_calendar_event", "check_calendar_availability", "create_lead",
  // Same RAG search worker.py's build_tools() now exposes to the LLM — gives
  // a voice call the same knowledge-base grounding as web chat.
  "search_documents", "read_full_document",
];

// Speech-to-speech models — audio in, audio out directly, no separate
// STT/TTS. Model ids and defaults confirmed against the installed LiveKit
// plugins (google.realtime.RealtimeModel / openai.realtime.RealtimeModel)
// as of this writing — check each provider's docs before assuming a newer
// model id works, these move fast.
const DEFAULT_REALTIME_MODEL_BY_PROVIDER: Record<VoiceAgentRealtimeProvider, string> = {
  google: "gemini-3.1-flash-live-preview",
  openai: "gpt-realtime",
};

const REALTIME_MODELS: Record<VoiceAgentRealtimeProvider, SelectOption[]> = {
  google: [
    { value: "gemini-3.1-flash-live-preview", label: "gemini-3.1-flash-live-preview (Recommended)" },
    { value: "gemini-2.5-flash", label: "gemini-2.5-flash" },
    { value: "custom", label: "Custom model..." },
  ],
  openai: [
    { value: "gpt-realtime", label: "gpt-realtime (Recommended)" },
    { value: "custom", label: "Custom model..." },
  ],
};

const REALTIME_VOICES: Record<VoiceAgentRealtimeProvider, SelectOption[]> = {
  google: [
    { value: "Puck", label: "Puck (Recommended)" },
    { value: "custom", label: "Custom voice..." },
  ],
  openai: [
    { value: "marin", label: "marin (Recommended)" },
    { value: "custom", label: "Custom voice..." },
  ],
};

const DEFAULT_MODEL_BY_PROVIDER: Record<VoiceAgentLlmProvider, string> = {
  openai: "gpt-5.6-sol",
  anthropic: "claude-fable-5",
  google: "gemini-3.7-flash",
  xai: "grok-4.6",
};

const RECOMMENDED_MODELS: Record<VoiceAgentLlmProvider, SelectOption[]> = {
  openai: [
    { value: "gpt-5.6-sol", label: "GPT-5.6 Sol (Recommended)" },
    { value: "gpt-5.6-terra", label: "GPT-5.6 Terra" },
    { value: "gpt-5.6-luna", label: "GPT-5.6 Luna" },
    { value: "gpt-5.5", label: "GPT-5.5" },
    { value: "gpt-5.5-pro", label: "GPT-5.5 Pro" },
    { value: "custom", label: "Custom model..." },
  ],
  anthropic: [
    { value: "claude-fable-5", label: "Claude Fable 5 (Recommended)" },
    { value: "claude-opus-5", label: "Claude Opus 5" },
    { value: "claude-sonnet-5", label: "Claude Sonnet 5" },
    { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
    { value: "claude-opus-4-8", label: "Claude Opus 4.8" },
    { value: "custom", label: "Custom model..." },
  ],
  google: [
    { value: "gemini-3.7-flash", label: "Gemini 3.7 Flash (Recommended)" },
    { value: "gemini-3.6-flash", label: "Gemini 3.6 Flash" },
    { value: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
    { value: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash-Lite" },
    { value: "gemini-3.1-flash-lite", label: "Gemini 3.1 Flash-Lite" },
    { value: "custom", label: "Custom model..." },
  ],
  xai: [
    { value: "grok-4.6", label: "Grok 4.6 (Recommended)" },
    { value: "grok-4.5", label: "Grok 4.5" },
    { value: "grok-4", label: "Grok 4" },
    { value: "grok-4-heavy", label: "Grok 4 Heavy" },
    { value: "grok-3", label: "Grok 3" },
    { value: "custom", label: "Custom model..." },
  ],
};

const RECOMMENDED_VOICES: Record<VoiceAgentTtsProvider, SelectOption[]> = {
  cartesia: [
    { value: "951aadea-a9be-4e00-92c9-ee57b1b4b7c1", label: "Baritone Voice (English)" },
    { value: "c63e2646-cd91-4475-ba7e-ef8d8c365313", label: "Clarion Voice (English)" },
    { value: "custom", label: "Custom voice ID..." },
  ],
  elevenlabs: [
    { value: "21m00Tcm4TlvDq8ikWAM", label: "Rachel" },
    { value: "AZnzlk1XvdvUeBnXmlld", label: "Domi" },
    { value: "EXAVITQu4vr4xnSDxMaL", label: "Bella" },
    { value: "custom", label: "Custom voice ID..." },
  ],
  rime: [
    { value: "custom", label: "Custom voice ID..." },
  ],
  lmnt: [
    { value: "custom", label: "Custom voice ID..." },
  ],
  azure: [
    { value: "custom", label: "Custom voice ID..." },
  ],
  google: [
    { value: "custom", label: "Custom voice ID..." },
  ],
};

type FormState = {
  name: string;
  use_case: VoiceAgentUseCase;
  persona: string;
  greeting: string;
  mode: VoiceAgentMode;
  llm_provider: VoiceAgentLlmProvider;
  llm_model: string;
  stt_provider: VoiceAgentSttProvider;
  tts_provider: VoiceAgentTtsProvider;
  tts_voice: string;
  // Realtime mode's own provider/model/voice — kept separate from the
  // pipeline fields above so switching tabs back and forth doesn't lose
  // either configuration.
  realtime_provider: VoiceAgentRealtimeProvider;
  realtime_model: string;
  realtime_voice: string;
  tools: string[];
  // BYOK — each agent uses its own owner's provider keys, entered here.
  // Blank on edit means "leave whatever's already saved unchanged".
  llm_api_key: string;
  stt_api_key: string;
  tts_api_key: string;
  realtime_api_key: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  use_case: "sales",
  persona: "",
  greeting: "",
  mode: "pipeline",
  llm_provider: "openai",
  llm_model: DEFAULT_MODEL_BY_PROVIDER.openai,
  stt_provider: "deepgram",
  tts_provider: "cartesia",
  tts_voice: "",
  realtime_provider: "google",
  realtime_model: DEFAULT_REALTIME_MODEL_BY_PROVIDER.google,
  realtime_voice: "",
  tools: [],
  llm_api_key: "",
  stt_api_key: "",
  tts_api_key: "",
  realtime_api_key: "",
};

const PIPELINE_FORM_STEPS = ["basics", "brain", "voicePipeline", "tools"] as const;
const REALTIME_FORM_STEPS = ["basics", "brain", "tools"] as const;

// Providers whose BYOK field isn't a plain API key string — shown as a
// hint under the key input instead of a generic placeholder.
const KEY_FORMAT_HINTS: Partial<Record<VoiceAgentSttProvider | VoiceAgentTtsProvider, string>> = {
  azure: "Format: region:key (e.g. eastus:abcd1234...)",
  google: "Paste the full GCP service-account JSON, not a short key.",
};

const STATUS_STYLES: Record<VoiceAgent["status"], string> = {
  draft: "bg-muted text-muted-foreground border-border",
  provisioning: "bg-amber-50 text-amber-700 dark:bg-amber-950/20 dark:text-amber-400 border-amber-100 dark:border-amber-900/30 animate-pulse",
  active: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400 border-emerald-100 dark:border-emerald-900/30",
  paused: "bg-muted text-muted-foreground border-border",
  error: "bg-destructive/10 text-destructive border-destructive/25",
};

export function VoiceAgentsView() {
  const t = useTranslations("dashboard.voiceAgents");

  const useCaseOptions: SelectOption[] = USE_CASES.map((uc) => ({ value: uc, label: t(`useCase.${uc}`) }));
  const llmProviderOptions: SelectOption[] = LLM_PROVIDERS.map((p) => ({ value: p, label: t(`llmProvider.${p}`) }));
  const realtimeProviderOptions: SelectOption[] = REALTIME_PROVIDERS.map((p) => ({ value: p, label: t(`llmProvider.${p}`) }));
  const sttProviderOptions: SelectOption[] = STT_PROVIDERS.map((p) => ({ value: p, label: t(`sttProvider.${p}`) }));
  const ttsProviderOptions: SelectOption[] = TTS_PROVIDERS.map((p) => ({ value: p, label: t(`ttsProvider.${p}`) }));
  const telephonyProviderOptions: SelectOption[] = [
    { value: "twilio_byok", label: t("telephonyProvider.twilio_byok") },
    { value: "telnyx_byok", label: t("telephonyProvider.telnyx_byok") },
  ];

  const [agents, setAgents] = useState<VoiceAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [banner, setBanner] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const editingAgent = editingId ? agents.find((a) => a.id === editingId) : null;

  // Step-by-step wizard instead of one long scrolling form. Realtime mode
  // has no separate STT/TTS/keys stage (a single speech-to-speech model
  // handles it, configured inline in the "brain" step), so it skips the
  // "voicePipeline" step entirely rather than showing an empty one.
  const [step, setStep] = useState(0);
  // Whether the panel was opened via "New Voice Agent" vs. the edit pencil —
  // saveProgress() adopts an id after the very first auto-save either way,
  // so editingId alone can't tell "created this session" from "was already
  // an existing agent" for the final done banner's wording.
  const [isNewFlow, setIsNewFlow] = useState(true);
  const [stepSaved, setStepSaved] = useState(false);
  const formSteps = form.mode === "realtime" ? REALTIME_FORM_STEPS : PIPELINE_FORM_STEPS;
  const currentStep = formSteps[Math.min(step, formSteps.length - 1)];
  useEffect(() => {
    if (step >= formSteps.length) setStep(formSteps.length - 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.mode]);

  const [numberDialogAgent, setNumberDialogAgent] = useState<VoiceAgent | null>(null);
  const [browserTestAgent, setBrowserTestAgent] = useState<VoiceAgent | null>(null);
  const [numberProvider, setNumberProvider] = useState<"twilio_byok" | "telnyx_byok">("twilio_byok");
  const [numberResults, setNumberResults] = useState<{ phone_number: string; locality?: string }[]>([]);
  const [numberSearching, setNumberSearching] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [callsByAgent, setCallsByAgent] = useState<Record<string, VoiceAgentCall[]>>({});
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const [callsLoading, setCallsLoading] = useState(false);

  useEffect(() => {
    fetchAgents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchAgents() {
    setLoading(true);
    try {
      const data = await voiceAgentsApi.list();
      setAgents(data);
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("loadError") });
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setErrorMsg(null);
    setStep(0);
    setIsNewFlow(true);
    setFormOpen(true);
  }

  function openEdit(agent: VoiceAgent) {
    setEditingId(agent.id);
    setIsNewFlow(false);
    const isRealtime = agent.mode === "realtime";
    setForm({
      ...EMPTY_FORM,
      name: agent.name,
      use_case: agent.use_case,
      persona: agent.persona,
      greeting: agent.greeting || "",
      mode: agent.mode,
      // Realtime config lives in the same llm_provider/llm_model/tts_voice
      // columns as pipeline mode (see kin-backend's voice_agents schema) —
      // split back out into the form's separate realtime_* fields here so
      // switching tabs doesn't clobber either configuration.
      llm_provider: isRealtime ? EMPTY_FORM.llm_provider : agent.llm_provider,
      llm_model: isRealtime ? EMPTY_FORM.llm_model : agent.llm_model,
      stt_provider: agent.stt_provider,
      tts_provider: agent.tts_provider,
      tts_voice: isRealtime ? "" : agent.tts_voice || "",
      realtime_provider: isRealtime ? (agent.llm_provider as VoiceAgentRealtimeProvider) : EMPTY_FORM.realtime_provider,
      realtime_model: isRealtime ? agent.llm_model : EMPTY_FORM.realtime_model,
      realtime_voice: isRealtime ? agent.tts_voice || "" : "",
      tools: agent.tools || [],
    });
    setErrorMsg(null);
    setStep(0);
    setFormOpen(true);
  }

  // Realtime mode stores its provider/model/voice/key in the same
  // llm_provider/llm_model/tts_voice/llm_api_key fields pipeline mode uses
  // (see kin-backend's voice_agents schema) — stt/tts fields are simply
  // omitted, the backend ignores them for a realtime-mode agent.
  function buildAgentBody() {
    return form.mode === "realtime"
      ? {
          name: form.name.trim(),
          use_case: form.use_case,
          persona: form.persona.trim(),
          greeting: form.greeting.trim() || undefined,
          mode: form.mode,
          llm_provider: form.realtime_provider,
          llm_model: form.realtime_model.trim() || DEFAULT_REALTIME_MODEL_BY_PROVIDER[form.realtime_provider],
          // Unused in realtime mode — sent as-is so the request still
          // matches VoiceAgentCreateBody's shape; the backend ignores them.
          stt_provider: form.stt_provider,
          tts_provider: form.tts_provider,
          tts_voice: form.realtime_voice.trim() || undefined,
          tools: form.tools,
          llm_api_key: form.realtime_api_key.trim() || undefined,
        }
      : {
          name: form.name.trim(),
          use_case: form.use_case,
          persona: form.persona.trim(),
          greeting: form.greeting.trim() || undefined,
          mode: form.mode,
          llm_provider: form.llm_provider,
          llm_model: form.llm_model.trim() || DEFAULT_MODEL_BY_PROVIDER[form.llm_provider],
          stt_provider: form.stt_provider,
          tts_provider: form.tts_provider,
          tts_voice: form.tts_voice.trim() || undefined,
          tools: form.tools,
          llm_api_key: form.llm_api_key.trim() || undefined,
          stt_api_key: form.stt_api_key.trim() || undefined,
          tts_api_key: form.tts_api_key.trim() || undefined,
        };
  }

  // Auto-saves the current form state — called on every step transition
  // (not just the final one), so nothing is lost if the panel is closed
  // mid-way through. The first successful save for a brand-new agent
  // creates the draft and adopts its id (editingId) so every save after
  // that is a plain update against the same row.
  async function saveProgress(): Promise<boolean> {
    setActionLoading(true);
    setErrorMsg(null);
    const body = buildAgentBody();
    try {
      if (editingId) {
        const updated = await voiceAgentsApi.update(editingId, body);
        setAgents((prev) => prev.map((a) => (a.id === editingId ? updated : a)));
      } else {
        const created = await voiceAgentsApi.create(body);
        setAgents((prev) => [created, ...prev]);
        setEditingId(created.id);
      }
      return true;
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : t("saveFailed"));
      return false;
    } finally {
      setActionLoading(false);
    }
  }

  async function handleFinish(e: React.FormEvent) {
    e.preventDefault();
    const ok = await saveProgress();
    if (!ok) return;
    setBanner({ kind: "ok", text: isNewFlow ? t("created", { name: form.name.trim() }) : t("updated", { name: form.name.trim() }) });
    setFormOpen(false);
  }

  async function handleDelete(agent: VoiceAgent) {
    if (!confirm(t("deleteConfirm", { name: agent.name }))) return;
    setBusyId(agent.id);
    setBanner(null);
    try {
      await voiceAgentsApi.delete(agent.id);
      setAgents((prev) => prev.filter((a) => a.id !== agent.id));
      setBanner({ kind: "ok", text: t("deleted", { name: agent.name }) });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("deleteFailed") });
    } finally {
      setBusyId(null);
    }
  }

  async function handleSearchNumbers() {
    if (!numberDialogAgent) return;
    setNumberSearching(true);
    setNumberResults([]);
    try {
      const results = await voiceAgentsApi.searchNumbers(numberProvider);
      setNumberResults(results);
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("numberSearchFailed") });
    } finally {
      setNumberSearching(false);
    }
  }

  async function handleProvisionNumber(phoneNumber: string) {
    if (!numberDialogAgent) return;
    setActionLoading(true);
    try {
      const updated = await voiceAgentsApi.provisionNumber(numberDialogAgent.id, numberProvider, phoneNumber);
      setAgents((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
      setBanner({ kind: "ok", text: t("numberConnected", { number: phoneNumber }) });
      setNumberDialogAgent(null);
      setNumberResults([]);
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("numberProvisionFailed") });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleTestCall(agent: VoiceAgent) {
    const number = prompt(t("testCallPrompt"));
    if (!number) return;
    setBusyId(agent.id);
    try {
      await voiceAgentsApi.testCall(agent.id, number.trim());
      setBanner({ kind: "ok", text: t("testCallStarted", { number: number.trim() }) });
    } catch (e) {
      setBanner({ kind: "err", text: e instanceof Error ? e.message : t("testCallFailed") });
    } finally {
      setBusyId(null);
    }
  }

  async function toggleExpanded(agent: VoiceAgent) {
    const next = expandedId === agent.id ? null : agent.id;
    setExpandedId(next);
    if (next && !callsByAgent[agent.id]) {
      setCallsLoading(true);
      try {
        const calls = await voiceAgentsApi.calls(agent.id);
        setCallsByAgent((prev) => ({ ...prev, [agent.id]: calls }));
      } catch {
        // surfaced only via the empty state below
      } finally {
        setCallsLoading(false);
      }
    }
  }

  function toggleTool(name: string) {
    setForm((prev) => ({
      ...prev,
      tools: prev.tools.includes(name) ? prev.tools.filter((n) => n !== name) : [...prev.tools, name],
    }));
  }

  async function goNextStep() {
    // Only the "basics" step has hard requirements to leave — the rest
    // (brain/voicePipeline) have sensible defaults from EMPTY_FORM, so
    // there's nothing that would block moving forward.
    if (currentStep === "basics") {
      if (!form.name.trim()) { setErrorMsg(t("nameRequired")); return; }
      if (!form.persona.trim()) { setErrorMsg(t("personaRequired")); return; }
    }
    const ok = await saveProgress();
    if (!ok) return;
    setStepSaved(true);
    setTimeout(() => setStepSaved(false), 1500);
    setStep((s) => Math.min(s + 1, formSteps.length - 1));
  }

  function goPrevStep() {
    setErrorMsg(null);
    setStep((s) => Math.max(s - 1, 0));
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
                : "bg-destructive/10 border-destructive/25 text-destructive dark:border-destructive/40"
            }`}
          >
            {banner.kind === "ok" ? (
              <CheckCircle2 className="size-4 mt-0.5 shrink-0" />
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
          <p className="text-sm text-muted-foreground mt-1">{t("header.description")}</p>
        </div>
        <Button onClick={openCreate} className="cursor-pointer shrink-0 gap-2" title={t("settingsDialog.dialogTitle")}>
          <Settings className="size-4" />
          {t("header.addAgent")}
        </Button>
      </div>

      {formOpen && (
      <div className="bg-card border border-border p-6 rounded-2xl shadow-sm">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h3 className="text-base font-bold tracking-tight">
              {editingId ? t("formDialog.editTitle") : t("formDialog.createTitle")}
            </h3>
            <p className="text-sm text-muted-foreground mt-1">{t("formDialog.description")}</p>
          </div>
          <button
            type="button"
            onClick={() => !actionLoading && setFormOpen(false)}
            disabled={actionLoading}
            className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            aria-label={t("formDialog.cancel")}
          >
            <X className="size-4" />
          </button>
        </div>

        <TelephonyByokSection />
        <div className="border-t border-border my-5" />

        {/* Step progress */}
        <div className="flex items-center gap-1.5 mb-2">
          {formSteps.map((s, i) => (
            <div key={s} className={cn("h-1 flex-1 rounded-full transition-colors", i <= step ? "bg-foreground" : "bg-muted")} />
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground mb-4">
          {t("formDialog.stepProgress", { current: step + 1, total: formSteps.length })} · {t(`formDialog.stepName.${currentStep}`)}
        </p>

        <form onSubmit={handleFinish} className="space-y-5">
          {currentStep === "basics" && (
          <div>
            <span className="text-xs font-semibold text-foreground/80 block mb-2">{t("formDialog.basicsSection")}</span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label={t("formDialog.nameLabel")}>
                <input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={t("formDialog.namePlaceholder")}
                  disabled={actionLoading}
                  className={inputCls}
                  required
                />
              </Field>
              <Field label={t("formDialog.useCaseLabel")}>
                <Select
                  value={form.use_case}
                  onChange={(v) => setForm((f) => ({ ...f, use_case: v as VoiceAgentUseCase }))}
                  options={useCaseOptions}
                  disabled={actionLoading}
                />
              </Field>
            </div>
            <Field label={t("formDialog.personaLabel")} hint={t("formDialog.personaHint")}>
              <textarea
                value={form.persona}
                onChange={(e) => setForm((f) => ({ ...f, persona: e.target.value }))}
                placeholder={t("formDialog.personaPlaceholder")}
                disabled={actionLoading}
                className={`${textareaCls} min-h-[120px]`}
                required
              />
            </Field>
            <Field label={t("formDialog.greetingLabel")} hint={t("formDialog.greetingHint")}>
              <input
                value={form.greeting}
                onChange={(e) => setForm((f) => ({ ...f, greeting: e.target.value }))}
                placeholder={t("formDialog.greetingPlaceholder")}
                disabled={actionLoading}
                className={inputCls}
              />
            </Field>
          </div>
          )}

          {currentStep === "brain" && (
          <div>
            <span className="text-xs font-semibold text-foreground/80 block mb-1">{t("formDialog.brainSection")}</span>
            <p className="text-[11px] text-muted-foreground mb-3">{t("formDialog.modeHint")}</p>

            {/* Mode tabs */}
            <div className="grid grid-cols-2 gap-2 mb-4">
              {MODES.map((m) => {
                const active = form.mode === m;
                return (
                  <button
                    key={m}
                    type="button"
                    disabled={actionLoading}
                    onClick={() =>
                      setForm((f) => ({
                        ...f,
                        mode: m,
                        // Realtime is Google/OpenAI only — jump to a valid
                        // provider if the pipeline tab had a different one.
                        realtime_provider:
                          m === "realtime" && !REALTIME_PROVIDERS.includes(f.llm_provider as VoiceAgentRealtimeProvider)
                            ? f.realtime_provider
                            : m === "realtime"
                              ? (f.llm_provider as VoiceAgentRealtimeProvider)
                              : f.realtime_provider,
                      }))
                    }
                    className={`rounded-xl border p-3 text-left transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed ${
                      active ? "border-foreground/30 bg-muted/60 ring-1 ring-foreground/10" : "border-border hover:border-foreground/20"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{t(`mode.${m}`)}</span>
                    <span className="text-[11px] text-muted-foreground block mt-0.5">
                      {t(m === "realtime" ? "formDialog.modeRealtimeDescription" : "formDialog.modePipelineDescription")}
                    </span>
                  </button>
                );
              })}
            </div>

            {form.mode === "realtime" ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label={t("formDialog.realtimeProviderLabel")}>
                    <Select
                      value={form.realtime_provider}
                      onChange={(v) => {
                        const provider = v as VoiceAgentRealtimeProvider;
                        setForm((f) => ({
                          ...f,
                          realtime_provider: provider,
                          realtime_model: DEFAULT_REALTIME_MODEL_BY_PROVIDER[provider],
                          realtime_voice: "",
                        }));
                      }}
                      options={realtimeProviderOptions}
                      disabled={actionLoading}
                    />
                  </Field>
                  <Field label={t("formDialog.realtimeModelLabel")}>
                    <Select
                      value={
                        REALTIME_MODELS[form.realtime_provider].some((m) => m.value === form.realtime_model)
                          ? form.realtime_model
                          : "custom"
                      }
                      onChange={(v) =>
                        setForm((f) => ({ ...f, realtime_model: v === "custom" ? "" : v }))
                      }
                      options={REALTIME_MODELS[form.realtime_provider]}
                      disabled={actionLoading}
                    />
                    {!REALTIME_MODELS[form.realtime_provider].some(
                      (m) => m.value === form.realtime_model && m.value !== "custom",
                    ) && (
                      <div className="mt-2">
                        <input
                          value={form.realtime_model}
                          onChange={(e) => setForm((f) => ({ ...f, realtime_model: e.target.value }))}
                          placeholder="e.g. gemini-3.1-flash-live-preview"
                          disabled={actionLoading}
                          className={inputCls}
                        />
                      </div>
                    )}
                  </Field>
                </div>
                <Field label={t("formDialog.realtimeVoiceLabel")} hint={t("formDialog.ttsVoiceHint")}>
                  <Select
                    value={
                      REALTIME_VOICES[form.realtime_provider].some((v) => v.value === form.realtime_voice)
                        ? form.realtime_voice
                        : "custom"
                    }
                    onChange={(v) =>
                      setForm((f) => ({ ...f, realtime_voice: v === "custom" ? "" : v }))
                    }
                    options={REALTIME_VOICES[form.realtime_provider]}
                    disabled={actionLoading}
                  />
                  {!REALTIME_VOICES[form.realtime_provider].some(
                    (v) => v.value === form.realtime_voice && v.value !== "custom",
                  ) && (
                    <div className="mt-2">
                      <input
                        value={form.realtime_voice}
                        onChange={(e) => setForm((f) => ({ ...f, realtime_voice: e.target.value }))}
                        placeholder={t("formDialog.ttsVoicePlaceholder")}
                        disabled={actionLoading}
                        className={inputCls}
                      />
                    </div>
                  )}
                </Field>

                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 space-y-2">
                  <Field
                    label={`${form.realtime_provider.toUpperCase()} API Key`}
                    hint={editingAgent?.has_llm_api_key ? t("formDialog.keySavedHint") : undefined}
                  >
                    <input
                      type="password"
                      value={form.realtime_api_key}
                      onChange={(e) => setForm((f) => ({ ...f, realtime_api_key: e.target.value }))}
                      placeholder={editingAgent?.has_llm_api_key ? t("formDialog.keyPlaceholderSaved") : t("formDialog.keyPlaceholderEmpty")}
                      disabled={actionLoading}
                      className={inputCls}
                      autoComplete="off"
                    />
                  </Field>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* LLM config — STT/TTS moved to their own "voicePipeline" step */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label={t("formDialog.llmProviderLabel")}>
                    <Select
                      value={form.llm_provider}
                      onChange={(v) => {
                        const provider = v as VoiceAgentLlmProvider;
                        setForm((f) => ({ ...f, llm_provider: provider, llm_model: DEFAULT_MODEL_BY_PROVIDER[provider] }));
                      }}
                      options={llmProviderOptions}
                      disabled={actionLoading}
                    />
                  </Field>
                  <Field label={t("formDialog.llmModelLabel")}>
                    <Select
                      value={RECOMMENDED_MODELS[form.llm_provider].some(m => m.value === form.llm_model) ? form.llm_model : "custom"}
                      onChange={(v) => {
                        if (v === "custom") {
                          setForm((f) => ({ ...f, llm_model: "" }));
                        } else {
                          setForm((f) => ({ ...f, llm_model: v }));
                        }
                      }}
                      options={RECOMMENDED_MODELS[form.llm_provider]}
                      disabled={actionLoading}
                    />
                    {(!RECOMMENDED_MODELS[form.llm_provider].some(m => m.value === form.llm_model && m.value !== "custom")) && (
                      <div className="mt-2">
                        <input
                          value={form.llm_model}
                          onChange={(e) => setForm((f) => ({ ...f, llm_model: e.target.value }))}
                          placeholder="e.g. gpt-5.6-sol"
                          disabled={actionLoading}
                          className={inputCls}
                        />
                      </div>
                    )}
                  </Field>
                </div>
              </div>
            )}
          </div>
          )}

          {currentStep === "voicePipeline" && (
          <div className="space-y-4">
            <div>
              <span className="text-xs font-semibold text-foreground/80 block mb-1">{t("formDialog.voicePipelineSection")}</span>
              <p className="text-[11px] text-muted-foreground mb-3">{t("formDialog.voicePipelineHint")}</p>

              {/* STT config */}
              <Field label={t("formDialog.sttProviderLabel")}>
                <Select
                  value={form.stt_provider}
                  onChange={(v) => setForm((f) => ({ ...f, stt_provider: v as VoiceAgentSttProvider }))}
                  options={sttProviderOptions}
                  disabled={actionLoading}
                />
              </Field>

              {/* TTS config */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                <Field label={t("formDialog.ttsProviderLabel")}>
                  <Select
                    value={form.tts_provider}
                    onChange={(v) => setForm((f) => ({ ...f, tts_provider: v as VoiceAgentTtsProvider }))}
                    options={ttsProviderOptions}
                    disabled={actionLoading}
                  />
                </Field>
                <Field label={t("formDialog.ttsVoiceLabel")} hint={t("formDialog.ttsVoiceHint")}>
                  <Select
                    value={(RECOMMENDED_VOICES[form.tts_provider] || []).some(v => v.value === form.tts_voice) ? form.tts_voice : "custom"}
                    onChange={(v) => {
                      if (v === "custom") {
                        setForm((f) => ({ ...f, tts_voice: "" }));
                      } else {
                        setForm((f) => ({ ...f, tts_voice: v }));
                      }
                    }}
                    options={RECOMMENDED_VOICES[form.tts_provider] || [{ value: "custom", label: "Custom voice ID..." }]}
                    disabled={actionLoading}
                  />
                  {(!RECOMMENDED_VOICES[form.tts_provider]?.some(v => v.value === form.tts_voice && v.value !== "custom")) && (
                    <div className="mt-2">
                      <input
                        value={form.tts_voice}
                        onChange={(e) => setForm((f) => ({ ...f, tts_voice: e.target.value }))}
                        placeholder={t("formDialog.ttsVoicePlaceholder")}
                        disabled={actionLoading}
                        className={inputCls}
                      />
                    </div>
                  )}
                </Field>
              </div>
            </div>

          {/* API Keys Section — pipeline mode only; realtime's single key
              field lives inline in the realtime panel above. */}
          {form.mode === "pipeline" && (
            <div className="pt-3 border-t border-border/50">
              <span className="text-xs font-semibold text-foreground/80 block mb-1">Provider API Keys</span>
              <p className="text-[11px] text-muted-foreground mb-3">{t("formDialog.keysSectionHint")}</p>

              <div className="space-y-3">
                {/* LLM Key */}
                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 space-y-2">
                  <Field
                    label={`${form.llm_provider.toUpperCase()} API Key`}
                    hint={editingAgent?.has_llm_api_key ? t("formDialog.keySavedHint") : undefined}
                  >
                    <input
                      type="password"
                      value={form.llm_api_key}
                      onChange={(e) => setForm((f) => ({ ...f, llm_api_key: e.target.value }))}
                      placeholder={editingAgent?.has_llm_api_key ? t("formDialog.keyPlaceholderSaved") : t("formDialog.keyPlaceholderEmpty")}
                      disabled={actionLoading}
                      className={inputCls}
                      autoComplete="off"
                    />
                  </Field>
                </div>

                {/* STT Key */}
                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 space-y-2">
                  <Field
                    label={`${form.stt_provider.toUpperCase()} API Key`}
                    hint={KEY_FORMAT_HINTS[form.stt_provider] ?? (editingAgent?.has_stt_api_key ? t("formDialog.keySavedHint") : undefined)}
                  >
                    <input
                      type="password"
                      value={form.stt_api_key}
                      onChange={(e) => setForm((f) => ({ ...f, stt_api_key: e.target.value }))}
                      placeholder={editingAgent?.has_stt_api_key ? t("formDialog.keyPlaceholderSaved") : t("formDialog.keyPlaceholderEmpty")}
                      disabled={actionLoading}
                      className={inputCls}
                      autoComplete="off"
                    />
                  </Field>
                </div>

                {/* TTS Key */}
                <div className="rounded-xl border border-border/70 bg-muted/20 p-3.5 space-y-2">
                  <Field
                    label={`${form.tts_provider.toUpperCase()} API Key`}
                    hint={KEY_FORMAT_HINTS[form.tts_provider] ?? (editingAgent?.has_tts_api_key ? t("formDialog.keySavedHint") : undefined)}
                  >
                    <input
                      type="password"
                      value={form.tts_api_key}
                      onChange={(e) => setForm((f) => ({ ...f, tts_api_key: e.target.value }))}
                      placeholder={editingAgent?.has_tts_api_key ? t("formDialog.keyPlaceholderSaved") : t("formDialog.keyPlaceholderEmpty")}
                      disabled={actionLoading}
                      className={inputCls}
                      autoComplete="off"
                    />
                  </Field>
                </div>
              </div>
            </div>
          )}
          </div>
          )}

          {currentStep === "tools" && (
          <div>
            <span className="text-xs font-semibold text-foreground/80 block mb-2">{t("formDialog.toolsSection")}</span>
            <div className="space-y-2">
              {AVAILABLE_TOOLS.map((tool) => (
                <label key={tool} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.tools.includes(tool)}
                    onChange={() => toggleTool(tool)}
                    disabled={actionLoading}
                    className="size-4 rounded border-border cursor-pointer"
                  />
                  <span>{t(`tool.${tool}`)}</span>
                </label>
              ))}
            </div>
          </div>
          )}

          {errorMsg && (
            <div className="text-xs text-destructive flex items-start gap-1.5 bg-destructive/10 border border-destructive/20 rounded-xl p-3">
              <AlertCircle className="size-4 mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <DialogFooter>
            {stepSaved && (
              <span className="flex items-center gap-1 text-xs text-emerald-700 mr-auto">
                <CheckCircle2 className="size-3.5" /> {t("formDialog.stepSaved")}
              </span>
            )}
            {step > 0 && (
              <Button type="button" variant="outline" onClick={goPrevStep} disabled={actionLoading} className="cursor-pointer">
                {t("formDialog.back")}
              </Button>
            )}
            <Button type="button" variant="outline" onClick={() => setFormOpen(false)} disabled={actionLoading} className="cursor-pointer">
              {t("formDialog.cancel")}
            </Button>
            {step < formSteps.length - 1 ? (
              <Button type="button" onClick={goNextStep} disabled={actionLoading} className="cursor-pointer gap-1.5">
                {actionLoading && <Loader2 className="size-3.5 animate-spin" />}
                {t("formDialog.next")}
              </Button>
            ) : (
              <Button type="submit" disabled={actionLoading} className="cursor-pointer gap-1.5">
                {actionLoading && <Loader2 className="size-3.5 animate-spin" />}
                {isNewFlow ? t("formDialog.create") : t("formDialog.save")}
              </Button>
            )}
          </DialogFooter>
        </form>
      </div>
      )}

      {!formOpen && (loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border p-12 text-center max-w-lg mx-auto">
          <div className="size-12 rounded-2xl bg-muted grid place-items-center mx-auto mb-4 text-muted-foreground">
            <Phone className="size-6" />
          </div>
          <h3 className="text-sm font-semibold">{t("empty.title")}</h3>
          <p className="mt-2 text-xs text-muted-foreground max-w-sm mx-auto">{t("empty.body")}</p>
          <Button onClick={openCreate} variant="outline" className="mt-5 cursor-pointer">
            {t("empty.addAgent")}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {agents.map((agent) => {
            const isExpanded = expandedId === agent.id;
            const isBusy = busyId === agent.id;
            const calls = callsByAgent[agent.id] || [];

            return (
              <div key={agent.id} className="rounded-2xl border border-border bg-card overflow-hidden transition-shadow hover:shadow-sm">
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="size-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-100/50 dark:border-indigo-900/50 grid place-items-center shrink-0">
                      <Phone className="size-5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <h4 className="text-sm font-semibold tracking-tight text-foreground">{agent.name}</h4>
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-muted text-muted-foreground border border-border">
                          {t(`useCase.${agent.use_case}`)}
                        </span>
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${STATUS_STYLES[agent.status]}`}>
                          {t(`status.${agent.status}`)}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          {agent.phone_number ? (
                            <>
                              <Phone className="size-3.5" />
                              <code className="bg-muted px-1.5 py-0.5 rounded text-[11px] font-mono text-foreground/80">{agent.phone_number}</code>
                            </>
                          ) : (
                            <span className="italic">{t("noNumber")}</span>
                          )}
                        </span>
                        <span>
                          {agent.mode === "realtime"
                            ? t("brainSummaryRealtime", { llm: agent.llm_provider })
                            : t("brainSummary", { llm: agent.llm_provider, stt: agent.stt_provider, tts: agent.tts_provider })}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center flex-wrap">
                    <TestInBrowserButton onClick={() => setBrowserTestAgent(agent)} disabled={isBusy} />
                    {!agent.phone_number ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setNumberDialogAgent(agent);
                          setNumberResults([]);
                        }}
                        disabled={isBusy}
                        className="cursor-pointer gap-1.5"
                      >
                        <Phone className="size-3.5" />
                        {t("connectNumber")}
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleTestCall(agent)}
                        disabled={isBusy}
                        className="cursor-pointer gap-1.5"
                      >
                        {isBusy ? <Loader2 className="size-3.5 animate-spin" /> : <PhoneCall className="size-3.5" />}
                        {t("testCall")}
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => openEdit(agent)} disabled={isBusy} className="cursor-pointer">
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(agent)}
                      disabled={isBusy}
                      className="cursor-pointer text-destructive hover:bg-destructive/10"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => toggleExpanded(agent)} className="cursor-pointer">
                      {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                    </Button>
                  </div>
                </div>

                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: "auto" }}
                      exit={{ height: 0 }}
                      className="overflow-hidden border-t border-border bg-muted/20"
                    >
                      <div className="p-5 space-y-3">
                        <h5 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{t("callHistory")}</h5>
                        {callsLoading ? (
                          <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                            <Loader2 className="size-3.5 animate-spin" /> {t("loading")}
                          </div>
                        ) : calls.length === 0 ? (
                          <div className="text-xs text-muted-foreground py-2 italic flex items-center gap-1.5">
                            <PhoneOff className="size-3.5" /> {t("noCallsYet")}
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {calls.map((call) => {
                              const directionLabel =
                                call.direction === "inbound" ? t("inbound")
                                  : call.direction === "web_test" ? t("webTest")
                                  : t("outbound");
                              const hasTranscript = call.transcript && call.transcript.length > 0;
                              const callExpanded = expandedCallId === call.id;
                              return (
                                <div key={call.id} className="border border-border/60 bg-card rounded-xl p-3 flex flex-col gap-1">
                                  <button
                                    type="button"
                                    onClick={() => hasTranscript && setExpandedCallId(callExpanded ? null : call.id)}
                                    className={cn("flex items-center justify-between text-xs w-full text-left", hasTranscript && "cursor-pointer")}
                                  >
                                    <span className="font-semibold flex items-center gap-1.5">
                                      {directionLabel} — {call.from_number || call.to_number || "—"}
                                      {hasTranscript && (callExpanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />)}
                                    </span>
                                    <span className="text-muted-foreground">{new Date(call.started_at).toLocaleString()}</span>
                                  </button>
                                  {call.summary && <p className="text-xs text-muted-foreground">{call.summary}</p>}
                                  {call.outcome && (
                                    <span className="inline-flex w-fit items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/30">
                                      {t(`outcome.${call.outcome}`)}
                                    </span>
                                  )}
                                  {callExpanded && hasTranscript && (
                                    <div className="mt-2 max-h-56 overflow-y-auto space-y-1.5 border-t border-border/60 pt-2">
                                      {call.transcript.map((turn, i) => (
                                        <div key={i} className="text-xs">
                                          <span className="font-semibold text-foreground/80">{turn.role}: </span>
                                          <span className="text-muted-foreground">{turn.text}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      ))}

      {/* Connect phone number dialog */}
      <Dialog
        open={!!numberDialogAgent}
        onClose={() => !actionLoading && setNumberDialogAgent(null)}
        title={t("numberDialog.title")}
        description={t("numberDialog.description")}
        size="md"
      >
        <div className="space-y-4">
          <Field label={t("numberDialog.providerLabel")}>
            <Select
              value={numberProvider}
              onChange={(v) => setNumberProvider(v as "twilio_byok" | "telnyx_byok")}
              options={telephonyProviderOptions}
              disabled={actionLoading}
            />
          </Field>

          <p className="text-[11px] text-muted-foreground rounded-lg border border-border bg-muted/30 px-3 py-2">
            {t("numberDialog.byokHint")}
          </p>

          <Button type="button" variant="outline" onClick={handleSearchNumbers} disabled={numberSearching} className="cursor-pointer gap-1.5 w-full">
            {numberSearching && <Loader2 className="size-3.5 animate-spin" />}
            {t("numberDialog.search")}
          </Button>

          {numberResults.length > 0 && (
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {numberResults.map((n) => (
                <button
                  key={n.phone_number}
                  type="button"
                  onClick={() => handleProvisionNumber(n.phone_number)}
                  disabled={actionLoading}
                  className="w-full flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted cursor-pointer"
                >
                  <span className="font-mono">{n.phone_number}</span>
                  {n.locality && <span className="text-xs text-muted-foreground">{n.locality}</span>}
                </button>
              ))}
            </div>
          )}
        </div>
      </Dialog>

      <VoiceAgentTestCallDialog
        agent={browserTestAgent}
        open={!!browserTestAgent}
        onClose={() => setBrowserTestAgent(null)}
      />
    </div>
  );
}
