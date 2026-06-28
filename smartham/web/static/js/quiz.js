let currentQuestion = null;
let answered = false;

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

async function loadQuestion() {
  answered = false;
  const level = document.getElementById('quiz-level').value;
  const section = document.getElementById('quiz-section').value.trim();
  const params = new URLSearchParams({ limit: '1' });
  if (level) params.set('level', level);
  if (section) params.set('section', section);

  document.getElementById('quiz-meta').textContent = 'Loading…';
  document.getElementById('quiz-stem').textContent = '';
  document.getElementById('choice-list').innerHTML = '';
  setFeedbackContent('<p class="summary-empty">Answer a question to see feedback and Ollama explanations.</p>');

  const res = await fetch(`/api/questions?${params}`);
  const data = await res.json();
  if (!data.questions?.length) {
    document.getElementById('quiz-meta').textContent = 'No questions found. Ingest PDFs in Settings.';
    return;
  }
  currentQuestion = data.questions[0];
  document.getElementById('quiz-meta').textContent =
    `${currentQuestion.id} · ${currentQuestion.level} · ${currentQuestion.section}`;
  document.getElementById('quiz-stem').textContent = currentQuestion.stem;
  renderChoices(currentQuestion);
}

async function submitAnswer(choice, btn) {
  if (!currentQuestion || answered) return;
  answered = true;
  document.querySelectorAll('.choice-btn').forEach((el) => (el.disabled = true));

  const res = await fetch('/api/quiz/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_id: currentQuestion.id, chosen: choice }),
  });
  const data = await res.json();

  if (data.correct) {
    btn.classList.add('is-correct');
    setFeedbackContent(
      `<p class="feedback-correct">Correct!</p><p>Streak: ${data.streak}</p>`
    );
  } else {
    btn.classList.add('is-wrong');
    document.querySelectorAll('.choice-btn').forEach((el) => {
      if (el.dataset.choice === data.correct_choice) el.classList.add('is-correct');
    });
    let html = `<p class="feedback-wrong">Incorrect. Correct answer: ${escapeHtml(data.correct_choice)}</p>`;
    if (data.explanation) {
      html += `<p>${escapeHtml(data.explanation)}</p>`;
    } else if (data.explanation_error) {
      html += `<p class="summary-empty">${escapeHtml(data.explanation_error)}</p>`;
    }
    setFeedbackContent(html);
  }

  showToasts(data.new_awards);
  refreshHeaderStatus();
}

document.getElementById('btn-next')?.addEventListener('click', loadQuestion);
document.addEventListener('DOMContentLoaded', loadQuestion);