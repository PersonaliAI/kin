import { Link } from "@/i18n/navigation";
import { SearchX } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Handles notFound() calls and unmatched paths inside the [locale] segment
// (i.e. almost every 404 a real visitor will hit, since next-intl's
// middleware routes unmatched top-level paths in here). Rendered inside the
// real root layout (app/[locale]/layout.tsx supplies <html>/<body>), so no
// document scaffolding needed here — see app/not-found.tsx for the
// self-contained fallback used for the rare request that never reaches
// locale routing at all.
export default function LocaleNotFound() {
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
        <div className="size-16 rounded-full bg-muted border border-border flex items-center justify-center mx-auto mb-6 text-muted-foreground">
          <SearchX className="size-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight mb-2">Page not found</h1>
        <p className="text-sm text-muted-foreground mb-8">
          The page you&apos;re looking for doesn&apos;t exist or may have moved.
        </p>
        <Link href="/" className={cn(buttonVariants({ variant: "default" }), "w-full h-10 font-medium")}>
          Back home
        </Link>
      </div>
    </div>
  );
}
