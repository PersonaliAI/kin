"use client";

import Script from "next/script";
import { Suspense, useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

const PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID;

// Routes deliberately kept out of the pixel: everything behind auth. Two
// reasons — we don't ship signed-in product usage to Meta, and it keeps the
// retargeting pool limited to people who haven't converted yet, so boosted
// spend isn't wasted chasing users who already signed up.
const EXCLUDED_PREFIXES = ["/dashboard", "/onboarding", "/auth", "/checkout", "/success"];

declare global {
  interface Window {
    fbq?: ((...args: unknown[]) => void) & { callMethod?: (...args: unknown[]) => void };
  }
}

function isExcluded(pathname: string) {
  return EXCLUDED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function MetaPixelInner({ pixelId }: { pixelId: string }) {
  const pathname = usePathname();
  const excluded = isExcluded(pathname);
  // The inline script fires the first PageView itself, so skip the effect once
  // to avoid double-counting the landing hit.
  const primed = useRef(false);

  useEffect(() => {
    if (excluded) return;
    if (!primed.current) {
      primed.current = true;
      return;
    }
    window.fbq?.("track", "PageView");
  }, [pathname, excluded]);

  if (excluded) return null;

  return (
    <Script id="meta-pixel" strategy="afterInteractive">
      {`
!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '${pixelId}');
fbq('track', 'PageView');
      `}
    </Script>
  );
}

/**
 * Meta (Facebook/Instagram) pixel — inert until NEXT_PUBLIC_META_PIXEL_ID is
 * set, so this is safe to ship before the ad account exists. Needed before any
 * Reels boosting: the pixel can't backfill, so installing it early is what
 * builds the retargeting pool for later campaigns.
 */
export function MetaPixel() {
  if (!PIXEL_ID) return null;
  return (
    <Suspense fallback={null}>
      <MetaPixelInner pixelId={PIXEL_ID} />
    </Suspense>
  );
}
