import { cache } from "react";
import { createClient } from "@/lib/supabase/server";

export type KinUser = {
  id: string;
  auth_user_id: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  
  briefing_enabled: boolean;
  plan: string;
};

/**
 * Server-side: resolve the public.users row for the current authed visitor.
 * Wrapped in React.cache so multiple components in the same request (layout +
 * page) share a single Supabase round-trip.
 */
export const getCurrentKinUser = cache(async (): Promise<{
  authEmail: string;
  authName: string;
  authAvatar: string | null;
  kin: KinUser;
}> => {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("not authenticated");

  const meta = (user.user_metadata ?? {}) as Record<string, unknown>;
  const authName =
    (meta.full_name as string) ||
    (meta.name as string) ||
    (user.email?.split("@")[0] ?? "there");
  const authAvatar = (meta.avatar_url as string) ?? null;

  const { data, error } = await supabase
    .from("users")
    .select(
      "id, auth_user_id, email, display_name, avatar_url, briefing_enabled, plan",
    )
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (error) throw error;

  if (data) {
    return {
      authEmail: user.email ?? "",
      authName,
      authAvatar,
      kin: data as KinUser,
    };
  }

  // Trigger didn't fire (legacy account) — create the row ourselves.
  const { data: created, error: insErr } = await supabase
    .from("users")
    .insert({
      auth_user_id: user.id,
      email: user.email,
      display_name: authName,
      avatar_url: authAvatar,
    })
    .select(
      "id, auth_user_id, email, display_name, avatar_url, briefing_enabled, plan",
    )
    .single();
  if (insErr) throw insErr;

  return {
    authEmail: user.email ?? "",
    authName,
    authAvatar,
    kin: created as KinUser,
  };
});
