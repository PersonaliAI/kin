"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { cn } from "@/lib/utils";
import { scheduleApi } from "@/lib/backend";
import { Loader2, Play, CheckCircle2, AlertCircle } from "lucide-react";

/**
 * Stateful component to render the custom interactive "Test Now" button in chat
 * and display the live schedule execution results inline.
 */
function TestScheduleButton({ taskId, label }: { taskId: string; label: string }) {
  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [result, setResult] = useState<{ reply: string; detail?: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function handleTest() {
    setStatus("running");
    setErrorMsg(null);
    try {
      const res = await scheduleApi.test(taskId);
      setResult(res);
      setStatus("success");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to run test");
      setStatus("error");
    }
  }

  return (
    <div className="my-3 space-y-2.5 max-w-xl">
      <button
        onClick={handleTest}
        disabled={status === "running"}
        className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 disabled:from-violet-600/60 disabled:to-indigo-600/60 text-white rounded-xl text-xs font-semibold shadow-md transition-all cursor-pointer select-none active:scale-95 disabled:pointer-events-none"
      >
        {status === "running" ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Play className="size-3.5 fill-current" />
        )}
        {status === "running" ? "Running Test..." : label || "Test Now"}
      </button>

      {status === "error" && (
        <div className="flex items-start gap-2 bg-destructive/10 border border-destructive/20 rounded-xl p-3 text-xs text-destructive">
          <AlertCircle className="size-4 shrink-0 mt-0.5" />
          <span className="font-medium">{errorMsg}</span>
        </div>
      )}

      {status === "success" && result && (
        <div className="bg-background/40 backdrop-blur-md border border-border rounded-xl p-4 shadow-sm space-y-2.5 animate-in fade-in duration-300">
          <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
            <CheckCircle2 className="size-4" />
            Test execution completed successfully
          </div>
          {result.detail && (
            <div className="text-xs text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
              {result.detail}
            </div>
          )}
          <div className="bg-muted/40 border border-border/60 rounded-lg p-3 max-h-[300px] overflow-y-auto">
            <Markdown className="text-xs">{result.reply || "*No output returned.*"}</Markdown>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Markdown renderer with GitHub-flavored markdown + KaTeX math support.
 *
 * Math syntax:
 *   inline:  $E = mc^2$
 *   block:   $$\sum_{n=1}^{N} n = \frac{N(N+1)}{2}$$
 *
 * GFM extras: tables, strikethrough, task lists, autolinks.
 */
export function Markdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        // Prose-ish typography without pulling in @tailwindcss/typography
        "text-sm leading-relaxed [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0",
        "[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:my-2 [&_li]:my-0.5",
        "[&_strong]:font-semibold [&_em]:italic",
        "[&_a]:underline [&_a]:underline-offset-2 [&_a]:font-medium hover:[&_a]:text-foreground/80",
        "[&_code]:font-mono [&_code]:text-[0.85em] [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded",
        "[&_pre]:bg-muted [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre_code]:bg-transparent [&_pre_code]:p-0",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:my-2 [&_blockquote]:text-muted-foreground",
        "[&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-3 [&_h1]:mb-1",
        "[&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1",
        "[&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1",
        "[&_table]:w-full [&_table]:my-2 [&_table]:text-xs [&_th]:text-left [&_th]:font-semibold [&_th]:px-2 [&_th]:py-1 [&_th]:border-b [&_th]:border-border [&_td]:px-2 [&_td]:py-1 [&_td]:border-b [&_td]:border-border/50",
        "[&_hr]:border-border [&_hr]:my-3",
        // Math block spacing
        "[&_.katex-display]:my-3 [&_.katex-display]:overflow-x-auto",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ href, children, ...props }) => {
            if (href?.startsWith("test-schedule:")) {
              const taskId = href.slice("test-schedule:".length);
              const label = typeof children === "string" ? children : "Test Now";
              return <TestScheduleButton taskId={taskId} label={label} />;
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
