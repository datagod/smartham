const FEEDBACK_THEME_KEY = 'smartham.feedbackTheme';

const THEME_OPTIONS = [
  { value: 'mainframe', label: '1970s mainframe' },
  { value: 'dotmatrix', label: '80s dot matrix printer' },
  { value: 'amber', label: 'Amber terminal' },
  { value: 'ansi', label: 'ANSI color terminal' },
  { value: 'blueprint', label: 'Blueprint' },
  { value: 'c64', label: 'Commodore 64' },
  { value: 'dune1984', label: 'Dune 1984' },
  { value: 'computer50s', label: 'Early 1950s computer' },
  { value: 'empire', label: 'Galactic Empire' },
  { value: 'icom', label: 'ICOM IC-9700' },
  { value: 'phosphor', label: 'Green phosphor CRT' },
  { value: 'kawaiimail', label: 'Kawaii Mail' },
  { value: 'lsmail', label: 'Leisure Suit Mailman' },
  { value: 'teleprinter', label: 'Line printer' },
  { value: 'logansrun', label: "Logan's Run" },
  { value: 'macintosh', label: 'Macintosh' },
  { value: 'mailtrek', label: 'Mail Trek (LCARS)' },
  { value: 'mailcraft', label: 'MailCraft' },
  { value: 'modern', label: 'Modern display' },
  { value: 'nasa70s', label: 'NASA Mission Control' },
  { value: 'newsprint', label: 'Newsprint' },
  { value: 'pacmail', label: 'PacMail' },
  { value: 'pdp11', label: 'PDP-11 terminal' },
  { value: 'reddwarf', label: 'Red Dwarf' },
  { value: 'arcade', label: 'Retro arcade CRT' },
  { value: 'solarized', label: 'Solarized' },
  { value: 'tripleplanets', label: 'Triple Planets' },
  { value: 'typewriter', label: 'Typewriter' },
  { value: 'weylandyutani', label: 'Weyland-Yutani Corp' },
].sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));

const THEMES = THEME_OPTIONS.map((t) => t.value);

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function populateThemeSelect(select) {
  if (!select) return;
  select.innerHTML = THEME_OPTIONS.map(
    ({ value, label }) =>
      `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`
  ).join('');
}

function applyTheme(theme) {
  if (theme === 'minecraft') theme = 'mailcraft';
  const chosen = THEMES.includes(theme) ? theme : 'modern';
  document.querySelectorAll('[data-theme-select]').forEach((select) => {
    select.value = chosen;
  });
  document.querySelectorAll('[data-theme-viewport]').forEach((viewport) => {
    viewport.className = `summary-viewport theme-${chosen}`;
  });
  try {
    localStorage.setItem(FEEDBACK_THEME_KEY, chosen);
  } catch (_) {
    /* ignore */
  }
}

function showToasts(awards) {
  const stack = document.getElementById('toast-stack');
  if (!stack || !Array.isArray(awards) || !awards.length) return;
  for (const award of awards) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.innerHTML = `<strong>${award.icon} ${award.name}</strong><br>${award.description}`;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 6000);
  }
}

function setThemedContent(html, bodyId = 'feedback-body') {
  const body = document.getElementById(bodyId);
  if (!body) return;
  body.className = 'summary-body';
  body.innerHTML = `<div class="markdown-body">${html}</div>`;
}

function setFeedbackContent(html) {
  setThemedContent(html);
}

async function refreshHeaderStatus() {
  const el = document.getElementById('header-status');
  if (!el) return;
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    el.textContent = `${data.total_questions} questions loaded · ${data.attempts} attempts · streak ${data.streak}`;
  } catch (_) {
    /* ignore */
  }
}

function initThemes() {
  const selects = document.querySelectorAll('[data-theme-select]');
  if (!selects.length) return;
  let saved = 'modern';
  try {
    saved = localStorage.getItem(FEEDBACK_THEME_KEY) || 'modern';
  } catch (_) {
    /* ignore */
  }
  selects.forEach((select) => {
    populateThemeSelect(select);
    select.addEventListener('change', () => applyTheme(select.value));
  });
  applyTheme(saved);
}

document.addEventListener('DOMContentLoaded', initThemes);