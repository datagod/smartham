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

document.addEventListener('DOMContentLoaded', () => {
  const themeKey = 'smartham.quizTheme';
  const themeSelect = document.getElementById('quiz-theme');
  if (themeSelect) {
    const saved = localStorage.getItem(themeKey) || 'modern';
    themeSelect.value = saved;
    const viewport = document.getElementById('feedback-viewport');
    if (viewport) viewport.className = `feedback-viewport theme-${saved}`;
    themeSelect.addEventListener('change', () => {
      const value = themeSelect.value;
      localStorage.setItem(themeKey, value);
      if (viewport) viewport.className = `feedback-viewport theme-${value}`;
    });
  }
});