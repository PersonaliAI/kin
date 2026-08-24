"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Plug } from "lucide-react";

export function NotConnected({ what }: { what: string }) {
  const t = useTranslations("dashboard.notConnected");
  return (
    <div className="rounded-xl border border-border bg-card p-12 text-center">
      <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
        <Plug className="size-5" />
      </div>
      <h3 className="mt-4 text-sm font-semibold">{t("title", { what })}</h3>
      <p className="mt-1 text-xs text-muted-foreground max-w-xs mx-auto">
        {t("body")}
      </p>
      <Button className="mt-4 h-9 px-4 cursor-pointer" render={<Link href="/dashboard/integrations" />}>
        {t("cta")}
      </Button>
    </div>
  );
}
