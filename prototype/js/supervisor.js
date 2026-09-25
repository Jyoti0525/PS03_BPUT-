/* ============================================================
   JEEVIA — Supervisor Dashboard JS (v2)
   ============================================================ */

'use strict';

/* ══════════════════════════════════════════════════════════════
   TAB NAVIGATION
══════════════════════════════════════════════════════════════ */
const tabs       = document.querySelectorAll('.sv-tab');
const sliderTabs = document.querySelectorAll('.sv-slider-tab');
const views      = document.querySelectorAll('.sv-view');

function activateSupervisorTab(targetId) {
  // Sync views
  views.forEach(v => v.classList.toggle('active', v.id === targetId));

  // Sync desktop tabs
  tabs.forEach(t => {
    const isTarget = t.id === targetId.replace('view-', 'tab-');
    t.classList.toggle('active', isTarget);
    t.setAttribute('aria-selected', isTarget ? 'true' : 'false');
  });

  // Sync mobile slider tabs
  sliderTabs.forEach(st => {
    const isTarget = st.getAttribute('data-target') === targetId;
    st.classList.toggle('active', isTarget);
  });

  // Auto-center in mobile slider
  if (window.JeeviaNav) {
    window.JeeviaNav.centerActive('.sv-mobile-nav .jeevia-slider-track');
  }
}

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.id.replace('tab-', 'view-');
    activateSupervisorTab(target);
  });
});

sliderTabs.forEach(st => {
  st.addEventListener('click', () => {
    const target = st.getAttribute('data-target');
    if (target) activateSupervisorTab(target);
  });
});

const mobileExportBtn = document.getElementById('sv-mobile-export-btn');
if (mobileExportBtn) {
  mobileExportBtn.addEventListener('click', () => {
    const desktopExport = document.getElementById('sv-export-btn');
    if (desktopExport) desktopExport.click();
  });
}


/* ══════════════════════════════════════════════════════════════
   HEADER DATE
══════════════════════════════════════════════════════════════ */
(function setDate() {
  const el = document.getElementById('sv-header-date');
  if (el) {
    el.textContent = new Date().toLocaleDateString('en-IN', {
      weekday:'long', year:'numeric', month:'long', day:'numeric'
    });
  }
})();


/* ══════════════════════════════════════════════════════════════
   SPECIALIST TOGGLES — update indicator dot & note text
══════════════════════════════════════════════════════════════ */
const SPEC_NOTES = {
  gp:    { on:'On duty today',             off:'Not on duty — GP cases may be rerouted',  visiting:null },
  obgyn: { on:'On-site today',             off:'Not on site — maternal cases referred',   visiting:'Visiting basis only' },
  cardio:{ on:'Cardiologist on site',      off:'Not on site — cardiac cases referred',    visiting:'By appointment' },
  pulmo: { on:'Pulmonologist on site',     off:'Not on site — respiratory cases referred',visiting:'Visiting Wed & Fri' },
  diab:  { on:'Diabetologist on site',     off:'Not on site — DM cases managed by GP',    visiting:'Visiting Wed & Fri' },
  anm:   { on:'ANM staff on duty',         off:'No ANM on duty',                          visiting:null },
  asha:  { on:'ASHA workers active',       off:'No ASHA workers today',                   visiting:null },
};

document.querySelectorAll('.sv-toggle input[data-spec]').forEach(toggle => {
  toggle.addEventListener('change', function () {
    const spec = this.dataset.spec;
    const dot  = document.getElementById(`spec-${spec}-dot`);
    const note = document.getElementById(`spec-${spec}-note`);
    if (dot)  { dot.className  = 'spec-indicator ' + (this.checked ? 'on' : 'off'); }
    if (note && SPEC_NOTES[spec]) {
      note.textContent = this.checked ? SPEC_NOTES[spec].on : SPEC_NOTES[spec].off;
    }
    toast(`${specName(spec)} marked as ${this.checked ? 'available' : 'unavailable'}. Referral logic updated.`);
  });
});

function specName(key) {
  const names = { gp:'General Physician', obgyn:'OB/GYN', cardio:'Cardiologist', pulmo:'Pulmonologist', diab:'Diabetologist', anm:'ANM/Nursing', asha:'ASHA Workers' };
  return names[key] || key;
}


/* ══════════════════════════════════════════════════════════════
   LANGUAGE TAGS
══════════════════════════════════════════════════════════════ */
document.querySelectorAll('.lang-tag').forEach(tag => {
  tag.addEventListener('click', () => {
    tag.classList.toggle('selected');
    const lang = tag.dataset.lang;
    const active = tag.classList.contains('selected');
    toast(`${tag.textContent} ${active ? 'added to' : 'removed from'} facility language list.`);
  });
});


/* ══════════════════════════════════════════════════════════════
   FESTIVAL TAGS
══════════════════════════════════════════════════════════════ */
document.querySelectorAll('.festival-tag').forEach(tag => {
  tag.addEventListener('click', () => tag.classList.toggle('selected'));
});


/* ══════════════════════════════════════════════════════════════
   FACILITY TYPE — update hint text
══════════════════════════════════════════════════════════════ */
const FACILITY_HINTS = {
  'phc'          : 'PHC — limited specialist availability. Referral routing to district hospital is active.',
  'govt-hospital': 'Government Hospital — full specialist suite expected. Referral logic set to within-facility escalation.',
  'camp'         : 'Public Health Camp — offline mode recommended. Limited diagnostics, community-level triage only.',
  'company'      : 'Company Clinic — occupational health focus. Workers\' compensation referral paths enabled.',
  'industrial'   : 'Industrial Health Unit — BOCW Act protocols. Trauma and occupational disease pathways active.',
  'campus'       : 'Campus Health Centre — student population. Mental health and IMCI pathways prioritized.',
};

const facilitySelect = document.getElementById('facility-type-select');
const facilityHint   = document.getElementById('facility-type-hint');
if (facilitySelect && facilityHint) {
  facilitySelect.addEventListener('change', function () {
    facilityHint.textContent = FACILITY_HINTS[this.value] || '';
  });
}


/* ══════════════════════════════════════════════════════════════
   CAPACITY PROGRESS BAR
══════════════════════════════════════════════════════════════ */
const capacityInput = document.getElementById('daily-capacity');
const capacityFill  = document.getElementById('capacity-fill');
const today = 47; // Demo value

if (capacityInput && capacityFill) {
  capacityInput.addEventListener('input', function () {
    const cap = parseInt(this.value) || 1;
    const pct = Math.min(100, (today / cap) * 100).toFixed(1);
    capacityFill.style.width = `${pct}%`;
    const label = capacityFill.closest('.config-block')?.querySelector('.config-progress-label');
    if (label) label.textContent = `${today} of ${cap} today (${pct}%)`;
  });
}


/* ══════════════════════════════════════════════════════════════
   SAVE FACILITY CONFIGURATION
══════════════════════════════════════════════════════════════ */
const saveBtn     = document.getElementById('save-facility-btn');
const saveConfirm = document.getElementById('sv-save-confirm');

if (saveBtn) {
  saveBtn.addEventListener('click', () => {
    saveBtn.textContent = 'Pushing configuration…';
    saveBtn.disabled = true;
    setTimeout(() => {
      saveBtn.textContent = 'Save & Push Configuration to All Kiosks';
      saveBtn.disabled = false;
      if (saveConfirm) {
        saveConfirm.style.display = 'block';
        saveConfirm.style.animation = 'none';
        void saveConfirm.offsetWidth;
        saveConfirm.style.animation = 'svFadeIn 0.3s ease both';
        setTimeout(() => { saveConfirm.style.display = 'none'; }, 5000);
      }
      toast('Configuration saved and pushed to all 3 connected kiosks.', 'success');
    }, 1200);
  });
}


/* ══════════════════════════════════════════════════════════════
   ALERT DISMISS
══════════════════════════════════════════════════════════════ */
document.querySelectorAll('.sv-alert-dismiss').forEach(btn => {
  btn.addEventListener('click', () => {
    const alert = btn.closest('.sv-alert');
    if (alert) {
      alert.style.opacity = '0';
      alert.style.transform = 'translateX(8px)';
      alert.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
      setTimeout(() => alert.remove(), 300);
      const count = parseInt(document.getElementById('sv-alert-count')?.textContent || '0');
      if (count > 0 && document.getElementById('sv-alert-count')) {
        document.getElementById('sv-alert-count').textContent = count - 1;
      }
    }
  });
});


/* ══════════════════════════════════════════════════════════════
   AUDIT LOG FILTERS
══════════════════════════════════════════════════════════════ */
const auditFilterType  = document.getElementById('audit-filter-type');
const auditFilterActor = document.getElementById('audit-filter-actor');

[auditFilterType, auditFilterActor].forEach(el => {
  if (el) el.addEventListener('change', filterAuditTable);
});

function filterAuditTable() {
  // Demo filter — shows/hides rows based on badge class
  const type  = (auditFilterType?.value  || 'all').toLowerCase();
  const actor = (auditFilterActor?.value || 'all').toLowerCase();
  document.querySelectorAll('#audit-tbody .audit-tr').forEach(row => {
    const badge = row.querySelector('.audit-badge');
    const roleEl = row.querySelector('.audit-role');
    const typeMatch  = type === 'all' || (badge && badge.classList.contains(type));
    const actorText  = (roleEl?.textContent || '').toLowerCase();
    const actorMatch = actor === 'all'
      || (actor === 'human' && actorText !== 'ai engine' && actorText !== 'system')
      || (actor === 'ai'    && (actorText === 'ai engine' || actorText === 'system'));
    row.style.display = (typeMatch && actorMatch) ? '' : 'none';
  });
}

document.getElementById('audit-csv-btn')?.addEventListener('click', () => {
  toast('Audit log export initiated. CSV download will begin shortly.', 'success');
});

document.getElementById('audit-load-more')?.addEventListener('click', () => {
  toast('Loading older audit records…');
});


/* ══════════════════════════════════════════════════════════════
   STAFF MANAGEMENT
══════════════════════════════════════════════════════════════ */
const enrollModal = document.getElementById('enroll-modal');
const enrollBtn   = document.getElementById('enroll-staff-btn');
const enrollClose = document.getElementById('enroll-modal-close');
const enrollCancel= document.getElementById('enroll-cancel-btn');

if (enrollBtn)   enrollBtn.addEventListener('click', () => { enrollModal.style.display = 'flex'; });
if (enrollClose) enrollClose.addEventListener('click', closeEnrollModal);
if (enrollCancel)enrollCancel.addEventListener('click', closeEnrollModal);

function closeEnrollModal() {
  if (enrollModal) enrollModal.style.display = 'none';
}

document.getElementById('enroll-send-otp-btn')?.addEventListener('click', () => {
  const phone = document.getElementById('enroll-phone')?.value;
  const role  = document.getElementById('enroll-role')?.value;
  if (!phone || !role) {
    toast('Please fill in phone number and role before sending OTP.', 'error');
    return;
  }
  const otpSection = document.getElementById('enroll-otp-section');
  if (otpSection) otpSection.style.display = 'block';
  document.getElementById('enroll-send-otp-btn').textContent = 'Verify OTP & Enroll';
  document.getElementById('enroll-send-otp-btn').addEventListener('click', completeEnroll, { once: true });
  toast('OTP sent to ' + phone);
});

function completeEnroll() {
  const otp = document.getElementById('enroll-otp')?.value;
  if (!otp || otp.length < 4) { toast('Please enter the OTP.', 'error'); return; }
  const confirm = document.getElementById('enroll-confirm');
  if (confirm) { confirm.style.display = 'block'; }
  document.getElementById('enroll-send-otp-btn').disabled = true;
  toast('Staff member enrolled successfully.', 'success');
  setTimeout(closeEnrollModal, 3000);
}

document.getElementById('resend-otp-btn')?.addEventListener('click', () => {
  toast('OTP resent to registered mobile number.');
});

// Staff search
document.getElementById('staff-search')?.addEventListener('input', function () {
  const q = this.value.toLowerCase();
  document.querySelectorAll('#staff-tbody .staff-tr').forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
});

// Staff role filter
document.getElementById('staff-filter-role')?.addEventListener('change', function () {
  const role = this.value;
  document.querySelectorAll('#staff-tbody .staff-tr').forEach(row => {
    if (role === 'all') { row.style.display = ''; return; }
    const roleTag = row.querySelector('.role-tag');
    row.style.display = (roleTag?.classList.contains(role)) ? '' : 'none';
  });
});

// Staff action buttons
document.querySelectorAll('.sv-action-btn.tiny:not(.danger)').forEach(btn => {
  if (btn.textContent.trim() === 'Edit') {
    btn.addEventListener('click', () => {
      const nameEl = btn.closest('.staff-tr')?.querySelector('.sn-name');
      toast(`Editing ${nameEl?.textContent || 'staff member'}…`);
    });
  }
  if (btn.textContent.trim() === 'Manage') {
    btn.addEventListener('click', () => {
      const kiosk = btn.closest('.kiosk-row')?.querySelector('.kiosk-name');
      toast(`Managing: ${kiosk?.textContent || 'device'}`);
    });
  }
});
document.querySelectorAll('.sv-action-btn.tiny.danger').forEach(btn => {
  btn.addEventListener('click', () => {
    const nameEl = btn.closest('.staff-tr')?.querySelector('.sn-name');
    if (nameEl && confirm(`Revoke access for ${nameEl.textContent}? This will immediately log them out.`)) {
      btn.closest('.staff-tr').style.opacity = '0.4';
      toast(`Access revoked for ${nameEl.textContent}.`, 'error');
    }
  });
});

document.getElementById('enroll-device-btn')?.addEventListener('click', () => {
  toast('Generating device enrollment OTP — send this to the device operator via SMS.');
});


/* ══════════════════════════════════════════════════════════════
   QUEUE MONITOR FILTERS
══════════════════════════════════════════════════════════════ */
document.querySelectorAll('.qf-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.qf-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    const filter = pill.dataset.filter;
    document.querySelectorAll('#queue-monitor-tbody .qm-row').forEach(row => {
      row.style.display = (filter === 'all' || row.dataset.urgency === filter) ? '' : 'none';
    });
  });
});

document.getElementById('queue-load-more')?.addEventListener('click', () => {
  toast('Loading remaining 11 patients from live queue…');
});

// Queue action buttons
document.querySelectorAll('.qm-actions .sv-action-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const patient = btn.closest('.qm-row')?.querySelector('.qm-patient')?.textContent;
    if (btn.classList.contains('danger')) {
      toast(`Escalating ${patient} to Medical Officer for immediate review.`, 'error');
    } else {
      toast(`Assigning ${patient} to next available doctor.`);
    }
  });
});


/* ══════════════════════════════════════════════════════════════
   LANGUAGE MODAL
══════════════════════════════════════════════════════════════ */
const LANG_LABELS = {
  en:'English', hi:'Hindi', ta:'Tamil', te:'Telugu', bn:'Bengali',
  kn:'Kannada', ml:'Malayalam', mr:'Marathi', gu:'Gujarati', pa:'Punjabi',
  ur:'Urdu', or:'Odia',
};
let selectedLang = 'en';

document.getElementById('sv-lang-btn')?.addEventListener('click', () => {
  document.getElementById('sv-lang-modal').style.display = 'flex';
});
document.getElementById('sv-lang-modal-close')?.addEventListener('click', () => {
  document.getElementById('sv-lang-modal').style.display = 'none';
});
document.getElementById('sv-lang-cancel')?.addEventListener('click', () => {
  document.getElementById('sv-lang-modal').style.display = 'none';
});
document.querySelectorAll('.sv-lang-opt').forEach(opt => {
  opt.addEventListener('click', () => {
    document.querySelectorAll('.sv-lang-opt').forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
    selectedLang = opt.dataset.lang;
  });
});
document.getElementById('sv-lang-confirm')?.addEventListener('click', () => {
  document.getElementById('sv-lang-modal').style.display = 'none';
  document.getElementById('sv-lang-current').textContent = LANG_LABELS[selectedLang] || selectedLang;
  toast(`Interface language changed to ${LANG_LABELS[selectedLang] || selectedLang}.`, 'success');
});


/* ══════════════════════════════════════════════════════════════
   QUICK ACTION BUTTONS
══════════════════════════════════════════════════════════════ */
document.getElementById('sv-export-btn')?.addEventListener('click', () => {
  toast('Generating full day report — download will begin shortly.', 'success');
});
document.getElementById('run-manual-purge')?.addEventListener('click', () => {
  if (confirm('Run manual data purge? This will immediately delete all raw audio and image files that have already been extracted.')) {
    toast('Manual purge initiated. 8 files scheduled for deletion.', 'success');
  }
});
document.getElementById('view-privacy-policy')?.addEventListener('click', () => {
  toast('Privacy Policy document will open in a new tab.');
});
document.getElementById('download-dpia')?.addEventListener('click', () => {
  toast('DPIA report generation initiated — download will begin shortly.', 'success');
});


/* ══════════════════════════════════════════════════════════════
   TOAST UTILITY
══════════════════════════════════════════════════════════════ */
function toast(message, type = '') {
  const container = document.getElementById('sv-toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'sv-toast' + (type ? ' ' + type : '');
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';
    el.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

/* ══════════════════════════════════════════════════════════════
   CLOSE MODAL ON OVERLAY CLICK
══════════════════════════════════════════════════════════════ */
[enrollModal, document.getElementById('sv-lang-modal')].forEach(overlay => {
  if (!overlay) return;
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.style.display = 'none';
  });
});
