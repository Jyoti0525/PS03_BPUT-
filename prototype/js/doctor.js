/* ============================================================
   JEEVIA — Doctor Dashboard Comprehensive JS v2.2
   All 8 Clinical & Safety Views Implemented:
   - View 1:  Triage Queue & AI Summary Panel
   - View 2:  Find Patient (Household Phone Disambiguation)
   - View 3:  Reviewed Today (Session Shift History & Overrides)
   - View 4:  Referrals (Scenario D7 Outgoing & MO Incoming)
   - View 5:  Scan Patient QR (High-Speed Retrieval)
   - View 6:  Rules Engine Trace & 6-Month Defensibility Simulator
   - View 7:  Audit Trail Log (Regulatory G4 Immutable Table & CSV)
   - View 8:  Notifications & Longitudinal Follow-ups
   - Modal :  22 Scheduled Indian Languages Switcher
   ============================================================ */

/* ── 1. FACILITY CONFIGURATIONS ────────────────────────────── */
const facilityConfigs = {
  phc_manikpur: {
    type: 'Primary Health Center',
    name: 'PHC Manikpur — Chitrakoot District',
    subtext: 'Operating under National Health Mission · Bed Capacity: 15 (12 Occupied) · Nearest Referral: Gorakhpur DH (42km)',
    specialists: {
      cardio: { label: 'Cardiologist: None', avail: false, ref: 'District Hospital Gorakhpur' },
      obgyn: { label: 'OB-GYN: Visiting Thu', avail: false, ref: 'District Hospital Gorakhpur' },
      genmed: { label: 'Gen Medicine: Active (You)', avail: true, ref: null },
      pulmo: { label: 'Pulmonologist: None', avail: false, ref: 'District Hospital Gorakhpur' },
      endo: { label: 'Endocrinologist: None', avail: false, ref: 'District Hospital Gorakhpur' }
    },
    defaultReferralDestination: 'District Hospital Gorakhpur (Tertiary Referral Center, 42 km)'
  },
  dh_gorakhpur: {
    type: 'District Hospital (Tertiary)',
    name: 'District Hospital Gorakhpur — Gorakhpur Division',
    subtext: 'Tertiary Level Care Facility · Bed Capacity: 250 (214 Occupied) · 24/7 Cath Lab & Emergency ICU Active',
    specialists: {
      cardio: { label: 'Cardiologist: Active (Dr. K. Verma)', avail: true, ref: null },
      obgyn: { label: 'OB-GYN: Active (Dr. S. Roy)', avail: true, ref: null },
      genmed: { label: 'Gen Medicine: Active (Duty MO)', avail: true, ref: null },
      pulmo: { label: 'Pulmonologist: Active (Dr. M. Khan)', avail: true, ref: null },
      endo: { label: 'Endocrinologist: Active (OPD 2)', avail: true, ref: null }
    },
    defaultReferralDestination: 'AIIMS Gorakhpur / King George Medical University Lucknow (Super-Specialty)'
  },
  campus_iitk: {
    type: 'Campus Health Center',
    name: 'Health Center IIT Kanpur — Institutional Clinic',
    subtext: 'Institutional Health Unit · Bed Capacity: 8 (3 Occupied) · Nearest Referral: Regency Hospital Kanpur (8.5km)',
    specialists: {
      cardio: { label: 'Cardiologist: None (Visiting Sat)', avail: false, ref: 'Regency Hospital Kanpur' },
      obgyn: { label: 'OB-GYN: None (On-Call)', avail: false, ref: 'GSVM Medical College Kanpur' },
      genmed: { label: 'Gen Medicine: Active (Duty MO)', avail: true, ref: null },
      pulmo: { label: 'Pulmonologist: None', avail: false, ref: 'Regency Hospital Kanpur' },
      endo: { label: 'Endocrinologist: None', avail: false, ref: 'Regency Hospital Kanpur' }
    },
    defaultReferralDestination: 'Regency Hospital Kanpur (Emergency Trauma & Critical Care, 8.5 km)'
  }
};

let currentFacilityKey = 'phc_manikpur';

/* ── 2. COMPREHENSIVE CLINICAL PATIENT DATASET ──────────────── */
const patients = {
  P001: {
    name: 'Radha Kumari',
    age: 42,
    gender: 'F',
    meta: '42F · Patient ID: JVA-P001 · Intake: 8 min ago',
    avatar: 'R',
    avatarClass: 'pa-coral',
    urgency: 'red',
    badge: 'Critical',
    lang: 'Hindi',
    intakeMode: 'Voice + OCR Intake',
    pid: 'JVA-P001',
    phone: '+91 98765 43210',
    consent: {
      isProxy: true,
      text: 'Proxy Consent by Ramesh Kumari (Husband) — Recorded at Manikpur Kiosk',
      lang: 'Consent recorded in Hindi audio · Verified by Kiosk ANM Sunita'
    },
    conflict: {
      hasConflict: true,
      title: 'Cross-Engine Disagreement Detected',
      message: 'PaddleOCR reading from physical lab slip shows <strong>BP 170/105 mmHg</strong>, whereas patient recorded voice response indicated <strong>160/100 mmHg</strong>.',
      action: 'Action Required: needs checking by clinician during exam'
    },
    summary: 'Patient presents with acute-onset retrosternal chest pain of 2 hours duration, radiating down the left arm. Known hypertensive for 5 years on irregular medication. Patient appears anxious, pale, and diaphoretic. Pain onset was at rest and has not responded to home remedies. No cough, fever, or prior anginal episodes reported. <strong>Urgency signals: Acute chest pain + radiation pattern + diaphoresis + hypertensive crisis (AIIMS ATP Tier 1 Red Flag).</strong>',
    rulesTrace: [
      { code: 'ATP-CARD-01', desc: 'Acute chest pain radiating to left arm + Diaphoresis', outcome: 'Immediate Critical', cls: 'red' },
      { code: 'ATP-VITAL-04', desc: 'Systolic BP ≥160 mmHg with cardiac symptoms', outcome: 'Hypertensive Crisis', cls: 'red' }
    ],
    vitals: [
      { v: '160/100', cls: 'danger', l: 'BP (mmHg)', sourceTag: 'Voice Snippet: 00:14', sourceCrop: 'audio_bp', needsCheck: true },
      { v: '98.2°F', cls: 'normal', l: 'Temp', sourceTag: 'Kiosk Infrared Sensor', sourceCrop: 'sensor_temp', needsCheck: false },
      { v: '97%', cls: 'normal', l: 'SpO₂', sourceTag: 'Pulse Oximeter Probe #2', sourceCrop: 'sensor_spo2', needsCheck: false },
      { v: '104', cls: 'danger', l: 'Pulse (bpm)', sourceTag: 'Pulse Oximeter Waveform', sourceCrop: 'sensor_pulse', needsCheck: false }
    ],
    ocr: {
      filename: 'Blood_report_Radha_P001.jpg — PaddleOCR v2.6',
      findings: [
        { name: 'Troponin I (Cardiac Marker)', value: '0.08 ng/mL ↑', ref: 'Normal <0.04', cls: 'abnormal', cropKey: 'crop_troponin', needsCheck: true },
        { name: 'Total Cholesterol', value: '238 mg/dL ↑', ref: 'Normal <200', cls: 'abnormal', cropKey: 'crop_cholesterol', needsCheck: false },
        { name: 'Haemoglobin', value: '11.8 g/dL', ref: 'Normal 12.0-15.0', cls: 'normal', cropKey: 'crop_hb', needsCheck: false },
        { name: 'Random Blood Glucose', value: '142 mg/dL', ref: 'Normal 70-140', cls: 'warning', cropKey: 'crop_glucose', needsCheck: false }
      ]
    },
    trending: [
      { param: 'Systolic BP (mmHg)', past2: '138', past1: '148', today: '160 ↑', trend: 'Worsening', arrow: 'up-bad', bars: [45, 65, 90] },
      { param: 'Diastolic BP (mmHg)', past2: '86', past1: '92', today: '100 ↑', trend: 'Worsening', arrow: 'up-bad', bars: [50, 70, 95] },
      { param: 'Total Cholesterol (mg/dL)', past2: '210', past1: '224', today: '238 ↑', trend: 'Elevated', arrow: 'up-bad', bars: [60, 75, 88] }
    ],
    flags: [
      '12-lead ECG not yet recorded at kiosk — AIIMS ATP mandates immediate clinician order',
      'Antihypertensive medication adherence history incomplete (brand name unknown)',
      'Family history of premature myocardial infarction not recorded in intake'
    ],
    followup: [
      { tag: 'Angina Onset', q: 'Did the chest heaviness start during physical effort or while sitting completely at rest?' },
      { tag: 'Medication Adherence', q: 'Did you take your morning blood pressure pill today or have you missed doses recently?' },
      { tag: 'Gastric vs Cardiac', q: 'Does the pain change when taking a deep breath or changing body posture?' }
    ],
    specialistRequired: 'cardio',
    autoEscalateSeconds: 462
  },

  P002: {
    name: 'Suresh Babu',
    age: 68,
    gender: 'M',
    meta: '68M · Patient ID: JVA-P002 · Intake: 14 min ago',
    avatar: 'S',
    avatarClass: 'pa-purple',
    urgency: 'red',
    badge: 'Critical',
    lang: 'Telugu',
    intakeMode: 'Voice + Nurse Vitals',
    pid: 'JVA-P002',
    phone: '+91 94401 23456',
    consent: {
      isProxy: false,
      text: 'Direct Patient Biometric Consent — Confirmed on Kiosk Touchscreen',
      lang: 'Consent recorded in Telugu audio · Non-proxy'
    },
    conflict: { hasConflict: false, title: '', message: '', action: '' },
    summary: 'Elderly male with 10-year documented COPD presenting with acute breathlessness and respiratory distress over 3 days. SpO₂ on room air is 89% (Emergency threshold). Accessory muscle use present; unable to speak in full sentences. Yellowish sputum for 48 hours with low-grade fever. <strong>Urgency signals: SpO₂ &lt;90% on room air + acute COPD exacerbation + tachypnea 28/min (AIIMS ATP Tier 1 Red Flag).</strong>',
    rulesTrace: [
      { code: 'ATP-RESP-02', desc: 'Room air SpO₂ &lt;90% in acute respiratory distress', outcome: 'Immediate Oxygenation', cls: 'red' },
      { code: 'ATP-RESP-06', desc: 'Inability to complete full sentences in known COPD', outcome: 'Severe Exacerbation', cls: 'red' }
    ],
    vitals: [
      { v: '89%', cls: 'danger', l: 'SpO₂ (Room Air)', sourceTag: 'Oximeter Probe #1 (Re-verified)', sourceCrop: 'sensor_spo2', needsCheck: true },
      { v: '28/min', cls: 'danger', l: 'Resp Rate', sourceTag: 'Nurse Counter Entry', sourceCrop: 'nurse_rr', needsCheck: false },
      { v: '118/76', cls: 'normal', l: 'BP (mmHg)', sourceTag: 'Digital Cuff #3', sourceCrop: 'sensor_bp', needsCheck: false },
      { v: '112', cls: 'danger', l: 'Pulse (bpm)', sourceTag: 'Pulse Oximeter', sourceCrop: 'sensor_pulse', needsCheck: false }
    ],
    ocr: null,
    trending: [
      { param: 'SpO₂ Room Air (%)', past2: '94%', past1: '92%', today: '89% ↓', trend: 'Hypoxemia Critical', arrow: 'down-bad', bars: [85, 75, 45] },
      { param: 'Respiratory Rate (/min)', past2: '18', past1: '20', today: '28 ↑', trend: 'Tachypnea', arrow: 'up-bad', bars: [40, 50, 95] }
    ],
    flags: [
      'Arterial Blood Gas (ABG) analyzer unavailable at this Primary Health Center',
      'Portable chest X-ray pending clinician authorization',
      'Inhaler compliance not documented in intake record'
    ],
    followup: [
      { tag: 'Oxygen History', q: 'Do you have home oxygen concentrator or cylinder at home?' },
      { tag: 'Sputum Evolution', q: 'Has your sputum changed from clear to dark green or blood-streaked?' },
      { tag: 'Steroid Use', q: 'Have you taken oral prednisolone or nebulized salbutamol in the last 24 hours?' }
    ],
    specialistRequired: 'pulmo',
    autoEscalateSeconds: 255
  },

  P003: {
    name: 'Ananya Roy',
    age: 26,
    gender: 'F',
    meta: '26F · Patient ID: JVA-P003 · Maternal 32 Weeks · Intake: 22 min ago',
    avatar: 'A',
    avatarClass: 'pa-coral',
    urgency: 'red',
    badge: 'Critical',
    lang: 'Bengali',
    intakeMode: 'Antenatal Card OCR + Nurse Intake',
    pid: 'JVA-P003',
    phone: '+91 98310 98765',
    consent: {
      isProxy: true,
      text: 'Proxy Consent by Sarita Roy (Mother-in-law) — Maternal Intake Kiosk',
      lang: 'Consent recorded in Bengali · Caregiver Proxy Authorized'
    },
    conflict: {
      hasConflict: true,
      title: 'Lab Extract Disagreement on Urine Protein',
      message: 'Mobile camera dipstick reader tagged <strong>Protein 3+</strong> while handwritten note in Mother-Child Card recorded <strong>Protein 1+</strong> at previous Sub-Center visit.',
      action: 'Action Required: needs checking via fresh clean-catch dipstick'
    },
    summary: 'Primigravida at 32 weeks gestation presenting with severe persistent frontal headache, blurred vision, and bilateral pedal oedema for 24 hours. Blood pressure today is 148/96 mmHg (severe gestational hypertension range). Urine dipstick shows proteinuria 2+. Fetal movements reported as active today. <strong>Urgency signals: BP ≥140/90 after 20w + severe persistent headache + visual disturbance + proteinuria = Pre-eclampsia Red Flag (AIIMS ATP &amp; Maternal Triage Tier 1).</strong>',
    rulesTrace: [
      { code: 'ATP-MAT-01', desc: 'Gestational age >20w + BP ≥140/90 + Neurological symptoms', outcome: 'Pre-Eclampsia Red Flag', cls: 'red' },
      { code: 'ATP-MAT-04', desc: 'Proteinuria ≥2+ in pregnancy with hypertension', outcome: 'Urgent Obstetric Care', cls: 'red' }
    ],
    vitals: [
      { v: '148/96', cls: 'danger', l: 'BP (mmHg)', sourceTag: 'Manual Mercury Sphygmomanometer', sourceCrop: 'nurse_bp', needsCheck: true },
      { v: '98.6°F', cls: 'normal', l: 'Temp', sourceTag: 'Infrared Sensor', sourceCrop: 'sensor_temp', needsCheck: false },
      { v: '98%', cls: 'normal', l: 'SpO₂', sourceTag: 'Pulse Oximeter Probe #3', sourceCrop: 'sensor_spo2', needsCheck: false },
      { v: '96', cls: 'warning', l: 'Pulse (bpm)', sourceTag: 'Pulse Oximeter', sourceCrop: 'sensor_pulse', needsCheck: false }
    ],
    ocr: {
      filename: 'MCH_Card_Ananya_P003.jpg — PaddleOCR v2.6',
      findings: [
        { name: 'Urine Protein Dipstick', value: '2+ (Moderate)', ref: 'Normal Nil', cls: 'abnormal', cropKey: 'crop_protein', needsCheck: true },
        { name: 'Haemoglobin', value: '9.4 g/dL ↓', ref: 'Normal ≥11.0 in pregnancy', cls: 'abnormal', cropKey: 'crop_maternal_hb', needsCheck: false },
        { name: 'Gestational Fundal Height', value: '31 cm', ref: 'Compatible with 32 weeks', cls: 'normal', cropKey: 'crop_fundal', needsCheck: false },
        { name: 'Previous BP (at 28 weeks)', value: '124/82 mmHg', ref: 'Baseline Normotensive', cls: 'normal', cropKey: 'crop_base_bp', needsCheck: false }
      ]
    },
    trending: [
      { param: 'Systolic BP (mmHg)', past2: '118 (24w)', past1: '124 (28w)', today: '148 (32w) ↑', trend: 'Acute Hypertensive Rise', arrow: 'up-bad', bars: [40, 52, 92] },
      { param: 'Diastolic BP (mmHg)', past2: '76 (24w)', past1: '82 (28w)', today: '96 (32w) ↑', trend: 'Severe Elevation', arrow: 'up-bad', bars: [45, 55, 95] },
      { param: 'Proteinuria', past2: 'Nil', past1: 'Trace', today: '2+ ↑', trend: 'Marked Progression', arrow: 'up-bad', bars: [10, 30, 85] }
    ],
    flags: [
      'Cardiotocography (CTG / Fetal Heart Monitor) not available at PHC Manikpur',
      'Serum Uric Acid and Liver Function Tests (LFTs) required to rule out HELLP syndrome',
      'No Obstetrician on site today — referral required under Emergency Obstetric Care (EmOC)'
    ],
    followup: [
      { tag: 'Epigastric Pain', q: 'Do you feel any severe pain right below your ribs or on the upper right side of your stomach?' },
      { tag: 'Visual Aura', q: 'Are you seeing flashing spots, zigzags, or dark shadows in your eyes right now?' },
      { tag: 'Fetal Kicks', q: 'How many distinct baby movements have you felt since morning today?' }
    ],
    specialistRequired: 'obgyn',
    autoEscalateSeconds: 690
  },

  P005: {
    name: 'Lakshmi Devi',
    age: 55,
    gender: 'F',
    meta: '55F · Patient ID: JVA-P005 · Chronic Diabetes · Intake: 38 min ago',
    avatar: 'L',
    avatarClass: 'pa-mint',
    urgency: 'yellow',
    badge: 'Semi-urgent',
    lang: 'Kannada',
    intakeMode: 'Lab Report OCR + Audio',
    pid: 'JVA-P005',
    phone: '+91 98801 11223',
    consent: {
      isProxy: false,
      text: 'Direct Patient Biometric Consent — Kiosk Fingerprint Authenticated',
      lang: 'Consent in Kannada audio · Direct'
    },
    conflict: {
      hasConflict: true,
      title: 'Lab Slip OCR Date Discrepancy',
      message: 'PaddleOCR extracted fasting blood glucose date as <strong>18-Sep-2026</strong> from external pathology slip, but patient stated test was done this morning (20-Sep).',
      action: 'Action Required: needs checking via point-of-care glucometer re-test'
    },
    summary: 'Known type-2 diabetic for 12 years presenting with progressive polyuria, polydipsia, blurring of vision, and extreme lethargy over the past 2 weeks. Uploaded lab slip shows Fasting Blood Glucose of 310 mg/dL and HbA1c of 9.8% (critically elevated). Currently prescribed Metformin 500mg BD + Glimepiride 1mg OD with reported poor compliance. <strong>Urgency signals: Fasting glucose >300 mg/dL + HbA1c >9% + blurred vision = Severe glycaemic decompensation requiring immediate medical modification.</strong>',
    rulesTrace: [
      { code: 'ATP-ENDO-02', desc: 'Fasting Blood Glucose >300 mg/dL with osmolar symptoms', outcome: 'Semi-Urgent Glycaemic', cls: 'yellow' },
      { code: 'ATP-ENDO-04', desc: 'HbA1c >9.0% chronic worsening trend', outcome: 'Medication Escalation', cls: 'yellow' }
    ],
    vitals: [
      { v: '310 mg/dL', cls: 'danger', l: 'Fasting Glucose', sourceTag: 'OCR Lab Slip Box #2', sourceCrop: 'crop_glucose_lakshmi', needsCheck: true },
      { v: '132/84', cls: 'warning', l: 'BP (mmHg)', sourceTag: 'Digital Cuff #2', sourceCrop: 'sensor_bp', needsCheck: false },
      { v: '98.4°F', cls: 'normal', l: 'Temp', sourceTag: 'Infrared Sensor', sourceCrop: 'sensor_temp', needsCheck: false },
      { v: '82', cls: 'normal', l: 'Pulse (bpm)', sourceTag: 'Pulse Oximeter', sourceCrop: 'sensor_pulse', needsCheck: false }
    ],
    ocr: {
      filename: 'HbA1c_Lakshmi_P005.pdf — PaddleOCR v2.6',
      findings: [
        { name: 'Glycated Haemoglobin (HbA1c)', value: '9.8% ↑↑', ref: 'Target <7.0%', cls: 'abnormal', cropKey: 'crop_hba1c_lakshmi', needsCheck: false },
        { name: 'Fasting Blood Sugar (FBS)', value: '310 mg/dL ↑↑', ref: 'Normal 70-110', cls: 'abnormal', cropKey: 'crop_fbs_lakshmi', needsCheck: true },
        { name: 'Serum Creatinine', value: '1.38 mg/dL', ref: 'Normal 0.6-1.2', cls: 'warning', cropKey: 'crop_creat_lakshmi', needsCheck: false },
        { name: 'Estimated GFR', value: '54 mL/min/1.73m²', ref: 'Stage 3a CKD Early Risk', cls: 'warning', cropKey: 'crop_egfr_lakshmi', needsCheck: false }
      ]
    },
    trending: [
      { param: 'HbA1c (%)', past2: '8.4% (6m ago)', past1: '9.1% (3m ago)', today: '9.8% Today ↑', trend: 'Progressive Rise', arrow: 'up-bad', bars: [50, 70, 95] },
      { param: 'Fasting Glucose (mg/dL)', past2: '210', past1: '265', today: '310 ↑', trend: 'Severe Worsening', arrow: 'up-bad', bars: [45, 68, 98] },
      { param: 'Serum Creatinine (mg/dL)', past2: '1.02', past1: '1.18', today: '1.38 ↑', trend: 'Renal Decline', arrow: 'up-bad', bars: [35, 50, 80] }
    ],
    flags: [
      'Urine microalbumin / creatinine ratio test overdue by 6 months',
      'Dilated fundoscopy eye exam not conducted in current calendar year',
      'Monofilament diabetic neuropathy sensory foot exam not recorded'
    ],
    followup: [
      { tag: 'Med Adherence', q: 'Are you taking your Glimepiride tablet before breakfast every single day or do you skip doses?' },
      { tag: 'Sensory Foot', q: 'Do you feel burning tingling or pins-and-needles in the soles of your feet at night?' },
      { tag: 'Urine Ketones', q: 'Have you felt any fruity smell in your breath or severe stomach cramping today?' }
    ],
    specialistRequired: 'endo',
    autoEscalateSeconds: 0
  },

  P008: {
    name: 'Priya Sharma',
    age: 24,
    gender: 'F',
    meta: '24F · Patient ID: JVA-P008 · Maternal 28 Weeks · Intake: 1h 2m ago',
    avatar: 'P',
    avatarClass: 'pa-mint',
    urgency: 'green',
    badge: 'Routine',
    lang: 'Hindi',
    intakeMode: 'Voice + Kiosk ANM',
    pid: 'JVA-P008',
    phone: '+91 98765 43210',
    consent: {
      isProxy: false,
      text: 'Direct Patient Digital Consent — Confirmed on Kiosk Screen',
      lang: 'Consent in Hindi · Direct'
    },
    conflict: { hasConflict: false, title: '', message: '', action: '' },
    summary: 'Primigravida at 28 weeks attending routine scheduled 3rd trimester antenatal check-up. Reports mild bilateral tension headache since morning, rating 2/10, relieved by rest. No photophobia, scotoma, nausea, or epigastric discomfort. Fetal kicks vigorous and regular. All maternal vitals within normal physiologic parameters. <strong>Urgency signals: None. Stable routine antenatal follow-up (AIIMS ATP Tier 3 Routine).</strong>',
    rulesTrace: [
      { code: 'ATP-ROUT-01', desc: 'Normotensive antenatal visit with benign mild symptom', outcome: 'Routine OPD Review', cls: 'green' }
    ],
    vitals: [
      { v: '118/76', cls: 'normal', l: 'BP (mmHg)', sourceTag: 'Digital Cuff #1', sourceCrop: 'sensor_bp', needsCheck: false },
      { v: '98.2°F', cls: 'normal', l: 'Temp', sourceTag: 'Infrared Sensor', sourceCrop: 'sensor_temp', needsCheck: false },
      { v: '99%', cls: 'normal', l: 'SpO₂', sourceTag: 'Pulse Oximeter', sourceCrop: 'sensor_spo2', needsCheck: false },
      { v: '78', cls: 'normal', l: 'Pulse (bpm)', sourceTag: 'Pulse Oximeter', sourceCrop: 'sensor_pulse', needsCheck: false }
    ],
    ocr: null,
    trending: [
      { param: 'Systolic BP (mmHg)', past2: '112 (16w)', past1: '116 (22w)', today: '118 (28w)', trend: 'Physiologically Stable', arrow: 'stable', bars: [40, 44, 46] },
      { param: 'Weight (kg)', past2: '51.5', past1: '54.0', today: '56.2', trend: 'Expected Maternal Gain', arrow: 'up-good', bars: [45, 55, 65] }
    ],
    flags: [
      'Iron & Folic Acid (IFA) tablet count check for compliance',
      'Tetanus Toxoid (Td-2 / Booster) documentation verification'
    ],
    followup: [
      { tag: 'Hydration & Rest', q: 'Did the mild headache start after prolonged sunlight exposure or missed meal?' },
      { tag: 'Fetal Movement', q: 'Are fetal movements consistent with your normal daily count?' }
    ],
    specialistRequired: 'obgyn',
    autoEscalateSeconds: 0
  }
};

/* ── 3. IMMUTABLE AUDIT TRAIL LOG (Regulatory G4) ───────────── */
const auditLog = [
  { timestamp: '2026-09-20 09:48:12', actor: 'Dr. Deepa Sharma (MO)', type: 'override', pid: 'JVA-P001', details: 'Downgraded Critical RED to Semi-Urgent. Rationale: "Repeat ECG normal, musculoskeletal tenderness on chest palpation"', superseded: 'ATP-CARD-01 superseded_by Dr. Deepa', hash: 'SHA256:7f49c0...' },
  { timestamp: '2026-09-20 09:40:05', actor: 'Engine Arbiter (YAML)', type: 'disagree', pid: 'JVA-P001', details: 'Disagreement: PaddleOCR BP (170/105) vs. Parrotlet Audio (160/100). Flagged for doctor check.', superseded: 'PaddleOCR-v2.6 vs. Parrotlet-v3', hash: 'SHA256:a18e9d...' },
  { timestamp: '2026-09-20 09:35:10', actor: 'Dr. Deepa Sharma (MO)', type: 'approve', pid: 'JVA-P012', details: 'Electronically signed triage note and dispatched routine medication prescription', superseded: 'Human Verified & Signed', hash: 'SHA256:bb4012...' },
  { timestamp: '2026-09-20 09:22:45', actor: 'Dr. Deepa Sharma (MO)', type: 'referral', pid: 'JVA-P003', details: 'Inter-hospital transfer note generated for District Hospital Gorakhpur (Obstetrics)', superseded: 'Auto-routed via specialist rule', hash: 'SHA256:ec9941...' },
  { timestamp: '2026-09-20 09:16:30', actor: 'Dr. Deepa Sharma (MO)', type: 'view', pid: 'JVA-P001', details: 'Patient card viewed via phone query (+91 98765 43210). Household disambiguation selected.', superseded: 'Explicit Doctor VIEW logged', hash: 'SHA256:99f012...' },
  { timestamp: '2026-09-20 09:15:22', actor: 'Auth Subsystem', type: 'view', pid: 'SYS', details: 'Medical Officer session authenticated. Registration UPMC-48921 verified with state registry.', superseded: 'Digital Credential STF-77492', hash: 'SHA256:11a4bb...' }
];

let activePatientId = 'P001';

/* ── 4. DOM ELEMENT REFERENCES ──────────────────────────────── */
const sidebar              = document.getElementById('dash-sidebar');
const sidebarToggle        = document.getElementById('sidebar-toggle');
const dashMain             = document.getElementById('dash-main');
const facilitySelector     = document.getElementById('facility-selector');
const queueSearch          = document.getElementById('queue-search');
const searchAuditNotice    = document.getElementById('search-audit-notice');
const btnOpenQrScanner     = document.getElementById('btn-open-qr-scanner');
const qrModal              = document.getElementById('qr-modal');
const btnCloseQr           = document.getElementById('btn-close-qr');
const cropModal            = document.getElementById('crop-modal');
const btnCloseCrop         = document.getElementById('btn-close-crop');
const btnDismissCrop       = document.getElementById('btn-dismiss-crop');
const cropPreviewContainer = document.getElementById('crop-preview-container');
const cropTitle            = document.getElementById('crop-title');
const cropSubtitle         = document.getElementById('crop-subtitle');
const cropConfidenceTag    = document.getElementById('crop-confidence-tag');
const overrideModal        = document.getElementById('override-modal');
const btnOverrideFlag      = document.getElementById('btn-override-flag');
const btnCancelOverride    = document.getElementById('btn-cancel-override');
const btnSubmitOverride    = document.getElementById('btn-submit-override');
const overrideCategory     = document.getElementById('override-category');
const overrideReason       = document.getElementById('override-reason');
const overrideCharCounter  = document.getElementById('override-char-counter');
const referralModal        = document.getElementById('referral-modal');
const btnReferral          = document.getElementById('btn-referral');
const btnCloseReferral     = document.getElementById('btn-close-referral');
const referralFacilityNotice= document.getElementById('referral-facility-notice');
const referralNoteText     = document.getElementById('referral-note-text');
const btnCopyReferral      = document.getElementById('btn-copy-referral');
const btnPrintReferral     = document.getElementById('btn-print-referral');
const btnDispatchAmbulance = document.getElementById('btn-dispatch-ambulance');
const escalationModal      = document.getElementById('escalation-modal');
const btnEscalate          = document.getElementById('btn-escalate');
const btnCancelEscalate    = document.getElementById('btn-cancel-escalate');
const btnConfirmEscalate   = document.getElementById('btn-confirm-escalate');
const escalateNotes        = document.getElementById('escalate-notes');
const editNoteModal        = document.getElementById('edit-note-modal');
const btnEdit              = document.getElementById('btn-edit');
const btnCloseEdit         = document.getElementById('btn-close-edit');
const btnCancelEdit        = document.getElementById('btn-cancel-edit');
const btnSaveEdit          = document.getElementById('btn-save-edit');
const editSummaryTextarea  = document.getElementById('edit-summary-textarea');
const editPatientName      = document.getElementById('edit-patient-name');
const btnApprove           = document.getElementById('btn-approve');
const notifBtn             = document.getElementById('notif-btn');
const notifDrawer          = document.getElementById('notif-drawer');
const notifDrawerOverlay   = document.getElementById('notif-drawer-overlay');
const btnCloseNotif        = document.getElementById('btn-close-notif');
const topbarAvatar         = document.getElementById('topbar-avatar');
const profileDropdown      = document.getElementById('profile-dropdown');
const langToggleBtn        = document.getElementById('lang-toggle-btn');
const langModal            = document.getElementById('lang-modal');
const langClose            = document.getElementById('lang-close');
const langCloseX           = document.getElementById('lang-close-x');
const langConfirm          = document.getElementById('lang-confirm');
const toastContainer       = document.getElementById('toast-container');
const detailPanel          = document.getElementById('detail-panel');
const detailOverlay        = document.getElementById('detail-overlay');
const detailPH             = document.getElementById('detail-placeholder');
const detailContent        = document.getElementById('detail-content');

/* ── 5. TAB VIEW ROUTER ─────────────────────────────────────── */
function switchView(viewId) {
  // Hide all views
  document.querySelectorAll('.doctor-view').forEach(v => v.classList.remove('active'));

  // Show target view
  const targetView = document.getElementById(viewId);
  if (targetView) {
    targetView.classList.add('active');
  }

  // Synchronize sidebar active states
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === viewId);
  });

  // Synchronize bottom tab active states
  document.querySelectorAll('.doctor-bottom-nav .doc-tab-item').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.view === viewId);
  });
  if (window.JeeviaNav) {
    window.JeeviaNav.centerActive('.doctor-bottom-nav .jeevia-slider-track');
  }

  // Close mobile drawer if open
  closeDetailDrawer();

  // Scroll main container to top
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Log view navigation to audit log
  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'view',
    pid: 'SYS',
    details: `Navigated to dashboard view: ${viewId}`,
    superseded: 'Navigation state active',
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });
}
window.switchView = switchView;

// Attach click to sidebar nav items with data-view
document.querySelectorAll('.sidebar-nav .nav-item[data-view]').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    switchView(item.dataset.view);
  });
});

// Attach click to mobile bottom nav items with data-view
document.querySelectorAll('.doctor-bottom-nav .doc-tab-item[data-view]').forEach(tab => {
  tab.addEventListener('click', e => {
    e.preventDefault();
    switchView(tab.dataset.view);
  });
});

/* ── 6. FACILITY CONFIGURATION LOGIC ────────────────────────── */
function updateFacilityUI(facKey) {
  currentFacilityKey = facKey;
  const cfg = facilityConfigs[facKey];
  if (!cfg) return;

  document.getElementById('fac-type-badge').textContent = cfg.type;
  document.getElementById('fac-name-label').textContent = cfg.name;
  document.getElementById('fac-subtext').textContent = cfg.subtext;
  document.getElementById('dropdown-facility-name').textContent = cfg.name;

  // Update specialist chips
  const chipsContainer = document.getElementById('fac-specialists-chips');
  chipsContainer.innerHTML = Object.entries(cfg.specialists).map(([k, s]) => `
    <span class="fac-spec-chip ${s.avail ? 'available' : 'unavailable'}" id="chip-${k}">
      <span class="spec-status-dot ${s.avail ? 'on' : 'off'}"></span>
      ${s.label}
    </span>
  `).join('');

  showToast(`Switched facility context to: ${cfg.name}`, 'info');
}

if (facilitySelector) {
  facilitySelector.addEventListener('change', e => {
    updateFacilityUI(e.target.value);
  });
}

/* ── 7. POPULATE PATIENT DETAIL PANEL ───────────────────────── */
function renderPatientDetail(pid) {
  activePatientId = pid;
  const p = patients[pid];
  if (!p) return;

  // Header & Avatar
  const avatarEl = document.getElementById('detail-avatar');
  avatarEl.textContent = p.avatar;
  avatarEl.className = `detail-avatar ${p.avatarClass}`;
  document.getElementById('detail-name').textContent = p.name;
  document.getElementById('detail-meta').textContent = p.meta;
  document.getElementById('detail-pid').textContent = `ID: ${p.pid}`;
  document.getElementById('detail-lang').textContent = p.lang;
  document.getElementById('detail-intake-mode').textContent = p.intakeMode;

  // Urgency badge
  const badgeEl = document.getElementById('detail-triage-badge');
  badgeEl.textContent = p.badge;
  badgeEl.className = `triage-badge triage-${p.urgency}`;

  // Consent Context
  const consentChip = document.getElementById('detail-consent-chip');
  consentChip.className = `consent-detail-chip ${p.consent.isProxy ? 'proxy-consent' : 'direct-consent'}`;
  document.getElementById('detail-consent-text').textContent = p.consent.text;
  document.getElementById('detail-consent-lang').innerHTML = `<svg class="dash-icon-sm" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> <span>${p.consent.lang}</span>`;

  // Conflict Banner (Engine disagreement)
  const conflictBanner = document.getElementById('conflict-banner');
  if (p.conflict && p.conflict.hasConflict) {
    conflictBanner.className = 'conflict-banner show';
    conflictBanner.querySelector('.conflict-title').textContent = p.conflict.title;
    document.getElementById('conflict-text').innerHTML = p.conflict.message;
    conflictBanner.querySelector('.conflict-needs-check span:last-child').textContent = p.conflict.action;
  } else {
    conflictBanner.className = 'conflict-banner';
  }

  // AI Structured Summary
  document.getElementById('detail-summary').innerHTML = p.summary;

  // Rules Engine Matches
  const rulesList = document.getElementById('rules-trace-list');
  rulesList.innerHTML = p.rulesTrace.map(r => `
    <div class="rule-trace-item">
      <div class="rule-trace-dot ${r.cls}"></div>
      <div>
        <span class="rule-name">${r.code}:</span>
        <span class="rule-trigger">${r.desc}</span>
      </div>
      <span class="rule-outcome ${r.cls}">${r.outcome}</span>
    </div>
  `).join('');

  // Vitals Grid with interactive Source Traceability
  const vitalsGrid = document.getElementById('detail-vitals');
  vitalsGrid.innerHTML = p.vitals.map(v => `
    <div class="vital-chip ${v.needsCheck ? 'conflict-flag' : ''}">
      <div class="vital-value ${v.cls}">${v.v}</div>
      <div class="vital-label">${v.l}</div>
      <div class="vital-source ${v.needsCheck ? 'needs-check' : ''}" onclick="showEvidenceModal('${v.sourceCrop}', '${v.l}: ${v.v}')" role="button" tabindex="0" title="Click to inspect raw evidence">
        <svg class="dash-icon-sm" viewBox="0 0 24 24">${v.sourceCrop.startsWith("audio") ? "<path d=\"M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z\"/><path d=\"M19 10v2a7 7 0 0 1-14 0v-2\"/>" : "<path d=\"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z\"/><polyline points=\"14 2 14 8 20 8\"/>"}</svg>
        <span>${v.sourceTag}</span>
        ${v.needsCheck ? '<span style="color:#DC2626; font-weight:800;">[needs checking]</span>' : ''}
      </div>
    </div>
  `).join('');

  // OCR Lab Findings
  const ocrSection = document.getElementById('detail-ocr');
  if (p.ocr) {
    ocrSection.style.display = '';
    document.getElementById('ocr-filename').textContent = p.ocr.filename;
    const findingsList = document.getElementById('ocr-findings-list');
    findingsList.innerHTML = p.ocr.findings.map(f => `
      <div class="ocr-finding-row">
        <div class="ocr-finding-name">${f.name} <span style="font-size:10px; color:var(--muted); font-style:italic;">(${f.ref})</span></div>
        <div class="ocr-finding-value">
          <span class="ocr-finding-number ${f.cls}">${f.value}</span>
          <span class="ocr-source-tag ${f.needsCheck ? 'needs-check' : 'from-ocr'}" onclick="showEvidenceModal('${f.cropKey}', '${f.name}: ${f.value}')" role="button" tabindex="0" title="View cropped report region">
            <svg class="dash-icon-sm" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> <span>Box Crop</span>
            ${f.needsCheck ? '<span style="font-weight:800; color:#DC2626;">needs checking</span>' : ''}
          </span>
        </div>
      </div>
    `).join('');
  } else {
    ocrSection.style.display = 'none';
  }

  // Longitudinal Trending Table
  const trendingSection = document.getElementById('detail-trending');
  if (p.trending && p.trending.length > 0) {
    trendingSection.style.display = '';
    const tbody = document.getElementById('trending-table-body');
    tbody.innerHTML = p.trending.map(t => `
      <tr>
        <td style="font-weight:700; color:var(--dark);">${t.param}</td>
        <td>${t.past2}</td>
        <td>${t.past1}</td>
        <td class="today-col">${t.today}</td>
        <td><span class="trend-arrow ${t.arrow}">${t.trend}</span></td>
        <td>
          <div class="trend-sparkline">
            <div class="spark-bar" style="height: ${t.bars[0]}%;"></div>
            <div class="spark-bar" style="height: ${t.bars[1]}%;"></div>
            <div class="spark-bar today ${t.arrow === 'up-bad' ? 'danger' : ''}" style="height: ${t.bars[2]}%;"></div>
          </div>
        </td>
      </tr>
    `).join('');
  } else {
    trendingSection.style.display = 'none';
  }

  // Flags Checklist
  const flagsList = document.getElementById('flags-list');
  flagsList.innerHTML = p.flags.map(f => `
    <div class="flag-item">
      <div class="flag-dot"></div>
      <span>${f}</span>
    </div>
  `).join('');

  // Follow-up Interview Prompts
  const followupList = document.getElementById('followup-list');
  followupList.innerHTML = p.followup.map(q => `
    <div class="followup-q">
      <span class="fq-tag">${q.tag}</span>
      <div>${q.q}</div>
    </div>
  `).join('');

  // Show content, hide placeholder
  detailPH.style.display = 'none';
  detailContent.classList.add('active');

  // Highlight selected row in queue
  document.querySelectorAll('.patient-row').forEach(r => r.classList.remove('selected'));
  const rowEl = document.getElementById(`row-${pid}`);
  if (rowEl) rowEl.classList.add('selected');

  // Mobile drawer support
  if (window.innerWidth <= 900) {
    detailPanel.classList.add('open');
    detailOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  detailPanel.scrollTop = 0;
}
window.renderPatientDetail = renderPatientDetail;

/* ── 8. PATIENT ROW SELECTION & NOTIF SHORTCUT ───────────────── */
function selectAndReview(pid) {
  if (notifDrawer.classList.contains('open')) {
    notifDrawer.classList.remove('open');
    notifDrawerOverlay.classList.remove('open');
  }
  switchView('view-queue');
  renderPatientDetail(pid);
}
window.selectAndReview = selectAndReview;

document.querySelectorAll('.patient-row').forEach(row => {
  row.addEventListener('click', () => {
    const pid = row.dataset.patient;
    renderPatientDetail(pid);
  });
  row.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      renderPatientDetail(row.dataset.patient);
    }
  });
});

/* ── 9. REAL-TIME AUTO-ESCALATION COUNTDOWN ─────────────────── */
const activeTimers = {
  P001: 462, // 7m 42s
  P002: 255, // 4m 15s
  P003: 690  // 11m 30s
};

function tickCountdowns() {
  Object.keys(activeTimers).forEach(pid => {
    if (activeTimers[pid] > 0) {
      activeTimers[pid]--;
      const mins = Math.floor(activeTimers[pid] / 60);
      const secs = activeTimers[pid] % 60;
      const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
      const el = document.getElementById(`countdown-${pid}`);
      if (el) {
        const valSpan = el.querySelector('.countdown-val');
        if (valSpan) {
          valSpan.textContent = `Auto-escalates: ${formatted}`;
        } else {
          el.innerHTML = `<svg class="dash-icon-sm" viewBox="0 0 24 24" style="width:12px; height:12px; vertical-align:-1px; margin-right:3px;" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg><span class="countdown-val">Auto-escalates: ${formatted}</span>`;
        }
      }
    } else if (activeTimers[pid] === 0) {
      activeTimers[pid] = -1;
      const el = document.getElementById(`countdown-${pid}`);
      if (el) {
        el.innerHTML = '<span class="countdown-val">Auto-Escalated to MO</span>';
        el.style.background = '#DC2626';
        el.style.color = '#fff';
      }
      const pName = patients[pid] ? patients[pid].name : pid;
      showToast(`Unreviewed critical case ${pName} (${pid}) auto-escalated to Tertiary On-Call!`, 'error');
    }
  });
}
setInterval(tickCountdowns, 1000);

/* ── 10. SEARCH & HOUSEHOLD PHONE DISAMBIGUATION (Tab 2) ─────── */
const findPatientInput = document.getElementById('find-patient-input');
const btnExecuteFindSearch = document.getElementById('btn-execute-find-search');
const candidateQueryLabel = document.getElementById('candidate-search-query');
const candidateCardsGrid = document.getElementById('candidate-cards-grid');

function executeFindSearch(query) {
  if (!query) query = findPatientInput.value.trim();
  if (!query) return;

  candidateQueryLabel.textContent = query;

  // Log search access to audit trail (Privacy Constraint)
  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'view',
    pid: query,
    details: `Manual search query executed for: "${query}". Restricted to PHC Manikpur facility scope.`,
    superseded: 'Search audit recorded',
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });

  const isPhoneSearch = /^(\+91|91)?[6-9]\d{2,9}$/.test(query.replace(/[\s\-\+]/g, ''));

  if (isPhoneSearch || query.includes('98765')) {
    // Shared household phone demonstration with 3 family members
    candidateCardsGrid.innerHTML = `
      <div class="candidate-card">
        <div class="candidate-header">
          <div class="patient-avatar pa-purple" style="width:36px; height:36px; font-size:14px;">R</div>
          <div>
            <div style="font-weight: 800; font-size: 14px; color: var(--dark);">Ramesh Kumar</div>
            <div style="font-size: 11px; color: var(--muted);">46M · Patient ID: JVA-P044</div>
          </div>
          <span class="candidate-relation-tag" style="margin-left: auto;">Head / Husband</span>
        </div>
        <div class="candidate-meta">
          <div><strong>Last Visit:</strong> 12-Jul-2026 (69 days ago)</div>
          <div><strong>Diagnosis:</strong> Essential Hypertension follow-up</div>
          <div><strong>Registered Facility:</strong> PHC Manikpur OPD #1</div>
        </div>
        <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="openPatientFromCandidate('P001')">
          Confirm &amp; Open Ramesh's Record
        </button>
      </div>

      <div class="candidate-card" style="border-color: var(--critical); background: rgba(220,38,38,0.02);">
        <div class="candidate-header">
          <div class="patient-avatar pa-coral" style="width:36px; height:36px; font-size:14px;">R</div>
          <div>
            <div style="font-weight: 800; font-size: 14px; color: var(--dark);">Radha Kumari</div>
            <div style="font-size: 11px; color: var(--muted);">42F · Patient ID: JVA-P001</div>
          </div>
          <span class="candidate-relation-tag" style="background:#FEE2E2; border-color:#FCA5A5; color:#991B1B; margin-left:auto;">
            Spouse / Wife (Active Intake Today)
          </span>
        </div>
        <div class="candidate-meta">
          <div><strong>Last Visit:</strong> Today, 20-Sep-2026 09:12 AM</div>
          <div><strong>Active Complaint:</strong> Retrosternal Chest Pain (2 hours)</div>
          <div><strong>Triage Assigned:</strong> Critical (AIIMS ATP Tier 1)</div>
        </div>
        <button class="btn btn-escalate btn-sm" style="width: 100%;" onclick="openPatientFromCandidate('P001')">
          Confirm Radha &amp; Open Live Triage Case
        </button>
      </div>

      <div class="candidate-card">
        <div class="candidate-header">
          <div class="patient-avatar pa-mint" style="width:36px; height:36px; font-size:14px;">P</div>
          <div>
            <div style="font-weight: 800; font-size: 14px; color: var(--dark);">Priya Kumar</div>
            <div style="font-size: 11px; color: var(--muted);">18F · Patient ID: JVA-P089</div>
          </div>
          <span class="candidate-relation-tag" style="margin-left: auto;">Daughter</span>
        </div>
        <div class="candidate-meta">
          <div><strong>Last Visit:</strong> 04-Aug-2026 (47 days ago)</div>
          <div><strong>Diagnosis:</strong> Seasonal allergic rhinitis</div>
          <div><strong>Immunization:</strong> Td booster complete</div>
        </div>
        <button class="btn btn-secondary btn-sm" style="width: 100%;" onclick="openPatientFromCandidate('P008')">
          Confirm &amp; Open Priya's Record
        </button>
      </div>
    `;
  } else {
    // Match against patients dictionary by ID or Name
    const cleanQ = query.toUpperCase();
    const matchedKey = Object.keys(patients).find(k => k === cleanQ || patients[k].pid === cleanQ || patients[k].name.toUpperCase().includes(cleanQ));
    if (matchedKey) {
      const p = patients[matchedKey];
      candidateCardsGrid.innerHTML = `
        <div class="candidate-card" style="grid-column: 1 / -1; max-width: 480px;">
          <div class="candidate-header">
            <div class="patient-avatar ${p.avatarClass}" style="width:40px; height:40px;">${p.avatar}</div>
            <div>
              <div style="font-weight: 800; font-size: 16px; color: var(--dark);">${p.name}</div>
              <div style="font-size: 12px; color: var(--muted);">${p.meta}</div>
            </div>
            <span class="triage-badge triage-${p.urgency}" style="margin-left: auto;">${p.badge}</span>
          </div>
          <div class="candidate-meta" style="margin-top: 10px;">
            <div><strong>Registered Phone:</strong> ${p.phone}</div>
            <div><strong>Consent Context:</strong> ${p.consent.text}</div>
            <div><strong>Active Summary:</strong> ${p.summary.replace(/<[^>]*>/g, '').substring(0, 110)}...</div>
          </div>
          <button class="btn btn-primary btn-sm" style="width: 100%; margin-top: 8px;" onclick="openPatientFromCandidate('${matchedKey}')">
            Confirm &amp; Open Clinical Record
          </button>
        </div>
      `;
    } else {
      candidateCardsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--muted); background: var(--bg); border-radius: var(--r-md);">
          No matching records found in PHC Manikpur facility database for query: "<strong>${query}</strong>"
        </div>
      `;
    }
  }
}

if (btnExecuteFindSearch) {
  btnExecuteFindSearch.addEventListener('click', () => executeFindSearch());
}

function triggerDemoSearch(type) {
  if (type === 'phone') {
    findPatientInput.value = '+91 98765 43210';
  } else {
    findPatientInput.value = type;
  }
  executeFindSearch();
}
window.triggerDemoSearch = triggerDemoSearch;

function openPatientFromCandidate(pid) {
  // Log explicit VIEW confirmation to audit trail
  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'view',
    pid: pid,
    details: `Doctor manually confirmed identity candidate and opened clinical record: ${patients[pid].name} (${pid})`,
    superseded: 'Identity verified',
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });

  switchView('view-queue');
  renderPatientDetail(pid);
  showToast(`Confirmed candidate match: Opened record for ${patients[pid].name} (${pid})`, 'success');
}
window.openPatientFromCandidate = openPatientFromCandidate;

/* ── 11. REVIEWED TODAY FILTERING & EXPORT (Tab 3) ───────────── */
const filterRevAll = document.getElementById('filter-rev-all');
const filterRevConfirmed = document.getElementById('filter-rev-confirmed');
const filterRevEscalated = document.getElementById('filter-rev-escalated');
const filterRevReferred = document.getElementById('filter-rev-referred');
const filterRevOverridden = document.getElementById('filter-rev-overridden');
const btnExportShiftFhir = document.getElementById('btn-export-shift-fhir');
const btnPrintShiftSummary = document.getElementById('btn-print-shift-summary');

function filterReviewedRows(filterKey) {
  const rows = document.querySelectorAll('#reviewed-patients-tbody tr');
  rows.forEach(r => {
    if (filterKey === 'all') {
      r.style.display = '';
    } else if (filterKey === 'overridden') {
      r.style.display = r.innerHTML.includes('Override') ? '' : 'none';
    } else if (filterKey === 'escalated') {
      r.style.display = r.innerHTML.includes('Escalated') ? '' : 'none';
    } else if (filterKey === 'referred') {
      r.style.display = r.innerHTML.includes('Referred') ? '' : 'none';
    } else if (filterKey === 'confirmed') {
      r.style.display = r.innerHTML.includes('Prescription Signed') ? '' : 'none';
    }
  });
}

[filterRevAll, filterRevConfirmed, filterRevEscalated, filterRevReferred, filterRevOverridden].forEach(btn => {
  if (btn) {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#view-reviewed .filter-pill').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      if (btn === filterRevAll) filterReviewedRows('all');
      if (btn === filterRevConfirmed) filterReviewedRows('confirmed');
      if (btn === filterRevEscalated) filterReviewedRows('escalated');
      if (btn === filterRevReferred) filterReviewedRows('referred');
      if (btn === filterRevOverridden) filterReviewedRows('overridden');
    });
  }
});

if (btnPrintShiftSummary) {
  btnPrintShiftSummary.addEventListener('click', () => window.print());
}

if (btnExportShiftFhir) {
  btnExportShiftFhir.addEventListener('click', () => {
    const bundle = {
      resourceType: 'Bundle',
      type: 'transaction',
      timestamp: new Date().toISOString(),
      facility: 'PHC Manikpur (UP)',
      practitioner: 'Dr. Deepa Sharma (UPMC-48921)',
      totalReviewedToday: 12,
      records: Object.keys(patients).map(k => ({
        patientId: patients[k].pid,
        name: patients[k].name,
        urgency: patients[k].urgency,
        summary: patients[k].summary.replace(/<[^>]*>/g, '')
      }))
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jeevia_shift_fhir_bundle_${Date.now()}.json`;
    a.click();
    showToast('FHIR R4 Bundle successfully exported to JSON!', 'success');
  });
}

/* ── 12. REFERRALS OUTGOING / INCOMING WORKFLOWS (Tab 4) ──────── */
const tabReferralOutgoing = document.getElementById('tab-referral-outgoing');
const tabReferralIncoming = document.getElementById('tab-referral-incoming');
const referralsOutgoingPanel = document.getElementById('referrals-outgoing-panel');
const referralsIncomingPanel = document.getElementById('referrals-incoming-panel');
const btnCall108Dispatch = document.getElementById('btn-call-108-dispatch');

if (tabReferralOutgoing && tabReferralIncoming) {
  tabReferralOutgoing.addEventListener('click', () => {
    tabReferralOutgoing.classList.add('active');
    tabReferralIncoming.classList.remove('active');
    referralsOutgoingPanel.style.display = 'block';
    referralsIncomingPanel.style.display = 'none';
  });

  tabReferralIncoming.addEventListener('click', () => {
    tabReferralIncoming.classList.add('active');
    tabReferralOutgoing.classList.remove('active');
    referralsOutgoingPanel.style.display = 'none';
    referralsIncomingPanel.style.display = 'block';
  });
}

if (btnCall108Dispatch) {
  btnCall108Dispatch.addEventListener('click', () => {
    showToast('108 Fleet Dispatch Link Opened: Ambulance Unit UP-108-EMR-8839 assigned to PHC Manikpur.', 'error');
  });
}

/* ── 13. RULES RECONSTRUCTION SIMULATOR (Tab 6) ──────────────── */
const btnRunReconstruct = document.getElementById('btn-run-reconstruct');
const reconstructPidInput = document.getElementById('reconstruct-pid-input');
const reconstructionOutput = document.getElementById('reconstruction-output');

if (btnRunReconstruct) {
  btnRunReconstruct.addEventListener('click', () => {
    const rawPid = reconstructPidInput.value.trim().toUpperCase();
    const pidKey = rawPid.replace('JVA-', '');
    const p = patients[pidKey] || patients['P001'];

    reconstructionOutput.innerHTML = `
      [AUDIT RECONSTRUCTION TRACE — 6 MONTH VERIFICATION]<br>
      RECONSTRUCTION TIMESTAMP: ${new Date().toLocaleString('en-IN')}<br>
      TARGET RECORD: ${p.pid} (${p.name}, ${p.meta.split('·')[0].trim()})<br>
      FACILITY SCOPE: PHC Manikpur (L2-PHC District Chitrakoot)<br>
      IMMUTABLE PROTOCOL: AIIMS_ATP_v2.4_2026.08.yaml<br>
      EVALUATION ENGINE: Deterministic YAML Rule Parser v1.8 (Non-LLM)<br>
      --------------------------------------------------<br>
      EXTRACTED INPUT VECTOR AT MOMENT OF TRIAGE:<br>
      ${p.vitals.map(v => `  - ${v.l} = ${v.v} [Source: ${v.sourceTag}]`).join('<br>')}<br>
      --------------------------------------------------<br>
      RULE MATCHES FIRED:<br>
      ${p.rulesTrace.map((r, i) => `  ${i + 1}. [${r.code}] ${r.desc} -> ${r.outcome}`).join('<br>')}<br>
      --------------------------------------------------<br>
      FINAL ASSIGNED URGENCY: ${p.badge}<br>
      EXPLAINABILITY CERTIFICATE: Cryptographically verifiable under Section 43A of IT Act &amp; DISHA Standards.<br>
      AUDIT STATUS: Fully Defensible in Medical Review Board.
    `;
    showToast(`Reconstructed AIIMS ATP decision trace for ${p.pid}`, 'success');
  });
}

/* ── 14. AUDIT LOG FILTERING & CSV EXPORT (Tab 7) ────────────── */
const btnExportAuditCsv = document.getElementById('btn-export-audit-csv');
const auditFilterAll = document.getElementById('audit-filter-all');
const auditFilterOverride = document.getElementById('audit-filter-override');
const auditFilterDisagree = document.getElementById('audit-filter-disagree');
const auditFilterViews = document.getElementById('audit-filter-views');
const auditFilterApprovals = document.getElementById('audit-filter-approvals');

function filterAuditRows(type) {
  const rows = document.querySelectorAll('#audit-table-tbody tr');
  rows.forEach(r => {
    if (type === 'all') {
      r.style.display = '';
    } else {
      r.style.display = r.innerHTML.toLowerCase().includes(type) ? '' : 'none';
    }
  });
}

[auditFilterAll, auditFilterOverride, auditFilterDisagree, auditFilterViews, auditFilterApprovals].forEach(btn => {
  if (btn) {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#view-audit-log .filter-pill').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      if (btn === auditFilterAll) filterAuditRows('all');
      if (btn === auditFilterOverride) filterAuditRows('override');
      if (btn === auditFilterDisagree) filterAuditRows('disagree');
      if (btn === auditFilterViews) filterAuditRows('view');
      if (btn === auditFilterApprovals) filterAuditRows('approve');
    });
  }
});

if (btnExportAuditCsv) {
  btnExportAuditCsv.addEventListener('click', () => {
    let csv = 'Timestamp,Actor,EventType,PatientID,Details,SupersededTag,IntegrityHash\n';
    auditLog.forEach(a => {
      csv += `"${a.timestamp}","${a.actor}","${a.type}","${a.pid}","${(a.details || '').replace(/"/g, '""')}","${(a.superseded || '').replace(/"/g, '""')}","${a.hash}"\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jeevia_compliance_audit_trail_${Date.now()}.csv`;
    a.click();
    showToast('Audit Trail exported to CSV (G4 Regulatory Archive)!', 'success');
  });
}

/* ── 15. QR SCANNER MODAL & SIMULATION ───────────────────────── */
btnOpenQrScanner.addEventListener('click', () => {
  qrModal.classList.add('open');
});
btnCloseQr.addEventListener('click', () => {
  qrModal.classList.remove('open');
});

function simulateScan(scannedPid) {
  qrModal.classList.remove('open');
  if (patients[scannedPid]) {
    switchView('view-queue');
    renderPatientDetail(scannedPid);
    showToast(`Token QR Scanned: Identified patient ${patients[scannedPid].name} (${scannedPid})`, 'success');
  }
}
window.simulateScan = simulateScan;

/* ── 16. SOURCE EVIDENCE MODAL ───────────────────────────────── */
function showEvidenceModal(cropKey, titleLabel) {
  cropTitle.textContent = `Source Evidence: ${titleLabel}`;

  if (cropKey.startsWith('audio')) {
    cropSubtitle.textContent = 'Speech extraction playback with localized confidence timestamp';
    cropConfidenceTag.textContent = 'Speech Model: Parrotlet-Whisper-v3 (Hindi) · Alignment Score: 98.4%';
    cropPreviewContainer.innerHTML = `
      <div style="width:100%; color:white; text-align:center;">
        <div style="font-size:13px; font-style:italic; color:#F7ADAD; margin-bottom:12px;">
          "मेरा सीना दो घंटे से बहुत जोर से दर्द कर रहा है और बाएँ हाथ तक खिंचाव है..."
        </div>
        <div class="audio-waveform-visual">
          <div class="wave-bar" style="animation-delay: 0.1s;"></div>
          <div class="wave-bar" style="animation-delay: 0.3s;"></div>
          <div class="wave-bar" style="animation-delay: 0.2s;"></div>
          <div class="wave-bar" style="animation-delay: 0.5s;"></div>
          <div class="wave-bar" style="animation-delay: 0.4s;"></div>
          <div class="wave-bar" style="animation-delay: 0.6s;"></div>
          <div class="wave-bar" style="animation-delay: 0.2s;"></div>
          <div class="wave-bar" style="animation-delay: 0.4s;"></div>
        </div>
        <div style="font-size:11px; color:#94a3b8; margin-top:8px;">Audio timestamp offset: 00:08 - 00:16 · Sampling Rate: 16 kHz</div>
      </div>
    `;
  } else {
    cropSubtitle.textContent = 'Cropped pixel bounding box extracted by PaddleOCR-v2.6';
    cropConfidenceTag.textContent = 'OCR Engine: PaddleOCR v2.6 · Bounding Box: [x:148, y:312, w:280, h:38] · Confidence: 94.6%';
    cropPreviewContainer.innerHTML = `
      <div class="crop-simulated-image">
        <div style="color:#64748b; font-size:10px; border-bottom:1px solid #e2e8f0; padding-bottom:4px; margin-bottom:8px;">
          MANIKPUR PATHOLOGY LABORATORY · CHITRAKOOT (UP)
        </div>
        <div>TEST: CARDIAC ENZYMES PROFILE</div>
        <div class="crop-highlight-box">
          TROPONIN I (HIGH SENSITIVITY): 0.08 ng/mL [REF: &lt;0.04] ↑ CRITICAL
        </div>
        <div style="color:#94a3b8; font-size:10px; margin-top:6px;">
          Extracted pixel region: 240 DPI monochrome scan · Contrast normalized
        </div>
      </div>
    `;
  }

  cropModal.classList.add('open');
}
window.showEvidenceModal = showEvidenceModal;

btnCloseCrop.addEventListener('click', () => cropModal.classList.remove('open'));
btnDismissCrop.addEventListener('click', () => cropModal.classList.remove('open'));

/* ── 17. OVERRIDE RED FLAG MODAL ─────────────────────────────── */
btnOverrideFlag.addEventListener('click', () => {
  overrideReason.value = '';
  overrideCategory.value = '';
  overrideCharCounter.textContent = '0 / 15 chars min';
  btnSubmitOverride.disabled = true;
  btnSubmitOverride.style.opacity = '0.5';
  btnSubmitOverride.style.cursor = 'not-allowed';
  overrideModal.classList.add('open');
});

btnCancelOverride.addEventListener('click', () => {
  overrideModal.classList.remove('open');
});

overrideReason.addEventListener('input', () => {
  const len = overrideReason.value.trim().length;
  overrideCharCounter.textContent = `${len} / 15 chars min`;
  const valid = len >= 15 && overrideCategory.value !== '';
  btnSubmitOverride.disabled = !valid;
  btnSubmitOverride.style.opacity = valid ? '1' : '0.5';
  btnSubmitOverride.style.cursor = valid ? 'pointer' : 'not-allowed';
});

overrideCategory.addEventListener('change', () => {
  const len = overrideReason.value.trim().length;
  const valid = len >= 15 && overrideCategory.value !== '';
  btnSubmitOverride.disabled = !valid;
  btnSubmitOverride.style.opacity = valid ? '1' : '0.5';
  btnSubmitOverride.style.cursor = valid ? 'pointer' : 'not-allowed';
});

btnSubmitOverride.addEventListener('click', () => {
  const reasonText = overrideReason.value.trim();
  const cat = overrideCategory.value;
  const p = patients[activePatientId];

  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'override',
    pid: activePatientId,
    details: `Downgraded Critical RED to Semi-Urgent. Category: ${cat}. Rationale: "${reasonText}"`,
    superseded: `ATP Rule superseded_by Dr. Deepa (UPMC-48921)`,
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });

  p.urgency = 'yellow';
  p.badge = 'Semi-urgent (Overridden)';
  p.summary += `<br><br><span style="color:#92400E; font-size:12px; font-weight:700;">[AUDIT NOTE: Red flag downgraded to Semi-urgent by Dr. Deepa Sharma. Rationale: "${reasonText}"]</span>`;

  delete activeTimers[activePatientId];
  const countdownEl = document.getElementById(`countdown-${activePatientId}`);
  if (countdownEl) countdownEl.remove();

  const row = document.getElementById(`row-${activePatientId}`);
  if (row) {
    row.className = 'patient-row urgent-yellow selected';
    row.dataset.urgency = 'yellow';
    row.querySelector('.triage-badge').textContent = 'Semi (Overridden)';
    row.querySelector('.triage-badge').className = 'triage-badge triage-yellow';
  }

  const critEl = document.getElementById('stat-critical');
  const semiEl = document.getElementById('stat-semi');
  critEl.textContent = Math.max(0, parseInt(critEl.textContent) - 1);
  semiEl.textContent = parseInt(semiEl.textContent) + 1;

  overrideModal.classList.remove('open');
  renderPatientDetail(activePatientId);
  showToast(`RED flag overridden for ${p.name}. Logged to compliance audit registry.`, 'warning');
});

/* ── 18. REFERRAL GENERATOR MODAL ────────────────────────────── */
btnReferral.addEventListener('click', () => {
  const p = patients[activePatientId];
  const fac = facilityConfigs[currentFacilityKey];
  const reqSpecKey = p.specialistRequired || 'genmed';
  const specObj = fac.specialists[reqSpecKey] || { avail: true };

  const missingSpecialist = !specObj.avail;
  referralFacilityNotice.style.display = missingSpecialist ? 'block' : 'none';
  if (missingSpecialist) {
    referralFacilityNotice.innerHTML = `
      <svg class="dash-icon-sm" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg> <strong>Specialist Constraint Trigger:</strong> ${fac.name} has <strong>NO on-site specialist for ${reqSpecKey.toUpperCase()}</strong>.<br>
      The rules engine has auto-routed this transfer directly to: <strong>${fac.defaultReferralDestination}</strong>.
    `;
  }

  const referralContent = `================================================================
JEEVIA INTER-HOSPITAL CLINICAL TRANSFER NOTE
Governed under National Health Mission / Ayushman Bharat
================================================================
ORIGINATING FACILITY: ${fac.name}
RECEIVING FACILITY   : ${fac.defaultReferralDestination}
REFERRING CLINICIAN  : Dr. Deepa Sharma, MBBS, MD (UPMC-48921)
DATE & TIME          : ${new Date().toLocaleString('en-IN')}
TRANSFER PRIORITY    : ${p.urgency === 'red' ? 'CODE RED — IMMEDIATE AMBULANCE DISPATCH' : 'CODE YELLOW — TIMED TRANSFER'}

PATIENT IDENTIFIERS:
  Name        : ${p.name}
  Age / Gender: ${p.meta.split('·')[0]}
  Patient ID  : ${p.pid}
  Consent     : ${p.consent.text}

CLINICAL REASON FOR TRANSFER:
  Facility lacking specialist: [${reqSpecKey.toUpperCase()}]
  Primary Diagnosis/Impression:
  ${p.summary.replace(/<[^>]*>/g, '')}

STABILIZATION GIVEN EN ROUTE:
  - IV Access 18G cannula secured in Left forearm
  - Continuous vital telemetry via Jeevia Companion App
  - Target Transfer Window: Under 45 minutes

DIGITAL SIGNATURE HASH: SHA256:${Math.random().toString(36).substring(2)}${Math.random().toString(36).substring(2)}
================================================================`;

  referralNoteText.textContent = referralContent;
  referralModal.classList.add('open');
});

btnCloseReferral.addEventListener('click', () => referralModal.classList.remove('open'));

btnCopyReferral.addEventListener('click', () => {
  navigator.clipboard.writeText(referralNoteText.textContent).then(() => {
    showToast('Referral transfer note copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Referral note copied!', 'success');
  });
});

btnPrintReferral.addEventListener('click', () => window.print());

btnDispatchAmbulance.addEventListener('click', () => {
  showToast('108 Emergency Ambulance Dispatched! ETA: 12 minutes to PHC Manikpur.', 'error');
});

/* ── 19. ESCALATION MODAL ────────────────────────────────────── */
btnEscalate.addEventListener('click', () => {
  const p = patients[activePatientId];
  document.getElementById('escalate-title').textContent = `Escalate Case: ${p.name} (${p.pid})`;
  escalateNotes.value = `Urgent referral required for ${p.name}. Acute presentation. Initial vitals stabilized. Direct handover requested to Senior Duty MO.`;
  escalationModal.classList.add('open');
});

btnCancelEscalate.addEventListener('click', () => escalationModal.classList.remove('open'));

btnConfirmEscalate.addEventListener('click', () => {
  const p = patients[activePatientId];
  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'referral',
    pid: activePatientId,
    details: `Case escalated to Tertiary On-Call. Handover: ${escalateNotes.value}`,
    superseded: 'Escalation active',
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });
  escalationModal.classList.remove('open');
  showToast(`Case for ${p.name} successfully escalated to Senior Medical Officer at Tertiary Care!`, 'error');
});

/* ── 20. EDIT NOTE MODAL ─────────────────────────────────────── */
btnEdit.addEventListener('click', () => {
  const p = patients[activePatientId];
  editPatientName.textContent = p.name;
  editSummaryTextarea.value = p.summary.replace(/<[^>]*>/g, '');
  editNoteModal.classList.add('open');
});

btnCloseEdit.addEventListener('click', () => editNoteModal.classList.remove('open'));
btnCancelEdit.addEventListener('click', () => editNoteModal.classList.remove('open'));

btnSaveEdit.addEventListener('click', () => {
  const p = patients[activePatientId];
  p.summary = editSummaryTextarea.value.trim() + '<br><br><span style="font-size:11px; color:var(--muted); font-style:italic;">[Clinically edited & signed by Dr. Deepa Sharma on ' + new Date().toLocaleTimeString() + ']</span>';
  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'approve',
    pid: activePatientId,
    details: `Triage note manually amended by doctor. Original draft preserved in version history.`,
    superseded: 'Draft v1 superseded_by Dr. Deepa',
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });
  editNoteModal.classList.remove('open');
  renderPatientDetail(activePatientId);
  showToast(`Triage note for ${p.name} successfully updated & digitally signed!`, 'success');
});

/* ── 21. APPROVE NOTE WORKFLOW ──────────────────────────────── */
btnApprove.addEventListener('click', () => {
  const p = patients[activePatientId];
  auditLog.push({
    timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
    actor: 'Dr. Deepa Sharma (MO)',
    type: 'approve',
    pid: activePatientId,
    details: `Clinical triage note signed off. Transferred to Pharmacy & Inpatient Ward Queue.`,
    superseded: 'Final signed disposition',
    hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
  });

  showToast(`Note for ${p.name} approved & confirmed! Sent to pharmacy / ward queue.`, 'success');
  
  const row = document.getElementById(`row-${activePatientId}`);
  if (row) {
    row.style.opacity = '0.4';
    row.querySelector('.review-btn').textContent = 'Approved ';
    row.querySelector('.review-btn').className = 'review-btn secondary';
  }

  const revCount = document.getElementById('sidebar-reviewed-count');
  if (revCount) revCount.textContent = parseInt(revCount.textContent) + 1;

  closeDetailDrawer();
});

/* ── 22. NOTIFICATIONS DRAWER & AVATAR ───────────────────────── */
notifBtn.addEventListener('click', () => {
  notifDrawer.classList.add('open');
  notifDrawerOverlay.classList.add('open');
});

btnCloseNotif.addEventListener('click', closeNotifDrawer);
notifDrawerOverlay.addEventListener('click', closeNotifDrawer);

function closeNotifDrawer() {
  notifDrawer.classList.remove('open');
  notifDrawerOverlay.classList.remove('open');
}

topbarAvatar.addEventListener('click', e => {
  e.stopPropagation();
  profileDropdown.classList.toggle('open');
});

document.addEventListener('click', e => {
  if (!profileDropdown.contains(e.target) && e.target !== topbarAvatar) {
    profileDropdown.classList.remove('open');
  }
});

document.getElementById('dropdown-audit-view').addEventListener('click', e => {
  e.preventDefault();
  profileDropdown.classList.remove('open');
  switchView('view-audit-log');
});

/* ── 23. LANGUAGE MODAL (22 Scheduled Indian Languages) ─────── */
langToggleBtn.addEventListener('click', () => langModal.classList.add('open'));
document.getElementById('nav-lang-side').addEventListener('click', e => {
  e.preventDefault();
  langModal.classList.add('open');
});
langClose.addEventListener('click', () => langModal.classList.remove('open'));
if (langCloseX) langCloseX.addEventListener('click', () => langModal.classList.remove('open'));

document.querySelectorAll('#lang-modal .lang-option').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#lang-modal .lang-option').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

langConfirm.addEventListener('click', () => {
  const selected = langModal.querySelector('.lang-option.active');
  if (selected) {
    const langEng = selected.querySelector('.lang-english').textContent;
    const langNat = selected.querySelector('.lang-native').textContent;
    showToast(`System locale localized to: ${langNat} (${langEng}) across all 22 official schedules!`, 'success');
  }
  langModal.classList.remove('open');
});

/* ── 24. FILTER PILLS (Queue) ───────────────────────────────── */
document.querySelectorAll('.filter-pill[data-filter]').forEach(pill => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.filter-pill[data-filter]').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    const filter = pill.dataset.filter;
    document.querySelectorAll('.patient-row').forEach(row => {
      row.style.display = (filter === 'all' || row.dataset.urgency === filter) ? '' : 'none';
    });
  });
});

/* ── 25. QUEUE INLINE SEARCH ────────────────────────────────── */
queueSearch.addEventListener('input', () => {
  const query = queueSearch.value.trim().toLowerCase();
  const isPhoneSearch = /^(\+91|91)?[6-9]\d{2,9}$/.test(query.replace(/\s+/g, ''));
  if (isPhoneSearch) {
    searchAuditNotice.classList.add('show');
    auditLog.push({
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      actor: 'Dr. Deepa Sharma (MO)',
      type: 'view',
      pid: query,
      details: `Queue inline phone query executed: ${query}. Restricted to PHC Manikpur.`,
      superseded: 'Audit noted',
      hash: 'SHA256:' + Math.random().toString(36).substring(2, 10)
    });
  } else {
    searchAuditNotice.classList.remove('show');
  }

  document.querySelectorAll('.patient-row').forEach(row => {
    const name = row.querySelector('.patient-name').textContent.toLowerCase();
    const complaint = row.querySelector('.patient-complaint').textContent.toLowerCase();
    const pid = row.dataset.patient.toLowerCase();
    const matches = name.includes(query) || complaint.includes(query) || pid.includes(query);
    row.style.display = matches ? '' : 'none';
  });
});

/* ── 26. SIDEBAR COLLAPSE & MOBILE DRAWER ───────────────────── */
sidebarToggle.addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
  dashMain.classList.toggle('sidebar-collapsed');
  sidebarToggle.textContent = sidebar.classList.contains('collapsed') ? '›' : '‹';
});

detailOverlay.addEventListener('click', closeDetailDrawer);

function closeDetailDrawer() {
  detailPanel.classList.remove('open');
  detailOverlay.classList.remove('open');
  document.body.style.overflow = '';
}

/* ── 27. TOAST NOTIFICATION UTILITY ─────────────────────────── */
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(30px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
window.showToast = showToast;

/* ── 28. INITIALIZATION ON DOM READY ────────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
  const now = new Date();
  const dateEl = document.getElementById('topbar-date');
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  // Initial load of Radha Kumari (P001)
  renderPatientDetail('P001');

  // Initial candidate search prep
  executeFindSearch('+91 98765 43210');
});
