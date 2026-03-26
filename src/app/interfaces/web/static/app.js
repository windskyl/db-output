const DOMAIN_LABELS = {
  jobs: '招聘信息',
  company_intel: '公司情报',
  finance: '金融市场',
  public_sentiment: '公众舆情',
};

const TOPIC_LABELS = {
  jobs: {
    backend: '后端开发',
    frontend: '前端开发',
    algorithm: '算法题与算法岗',
    testing: '测试与质量保障',
    devops: 'DevOps 与运维',
    data_engineering: '数据工程',
    client: '客户端开发',
  },
  company_intel: {
    company_profile: '公司画像',
    product_update: '产品动态',
    tech_blog: '技术博客',
    open_source_activity: '开源动态',
    funding_event: '融资事件',
    career_page: '招聘页面',
  },
  finance: {
    market_quote: '行情报价',
    company_announcement: '公司公告',
    financial_report: '财务报告',
    fund_holding: '基金持仓',
    investment_news: '投资新闻',
  },
  public_sentiment: {
    interview_experience: '面试体验',
    salary_benefits: '薪酬福利',
    workload_overtime: '工作强度',
    management_culture: '管理与文化',
    tech_stack_engineering: '技术栈与工程',
    layoff_hiring_freeze: '裁员与冻结招聘',
    remote_office_policy: '远程与办公政策',
  },
};

const SENTIMENT_LABELS = {
  positive: '偏正向',
  neutral: '中性',
  negative: '偏负向',
};

const RUN_STATUS_LABELS = {
  success: '成功',
  failed: '失败',
  unknown: '未知',
};

const ARTIFACT_LABELS = {
  raw_file: '原始数据文件',
  normalized_file: '归一化文件',
  sqlite_file: 'SQLite 结果库',
  quality_report_file: '质量报告',
  run_report_file: '运行报告',
  cache_dir: '缓存目录',
};

const IMPORT_MODE_LABELS = {
  json: 'JSON',
  json_block: 'JSON 代码块',
  heuristic: '启发式解析',
};

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
  downloadTaskBtn: document.getElementById('downloadTaskBtn'),
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

function formatDomainLabel(domainName) {
  return DOMAIN_LABELS[domainName] || domainName || '未知领域';
}

function formatTopicLabel(domainName, topicName) {
  return TOPIC_LABELS[domainName]?.[topicName] || topicName || '未命名主题';
}

function formatSentimentLabel(label) {
  return SENTIMENT_LABELS[label] || label || '未知';
}

function formatRunStatus(status) {
  return RUN_STATUS_LABELS[status] || status || '未知';
}

function formatSourceText(source) {
  if (!source) {
    return '未知来源';
  }
  if (typeof source === 'string') {
    return source;
  }
  return source.source_label || source.source_id || source.connector_kind || '未知来源';
}

function formatArtifactText(key, value) {
  return `${ARTIFACT_LABELS[key] || key}：${value}`;
}

function formatImportMode(mode) {
  return IMPORT_MODE_LABELS[mode] || mode || '未知模式';
}

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
    throw new Error(payload.error || '请求失败。');
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
    text.textContent = formatTopicLabel(domainName, topic);
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
    option.textContent = formatSourceText(source);
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
  ensureSelectOption(els.targetTypeInput, value.targetType, formatTargetTypeLabel(value.targetType));
  ensureSelectOption(els.scenarioInput, value.scenario, formatScenarioLabel(value.scenario));
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
    throw new Error('任务 JSON 为空。');
  }
  return JSON.parse(text);
}

function setTaskEditor(task) {
  els.taskJsonEditor.value = stringifyJson(task);
}

function hydrateFormFromTask(task) {
  if (!task) {
    return;
  }
  els.domainSelect.value = task.domain || els.domainSelect.value;
  applyDomainDefaults(els.domainSelect.value);
  renderTopicOptions(els.domainSelect.value);
  renderSourceOptions(els.domainSelect.value);

  const scenarioValue = task.scenario_template || '';
  const targetTypeValue = task.targets?.[0]?.type || '';
  ensureSelectOption(els.scenarioInput, scenarioValue, formatScenarioLabel(scenarioValue));
  ensureSelectOption(els.targetTypeInput, targetTypeValue, formatTargetTypeLabel(targetTypeValue));
  els.scenarioInput.value = scenarioValue;
  els.taskIdInput.value = task.task_id || '';
  els.targetTypeInput.value = targetTypeValue;
  els.targetValueInput.value = task.targets?.[0]?.value || '';
  els.startDateInput.value = (task.time_range?.start || '').slice(0, 10);
  els.endDateInput.value = (task.time_range?.end || '').slice(0, 10);
  els.timezoneInput.value = task.time_range?.timezone || 'UTC';
  els.selectionModeSelect.value = task.source_policy?.selection_mode || 'auto';
  els.minRelevanceInput.value = task.relevance_policy?.min_relevance_score ?? 0.6;
  els.maxSourcesInput.value = task.source_policy?.max_sources ?? 3;
  els.maxOutputInput.value = task.output_policy?.max_output_records ?? 1000;
  els.allowHtmlInput.checked = task.source_policy?.allow_html ?? true;
  els.allowRssInput.checked = task.source_policy?.allow_rss ?? true;
  els.allowApiInput.checked = task.source_policy?.allow_api ?? true;
  els.preferOfficialInput.checked = task.source_policy?.prefer_official ?? false;
  els.enableCacheInput.checked = task.run_policy?.enable_cache ?? false;

  const selectedTopics = new Set(task.topic_scope || []);
  document.querySelectorAll('.topic-chip input').forEach((input) => {
    input.checked = selectedTopics.has(input.value);
  });

  const selectedSources = new Set(task.source_policy?.whitelist || []);
  Array.from(els.sourceWhitelist.options).forEach((option) => {
    option.selected = selectedSources.has(option.value);
  });
}

function renderSummaryCards(cards) {
  els.summaryCards.innerHTML = '';
  if (!cards.length) {
    els.summaryCards.innerHTML = '<div class="summary-card"><div class="summary-label">暂无摘要</div><div class="summary-value">-</div></div>';
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
    container.textContent = '暂无内容。';
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
    els.recentTasks.textContent = '本地还没有运行记录。';
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
    meta.textContent = `领域：${formatDomainLabel(item.domain)}｜状态：${formatRunStatus(item.status)}｜输出：${item.output_count}｜更新时间：${item.updated_at}`;
    left.append(title, meta);
    const actions = document.createElement('div');
    actions.className = 'task-row-actions';

    const useBtn = document.createElement('button');
    useBtn.className = 'ghost-btn';
    useBtn.type = 'button';
    useBtn.textContent = '复用任务';
    useBtn.addEventListener('click', () => runAction(() => loadRecentTaskIntoEditor(item.task_id, item.domain)));

    const reportBtn = document.createElement('button');
    reportBtn.className = 'ghost-btn';
    reportBtn.type = 'button';
    reportBtn.textContent = '查看报告';
    reportBtn.addEventListener('click', () => runAction(() => loadRecentTaskReport(item.task_id, item.domain)));

    actions.append(useBtn, reportBtn);
    row.append(left, actions);
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
  setStatus('success', '已加载历史报告');
  renderResult('report', payload.result);
}

async function loadRecentTaskIntoEditor(taskId, domain) {
  const payload = await fetchJson('/api/task', {
    method: 'POST',
    body: JSON.stringify({ task_id: taskId, domain }),
  });
  const taskPayload = payload.result.task_payload;
  if (!taskPayload) {
    throw new Error('该历史任务未保存完整任务内容，无法回填。');
  }
  setTaskEditor(taskPayload);
  hydrateFormFromTask(taskPayload);
  switchTab('json');
  setStatus('success', '任务已回填');
  els.resultNarrative.textContent = `任务 ${taskId} 已回填到编辑器，你可以直接校验、调整或重新运行。`;
  els.resultJson.textContent = stringifyJson(payload.result);
}

function renderDomainSummary(summary) {
  els.domainSummary.innerHTML = '';
  if (!summary) {
    els.domainSummary.textContent = '暂时没有可展示的领域摘要。';
    return;
  }

  if (summary.narrative) {
    const narrative = document.createElement('article');
    narrative.className = 'topic-card';
    narrative.innerHTML = `<div class="topic-copy"><p>${summary.narrative}</p></div>`;
    els.domainSummary.appendChild(narrative);
  }

  if (summary.cards?.length) {
    const cardRow = document.createElement('div');
    cardRow.className = 'summary-grid';
    for (const item of summary.cards) {
      const card = document.createElement('article');
      card.className = 'summary-card';
      card.innerHTML = '<div class="summary-label"></div><div class="summary-value"></div>';
      card.querySelector('.summary-label').textContent = item.label;
      card.querySelector('.summary-value').textContent = String(item.value);
      cardRow.appendChild(card);
    }
    els.domainSummary.appendChild(cardRow);
  }

  if (summary.topics?.length) {
    for (const topic of summary.topics) {
      const card = document.createElement('article');
      card.className = 'topic-card';
      const positiveCues = (topic.positive_cue_counts || []).map((item) => `${item.cue} x${item.count}`);
      const negativeCues = (topic.negative_cue_counts || []).map((item) => `${item.cue} x${item.count}`);
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
      card.querySelector('h4').textContent = formatTopicLabel(summary.kind, topic.topic_name);
      card.querySelector('.topic-badge').textContent = `主导情绪：${formatSentimentLabel(topic.dominant_sentiment_label)}`;
      const metricRow = card.querySelector('.metric-row');
      const metrics = [
        `帖子 ${topic.post_count}`,
        `正向 ${topic.positive_count}`,
        `中性 ${topic.neutral_count}`,
        `负向 ${topic.negative_count}`,
        `均分 ${topic.average_sentiment_score}`,
      ];
      for (const metric of metrics) {
        const pill = document.createElement('span');
        pill.className = 'metric-pill';
        pill.textContent = metric;
        metricRow.appendChild(pill);
      }
      card.querySelector('.topic-copy').innerHTML = `
        <p><strong>最正向样本：</strong>${topic.most_positive_title || '暂无'}</p>
        <p><strong>最负向样本：</strong>${topic.most_negative_title || '暂无'}</p>
        <p><strong>最中性样本：</strong>${topic.most_neutral_title || '暂无'}</p>
      `;
      const positiveList = card.querySelector('.cue-list.positive');
      const negativeList = card.querySelector('.cue-list.negative');
      for (const cue of positiveCues) {
        const chip = document.createElement('span');
        chip.className = 'cue-chip';
        chip.textContent = `正向线索 ${cue}`;
        positiveList.appendChild(chip);
      }
      for (const cue of negativeCues) {
        const chip = document.createElement('span');
        chip.className = 'cue-chip';
        chip.textContent = `负向线索 ${cue}`;
        negativeList.appendChild(chip);
      }
      els.domainSummary.appendChild(card);
    }
    return;
  }

  if (summary.sections?.length) {
    for (const section of summary.sections) {
      const card = document.createElement('article');
      card.className = 'topic-card';
      card.innerHTML = '<div class="topic-head"><h4></h4></div><div class="metric-row"></div>';
      card.querySelector('h4').textContent = section.title;
      const metricRow = card.querySelector('.metric-row');
      for (const item of section.items || []) {
        const pill = document.createElement('span');
        pill.className = 'metric-pill';
        pill.textContent = `${item.label}：${item.value}`;
        metricRow.appendChild(pill);
      }
      els.domainSummary.appendChild(card);
    }
    return;
  }

  els.domainSummary.textContent = '暂时没有可展示的领域摘要。';
}

function summarizeResult(kind, result) {
  if (kind === 'validate') {
    const task = result.task || {};
    const sources = result.selected_source_details || result.selected_sources || [];
    return {
      text: `任务 ${task.task_id || '未命名任务'} 校验通过。当前配置会在 ${formatDomainLabel(task.domain || '')} 领域选择 ${sources.length} 个来源。`,
      cards: [
        { label: '已选来源', value: sources.length },
        { label: '目标数', value: task.target_count || 0 },
      ],
    };
  }
  if (kind === 'run') {
    const report = result.quality_report || {};
    return {
      text: `任务运行完成。共抓取 ${report.raw_count || 0} 条原始记录，归一化 ${report.normalized_count || 0} 条，最终保留 ${report.output_count || 0} 条结果。`,
      cards: [
        { label: '原始记录', value: report.raw_count || 0 },
        { label: '归一化', value: report.normalized_count || 0 },
        { label: '最终输出', value: report.output_count || 0 },
        { label: '请求数', value: report.fetch_stats?.total_requests || 0 },
      ],
    };
  }
  if (kind === 'report') {
    const report = result.quality_report || {};
    return {
      text: `已加载质量报告。该任务共产出 ${report.output_count || 0} 条最终结果，下方摘要汇总了最值得关注的信号。`,
      cards: [
        { label: '最终输出', value: report.output_count || 0 },
        { label: '告警数', value: (report.warnings || []).length },
      ],
    };
  }
  return { text: '操作已完成。', cards: [] };
}

function renderResult(kind, result) {
  const summary = summarizeResult(kind, result);
  els.resultNarrative.textContent = summary.text;
  renderSummaryCards(summary.cards);
  renderDomainSummary(result.quality_report?.domain_summary || result.domain_summary || null);
  const selectedSources = result.selected_source_details || result.selected_sources || [];
  renderListCard(els.selectedSources, selectedSources.map((item) => formatSourceText(item)));
  const artifacts = result.artifacts || result.files || {};
  renderListCard(
    els.artifactPaths,
    Object.entries(artifacts).map(([key, value]) => formatArtifactText(key, value)),
  );
  els.resultJson.textContent = stringifyJson(result);
}

async function handleBuildFromForm() {
  setStatus('idle', '正在生成草稿');
  const payload = await fetchJson('/api/draft/form', {
    method: 'POST',
    body: JSON.stringify(currentFormPayload()),
  });
  setTaskEditor(payload.task);
  setStatus('success', '草稿已生成');
  els.resultNarrative.textContent = '已根据表单生成任务草稿。你可以直接校验或运行，也可以先调整 JSON。';
}

async function handleImportDocument() {
  const file = els.documentInput.files?.[0];
  if (!file) {
    throw new Error('请先选择本地文档。');
  }
  const content = await file.text();
  const payload = await fetchJson('/api/draft/document', {
    method: 'POST',
    body: JSON.stringify({ file_name: file.name, content }),
  });
  state.importedDocument = payload.document;
  els.documentPreview.textContent = payload.document.preview || '';
  setTaskEditor(payload.task_payload);
  hydrateFormFromTask(payload.task_payload);
  setStatus('success', `已导入（${formatImportMode(payload.mode)}）`);
  const warnings = payload.warnings?.length ? ` 注意：${payload.warnings.join(' ')}` : '';
  els.resultNarrative.textContent = `文档已安全解析为任务草稿。${warnings}`;
  els.resultJson.textContent = stringifyJson(payload);
}

async function handleValidate() {
  const payload = await fetchJson('/api/validate', {
    method: 'POST',
    body: JSON.stringify({ task: getTaskFromEditor() }),
  });
  setStatus('success', '校验通过');
  renderResult('validate', payload.result);
}

async function handleRun() {
  const payload = await fetchJson('/api/run', {
    method: 'POST',
    body: JSON.stringify({ task: getTaskFromEditor() }),
  });
  setStatus('success', '运行完成');
  renderResult('run', payload.result);
  await loadRecentTasks();
}

function downloadCurrentTaskJson() {
  const task = getTaskFromEditor();
  const blob = new Blob([stringifyJson(task)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${task.task_id || 'task'}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  setStatus('success', '任务 JSON 已下载');
}

async function handleReport() {
  const task = getTaskFromEditor();
  const payload = await fetchJson('/api/report', {
    method: 'POST',
    body: JSON.stringify({ task_id: task.task_id, domain: task.domain, kind: 'quality' }),
  });
  setStatus('success', '报告已加载');
  renderResult('report', payload.result);
}

async function loadMeta() {
  const payload = await fetchJson('/api/meta');
  state.meta = payload.meta;
  els.exampleSelect.innerHTML = '<option value="">请选择示例任务</option>';
  for (const example of state.meta.examples) {
    const option = document.createElement('option');
    option.value = example.name;
    const domainText = example.domain ? `｜${formatDomainLabel(example.domain)}` : '';
    option.textContent = `${example.name}${domainText}`;
    els.exampleSelect.appendChild(option);
  }
  els.domainSelect.innerHTML = '';
  for (const domain of state.meta.domains) {
    const option = document.createElement('option');
    option.value = domain.name;
    option.textContent = formatDomainLabel(domain.name);
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
    throw new Error('请先选择示例任务。');
  }
  const payload = await fetchJson(`/api/example?name=${encodeURIComponent(name)}`);
  setTaskEditor(payload.task);
  hydrateFormFromTask(payload.task);
  setStatus('success', '示例已载入');
  els.resultNarrative.textContent = `示例任务 ${name} 已载入任务 JSON 编辑器。`;
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
  els.downloadTaskBtn.addEventListener('click', () => runAction(async () => downloadCurrentTaskJson()));
  els.loadExampleBtn.addEventListener('click', () => runAction(loadExample));
  els.refreshTasksBtn.addEventListener('click', () => runAction(loadRecentTasks));
}

async function runAction(fn) {
  try {
    setStatus('idle', '处理中');
    await fn();
  } catch (error) {
    setStatus('error', '出错');
    els.resultNarrative.textContent = error.message || '发生未知错误。';
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
    setStatus('idle', '就绪');
    els.resultNarrative.textContent = '请选择领域，然后填写表单或导入本地文档。先生成任务草稿，再执行校验或运行。';
  } catch (error) {
    setStatus('error', '初始化失败');
    els.resultNarrative.textContent = error.message || '初始化失败。';
    els.resultJson.textContent = error.stack || String(error);
  }
})();