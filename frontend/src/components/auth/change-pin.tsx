"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button, FieldError, Label, Modal } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { NewPinFields, PinInput, newPinError } from "./fields";

/** Dashboard "Change PIN" — needs the current PIN, then a new one twice. */
export function ChangePinModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [current, setCurrent] = useState("");
  const [pin, setPin] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setCurrent("");
    setPin("");
    setConfirm("");
    setErr(null);
    onClose();
  };

  async function save() {
    setErr(null);
    if (!/^\d{4,6}$/.test(current)) return setErr("Enter your current PIN");
    const p = newPinError(pin, confirm) ?? (pin === current ? "Choose a different PIN" : null);
    if (p) return setErr(p);
    setBusy(true);
    try {
      await api.changePin(current, pin);
      toast("PIN changed. Use the new PIN next time you sign in.");
      close();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not change PIN");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      size="sm"
      title="Change account PIN"
      subtitle="Your PIN is the second factor after the phone OTP."
      footer={
        <>
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button onClick={save} loading={busy}>
            Save new PIN
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="cur-pin">Current PIN</Label>
          <PinInput id="cur-pin" value={current} onChange={setCurrent} label="Current PIN" />
        </div>
        <NewPinFields pin={pin} confirm={confirm} onPin={setPin} onConfirm={setConfirm} />
        <FieldError>{err}</FieldError>
      </div>
    </Modal>
  );
}
