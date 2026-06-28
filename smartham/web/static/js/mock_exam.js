let exam = null;
let index = 0;
let answers = {};
let timerId = null;
let deadline = null;

function showSection(id) {
  ['exam-setup', 'exam-active', 'exam-results'].forEach((name) => {
    const el = document.getElementById(name);
    if (el) el.hidden = name !== id;
  });
}

function renderExamQuestion() {
  const q = exam.questions[index];
  document.getElementById('exam-progress').textContent =
    `Question ${index + 1} of ${exam.questions.length}`;
  document.getElementById('exam-meta').textContent = `${q.id} · ${q.section}`;
  document.getElementById('exam-stem').textContent = q.stem;

  const list = document.getElementById('exam-choices');
  list.innerHTML = '';
  for (const [letter, key] of [
    ['A', 'choice_a'],
    ['B', 'choice_b'],
    ['C', 'choice_c'],
    ['D', 'choice_d'],
  ]) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'choice-btn';
    if (answers[q.id] === letter) btn.classList.add('is-correct');
    btn.textContent = `${letter}) ${q[key]}`;
    btn.addEventListener('click', () => {
      answers[q.id] = letter;
      renderExamQuestion();
    });
    list.appendChild(btn);
  }
}

function updateTimer() {
  const el = document.getElementById('exam-timer');
  if (!deadline || !el) return;
  const left = Math.max(0, deadline - Date.now());
  const mins = Math.floor(left / 60000);
  const secs = Math.floor((left % 60000) / 1000);
  el.textContent = `Time remaining: ${mins}:${String(secs).padStart(2, '0')}`;
}

async function startExam() {
  const level = document.getElementById('exam-level').value;
  const res = await fetch('/api/mock-exam/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.error || 'Could not start exam');
    return;
  }
  exam = data;
  index = 0;
  answers = {};
  showSection('exam-active');
  deadline = Date.now() + data.time_limit_minutes * 60 * 1000;
  if (timerId) clearInterval(timerId);
  timerId = setInterval(updateTimer, 1000);
  updateTimer();
  renderExamQuestion();
}

async function submitExam() {
  if (!exam) return;
  if (!confirm('Submit your mock exam?')) return;
  const res = await fetch('/api/mock-exam/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exam_id: exam.exam_id, answers }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.error || 'Submit failed');
    return;
  }
  if (timerId) clearInterval(timerId);
  showSection('exam-results');
  const body = document.getElementById('exam-results-body');
  body.innerHTML = `
    <p class="quiz-stem">${data.passed ? 'Passed' : 'Not passed'} — ${data.percent}% (${data.correct}/${data.total})</p>
    <p class="hint">Pass mark: ${Math.round(data.pass_mark * 100)}%</p>
  `;
  showToasts(data.new_awards);
  refreshHeaderStatus();
}

document.getElementById('btn-start-exam')?.addEventListener('click', startExam);
document.getElementById('btn-prev-q')?.addEventListener('click', () => {
  if (index > 0) { index -= 1; renderExamQuestion(); }
});
document.getElementById('btn-next-q')?.addEventListener('click', () => {
  if (index < exam.questions.length - 1) { index += 1; renderExamQuestion(); }
});
document.getElementById('btn-submit-exam')?.addEventListener('click', submitExam);
document.getElementById('btn-restart-exam')?.addEventListener('click', () => {
  showSection('exam-setup');
});