"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { KinMark } from "@/components/kin-mark";
import { LanguageSwitcher } from "@/components/language-switcher";
import {
  Mail,
  Calendar,
  ListTodo,
  Users,
  Mic,
  Brain,
  ArrowRight,
  Check,
  CheckCheck,
  Send,
  Sparkles,
  ChevronDown,
  MessageCircle,
  MoreVertical,
  Paperclip,
  Phone,
  Smile,
} from "lucide-react";
import { kinUrl } from "@/lib/kin-url";

const ORANGE = "#f97316";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56 0-.27-.01-1.17-.02-2.12-3.2.7-3.87-1.36-3.87-1.36-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.05 11.05 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.76.12 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.07.78 2.15 0 1.55-.01 2.8-.01 3.18 0 .31.21.67.8.56A10.51 10.51 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"/>
    </svg>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   Hero conversation mockup — a looping, typed-out demo of Kin actually
   doing something, not a static screenshot. This is the signature visual.
   ──────────────────────────────────────────────────────────────────────── */

type DemoStep =
  | { role: "user"; text: string }
  | { role: "kin"; text: string; card?: { icon: React.ElementType; title: string; sub: string } };

function useDemoScripts(): DemoStep[][] {
  const t = useTranslations("landing.demo");
  return [
    [
      { role: "user", text: t("calendar.user") },
      {
        role: "kin",
        text: t("calendar.reply1"),
        card: { icon: Calendar, title: t("calendar.cardTitle"), sub: t("calendar.cardSub") },
      },
      { role: "kin", text: t("calendar.reply2") },
    ],
    [
      { role: "user", text: t("email.user") },
      {
        role: "kin",
        text: t("email.reply1"),
        card: { icon: Mail, title: t("email.cardTitle"), sub: t("email.cardSub") },
      },
      { role: "kin", text: t("email.reply2") },
    ],
    [
      { role: "user", text: t("task.user") },
      {
        role: "kin",
        text: t("task.reply1"),
        card: { icon: ListTodo, title: t("task.cardTitle"), sub: t("task.cardSub") },
      },
      { role: "kin", text: t("task.reply2") },
    ],
  ];
}

// Advances a few characters per tick at a slower interval rather than one
// character every ~16ms — the original per-character/60fps cadence meant
// 40+ React re-renders per message, each forcing the bubble (a shrink-to-fit
// flex item) to re-measure its width. Combined with AnimatePresence doing
// its own layout measurement for sibling messages at the same time, that
// was frequent enough to occasionally leave the bubble mid-reflow with a
// stale, unwrapped width on slower devices.
function useTypewriter(text: string, active: boolean, speed = 45, charsPerTick = 3) {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (!active) { setOut(""); return; }
    let i = 0;
    setOut("");
    const id = setInterval(() => {
      i += charsPerTick;
      setOut(text.slice(0, i));
      if (i >= text.length) clearInterval(id);
    }, speed);
    return () => clearInterval(id);
  }, [text, active, speed, charsPerTick]);
  return out;
}

function ConversationCard() {
  const demoScripts = useDemoScripts();
  const [scriptIdx, setScriptIdx] = useState(0);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const script = demoScripts[scriptIdx];

  useEffect(() => {
    setVisibleSteps(0);
    const timers: ReturnType<typeof setTimeout>[] = [];
    script.forEach((_, i) => {
      timers.push(setTimeout(() => setVisibleSteps((v) => Math.max(v, i + 1)), i * 1400 + 300));
    });
    const cycle = setTimeout(() => {
      setScriptIdx((s) => (s + 1) % demoScripts.length);
    }, script.length * 1400 + 3200);
    return () => { timers.forEach(clearTimeout); clearTimeout(cycle); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scriptIdx]);

  const lastUserText = useTypewriter(
    script.find((s) => s.role === "user")?.text ?? "",
    visibleSteps >= 1
  );

  return (
    <div className="relative w-full max-w-md mx-auto lg:mx-0">
      {/* glow */}
      <div
        className="absolute -inset-8 rounded-[3rem] blur-3xl opacity-30 -z-10"
        style={{ background: `radial-gradient(circle at 30% 20%, ${ORANGE}, transparent 60%)` }}
      />
      {/* Telegram dark-theme chat window */}
      <div className="rounded-3xl border border-white/10 shadow-2xl overflow-hidden" style={{ background: "#0e1621" }}>
        {/* chat header — avatar / name / online, like Telegram's top bar */}
        <div className="flex items-center gap-3 px-4 py-2.5" style={{ background: "#17212b" }}>
          <div
            className="size-9 rounded-full grid place-items-center shrink-0"
            style={{ background: `linear-gradient(135deg, ${ORANGE}, #fb923c)` }}
          >
            <span className="text-white text-[15px] font-bold leading-none">K</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[13.5px] font-semibold text-white leading-tight">Kin</p>
            <p className="text-[11.5px] leading-tight" style={{ color: "#6ab3f3" }}>online</p>
          </div>
          <Phone className="size-4 text-white/35" />
          <MoreVertical className="size-4 text-white/35" />
        </div>

        {/* messages — fixed height, newest anchored to the bottom like a real
            chat, so the loop never resizes the card or clips a bubble.
            Keyed by scriptIdx so React hard-swaps the whole list when the
            script changes, instead of asking AnimatePresence to cross-fade
            between two unrelated arrays — that reliably left old bubbles
            stuck mid-exit under real timing (9 piled up instead of 3),
            which is what was intermittently blowing out the card's width. */}
        <div key={scriptIdx} className="px-3 py-3 h-[300px] flex flex-col justify-end gap-1.5 overflow-hidden">
          <AnimatePresence mode="popLayout">
            {script.slice(0, visibleSteps).map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className={`min-w-0 flex ${step.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`min-w-0 max-w-[85%] px-3 py-1.5 text-[13px] leading-snug text-white ${
                    step.role === "user" ? "rounded-2xl rounded-br-md" : "rounded-2xl rounded-bl-md"
                  }`}
                  style={{ background: step.role === "user" ? "#2b5278" : "#182533" }}
                >
                  {/* min-w-0: this is a flex item (parent row is `flex
                      justify-start/end`). Flex items default to
                      min-width:auto, which lets a descendant's unbreakable
                      min-content width (the card sub-line below uses
                      `truncate`, i.e. white-space:nowrap, so its minimum
                      width IS its full un-wrapped width) override
                      max-w-[85%] and force this bubble wider than intended.
                      Longer sub-text (e.g. the Marcus/invoice card) pushed
                      the bubble — and the whole chat card — past its right
                      margin because of exactly this. min-w-0 lets max-width
                      actually win, so truncate can do its job instead. */}
                  {i === 0 && step.role === "user" ? (
                    // Grid-stacks an invisible copy of the FULL final text
                    // under the visible partial (typing) text, in the same
                    // cell. The grid track sizes to the larger (full-text)
                    // item immediately, so the bubble reserves its final
                    // width up front instead of re-measuring shrink-to-fit
                    // on every character as the text grows.
                    <p className="grid">
                      <span className="invisible [grid-area:1/1]" aria-hidden="true">{step.text}</span>
                      <span className="[grid-area:1/1]">{lastUserText}</span>
                    </p>
                  ) : (
                    <p>{step.text}</p>
                  )}
                  {"card" in step && step.card && (
                    <div className="mt-2 mb-0.5 flex items-center gap-2.5 rounded-xl bg-white/5 border border-white/10 px-3 py-2.5">
                      <div className="size-8 rounded-lg grid place-items-center shrink-0" style={{ background: `${ORANGE}22` }}>
                        <step.card.icon className="size-4" style={{ color: ORANGE }} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[12px] font-medium text-white truncate">{step.card.title}</p>
                        <p className="text-[11px] text-white/50 truncate">{step.card.sub}</p>
                      </div>
                    </div>
                  )}
                  <span
                    className="float-right ml-2 mt-1.5 flex items-center gap-0.5 text-[10px] leading-none"
                    style={{ color: step.role === "user" ? "#7da8d3" : "rgba(255,255,255,0.35)" }}
                  >
                    2:1{4 + Math.floor(i / 2)} PM
                    {step.role === "user" && <CheckCheck className="size-3" style={{ color: "#6ab3f3" }} />}
                  </span>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* input bar — Telegram-style message field */}
        <div className="px-3 py-2.5 flex items-center gap-2.5" style={{ background: "#17212b" }}>
          <Smile className="size-5 text-white/30 shrink-0" />
          <div className="flex-1 text-[13px] text-white/30">Message</div>
          <Paperclip className="size-5 text-white/30 shrink-0" />
          <div className="size-9 rounded-full grid place-items-center shrink-0" style={{ background: "#5288c1" }}>
            <Send className="size-4 text-white" />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   Nav
   ──────────────────────────────────────────────────────────────────────── */

function Nav() {
  const t = useTranslations("landing.nav");
  return (
    <header className="fixed top-0 inset-x-0 z-50 bg-neutral-950/80 backdrop-blur-xl border-b border-white/5">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <KinMark size={28} />
          <span className="font-semibold text-white text-sm tracking-tight">Kin</span>
        </Link>
        <nav className="hidden md:flex items-center gap-7 text-[13px] text-white/60">
          <a href="#capabilities" className="hover:text-white transition-colors">{t("capabilities")}</a>
          <a href="#pricing" className="hover:text-white transition-colors">{t("pricing")}</a>
          <a href="#faq" className="hover:text-white transition-colors">{t("faq")}</a>
          <a href="https://personaliai.com" className="hover:text-white transition-colors">{t("personaliai")}</a>
        </nav>
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/PersonaliAI/kin"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Kin on GitHub"
            className="hidden sm:inline-flex items-center justify-center size-8 rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors"
          >
            <GithubIcon className="size-4" />
          </a>
          <LanguageSwitcher variant="dark" />
          <Link href={kinUrl("/login")} className="hidden sm:inline text-[13px] text-white/60 hover:text-white transition-colors">
            {t("login")}
          </Link>
          <Link
            href={kinUrl("/signup")}
            className="inline-flex items-center gap-1.5 rounded-full bg-white text-neutral-900 text-[13px] font-semibold px-4 py-2 hover:bg-white/90 transition-colors"
          >
            {t("startFree")}
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   Hero
   ──────────────────────────────────────────────────────────────────────── */

function Hero() {
  const t = useTranslations("landing.hero");
  return (
    <section className="relative overflow-hidden pt-28 pb-20 md:pt-48 md:pb-32">
      <div
        className="absolute inset-0 -z-10 opacity-40"
        style={{
          backgroundImage:
            "radial-gradient(1px 1px at 20px 20px, rgba(255,255,255,0.15) 1px, transparent 0)",
          backgroundSize: "34px 34px",
        }}
      />
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] -z-10 opacity-20 blur-3xl"
        style={{ background: `radial-gradient(ellipse at center, ${ORANGE}, transparent 65%)` }}
      />

      <div className="max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[12px] text-white/60 mb-6"
          >
            <Sparkles className="size-3.5" style={{ color: ORANGE }} />
            {t("badge")}
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="text-4xl sm:text-5xl lg:text-[3.4rem] font-semibold tracking-tight leading-[1.08] text-white"
          >
            {t("titleLine1")}
            <br />
            <span className="relative inline-block">
              <span style={{ color: ORANGE }}>{t("titleHighlight")}</span>
            </span>
            .
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mt-6 text-[15px] sm:text-base text-white/55 leading-relaxed max-w-md"
          >
            {t("description")}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="mt-8 sm:mt-9 flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3"
          >
            {/* Explicit w-full/sm:w-auto instead of items-stretch: stretch
                depends on the flex container resolving cross-axis sizing
                every render, which measurably did not happen consistently
                here (button width was observed flip-flopping between the
                correct 342px and an overflowing 379px on the same loaded
                page). An explicit width is a fixed value, not a recalculated
                one, so it can't intermittently drift. */}
            <Link
              href={kinUrl("/signup")}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-full text-white text-sm font-semibold px-6 py-3.5 transition-transform hover:scale-[1.02]"
              style={{ background: ORANGE }}
            >
              {t("ctaPrimary")}
              <ArrowRight className="size-4" />
            </Link>
            <a
              href="#capabilities"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-full border border-white/15 text-white/80 text-sm font-medium px-6 py-3.5 hover:bg-white/5 transition-colors"
            >
              {t("ctaSecondary")}
            </a>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
            className="mt-5 text-[12px] text-white/35"
          >
            {t("tagline")}
          </motion.p>
        </div>

        <motion.div
          className="min-w-0"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15, duration: 0.5 }}
        >
          {/* min-w-0: this is a grid item (the hero is a single-column grid
              on mobile). Grid items default to min-width:auto, same trap as
              flex items — deep inside, a truncated (white-space:nowrap)
              card subtitle's unbreakable min-content width was winning over
              max-w-[85%] all the way up through the grid track itself, so
              every row in the card (header, messages, input bar) rendered
              ~36px wider in lockstep, right when the Marcus/invoice script
              (longest subtitle) was on screen. Fixing the bubble/row levels
              alone didn't help because the grid track — one level above all
              of that — was still the thing actually expanding. */}
          <ConversationCard />
        </motion.div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   Capabilities
   ──────────────────────────────────────────────────────────────────────── */

const CAPABILITY_ICONS = {
  email: Mail,
  calendar: Calendar,
  tasks: ListTodo,
  contacts: Users,
  voice: Mic,
  memory: Brain,
} as const;

function Capabilities() {
  const t = useTranslations("landing.capabilities");
  const ids = Object.keys(CAPABILITY_ICONS) as (keyof typeof CAPABILITY_ICONS)[];
  return (
    <section id="capabilities" className="py-24 md:py-32 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-6">
        <div className="max-w-xl mb-16">
          <p className="text-[13px] font-medium mb-3" style={{ color: ORANGE }}>{t("eyebrow")}</p>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white">
            {t("heading")}
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-white/5 rounded-2xl overflow-hidden border border-white/5">
          {ids.map((id, i) => {
            const Icon = CAPABILITY_ICONS[id];
            return (
              <motion.div
                key={id}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                className="bg-neutral-950 p-7 hover:bg-white/[0.02] transition-colors"
              >
                <div className="size-10 rounded-xl grid place-items-center mb-5" style={{ background: `${ORANGE}18` }}>
                  <Icon className="size-5" style={{ color: ORANGE }} />
                </div>
                <h3 className="text-[15px] font-semibold text-white mb-2">{t(`items.${id}.title`)}</h3>
                <p className="text-[13.5px] text-white/50 leading-relaxed">{t(`items.${id}.desc`)}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   How it works — timeline
   ──────────────────────────────────────────────────────────────────────── */

const HOW_IT_WORKS_IDS = ["send", "figures", "parallel", "answer"] as const;

function HowItWorks() {
  const t = useTranslations("landing.howItWorks");
  return (
    <section className="py-24 md:py-32 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-6">
        <p className="text-[13px] font-medium mb-3" style={{ color: ORANGE }}>{t("eyebrow")}</p>
        <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white mb-16">
          {t("heading")}
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {HOW_IT_WORKS_IDS.map((id, i) => (
            <motion.div
              key={id}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.3, delay: i * 0.08 }}
              className="relative"
            >
              <span className="text-4xl font-bold text-white/10 tabular-nums">{String(i + 1).padStart(2, "0")}</span>
              <h3 className="text-[15px] font-semibold text-white mt-3 mb-2">{t(`steps.${id}.title`)}</h3>
              <p className="text-[13.5px] text-white/50 leading-relaxed">{t(`steps.${id}.desc`)}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   Pricing
   ──────────────────────────────────────────────────────────────────────── */

const PLAN_IDS = [
  { id: "free", highlighted: false, free: true, badge: false },
  { id: "basic", highlighted: false, free: false, badge: false },
  { id: "pro", highlighted: true, free: false, badge: true },
  { id: "executive", highlighted: false, free: false, badge: false },
] as const;

function Pricing() {
  const t = useTranslations("landing.pricing");
  return (
    <section id="pricing" className="py-24 md:py-32 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center max-w-xl mx-auto mb-16">
          <p className="text-[13px] font-medium mb-3" style={{ color: ORANGE }}>{t("eyebrow")}</p>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white">
            {t("heading")}
          </h2>
          <p className="mt-4 text-[14px] text-white/50">{t("subheading")}</p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {PLAN_IDS.map((plan, i) => {
            const features = t.raw(`plans.${plan.id}.features`) as string[];
            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: i * 0.06 }}
                className={`rounded-2xl p-6 flex flex-col border ${
                  plan.highlighted ? "border-transparent bg-gradient-to-b from-white/[0.06] to-transparent ring-1" : "border-white/10 bg-white/[0.02]"
                }`}
                style={plan.highlighted ? { boxShadow: `0 0 0 1px ${ORANGE}55` } : undefined}
              >
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-[15px] font-semibold text-white">{t(`plans.${plan.id}.name`)}</h3>
                  {plan.badge && (
                    <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full" style={{ background: `${ORANGE}22`, color: ORANGE }}>
                      {t("mostPopular")}
                    </span>
                  )}
                </div>
                <p className="text-[12.5px] text-white/45 mb-5 min-h-[2.2em]">{t(`plans.${plan.id}.desc`)}</p>
                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-3xl font-bold text-white tracking-tight">
                    {plan.id === "free" ? "$0" : plan.id === "basic" ? "$5.99" : plan.id === "pro" ? "$19" : "$59"}
                  </span>
                  <span className="text-[13px] text-white/40">{plan.id === "free" ? "" : "/mo"}</span>
                </div>
                <Link
                  href={kinUrl(plan.free ? "/login" : "/signup")}
                  className={`mb-6 text-center rounded-full py-2.5 text-[13px] font-semibold transition-colors ${
                    plan.highlighted ? "text-white hover:opacity-90" : "border border-white/15 text-white/80 hover:bg-white/5"
                  }`}
                  style={plan.highlighted ? { background: ORANGE } : undefined}
                >
                  {t(`plans.${plan.id}.cta`)}
                </Link>
                <ul className="space-y-2.5">
                  {features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-[12.5px] text-white/55">
                      <Check className="size-3.5 mt-0.5 shrink-0" style={{ color: ORANGE }} />
                      {f}
                    </li>
                  ))}
                </ul>
              </motion.div>
            );
          })}
        </div>
        <p className="text-center mt-8 text-[12px] text-white/35">
          {t("footnote")}
        </p>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   FAQ
   ──────────────────────────────────────────────────────────────────────── */

function FAQ() {
  const t = useTranslations("landing.faq");
  const items = t.raw("items") as { q: string; a: string }[];
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" className="py-24 md:py-32 border-t border-white/5">
      <div className="max-w-2xl mx-auto px-6">
        <p className="text-[13px] font-medium mb-3 text-center" style={{ color: ORANGE }}>{t("eyebrow")}</p>
        <h2 className="text-3xl font-semibold tracking-tight text-white text-center mb-12">
          {t("heading")}
        </h2>
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={item.q} className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left"
              >
                <span className="text-[14px] font-medium text-white">{item.q}</span>
                <ChevronDown className={`size-4 text-white/40 shrink-0 transition-transform ${open === i ? "rotate-180" : ""}`} />
              </button>
              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <p className="px-5 pb-4 text-[13.5px] text-white/55 leading-relaxed">{item.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   CTA + Footer
   ──────────────────────────────────────────────────────────────────────── */

function CTA() {
  const t = useTranslations("landing.cta");
  return (
    <section className="py-24 md:py-28 border-t border-white/5">
      <div className="max-w-2xl mx-auto px-6 text-center">
        <div className="inline-flex size-12 rounded-2xl items-center justify-center mb-6" style={{ background: `${ORANGE}18` }}>
          <MessageCircle className="size-6" style={{ color: ORANGE }} />
        </div>
        <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white mb-4">
          {t("heading")}
        </h2>
        <p className="text-[14.5px] text-white/50 mb-8">
          {t("description")}
        </p>
        <Link
          href={kinUrl("/signup")}
          className="inline-flex items-center gap-2 rounded-full text-white text-sm font-semibold px-7 py-3.5 hover:scale-[1.02] transition-transform"
          style={{ background: ORANGE }}
        >
          {t("button")}
          <ArrowRight className="size-4" />
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  const t = useTranslations("landing.footer");
  return (
    <footer className="border-t border-white/5 py-10">
      <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <KinMark size={20} />
          <span className="text-[13px] text-white/50">{t("tagline")}</span>
        </div>
        <div className="flex items-center gap-6 text-[12.5px] text-white/40">
          <a href="https://personaliai.com" className="hover:text-white/70 transition-colors">{t("personaliai")}</a>
          <a href="https://personaliai.com/privacy" className="hover:text-white/70 transition-colors">{t("privacy")}</a>
          <a href="https://personaliai.com/terms" className="hover:text-white/70 transition-colors">{t("terms")}</a>
        </div>
      </div>
    </footer>
  );
}

/* ────────────────────────────────────────────────────────────────────────
   Page
   ──────────────────────────────────────────────────────────────────────── */

export default function Home() {
  return (
    <div className="min-h-screen bg-neutral-950 text-white antialiased">
      <Nav />
      <main>
        <Hero />
        <Capabilities />
        <HowItWorks />
        <Pricing />
        <FAQ />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
