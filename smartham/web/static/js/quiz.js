let currentQuestion = null;
let answered = false;
let prefetchPromise = null;

function renderChoices(question) {
  const list = document.getElementById('choice-list');
  list.innerHTML = '';
  const labels = [
    ['A', question.choice_a],
    ['B', question.choice_b],
    ['C', question.choice_c],
    ['D', question.choice_d],
  ];
  for (const [letter, text] of labels) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'choice-btn';
    btn.dataset.choice = letter;
    btn.textContent = `${letter}) ${text}`;
    btn.addEventListener('click', () => submitAnswer(letter, btn));
    list.appendChild(btn);
  }
}

function prefetchExplanation(questionId) {
  prefetchPromise = fetch('/api/quiz/prefetch-explanation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id: questionId }),
  }).catch(() => null);
  return prefetchPromise;
}

function formatFeedback(data) {
  let html = '';
  if (data.correct) {
    html += `<p class="feedback-correct">Correct!</p><p>Streak: ${data.streak}</p>`;
  } else {
    html += `<p class="feedback-wrong">Incorrect. Correct answer: ${escapeHtml(data.correct_choice)}</p>`;
  }
  if (data.explanation) {
    html += `<p>${escapeHtml(data.explanation)}</p>`;
  } else if (data.explanation_error) {
    html += `<p class="summary-empty">${escapeHtml(data.explanation_error)}</p>`;
  }
  return html;
}

async function loadQuestion() {
  answered = false;
  prefetchPromise = null;
  const level = document.getElementById('quiz-level').value;
  const section = document.getElementById('quiz-section').value.trim();
  const params = new URLSearchParams({ limit: '1' });
  if (level) params.set('level', level);
  if (section) params.set('section', section);

  document.getElementById('quiz-meta').textContent = 'Loading…';
  document.getElementById('quiz-stem').textContent = '';
  document.getElementById('choice-list').innerHTML = '';
  setFeedbackContent('<p class="summary-empty">Preparing explanation while you think…</p>');

  const res = await fetch(`/api/questions?${params}`);
  const data = await res.json();
  if (!data.questions?.length) {
    document.getElementById('quiz-meta').textContent = 'No questions found. Ingest PDFs in Settings.';
    setFeedbackContent('<p class="summary-empty">No questions available.</p>');
    return;
  }
  currentQuestion = data.questions[0];
  document.getElementById('quiz-meta').textContent =
    `${currentQuestion.id} · ${currentQuestion.level} · ${currentQuestion.section}`;
  document.getElementById('quiz-stem').textContent = currentQuestion.stem;
  renderChoices(currentQuestion);
  prefetchExplanation(currentQuestion.id).then(async (resp) => {
    if (!resp || !currentQuestion || currentQuestion.id !== data.questions[0].id) return;
    const prefetch = await resp.json();
    if (prefetch.ready && prefetch.explanation) {
      setFeedbackContent(
        '<p class="summary-empty">Explanation ready — answer the question to see how you did.</p>'
      );
    }
  });
}

async function submitAnswer(choice, btn) {
  if (!currentQuestion || answered) return;
  answered = true;
  document.querySelectorAll('.choice-btn').forEach((el) => (el.disabled = true));

  if (prefetchPromise) {
    await prefetchPromise.catch(() => null);
  }

  const res = await fetch('/api/quiz/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id: currentQuestion.id, chosen: choice }),
  });
  const data = await res.json();

  if (data.correct) {
    btn.classList.add('is-correct');
  } else {
    btn.classList.add('is-wrong');
    document.querySelectorAll('.choice-btn').forEach((el) => {
      if (el.dataset.choice === data.correct_choice) el.classList.add('is-correct');
    });
  }

  setFeedbackContent(formatFeedback(data));

  if (!data.explanation && data.explanation_error?.includes('still being generated')) {
    const questionId = currentQuestion.id;
    for (let i = 0; i < 8; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const poll = await fetch(`/api/quiz/explanation/${encodeURIComponent(questionId)}`);
      const status = await poll.json();
      if (status.ready && status.explanation) {
        data.explanation = status.explanation;
        data.explanation_error = null;
        setFeedbackContent(formatFeedback(data));
        break;
      }
    }
  }

  showToasts(data.new_awards);
  refreshHeaderStatus();
}

function initQuizFilters() {
  const params = new URLSearchParams(window.location.search);
  const level = params.get('level');
  if (level === 'basic' || level === 'advanced') {
    document.getElementById('quiz-level').value = level;
  }
}

document.getElementById('btn-next')?.addEventListener('click', loadQuestion);
document.addEventListener('DOMContentLoaded', () => {
  initQuizFilters();
  loadQuestion();
});