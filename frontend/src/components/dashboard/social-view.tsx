"use client";

import { useEffect, useRef, useState } from "react";
import { 
  Share2, Plus, Calendar, Clock, Send, BarChart3, Settings, Link, Sparkles, 
  Trash2, Radio, Check, X, RefreshCw, Layers, MessageSquare, AlertCircle, 
  ThumbsUp, Eye, Heart, MousePointerClick, MessageSquareCode, Image as ImageIcon,
  FolderOpen, Plug, Copy, CheckCheck, FileText, ChevronRight, BarChart2, Globe,
  MoreVertical, ChevronLeft, CalendarDays, List, Bold, Underline, Smile, ChevronDown,
  Lock, ArrowRight, Save, Calendar as CalendarIcon, Sliders, Hash, Rss
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, Field, inputCls } from "@/components/dashboard/dialog";
import { Select } from "@/components/ui/select";
import { FloatingPopover } from "@/components/ui/floating-popover";
import {
  socialApi,
  type SocialPost,
  type SocialAutoPost,
  type SocialAccount,
  type SocialMediaAsset as MediaAsset,
} from "@/lib/backend";

interface Tag {
  id: string;
  name: string;
  color: string;
}

type TabType = "launches" | "agent" | "media" | "analytics" | "integrations" | "feeds" | "plugs";

const LOGOS: Record<string, React.ReactNode> = {
  x: (
    <svg className="size-5 fill-current text-white" viewBox="0 0 24 24">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  ),
  linkedin: (
    <svg className="size-5 fill-current text-white" viewBox="0 0 24 24">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  ),
  instagram: (
    <svg className="size-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  ),
  facebook: (
    <svg className="size-5 fill-current text-white" viewBox="0 0 24 24">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  ),
  threads: (
    <svg className="size-5 fill-current text-white" viewBox="0 0 24 24">
      <path d="M12.03 0C5.396 0 .02 5.396.02 12.03c0 6.635 5.375 12.03 12.01 12.03 6.635 0 12.03-5.395 12.03-12.03C24.06 5.396 18.665 0 12.03 0zm5.111 16.516c-.521.849-1.282 1.489-2.28 1.916-.998.428-2.148.643-3.45.643-2.288 0-4.043-.65-5.267-1.951-1.223-1.301-1.835-3.097-1.835-5.387 0-2.261.603-4.032 1.808-5.312 1.206-1.281 2.915-1.921 5.127-1.921 1.79 0 3.256.402 4.397 1.207 1.141.804 1.767 1.96 1.88 3.468h-2.316c-.143-.889-.523-1.547-1.141-1.975-.618-.428-1.49-.643-2.617-.643-1.439 0-2.548.423-3.328 1.27-.78.847-1.17 2.083-1.17 3.707 0 1.636.379 2.871 1.136 3.706.757.836 1.821 1.254 3.192 1.254 1.733 0 2.915-.558 3.548-1.674v.898z" />
    </svg>
  ),
  youtube: (
    <svg className="size-5 fill-current text-white" viewBox="0 0 24 24">
      <path d="M23.498 6.163a3.003 3.003 0 0 0-2.11-2.107C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.388.511a3.002 3.002 0 0 0-2.11 2.107C0 8.053 0 12 0 12s0 3.947.502 5.837a3.003 3.003 0 0 0 2.11 2.107C4.495 20.455 12 20.455 12 20.455s7.505 0 9.388-.511a3.002 3.002 0 0 0 2.11-2.107C24 15.947 24 12 24 12s0-3.947-.502-5.837zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  ),
  tiktok: (
    <svg className="size-5 fill-current text-white" viewBox="0 0 24 24">
      <path d="M12.525.02c1.31-.032 2.614-.01 3.91-.01.08 1.543.914 2.895 2.228 3.7A8.139 8.139 0 0 0 24 4.887v4.066c-1.84-.047-3.562-.64-4.99-1.69-.026 4.316-.01 8.636-.02 12.95-.084 4.254-3.553 7.82-7.818 7.783A7.785 7.785 0 0 1 3.42 20.218a7.801 7.801 0 0 1 6.837-7.734c.005 1.343-.004 2.686.004 4.029a3.784 3.784 0 0 0-3.13 3.654 3.791 3.791 0 0 0 3.82 3.766 3.79 3.79 0 0 0 3.796-3.797c.01-4.707.003-9.414.007-14.122.016-2.02.003-4.04.01-6.06-.057.025-.114.03-.173.066z" />
    </svg>
  ),
};

// Field config for platforms connected via a manual form (API key, webhook
// URL, instance URL, ...) instead of an OAuth redirect. Keys match what
// each provider's connect_manual() expects server-side
// (kin-backend/social_providers/*.py).
const MANUAL_CONNECT_FIELDS: Record<string, { key: string; label: string; placeholder?: string }[]> = {
  discord: [{ key: "webhook_url", label: "Channel webhook URL", placeholder: "https://discord.com/api/webhooks/..." }],
  slack: [{ key: "webhook_url", label: "Incoming Webhook URL", placeholder: "https://hooks.slack.com/services/..." }],
  telegram: [
    { key: "chat_id", label: "Channel/chat id or @username" },
    { key: "api_key", label: "Bot token (optional — uses Kin's bot if blank)" },
  ],
  dev_to: [{ key: "api_key", label: "Dev.to API key" }],
  hashnode: [
    { key: "api_key", label: "Personal access token" },
    { key: "publication_id", label: "Publication id" },
  ],
  medium: [{ key: "api_key", label: "Integration token" }],
  listmonk: [
    { key: "domain", label: "Listmonk domain", placeholder: "https://newsletter.example.com" },
    { key: "api_user", label: "API user" },
    { key: "api_key", label: "API key" },
    { key: "list_id", label: "List id" },
  ],
  whop: [
    { key: "api_key", label: "Whop API key" },
    { key: "forum_id", label: "Forum experience id" },
  ],
  mastodon: [
    { key: "instance_url", label: "Instance URL", placeholder: "https://mastodon.social" },
    { key: "api_key", label: "Access token" },
  ],
  wordpress: [
    { key: "instance_url", label: "Site URL", placeholder: "https://myblog.com" },
    { key: "username", label: "WordPress username" },
    { key: "api_key", label: "Application password" },
  ],
  lemmy: [
    { key: "instance_url", label: "Instance URL", placeholder: "https://lemmy.world" },
    { key: "username", label: "Username" },
    { key: "api_key", label: "Password" },
    { key: "community", label: "Target community name" },
  ],
  bluesky: [
    { key: "username", label: "Handle", placeholder: "you.bsky.social" },
    { key: "api_key", label: "App password" },
    { key: "instance_url", label: "PDS URL (optional)", placeholder: "https://bsky.social" },
  ],
  nostr: [
    { key: "api_key", label: "Private key (64 hex chars)" },
    { key: "relays", label: "Relays (optional, comma-separated)" },
  ],
  farcaster: [{ key: "api_key", label: "Neynar signer_uuid" }],
};

export function SocialView() {
  const t = useTranslations("dashboard.social");

  // Navigation State
  const [activeTab, setActiveTab] = useState<TabType>("launches");

  // Database States
  const [posts, setPosts] = useState<SocialPost[]>([]);
  const [feeds, setFeeds] = useState<SocialAutoPost[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [mediaFiles, setMediaFiles] = useState<MediaAsset[]>([]);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  
  // Modals Visibility
  const [showComposer, setShowComposer] = useState(false);
  const [showChannelConnect, setShowChannelConnect] = useState(false);
  const [activeChannelMenu, setActiveChannelMenu] = useState<string | null>(null);

  // Custom picker dropdown displays
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showTagSelector, setShowTagSelector] = useState(false);
  const [showRepeatSelector, setShowRepeatSelector] = useState(false);

  // Picker values
  const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
  const [repeatInterval, setRepeatInterval] = useState("None");
  const [customTagInput, setCustomTagInput] = useState("");
  const [customTagColor, setCustomTagColor] = useState("#6366f1");

  // Accordion Settings States
  const [showSettingsAccordion, setShowSettingsAccordion] = useState(false);

  // Instagram Custom Settings States
  const [instaPostType, setInstaPostType] = useState("post_reel");
  const [instaCollaborators, setInstaCollaborators] = useState<string[]>([]);
  const [instaCollaboratorInput, setInstaCollaboratorInput] = useState("");
  const [instaAudio, setInstaAudio] = useState("");
  const [instaTrialReel, setInstaTrialReel] = useState(false);

  // X Custom Settings States
  const [xReplyPrivacy, setXReplyPrivacy] = useState("everyone");
  const [xIsPremiumFormat, setXIsPremiumFormat] = useState(false);

  // LinkedIn Custom Settings States
  const [linkedinCommentPrivacy, setLinkedinCommentPrivacy] = useState("anyone");
  const [linkedinVisibility, setLinkedinVisibility] = useState("anyone");

  // YouTube Custom Settings States
  const [ytPrivacy, setYtPrivacy] = useState("public");
  const [ytMadeForKids, setYtMadeForKids] = useState(false);

  // TikTok Custom Settings States
  const [tiktokAllowComments, setTiktokAllowComments] = useState(true);
  const [tiktokAllowDuets, setTiktokAllowDuets] = useState(true);
  const [tiktokAllowStitch, setTiktokAllowStitch] = useState(true);
  const [tiktokPrivacy, setTiktokPrivacy] = useState("everyone");


  // Custom Date Picker Month parameters
  const [pickerDate, setPickerDate] = useState(() => new Date());
  const [pickerHour, setPickerHour] = useState("07");
  const [pickerMinute, setPickerMinute] = useState("00");
  const [pickerAmpm, setPickerAmpm] = useState("PM");

  const [analytics, setAnalytics] = useState({
    impressions: 0,
    likes: 0,
    reposts: 0,
    clicks: 0
  });
  const [analyticsSeries, setAnalyticsSeries] = useState<
    { date: string; impressions: number; likes: number; reposts: number; comments: number; clicks: number }[]
  >([]);

  // Calendar parameters
  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(() => {
    const d = new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  });
  const [calendarView, setCalendarView] = useState<"week" | "day" | "month">("week");
  
  // Composer Form States
  // Set when the composer was opened by clicking an existing post (vs. the
  // "Create Post"/"Add Post" actions) — makes handleCreatePost PATCH that
  // post instead of creating a duplicate.
  const [editingPostId, setEditingPostId] = useState<string | null>(null);
  // Postiz-style Global/per-channel content: globalContent is what every
  // selected account posts unless it has its own entry in contentOverrides.
  // activeComposerTab is "global" or a specific account id — whichever tab
  // the textarea is currently bound to.
  const [globalContent, setGlobalContent] = useState("");
  const [contentOverrides, setContentOverrides] = useState<Record<string, string>>({});
  const [activeComposerTab, setActiveComposerTab] = useState<string>("global");
  const [publishDate, setPublishDate] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  // Multi-select: which connected ACCOUNTS (not platforms) this post targets.
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [isDraft, setIsDraft] = useState(false);
  const [addComment, setAddComment] = useState(false);
  const [commentContent, setCommentContent] = useState("");
  
  // RSS Feeds Form States
  const [feedTitle, setFeedTitle] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [feedIntegrations, setFeedIntegrations] = useState<string[]>(["x"]);

  // AI Copilot States
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiUrl, setAiUrl] = useState("");
  const [aiTone, setAiTone] = useState("viral");
  const [aiType, setAiType] = useState("outlines");
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiOutlines, setAiOutlines] = useState<string[]>([]);
  
  // Outbound webhook (fired on post.published / post.failed)
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookActive, setWebhookActive] = useState(true);
  const [webhookSecret, setWebhookSecret] = useState<string | null>(null);
  const [webhookSaving, setWebhookSaving] = useState(false);
  const [existingWebhook, setExistingWebhook] = useState<{ id: string; url: string; active: boolean } | null>(null);
  
  // Connected Channels (synced from actual user credentials)
  const [connectedSlugs, setConnectedSlugs] = useState<string[]>([]);
  // Which slugs already have a real (non-stub) provider implementation —
  // drives the "(coming soon)" label in the connect modal.
  const [realSlugs, setRealSlugs] = useState<string[]>([]);
  // Per-account display info (avatar/handle) captured at connect time, keyed
  // by slug — shown in place of the generic platform logo when available,
  // matching Postiz's per-account profile picture in the channel list.
  const [accountInfo, setAccountInfo] = useState<Record<string, { avatarUrl: string | null; handle: string | null }>>({});
  // The real connected ACCOUNTS (can be N per slug, e.g. two X accounts) —
  // drives the composer's multi-select, the tab strip, and the Active
  // Channels sidebar. Distinct from connectedSlugs/accountInfo above, which
  // are platform-level (one slot per slug) and still back the Add Channel /
  // Integrations grids where accounts don't need to be distinguished.
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const accountsById = Object.fromEntries(accounts.map((a) => [a.id, a]));
  // Which account's platform-specific settings/preview to show: the tab
  // strip's active account when it isn't "global", otherwise the first
  // selected account (Global still needs *a* platform to render against).
  const activeAccountId = activeComposerTab !== "global" ? activeComposerTab : selectedAccountIds[0];
  const activeSlug = accountsById[activeAccountId || ""]?.slug || "x";
  // What the composer textarea currently shows/edits: the active account's
  // override if it has one, otherwise the shared global text.
  const composerContent = activeComposerTab === "global"
    ? globalContent
    : (contentOverrides[activeComposerTab] ?? globalContent);
  function setComposerContent(text: string) {
    if (activeComposerTab === "global") {
      setGlobalContent(text);
    } else {
      setContentOverrides((prev) => ({ ...prev, [activeComposerTab]: text }));
    }
  }
  const [manualConnectSlug, setManualConnectSlug] = useState<string | null>(null);
  const [manualForm, setManualForm] = useState<Record<string, string>>({});
  const [manualSubmitting, setManualSubmitting] = useState(false);

  const channels = [
    { slug: "x", name: "X (Twitter)", color: "bg-neutral-900 border-neutral-800 text-white" },
    { slug: "linkedin", name: "LinkedIn", color: "bg-blue-600 border-blue-500 text-white" },
    { slug: "instagram", name: "Instagram", color: "bg-pink-600 border-pink-500 text-white" },
    { slug: "facebook", name: "Facebook", color: "bg-blue-800 border-blue-700 text-white" },
    { slug: "threads", name: "Threads", color: "bg-black border-zinc-800 text-white" },
    { slug: "youtube", name: "YouTube", color: "bg-red-600 border-red-500 text-white" },
    { slug: "tiktok", name: "TikTok", color: "bg-zinc-900 border-zinc-800 text-white" },
    { slug: "reddit", name: "Reddit", color: "bg-orange-600 border-orange-500 text-white" },
    { slug: "pinterest", name: "Pinterest", color: "bg-rose-600 border-rose-500 text-white" },
    { slug: "mastodon", name: "Mastodon", color: "bg-indigo-600 border-indigo-500 text-white" },
    { slug: "bluesky", name: "Bluesky", color: "bg-sky-500 border-sky-400 text-white" },
    { slug: "discord", name: "Discord", color: "bg-indigo-800 border-indigo-700 text-white" },
    { slug: "slack", name: "Slack", color: "bg-purple-700 border-purple-650 text-white" },
    { slug: "telegram", name: "Telegram", color: "bg-sky-600 border-sky-500 text-white" },
    { slug: "dev_to", name: "Dev.to", color: "bg-neutral-850 border-neutral-800 text-white" },
    { slug: "dribbble", name: "Dribbble", color: "bg-pink-500 border-pink-400 text-white" },
    { slug: "farcaster", name: "Farcaster", color: "bg-violet-850 border-violet-800 text-white" },
    { slug: "gmb", name: "Google Business", color: "bg-sky-700 border-sky-600 text-white" },
    { slug: "hashnode", name: "Hashnode", color: "bg-blue-850 border-blue-800 text-white" },
    { slug: "kick", name: "Kick", color: "bg-green-600 border-green-500 text-white" },
    { slug: "lemmy", name: "Lemmy", color: "bg-zinc-800 border-zinc-700 text-white" },
    { slug: "listmonk", name: "Listmonk", color: "bg-emerald-600 border-emerald-500 text-white" },
    { slug: "medium", name: "Medium", color: "bg-neutral-900 border-neutral-800 text-white" },
    { slug: "mewe", name: "MeWe", color: "bg-blue-900 border-blue-850 text-white" },
    { slug: "moltbook", name: "Moltbook", color: "bg-slate-700 border-slate-600 text-white" },
    { slug: "nostr", name: "Nostr", color: "bg-purple-900 border-purple-850 text-white" },
    { slug: "skool", name: "Skool", color: "bg-amber-600 border-amber-500 text-white" },
    { slug: "tumblr", name: "Tumblr", color: "bg-indigo-900 border-indigo-850 text-white" },
    { slug: "twitch", name: "Twitch", color: "bg-purple-600 border-purple-550 text-white" },
    { slug: "vk", name: "VK", color: "bg-blue-500 border-blue-450 text-white" },
    { slug: "whop", name: "Whop", color: "bg-amber-500 border-amber-400 text-black" },
    { slug: "wordpress", name: "WordPress", color: "bg-blue-900 border-blue-850 text-white" },
  ];

  // Load Initial Data
  useEffect(() => {
    fetchPosts();
    fetchFeeds();
    fetchAnalytics();
    fetchMedia();
    fetchIntegrations();
    fetchAccounts();
    fetchTags();
    fetchWebhook();
  }, []);

  // Keep the tab strip pointed somewhere valid — if the account it was on
  // gets deselected (or only one account remains, hiding the strip), fall
  // back to Global instead of silently editing an override no one can see.
  useEffect(() => {
    if (activeComposerTab !== "global" && !selectedAccountIds.includes(activeComposerTab)) {
      setActiveComposerTab("global");
    }
  }, [selectedAccountIds, activeComposerTab]);

  async function fetchAccounts() {
    try {
      setAccounts(await socialApi.accounts.list());
    } catch (err) {
      console.error("Failed to fetch social accounts", err);
    }
  }

  async function fetchWebhook() {
    try {
      const hook = await socialApi.webhook.get();
      if (hook) {
        setExistingWebhook(hook);
        setWebhookUrl(hook.url);
        setWebhookActive(hook.active);
      }
    } catch (err) {
      console.error("Failed to fetch webhook", err);
    }
  }

  async function handleSaveWebhook(e: React.FormEvent) {
    e.preventDefault();
    if (!webhookUrl.trim()) return;
    setWebhookSaving(true);
    try {
      const res = await socialApi.webhook.save(webhookUrl, webhookActive);
      setWebhookSecret(res.secret);
      fetchWebhook();
    } catch (err) {
      console.error("Failed to save webhook", err);
    } finally {
      setWebhookSaving(false);
    }
  }

  async function handleDeleteWebhook() {
    try {
      await socialApi.webhook.delete();
      setExistingWebhook(null);
      setWebhookUrl("");
      setWebhookSecret(null);
    } catch (err) {
      console.error("Failed to delete webhook", err);
    }
  }

  async function fetchPosts() {
    try {
      setPosts(await socialApi.posts.list());
    } catch (err) {
      console.error("Failed to fetch posts", err);
    }
  }

  async function fetchFeeds() {
    try {
      setFeeds(await socialApi.autoPosts.list());
    } catch (err) {
      console.error("Failed to fetch feeds", err);
    }
  }

  async function fetchAnalytics() {
    try {
      setAnalytics(await socialApi.analytics.summary());
    } catch (err) {
      console.error("Failed to fetch analytics", err);
    }
    try {
      const { series } = await socialApi.analytics.timeseries(7);
      setAnalyticsSeries(series);
    } catch (err) {
      console.error("Failed to fetch analytics timeseries", err);
    }
  }

  async function fetchMedia() {
    try {
      setMediaFiles(await socialApi.media.list());
    } catch (err) {
      console.error("Failed to fetch media assets", err);
    }
  }

  async function fetchTags() {
    try {
      setTags(await socialApi.tags.list());
    } catch (err) {
      console.error("Failed to fetch tags", err);
    }
  }

  // Get connected platform slugs from real user_credentials-backed integrations
  async function fetchIntegrations() {
    try {
      const data = await socialApi.integrations.list();
      setConnectedSlugs(data.filter((c) => c.connected).map((c) => c.slug));
      setRealSlugs(data.filter((c) => c.real).map((c) => c.slug));
      setAccountInfo(
        Object.fromEntries(
          data
            .filter((c) => c.connected)
            .map((c) => [c.slug, { avatarUrl: c.avatarUrl, handle: c.handle || c.displayName }]),
        ),
      );
    } catch (err) {
      console.error("Failed to fetch integrations", err);
    }
  }

  // Initialized synchronously from the ?social=error&provider=slug return
  // param (if present) so the banner shows on first paint instead of via a
  // setState-in-effect that would trigger an extra render.
  const [connectError, setConnectError] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const params = new URLSearchParams(window.location.search);
    if (params.get("social") !== "error") return null;
    const provider = params.get("provider");
    return provider ? t("errors.connectFailed", { provider }) : t("errors.connectFailedGeneric");
  });

  // Always runs the connect flow (OAuth redirect or manual-connect form),
  // regardless of whether the platform already has a connected account —
  // this is what lets the Add Channel grid add a SECOND account of a
  // platform instead of only ever connecting the first.
  async function handleStartConnect(slug: string) {
    setConnectError(null);
    try {
      if (MANUAL_CONNECT_FIELDS[slug]) {
        setManualForm({});
        setManualConnectSlug(slug);
        return;
      }
      const { url } = await socialApi.integrations.start(slug);
      window.location.href = url;
    } catch (err) {
      console.error("Failed to start connection", err);
      setConnectError(err instanceof Error ? err.message : `Could not connect ${slug}`);
    }
  }

  // Integrations tab toggle: connect if not connected, else disconnect
  // EVERY account on that platform (the tab is platform-level; per-account
  // disconnects live in the Active Channels sidebar instead).
  async function handleConnectToggle(slug: string) {
    const isConnected = connectedSlugs.includes(slug);
    if (!isConnected) {
      await handleStartConnect(slug);
      return;
    }
    setConnectError(null);
    try {
      await socialApi.integrations.disconnect(slug);
      setConnectedSlugs((prev) => prev.filter((s) => s !== slug));
      fetchAccounts();
    } catch (err) {
      console.error("Failed to disconnect", err);
      setConnectError(err instanceof Error ? err.message : `Could not disconnect ${slug}`);
    }
  }

  async function handleManualConnectSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!manualConnectSlug) return;
    setManualSubmitting(true);
    setConnectError(null);
    try {
      await socialApi.integrations.connectManual(manualConnectSlug, manualForm);
      setConnectedSlugs((prev) => [...prev, manualConnectSlug]);
      fetchAccounts();
      setManualConnectSlug(null);
      setShowChannelConnect(false);
    } catch (err) {
      console.error("Manual connect failed", err);
      setConnectError(err instanceof Error ? err.message : `Could not connect ${manualConnectSlug}`);
    } finally {
      setManualSubmitting(false);
    }
  }

  // Clean up the ?social=ok|error&provider=slug return param from the OAuth
  // callback (banner itself is set synchronously above); refresh the
  // connected-accounts list on success.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const social = params.get("social");
    if (!social) return;
    if (social !== "error") {
      fetchIntegrations();
      fetchAccounts();
    }
    params.delete("social");
    params.delete("provider");
    const qs = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
  }, []);

  // Opens the composer for a brand-new post. Always resets prior state so a
  // stale edit (or a previous draft) doesn't leak into the next post.
  function openNewComposer(prefill?: {
    publishDate?: string;
    accountId?: string;
    content?: string;
    imageUrl?: string;
  }) {
    setEditingPostId(null);
    setGlobalContent(prefill?.content ?? "");
    setContentOverrides({});
    setActiveComposerTab("global");
    setImageUrl(prefill?.imageUrl ?? "");
    const defaultAccount = prefill?.accountId || accounts[0]?.id;
    setSelectedAccountIds(defaultAccount ? [defaultAccount] : []);
    if (prefill?.publishDate) setPublishDate(prefill.publishDate);
    setIsDraft(false);
    setAddComment(false);
    setCommentContent("");
    setShowComposer(true);
  }

  // Opens the composer pre-filled from an existing post, in edit mode —
  // handleCreatePost below PATCHes it instead of creating a duplicate.
  // Bulk-editing every channel of a multi-account post at once is out of
  // scope for now: this always edits just the one underlying row/account.
  function openEditComposer(post: SocialPost) {
    setEditingPostId(post.id);
    setGlobalContent(post.content);
    setContentOverrides({});
    setActiveComposerTab("global");
    setImageUrl(post.image_url || "");
    const accountId = post.social_account_id || accounts.find((a) => a.slug === post.integration_slug)?.id;
    setSelectedAccountIds(accountId ? [accountId] : []);
    setIsDraft(post.state === "draft");
    setAddComment(false);
    setCommentContent("");
    setShowComposer(true);
  }

  // Create Post — if "Add comment" is checked, a second post is queued
  // immediately after with parent_post_id set, which the backend cron
  // publishes as a reply/comment on the parent once the parent goes live
  // (see kin-backend main.py's /cron/publish-social-posts thread handling).
  // Only the fields a given platform's provider actually reads (see
  // kin-backend/social_providers/{youtube,tiktok,linkedin,x}.py) — everything
  // else in the accordion is UI-only until a provider honors it too.
  function buildPlatformSettings(): Record<string, unknown> | null {
    switch (activeSlug) {
      case "youtube":
        return { privacy: ytPrivacy, made_for_kids: ytMadeForKids };
      case "tiktok":
        return {
          privacy: tiktokPrivacy,
          allow_comments: tiktokAllowComments,
          allow_duets: tiktokAllowDuets,
          allow_stitch: tiktokAllowStitch,
        };
      case "linkedin":
        return { visibility: linkedinVisibility, comment_privacy: linkedinCommentPrivacy };
      case "x":
        return { reply_privacy: xReplyPrivacy, premium_format: xIsPremiumFormat };
      default:
        return null;
    }
  }

  const REPEAT_INTERVAL_MAP: Record<string, "daily" | "weekly" | "monthly" | null> = {
    None: null,
    "Every Day": "daily",
    "Every Week": "weekly",
    "Every Month": "monthly",
  };

  // Shows the connected account's real profile picture (captured at connect
  // time, where the platform provides one) instead of the generic brand
  // logo — falls back to the logo when no avatar was captured, or when the
  // avatar URL fails to actually load (some CDNs, e.g. LinkedIn's, reject
  // hotlinked <img> requests without a same-origin Referer).
  function ChannelIcon({ slug, className }: { slug: string; className?: string }) {
    const avatar = accountInfo[slug]?.avatarUrl;
    const [broken, setBroken] = useState(false);
    if (avatar && !broken) {
      return (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={avatar}
          alt=""
          referrerPolicy="no-referrer"
          onError={() => setBroken(true)}
          className={`${className || "size-4"} rounded-full object-cover`}
        />
      );
    }
    return <>{LOGOS[slug] || <Globe className={className || "size-4 text-white"} />}</>;
  }

  // Sidebar "Active Channels" card avatar: the real profile photo fills the
  // whole circle (previously it was rendered at icon-size inside the circle,
  // which made a legitimately-loaded photo look like it "wasn't showing"),
  // with a small platform-logo badge in the corner so the network is still
  // identifiable at a glance — mirrors Postiz's connected-account list style.
  function ChannelAvatar({ account, size }: { account: SocialAccount; size: string }) {
    const slug = account.slug;
    const avatar = account.avatarUrl;
    const [broken, setBroken] = useState(false);
    const hasPhoto = !!avatar && !broken;
    return (
      <div className={`${size} shrink-0 rounded-full relative`}>
        {hasPhoto ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={avatar!}
            alt=""
            referrerPolicy="no-referrer"
            onError={() => setBroken(true)}
            className={`${size} rounded-full object-cover border border-border`}
          />
        ) : (
          <div className={`${size} rounded-full bg-neutral-900 border border-border flex items-center justify-center overflow-hidden`}>
            {LOGOS[slug] || <Globe className="size-1/2 text-white" />}
          </div>
        )}
        <span className="absolute -bottom-0.5 -right-0.5 size-4 rounded-full bg-neutral-900 border-2 border-card flex items-center justify-center overflow-hidden">
          {hasPhoto ? (
            <span className="scale-[0.55] flex items-center justify-center">
              {LOGOS[slug] || <Globe className="size-3 text-white" />}
            </span>
          ) : (
            <Check className="size-2 text-emerald-400" />
          )}
        </span>
      </div>
    );
  }

  // Real per-platform preview shapes (Postiz renders a distinct mockup per
  // platform rather than one generic card) — X, LinkedIn, and Instagram get
  // their own layout since they're the most visually distinctive; every
  // other platform falls back to the original generic card.
  function renderPlatformPreview() {
    const info = accountsById[activeAccountId || ""];
    const content = composerContent;
    const displayName = info?.displayName || info?.handle || channels.find((c) => c.slug === activeSlug)?.name || "PersonaliAI";
    const handle = info?.handle ? `@${info.handle}` : "@personal_ai";

    if (activeSlug === "x") {
      return (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm space-y-3 max-w-sm mx-auto">
          <div className="flex items-start gap-2.5">
            <div className="size-10 rounded-full bg-neutral-900 border border-border flex items-center justify-center shrink-0 overflow-hidden">
              <ChannelIcon slug="x" className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1 flex-wrap">
                <h4 className="text-[13px] font-bold truncate">{displayName}</h4>
                <span className="text-[13px] text-muted-foreground">{handle} · now</span>
              </div>
              <p className="text-sm leading-snug whitespace-pre-wrap mt-0.5">{content}</p>
              {imageUrl && (
                <div className="rounded-2xl overflow-hidden border border-border/40 mt-2.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={imageUrl} alt="preview" className="w-full max-h-64 object-cover" />
                </div>
              )}
              <div className="flex items-center justify-between text-muted-foreground pt-3 max-w-[280px] text-[11px]">
                <span className="flex items-center gap-1"><MessageSquare className="size-3.5" /> 0</span>
                <span className="flex items-center gap-1"><Share2 className="size-3.5" /> 0</span>
                <span className="flex items-center gap-1"><Heart className="size-3.5" /> 0</span>
                <span className="flex items-center gap-1"><Eye className="size-3.5" /> 0</span>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (activeSlug === "linkedin") {
      return (
        <div className="rounded-xl border border-border bg-card shadow-sm max-w-sm mx-auto overflow-hidden">
          <div className="p-4 pb-3 flex items-center gap-2.5">
            <div className="size-11 rounded-full bg-neutral-900 border border-border flex items-center justify-center shrink-0 overflow-hidden">
              <ChannelIcon slug="linkedin" className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1">
                <h4 className="text-[13px] font-bold truncate">{displayName}</h4>
                <span className="text-[10px] text-muted-foreground">• 1st</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-none mt-0.5">now · 🌐</p>
            </div>
          </div>
          <p className="px-4 pb-3 text-[13px] leading-relaxed whitespace-pre-wrap">{content}</p>
          {imageUrl && (
            <div className="border-t border-border/40">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={imageUrl} alt="preview" className="w-full max-h-64 object-cover" />
            </div>
          )}
          <div className="flex items-center justify-around text-[11px] font-semibold text-muted-foreground border-t border-border/40 py-1.5">
            <span className="flex items-center gap-1.5 px-2 py-1.5"><ThumbsUp className="size-4" /> Like</span>
            <span className="flex items-center gap-1.5 px-2 py-1.5"><MessageSquare className="size-4" /> Comment</span>
            <span className="flex items-center gap-1.5 px-2 py-1.5"><Share2 className="size-4" /> Repost</span>
          </div>
        </div>
      );
    }

    if (activeSlug === "instagram") {
      return (
        <div className="rounded-xl border border-border bg-card shadow-sm max-w-sm mx-auto overflow-hidden">
          <div className="p-3 flex items-center gap-2.5">
            <div className="size-8 rounded-full bg-neutral-900 border border-border flex items-center justify-center shrink-0 overflow-hidden">
              <ChannelIcon slug="instagram" className="size-4" />
            </div>
            <h4 className="text-[13px] font-bold truncate">{displayName}</h4>
          </div>
          {imageUrl ? (
            <div className="aspect-square bg-muted">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={imageUrl} alt="preview" className="w-full h-full object-cover" />
            </div>
          ) : (
            <div className="aspect-square bg-muted flex items-center justify-center text-center px-6">
              <p className="text-[11px] text-muted-foreground">Instagram posts need an image or video — add one below.</p>
            </div>
          )}
          <div className="p-3 space-y-1.5">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Heart className="size-5" />
              <MessageSquare className="size-5" />
              <Share2 className="size-5" />
            </div>
            <p className="text-[13px]"><span className="font-bold">{displayName}</span> {content}</p>
          </div>
        </div>
      );
    }

    // Generic fallback card for every other platform.
    return (
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-3 max-w-sm mx-auto">
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-full bg-neutral-900 border border-border flex items-center justify-center overflow-hidden">
            <ChannelIcon slug={activeSlug} className="size-4" />
          </div>
          <div>
            <div className="flex items-center gap-1">
              <h4 className="text-xs font-bold">{displayName}</h4>
              <span className="text-[10px] text-indigo-500">✔</span>
            </div>
            <p className="text-[9px] text-muted-foreground leading-none">{handle} • now</p>
          </div>
        </div>
        <p className="text-xs leading-relaxed whitespace-pre-wrap">{content}</p>
        {imageUrl && (
          <div className="rounded-lg overflow-hidden border border-border/40 aspect-video bg-muted flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={imageUrl} alt="preview" className="object-cover w-full h-full" />
          </div>
        )}
        <div className="flex items-center justify-between text-muted-foreground border-t border-border/40 pt-2 text-[10px]">
          <span className="flex items-center gap-1"><MessageSquare className="size-3.5" /> 0</span>
          <span className="flex items-center gap-1"><Heart className="size-3.5" /> 0</span>
          <span className="flex items-center gap-1"><Eye className="size-3.5" /> 0</span>
          <span className="flex items-center gap-1"><Share2 className="size-3.5" /></span>
        </div>
      </div>
    );
  }

  async function handleCreatePost(e: React.FormEvent, draft: boolean = isDraft) {
    e.preventDefault();
    if (!globalContent.trim() || !publishDate || selectedAccountIds.length === 0) return;

    try {
      const publishIso = new Date(publishDate).toISOString();
      const state = draft ? "draft" : "queue";

      if (editingPostId) {
        // Editing an existing post — PATCH it in place rather than creating
        // a duplicate (repeat/delayed-comment don't apply to an edit; bulk-
        // editing every channel of a multi-account post isn't supported yet,
        // this always edits the single underlying row).
        await socialApi.posts.update(editingPostId, {
          content: globalContent,
          publish_date: publishIso,
          state,
          image_url: imageUrl || null,
          settings: buildPlatformSettings(),
        });
      } else {
        const repeat = draft ? null : REPEAT_INTERVAL_MAP[repeatInterval];
        const created = await socialApi.posts.create({
          social_account_ids: selectedAccountIds,
          content: globalContent,
          content_overrides: contentOverrides,
          publish_date: publishIso,
          state,
          image_url: imageUrl || null,
          settings: buildPlatformSettings(),
          repeat_interval: repeat,
          repeat_count: repeat ? 4 : undefined,
        });
        const createdArr = Array.isArray(created) ? created : [created];

        if (addComment && commentContent.trim() && !draft) {
          // Each channel's comment must reply to THAT channel's own parent
          // post row (the cron job posts it using the parent's release_id),
          // so this can't go through the single multi-account create call —
          // one request per created post instead.
          await Promise.all(
            createdArr
              .filter((p) => p.social_account_id)
              .map((p) =>
                socialApi.posts.create({
                  social_account_ids: [p.social_account_id!],
                  content: commentContent,
                  publish_date: publishIso,
                  state: "queue",
                  parent_post_id: p.id,
                }),
              ),
          );
        }
      }

      setEditingPostId(null);
      setGlobalContent("");
      setContentOverrides({});
      setActiveComposerTab("global");
      setImageUrl("");
      setPublishDate("");
      setAddComment(false);
      setCommentContent("");
      setRepeatInterval("None");
      setShowComposer(false);
      fetchPosts();
    } catch (err) {
      console.error("Failed to schedule post", err);
    }
  }

  // Create Tag
  async function handleCreateTag() {
    if (!customTagInput.trim()) return;
    try {
      await socialApi.tags.create({ name: customTagInput, color: customTagColor });
      setCustomTagInput("");
      fetchTags();
    } catch (err) {
      console.error("Failed to create tag", err);
    }
  }

  // Delete Post
  async function handleDeletePost(id: string) {
    try {
      await socialApi.posts.delete(id);
      fetchPosts();
      fetchAnalytics();
    } catch (err) {
      console.error("Failed to delete post", err);
    }
  }

  // RSS Auto-Post Feeds
  const [showFeedModal, setShowFeedModal] = useState(false);
  const [feedSaving, setFeedSaving] = useState(false);
  const [feedGenerateContent, setFeedGenerateContent] = useState(false);

  async function handleCreateFeed(e: React.FormEvent) {
    e.preventDefault();
    if (!feedTitle.trim() || !feedUrl.trim() || feedIntegrations.length === 0) return;
    setFeedSaving(true);
    try {
      await socialApi.autoPosts.create({
        title: feedTitle,
        url: feedUrl,
        active: true,
        generate_content: feedGenerateContent,
        integrations: feedIntegrations,
      });
      setFeedTitle("");
      setFeedUrl("");
      setFeedIntegrations(["x"]);
      setFeedGenerateContent(false);
      setShowFeedModal(false);
      fetchFeeds();
    } catch (err) {
      console.error("Failed to create feed", err);
    } finally {
      setFeedSaving(false);
    }
  }

  async function handleDeleteFeed(id: string, title: string) {
    if (!window.confirm(t("feeds.deleteConfirm", { title }))) return;
    try {
      await socialApi.autoPosts.delete(id);
      fetchFeeds();
    } catch (err) {
      console.error("Failed to delete feed", err);
    }
  }

  // AI Outlines Generation — calls Kin's own Gemini-backed generator
  // (kin-backend main.py POST /api/social/generate).
  async function handleAiCopilotGenerate() {
    if (!aiPrompt.trim()) return;
    setAiGenerating(true);
    try {
      const res = await socialApi.generate({
        prompt: aiPrompt,
        tone: aiTone,
        kind: aiType === "posts" ? "post" : "outlines",
        url: aiUrl || undefined,
      });
      setAiOutlines(res.outlines || (res.content ? [res.content] : []));
    } catch (err) {
      console.error("AI generation failed", err);
      setAiOutlines([]);
    } finally {
      setAiGenerating(false);
    }
  }

  // Handle local file uploads
  const [uploading, setUploading] = useState(false);
  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await socialApi.media.upload(file);
      fetchMedia();
    } catch (err) {
      console.error("Media upload failed", err);
    } finally {
      setUploading(false);
    }
  }

  // Composer text-formatting toolbar (Bold/Underline/Emoji). None of these
  // platforms render HTML/markdown in a post, so "bold"/"underline" work via
  // swapping the selected text for Unicode look-alike characters — a real
  // technique other social schedulers use, not decoration. Emoji is a small
  // inline picker inserting at the cursor.
  const contentTextareaRef = useRef<HTMLTextAreaElement>(null);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const emojiBtnRef = useRef<HTMLButtonElement>(null);
  const dateBtnRef = useRef<HTMLButtonElement>(null);
  const tagBtnRef = useRef<HTMLButtonElement>(null);
  const repeatBtnRef = useRef<HTMLButtonElement>(null);
  const channelMenuBtnRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const BOLD_MAP: Record<string, string> = (() => {
    const map: Record<string, string> = {};
    const upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const lower = "abcdefghijklmnopqrstuvwxyz";
    const digits = "0123456789";
    for (let i = 0; i < upper.length; i++) map[upper[i]] = String.fromCodePoint(0x1d400 + i);
    for (let i = 0; i < lower.length; i++) map[lower[i]] = String.fromCodePoint(0x1d41a + i);
    for (let i = 0; i < digits.length; i++) map[digits[i]] = String.fromCodePoint(0x1d7ce + i);
    return map;
  })();

  function applyToSelection(transform: (text: string) => string) {
    const el = contentTextareaRef.current;
    if (!el) return;
    const { selectionStart, selectionEnd } = el;
    if (selectionStart === selectionEnd) return; // nothing selected
    const before = composerContent.slice(0, selectionStart);
    const selected = composerContent.slice(selectionStart, selectionEnd);
    const after = composerContent.slice(selectionEnd);
    const transformed = transform(selected);
    setComposerContent(before + transformed + after);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(before.length, before.length + transformed.length);
    });
  }

  function handleBold() {
    applyToSelection((text) => Array.from(text).map((ch) => BOLD_MAP[ch] || ch).join(""));
  }

  function handleUnderline() {
    // Combining low line (U+0332) after every character — renders as an
    // underline in virtually every font, no HTML needed.
    applyToSelection((text) => Array.from(text).map((ch) => (ch === "\n" ? ch : ch + "̲")).join(""));
  }

  function insertEmoji(emoji: string) {
    const el = contentTextareaRef.current;
    const pos = el?.selectionStart ?? composerContent.length;
    setComposerContent(composerContent.slice(0, pos) + emoji + composerContent.slice(pos));
    setShowEmojiPicker(false);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(pos + emoji.length, pos + emoji.length);
    });
  }

  const EMOJI_PICKS = ["😀", "😂", "🔥", "🎉", "❤️", "👍", "🚀", "✨", "💡", "📈", "🙌", "😎", "🤔", "👀", "✅", "⚡"];

  // Composer's "Insert Media" — uploads straight from the user's device
  // instead of only accepting a pasted URL, and keeps the Media Library in
  // sync since the file lands in the same storage bucket.
  const composerFileInputRef = useRef<HTMLInputElement>(null);
  const [composerUploading, setComposerUploading] = useState(false);
  async function handleComposerMediaUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;
    setComposerUploading(true);
    try {
      const asset = await socialApi.media.upload(file);
      setImageUrl(asset.url);
      fetchMedia();
    } catch (err) {
      console.error("Composer media upload failed", err);
    } finally {
      setComposerUploading(false);
    }
  }

  function triggerCopy(text: string) {
    navigator.clipboard.writeText(text);
    setCopiedUrl(text);
    setTimeout(() => setCopiedUrl(null), 2000);
  }

  // Calendar dates computation
  const getDatesOfWeek = () => {
    const dates = [];
    const temp = new Date(currentWeekStart);
    for (let i = 0; i < 7; i++) {
      dates.push(new Date(temp));
      temp.setDate(temp.getDate() + 1);
    }
    return dates;
  };

  const getWeekRangeString = () => {
    const dates = getDatesOfWeek();
    const start = dates[0];
    const end = dates[6];
    const options: Intl.DateTimeFormatOptions = { month: "2-digit", day: "2-digit", year: "numeric" };
    return `${start.toLocaleDateString(undefined, options)} - ${end.toLocaleDateString(undefined, options)}`;
  };

  const shiftWeek = (direction: number) => {
    const temp = new Date(currentWeekStart);
    temp.setDate(temp.getDate() + direction * 7);
    setCurrentWeekStart(temp);
  };

  const weekDates = getDatesOfWeek();
  const hoursOfDay = Array.from({ length: 24 }, (_, i) => i);

  const getPostsForCell = (date: Date, hour: number) => {
    return posts.filter(p => {
      const pDate = new Date(p.publish_date);
      return pDate.getFullYear() === date.getFullYear() &&
             pDate.getMonth() === date.getMonth() &&
             pDate.getDate() === date.getDate() &&
             pDate.getHours() === hour;
    });
  };

  // Custom Date Picker handlers
  const handlePickerDateSelect = (dayNum: number) => {
    const target = new Date(pickerDate);
    target.setDate(dayNum);
    
    // Parse hours & minutes
    let hoursVal = parseInt(pickerHour);
    if (pickerAmpm === "PM" && hoursVal < 12) hoursVal += 12;
    if (pickerAmpm === "AM" && hoursVal === 12) hoursVal = 0;
    target.setHours(hoursVal);
    target.setMinutes(parseInt(pickerMinute));
    target.setSeconds(0);

    const offset = target.getTimezoneOffset();
    const localDate = new Date(target.getTime() - (offset*60*1000));
    setPublishDate(localDate.toISOString().slice(0, 16));
    setShowDatePicker(false);
  };

  const getDaysInPickerMonth = () => {
    const year = pickerDate.getFullYear();
    const month = pickerDate.getMonth();
    return new Date(year, month + 1, 0).getDate();
  };

  // Which weekday (0=Sun..6=Sat) the 1st of the displayed month falls on —
  // used to pad the grid with leading blanks so day numbers line up under
  // the correct S/M/T/W/T/F/S column instead of always starting at column 1.
  const getFirstWeekdayOfPickerMonth = () => {
    return new Date(pickerDate.getFullYear(), pickerDate.getMonth(), 1).getDay();
  };

  const getCharacterLimit = (slug: string) => {
    switch (slug) {
      case "x": return 280;
      case "threads": return 500;
      case "linkedin": return 3000;
      case "youtube": return 5000;
      case "instagram": return 2200;
      case "tiktok": return 2200;
      case "facebook": return 63206;
      default: return 2200;
    }
  };

  const charLimit = getCharacterLimit(activeSlug);

  return (
    <div className="space-y-6">
      
      {/* 1. HORIZONTAL MENU TAB BAR — scrolls instead of wrapping to many
          lines now that there are 7 tabs, so it stays a single tidy row on
          phones instead of a messy multi-row wrap. */}
      <div className="border-b border-border pb-2">
        <div className="flex items-center gap-1 bg-muted/30 p-1 rounded-xl border border-border/40 overflow-x-auto scrollbar-none w-full sm:w-fit">
          {(
            [
              { id: "launches", label: t("tabs.launches"), icon: Calendar },
              { id: "agent", label: t("tabs.agent"), icon: Sparkles },
              { id: "media", label: t("tabs.media"), icon: ImageIcon },
              { id: "analytics", label: t("tabs.analytics"), icon: BarChart2 },
              { id: "integrations", label: t("tabs.integrations"), icon: Globe },
              { id: "feeds", label: t("tabs.feeds"), icon: Rss },
              { id: "plugs", label: t("tabs.plugs"), icon: Plug },
            ] as const
          ).map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold tracking-wide transition-all cursor-pointer shrink-0 ${
                  active
                    ? "bg-card text-indigo-500 shadow-sm border border-border"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                <Icon className="size-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. TAB BLOCKS */}

      {/* ==================== LAUNCHES (CALENDAR GRID) ==================== */}
      {activeTab === "launches" && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">
          
          {/* Left sidebar panel */}
          <div className="xl:col-span-1 bg-card rounded-2xl border border-border p-5 space-y-5 shadow-sm">
            <div className="space-y-2">
              <Button
                onClick={() => openNewComposer()}
                className="w-full gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold"
              >
                <Plus className="size-4" />
                {t("sidebar.createPost")}
              </Button>
              <Button
                onClick={() => setShowChannelConnect(true)}
                variant="outline"
                className="w-full gap-2 text-foreground font-semibold"
              >
                <Plus className="size-4 text-indigo-500" />
                {t("sidebar.addChannel")}
              </Button>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between items-center text-xs font-bold text-muted-foreground uppercase tracking-widest px-1">
                <span>{t("sidebar.activeChannels")}</span>
                <span className="text-[10px] text-indigo-500 lowercase">
                  {t("sidebar.connectedCount", { count: accounts.length })}
                </span>
              </div>

              {/* One row per connected ACCOUNT, not per platform — two X
                  accounts show as two separate rows here, each independently
                  removable, matching Postiz's per-account channel list. */}
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {accounts.map((account) => (
                  <div
                    key={account.id}
                    className="flex justify-between items-center gap-2 p-2.5 rounded-xl border border-border bg-muted/20 hover:bg-muted/40 transition-all group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <ChannelAvatar account={account} size="size-10" />
                      <div className="min-w-0">
                        <h4 className="text-xs font-bold truncate">
                          {channels.find((c) => c.slug === account.slug)?.name ?? account.slug}
                        </h4>
                        <p className="text-[10px] text-muted-foreground truncate max-w-[130px]">
                          {account.handle ? `@${account.handle}` : account.displayName || (
                            <span className="text-emerald-500 font-semibold">Connected</span>
                          )}
                        </p>
                      </div>
                    </div>

                    <div className="relative">
                      <button
                        ref={(el) => { channelMenuBtnRefs.current[account.id] = el; }}
                        onClick={() => setActiveChannelMenu(activeChannelMenu === account.id ? null : account.id)}
                        className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted/80 cursor-pointer"
                      >
                        <MoreVertical className="size-4" />
                      </button>

                      <FloatingPopover
                        open={activeChannelMenu === account.id}
                        anchorRef={{ current: channelMenuBtnRefs.current[account.id] }}
                        onClose={() => setActiveChannelMenu(null)}
                        align="right"
                        className="w-40 p-1.5 space-y-0.5"
                      >
                          <button
                            onClick={() => {
                              openNewComposer({ accountId: account.id });
                              setActiveChannelMenu(null);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-muted font-semibold flex items-center gap-2"
                          >
                            <Send className="size-3 text-indigo-500" /> {t("channelMenu.createPost")}
                          </button>
                          <button
                            onClick={() => {
                              triggerCopy(account.id + "_channel_id");
                              setActiveChannelMenu(null);
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-muted font-semibold flex items-center gap-2"
                          >
                            <Copy className="size-3" /> {t("channelMenu.copyChannelId")}
                          </button>
                          <div className="h-[1px] bg-border my-1" />
                          <button
                            onClick={async () => {
                              await socialApi.accounts.disconnect(account.id);
                              setActiveChannelMenu(null);
                              fetchAccounts();
                              fetchIntegrations();
                            }}
                            className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-muted text-red-500 font-semibold flex items-center gap-2"
                          >
                            <Trash2 className="size-3" /> {t("channelMenu.delete")}
                          </button>
                      </FloatingPopover>
                    </div>
                  </div>
                ))}
                {accounts.length === 0 && (
                  <p className="text-[10px] text-muted-foreground text-center py-4">{t("sidebar.noChannels")}</p>
                )}
              </div>
            </div>
          </div>

          {/* Calendar weekly grid */}
          <div className="xl:col-span-3 bg-card rounded-2xl border border-border p-6 shadow-sm space-y-4">
            
            {/* Header controls */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/60 pb-4">
              <div className="flex items-center gap-3">
                <span className="text-base font-bold text-foreground">{t("calendar.title")}</span>
                <div className="flex items-center bg-muted/40 border border-border/40 rounded-xl p-1">
                  <button
                    onClick={() => shiftWeek(-1)}
                    className="p-1.5 hover:bg-card rounded-lg text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <ChevronLeft className="size-4" />
                  </button>
                  <button
                    onClick={() => setCurrentWeekStart(new Date())}
                    className="px-3 py-1 text-xs font-semibold hover:bg-card rounded-lg cursor-pointer"
                  >
                    {t("calendar.today")}
                  </button>
                  <button
                    onClick={() => shiftWeek(1)}
                    className="p-1.5 hover:bg-card rounded-lg text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <ChevronRight className="size-4" />
                  </button>
                </div>
                <span className="text-xs font-semibold text-muted-foreground">{getWeekRangeString()}</span>
              </div>

              <div className="flex items-center gap-1 bg-muted/40 border border-border/40 rounded-xl p-1">
                {(["day", "week", "month"] as const).map((view) => (
                  <button
                    key={view}
                    onClick={() => setCalendarView(view)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold capitalize cursor-pointer ${
                      calendarView === view ? "bg-card text-indigo-500 shadow-sm" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {t(`calendar.${view}`)}
                  </button>
                ))}
              </div>
            </div>

            {/* Grid wrapper - Fully Responsive */}
            <div className="overflow-x-auto">
              {/* Desktop view (only on md and up) */}
              <div className="hidden md:block min-w-[800px] border border-border/60 rounded-xl overflow-hidden bg-muted/5">
                
                {/* Columns headers */}
                <div className="grid grid-cols-8 border-b border-border bg-muted/30">
                  <div className="p-3 text-[10px] font-bold text-muted-foreground uppercase text-center border-r border-border/40">
                    Time
                  </div>
                  {weekDates.map((date, idx) => {
                    const isToday = new Date().toDateString() === date.toDateString();
                    return (
                      <div 
                        key={idx} 
                        className={`p-3 text-center border-r border-border/40 last:border-0 ${isToday ? "bg-indigo-500/5 text-indigo-500 font-bold" : ""}`}
                      >
                        <p className="text-[10px] uppercase font-semibold text-muted-foreground">
                          {date.toLocaleDateString(undefined, { weekday: "short" })}
                        </p>
                        <p className="text-sm">
                          {date.getDate()}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Grid hourly cells */}
                <div className="max-h-[500px] overflow-y-auto pr-1">
                  {hoursOfDay.map((hour) => (
                    <div key={hour} className="grid grid-cols-8 border-b border-border/40 last:border-0 group">
                      <div className="p-3 text-[10px] font-semibold text-muted-foreground text-center border-r border-border/40 flex items-center justify-center bg-muted/10">
                        {hour === 0 ? "12:00 AM" : hour < 12 ? `${hour}:00 AM` : hour === 12 ? "12:00 PM" : `${hour - 12}:00 PM`}
                      </div>

                      {weekDates.map((date, dayIdx) => {
                        const cellPosts = getPostsForCell(date, hour);
                        return (
                          <div 
                            key={dayIdx}
                            onClick={() => {
                              const scheduled = new Date(date);
                              scheduled.setHours(hour);
                              scheduled.setMinutes(0);
                              const offset = scheduled.getTimezoneOffset();
                              const localDate = new Date(scheduled.getTime() - (offset*60*1000));
                              openNewComposer({ publishDate: localDate.toISOString().slice(0, 16) });
                            }}
                            className="p-1 border-r border-border/40 last:border-0 min-h-[50px] relative hover:bg-indigo-500/5 transition-all cursor-pointer flex flex-col gap-1"
                          >
                            {cellPosts.map((post) => (
                              <div
                                key={post.id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openEditComposer(post);
                                }}
                                className={`p-1.5 rounded-lg text-[9px] font-bold border leading-tight ${
                                  post.state === "published"
                                    ? "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/20 dark:text-emerald-400 dark:border-emerald-900/30"
                                    : post.state === "failed"
                                    ? "bg-red-50 text-red-800 border-red-200 dark:bg-red-950/20 dark:text-red-400 dark:border-red-900/30"
                                    : "bg-indigo-50 text-indigo-800 border-indigo-200 dark:bg-indigo-950/20 dark:text-indigo-400 dark:border-indigo-900/30"
                                }`}
                              >
                                <div className="flex items-center gap-1 mb-0.5 uppercase tracking-wider text-[8px]">
                                  {post.integration_slug}
                                </div>
                                <p className="truncate">{post.content}</p>
                              </div>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>

              </div>

              {/* Mobile View: Clean card list feed (displays below md viewport) */}
              <div className="block md:hidden space-y-4">
                {weekDates.map((date, idx) => {
                  const dayPosts = posts.filter(p => new Date(p.publish_date).toDateString() === date.toDateString());
                  return (
                    <div key={idx} className="p-4 rounded-xl border border-border bg-muted/10 space-y-3">
                      <div className="flex justify-between items-center border-b border-border/40 pb-2">
                        <span className="text-xs font-bold text-foreground capitalize">
                          {date.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
                        </span>
                        <Button 
                          size="sm" 
                          variant="ghost" 
                          className="h-7 text-[10px] font-bold gap-1 text-indigo-500"
                          onClick={() => {
                            const scheduled = new Date(date);
                            scheduled.setHours(9);
                            scheduled.setMinutes(0);
                            const offset = scheduled.getTimezoneOffset();
                            const localDate = new Date(scheduled.getTime() - (offset*60*1000));
                            openNewComposer({ publishDate: localDate.toISOString().slice(0, 16) });
                          }}
                        >
                          <Plus className="size-3" /> {t("calendar.addPost")}
                        </Button>
                      </div>

                      {dayPosts.length === 0 ? (
                        <p className="text-[10px] text-muted-foreground py-2 text-center">{t("calendar.noPosts")}</p>
                      ) : (
                        <div className="space-y-2">
                          {dayPosts.map((post) => (
                            <div
                              key={post.id}
                              onClick={() => {
                                openEditComposer(post);
                              }}
                              className="p-3 rounded-lg border border-border bg-card flex justify-between items-center"
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase bg-neutral-900 text-white">
                                    {post.integration_slug}
                                  </span>
                                  <span className="text-[9px] text-muted-foreground">
                                    {new Date(post.publish_date).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                                  </span>
                                </div>
                                <p className="text-xs line-clamp-2">{post.content}</p>
                              </div>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={(e) => { e.stopPropagation(); handleDeletePost(post.id); }}
                                className="text-red-500 p-1 hover:bg-red-50 dark:hover:bg-red-950/20"
                              >
                                <Trash2 className="size-3.5" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

            </div>

          </div>

        </div>
      )}

      {/* ==================== MODAL: CREATE POST SPLIT COMPOSER ==================== */}
      {showComposer && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-5xl rounded-2xl border border-border shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">

            {/* Sticky header: title, close, and channel selector always stay
                visible regardless of how tall the form/preview content grows —
                these were the controls users reported as "cropped" when they
                scrolled inside the old single scrolling pane. */}
            <div className="shrink-0 p-6 pb-3 border-b border-border/60 space-y-2">
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold flex items-center gap-2">
                  <Share2 className="size-4.5 text-indigo-500" />
                  {editingPostId ? t("composer.editTitle") : t("composer.title")}
                </h3>
                <button
                  type="button"
                  onClick={() => {
                    setShowComposer(false);
                    setEditingPostId(null);
                  }}
                  className="text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="size-5" />
                </button>
              </div>

              {/* Channel multi-select: clicking toggles an account in/out of
                  selectedAccountIds (a real multi-select, not single-select
                  radio behavior) — mirrors Postiz's avatar-chip picker, which
                  lets one post target several accounts at once, including
                  more than one account on the same platform. */}
              {/* px-1 -mx-1: the selected icon's scale-105 needs a little
                  room at the very start/end of the row, otherwise the
                  overflow-x-auto boundary clips it flush at scroll position 0
                  (looks like the circle is "cropped" at the start). The
                  negative margin cancels the padding's visual indent so the
                  row still lines up with the header/content above it. */}
              <div className="flex items-center gap-2 py-1 px-1 -mx-1 overflow-x-auto overflow-y-visible scrollbar-none">
                {accounts.map((account) => {
                  const isSelected = selectedAccountIds.includes(account.id);
                  return (
                    <button
                      key={account.id}
                      type="button"
                      onClick={() =>
                        setSelectedAccountIds((prev) =>
                          isSelected ? prev.filter((id) => id !== account.id) : [...prev, account.id],
                        )
                      }
                      className={`size-10 rounded-full border flex items-center justify-center relative cursor-pointer transition-all shrink-0 ${
                        isSelected
                          ? "border-transparent ring-2 ring-indigo-500 scale-105 bg-neutral-900"
                          : "border-border bg-muted/40 hover:bg-muted opacity-60 hover:opacity-100"
                      }`}
                    >
                      {/* overflow-hidden lives on this inner wrapper, not the
                          button itself — the selected-badge below sits on the
                          button's rim via negative offsets and was getting
                          clipped when the button carried overflow-hidden. */}
                      <span className="size-full rounded-full overflow-hidden flex items-center justify-center">
                        <ChannelIcon slug={account.slug} className="size-5" />
                      </span>
                      {isSelected && (
                        <span className="absolute -bottom-0.5 -right-0.5 size-3.5 bg-indigo-500 rounded-full border-2 border-card flex items-center justify-center">
                          <Check className="size-2 text-white" />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Global / per-channel content tabs — only shown once 2+
                  accounts are selected, since with one account there's
                  nothing for Global to differ from. Matches Postiz: content
                  is shared (Global) by default, and a channel only becomes
                  independent once you switch to its tab and edit it there. */}
              {selectedAccountIds.length > 1 && (
                <div className="flex items-center gap-1.5 pt-1 overflow-x-auto scrollbar-none">
                  <button
                    type="button"
                    onClick={() => setActiveComposerTab("global")}
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1.5 shrink-0 cursor-pointer ${
                      activeComposerTab === "global"
                        ? "bg-indigo-600 text-white"
                        : "bg-muted/40 text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    <Globe className="size-3" /> Global
                  </button>
                  {selectedAccountIds.map((accountId) => {
                    const account = accountsById[accountId];
                    if (!account) return null;
                    const hasOverride = accountId in contentOverrides;
                    return (
                      <button
                        key={accountId}
                        type="button"
                        onClick={() => setActiveComposerTab(accountId)}
                        className={`pl-1 pr-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1.5 shrink-0 cursor-pointer relative ${
                          activeComposerTab === accountId
                            ? "bg-indigo-600 text-white"
                            : "bg-muted/40 text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        <span className="size-4 rounded-full overflow-hidden flex items-center justify-center bg-neutral-900">
                          <ChannelIcon slug={account.slug} className="size-2.5" />
                        </span>
                        {account.handle || account.displayName || account.name}
                        {hasOverride && (
                          <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-pink-500" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Scrollable body: on desktop the editor and preview are two
                independently-scrolling side-by-side panes. On mobile they
                stack — giving each pane its own overflow-y-auto there would
                force a 50/50 height split regardless of content, squeezing
                the preview into a tiny fixed box, so on mobile the OUTER
                wrapper scrolls as a single column instead and each pane
                just takes its natural height. */}
            <div className="flex-1 min-h-0 flex flex-col md:flex-row overflow-y-auto md:overflow-hidden">

            {/* Left Pane: Editor */}
            <form onSubmit={handleCreatePost} className="flex-1 p-6 md:overflow-y-auto border-r border-border/80 space-y-4">
              <div className="space-y-4">
                {/* content textarea */}
                <div>
                  <textarea
                    ref={contentTextareaRef}
                    value={composerContent}
                    onChange={(e) => setComposerContent(e.target.value)}
                    placeholder={
                      activeComposerTab === "global"
                        ? t("composer.placeholder")
                        : `Override for ${accountsById[activeComposerTab]?.handle || accountsById[activeComposerTab]?.name || "this channel"}...`
                    }
                    rows={6}
                    className="w-full rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  {activeComposerTab !== "global" && activeComposerTab in contentOverrides && (
                    <button
                      type="button"
                      onClick={() =>
                        setContentOverrides((prev) => {
                          const next = { ...prev };
                          delete next[activeComposerTab];
                          return next;
                        })
                      }
                      className="text-[10px] text-indigo-500 font-bold hover:underline mt-1 cursor-pointer"
                    >
                      Reset to global content
                    </button>
                  )}
                  
                  {/* editor toolbars */}
                  <div className="flex justify-between items-center mt-2 px-1">
                    <div className="flex items-center gap-3 text-muted-foreground">
                      <input
                        ref={composerFileInputRef}
                        type="file"
                        accept="image/*,video/*"
                        onChange={handleComposerMediaUpload}
                        className="hidden"
                      />
                      <button
                        type="button"
                        disabled={composerUploading}
                        onClick={() => composerFileInputRef.current?.click()}
                        className="hover:text-foreground cursor-pointer flex items-center gap-1 text-[11px] font-bold disabled:opacity-50"
                      >
                        <ImageIcon className="size-4 text-indigo-500" />
                        {composerUploading ? t("composer.uploading") : t("composer.insertMedia")}
                      </button>
                      <button
                        type="button"
                        title="Bold selected text"
                        onClick={handleBold}
                        className="hover:text-foreground cursor-pointer"
                      >
                        <Bold className="size-4" />
                      </button>
                      <button
                        type="button"
                        title="Underline selected text"
                        onClick={handleUnderline}
                        className="hover:text-foreground cursor-pointer"
                      >
                        <Underline className="size-4" />
                      </button>
                      <div className="relative">
                        <button
                          ref={emojiBtnRef}
                          type="button"
                          title="Insert emoji"
                          onClick={() => setShowEmojiPicker((s) => !s)}
                          className="hover:text-foreground cursor-pointer"
                        >
                          <Smile className="size-4" />
                        </button>
                        <FloatingPopover
                          open={showEmojiPicker}
                          anchorRef={emojiBtnRef}
                          onClose={() => setShowEmojiPicker(false)}
                          className="grid grid-cols-8 gap-1 p-2 w-56"
                        >
                          {EMOJI_PICKS.map((emoji) => (
                            <button
                              key={emoji}
                              type="button"
                              onClick={() => insertEmoji(emoji)}
                              className="text-base hover:bg-muted rounded p-1 cursor-pointer"
                            >
                              {emoji}
                            </button>
                          ))}
                        </FloatingPopover>
                      </div>
                    </div>
                    <span className={`text-[10px] font-semibold ${composerContent.length > charLimit ? 'text-red-500 font-bold' : 'text-muted-foreground'}`}>
                      {composerContent.length}/{charLimit}
                    </span>
                  </div>
                </div>

                {/* Comment box */}
                <div className="border-t border-border/50 pt-3">
                  <label className="flex items-center gap-2 cursor-pointer mb-2">
                    <input
                      type="checkbox"
                      checked={addComment}
                      onChange={(e) => setAddComment(e.target.checked)}
                      className="rounded border-border focus:ring-indigo-500"
                    />
                    <span className="text-xs font-semibold text-indigo-500">
                      {t("composer.addComment")}
                    </span>
                  </label>
                  {addComment && (
                    <textarea
                      value={commentContent}
                      onChange={(e) => setCommentContent(e.target.value)}
                      placeholder={t("composer.commentPlaceholder")}
                      rows={2}
                      className="w-full rounded-lg border border-border bg-background p-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  )}
                </div>

                {/* Collapsible Accordion Settings Panel */}
                <div className="space-y-3">
                  <div 
                    onClick={() => setShowSettingsAccordion(!showSettingsAccordion)}
                    className="bg-indigo-600 hover:bg-indigo-700 rounded-xl px-4 py-2.5 flex items-center justify-between text-white text-xs font-bold cursor-pointer transition-all shadow-sm select-none"
                  >
                    <span className="flex items-center gap-2">
                      <Settings className="size-4 animate-spin-slow" /> {t("composer.settings")}
                    </span>
                    <ChevronDown className={`size-4 transition-transform duration-200 ${showSettingsAccordion ? 'rotate-180' : ''}`} />
                  </div>

                  {showSettingsAccordion && (
                    <div className="p-4 rounded-xl border border-border bg-muted/10 space-y-4 animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="flex items-center gap-2 border-b border-border/40 pb-2">
                        <div className="size-6 rounded-full bg-neutral-900 border border-border flex items-center justify-center relative shadow-sm">
                          {LOGOS[activeSlug] || <Globe className="size-3 text-white" />}
                        </div>
                        <h4 className="text-xs font-bold uppercase tracking-wider">{activeSlug} Settings</h4>
                      </div>

                      {/* Instagram */}
                      {activeSlug === "instagram" && (
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Post Type
                            </label>
                            <Select
                              value={instaPostType}
                              onChange={setInstaPostType}
                              options={[
                                { value: "post_reel", label: "Post / Reel" },
                                { value: "story", label: "Story" },
                              ]}
                            />
                          </div>

                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Collaborators (max 3) - accounts can&apos;t be private
                            </label>
                            <div className="flex gap-2">
                              <input 
                                type="text" 
                                placeholder="Add a tag..." 
                                value={instaCollaboratorInput}
                                onChange={(e) => setInstaCollaboratorInput(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    if (instaCollaboratorInput.trim() && instaCollaborators.length < 3) {
                                      setInstaCollaborators([...instaCollaborators, instaCollaboratorInput.trim()]);
                                      setInstaCollaboratorInput("");
                                    }
                                  }
                                }}
                                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none"
                              />
                              <Button 
                                type="button" 
                                size="sm"
                                onClick={() => {
                                  if (instaCollaboratorInput.trim() && instaCollaborators.length < 3) {
                                    setInstaCollaborators([...instaCollaborators, instaCollaboratorInput.trim()]);
                                    setInstaCollaboratorInput("");
                                  }
                                }}
                              >
                                Add
                              </Button>
                            </div>
                            {instaCollaborators.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-2">
                                {instaCollaborators.map((c, i) => (
                                  <span key={i} className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-500 text-[10px] font-bold flex items-center gap-1">
                                    @{c}
                                    <button type="button" onClick={() => setInstaCollaborators(instaCollaborators.filter((_, idx) => idx !== i))}>
                                      <X className="size-3 cursor-pointer" />
                                    </button>
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Audio (Reels only - single video)
                            </label>
                            <div className="flex gap-2">
                              <Select
                                value="music"
                                onChange={() => {}}
                                options={[{ value: "music", label: "Music" }]}
                                className="w-28 shrink-0"
                              />
                              <input 
                                type="text" 
                                placeholder="Search audio (empty shows trending)" 
                                value={instaAudio}
                                onChange={(e) => setInstaAudio(e.target.value)}
                                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none"
                              />
                              <button 
                                type="button" 
                                onClick={() => setInstaAudio("")}
                                className="px-3 py-2 border border-border rounded-lg text-xs hover:bg-muted font-bold cursor-pointer"
                              >
                                Cancel
                              </button>
                            </div>
                            <div className="p-3 border border-border/40 rounded-lg text-center text-[10px] text-muted-foreground bg-muted/20 mt-1">
                              No audio found
                            </div>
                          </div>

                          <label className="flex items-center gap-2 cursor-pointer pt-1">
                            <input 
                              type="checkbox" 
                              checked={instaTrialReel}
                              onChange={(e) => setInstaTrialReel(e.target.checked)}
                              className="rounded border-border focus:ring-indigo-500"
                            />
                            <span className="text-xs font-semibold text-muted-foreground">
                              Trial Reel (share only to non-followers first)
                            </span>
                          </label>
                        </div>
                      )}

                      {/* X */}
                      {activeSlug === "x" && (
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Who can reply
                            </label>
                            <Select
                              value={xReplyPrivacy}
                              onChange={setXReplyPrivacy}
                              options={[
                                { value: "everyone", label: "Everyone" },
                                { value: "followed", label: "Accounts you follow" },
                                { value: "mentioned", label: "Only accounts you mention" },
                              ]}
                            />
                          </div>

                          <label className="flex items-center gap-2 cursor-pointer">
                            <input 
                              type="checkbox" 
                              checked={xIsPremiumFormat}
                              onChange={(e) => setXIsPremiumFormat(e.target.checked)}
                              className="rounded border-border focus:ring-indigo-500"
                            />
                            <span className="text-xs font-semibold text-muted-foreground">
                              Enable premium long post format (up to 25k chars)
                            </span>
                          </label>
                        </div>
                      )}

                      {/* LinkedIn */}
                      {activeSlug === "linkedin" && (
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Who can comment
                            </label>
                            <Select
                              value={linkedinCommentPrivacy}
                              onChange={setLinkedinCommentPrivacy}
                              options={[
                                { value: "anyone", label: "Anyone" },
                                { value: "connections", label: "Connections only" },
                                { value: "none", label: "No one" },
                              ]}
                            />
                          </div>

                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Visibility
                            </label>
                            <Select
                              value={linkedinVisibility}
                              onChange={setLinkedinVisibility}
                              options={[
                                { value: "anyone", label: "Anyone (Public)" },
                                { value: "connections", label: "Connections only" },
                              ]}
                            />
                          </div>
                        </div>
                      )}

                      {/* YouTube */}
                      {activeSlug === "youtube" && (
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Video Privacy
                            </label>
                            <Select
                              value={ytPrivacy}
                              onChange={setYtPrivacy}
                              options={[
                                { value: "public", label: "Public" },
                                { value: "unlisted", label: "Unlisted" },
                                { value: "private", label: "Private" },
                              ]}
                            />
                          </div>

                          <label className="flex items-center gap-2 cursor-pointer">
                            <input 
                              type="checkbox" 
                              checked={ytMadeForKids}
                              onChange={(e) => setYtMadeForKids(e.target.checked)}
                              className="rounded border-border focus:ring-indigo-500"
                            />
                            <span className="text-xs font-semibold text-muted-foreground">
                              Yes, it&apos;s made for kids
                            </span>
                          </label>
                        </div>
                      )}

                      {/* TikTok */}
                      {activeSlug === "tiktok" && (
                        <div className="space-y-4">
                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Video Privacy
                            </label>
                            <Select
                              value={tiktokPrivacy}
                              onChange={setTiktokPrivacy}
                              options={[
                                { value: "everyone", label: "Everyone" },
                                { value: "friends", label: "Friends only" },
                                { value: "self", label: "Private" },
                              ]}
                            />
                          </div>

                          <div className="flex flex-col gap-2 pt-1">
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input 
                                type="checkbox" 
                                checked={tiktokAllowComments}
                                onChange={(e) => setTiktokAllowComments(e.target.checked)}
                                className="rounded border-border focus:ring-indigo-500"
                              />
                              <span className="text-xs font-semibold text-muted-foreground">Allow Comments</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input 
                                type="checkbox" 
                                checked={tiktokAllowDuets}
                                onChange={(e) => setTiktokAllowDuets(e.target.checked)}
                                className="rounded border-border focus:ring-indigo-500"
                              />
                              <span className="text-xs font-semibold text-muted-foreground">Allow Duet</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input 
                                type="checkbox" 
                                checked={tiktokAllowStitch}
                                onChange={(e) => setTiktokAllowStitch(e.target.checked)}
                                className="rounded border-border focus:ring-indigo-500"
                              />
                              <span className="text-xs font-semibold text-muted-foreground">Allow Stitch</span>
                            </label>
                          </div>
                        </div>
                      )}

                      {/* Fallback default settings */}
                      {!["instagram", "x", "linkedin", "youtube", "tiktok"].includes(activeSlug) && (
                        <div className="space-y-3">
                          <p className="text-[10px] text-muted-foreground">No custom settings required for {activeSlug}. Standard publish limits apply.</p>
                          <div>
                            <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                              Audience targeting
                            </label>
                            <Select
                              value="public"
                              onChange={() => {}}
                              options={[{ value: "public", label: "Public / All followers" }]}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* media & date picker */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                      Media URL
                    </label>
                    <input
                      type="text"
                      value={imageUrl}
                      onChange={(e) => setImageUrl(e.target.value)}
                      placeholder="https://example.com/image.jpg"
                      className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  {/* Premium calendar date picker trigger */}
                  <div className="relative">
                    <label className="text-[10px] font-bold text-muted-foreground block mb-1 uppercase tracking-wider">
                      Publish Date
                    </label>
                    <button
                      ref={dateBtnRef}
                      type="button"
                      onClick={() => setShowDatePicker(!showDatePicker)}
                      className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-left flex items-center justify-between hover:bg-muted/40 cursor-pointer"
                    >
                      <span className="truncate">{publishDate ? new Date(publishDate).toLocaleString() : "Select Date & Time"}</span>
                      <CalendarIcon className="size-4 text-indigo-500" />
                    </button>

                    {/* Rendered via a portal (FloatingPopover) so it isn't
                        clipped by the composer pane's own overflow-y-auto —
                        that clipping, not positioning, was the actual cause
                        of the popover appearing "cropped". */}
                    <FloatingPopover
                      open={showDatePicker}
                      anchorRef={dateBtnRef}
                      onClose={() => setShowDatePicker(false)}
                      className="w-64"
                    >
                      <div className="p-4 space-y-3">
                        <div className="flex justify-between items-center text-xs font-bold">
                          <span>{pickerDate.toLocaleString(undefined, { month: 'long', year: 'numeric' })}</span>
                          <div className="flex gap-1">
                            <button 
                              type="button" 
                              onClick={() => setPickerDate(new Date(pickerDate.setMonth(pickerDate.getMonth() - 1)))}
                              className="p-1 hover:bg-muted rounded"
                            >
                              <ChevronLeft className="size-3" />
                            </button>
                            <button 
                              type="button" 
                              onClick={() => setPickerDate(new Date(pickerDate.setMonth(pickerDate.getMonth() + 1)))}
                              className="p-1 hover:bg-muted rounded"
                            >
                              <ChevronRight className="size-3" />
                            </button>
                          </div>
                        </div>

                        {/* Calendar days grid — padded with leading blanks so
                            day numbers line up under the correct weekday
                            column instead of always starting at S. */}
                        <div className="grid grid-cols-7 gap-1 text-center text-[10px]">
                          {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                            <span key={i} className="text-muted-foreground font-semibold pb-1">{d}</span>
                          ))}
                          {Array.from({ length: getFirstWeekdayOfPickerMonth() }, (_, i) => (
                            <span key={`blank-${i}`} />
                          ))}
                          {Array.from({ length: getDaysInPickerMonth() }, (_, i) => i + 1).map((dayNum) => {
                            const cellDate = new Date(pickerDate.getFullYear(), pickerDate.getMonth(), dayNum);
                            const isToday = cellDate.toDateString() === new Date().toDateString();
                            const isSelected = publishDate && cellDate.toDateString() === new Date(publishDate).toDateString();
                            return (
                              <button
                                key={dayNum}
                                type="button"
                                onClick={() => handlePickerDateSelect(dayNum)}
                                className={`p-1 rounded font-bold cursor-pointer ${
                                  isSelected
                                    ? "bg-indigo-600 text-white"
                                    : isToday
                                    ? "ring-1 ring-indigo-500 text-indigo-500"
                                    : "hover:bg-indigo-600 hover:text-white"
                                }`}
                              >
                                {dayNum}
                              </button>
                            );
                          })}
                        </div>

                        {/* Time Selectors */}
                        <div className="border-t border-border/50 pt-2 grid grid-cols-3 gap-1">
                          <Select
                            value={pickerHour}
                            onChange={setPickerHour}
                            options={Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0")).map((h) => ({
                              value: h,
                              label: h,
                            }))}
                            className="text-[10px]"
                          />
                          <Select
                            value={pickerMinute}
                            onChange={setPickerMinute}
                            options={Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, "0")).map((m) => ({
                              value: m,
                              label: m,
                            }))}
                            className="text-[10px]"
                          />
                          <Select
                            value={pickerAmpm}
                            onChange={setPickerAmpm}
                            options={[
                              { value: "AM", label: "AM" },
                              { value: "PM", label: "PM" },
                            ]}
                            className="text-[10px]"
                          />
                        </div>
                      </div>
                    </FloatingPopover>
                  </div>
                </div>
              </div>

              {/* Tag Selection & Repeat settings */}
              <div className="flex flex-wrap gap-2 pt-2 relative">
                
                {/* Custom Tags Dropdown */}
                <div className="relative">
                  <button
                    ref={tagBtnRef}
                    type="button"
                    onClick={() => setShowTagSelector(!showTagSelector)}
                    className="px-3 py-1.5 rounded-lg border border-border bg-muted/40 hover:bg-muted text-[10px] font-bold flex items-center gap-1.5 cursor-pointer"
                  >
                    {selectedTag ? (
                      <span className="flex items-center gap-1.5">
                        <span className="size-2 rounded-full" style={{ backgroundColor: selectedTag.color }} />
                        {selectedTag.name}
                      </span>
                    ) : (
                      <>Add New Tag <ChevronDown className="size-3" /></>
                    )}
                  </button>

                  <FloatingPopover
                    open={showTagSelector}
                    anchorRef={tagBtnRef}
                    onClose={() => setShowTagSelector(false)}
                    className="w-48 p-3 space-y-2.5"
                  >
                      <div className="space-y-1">
                        <p className="text-[9px] uppercase font-bold text-muted-foreground">Select Tag</p>
                        <div className="max-h-24 overflow-y-auto pr-1 space-y-1">
                          {tags.map((tag) => (
                            <button
                              key={tag.id}
                              type="button"
                              onClick={() => {
                                setSelectedTag(tag);
                                setShowTagSelector(false);
                              }}
                              className="w-full text-left px-2 py-1 rounded hover:bg-muted text-[10px] flex items-center gap-2"
                            >
                              <span className="size-2 rounded-full" style={{ backgroundColor: tag.color }} />
                              {tag.name}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="border-t border-border/50 pt-2 space-y-1.5">
                        <input
                          type="text"
                          value={customTagInput}
                          onChange={(e) => setCustomTagInput(e.target.value)}
                          placeholder="Tag name"
                          className="w-full rounded border border-border bg-background px-2 py-1 text-[10px]"
                        />
                        <div className="flex justify-between items-center">
                          <input
                            type="color"
                            value={customTagColor}
                            onChange={(e) => setCustomTagColor(e.target.value)}
                            className="size-5 rounded border-0 cursor-pointer"
                          />
                          <Button size="sm" type="button" className="h-6 text-[9px]" onClick={handleCreateTag}>
                            Add Tag
                          </Button>
                        </div>
                      </div>
                  </FloatingPopover>
                </div>

                {/* Custom Repeat Dropdown */}
                <div className="relative">
                  <button
                    ref={repeatBtnRef}
                    type="button"
                    onClick={() => setShowRepeatSelector(!showRepeatSelector)}
                    className="px-3 py-1.5 rounded-lg border border-border bg-muted/40 hover:bg-muted text-[10px] font-bold flex items-center gap-1.5 cursor-pointer"
                  >
                    {t("composer.repeat", { interval: repeatInterval })} <ChevronDown className="size-3" />
                  </button>

                  <FloatingPopover
                    open={showRepeatSelector}
                    anchorRef={repeatBtnRef}
                    onClose={() => setShowRepeatSelector(false)}
                    className="w-40 p-1.5 space-y-0.5"
                  >
                      {["None", "Every Day", "Every Week", "Every Month"].map((interval) => (
                        <button
                          key={interval}
                          type="button"
                          onClick={() => {
                            setRepeatInterval(interval);
                            setShowRepeatSelector(false);
                          }}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs hover:bg-muted font-semibold flex items-center justify-between"
                        >
                          {interval}
                          {repeatInterval === interval && <Check className="size-3.5 text-indigo-500" />}
                        </button>
                      ))}
                  </FloatingPopover>
                </div>

              </div>

            </form>

            {/* Right Pane: Post Preview */}
            <div className="flex-1 p-6 bg-muted/10 md:overflow-y-auto space-y-4">
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-widest">
                Post Preview
              </h3>

              {composerContent ? (
                renderPlatformPreview()
              ) : (
                <div className="text-center py-12 text-xs text-muted-foreground">
                  Start writing your post for a preview
                </div>
              )}
            </div>

            </div>

            {/* Sticky footer: publish-date indicator + submit actions always
                stay reachable without scrolling. */}
            <div className="shrink-0 p-4 border-t border-border/60 space-y-2">
              {publishDate && (
                <p className="text-[10px] text-indigo-500 font-bold flex items-center gap-1.5">
                  <Clock className="size-3.5" /> Will publish on: {new Date(publishDate).toLocaleString()}
                </p>
              )}
              <div className="flex gap-2">
                {/* Only shown when editing an existing post — the desktop
                    calendar grid has no delete affordance of its own (that
                    only existed in the mobile-only list view), so this was
                    the one place a scheduled/draft post could actually be
                    removed from. */}
                {editingPostId && (
                  <Button
                    type="button"
                    variant="outline"
                    className="text-xs text-red-500 border-red-500/30 hover:bg-red-500/10"
                    onClick={async () => {
                      if (!window.confirm(t("composer.deleteConfirm"))) return;
                      await handleDeletePost(editingPostId);
                      setEditingPostId(null);
                      setShowComposer(false);
                    }}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 text-xs"
                  onClick={(e) => handleCreatePost(e, true)}
                >
                  {t("composer.saveDraft")}
                </Button>
                <Button
                  type="button"
                  className="flex-1 text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                  onClick={(e) => handleCreatePost(e, false)}
                >
                  {editingPostId ? t("composer.update") : t("composer.schedule")}
                </Button>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ==================== MODAL: CONFIGURE CHANNEL ==================== */}
      <Dialog
        open={showChannelConnect && !manualConnectSlug}
        onClose={() => setShowChannelConnect(false)}
        title={t("connect.title")}
        description={t("connect.help")}
        size="md"
      >
        {connectError && (
          <p className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
            {connectError}
          </p>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-80 overflow-y-auto pr-1">
          {channels.map((chan) => {
            const isReal = realSlugs.includes(chan.slug);
            const alreadyConnected = connectedSlugs.includes(chan.slug);
            return (
              <button
                key={chan.slug}
                onClick={() => isReal && handleStartConnect(chan.slug)}
                disabled={!isReal}
                className="p-3 rounded-xl border border-border bg-muted/40 hover:bg-muted/70 transition-all text-center space-y-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <div className="size-12 rounded-full bg-neutral-900 border border-border flex items-center justify-center mx-auto shadow-sm">
                  {LOGOS[chan.slug] || <Globe className="size-4 text-white" />}
                </div>
                <h4 className="text-[10px] font-bold leading-tight">{chan.name}</h4>
                {!isReal ? (
                  <span className="block text-[9px] text-muted-foreground">{t("connect.comingSoon")}</span>
                ) : alreadyConnected ? (
                  <span className="block text-[9px] text-emerald-500 font-semibold">{t("connect.addAnother")}</span>
                ) : null}
              </button>
            );
          })}
        </div>

        <DialogFooter>
          <Button onClick={() => setShowChannelConnect(false)} variant="outline" className="w-full text-xs">
            {t("connect.close")}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* ==================== MODAL: MANUAL CONNECT FORM ==================== */}
      <Dialog
        open={!!manualConnectSlug && !!MANUAL_CONNECT_FIELDS[manualConnectSlug || ""]}
        onClose={() => setManualConnectSlug(null)}
        title={t("connect.connectTitle", {
          name: channels.find((c) => c.slug === manualConnectSlug)?.name || manualConnectSlug || "",
        })}
        size="md"
      >
        <form onSubmit={handleManualConnectSubmit}>
          {connectError && (
            <p className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">
              {connectError}
            </p>
          )}

          {manualConnectSlug &&
            MANUAL_CONNECT_FIELDS[manualConnectSlug]?.map((field) => (
              <Field key={field.key} label={field.label}>
                <input
                  type="text"
                  value={manualForm[field.key] || ""}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, [field.key]: e.target.value }))}
                  placeholder={field.placeholder}
                  className={inputCls}
                />
              </Field>
            ))}

          <DialogFooter>
            <Button type="submit" disabled={manualSubmitting} className="w-full text-xs">
              {manualSubmitting ? t("connect.connecting") : t("connect.connectCta")}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* ==================== AI COPILOT WORKSPACE ==================== */}
      {activeTab === "agent" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
              <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
                <Sparkles className="size-5 text-indigo-500" />
                AI Content Generator & Copilot
              </h2>
              
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-muted-foreground block mb-1 font-medium">
                    What should the post be about? (Prompt / Instructions)
                  </label>
                  <textarea
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    placeholder="e.g. A series of hooks introducing the new Supabase vector extensions or outlining a case study on Next.js server actions."
                    rows={4}
                    className="w-full rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1 font-medium">
                      Reference URL (Optional)
                    </label>
                    <input
                      type="url"
                      value={aiUrl}
                      onChange={(e) => setAiUrl(e.target.value)}
                      placeholder="https://myblog.com/new-release"
                      className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1 font-medium">
                      Tone Style
                    </label>
                    <Select
                      value={aiTone}
                      onChange={setAiTone}
                      options={[
                        { value: "viral", label: "Viral Hook" },
                        { value: "professional", label: "Professional / Educational" },
                        { value: "casual", label: "Casual / Friendly" },
                        { value: "corporate", label: "Corporate Announcement" },
                      ]}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground block mb-1 font-medium">
                      Generation Goal
                    </label>
                    <Select
                      value={aiType}
                      onChange={setAiType}
                      options={[
                        { value: "outlines", label: "Draft Outlines" },
                        { value: "posts", label: "Full Post Drafts" },
                        { value: "hooks", label: "Platform Hooks / Headlines" },
                      ]}
                    />
                  </div>
                </div>

                <Button 
                  onClick={handleAiCopilotGenerate} 
                  disabled={aiGenerating || !aiPrompt.trim()}
                  className="w-full gap-2"
                >
                  <Sparkles className="size-4" />
                  {aiGenerating ? "Gemini is analyzing & drafting..." : "Generate AI Copy"}
                </Button>
              </div>
            </div>

            {aiOutlines.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground">Generated Recommendations:</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {aiOutlines.map((out, idx) => (
                    <div key={idx} className="p-4 rounded-xl border border-border bg-card space-y-3 relative group">
                      <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed">{out}</pre>
                      <Button
                        onClick={() => {
                          setActiveTab("launches");
                          openNewComposer({ content: out.split("\n").slice(1).join("\n") });
                        }}
                        className="w-full text-xs bg-indigo-600 text-white font-bold"
                        size="sm"
                      >
                        Apply to Composer
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          <div className="space-y-6">
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-3">
              <h3 className="text-base font-semibold">AI Assistant Settings</h3>
              <p className="text-xs text-muted-foreground">
                Kin uses Gemini Pro models to generate outlines and schedule copies grounded in your connected files.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ==================== MEDIA LIBRARY ==================== */}
      {activeTab === "media" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-2">
              <ImageIcon className="size-5 text-indigo-500" />
              Media Library
            </h2>
            <p className="text-xs text-muted-foreground mb-4">
              Upload images, videos, and graphical assets to publish. Assets are stored securely in your Supabase bucket.
            </p>

            <div className="border-2 border-dashed border-border rounded-xl p-8 text-center bg-muted/10 relative hover:bg-muted/20 transition-all">
              <input
                type="file"
                onChange={handleFileUpload}
                accept="image/*,video/*"
                className="absolute inset-0 opacity-0 cursor-pointer"
                disabled={uploading}
              />
              <ImageIcon className="size-10 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm font-semibold">
                {uploading ? "Uploading asset to storage..." : "Click or drag & drop to upload files"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Supports PNG, JPG, GIF, WebP, and MP4 files up to 20MB
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {mediaFiles.map((file, idx) => (
              <div key={idx} className="rounded-xl border border-border bg-card overflow-hidden group shadow-sm flex flex-col justify-between">
                <div className="aspect-video bg-muted relative flex items-center justify-center overflow-hidden">
                  <img src={file.url} alt={file.name} className="object-cover w-full h-full" />
                </div>
                <div className="p-3 space-y-2 border-t border-border/50">
                  <p className="text-xs font-semibold truncate">{file.name.substring(7)}</p>
                  <p className="text-[10px] text-muted-foreground">
                    Size: {(file.size / 1024).toFixed(1)} KB
                  </p>
                  <div className="flex gap-1.5 pt-1">
                    <Button
                      variant="outline"
                      className="flex-1 text-[10px] h-7 gap-1"
                      onClick={() => triggerCopy(file.url)}
                    >
                      {copiedUrl === file.url ? <CheckCheck className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                      Copy Link
                    </Button>
                    <Button
                      className="flex-1 text-[10px] h-7"
                      onClick={() => {
                        setActiveTab("launches");
                        openNewComposer({ imageUrl: file.url });
                      }}
                    >
                      Use
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================== ANALYTICS DASHBOARD ==================== */}
      {activeTab === "analytics" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-5 rounded-2xl border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold">
                {t("analytics.impressions")}
                <Eye className="size-4.5 text-blue-500" />
              </div>
              <div className="text-2xl font-bold">{analytics.impressions.toLocaleString()}</div>
            </div>

            <div className="p-5 rounded-2xl border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold">
                {t("analytics.clicks")}
                <MousePointerClick className="size-4.5 text-emerald-500" />
              </div>
              <div className="text-2xl font-bold">{analytics.clicks.toLocaleString()}</div>
            </div>

            <div className="p-5 rounded-2xl border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold">
                {t("analytics.likes")}
                <Heart className="size-4.5 text-red-500" />
              </div>
              <div className="text-2xl font-bold">{analytics.likes.toLocaleString()}</div>
            </div>

            <div className="p-5 rounded-2xl border border-border bg-card shadow-sm space-y-2">
              <div className="flex items-center justify-between text-muted-foreground text-xs font-semibold">
                {t("analytics.reposts")}
                <Share2 className="size-4.5 text-indigo-500" />
              </div>
              <div className="text-2xl font-bold">{analytics.reposts.toLocaleString()}</div>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <h3 className="text-base font-semibold mb-4">{t("analytics.trendTitle")}</h3>
            <div className="w-full h-64 bg-muted/10 rounded-xl border border-border/50 p-4 flex flex-col justify-between">
              {analyticsSeries.every((d) => d.impressions === 0) ? (
                <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
                  {t("analytics.noData")}
                </div>
              ) : (
                <div className="flex-1 w-full relative">
                  <svg className="w-full h-full overflow-visible" viewBox="0 0 500 200" preserveAspectRatio="none">
                    <line x1="0" y1="50" x2="500" y2="50" stroke="rgba(156,163,175,0.08)" strokeWidth="1" />
                    <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(156,163,175,0.08)" strokeWidth="1" />
                    <line x1="0" y1="150" x2="500" y2="150" stroke="rgba(156,163,175,0.08)" strokeWidth="1" />
                    {(() => {
                      const max = Math.max(1, ...analyticsSeries.map((d) => d.impressions));
                      const n = Math.max(1, analyticsSeries.length - 1);
                      const points = analyticsSeries.map((d, i) => {
                        const x = (i / n) * 500;
                        const y = 190 - (d.impressions / max) * 170;
                        return [x, y] as const;
                      });
                      const line = points.map(([x, y]) => `${x},${y}`).join(" ");
                      const area = `0,200 ${line} 500,200`;
                      return (
                        <>
                          <polygon points={area} fill="url(#areaGrad)" />
                          <polyline
                            points={line}
                            fill="none"
                            stroke="url(#chartGrad)"
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          {points.map(([x, y], i) => (
                            <circle key={i} cx={x} cy={y} r="3" fill="#6366f1" />
                          ))}
                        </>
                      );
                    })()}
                    <defs>
                      <linearGradient id="chartGrad" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="100%" stopColor="#3b82f6" />
                      </linearGradient>
                      <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="rgba(99,102,241,0.15)" />
                        <stop offset="100%" stopColor="rgba(99,102,241,0.0)" />
                      </linearGradient>
                    </defs>
                  </svg>
                </div>
              )}
              <div className="flex justify-between text-[10px] text-muted-foreground pt-3 border-t border-border/40">
                {analyticsSeries.map((d) => (
                  <span key={d.date}>
                    {new Date(d.date).toLocaleDateString(undefined, { weekday: "short" })}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================== INTEGRATIONS (OAUTH CHANNELS) ==================== */}
      {activeTab === "integrations" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-2">
              <Globe className="size-5 text-indigo-500" />
              {t("integrationsTab.title")}
            </h2>
            <p className="text-xs text-muted-foreground mb-4">{t("integrationsTab.help")}</p>

            {connectError && (
              <p className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4">
                {connectError}
              </p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {channels.map((chan) => {
                const isReal = realSlugs.includes(chan.slug);
                const isConnected = connectedSlugs.includes(chan.slug);
                return (
                  <div key={chan.slug} className="p-4 rounded-xl border border-border bg-muted/40 hover:bg-muted/65 transition-all flex flex-col justify-between h-36">
                    <div className="flex justify-between items-start">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                        isConnected ? "bg-emerald-500/10 text-emerald-500" : "bg-zinc-500/10 text-muted-foreground"
                      }`}>
                        {isConnected ? t("integrationsTab.active") : isReal ? t("integrationsTab.offline") : t("integrationsTab.comingSoon")}
                      </span>
                      <span className="size-8 rounded-full bg-neutral-900 border border-border flex items-center justify-center relative shadow-sm overflow-hidden">
                        <ChannelIcon slug={chan.slug} className="size-4" />
                      </span>
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold">{chan.name}</h4>
                      <p className="text-[10px] text-muted-foreground">
                        {isConnected ? t("integrationsTab.connectedYes") : t("integrationsTab.connectedNo")}
                      </p>
                    </div>
                    <Button
                      onClick={() => handleConnectToggle(chan.slug)}
                      variant={isConnected ? "outline" : "default"}
                      size="sm"
                      disabled={!isConnected && !isReal}
                      className="w-full text-xs h-8 font-bold"
                    >
                      {isConnected ? t("integrationsTab.disconnect") : t("integrationsTab.authorize")}
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ==================== RSS AUTO-POST FEEDS ==================== */}
      {activeTab === "feeds" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
              <div className="min-w-0">
                <h2 className="text-lg font-semibold flex items-center gap-2 mb-1">
                  <Rss className="size-5 text-indigo-500" />
                  {t("feeds.title")}
                </h2>
                <p className="text-xs text-muted-foreground">{t("feeds.help")}</p>
              </div>
              <Button onClick={() => setShowFeedModal(true)} className="gap-2 shrink-0 bg-indigo-600 hover:bg-indigo-700 text-white font-bold">
                <Plus className="size-4" />
                {t("feeds.addFeed")}
              </Button>
            </div>

            {feeds.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-8">{t("feeds.empty")}</p>
            ) : (
              <div className="space-y-2.5">
                {feeds.map((feed) => (
                  <div
                    key={feed.id}
                    className="flex items-center justify-between p-3.5 rounded-xl border border-border bg-muted/20"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold truncate">{feed.title}</h4>
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                          feed.active ? "bg-emerald-500/10 text-emerald-500" : "bg-zinc-500/10 text-muted-foreground"
                        }`}>
                          {feed.active ? t("feeds.active") : t("feeds.paused")}
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground truncate">{feed.url}</p>
                      <div className="flex items-center gap-1 mt-1.5">
                        {feed.integrations.map((slug) => (
                          <span key={slug} className="size-5 rounded-full bg-neutral-900 border border-border flex items-center justify-center">
                            {LOGOS[slug] || <Globe className="size-2.5 text-white" />}
                          </span>
                        ))}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteFeed(feed.id, feed.title)}
                      className="text-red-500 shrink-0 hover:bg-red-50 dark:hover:bg-red-950/20"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================== MODAL: NEW RSS FEED ==================== */}
      <Dialog open={showFeedModal} onClose={() => setShowFeedModal(false)} title={t("feeds.newFeed")} size="md">
        <form onSubmit={handleCreateFeed}>
          <Field label={t("feeds.nameLabel")}>
            <input
              type="text"
              value={feedTitle}
              onChange={(e) => setFeedTitle(e.target.value)}
              placeholder={t("feeds.namePlaceholder")}
              className={inputCls}
            />
          </Field>
          <Field label={t("feeds.urlLabel")}>
            <input
              type="url"
              value={feedUrl}
              onChange={(e) => setFeedUrl(e.target.value)}
              placeholder={t("feeds.urlPlaceholder")}
              className={inputCls}
            />
          </Field>
          <Field label={t("feeds.channelsLabel")}>
            <div className="flex flex-wrap gap-2">
              {channels.filter((c) => connectedSlugs.includes(c.slug)).map((chan) => {
                const selected = feedIntegrations.includes(chan.slug);
                return (
                  <button
                    key={chan.slug}
                    type="button"
                    onClick={() =>
                      setFeedIntegrations((prev) =>
                        selected ? prev.filter((s) => s !== chan.slug) : [...prev, chan.slug],
                      )
                    }
                    className={`size-9 rounded-full border flex items-center justify-center relative cursor-pointer transition-all overflow-hidden ${
                      selected ? "ring-2 ring-indigo-500 border-indigo-500 bg-neutral-900" : "border-border bg-muted/40 hover:bg-muted"
                    }`}
                  >
                    <ChannelIcon slug={chan.slug} className="size-4" />
                  </button>
                );
              })}
            </div>
          </Field>
          <label className="flex items-center gap-2 cursor-pointer mb-2">
            <input
              type="checkbox"
              checked={feedGenerateContent}
              onChange={(e) => setFeedGenerateContent(e.target.checked)}
              className="rounded border-border focus:ring-indigo-500"
            />
            <span className="text-xs font-semibold text-muted-foreground">{t("feeds.generateLabel")}</span>
          </label>

          <DialogFooter>
            <Button type="submit" disabled={feedSaving} className="w-full text-xs">
              {feedSaving ? t("feeds.saving") : t("feeds.save")}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* ==================== WEBHOOKS ==================== */}
      {activeTab === "plugs" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <form
              onSubmit={handleSaveWebhook}
              className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-4"
            >
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Plug className="size-5 text-indigo-500" />
                {t("webhooks.title")}
              </h2>
              <p className="text-xs text-muted-foreground">{t("webhooks.help")}</p>

              <div>
                <label className="text-xs text-muted-foreground block mb-1 font-medium">{t("webhooks.urlLabel")}</label>
                <input
                  type="url"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  placeholder="https://my-service.com/webhooks/kin-social"
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={webhookActive}
                  onChange={(e) => setWebhookActive(e.target.checked)}
                  className="rounded border-border focus:ring-indigo-500"
                />
                <span className="text-xs font-semibold text-muted-foreground">{t("webhooks.activeLabel")}</span>
              </label>

              {webhookSecret && (
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-1.5">
                  <p className="text-[10px] font-bold text-amber-600 dark:text-amber-400">{t("webhooks.secretNotice")}</p>
                  <div className="flex gap-2">
                    <input
                      readOnly
                      value={webhookSecret}
                      className="flex-1 rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-xs font-mono select-all focus:outline-none"
                    />
                    <Button type="button" variant="outline" size="sm" onClick={() => triggerCopy(webhookSecret)}>
                      {copiedUrl === webhookSecret ? <CheckCheck className="size-4" /> : <Copy className="size-4" />}
                    </Button>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <Button type="submit" disabled={webhookSaving || !webhookUrl.trim()} className="flex-1 text-xs">
                  {webhookSaving ? t("webhooks.saving") : t("webhooks.save")}
                </Button>
                {existingWebhook && (
                  <Button type="button" variant="outline" onClick={handleDeleteWebhook} className="text-red-500 text-xs">
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            </form>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-3">
              <h3 className="text-base font-semibold">{t("webhooks.docsTitle")}</h3>
              <p className="text-xs text-muted-foreground">{t("webhooks.docsBody")}</p>
              <pre className="p-3 bg-neutral-900 text-white rounded-lg text-[9px] font-mono whitespace-pre-wrap leading-relaxed">
{`POST <your-url>
X-Kin-Signature: hmac_sha256(secret, body)

{
  "event": "post.published" | "post.failed",
  "post": {
    "id": "...",
    "integration_slug": "linkedin",
    "state": "published",
    "release_url": "https://...",
    "error": null
  }
}`}
              </pre>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
