import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import "../globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AnalyticsProvider } from "@/components/analytics-provider";
import { MetaPixel } from "@/components/meta-pixel";
import { routing } from "@/i18n/routing";

const OG_LOCALE: Record<string, string> = {
  en: "en_US",
  it: "it_IT",
  fr: "fr_FR",
  es: "es_ES",
};

// Runs before hydration so the correct theme class is present on first
// paint — otherwise the page flashes light before JS applies the stored
// preference (FOUC).
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("kin-theme") || "light";
    var dark = stored === "dark" || (stored === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
  } catch (e) {}
})();
`;

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

// App-only segments (dashboard, login, etc.) opt out of indexing via their
// own layouts — the public landing page at "/" must stay indexable, so no
// sitewide robots block here.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "metadata" });

  return {
    metadataBase: new URL("https://kin.personaliai.com"),
    title: {
      default: t("title"),
      template: `%s | Kin`,
    },
    description: t("description"),
    // No explicit `icons` override here — Next.js auto-generates favicon/
    // apple-touch-icon <link> tags from src/app/icon.tsx and apple-icon.tsx
    // (the Kin brand mark). A previous fix accidentally pointed these at
    // stale public/favicon.ico|png files left over from splitting this app
    // out of personali-frontend, which used an unrelated robot mascot.
    openGraph: {
      type: "website",
      url: "https://kin.personaliai.com/",
      siteName: "Kin",
      title: t("title"),
      description: t("ogDescription"),
      locale: OG_LOCALE[locale] ?? "en_US",
    },
    twitter: {
      card: "summary_large_image",
      title: t("title"),
      description: t("ogDescription"),
    },
    alternates: {
      languages: Object.fromEntries(
        routing.locales.map((l) => [
          l,
          l === routing.defaultLocale
            ? "https://kin.personaliai.com/"
            : `https://kin.personaliai.com/${l}`,
        ]),
      ),
    },
  };
}

export default async function RootLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  // Enables static rendering for this locale's subtree.
  setRequestLocale(locale);

  return (
    <html lang={locale} className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <NextIntlClientProvider>
          <ThemeProvider>
            <AnalyticsProvider />
            <MetaPixel />
            {children}
          </ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
