"use client";

import { useState } from "react";
import { Users, KeyRound, RotateCcw, UserX, UserCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { useSession, usePrefs } from "@/components/providers";
import { Badge, Button, Card, Empty, ErrorNote, Modal, Select, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { langByCode } from "@/lib/i18n/languages";
import { DutyList } from "@/components/staff/duty";
import type { Role, User } from "@/lib/types";

const STAFF_ROLES: { v: Role; label: string }[] = [
  { v: "doctor", label: "Doctor" },
  { v: "nurse", label: "Nurse / ANM" },
  { v: "receptionist", label: "Receptionist" },
  { v: "supervisor", label: "Supervisor" },
];

type Pending = { user: User; kind: "reset" | "deactivate" | "reactivate" };

export default function StaffPage() {
  const { tr } = usePrefs();
  const { user: me } = useSession();
  const canManage = me?.role === "supervisor";
  const { data, error, loading, reload } = useAsync(() => api.listUsers(), []);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    try {
      await fn();
      toast(done);
      setPending(null);
      reload();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : tr("Action failed"), "error");
    } finally {
      setBusy(false);
    }
  }

  const confirm = pending && {
    reset: { title: `Reset ${pending.user.name}’s PIN?`, body: "Their current PIN stops working now. At their next sign-in they verify their phone with an OTP and create a new PIN.", cta: "Reset PIN", go: () => run(() => api.resetStaffPin(pending.user.id), "PIN reset — they will set a new one at next sign-in") },
    deactivate: { title: `Deactivate ${pending.user.name}?`, body: "They are signed out everywhere and cannot sign in until reactivated. Their past work and audit history are kept.", cta: "Deactivate", go: () => run(() => api.updateUser(pending.user.id, { is_active: false }), "Account deactivated") },
    reactivate: { title: `Reactivate ${pending.user.name}?`, body: "They can sign in again with their phone OTP and PIN.", cta: "Reactivate", go: () => run(() => api.updateUser(pending.user.id, { is_active: true }), "Account reactivated") },
  }[pending.kind];

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={tr("Staff")} subtitle={canManage ? tr("Accounts linked to this facility. Change roles, reset forgotten PINs or remove access. Every change is audited.") : tr("Accounts linked to this facility. New staff register themselves with phone OTP and a PIN.")} />
      {canManage && data && (
        <div className="mb-4">
          <DutyList staff={data} onChange={reload} compact />
        </div>
      )}
      {error ? (
        <ErrorNote error={error} onRetry={reload} />
      ) : loading && !data ? (
        <Spinner />
      ) : !data?.length ? (
        <Card>
          <Empty icon={<Users className="size-6" />} title={tr("No staff yet")} />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {data.map((u) => {
              const self = u.id === me?.id;
              const inactive = u.is_active === false;
              return (
                <li key={u.id} className={inactive ? "flex flex-wrap items-center gap-3 bg-canvas/60 px-4 py-3 opacity-75" : "flex flex-wrap items-center gap-3 px-4 py-3"}>
                  <span className="grid size-10 place-items-center rounded-full bg-teal-50 font-bold text-teal-700">{u.name.replace(/^Dr\.\s*/, "").charAt(0)}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-ink">
                      {u.name} {self && <span className="text-xs font-normal text-muted">{tr("(you)")}</span>}
                    </p>
                    <p className="text-xs text-muted">
                      +91 {u.phone.slice(0, 5)}••••• · {tr(langByCode(u.language).name)} {tr("· joined")} {timeAgo(u.created_at)}
                    </p>
                  </div>
                  {u.registration_no && <Badge>{u.registration_no}</Badge>}
                  {u.has_pin ? (
                    <Badge tone="teal">
                      <KeyRound className="size-3" /> {tr("PIN set")}
                    </Badge>
                  ) : (
                    <Badge tone="semi">{tr("PIN pending")}</Badge>
                  )}
                  {inactive && <Badge tone="crit">{tr("Deactivated")}</Badge>}
                  {canManage && !self ? (
                    <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                      <Select aria-label={`Role for ${u.name}`} value={u.role} disabled={busy || inactive} onChange={(e) => run(() => api.updateUser(u.id, { role: e.target.value as Role }), `Role changed to ${e.target.value}`)} className="h-9 w-36 text-sm">
                        {STAFF_ROLES.map((r) => (
                          <option key={r.v} value={r.v}>
                            {tr(r.label)}
                          </option>
                        ))}
                      </Select>
                      {!inactive && (
                        <Button size="sm" variant="secondary" icon={<RotateCcw className="size-4" />} onClick={() => setPending({ user: u, kind: "reset" })}>
                          {tr("Reset PIN")}
                        </Button>
                      )}
                      {inactive ? (
                        <Button size="sm" variant="secondary" icon={<UserCheck className="size-4" />} onClick={() => setPending({ user: u, kind: "reactivate" })}>
                          {tr("Reactivate")}
                        </Button>
                      ) : (
                        <Button size="sm" variant="ghost" icon={<UserX className="size-4" />} onClick={() => setPending({ user: u, kind: "deactivate" })}>
                          {tr("Deactivate")}
                        </Button>
                      )}
                    </div>
                  ) : (
                    <Badge tone="info">{tr(u.role)}</Badge>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      )}
      <Modal
        open={!!pending}
        onClose={() => setPending(null)}
        size="sm"
        title={tr(confirm?.title)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPending(null)}>
              {tr("Cancel")}
            </Button>
            <Button variant={pending?.kind === "deactivate" ? "danger" : "primary"} loading={busy} onClick={confirm?.go}>
              {confirm?.cta}
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-2">{tr(confirm?.body)}</p>
      </Modal>
    </div>
  );
}
