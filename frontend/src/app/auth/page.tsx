"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Stethoscope, HeartPulse, ClipboardList, UserRound, Briefcase, KeyRound, Smartphone, CheckCircle2, ShieldCheck, ArrowLeft, Syringe } from "lucide-react";
import { api, ApiError, getDeviceId, API_MODE } from "@/lib/api";
import { usePrefs, useSession } from "@/components/providers";
import { HOME_FOR_ROLE } from "@/components/layout/role-gate";
import { A11yButton, LanguageButton, Logo } from "@/components/layout/chrome";
import { Button, Card, FieldError, Input, Label, Select, Segmented, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { DEMO_LOGINS } from "@/lib/api/mock/seed";
import { LANGUAGES } from "@/lib/i18n/languages";
import type { Facility, OtpChallenge, Role, User } from "@/lib/types";
import { useAsync } from "@/lib/hooks";

type RegRole = Exclude<Role, "kiosk">;

const ROLE_CARDS: { role: RegRole; label: string; body: string; icon: React.ReactNode }[] = [
  { role: "doctor", label: "Doctor / Medical Officer", body: "Review triage notes, override, refer", icon: <Stethoscope /> },
  { role: "nurse", label: "Nurse / ANM", body: "Run the kiosk, record vitals, follow-ups", icon: <Syringe /> },
  { role: "receptionist", label: "Receptionist", body: "Register patients, manage kiosk devices", icon: <ClipboardList /> },
  { role: "supervisor", label: "Supervisor", body: "Facility setup, specialists, audit", icon: <ShieldCheck /> },
  { role: "patient", label: "Patient", body: "Add problems, upload reports, reminders", icon: <HeartPulse /> },
  { role: "employer", label: "Employer / HR", body: "Cohort fitness status only", icon: <Briefcase /> },
];

const CLINICAL: RegRole[] = ["doctor", "nurse"];

function OtpBoxes({ value, onChange, autoFocus }: { value: string; onChange: (v: string) => void; autoFocus?: boolean }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);
  return (
    <div className="flex gap-2" onPaste={(e) => {
      const digits = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
      if (digits) {
        e.preventDefault();
        onChange(digits);
        refs.current[Math.min(digits.length, 5)]?.focus();
      }
    }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`OTP digit ${i + 1}`}
          maxLength={1}
          value={value[i] ?? ""}
          onChange={(e) => {
            const d = e.target.value.replace(/\D/g, "").slice(-1);
            const arr = value.padEnd(6, " ").split("");
            arr[i] = d || " ";
            onChange(arr.join("").trimEnd());
            if (d && i < 5) refs.current[i + 1]?.focus();
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !value[i] && i > 0) refs.current[i - 1]?.focus();
          }}
          className="h-13 w-11 rounded-xl border border-line bg-white text-center text-xl font-bold text-ink focus:border-teal-600 focus:ring-4 focus:ring-teal-100 focus:outline-none sm:w-12"
        />
      ))}
    </div>
  );
}

function AuthInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { t, lang } = usePrefs();
  const { signIn, user } = useSession();
  const [mode, setMode] = useState<"signin" | "register">(params.get("mode") === "register" ? "register" : "signin");
  const next = params.get("next");

  const go = (u: User) => router.replace(next && next.startsWith("/") ? next : HOME_FOR_ROLE[u.role]);

  /* ── Sign-in state ── */
  const [method, setMethod] = useState<"otp" | "pin">("otp");
  const [phone, setPhone] = useState("");
  const [challenge, setChallenge] = useState<OtpChallenge | null>(null);
  const [otp, setOtp] = useState("");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pinStep, setPinStep] = useState<User | null>(null);
  const [newPin, setNewPin] = useState("");
  const [countdown, setCountdown] = useState(0);

  /* ── Registration state ── */
  const [step, setStep] = useState(1);
  const [role, setRole] = useState<RegRole | null>(null);
  const [name, setName] = useState("");
  const [facilityId, setFacilityId] = useState("");
  const [regNo, setRegNo] = useState("");
  const [prefLang, setPrefLang] = useState(lang);
  const [regToken, setRegToken] = useState<string | null>(null);
  const [terms, setTerms] = useState(false);
  const { data: facilities } = useAsync<Facility[]>(() => api.listFacilities(), []);

  useEffect(() => {
    if (user && !pinStep) go(user);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    if (countdown <= 0) return;
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [countdown]);

  const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Something went wrong");

  async function sendOtp() {
    setErr(null);
    if (!/^\d{10}$/.test(phone)) return setErr("Enter a valid 10-digit mobile number");
    setBusy(true);
    try {
      const c = await api.requestOtp(phone);
      setChallenge(c);
      setOtp("");
      setCountdown(30);
      toast(c.dev_code ? `OTP sent. Demo code: ${c.dev_code}` : `OTP sent to +91 ${phone}`, "info");
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function verifySignIn() {
    if (!challenge) return;
    setErr(null);
    if (otp.length !== 6) return setErr("Enter all 6 digits");
    setBusy(true);
    try {
      const r = await api.verifyOtp(challenge.challenge_id, otp);
      if (r.status === "new_user") {
        setRegToken(r.registration_token);
        setMode("register");
        setStep(1);
        toast("Phone verified. This number is new — please register.", "info");
        return;
      }
      if (!r.user.has_pin) {
        setPinStep(r.user);
        signIn(r.tokens, r.user);
        return;
      }
      signIn(r.tokens, r.user);
      toast(`Welcome, ${r.user.name}`);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function pinLogin() {
    setErr(null);
    if (!/^\d{10}$/.test(phone)) return setErr("Enter a valid 10-digit mobile number");
    if (!/^\d{4,6}$/.test(pin)) return setErr("PIN is 4–6 digits");
    setBusy(true);
    try {
      const r = await api.loginWithPin(phone, pin, getDeviceId());
      signIn(r.tokens, r.user);
      toast(`Welcome back, ${r.user.name}`);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function savePin() {
    if (!pinStep) return;
    setErr(null);
    if (!/^\d{4,6}$/.test(newPin)) return setErr("PIN must be 4–6 digits");
    setBusy(true);
    try {
      await api.setPin(newPin, getDeviceId());
      toast("PIN set for this device");
      go(pinStep);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function register() {
    if (!regToken || !role) return;
    setErr(null);
    if (!terms) return setErr("Please accept the terms to continue");
    setBusy(true);
    try {
      const r = await api.register({
        registration_token: regToken,
        name: role === "doctor" && !/^dr\.?\s/i.test(name) ? `Dr. ${name}` : name,
        role,
        facility_id: role === "patient" ? null : facilityId || null,
        registration_no: regNo || null,
        language: prefLang,
        accepted_terms: true,
        device_id: getDeviceId(),
      });
      signIn(r.tokens, r.user);
      setPinStep(r.user);
      toast("Registration complete");
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  const regSteps = ["User type", "Personal info", "Phone", "OTP", "Terms"];

  /* ── PIN setup (after first OTP login / registration) ── */
  if (pinStep) {
    return (
      <Card className="p-6">
        <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-teal-50 text-teal-700">
          <KeyRound className="size-6" />
        </div>
        <h2 className="text-xl font-bold text-ink">Set a PIN for this device</h2>
        <p className="mt-1 text-sm text-muted">Next time, sign in with your phone and PIN on this device — no OTP needed. The PIN only works on this device.</p>
        <div className="mt-5">
          <Label htmlFor="new-pin">4–6 digit PIN</Label>
          <Input id="new-pin" type="password" inputMode="numeric" maxLength={6} value={newPin} onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ""))} className="tracking-[0.5em]" />
          <FieldError>{err}</FieldError>
        </div>
        <div className="mt-5 flex gap-2">
          <Button onClick={savePin} loading={busy} className="flex-1" size="lg">
            Save PIN
          </Button>
          <Button variant="ghost" size="lg" onClick={() => go(pinStep)}>
            {t("common.skip")}
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-line p-2">
        <Segmented
          className="w-full [&>button]:flex-1"
          value={mode}
          onChange={(m) => {
            setMode(m);
            setErr(null);
          }}
          options={[
            { value: "signin", label: t("auth.signin") },
            { value: "register", label: t("auth.register") },
          ]}
        />
      </div>

      {mode === "signin" ? (
        <div className="p-6">
          <h2 className="text-xl font-bold text-ink">Welcome back</h2>
          <p className="mt-1 text-sm text-muted">Sign in with your mobile number.</p>

          <div className="mt-4 flex gap-2">
            {(["otp", "pin"] as const).map((m) => (
              <button key={m} onClick={() => { setMethod(m); setErr(null); }} className={cx("flex flex-1 items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium", method === m ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-muted")}>
                {m === "otp" ? <Smartphone className="size-4" /> : <KeyRound className="size-4" />}
                {m === "otp" ? "OTP" : "PIN (this device)"}
              </button>
            ))}
          </div>

          <div className="mt-5">
            <Label htmlFor="phone">{t("auth.phone")}</Label>
            <div className="flex gap-2">
              <span className="inline-flex h-11 items-center rounded-xl border border-line bg-canvas px-3 text-sm font-medium text-muted">+91</span>
              <Input id="phone" inputMode="numeric" autoComplete="tel-national" placeholder="98765 43210" value={phone} onChange={(e) => { setPhone(e.target.value.replace(/\D/g, "").slice(0, 10)); setChallenge(null); }} />
            </div>
          </div>

          {method === "otp" ? (
            challenge ? (
              <div className="mt-5">
                <Label>{t("auth.otp")}</Label>
                <OtpBoxes value={otp} onChange={setOtp} autoFocus />
                <p className="mt-2 text-xs text-muted">
                  {countdown > 0 ? `Resend in ${countdown}s` : <button className="font-semibold text-teal-700" onClick={sendOtp}>Resend OTP</button>}
                  {challenge.dev_code && <span className="ml-2 rounded bg-teal-50 px-1.5 py-0.5 font-mono text-teal-800">demo code {challenge.dev_code}</span>}
                </p>
                <FieldError>{err}</FieldError>
                <Button className="mt-5 w-full" size="lg" onClick={verifySignIn} loading={busy}>
                  {t("auth.verify")} & {t("auth.signin")}
                </Button>
              </div>
            ) : (
              <>
                <FieldError>{err}</FieldError>
                <Button className="mt-5 w-full" size="lg" onClick={sendOtp} loading={busy}>
                  {t("auth.sendOtp")}
                </Button>
              </>
            )
          ) : (
            <div className="mt-4">
              <Label htmlFor="pin">PIN</Label>
              <Input id="pin" type="password" inputMode="numeric" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} className="tracking-[0.5em]" />
              <p className="mt-1.5 text-xs text-muted">PINs are bound to the device they were created on.</p>
              <FieldError>{err}</FieldError>
              <Button className="mt-5 w-full" size="lg" onClick={pinLogin} loading={busy}>
                {t("auth.signin")}
              </Button>
            </div>
          )}

          {API_MODE === "mock" && (
            <div className="mt-6 rounded-xl border border-dashed border-teal-300 bg-teal-50/60 p-3">
              <p className="text-xs font-semibold text-teal-800">Demo accounts (synthetic) — OTP is always 123456</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {DEMO_LOGINS.map((d) => (
                  <button key={d.phone} onClick={() => { setPhone(d.phone); setMethod("otp"); setChallenge(null); }} className="rounded-full border border-teal-200 bg-white px-2.5 py-1 text-xs font-medium text-teal-800 hover:bg-teal-100">
                    {d.role}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-6">
          <ol className="mb-5 flex items-center gap-1.5" aria-label="Registration progress">
            {regSteps.map((s, i) => (
              <li key={s} className="flex flex-1 flex-col gap-1">
                <span className={cx("h-1.5 rounded-full", i + 1 < step ? "bg-teal-600" : i + 1 === step ? "bg-coral-500" : "bg-line")} />
                <span className={cx("hidden text-[11px] sm:block", i + 1 === step ? "font-semibold text-ink" : "text-subtle")}>{s}</span>
              </li>
            ))}
          </ol>

          {step === 1 && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">{t("auth.userType")}</h2>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {ROLE_CARDS.map((c) => (
                  <button key={c.role} onClick={() => setRole(c.role)} aria-pressed={role === c.role} className={cx("flex items-start gap-3 rounded-xl border p-3 text-left transition-colors", role === c.role ? "border-teal-600 bg-teal-50" : "border-line hover:bg-canvas")}>
                    <span className={cx("mt-0.5 [&>svg]:size-5", role === c.role ? "text-teal-700" : "text-muted")}>{c.icon}</span>
                    <span>
                      <span className="block text-sm font-semibold text-ink">{c.label}</span>
                      <span className="block text-xs text-muted">{c.body}</span>
                    </span>
                  </button>
                ))}
              </div>
              <Button className="mt-5 w-full" size="lg" disabled={!role} onClick={() => setStep(2)}>
                {t("common.next")}
              </Button>
            </div>
          )}

          {step === 2 && role && (
            <div className="fade-up space-y-4">
              <h2 className="text-xl font-bold text-ink">Personal info</h2>
              <div>
                <Label htmlFor="name">Full name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder={role === "doctor" ? "Deepa Sharma" : "Your name"} />
              </div>
              {role !== "patient" && (
                <div>
                  <Label htmlFor="facility">Facility</Label>
                  <Select id="facility" value={facilityId} onChange={(e) => setFacilityId(e.target.value)}>
                    <option value="">Select your facility</option>
                    {facilities?.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} — {f.district}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              {CLINICAL.includes(role) && (
                <div>
                  <Label htmlFor="regno" hint="(State medical / nursing council)">Registration number</Label>
                  <Input id="regno" value={regNo} onChange={(e) => setRegNo(e.target.value)} placeholder="e.g. UPMC-48921" />
                </div>
              )}
              <div>
                <Label htmlFor="plang">Preferred language</Label>
                <Select id="plang" value={prefLang} onChange={(e) => setPrefLang(e.target.value)}>
                  {LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.name} — {l.native}
                    </option>
                  ))}
                </Select>
              </div>
              <FieldError>{err}</FieldError>
              <div className="flex gap-2 pt-1">
                <Button variant="secondary" size="lg" onClick={() => setStep(1)} icon={<ArrowLeft className="size-4" />}>
                  {t("common.back")}
                </Button>
                <Button
                  className="flex-1"
                  size="lg"
                  onClick={() => {
                    setErr(null);
                    if (name.trim().length < 2) return setErr("Enter your full name");
                    if (role !== "patient" && !facilityId) return setErr("Select your facility");
                    if (CLINICAL.includes(role) && regNo.trim().length < 4) return setErr("Registration number is required for clinical staff");
                    setStep(regToken ? 5 : 3);
                  }}
                >
                  {t("common.next")}
                </Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">{t("auth.phone")}</h2>
              <p className="mt-1 text-sm text-muted">We will send a one-time code to verify it.</p>
              <div className="mt-4 flex gap-2">
                <span className="inline-flex h-11 items-center rounded-xl border border-line bg-canvas px-3 text-sm font-medium text-muted">+91</span>
                <Input inputMode="numeric" value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))} placeholder="98765 43210" />
              </div>
              <FieldError>{err}</FieldError>
              <div className="mt-5 flex gap-2">
                <Button variant="secondary" size="lg" onClick={() => setStep(2)} icon={<ArrowLeft className="size-4" />}>
                  {t("common.back")}
                </Button>
                <Button className="flex-1" size="lg" loading={busy} onClick={async () => { await sendOtp(); if (/^\d{10}$/.test(phone)) setStep(4); }}>
                  {t("auth.sendOtp")}
                </Button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">OTP verification</h2>
              <p className="mt-1 text-sm text-muted">Sent to +91 {phone.slice(0, 5)}•••••</p>
              <div className="mt-4">
                <OtpBoxes value={otp} onChange={setOtp} autoFocus />
                {challenge?.dev_code && <p className="mt-2 text-xs"><span className="rounded bg-teal-50 px-1.5 py-0.5 font-mono text-teal-800">demo code {challenge.dev_code}</span></p>}
              </div>
              <FieldError>{err}</FieldError>
              <div className="mt-5 flex gap-2">
                <Button variant="secondary" size="lg" onClick={() => setStep(3)} icon={<ArrowLeft className="size-4" />}>
                  {t("common.back")}
                </Button>
                <Button
                  className="flex-1"
                  size="lg"
                  loading={busy}
                  onClick={async () => {
                    if (!challenge) return;
                    setErr(null);
                    if (otp.length !== 6) return setErr("Enter all 6 digits");
                    setBusy(true);
                    try {
                      const r = await api.verifyOtp(challenge.challenge_id, otp);
                      if (r.status === "authenticated") {
                        toast("This number is already registered — signed you in.", "info");
                        signIn(r.tokens, r.user);
                        return;
                      }
                      setRegToken(r.registration_token);
                      setStep(5);
                    } catch (e) {
                      setErr(errMsg(e));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {t("auth.verify")}
                </Button>
              </div>
            </div>
          )}

          {step === 5 && role && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">Terms & privacy</h2>
              <div className="mt-3 max-h-52 space-y-2 overflow-y-auto rounded-xl border border-line bg-canvas p-3 text-sm text-muted">
                <p><strong className="text-ink">Educational prototype.</strong> Jeevia supports triage review. It does not diagnose, prescribe or replace a qualified professional.</p>
                <p><strong className="text-ink">Role-based access.</strong> You will only see what your role needs. Facility admins cannot read clinical notes; employers see fitness status only.</p>
                <p><strong className="text-ink">Audit.</strong> Every record you view, edit, override or export is written to an append-only audit log with your name.</p>
                <p><strong className="text-ink">Retention.</strong> Raw voice recordings and photos are deleted automatically after the retention window.</p>
                <p><strong className="text-ink">Synthetic data only.</strong> Do not enter real patient information into this prototype.</p>
              </div>
              <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3">
                <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-0.5 size-5 accent-teal-700" />
                <span className="text-sm font-medium text-ink">{t("auth.terms")}</span>
              </label>
              <div className="mt-4 rounded-xl bg-canvas p-3 text-sm">
                <p className="font-semibold text-ink">{name || "—"}</p>
                <p className="text-muted">
                  {ROLE_CARDS.find((c) => c.role === role)?.label} · +91 {phone}
                  {facilityId && ` · ${facilities?.find((f) => f.id === facilityId)?.name}`}
                </p>
              </div>
              <FieldError>{err}</FieldError>
              <div className="mt-5 flex gap-2">
                <Button variant="secondary" size="lg" onClick={() => setStep(2)} icon={<ArrowLeft className="size-4" />}>
                  {t("common.back")}
                </Button>
                <Button className="flex-1" size="lg" variant="teal" onClick={register} loading={busy} disabled={!terms} icon={<CheckCircle2 className="size-5" />}>
                  {t("auth.register")}
                </Button>
              </div>
            </div>
          )}
          {step === 1 && regToken && <p className="mt-3 text-center text-xs text-teal-700">Phone +91 {phone} already verified.</p>}
        </div>
      )}
    </Card>
  );
}

export default function AuthPage() {
  return (
    <div className="min-h-[calc(100vh-28px)] bg-[radial-gradient(70%_50%_at_100%_0%,var(--color-teal-100),transparent),radial-gradient(60%_50%_at_0%_100%,var(--color-coral-50),transparent)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Logo />
        <div className="flex gap-2">
          <LanguageButton />
          <A11yButton />
        </div>
      </div>
      <div className="mx-auto grid max-w-6xl items-start gap-10 px-4 pt-4 pb-16 lg:grid-cols-[1fr_440px]">
        <div className="hidden pt-8 lg:block">
          <h1 className="text-4xl font-extrabold tracking-tight text-ink">Secure, role-based access</h1>
          <p className="mt-3 max-w-md text-lg text-muted">Phone + OTP for first sign-in, then a device-bound PIN for speed at busy counters. Every session is logged.</p>
          <ul className="mt-8 space-y-3 text-sm text-ink-2">
            {[
              [<UserRound key="a" className="size-4" />, "Patients never see triage status — only their own visits and reminders."],
              [<ShieldCheck key="b" className="size-4" />, "JWT sessions with short expiry and refresh."],
              [<KeyRound key="c" className="size-4" />, "PIN is hashed with the device id — useless on any other device."],
            ].map(([i, s], k) => (
              <li key={k} className="flex items-start gap-3">
                <span className="mt-0.5 grid size-7 place-items-center rounded-lg bg-white text-teal-700 shadow-sm">{i}</span>
                <span className="pt-1">{s}</span>
              </li>
            ))}
          </ul>
        </div>
        <Suspense>
          <AuthInner />
        </Suspense>
      </div>
    </div>
  );
}
