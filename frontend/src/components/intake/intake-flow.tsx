"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  Mic, Square, Volume2, Check, RotateCcw, Camera, FileText, UserRound, Users, Lock, Eye, HandHeart, Stethoscope, Baby, HeartPulse, ArrowLeft, ArrowRight,
  Search, UserPlus, WifiOff, Trash2, Keyboard, CheckCircle2, Activity, Sparkles, HardHat, Building2, AlertTriangle,
  PhoneCall,
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
import { cadreName, isNational } from "@/lib/cadres";
import { EXPOSURE_LABEL, type Exposure, type FacilityRegion, type ConsentMode, type FileObject, type IntakeAnswer, type OccupationalIntake, type Patient, type PatientCandidate, type PatientCategory, type PhoneOwner, type PrivacyContext, type SymptomEntry, type NumericVital, type VitalsInput, type VisitKind } from "@/lib/types";
import { fmtDate } from "@/lib/hooks";
import { FIELDS as VITAL_FIELDS } from "@/components/triage/observations";
import { DURATIONS, SEVERITIES, SYMPTOMS, contextQuestions } from "./catalog";

// The built-in contact (backend config default) is shown in the patient's language; a facility's own text is shown as typed.
const DEFAULT_GRIEVANCE = "Grievance officer at this facility's front desk, or call 104";

/** One speech engine's hearing of a recording (B9); `differences` non-empty = the two engines disagree. */
type Hearing = { engine: string; text: string; translation?: string | null; differences: string[] };

type Step = "consent" | "identity" | "visit" | "symptoms" | "details" | "uploads" | "followup" | "vitals" | "review";

/** Engine label for transcripts produced by the browser's own speech recognition (fallback only). */
const BROWSER_ASR = "Browser speech recognition";

export interface IntakeResult {
  token: string;
  patientCode: string | null;
  offline: boolean;
  /** Filled in from home (C3): "show_at_desk", or "emergency" when a danger sign was reported. Never a tier. */
  homeAdvice?: "emergency" | "show_at_desk" | null;
  /** Who to complain to about data handling (DPDP s. 13), from the server; printed on the slip. */
  grievanceContact?: string | null;
}

/** DPDP Act s. 9: under 18, consent comes from a parent or lawful guardian. Same list as the server. */
const GUARDIANS = ["Mother", "Father", "Guardian"];

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
  offlineQueue = true,
  patientLoad = "normal",
  onFinished,
  onReset,
  organisationName,
}: {
  /** kiosk = staff-unlocked tablet · link = public kiosk link (/k/CODE) · patient = patient's own account */
  mode: "kiosk" | "patient" | "link";
  facilityId: string;
  fixedPatient?: Patient | null;
  offline: boolean;
  /** F2: whether this facility queues intakes on the device when the network is down. */
  offlineQueue?: boolean;
  /** F2: on a high-load day only the safety questions are asked. */
  patientLoad?: "low" | "normal" | "high";
  onFinished?: (r: IntakeResult) => void;
  /** Start a fresh intake (next patient) without reloading, so kiosk state such as offline mode survives. */
  onReset?: () => void;
  /** Set when the facility is an organisation's workplace (company clinic, campus…): asks for the employee / student ID. */
  organisationName?: string | null;
}) {
  const { tr, t, lang, readAloud } = usePrefs();
  // F5: the helper list names the state's community health worker (ASHA, Mitanin, Sahiya…). Facility details are public.
  const [region, setRegion] = useState<FacilityRegion | null>(null);
  const [facType, setFacType] = useState<string | null>(null);
  useEffect(() => {
    api.getFacility(facilityId).then((f) => {
      setRegion(f.region ?? null);
      setFacType(f.type);
    }, () => undefined);
  }, [facilityId]);
  // D4: staff at the kiosk can hand a pregnant woman's follow-up to a named health worker.
  const [healthWorkers, setHealthWorkers] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => {
    if (mode !== "kiosk") return;
    api.listHealthWorkers().then(setHealthWorkers, () => undefined);
  }, [mode, facilityId]);
  const communityWorker = isNational(region, "community") ? "ASHA worker" : cadreName(region, "community", lang);
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
  // "Continue without AI" (G1): no speech recognition, translation or report reading for this visit.
  const [aiAssist, setAiAssist] = useState(true);

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
  // second: the other speech engine's hearing of the same recording (B9); `differences` non-empty = they disagree
  const [pending, setPending] = useState<{ original: string; text: string; engine: string; audio: Blob | null; mt?: string; second?: Hearing; confidence?: number | null; low?: boolean } | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const recRef = useRef<Recorder | null>(null);
  // B9 offline check still running: its result goes to the read-back, or to the entry if already confirmed
  const [checking, setChecking] = useState<{ id: string; original: string } | null>(null);
  useEffect(() => {
    if (!checking) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const started = Date.now();
    const tick = async () => {
      try {
        const so = await api.secondCheck(checking.id);
        if (stop) return;
        if (so.pending && Date.now() - started < 180_000) {
          timer = setTimeout(tick, 3000);
          return;
        }
        if (so.text) {
          const h: Hearing = { engine: so.engine, text: so.text, translation: so.translation ?? null, differences: so.disagree ? (so.differences ?? []) : [] };
          setPending((p) => (p && p.original === checking.original && !p.second ? { ...p, second: h } : p));
          setEntries((es) => es.map((e) => (e.original_text === checking.original && !e.second_hearing ? { ...e, second_hearing: { engine: h.engine, text: h.text, translation: h.translation ?? null } } : e)));
        }
      } catch {
        /* the check is optional — the patient already confirmed what they said */
      }
      if (!stop) setChecking(null);
    };
    timer = setTimeout(tick, 3000);
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [checking]);

  // details
  const [duration, setDuration] = useState<string | null>(null);
  const [severity, setSeverity] = useState<number | null>(null);
  const [maternal, setMaternal] = useState({ gestation_weeks: "", anc_visits: "", next_checkup: "", reminder_channel: "sms" as "sms" | "voice" | "none", phone_belongs_to: "" as PhoneOwner | "", assigned_worker_id: "" });
  // D3: campus clinics count fevers per hostel block. D2: workplace clinics ask about exposure and protection.
  const [hostel, setHostel] = useState("");
  const [occ, setOcc] = useState({ exposures: [] as Exposure[], years: "", cough_weeks: "", breathless_vs_last: "" as NonNullable<OccupationalIntake["breathless_vs_last"]> | "", ppe_issued: "" as "" | "yes" | "no", ppe_used: "" as NonNullable<OccupationalIntake["ppe_used"]> | "", fev1: "", fvc: "" });
  const [chronic, setChronic] = useState({ condition: "", last_checkup: "", current_medicines: "", feeling_vs_last: "same" as "better" | "same" | "worse" | "unsure" });

  // uploads / follow-up / vitals
  const [files, setFiles] = useState<FileObject[]>([]);
  const [answers, setAnswers] = useState<Record<string, IntakeAnswer>>({});
  const [vitals, setVitals] = useState<Record<NumericVital, string>>({ bp_systolic: "", bp_diastolic: "", pulse: "", temp_f: "", spo2: "", resp_rate: "", glucose: "" });

  const age = patient?.age ?? (Number(newP.age) || 30);
  const [lowHeard, setLowHeard] = useState<Set<string>>(new Set());
  const chief = useMemo(() => {
    // Words heard with low confidence are not the complaint: the health worker asks about them.
    const first = entries.find((e) => !lowHeard.has(e.original_text))?.text || typed.trim();
    if (first) return first.length > 90 ? first.slice(0, 87) + "…" : first;
    if (selected.length) return selected.join(", ");
    return category === "maternal" ? "Antenatal check-up" : category === "chronic" ? `${chronic.condition || "Chronic"} follow-up` : "";
  }, [entries, typed, selected, category, chronic.condition, lowHeard]);

  const questions = useMemo(
    () => (category ? contextQuestions({ chief_complaint: chief, selected_symptoms: selected, category, symptoms: entries, duration, sex: patient?.sex ?? newP.sex }, age, patientLoad) : []),
    [chief, selected, category, entries, duration, age, patientLoad, patient?.sex, newP.sex],
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
    if (!result || !onReset || result.homeAdvice) return; // from home: the number stays on the patient's own phone
    const id = setTimeout(onReset, 60_000);
    return () => clearTimeout(id);
  }, [result, onReset, mode]);

  useEffect(() => {
    // F3: a patient who cannot read hears the consent and the disclaimer, then each question with its choices.
    if (readAloud && step !== "vitals" && step !== "followup") speak(step === "consent" ? `${t("kiosk.welcome")} ${t("kiosk.consent.body")} ${t("disclaimer.short")}` : t(STEP_TITLE[step]), lang);
    return () => stopSpeaking();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, readAloud, lang]);

  useEffect(() => {
    if (!readAloud || step !== "followup") return;
    const q = questions.find((x) => !answers[x.qid]);
    const first = Object.keys(answers).length === 0 ? `${t(STEP_TITLE[step])} ` : "";
    speak(q ? `${first}${tr(q.question)} ${q.options.map((o) => tr(o)).join(", ")}` : tr("No more questions. Thank you!"), lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, readAloud, lang, answers]);

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
        if ((patient?.age ?? 99) < 18 && !(consentMode === "proxy" && GUARDIANS.includes(proxyRel))) return "Patients under 18 need consent from a parent or guardian. Choose Mother, Father or Guardian.";
        if (!agreed) return "Consent is needed to continue";
        return null;
      case "identity":
        if (patient) return null;
        if (!isNew) return "Find the patient or register a new person";
        if (newP.name.trim().length < 2) return "Enter the patient's name";
        if (!newP.age || Number(newP.age) < 0 || Number(newP.age) > 120) return "Enter a valid age";
        if (!newP.sex) return "Choose sex";
        // A form for any centre is found by this number if the patient loses the reference.
        if (!newP.phone && facilityId === "fac_any_centre") return "Enter a mobile number: any centre finds your form with it";
        if (newP.phone && !/^\d{10}$/.test(newP.phone)) return "Phone must be 10 digits";
        return null;
      case "visit":
        return category ? null : "Choose the visit type";
      case "symptoms":
        if (pending) return "Confirm or re-record the voice note first";
        if (!entries.length && !typed.trim() && !selected.length && category === "normal") return "Tell us at least one problem — speak, type or tap";
        return null;
      case "vitals":
        return vitalsProblem(vitals);
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
    if (e) return setErr(tr(e));
    const age = patient?.age ?? Number(newP.age);
    if (step === "identity" && age < 18 && !(consentMode === "proxy" && GUARDIANS.includes(proxyRel))) {
      // Back to consent with "helping" chosen: a parent or guardian gives it, then the intake goes on.
      setConsentMode("proxy");
      if (!GUARDIANS.includes(proxyRel)) setProxyRel("");
      setStep("consent");
      return setErr(tr("Patients under 18 need consent from a parent or guardian. Choose Mother, Father or Guardian."));
    }
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
    const heard = r?.transcript?.trim() ?? "";
    const audio = r?.audio ?? null;
    let next: typeof pending = null;
    if (audio && !offline) {
      // Server first: offline IndicConformer transcript + IndicTrans2 English, both engines named.
      setTranscribing(true);
      try {
        const res = await api.transcribe(audio, lang, { secondOpinion: aiAssist });
        const so = res.second_opinion;
        // IndicWhisper (offline) answers after the read-back has started; picked up below when ready
        setChecking(so?.pending ? { id: so.pending, original: res.text } : null);
        next = {
          original: res.text,
          text: res.translation?.text ?? res.text,
          engine: res.translation ? `${res.engine} + ${res.translation.engine}` : res.engine,
          audio,
          mt: res.translation?.engine,
          second: so?.text ? { engine: so.engine, text: so.text, translation: so.translation ?? null, differences: so.disagree ? (so.differences ?? []) : [] } : undefined,
          confidence: res.confidence,
          low: res.low_confidence,
        };
      } catch (e) {
        if (e instanceof ApiError && e.status === 422) {
          setErr(e.message); // the recording itself was unusable (silent / too short) — ask again
          return;
        }
        /* server speech unavailable — fall back to what the browser heard, if anything */
      } finally {
        setTranscribing(false);
      }
    }
    // Browser fallback: English is kept as heard; other languages are translated when the intake is submitted.
    if (!next && heard) next = { original: heard, text: heard, engine: BROWSER_ASR, audio };
    if (!next) {
      setErr(tr("Could not understand the recording — please speak again, or type or tap your symptoms"));
      return;
    }
    setPending(next);
    speak(`${t("kiosk.symptoms.readback")} ${next.original}`, lang, undefined, { online: aiAssist });
  };

  // B9: the patient says the second engine heard them right; the first engine's words are kept beside it
  const useOtherHearing = () => {
    if (!pending?.second) return;
    const s = pending.second;
    const first = pending.engine.split(" + ")[0];
    setPending({
      ...pending,
      original: s.text,
      text: s.translation ?? s.text,
      engine: s.translation && pending.mt ? `${s.engine} + ${pending.mt}` : s.engine,
      second: { engine: first, text: pending.original, translation: pending.text !== pending.original ? pending.text : null, differences: s.differences },
    });
    speak(`${t("kiosk.symptoms.readback")} ${s.text}`, lang, undefined, { online: aiAssist });
  };

  const confirmVoice = async (ok: boolean) => {
    if (!pending) return;
    stopSpeaking();
    if (!ok) {
      setPending(null);
      return;
    }
    const second_hearing = pending.second ? { engine: pending.second.engine, text: pending.second.text, translation: pending.second.translation ?? null } : null;
    setEntries((e) => [...e, { text: pending.text, original_text: pending.original, language: lang, source: "voice", confirmed_by_readback: true, engine: pending.engine, second_hearing, confidence: pending.confidence ?? null }]);
    if (pending.low) setLowHeard((s) => new Set(s).add(pending.original));
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
        const up = await api.uploadFile(await compressImage(f), kind, null, null, aiAssist, aiAssist);
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
      // Decoded here, not with fetch(): the page's security policy does not allow fetching data: URLs.
      const blob = new Blob([decodeURIComponent(img.dataUrl.slice(img.dataUrl.indexOf(",") + 1))], { type: "image/svg+xml" });
      const up = await api.uploadFile(new File([blob], `${key}_sample_report.svg`, { type: "image/svg+xml" }), "report", null, key, aiAssist);
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
          ? {
              gestation_weeks: num(maternal.gestation_weeks), anc_visits: num(maternal.anc_visits), next_checkup: maternal.next_checkup || null, reminder_channel: maternal.reminder_channel,
              phone_belongs_to: maternal.phone_belongs_to || null, assigned_worker_id: maternal.assigned_worker_id || null,
            }
          : null,
      cluster_key: facType === "campus" && hostel.trim() ? hostel.trim() : null,
      occupational: occ.exposures.length
        ? {
            exposures: occ.exposures, years_exposed: num(occ.years), cough_weeks: num(occ.cough_weeks), breathless_vs_last: occ.breathless_vs_last || null,
            ppe_issued: occ.ppe_issued ? occ.ppe_issued === "yes" : null, ppe_used: occ.ppe_used || null, fev1_l: num(occ.fev1), fvc_l: num(occ.fvc),
          }
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
      scopes: ["triage", "share_with_treating_team", "store_reports_until_expiry", aiAssist ? "ai_assist" : "no_ai"],
    };
    const newPatient = isNew
      ? { name: newP.name.trim(), age: Number(newP.age), sex: newP.sex as "F" | "M" | "O", phone: newP.phone || null, language: lang, category: category!, village: null, employee_code: (organisationName && newP.employee_code.trim()) || null }
      : null;

    try {
      if (offline && !offlineQueue) {
        setErr(tr("No network, and this facility does not queue intakes on the device. Use the paper form and enter it when the connection is back."));
        return;
      }
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
      const r = { token: enc.token ?? `A-${enc.id.slice(-3).toUpperCase()}`, patientCode: p.code, offline: false, homeAdvice: enc.home_advice ?? null, grievanceContact: c.grievance_contact ?? null };
      setResult(r);
      onFinished?.(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Could not submit"));
    } finally {
      setBusy(false);
    }
  };

  /* ── Result (token) — never shows urgency ── */
  if (result?.homeAdvice === "emergency") {
    return (
      <Card className="fade-up mx-auto max-w-xl border-crit-line p-8 text-center" role="alert">
        <PhoneCall className="mx-auto size-14 text-crit" />
        <h2 className="mt-3 text-3xl font-bold text-crit">{t("kiosk.home.emergency.title")}</h2>
        <p className="mt-3 text-lg text-ink-2">{result.token.startsWith("J-") ? tr("Go to the nearest hospital emergency now, or call 108. Show this reference there.") : t("kiosk.home.emergency.body")}</p>
        <a href="tel:108" className="mt-6 block">
          <Button size="xl" variant="danger" className="w-full" icon={<PhoneCall className="size-5" />}>
            108
          </Button>
        </a>
        <p className="mt-6 text-sm text-muted">
          {t("kiosk.home.token")}: <span className="font-mono font-bold text-ink">{result.token}</span>
        </p>
        {result.token.startsWith("J-") && (
          <div className="mt-4 inline-flex flex-col items-center rounded-2xl border border-line bg-white p-4">
            <QRCodeSVG value={`${window.location.origin}/desk?claim=${result.token}`} size={160} title={`${tr("QR code with your reference")} ${result.token}`} />
            <p className="mt-2 text-xs text-muted">{tr("Take a photo or screenshot of this screen. Lost it? Give your mobile number at the desk.")}</p>
          </div>
        )}
      </Card>
    );
  }

  if (result) {
    const home = result.homeAdvice === "show_at_desk";
    return (
      <Card className="fade-up mx-auto max-w-xl p-8 text-center">
        <CheckCircle2 className="mx-auto size-14 text-teal-600" />
        <h2 className="mt-3 text-3xl font-bold text-ink">{t("kiosk.done.title")}</h2>
        <p className="mt-2 text-lg text-muted">
          {result.token.startsWith("J-") ? tr("Take this reference to any health centre. Show it, or this QR code, at the desk; your details will be ready there.") : home ? t("kiosk.home.body") : t("kiosk.done.body")}
        </p>
        <p className="mt-6 text-sm font-semibold tracking-wider text-muted uppercase">{home ? t("kiosk.home.token") : t("kiosk.done.token")}</p>
        <p className="text-6xl font-extrabold tracking-tight text-ink tabular-nums">{result.token}</p>
        {result.token.startsWith("J-") && (
          <div className="mt-4 inline-flex flex-col items-center rounded-2xl border border-line bg-white p-4">
            <QRCodeSVG value={`${window.location.origin}/desk?claim=${result.token}`} size={160} title={`${tr("QR code with your reference")} ${result.token}`} />
            <p className="mt-2 text-xs text-muted">{tr("Take a photo or screenshot of this screen. Lost it? Give your mobile number at the desk.")}</p>
          </div>
        )}
        <button type="button" onClick={() => speak(`${home ? t("kiosk.home.token") : t("kiosk.done.token")}: ${result.token.split("").join(" ")}`, lang)} className="mt-3 inline-flex min-h-12 items-center gap-1 rounded-full bg-canvas px-4 text-sm font-semibold text-ink-2 hover:bg-line" aria-label={t("common.listen")}>
          <Volume2 className="size-4" /> {t("common.listen")}
        </button>
        {result.patientCode && (
          <div className="mt-6 inline-flex flex-col items-center rounded-2xl border border-line bg-white p-4">
            <QRCodeSVG value={`jeevia:${result.patientCode}`} size={132} title={`${tr("QR code with your patient ID")} ${result.patientCode}`} />
            <p className="mt-2 text-xs text-muted">{tr("Your patient ID — show it on your next visit")}</p>
            <p className="font-mono text-base font-bold text-ink">{result.patientCode}</p>
          </div>
        )}
        <p className="mt-5 text-sm text-muted">
          {t("kiosk.done.grievance")} {!result.grievanceContact || result.grievanceContact === DEFAULT_GRIEVANCE ? t("kiosk.done.grievance.default") : result.grievanceContact}
        </p>
        {home && <p className="mt-5 rounded-xl border border-crit-line bg-crit-bg px-4 py-2.5 text-sm font-medium text-crit">{t("kiosk.home.danger")}</p>}
        {result.offline && (
          <p className="mt-5 flex items-center justify-center gap-2 rounded-xl bg-semi-bg px-4 py-2 text-sm font-medium text-semi">
            <WifiOff className="size-4" /> {t("kiosk.offline")}
          </p>
        )}
        <Button size="xl" className="mt-8 w-full" variant="teal" icon={mode === "link" ? <ArrowLeft className="size-5" /> : undefined} onClick={() => (onReset ? onReset() : window.location.reload())}>
          {mode === "kiosk" ? t("kiosk.done.next") : mode === "link" ? tr("Back to landing page") : t("common.done")}
        </Button>
      </Card>
    );
  }

  const listen = (text: string) => (
    <button type="button" onClick={() => speak(text, lang)} className="inline-flex min-h-12 items-center gap-1 rounded-full bg-canvas px-3.5 text-xs font-semibold text-ink-2 hover:bg-line" aria-label={t("common.listen")}>
      <Volume2 className="size-3.5" /> {t("common.listen")}
    </button>
  );

  return (
    <div className="mx-auto max-w-3xl">
      {!voiceOk && (
        <p className="mb-4 flex items-start gap-2 rounded-xl border border-semi/30 bg-semi-bg px-4 py-2.5 text-sm text-ink-2">
          <Volume2 className="mt-0.5 size-4 shrink-0 text-semi" />
          {tr("This device has no {lang} voice, so questions are not read aloud. Install the {lang} voice in the device’s text-to-speech settings.", { lang: langByCode(lang).native })}
        </p>
      )}
      {/* progress */}
      <div className="mb-5 flex items-center gap-1.5" role="progressbar" aria-valuemin={1} aria-valuemax={steps.length} aria-valuenow={idx + 1} aria-label={tr("Step {n} of {m}", { n: idx + 1, m: steps.length })}>
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
                    {["Mother", "Father", "Guardian", "Husband", "Wife", "Son", "Daughter", "Mother-in-law", "Other family", communityWorker, "Caregiver"].map((r) => (
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
            <div>
              <p className="mb-2 text-sm font-semibold text-ink-2">{tr("Computer helpers")}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <BigChoice selected={aiAssist} onClick={() => setAiAssist(true)} icon={<Sparkles />} title={tr("Use AI helpers")} body={tr("Speech to text, translation and reading reports on this facility's computer. Your recorded words, and photos of handwritten papers, may also be read by a second engine online, in India (Sarvam AI).")} />
                <BigChoice selected={!aiAssist} onClick={() => setAiAssist(false)} icon={<Keyboard />} title={tr("Continue without AI")} body={tr("Type or tap only. Staff read your reports themselves. Your care is the same.")} />
              </div>
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
                  <Label htmlFor="np-phone">{facilityId === "fac_any_centre" ? tr("Mobile number (needed: any centre finds your form with it)") : t("kiosk.identity.phone")}</Label>
                  <Input id="np-phone" inputMode="numeric" value={newP.phone} onChange={(e) => setNewP({ ...newP, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} className="h-13 text-lg" />
                </div>
                {organisationName && (
                  <div className="sm:col-span-2">
                    <Label htmlFor="np-emp" hint={tr("(optional)")}>{organisationName} {tr("employee / student ID")}</Label>
                    <Input id="np-emp" value={newP.employee_code} onChange={(e) => setNewP({ ...newP, employee_code: e.target.value.toUpperCase().slice(0, 40) })} className="h-13 text-lg" placeholder={tr("e.g. KSW-1041")} />
                  </div>
                )}
                <Button variant="ghost" className="min-h-12 sm:col-span-2" onClick={() => { setIsNew(false); setCandidates(null); }} icon={<Search className="size-4" />} disabled={offline}>
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
                      <button key={c.patient.id} type="button" onClick={() => { setPatient(c.patient); void api.pickPatient(c.patient.id, c.match_reason, candidates.length).catch(() => undefined); }} className="flex w-full items-center gap-3 rounded-2xl border-2 border-line p-3 text-left hover:border-teal-300">
                        <span className="grid size-11 place-items-center rounded-xl bg-coral-100 font-bold text-coral-700">{c.patient.name.charAt(0)}</span>
                        <span className="flex-1">
                          <span className="block font-semibold text-ink">{c.patient.name}</span>
                          <span className="block text-sm text-muted">{c.patient.age} y · {c.patient.sex} · {c.patient.code}{c.match_reason ? ` · ${tr(c.match_reason)}` : ""}</span>
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
            {!aiAssist && (
              <p className="flex items-center gap-2 rounded-2xl bg-canvas p-4 text-base text-ink-2">
                <Keyboard className="size-5 shrink-0" /> {tr("AI helpers are off for this visit. Please tap the pictures or type.")}
              </p>
            )}
            <div className={cx("flex flex-col items-center gap-3 rounded-2xl bg-canvas p-5", !aiAssist && "hidden")}>
              <button
                type="button"
                onClick={toggleMic}
                disabled={!!pending || transcribing}
                className={cx("grid size-28 place-items-center rounded-full text-white shadow-lg transition-transform active:scale-95 disabled:opacity-50", recording ? "recording-pulse bg-crit" : "bg-teal-700 hover:bg-teal-800")}
                aria-label={recording ? t("kiosk.symptoms.stop") : t("kiosk.symptoms.speak")}
              >
                {recording ? <Square className="size-10" /> : <Mic className="size-12" />}
              </button>
              <p className="text-lg font-semibold text-ink">{recording ? t("kiosk.symptoms.stop") : t("kiosk.symptoms.speak")}</p>
              <p className="text-sm text-muted">{langByCode(lang).native} · {!offline ? tr("transcribed on the facility server") : canRecognise() ? tr("on-device transcription") : tr("voice needs the server — please type or tap")}</p>
              {recording && partial && <p className="max-w-lg text-center text-lg text-ink-2 italic">“{partial}”</p>}
              {transcribing && <p className="text-base text-ink-2" role="status">{tr("Understanding what you said…")}</p>}
            </div>

            {pending && (
              <div className="rounded-2xl border-2 border-coral-300 bg-coral-50 p-4">
                <p className="text-sm font-semibold text-coral-700">{t("kiosk.symptoms.readback")}</p>
                <p className="mt-1 text-xl font-medium text-ink">“{pending.original}”</p>
                {pending.text !== pending.original && <p className="mt-1 text-sm text-muted" lang="en">→ {pending.text}</p>}
                <p className="mt-1 text-xs text-subtle">{pending.engine}</p>
                {pending.low && (
                  <p className="mt-3 flex items-start gap-2 rounded-xl border border-semi/40 bg-white p-3 text-sm text-ink" role="alert"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-semi" />{tr("We are not sure we heard this correctly. A health worker will ask you about it. You can also say it again or tap the pictures.")}</p>
                )}
                {checking?.original === pending.original && !pending.second && (
                  <p className="mt-2 text-xs text-muted" role="status">{tr("A second engine is still checking what it heard…")}</p>
                )}
                {pending.second && pending.second.differences.length > 0 && (
                  <div className="mt-3 rounded-xl border border-semi/40 bg-white p-3" role="alert">
                    <p className="flex items-center gap-2 text-sm font-semibold text-semi"><AlertTriangle className="size-4" />{tr("A second engine heard something different")}</p>
                    <p className="mt-1 text-lg text-ink">“{pending.second.text}”</p>
                    {pending.second.translation && <p className="mt-1 text-sm text-muted" lang="en">→ {pending.second.translation}</p>}
                    <p className="mt-1 text-xs text-subtle">{pending.second.engine}</p>
                    <ul className="mt-2 list-disc pl-5 text-xs text-ink-2" lang="en">
                      {pending.second.differences.map((d) => <li key={d}>{d}</li>)}
                    </ul>
                    <p className="mt-2 text-sm text-ink-2">{tr("Ask the patient which is right.")}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" onClick={useOtherHearing}>{tr("Use this one instead")}</Button>
                      <Button size="sm" variant="ghost" onClick={() => speak(pending.second!.text, lang, undefined, { online: aiAssist })} icon={<Volume2 className="size-4" />}>{t("common.listen")}</Button>
                    </div>
                  </div>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="lg" variant="teal" onClick={() => confirmVoice(true)} icon={<Check className="size-5" />}>{t("kiosk.symptoms.correct")}</Button>
                  <Button size="lg" variant="secondary" onClick={() => confirmVoice(false)} icon={<RotateCcw className="size-5" />}>{t("kiosk.symptoms.again")}</Button>
                  <Button size="lg" variant="ghost" onClick={() => speak(pending.original, lang, undefined, { online: aiAssist })} icon={<Volume2 className="size-5" />}>{t("common.listen")}</Button>
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
                    <ClinicDays facilityId={facilityId} kind="anc_checkup" value={maternal.next_checkup} onPick={(d) => setMaternal({ ...maternal, next_checkup: d })} />
                  </div>
                  <div>
                    <Label htmlFor="m-rem">{tr("Remind me by")}</Label>
                    <Select id="m-rem" value={maternal.reminder_channel} onChange={(e) => setMaternal({ ...maternal, reminder_channel: e.target.value as "sms" | "voice" | "none" })} className="h-12">
                      <option value="sms">{tr("SMS")}</option>
                      <option value="voice">{tr("Voice call")}</option>
                      <option value="none">{tr("No reminder")}</option>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="m-phone">{tr("Whose phone is this number?")}</Label>
                    <Select id="m-phone" value={maternal.phone_belongs_to} onChange={(e) => setMaternal({ ...maternal, phone_belongs_to: e.target.value as PhoneOwner | "" })} className="h-12">
                      <option value="">{tr("Not asked")}</option>
                      <option value="self">{tr("My own phone")}</option>
                      <option value="husband">{tr("My husband's phone")}</option>
                      <option value="household">{tr("A family phone")}</option>
                      <option value="none">{tr("No phone")}</option>
                    </Select>
                    <p className="mt-1 text-xs text-muted">{tr("On a phone that is not hers, reminders never mention pregnancy.")}</p>
                  </div>
                  {mode === "kiosk" && healthWorkers.length > 0 && (
                    <div>
                      <Label htmlFor="m-hw">{tr("Follow-up by")}</Label>
                      <Select id="m-hw" value={maternal.assigned_worker_id} onChange={(e) => setMaternal({ ...maternal, assigned_worker_id: e.target.value })} className="h-12">
                        <option value="">{tr("Not assigned")}</option>
                        {healthWorkers.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                      </Select>
                      <p className="mt-1 text-xs text-muted">{tr("If the check-up is missed, this {w} is told first.", { w: communityWorker })}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {facType === "campus" && (
              <div className="rounded-2xl border border-line p-4">
                <Label htmlFor="hostel" hint={tr("(optional)")}><span className="inline-flex items-center gap-1.5"><Building2 className="size-4" /> {tr("Hostel or block where you stay")}</span></Label>
                <Input id="hostel" value={hostel} onChange={(e) => setHostel(e.target.value.slice(0, 80))} className="h-12" placeholder={tr("e.g. Hostel Block C")} />
                <p className="mt-1 text-xs text-muted">{tr("Used only to count fevers per hostel, so the campus doctor can spot an outbreak. Your name is never shown with it.")}</p>
              </div>
            )}

            {(facType === "industrial_unit" || facType === "company_clinic" || !!patient?.organisation_id) && (
              <div className="rounded-2xl border border-semi-line bg-semi-bg/40 p-4">
                <p className="mb-1 flex items-center gap-2 font-semibold text-ink"><HardHat className="size-5" /> {tr("Work and exposure")}</p>
                <p className="mb-3 text-xs text-muted">{tr("For the workplace health check. Your employer never sees these answers or any symptom, only department totals.")}</p>
                <Label>{tr("At work, are you exposed to")}</Label>
                <div className="mb-3 flex flex-wrap gap-2">
                  {(Object.keys(EXPOSURE_LABEL) as Exposure[]).map((x) => {
                    const on = occ.exposures.includes(x);
                    return (
                      <button key={x} type="button" aria-pressed={on} onClick={() => setOcc({ ...occ, exposures: on ? occ.exposures.filter((y) => y !== x) : [...occ.exposures, x] })}
                        className={cx("min-h-11 rounded-xl border-2 px-3 text-sm font-semibold", on ? "border-ink bg-white text-ink" : "border-line text-ink-2")}>
                        {tr(EXPOSURE_LABEL[x])}
                      </button>
                    );
                  })}
                </div>
                {occ.exposures.length > 0 && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="o-years">{tr("Years in this work")}</Label>
                      <Input id="o-years" inputMode="decimal" value={occ.years} onChange={(e) => setOcc({ ...occ, years: e.target.value.replace(/[^\d.]/g, "").slice(0, 4) })} className="h-12" />
                    </div>
                    <div>
                      <Label htmlFor="o-cough" hint={tr("(0 if no cough)")}>{tr("Weeks of cough")}</Label>
                      <Input id="o-cough" inputMode="numeric" value={occ.cough_weeks} onChange={(e) => setOcc({ ...occ, cough_weeks: e.target.value.replace(/\D/g, "").slice(0, 3) })} className="h-12" />
                    </div>
                    <div className="sm:col-span-2">
                      <Label>{tr("Breathing compared with the last workplace check")}</Label>
                      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                        {(["better", "same", "worse", "unsure", "first"] as const).map((f) => (
                          <button key={f} type="button" aria-pressed={occ.breathless_vs_last === f} onClick={() => setOcc({ ...occ, breathless_vs_last: f })}
                            className={cx("h-11 rounded-xl border-2 text-sm font-semibold", occ.breathless_vs_last === f ? "border-ink bg-white text-ink" : "border-line text-ink-2")}>
                            {tr(f === "first" ? "First check" : f === "unsure" ? "Not sure" : f[0].toUpperCase() + f.slice(1))}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="o-ppe">{tr("Mask, ear plugs or gloves given?")}</Label>
                      <Select id="o-ppe" value={occ.ppe_issued} onChange={(e) => setOcc({ ...occ, ppe_issued: e.target.value as "" | "yes" | "no" })} className="h-12">
                        <option value="">{tr("Not asked")}</option>
                        <option value="yes">{tr("Yes")}</option>
                        <option value="no">{tr("No")}</option>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="o-ppeuse">{tr("Worn during work")}</Label>
                      <Select id="o-ppeuse" value={occ.ppe_used} onChange={(e) => setOcc({ ...occ, ppe_used: e.target.value as "" | "always" | "sometimes" | "never" })} className="h-12" disabled={occ.ppe_issued === "no"}>
                        <option value="">{tr("Not asked")}</option>
                        <option value="always">{tr("Always")}</option>
                        <option value="sometimes">{tr("Sometimes")}</option>
                        <option value="never">{tr("Never")}</option>
                      </Select>
                    </div>
                    {mode === "kiosk" && (
                      <>
                        <div>
                          <Label htmlFor="o-fev1" hint={tr("(spirometry, staff)")}>FEV1 (L)</Label>
                          <Input id="o-fev1" inputMode="decimal" value={occ.fev1} onChange={(e) => setOcc({ ...occ, fev1: e.target.value.replace(/[^\d.]/g, "").slice(0, 4) })} className="h-12" />
                        </div>
                        <div>
                          <Label htmlFor="o-fvc" hint={tr("(spirometry, staff)")}>FVC (L)</Label>
                          <Input id="o-fvc" inputMode="decimal" value={occ.fvc} onChange={(e) => setOcc({ ...occ, fvc: e.target.value.replace(/[^\d.]/g, "").slice(0, 4) })} className="h-12" />
                        </div>
                        <p className="text-xs text-muted sm:col-span-2">{tr("FEV1 is compared with this worker's own earliest recorded value; a fall of 15 % or more raises the case to YELLOW (ATS 2014).")}</p>
                      </>
                    )}
                  </div>
                )}
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
                  <Button key={s.key} variant="secondary" size="sm" className="min-h-12" onClick={() => addSample(s.key)} disabled={busy || offline} icon={<FileText className="size-4" />}>
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
                    {f.read_quality && !f.read_quality.ok && (
                      <p role="alert" className="mt-0.5 text-xs font-medium text-crit">
                        {f.read_quality.issues.map((i) => tr(i)).join(" · ")}
                      </p>
                    )}
                    {f.read_quality?.ok && f.kind === "report" && (
                      <p className="mt-0.5 text-xs text-rout">{tr("Readable")} ✓</p>
                    )}
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-muted">{tr("Photos and reports are deleted automatically after 3–7 days. Voice recordings after 24 hours.")}</p>
          </div>
        )}

        {step === "followup" && (
          <div className="space-y-5">
            {patientLoad === "high" && <p className="mb-3 text-sm text-muted">{tr("Busy day at this facility: only the safety questions are asked. The nurse asks the rest.")}</p>}
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
            <p className="mb-4 text-sm text-muted">{tr("Optional. Entered by the nurse / ANM. Readings feed the deterministic rules engine.")} {tr("Leave a box blank if it was not measured; the note lists it as not measured.")}</p>
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
                  <Input id={`v-${k}`} inputMode="decimal" value={vitals[k]} placeholder={tr("Not measured")} onChange={(e) => setVitals({ ...vitals, [k]: e.target.value.replace(/[^\d.]/g, "").slice(0, 5) })} className="h-12 text-lg tabular-nums placeholder:text-sm" />
                </div>
              ))}
            </div>
          </div>
        )}

        {step === "review" && (
          <div className="space-y-3 text-base">
            <Row k="Patient" v={patient ? `${patient.name} · ${tr("{n} y", { n: patient.age })} · ${patient.code}` : `${newP.name} · ${tr("{n} y", { n: newP.age })} · ${tr("new")}`} />
            <Row k="Consent" v={consentMode === "proxy" ? tr("Given by {name} ({rel})", { name: proxyName, rel: tr(proxyRel) }) : "Given by patient"} />
            <Row k="Computer helpers" v={aiAssist ? "Use AI helpers" : "Continue without AI"} />
            <Row k="Visit" v={category ?? "—"} />
            {/* The patient checks their own words, not the English translation staff read. */}
            <Row k="Problem" v={entries.find((e) => !lowHeard.has(e.original_text))?.original_text?.trim() || typed.trim() || chief || "—"} />
            {selected.some((x) => !chief.toLowerCase().includes(x.toLowerCase())) && <Row k="Also" v={selected.filter((x) => !chief.toLowerCase().includes(x.toLowerCase())).map((x) => tr(x)).join(", ")} />}
            <Row k="Since" v={duration ?? answers.dur?.answer ?? "—"} />
            <Row k="Files" v={tr("{n} report / photo", { n: files.filter((f) => f.kind !== "audio").length })} />
            {Object.values(answers).length > 0 && <Row k="Answers" v={Object.values(answers).map((a) => tr(a.answer)).join(" · ")} />}
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

/** E5: the facility's next clinic days for this visit; a date on another day is moved to the next clinic day. */
function ClinicDays({ facilityId, kind, value, onPick }: { facilityId: string; kind: VisitKind; value: string; onPick: (d: string) => void }) {
  const { tr } = usePrefs();
  const [v, setV] = useState<{ rule: string; days: string[] } | null>(null);
  useEffect(() => {
    let live = true;
    api.visitDays(facilityId, kind).then((r) => live && setV(r)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [facilityId, kind]);
  if (!v?.days.length) return null;
  return (
    <div className="mt-1.5">
      <div className="flex flex-wrap gap-1.5">
        {v.days.map((d) => (
          <button key={d} type="button" onClick={() => onPick(d)} aria-pressed={value === d} className={cx("rounded-lg border px-2 py-1 text-xs font-semibold", value === d ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-ink-2")}>
            {fmtDate(d)}
          </button>
        ))}
      </div>
      <p className="mt-1 text-xs text-muted">{tr(v.rule)}. {tr("Another date moves to the next clinic day.")}</p>
    </div>
  );
}

/** A8: units are fixed (°F, mmHg …); a value outside the plausible range is refused, not converted. Blank = not measured. */
function vitalsProblem(v: Record<NumericVital, string>): string | null {
  for (const f of VITAL_FIELDS) {
    if (!v[f.key].trim()) continue;
    const n = Number(v[f.key]);
    if (f.key === "temp_f" && n >= 30 && n <= 45) return "Temperature looks like °C — enter it in °F (for example 98.6)";
    if (!Number.isFinite(n) || n < f.min || n > f.max) return `${f.label}: should be ${f.min}–${f.max} ${f.unit}`;
  }
  if (v.bp_systolic && v.bp_diastolic && Number(v.bp_systolic) <= Number(v.bp_diastolic)) return "BP systolic must be higher than diastolic — check the reading";
  if (!!v.bp_systolic !== !!v.bp_diastolic) return "Enter both BP numbers, or leave both blank";
  return null;
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
