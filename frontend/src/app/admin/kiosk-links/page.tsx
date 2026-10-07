"use client";

import { usePrefs } from "@/components/providers";
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Copy, ExternalLink, House, Link2, Plus, Printer, ShieldOff, QrCode } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Input, Label, Modal, Spinner, Toggle } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { KioskLink } from "@/lib/types";

export default function KioskLinksPage() {
  const { tr } = usePrefs();
  const { data, error, loading, reload } = useAsync(() => api.listKioskLinks(), [], { pollMs: 30_000 });
  const [label, setLabel] = useState("");
  const [forHome, setForHome] = useState(false);
  const [busy, setBusy] = useState(false);
  const [qr, setQr] = useState<KioskLink | null>(null);

  const create = async () => {
    if (label.trim().length < 2) return toast(tr("Give the link a name, e.g. 'OPD waiting area'"), "error");
    setBusy(true);
    try {
      const k = await api.createKioskLink(label, forHome);
      setLabel("");
      setForHome(false);
      reload();
      setQr(k);
      toast(tr("Kiosk link created"));
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Failed"), "error");
    } finally {
      setBusy(false);
    }
  };

  const copy = (url: string) => {
    navigator.clipboard?.writeText(url);
    toast(tr("Link copied"));
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={tr("Kiosk links")}
        subtitle={tr("Share a link or print its QR. Anyone who opens it — a waiting-room tablet or a patient's own phone — can register and get a token for this facility. No staff login needed.")}
      />

      <Card className="p-4">
        <Label htmlFor="kl-label">{tr("New link")}</Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input id="kl-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder={tr("Where will it be used? e.g. OPD waiting area, Camp tablet 2")} onKeyDown={(e) => e.key === "Enter" && create()} />
          <Button onClick={create} loading={busy} variant="teal" icon={<Plus className="size-4" />}>
            {tr("Create link")}
          </Button>
        </div>
        <div className="mt-3">
          <Toggle
            checked={forHome}
            onChange={setForHome}
            label={tr("For filling in from home")}
            description={tr("Share it by SMS or on a poster. Patients fill in before coming and get an H- number; they join the queue only when the desk checks them in, so nobody is moved ahead of people already waiting.")}
          />
        </div>
        <p className="mt-2 text-xs text-muted">{tr("A kiosk link can only register patients, record consent, upload reports and submit intakes. It can never read the queue or any notes. Revoke it any time.")}</p>
      </Card>

      <div className="mt-5">
        {error ? (
          <ErrorNote error={error} onRetry={reload} />
        ) : loading && !data ? (
          <Spinner />
        ) : !data?.length ? (
          <Card>
            <Empty icon={<Link2 className="size-6" />} title={tr("No kiosk links yet")} body={tr("Create one above for each place patients will check in.")} />
          </Card>
        ) : (
          <div className="grid gap-3">
            {data.map((k) => (
              <Card key={k.id} className={k.revoked ? "opacity-60" : ""}>
                <div className="flex flex-wrap items-center gap-4 p-4">
                  <button onClick={() => !k.revoked && setQr(k)} className="rounded-xl border border-line bg-white p-1.5" aria-label={`Show QR for ${k.label}`}>
                    <QRCodeSVG value={k.url} size={64} />
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-ink">{tr(k.label)}</p>
                      <span className="rounded-md bg-canvas px-2 py-0.5 font-mono text-sm font-bold tracking-widest text-ink-2">{k.code}</span>
                      {k.revoked ? <Badge tone="crit">{tr("Revoked")}</Badge> : <Badge tone="rout">{tr("Active")}</Badge>}
                      {k.for_home && (
                        <Badge tone="info">
                          <House className="size-3" /> {tr("From home")}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-0.5 truncate font-mono text-xs text-muted">{k.url}</p>
                    <p className="mt-1 text-xs text-subtle">
                      {k.intakes_today} {tr("intake")}{k.intakes_today === 1 ? "" : "s"} {tr("today ·")} {k.sessions} {tr("session")}{k.sessions === 1 ? "" : "s"} {tr("opened")}
                      {k.last_used_at && ` · ${tr("last used {t}", { t: timeAgo(k.last_used_at) })}`} {tr("· created by")} {k.created_by}
                    </p>
                  </div>
                  {!k.revoked && (
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" icon={<Copy className="size-4" />} onClick={() => copy(k.url)}>
                        {tr("Copy")}
                      </Button>
                      <a href={k.url} target="_blank" rel="noreferrer">
                        <Button size="sm" variant="secondary" icon={<ExternalLink className="size-4" />}>
                          {tr("Open")}
                        </Button>
                      </a>
                      <Button size="sm" variant="secondary" icon={<QrCode className="size-4" />} onClick={() => setQr(k)}>
                        {tr("QR")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<ShieldOff className="size-4" />}
                        onClick={async () => {
                          if (!confirm(`Revoke "${k.label}"? Tablets using it will stop working immediately.`)) return;
                          await api.revokeKioskLink(k.id);
                          toast(tr("Link revoked"));
                          reload();
                        }}
                      >
                        {tr("Revoke")}
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={!!qr}
        onClose={() => setQr(null)}
        title={qr?.label ?? ""}
        subtitle={tr("Print and put this up where patients wait, or open the link on a tablet.")}
        footer={
          <>
            <Button variant="secondary" icon={<Copy className="size-4" />} onClick={() => qr && copy(qr.url)}>
              {tr("Copy link")}
            </Button>
            <Button
              icon={<Printer className="size-4" />}
              onClick={() => {
                const svg = document.getElementById("kiosk-qr")?.outerHTML ?? "";
                const w = window.open("", "_blank");
                if (!w || !qr) return;
                w.document.write(
                  `<html><head><title>${qr.label}</title></head><body style="font-family:system-ui;text-align:center;padding:48px"><h1 style="margin:0 0 8px">${qr.for_home ? "Fill in before you come" : "Scan to get your token"}</h1>${qr.for_home ? '<p style="margin:0 0 8px">Show your H- number at the desk when you arrive. Your place in the queue starts when you arrive.</p><p style="margin:0 0 16px;font-weight:600">Chest pain, trouble breathing, heavy bleeding or fits: do not wait — go to emergency or call 108.</p>' : ""}<p style="color:#555;margin:0 0 24px">${qr.label}</p>${svg.replace(/width="\d+"/, 'width="360"').replace(/height="\d+"/, 'height="360"')}<p style="font:600 22px monospace;letter-spacing:4px">${qr.code}</p><p style="color:#555">${qr.url}</p><p style="color:#a33;font-size:12px;margin-top:32px">Triage support only — not a diagnosis. A health worker reviews every entry.</p><script>window.onload=()=>window.print()</script></body></html>`,
                );
                w.document.close();
              }}
            >
              {tr("Print poster")}
            </Button>
          </>
        }
      >
        {qr && (
          <div className="flex flex-col items-center gap-3 py-2">
            <QRCodeSVG id="kiosk-qr" value={qr.url} size={220} />
            <p className="font-mono text-lg font-bold tracking-[0.3em] text-ink">{qr.code}</p>
            <p className="font-mono text-xs break-all text-muted">{qr.url}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
