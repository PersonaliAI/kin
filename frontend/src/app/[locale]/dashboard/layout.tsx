import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getCurrentKinUser } from "@/lib/user";
import { DashboardShell } from "@/components/dashboard/shell";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Dashboard",
  robots: { index: false, follow: false },
};

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { authEmail, authName, authAvatar, kin } = await getCurrentKinUser();

  return (
    <DashboardShell
      user={{
        authEmail,
        authName,
        authAvatar: authAvatar ?? kin.avatar_url,
      }}
    >
      {children}
    </DashboardShell>
  );
}
