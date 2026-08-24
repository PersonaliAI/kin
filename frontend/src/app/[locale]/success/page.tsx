"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { CheckCircle2, MessageSquare, ArrowRight, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";

export default function SuccessPage() {
  const t = useTranslations("auth.success");
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Background dot grid pattern */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-50" 
           style={{ 
             backgroundImage: 'radial-gradient(circle, #d4d4d4 1px, transparent 1px)', 
             backgroundSize: '24px 24px' 
           }}>
      </div>

      <div className="w-full max-w-sm z-10 text-center space-y-8">
        <motion.div 
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="size-20 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center mx-auto text-emerald-600 shadow-sm"
        >
          <CheckCircle2 className="size-10" />
        </motion.div>

        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight italic">{t("title")}</h1>
          <p className="text-muted-foreground text-sm leading-relaxed">
            {t("message")}
          </p>
        </div>

        <div className="pt-4 space-y-4">
          <Link
            href="/dashboard"
            className="w-full h-12 bg-foreground text-background rounded-lg font-bold flex items-center justify-center gap-3 hover:bg-foreground/90 transition-all shadow-lg"
          >
            <ArrowRight className="size-5" />
            {t("openDashboard")}
          </Link>

          <a
            href="https://t.me/KinByPersonaliAI_bot"
            target="_blank"
            rel="noreferrer"
            className="w-full h-11 border border-border rounded-lg font-semibold flex items-center justify-center gap-3 hover:bg-muted transition-all text-sm"
          >
            <MessageSquare className="size-4" />
            {t("openTelegram")}
            <ExternalLink className="size-3" />
          </a>
        </div>

        <div className="pt-12 border-t border-border/50">
          <div className="flex items-center justify-center gap-2 text-[9px] font-bold uppercase tracking-widest text-emerald-600">
            <div className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            {t("statusBadge")}
          </div>
        </div>
      </div>
    </div>
  );
}
