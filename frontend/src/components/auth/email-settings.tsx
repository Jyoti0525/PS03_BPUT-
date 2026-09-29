"use client";

import { useState } from "react";
import { MailCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useSession, usePrefs } from "@/components/providers";
import { Button, FieldError, Input, Label, Modal } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { OtpBoxes } from "./fields";
import { localiseServerMessage } from "@/lib/i18n/phrases";

/** Add, change or remove the verified email that can receive sign-in codes. */
export function EmailModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, refresh } = useSession();
  const { tr, lang } = usePrefs();
  const [email, setEmail] = useState("");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setEmail("");
    setChallenge(null);
    setCode("");
    setErr(null);
    onClose();
  };
  const fail = (e: unknown) => setErr(localiseServerMessage(e instanceof ApiError ? e.message : tr("Something went wrong"), tr));

  async function send() {
    setErr(null);
    if (!/^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$/.test(email.trim())) return setErr(tr("Enter a valid email address"));
    setBusy(true);
    try {
      setChallenge((await api.emailStart(email.trim().toLowerCase(), lang)).challenge_id);
      toast(tr("Code sent to {e}", { e: email.trim() }), "info");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!challenge) return;
    setErr(null);
    if (code.length !== 6) return setErr(tr("Enter all 6 digits"));
    setBusy(true);
    try {
      await api.emailConfirm(challenge, code);
      await refresh();
      toast(tr("Email verified — you can now receive sign-in codes by email"));
      close();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.emailRemove();
      await refresh();
      toast(tr("Email removed from your account"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      size="sm"
      title={tr("Email for sign-in codes")}
      subtitle={tr("Optional. Receive your one-time code by email when SMS is not convenient.")}
      footer={
        <>
          <Button variant="ghost" onClick={close}>
            {tr("Close")}
          </Button>
          {challenge ? (
            <Button onClick={confirm} loading={busy}>
              {tr("Verify email")}
            </Button>
          ) : (
            <Button onClick={send} loading={busy}>
              {tr("Send code")}
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {user?.email && (
          <div className="flex items-center justify-between gap-3 rounded-xl bg-teal-50 px-3 py-2.5 text-sm">
            <span className="flex min-w-0 items-center gap-2 text-teal-800">
              <MailCheck className="size-4 shrink-0" />
              <span className="truncate font-medium">{user.email}</span>
            </span>
            <Button size="sm" variant="ghost" onClick={remove} disabled={busy}>
              {tr("Remove")}
            </Button>
          </div>
        )}
        {!challenge ? (
          <div>
            <Label htmlFor="acct-email">{user?.email ? tr("Change to a new email") : tr("Email address")}</Label>
            <Input id="acct-email" type="email" inputMode="email" autoComplete="email" placeholder="name@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        ) : (
          <div>
            <Label>{tr("Enter the 6-digit code we emailed to {e}", { e: email.trim() })}</Label>
            <OtpBoxes value={code} onChange={setCode} autoFocus />
          </div>
        )}
        <FieldError>{err}</FieldError>
      </div>
    </Modal>
  );
}
