"use client";

import { usePrefs } from "@/components/providers";
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Copy, KeyRound, Printer, QrCode, ShieldOff, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, useNow, timeAgo } from "@/lib/hooks";
import { Badge, Button, Label, Modal, Select } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Encounter, ShareLink } from "@/lib/types";

const VALIDITY = [
  { h: 24, label: "24 hours" },
  { h: 72, label: "3 days" },
  { h: 168, label: "7 days" },
  { h: 720, label: "30 days" },
];

export function printShareSlip(enc: Encounter, link: ShareLink, facilityName?: string) {
  const svg = document.getElementById(`share-qr-${link.id}`)?.outerHTML ?? "";
  const w = window.open("", "_blank");
  if (!w) return;
  const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!);
  w.document.write(`<html><head><title>Referral summary ${esc(enc.patient.code)}</title>
<style>body{font-family:system-ui,sans-serif;max-width:520px;margin:32px auto;color:#111;text-align:center}
.card{border:2px solid #16182b;border-radius:16px;padding:24px}h1{font-size:20px;margin:0}p{margin:6px 0}
.code{font:700 30px ui-monospace,monospace;letter-spacing:8px;margin:8px 0}.muted{color:#555;font-size:13px}</style></head>
<body><div class="card"><h1>Patient summary — scan to open</h1>
<p class="muted">${esc(facilityName ?? "")}</p>
<p><b>${esc(enc.patient.name)}</b> · ${enc.patient.age}/${enc.patient.sex} · ${esc(enc.patient.code)}${enc.token ? ` · Token ${esc(enc.token)}` : ""}</p>
${svg.replace(/width="\d+"/, 'width="260"').replace(/height="\d+"/, 'height="260"')}
<p class="muted">Access code</p><p class="code">${esc(link.access_code ?? "••••••")}</p>
<p class="muted">Valid until ${new Date(link.expires_at).toLocaleString("en-IN")}</p>
<p class="muted" style="word-break:break-all">${esc(link.url)}</p>
<p class="muted" style="color:#a33;margin-top:16px">Triage support only — not a diagnosis. For the receiving clinician.</p></div>
<script>window.onload=()=>window.print()</script></body></html>`);
  w.document.close();
}

/** Create and manage the QR summary for one encounter. */
export function ShareQrModal({ enc, facilityName, onClose, initial }: { enc: Encounter; facilityName?: string; onClose: () => void; initial?: ShareLink | null }) {
  const { tr } = usePrefs();
  const [hours, setHours] = useState(72);
  const [created, setCreated] = useState<ShareLink | null>(initial ?? null);
  const [busy, setBusy] = useState(false);
  const { data: links, reload } = useAsync(() => api.listShares(enc.id), [enc.id]);
  const now = useNow(60_000);

  const create = async () => {
    setBusy(true);
    try {
      setCreated(await api.createShare(enc.id, hours, "referral"));
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Could not create link"), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={tr("QR summary for referral")}
      subtitle={tr("The receiving clinician scans the QR and enters the access code to see this patient's details, the reviewed note, the referral and the uploaded documents.")}
    >
      {created ? (
        <div className="grid items-center gap-6 sm:grid-cols-[auto_1fr]">
          <div className="mx-auto rounded-2xl border border-line bg-white p-3">
            <QRCodeSVG id={`share-qr-${created.id}`} value={created.url} size={200} />
          </div>
          <div>
            <p className="flex items-center gap-1.5 text-sm text-muted">
              <KeyRound className="size-4" /> {tr("Access code — shown only now")}
            </p>
            <p className="font-mono text-4xl font-extrabold tracking-[0.3em] text-ink">{created.access_code}</p>
            <p className="mt-2 flex items-center gap-1.5 text-sm text-muted">
              <Clock className="size-4" /> {tr("Valid until")} {new Date(created.expires_at).toLocaleString("en-IN")}
            </p>
            <p className="mt-2 font-mono text-xs break-all text-subtle">{created.url}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button icon={<Printer className="size-4" />} onClick={() => printShareSlip(enc, created, facilityName)}>
                {tr("Print slip")}
              </Button>
              <Button
                variant="secondary"
                icon={<Copy className="size-4" />}
                onClick={() => {
                  navigator.clipboard?.writeText(`${created.url}\nAccess code: ${created.access_code}`);
                  toast(tr("Link and code copied"));
                }}
              >
                {tr("Copy link + code")}
              </Button>
              <Button variant="ghost" onClick={() => setCreated(null)}>
                {tr("New link")}
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted">{tr("Give the slip to the patient or send it with the referral. Share the code separately if you send the link by message.")}</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Label htmlFor="share-hours">{tr("Link valid for")}</Label>
            <Select id="share-hours" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
              {VALIDITY.map((v) => (
                <option key={v.h} value={v.h}>
                  {tr(v.label)}
                </option>
              ))}
            </Select>
          </div>
          <Button variant="teal" size="lg" loading={busy} onClick={create} icon={<QrCode className="size-5" />}>
            {tr("Create QR")}
          </Button>
        </div>
      )}

      {!!links?.length && (
        <div className="mt-6 border-t border-line pt-4">
          <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Links for this visit")}</p>
          <ul className="space-y-2">
            {links.map((l) => {
              const expired = Date.parse(l.expires_at) < now;
              return (
                <li key={l.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm">
                  <span className="flex-1 text-ink">
                    {tr("by")} {l.created_by} · {timeAgo(l.created_at)} {tr("· opened")} {l.views}×
                  </span>
                  {l.revoked ? <Badge tone="crit">{tr("Revoked")}</Badge> : expired ? <Badge>{tr("Expired")}</Badge> : <Badge tone="rout">{tr("Active until")} {new Date(l.expires_at).toLocaleDateString("en-IN")}</Badge>}
                  {!l.revoked && !expired && (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<ShieldOff className="size-4" />}
                      onClick={async () => {
                        await api.revokeShare(l.id);
                        toast(tr("Link revoked"));
                        reload();
                      }}
                    >
                      {tr("Revoke")}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Modal>
  );
}
