/**
 * Jeevia — Universal Responsive Navigation Manager
 * Handles auto-centering active slider items, smooth swipe behavior,
 * and view coordination across desktop and mobile.
 */

(function () {
  'use strict';

  function initSliderNavs() {
    const sliderTracks = document.querySelectorAll('.jeevia-slider-track');

    sliderTracks.forEach((track) => {
      // 1. Auto-center the active item on initial load
      const activeItem = track.querySelector('.jeevia-slider-item.active');
      if (activeItem) {
        centerItem(track, activeItem, false);
      }

      // 2. Click handler to auto-center clicked item
      track.addEventListener('click', (e) => {
        const item = e.target.closest('.jeevia-slider-item');
        if (!item) return;

        // If it links to in-page hash or view, update active class
        const isAnchor = item.getAttribute('href') && item.getAttribute('href').startsWith('#');
        const hasView = item.hasAttribute('data-view');

        if (isAnchor || hasView) {
          track.querySelectorAll('.jeevia-slider-item').forEach((el) => el.classList.remove('active'));
          item.classList.add('active');
        }

        centerItem(track, item, true);
      });

      // 3. Mouse Drag-to-Scroll Support for desktop simulation/touchpads
      let isDown = false;
      let startX = 0;
      let scrollLeft = 0;

      track.addEventListener('mousedown', (e) => {
        isDown = true;
        track.classList.add('is-dragging');
        startX = e.pageX - track.offsetLeft;
        scrollLeft = track.scrollLeft;
      });

      track.addEventListener('mouseleave', () => {
        isDown = false;
        track.classList.remove('is-dragging');
      });

      track.addEventListener('mouseup', () => {
        isDown = false;
        track.classList.remove('is-dragging');
      });

      track.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        e.preventDefault();
        const x = e.pageX - track.offsetLeft;
        const walk = (x - startX) * 1.5; // Drag sensitivity
        track.scrollLeft = scrollLeft - walk;
      });
    });
  }

  /**
   * Smoothly center an element within a scrollable horizontal container
   */
  function centerItem(track, item, smooth = true) {
    if (!track || !item) return;
    const trackWidth = track.clientWidth;
    const itemLeft = item.offsetLeft;
    const itemWidth = item.offsetWidth;

    const targetScroll = itemLeft - trackWidth / 2 + itemWidth / 2;

    track.scrollTo({
      left: Math.max(0, targetScroll),
      behavior: smooth ? 'smooth' : 'auto'
    });
  }

  // Expose helper globally so page-specific tab switchers can call it
  window.JeeviaNav = {
    init: initSliderNavs,
    centerActive: function (trackSelector) {
      const track = document.querySelector(trackSelector || '.jeevia-slider-track');
      if (!track) return;
      const active = track.querySelector('.jeevia-slider-item.active');
      if (active) centerItem(track, active, true);
    },
    setActiveView: function (viewId) {
      document.querySelectorAll('.jeevia-slider-item').forEach((item) => {
        if (item.getAttribute('data-view') === viewId) {
          item.classList.add('active');
          const track = item.closest('.jeevia-slider-track');
          if (track) centerItem(track, item, true);
        } else if (item.hasAttribute('data-view')) {
          item.classList.remove('active');
        }
      });
    }
  };

  // Run on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSliderNavs);
  } else {
    initSliderNavs();
  }
})();
