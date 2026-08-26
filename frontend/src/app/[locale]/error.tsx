"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Route-segment error boundary — catches unexpected render/runtime errors
// anywhere under [locale] (landing, auth, dashboard, ...) and shows a
// branded fallback instead of Next's default error screen. Must be a
// Client Component. Kept deliberately simple (no i18n) since this is a
// last-resort fallback, not a page users are expected to see routinely.
export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled route error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background relative overflow-hidden">
      <div
        className="absolute inset-0 z-0 pointer-events-none opacity-50"
        style={{
          backgroundImage: "radial-gradient(circle, #d4d4d4 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      />

      <div className="w-full max-w-sm z-10 text-center">
        <div className="size-16 rounded-full bg-red-50 border border-red-100 flex items-center justify-center mx-auto mb-6 text-red-600">
          <AlertTriangle className="size-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight mb-2">Something went wrong</h1>
        <p className="text-sm text-muted-foreground mb-8">
          An unexpected error occurred. You can try again, or head back home.
        </p>
        <div className="space-y-3 flex flex-col">
          <button
            type="button"
            onClick={() => reset()}
            className={cn(buttonVariants({ variant: "default" }), "w-full h-10 font-medium cursor-pointer")}
          >
            Try again
          </button>
          <Link href="/" className={cn(buttonVariants({ variant: "outline" }), "w-full h-10 font-medium")}>
            Back home
          </Link>
        </div>
      </div>
    </div>
  );
}
