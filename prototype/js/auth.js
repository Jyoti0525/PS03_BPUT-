/* ============================================================
   JEEVIA — Authentication Page JavaScript
   Handles: Tab switching, multi-step Sign Up flow,
            role selection, OTP timer, password toggle,
            form validation, language modal
   ============================================================ */

'use strict';

/* ── State ──────────────────────────────────────────────────── */
const state = {
  currentSignUpStep: 1,
  totalSteps: 5,
  selectedRole: null,
  termsAccepted: false,
  phone: '',
  name: '',
  otpTimerInterval: null
};

/* ── Utility Helpers ────────────────────────────────────────── */
function $(id) { return document.getElementById(id); }
function $$(selector) { return document.querySelectorAll(selector); }

function showElement(el) {
  if (typeof el === 'string') el = $(el);
  if (el) el.style.display = 'block';
}

function hideElement(el) {
  if (typeof el === 'string') el = $(el);
  if (el) el.style.display = 'none';
}

function showError(inputId, message) {
  const input = $(inputId);
  if (!input) return;
  input.style.borderColor = 'var(--critical)';
  input.style.boxShadow = '0 0 0 4px rgba(220,38,38,0.1)';

  let errorEl = input.parentElement.querySelector('.field-error');
  if (!errorEl) {
    errorEl = document.createElement('span');
    errorEl.className = 'field-error';
    errorEl.style.cssText = 'color: var(--critical); font-size: 12px; font-weight:500; display:block; margin-top:4px;';
    errorEl.setAttribute('role', 'alert');
    input.parentElement.appendChild(errorEl);
  }
  errorEl.textContent = message;
}

function clearError(inputId) {
  const input = $(inputId);
  if (!input) return;
  input.style.borderColor = '';
  input.style.boxShadow = '';
  const errorEl = input.parentElement.querySelector('.field-error');
  if (errorEl) errorEl.remove();
}

function showToast(message, type = 'success') {
  // Remove existing toasts
  document.querySelectorAll('.jeevia-toast').forEach(t => t.remove());

  const toast = document.createElement('div');
  toast.className = 'jeevia-toast';
  const colors = {
    success: { bg: 'var(--teal-light)', color: 'var(--teal-dark)', border: 'var(--teal)', icon: '' },
    error:   { bg: '#FEE2E2', color: '#991B1B', border: 'var(--critical)', icon: '' },
    info:    { bg: 'var(--coral-light)', color: 'var(--coral-dark)', border: 'var(--coral)', icon: '' }
  };
  const c = colors[type] || colors.info;

  toast.style.cssText = `
    position: fixed;
    top: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(-20px);
    background: ${c.bg};
    color: ${c.color};
    border: 1px solid ${c.border};
    padding: 12px 20px;
    border-radius: var(--r-full);
    font-size: 14px;
    font-weight: 600;
    z-index: 9999;
    box-shadow: var(--shadow-md);
    opacity: 0;
    transition: all 0.3s var(--ease);
    white-space: nowrap;
  `;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.textContent = `${c.icon} ${message}`;

  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(-50%) translateY(0)';
  });

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(-20px)';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ── Tab Switching ──────────────────────────────────────────── */
function initTabs() {
  const tabSignin = $('tab-signin');
  const tabSignup = $('tab-signup');
  const panelSignin = $('panel-signin');
  const panelSignup = $('panel-signup');

  function showSignIn() {
    tabSignin.classList.add('active');
    tabSignup.classList.remove('active');
    tabSignin.setAttribute('aria-selected', 'true');
    tabSignup.setAttribute('aria-selected', 'false');
    showElement(panelSignin);
    hideElement(panelSignup);
    // Clear URL hash
    history.replaceState(null, '', window.location.pathname);
  }

  function showSignUp() {
    tabSignup.classList.add('active');
    tabSignin.classList.remove('active');
    tabSignup.setAttribute('aria-selected', 'true');
    tabSignin.setAttribute('aria-selected', 'false');
    hideElement(panelSignin);
    showElement(panelSignup);
  }

  tabSignin?.addEventListener('click', showSignIn);
  tabSignup?.addEventListener('click', showSignUp);

  // Cross-link buttons
  $('goto-signup-btn')?.addEventListener('click', showSignUp);
  $('goto-signin-btn')?.addEventListener('click', showSignIn);

  // Handle hash on load
  if (window.location.hash === '#signup') {
    showSignUp();
  }
}


/* ── Step Navigation ────────────────────────────────────────── */
function goToStep(stepNumber) {
  const prev = $('step-' + state.currentSignUpStep);
  const next = $('step-' + stepNumber);

  if (prev) prev.classList.remove('active');
  if (next) {
    next.classList.add('active');
    next.style.animation = 'none';
    requestAnimationFrame(() => {
      next.style.animation = 'fadeInUp 0.4s var(--ease) both';
    });
  }

  state.currentSignUpStep = stepNumber;
  updateStepDots();

  // Update aria
  const progressbar = $('signup-step-indicator');
  if (progressbar) progressbar.setAttribute('aria-valuenow', stepNumber);

  // Hide bottom link on success step
  const bottomLink = $('signup-bottom-link');
  if (bottomLink) {
    bottomLink.style.display = stepNumber === 5 ? 'none' : '';
  }
}

function updateStepDots() {
  for (let i = 1; i <= state.totalSteps; i++) {
    const dot = $('dot-' + i);
    if (!dot) continue;
    dot.classList.remove('active', 'done');
    if (i === state.currentSignUpStep) {
      dot.classList.add('active');
    } else if (i < state.currentSignUpStep) {
      dot.classList.add('done');
    }
  }
}


/* ── Role Selection (Step 1) ────────────────────────────────── */
function initRoleSelection() {
  const roleCards = $$('.role-card');
  const nextBtn   = $('step1-next');

  roleCards.forEach(card => {
    card.addEventListener('click', () => {
      // Deselect all
      roleCards.forEach(c => {
        c.classList.remove('selected');
        c.setAttribute('aria-pressed', 'false');
      });

      // Select clicked
      card.classList.add('selected');
      card.setAttribute('aria-pressed', 'true');
      state.selectedRole = card.dataset.role;

      // Enable next button
      if (nextBtn) {
        nextBtn.disabled = false;
        nextBtn.removeAttribute('aria-disabled');
      }

      // Show/hide professional section in step 4
      const profSection = $('professional-section');
      if (profSection) {
        profSection.style.display = (state.selectedRole === 'doctor' || state.selectedRole === 'supervisor') ? 'block' : 'none';
      }

      // Update brand panel highlight (visual feedback)
      document.querySelectorAll('.auth-role-pill').forEach((pill, i) => {
        const roles = ['doctor', 'patient', 'supervisor'];
        pill.style.borderColor = roles[i] === state.selectedRole ? 'rgba(242, 145, 145, 0.6)' : '';
        pill.style.background  = roles[i] === state.selectedRole ? 'rgba(242, 145, 145, 0.1)' : '';
      });
    });

    // Keyboard support
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        card.click();
      }
    });
  });

  nextBtn?.addEventListener('click', () => {
    if (state.selectedRole) {
      goToStep(2);
    }
  });
}


/* ── Step 2 — Personal Info ─────────────────────────────────── */
function initStep2() {
  const nextBtn  = $('step2-next');
  const backBtn  = $('step2-back');
  const sendOtp  = $('send-otp-btn');
  const nameInput  = $('signup-name');
  const phoneInput = $('signup-phone');

  function validate() {
    let valid = true;

    const name = nameInput?.value.trim();
    if (!name || name.length < 2) {
      showError('signup-name', 'Please enter your full name');
      valid = false;
    } else {
      clearError('signup-name');
    }

    const phone = phoneInput?.value.trim();
    if (!phone || !/^\d{10}$/.test(phone)) {
      showError('signup-phone', 'Please enter a valid 10-digit mobile number');
      valid = false;
    } else {
      clearError('signup-phone');
    }

    return valid;
  }

  // Phone input: numbers only
  phoneInput?.addEventListener('input', () => {
    phoneInput.value = phoneInput.value.replace(/\D/g, '').slice(0, 10);
  });

  sendOtp?.addEventListener('click', () => {
    if (validate()) {
      showToast('OTP sent to +91 ' + $('signup-phone').value, 'info');
    }
  });

  nextBtn?.addEventListener('click', () => {
    if (validate()) {
      state.name  = nameInput.value.trim();
      state.phone = phoneInput.value.trim();

      // Update OTP display
      const otpDisplay = $('otp-phone-display');
      if (otpDisplay) {
        const masked = state.phone.slice(0, 5) + 'XXXXX';
        otpDisplay.innerHTML = `+91 <span style="color:var(--coral)">${masked}</span>`;
      }

      showToast('OTP sent to +91 ' + state.phone, 'info');
      goToStep(3);
      startOtpTimer();
    }
  });

  backBtn?.addEventListener('click', () => goToStep(1));
}


/* ── Step 3 — OTP ───────────────────────────────────────────── */
function initStep3() {
  const otpInputs = $$('.otp-input');
  const nextBtn   = $('step3-next');
  const backBtn   = $('step3-back');
  const resendBtn = $('otp-resend-btn');

  // Auto-advance on input
  otpInputs.forEach((input, idx) => {
    input.addEventListener('input', () => {
      // Single digit enforcement
      if (input.value.length > 1) input.value = input.value.slice(-1);

      if (input.value && idx < otpInputs.length - 1) {
        otpInputs[idx + 1].focus();
      }

      input.classList.toggle('filled', !!input.value);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && idx > 0) {
        otpInputs[idx - 1].focus();
        otpInputs[idx - 1].value = '';
        otpInputs[idx - 1].classList.remove('filled');
      }
    });

    // Prevent non-numeric
    input.addEventListener('keypress', (e) => {
      if (!/[0-9]/.test(e.key)) e.preventDefault();
    });

    // Select on focus
    input.addEventListener('focus', () => input.select());
  });

  nextBtn?.addEventListener('click', () => {
    const otp = Array.from(otpInputs).map(i => i.value).join('');
    if (otp.length !== 6) {
      showToast('Please enter all 6 digits of the OTP', 'error');
      return;
    }

    // Simulate OTP verification (prototype: accept any 6-digit OTP)
    showToast('OTP verified successfully!', 'success');
    goToStep(4);

    // Show professional section based on role
    const profSection = $('professional-section');
    if (profSection) {
      profSection.style.display = (state.selectedRole === 'doctor' || state.selectedRole === 'supervisor') ? 'block' : 'none';
    }
  });

  backBtn?.addEventListener('click', () => {
    stopOtpTimer();
    goToStep(2);
  });

  resendBtn?.addEventListener('click', () => {
    // Clear OTP inputs
    otpInputs.forEach(input => {
      input.value = '';
      input.classList.remove('filled');
    });
    otpInputs[0]?.focus();
    startOtpTimer();
    showToast('New OTP sent!', 'info');
  });
}

function startOtpTimer() {
  stopOtpTimer();

  let seconds = 60;
  const timerEl  = $('otp-timer');
  const resendBtn = $('otp-resend-btn');

  if (timerEl) timerEl.textContent = seconds + 's';
  if (resendBtn) resendBtn.classList.remove('show');

  // Show timer text
  const resendRow = document.querySelector('.otp-resend');
  if (resendRow) {
    const timerText = resendRow.querySelector('span:not(.otp-timer)');
    // Show "Resend OTP in X s"
  }

  state.otpTimerInterval = setInterval(() => {
    seconds--;
    if (timerEl) timerEl.textContent = seconds + 's';

    if (seconds <= 0) {
      stopOtpTimer();
      if (timerEl) timerEl.textContent = '';
      if (resendBtn) resendBtn.classList.add('show');

      // Update label
      const resendParent = document.querySelector('.otp-resend');
      if (resendParent) {
        const textNode = Array.from(resendParent.childNodes).find(n => n.nodeType === 3);
        if (textNode) textNode.textContent = "Didn't receive it? ";
      }
    }
  }, 1000);
}

function stopOtpTimer() {
  if (state.otpTimerInterval) {
    clearInterval(state.otpTimerInterval);
    state.otpTimerInterval = null;
  }
}


/* ── Step 4 — Account Setup ─────────────────────────────────── */
function initStep4() {
  const nextBtn       = $('step4-next');
  const backBtn       = $('step4-back');
  const pwdInput      = $('signup-password');
  const confirmInput  = $('signup-confirm-password');
  const termsCheck    = $('terms-check');
  const pwdToggle     = $('signup-pwd-toggle');
  const confirmToggle = $('signup-confirm-pwd-toggle');

  // Password toggles
  initPasswordToggle('signup-password', 'signup-pwd-toggle');
  initPasswordToggle('signup-confirm-password', 'signup-confirm-pwd-toggle');

  // Terms checkbox
  termsCheck?.addEventListener('click', () => {
    state.termsAccepted = !state.termsAccepted;
    termsCheck.classList.toggle('checked', state.termsAccepted);
    termsCheck.setAttribute('aria-checked', String(state.termsAccepted));
  });

  termsCheck?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      termsCheck.click();
    }
  });

  function validate() {
    let valid = true;

    const pwd = pwdInput?.value;
    if (!pwd || pwd.length < 8) {
      showError('signup-password', 'Password must be at least 8 characters');
      valid = false;
    } else {
      clearError('signup-password');
    }

    const confirm = confirmInput?.value;
    if (pwd !== confirm) {
      showError('signup-confirm-password', 'Passwords do not match');
      valid = false;
    } else if (confirm) {
      clearError('signup-confirm-password');
    }

    if (!state.termsAccepted) {
      showToast('Please accept the Terms of Service to continue', 'error');
      valid = false;
    }

    return valid;
  }

  nextBtn?.addEventListener('click', () => {
    if (validate()) {
      // Update success screen
      const successName = $('success-name');
      if (successName) {
        const prefix = state.selectedRole === 'doctor' ? 'Dr. ' : state.selectedRole === 'supervisor' ? '' : '';
        successName.textContent = prefix + (state.name || 'User');
      }

      goToStep(5);

      // Role-based redirect on signup success
      const roleMap = {
        doctor:     'doctor-dashboard.html',
        supervisor: 'supervisor-dashboard.html',
        patient:    'patient-intake.html'
      };
      const targetUrl = roleMap[state.selectedRole] || 'patient-intake.html';

      const btn = $('go-to-dashboard');
      if (btn) {
        btn.href = targetUrl;
        btn.style.animation = 'pulse-soft 1s ease-in-out infinite';
      }

      // Auto-redirect after 4 seconds
      setTimeout(() => {
        window.location.href = targetUrl;
      }, 4000);
    }
  });

  backBtn?.addEventListener('click', () => goToStep(3));
}


/* ── Password Visibility Toggle ─────────────────────────────── */
function initPasswordToggle(inputId, toggleId) {
  const input  = $(inputId);
  const toggle = $(toggleId);
  if (!input || !toggle) return;

  let visible = false;

  toggle.addEventListener('click', () => {
    visible = !visible;
    input.type = visible ? 'text' : 'password';
    toggle.innerHTML = visible ? '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>' : '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    toggle.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
  });
}


/* ── Sign In Form ───────────────────────────────────────────── */
function initSignIn() {
  const form       = $('signin-form');
  const submitBtn  = $('signin-submit-btn');
  const phoneInput = $('signin-phone');

  initPasswordToggle('signin-password', 'signin-pwd-toggle');

  // Phone: numbers only
  phoneInput?.addEventListener('input', () => {
    phoneInput.value = phoneInput.value.replace(/\D/g, '').slice(0, 10);
  });

  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    let valid = true;

    const phone = phoneInput?.value.trim();
    if (!phone || !/^\d{10}$/.test(phone)) {
      showError('signin-phone', 'Enter your 10-digit mobile number');
      valid = false;
    } else {
      clearError('signin-phone');
    }

    const pwd = $('signin-password')?.value;
    if (!pwd || pwd.length < 1) {
      showError('signin-password', 'Please enter your password');
      valid = false;
    } else {
      clearError('signin-password');
    }

    if (valid) {
      submitBtn.textContent = 'Signing in...';
      submitBtn.disabled = true;

      // Simulate login (prototype) — detect demo role from phone prefix
      setTimeout(() => {
        // Demo routing: any number starting with 9 = doctor, 8 = supervisor, others = patient
        const firstDigit = (phoneInput?.value || '').charAt(0);
        let dashboardUrl = 'patient-intake.html';
        let roleLabel = 'Patient';
        if (firstDigit === '9') { dashboardUrl = 'doctor-dashboard.html'; roleLabel = 'Doctor'; }
        else if (firstDigit === '8') { dashboardUrl = 'supervisor-dashboard.html'; roleLabel = 'Supervisor'; }

        showToast(`Signed in as ${roleLabel}! Redirecting to dashboard...`, 'success');
        setTimeout(() => {
          window.location.href = dashboardUrl;
        }, 1500);
      }, 1200);
    }
  });
}


/* ── Language Modal (Auth page) ─────────────────────────────── */
function initAuthLanguageModal() {
  const openBtn    = $('auth-lang-btn');
  const overlay    = $('auth-lang-modal');
  const confirmBtn = $('auth-lang-confirm');
  const closeBtn   = $('auth-lang-close');
  const options    = $$('#auth-lang-modal .lang-option');

  if (!overlay) return;

  let selectedLang = 'en';

  function open() {
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function close() {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  openBtn?.addEventListener('click', open);
  closeBtn?.addEventListener('click', close);
  confirmBtn?.addEventListener('click', () => {
    showToast('Language updated!', 'success');
    close();
  });

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
  });

  options.forEach(opt => {
    opt.addEventListener('click', () => {
      options.forEach(o => o.classList.remove('active'));
      opt.classList.add('active');
      selectedLang = opt.dataset.lang;
    });
  });
}


/* ── Init all ───────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initRoleSelection();
  initStep2();
  initStep3();
  initStep4();
  initSignIn();
  initAuthLanguageModal();

  // Auto-focus phone on sign-in panel
  const signinPhone = $('signin-phone');
  if (signinPhone && !window.location.hash) {
    setTimeout(() => signinPhone.focus(), 300);
  }

  console.log('[Jeevia Auth] Initialized — Educational Prototype');
});
