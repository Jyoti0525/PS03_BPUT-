/* ============================================================
   JEEVIA — Landing Page JavaScript
   Handles: navbar scroll, mobile menu, scroll reveal,
            language modal, smooth scroll
   ============================================================ */

'use strict';

/* ── Navbar scroll effect ───────────────────────────────────── */
(function initNavbar() {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;

  let lastScroll = 0;

  window.addEventListener('scroll', () => {
    const currentScroll = window.scrollY;
    if (currentScroll > 20) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
    lastScroll = currentScroll;
  }, { passive: true });
})();


/* ── Mobile hamburger menu ──────────────────────────────────── */
(function initMobileMenu() {
  const hamburger = document.getElementById('nav-hamburger');
  const mobileMenu = document.getElementById('nav-mobile-menu');
  if (!hamburger || !mobileMenu) return;

  let isOpen = false;

  function toggleMenu() {
    isOpen = !isOpen;
    hamburger.classList.toggle('active', isOpen);
    mobileMenu.classList.toggle('open', isOpen);
    hamburger.setAttribute('aria-expanded', String(isOpen));
    mobileMenu.setAttribute('aria-hidden', String(!isOpen));
    document.body.style.overflow = isOpen ? 'hidden' : '';
  }

  hamburger.addEventListener('click', toggleMenu);

  // Close on link click
  mobileMenu.querySelectorAll('a, button:not(#mobile-lang-btn)').forEach(el => {
    el.addEventListener('click', () => {
      if (isOpen) toggleMenu();
    });
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (isOpen && !hamburger.contains(e.target) && !mobileMenu.contains(e.target)) {
      toggleMenu();
    }
  });

  // Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen) toggleMenu();
  });
})();


/* ── Scroll Reveal ──────────────────────────────────────────── */
(function initScrollReveal() {
  const elements = document.querySelectorAll('.reveal');
  if (!elements.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -60px 0px'
  });

  elements.forEach(el => observer.observe(el));
})();


/* ── Language Modal ─────────────────────────────────────────── */
(function initLanguageModal() {
  const overlay       = document.getElementById('lang-modal-overlay');
  const openBtns      = [
    document.getElementById('nav-lang-btn'),
    document.getElementById('mobile-lang-btn')
  ].filter(Boolean);
  const confirmBtn    = document.getElementById('lang-confirm');
  const closeBtn      = document.getElementById('lang-close');
  const langOptions   = document.querySelectorAll('#lang-modal-overlay .lang-option');
  const navLangBtn    = document.getElementById('nav-lang-btn');

  if (!overlay) return;

  let selectedLang = 'en';
  const langLabels = {
    en: 'English', hi: 'हिंदी', ta: 'தமிழ்', te: 'తెలుగు',
    bn: 'বাংলা', kn: 'ಕನ್ನಡ', ml: 'മലയാളം', mr: 'मराठी', gu: 'ગુજરાતી'
  };

  function openModal() {
    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    overlay.querySelector('.lang-modal').focus?.();
  }

  function closeModal() {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  openBtns.forEach(btn => btn?.addEventListener('click', openModal));
  closeBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  langOptions.forEach(option => {
    option.addEventListener('click', () => {
      langOptions.forEach(o => {
        o.classList.remove('active');
        o.setAttribute('aria-pressed', 'false');
      });
      option.classList.add('active');
      option.setAttribute('aria-pressed', 'true');
      selectedLang = option.dataset.lang;
    });
  });

  confirmBtn?.addEventListener('click', () => {
    if (navLangBtn) {
      navLangBtn.textContent = langLabels[selectedLang] || langLabels.en;
    }
    closeModal();
    // In production: apply translation here
    console.log('[Jeevia] Language selected:', selectedLang);
  });
})();


/* ── Smooth scroll for anchor links ─────────────────────────── */
(function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const href = anchor.getAttribute('href');
      if (href === '#') return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const offset = 80; // navbar height
      const top = target.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    });
  });
})();


/* ── Scenarios scroll drag on desktop ───────────────────────── */
(function initDragScroll() {
  const slider = document.querySelector('.scenarios-scroll');
  if (!slider) return;

  let isDown = false;
  let startX;
  let scrollLeft;

  slider.addEventListener('mousedown', (e) => {
    isDown = true;
    slider.style.cursor = 'grabbing';
    startX = e.pageX - slider.offsetLeft;
    scrollLeft = slider.scrollLeft;
  });

  slider.addEventListener('mouseleave', () => {
    isDown = false;
    slider.style.cursor = 'grab';
  });

  slider.addEventListener('mouseup', () => {
    isDown = false;
    slider.style.cursor = 'grab';
  });

  slider.addEventListener('mousemove', (e) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - slider.offsetLeft;
    const walk = (x - startX) * 2;
    slider.scrollLeft = scrollLeft - walk;
  });

  slider.style.cursor = 'grab';
})();


/* ── Animate hero stats counter ─────────────────────────────── */
(function initCounters() {
  const counters = [
    { id: null, selector: '.hero-stat-value', data: ['22+', '4 min', '100%'] }
  ];

  // Simple stagger entrance — values are static text, just add a pulse
  const statEls = document.querySelectorAll('.hero-stat-value');
  statEls.forEach((el, i) => {
    setTimeout(() => {
      el.style.animation = 'pulse-soft 0.5s ease-in-out';
      setTimeout(() => { el.style.animation = ''; }, 500);
    }, 800 + i * 200);
  });
})();


/* ── Active nav link on scroll ──────────────────────────────── */
(function initActiveNav() {
  const sections = ['home', 'features', 'how-it-works', 'scenarios', 'disclaimer'];
  const navMap = {
    features: 'nav-features',
    'how-it-works': 'nav-how',
    scenarios: 'nav-scenarios',
    disclaimer: 'nav-disclaimer'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && navMap[entry.target.id]) {
        document.querySelectorAll('.nav-center .nav-link').forEach(l => l.style.color = '');
        const activeLink = document.getElementById(navMap[entry.target.id]);
        if (activeLink) activeLink.style.color = 'var(--dark)';
      }
    });
  }, { threshold: 0.4 });

  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });
})();


/* ── Handle #signup hash redirect from landing page ─────────── */
(function checkHash() {
  if (window.location.hash === '#signup') {
    // Redirect to auth with signup open
    window.location.href = 'auth.html#signup';
  }
})();
