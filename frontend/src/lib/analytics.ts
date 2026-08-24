import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  getAnalytics,
  isSupported,
  logEvent as firebaseLogEvent,
  setUserProperties,
  type Analytics,
} from "firebase/analytics";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

let app: FirebaseApp | null = null;
let analytics: Analytics | null = null;
let initPromise: Promise<Analytics | null> | null = null;

// Firebase Analytics only works in a real browser (uses IndexedDB) — never
// initialize during SSR, and skip gracefully in browsers that don't support
// it (e.g. some in-app webviews) rather than throwing.
async function getAnalyticsInstance(): Promise<Analytics | null> {
  if (typeof window === "undefined") return null;
  if (!firebaseConfig.apiKey || !firebaseConfig.measurementId) return null;
  if (analytics) return analytics;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    if (!(await isSupported())) return null;
    app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
    analytics = getAnalytics(app);
    return analytics;
  })();
  return initPromise;
}

export async function logEvent(name: string, params?: Record<string, unknown>) {
  const instance = await getAnalyticsInstance();
  if (!instance) return;
  firebaseLogEvent(instance, name, params);
}

export async function setAnalyticsUserProperties(props: Record<string, string>) {
  const instance = await getAnalyticsInstance();
  if (!instance) return;
  setUserProperties(instance, props);
}

// ---------------------------------------------------------------------------
// UTM first-touch attribution
//
// Kin has no attribution today — a signup can't be traced back to which
// channel produced it. Capture utm_* params (+ referrer as a fallback) the
// first time we see them for this browser, persist to localStorage so they
// survive the OAuth round-trip through /auth/callback, and attach them to
// the sign_up event once a new account actually completes onboarding.
// ---------------------------------------------------------------------------

const ATTRIBUTION_KEY = "kin_first_touch_attribution";
const UTM_PARAMS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"] as const;

export type Attribution = Partial<Record<(typeof UTM_PARAMS)[number], string>> & {
  referrer?: string;
  landing_page?: string;
  captured_at?: string;
};

export function captureFirstTouchAttribution(url: URL) {
  if (typeof window === "undefined") return;
  if (localStorage.getItem(ATTRIBUTION_KEY)) return; // first touch only

  const found: Attribution = {};
  let hasUtm = false;
  for (const key of UTM_PARAMS) {
    const v = url.searchParams.get(key);
    if (v) {
      found[key] = v;
      hasUtm = true;
    }
  }
  if (!hasUtm && !document.referrer) return; // nothing worth storing yet

  found.referrer = document.referrer || undefined;
  found.landing_page = url.pathname;
  found.captured_at = new Date().toISOString();
  localStorage.setItem(ATTRIBUTION_KEY, JSON.stringify(found));
}

export function getFirstTouchAttribution(): Attribution | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(ATTRIBUTION_KEY);
    return raw ? (JSON.parse(raw) as Attribution) : null;
  } catch {
    return null;
  }
}

const SIGNUP_EVENT_KEY = "kin_signup_event_sent";

// Guarded so a single new account only ever fires sign_up once, even if
// /onboarding is revisited (back button, refresh, etc.).
export async function logSignUpOnce(method: "password" | "google" | "microsoft") {
  if (typeof window === "undefined") return;
  if (sessionStorage.getItem(SIGNUP_EVENT_KEY)) return;
  sessionStorage.setItem(SIGNUP_EVENT_KEY, "1");
  const attribution = getFirstTouchAttribution();
  await logEvent("sign_up", { method, ...attribution });
}
