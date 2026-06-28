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

function formatInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(
    /^([A-D])\)\s*/i,
    '<span class="feedback-choice-label">$1)</span> '
  );
  html = html.replace(
    /^([A-D])\s+is\s+/i,
    '<span class="feedback-choice-label">$1</span> is '
  );
  return html;
}

function isExplanationListLine(line) {
  const trimmed = line.trim();
  return (
    /^[-*•]\s+/.test(trimmed) ||
    /^\d+\.\s+/.test(trimmed) ||
    /^[A-D]\)\s/i.test(trimmed) ||
    /^[A-D]\s+is(n't| not)?\s/i.test(trimmed) ||
    /^[A-D]\s+does(n't| not)?\s/i.test(trimmed)
  );
}

function formatExplanation(text) {
  if (!text) return '';

  const blocks = String(text)
    .replace(/\r\n/g, '\n')
    .trim()
    .split(/\n\s*\n/);

  let html = '';
  for (const block of blocks) {
    const lines = block
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) continue;

    if (lines.length === 1) {
      const line = lines[0];
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        const level = heading[1].length;
        const content = formatInlineMarkdown(heading[2]);
        html +=
          level <= 2
            ? `<h2 class="summary-section">${content}</h2>`
            : `<h3>${content}</h3>`;
      } else if (line.endsWith(':') && line.length < 96 && !/\.\s/.test(line)) {
        html += `<h3 class="feedback-lead">${formatInlineMarkdown(line)}</h3>`;
      } else {
        const choiceItem = /^[A-D]\s+(is|isn't|is not|does|doesn't|does not)\b/i.test(line);
        const choiceClass = choiceItem ? ' class="feedback-choice-item"' : '';
        html += `<p${choiceClass}>${formatInlineMarkdown(line)}</p>`;
      }
      continue;
    }

    const listLines = lines.filter(isExplanationListLine);
    if (listLines.length >= 2 && listLines.length >= lines.length - 1) {
      html += '<ul class="feedback-points">';
      for (const line of lines) {
        const cleaned = line.replace(/^[-*•]\s+/, '').replace(/^\d+\.\s+/, '');
        html += `<li>${formatInlineMarkdown(cleaned)}</li>`;
      }
      html += '</ul>';
      continue;
    }

    for (const line of lines) {
      html += `<p>${formatInlineMarkdown(line)}</p>`;
    }
  }

  return html;
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