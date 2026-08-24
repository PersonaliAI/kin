import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { AlertCircle } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default async function AuthErrorPage() {
  const t = await getTranslations("auth.authCodeError");
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background relative overflow-hidden">
      {/* Background dot grid pattern */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-50"
           style={{
             backgroundImage: 'radial-gradient(circle, #d4d4d4 1px, transparent 1px)',
             backgroundSize: '24px 24px'
           }}>
      </div>

      <div className="w-full max-w-sm z-10 text-center">
        <div className="size-16 rounded-full bg-red-50 border border-red-100 flex items-center justify-center mx-auto mb-6 text-red-600">
          <AlertCircle className="size-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight mb-2">{t("title")}</h1>
        <p className="text-sm text-muted-foreground mb-8">
          {t("message")}
        </p>
        <div className="space-y-4 flex flex-col">
          <Link href="/login" className={cn(buttonVariants({ variant: "default" }), "w-full h-10 font-medium")}>
            {t("tryAgain")}
          </Link>
          <Link href="/" className={cn(buttonVariants({ variant: "outline" }), "w-full h-10 font-medium")}>
            {t("backHome")}
          </Link>
        </div>
      </div>
    </div>
  );
}
