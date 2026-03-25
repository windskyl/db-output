const state = {
  meta: null,
  importedDocument: null,
};

const els = {
  domainSelect: document.getElementById('domainSelect'),
  scenarioInput: document.getElementById('scenarioInput'),
  taskIdInput: document.getElementById('taskIdInput'),
  targetTypeInput: document.getElementById('targetTypeInput'),
  targetValueInput: document.getElementById('targetValueInput'),
  startDateInput: document.getElementById('startDateInput'),
  endDateInput: document.getElementById('endDateInput'),
  timezoneInput: document.getElementById('timezoneInput'),
  selectionModeSelect: document.getElementById('selectionModeSelect'),
  minRelevanceInput: document.getElementById('minRelevanceInput'),
  maxSourcesInput: document.getElementById('maxSourcesInput'),
  maxOutputInput: document.getElementById('maxOutputInput'),
  topicOptions: document.getElementById('topicOptions'),
  sourceWhitelist: document.getElementById('sourceWhitelist'),
  allowHtmlInput: document.getElementById('allowHtmlInput'),
  allowRssInput: document.getElementById('allowRssInput'),
  allowApiInput: document.getElementById('allowApiInput'),
  preferOfficialInput: document.getElementById('preferOfficialInput'),
  enableCacheInput: document.getElementById('enableCacheInput'),
  buildFromFormBtn: document.getElementById('buildFromFormBtn'),
  documentInput: document.getElementById('documentInput'),
  importDocumentBtn: document.getElementById('importDocumentBtn'),
  documentPreview: document.getElementById('documentPreview'),
  taskJsonEditor: document.getElementById('taskJsonEditor'),
  validateBtn: document.getElementById('validateBtn'),
  runBtn: document.getElementById('runBtn'),
  reportBtn: document.getElementById('reportBtn'),
  resultJson: document.getElementById('resultJson'),
  summaryCards: document.getElementById('summaryCards'),
  selectedSources: document.getElementById('selectedSources'),
  artifactPaths: document.getElementById('artifactPaths'),
  domainSummary: document.getElementById('domainSummary'),
  resultNarrative: document.getElementById('resultNarrative'),
  statusBadge: document.getElementById('statusBadge'),
  exampleSelect: document.getElementById('exampleSelect'),
  loadExampleBtn: document.getElementById('loadExampleBtn'),
  recentTasks: document.getElementById('recentTasks'),
  refreshTasksBtn: document.getElementById('refreshTasksBtn'),
};

function setStatus(kind, text) {
  els.statusBadge.className = `status-badge ${kind}`;
  els.statusBadge.textContent = text;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.error || 'Request failed');
  }
  return payload;
}

function stringifyJson(value) {
  return JSON.stringify(value, null, 2);
}

function coerceSelectedTopics() {
  return Array.from(document.querySelectorAll('.topic-chip input:checked')).map((input) => input.value);
}

function coerceSelectedSources() {
  return Array.from(els.sourceWhitelist.selectedOptions).map((option) => option.value);
}

function renderTopicOptions(domainName) {
  const domain = state.meta.domains.find((item) => item.name === domainName);
  els.topicOptions.innerHTML = '';
  if (!domain) {
    return;
  }
  for (const topic of domain.topics) {
    const label = document.createElement('label');
    label.className = 'topic-chip';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = topic;
    if (topic === domain.topics[0]) {
      input.checked = true;
    }
    const text = document.createElement('span');
    text.textContent = topic;
    label.append(input, text);
    els.topicOptions.appendChild(label);
  }
}

function renderSourceOptions(domainName) {
  const sources = state.meta.sources[domainName] || [];
  els.sourceWhitelist.innerHTML = '';
  for (const source of sources) {
    const option = document.createElement('option');
    option.value = source.source_id;
    option.textContent = `${source.source_id} · ${source.source_label}`;
    els.sourceWhitelist.appendChild(option);
  }
}

function applyDomainDefaults(domainName) {
  const defaults = {
    jobs: { targetType: 'keyword', scenario: 'job_hunt_engineering_basic', channels: [true, true, true], selectionMode: 'auto' },
    company_intel: { targetType: 'company', scenario: 'company_due_diligence', channels: [true, false, false], selectionMode: 'auto' },
    finance: { targetType: 'ticker', scenario: 'investment_market_quote_basic', channels: [true, true, true], selectionMode: 'auto' },
    public_sentiment: { targetType: 'company', scenario: 'company_sentiment_tracking_basic', channels: [false, false, true], selectionMode: 'explicit' },
  };
  const value = defaults[domainName] || defaults.jobs;
  els.targetTypeInput.value = value.targetType;
  els.scenarioInput.value = value.scenario;
  els.allowHtmlInput.checked = value.channels[0];
  els.allowRssInput.checked = value.channels[1];
  els.allowApiInput.checked = value.channels[2];
  els.selectionModeSelect.value = value.selectionMode;
}

function currentFormPayload() {
  return {
    domain: els.domainSelect.value,
    scenario_template: els.scenarioInput.value,
    task_id: els.taskIdInput.value,
    target_type: els.targetTypeInput.value,
    target_value: els.targetValueInput.value,
    topic_scope: coerceSelectedTopics(),
    start: els.startDateInput.value,
    end: els.endDateInput.value,
    timezone: els.timezoneInput.value,
    selection_mode: els.selectionModeSelect.value,
    whitelist: coerceSelectedSources(),
    allow_html: els.allowHtmlInput.checked,
    allow_rss: els.allowRssInput.checked,
    allow_api: els.allowApiInput.checked,
    prefer_official: els.preferOfficialInput.checked,
    enable_cache: els.enableCacheInput.checked,
    min_relevance_score: els.minRelevanceInput.value,
    max_sources: els.maxSourcesInput.value,
    max_output_records: els.maxOutputInput.value,
  };
}

function getTaskFromEditor() {
  const text = els.taskJsonEditor.value.trim();
  if (!text) {
    throw new Error('Task JSON is empty.');
  }
  return JSON.parse(text);
}

function setTaskEditor(task) {
  els.taskJsonEditor.value = stringifyJson(task);
}

function renderSummaryCards(cards) {
  els.summaryCards.innerHTML = '';
  if (!cards.length) {
    els.summaryCards.innerHTML = '<div class="summary-card"><div class="summary-label">No summary</div><div class="summary-value">-</div></div>';
    return;
  }
  for (const card of cards) {
    const node = document.createElement('article');
    node.className = 'summary-card';
    node.innerHTML = '<div class="summary-label"></div><div class="summary-value"></div>';
    node.querySelector('.summary-label').textContent = card.label;
    node.querySelector('.summary-value').textContent = String(card.value);
    els.summaryCards.appendChild(node);
  }
}

function renderListCard(container, items) {
  container.innerHTML = '';
  if (!items.length) {
    container.textContent = 'Nothing to show yet.';
    return;
  }
  const list = document.createElement('ul');
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    list.appendChild(li);
  }
  container.appendChild(list);
}

function renderRecentTasks(items) {
  els.recentTasks.innerHTML = '';
  if (!items.length) {
    els.recentTasks.textContent = 'No local runs are available yet.';
    return;
  }
  for (const item of items) {
    const row = document.createElement('article');
    row.className = 'task-row';
    const left = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'task-row-title';
    title.textContent = item.task_id;
    const meta = document.createElement('div');
    meta.className = 'task-row-meta';
    meta.textContent = `${item.domain} · ${item.status} · output ${item.output_count} · updated ${item.updated_at}`;
    left.append(title, meta);
    const button = document.createElement('button');
    button.className = 'ghost-btn';
    button.type = 'button';
    button.textContent = 'View report';
    button.addEventListener('click', () => runAction(() => loadRecentTaskReport(item.task_id, item.domain)));
    row.append(left, button);
    els.recentTasks.appendChild(row);
  }
}

async function loadRecentTasks() {
  const payload = await fetchJson('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({ limit: 8 }),
  });
  renderRecentTasks(payload.result.tasks || []);
}

async function loadRecentTaskReport(taskId, domain) {
  const payload = await fetchJson('/api/report', {
    method: 'POST',
    body: JSON.stringify({ task_id: taskId, domain, kind: 'quality' }),
  });
  setStatus('success', 'Historic report loaded');
  renderResult('report', payload.result);
}

function renderDomainSummary(summary) {
  els.domainSummary.innerHTML = '';
  if (!summary || !summary.topics || !summary.topics.length) {
    els.domainSummary.textContent = 'No domain-specific summary is available yet.';
    return;
  }
  for (const topic of summary.topics) {
    const card = document.createElement('article');
    card.className = 'topic-card';
    const positiveCues = (topic.positive_cue_counts || []).map((item) => `${item.cue} ×${item.count}`);
    const negativeCues = (topic.negative_cue_counts || []).map((item) => `${item.cue} ×${item.count}`);
    card.innerHTML = `
      <div class="topic-head">
        <h4></h4>
        <span class="topic-badge"></span>
      </div>
      <div class="metric-row"></div>
      <div class="topic-copy"></div>
      <div class="cue-list positive"></div>
      <div class="cue-list negative"></div>
    `;
    card.querySelector('h4').textContent = topic.topic_name;
    card.querySelector('.topic-badge').textContent = `dominant: ${topic.dominant_sentiment_label}`;
    const metricRow = card.querySelector('.metric-row');
    const metrics = [
      `posts ${topic.post_count}`,
      `positive ${topic.positive_count}`,
      `neutral ${topic.neutral_count}`,
      `negative ${topic.negative_count}`,
      `avg ${topic.average_sentiment_score}`,
    ];
    for (const metric of metrics) {
      const pill = document.createElement('span');
      pill.className = 'metric-pill';
      pill.textContent = metric;
      metricRow.appendChild(pill);
    }
    card.querySelector('.topic-copy').innerHTML = `
      <p><strong>Most positive:</strong> ${topic.most_positive_title || 'N/A'}</p>
      <p><strong>Most negative:</strong> ${topic.most_negative_title || 'N/A'}</p>
      <p><strong>Most neutral:</strong> ${topic.most_neutral_title || 'N/A'}</p>
    `;
    const positiveList = card.querySelector('.cue-list.positive');
    const negativeList = card.querySelector('.cue-list.negative');
    if (positiveCues.length) {
      for (const cue of positiveCues) {
        const chip = document.createElement('span');
        chip.className = 'cue-chip';
        chip.textContent = `Positive cue ${cue}`;
        positiveList.appendChild(chip);
      }
    }
    if (negativeCues.length) {
      for (const cue of negativeCues) {
        const chip = document.createElement('span');
        chip.className = 'cue-chip';
        chip.textContent = `Negative cue ${cue}`;
        negativeList.appendChild(chip);
      }
    }
    els.domainSummary.appendChild(card);
  }
}

function summarizeResult(kind, result) {
  if (kind === 'validate') {
    const task = result.task || {};
    const sources = result.selected_sources || [];
    return {
      text: `Task ${task.task_id || ''} is valid. The current configuration would select ${sources.length} source(s) for domain ${task.domain || ''}.`,
      cards: [
        { label: 'Selected sources', value: sources.length },
        { label: 'Targets', value: task.target_count || 0 },
      ],
    };
  }
  if (kind === 'run') {
    const report = result.quality_report || {};
    return {
      text: `Run completed successfully. Collected ${report.raw_count || 0} raw records, normalized ${report.normalized_count || 0}, and kept ${report.output_count || 0} final rows.`,
      cards: [
        { label: 'Raw records', value: report.raw_count || 0 },
        { label: 'Normalized', value: report.normalized_count || 0 },
        { label: 'Output', value: report.output_count || 0 },
        { label: 'Requests', value: report.fetch_stats?.total_requests || 0 },
      ],
    };
  }
  if (kind === 'report') {
    const report = result.quality_report || {};
    return {
      text: `Quality report loaded. This task produced ${report.output_count || 0} final rows, and the domain summary below highlights the most useful signals.`,
      cards: [
        { label: 'Output', value: report.output_count || 0 },
        { label: 'Warnings', value: (report.warnings || []).length },
      ],
    };
  }
  return { text: 'Action completed.', cards: [] };
}

function renderResult(kind, result) {
  const summary = summarizeResult(kind, result);
  els.resultNarrative.textContent = summary.text;
  renderSummaryCards(summary.cards);
  renderDomainSummary(result.quality_report?.domain_summary || result.domain_summary || null);
  renderListCard(
    els.selectedSources,
    (result.selected_sources || []).map((item) => `${item.source_id} · ${item.source_label || item.connector_kind || ''}`),
  );
  const artifacts = result.artifacts || result.files || {};
  renderListCard(
    els.artifactPaths,
    Object.entries(artifacts).map(([key, value]) => `${key}: ${value}`),
  );
  els.resultJson.textContent = stringifyJson(result);
}

async function handleBuildFromForm() {
  setStatus('idle', 'Building draft');
  const payload = await fetchJson('/api/draft/form', {
    method: 'POST',
    body: JSON.stringify(currentFormPayload()),
  });
  setTaskEditor(payload.task);
  setStatus('success', 'Draft ready');
  els.resultNarrative.textContent = 'A task draft was generated from the form. You can validate or run it directly, or adjust the JSON first.';
}

async function handleImportDocument() {
  const file = els.documentInput.files?.[0];
  if (!file) {
    throw new Error('Please choose a local document first.');
  }
  const content = await file.text();
  const payload = await fetchJson('/api/draft/document', {
    method: 'POST',
    body: JSON.stringify({ file_name: file.name, content }),
  });
  state.importedDocument = payload.document;
  els.documentPreview.textContent = payload.document.preview || '';
  setTaskEditor(payload.task_payload);
  setStatus('success', `Imported (${payload.mode})`);
  const warnings = payload.warnings?.length ? ` Warnings: ${payload.warnings.join(' ')}` : '';
  els.resultNarrative.textContent = `The document was parsed safely into a task draft.${warnings}`;
  els.resultJson.textContent = stringifyJson(payload);
}

async function handleValidate() {
  const payload = await fetchJson('/api/validate', {
    method: 'POST',
    body: JSON.stringify({ task: getTaskFromEditor() }),
  });
  setStatus('success', 'Validation passed');
  renderResult('validate', payload.result);
}

async function handleRun() {
  const payload = await fetchJson('/api/run', {
    method: 'POST',
    body: JSON.stringify({ task: getTaskFromEditor() }),
  });
  setStatus('success', 'Run completed');
  renderResult('run', payload.result);
  await loadRecentTasks();
}

async function handleReport() {
  const task = getTaskFromEditor();
  const payload = await fetchJson('/api/report', {
    method: 'POST',
    body: JSON.stringify({ task_id: task.task_id, domain: task.domain, kind: 'quality' }),
  });
  setStatus('success', 'Report loaded');
  renderResult('report', payload.result);
}

async function loadMeta() {
  const payload = await fetchJson('/api/meta');
  state.meta = payload.meta;
  els.exampleSelect.innerHTML = '<option value="">Choose an example task</option>';
  for (const example of state.meta.examples) {
    const option = document.createElement('option');
    option.value = example.name;
    option.textContent = `${example.name} · ${example.domain || 'unknown'}`;
    els.exampleSelect.appendChild(option);
  }
  els.domainSelect.innerHTML = '';
  for (const domain of state.meta.domains) {
    const option = document.createElement('option');
    option.value = domain.name;
    option.textContent = domain.name;
    els.domainSelect.appendChild(option);
  }
  els.domainSelect.value = state.meta.domains[0]?.name || 'jobs';
  applyDomainDefaults(els.domainSelect.value);
  renderTopicOptions(els.domainSelect.value);
  renderSourceOptions(els.domainSelect.value);
}

async function loadExample() {
  const name = els.exampleSelect.value;
  if (!name) {
    throw new Error('Please choose an example task first.');
  }
  const payload = await fetchJson(`/api/example?name=${encodeURIComponent(name)}`);
  setTaskEditor(payload.task);
  setStatus('success', 'Example loaded');
  els.resultNarrative.textContent = `Example task ${name} is loaded into the Task JSON editor.`;
}

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === name);
  });
  document.querySelectorAll('.tab-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.dataset.tabPanel === name);
  });
}

function wireEvents() {
  document.querySelectorAll('.tab-btn').forEach((button) => {
    button.addEventListener('click', () => switchTab(button.dataset.tab));
  });
  els.domainSelect.addEventListener('change', () => {
    applyDomainDefaults(els.domainSelect.value);
    renderTopicOptions(els.domainSelect.value);
    renderSourceOptions(els.domainSelect.value);
  });
  els.buildFromFormBtn.addEventListener('click', () => runAction(handleBuildFromForm));
  els.importDocumentBtn.addEventListener('click', () => runAction(handleImportDocument));
  els.validateBtn.addEventListener('click', () => runAction(handleValidate));
  els.runBtn.addEventListener('click', () => runAction(handleRun));
  els.reportBtn.addEventListener('click', () => runAction(handleReport));
  els.loadExampleBtn.addEventListener('click', () => runAction(loadExample));
  els.refreshTasksBtn.addEventListener('click', () => runAction(loadRecentTasks));
}

async function runAction(fn) {
  try {
    setStatus('idle', 'Working');
    await fn();
  } catch (error) {
    setStatus('error', 'Error');
    els.resultNarrative.textContent = error.message;
    els.resultJson.textContent = error.stack || String(error);
    renderSummaryCards([]);
    renderListCard(els.selectedSources, []);
    renderListCard(els.artifactPaths, []);
    renderDomainSummary(null);
  }
}

(async function init() {
  try {
    await loadMeta();
    wireEvents();
    await loadRecentTasks();
    setStatus('idle', 'Ready');
    els.resultNarrative.textContent = 'Choose a domain and either fill the form or import a local document. Build a task draft first, then validate or run it.';
  } catch (error) {
    setStatus('error', 'Init failed');
    els.resultNarrative.textContent = error.message;
    els.resultJson.textContent = error.stack || String(error);
  }
})();