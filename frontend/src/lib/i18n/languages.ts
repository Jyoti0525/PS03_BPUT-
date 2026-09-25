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
