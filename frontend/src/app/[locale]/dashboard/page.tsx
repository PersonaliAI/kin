import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { ArrowUpRight, MessageSquare, Mic, Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LocalTime } from "@/components/local-time";
import { Markdown } from "@/components/markdown";
import { UsageMeter } from "@/components/dashboard/usage-meter";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function DashboardOverviewPage() {
  const t = await getTranslations("dashboard.overview");
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();

  const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

  const [
    { count: turns24h },
    { count: turns7d },
    { count: openTasks },
    { count: contactsTotal },
    { data: recent },
  ] = await Promise.all([
    supabase
      .from("messages")
      .select("*", { count: "exact", head: true })
      .eq("user_id", kin.id)
      .gte("created_at", dayAgo),
    supabase
      .from("messages")
      .select("*", { count: "exact", head: true })
      .eq("user_id", kin.id)
      .gte("created_at", weekAgo),
    supabase
      .from("tasks")
      .select("*", { count: "exact", head: true })
      .eq("user_id", kin.id)
      .neq("status", "done"),
    supabase
      .from("contacts")
      .select("*", { count: "exact", head: true })
      .eq("user_id", kin.id),
    supabase
      .from("messages")
      .select("id, role, content, source, created_at, latency_ms")
      .eq("user_id", kin.id)
      .order("created_at", { ascending: false })
      .limit(6),
  ]);

  const isEmpty = (turns7d ?? 0) === 0;

  const stats = [
    { label: t("stats.conversations24h"), value: turns24h ?? 0, hint: t("stats.conversations24hHint") },
    { label: t("stats.conversations7d"), value: turns7d ?? 0, hint: t("stats.conversations7dHint") },
    { label: t("stats.openTasks"), value: openTasks ?? 0, hint: t("stats.openTasksHint") },
    { label: t("stats.contacts"), value: contactsTotal ?? 0, hint: t("stats.contactsHint") },
  ];

  return (
    <main className="flex-1 overflow-y-auto overflow-x-hidden">
      <div className="p-5 md:p-8 max-w-6xl w-full mx-auto space-y-8">
        <section className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-baseline justify-between mb-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                {t("monthlyUsage")}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t("planAndCount")}
              </p>
            </div>
            <Link
              href="/dashboard/billing"
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              {t("managePlan")} <ArrowUpRight className="size-3" />
            </Link>
          </div>
          <UsageMeter compact />
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <QuickAction
            href="/dashboard/chat"
            icon={MessageSquare}
            title={t("startChat")}
            sub={t("startChatSub")}
          />
          <QuickAction
            href="/dashboard/chat?voice=1"
            icon={Mic}
            title={t("speakToKin")}
            sub={t("speakToKinSub")}
          />

        </section>

        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {stats.map((s) => (
            <div key={s.label} className="rounded-xl bg-card border border-border p-4">
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                {s.label}
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight">{s.value}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">{s.hint}</div>
            </div>
          ))}
        </section>

        <section>
          <div className="flex items-end justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold">{t("recentActivity")}</h2>
              <p className="text-xs text-muted-foreground">
                {t("recentActivitySub")}
              </p>
            </div>
            <Link
              href="/dashboard/activity"
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              {t("viewAll")} <ArrowUpRight className="size-3" />
            </Link>
          </div>

          <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
            {isEmpty ? (
              <EmptyState />
            ) : (
              (recent ?? []).map((m) => (
                <div
                  key={m.id}
                  className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors"
                >
                  <div
                    className={`mt-0.5 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${
                      m.role === "user"
                        ? "bg-muted text-muted-foreground"
                        : "bg-orange-50 text-orange-600"
                    }`}
                  >
                    {m.role}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-foreground line-clamp-3">
                      {m.content ? (
                        m.role === "assistant" ? (
                          <Markdown>{m.content}</Markdown>
                        ) : (
                          <span className="whitespace-pre-wrap break-words">
                            {m.content}
                          </span>
                        )
                      ) : (
                        <span className="text-muted-foreground italic">{t("voiceMessage")}</span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground flex items-center gap-2">
                      <span className="capitalize">{m.source}</span>
                      <span>·</span>
                      <LocalTime iso={m.created_at} mode="relative" />
                      {m.latency_ms != null && (
                        <>
                          <span>·</span>
                          <span>{Math.round(m.latency_ms)}ms</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function QuickAction({
  href,
  icon: Icon,
  title,
  sub,
}: {
  href: string;
  icon: typeof MessageSquare;
  title: string;
  sub: string;
}) {
  return (
    <Link
      href={href}
      prefetch
      className="group rounded-xl bg-card border border-border p-4 hover:border-foreground/20 transition-all hover:-translate-y-0.5"
    >
      <div className="size-8 rounded-lg bg-muted text-muted-foreground grid place-items-center group-hover:bg-foreground group-hover:text-background transition-colors">
        <Icon className="size-4" />
      </div>
      <div className="mt-3 text-sm font-semibold">{title}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>
    </Link>
  );
}

async function EmptyState() {
  const t = await getTranslations("dashboard.overview");
  return (
    <div className="p-10 text-center">
      <div className="size-10 mx-auto rounded-xl bg-muted grid place-items-center text-muted-foreground">
        <Sparkles className="size-5" />
      </div>
      <h3 className="mt-4 text-sm font-semibold">{t("emptyTitle")}</h3>
      <p className="mt-1 text-xs text-muted-foreground max-w-xs mx-auto">
        {t("emptySub")}
      </p>
      <Button className="mt-4 h-9 px-4 cursor-pointer" render={<Link href="/dashboard/chat" />}>
        {t("openChat")}
      </Button>
    </div>
  );
}
