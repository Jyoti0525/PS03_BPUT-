/** Synthetic seed data. No real patient records — every name and value is invented. */
import type { Cohort, Facility, IntakePayload, Patient, User } from "@/lib/types";

export const DEMO_OTP = "123456";

export const SEED_FACILITIES: Facility[] = [
  {
    id: "fac_phc_manikpur",
    name: "PHC Manikpur",
    type: "phc",
    district: "Chitrakoot",
    state: "Uttar Pradesh",
    languages: ["hi", "en"],
    specialists: [
      { key: "genmed", label: "General Medicine", available: true, schedule: "Daily" },
      { key: "obgyn", label: "Obstetrics & Gynaecology", available: false, schedule: "Visiting Thursday" },
      { key: "cardio", label: "Cardiology", available: false, schedule: null },
      { key: "pulmo", label: "Pulmonology", available: false, schedule: null },
      { key: "paeds", label: "Paediatrics", available: false, schedule: "Visiting Monday" },
      { key: "endo", label: "Endocrinology", available: false, schedule: null },
    ],
    referral_destination: "District Hospital Gorakhpur (42 km)",
    beds_total: 15,
    beds_occupied: 11,
    offline_mode: true,
    capabilities: { lab: true, xray: false, ecg: true, oxygen: true, ambulance: true, pharmacy: true, labour_room: true },
  },
  {
    id: "fac_dh_gorakhpur",
    name: "District Hospital Gorakhpur",
    type: "district_hospital",
    district: "Gorakhpur",
    state: "Uttar Pradesh",
    languages: ["hi", "en", "bho"],
    specialists: [
      { key: "genmed", label: "General Medicine", available: true, schedule: "24×7" },
      { key: "obgyn", label: "Obstetrics & Gynaecology", available: true, schedule: "24×7" },
      { key: "cardio", label: "Cardiology", available: true, schedule: "OPD Mon–Sat" },
      { key: "pulmo", label: "Pulmonology", available: true, schedule: "OPD Tue/Fri" },
      { key: "paeds", label: "Paediatrics", available: true, schedule: "24×7" },
      { key: "endo", label: "Endocrinology", available: true, schedule: "OPD Wed" },
    ],
    referral_destination: "AIIMS Gorakhpur (super-speciality)",
    beds_total: 250,
    beds_occupied: 214,
    offline_mode: false,
    capabilities: { lab: true, xray: true, ecg: true, oxygen: true, ambulance: true, pharmacy: true, labour_room: true, icu: true },
  },
  {
    id: "fac_kalinganagar",
    name: "Kalinganagar Industrial Estate Health Unit",
    type: "industrial_unit",
    district: "Jajpur",
    state: "Odisha",
    languages: ["or", "hi", "en"],
    specialists: [
      { key: "genmed", label: "Occupational Health Physician", available: true, schedule: "Shift A & B" },
      { key: "ortho", label: "Orthopaedics", available: false, schedule: "Visiting Saturday" },
      { key: "burns", label: "Burns & Plastic Surgery", available: false, schedule: null },
    ],
    referral_destination: "SCB Medical College, Cuttack (95 km)",
    beds_total: 6,
    beds_occupied: 1,
    offline_mode: false,
    capabilities: { lab: false, xray: true, ecg: true, oxygen: true, ambulance: true, pharmacy: true },
  },
  {
    id: "fac_bput_campus",
    name: "BPUT Campus Health Centre",
    type: "campus",
    district: "Sundargarh",
    state: "Odisha",
    languages: ["or", "en", "hi"],
    specialists: [
      { key: "genmed", label: "General Medicine", available: true, schedule: "9am–5pm" },
      { key: "psych", label: "Counsellor", available: true, schedule: "Tue/Thu" },
    ],
    referral_destination: "Ispat General Hospital, Rourkela (6 km)",
    beds_total: 8,
    beds_occupied: 2,
    offline_mode: false,
    capabilities: { lab: true, xray: false, ecg: false, oxygen: true, ambulance: true, pharmacy: true },
  },
  {
    id: "fac_koraput_camp",
    name: "Public Health Camp — Koraput",
    type: "health_camp",
    district: "Koraput",
    state: "Odisha",
    languages: ["or", "hi"],
    specialists: [{ key: "genmed", label: "Camp Medical Officer", available: true, schedule: "Camp days only" }],
    referral_destination: "SLN Medical College, Koraput (18 km)",
    beds_total: 0,
    beds_occupied: 0,
    offline_mode: true,
    capabilities: { lab: false, xray: false, ecg: false, oxygen: false, ambulance: false, pharmacy: true },
  },
];

const now = Date.now();
const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
const MIN = 60_000;
const DAY = 86_400_000;

export const SEED_USERS: (User & { pin?: string })[] = [
  { id: "usr_doc1", phone: "9000000001", name: "Dr. Deepa Sharma", role: "doctor", facility_id: "fac_phc_manikpur", registration_no: "UPMC-48921", language: "en", has_pin: false, created_at: iso(90 * DAY) },
  { id: "usr_nurse1", phone: "9000000002", name: "Sunita Yadav (ANM)", role: "nurse", facility_id: "fac_phc_manikpur", registration_no: "UPNC-22817", language: "hi", has_pin: false, created_at: iso(80 * DAY) },
  { id: "usr_recep1", phone: "9000000003", name: "Rakesh Tiwari", role: "receptionist", facility_id: "fac_phc_manikpur", registration_no: null, language: "hi", has_pin: false, created_at: iso(70 * DAY) },
  { id: "usr_sup1", phone: "9000000004", name: "Meera Nair", role: "supervisor", facility_id: "fac_phc_manikpur", registration_no: null, language: "en", has_pin: false, created_at: iso(120 * DAY) },
  { id: "usr_emp1", phone: "9000000005", name: "Arjun Patnaik (HR — Safety)", role: "employer", facility_id: "fac_kalinganagar", registration_no: null, language: "en", has_pin: false, created_at: iso(60 * DAY) },
  { id: "usr_pat1", phone: "9876543210", name: "Priya Sharma", role: "patient", facility_id: null, registration_no: null, language: "hi", has_pin: false, created_at: iso(40 * DAY) },
];

export const DEMO_LOGINS = [
  { role: "doctor", phone: "9000000001", name: "Dr. Deepa Sharma" },
  { role: "nurse", phone: "9000000002", name: "Sunita Yadav (ANM)" },
  { role: "receptionist", phone: "9000000003", name: "Rakesh Tiwari" },
  { role: "supervisor", phone: "9000000004", name: "Meera Nair" },
  { role: "patient", phone: "9876543210", name: "Priya Sharma" },
  { role: "employer", phone: "9000000005", name: "Arjun Patnaik" },
] as const;

export const SEED_PATIENTS: Patient[] = [
  { id: "pat_001", code: "JVA-P001", name: "Radha Kumari", age: 42, sex: "F", phone: "9876543210", language: "hi", category: "normal", village: "Manikpur", created_at: iso(200 * DAY) },
  { id: "pat_002", code: "JVA-P002", name: "Suresh Babu", age: 68, sex: "M", phone: "9440123456", language: "te", category: "chronic", village: "Karwi", created_at: iso(400 * DAY) },
  { id: "pat_003", code: "JVA-P003", name: "Ananya Roy", age: 26, sex: "F", phone: "9831098765", language: "bn", category: "maternal", village: "Manikpur", created_at: iso(150 * DAY) },
  { id: "pat_005", code: "JVA-P005", name: "Lakshmi Devi", age: 55, sex: "F", phone: "9880111223", language: "kn", category: "chronic", village: "Mau", created_at: iso(500 * DAY) },
  { id: "pat_008", code: "JVA-P008", name: "Priya Sharma", age: 24, sex: "F", phone: "9876543210", language: "hi", category: "maternal", village: "Manikpur", created_at: iso(120 * DAY) },
  { id: "pat_010", code: "JVA-P010", name: "Aarav Singh", age: 3, sex: "M", phone: "9876543210", language: "hi", category: "normal", village: "Manikpur", created_at: iso(30 * DAY) },
  { id: "pat_011", code: "JVA-P011", name: "Bikash Nayak", age: 34, sex: "M", phone: "9437001122", language: "or", category: "normal", village: "Kalinganagar", employer_id: "emp_kalinga", created_at: iso(300 * DAY) },
  { id: "pat_012", code: "JVA-P012", name: "Ritika Mohanty", age: 20, sex: "F", phone: "9938112233", language: "or", category: "normal", village: "Rourkela", created_at: iso(10 * DAY) },
];

type SeedIntake = Omit<IntakePayload, "patient_id" | "facility_id" | "client_ref" | "file_ids" | "consent_id"> & {
  patient_id: string;
  minutes_ago: number;
  sample_reports?: string[];
  proxy?: { name: string; relation: string };
  status?: "queued" | "closed";
  facility_id?: string;
};

const sym = (text: string, original = text, language = "en", source: "voice" | "text" = "voice") => ({
  text,
  original_text: original,
  language,
  source,
  confirmed_by_readback: source === "voice",
});

/** Older closed visits — give chronic/maternal patients a longitudinal baseline. */
export const SEED_HISTORY: SeedIntake[] = [
  { patient_id: "pat_001", minutes_ago: 60 * DAY / MIN * 1, category: "normal", language: "hi", chief_complaint: "BP follow-up", symptoms: [sym("Routine BP check", "BP जांच", "hi")], selected_symptoms: [], duration: null, severity: 2, answers: [], vitals: { bp_systolic: 138, bp_diastolic: 86, pulse: 84 }, status: "closed" },
  { patient_id: "pat_001", minutes_ago: 30 * DAY / MIN, category: "normal", language: "hi", chief_complaint: "Headache and BP check", symptoms: [sym("Headache in the evenings", "शाम को सिरदर्द", "hi")], selected_symptoms: [], duration: "1 week", severity: 3, answers: [], vitals: { bp_systolic: 148, bp_diastolic: 92, pulse: 88 }, status: "closed" },
  { patient_id: "pat_005", minutes_ago: 180 * DAY / MIN, category: "chronic", language: "kn", chief_complaint: "Diabetes check-in", symptoms: [sym("Sugar check")], selected_symptoms: [], duration: null, severity: 1, answers: [], vitals: { glucose: 210, bp_systolic: 128, bp_diastolic: 80 }, chronic: { condition: "Type 2 diabetes", feeling_vs_last: "same" }, status: "closed" },
  { patient_id: "pat_005", minutes_ago: 90 * DAY / MIN, category: "chronic", language: "kn", chief_complaint: "Diabetes check-in", symptoms: [sym("More thirst than usual")], selected_symptoms: [], duration: null, severity: 3, answers: [], vitals: { glucose: 265, bp_systolic: 130, bp_diastolic: 82 }, chronic: { condition: "Type 2 diabetes", feeling_vs_last: "worse" }, status: "closed" },
  { patient_id: "pat_003", minutes_ago: 56 * DAY / MIN, category: "maternal", language: "bn", chief_complaint: "ANC visit (24 weeks)", symptoms: [sym("Routine antenatal visit")], selected_symptoms: [], duration: null, severity: 0, answers: [], vitals: { bp_systolic: 118, bp_diastolic: 76 }, maternal: { gestation_weeks: 24 }, status: "closed" },
  { patient_id: "pat_003", minutes_ago: 28 * DAY / MIN, category: "maternal", language: "bn", chief_complaint: "ANC visit (28 weeks)", symptoms: [sym("Routine antenatal visit")], selected_symptoms: [], duration: null, severity: 0, answers: [], vitals: { bp_systolic: 124, bp_diastolic: 82 }, maternal: { gestation_weeks: 28 }, status: "closed" },
  { patient_id: "pat_008", minutes_ago: 42 * DAY / MIN, category: "maternal", language: "hi", chief_complaint: "ANC visit (22 weeks)", symptoms: [sym("Routine antenatal visit")], selected_symptoms: [], duration: null, severity: 0, answers: [], vitals: { bp_systolic: 116, bp_diastolic: 74 }, maternal: { gestation_weeks: 22 }, status: "closed" },
];

/** Today's queue. */
export const SEED_TODAY: SeedIntake[] = [
  {
    patient_id: "pat_001",
    minutes_ago: 8,
    category: "normal",
    language: "hi",
    chief_complaint: "Chest pain radiating to left arm",
    symptoms: [sym("Chest pain since 2 hours going to the left arm, sweating a lot", "दो घंटे से सीने में दर्द है जो बाएं हाथ तक जा रहा है, बहुत पसीना आ रहा है", "hi")],
    selected_symptoms: ["Sweating", "Anxiety"],
    duration: "2 hours",
    severity: 8,
    answers: [{ qid: "q_onset", question: "Did it start at rest?", answer: "Yes, while sitting" }],
    vitals: { bp_systolic: 160, bp_diastolic: 100, pulse: 104, spo2: 97, temp_f: 98.2 },
    sample_reports: ["lipid"],
    proxy: { name: "Ramesh Kumar", relation: "Husband" },
  },
  {
    patient_id: "pat_002",
    minutes_ago: 14,
    category: "chronic",
    language: "te",
    chief_complaint: "Breathlessness for 3 days (known COPD)",
    symptoms: [sym("Breathless for three days, yellow sputum, cannot walk to the toilet", "మూడు రోజులుగా ఆయాసం, పసుపు కఫం", "te")],
    selected_symptoms: ["Cough", "Fever"],
    duration: "3 days",
    severity: 7,
    answers: [],
    vitals: { spo2: 89, resp_rate: 28, bp_systolic: 118, bp_diastolic: 76, pulse: 112 },
    chronic: { condition: "COPD", last_checkup: "3 months ago", current_medicines: "Inhaler (name not known)", feeling_vs_last: "worse" },
  },
  {
    patient_id: "pat_003",
    minutes_ago: 22,
    category: "maternal",
    language: "bn",
    chief_complaint: "Severe headache and blurred vision, 32 weeks pregnant",
    symptoms: [sym("Severe headache since yesterday, blurred vision, swelling in feet", "কাল থেকে প্রচণ্ড মাথাব্যথা, চোখে ঝাপসা দেখছি", "bn")],
    selected_symptoms: ["Swelling"],
    duration: "1 day",
    severity: 7,
    answers: [],
    vitals: { bp_systolic: 148, bp_diastolic: 96, pulse: 96, spo2: 98 },
    maternal: { gestation_weeks: 32, anc_visits: 3, reminder_channel: "voice" },
    sample_reports: ["anc"],
    proxy: { name: "Sarita Roy", relation: "Mother-in-law" },
  },
  {
    patient_id: "pat_010",
    minutes_ago: 11,
    category: "normal",
    language: "hi",
    chief_complaint: "Child with high fever and one convulsion",
    symptoms: [sym("High fever since last night and had fits once this morning, very sleepy", "कल रात से तेज़ बुखार, सुबह एक बार झटके आए", "hi")],
    selected_symptoms: ["Fever", "Not feeding"],
    duration: "1 day",
    severity: null,
    answers: [],
    vitals: { temp_f: 103.4, pulse: 140, resp_rate: 42 },
    proxy: { name: "Radha Kumari", relation: "Mother" },
  },
  {
    patient_id: "pat_005",
    minutes_ago: 38,
    category: "chronic",
    language: "kn",
    chief_complaint: "Excess thirst and blurred vision (diabetic)",
    symptoms: [sym("Passing urine very often, always thirsty, vision blurry, very tired", "ಬಾಯಾರಿಕೆ ಹೆಚ್ಚು, ಕಣ್ಣು ಮಂದ", "kn")],
    selected_symptoms: ["Tiredness"],
    duration: "2 weeks",
    severity: 5,
    answers: [],
    vitals: { glucose: 318, bp_systolic: 132, bp_diastolic: 84, pulse: 82 },
    chronic: { condition: "Type 2 diabetes", last_checkup: "3 months ago", current_medicines: "Metformin 500 BD, Glimepiride 1 OD — misses doses", feeling_vs_last: "worse" },
    sample_reports: ["glucose"],
  },
  {
    patient_id: "pat_011",
    minutes_ago: 26,
    facility_id: "fac_kalinganagar",
    category: "normal",
    language: "or",
    chief_complaint: "Burn on forearm at work",
    symptoms: [sym("Hot metal splash burn on right forearm during shift", "କାମ କରିବା ସମୟରେ ହାତ ପୋଡ଼ିଗଲା", "or")],
    selected_symptoms: ["Injury"],
    duration: "1 hour",
    severity: 6,
    answers: [],
    vitals: { bp_systolic: 128, bp_diastolic: 82, pulse: 96, spo2: 99 },
  },
  {
    patient_id: "pat_012",
    minutes_ago: 47,
    facility_id: "fac_bput_campus",
    category: "normal",
    language: "or",
    chief_complaint: "Fever for 4 days with body ache",
    symptoms: [sym("Fever for four days with body ache and headache", "ଚାରି ଦିନ ହେଲା ଜ୍ୱର", "or")],
    selected_symptoms: ["Fever", "Body ache", "Headache"],
    duration: "4 days",
    severity: 5,
    answers: [],
    vitals: { temp_f: 101.8, pulse: 98, spo2: 98, bp_systolic: 112, bp_diastolic: 72 },
    sample_reports: ["cbc"],
  },
  {
    patient_id: "pat_008",
    minutes_ago: 62,
    category: "maternal",
    language: "hi",
    chief_complaint: "Routine antenatal visit, mild headache",
    symptoms: [sym("Came for regular checkup, slight headache since morning", "नियमित जांच, सुबह से हल्का सिरदर्द", "hi")],
    selected_symptoms: [],
    duration: "since morning",
    severity: 2,
    answers: [],
    vitals: { bp_systolic: 118, bp_diastolic: 76, pulse: 78, spo2: 99, temp_f: 98.2 },
    maternal: { gestation_weeks: 28, anc_visits: 3, next_checkup: new Date(now + 14 * DAY).toISOString().slice(0, 10), reminder_channel: "sms" },
  },
];

export const SEED_COHORTS: Cohort[] = [
  {
    id: "coh_furnace",
    name: "Blast furnace — Shift A",
    employer_name: "Kalinga Steel Works (synthetic)",
    screening_type: "Periodic occupational health screening",
    workers: [
      { worker_code: "KSW-1041", department: "Furnace", fitness_status: "fit", last_screened_at: iso(12 * DAY) },
      { worker_code: "KSW-1042", department: "Furnace", fitness_status: "fit", last_screened_at: iso(12 * DAY) },
      { worker_code: "KSW-1043", department: "Furnace", fitness_status: "fit_with_restrictions", last_screened_at: iso(11 * DAY) },
      { worker_code: "KSW-1044", department: "Furnace", fitness_status: "temporarily_unfit", last_screened_at: iso(0.1 * DAY) },
      { worker_code: "KSW-1045", department: "Furnace", fitness_status: "pending_review", last_screened_at: null },
      { worker_code: "KSW-1046", department: "Furnace", fitness_status: "fit", last_screened_at: iso(10 * DAY) },
    ],
  },
  {
    id: "coh_rolling",
    name: "Rolling mill — Shift B",
    employer_name: "Kalinga Steel Works (synthetic)",
    screening_type: "Heat-stress screening (summer)",
    workers: [
      { worker_code: "KSW-2201", department: "Rolling mill", fitness_status: "fit", last_screened_at: iso(3 * DAY) },
      { worker_code: "KSW-2202", department: "Rolling mill", fitness_status: "fit", last_screened_at: iso(3 * DAY) },
      { worker_code: "KSW-2203", department: "Rolling mill", fitness_status: "fit_with_restrictions", last_screened_at: iso(4 * DAY) },
      { worker_code: "KSW-2204", department: "Rolling mill", fitness_status: "pending_review", last_screened_at: null },
    ],
  },
];
