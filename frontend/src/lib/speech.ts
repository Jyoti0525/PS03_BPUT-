/**
 * Browser speech helpers. TTS read-back uses speechSynthesis; live transcription uses the Web
 * Speech API where present. Production ASR (IndicConformer offline / Bhashini online) runs on the
 * server — the recorded audio is uploaded and deleted after the transcript is confirmed.
 */
import { langByCode } from "@/lib/i18n/languages";

export function canSpeak() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string, lang: string, onEnd?: () => void) {
  if (!canSpeak()) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = langByCode(lang).bcp47;
  u.rate = 0.9;
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang === u.lang) ?? window.speechSynthesis.getVoices().find((v) => v.lang.startsWith(u.lang.slice(0, 2)));
  if (voice) u.voice = voice;
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
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
