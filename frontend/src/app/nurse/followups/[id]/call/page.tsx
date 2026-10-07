"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Bot, Mic, MicOff, Phone, PhoneCall, PhoneOff, Send, ShieldAlert, Siren, UserRound, Volume2, CheckCircle2, Info } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, CardHeader, ErrorNote, Input, Select, Spinner, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { hasVoice, speak, startCapture, stopSpeaking } from "@/lib/speech";
import { langByCode } from "@/lib/i18n/languages";
import type { Call, CallLanguage, Followup } from "@/lib/types";

type Lang = CallLanguage;
// What a tapped answer says, in the call's language (the English goes alongside so the rules read both).
const QUICK: Record<Lang, { yes: string; no: string; unsure: string }> = {
  en: { yes: "Yes", no: "No", unsure: "Not sure" },
  hi: { yes: "हाँ", no: "नहीं", unsure: "पता नहीं" },
  or: { yes: "ହଁ", no: "ନା", unsure: "ଜାଣିନି" },
  bn: { yes: "হ্যাঁ", no: "না", unsure: "জানি না" },
  ta: { yes: "ஆம்", no: "இல்லை", unsure: "தெரியாது" },
  te: { yes: "అవును", no: "లేదు", unsure: "తెలియదు" },
  gu: { yes: "હા", no: "ના", unsure: "ખબર નથી" },
  kn: { yes: "ಹೌದು", no: "ಇಲ್ಲ", unsure: "ಗೊತ್ತಿಲ್ಲ" },
  ml: { yes: "അതെ", no: "ഇല്ല", unsure: "അറിയില്ല" },
  mr: { yes: "हो", no: "नाही", unsure: "माहीत नाही" },
  pa: { yes: "ਹਾਂ", no: "ਨਹੀਂ", unsure: "ਪਤਾ ਨਹੀਂ" },
};
const CALL_LANGS = Object.keys(QUICK) as Lang[];
const langName = (l: string) => langByCode(l).native;

const OUTCOME: Record<NonNullable<Call["outcome"]>, { title: string; body: string; tone: "crit" | "semi" | "rout" | "neutral" }> = {
  danger_sign: { title: "Danger sign — call ended, a person paged", body: "The medical officer and the assigned health worker have an alert to phone back now. The agent said nothing about what the sign may mean.", tone: "crit" },
  unclear: { title: "No clear answer to a danger-sign question — a person must call", body: "Unknown is never normal: the medical officer and the assigned health worker have an alert.", tone: "semi" },
  completed: { title: "No danger sign reported", body: "An automated call is weak evidence: people often give the safe answer to an unfamiliar voice. The follow-up stays open until the visit.", tone: "rout" },
  message_left: { title: "Message left with someone else", body: "Nothing about health was said. The follow-up stays open.", tone: "neutral" },
  no_answer: { title: "No answer", body: "Recorded as an attempt. Try again later or visit.", tone: "neutral" },
  hung_up: { title: "Call cut off", body: "The questions were not finished. Try again or visit.", tone: "neutral" },
};

/** E6: a reminder call, simulated in the browser. The agent's lines are fixed text; the rules read each answer. */
export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const { tr } = usePrefs();
  const fu = useAsync(async () => (await api.listFollowups("all")).find((f) => f.id === id) ?? null, [id]);
  const past = useAsync(() => api.listCalls(id), [id]);
  const tel = useAsync(() => api.telephonyStatus(), []);
  const [picked, setCall] = useState<Call | null>(null);
  // A call still open (after a page reload) is resumed
  const call = picked ?? past.data?.find((c) => c.status === "active") ?? null;
  const [lang, setLang] = useState<Lang | "patient">("patient");
  const [busy, setBusy] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [voiceOn, setVoiceOn] = useState(true);
  const [recording, setRecording] = useState(false);
  const recRef = useRef<Awaited<ReturnType<typeof startCapture>> | null>(null);
  const spoken = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const [voiceFailed, setVoiceFailed] = useState(false);

  function silence() {
    stopSpeaking();
    audio.current?.pause();
    audio.current = null;
  }

  // A real phone call runs on Twilio's side: follow it here until it ends
  const ringing = call?.channel === "phone" && call.status === "active" ? call.id : null;
  useEffect(() => {
    if (!ringing) return;
    const t = window.setInterval(async () => {
      try {
        const c = await api.getCall(ringing);
        setCall(c);
        if (c.status === "ended") {
          past.reload();
          fu.reload();
        }
      } catch {
        /* the next poll tries again */
      }
    }, 2000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ringing]);

  // Read each new agent line aloud: Sarvam's voice when the server has it, else the device's own voice.
  // On a phone call the patient hears it on the phone, not here.
  useEffect(() => {
    if (!call) return;
    const lines = call.turns.filter((t) => t.who === "agent");
    if (lines.length > spoken.current) {
      spoken.current = lines.length;
      const i = call.turns.lastIndexOf(lines[lines.length - 1]);
      const text = call.turns[i].text;
      if (voiceOn && call.operator === "agent" && call.channel !== "phone") {
        silence();
        if (call.voice === "sarvam") {
          api.callAudio(call.id, i)
            .then((blob) => {
              const url = URL.createObjectURL(blob);
              const a = new Audio(url);
              a.onended = () => URL.revokeObjectURL(url);
              audio.current = a;
              return a.play();
            })
            .catch(() => {
              setVoiceFailed(true);
              speak(text, call.language);
            });
        } else speak(text, call.language);
      }
    }
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [call, voiceOn]);
  useEffect(() => () => silence(), []);

  async function run(label: string, fn: () => Promise<Call>) {
    setBusy(label);
    try {
      const c = await fn();
      setCall(c);
      if (c.status === "ended") {
        past.reload();
        fu.reload();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Failed"), "error");
    } finally {
      setBusy(null);
    }
  }

  const start = (operator: Call["operator"], channel: Call["channel"] = "browser") => {
    spoken.current = 0;
    return run(channel === "phone" ? "phone" : "start", () => api.startCall(id, { operator, channel, ...(lang !== "patient" ? { language: lang } : {}) }));
  };
  const answer = (text: string, original?: string) => call && run("answer", () => api.callAnswer(call.id, text, original));

  async function toggleMic() {
    if (!call) return;
    if (!recording) {
      silence();
      try {
        recRef.current = await startCapture(call.language, () => {});
        setRecording(true);
      } catch {
        toast(tr("Microphone not available — type or tap instead"), "error");
      }
      return;
    }
    setRecording(false);
    const r = await recRef.current?.stop();
    recRef.current = null;
    let original = r?.transcript?.trim() ?? "";
    let english = original;
    if (r?.audio) {
      setBusy("transcribe");
      try {
        const t = await api.transcribe(r.audio, call.language);
        original = t.text;
        english = t.translation?.text ?? t.text;
      } catch (e) {
        if (e instanceof ApiError && e.status === 422) toast(e.message, "error");
      } finally {
        setBusy(null);
      }
    }
    if (!original) {
      toast(tr("Could not understand the recording — type or tap the answer"), "error");
      return;
    }
    answer(english, original);
  }

  if (fu.error) return <ErrorNote error={fu.error} onRetry={fu.reload} />;
  if (fu.loading && !fu.data) return <Spinner />;
  const f = fu.data as Followup | null;
  if (!f) return <ErrorNote error={new Error(tr("Follow-up not found"))} />;
  const active = call?.status === "active";
  const q = QUICK[call?.language ?? "en"];
  const human = f.who_calls.who === "human";

  return (
    <div className="mx-auto max-w-5xl">
      <Link href="/nurse/followups" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> {tr("Follow-ups")}</Link>
      <PageHeader
        title={tr("Reminder call — {n}", { n: f.patient_name })}
        subtitle={tr("Simulated: no phone call is made in this build. The agent's lines are shown and read aloud here; type, tap or speak what the patient says.")}
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader
            icon={call?.operator === "human" ? <UserRound className="size-4" /> : <Bot className="size-4" />}
            title={call ? (call.operator === "agent" ? tr("Agent call") : tr("A person calls, reading the script")) : tr("Start the call")}
            subtitle={call ? `${langName(call.language)} · ${call.audience === "patient" ? tr("speaking to the patient") : tr("someone else — nothing about health is said")}` : `${f.phone ?? ""}`}
            action={
              call && (
                <button className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink" onClick={() => { setVoiceOn(!voiceOn); silence(); }}>
                  <Volume2 className="size-4" /> {voiceOn ? tr("Voice on") : tr("Voice off")}
                </button>
              )
            }
          />
          {!call ? (
            <div className="space-y-4 p-4">
              <div className={cx("rounded-xl border p-3 text-sm", human ? "border-semi-line bg-semi-bg text-semi" : "border-teal-200 bg-teal-50 text-teal-800")}>
                <p className="font-semibold">{human ? tr("A person must call, not the agent") : tr("The agent may call")}</p>
                <p>{tr(f.who_calls.why)}</p>
              </div>
              <div>
                <p className="mb-1 text-sm font-medium text-ink">{tr("Language of the call")}</p>
                <Select value={lang} onChange={(e) => setLang(e.target.value as Lang | "patient")} className="max-w-xs">
                  <option value="patient">{tr("Patient's language")}</option>
                  {CALL_LANGS.map((l) => <option key={l} value={l}>{langName(l)} · {langByCode(l).name}</option>)}
                </Select>
              </div>
              <div className="flex flex-wrap gap-2">
                {!human && tel.data?.calls && (
                  <Button variant="teal" icon={<PhoneCall className="size-4" />} loading={busy === "phone"} onClick={() => start("agent", "phone")}>
                    {tr("Ring the demo phone {n}", { n: tel.data.demo_to ?? "" })}
                  </Button>
                )}
                {!human && <Button variant={tel.data?.calls ? "secondary" : "teal"} icon={<Phone className="size-4" />} loading={busy === "start"} onClick={() => start("agent")}>{tr("Start agent call")}</Button>}
                <Button variant={human ? "teal" : "secondary"} icon={<UserRound className="size-4" />} loading={busy === "start"} onClick={() => start("human")}>{tr("I will call and read the script")}</Button>
              </div>
            </div>
          ) : (
            <div className="p-4">
              <ol className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
                {call.turns.map((t, i) => (
                  <li key={i} className={cx("flex", t.who === "patient" ? "justify-end" : "justify-start")}>
                    <div className={cx("max-w-[85%] rounded-2xl px-3 py-2 text-sm",
                      t.who === "agent" ? "rounded-bl-sm bg-canvas text-ink" : t.findings?.length ? "rounded-br-sm bg-crit-bg text-crit" : "rounded-br-sm bg-teal-700 text-white")}>
                      <p>{t.text}</p>
                      {t.text_en && call.language !== "en" && <p className={cx("mt-0.5 text-xs", t.who === "agent" ? "text-muted" : "opacity-80")}>{t.text_en}</p>}
                      {t.unread && <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide opacity-80">{tr("Not read: no English translation")}</p>}
                      {t.who === "patient" && (t.findings?.length || t.heard) && (
                        <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide opacity-80">
                          {t.findings?.length ? `${tr("danger sign")}: ${t.findings.join(", ").replaceAll("_", " ")}` : `${tr("heard")}: ${tr(t.heard ?? "")}`}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
                <div ref={bottom} />
              </ol>
              {call.operator === "agent" && voiceOn && call.voice === "sarvam" && !voiceFailed && call.channel !== "phone" && (
                <p className="mt-2 text-xs text-muted">{tr("Voice: Sarvam Bulbul (online). It speaks the fixed line shown, nothing else.")}</p>
              )}
              {call.operator === "agent" && voiceOn && call.channel !== "phone" && (call.voice !== "sarvam" || voiceFailed) && !hasVoice(call.language) && (
                <p className="mt-2 text-xs text-muted">{tr("This device has no {l} voice, so the line is shown but not spoken.", { l: langName(call.language) })}</p>
              )}
              {active && call.channel === "phone" ? (
                <div className="mt-4 space-y-3 border-t border-line pt-3">
                  <p className="flex items-center gap-2 text-sm text-ink-2">
                    <PhoneCall className="size-4 animate-pulse text-teal-700" />
                    {call.notes?.phone?.answered
                      ? tr("On the phone: the patient answers on the keypad (1 yes, 2 no, 3 not sure). The last question is recorded.")
                      : tr("Ringing the demo phone {n}…", { n: call.notes?.phone?.to ?? "" })}
                  </p>
                  <Button size="sm" variant="ghost" icon={<PhoneOff className="size-4" />} disabled={!!busy} onClick={() => run("end", () => api.endCall(call.id, "hung_up"))}>{tr("Hang up")}</Button>
                </div>
              ) : active ? (
                <div className="mt-4 space-y-3 border-t border-line pt-3">
                  {call.expects === "yes_no" && (
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" disabled={!!busy} onClick={() => answer("Yes", q.yes)}>{q.yes}</Button>
                      <Button variant="secondary" disabled={!!busy} onClick={() => answer("No", q.no)}>{q.no}</Button>
                      <Button variant="secondary" disabled={!!busy} onClick={() => answer("Not sure", q.unsure)}>{q.unsure}</Button>
                    </div>
                  )}
                  <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (typed.trim()) { answer(typed.trim()); setTyped(""); } }}>
                    <Input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={tr("Type what the patient said, in any language")} />
                    <Button type="submit" variant="primary" icon={<Send className="size-4" />} loading={busy === "answer"} disabled={!typed.trim()}>{tr("Send")}</Button>
                    <Button type="button" variant={recording ? "danger" : "outline"} icon={recording ? <MicOff className="size-4" /> : <Mic className="size-4" />} loading={busy === "transcribe"} onClick={toggleMic}>
                      {recording ? tr("Stop") : tr("Speak")}
                    </Button>
                  </form>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="ghost" icon={<PhoneOff className="size-4" />} disabled={!!busy} onClick={() => run("end", () => api.endCall(call.id, "no_answer"))}>{tr("No answer")}</Button>
                    <Button size="sm" variant="ghost" icon={<PhoneOff className="size-4" />} disabled={!!busy} onClick={() => run("end", () => api.endCall(call.id, "hung_up"))}>{tr("Call cut off")}</Button>
                  </div>
                </div>
              ) : call.outcome && (
                <Outcome call={call} />
              )}
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader icon={<ShieldAlert className="size-4" />} title={tr("What the agent may do")} />
            <ul className="space-y-2 p-4 text-sm text-ink-2">
              <li>{tr("Logistics and yes / no questions only. It never answers with advice: under India's Telemedicine Practice Guidelines 2020 an AI platform may not counsel a patient.")}</li>
              <li>{tr("A danger sign said anywhere ends the call and pages a person. So does “not sure” on a danger-sign question.")}</li>
              <li>{tr("If the last visit was RED, YELLOW or never fully assessed, or the patient chose no AI, a person calls instead.")}</li>
              <li>{tr("On a phone that is not hers, or when someone else answers, nothing about health is said.")}</li>
              <li>{tr("Answers are read by fixed rules, not by a model: the intake word lists in English, Hindi and Odia, and the English translation for other languages. A word like “less” or “a little” counts as not sure.")}</li>
            </ul>
            {call?.sources && (
              <p className="border-t border-line px-4 py-3 text-xs text-muted">{tr("Danger signs from")}: {call.sources.map((s) => s.short).join("; ")}</p>
            )}
          </Card>
          {!!past.data?.filter((c) => c.status === "ended").length && (
            <Card>
              <CardHeader icon={<Info className="size-4" />} title={tr("Earlier calls")} />
              <ul className="divide-y divide-line text-sm">
                {past.data.filter((c) => c.status === "ended").map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-2 px-4 py-2">
                    <button className="text-left text-ink hover:underline" onClick={() => setCall(c)}>{timeAgo(c.started_at)} · {c.operator === "agent" ? tr("agent") : tr("person")}</button>
                    <Badge tone={c.outcome ? OUTCOME[c.outcome].tone : "neutral"}>{tr((c.outcome ?? "").replace("_", " "))}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Outcome({ call }: { call: Call }) {
  const { tr } = usePrefs();
  const o = OUTCOME[call.outcome!];
  const box = { crit: "border-crit-line bg-crit-bg text-crit", semi: "border-semi-line bg-semi-bg text-semi", rout: "border-rout-line bg-rout-bg text-rout", neutral: "border-line bg-canvas text-ink" }[o.tone];
  return (
    <div className={cx("mt-4 rounded-xl border p-4 text-sm", box)}>
      <p className="flex items-center gap-2 font-semibold">{o.tone === "crit" ? <Siren className="size-5" /> : <CheckCircle2 className="size-5" />} {tr(o.title)}</p>
      <p className="mt-1">{tr(o.body)}</p>
      {call.red_flags?.map((f, i) => (
        <p key={i} className="mt-1"><span className="font-semibold">{tr(f.label)}</span> — <span className="opacity-80">{f.evidence}</span></p>
      ))}
      {call.notes?.flags?.map((n) => <p key={n} className="mt-1">{tr("Noted")}: {tr(n)}</p>)}
      {call.notes?.said && <p className="mt-1">{tr("Also said")}: “{call.notes.said}”</p>}
      {call.notes?.staff_sms?.sent && <p className="mt-1">{tr("Also texted to the demo phone {n} (standing in for the medical officer and the health worker).", { n: call.notes.staff_sms.to ?? "" })}</p>}
      {call.notes?.can_come != null && <p className="mt-1">{call.notes.can_come ? tr("Said they can come this week.") : tr("Said they cannot come this week — a home visit is needed.")}</p>}
    </div>
  );
}
