/** The 22 scheduled languages of India plus English, with BCP-47 tags for speech APIs. */
export interface Language {
  code: string;
  name: string;
  native: string;
  bcp47: string;
}

export const LANGUAGES: Language[] = [
  { code: "en", name: "English", native: "English", bcp47: "en-IN" },
  { code: "hi", name: "Hindi", native: "हिन्दी", bcp47: "hi-IN" },
  { code: "or", name: "Odia", native: "ଓଡ଼ିଆ", bcp47: "or-IN" },
  { code: "bn", name: "Bengali", native: "বাংলা", bcp47: "bn-IN" },
  { code: "te", name: "Telugu", native: "తెలుగు", bcp47: "te-IN" },
  { code: "ta", name: "Tamil", native: "தமிழ்", bcp47: "ta-IN" },
  { code: "mr", name: "Marathi", native: "मराठी", bcp47: "mr-IN" },
  { code: "gu", name: "Gujarati", native: "ગુજરાતી", bcp47: "gu-IN" },
  { code: "kn", name: "Kannada", native: "ಕನ್ನಡ", bcp47: "kn-IN" },
  { code: "ml", name: "Malayalam", native: "മലയാളം", bcp47: "ml-IN" },
  { code: "pa", name: "Punjabi", native: "ਪੰਜਾਬੀ", bcp47: "pa-IN" },
  { code: "as", name: "Assamese", native: "অসমীয়া", bcp47: "as-IN" },
  { code: "ur", name: "Urdu", native: "اردو", bcp47: "ur-IN" },
  { code: "mai", name: "Maithili", native: "मैथिली", bcp47: "mai-IN" },
  { code: "sat", name: "Santali", native: "ᱥᱟᱱᱛᱟᱲᱤ", bcp47: "sat-IN" },
  { code: "ks", name: "Kashmiri", native: "کٲشُر", bcp47: "ks-IN" },
  { code: "ne", name: "Nepali", native: "नेपाली", bcp47: "ne-IN" },
  { code: "sd", name: "Sindhi", native: "سنڌي", bcp47: "sd-IN" },
  { code: "kok", name: "Konkani", native: "कोंकणी", bcp47: "kok-IN" },
  { code: "doi", name: "Dogri", native: "डोगरी", bcp47: "doi-IN" },
  { code: "mni", name: "Manipuri", native: "মৈতৈলোন্", bcp47: "mni-IN" },
  { code: "brx", name: "Bodo", native: "बड़ो", bcp47: "brx-IN" },
  { code: "sa", name: "Sanskrit", native: "संस्कृतम्", bcp47: "sa-IN" },
];

export const langByCode = (code: string) => LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];

/**
 * Speech recognition measured on public speech with human transcripts (docs/EVALUATION.md): FLEURS read speech, and
 * IndicVoices (CC BY 4.0, natural speech) for the eight languages FLEURS lacks (brx doi kok ks mai mni sa sat).
 * Any language not listed is unmeasured: the kiosk says so, and the health worker checks the transcript.
 */
export const ASR_MEASURED: Record<string, { wer: number; clips: number }> = {
  as: { wer: 23.1, clips: 25 },
  bn: { wer: 11.5, clips: 25 },
  gu: { wer: 15.9, clips: 25 },
  hi: { wer: 10.7, clips: 25 },
  kn: { wer: 20.6, clips: 25 },
  ml: { wer: 20.7, clips: 25 },
  mr: { wer: 21.3, clips: 25 },
  ne: { wer: 29.1, clips: 25 },
  or: { wer: 21.6, clips: 25 },
  pa: { wer: 14.2, clips: 25 },
  ta: { wer: 38.1, clips: 25 },
  te: { wer: 31.5, clips: 25 },
  ur: { wer: 25.2, clips: 25 },
  brx: { wer: 15.6, clips: 21 },
  doi: { wer: 25.4, clips: 25 },
  kok: { wer: 33.0, clips: 23 },
  ks: { wer: 40.4, clips: 23 },
  mai: { wer: 28.1, clips: 25 },
  mni: { wer: 14.2, clips: 25 },
  sa: { wer: 11.4, clips: 23 },
  sat: { wer: 24.7, clips: 23 },
  // sd left out: the model writes Sindhi in Devanagari and FLEURS in Arabic script, so its WER measures the script.
};
