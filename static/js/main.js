// main.js — Scholarship Eligibility Predictor

document.addEventListener('DOMContentLoaded', function() {

  // ── Z-score validation ──────────────────────
  const zInput = document.getElementById('z_score');
  if (zInput) {
    zInput.addEventListener('blur', function() {
      const val = parseFloat(this.value);
      if (isNaN(val) || val < 0.5 || val > 2.8) {
        this.style.borderColor = '#A53030';
        showError(this,
          'Z-score must be between 0.50 and 2.80.');
      } else {
        this.style.borderColor = '#2E7D52';
        clearError(this);
      }
    });
    zInput.addEventListener('input', function() {
      this.style.borderColor = '#AECDE8';
      clearError(this);
    });
  }

  // ── Income validation ───────────────────────
  const incInput = document.getElementById(
    'annual_income');
  if (incInput) {
    incInput.addEventListener('blur', function() {
      const val = parseInt(this.value);
      if (isNaN(val) || val < 0) {
        this.style.borderColor = '#A53030';
        showError(this,
          'Please enter a valid income.');
      } else {
        this.style.borderColor = '#2E7D52';
        clearError(this);
      }
    });
  }

  // ── Animate probability bars ────────────────
  const bars = document.querySelectorAll(
    '.prob-bar-fill');
  if (bars.length > 0) {
    bars.forEach(bar => {
      const target = bar.getAttribute('data-target');
      setTimeout(() => {
        bar.style.width = target + '%';
      }, 300);
    });
  }

  // ── Auto-dismiss flash messages ─────────────
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.opacity    = '0';
      f.style.transition = 'opacity .5s';
      setTimeout(() => f.remove(), 500);
    }, 5000);
  });

});

// ── Helpers ─────────────────────────────────────
function showError(el, msg) {
  let err = el.parentNode.querySelector(
    '.field-error');
  if (!err) {
    err = document.createElement('span');
    err.className = 'field-error';
    el.parentNode.appendChild(err);
  }
  err.textContent = msg;
}

function clearError(el) {
  const err = el.parentNode.querySelector(
    '.field-error');
  if (err) err.remove();
}