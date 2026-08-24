"use client";

import { useEffect, useState } from "react";

type Mode = "relative" | "time" | "datetime" | "day";

/**
 * Renders a timestamp in the *user's* locale + timezone.
 *
 * Server Components run in Cloud Run's container (UTC), so any
 * `toLocaleString` call up there formats in the wrong timezone. This
 * component punts the formatting to the browser after hydration. The
 * initial server-rendered value is the safe UTC fallback so we don't get
 * a hydration mismatch warning.
 */
export function LocalTime({
  iso,
  mode = "datetime",
}: {
  iso: string;
  mode?: Mode;
}) {
  const [text, setText] = useState(() => fallback(iso, mode));

  useEffect(() => {
    setText(format(new Date(iso), mode));
    if (mode === "relative") {
      // Refresh "5 minutes ago" labels every 30s so the feed stays accurate.
      const t = setInterval(() => setText(format(new Date(iso), mode)), 30_000);
      return () => clearInterval(t);
    }
  }, [iso, mode]);

  return (
    <time dateTime={iso} suppressHydrationWarning>
      {text}
    </time>
  );
}

function fallback(iso: string, mode: Mode): string {
  // Server-side: ISO. Replaced on hydration. suppressHydrationWarning
  // prevents the warning until the client overwrites this.
  if (mode === "day") return iso.slice(0, 10);
  if (mode === "time") return iso.slice(11, 16);
  return iso.replace("T", " ").slice(0, 16);
}

function format(d: Date, mode: Mode): string {
  if (mode === "day") {
    return d.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  }
  if (mode === "time") {
    return d.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  }
  if (mode === "datetime") {
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }
  // relative
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 5) return "just now";
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Returns the local-day key for grouping. SSR uses UTC; client re-groups on
 * hydration via useEffect inside the consumer.
 */
export function localDayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}
