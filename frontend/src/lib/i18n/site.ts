/** Public website copy in the three fully translated interface languages. */
import { usePrefs } from "@/components/providers";

type Item = { title: string; body: string };

export interface SiteCopy {
  nav: { features: string; how: string; scenarios: string; safety: string; signIn: string; getStarted: string; openWorkspace: string };
  hero: {
    badge: string;
    title: [string, string, string];
    body: string;
    primary: string;
    secondary: string;
    stats: [string, string, string];
  };
  queue: {
    title: string;
    critical: string;
    semi: string;
    routine: string;
    rules: string;
    rulesBody: string;
    status: string;
    flagged: string;
    footerLeft: string;
    footerRight: string;
    patients: { name: string; detail: string; u: "red" | "yellow" | "green" }[];
  };
  facilities: string[];
  features: { eyebrow: string; title: [string, string]; body: string; items: Item[] };
  how: { eyebrow: string; title: [string, string]; body: string; steps: Item[] };
  scenarios: { eyebrow: string; title: [string, string]; items: (Item & { tag: string })[] };
  safety: { eyebrow: string; title: [string, string]; items: Item[]; noticeTitle: string; noticeLead: string; notice: string };
  cta: { title: string; body: string; primary: string; secondary: string };
  status: {
    eyebrow: string;
    title: [string, string];
    body: string;
    allOk: string;
    degraded: string;
    offline: string;
    waking: string;
    checking: string;
    demo: string;
    website: string;
    api: string;
    database: string;
    sms: string;
    storage: string;
    online: string;
    asleep: string;
    ready: string;
    notReady: string;
    uptime: string;
    checked: string;
    checkNow: string;
    wake: string;
    restart: string;
    sleepHint: string;
  };
  footer: {
    blurb: string;
    badges: [string, string];
    product: string;
    teams: string;
    legal: string;
    teamLinks: [string, string, string, string];
    legalLinks: [string, string, string, string];
    kiosk: string;
    rights: string;
    note: string;
  };
}

const en: SiteCopy = {
  nav: { features: "Features", how: "How it works", scenarios: "Scenarios", safety: "Safety", signIn: "Sign in", getStarted: "Get started", openWorkspace: "Open workspace" },
  hero: {
    badge: "Healthcare triage assistant for India",
    title: ["Smarter triage,", "faster care", "across India"],
    body: "Jeevia helps doctors, nurses and health workers at government hospitals, PHCs and health camps collect, summarise and prioritise patient symptoms — safely and in the patient's own language.",
    primary: "Get started",
    secondary: "See how it works",
    stats: ["Indian languages", "Target review time", "Human reviewed"],
  },
  queue: {
    title: "Today's triage queue",
    critical: "Critical",
    semi: "Semi-urgent",
    routine: "Routine",
    rules: "Rules engine",
    rulesBody: "AIIMS ATP · IMCI",
    status: "Queue status",
    flagged: "flagged for review",
    footerLeft: "Structured note",
    footerRight: "Reviewed by Dr. Sharma",
    patients: [
      { name: "Radha Kumari, 42F", detail: "Chest pain · 2h · radiating to arm", u: "red" },
      { name: "Aarav Singh, 3M", detail: "High fever · one convulsion", u: "red" },
      { name: "Mohammed Rafiq, 28M", detail: "Fever 102°F · 3 days · fatigue", u: "yellow" },
      { name: "Lakshmi Devi, 55F", detail: "Diabetic · FBS 310 on lab slip", u: "yellow" },
      { name: "Priya Sharma, 24F", detail: "Mild headache · antenatal check-up", u: "green" },
      { name: "Arjun Nair, 65M", detail: "Chronic diabetes · follow-up", u: "green" },
    ],
  },
  facilities: ["Government hospitals", "Primary health centres", "Public health camps", "Industrial health units", "Campus health centres", "Company clinics"],
  features: {
    eyebrow: "What Jeevia does",
    title: ["Everything a health worker needs,", "nothing they don't"],
    body: "Designed for the realities of Indian healthcare — patchy connectivity, many languages, heavy patient load and scarce specialists.",
    items: [
      { title: "Multimodal symptom intake", body: "Patients speak, type or tap pictures in their own language. The kiosk reads the words back aloud so they can confirm before anything is saved." },
      { title: "Lab report extraction", body: "Photograph a printed or handwritten report. Values are extracted and shown beside the exact cropped region they came from." },
      { title: "Structured triage note", body: "A concise, non-diagnostic summary with timeline, missing information and follow-up questions for the reviewing clinician." },
      { title: "22-language support", body: "Every scheduled Indian language for patient speech, with full screens in English, Hindi and Odia." },
      { title: "Human-review workflow", body: "A red / yellow / green queue from fixed clinical rules. Doctors confirm, override with a written reason, escalate or refer." },
      { title: "Privacy-first design", body: "Consent before intake, role-based access, tamper-evident audit log and automatic deletion of raw audio and photos." },
    ],
  },
  how: {
    eyebrow: "The process",
    title: ["From symptom to", "structured review"],
    body: "Three steps, designed to be reviewed in under four minutes, with the clinician in control throughout.",
    steps: [
      { title: "Patient intake", body: "A health worker unlocks the kiosk. The patient speaks or taps symptoms, uploads reports and answers a few simple follow-up questions — even offline." },
      { title: "Rules + summary", body: "Deterministic AIIMS ATP and IMCI rules set the urgency. The note organises symptoms, vitals and report values, each traced to its source." },
      { title: "Doctor review", body: "The doctor sees a prioritised queue, checks flagged values, confirms or edits the note and decides on referral. The system only supports — never decides." },
    ],
  },
  scenarios: {
    eyebrow: "India-wide scenarios",
    title: ["Built for every", "Indian healthcare setting"],
    items: [
      { tag: "Outpatient", title: "OPD queue triage", body: "Sort a crowded morning OPD so chest pain and breathlessness are seen first, not last." },
      { tag: "Industrial", title: "Occupational screening", body: "Burns, injuries and heat stress at industrial estates. Employers see fitness status only — never records." },
      { tag: "Campus", title: "Campus fever triage", body: "Spot dengue-season warning signs across a hostel population and track who needs a recheck." },
      { tag: "Maternal", title: "Maternal follow-up", body: "Pre-eclampsia red flags, antenatal history and automatic check-up reminders by SMS or voice call." },
      { tag: "Chronic disease", title: "Chronic check-in", body: "Compare today's sugar or BP with earlier visits and show the doctor whether things are getting worse." },
      { tag: "Health camps", title: "Camp screening", body: "Works offline in remote camps. The queue syncs automatically when the connection returns." },
      { tag: "Referral", title: "Referral note preparation", body: "One click turns the reviewed note into a referral for the right higher facility, based on who is on duty." },
    ],
  },
  safety: {
    eyebrow: "Safety & privacy",
    title: ["Safety rules the", "system is built around"],
    items: [
      { title: "Non-diagnostic", body: "Organises what the patient said and brought. Never diagnoses, never prescribes." },
      { title: "Deterministic urgency", body: "Urgency comes only from fixed AIIMS ATP and IMCI rules — never from a language model." },
      { title: "Human in the loop", body: "A qualified reviewer confirms every note. Overrides need a written reason and are logged." },
      { title: "Source traceability", body: "Each extracted value sits beside the report crop or transcript it came from." },
      { title: "Tamper-evident audit", body: "Every view, edit, override and export is recorded in a hash-chained log that cannot be changed." },
      { title: "Minimal retention", body: "Raw audio and photos are deleted automatically. Patients never see triage status." },
    ],
    noticeTitle: "Important safety notice",
    noticeLead: "Jeevia supports triage — it does not replace a clinician.",
    notice: "It organises patient-provided information, highlights urgency signals and speeds up qualified review. It does not diagnose or prescribe. Every output is advisory and must be reviewed by licensed healthcare staff before any clinical decision.",
  },
  cta: { title: "Ready to shorten your queue?", body: "Set up your facility, bind a kiosk tablet and start your first intake in minutes.", primary: "Create an account", secondary: "Open the kiosk" },
  status: {
    eyebrow: "Live system status",
    title: ["Is everything", "up and running?"],
    body: "Checked every 20 seconds from your browser. The API server sleeps after 15 idle minutes to save resources \u2014 wake it with one tap.",
    allOk: "All systems operational",
    degraded: "Partly degraded",
    offline: "Server is asleep or unreachable",
    waking: "Waking the server\u2026",
    checking: "Checking\u2026",
    demo: "Local demo mode \u2014 no server",
    website: "Website",
    api: "API server",
    database: "Database",
    sms: "SMS sign-in codes",
    storage: "Document storage",
    online: "Online",
    asleep: "Asleep",
    ready: "Ready",
    notReady: "Not configured",
    uptime: "up",
    checked: "checked",
    checkNow: "Check now",
    wake: "Wake server",
    restart: "Restart server",
    sleepHint: "Waking usually takes 30\u201360 seconds.",
  },
  footer: {
    blurb: "Multimodal triage assistant for government and institutional health facilities across India.",
    badges: ["Human reviewed", "Non-diagnostic"],
    product: "Product",
    teams: "For teams",
    legal: "Safety & privacy",
    teamLinks: ["Doctors", "Nurses & ANMs", "Facility admins", "Employers"],
    legalLinks: ["Clinical disclaimer", "Privacy & consent", "Data retention", "Audit log"],
    kiosk: "Patient kiosk",
    rights: "Jeevia. All rights reserved.",
    note: "All health-related outputs are advisory and reviewer-facing only.",
  },
};

const hi: SiteCopy = {
  nav: { features: "विशेषताएँ", how: "कैसे काम करता है", scenarios: "उपयोग", safety: "सुरक्षा", signIn: "साइन इन", getStarted: "शुरू करें", openWorkspace: "वर्कस्पेस खोलें" },
  hero: {
    badge: "भारत के लिए स्वास्थ्य ट्रायेज सहायक",
    title: ["बेहतर ट्रायेज,", "जल्दी इलाज", "पूरे भारत में"],
    body: "जीविया सरकारी अस्पतालों, PHC और स्वास्थ्य शिविरों में डॉक्टरों, नर्सों और स्वास्थ्य कर्मियों को मरीज़ के लक्षण उसकी अपनी भाषा में सुरक्षित रूप से दर्ज करने, सारांश बनाने और प्राथमिकता तय करने में मदद करता है।",
    primary: "शुरू करें",
    secondary: "देखें कैसे काम करता है",
    stats: ["भारतीय भाषाएँ", "लक्ष्य समीक्षा समय", "मानव द्वारा समीक्षा"],
  },
  queue: {
    title: "आज की ट्रायेज कतार",
    critical: "गंभीर",
    semi: "अर्ध-आपात",
    routine: "सामान्य",
    rules: "नियम इंजन",
    rulesBody: "AIIMS ATP · IMCI",
    status: "कतार की स्थिति",
    flagged: "समीक्षा हेतु चिह्नित",
    footerLeft: "संरचित नोट",
    footerRight: "डॉ. शर्मा द्वारा समीक्षा",
    patients: [
      { name: "राधा कुमारी, 42 म", detail: "सीने में दर्द · 2 घंटे · हाथ तक", u: "red" },
      { name: "आरव सिंह, 3 पु", detail: "तेज़ बुखार · एक बार दौरा", u: "red" },
      { name: "मोहम्मद रफ़ीक़, 28 पु", detail: "बुखार 102°F · 3 दिन · थकान", u: "yellow" },
      { name: "लक्ष्मी देवी, 55 म", detail: "मधुमेह · रिपोर्ट में FBS 310", u: "yellow" },
      { name: "प्रिया शर्मा, 24 म", detail: "हल्का सिरदर्द · प्रसवपूर्व जांच", u: "green" },
      { name: "अर्जुन नायर, 65 पु", detail: "पुराना मधुमेह · फ़ॉलो-अप", u: "green" },
    ],
  },
  facilities: ["सरकारी अस्पताल", "प्राथमिक स्वास्थ्य केंद्र", "सार्वजनिक स्वास्थ्य शिविर", "औद्योगिक स्वास्थ्य इकाइयाँ", "कैंपस स्वास्थ्य केंद्र", "कंपनी क्लिनिक"],
  features: {
    eyebrow: "जीविया क्या करता है",
    title: ["स्वास्थ्य कर्मी को जो चाहिए,", "बस वही"],
    body: "भारतीय स्वास्थ्य व्यवस्था की सच्चाई के लिए बना — कमज़ोर नेटवर्क, कई भाषाएँ, भारी भीड़ और कम विशेषज्ञ।",
    items: [
      { title: "बहु-माध्यम लक्षण दर्ज", body: "मरीज़ अपनी भाषा में बोलते, लिखते या चित्र चुनते हैं। कियोस्क शब्द दोहराकर सुनाता है ताकि सहेजने से पहले पुष्टि हो सके।" },
      { title: "लैब रिपोर्ट से मान", body: "छपी या हाथ से लिखी रिपोर्ट की फ़ोटो लें। हर मान उसी हिस्से के साथ दिखता है जहाँ से पढ़ा गया।" },
      { title: "संरचित ट्रायेज नोट", body: "समय-रेखा, छूटी जानकारी और अगले प्रश्नों के साथ संक्षिप्त सारांश — निदान नहीं।" },
      { title: "22 भाषाओं का समर्थन", body: "मरीज़ की बोली के लिए सभी अनुसूचित भारतीय भाषाएँ; पूरी स्क्रीन अंग्रेज़ी, हिंदी और ओड़िया में।" },
      { title: "मानव समीक्षा प्रक्रिया", body: "तय क्लिनिकल नियमों से लाल / पीली / हरी कतार। डॉक्टर पुष्टि करते हैं, लिखित कारण से बदलते हैं, आगे भेजते हैं।" },
      { title: "गोपनीयता पहले", body: "दर्ज करने से पहले सहमति, भूमिका-आधारित पहुँच, बदलाव-रोधी ऑडिट लॉग और आवाज़ व फ़ोटो का अपने-आप हटना।" },
    ],
  },
  how: {
    eyebrow: "प्रक्रिया",
    title: ["लक्षण से", "संरचित समीक्षा तक"],
    body: "तीन चरण, चार मिनट से कम में समीक्षा के लिए — हर समय नियंत्रण डॉक्टर के पास।",
    steps: [
      { title: "मरीज़ की जानकारी", body: "स्वास्थ्य कर्मी कियोस्क खोलते हैं। मरीज़ बोलकर या चित्र चुनकर लक्षण बताते हैं, रिपोर्ट जोड़ते हैं — बिना इंटरनेट भी।" },
      { title: "नियम + सारांश", body: "AIIMS ATP और IMCI के तय नियम तात्कालिकता तय करते हैं। नोट में हर मान अपने स्रोत के साथ होता है।" },
      { title: "डॉक्टर की समीक्षा", body: "डॉक्टर प्राथमिकता वाली कतार देखते हैं, चिह्नित मान जाँचते हैं, नोट की पुष्टि करते हैं और रेफ़रल तय करते हैं।" },
    ],
  },
  scenarios: {
    eyebrow: "पूरे भारत के लिए",
    title: ["हर तरह की", "स्वास्थ्य सुविधा के लिए"],
    items: [
      { tag: "ओपीडी", title: "ओपीडी कतार ट्रायेज", body: "भीड़ भरी ओपीडी में सीने का दर्द और साँस की तकलीफ़ पहले देखी जाए।" },
      { tag: "औद्योगिक", title: "व्यावसायिक जांच", body: "औद्योगिक क्षेत्रों में जलना, चोट और गर्मी का असर। नियोक्ता को केवल फ़िटनेस स्थिति दिखती है।" },
      { tag: "कैंपस", title: "कैंपस बुखार ट्रायेज", body: "छात्रावासों में डेंगू के मौसम के चेतावनी संकेत पहचानें।" },
      { tag: "मातृत्व", title: "मातृ स्वास्थ्य फ़ॉलो-अप", body: "प्री-एक्लेम्पसिया के संकेत और SMS या कॉल से जांच के रिमाइंडर।" },
      { tag: "पुरानी बीमारी", title: "नियमित जांच", body: "आज की शुगर या BP की पिछली मुलाक़ातों से तुलना।" },
      { tag: "शिविर", title: "शिविर जांच", body: "दूर-दराज़ शिविरों में बिना इंटरनेट काम करता है, बाद में अपने-आप सिंक।" },
      { tag: "रेफ़रल", title: "रेफ़रल नोट", body: "एक क्लिक में सही बड़े अस्पताल के लिए रेफ़रल नोट।" },
    ],
  },
  safety: {
    eyebrow: "सुरक्षा व गोपनीयता",
    title: ["सुरक्षा के नियम", "जिन पर यह बना है"],
    items: [
      { title: "निदान नहीं", body: "मरीज़ ने जो बताया उसे व्यवस्थित करता है। न निदान, न दवा।" },
      { title: "तय नियमों से तात्कालिकता", body: "तात्कालिकता केवल AIIMS ATP और IMCI नियमों से — भाषा मॉडल से कभी नहीं।" },
      { title: "मानव नियंत्रण", body: "हर नोट योग्य समीक्षक देखते हैं। बदलाव के लिए लिखित कारण ज़रूरी है।" },
      { title: "स्रोत सहित मान", body: "हर मान रिपोर्ट के उसी हिस्से या बोले गए शब्दों के साथ दिखता है।" },
      { title: "बदलाव-रोधी ऑडिट", body: "हर देखना, बदलना और निर्यात ऐसे लॉग में दर्ज जो बदला नहीं जा सकता।" },
      { title: "न्यूनतम भंडारण", body: "आवाज़ और फ़ोटो अपने-आप हटते हैं। मरीज़ को ट्रायेज स्थिति नहीं दिखती।" },
    ],
    noticeTitle: "महत्वपूर्ण सुरक्षा सूचना",
    noticeLead: "जीविया ट्रायेज में मदद करता है — डॉक्टर की जगह नहीं लेता।",
    notice: "यह मरीज़ की दी जानकारी को व्यवस्थित करता है और तात्कालिकता के संकेत दिखाता है। यह निदान या दवा नहीं देता। हर परिणाम सलाह मात्र है और किसी भी निर्णय से पहले लाइसेंस प्राप्त स्वास्थ्य कर्मी द्वारा देखा जाना चाहिए।",
  },
  cta: { title: "अपनी कतार छोटी करें", body: "अपनी सुविधा सेट करें, कियोस्क टैबलेट जोड़ें और कुछ ही मिनटों में पहली जानकारी दर्ज करें।", primary: "खाता बनाएँ", secondary: "कियोस्क खोलें" },
  status: {
    eyebrow: "\u0938\u093f\u0938\u094d\u091f\u092e \u0915\u0940 \u0932\u093e\u0907\u0935 \u0938\u094d\u0925\u093f\u0924\u093f",
    title: ["क्या सब कुछ", "चल रहा है?"],
    body: "\u0906\u092a\u0915\u0947 \u092c\u094d\u0930\u093e\u0909\u091c\u093c\u0930 \u0938\u0947 \u0939\u0930 20 \u0938\u0947\u0915\u0902\u0921 \u092e\u0947\u0902 \u091c\u093e\u0901\u091a\u0964 API \u0938\u0930\u094d\u0935\u0930 15 \u092e\u093f\u0928\u091f \u0916\u093e\u0932\u0940 \u0930\u0939\u0928\u0947 \u092a\u0930 \u0938\u094b \u091c\u093e\u0924\u093e \u0939\u0948 \u2014 \u090f\u0915 \u091f\u0948\u092a \u0938\u0947 \u091c\u0917\u093e\u090f\u0901\u0964",
    allOk: "\u0938\u092d\u0940 \u0938\u093f\u0938\u094d\u091f\u092e \u091a\u093e\u0932\u0942 \u0939\u0948\u0902",
    degraded: "\u0906\u0902\u0936\u093f\u0915 \u0938\u092e\u0938\u094d\u092f\u093e",
    offline: "\u0938\u0930\u094d\u0935\u0930 \u0938\u094b \u0930\u0939\u093e \u0939\u0948 \u092f\u093e \u092a\u0939\u0941\u0901\u091a \u0938\u0947 \u092c\u093e\u0939\u0930 \u0939\u0948",
    waking: "\u0938\u0930\u094d\u0935\u0930 \u091c\u0917\u093e\u092f\u093e \u091c\u093e \u0930\u0939\u093e \u0939\u0948\u2026",
    checking: "\u091c\u093e\u0901\u091a \u0939\u094b \u0930\u0939\u0940 \u0939\u0948\u2026",
    demo: "\u0932\u094b\u0915\u0932 \u0921\u0947\u092e\u094b \u092e\u094b\u0921 \u2014 \u0938\u0930\u094d\u0935\u0930 \u0928\u0939\u0940\u0902",
    website: "\u0935\u0947\u092c\u0938\u093e\u0907\u091f",
    api: "API \u0938\u0930\u094d\u0935\u0930",
    database: "\u0921\u0947\u091f\u093e\u092c\u0947\u0938",
    sms: "SMS \u0938\u093e\u0907\u0928-\u0907\u0928 \u0915\u094b\u0921",
    storage: "\u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c\u093c \u092d\u0902\u0921\u093e\u0930\u0923",
    online: "\u0911\u0928\u0932\u093e\u0907\u0928",
    asleep: "\u0938\u094b \u0930\u0939\u093e \u0939\u0948",
    ready: "\u0924\u0948\u092f\u093e\u0930",
    notReady: "\u0938\u0947\u091f \u0928\u0939\u0940\u0902",
    uptime: "\u091a\u093e\u0932\u0942",
    checked: "\u091c\u093e\u0901\u091a\u093e",
    checkNow: "\u0905\u092d\u0940 \u091c\u093e\u0901\u091a\u0947\u0902",
    wake: "\u0938\u0930\u094d\u0935\u0930 \u091c\u0917\u093e\u090f\u0901",
    restart: "\u0938\u0930\u094d\u0935\u0930 \u0930\u0940\u0938\u094d\u091f\u093e\u0930\u094d\u091f \u0915\u0930\u0947\u0902",
    sleepHint: "\u091c\u0917\u093e\u0928\u0947 \u092e\u0947\u0902 \u0906\u092e\u0924\u094c\u0930 \u092a\u0930 30\u201360 \u0938\u0947\u0915\u0902\u0921 \u0932\u0917\u0924\u0947 \u0939\u0948\u0902\u0964",
  },
  footer: {
    blurb: "भारत भर के सरकारी और संस्थागत स्वास्थ्य केंद्रों के लिए बहु-माध्यम ट्रायेज सहायक।",
    badges: ["मानव समीक्षा", "निदान नहीं"],
    product: "उत्पाद",
    teams: "टीमों के लिए",
    legal: "सुरक्षा व गोपनीयता",
    teamLinks: ["डॉक्टर", "नर्स व ANM", "सुविधा प्रबंधक", "नियोक्ता"],
    legalLinks: ["क्लिनिकल अस्वीकरण", "गोपनीयता व सहमति", "डेटा भंडारण", "ऑडिट लॉग"],
    kiosk: "मरीज़ कियोस्क",
    rights: "जीविया। सर्वाधिकार सुरक्षित।",
    note: "स्वास्थ्य संबंधी हर परिणाम केवल सलाह है और समीक्षक के लिए है।",
  },
};

const or: SiteCopy = {
  nav: { features: "ବୈଶିଷ୍ଟ୍ୟ", how: "କିପରି କାମ କରେ", scenarios: "ବ୍ୟବହାର", safety: "ସୁରକ୍ଷା", signIn: "ସାଇନ୍ ଇନ୍", getStarted: "ଆରମ୍ଭ କରନ୍ତୁ", openWorkspace: "ୱର୍କସ୍ପେସ୍ ଖୋଲନ୍ତୁ" },
  hero: {
    badge: "ଭାରତ ପାଇଁ ସ୍ୱାସ୍ଥ୍ୟ ଟ୍ରାଇଏଜ୍ ସହାୟକ",
    title: ["ଉନ୍ନତ ଟ୍ରାଇଏଜ୍,", "ଶୀଘ୍ର ଚିକିତ୍ସା", "ସାରା ଭାରତରେ"],
    body: "ଜୀବିଆ ସରକାରୀ ଡାକ୍ତରଖାନା, PHC ଓ ସ୍ୱାସ୍ଥ୍ୟ ଶିବିରରେ ଡାକ୍ତର, ନର୍ସ ଓ ସ୍ୱାସ୍ଥ୍ୟକର୍ମୀଙ୍କୁ ରୋଗୀଙ୍କ ଲକ୍ଷଣ ତାଙ୍କ ନିଜ ଭାଷାରେ ସୁରକ୍ଷିତ ଭାବେ ସଂଗ୍ରହ, ସାରାଂଶ ଓ ପ୍ରାଥମିକତା ନିର୍ଣ୍ଣୟରେ ସାହାଯ୍ୟ କରେ।",
    primary: "ଆରମ୍ଭ କରନ୍ତୁ",
    secondary: "କିପରି କାମ କରେ ଦେଖନ୍ତୁ",
    stats: ["ଭାରତୀୟ ଭାଷା", "ଲକ୍ଷ୍ୟ ସମୀକ୍ଷା ସମୟ", "ମଣିଷ ଦ୍ୱାରା ସମୀକ୍ଷା"],
  },
  queue: {
    title: "ଆଜିର ଟ୍ରାଇଏଜ୍ ଧାଡ଼ି",
    critical: "ଗୁରୁତର",
    semi: "ଅର୍ଦ୍ଧ-ଜରୁରୀ",
    routine: "ସାଧାରଣ",
    rules: "ନିୟମ ଇଞ୍ଜିନ୍",
    rulesBody: "AIIMS ATP · IMCI",
    status: "ଧାଡ଼ି ସ୍ଥିତି",
    flagged: "ସମୀକ୍ଷା ପାଇଁ ଚିହ୍ନିତ",
    footerLeft: "ସଂରଚିତ ନୋଟ୍",
    footerRight: "ଡା. ଶର୍ମାଙ୍କ ସମୀକ୍ଷା",
    patients: [
      { name: "ରାଧା କୁମାରୀ, 42 ମ", detail: "ଛାତି ଯନ୍ତ୍ରଣା · 2 ଘଣ୍ଟା · ହାତ ପର୍ଯ୍ୟନ୍ତ", u: "red" },
      { name: "ଆରବ ସିଂ, 3 ପୁ", detail: "ଅଧିକ ଜ୍ୱର · ଥରେ ଝଟକା", u: "red" },
      { name: "ମହମ୍ମଦ ରଫିକ୍, 28 ପୁ", detail: "ଜ୍ୱର 102°F · 3 ଦିନ · କ୍ଲାନ୍ତି", u: "yellow" },
      { name: "ଲକ୍ଷ୍ମୀ ଦେବୀ, 55 ମ", detail: "ମଧୁମେହ · ରିପୋର୍ଟରେ FBS 310", u: "yellow" },
      { name: "ପ୍ରିୟା ଶର୍ମା, 24 ମ", detail: "ସାମାନ୍ୟ ମୁଣ୍ଡବିନ୍ଧା · ଗର୍ଭକାଳୀନ ଯାଞ୍ଚ", u: "green" },
      { name: "ଅର୍ଜୁନ ନାୟର, 65 ପୁ", detail: "ପୁରୁଣା ମଧୁମେହ · ଫଲୋ-ଅପ୍", u: "green" },
    ],
  },
  facilities: ["ସରକାରୀ ଡାକ୍ତରଖାନା", "ପ୍ରାଥମିକ ସ୍ୱାସ୍ଥ୍ୟ କେନ୍ଦ୍ର", "ସାର୍ବଜନୀନ ସ୍ୱାସ୍ଥ୍ୟ ଶିବିର", "ଶିଳ୍ପ ସ୍ୱାସ୍ଥ୍ୟ ୟୁନିଟ୍", "କ୍ୟାମ୍ପସ୍ ସ୍ୱାସ୍ଥ୍ୟ କେନ୍ଦ୍ର", "କମ୍ପାନୀ କ୍ଲିନିକ୍"],
  features: {
    eyebrow: "ଜୀବିଆ କ'ଣ କରେ",
    title: ["ସ୍ୱାସ୍ଥ୍ୟକର୍ମୀଙ୍କୁ ଯାହା ଦରକାର,", "କେବଳ ତାହା"],
    body: "ଭାରତୀୟ ସ୍ୱାସ୍ଥ୍ୟସେବାର ବାସ୍ତବତା ପାଇଁ ତିଆରି — ଦୁର୍ବଳ ନେଟୱର୍କ, ଅନେକ ଭାଷା, ଅଧିକ ଭିଡ଼ ଓ କମ୍ ବିଶେଷଜ୍ଞ।",
    items: [
      { title: "ବହୁ-ମାଧ୍ୟମ ଲକ୍ଷଣ ସଂଗ୍ରହ", body: "ରୋଗୀ ନିଜ ଭାଷାରେ କୁହନ୍ତି, ଲେଖନ୍ତି ବା ଚିତ୍ର ବାଛନ୍ତି। କିଓସ୍କ ଶବ୍ଦ ପୁଣି ଶୁଣାଏ ଯେପରି ସେଭ୍ ପୂର୍ବରୁ ନିଶ୍ଚିତ ହୁଏ।" },
      { title: "ଲ୍ୟାବ୍ ରିପୋର୍ଟରୁ ମୂଲ୍ୟ", body: "ଛପା ବା ହାତଲେଖା ରିପୋର୍ଟର ଫଟୋ ନିଅନ୍ତୁ। ପ୍ରତ୍ୟେକ ମୂଲ୍ୟ ସେହି ଅଂଶ ସହ ଦେଖାଯାଏ ଯେଉଁଠୁ ପଢ଼ାଗଲା।" },
      { title: "ସଂରଚିତ ଟ୍ରାଇଏଜ୍ ନୋଟ୍", body: "ସମୟରେଖା, ଅଭାବ ତଥ୍ୟ ଓ ପରବର୍ତ୍ତୀ ପ୍ରଶ୍ନ ସହ ସଂକ୍ଷିପ୍ତ ସାରାଂଶ — ରୋଗ ନିର୍ଣ୍ଣୟ ନୁହେଁ।" },
      { title: "22 ଭାଷା ସହାୟତା", body: "ରୋଗୀଙ୍କ କଥା ପାଇଁ ସମସ୍ତ ଅନୁସୂଚିତ ଭାରତୀୟ ଭାଷା; ପୂର୍ଣ୍ଣ ସ୍କ୍ରିନ୍ ଇଂରାଜୀ, ହିନ୍ଦୀ ଓ ଓଡ଼ିଆରେ।" },
      { title: "ମଣିଷ ସମୀକ୍ଷା ପ୍ରକ୍ରିୟା", body: "ସ୍ଥିର କ୍ଲିନିକାଲ୍ ନିୟମରୁ ନାଲି / ହଳଦିଆ / ସବୁଜ ଧାଡ଼ି। ଡାକ୍ତର ନିଶ୍ଚିତ କରନ୍ତି, ଲିଖିତ କାରଣ ସହ ବଦଳାନ୍ତି, ରେଫର୍ କରନ୍ତି।" },
      { title: "ଗୋପନୀୟତା ପ୍ରଥମ", body: "ସଂଗ୍ରହ ପୂର୍ବରୁ ସମ୍ମତି, ଭୂମିକା-ଆଧାରିତ ପ୍ରବେଶ, ପରିବର୍ତ୍ତନ-ରୋଧୀ ଅଡିଟ୍ ଲଗ୍ ଓ ସ୍ୱର-ଫଟୋ ସ୍ୱତଃ ବିଲୋପ।" },
    ],
  },
  how: {
    eyebrow: "ପ୍ରକ୍ରିୟା",
    title: ["ଲକ୍ଷଣରୁ", "ସଂରଚିତ ସମୀକ୍ଷା ପର୍ଯ୍ୟନ୍ତ"],
    body: "ତିନୋଟି ପଦକ୍ଷେପ, ଚାରି ମିନିଟ୍ ଭିତରେ ସମୀକ୍ଷା ପାଇଁ — ସବୁବେଳେ ନିୟନ୍ତ୍ରଣ ଡାକ୍ତରଙ୍କ ହାତରେ।",
    steps: [
      { title: "ରୋଗୀ ତଥ୍ୟ", body: "ସ୍ୱାସ୍ଥ୍ୟକର୍ମୀ କିଓସ୍କ ଖୋଲନ୍ତି। ରୋଗୀ କହି ବା ଚିତ୍ର ବାଛି ଲକ୍ଷଣ ଜଣାନ୍ତି, ରିପୋର୍ଟ ଯୋଡନ୍ତି — ଇଣ୍ଟରନେଟ୍ ବିନା ମଧ୍ୟ।" },
      { title: "ନିୟମ + ସାରାଂଶ", body: "AIIMS ATP ଓ IMCI ର ସ୍ଥିର ନିୟମ ଜରୁରୀତା ସ୍ଥିର କରେ। ନୋଟରେ ପ୍ରତ୍ୟେକ ମୂଲ୍ୟ ତାର ଉତ୍ସ ସହ ଥାଏ।" },
      { title: "ଡାକ୍ତରଙ୍କ ସମୀକ୍ଷା", body: "ଡାକ୍ତର ପ୍ରାଥମିକତା ଧାଡ଼ି ଦେଖନ୍ତି, ଚିହ୍ନିତ ମୂଲ୍ୟ ଯାଞ୍ଚ କରନ୍ତି, ନୋଟ୍ ନିଶ୍ଚିତ କରି ରେଫରାଲ୍ ସ୍ଥିର କରନ୍ତି।" },
    ],
  },
  scenarios: {
    eyebrow: "ସାରା ଭାରତ ପାଇଁ",
    title: ["ପ୍ରତ୍ୟେକ ପ୍ରକାର", "ସ୍ୱାସ୍ଥ୍ୟ କେନ୍ଦ୍ର ପାଇଁ"],
    items: [
      { tag: "ଓପିଡି", title: "ଓପିଡି ଧାଡ଼ି ଟ୍ରାଇଏଜ୍", body: "ଭିଡ଼ ଓପିଡିରେ ଛାତି ଯନ୍ତ୍ରଣା ଓ ନିଶ୍ୱାସ ଅସୁବିଧା ପ୍ରଥମେ ଦେଖାଯାଉ।" },
      { tag: "ଶିଳ୍ପ", title: "ବୃତ୍ତିଗତ ଯାଞ୍ଚ", body: "ଶିଳ୍ପାଞ୍ଚଳରେ ପୋଡ଼ା, ଆଘାତ ଓ ଗରମ ପ୍ରଭାବ। ନିଯୁକ୍ତିଦାତା କେବଳ ଫିଟନେସ୍ ସ୍ଥିତି ଦେଖନ୍ତି।" },
      { tag: "କ୍ୟାମ୍ପସ୍", title: "କ୍ୟାମ୍ପସ୍ ଜ୍ୱର ଟ୍ରାଇଏଜ୍", body: "ହଷ୍ଟେଲରେ ଡେଙ୍ଗୁ ଋତୁର ସତର୍କ ସଙ୍କେତ ଚିହ୍ନଟ କରନ୍ତୁ।" },
      { tag: "ମାତୃତ୍ୱ", title: "ମାତୃ ସ୍ୱାସ୍ଥ୍ୟ ଫଲୋ-ଅପ୍", body: "ପ୍ରି-ଏକ୍ଲାମ୍ପସିଆ ସଙ୍କେତ ଓ SMS ବା କଲ୍ ମାଧ୍ୟମରେ ଯାଞ୍ଚ ସ୍ମାରକ।" },
      { tag: "ଦୀର୍ଘ ରୋଗ", title: "ନିୟମିତ ଯାଞ୍ଚ", body: "ଆଜିର ଶର୍କରା ବା BP ପୂର୍ବ ସାକ୍ଷାତ ସହ ତୁଳନା।" },
      { tag: "ଶିବିର", title: "ଶିବିର ଯାଞ୍ଚ", body: "ଦୂରାଞ୍ଚଳ ଶିବିରରେ ଇଣ୍ଟରନେଟ୍ ବିନା କାମ କରେ, ପରେ ସ୍ୱତଃ ସିଙ୍କ୍।" },
      { tag: "ରେଫରାଲ୍", title: "ରେଫରାଲ୍ ନୋଟ୍", body: "ଗୋଟିଏ କ୍ଲିକରେ ଠିକ୍ ବଡ଼ ଡାକ୍ତରଖାନା ପାଇଁ ରେଫରାଲ୍ ନୋଟ୍।" },
    ],
  },
  safety: {
    eyebrow: "ସୁରକ୍ଷା ଓ ଗୋପନୀୟତା",
    title: ["ସୁରକ୍ଷା ନିୟମ", "ଯାହା ଉପରେ ଏହା ତିଆରି"],
    items: [
      { title: "ରୋଗ ନିର୍ଣ୍ଣୟ ନୁହେଁ", body: "ରୋଗୀ ଯାହା କହିଲେ ତାହା ସଜାଏ। ନିର୍ଣ୍ଣୟ ନାହିଁ, ଔଷଧ ନାହିଁ।" },
      { title: "ସ୍ଥିର ନିୟମରୁ ଜରୁରୀତା", body: "ଜରୁରୀତା କେବଳ AIIMS ATP ଓ IMCI ନିୟମରୁ — ଭାଷା ମଡେଲରୁ କେବେ ନୁହେଁ।" },
      { title: "ମଣିଷ ନିୟନ୍ତ୍ରଣ", body: "ପ୍ରତ୍ୟେକ ନୋଟ୍ ଯୋଗ୍ୟ ସମୀକ୍ଷକ ଦେଖନ୍ତି। ବଦଳାଇବାକୁ ଲିଖିତ କାରଣ ଆବଶ୍ୟକ।" },
      { title: "ଉତ୍ସ ସହ ମୂଲ୍ୟ", body: "ପ୍ରତ୍ୟେକ ମୂଲ୍ୟ ରିପୋର୍ଟର ସେହି ଅଂଶ ବା କୁହାଯାଇଥିବା ଶବ୍ଦ ସହ ଦେଖାଯାଏ।" },
      { title: "ପରିବର୍ତ୍ତନ-ରୋଧୀ ଅଡିଟ୍", body: "ପ୍ରତ୍ୟେକ ଦେଖା, ବଦଳ ଓ ରପ୍ତାନି ଏପରି ଲଗରେ ଯାହା ବଦଳାଯାଇ ପାରିବ ନାହିଁ।" },
      { title: "ସର୍ବନିମ୍ନ ସଂରକ୍ଷଣ", body: "ସ୍ୱର ଓ ଫଟୋ ସ୍ୱତଃ ବିଲୋପ ହୁଏ। ରୋଗୀ ଟ୍ରାଇଏଜ୍ ସ୍ଥିତି ଦେଖନ୍ତି ନାହିଁ।" },
    ],
    noticeTitle: "ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ ସୁରକ୍ଷା ସୂଚନା",
    noticeLead: "ଜୀବିଆ ଟ୍ରାଇଏଜରେ ସାହାଯ୍ୟ କରେ — ଡାକ୍ତରଙ୍କ ସ୍ଥାନ ନିଏ ନାହିଁ।",
    notice: "ଏହା ରୋଗୀଙ୍କ ଦିଆଯାଇଥିବା ତଥ୍ୟ ସଜାଏ ଓ ଜରୁରୀତା ସଙ୍କେତ ଦେଖାଏ। ଏହା ରୋଗ ନିର୍ଣ୍ଣୟ ବା ଔଷଧ ଦିଏ ନାହିଁ। ପ୍ରତ୍ୟେକ ଫଳାଫଳ କେବଳ ପରାମର୍ଶ ଏବଂ ଯେକୌଣସି ନିଷ୍ପତ୍ତି ପୂର୍ବରୁ ଅନୁମତିପ୍ରାପ୍ତ ସ୍ୱାସ୍ଥ୍ୟକର୍ମୀ ଦେଖିବା ଆବଶ୍ୟକ।",
  },
  cta: { title: "ଆପଣଙ୍କ ଧାଡ଼ି ଛୋଟ କରନ୍ତୁ", body: "ଆପଣଙ୍କ କେନ୍ଦ୍ର ସେଟ୍ କରନ୍ତୁ, କିଓସ୍କ ଟାବଲେଟ୍ ଯୋଡନ୍ତୁ ଓ କିଛି ମିନିଟରେ ପ୍ରଥମ ତଥ୍ୟ ସଂଗ୍ରହ କରନ୍ତୁ।", primary: "ଆକାଉଣ୍ଟ ତିଆରି କରନ୍ତୁ", secondary: "କିଓସ୍କ ଖୋଲନ୍ତୁ" },
  status: {
    eyebrow: "\u0b38\u0b3f\u0b37\u0b4d\u0b1f\u0b2e\u0b30 \u0b32\u0b3e\u0b07\u0b2d\u0b4d \u0b38\u0b4d\u0b25\u0b3f\u0b24\u0b3f",
    title: ["ସବୁକିଛି", "ଚାଲୁଛି କି?"],
    body: "\u0b06\u0b2a\u0b23\u0b19\u0b4d\u0b15 \u0b2c\u0b4d\u0b30\u0b3e\u0b09\u0b1c\u0b30\u0b30\u0b41 \u0b2a\u0b4d\u0b30\u0b24\u0b3f 20 \u0b38\u0b47\u0b15\u0b47\u0b23\u0b4d\u0b21\u0b30\u0b47 \u0b2f\u0b3e\u0b1e\u0b4d\u0b1a\u0964 API \u0b38\u0b30\u0b4d\u0b2d\u0b30 15 \u0b2e\u0b3f\u0b28\u0b3f\u0b1f\u0b4d \u0b16\u0b3e\u0b32\u0b3f \u0b30\u0b39\u0b3f\u0b32\u0b47 \u0b36\u0b4b\u0b07\u0b2f\u0b3e\u0b0f \u2014 \u0b17\u0b4b\u0b1f\u0b3f\u0b0f \u0b1f\u0b4d\u0b5f\u0b3e\u0b2a\u0b30\u0b47 \u0b1c\u0b17\u0b3e\u0b28\u0b4d\u0b24\u0b41\u0964",
    allOk: "\u0b38\u0b2e\u0b38\u0b4d\u0b24 \u0b38\u0b3f\u0b37\u0b4d\u0b1f\u0b2e \u0b1a\u0b3e\u0b32\u0b41\u0b1b\u0b3f",
    degraded: "\u0b06\u0b02\u0b36\u0b3f\u0b15 \u0b38\u0b2e\u0b38\u0b4d\u0b5f\u0b3e",
    offline: "\u0b38\u0b30\u0b4d\u0b2d\u0b30 \u0b36\u0b4b\u0b07\u0b1b\u0b3f \u0b2c\u0b3e \u0b2a\u0b39\u0b1e\u0b4d\u0b1a \u0b2c\u0b3e\u0b39\u0b3e\u0b30\u0b47",
    waking: "\u0b38\u0b30\u0b4d\u0b2d\u0b30 \u0b1c\u0b17\u0b3e\u0b2f\u0b3e\u0b09\u0b1b\u0b3f\u2026",
    checking: "\u0b2f\u0b3e\u0b1e\u0b4d\u0b1a \u0b39\u0b47\u0b09\u0b1b\u0b3f\u2026",
    demo: "\u0b32\u0b4b\u0b15\u0b3e\u0b32\u0b4d \u0b21\u0b47\u0b2e\u0b4b \u0b2e\u0b4b\u0b21\u0b4d \u2014 \u0b38\u0b30\u0b4d\u0b2d\u0b30 \u0b28\u0b3e\u0b39\u0b3f\u0b01",
    website: "\u0b71\u0b47\u0b2c\u0b38\u0b3e\u0b07\u0b1f\u0b4d",
    api: "API \u0b38\u0b30\u0b4d\u0b2d\u0b30",
    database: "\u0b21\u0b3e\u0b1f\u0b3e\u0b2c\u0b47\u0b38\u0b4d",
    sms: "SMS \u0b38\u0b3e\u0b07\u0b28\u0b4d-\u0b07\u0b28\u0b4d \u0b15\u0b4b\u0b21\u0b4d",
    storage: "\u0b26\u0b38\u0b4d\u0b24\u0b3e\u0b2c\u0b3f\u0b1c \u0b38\u0b02\u0b30\u0b15\u0b4d\u0b37\u0b23",
    online: "\u0b05\u0b28\u0b32\u0b3e\u0b07\u0b28\u0b4d",
    asleep: "\u0b36\u0b4b\u0b07\u0b1b\u0b3f",
    ready: "\u0b2a\u0b4d\u0b30\u0b38\u0b4d\u0b24\u0b41\u0b24",
    notReady: "\u0b38\u0b47\u0b1f\u0b4d \u0b39\u0b4b\u0b07\u0b28\u0b3e\u0b39\u0b3f\u0b01",
    uptime: "\u0b1a\u0b3e\u0b32\u0b41",
    checked: "\u0b2f\u0b3e\u0b1e\u0b4d\u0b1a",
    checkNow: "\u0b0f\u0b2c\u0b47 \u0b2f\u0b3e\u0b1e\u0b4d\u0b1a",
    wake: "\u0b38\u0b30\u0b4d\u0b2d\u0b30 \u0b1c\u0b17\u0b3e\u0b28\u0b4d\u0b24\u0b41",
    restart: "\u0b38\u0b30\u0b4d\u0b2d\u0b30 \u0b30\u0b3f\u0b37\u0b4d\u0b1f\u0b3e\u0b30\u0b4d\u0b1f",
    sleepHint: "\u0b1c\u0b17\u0b3e\u0b07\u0b2c\u0b3e\u0b15\u0b41 \u0b38\u0b3e\u0b27\u0b3e\u0b30\u0b23\u0b24\u0b03 30\u201360 \u0b38\u0b47\u0b15\u0b47\u0b23\u0b4d\u0b21 \u0b32\u0b3e\u0b17\u0b47\u0964",
  },
  footer: {
    blurb: "ସାରା ଭାରତର ସରକାରୀ ଓ ଅନୁଷ୍ଠାନିକ ସ୍ୱାସ୍ଥ୍ୟ କେନ୍ଦ୍ର ପାଇଁ ବହୁ-ମାଧ୍ୟମ ଟ୍ରାଇଏଜ୍ ସହାୟକ।",
    badges: ["ମଣିଷ ସମୀକ୍ଷା", "ରୋଗ ନିର୍ଣ୍ଣୟ ନୁହେଁ"],
    product: "ଉତ୍ପାଦ",
    teams: "ଦଳ ପାଇଁ",
    legal: "ସୁରକ୍ଷା ଓ ଗୋପନୀୟତା",
    teamLinks: ["ଡାକ୍ତର", "ନର୍ସ ଓ ANM", "କେନ୍ଦ୍ର ପରିଚାଳକ", "ନିଯୁକ୍ତିଦାତା"],
    legalLinks: ["କ୍ଲିନିକାଲ୍ ଅସ୍ୱୀକାର", "ଗୋପନୀୟତା ଓ ସମ୍ମତି", "ତଥ୍ୟ ସଂରକ୍ଷଣ", "ଅଡିଟ୍ ଲଗ୍"],
    kiosk: "ରୋଗୀ କିଓସ୍କ",
    rights: "ଜୀବିଆ। ସର୍ବସ୍ୱତ୍ୱ ସଂରକ୍ଷିତ।",
    note: "ସମସ୍ତ ସ୍ୱାସ୍ଥ୍ୟ ସମ୍ବନ୍ଧୀୟ ଫଳାଫଳ କେବଳ ପରାମର୍ଶ ଓ ସମୀକ୍ଷକଙ୍କ ପାଇଁ।",
  },
};

const SITE: Record<string, SiteCopy> = { en, hi, or };

export function useSite(): SiteCopy {
  const { lang } = usePrefs();
  return SITE[lang] ?? en;
}
