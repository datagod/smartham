let selectedId = null;

async function loadSections() {
  const list = document.getElementById('study-list');
  const res = await fetch('/api/study/sections');
  const data = await res.json();
  if (!data.sections?.length) {
    list.innerHTML = '<p class="summary-empty">No study sections found. Ingest PDFs in Settings.</p>';
    setThemedContent('<p class="summary-empty">No study sections available.</p>');
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
  setThemedContent('<p class="summary-empty">Select a section from the reference library.</p>');
}

function renderSectionContent(data, summaryHtml = '') {
  let html = `
    <h2>${escapeHtml(data.title || data.source_file)}</h2>
    <p class="summary-from">${escapeHtml(data.source_file)} · page ${data.page_number}</p>
    <pre style="white-space:pre-wrap;font-family:inherit;font-size:0.88rem">${escapeHtml(data.body)}</pre>
  `;
  if (summaryHtml) {
    html += `
      <h2 class="summary-section">Ollama Summary</h2>
      <pre style="white-space:pre-wrap;font-family:inherit;font-size:0.9rem">${escapeHtml(summaryHtml)}</pre>
    `;
  }
  return html;
}

async function selectSection(id) {
  selectedId = id;
  document.getElementById('btn-summarize').disabled = false;
  setThemedContent('<p class="summary-empty">Loading…</p>');
  const res = await fetch(`/api/study/section/${id}`);
  const data = await res.json();
  setThemedContent(renderSectionContent(data));
}

document.getElementById('btn-summarize')?.addEventListener('click', async () => {
  if (!selectedId) return;
  const sectionRes = await fetch(`/api/study/section/${selectedId}`);
  const sectionData = await sectionRes.json();
  setThemedContent(renderSectionContent(sectionData) + '<p class="summary-empty">Generating summary…</p>');

  const res = await fetch('/api/study/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section_id: selectedId }),
  });
  const data = await res.json();
  if (!res.ok) {
    setThemedContent(
      renderSectionContent(sectionData) +
        `<p class="summary-empty">${escapeHtml(data.error || 'Summary failed')}</p>`
    );
    return;
  }
  setThemedContent(renderSectionContent(sectionData, data.summary));
});

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

document.addEventListener('DOMContentLoaded', loadSections);