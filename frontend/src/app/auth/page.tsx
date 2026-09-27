"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Stethoscope, HeartPulse, ClipboardList, UserRound, Briefcase, KeyRound, CheckCircle2, ShieldCheck, ArrowLeft, Syringe, LockKeyhole, Building2 } from "lucide-react";
import { api, ApiError, getDeviceId } from "@/lib/api";
import { usePrefs, useSession } from "@/components/providers";
import { HOME_FOR_ROLE } from "@/components/layout/role-gate";
import { SiteFooter, SiteHeader } from "@/components/site/site-chrome";
import { Button, Card, FieldError, Input, Label, Select, Segmented, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { OtpBoxes, PinInput, NewPinFields, newPinError } from "@/components/auth/fields";
import { WorkplacePicker, workplaceLabel, type Workplace } from "@/components/auth/workplace-picker";
import { DEMO_LOGINS } from "@/lib/samples";
import { SAMPLE_PIN } from "@/lib/pin";
import { LANGUAGES } from "@/lib/i18n/languages";
import { PIN_ROLES, type FacilityType, type NewOrganisationInput, type OrgKind, type OtpChallenge, type OtpVerifyResult, type Role, type User } from "@/lib/types";
import { INDIAN_STATES } from "@/lib/india";
import { localiseServerMessage } from "@/lib/i18n/phrases";

/** The walkthrough accounts work in every environment (OTP 123456, PIN 4826); hide with NEXT_PUBLIC_HIDE_SAMPLES=1. */
const SHOW_SAMPLES = process.env.NEXT_PUBLIC_HIDE_SAMPLES !== "1";

type RegRole = Exclude<Role, "kiosk">;
type PinGate = Extract<OtpVerifyResult, { pin_token: string }>;
type StepKey = "role" | "info" | "workplace" | "phone" | "otp" | "pin" | "terms";

const ROLE_CARDS: { role: RegRole; label: string; body: string; icon: React.ReactNode }[] = [
  { role: "doctor", label: "Doctor / Medical Officer", body: "Review triage notes, override, refer", icon: <Stethoscope /> },
  { role: "nurse", label: "Nurse / ANM", body: "Run the kiosk, record vitals, follow-ups", icon: <Syringe /> },
  { role: "receptionist", label: "Receptionist", body: "Register patients, manage kiosk devices", icon: <ClipboardList /> },
  { role: "supervisor", label: "Supervisor", body: "Facility setup, staff, audit", icon: <ShieldCheck /> },
  { role: "patient", label: "Patient", body: "Add problems, upload reports, reminders", icon: <HeartPulse /> },
  { role: "employer", label: "Employer / Organisation", body: "Register your company, campus or camp", icon: <Briefcase /> },
];

const STEP_LABEL: Record<StepKey, string> = { role: "User type", info: "Personal info", workplace: "Workplace", phone: "Phone", otp: "OTP", pin: "PIN", terms: "Terms" };

const CLINICAL: RegRole[] = ["doctor", "nurse"];

const ORG_KINDS: { v: OrgKind; label: string }[] = [
  { v: "company", label: "Company" },
  { v: "industrial", label: "Industrial estate / unit" },
  { v: "campus", label: "College / school campus" },
  { v: "ngo", label: "NGO / health camp organiser" },
  { v: "government_programme", label: "Government programme" },
];

const ORG_FAC_TYPES: { v: FacilityType; label: string }[] = [
  { v: "company_clinic", label: "Company clinic / OHC" },
  { v: "industrial_unit", label: "Industrial unit health centre" },
  { v: "campus", label: "Campus health centre" },
  { v: "health_camp", label: "Health camp" },
];

const EMPTY_ORG: NewOrganisationInput = { name: "", kind: "company", registration_no: "", state: "", district: "", facility: { name: "", type: "company_clinic", district: "", state: "" } };

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Something went wrong");

function PhoneField({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-2">
      <span className="inline-flex h-11 items-center rounded-xl border border-line bg-canvas px-3 text-sm font-medium text-muted">+91</span>
      <Input id={id} inputMode="numeric" autoComplete="tel-national" placeholder="98765 43210" value={value} onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 10))} />
    </div>
  );
}

/** Second factor: after the phone OTP, staff and employers enter (or create) their account PIN. */
function PinStep({ gate, onGate, onDone, onCancel }: { gate: PinGate; onGate: (g: PinGate) => void; onDone: (r: { tokens: Parameters<ReturnType<typeof useSession>["signIn"]>[0]; user: User }) => void; onCancel: () => void }) {
  const { tr } = usePrefs();
  const [pin, setPin] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [askSupervisor, setAskSupervisor] = useState(false);
  const setup = gate.status === "pin_setup_required";

  async function submit() {
    setErr(null);
    if (setup) {
      const p = newPinError(pin, confirm);
      if (p) return setErr(p);
    } else if (!/^\d{4,6}$/.test(pin)) return setErr(tr("Your PIN is 4–6 digits"));
    setBusy(true);
    try {
      onDone(setup ? await api.setupPin(gate.pin_token, pin) : await api.verifyPin(gate.pin_token, pin));
    } catch (e) {
      setErr(errMsg(e));
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  async function forgot() {
    setErr(null);
    if (!gate.can_reset_pin) return setAskSupervisor(true);
    setBusy(true);
    try {
      const r = await api.forgotPin(gate.pin_token);
      if ("pin_token" in r) {
        setPin("");
        setConfirm("");
        onGate(r);
        toast(tr("Phone verified — choose a new PIN"), "info");
      }
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-teal-50 text-teal-700">
        <LockKeyhole className="size-6" />
      </div>
      <p className="text-xs font-semibold tracking-wide text-teal-700 uppercase">{tr("Step 2 of 2 · Account PIN")}</p>
      <h2 className="mt-1 text-xl font-bold text-ink">{setup ? `Create your PIN, ${gate.name.split(" ")[0]}` : `Welcome back, ${gate.name.split(" ")[0]}`}</h2>
      <p className="mt-1 text-sm text-muted">
        {setup ? tr("Your dashboard is protected by two factors: your phone OTP and a PIN only you know. You will need it every time you sign in.") : tr("Phone verified. Enter your 4–6 digit account PIN to open your dashboard.")}
      </p>
      <div className="mt-5">
        {setup ? (
          <NewPinFields pin={pin} confirm={confirm} onPin={setPin} onConfirm={setConfirm} />
        ) : (
          <>
            <Label htmlFor="pin">{tr("Account PIN")}</Label>
            <PinInput id="pin" value={pin} onChange={setPin} autoFocus onEnter={submit} label={tr("Account PIN")} />
          </>
        )}
        <FieldError>{err}</FieldError>
      </div>
      <Button className="mt-5 w-full" size="lg" onClick={submit} loading={busy} icon={<KeyRound className="size-4" />}>
        {setup ? tr("Save PIN & continue") : tr("Unlock dashboard")}
      </Button>
      <div className="mt-3 flex items-center justify-between text-sm">
        <button onClick={onCancel} className="inline-flex items-center gap-1 font-medium text-muted hover:text-ink">
          <ArrowLeft className="size-4" /> {tr("Use another number")}
        </button>
        {!setup && (
          <button onClick={forgot} className="font-semibold text-teal-700 hover:underline">
            {tr("Forgot PIN?")}
          </button>
        )}
      </div>
      {askSupervisor && <p className="mt-3 rounded-xl bg-coral-50 p-3 text-sm text-ink-2">{tr("For your security, only your facility supervisor can reset a doctor, nurse or receptionist PIN. Ask them to open Admin → Staff → Reset PIN, then sign in again to create a new one.")}</p>}
    </Card>
  );
}

function OrganisationForm({ value, onChange }: { value: NewOrganisationInput; onChange: (o: NewOrganisationInput) => void }) {
  const { tr } = usePrefs();
  const set = (p: Partial<NewOrganisationInput>) => onChange({ ...value, ...p });
  const setFac = (p: Partial<NewOrganisationInput["facility"]>) => onChange({ ...value, facility: { ...value.facility, ...p } });
  return (
    <div className="space-y-3">
      <div>
        <Label htmlFor="org-name">{tr("Organisation name")}</Label>
        <Input id="org-name" value={value.name} onChange={(e) => set({ name: e.target.value })} placeholder={tr("e.g. Kalinga Steel Works Ltd.")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor="org-kind">{tr("Type")}</Label>
          <Select id="org-kind" value={value.kind} onChange={(e) => set({ kind: e.target.value as OrgKind })}>
            {ORG_KINDS.map((k) => (
              <option key={k.v} value={k.v}>
                {tr(k.label)}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="org-reg" hint={tr("(optional)")}>{tr("CIN / registration no.")}</Label>
          <Input id="org-reg" value={value.registration_no ?? ""} onChange={(e) => set({ registration_no: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="org-state">{tr("State")}</Label>
          <Select id="org-state" value={value.state} onChange={(e) => onChange({ ...value, state: e.target.value, facility: { ...value.facility, state: value.facility.state || e.target.value } })}>
            <option value="">{tr("Select")}</option>
            {INDIAN_STATES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="org-dist">{tr("District")}</Label>
          <Input id="org-dist" value={value.district} onChange={(e) => onChange({ ...value, district: e.target.value, facility: { ...value.facility, district: e.target.value } })} />
        </div>
      </div>
      <div className="space-y-3 rounded-xl border border-coral-200 bg-coral-50/40 p-3">
        <p className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Building2 className="size-4 text-coral-600" /> {tr("First workplace health centre")}
        </p>
        <div>
          <Label htmlFor="of-name">{tr("Name")}</Label>
          <Input id="of-name" value={value.facility.name} onChange={(e) => setFac({ name: e.target.value })} placeholder={tr("e.g. KSW Occupational Health Centre")} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="of-type">{tr("Type")}</Label>
            <Select id="of-type" value={value.facility.type} onChange={(e) => setFac({ type: e.target.value as FacilityType })}>
              {ORG_FAC_TYPES.map((k) => (
                <option key={k.v} value={k.v}>
                  {tr(k.label)}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="of-pin" hint={tr("(optional)")}>{tr("PIN code")}</Label>
            <Input id="of-pin" inputMode="numeric" value={value.facility.pincode ?? ""} onChange={(e) => setFac({ pincode: e.target.value.replace(/\D/g, "").slice(0, 6) })} />
          </div>
        </div>
        <p className="text-xs text-muted">{tr("Once registered, your doctors, nurses and workers can pick this workplace when they sign up. Add more sites later from the employer portal.")}</p>
      </div>
    </div>
  );
}

function AuthInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { t, tr, lang } = usePrefs();
  const { signIn, user } = useSession();
  const [mode, setMode] = useState<"signin" | "register">(params.get("mode") === "register" ? "register" : "signin");
  const next = params.get("next");

  const go = (u: User) => router.replace(next && next.startsWith("/") ? next : HOME_FOR_ROLE[u.role]);

  /* ── Shared phone/OTP state ── */
  const [phone, setPhone] = useState("");
  const [challenge, setChallenge] = useState<OtpChallenge | null>(null);
  const [otp, setOtp] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [gate, setGate] = useState<PinGate | null>(null);
  const [taken, setTaken] = useState(false);

  /* ── Registration state ── */
  const [stepKey, setStepKey] = useState<StepKey>("role");
  const [role, setRole] = useState<RegRole | null>(null);
  const [name, setName] = useState("");
  const [regNo, setRegNo] = useState("");
  const [prefLang, setPrefLang] = useState(lang);
  const [regToken, setRegToken] = useState<string | null>(null);
  const [terms, setTerms] = useState(false);
  const [workplace, setWorkplace] = useState<Workplace>(null);
  const [org, setOrg] = useState<NewOrganisationInput>(EMPTY_ORG);
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");

  const steps = useMemo<StepKey[]>(() => {
    const s: StepKey[] = ["role", "info"];
    if (role && role !== "patient") s.push("workplace");
    s.push("phone", "otp");
    if (role && PIN_ROLES.includes(role)) s.push("pin");
    s.push("terms");
    return s;
  }, [role]);
  const stepIdx = steps.indexOf(stepKey);
  const nextStep = () => {
    let i = stepIdx + 1;
    while (regToken && (steps[i] === "phone" || steps[i] === "otp")) i++;
    setErr(null);
    setStepKey(steps[i]);
  };
  const prevStep = () => {
    let i = stepIdx - 1;
    while (regToken && (steps[i] === "phone" || steps[i] === "otp")) i--;
    setErr(null);
    setStepKey(steps[Math.max(0, i)]);
  };

  useEffect(() => {
    if (user) go(user);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    if (countdown <= 0) return;
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [countdown]);

  async function sendOtp(): Promise<boolean> {
    setErr(null);
    if (!/^\d{10}$/.test(phone)) {
      setErr(tr("Enter a valid 10-digit mobile number"));
      return false;
    }
    setBusy(true);
    try {
      const c = await api.requestOtp(phone);
      setChallenge(c);
      setOtp("");
      setCountdown(30);
      toast(c.dev_code ? `OTP sent. Demo code: ${c.dev_code}` : `OTP sent to +91 ${phone}`, "info");
      return true;
    } catch (e) {
      setErr(localiseServerMessage(errMsg(e), tr));
      return false;
    } finally {
      setBusy(false);
    }
  }

  /** Verify the OTP; returns the result for the caller to route. */
  async function verify(purpose: "signin" | "register" = "signin"): Promise<OtpVerifyResult | null> {
    if (!challenge) return null;
    setErr(null);
    if (otp.length !== 6) {
      setErr(tr("Enter all 6 digits"));
      return null;
    }
    setBusy(true);
    try {
      return await api.verifyOtp(challenge.challenge_id, otp, purpose);
    } catch (e) {
      setErr(localiseServerMessage(errMsg(e), tr));
      setTaken(purpose === "register" && e instanceof ApiError && e.status === 409);
      return null;
    } finally {
      setBusy(false);
    }
  }

  function routeExisting(r: OtpVerifyResult) {
    if (r.status === "authenticated") {
      signIn(r.tokens, r.user);
      toast(`Welcome, ${r.user.name}`);
    } else if (r.status === "pin_required" || r.status === "pin_setup_required") {
      setGate(r);
    }
  }

  async function verifySignIn() {
    const r = await verify();
    if (!r) return;
    if (r.status === "new_user") {
      setRegToken(r.registration_token);
      setMode("register");
      setStepKey("role");
      toast(tr("Phone verified. This number is new — please register."), "info");
      return;
    }
    routeExisting(r);
  }

  function validateWorkplace(): string | null {
    if (role === "employer") {
      if (org.name.trim().length < 3) return "Enter your organisation’s name";
      if (!org.state || org.district.trim().length < 2) return "Select the state and enter the district";
      if (org.facility.name.trim().length < 3) return "Name your first workplace health centre";
      return null;
    }
    if (!workplace) return "Search and select your workplace";
    if (workplace.kind === "new") {
      const f = workplace.facility;
      if (f.name.trim().length < 3 || !f.state || f.district.trim().length < 2) return "Enter the facility name, state and district";
    }
    return null;
  }

  async function register() {
    if (!regToken || !role) return;
    setErr(null);
    if (!terms) return setErr(tr("Please accept the terms to continue"));
    setBusy(true);
    try {
      const r = await api.register({
        registration_token: regToken,
        name: role === "doctor" && !/^dr\.?\s/i.test(name) ? `Dr. ${name.trim()}` : name.trim(),
        role,
        facility_id: workplace?.kind === "existing" && role !== "employer" ? workplace.facility_id : null,
        directory_ref: workplace?.kind === "directory" && role !== "employer" ? workplace.directory_ref : null,
        new_facility: workplace?.kind === "new" && role === "supervisor" ? workplace.facility : null,
        new_organisation: role === "employer" ? { ...org, registration_no: org.registration_no || null, facility: { ...org.facility, state: org.facility.state || org.state, district: org.facility.district || org.district } } : null,
        registration_no: regNo || null,
        pin: PIN_ROLES.includes(role) ? newPin : null,
        language: prefLang,
        accepted_terms: true,
        device_id: getDeviceId(),
      });
      signIn(r.tokens, r.user);
      toast(tr("Registration complete"));
    } catch (e) {
      setErr(localiseServerMessage(errMsg(e), tr));
    } finally {
      setBusy(false);
    }
  }

  if (gate) {
    return (
      <PinStep
        gate={gate}
        onGate={setGate}
        onDone={(r) => {
          signIn(r.tokens, r.user);
          toast(`Welcome, ${r.user.name}`);
        }}
        onCancel={() => {
          setGate(null);
          setChallenge(null);
          setOtp("");
          setMode("signin");
        }}
      />
    );
  }

  const roleLabel = ROLE_CARDS.find((c) => c.role === role)?.label;
  const back = (
    <Button variant="secondary" size="lg" onClick={prevStep} icon={<ArrowLeft className="size-4" />}>
      {t("common.back")}
    </Button>
  );

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
          <h2 className="text-xl font-bold text-ink">{tr("Welcome back")}</h2>
          <p className="mt-1 text-sm text-muted">{tr("Sign in with your mobile number. Staff and employers then enter their account PIN.")}</p>

          <div className="mt-5">
            <Label htmlFor="phone">{t("auth.phone")}</Label>
            <PhoneField
              id="phone"
              value={phone}
              onChange={(v) => {
                setPhone(v);
                setChallenge(null);
              }}
            />
          </div>

          {challenge ? (
            <div className="mt-5">
              <Label>{t("auth.otp")}</Label>
              <OtpBoxes value={otp} onChange={setOtp} autoFocus />
              <p className="mt-2 text-xs text-muted">
                {countdown > 0 ? (
                  `Resend in ${countdown}s`
                ) : (
                  <button className="font-semibold text-teal-700" onClick={sendOtp}>
                    {tr("Resend OTP")}
                  </button>
                )}
                {challenge.dev_code && <span className="ml-2 rounded bg-teal-50 px-1.5 py-0.5 font-mono text-teal-800">{tr("demo code")} {challenge.dev_code}</span>}
              </p>
              <FieldError>{err}</FieldError>
              <Button className="mt-5 w-full" size="lg" onClick={verifySignIn} loading={busy}>
                {t("auth.verify")} {tr("& continue")}
              </Button>
            </div>
          ) : (
            <>
              <FieldError>{err}</FieldError>
              <Button className="mt-5 w-full" size="lg" onClick={sendOtp} loading={busy}>
                {t("auth.sendOtp")}
              </Button>
            </>
          )}

          {SHOW_SAMPLES && (
            <div className="mt-6 rounded-xl border border-dashed border-teal-300 bg-teal-50/60 p-3">
              <p className="text-xs font-semibold text-teal-800">
                {tr("Sample accounts — OTP 123456 · staff PIN")} {SAMPLE_PIN}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {DEMO_LOGINS.map((d) => (
                  <button
                    key={d.phone}
                    onClick={() => {
                      setPhone(d.phone);
                      setChallenge(null);
                    }}
                    className="rounded-full border border-teal-200 bg-white px-2.5 py-1 text-xs font-medium text-teal-800 hover:bg-teal-100"
                  >
                    {d.role}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-6">
          <ol className="mb-5 flex items-center gap-1.5" aria-label={tr("Registration progress")}>
            {steps.map((s, i) => (
              <li key={s} className="flex flex-1 flex-col gap-1">
                <span className={cx("h-1.5 rounded-full", i < stepIdx ? "bg-teal-600" : i === stepIdx ? "bg-coral-500" : "bg-line")} />
                <span className={cx("hidden text-[11px] sm:block", i === stepIdx ? "font-semibold text-ink" : "text-subtle")}>{STEP_LABEL[s]}</span>
              </li>
            ))}
          </ol>

          {stepKey === "role" && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">{t("auth.userType")}</h2>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {ROLE_CARDS.map((c) => (
                  <button key={c.role} onClick={() => setRole(c.role)} aria-pressed={role === c.role} className={cx("flex items-start gap-3 rounded-xl border p-3 text-left transition-colors", role === c.role ? "border-teal-600 bg-teal-50" : "border-line hover:bg-canvas")}>
                    <span className={cx("mt-0.5 [&>svg]:size-5", role === c.role ? "text-teal-700" : "text-muted")}>{c.icon}</span>
                    <span>
                      <span className="block text-sm font-semibold text-ink">{tr(c.label)}</span>
                      <span className="block text-xs text-muted">{tr(c.body)}</span>
                    </span>
                  </button>
                ))}
              </div>
              <Button className="mt-5 w-full" size="lg" disabled={!role} onClick={nextStep}>
                {t("common.next")}
              </Button>
              {regToken && <p className="mt-3 text-center text-xs text-teal-700">{tr("Phone +91")} {phone} {tr("already verified.")}</p>}
            </div>
          )}

          {stepKey === "info" && role && (
            <div className="fade-up space-y-4">
              <h2 className="text-xl font-bold text-ink">{tr("Personal info")}</h2>
              <div>
                <Label htmlFor="name">{role === "employer" ? tr("Your full name (HR / admin contact)") : tr("Full name")}</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder={role === "doctor" ? tr("Deepa Sharma") : tr("Your name")} />
              </div>
              {CLINICAL.includes(role) && (
                <div>
                  <Label htmlFor="regno" hint={tr("(State medical / nursing council)")}>{tr("Registration number")}</Label>
                  <Input id="regno" value={regNo} onChange={(e) => setRegNo(e.target.value)} placeholder={tr("e.g. UPMC-48921")} />
                </div>
              )}
              <div>
                <Label htmlFor="plang">{tr("Preferred language")}</Label>
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
                {back}
                <Button
                  className="flex-1"
                  size="lg"
                  onClick={() => {
                    setErr(null);
                    if (name.trim().length < 2) return setErr(tr("Enter your full name"));
                    if (CLINICAL.includes(role) && regNo.trim().length < 4) return setErr(tr("Registration number is required for clinical staff"));
                    nextStep();
                  }}
                >
                  {t("common.next")}
                </Button>
              </div>
            </div>
          )}

          {stepKey === "workplace" && role && (
            <div className="fade-up space-y-4">
              <div>
                <h2 className="text-xl font-bold text-ink">{role === "employer" ? tr("Register your organisation") : tr("Where do you work?")}</h2>
                <p className="mt-1 text-sm text-muted">{role === "employer" ? tr("Company clinics, industrial units, campuses and health camps are listed on Jeevia only after their organisation registers.") : tr("Search any health facility in India by name, district or PIN code.")}</p>
              </div>
              {role === "employer" ? <OrganisationForm value={org} onChange={setOrg} /> : <WorkplacePicker role={role} value={workplace} onChange={setWorkplace} />}
              <FieldError>{err}</FieldError>
              <div className="flex gap-2 pt-1">
                {back}
                <Button
                  className="flex-1"
                  size="lg"
                  onClick={() => {
                    const p = validateWorkplace();
                    if (p) return setErr(p);
                    nextStep();
                  }}
                >
                  {t("common.next")}
                </Button>
              </div>
            </div>
          )}

          {stepKey === "phone" && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">{t("auth.phone")}</h2>
              <p className="mt-1 text-sm text-muted">{tr("We will send a one-time code to verify it.")}</p>
              <div className="mt-4">
                <PhoneField id="reg-phone" value={phone} onChange={setPhone} />
              </div>
              <FieldError>{err}</FieldError>
              <div className="mt-5 flex gap-2">
                {back}
                <Button className="flex-1" size="lg" loading={busy} onClick={async () => (await sendOtp()) && setStepKey("otp")}>
                  {t("auth.sendOtp")}
                </Button>
              </div>
            </div>
          )}

          {stepKey === "otp" && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">{tr("OTP verification")}</h2>
              <p className="mt-1 text-sm text-muted">{tr("Sent to +91")} {phone.slice(0, 5)}•••••</p>
              <div className="mt-4">
                <OtpBoxes value={otp} onChange={setOtp} autoFocus />
                {challenge?.dev_code && (
                  <p className="mt-2 text-xs">
                    <span className="rounded bg-teal-50 px-1.5 py-0.5 font-mono text-teal-800">{tr("demo code")} {challenge.dev_code}</span>
                  </p>
                )}
              </div>
              <FieldError>{err}</FieldError>
              {taken && (
                <Button
                  variant="secondary"
                  className="mt-3 w-full"
                  onClick={() => {
                    setTaken(false);
                    setErr(null);
                    setChallenge(null);
                    setOtp("");
                    setMode("signin");
                  }}
                >
                  {tr("Sign in instead")}
                </Button>
              )}
              <div className="mt-5 flex gap-2">
                {back}
                <Button
                  className="flex-1"
                  size="lg"
                  loading={busy}
                  onClick={async () => {
                    const r = await verify("register");
                    if (r?.status === "new_user") {
                      setRegToken(r.registration_token);
                      setErr(null);
                      setStepKey(steps[stepIdx + 1]);
                    }
                  }}
                >
                  {t("auth.verify")}
                </Button>
              </div>
            </div>
          )}

          {stepKey === "pin" && (
            <div className="fade-up">
              <div className="mb-3 grid size-11 place-items-center rounded-2xl bg-teal-50 text-teal-700">
                <LockKeyhole className="size-5" />
              </div>
              <h2 className="text-xl font-bold text-ink">{tr("Create your account PIN")}</h2>
              <p className="mt-1 mb-4 text-sm text-muted">{tr("Signing in to your dashboard will need both an OTP on this phone and this PIN. You can change it later from your dashboard.")}</p>
              <NewPinFields pin={newPin} confirm={confirmPin} onPin={setNewPin} onConfirm={setConfirmPin} />
              <FieldError>{err}</FieldError>
              <div className="mt-5 flex gap-2">
                {back}
                <Button
                  className="flex-1"
                  size="lg"
                  onClick={() => {
                    const p = newPinError(newPin, confirmPin);
                    if (p) return setErr(p);
                    nextStep();
                  }}
                >
                  {t("common.next")}
                </Button>
              </div>
            </div>
          )}

          {stepKey === "terms" && role && (
            <div className="fade-up">
              <h2 className="text-xl font-bold text-ink">{tr("Terms & privacy")}</h2>
              <div className="mt-3 max-h-52 space-y-2 overflow-y-auto rounded-xl border border-line bg-canvas p-3 text-sm text-muted">
                <p><strong className="text-ink">{tr("Triage support, not diagnosis.")}</strong> {tr("Jeevia supports triage review. It does not diagnose, prescribe or replace a qualified professional.")}</p>
                <p><strong className="text-ink">{tr("Role-based access.")}</strong> {tr("You only see what your role needs. Patient documents and photos open only for the doctors and nurses treating that patient. Employers see fitness status only.")}</p>
                <p><strong className="text-ink">{tr("Two-factor sign-in.")}</strong> {tr("Staff and employer dashboards need a phone OTP and your account PIN. Never share your PIN.")}</p>
                <p><strong className="text-ink">{tr("Audit.")}</strong> {tr("Every record you view, edit, override or export is written to an append-only audit log with your name.")}</p>
                <p><strong className="text-ink">{tr("Retention.")}</strong> {tr("Raw voice recordings and photos are deleted automatically after the retention window.")}</p>
              </div>
              <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3">
                <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-0.5 size-5 accent-teal-700" />
                <span className="text-sm font-medium text-ink">{t("auth.terms")}</span>
              </label>
              <div className="mt-4 rounded-xl bg-canvas p-3 text-sm">
                <p className="font-semibold text-ink">{name || "—"}</p>
                <p className="text-muted">
                  {roleLabel} · +91 {phone}
                  {role === "employer" ? ` · ${org.name}` : workplace ? ` · ${workplaceLabel(workplace)}` : ""}
                  {PIN_ROLES.includes(role) && tr(" · PIN set")}
                </p>
              </div>
              <FieldError>{err}</FieldError>
              <div className="mt-5 flex gap-2">
                {back}
                <Button className="flex-1" size="lg" variant="teal" onClick={register} loading={busy} disabled={!terms} icon={<CheckCircle2 className="size-5" />}>
                  {t("auth.register")}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default function AuthPage() {
  const { tr } = usePrefs();
  return (
    <div className="min-h-[calc(100vh-28px)] bg-[radial-gradient(60%_50%_at_100%_0%,var(--color-teal-100),transparent),radial-gradient(60%_50%_at_0%_100%,var(--color-coral-50),transparent)]">
      <SiteHeader />
      <div className="mx-auto grid max-w-6xl items-start gap-10 px-4 pt-8 pb-20 sm:px-6 lg:grid-cols-[1fr_460px]">
        <div className="hidden pt-8 lg:block">
          <h1 className="text-4xl leading-tight font-extrabold tracking-tight text-ink">
            {tr("Secure,")} <span className="text-gradient">{tr("role-based")}</span> {tr("access")}
          </h1>
          <p className="mt-3 max-w-md text-lg text-muted">{tr("Phone OTP plus a personal PIN for every staff and employer dashboard. Every session is logged.")}</p>
          <ul className="mt-8 space-y-3 text-sm text-ink-2">
            {[
              [<UserRound key="a" className="size-4" />, "Patients never see triage status — only their own visits and reminders."],
              [<LockKeyhole key="b" className="size-4" />, "Two-factor sign-in: the OTP proves your phone, the PIN proves it’s you."],
              [<ShieldCheck key="c" className="size-4" />, "Patient documents open only for the doctors and nurses treating them."],
              [<Building2 key="d" className="size-4" />, "Every health facility in India, plus company and campus clinics registered by their organisation."],
            ].map(([i, s], k) => (
              <li key={k} className="flex items-start gap-3">
                <span className="mt-0.5 grid size-8 place-items-center rounded-xl bg-white text-coral-500 shadow-sm">{i}</span>
                <span className="pt-1.5">{s}</span>
              </li>
            ))}
          </ul>
        </div>
        <Suspense>
          <AuthInner />
        </Suspense>
      </div>
      <SiteFooter />
    </div>
  );
}
