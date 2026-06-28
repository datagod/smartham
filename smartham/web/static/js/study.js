let selectedId = null;

async function loadSections() {
  const list = document.getElementById('study-list');
  const res = await fetch('/api/study/sections');
  const data = await res.json();
  if (!data.sections?.length) {
    list.innerHTML = '<p class="summary-empty">No study sections found. Ingest PDFs in Settings.</p>';
    return;
  }
  list.innerHTML = '<ul class="study-list"></ul>';
  const ul = list.querySelector('ul');
  for (const section of data.sections) {
    const li = document.createElement('li');
    li.className = 'study-item';
    li.innerHTML = `
      <div class="study-item-title">${escapeHtml(section.title || section.source_file)}</div>
      <div class="study-item-meta">${escapeHtml(section.source_file)} · page ${section.page_number}</div>
    `;
    li.addEventListener('click', () => selectSection(section.id));
    ul.appendChild(li);
  }
}

async function selectSection(id) {
  selectedId = id;
  document.getElementById('btn-summarize').disabled = false;
  const body = document.getElementById('study-body');
  body.innerHTML = '<p class="summary-empty">Loading…</p>';
  const res = await fetch(`/api/study/section/${id}`);
  const data = await res.json();
  body.innerHTML = `
    <h3 style="margin-bottom:0.5rem">${escapeHtml(data.title || data.source_file)}</h3>
    <p class="quiz-meta">${escapeHtml(data.source_file)} · page ${data.page_number}</p>
    <pre style="white-space:pre-wrap;font-family:var(--font);font-size:0.88rem;margin-top:0.75rem">${escapeHtml(data.body)}</pre>
  `;
}

document.getElementById('btn-summarize')?.addEventListener('click', async () => {
  if (!selectedId) return;
  const body = document.getElementById('study-body');
  const existing = body.innerHTML;
  body.innerHTML = existing + '<p class="hint" style="margin-top:1rem">Generating summary…</p>';
  const res = await fetch('/api/study/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section_id: selectedId }),
  });
  const data = await res.json();
  if (!res.ok) {
    body.innerHTML = existing + `<p class="status-line error" style="margin-top:1rem">${escapeHtml(data.error)}</p>`;
    return;
  }
  body.innerHTML = existing + `
    <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid var(--border)">
      <h3>Ollama Summary</h3>
      <pre style="white-space:pre-wrap;font-family:var(--font);font-size:0.9rem;margin-top:0.5rem">${escapeHtml(data.summary)}</pre>
    </div>
  `;
});

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

document.addEventListener('DOMContentLoaded', loadSections);