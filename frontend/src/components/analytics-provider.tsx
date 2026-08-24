"use client";

import { Suspense, useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { captureFirstTouchAttribution, logEvent } from "@/lib/analytics";

function AnalyticsInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    const url = new URL(window.location.href);
    captureFirstTouchAttribution(url);
    logEvent("page_view", {
      page_path: pathname,
      page_location: window.location.href,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, searchParams]);

  return null;
}

export function AnalyticsProvider() {
  return (
    <Suspense fallback={null}>
      <AnalyticsInner />
    </Suspense>
  );
}
