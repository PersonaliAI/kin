/**
 * Returns the full list of IANA timezones the browser knows about.
 * Falls back to a curated subset for older browsers.
 */
export function listTimezones(): string[] {
  try {
    const fn = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] })
      .supportedValuesOf;
    if (typeof fn === "function") {
      const arr = fn("timeZone");
      if (Array.isArray(arr) && arr.length > 0) return arr;
    }
  } catch {
    // fall through
  }
  return FALLBACK_TIMEZONES;
}

export function detectTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function formatTimezone(tz: string): string {
  // "Asia/Colombo" → "Asia / Colombo"
  return tz.replace(/_/g, " ");
}

export function offsetLabel(tz: string): string {
  try {
    const dtf = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      timeZoneName: "shortOffset",
    });
    const parts = dtf.formatToParts(new Date());
    const tzName = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
    return tzName || "";
  } catch {
    return "";
  }
}

const FALLBACK_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Toronto",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Madrid",
  "Europe/Rome",
  "Europe/Athens",
  "Europe/Moscow",
  "Africa/Cairo",
  "Africa/Johannesburg",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Colombo",
  "Asia/Karachi",
  "Asia/Dhaka",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Hong_Kong",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Australia/Sydney",
  "Pacific/Auckland",
];
