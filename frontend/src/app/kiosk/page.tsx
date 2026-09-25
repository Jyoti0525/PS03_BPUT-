"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, TabletSmartphone, Wifi, WifiOff, CloudUpload, ShieldCheck, LogIn } from "lucide-react";
import { api, getDeviceId } from "@/lib/api";
import { useSession } from "@/components/providers";
import { useAsync, useOnline } from "@/lib/hooks";
import { A11yButton, LanguageButton, Logo } from "@/components/layout/chrome";
import { Badge, Button, Card, Input, Label, Spinner, Toggle } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { IntakeFlow } from "@/components/intake/intake-flow";
import { flushOutbox, isSimulatedOffline, setSimulatedOffline, subscribeOutbox, type OutboxItem } from "@/lib/offline/outbox";
import { STAFF_ROLES } from "@/lib/types";

export default function KioskPage() {
  const { user, loading, signOut } = useSession();
  const router = useRouter();
  const online = useOnline();
  const [simOffline, setSimOfflineState] = useState(isSimulatedOffline);
  const [session, setSession] = useState(0);
  const setSimOffline = (v: boolean) => {
    setSimulatedOffline(v);
    setSimOfflineState(v);
  };
  const [outbox, setOutbox] = useState<OutboxItem[]>([]);
  const [label, setLabel] = useState("OPD entrance tablet");
  const [binding, setBinding] = useState(false);
  const isStaff = !!user && STAFF_ROLES.includes(user.role);
  const deviceId = typeof window === "undefined" ? "" : getDeviceId();
  const { data: devices, reload } = useAsync(() => (isStaff ? api.listDevices() : Promise.resolve([])), [isStaff]);
  const { data: facility } = useAsync(() => (user?.facility_id ? api.getFacility(user.facility_id) : Promise.resolve(null)), [user?.facility_id]);
  const bound = devices?.find((d) => d.id === deviceId && !d.revoked);
  const offline = !online || simOffline;

  useEffect(() => subscribeOutbox(setOutbox), []);

  useEffect(() => {
    if (!simOffline && online && outbox.length) {
      flushOutbox().then((r) => r.sent && toast(`${r.sent} offline intake${r.sent > 1 ? "s" : ""} synced`));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simOffline, online]);

  if (loading) return <Spinner />;

  /* Patients do not log in — a staff member unlocks the device. */
  if (!isStaff) {
    return (
      <div className="grid min-h-[calc(100vh-28px)] place-items-center bg-canvas p-4">
        <Card className="max-w-md p-8 text-center">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-coral-100 text-coral-700">
            <Lock className="size-7" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-ink">Kiosk locked</h1>
          <p className="mt-2 text-muted">Patients do not sign in. A nurse, ANM or receptionist unlocks this tablet with their staff account; it then stays in intake mode.</p>
          <Link href="/auth?next=/kiosk">
            <Button size="xl" className="mt-6 w-full" icon={<LogIn className="size-5" />}>
              Staff unlock
            </Button>
          </Link>
          {user && <p className="mt-3 text-sm text-crit">Signed in as {user.role} — kiosk requires a staff role.</p>}
        </Card>
      </div>
    );
  }

  if (devices && !bound) {
    return (
      <div className="grid min-h-[calc(100vh-28px)] place-items-center bg-canvas p-4">
        <Card className="max-w-md p-8">
          <div className="grid size-14 place-items-center rounded-2xl bg-teal-50 text-teal-700">
            <TabletSmartphone className="size-7" />
          </div>
          <h1 className="mt-4 text-2xl font-bold text-ink">Bind this device</h1>
          <p className="mt-2 text-muted">
            This tablet is not yet registered to <strong>{facility?.name ?? "your facility"}</strong>. Binding lets it submit intakes under the facility and is recorded in the audit log.
          </p>
          <div className="mt-5">
            <Label htmlFor="dev-label">Device name</Label>
            <Input id="dev-label" value={label} onChange={(e) => setLabel(e.target.value)} />
            <p className="mt-1 font-mono text-xs text-subtle">{deviceId}</p>
          </div>
          <Button
            size="lg"
            className="mt-5 w-full"
            variant="teal"
            loading={binding}
            onClick={async () => {
              setBinding(true);
              try {
                await api.bindDevice(label, deviceId);
                toast("Device bound to facility");
                reload();
              } catch (e) {
                toast(e instanceof Error ? e.message : "Failed", "error");
              } finally {
                setBinding(false);
              }
            }}
            icon={<ShieldCheck className="size-5" />}
          >
            Bind device
          </Button>
        </Card>
      </div>
    );
  }

  if (!devices) return <Spinner />;

  return (
    <div className="min-h-[calc(100vh-28px)] bg-[linear-gradient(180deg,var(--color-teal-50),var(--color-canvas)_40%)]">
      <header className="no-print border-b border-line bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
          <Logo />
          <span className="hidden text-sm text-muted md:inline">{facility?.name} · {bound?.label}</span>
          <div className="ml-auto flex items-center gap-2">
            {offline ? <Badge tone="semi"><WifiOff className="size-3" /> Offline</Badge> : <Badge tone="rout"><Wifi className="size-3" /> Online</Badge>}
            {outbox.length > 0 && <Badge tone="info"><CloudUpload className="size-3" /> {outbox.length} queued</Badge>}
            <LanguageButton />
            <A11yButton />
            <Button
              variant="ghost"
              size="sm"
              icon={<Lock className="size-4" />}
              onClick={async () => {
                await signOut();
                router.replace("/kiosk");
              }}
            >
              Lock
            </Button>
          </div>
        </div>
      </header>
      <main className="px-4 py-6">
        {user?.facility_id && <IntakeFlow key={session} mode="kiosk" facilityId={user.facility_id} offline={offline} onReset={() => setSession((n) => n + 1)} />}
        <div className="no-print mx-auto mt-8 max-w-3xl rounded-2xl border border-dashed border-line bg-white/70 p-4">
          <Toggle
            checked={simOffline}
            onChange={setSimOffline}
            label="Simulate offline (rural camp)"
            description="Intakes are queued in IndexedDB on this device and synced automatically when you switch back online."
          />
          <p className="mt-2 text-xs text-muted">Staff on duty: {user?.name}</p>
        </div>
      </main>
    </div>
  );
}
