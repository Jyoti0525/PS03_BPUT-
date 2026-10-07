/** Minimal sample data: two facilities, sample staff, three sample patients. No real patient records. */
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
  }
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
  { id: "usr_hw1", phone: "9000000006", name: "Kamla Devi (ASHA)", role: "health_worker", facility_id: "fac_phc_manikpur", registration_no: null, language: "hi", has_pin: false, created_at: iso(50 * DAY) },
  { id: "usr_mo1", phone: "9000000007", name: "Dr. Anil Verma (Medical Officer i/c)", role: "medical_officer", facility_id: "fac_phc_manikpur", registration_no: "UPMC-51207", language: "en", has_pin: false, created_at: iso(100 * DAY) },
];

export { DEMO_LOGINS } from "@/lib/samples";

export const SEED_PATIENTS: Patient[] = [
  { id: "pat_001", code: "JVA-P001", name: "Radha Kumari", age: 42, sex: "F", phone: "9876543210", language: "hi", category: "normal", village: "Manikpur", created_at: iso(200 * DAY) },
  { id: "pat_002", code: "JVA-P002", name: "Lakshmi Devi", age: 55, sex: "F", phone: "9880111223", language: "kn", category: "chronic", village: "Mau", created_at: iso(500 * DAY) },
  { id: "pat_003", code: "JVA-P003", name: "Priya Sharma", age: 24, sex: "F", phone: "9876543210", language: "hi", category: "maternal", village: "Manikpur", created_at: iso(120 * DAY) },
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
  { patient_id: "pat_002", minutes_ago: 90 * DAY / MIN, category: "chronic", language: "kn", chief_complaint: "Diabetes check-in", symptoms: [sym("More thirst than usual")], selected_symptoms: [], duration: null, severity: 3, answers: [], vitals: { glucose: 265, bp_systolic: 130, bp_diastolic: 82 }, chronic: { condition: "Type 2 diabetes", feeling_vs_last: "worse" }, status: "closed" },
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
    patient_id: "pat_003",
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
    employer_name: "Kalinga Steel Works (sample)",
    screening_type: "Periodic occupational health screening",
    workers: [
      { worker_code: "KSW-1041", department: "Furnace", fitness_status: "fit", last_screened_at: iso(12 * DAY) },
      { worker_code: "KSW-1043", department: "Furnace", fitness_status: "fit_with_restrictions", last_screened_at: iso(11 * DAY) },
      { worker_code: "KSW-1045", department: "Furnace", fitness_status: "pending_review", last_screened_at: null },
    ],
  },
];
