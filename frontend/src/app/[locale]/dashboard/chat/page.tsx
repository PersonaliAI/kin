import { ChatView } from "@/components/dashboard/chat-view";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";

export const dynamic = "force-dynamic";

export default async function ChatPage({
  searchParams,
}: {
  searchParams: Promise<{ voice?: string; s?: string }>;
}) {
  const { kin } = await getCurrentKinUser();
  const supabase = await createClient();
  const sp = await searchParams;
  let sessionId: string = sp.s || "";
  if (!sessionId) {
    const { data: latest } = await supabase
      .from("messages")
      .select("session_id")
      .eq("user_id", kin.id)
      .eq("source", "web")
      .order("created_at", { ascending: false })
      .limit(1);
    sessionId = (latest?.[0]?.session_id as string) || `web-${kin.id}`;
  }

  const { data: rows } = await supabase
    .from("messages")
    .select("id, role, content, audio_url, created_at")
    .eq("user_id", kin.id)
    .eq("source", "web")
    .eq("session_id", sessionId)
    .order("created_at", { ascending: false })
    .limit(40);

  const initial = (rows ?? [])
    .reverse()
    .map((r) => ({
      id: r.id as string,
      role: (r.role as "user" | "assistant") ?? "user",
      content: r.content ?? "",
      ...(r.audio_url ? { kind: "voice" as const, audioUrl: r.audio_url as string } : {}),
    }));

  return (
    <ChatView
      initial={initial}
      initialSessionId={sessionId}
      voiceFirst={sp?.voice === "1"}
    />
  );
}
