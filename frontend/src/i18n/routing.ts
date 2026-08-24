import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "it", "fr", "es"],
  defaultLocale: "en",
  // English stays at "/", other locales are prefixed "/it/...", "/fr/...",
  // "/es/..." — lets links be shared/bookmarked and keeps hreflang/SEO clean.
  localePrefix: "as-needed",
});

export type AppLocale = (typeof routing.locales)[number];
