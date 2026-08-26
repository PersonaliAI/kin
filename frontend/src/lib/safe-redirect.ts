// Validates a caller-supplied `?next=` (or similar) redirect target before
// it's ever handed to `window.location.href` or `NextResponse.redirect`.
//
// A plain `next.startsWith("/")` check is NOT enough: both `//evil.com` and
// `/\evil.com` are relative-looking strings that browsers resolve to an
// absolute, off-origin URL (protocol-relative and backslash-as-slash
// tricks, respectively). Rejecting those two prefixes in addition to
// requiring a leading "/" keeps the value a same-origin path.
//
// This is the single source of truth for that check — previously the same
// (partially incorrect) logic was duplicated across login/page.tsx,
// signup/page.tsx, onboarding/page.tsx, and auth/callback/route.ts.
export function safeNextPath(
  next: string | null | undefined,
  fallback: string = "/dashboard",
): string {
  if (
    typeof next === "string" &&
    next.startsWith("/") &&
    !next.startsWith("//") &&
    !next.startsWith("/\\")
  ) {
    return next;
  }
  return fallback;
}
