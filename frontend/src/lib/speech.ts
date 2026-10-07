/**
 * Browser speech helpers. TTS read-back uses speechSynthesis; live transcription uses the Web
 * Speech API where present. Production ASR (IndicConformer offline / Bhashini online) runs on the
 * server — the recorded audio is uploaded and deleted after the transcript is confirmed.
 */
import { langByCode } from "@/lib/i18n/languages";

export function canSpeak() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

let voices: SpeechSynthesisVoice[] = [];

function loadVoices() {
  if (!canSpeak()) return;
  voices = window.speechSynthesis.getVoices();
}

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  loadVoices();
  window.speechSynthesis.addEventListener?.("voiceschanged", loadVoices);
}

/** Best installed voice for a language (exact region first, then any voice of that language). */
export function voiceFor(lang: string): SpeechSynthesisVoice | null {
  if (!voices.length) loadVoices();
  const tag = langByCode(lang).bcp47.toLowerCase();
  const base = tag.split("-")[0];
  return voices.find((v) => v.lang.toLowerCase().replace("_", "-") === tag) ?? voices.find((v) => v.lang.toLowerCase().split(/[-_]/)[0] === base) ?? null;
}

/** Whether this device can read text aloud in the language (English always falls back to the default voice). */
export function hasVoice(lang: string): boolean {
  if (lang !== "en" && !voiceFor(lang) && onlineVoice && typeof navigator !== "undefined" && navigator.onLine) return true; // A7: online voice
  return canSpeak() && (lang === "en" || !!voiceFor(lang));
}

/**
 * Reads text aloud in the patient's language. If the device has no voice for that language we do not
 * let an English voice mangle Odia or Hindi text — nothing is spoken and `false` is returned.
 */
export function speak(text: string, lang: string, onEnd?: () => void, opts: { online?: boolean } = {}): boolean {
  const voice = canSpeak() ? voiceFor(lang) : null;
  if (!voice && lang !== "en") {
    // A7: no device voice (Windows has none for Odia). Online voice if allowed; the patient's own words only with consent.
    if (opts.online !== false && onlineVoice && typeof navigator !== "undefined" && navigator.onLine) {
      playOnline(text, lang, onEnd);
      return true;
    }
    onEnd?.();
    return false;
  }
  if (!canSpeak()) {
    onEnd?.();
    return false;
  }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = voice?.lang ?? langByCode(lang).bcp47;
  u.rate = 0.9;
  if (voice) u.voice = voice;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
  return true;
}

/** A7: the server's online voice (Sarvam Bulbul), registered by the API layer so this file has no API import. */
let onlineVoice: ((text: string, lang: string) => Promise<Blob>) | null = null;
let playing: HTMLAudioElement | null = null;

export function setOnlineVoice(fn: ((text: string, lang: string) => Promise<Blob>) | null) {
  onlineVoice = fn;
}

function playOnline(text: string, lang: string, onEnd?: () => void) {
  stopSpeaking();
  onlineVoice!(text, lang)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      playing = a;
      a.onended = a.onerror = () => {
        URL.revokeObjectURL(url);
        onEnd?.();
      };
      return a.play();
    })
    .catch(() => onEnd?.());
}

export function stopSpeaking() {
  playing?.pause();
  playing = null;
  if (canSpeak()) window.speechSynthesis.cancel();
}

interface RecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

export function canRecognise() {
  return typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
}

export interface Recorder {
  stop(): Promise<{ transcript: string; audio: Blob | null }>;
}

/**
 * Starts capturing speech. Resolves the transcript when stopped. Also records raw audio (for the
 * server ASR + audit) when MediaRecorder is available.
 */
export async function startCapture(lang: string, onPartial: (t: string) => void): Promise<Recorder> {
  let transcript = "";
  let rec: RecognitionLike | null = null;
  const W = window as unknown as { SpeechRecognition?: new () => RecognitionLike; webkitSpeechRecognition?: new () => RecognitionLike };
  const Ctor = W.SpeechRecognition ?? W.webkitSpeechRecognition;
  if (Ctor) {
    rec = new Ctor();
    rec.lang = langByCode(lang).bcp47;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let full = "";
      for (let i = 0; i < e.results.length; i++) full += e.results[i][0].transcript + " ";
      transcript = full.trim();
      onPartial(transcript);
    };
    rec.onerror = () => {};
    try {
      rec.start();
    } catch {
      rec = null;
    }
  }

  let media: MediaRecorder | null = null;
  const chunks: Blob[] = [];
  let stream: MediaStream | null = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    media = new MediaRecorder(stream);
    media.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    media.start();
  } catch {
    media = null;
  }

  return {
    stop: () =>
      new Promise((resolve) => {
        rec?.stop();
        const finish = () => {
          stream?.getTracks().forEach((t) => t.stop());
          resolve({ transcript, audio: chunks.length ? new Blob(chunks, { type: media?.mimeType || "audio/webm" }) : null });
        };
        if (media && media.state !== "inactive") {
          media.onstop = () => setTimeout(finish, 250);
          media.stop();
        } else setTimeout(finish, 300);
      }),
  };
}
