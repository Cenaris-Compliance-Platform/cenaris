/* =========================================================
   Cenaris Guided Walkthrough Tour Engine
   walkthrough-tour.js
   ========================================================= */
(function () {
  'use strict';

  /* ── Config ─────────────────────────────────────────────── */
  const API_BASE = '/api/v1';
  const CSRF = document.querySelector('meta[name="csrf-token"]')?.content
    || window.__CENARIS_CSRF__
    || '';

  /* ── State ───────────────────────────────────────────────── */
  let tourState = null;   // server state object
  let tourSteps = [];     // step definitions from server
  let currentStep = 0;
  let pageKey = null;
  let nudgeShown = false;

  /* ── DOM refs (created lazily) ───────────────────────────── */
  let overlayEl = null;
  let tooltipEl = null;
  let ringWrapEl = null;
  let nudgeEl = null;
  let menuEl = null;
  let currentHighlighted = null;

  /* ── Helpers ─────────────────────────────────────────────── */
  function apiPost(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
      body: JSON.stringify(body || {}),
    }).then(function (r) { return r.json(); });
  }

  function apiGet(url) {
    return fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': CSRF },
    }).then(function (r) { return r.json(); });
  }

  function nudgeDismissed() {
    try { return localStorage.getItem('wt_nudge_' + pageKey) === '1'; } catch (e) { return false; }
  }

  function dismissNudge() {
    try { localStorage.setItem('wt_nudge_' + pageKey, '1'); } catch (e) {}
  }

  /* ── Ring ────────────────────────────────────────────────── */
  const RING_R = 14;
  const RING_CIRC = 2 * Math.PI * RING_R;

  function buildRing() {
    if (ringWrapEl) return;
    const wrap = document.createElement('div');
    wrap.className = 'wt-ring-wrap';
    wrap.id = 'wtRingWrap';
    wrap.setAttribute('title', 'Guided tour — click to open');
    wrap.setAttribute('role', 'button');
    wrap.setAttribute('aria-label', 'Guided tour progress');
    wrap.innerHTML = `
      <svg class="wt-ring-svg" viewBox="0 0 36 36" aria-hidden="true">
        <circle class="wt-ring-bg" cx="18" cy="18" r="${RING_R}"/>
        <circle class="wt-ring-progress" id="wtRingProgress"
          cx="18" cy="18" r="${RING_R}"
          stroke-dasharray="${RING_CIRC}"
          stroke-dashoffset="${RING_CIRC}"/>
      </svg>
      <div class="wt-ring-icon" id="wtRingIcon">
        <i class="bi bi-compass"></i>
      </div>`;
    wrap.addEventListener('click', onRingClick);
    document.body.appendChild(wrap);
    ringWrapEl = wrap;
  }

  function updateRing(state) {
    if (!ringWrapEl) buildRing();
    const progress = document.getElementById('wtRingProgress');
    const icon = document.getElementById('wtRingIcon');
    if (!progress || !icon) return;

    const total = Math.max(1, state.total_stages || tourSteps.length || 1);
    const done = state.stages_completed || 0;
    const pct = done / total;
    const offset = RING_CIRC * (1 - pct);

    progress.style.strokeDashoffset = offset;

    if (state.state === 'completed') {
      progress.classList.add('wt-ring-done-color');
      ringWrapEl.classList.add('wt-ring-completed');
      icon.innerHTML = '<i class="bi bi-check2" style="color:#198754"></i>';
    } else if (state.state === 'in_progress') {
      progress.classList.remove('wt-ring-done-color');
      ringWrapEl.classList.remove('wt-ring-completed');
      icon.textContent = done + '/' + total;
      icon.style.fontSize = '0.6rem';
    } else {
      progress.classList.remove('wt-ring-done-color');
      ringWrapEl.classList.remove('wt-ring-completed');
      icon.innerHTML = '<i class="bi bi-compass"></i>';
    }
  }

  /* ── Overlay ─────────────────────────────────────────────── */
  function showOverlay() {
    if (!overlayEl) {
      overlayEl = document.createElement('div');
      overlayEl.className = 'wt-overlay';
      overlayEl.id = 'wtOverlay';
      overlayEl.addEventListener('click', function (e) {
        if (e.target === overlayEl) hideTour();
      });
      document.body.appendChild(overlayEl);
    }
    overlayEl.classList.add('is-active');
  }

  function hideOverlay() {
    if (overlayEl) overlayEl.classList.remove('is-active');
  }

  /* ── Spotlight ───────────────────────────────────────────── */
  let shadowEl = null;

  function spotlight(el) {
    clearSpotlight();
    if (!el) return;
    el.classList.add('wt-spotlight');
    currentHighlighted = el;

    // Create standalone shadow to avoid clipping
    if (!shadowEl) {
      shadowEl = document.createElement('div');
      shadowEl.className = 'wt-spotlight-shadow';
      document.body.appendChild(shadowEl);
    }
    const rect = el.getBoundingClientRect();
    shadowEl.style.top = (rect.top + window.scrollY) + 'px';
    shadowEl.style.left = (rect.left + window.scrollX) + 'px';
    shadowEl.style.width = rect.width + 'px';
    shadowEl.style.height = rect.height + 'px';
    shadowEl.style.opacity = '1';
    const style = window.getComputedStyle(el);
    shadowEl.style.borderRadius = style.borderRadius || '6px';

    // Scroll into view gently
    try {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (e) {
      el.scrollIntoView(true);
    }
  }

  function clearSpotlight() {
    if (currentHighlighted) {
      currentHighlighted.classList.remove('wt-spotlight');
      currentHighlighted = null;
    }
    if (shadowEl) {
      shadowEl.style.opacity = '0';
      // Don't remove it, just hide so it can transition back in if needed
    }
  }

  function removeSpotlight() {
    clearSpotlight();
    if (shadowEl) {
      shadowEl.remove();
      shadowEl = null;
    }
  }

  /* ── Tooltip ─────────────────────────────────────────────── */
  function buildTooltip() {
    if (tooltipEl) return;
    const el = document.createElement('div');
    el.className = 'wt-tooltip is-initial';
    el.id = 'wtTooltip';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'true');
    el.setAttribute('aria-labelledby', 'wtTooltipTitle');
    el.innerHTML = `
      <div class="wt-arrow" id="wtArrow"></div>
      <div class="wt-tooltip-header">
        <span class="wt-tooltip-step-label" id="wtStepLabel">Step 1 of 1</span>
        <button class="wt-tooltip-close" id="wtTooltipClose" aria-label="Close tour">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div class="wt-progress-dots" id="wtDots"></div>
      <div class="wt-tooltip-body">
        <div class="wt-tooltip-title" id="wtTooltipTitle"></div>
        <p class="wt-tooltip-desc" id="wtTooltipDesc"></p>
      </div>
      <div class="wt-tooltip-footer">
        <button class="wt-tooltip-skip" id="wtSkip">Skip tour</button>
        <div class="wt-tooltip-nav">
          <button class="wt-btn-back" id="wtBack">← Back</button>
          <button class="wt-btn-next" id="wtNext">Next →</button>
          <button class="wt-btn-done d-none" id="wtDone">✓ Done</button>
        </div>
      </div>`;

    // Wire close button (el is not yet in DOM, use el.querySelector not getElementById)
    el.querySelector('#wtTooltipClose').addEventListener('click', hideTour);
    el.querySelector('#wtSkip').addEventListener('click', onSkipTour);
    el.querySelector('#wtBack').addEventListener('click', onBack);
    el.querySelector('#wtNext').addEventListener('click', onNext);
    el.querySelector('#wtDone').addEventListener('click', onDone);

    document.body.appendChild(el);
    tooltipEl = el;
  }

  function renderTooltip(stepIdx) {
    if (!tooltipEl) buildTooltip();
    const step = tourSteps[stepIdx];
    const total = tourSteps.length;
    const isLast = stepIdx === total - 1;

    const body = tooltipEl.querySelector('.wt-tooltip-body');
    body.style.transition = 'none';
    body.style.opacity = '0';
    body.style.transform = 'translateY(5px)';
    
    setTimeout(() => {
      tooltipEl.querySelector('#wtStepLabel').textContent =
        'Step ' + (stepIdx + 1) + ' of ' + total;
      tooltipEl.querySelector('#wtTooltipTitle').textContent = step.title || '';
      tooltipEl.querySelector('#wtTooltipDesc').textContent = step.description || '';
      
      body.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
      body.style.opacity = '1';
      body.style.transform = 'translateY(0)';
    }, 150);

    // Back button
    const backBtn = tooltipEl.querySelector('#wtBack');
    backBtn.style.display = stepIdx === 0 ? 'none' : '';

    // Next / Done
    const nextBtn = tooltipEl.querySelector('#wtNext');
    const doneBtn = tooltipEl.querySelector('#wtDone');
    nextBtn.classList.toggle('d-none', isLast);
    doneBtn.classList.toggle('d-none', !isLast);

    // Dots
    const dotsEl = tooltipEl.querySelector('#wtDots');
    const dots = [];
    for (let i = 0; i < total; i++) {
      let cls = 'wt-dot';
      if (i < stepIdx) cls += ' is-done';
      else if (i === stepIdx) cls += ' is-current';
      dots.push('<span class="' + cls + '"></span>');
    }
    dotsEl.innerHTML = dots.join('');

    // Position
    const targetId = step.target_element;
    const targetEl = targetId ? document.getElementById(targetId) : null;
    const placement = step.placement || 'bottom';
    positionTooltip(targetEl, placement);

    // After first position, allow transitions
    if (tooltipEl.classList.contains('is-initial')) {
      requestAnimationFrame(() => {
        tooltipEl.classList.remove('is-initial');
      });
    }
  }

  function positionTooltip(targetEl, placement) {
    if (!tooltipEl) return;
    // Reset positioning and transform without clearing CSS transitions
    tooltipEl.style.top = '';
    tooltipEl.style.left = '';
    tooltipEl.style.bottom = '';
    tooltipEl.style.right = '';
    tooltipEl.style.transform = '';

    const arrow = tooltipEl.querySelector('#wtArrow');
    if (arrow) arrow.className = 'wt-arrow';

    const GAP = 16;
    const TW = 300;
    const TH = tooltipEl.offsetHeight || 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    if (!targetEl) {
      // Centered fallback
      tooltipEl.style.top = '50%';
      tooltipEl.style.left = '50%';
      tooltipEl.style.transform = 'translate(-50%, -50%)';
      return;
    }

    const r = targetEl.getBoundingClientRect();
    let top, left;
    let resolvedPlacement = placement;

    // Auto-flip if near edge
    if (placement === 'bottom' && r.bottom + TH + GAP > vh) resolvedPlacement = 'top';
    if (placement === 'top' && r.top - TH - GAP < 0) resolvedPlacement = 'bottom';
    if (placement === 'right' && r.right + TW + GAP > vw) resolvedPlacement = 'left';
    if (placement === 'left' && r.left - TW - GAP < 0) resolvedPlacement = 'right';

    if (resolvedPlacement === 'bottom') {
      top = r.bottom + GAP;
      left = Math.min(Math.max(r.left + r.width / 2 - TW / 2, 8), vw - TW - 8);
      if (arrow) arrow.classList.add('arrow-top');
    } else if (resolvedPlacement === 'top') {
      top = r.top - GAP - TH;
      left = Math.min(Math.max(r.left + r.width / 2 - TW / 2, 8), vw - TW - 8);
      if (arrow) arrow.classList.add('arrow-bottom');
    } else if (resolvedPlacement === 'right') {
      top = Math.min(Math.max(r.top + r.height / 2 - TH / 2, 8), vh - TH - 8);
      left = r.right + GAP;
      if (arrow) arrow.classList.add('arrow-left');
    } else {
      top = Math.min(Math.max(r.top + r.height / 2 - TH / 2, 8), vh - TH - 8);
      left = r.left - GAP - TW;
      if (arrow) arrow.classList.add('arrow-right');
    }

    // Ensure tooltip is strictly bounded within the viewport
    // Even if an element is massive (like a long table), the card will stay on screen.
    const finalTop = Math.min(Math.max(8, top), vh - TH - 8);
    const finalLeft = Math.min(Math.max(8, left), vw - TW - 8);

    tooltipEl.style.top = finalTop + 'px';
    tooltipEl.style.left = finalLeft + 'px';
    tooltipEl.style.transform = 'none';
  }

  /* ── Tour lifecycle ──────────────────────────────────────── */
  function startTour(fromStep) {
    currentStep = fromStep || 0;
    closeNudge();
    closeMenu();
    // Tell backend we've started (only if not already in_progress)
    if (tourState && tourState.state === 'not_started') {
      apiPost(API_BASE + '/walkthroughs/state/' + encodeURIComponent(pageKey) + '/start', {})
        .then(function (d) {
          if (d && d.state) {
            tourState.state = 'in_progress';
            tourState.stages_completed = 0;
            updateRing(tourState);
          }
        })
        .catch(function () { /* non-critical */ });
    }
    showOverlay();
    buildTooltip();
    goToStep(currentStep);
  }

  function goToStep(idx) {
    currentStep = idx;
    const step = tourSteps[idx];
    if (!step) return;
    const targetEl = step.target_element
      ? document.getElementById(step.target_element)
      : null;

    // Automatically expand any collapsed parent containers (or the element itself)
    let didExpand = false;
    if (targetEl) {
      let node = targetEl;
      while (node) {
        if (node.classList && node.classList.contains('collapse') && !node.classList.contains('show')) {
          node.classList.add('show');
          didExpand = true;
          if (node.id) {
            const btn = document.querySelector('[aria-controls="' + node.id + '"]');
            if (btn) btn.setAttribute('aria-expanded', 'true');
          }
        }
        node = node.parentElement;
      }
    }

    if (didExpand) {
      // Wait for Bootstrap collapse animation to finish
      setTimeout(function() {
        spotlight(targetEl);
        setTimeout(function () { renderTooltip(idx); }, 180);
      }, 350);
    } else {
      spotlight(targetEl);
      setTimeout(function () { renderTooltip(idx); }, 180);
    }
  }

  async function onNext() {
    if (!tourState) return;
    try {
      await apiPost(API_BASE + '/walkthroughs/state/' + tourState.id + '/next-stage', {});
      tourState.stages_completed = (tourState.stages_completed || 0) + 1;
      tourState.current_stage = (tourState.current_stage || 0) + 1;
      updateRing(tourState);
    } catch (e) { /* non-critical */ }
    goToStep(currentStep + 1);
  }

  function onBack() {
    if (currentStep > 0) goToStep(currentStep - 1);
  }

  async function onDone() {
    if (!tourState) return hideTour();
    try {
      await apiPost(API_BASE + '/walkthroughs/state/' + tourState.id + '/complete', {});
      tourState.state = 'completed';
      tourState.stages_completed = tourSteps.length;
      tourState.completion_percentage = 100;
      updateRing(tourState);
    } catch (e) { /* non-critical */ }
    hideTour();
  }

  async function onSkipTour() {
    if (!tourState) return hideTour();
    try {
      await apiPost(API_BASE + '/walkthroughs/state/' + tourState.id + '/dismiss', { hours: 24 });
    } catch (e) { /* non-critical */ }
    hideTour();
  }

  function hideTour() {
    clearSpotlight();
    removeSpotlight();
    hideOverlay();
    if (tooltipEl) {
      tooltipEl.remove();
      tooltipEl = null;
    }
    closeNudge();
  }

  /* ── Ring click menu ─────────────────────────────────────── */
  function onRingClick(e) {
    e.stopPropagation();
    if (menuEl) { closeMenu(); return; }
    if (!tourState) return;

    menuEl = document.createElement('div');
    menuEl.className = 'wt-ring-menu';
    menuEl.id = 'wtRingMenu';

    const items = [];
    if (tourState.state === 'in_progress') {
      items.push({ icon: 'bi-play-circle', label: 'Continue tour', action: function () { startTour(tourState.current_stage || 0); } });
    } else if (tourState.state === 'not_started') {
      items.push({ icon: 'bi-play-circle', label: 'Start tour', action: function () { startTour(0); } });
    } else if (tourState.state === 'completed') {
      items.push({ icon: 'bi-arrow-counterclockwise', label: 'Redo tour', action: onRedoFromMenu });
    }
    items.push({ icon: 'bi-arrow-counterclockwise', label: 'Restart from step 1', action: onRedoFromMenu });
    items.push({ icon: 'bi-gear', label: 'Manage in Settings', action: function () { window.location.href = '/profile'; } });

    menuEl.innerHTML = items.map(function (item) {
      return '<button class="wt-ring-menu-item"><i class="bi ' + item.icon + '"></i>' + item.label + '</button>';
    }).join('');

    menuEl.querySelectorAll('button').forEach(function (btn, idx) {
      btn.addEventListener('click', function () { closeMenu(); items[idx].action(); });
    });

    document.body.appendChild(menuEl);
    setTimeout(function () {
      document.addEventListener('click', closeMenuOnOutside, { once: true });
    }, 0);
  }

  async function onRedoFromMenu() {
    if (!tourState) return;
    try {
      await apiPost(API_BASE + '/walkthroughs/state/' + tourState.id + '/reset', {});
      tourState.state = 'in_progress';
      tourState.current_stage = 0;
      tourState.stages_completed = 0;
      tourState.completion_percentage = 0;
      updateRing(tourState);
    } catch (e) { /* non-critical */ }
    startTour(0);
  }

  function closeMenu() {
    if (menuEl) { menuEl.remove(); menuEl = null; }
  }

  function closeMenuOnOutside() {
    closeMenu();
  }

  /* ── Nudge ───────────────────────────────────────────────── */
  function showNudge() {
    if (nudgeShown || nudgeDismissed()) return;
    nudgeShown = true;

    const isResume = tourState && tourState.state === 'in_progress';
    nudgeEl = document.createElement('div');
    nudgeEl.className = 'wt-nudge';
    nudgeEl.id = 'wtNudge';
    nudgeEl.innerHTML =
      '<div class="wt-nudge-title">' + (isResume ? '▶ Continue your tour' : '👋 New to this page?') + '</div>' +
      '<p class="wt-nudge-text">' + (isResume
        ? 'You left off at step ' + ((tourState.current_stage || 0) + 1) + '. Continue from where you stopped.'
        : 'Take a quick guided tour to learn the key features on this page.') + '</p>' +
      '<div class="wt-nudge-actions">' +
        '<button class="wt-nudge-start" id="wtNudgeStart">' + (isResume ? 'Continue' : 'Take the tour') + '</button>' +
        '<button class="wt-nudge-dismiss" id="wtNudgeDismiss">Not now</button>' +
      '</div>';

    nudgeEl.querySelector('#wtNudgeStart').addEventListener('click', function () {
      closeNudge();
      startTour(isResume ? (tourState.current_stage || 0) : 0);
    });
    nudgeEl.querySelector('#wtNudgeDismiss').addEventListener('click', function () {
      dismissNudge();
      closeNudge();
    });

    document.body.appendChild(nudgeEl);
  }

  function closeNudge() {
    if (nudgeEl) { nudgeEl.remove(); nudgeEl = null; }
  }

  /* ── Keyboard ────────────────────────────────────────────── */
  document.addEventListener('keydown', function (e) {
    if (!tooltipEl) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') onNext();
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') onBack();
    else if (e.key === 'Escape') hideTour();
  });

  /* ── Initialise ──────────────────────────────────────────── */
  async function init() {
    pageKey = window.WALKTHROUGH_PAGE_KEY;
    if (!pageKey) return;   // page has no tour

    buildRing();

    try {
      const data = await apiGet(API_BASE + '/walkthroughs/state/' + encodeURIComponent(pageKey));
      if (!data || !data.success) return;
      tourState = data.state;
      tourSteps = Array.isArray(tourState.stages) ? tourState.stages : [];

      updateRing(tourState);

      const s = tourState.state;
      if (s === 'not_started' && !nudgeDismissed()) {
        setTimeout(showNudge, 1500);
      } else if (s === 'in_progress' && !nudgeDismissed()) {
        setTimeout(showNudge, 800);
      }
      // completed → just show green ring, no nudge
    } catch (e) {
      // silently fail — tour is a nice-to-have
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose globally so inline onclick can also trigger tour
  window.CenarisWalkthrough = {
    start: function (step) { startTour(step || 0); },
    hide: hideTour,
  };
})();
