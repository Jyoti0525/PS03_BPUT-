/* ============================================================
   JEEVIA — Patient Intake Kiosk JS  (v3 — 3-Panel Layout)
   Consent modal → 3-panel kiosk → token overlay
   ============================================================ */

/* ══════════════════════════════════════════════════════════════
   APP STATE
══════════════════════════════════════════════════════════════ */
const appState = {
  // Identity
  lang:         'en',
  patientName:  '',
  patientAge:   '',
  patientGender:'',
  patientPhone: '',
  patientType:  '',   // new | returning | maternal | chronic

  // Symptoms
  symptoms:     '',   // combined text from all input methods
  voiceTranscript: '',
  timeline:     '',   // e.g. "2-3 days"
  severity:     null, // 1-10
  uploadsDone:  false,
  photosDone:   false,

  // Context engine answers
  contextAnswers: {},

  // Vitals (staff-only)
  vitals: {},
  urgency: 'green',   // green | yellow | red — NEVER shown to patient

  // Multiple complaints
  problems: [{ id: 0, label: 'Primary Complaint', symptoms: '' }],
  activeProblem: 0,

  // Session token
  tokenNumber:  '',
};

/* ══════════════════════════════════════════════════════════════
   CONSENT MODAL — 3-page flow
══════════════════════════════════════════════════════════════ */
let modalPage = 1;

/* ── Page 1: Consent ── */
const consentTog = document.getElementById('consent-tog');
const consentNextBtn = document.getElementById('consent-next-btn');

consentTog.addEventListener('change', () => {
  consentNextBtn.disabled = !consentTog.checked;
  document.getElementById('consent-agree-label').textContent = consentTog.checked
    ? '✅ Consent given — ready to continue'
    : 'I understand and agree to share my information for triage purposes';
});

// Large text mode
document.getElementById('large-text-tog').addEventListener('change', function () {
  document.documentElement.style.fontSize = this.checked ? '18px' : '';
});

// Language pills on consent page
document.querySelectorAll('.pi-lang-quick-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.pi-lang-quick-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    appState.lang = btn.dataset.lang;
    updateLangDisplay();
  });
});

consentNextBtn.addEventListener('click', () => goModalPage(2));
document.getElementById('identity-back-btn').addEventListener('click', () => goModalPage(1));
document.getElementById('identity-next-btn').addEventListener('click', () => goModalPage(3));
document.getElementById('type-back-btn').addEventListener('click', () => goModalPage(2));

function goModalPage(n) {
  document.querySelectorAll('.pi-mpage').forEach(p => p.classList.remove('active'));
  document.getElementById(`mpage-${n}`).classList.add('active');
  modalPage = n;
  // Update step indicators
  document.querySelectorAll('.pi-mstep').forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i + 1 < n) s.classList.add('done');
    if (i + 1 === n) s.classList.add('active');
  });
}

/* ── Page 2: Identity ── */
['pi-name','pi-age','pi-gender','pi-phone'].forEach(id => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener('change', e => {
      if (id === 'pi-name')   appState.patientName   = e.target.value;
      if (id === 'pi-age')    appState.patientAge    = e.target.value;
      if (id === 'pi-gender') appState.patientGender = e.target.value;
      if (id === 'pi-phone')  appState.patientPhone  = e.target.value;
    });
    el.addEventListener('input', e => {
      if (id === 'pi-name')   appState.patientName   = e.target.value;
      if (id === 'pi-age')    appState.patientAge    = e.target.value;
    });
  }
});

/* ── Page 3: Visit type ── */
const typeNextBtn = document.getElementById('type-next-btn');

document.querySelectorAll('.pi-type-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.pi-type-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    appState.patientType = card.dataset.type;
    typeNextBtn.disabled = false;
  });
});

typeNextBtn.addEventListener('click', () => {
  // Capture identity
  appState.patientName   = document.getElementById('pi-name').value   || 'Anonymous';
  appState.patientAge    = document.getElementById('pi-age').value    || '—';
  appState.patientGender = document.getElementById('pi-gender').value || '—';
  appState.patientPhone  = document.getElementById('pi-phone').value  || '';

  // Close modal, open kiosk
  document.getElementById('consent-modal').classList.remove('active');
  const kiosk = document.getElementById('kiosk');
  kiosk.style.display = 'flex';
  kiosk.style.flexDirection = 'column';
  kiosk.style.minHeight = '100vh';

  // Update kiosk top bar
  document.getElementById('kiosk-patient-name-display').textContent = appState.patientName;
  document.getElementById('kiosk-patient-meta-display').textContent =
    `${appState.patientAge}y · ${appState.patientGender || '—'} · ${
      { new:'New', returning:'Returning', maternal:'Maternal', chronic:'Chronic' }[appState.patientType] || ''
    }`;

  // Trigger scenario drawers if needed
  if (appState.patientType === 'maternal') activateMaternalMode();
  if (appState.patientType === 'chronic')  activateChronicMode();
  if (appState.patientType === 'returning') {
    addNoteEntry('🔄', 'Visit Type', 'Returning patient — historical records loaded');
  }

  // Add patient type to note
  if (appState.patientType === 'new') {
    addNoteEntry('🆕', 'Visit Type', 'New patient — first visit today');
  }
});


/* ══════════════════════════════════════════════════════════════
   LEFT PANEL: INPUT CLUSTER
══════════════════════════════════════════════════════════════ */

/* ── Card 1: Voice Recording ── */
let isRecording = false;
let recordingTimer = null;
let recSeconds = 0;

const demoTranscripts = [
  'मुझे 3 दिनों से बुखार है और सिर में बहुत दर्द हो रहा है। कमज़ोरी भी है।',
  'I have had fever for 3 days with severe headache, body ache, and weakness.',
  'నాకు 3 రోజుల నుండి జ్వరం, తలనొప్పి, మరియు చాలా అలసట ఉంది.',
  'எனக்கு 3 நாட்களாக காய்ச்சல், தலைவலி மற்றும் உடல் வலி உள்ளது.',
];
let demoTranscriptIdx = 0;

const bigMicBtn = document.getElementById('big-mic-btn');
const micIcon   = document.getElementById('mic-icon');
const micStatus = document.getElementById('mic-status');
const transcriptBox = document.getElementById('voice-transcript-box');

bigMicBtn.addEventListener('click', () => {
  if (!isRecording) {
    // Start recording
    isRecording = true;
    bigMicBtn.classList.add('recording');
    micIcon.textContent = '⏹️';
    micStatus.textContent = 'Recording… tap to stop';
    transcriptBox.classList.remove('show');
    recSeconds = 0;

    recordingTimer = setInterval(() => {
      recSeconds++;
      micStatus.textContent = `Recording… ${recSeconds}s — tap to stop`;
    }, 1000);

  } else {
    // Stop recording
    isRecording = false;
    clearInterval(recordingTimer);
    bigMicBtn.classList.remove('recording');
    micIcon.textContent = '✅';
    micStatus.textContent = 'Tap to record again';

    const transcript = demoTranscripts[demoTranscriptIdx % demoTranscripts.length];
    demoTranscriptIdx++;
    transcriptBox.textContent = transcript;
    transcriptBox.classList.add('show');
    appState.voiceTranscript = transcript;
    appState.symptoms = (appState.symptoms + ' ' + transcript).trim();

    // Update note and trigger context engine
    addNoteEntry('🎙️', 'Spoken Complaint', transcript.slice(0, 80) + (transcript.length > 80 ? '…' : ''));
    enableConfirmButton();
    setTimeout(() => triggerContextEngine(transcript), 600);
  }
});

/* ── Card 1: Text fallback ── */
const textFallbackToggle = document.getElementById('text-fallback-toggle');
const textFallbackArea   = document.getElementById('text-fallback-area');

textFallbackToggle.addEventListener('click', () => {
  const isHidden = textFallbackArea.style.display === 'none';
  textFallbackArea.style.display = isHidden ? 'block' : 'none';
  textFallbackToggle.textContent = isHidden ? '🎙️ Switch to voice instead' : '✍️ Prefer to type instead?';
});

const kioskTextarea = document.getElementById('kiosk-symptom-text');
let textDebounce = null;

kioskTextarea.addEventListener('input', function () {
  document.getElementById('text-char-hint').textContent = `${this.value.length} characters`;
  appState.symptoms = (appState.voiceTranscript + ' ' + this.value).trim();

  clearTimeout(textDebounce);
  if (this.value.length > 20) {
    textDebounce = setTimeout(() => {
      // Add to note
      addNoteEntry('✍️', 'Typed Complaint', this.value.slice(0, 80) + (this.value.length > 80 ? '…' : ''));
      triggerContextEngine(this.value);
      enableConfirmButton();
    }, 800);
  }
});

/* ── Card 2: Report Upload ── */
const uploadDropZone = document.getElementById('upload-drop-zone');
const reportFileInput = document.getElementById('report-file-input');
const ocrProcessing  = document.getElementById('ocr-processing');
const ocrResult      = document.getElementById('ocr-result');

uploadDropZone.addEventListener('click', () => reportFileInput.click());
uploadDropZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') reportFileInput.click(); });
uploadDropZone.addEventListener('dragover', e => { e.preventDefault(); uploadDropZone.classList.add('drag-over'); });
uploadDropZone.addEventListener('dragleave', () => uploadDropZone.classList.remove('drag-over'));
uploadDropZone.addEventListener('drop', e => { e.preventDefault(); uploadDropZone.classList.remove('drag-over'); simulateOCR(); });
reportFileInput.addEventListener('change', simulateOCR);

function simulateOCR() {
  uploadDropZone.style.display = 'none';
  ocrProcessing.style.display = 'flex';

  setTimeout(() => {
    ocrProcessing.style.display = 'none';
    ocrResult.style.display = 'block';
    ocrResult.style.animation = 'questionFadeIn 0.4s ease both';
    appState.uploadsDone = true;
    addNoteEntry('📄', 'Lab Report Uploaded', 'OCR extracted: Hb 9.2 g/dL (Low), Glucose 310 mg/dL (High)');
    enableConfirmButton();
    // Trigger context based on glucose
    triggerContextEngine('high glucose blood sugar diabetic');
  }, 2400);
}

/* ── Card 3: Photo Upload ── */
const photoDropZone  = document.getElementById('photo-drop-zone');
const photoFileInput = document.getElementById('photo-file-input');
const photoGrid      = document.getElementById('photo-preview-grid');

photoDropZone.addEventListener('click', () => photoFileInput.click());
photoDropZone.addEventListener('keydown', e => { if (e.key === 'Enter') photoFileInput.click(); });
photoFileInput.addEventListener('change', function () {
  if (this.files && this.files.length > 0) {
    simulatePhotoUpload(this.files[0].name);
  }
});

function simulatePhotoUpload(filename) {
  const thumb = document.createElement('div');
  thumb.className = 'photo-thumb';
  thumb.textContent = '📷';
  photoGrid.appendChild(thumb);
  appState.photosDone = true;
  addNoteEntry('🖼️', 'Photo Uploaded', `Image captured: ${filename || 'photo.jpg'}`);
  enableConfirmButton();
}

/* ── Card 4: Timeline Chips ── */
const timelineChips = document.querySelectorAll('.timeline-chip');
const timelineSelectedLabel = document.getElementById('timeline-selected-label');
const severitySection = document.getElementById('severity-section');

timelineChips.forEach(chip => {
  chip.addEventListener('click', () => {
    timelineChips.forEach(c => c.classList.remove('selected'));
    chip.classList.add('selected');
    appState.timeline = chip.dataset.value;

    timelineSelectedLabel.style.display = 'block';
    timelineSelectedLabel.textContent = `📅 Selected: "${appState.timeline}"`;

    // Show severity after timeline selection
    severitySection.style.display = 'block';
    severitySection.style.animation = 'questionFadeIn 0.3s ease both';

    addNoteEntry('📅', 'Symptom Start', `Started: ${appState.timeline}`);
    enableConfirmButton();
  });
});

/* ── Card 4: Severity Scale ── */
document.querySelectorAll('.severity-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.severity-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    appState.severity = parseInt(btn.dataset.val);
    addNoteEntry('🔢', 'Severity Rating', `${appState.severity}/10 — ${getSeverityText(appState.severity)}`);
    enableConfirmButton();
  });
});

function getSeverityText(v) {
  if (v <= 3) return 'Mild';
  if (v <= 6) return 'Moderate';
  if (v <= 8) return 'Severe';
  return 'Very severe';
}


/* ══════════════════════════════════════════════════════════════
   CENTER PANEL: CONTEXT ENGINE
══════════════════════════════════════════════════════════════ */

// Question bank — keyword → questions
const QUESTION_BANK = {
  fever:    [
    { id:'q-chills',     q:'Are you experiencing chills or shivering?', type:'chips', options:['Yes, intense chills','Mild chills','No chills'] },
    { id:'q-sweating',   q:'Do you have night sweats?', type:'chips', options:['Yes, heavy sweating','Mild','No'] },
    { id:'q-travel',     q:'Have you travelled recently or been exposed to anyone ill?', type:'chips', options:['Yes — travelled','Yes — contact','No'] },
  ],
  cough:    [
    { id:'q-chestpain',  q:'Are you experiencing any chest pain or tightness?', type:'chips', options:['Yes — severe','Mild','No chest pain'] },
    { id:'q-breathless', q:'Do you feel short of breath?', type:'chips', options:['Yes — at rest','Only on walking','No'] },
    { id:'q-sputum',     q:'Are you coughing up phlegm or blood?', type:'chips', options:['Yes — blood','Yes — phlegm','Dry cough only'] },
  ],
  headache: [
    { id:'q-vision',     q:'Any changes in your vision or seeing flashes of light?', type:'chips', options:['Yes','No'] },
    { id:'q-nausea',     q:'Do you feel nauseous or have you vomited?', type:'chips', options:['Yes — vomited','Nausea only','No'] },
    { id:'q-neck',       q:'Do you have stiffness in your neck?', type:'chips', options:['Yes','No'] },
  ],
  glucose:  [
    { id:'q-diabetes',   q:'Have you been told you have diabetes?', type:'chips', options:['Yes — Type 2','Yes — Type 1','Not confirmed','No'] },
    { id:'q-medicines',  q:'Are you currently taking medicines for blood sugar?', type:'text', placeholder:'e.g., Metformin 500mg' },
    { id:'q-thirst',     q:'Are you feeling unusually thirsty or urinating frequently?', type:'chips', options:['Yes — both','Just thirsty','Just urinating','No'] },
  ],
  pain:     [
    { id:'q-painloc',    q:'Where exactly do you feel the pain?', type:'text', placeholder:'e.g., lower back, stomach, chest' },
    { id:'q-paintype',   q:'What type of pain is it?', type:'chips', options:['Sharp/stabbing','Dull/aching','Burning','Cramping','Throbbing'] },
  ],
  weakness: [
    { id:'q-duration',   q:'How long have you been feeling this weakness?', type:'chips', options:['Since today','2–3 days','Since last week','Longer'] },
    { id:'q-eating',     q:'Are you eating and drinking normally?', type:'chips', options:['Yes','Reduced appetite','Cannot eat','No water intake'] },
  ],
};

const KEYWORD_MAP = [
  { keywords:['fever','bukhar','jwar','kaichal','jvara','bwokhar'], bank:'fever' },
  { keywords:['cough','khansi','kosam','irumal','khasi'], bank:'cough' },
  { keywords:['headache','sirdard','talanopp','talaivali','mathayardam'], bank:'headache' },
  { keywords:['glucose','sugar','diabetic','diabetes','madhumeha'], bank:'glucose' },
  { keywords:['pain','dard','vali','vethana','veytha'], bank:'pain' },
  { keywords:['weak','weakness','thakan','takkam','alasata'], bank:'weakness' },
];

const shownQuestions = new Set();
let totalQuestions = 0;
let answeredQuestions = 0;

function triggerContextEngine(text) {
  const lower = text.toLowerCase();
  let questionsAdded = 0;

  KEYWORD_MAP.forEach(({ keywords, bank }) => {
    if (keywords.some(kw => lower.includes(kw)) && QUESTION_BANK[bank]) {
      QUESTION_BANK[bank].forEach(q => {
        if (!shownQuestions.has(q.id)) {
          shownQuestions.add(q.id);
          renderContextQuestion(q);
          questionsAdded++;
          totalQuestions++;
        }
      });
    }
  });

  if (questionsAdded > 0) {
    // Hide empty state
    document.getElementById('context-empty').style.display = 'none';
    // Show progress bar
    document.getElementById('context-progress-bar').style.display = 'block';
    updateContextProgress();
  }
}

function renderContextQuestion(qData) {
  const container = document.getElementById('context-questions');
  const card = document.createElement('div');
  card.className = 'context-q-card';
  card.id = `qcard-${qData.id}`;
  card.style.animationDelay = `${container.children.length * 0.08}s`;

  let answerHtml = '';
  if (qData.type === 'chips') {
    answerHtml = `<div class="cq-options" role="group" aria-label="${qData.q}">
      ${qData.options.map(opt =>
        `<button class="cq-option-btn" data-qid="${qData.id}" data-val="${opt}">${opt}</button>`
      ).join('')}
    </div>`;
  } else if (qData.type === 'text') {
    answerHtml = `<input type="text" class="cq-text-input" id="cqin-${qData.id}" placeholder="${qData.placeholder || 'Your answer…'}" aria-label="${qData.q}">`;
  }

  card.innerHTML = `
    <div class="cq-question">${qData.q}</div>
    ${answerHtml}
  `;
  container.appendChild(card);

  // Chip answer listener
  card.querySelectorAll('.cq-option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const qid = btn.dataset.qid;
      const val = btn.dataset.val;
      card.querySelectorAll('.cq-option-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');

      const wasNew = !appState.contextAnswers[qid];
      appState.contextAnswers[qid] = val;
      if (wasNew) { answeredQuestions++; updateContextProgress(); }

      addNoteEntry('❓', 'Answered', `${qData.q.slice(0,40)}…: ${val}`);
    });
  });

  // Text input listener
  const textIn = card.querySelector('.cq-text-input');
  if (textIn) {
    let debounce = null;
    textIn.addEventListener('input', function () {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        const wasNew = !appState.contextAnswers[qData.id];
        appState.contextAnswers[qData.id] = this.value;
        if (wasNew && this.value.length > 2) {
          answeredQuestions++;
          updateContextProgress();
          addNoteEntry('❓', 'Answered', `${qData.q.slice(0,40)}…: ${this.value}`);
        }
      }, 600);
    });
  }
}

function updateContextProgress() {
  document.getElementById('cpb-answered').textContent = answeredQuestions;
  document.getElementById('cpb-total').textContent = totalQuestions;
  const pct = totalQuestions > 0 ? (answeredQuestions / totalQuestions) * 100 : 0;
  document.getElementById('cpb-fill').style.width = `${pct}%`;
}


/* ══════════════════════════════════════════════════════════════
   RIGHT PANEL: LIVE PATIENT NOTE BUILDER
══════════════════════════════════════════════════════════════ */
let noteEntryCount = 0;

function addNoteEntry(icon, label, value) {
  const noteEntries = document.getElementById('note-entries');

  // Hide empty state on first entry
  const emptyEl = document.getElementById('note-empty');
  if (emptyEl) emptyEl.remove();

  // Don't duplicate exact same value
  const existing = noteEntries.querySelectorAll('.note-entry-value');
  for (const el of existing) {
    if (el.textContent === value) return;
  }

  const now = new Date();
  const timeStr = now.toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' });

  const entry = document.createElement('div');
  entry.className = 'note-entry';
  entry.style.animationDelay = `${noteEntryCount * 0.06}s`;
  entry.innerHTML = `
    <div class="note-entry-icon">${icon}</div>
    <div class="note-entry-body">
      <div class="note-entry-label">${label}</div>
      <div class="note-entry-value">${value}</div>
      <div class="note-entry-time">${timeStr}</div>
    </div>
  `;
  noteEntries.appendChild(entry);
  noteEntryCount++;

  // Scroll to bottom
  noteEntries.scrollTop = noteEntries.scrollHeight;

  // Live indicator pulse
  const liveIndicator = document.getElementById('note-live-indicator');
  if (liveIndicator) {
    liveIndicator.style.color = '#F29191';
    setTimeout(() => { liveIndicator.style.color = ''; }, 1000);
  }
}

function enableConfirmButton() {
  const confirmBtn = document.getElementById('confirm-queue-btn');
  if (confirmBtn && noteEntryCount > 0) {
    confirmBtn.disabled = false;
  }
}

/* Confirm & Join Queue */
document.getElementById('confirm-queue-btn').addEventListener('click', () => {
  showTokenOverlay();
});


/* ══════════════════════════════════════════════════════════════
   QUEUE TOKEN OVERLAY
══════════════════════════════════════════════════════════════ */
function showTokenOverlay() {
  const letters = 'ABCDE';
  const letter = letters[Math.floor(Math.random() * letters.length)];
  const num = Math.floor(Math.random() * 90 + 10);
  appState.tokenNumber = `${letter}-${String(num).padStart(3, '0')}`;

  document.getElementById('token-display-number').textContent = appState.tokenNumber;

  // Wait time based on type
  const waits = { new:'~18 minutes', returning:'~12 minutes', maternal:'~8 minutes', chronic:'~10 minutes' };
  document.getElementById('token-display-wait').textContent = waits[appState.patientType] || '~20 minutes';

  // IMPORTANT SAFETY RULE: NO triage RED/YELLOW/GREEN shown to patient
  // Token overlay deliberately omits urgency color/badge

  const overlay = document.getElementById('token-overlay');
  overlay.style.display = 'flex';
  overlay.style.animation = 'overlayFadeIn 0.3s ease both';
}

/* Token SMS */
document.getElementById('token-sms-btn').addEventListener('click', () => {
  const phone = document.getElementById('token-sms-phone').value;
  if (phone.length >= 10) {
    document.getElementById('token-sms-btn').textContent = '✅ Sent!';
    document.getElementById('token-sms-btn').disabled = true;
    document.getElementById('token-sms-confirm').style.display = 'block';
    document.getElementById('token-sms-confirm').style.animation = 'questionFadeIn 0.3s ease both';
  }
});


/* ══════════════════════════════════════════════════════════════
   MATERNAL SCENARIO DRAWER
══════════════════════════════════════════════════════════════ */
function activateMaternalMode() {
  const drawer = document.getElementById('maternal-drawer');
  drawer.style.display = 'block';
  drawer.style.animation = 'none';
  void drawer.offsetWidth;
  drawer.style.animation = '';

  // Footer indicator
  const fi = document.getElementById('footer-scenario-indicator');
  fi.style.display = 'block';
  fi.innerHTML = '<span style="color:#B1E5E6;">🤱 Maternal Mode Active · ANC Schedule Loaded</span>';

  // Add to note
  addNoteEntry('🤱', 'Visit Type', 'Maternal patient — ANC checkup schedule loaded');
}

document.getElementById('maternal-drawer-close').addEventListener('click', () => {
  document.getElementById('maternal-drawer').style.display = 'none';
});

document.getElementById('maternal-sms-btn').addEventListener('click', () => {
  document.getElementById('maternal-sms-confirm').style.display = 'block';
  document.getElementById('maternal-sms-confirm').style.animation = 'questionFadeIn 0.3s ease both';
  document.getElementById('maternal-sms-btn').textContent = '✅ SMS Scheduled';
  document.getElementById('maternal-sms-btn').disabled = true;
  addNoteEntry('📲', 'ANC Reminder', 'SMS reminder scheduled for next ANC visit');
});

document.getElementById('maternal-voice-btn').addEventListener('click', function () {
  this.textContent = '✅ Voice Call Scheduled';
  this.disabled = true;
  addNoteEntry('📞', 'Voice Agent', 'Automated call scheduled via CRM Voice Agent');
});


/* ══════════════════════════════════════════════════════════════
   CHRONIC DISEASE DRAWER
══════════════════════════════════════════════════════════════ */
function activateChronicMode() {
  const drawer = document.getElementById('chronic-drawer');
  drawer.style.display = 'block';

  const fi = document.getElementById('footer-scenario-indicator');
  fi.style.display = 'block';
  fi.innerHTML = '<span style="color:#F7ADAD;">💊 Chronic Mode · Historical data loaded</span>';

  addNoteEntry('💊', 'Visit Type', 'Chronic follow-up — last visit data: Glucose 290 mg/dL, HbA1c 9.1%');
}

document.getElementById('chronic-drawer-close').addEventListener('click', () => {
  document.getElementById('chronic-drawer').style.display = 'none';
});

// Improvement question
document.querySelectorAll('.ciq-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.ciq-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    const val = btn.dataset.val;
    const selected = document.getElementById('ciq-selected');
    const msgs = {
      better: '😊 Patient reports improvement since last visit.',
      same:   '😐 Patient reports condition unchanged.',
      worse:  '😟 Patient reports condition has worsened since last visit.',
    };
    selected.style.display = 'block';
    selected.textContent = msgs[val];
    selected.style.animation = 'questionFadeIn 0.3s ease both';
    addNoteEntry('📊', 'Longitudinal Status', msgs[val]);
  });
});

// Medication adherence
document.querySelectorAll('.cma-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.cma-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    const val = btn.dataset.val;
    const msgs = { yes:'Medications taken regularly', sometimes:'Adherence — sometimes taken', no:'Not taking medications / ran out' };
    document.getElementById('ch-meds-today').textContent = msgs[val];
    addNoteEntry('💊', 'Medication Adherence', msgs[val]);
  });
});


/* ══════════════════════════════════════════════════════════════
   NURSE VITALS PANEL
══════════════════════════════════════════════════════════════ */
document.getElementById('kiosk-vitals-btn').addEventListener('click', () => {
  const overlay = document.getElementById('vitals-overlay');
  overlay.style.display = 'flex';
});

document.getElementById('vitals-panel-close').addEventListener('click', () => {
  document.getElementById('vitals-overlay').style.display = 'none';
});

document.getElementById('vitals-cancel-btn').addEventListener('click', () => {
  document.getElementById('vitals-overlay').style.display = 'none';
});

// Live urgency calculation (staff-only, never shown to patient)
['vit-temp','vit-bp','vit-spo2','vit-pulse'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', updateVitalsUrgency);
});

function updateVitalsUrgency() {
  const temp  = parseFloat(document.getElementById('vit-temp').value)  || 0;
  const spo2  = parseFloat(document.getElementById('vit-spo2').value)  || 100;
  const pulse = parseFloat(document.getElementById('vit-pulse').value) || 70;
  const bpRaw = document.getElementById('vit-bp').value;
  const sys   = bpRaw ? parseInt(bpRaw.split('/')[0]) : 120;

  let emoji = '🟢', label = 'Vitals within normal range', urgency = 'green';
  if (temp >= 104 || spo2 < 90 || sys >= 160 || pulse > 130) {
    emoji = '🔴'; label = 'Critical — immediate review needed'; urgency = 'red';
  } else if (temp >= 101 || spo2 < 95 || sys >= 140 || pulse > 100) {
    emoji = '🟡'; label = 'Semi-urgent — review within 30 min'; urgency = 'yellow';
  }

  appState.urgency = urgency;
  const prevEl = document.getElementById('vitals-urgency-preview');
  prevEl.querySelector('span').textContent = emoji;
  document.getElementById('vup-label').textContent = label;

  const colors = { green: '#E8FAFA', yellow: 'rgba(217,119,6,0.08)', red: 'rgba(220,38,38,0.06)' };
  const borders = { green: '#B1E5E6', yellow: 'rgba(217,119,6,0.3)', red: 'rgba(220,38,38,0.3)' };
  prevEl.style.background   = colors[urgency];
  prevEl.style.borderColor  = borders[urgency];
}

document.getElementById('vitals-save-btn').addEventListener('click', () => {
  appState.vitals = {
    temp:   document.getElementById('vit-temp').value,
    bp:     document.getElementById('vit-bp').value,
    spo2:   document.getElementById('vit-spo2').value,
    pulse:  document.getElementById('vit-pulse').value,
    weight: document.getElementById('vit-weight').value,
    height: document.getElementById('vit-height').value,
  };
  document.getElementById('vitals-overlay').style.display = 'none';
  document.getElementById('vitals-badge').textContent = '✅ Done';
  document.getElementById('vitals-badge').style.background = 'rgba(22,163,74,0.2)';
  document.getElementById('vitals-badge').style.color = '#86EFAC';

  // Add vitals to note (patient-safe: no triage tag)
  if (appState.vitals.temp)  addNoteEntry('🌡️', 'Temperature',    `${appState.vitals.temp}°F`);
  if (appState.vitals.bp)    addNoteEntry('🩸', 'Blood Pressure', `${appState.vitals.bp} mmHg`);
  if (appState.vitals.spo2)  addNoteEntry('💨', 'SpO₂',           `${appState.vitals.spo2}%`);
  if (appState.vitals.pulse) addNoteEntry('❤️', 'Pulse Rate',     `${appState.vitals.pulse} bpm`);

  enableConfirmButton();
});


/* ══════════════════════════════════════════════════════════════
   ADD NEW PROBLEM
══════════════════════════════════════════════════════════════ */
document.getElementById('add-problem-btn').addEventListener('click', () => {
  const newId = appState.problems.length;
  appState.problems.push({ id: newId, label: `Problem ${newId + 1}`, symptoms: '' });
  appState.activeProblem = newId;

  // Add chip to strip
  const strip = document.getElementById('problems-strip');
  const chip = document.createElement('div');
  chip.className = 'kiosk-problem-chip active';
  chip.id = `problem-chip-${newId}`;
  chip.setAttribute('role', 'listitem');
  chip.innerHTML = `<span class="problem-num">${newId + 1}</span><span class="problem-label" id="problem-label-${newId}">Problem ${newId + 1}</span>`;
  strip.appendChild(chip);

  // Mark all other chips inactive
  strip.querySelectorAll('.kiosk-problem-chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');

  // Add separator to note
  addNoteEntry('➕', `Problem ${newId + 1}`, 'New complaint added — describe below');

  // Scroll strip to show new chip
  strip.scrollLeft = strip.scrollWidth;

  // Reset voice area for new problem
  micIcon.textContent = '🎙️';
  micStatus.textContent = 'Tap to Speak';
  transcriptBox.textContent = '';
  transcriptBox.classList.remove('show');
});


/* ══════════════════════════════════════════════════════════════
   LANGUAGE MODAL
══════════════════════════════════════════════════════════════ */
const LANG_LABELS = {
  en:'English', hi:'हिन्दी', ta:'தமிழ்', te:'తెలుగు', bn:'বাংলা',
  kn:'ಕನ್ನಡ', ml:'മലയാളം', mr:'मराठी', gu:'ગુજરાતી', pa:'ਪੰਜਾਬੀ',
  or:'ଓଡ଼ିଆ', as:'অসমীয়া', mai:'मैथिली', ur:'اردو', ne:'नेपाली',
  ks:'کٲشُر', sa:'संस्कृतम्', kok:'कोंकणी', doi:'डोगरी', mni:'মণিপুরী',
  sat:'संथाली', sd:'سنڌي',
};

document.getElementById('kiosk-lang-btn').addEventListener('click', () => {
  document.getElementById('kiosk-lang-modal').classList.add('open');
});

document.getElementById('kiosk-lang-modal-close').addEventListener('click', () => {
  document.getElementById('kiosk-lang-modal').classList.remove('open');
});
document.getElementById('kiosk-lang-cancel').addEventListener('click', () => {
  document.getElementById('kiosk-lang-modal').classList.remove('open');
});

document.querySelectorAll('.lang-22-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.lang-22-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    appState.lang = btn.dataset.lang;
  });
});

document.getElementById('kiosk-lang-confirm').addEventListener('click', () => {
  document.getElementById('kiosk-lang-modal').classList.remove('open');
  updateLangDisplay();
});

function updateLangDisplay() {
  const label = LANG_LABELS[appState.lang] || appState.lang;
  document.getElementById('kiosk-lang-label').textContent = label;
  // Sync consent page pills
  document.querySelectorAll('.pi-lang-quick-btn').forEach(b => {
    b.classList.toggle('selected', b.dataset.lang === appState.lang);
  });
}


/* ══════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════ */
// Ensure modal shows immediately
document.getElementById('consent-modal').classList.add('active');

// Add facility name to token display
document.querySelector('.token-display-facility').textContent = 'PHC Manikpur · OPD Queue';
