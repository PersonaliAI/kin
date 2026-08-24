import { createClient } from "@/lib/supabase/client";

export const BACKEND_URL = (() => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");
  return url;
})();

async function authHeader(): Promise<HeadersInit> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("not signed in");
  return { Authorization: `Bearer ${token}` };
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = await authHeader();
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      ...headers,
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const raw = await res.text();
    // FastAPI error bodies are {"detail": "..."} — surface just the message
    // instead of dumping raw JSON in front of the user.
    let message = raw;
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed?.detail === "string") message = parsed.detail;
    } catch {
      /* not JSON — use raw text as-is */
    }
    throw new Error(message || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export type ChatResponse = { reply: string; session_id: string; thinking?: string | null };

export type ChatSession = {
  session_id: string;
  title: string | null;
  message_count: number;
  first_at: string;
  last_at: string;
};

export async function sendChat(args: {
  text: string;
  audio?: Blob | null;
  sessionId?: string;
}): Promise<ChatResponse> {
  const fd = new FormData();
  fd.append("text", args.text ?? "");
  if (args.sessionId) fd.append("session_id", args.sessionId);
  if (args.audio) fd.append("audio", args.audio, "voice.webm");

  const headers = await authHeader();
  const res = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers,
    body: fd,
  });
  if (!res.ok) {
    const raw = await res.text();
    let message = raw;
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed?.detail === "string") message = parsed.detail;
    } catch {
      /* not JSON — use raw text as-is */
    }
    throw new Error(message || `Chat request failed (${res.status})`);
  }
  return res.json();
}

export const chatSessions = {
  list: () => api<{ sessions: ChatSession[] }>("/api/chat/sessions"),
  delete: (id: string) => api<{ status: string }>(`/api/chat/sessions/${id}`, { method: "DELETE" }),
};

// ---- Direct document upload (web chat paperclip) -------------------------

export type UploadedDoc = {
  status: "indexed" | "failed";
  file_name: string;
  chunk_count: number;
  document_id?: string;
  error?: string | null;
};

export async function uploadDocument(file: File): Promise<UploadedDoc> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const headers = await authHeader();
  const res = await fetch(`${BACKEND_URL}/api/documents/upload`, {
    method: "POST",
    headers,
    body: fd,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`upload failed (${res.status}): ${err}`);
  }
  return res.json();
}

// ---- Kin Flow (chat-built automations) -----------------------------------

export type FlowSummary = {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "active" | "paused" | "archived";
  missing_credentials: MissingCredential[];
  last_run_at: string | null;
  last_run_status: string | null;
  total_runs: number;
  updated_at: string;
};

export type MissingCredential = {
  integration: string;
  name?: string;
  auth_type: "oauth_passthrough" | "api_key";
  provider?: string;
  fields?: { name: string; label: string; help?: string }[];
  hint: string;
  connect_url: string;
};

export type FlowDsl = {
  trigger?: { type: string; config?: Record<string, unknown> } | null;
  nodes: Array<{
    id: string;
    integration: string;
    action: string;
    args?: Record<string, unknown>;
    label?: string;
  }>;
  // Edge tuple: [from, to] or [from, to, branch] where branch is 'true'/'false'
  // for logic.if outputs.
  edges: Array<[string, string] | [string, string, string]>;
};

export type FlowDetail = FlowSummary & { dsl: FlowDsl };

export type FlowRun = {
  id: string;
  flow_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "dead" | "cancelled";
  triggered_by: string;
  started_at: string | null;
  finished_at: string | null;
  error_summary: string | null;
  created_at: string;
};

export type FlowStep = {
  id: string;
  run_id: string;
  node_id: string;
  integration_slug: string | null;
  action: string | null;
  attempt: number;
  status: string;
  input: unknown;
  output: unknown;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
};

// Events from the streaming /build endpoint
export type FlowBuildEvent =
  | { type: "phase"; label: string }
  | { type: "tool"; name: string; args: Record<string, unknown> }
  | { type: "result"; name: string; result: unknown }
  | { type: "reply"; text: string }
  | { type: "missing_credentials"; missing: MissingCredential[] }
  | { type: "warning"; message: string }
  | { type: "error"; message: string }
  | { type: "done"; trace?: unknown[] }
  | { type: "finished" };

export type IntegrationSummary = {
  slug: string;
  name: string;
  description: string;
  category: string;
  source: "builtin" | "community" | "verified";
  icon_url: string | null;
  install_count: number;
  rating_sum: number;
  rating_count: number;
};

export const flows = {
  list: () => api<{ flows: FlowSummary[] }>("/api/flows"),
  create: (name: string, description?: string) =>
    api<FlowDetail>("/api/flows", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  get: (id: string) => api<FlowDetail>(`/api/flows/${id}`),
  update: (id: string, body: Partial<{ name: string; description: string; dsl: FlowDsl; status: string }>) =>
    api<FlowDetail>(`/api/flows/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: (id: string) =>
    api<{ status: string }>(`/api/flows/${id}`, { method: "DELETE" }),
  build: (id: string, message: string, history?: { role: string; content: string }[]) =>
    api<{ reply: string; trace: unknown[]; missing_credentials?: MissingCredential[] }>(
      `/api/flows/${id}/build`,
      {
        method: "POST",
        body: JSON.stringify({ message, history }),
      },
    ),
  buildStream: async function* (
    id: string,
    message: string,
    history?: { role: string; content: string }[],
  ): AsyncGenerator<FlowBuildEvent> {
    const headers = await authHeader();
    const res = await fetch(`${BACKEND_URL}/api/flows/${id}/build-stream`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    if (!res.ok || !res.body) {
      const err = await res.text();
      throw new Error(`stream failed (${res.status}): ${err}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const dataLine = part.split("\n").find((l) => l.startsWith("data:"));
        if (!dataLine) continue;
        try {
          yield JSON.parse(dataLine.slice(5).trim()) as FlowBuildEvent;
        } catch {
          /* malformed event */
        }
      }
    }
  },
  run: (id: string, triggerPayload?: Record<string, unknown>) =>
    api<FlowRun>(`/api/flows/${id}/run`, {
      method: "POST",
      body: JSON.stringify({ trigger_payload: triggerPayload || {} }),
    }),
  runs: (id: string) =>
    api<{ runs: FlowRun[] }>(`/api/flows/${id}/runs`),
};

export const flowRuns = {
  get: (id: string) =>
    api<{ run: FlowRun; steps: FlowStep[] }>(`/api/flow-runs/${id}`),
  retryFrom: (runId: string, nodeId: string) =>
    api<{ status: string }>(`/api/flow-runs/${runId}/retry-from/${nodeId}`, {
      method: "POST",
    }),
};

export const integrationsCatalog = {
  list: (category?: string) =>
    api<{ integrations: IntegrationSummary[] }>(
      `/api/integrations-catalog${category ? `?category=${category}` : ""}`,
    ),
  get: (slug: string) =>
    api<IntegrationSummary & { manifest: unknown }>(`/api/integrations-catalog/${slug}`),
};

export const flowCredentials = {
  list: () =>
    api<{ credentials: Array<{ integration_slug: string; auth_type: string; expires_at: string | null; updated_at: string }> }>(
      "/api/flow-credentials",
    ),
  save: (integrationSlug: string, payload: Record<string, unknown>) =>
    api<{ status: string }>("/api/flow-credentials", {
      method: "POST",
      body: JSON.stringify({ integration_slug: integrationSlug, payload }),
    }),
  delete: (slug: string) =>
    api<{ status: string }>(`/api/flow-credentials/${slug}`, { method: "DELETE" }),
};

export type FlowLimits = {
  plan: string;
  limits: { max_flows: number; max_runs_per_month: number; can_publish: number };
  usage: { active_flows: number; runs_this_month: number };
};

export const flowLimits = {
  get: () => api<FlowLimits>("/api/flow-limits"),
};

// Marketplace / install / publish / review
export const marketplace = {
  installs:    () => api<{ installs: { integration_slug: string; installed_at: string }[] }>("/api/integration-installs"),
  install:     (slug: string) => api<{ status: string }>(`/api/integration-installs/${slug}`, { method: "POST" }),
  uninstall:   (slug: string) => api<{ status: string }>(`/api/integration-installs/${slug}`, { method: "DELETE" }),
  review:      (slug: string, rating: number, comment?: string) =>
    api<{ status: string }>(`/api/integrations-catalog/${slug}/review`, {
      method: "POST",
      body: JSON.stringify({ rating, comment }),
    }),
  publish:     (body: { slug?: string; name?: string; description?: string; category?: string; manifest?: unknown; icon_url?: string; publisher_name?: string; openapi_url?: string }) =>
    api<IntegrationSummary & { status: string }>("/api/integrations-publish", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// Flow form trigger (auto-hosted public forms)
export type FormFieldDef = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  placeholder?: string | null;
  help?: string | null;
  options?: string[] | null;
};

export type FlowForm = {
  flow_id: string;
  slug: string;
  title: string;
  fields: FormFieldDef[];
  submit_label: string;
  success_message: string;
};

export const flowForms = {
  ensure: (flowId: string) =>
    api<FlowForm>(`/api/flows/${flowId}/form`),
  update: (
    flowId: string,
    body: Partial<{
      title: string;
      fields: FormFieldDef[];
      submit_label: string;
      success_message: string;
    }>,
  ) =>
    api<FlowForm>(`/api/flows/${flowId}/form`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};

// ---- Integrations ---------------------------------------------------------

export type CalendarEvent = {
  id: string;
  source?: "google" | "microsoft";
  summary: string;
  location: string | null;
  html_link: string | null;
  start: string | null;
  end: string | null;
  all_day: boolean;
  attendees: string[];
};

export type GmailMessage = {
  id: string;
  source?: "google" | "microsoft";
  thread_id: string;
  from: string;
  subject: string;
  snippet: string;
  received_at: string;
  unread: boolean;
  url: string;
};

export type ExtraGoogleAccount = {
  id: string;
  label: string | null;
  google_email: string | null;
  created_at: string;
};

export const integrations = {
  startGoogleConnect: (mode: "primary" | "add" = "primary") =>
    api<{ url: string }>(`/api/integrations/google/start?mode=${mode}`, { method: "POST" }),
  disconnectGoogle: () =>
    api<{ status: string }>("/api/integrations/google/disconnect", {
      method: "POST",
    }),
  extraGoogleAccounts: () =>
    api<{ accounts: ExtraGoogleAccount[]; max: number; used: number }>(
      "/api/integrations/google/accounts",
    ),
  disconnectExtraGoogleAccount: (id: string) =>
    api<{ status: string }>(`/api/integrations/google/accounts/${id}`, {
      method: "DELETE",
    }),
  startMicrosoftConnect: () =>
    api<{ url: string }>("/api/integrations/microsoft/start", { method: "POST" }),
  disconnectMicrosoft: () =>
    api<{ status: string }>("/api/integrations/microsoft/disconnect", {
      method: "POST",
    }),
  calendar: () =>
    api<{ events: CalendarEvent[]; connected: { google: boolean; microsoft: boolean } }>(
      "/api/integrations/calendar/events",
    ),
  gmail: () =>
    api<{ messages: GmailMessage[]; connected: { google: boolean; microsoft: boolean } }>(
      "/api/integrations/gmail/messages",
    ),
  tasks: () =>
    api<{
      tasks: (Task & {
        source: "kin" | "google" | "microsoft";
        external_id?: string;
        list_id?: string;
      })[];
      connected: { google: boolean; microsoft: boolean };
    }>("/api/integrations/tasks"),
  toggleExternalTask: (
    source: "google" | "microsoft",
    externalId: string,
    completed: boolean,
    listId?: string,
  ) =>
    api<{ id: string; status: string }>(
      `/api/integrations/tasks/${source}/${encodeURIComponent(externalId)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ completed, list_id: listId }),
      },
    ),
  contacts: () =>
    api<{
      kin: KinContact[];
      external: GoogleContact[];
      connected: { google: boolean; microsoft: boolean };
    }>("/api/integrations/contacts"),
};

export type KinContact = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  notes: string | null;
  updated_at: string | null;
};

// ---- Social scheduling (Postiz-equivalent) --------------------------------

export type SocialPost = {
  id: string;
  user_id: string;
  integration_slug: string;
  social_account_id?: string | null;
  group_id?: string | null;
  state: "draft" | "queue" | "published" | "failed";
  publish_date: string;
  content: string;
  image_url?: string | null;
  parent_post_id?: string | null;
  release_id?: string | null;
  release_url?: string | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type SocialAutoPost = {
  id: string;
  title: string;
  url: string;
  active: boolean;
  generate_content: boolean;
  integrations: string[];
  last_processed_url?: string | null;
};

export type SocialTag = { id: string; name: string; color: string };

export type SocialMediaAsset = {
  name: string;
  url: string;
  size: number;
  type?: string;
  created_at?: string;
};

export type SocialIntegration = {
  slug: string;
  name: string;
  connected: boolean;
  connectedAt: string | null;
  avatarUrl: string | null;
  handle: string | null;
  displayName: string | null;
  oauth2: boolean;
  real: boolean;
};

// A real connected account — unlike SocialIntegration (one row per
// supported platform), there can be multiple SocialAccount rows for the
// same slug (e.g. two X accounts).
export type SocialAccount = {
  id: string;
  slug: string;
  name: string;
  displayName: string | null;
  handle: string | null;
  avatarUrl: string | null;
  connectedAt: string;
};

export const socialApi = {
  posts: {
    list: (state?: SocialPost["state"]) =>
      api<SocialPost[]>(`/api/social/posts${state ? `?state=${state}` : ""}`),
    create: (body: {
      social_account_ids: string[];
      content: string;
      content_overrides?: Record<string, string>;
      publish_date: string;
      state?: "draft" | "queue";
      image_url?: string | null;
      parent_post_id?: string | null;
      settings?: Record<string, unknown> | null;
      repeat_interval?: "daily" | "weekly" | "monthly" | null;
      repeat_count?: number | null;
    }) => api<SocialPost | SocialPost[]>("/api/social/posts", { method: "POST", body: JSON.stringify(body) }),
    update: (
      id: string,
      body: Partial<Pick<SocialPost, "content" | "publish_date" | "state" | "image_url">> & {
        settings?: Record<string, unknown> | null;
      },
    ) => api<SocialPost>(`/api/social/posts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id: string) => api<{ success: boolean }>(`/api/social/posts/${id}`, { method: "DELETE" }),
  },
  autoPosts: {
    list: () => api<SocialAutoPost[]>("/api/social/auto-posts"),
    create: (body: {
      title: string;
      url: string;
      active?: boolean;
      generate_content?: boolean;
      integrations?: string[];
    }) => api<SocialAutoPost>("/api/social/auto-posts", { method: "POST", body: JSON.stringify(body) }),
    delete: (id: string) => api<{ success: boolean }>(`/api/social/auto-posts/${id}`, { method: "DELETE" }),
  },
  tags: {
    list: () => api<SocialTag[]>("/api/social/tags"),
    create: (body: { name: string; color?: string }) =>
      api<SocialTag>("/api/social/tags", { method: "POST", body: JSON.stringify(body) }),
  },
  analytics: {
    summary: () =>
      api<{ impressions: number; likes: number; reposts: number; clicks: number }>(
        "/api/social/analytics",
      ),
    timeseries: (days: number = 7) =>
      api<{
        series: { date: string; impressions: number; likes: number; reposts: number; comments: number; clicks: number }[];
      }>(`/api/social/analytics/timeseries?days=${days}`),
  },
  media: {
    list: () => api<SocialMediaAsset[]>("/api/social/media"),
    upload: async (file: File): Promise<SocialMediaAsset> => {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const headers = await authHeader();
      const res = await fetch(`${BACKEND_URL}/api/social/media`, { method: "POST", headers, body: fd });
      if (!res.ok) throw new Error(`upload failed (${res.status})`);
      return res.json();
    },
  },
  integrations: {
    list: () => api<SocialIntegration[]>("/api/social/integrations"),
    start: (slug: string) =>
      api<{ url: string }>(`/api/social/integrations/${slug}/start`, { method: "POST" }),
    connectManual: (slug: string, form: Record<string, unknown>) =>
      api<{ status: string }>(`/api/social/integrations/${slug}/connect-manual`, {
        method: "POST",
        body: JSON.stringify(form),
      }),
    disconnect: (slug: string) =>
      api<{ status: string }>(`/api/social/integrations/${slug}/disconnect`, { method: "POST" }),
  },
  accounts: {
    list: () => api<SocialAccount[]>("/api/social/accounts"),
    disconnect: (accountId: string) =>
      api<{ status: string }>(`/api/social/accounts/${accountId}/disconnect`, { method: "POST" }),
  },
  webhook: {
    get: () => api<{ id: string; url: string; active: boolean; created_at: string } | null>("/api/social/webhook"),
    save: (url: string, active: boolean = true) =>
      api<{ status: string; secret: string }>("/api/social/webhook", {
        method: "POST",
        body: JSON.stringify({ url, active }),
      }),
    delete: () => api<{ status: string }>("/api/social/webhook", { method: "DELETE" }),
  },
  generate: (body: { prompt: string; tone?: string; kind?: "outlines" | "post"; url?: string }) =>
    api<{ outlines?: string[]; content?: string }>("/api/social/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// ---- Settings -------------------------------------------------------------

export type SignatureLink = { label?: string; url: string };

export const settings = {
  update: (patch: {
    display_name?: string;
    timezone?: string;
    country?: string | null;
    system_prompt?: string;
    briefing_enabled?: boolean;
    briefing_time?: string;
    marketing_opt_in?: boolean;
    memory_enabled?: boolean;
    confirm_before_write?: boolean;
    email_followups_enabled?: boolean;
    email_signature_enabled?: boolean;
    email_signature_name?: string;
    email_signature_title?: string;
    email_signature_phone?: string;
    email_signature_links?: SignatureLink[];
    preferred_provider?: string;
    preferred_model?: string | null;
  }) =>
    api<{ status: string }>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
};

export async function exportMyData(): Promise<void> {
  const headers = await authHeader();
  const res = await fetch(`${BACKEND_URL}/api/export`, { headers });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] || "kin-export.json";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---- Usage / quota --------------------------------------------------------

export type Task = {
  id: string;
  title: string;
  description: string | null;
  status: "todo" | "in_progress" | "done";
  priority: "low" | "medium" | "high";
  due_date: string | null;
  updated_at: string | null;
};

export type Usage = {
  plan: string;
  used: number;
  limit: number;
  remaining: number;
  resets_at: string;
  tokens?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
};

export const usageApi = {
  current: () => api<Usage>("/api/usage"),
};

// ---- Executive: API keys, webhooks, account manager, prompt tuning -------

export type KinApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  revoked: boolean;
  request_count: number;
  last_used_at: string | null;
  created_at: string;
};

export const kinApiKeysApi = {
  list: () => api<{ api_keys: KinApiKey[] }>("/api/kin/api-keys"),
  create: (name: string) =>
    api<KinApiKey & { key: string }>("/api/kin/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  revoke: (id: string) =>
    api<{ status: string }>(`/api/kin/api-keys/${id}`, { method: "DELETE" }),
};

export type KinWebhook = {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
};

export type KinWebhookDelivery = {
  id: string;
  event: string;
  status: "pending" | "delivered" | "failed";
  response_code: number | null;
  last_error: string | null;
  created_at: string;
  delivered_at: string | null;
};

export const kinWebhooksApi = {
  list: () => api<{ webhooks: KinWebhook[] }>("/api/kin/webhooks"),
  create: (url: string, events: string[] = ["message.created"]) =>
    api<KinWebhook & { secret: string }>("/api/kin/webhooks", {
      method: "POST",
      body: JSON.stringify({ url, events }),
    }),
  setActive: (id: string, active: boolean) =>
    api<{ status: string }>(`/api/kin/webhooks/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    }),
  delete: (id: string) =>
    api<{ status: string }>(`/api/kin/webhooks/${id}`, { method: "DELETE" }),
  deliveries: (id: string) =>
    api<{ deliveries: KinWebhookDelivery[] }>(`/api/kin/webhooks/${id}/deliveries`),
};

export type AccountManager = {
  name: string;
  email: string;
  calendly_url: string | null;
  assigned: boolean;
};

export const accountManagerApi = {
  get: () => api<AccountManager>("/api/kin/account-manager"),
};

export type PromptTuningStatus = { eligible: boolean; next_eligible_at: string | null };
export type PromptTuningSuggestion = { suggested_prompt: string; rationale: string };

export const promptTuningApi = {
  status: () => api<PromptTuningStatus>("/api/kin/prompt-tuning/status"),
  suggest: () => api<PromptTuningSuggestion>("/api/kin/prompt-tuning/suggest", { method: "POST" }),
  apply: (system_prompt: string) =>
    api<{ status: string }>("/api/kin/prompt-tuning/apply", {
      method: "POST",
      body: JSON.stringify({ system_prompt }),
    }),
};

// ---- Google Contacts ------------------------------------------------------

export type GoogleContact = {
  resource_name: string;
  source?: "google" | "microsoft";
  name: string;
  given_name: string;
  family_name: string;
  emails: string[];
  phones: string[];
  company: string;
  title?: string;
  job_title?: string;
  notes: string;
};

export const googleContactsApi = {
  list: (query: string = "") =>
    api<{ connected: boolean; contacts: GoogleContact[]; error?: string }>(
      `/api/google/contacts${query ? `?query=${encodeURIComponent(query)}` : ""}`,
    ),
  create: (payload: {
    name: string;
    email?: string | null;
    phone?: string | null;
    company?: string | null;
    notes?: string | null;
  }) =>
    api<GoogleContact>("/api/google/contacts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ---- Microsoft Contacts -----------------------------------------------
// Notes aren't supported here — Microsoft Graph's contact resource has no
// equivalent field wired up on the backend (unlike Google's biographies).

export const microsoftContactsApi = {
  create: (payload: {
    name: string;
    email?: string | null;
    phone?: string | null;
    company?: string | null;
  }) =>
    api<GoogleContact>("/api/microsoft/contacts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ---- Memory ---------------------------------------------------------------

export type Memory = {
  id: string;
  content: string;
  kind: string | null;
  source_session: string | null;
  created_at: string;
};

export const memoryApi = {
  list: () => api<{ memories: Memory[] }>("/api/memory"),
  add: (content: string, kind: string = "fact") =>
    api<{ status: string }>("/api/memory", {
      method: "POST",
      body: JSON.stringify({ content, kind }),
    }),
  delete: (id: string) =>
    api<{ status: string }>(`/api/memory/${id}`, { method: "DELETE" }),
  wipe: () => api<{ status: string }>("/api/memory", { method: "DELETE" }),
};

// ---- Documents (Drive RAG) -----------------------------------------------

export type DriveDocument = {
  id: string;
  drive_file_id: string;
  file_name: string;
  mime_type: string | null;
  web_view_link: string | null;
  parent_folder_id: string | null;
  size_bytes: number | null;
  modified_at: string | null;
  indexed_at: string;
  chunk_count: number;
  status: "indexed" | "failed" | "pending";
  error: string | null;
};

export type DriveBrowseFile = {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number | null;
  modified_at: string | null;
  web_view_link: string | null;
  parent_folder_id: string | null;
  owner: string | null;
};

export const documentsApi = {
  list: () => api<{ documents: DriveDocument[] }>("/api/documents"),
  indexFolder: (
    folderIdOrUrl: string,
    maxFiles = 50,
    source: "gdrive" | "onedrive" = "gdrive",
  ) =>
    api<{ status: string; folder_id: string; source: string }>(
      "/api/documents/index-folder",
      {
        method: "POST",
        body: JSON.stringify({
          folder_id_or_url: folderIdOrUrl,
          max_files: maxFiles,
          source,
        }),
      },
    ),
  indexFiles: (file_ids: string[]) =>
    api<{ status: string; count: number }>("/api/documents/index-files", {
      method: "POST",
      body: JSON.stringify({ file_ids }),
    }),
  delete: (documentId: string) =>
    api<{ status: string }>(`/api/documents/${documentId}`, {
      method: "DELETE",
    }),
  wipe: (status?: "indexed" | "failed" | "pending") =>
    api<{ status: string }>(
      `/api/documents${status ? `?status=${status}` : ""}`,
      { method: "DELETE" },
    ),
  browse: (params: { folder_id?: string; query?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.folder_id) qs.set("folder_id", params.folder_id);
    if (params.query) qs.set("query", params.query);
    return api<{ files: DriveBrowseFile[]; next_page_token: string | null }>(
      `/api/documents/browse${qs.toString() ? `?${qs}` : ""}`,
    );
  },
};

// ---- Model Context Protocol (MCP) -----------------------------------------

export type McpToolProperty = {
  type?: string;
  description?: string;
  [key: string]: unknown;
};

export type McpTool = {
  name: string;
  description?: string;
  inputSchema?: {
    properties?: Record<string, McpToolProperty>;
    required?: string[];
  };
};

export type McpServer = {
  id: string;
  user_id: string;
  name: string;
  url: string;
  headers: Record<string, string>;
  tools: McpTool[];
  oauth_flow_status: "none" | "awaiting_authorization" | "authorized";
  oauth_client_id?: string;
  oauth_client_secret?: string;
  oauth_auth_url?: string;
  oauth_token_url?: string;
  oauth_scopes?: string;
  created_at: string;
  updated_at: string;
};

export const mcpApi = {
  list: () => api<McpServer[]>("/api/mcp"),
  create: (
    name: string,
    url: string,
    headers?: Record<string, string>,
    oauth_client_id?: string,
    oauth_client_secret?: string,
    oauth_auth_url?: string,
    oauth_token_url?: string,
    oauth_scopes?: string
  ) =>
    api<McpServer>("/api/mcp", {
      method: "POST",
      body: JSON.stringify({
        name,
        url,
        headers,
        oauth_client_id,
        oauth_client_secret,
        oauth_auth_url,
        oauth_token_url,
        oauth_scopes,
      }),
    }),
  test: (id: string) =>
    api<{ status: string; tools: McpTool[] }>(`/api/mcp/${id}/test`, {
      method: "POST",
    }),
  delete: (id: string) =>
    api<{ status: string }>(`/api/mcp/${id}`, { method: "DELETE" }),
  oauthStart: (id: string, redirectUri: string) =>
    api<{ url: string }>(`/api/mcp/${id}/oauth/start?redirect_uri=${encodeURIComponent(redirectUri)}`, {
      method: "POST",
    }),
};

// ---- Voice Agents ----------------------------------------------------------

export type VoiceAgentLlmProvider = "openai" | "anthropic" | "google" | "groq" | "xai";
export type VoiceAgentSttProvider = "deepgram" | "google" | "azure" | "assemblyai" | "openai";
export type VoiceAgentTtsProvider = "elevenlabs" | "cartesia" | "rime" | "lmnt" | "azure";
export type VoiceAgentUseCase = "sales" | "receptionist" | "custom";
export type VoiceAgentTelephonyProvider = "twilio_managed" | "telnyx_managed" | "byo_sip";
export type VoiceAgentStatus = "draft" | "provisioning" | "active" | "paused" | "error";

export type VoiceAgent = {
  id: string;
  user_id: string;
  name: string;
  use_case: VoiceAgentUseCase;
  persona: string;
  greeting: string | null;
  llm_provider: VoiceAgentLlmProvider;
  llm_model: string;
  stt_provider: VoiceAgentSttProvider;
  tts_provider: VoiceAgentTtsProvider;
  tts_voice: string | null;
  tools: string[];
  telephony_provider: VoiceAgentTelephonyProvider | null;
  phone_number: string | null;
  status: VoiceAgentStatus;
  inbound_enabled: boolean;
  created_at: string;
  updated_at: string;
  // BYOK — booleans only; the backend never returns the actual key.
  has_llm_api_key: boolean;
  has_stt_api_key: boolean;
  has_tts_api_key: boolean;
};

export type VoiceAgentCall = {
  id: string;
  voice_agent_id: string;
  direction: "inbound" | "outbound";
  from_number: string | null;
  to_number: string | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  transcript: { role: string; text: string }[];
  summary: string | null;
  outcome: string | null;
  recording_url: string | null;
  status: "in_progress" | "completed" | "failed";
};

export type VoiceAgentCreateBody = {
  name: string;
  use_case: VoiceAgentUseCase;
  persona: string;
  greeting?: string;
  llm_provider: VoiceAgentLlmProvider;
  llm_model: string;
  stt_provider: VoiceAgentSttProvider;
  tts_provider: VoiceAgentTtsProvider;
  tts_voice?: string;
  tools: string[];
  // BYOK — plaintext over HTTPS to your own backend, same as the existing
  // text-chat BYOK flow. Omit/leave blank to keep whatever's already saved.
  llm_api_key?: string;
  stt_api_key?: string;
  tts_api_key?: string;
};

export const voiceAgentsApi = {
  list: () => api<VoiceAgent[]>("/api/voice-agents"),
  create: (body: VoiceAgentCreateBody) =>
    api<VoiceAgent>("/api/voice-agents", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: Partial<VoiceAgentCreateBody & { inbound_enabled: boolean }>) =>
    api<VoiceAgent>(`/api/voice-agents/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (id: string) => api<{ status: string }>(`/api/voice-agents/${id}`, { method: "DELETE" }),
  calls: (id: string) => api<VoiceAgentCall[]>(`/api/voice-agents/${id}/calls`),
  searchNumbers: (provider: VoiceAgentTelephonyProvider, country = "US", areaCode?: string) =>
    api<{ phone_number: string; locality?: string; region?: string }[]>(
      `/api/voice-agents/available-numbers?provider=${provider}&country=${country}${areaCode ? `&area_code=${areaCode}` : ""}`,
    ),
  provisionNumber: (id: string, telephony_provider: "twilio_managed" | "telnyx_managed", phone_number: string) =>
    api<VoiceAgent>(`/api/voice-agents/${id}/provision-number`, {
      method: "POST",
      body: JSON.stringify({ telephony_provider, phone_number }),
    }),
  testCall: (id: string, to_number: string) =>
    api<{ status: string; room_name: string }>(`/api/voice-agents/${id}/test-call`, {
      method: "POST",
      body: JSON.stringify({ to_number }),
    }),
};

// ---- Scheduled Tasks -----------------------------------------------------

export type ScheduledTask = {
  id: string;
  user_id: string;
  name: string;
  prompt: string;
  cron_expression: string;
  timezone: string;
  channel: "web" | "email";
  is_active: boolean;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export const scheduleApi = {
  list: () => api<ScheduledTask[]>("/api/schedule"),
  create: (body: {
    name: string;
    prompt: string;
    cron_expression: string;
    timezone?: string;
    channel?: "web" | "email";
  }) =>
    api<ScheduledTask>("/api/schedule", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (
    id: string,
    body: Partial<{
      name: string;
      prompt: string;
      cron_expression: string;
      timezone: string;
      channel: "web" | "email";
      is_active: boolean;
    }>,
  ) =>
    api<ScheduledTask>(`/api/schedule/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: (id: string) =>
    api<{ status: string }>(`/api/schedule/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    api<{ status: string; reply: string; detail?: string }>(
      `/api/schedule/${id}/test`,
      { method: "POST" },
    ),
};

// ---- LLM providers / models / BYOK keys / usage ---------------------------

export type LlmModel = { id: string; label: string };

export type LlmProvider = {
  id: string;
  label: string;
  byok_required: boolean;
  has_key: boolean;
  models: LlmModel[];
};

export const llmModelsApi = {
  list: () => api<{ providers: LlmProvider[] }>("/api/llm-models"),
};

export type LlmKey = { provider: string; updated_at: string };

export const llmKeysApi = {
  list: () => api<{ keys: LlmKey[] }>("/api/llm-keys"),
  save: (provider: string, apiKey: string) =>
    api<{ status: string }>("/api/llm-keys", {
      method: "POST",
      body: JSON.stringify({ provider, api_key: apiKey }),
    }),
  delete: (provider: string) =>
    api<{ status: string }>(`/api/llm-keys/${provider}`, { method: "DELETE" }),
};

export type LlmUsageByModel = {
  provider: string;
  model: string;
  cost_usd: number;
  tokens: number;
  calls: number;
};

export type LlmUsageByFeature = {
  feature: string;
  cost_usd: number;
  tokens: number;
  calls: number;
};

export type LlmUsagePeriod = {
  total_cost_usd: number;
  total_tokens: number;
  unknown_cost_calls: number;
  by_model: LlmUsageByModel[];
  by_feature: LlmUsageByFeature[];
};

export type LlmUsage = {
  month: LlmUsagePeriod;
  last_7_days: LlmUsagePeriod;
};

export const llmUsageApi = {
  current: () => api<LlmUsage>("/api/usage/llm"),
};
