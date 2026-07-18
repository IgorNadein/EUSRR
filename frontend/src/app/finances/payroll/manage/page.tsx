"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { PayrollAdminWorkspace } from "@/components/finance/admin/PayrollAdminWorkspace";
import { useUser } from "@/contexts/UserContext";
import { canOpenPayrollAdmin } from "@/lib/permissions";

export default function PayrollManagePage() {
  const { user, loading } = useUser();
  const router = useRouter();
  const canManagePayroll = canOpenPayrollAdmin(user);

  useEffect(() => {
    if (!loading && user && !canManagePayroll) router.replace("/finances");
  }, [canManagePayroll, loading, router, user]);

  return (
    <AppShell desktopWideMode>
      {!loading && canManagePayroll ? (
        <PayrollAdminWorkspace />
      ) : (
        <section className="app-surface flex min-h-64 items-center justify-center rounded-2xl">
          <Loader2 className="app-accent-text animate-spin" size={26} />
        </section>
      )}
    </AppShell>
  );
}
