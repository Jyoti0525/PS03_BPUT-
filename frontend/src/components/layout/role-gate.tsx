"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSession, usePrefs } from "@/components/providers";
import type { Role } from "@/lib/types";
import { Spinner } from "@/components/ui";

export const HOME_FOR_ROLE: Record<Role, string> = {
  doctor: "/reviewer",
  medical_officer: "/reviewer",
  nurse: "/nurse",
  health_worker: "/nurse",
  receptionist: "/desk",
  supervisor: "/admin",
  patient: "/patient",
  employer: "/employer",
  kiosk: "/kiosk",
};

/** Client-side role-based access. The API enforces the same rules server-side. */
export function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { tr } = usePrefs();
  const { user, loading } = useSession();
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/auth?next=${encodeURIComponent(path)}`);
    else if (!roles.includes(user.role)) router.replace(HOME_FOR_ROLE[user.role]);
  }, [user, loading, roles, router, path]);

  if (loading || !user || !roles.includes(user.role)) return <Spinner label={tr("Checking access…")} />;
  return <>{children}</>;
}
