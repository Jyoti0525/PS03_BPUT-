"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  Mic, Square, Volume2, Check, RotateCcw, Camera, FileText, UserRound, Users, Lock, Eye, HandHeart, Stethoscope, Baby, HeartPulse, ArrowLeft, ArrowRight,
  Search, UserPlus, WifiOff, Trash2, Keyboard, CheckCircle2, Activity,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { usePrefs } from "@/components/providers";
import { Button, Card, FieldError, Input, Label, Select, Textarea, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { canRecognise, hasVoice, speak, startCapture, stopSpeaking, type Recorder } from "@/lib/speech";
import { enqueue } from "@/lib/offline/outbox";
import { compressImage } from "@/lib/image";
import { SAMPLE_FACILITY_ID, SAMPLE_REPORTS, sampleReportImage } from "@/lib/sample-reports";
import { API_MODE } from "@/lib/api";
import { langByCode } from "@/lib/i18n/languages";
import type { DictKey } from "@/lib/i18n/dict";
import type { ConsentMode, FileObject, IntakeAnswer, Patient, PatientCandidate, PatientCategory, PrivacyContext, SymptomEntry, VitalsInput } from "@/lib/types";
import { DURATIONS, SEVERITIES, SYMPTOMS, contextQuestions } from "./catalog";

type Step = "consent" | "identity" | "visit" | "symptoms" | "details" | "uploads" | "followup" | "vitals" | "review";

const DEMO_SPEECH: Record<string, string> = {
  en: "I have had fever for four days with body ache and headache",
  hi: "मुझे चार दिन से बुखार है, बदन दर्द और सिरदर्द भी है",
  or: "ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର, ଦେହ ବିନ୍ଧା ଓ ମୁଣ୍ଡ ବିନ୍ଧା",
};
/** Working-language rendering of the demo phrases (translation normally happens server-side via IndicTrans2). */
const DEMO_TRANSLATION = "I have had fever for four days with body ache and headache";

export interface IntakeResult {
  token: string;
  patientCode: string | null;
  offline: boolean;
}

function BigChoice({ selected, onClick, icon, title, body, className }: { selected: boolean; onClick: () => void; icon: React.ReactNode; title: string; body?: string; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cx(
        "flex min-h-20 items-center gap-4 rounded-2xl border-2 p-4 text-left transition-colors",
        selected ? "border-teal-600 bg-teal-50" : "border-line bg-white hover:border-teal-200",
        className,
      )}
    >
      <span className={cx("grid size-12 shrink-0 place-items-center rounded-xl iconmode:size-16 [&>svg]:size-6 iconmode:[&>svg]:size-9", selected ? "bg-teal-600 text-white" : "bg-canvas text-ink-2")}>{icon}</span>
      <span className="min-w-0">
        <span className="block text-lg font-semibold text-ink">{title}</span>
        {body && <span className="block text-sm text-muted iconmode:hidden">{body}</span>}
      </span>
      {selected && <Check className="ml-auto size-6 shrink-0 text-teal-700" />}
    </button>
  );
}

export function IntakeFlow({
  mode,
  facilityId,
  fixedPatient,
  offline,
  onFinished,
  onReset,
  organisationName,
}: {
  /** kiosk = staff-unlocked tablet · link = public kiosk link (/k/CODE) · patient = patient's own account */
  mode: "kiosk" | "patient" | "link";
  facilityId: string;
  fixedPatient?: Patient | null;
  offline: boolean;
  onFinished?: (r: IntakeResult) => void;
  /** Start a fresh intake (next patient) without reloading, so kiosk state such as offline mode survives. */
  onReset?: () => void;
  /** Set when the facility is an organisation's workplace (company clinic, campus…): asks for the employee / student ID. */
  organisationName?: string | null;
}) {
  const { tr, t, lang, readAloud } = usePrefs();
  const [voiceOk, setVoiceOk] = useState(true);
  useEffect(() => {
    // Voices load asynchronously; check now and again once the list arrives.
    const check = () => setVoiceOk(hasVoice(lang));
    const id = setTimeout(check, 600);
    window.speechSynthesis?.addEventListener?.("voiceschanged", check);
    return () => {
      clearTimeout(id);
      window.speechSynthesis?.removeEventListener?.("voiceschanged", check);
    };
  }, [lang]);
  const steps: Step[] = useMemo(
    () =>
      mode === "kiosk"
        ? ["consent", "identity", "visit", "symptoms", "details", "uploads", "followup", "vitals", "review"]
        : mode === "link"
          ? ["consent", "identity", "visit", "symptoms", "details", "uploads", "followup", "review"]
          : ["consent", "visit", "symptoms", "details", "uploads", "followup", "review"],
    [mode],
  );
  const [step, setStep] = useState<Step>("consent");
  const idx = steps.indexOf(step);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IntakeResult | null>(null);
  const clientRef = useRef(`cr_${crypto.randomUUID()}`);
  const capturedAt = useRef(new Date().toISOString());

  // consent
  const [consentMode, setConsentMode] = useState<ConsentMode>("self");
  const [proxyName, setProxyName] = useState("");
  const [proxyRel, setProxyRel] = useState("");
  const [privacy, setPrivacy] = useState<PrivacyContext>(mode === "kiosk" ? "assisted" : "private");
  const [returning, setReturning] = useState({ code: "", phone: "" });
  const [agreed, setAgreed] = useState(false);

  // identity
  const [lookupPhone, setLookupPhone] = useState("");
  const [candidates, setCandidates] = useState<PatientCandidate[] | null>(null);
  const [patient, setPatient] = useState<Patient | null>(fixedPatient ?? null);
  const [newP, setNewP] = useState({ name: "", age: "", sex: "" as "" | "F" | "M" | "O", phone: "", employee_code: "" });
  const [isNew, setIsNew] = useState(false);

  // visit & symptoms
  const [category, setCategory] = useState<PatientCategory | null>(null);
  const [entries, setEntries] = useState<SymptomEntry[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [typed, setTyped] = useState("");
  const [recording, setRecording] = useState(false);
  const [partial, setPartial] = useState("");
  const [pending, setPending] = useState<{ original: string; text: string; audio: Blob | null } | null>(null);
  const recRef = useRef<Recorder | null>(null);

  // details
  const [duration, setDuration] = useState<string | null>(null);
  const [severity, setSeverity] = useState<number | null>(null);
  const [maternal, setMaternal] = useState({ gestation_weeks: "", anc_visits: "", next_checkup: "", reminder_channel: "sms" as "sms" | "voice" | "none" });
  const [chronic, setChronic] = useState({ condition: "", last_checkup: "", current_medicines: "", feeling_vs_last: "same" as "better" | "same" | "worse" | "unsure" });

  // uploads / follow-up / vitals
  const [files, setFiles] = useState<FileObject[]>([]);
  const [answers, setAnswers] = useState<Record<string, IntakeAnswer>>({});
  const [vitals, setVitals] = useState<Record<keyof VitalsInput, string>>({ bp_systolic: "", bp_diastolic: "", pulse: "", temp_f: "", spo2: "", resp_rate: "", glucose: "" });

  const age = patient?.age ?? (Number(newP.age) || 30);
  const chief = useMemo(() => {
    const first = entries[0]?.text || typed.trim();
    if (first) return first.length > 90 ? first.slice(0, 87) + "…" : first;
    if (selected.length) return selected.join(", ");
    return category === "maternal" ? "Antenatal check-up" : category === "chronic" ? `${chronic.condition || "Chronic"} follow-up` : "";
  }, [entries, typed, selected, category, chronic.condition]);

  const questions = useMemo(
    () => (category ? contextQuestions({ chief_complaint: chief, selected_symptoms: selected, category, symptoms: entries, duration }, age) : []),
    [chief, selected, category, entries, duration, age],
  );

  const STEP_TITLE: Record<Step, DictKey> = {
    consent: "kiosk.consent.title",
    identity: "kiosk.identity.title",
    visit: "kiosk.visit.title",
    symptoms: "kiosk.symptoms.title",
    details: "kiosk.duration.title",
    uploads: "kiosk.upload.title",
    followup: "kiosk.followup.title",
    vitals: "kiosk.identity.title",
    review: "kiosk.review.title",
  };

  // Shared tablets: return to the start screen a minute after the token is shown.
  useEffect(() => {
    if (!result || !onReset || mode === "patient") return;
    const id = setTimeout(onReset, 60_000);
    return () => clearTimeout(id);
  }, [result, onReset, mode]);

  useEffect(() => {
    if (readAloud && step !== "vitals") speak(step === "consent" ? `${t("kiosk.welcome")} ${t("kiosk.consent.body")}` : t(STEP_TITLE[step]), lang);
    return () => stopSpeaking();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, readAloud, lang]);

  const go = (d: 1 | -1) => {
    setErr(null);
    const next = steps[idx + d];
    if (next) setStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  /* ── validation per step ── */
  const validate = (): string | null => {
    switch (step) {
      case "consent":
        if (consentMode === "proxy" && (proxyName.trim().length < 2 || !proxyRel)) return "Enter the helper's name and relationship";
        if (!agreed) return "Consent is needed to continue";
        return null;
      case "identity":
        if (patient) return null;
        if (!isNew) return "Find the patient or register a new person";
        if (newP.name.trim().length < 2) return "Enter the patient's name";
        if (!newP.age || Number(newP.age) < 0 || Number(newP.age) > 120) return "Enter a valid age";
        if (!newP.sex) return "Choose sex";
        if (newP.phone && !/^\d{10}$/.test(newP.phone)) return "Phone must be 10 digits";
        return null;
      case "visit":
        return category ? null : "Choose the visit type";
      case "symptoms":
        if (pending) return "Confirm or re-record the voice note first";
        if (!entries.length && !typed.trim() && !selected.length && category === "normal") return "Tell us at least one problem — speak, type or tap";
        return null;
      case "details":
        if (category === "maternal" && maternal.gestation_weeks && (Number(maternal.gestation_weeks) < 1 || Number(maternal.gestation_weeks) > 42)) return "Weeks of pregnancy should be 1–42";
        if (category === "chronic" && !chronic.condition.trim()) return "Which long-term illness?";
        return null;
      default:
        return null;
    }
  };

  const next = () => {
    const e = validate();
    if (e) return setErr(e);
    go(1);
  };

  /* ── identity ── */
  const findPatient = async () => {
    setErr(null);
    if (!/^\d{10}$/.test(lookupPhone) && !/^jva-/i.test(lookupPhone)) return setErr(tr("Enter a 10-digit phone or a patient ID"));
    setBusy(true);
    try {
      const c = /^jva-/i.test(lookupPhone) ? [{ patient: await api.getPatientByCode(lookupPhone), last_visit_at: null, match_reason: "Patient ID" }] : await api.searchPatients(lookupPhone);
      setCandidates(c);
      if (!c.length) {
        setIsNew(true);
        setNewP((p) => ({ ...p, phone: /^\d{10}$/.test(lookupPhone) ? lookupPhone : "" }));
      }
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 404 ? tr("No patient with that ID") : e instanceof Error ? e.message : tr("Search failed"));
    } finally {
      setBusy(false);
    }
  };

  /* ── voice ── */
  const toggleMic = async () => {
    setErr(null);
    if (!recording) {
      setPartial("");
      stopSpeaking();
      try {
        recRef.current = await startCapture(lang, setPartial);
        setRecording(true);
      } catch {
        setErr(tr("Microphone not available — type or tap instead"));
      }
      return;
    }
    setRecording(false);
    const r = await recRef.current?.stop();
    recRef.current = null;
    let original = r?.transcript?.trim() ?? "";
    let text = original;
    if (!original) {
      // No live ASR in this browser: server-side IndicConformer would transcribe the audio.
      original = DEMO_SPEECH[lang] ?? DEMO_SPEECH.en;
      text = DEMO_TRANSLATION;
      toast(canRecognise() ? tr("Could not hear clearly — using demo transcript") : tr("Live transcription unavailable — demo transcript used"), "info");
    } else if (lang !== "en") {
      text = original; // translated server-side (IndicTrans2); raw text kept for audit
    }
    setPending({ original, text, audio: r?.audio ?? null });
    speak(`${t("kiosk.symptoms.readback")} ${original}`, lang);
  };

  const confirmVoice = async (ok: boolean) => {
    if (!pending) return;
    stopSpeaking();
    if (!ok) {
      setPending(null);
      return;
    }
    setEntries((e) => [...e, { text: pending.text, original_text: pending.original, language: lang, source: "voice", confirmed_by_readback: true }]);
    if (pending.audio && !offline) {
      try {
        const f = await api.uploadFile(new File([pending.audio], `voice_${Date.now()}.webm`, { type: pending.audio.type }), "audio");
        setFiles((cur) => [...cur, f]);
      } catch {
        /* audio is optional — transcript already captured */
      }
    }
    setPending(null);
  };

  /* ── uploads ── */
  const onPick = async (list: FileList | null, kind: "report" | "image") => {
    if (!list?.length) return;
    if (offline) return setErr(tr("Uploads need a connection — ask staff to add reports after syncing"));
    setBusy(true);
    try {
      for (const f of Array.from(list)) {
        if (f.size > 20 * 1024 * 1024) throw new Error("File too large (max 20 MB before compression)");
        const up = await api.uploadFile(await compressImage(f), kind);
        setFiles((cur) => [...cur, up]);
      }
      toast(tr("Uploaded"));
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Upload failed"));
    } finally {
      setBusy(false);
    }
  };

  const addSample = async (key: string) => {
    if (offline) return setErr(tr("Uploads need a connection"));
    setBusy(true);
    try {
      const img = sampleReportImage(key, patient?.name ?? (newP.name || "Patient"));
      const blob = await (await fetch(img.dataUrl)).blob();
      const up = await api.uploadFile(new File([blob], `${key}_sample_report.svg`, { type: "image/svg+xml" }), "report", null, key);
      setFiles((cur) => [...cur, up]);
      toast(tr("Sample report attached"));
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Upload failed"));
    } finally {
      setBusy(false);
    }
  };

  /* ── submit ── */
  const submit = async () => {
    setErr(null);
    setBusy(true);
    const num = (s: string) => (s.trim() ? Number(s) : null);
    const v: VitalsInput = {
      bp_systolic: num(vitals.bp_systolic),
      bp_diastolic: num(vitals.bp_diastolic),
      pulse: num(vitals.pulse),
      temp_f: num(vitals.temp_f),
      spo2: num(vitals.spo2),
      resp_rate: num(vitals.resp_rate),
      glucose: num(vitals.glucose),
    };
    const symptoms: SymptomEntry[] = [...entries, ...(typed.trim() ? [{ text: typed.trim(), original_text: typed.trim(), language: lang, source: "text" as const, confirmed_by_readback: false }] : [])];
    const durAnswer = answers.dur?.answer;
    const intake = {
      facility_id: facilityId,
      category: category!,
      language: lang,
      chief_complaint: chief || "General check-up",
      symptoms,
      selected_symptoms: selected,
      duration: duration ?? durAnswer ?? null,
      severity,
      answers: Object.values(answers),
      file_ids: files.map((f) => f.id),
      vitals: Object.values(v).some((x) => x != null) ? v : null,
      maternal:
        category === "maternal"
          ? { gestation_weeks: num(maternal.gestation_weeks), anc_visits: num(maternal.anc_visits), next_checkup: maternal.next_checkup || null, reminder_channel: maternal.reminder_channel }
          : null,
      chronic: category === "chronic" ? { condition: chronic.condition, last_checkup: chronic.last_checkup || null, current_medicines: chronic.current_medicines || null, feeling_vs_last: chronic.feeling_vs_last } : null,
      client_ref: clientRef.current,
      captured_at: capturedAt.current,
    };
    const consent = {
      mode: consentMode,
      proxy_name: consentMode === "proxy" ? proxyName : null,
      proxy_relation: consentMode === "proxy" ? proxyRel : null,
      privacy_context: privacy,
      language: lang,
      scopes: ["triage", "share_with_treating_team", "store_reports_until_expiry"],
    };
    const newPatient = isNew
      ? { name: newP.name.trim(), age: Number(newP.age), sex: newP.sex as "F" | "M" | "O", phone: newP.phone || null, language: lang, category: category!, village: null, employee_code: (organisationName && newP.employee_code.trim()) || null }
      : null;

    try {
      if (offline) {
        await enqueue({ client_ref: clientRef.current, new_patient: newPatient, consent, intake: { ...intake, patient_id: patient?.id ?? null } });
        const r = { token: `OFF-${clientRef.current.slice(3, 7).toUpperCase()}`, patientCode: patient?.code ?? null, offline: true };
        setResult(r);
        onFinished?.(r);
        return;
      }
      const p = patient ?? (await api.createPatient(newPatient!));
      const c = await api.captureConsent({ ...consent, patient_id: p.id });
      const enc = await api.submitIntake({ ...intake, patient_id: p.id, consent_id: c.id });
      const r = { token: enc.token ?? `A-${enc.id.slice(-3).toUpperCase()}`, patientCode: p.code, offline: false };
      setResult(r);
      onFinished?.(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Could not submit"));
    } finally {
      setBusy(false);
    }
  };

  /* ── Result (token) — never shows urgency ── */
  if (result) {
    return (
      <Card className="fade-up mx-auto max-w-xl p-8 text-center">
        <CheckCircle2 className="mx-auto size-14 text-teal-600" />
        <h2 className="mt-3 text-3xl font-bold text-ink">{t("kiosk.done.title")}</h2>
        <p className="mt-2 text-lg text-muted">{t("kiosk.done.body")}</p>
        <p className="mt-6 text-sm font-semibold tracking-wider text-muted uppercase">{t("kiosk.done.token")}</p>
        <p className="text-6xl font-extrabold tracking-tight text-ink tabular-nums">{result.token}</p>
        {result.patientCode && (
          <div className="mt-6 inline-flex flex-col items-center rounded-2xl border border-line bg-white p-4">
            <QRCodeSVG value={`jeevia:${result.patientCode}`} size={132} />
            <p className="mt-2 font-mono text-sm text-muted">{result.patientCode}</p>
          </div>
        )}
        {result.offline && (
          <p className="mt-5 flex items-center justify-center gap-2 rounded-xl bg-semi-bg px-4 py-2 text-sm font-medium text-semi">
            <WifiOff className="size-4" /> {t("kiosk.offline")}
          </p>
        )}
        <Button size="xl" className="mt-8 w-full" variant="teal" onClick={() => (onReset ? onReset() : window.location.reload())}>
          {mode === "kiosk" ? t("kiosk.done.next") : t("common.done")}
        </Button>
      </Card>
    );
  }

  const listen = (text: string) => (
    <button type="button" onClick={() => speak(text, lang)} className="inline-flex items-center gap-1 rounded-full bg-canvas px-2.5 py-1 text-xs font-semibold text-ink-2 hover:bg-line" aria-label={t("common.listen")}>
      <Volume2 className="size-3.5" /> {t("common.listen")}
    </button>
  );

  return (
    <div className="mx-auto max-w-3xl">
      {!voiceOk && (
        <p className="mb-4 flex items-start gap-2 rounded-xl border border-semi/30 bg-semi-bg px-4 py-2.5 text-sm text-ink-2">
          <Volume2 className="mt-0.5 size-4 shrink-0 text-semi" />
          {tr("This device has no {lang} voice, so questions are not read aloud. Install the {lang} voice in the device’s text-to-speech settings.", { lang: langByCode(lang).name })}
        </p>
      )}
      {/* progress */}
      <div className="mb-5 flex items-center gap-1.5" aria-label={tr("Step {n} of {m}", { n: idx + 1, m: steps.length })}>
        {steps.map((s, i) => (
          <span key={s} className={cx("h-2 flex-1 rounded-full transition-colors", i < idx ? "bg-teal-600" : i === idx ? "bg-coral-500" : "bg-line")} />
        ))}
      </div>

      <Card className="fade-up p-5 sm:p-7" key={step}>
        <div className="mb-5 flex items-start justify-between gap-3">
          <h2 className="text-2xl font-bold text-ink sm:text-3xl">{step === "vitals" ? tr("For staff: vitals") : t(STEP_TITLE[step])}</h2>
          {step !== "vitals" && listen(step === "consent" ? t("kiosk.consent.body") : t(STEP_TITLE[step]))}
        </div>

        {step === "consent" && (
          <div className="space-y-5">
            <p className="rounded-2xl bg-teal-50 p-4 text-lg leading-relaxed text-teal-800">{t("kiosk.consent.body")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <BigChoice selected={consentMode === "self"} onClick={() => setConsentMode("self")} icon={<UserRound />} title={t("kiosk.consent.self")} />
              <BigChoice selected={consentMode === "proxy"} onClick={() => setConsentMode("proxy")} icon={<Users />} title={t("kiosk.consent.proxy")} />
            </div>
            {consentMode === "proxy" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="px-name">{tr("Helper's name")}</Label>
                  <Input id="px-name" value={proxyName} onChange={(e) => setProxyName(e.target.value)} className="h-12 text-lg" />
                </div>
                <div>
                  <Label htmlFor="px-rel">{tr("Relationship")}</Label>
                  <Select id="px-rel" value={proxyRel} onChange={(e) => setProxyRel(e.target.value)} className="h-12 text-lg">
                    <option value="">{tr("Choose")}</option>
                    {["Mother", "Father", "Husband", "Wife", "Son", "Daughter", "Mother-in-law", "Other family", "ASHA worker", "Caregiver"].map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </Select>
                </div>
              </div>
            )}
            <div>
              <p className="mb-2 text-sm font-semibold text-ink-2">{t("kiosk.privacy.title")}</p>
              <div className="grid gap-2 sm:grid-cols-3">
                {(
                  [
                    ["private", "kiosk.privacy.private", <Lock key="l" />],
                    ["shared_space", "kiosk.privacy.shared", <Eye key="e" />],
                    ["assisted", "kiosk.privacy.assisted", <HandHeart key="h" />],
                  ] as const
                ).map(([v, k, icon]) => (
                  <button key={v} type="button" onClick={() => setPrivacy(v)} aria-pressed={privacy === v} className={cx("flex items-center gap-2 rounded-xl border-2 px-3 py-3 text-left text-sm font-medium", privacy === v ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-ink-2")}>
                    <span className="[&>svg]:size-5">{icon}</span> {t(k)}
                  </button>
                ))}
              </div>
              {privacy === "shared_space" && <p className="mt-2 text-sm text-semi">{tr("Sensitive questions will be asked by a health worker in private.")}</p>}
            </div>
            <label className="flex cursor-pointer items-center gap-4 rounded-2xl border-2 border-line p-4 has-checked:border-teal-600 has-checked:bg-teal-50">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="size-7 accent-teal-700" />
              <span className="text-lg font-semibold text-ink">{t("kiosk.consent.agree")}</span>
            </label>
          </div>
        )}

        {step === "identity" && (
          <div className="space-y-5">
            {patient ? (
              <div className="flex items-center gap-4 rounded-2xl border-2 border-teal-600 bg-teal-50 p-4">
                <span className="grid size-12 place-items-center rounded-xl bg-teal-600 text-lg font-bold text-white">{patient.name.charAt(0)}</span>
                <div className="flex-1">
                  <p className="text-lg font-semibold text-ink">{patient.name}</p>
                  <p className="text-sm text-muted">{patient.age} y · {patient.sex} · {patient.code}</p>
                </div>
                <Button variant="ghost" onClick={() => setPatient(null)}>{tr("Change")}</Button>
              </div>
            ) : isNew ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Label htmlFor="np-name">{t("kiosk.identity.name")}</Label>
                  <Input id="np-name" value={newP.name} onChange={(e) => setNewP({ ...newP, name: e.target.value })} className="h-13 text-lg" autoFocus />
                </div>
                <div>
                  <Label htmlFor="np-age">{t("kiosk.identity.age")}</Label>
                  <Input id="np-age" inputMode="numeric" value={newP.age} onChange={(e) => setNewP({ ...newP, age: e.target.value.replace(/\D/g, "").slice(0, 3) })} className="h-13 text-lg" />
                </div>
                <div>
                  <Label>{t("kiosk.identity.sex")}</Label>
                  <div className="grid grid-cols-3 gap-2">
                    {(["F", "M", "O"] as const).map((s) => (
                      <button key={s} type="button" onClick={() => setNewP({ ...newP, sex: s })} aria-pressed={newP.sex === s} className={cx("h-13 rounded-xl border-2 font-semibold", newP.sex === s ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-ink-2")}>
                        {t(s === "F" ? "kiosk.identity.female" : s === "M" ? "kiosk.identity.male" : "kiosk.identity.other")}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="np-phone">{t("kiosk.identity.phone")}</Label>
                  <Input id="np-phone" inputMode="numeric" value={newP.phone} onChange={(e) => setNewP({ ...newP, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} className="h-13 text-lg" />
                </div>
                {organisationName && (
                  <div className="sm:col-span-2">
                    <Label htmlFor="np-emp" hint={tr("(optional)")}>{organisationName} {tr("employee / student ID")}</Label>
                    <Input id="np-emp" value={newP.employee_code} onChange={(e) => setNewP({ ...newP, employee_code: e.target.value.toUpperCase().slice(0, 40) })} className="h-13 text-lg" placeholder={tr("e.g. KSW-1041")} />
                  </div>
                )}
                <Button variant="ghost" className="sm:col-span-2" onClick={() => { setIsNew(false); setCandidates(null); }} icon={<Search className="size-4" />} disabled={offline}>
                  {mode === "link" ? tr("I have visited before") : tr("Search existing patients instead")}
                </Button>
              </div>
            ) : mode === "link" ? (
              <div className="space-y-5">
                <Button variant="teal" size="xl" className="w-full" onClick={() => setIsNew(true)} icon={<UserPlus className="size-6" />}>
                  {tr("First visit — register")}
                </Button>
                <div className="rounded-2xl border-2 border-line p-4">
                  <p className="font-semibold text-ink">{tr("Been here before?")}</p>
                  <p className="text-sm text-muted">{tr("Enter the ID printed on your old token and your phone number.")}</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                    <Input value={returning.code} onChange={(e) => setReturning({ ...returning, code: e.target.value.toUpperCase().trim() })} placeholder={tr("JVA-P012")} aria-label={tr("Patient ID")} className="h-12 text-lg" disabled={offline} />
                    <Input value={returning.phone} inputMode="numeric" onChange={(e) => setReturning({ ...returning, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} placeholder={tr("Phone")} aria-label={tr("Phone")} className="h-12 text-lg" disabled={offline} />
                    <Button
                      size="lg"
                      className="h-12"
                      loading={busy}
                      disabled={offline}
                      onClick={async () => {
                        setErr(null);
                        if (!/^JVA-/i.test(returning.code) || !/^\d{10}$/.test(returning.phone)) return setErr(tr("Enter your Jeevia ID (JVA-…) and 10-digit phone"));
                        setBusy(true);
                        try {
                          setPatient(await api.kioskIdentify(returning.code, returning.phone));
                        } catch (e) {
                          setErr(e instanceof Error ? e.message : tr("Not found"));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      {tr("Continue")}
                    </Button>
                  </div>
                  {offline && <p className="mt-2 text-sm text-semi">{tr("Offline — register as new; records are matched when synced.")}</p>}
                </div>
              </div>
            ) : (
              <>
                <p className="text-muted">{tr("Returning? Search by phone (may be shared by family) or patient ID from an old token.")}</p>
                <div className="flex gap-2">
                  <Input value={lookupPhone} onChange={(e) => setLookupPhone(e.target.value.trim())} placeholder={tr("Phone or JVA-…")} className="h-13 text-lg" disabled={offline} />
                  <Button size="lg" className="h-13" onClick={findPatient} loading={busy} disabled={offline} icon={<Search className="size-5" />}>
                    {tr("Find")}
                  </Button>
                </div>
                {offline && <p className="text-sm text-semi">{tr("Offline — search is unavailable. Register as new; records are matched when synced.")}</p>}
                {candidates && candidates.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-ink-2">{candidates.length > 1 ? tr("Several people use this phone — who is the patient?") : tr("Is this the patient?")}</p>
                    {candidates.map((c) => (
                      <button key={c.patient.id} type="button" onClick={() => setPatient(c.patient)} className="flex w-full items-center gap-3 rounded-2xl border-2 border-line p-3 text-left hover:border-teal-300">
                        <span className="grid size-11 place-items-center rounded-xl bg-coral-100 font-bold text-coral-700">{c.patient.name.charAt(0)}</span>
                        <span className="flex-1">
                          <span className="block font-semibold text-ink">{c.patient.name}</span>
                          <span className="block text-sm text-muted">{c.patient.age} y · {c.patient.sex} · {c.patient.code}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <Button variant="secondary" size="xl" className="w-full" onClick={() => setIsNew(true)} icon={<UserPlus className="size-6" />}>
                  {tr("New patient")}
                </Button>
              </>
            )}
          </div>
        )}

        {step === "visit" && (
          <div className="grid gap-3">
            <BigChoice selected={category === "normal"} onClick={() => setCategory("normal")} icon={<Stethoscope />} title={t("kiosk.visit.normal")} body={tr("Fever, pain, injury, cough or any new problem")} />
            <BigChoice selected={category === "maternal"} onClick={() => setCategory("maternal")} icon={<Baby />} title={t("kiosk.visit.maternal")} body={tr("Antenatal visit or a problem during pregnancy")} />
            <BigChoice selected={category === "chronic"} onClick={() => setCategory("chronic")} icon={<HeartPulse />} title={t("kiosk.visit.chronic")} body={tr("Diabetes, BP, asthma/COPD, TB or other long-term illness")} />
          </div>
        )}

        {step === "symptoms" && (
          <div className="space-y-6">
            <div className="flex flex-col items-center gap-3 rounded-2xl bg-canvas p-5">
              <button
                type="button"
                onClick={toggleMic}
                disabled={!!pending}
                className={cx("grid size-28 place-items-center rounded-full text-white shadow-lg transition-transform active:scale-95 disabled:opacity-50", recording ? "recording-pulse bg-crit" : "bg-teal-700 hover:bg-teal-800")}
                aria-label={recording ? t("kiosk.symptoms.stop") : t("kiosk.symptoms.speak")}
              >
                {recording ? <Square className="size-10" /> : <Mic className="size-12" />}
              </button>
              <p className="text-lg font-semibold text-ink">{recording ? t("kiosk.symptoms.stop") : t("kiosk.symptoms.speak")}</p>
              <p className="text-sm text-muted">{langByCode(lang).native} · {canRecognise() ? tr("live transcription") : tr("recorded for server transcription")}</p>
              {recording && partial && <p className="max-w-lg text-center text-lg text-ink-2 italic">“{partial}”</p>}
            </div>

            {pending && (
              <div className="rounded-2xl border-2 border-coral-300 bg-coral-50 p-4">
                <p className="text-sm font-semibold text-coral-700">{t("kiosk.symptoms.readback")}</p>
                <p className="mt-1 text-xl font-medium text-ink">“{pending.original}”</p>
                {pending.text !== pending.original && <p className="mt-1 text-sm text-muted">→ {tr(pending.text)}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="lg" variant="teal" onClick={() => confirmVoice(true)} icon={<Check className="size-5" />}>{t("kiosk.symptoms.correct")}</Button>
                  <Button size="lg" variant="secondary" onClick={() => confirmVoice(false)} icon={<RotateCcw className="size-5" />}>{t("kiosk.symptoms.again")}</Button>
                  <Button size="lg" variant="ghost" onClick={() => speak(pending.original, lang)} icon={<Volume2 className="size-5" />}>{t("common.listen")}</Button>
                </div>
              </div>
            )}

            {entries.length > 0 && (
              <ul className="space-y-2">
                {entries.map((e, i) => (
                  <li key={i} className="flex items-start gap-3 rounded-xl border border-line bg-white p-3">
                    <Mic className="mt-1 size-4 shrink-0 text-teal-700" />
                    <span className="flex-1 text-ink">{e.original_text}</span>
                    <button type="button" onClick={() => setEntries(entries.filter((_, j) => j !== i))} className="text-subtle hover:text-crit" aria-label={tr("Remove")}>
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div>
              <p className="mb-2 text-sm font-semibold text-ink-2">{t("kiosk.symptoms.pick")}</p>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {SYMPTOMS.map((s) => {
                  const on = selected.includes(s.en);
                  return (
                    <button
                      key={s.key}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setSelected(on ? selected.filter((x) => x !== s.en) : [...selected, s.en])}
                      className={cx("flex flex-col items-center gap-1.5 rounded-2xl border-2 px-2 py-3 text-center transition-colors iconmode:py-5", on ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line bg-white text-ink-2 hover:border-teal-200")}
                    >
                      <span className="[&>svg]:size-7 iconmode:[&>svg]:size-11">{s.icon}</span>
                      <span className="text-sm leading-tight font-medium">{t(s.key)}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="iconmode:hidden">
              <Label htmlFor="typed">
                <Keyboard className="mr-1 inline size-4" /> {t("kiosk.symptoms.type")}
              </Label>
              <Textarea id="typed" rows={3} value={typed} onChange={(e) => setTyped(e.target.value)} className="text-lg" />
            </div>
          </div>
        )}

        {step === "details" && (
          <div className="space-y-6">
            <div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {DURATIONS.map((d) => (
                  <button key={d.key} type="button" onClick={() => setDuration(d.en)} aria-pressed={duration === d.en} className={cx("min-h-14 rounded-xl border-2 px-2 text-base font-semibold", duration === d.en ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-ink-2")}>
                    {t(d.key)}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-lg font-semibold text-ink">{t("kiosk.severity.title")}</p>
              <div className="grid grid-cols-4 gap-2">
                {SEVERITIES.map((s) => (
                  <button key={s.key} type="button" onClick={() => setSeverity(s.value)} aria-pressed={severity === s.value} className={cx("flex flex-col items-center gap-1 rounded-2xl border-2 py-3", severity === s.value ? "border-ink bg-canvas" : "border-line")}>
                    <span className={cx("[&>svg]:size-9 iconmode:[&>svg]:size-12", s.cls)}>{s.icon}</span>
                    <span className="text-sm font-semibold text-ink-2">{t(s.key)}</span>
                  </button>
                ))}
              </div>
            </div>

            {category === "maternal" && (
              <div className="rounded-2xl border border-coral-200 bg-coral-50/50 p-4">
                <p className="mb-3 flex items-center gap-2 font-semibold text-coral-700"><Baby className="size-5" /> {tr("Pregnancy details")}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="m-weeks">{tr("Weeks of pregnancy")}</Label>
                    <Input id="m-weeks" inputMode="numeric" value={maternal.gestation_weeks} onChange={(e) => setMaternal({ ...maternal, gestation_weeks: e.target.value.replace(/\D/g, "").slice(0, 2) })} className="h-12 text-lg" />
                  </div>
                  <div>
                    <Label htmlFor="m-anc">{tr("Check-ups done so far")}</Label>
                    <Input id="m-anc" inputMode="numeric" value={maternal.anc_visits} onChange={(e) => setMaternal({ ...maternal, anc_visits: e.target.value.replace(/\D/g, "").slice(0, 2) })} className="h-12 text-lg" />
                  </div>
                  <div>
                    <Label htmlFor="m-next">{tr("Next check-up date")}</Label>
                    <Input id="m-next" type="date" value={maternal.next_checkup} onChange={(e) => setMaternal({ ...maternal, next_checkup: e.target.value })} className="h-12" />
                  </div>
                  <div>
                    <Label htmlFor="m-rem">{tr("Remind me by")}</Label>
                    <Select id="m-rem" value={maternal.reminder_channel} onChange={(e) => setMaternal({ ...maternal, reminder_channel: e.target.value as "sms" | "voice" | "none" })} className="h-12">
                      <option value="sms">{tr("SMS")}</option>
                      <option value="voice">{tr("Voice call in my language")}</option>
                      <option value="none">{tr("No reminder")}</option>
                    </Select>
                  </div>
                </div>
              </div>
            )}

            {category === "chronic" && (
              <div className="rounded-2xl border border-teal-200 bg-teal-50/50 p-4">
                <p className="mb-3 flex items-center gap-2 font-semibold text-teal-800"><HeartPulse className="size-5" /> {tr("Long-term illness")}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="c-cond">{tr("Illness")}</Label>
                    <Select id="c-cond" value={chronic.condition} onChange={(e) => setChronic({ ...chronic, condition: e.target.value })} className="h-12">
                      <option value="">{tr("Choose")}</option>
                      {["Type 2 diabetes", "High blood pressure", "COPD / asthma", "Tuberculosis (on treatment)", "Heart disease", "Kidney disease", "Epilepsy", "Other"].map((c) => <option key={c}>{c}</option>)}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="c-last">{tr("Last check-up")}</Label>
                    <Select id="c-last" value={chronic.last_checkup} onChange={(e) => setChronic({ ...chronic, last_checkup: e.target.value })} className="h-12">
                      <option value="">{tr("Don't remember")}</option>
                      {["Less than 1 month ago", "1–3 months ago", "3–6 months ago", "More than 6 months ago"].map((c) => <option key={c}>{c}</option>)}
                    </Select>
                  </div>
                  <div className="sm:col-span-2">
                    <Label htmlFor="c-meds">{tr("Medicines you take")}</Label>
                    <Input id="c-meds" value={chronic.current_medicines} onChange={(e) => setChronic({ ...chronic, current_medicines: e.target.value })} className="h-12" placeholder={tr("Names, or 'white tablet twice a day'")} />
                  </div>
                  <div className="sm:col-span-2">
                    <Label>{tr("Compared with last time you feel")}</Label>
                    <div className="grid grid-cols-4 gap-2">
                      {(["better", "same", "worse", "unsure"] as const).map((f) => (
                        <button key={f} type="button" onClick={() => setChronic({ ...chronic, feeling_vs_last: f })} aria-pressed={chronic.feeling_vs_last === f} className={cx("h-12 rounded-xl border-2 font-semibold capitalize", chronic.feeling_vs_last === f ? "border-teal-600 bg-white text-teal-800" : "border-line text-ink-2")}>
                          {f}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {step === "uploads" && (
          <div className="space-y-5">
            <p className="text-lg text-muted">{t("kiosk.upload.body")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className={cx("flex min-h-24 cursor-pointer items-center gap-4 rounded-2xl border-2 border-dashed border-teal-300 bg-teal-50/50 p-4", offline && "pointer-events-none opacity-50")}>
                <Camera className="size-9 text-teal-700" />
                <span>
                  <span className="block text-lg font-semibold text-ink">{t("kiosk.upload.camera")}</span>
                  <span className="block text-sm text-muted">{tr("Lab report, prescription")}</span>
                </span>
                <input type="file" accept="image/*,application/pdf" capture="environment" className="sr-only" onChange={(e) => onPick(e.target.files, "report")} />
              </label>
              <label className={cx("flex min-h-24 cursor-pointer items-center gap-4 rounded-2xl border-2 border-dashed border-coral-300 bg-coral-50/50 p-4", offline && "pointer-events-none opacity-50")}>
                <Activity className="size-9 text-coral-600" />
                <span>
                  <span className="block text-lg font-semibold text-ink">{tr("Photo of the problem")}</span>
                  <span className="block text-sm text-muted">{tr("Rash, wound, swelling")}</span>
                </span>
                <input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => onPick(e.target.files, "image")} />
              </label>
            </div>
            {(API_MODE === "mock" || facilityId === SAMPLE_FACILITY_ID) && (
            <div>
              <p className="mb-2 text-sm font-semibold text-ink-2">{t("kiosk.upload.sample")} <span className="font-normal text-muted">{tr("(synthetic, for the demo — OCR values are traced to the image)")}</span></p>
              <div className="flex flex-wrap gap-2">
                {SAMPLE_REPORTS.map((s) => (
                  <Button key={s.key} variant="secondary" size="sm" onClick={() => addSample(s.key)} disabled={busy || offline} icon={<FileText className="size-4" />}>
                    {tr(s.title)}
                  </Button>
                ))}
              </div>
            </div>
            )}
            {files.filter((f) => f.kind !== "audio").length > 0 && (
              <div className="flex flex-wrap gap-3">
                {files.filter((f) => f.kind !== "audio").map((f) => (
                  <div key={f.id} className="w-28">
                    {f.url && f.content_type.startsWith("image") ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={f.url} alt={f.filename} className="h-24 w-28 rounded-xl border border-line object-cover object-top" />
                    ) : (
                      <div className="grid h-24 w-28 place-items-center rounded-xl border border-line bg-canvas"><FileText className="size-8 text-muted" /></div>
                    )}
                    <p className="mt-1 truncate text-xs text-muted">{f.filename}</p>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-muted">{tr("Photos and reports are deleted automatically after 3–7 days. Voice recordings after 24 hours.")}</p>
          </div>
        )}

        {step === "followup" && (
          <div className="space-y-5">
            {questions.length === 0 && <p className="text-lg text-muted">{tr("No more questions. Thank you!")}</p>}
            {questions.map((q) => (
              <div key={q.qid}>
                <div className="mb-2 flex items-start justify-between gap-2">
                  <p className="text-lg font-semibold text-ink">{tr(q.question)}</p>
                  {listen(tr(q.question))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {q.options.map((o) => (
                    <button
                      key={o}
                      type="button"
                      onClick={() => setAnswers({ ...answers, [q.qid]: { qid: q.qid, question: q.question, answer: o } })}
                      aria-pressed={answers[q.qid]?.answer === o}
                      className={cx("min-h-12 rounded-xl border-2 px-4 text-base font-medium", answers[q.qid]?.answer === o ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-ink-2")}
                    >
                      {tr(o)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {step === "vitals" && (
          <div>
            <p className="mb-4 text-sm text-muted">{tr("Optional. Entered by the nurse / ANM. Readings feed the deterministic rules engine.")}</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {(
                [
                  ["bp_systolic", "BP systolic", "mmHg"],
                  ["bp_diastolic", "BP diastolic", "mmHg"],
                  ["pulse", "Pulse", "bpm"],
                  ["spo2", "SpO₂", "%"],
                  ["temp_f", "Temperature", "°F"],
                  ["resp_rate", "Resp. rate", "/min"],
                  ["glucose", "Glucose (POC)", "mg/dL"],
                ] as const
              ).map(([k, label, unit]) => (
                <div key={k}>
                  <Label htmlFor={`v-${k}`} hint={unit}>{label}</Label>
                  <Input id={`v-${k}`} inputMode="decimal" value={vitals[k]} onChange={(e) => setVitals({ ...vitals, [k]: e.target.value.replace(/[^\d.]/g, "").slice(0, 5) })} className="h-12 text-lg tabular-nums" />
                </div>
              ))}
            </div>
          </div>
        )}

        {step === "review" && (
          <div className="space-y-3 text-base">
            <Row k="Patient" v={patient ? `${patient.name} · ${patient.age} y · ${patient.code}` : `${newP.name} · ${newP.age} y (new)`} />
            <Row k="Consent" v={consentMode === "proxy" ? `Given by ${proxyName} (${proxyRel})` : "Given by patient"} />
            <Row k="Visit" v={category ?? "—"} />
            <Row k="Problem" v={chief || "—"} />
            {selected.length > 0 && <Row k="Also" v={selected.join(", ")} />}
            <Row k="Since" v={duration ?? answers.dur?.answer ?? "—"} />
            <Row k="Files" v={tr("{n} report / photo", { n: files.filter((f) => f.kind !== "audio").length })} />
            {Object.values(answers).length > 0 && <Row k="Answers" v={Object.values(answers).map((a) => a.answer).join(" · ")} />}
            {offline && (
              <p className="flex items-center gap-2 rounded-xl bg-semi-bg px-3 py-2 text-sm font-medium text-semi">
                <WifiOff className="size-4" /> {t("kiosk.offline")}
              </p>
            )}
          </div>
        )}

        <FieldError>{err}</FieldError>

        <div className="mt-7 flex gap-3">
          {idx > 0 && (
            <Button variant="secondary" size="xl" onClick={() => go(-1)} icon={<ArrowLeft className="size-6" />} aria-label={t("common.back")}>
              <span className="iconmode:hidden">{t("common.back")}</span>
            </Button>
          )}
          {step === "review" ? (
            <Button size="xl" variant="teal" className="flex-1" onClick={submit} loading={busy} icon={<Check className="size-6" />}>
              {t("common.submit")}
            </Button>
          ) : (
            <Button size="xl" className="flex-1" onClick={next} disabled={busy}>
              {step === "uploads" && !files.length ? t("common.skip") : step === "vitals" && !Object.values(vitals).some(Boolean) ? t("common.skip") : t("common.next")} <ArrowRight className="size-6" />
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  const { tr } = usePrefs();
  return (
    <div className="flex gap-4 border-b border-line pb-2 last:border-0">
      <span className="w-24 shrink-0 text-muted">{tr(k)}</span>
      <span className="font-medium text-ink capitalize-first">{tr(v)}</span>
    </div>
  );
}
