"use client";

import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Copy, ExternalLink, Link2, Plus, Printer, ShieldOff, QrCode } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Input, Label, Modal, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { KioskLink } from "@/lib/types";

export default function KioskLinksPage() {
  const { data, error, loading, reload } = useAsync(() => api.listKioskLinks(), [], { pollMs: 30_000 });
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [qr, setQr] = useState<KioskLink | null>(null);

  const create = async () => {
    if (label.trim().length < 2) return toast("Give the link a name, e.g. 'OPD waiting area'", "error");
    setBusy(true);
    try {
      const k = await api.createKioskLink(label);
      setLabel("");
      reload();
      setQr(k);
      toast("Kiosk link created");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const copy = (url: string) => {
    navigator.clipboard?.writeText(url);
    toast("Link copied");
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Kiosk links"
        subtitle="Share a link or print its QR. Anyone who opens it — a waiting-room tablet or a patient's own phone — can register and get a token for this facility. No staff login needed."
      />

      <Card className="p-4">
        <Label htmlFor="kl-label">New link</Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input id="kl-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Where will it be used? e.g. OPD waiting area, Camp tablet 2" onKeyDown={(e) => e.key === "Enter" && create()} />
          <Button onClick={create} loading={busy} variant="teal" icon={<Plus className="size-4" />}>
            Create link
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted">A kiosk link can only register patients, record consent, upload reports and submit intakes. It can never read the queue or any notes. Revoke it any time.</p>
      </Card>

      <div className="mt-5">
        {error ? (
          <ErrorNote error={error} onRetry={reload} />
        ) : loading && !data ? (
          <Spinner />
        ) : !data?.length ? (
          <Card>
            <Empty icon={<Link2 className="size-6" />} title="No kiosk links yet" body="Create one above for each place patients will check in." />
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
                      <p className="font-semibold text-ink">{k.label}</p>
                      <span className="rounded-md bg-canvas px-2 py-0.5 font-mono text-sm font-bold tracking-widest text-ink-2">{k.code}</span>
                      {k.revoked ? <Badge tone="crit">Revoked</Badge> : <Badge tone="rout">Active</Badge>}
                    </div>
                    <p className="mt-0.5 truncate font-mono text-xs text-muted">{k.url}</p>
                    <p className="mt-1 text-xs text-subtle">
                      {k.intakes_today} intake{k.intakes_today === 1 ? "" : "s"} today · {k.sessions} session{k.sessions === 1 ? "" : "s"} opened
                      {k.last_used_at && ` · last used ${timeAgo(k.last_used_at)}`} · created by {k.created_by}
                    </p>
                  </div>
                  {!k.revoked && (
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" icon={<Copy className="size-4" />} onClick={() => copy(k.url)}>
                        Copy
                      </Button>
                      <a href={k.url} target="_blank" rel="noreferrer">
                        <Button size="sm" variant="secondary" icon={<ExternalLink className="size-4" />}>
                          Open
                        </Button>
                      </a>
                      <Button size="sm" variant="secondary" icon={<QrCode className="size-4" />} onClick={() => setQr(k)}>
                        QR
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={<ShieldOff className="size-4" />}
                        onClick={async () => {
                          if (!confirm(`Revoke "${k.label}"? Tablets using it will stop working immediately.`)) return;
                          await api.revokeKioskLink(k.id);
                          toast("Link revoked");
                          reload();
                        }}
                      >
                        Revoke
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
        subtitle="Print and put this up where patients wait, or open the link on a tablet."
        footer={
          <>
            <Button variant="secondary" icon={<Copy className="size-4" />} onClick={() => qr && copy(qr.url)}>
              Copy link
            </Button>
            <Button
              icon={<Printer className="size-4" />}
              onClick={() => {
                const svg = document.getElementById("kiosk-qr")?.outerHTML ?? "";
                const w = window.open("", "_blank");
                if (!w || !qr) return;
                w.document.write(
                  `<html><head><title>${qr.label}</title></head><body style="font-family:system-ui;text-align:center;padding:48px"><h1 style="margin:0 0 8px">Scan to get your token</h1><p style="color:#555;margin:0 0 24px">${qr.label}</p>${svg.replace(/width="\d+"/, 'width="360"').replace(/height="\d+"/, 'height="360"')}<p style="font:600 22px monospace;letter-spacing:4px">${qr.code}</p><p style="color:#555">${qr.url}</p><p style="color:#a33;font-size:12px;margin-top:32px">Triage support only — not a diagnosis. A health worker reviews every entry.</p><script>window.onload=()=>window.print()</script></body></html>`,
                );
                w.document.close();
              }}
            >
              Print poster
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
