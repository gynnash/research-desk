'use strict';

(() => {
  const $ = selector => document.querySelector(selector);
  const state = {session: null, topics: [], confirmations: [], selected: null,
    preview: null, screen: 'topics', busy: false, revokeId: null, topicsAvailable: false, recordsAvailable: false};
  const fields = {title: $('#title'), angle: $('#angle'), audience: $('#audience'),
    target_words: $('#target-words')};

  function text(value, fallback = '') {
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return String(value);
    return fallback;
  }
  function list(value) { return Array.isArray(value) ? value : []; }
  function element(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = text(value);
    return node;
  }
  function setText(selector, value) { $(selector).textContent = text(value); }
  function message(selector, value) {
    const node = $(selector);
    node.textContent = text(value);
    node.hidden = !value;
  }
  function announce(value) { setText('#live', value); }
  function showGlobalError(value) {
    setText('#global-error-text', value);
    $('#global-error').hidden = !value;
  }
  function displayDate(value) {
    if (!value) return '时间未提供';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? text(value) : date.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
    });
  }
  function modelName(value) {
    return text(value, text(value && value.id, text(value && value.model, '未提供')));
  }
  function humanItem(value) {
    if (typeof value === 'string') return value;
    if (value && typeof value === 'object') return text(value.text, text(value.description, text(value.question, text(value.summary))));
    return '';
  }
  function renderList(selector, values, empty) {
    const container = $(selector);
    const items = list(values).map(humanItem).filter(Boolean);
    container.replaceChildren(...(items.length ? items : [empty]).map(value => element('li', '', value)));
  }
  function originLabel(value) {
    const names = {human_baseline: '人工历史基线', history: '历史资料', research: '本轮研究', reviewed_research: '本轮已审阅研究'};
    return names[value] || text(value, '来源身份未提供');
  }
  function topicLabel(value) { return ({'agent-memory': 'Agent Memory', 'agent-rl': 'Agent RL'})[value] || text(value, '研究选题'); }
  function coverageLabel(value) {
    const names = {abstract: '仅论文摘要', abstract_only: '仅论文摘要', excerpt: '仅博客节选', excerpt_only: '仅博客节选', full_text: '全文', human_baseline: '人工历史笔记', historical_note: '人工历史笔记'};
    return names[value] || text(value, '阅读范围未提供');
  }
  function evidenceDetails(evidence, compact = false) {
    return list(evidence).map((item, index) => {
      const details = element('details', 'source');
      const summary = element('summary');
      const name = element('div');
      name.append(element('div', 'ref-name', text(item.title, '未命名证据')),
        element('div', 'ref-note', `${coverageLabel(item.coverage)} · ${originLabel(item.origin)}`));
      summary.append(element('span', 'ref-id', text(item.id, `E${index + 1}`)), name);
      const body = element('div', 'source-body');
      const content = Array.isArray(item.summary) ? item.summary.map(humanItem).filter(Boolean).join('\n') : text(item.summary, text(item.text));
      body.append(element('p', '', content || '此证据未提供摘要，请保留其阅读范围。'));
      const sourceUrls = list(item.source_urls).filter(value => typeof value === 'string');
      if (sourceUrls.length) body.append(element('p', 'source-path', `原文来源：${sourceUrls.join('\n')}`));
      if (item.path) {
        body.append(element('p', 'source-path', `资料：${text(item.path)}`));
        const readButton = element('button', 'text-button', '查看已入库笔记');
        readButton.type = 'button';
        readButton.addEventListener('click', () => openDocument(item.path));
        body.append(readButton);
      }
      details.append(summary, body);
      if (!compact && index === 0) details.open = true;
      return details;
    });
  }
  async function openDocument(path) {
    if (state.busy || typeof path !== 'string') return;
    const dialog = $('#document-dialog');
    setText('#document-path', path);
    setText('#document-content', '正在读取笔记…');
    message('#document-error', '');
    dialog.showModal();
    try {
      const data = await api(`/api/document?path=${encodeURIComponent(path)}`);
      if (dialog.open && $('#document-path').textContent === path) {
        setText('#document-content', text(data.content, text(data.text, '此笔记没有可显示的正文。')));
      }
    } catch (error) {
      if (dialog.open && $('#document-path').textContent === path) {
        setText('#document-content', '');
        message('#document-error', error.message);
      }
    }
  }

  async function api(path, body) {
    const options = {method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
      cache: 'no-store', headers: {'Accept': 'application/json'}};
    if (body !== undefined) {
      if (!state.session || !state.session.csrf_token) throw new Error('本地会话尚未就绪，请刷新页面后重试。');
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-ResearchDesk-CSRF'] = state.session.csrf_token;
      options.body = JSON.stringify(body);
    }
    let response;
    try { response = await fetch(path, options); }
    catch (_) { throw new Error('无法连接本地工作台。请确认页面服务仍在运行，再刷新记录核对结果。'); }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error('工作台未返回有效结果。请先刷新记录核对保存状态，不要重复确认。'); }
    if (!response.ok) {
      const error = new Error(text(data.error && data.error.message, '操作未完成，请刷新后重试。'));
      error.code = text(data.error && data.error.code);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function showScreen(name, focus = true) {
    if (!['topics', 'evidence', 'edit', 'review', 'records'].includes(name)) return;
    if (['evidence', 'edit'].includes(name) && !state.selected) name = 'topics';
    if (name === 'review' && !state.preview) name = 'edit';
    state.screen = name;
    document.querySelectorAll('[data-screen]').forEach(node => { node.hidden = node.dataset.screen !== name; });
    document.querySelectorAll('.nav').forEach(node => {
      const current = node.dataset.action === (name === 'records' ? 'records' : 'topics');
      if (current) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current');
    });
    if (focus) {
      const heading = $(`[data-screen="${name}"] h1`);
      if (heading) heading.focus({preventScroll: true});
      window.scrollTo({top: 0, behavior: 'instant'});
    }
  }
  function renderTopics() {
    const container = $('#topic-list');
    container.replaceChildren();
    setText('#topic-count', state.topicsAvailable ? state.topics.length : '—');
    $('#topics-empty').hidden = !state.topicsAvailable || state.topics.length > 0;
    if (!state.topicsAvailable) {
      container.append(element('p', 'notice quiet', '待确认选题暂时无法读取。若有待同步记录，请先在“确认记录”中重试同步，再刷新选题。'));
      return;
    }
    for (const topic of state.topics) {
      const card = element('article', 'card topic-card');
      const meta = element('div', 'meta');
      meta.append(element('span', 'tag', topicLabel(topic.topic)),
        element('span', '', topic.date ? displayDate(topic.date) : '已正式入库'),
        element('span', 'status', '待你确认'));
      const evidence = list(topic.evidence);
      const counts = element('div', 'evidence-count');
      counts.append(element('span', '', `${Number.isInteger(topic.evidence_count) ? topic.evidence_count : evidence.length} 份研究与历史证据`),
        element('span', '', '独立审阅后正式入库'),
        element('span', '', `${list(topic.evidence_gaps).length} 条证据边界 / 缺口`));
      const footer = element('div', 'card-footer');
      const button = element('button', 'primary', '查看选题与证据 →');
      button.type = 'button';
      button.addEventListener('click', () => openTopic(topic.id));
      footer.append(element('span', 'small', '按阅读范围使用证据，保留历史资料身份'), button);
      card.append(meta, element('h2', 'topic-title', text(topic.title, '未命名选题')),
        element('p', 'topic-description', text(topic.angle, '查看证据后，调整本次文章的写作角度。')), counts, footer);
      container.append(card);
    }
  }
  async function openTopic(id) {
    if (state.busy) return;
    state.selected = state.topics.find(topic => topic.id === id);
    if (!state.selected) { showGlobalError('这张选题已变化，请刷新待确认列表。'); return; }
    state.preview = null;
    $('#acknowledged').checked = false;
    let topic = state.selected;
    state.busy = true;
    $('#loading').hidden = false;
    setText('#loading', '正在核对选题与证据…');
    showGlobalError('');
    try {
      const expanded = await api('/api/preview', {topic_id: id, choices: {
        title: topic.title, angle: topic.angle, audience: topic.audience,
        target_words: Number.isInteger(topic.target_words) ? topic.target_words : state.session.config.words.default
      }});
      topic = {...topic, ...expanded};
      state.selected = topic;
    } catch (error) {
      state.selected = null;
      showGlobalError(error.message);
      return;
    } finally { state.busy = false; $('#loading').hidden = true; setText('#loading', '正在读取工作台…'); }
    const words = state.session.config.words;
    fields.title.value = text(topic.title);
    fields.angle.value = text(topic.angle);
    fields.audience.value = text(topic.audience);
    fields.target_words.value = String(words.default);
    setText('#evidence-title', topic.title);
    const details = evidenceDetails(topic.evidence);
    $('#evidence-list').replaceChildren(...(details.length ? details : [element('p', 'small', '尚未提供可展示的证据，请暂缓确认。')]));
    renderList('#evidence-questions', topic.key_questions, '此卡未列出具体问题，请在写作角度中明确范围。');
    renderList('#evidence-gaps', topic.evidence_gaps, '此卡未单列缺口；请继续按各资料实际阅读范围使用证据。');
    message('#edit-error', '');
    updateDraft();
    showScreen('evidence');
  }
  function updateDraft() {
    setText('#draft-title', fields.title.value || '填写文章标题');
    setText('#draft-audience', fields.audience.value || '填写目标读者');
    setText('#draft-angle', fields.angle.value || '填写写作角度');
  }
  function configureSession(session) {
    const words = session && session.config && session.config.words;
    if (!session.csrf_token || typeof session.writing_available !== 'boolean' || !words ||
        !Number.isInteger(words.min) || !Number.isInteger(words.max) || !Number.isInteger(words.default) ||
        words.min < 1 || words.max < words.min || words.default < words.min || words.default > words.max) {
      throw new Error('本地工作台配置未就绪，暂时无法保存确认。请检查页面服务配置后刷新。');
    }
    state.session = session;
    fields.target_words.min = String(words.min);
    fields.target_words.max = String(words.max);
    setText('#words-hint', `可选 ${words.min.toLocaleString('zh-CN')}–${words.max.toLocaleString('zh-CN')} 字；实际内容以证据范围为限。`);
  }
  async function load() {
    if (state.busy) return;
    state.busy = true;
    $('#loading').hidden = false;
    showGlobalError('');
    try {
      const [session, topics, records] = await Promise.allSettled([api('/api/session'), api('/api/topics'), api('/api/confirmations')]);
      const errors = [];
      if (session.status === 'fulfilled') configureSession(session.value);
      else { state.session = null; errors.push(session.reason.message); }
      state.topicsAvailable = topics.status === 'fulfilled';
      state.recordsAvailable = records.status === 'fulfilled';
      state.topics = state.topicsAvailable ? list(topics.value.topics).filter(topic => topic.status === 'proposed') : [];
      state.confirmations = state.recordsAvailable ? list(records.value.confirmations) : [];
      if (!state.topicsAvailable) errors.push(topics.reason.message);
      if (!state.recordsAvailable) errors.push(records.reason.message);
      state.selected = null;
      state.preview = null;
      $('#acknowledged').checked = false;
      renderTopics();
      renderRecords();
      showScreen(state.screen === 'records' ? 'records' : 'topics', false);
      if (errors.length) showGlobalError([...new Set(errors)].join(' '));
      announce('工作台已更新。');
    } catch (error) { showGlobalError(error.message); }
    finally { state.busy = false; $('#loading').hidden = true; }
  }
  async function reloadRecords() {
    if (state.busy) return;
    state.busy = true;
    showGlobalError('');
    try {
      const [records, topics] = await Promise.allSettled([api('/api/confirmations'), api('/api/topics')]);
      state.recordsAvailable = records.status === 'fulfilled';
      state.topicsAvailable = topics.status === 'fulfilled';
      state.confirmations = state.recordsAvailable ? list(records.value.confirmations) : [];
      state.topics = state.topicsAvailable ? list(topics.value.topics).filter(topic => topic.status === 'proposed') : [];
      renderRecords();
      renderTopics();
      const errors = [records, topics].filter(result => result.status === 'rejected').map(result => result.reason.message);
      if (errors.length) showGlobalError([...new Set(errors)].join(' '));
      announce('确认记录已更新。');
    } catch (error) { showGlobalError(error.message); }
    finally { state.busy = false; }
  }
  function writingSummary(preview) {
    const writing = preview.writing || state.session.config.writing || {};
    const models = writing.models || {};
    const budget = writing.budget || {};
    setText('#final-models', `生成模型：${modelName(models.writing)}；独立审阅模型：${modelName(models.review)}。`);
    const calls = Number.isInteger(budget.max_calls) ? `${budget.max_calls} 次` : '未提供';
    const stage = Number.isInteger(budget.max_calls_per_stage) ? `${budget.max_calls_per_stage} 次` : '未提供';
    const revisions = Number.isInteger(budget.max_revisions) ? `${budget.max_revisions} 次` : '未提供';
    setText('#final-budget', `本次最多 ${calls}会员请求；每阶段最多 ${stage}；每阶段最多修订 ${revisions}。实际执行仍需核对共享会员预算。`);
  }
  function updateExpiry() {
    const expires = state.preview ? Date.parse(state.preview.expires_at) : NaN;
    const remaining = expires - Date.now();
    const valid = Number.isFinite(remaining) && remaining > 0;
    if (state.preview) {
      setText('#preview-expiry', valid ? `预览将在 ${Math.ceil(remaining / 60000)} 分钟内到期` : '此预览已过期，请返回调整页重新预览。');
    }
    $('#confirm-button').disabled = state.busy || !valid || !$('#acknowledged').checked;
    return valid;
  }
  async function createPreview(event) {
    event.preventDefault();
    if (state.busy || !state.selected) return;
    if (!$('#edit-form').reportValidity()) return;
    const choices = {title: fields.title.value.trim(), angle: fields.angle.value.trim(),
      audience: fields.audience.value.trim(), target_words: Number(fields.target_words.value)};
    if (!choices.title || !choices.angle || !choices.audience) { message('#edit-error', '请填写文章标题、写作角度和目标读者。'); return; }
    state.busy = true;
    state.preview = null;
    $('#preview-button').disabled = true;
    setText('#preview-button', '正在固定预览…');
    message('#edit-error', '');
    try {
      const preview = await api('/api/preview', {topic_id: state.selected.id, choices});
      if (!preview.preview_id || !Number.isFinite(Date.parse(preview.expires_at))) throw new Error('预览信息不完整，请刷新后重新预览。');
      state.preview = preview;
      $('#acknowledged').checked = false;
      setText('#final-title', preview.title);
      setText('#final-audience', preview.audience);
      setText('#final-words', `约 ${Number(preview.target_words).toLocaleString('zh-CN')} 字`);
      setText('#final-angle', preview.angle);
      $('#final-evidence').replaceChildren(...evidenceDetails(preview.evidence, true));
      renderList('#final-gaps', preview.evidence_gaps, '未另列缺口；继续保留各项证据的阅读范围。');
      renderList('#final-questions', preview.key_questions, '以以上写作角度和证据范围为准。');
      writingSummary(preview);
      message('#review-error', '');
      showScreen('review');
      announce('已生成固定预览，请核对后手动勾选确认。');
    } catch (error) { message('#edit-error', error.message); }
    finally {
      state.busy = false;
      $('#preview-button').disabled = false;
      setText('#preview-button', '查看最终预览 →');
      updateExpiry();
    }
  }
  async function confirm() {
    if (state.busy || !state.preview || !$('#acknowledged').checked || !updateExpiry()) return;
    state.busy = true;
    $('#confirm-button').disabled = true;
    $('#acknowledged').disabled = true;
    setText('#confirm-button', '正在保存并同步…');
    message('#review-error', '');
    try {
      const result = await api('/api/confirm', {preview_id: state.preview.preview_id, acknowledged: true});
      const record = result.confirmation;
      if (!record || !record.id) throw new Error('未收到完整确认记录，请先刷新“确认记录”核对结果，不要重复确认。');
      const confirmedTopic = record.topic_id || state.preview.topic_id || (state.selected && state.selected.id);
      state.confirmations = [record, ...state.confirmations.filter(item => item.id !== record.id)];
      state.topics = state.topics.filter(topic => topic.id !== confirmedTopic);
      state.preview = null;
      $('#acknowledged').checked = false;
      renderTopics();
      renderRecords();
      message('#records-message', record.synced === false ? '确认已保存在本机，但同步尚未完成。不会启动写作；请保留记录并检查同步状态。' : '已保存写作确认。点击“开始测试写作”后才会派发大纲、初稿和候选稿任务；不会发布公众号。');
      showScreen('records');
      announce('已保存写作确认，尚未开始写作。');
    } catch (error) {
      // Never automatically retry a state change: the server may have persisted it.
      state.preview = null;
      $('#acknowledged').checked = false;
      message('#review-error', `${error.message} 请先打开“确认记录”并刷新核对结果；如未保存，再重新预览。`);
      setText('#preview-expiry', '请先核对保存结果，再重新预览。');
    } finally {
      state.busy = false;
      $('#acknowledged').disabled = false;
      setText('#confirm-button', '保存写作确认');
      $('#confirm-button').disabled = true;
    }
  }
  function recordStatus(record) {
    const names = {confirmed_waiting_writer: '已确认 · 等待开始写作', confirmed: '已确认 · 等待开始写作', revoked: '已撤回', invalidated: '已失效', sync_pending: '已保存 · 等待同步', pending_sync: '确认已保存 · 等待同步', revocation_pending_sync: '撤回已保存 · 等待同步'};
    if (record.synced === false && !['revoked', 'invalidated', 'revocation_pending_sync'].includes(record.status)) return names.pending_sync;
    if (['confirmed_waiting_writer', 'confirmed'].includes(record.status)) {
      const progress = record.writing || {};
      const states = {queued: '已派发 · 等待执行', dispatch_unknown: '派发状态待核对',
        in_progress: '测试写作进行中', paused: '测试写作已暂停', test_accepted: '三稿已通过审阅 · TEST',
        rejected: '独立审阅未通过', blocked: '证据不足 · 已停止', revision_required: '修订仍未通过',
        unknown_request: '请求结果未知 · 已停止', integrity_blocked: '记录待核对 · 已停止'};
      if (states[progress.status]) return states[progress.status];
    }
    return names[record.status] || '状态待核对';
  }
  function renderRecords() {
    const container = $('#record-list');
    container.replaceChildren();
    setText('#record-count', state.recordsAvailable ? state.confirmations.length : '—');
    $('#records-empty').hidden = !state.recordsAvailable || state.confirmations.length > 0;
    if (!state.recordsAvailable) {
      container.append(element('p', 'notice quiet', '确认记录暂时无法读取，当前无法确定保存状态。请保留现场并刷新，不要重复确认。'));
      return;
    }
    for (const record of state.confirmations) {
      const card = element('article', 'card record-card');
      const meta = element('div', 'meta');
      meta.append(element('span', 'tag', topicLabel(record.topic)),
        element('span', `status${['revoked', 'invalidated'].includes(record.status) ? ' revoked' : ''}`, recordStatus(record)));
      card.append(meta, element('h2', '', text(record.title, '写作确认')));
      const choices = record.choices || record;
      if (choices.angle) card.append(element('p', 'topic-description', choices.angle));
      const details = element('div', 'record-details');
      const progress = record.writing || {};
      details.append(element('span', '', `确认时间：${displayDate(record.created_at)}`),
        element('span', '', `Writing：${Number.isInteger(progress.completed_calls) ? progress.completed_calls : 0} 次已完成 / ${Number.isInteger(progress.reserved_calls) ? progress.reserved_calls : 0} 次已预留`),
        element('span', '', '公众号：未授权发布'));
      if (choices.target_words) details.append(element('span', '', `目标篇幅：约 ${Number(choices.target_words).toLocaleString('zh-CN')} 字`));
      card.append(details, element('p', 'record-id', `确认 ID：${text(record.id)}`));
      if (record.reason) card.append(element('p', 'notice warm', record.reason));
      if (progress.reason) card.append(element('p', 'notice warm', progress.reason));
      if (record.writing_started) {
        const stages = element('div', 'phases');
        for (const [key, label] of [['outline', '大纲'], ['draft', '初稿'], ['candidate', '候选稿']]) {
          stages.append(element('span', '', `${label}${progress.stages && progress.stages[key] ? ' ✓ 已审阅' : ' · 待完成'}`));
        }
        card.append(stages);
      }
      if (list(progress.documents).length) {
        const documents = element('div', 'record-buttons');
        for (const item of progress.documents) {
          const button = element('button', 'secondary compact', text(item.label, '查看稿件'));
          button.type = 'button';
          button.addEventListener('click', () => openDocument(item.path));
          documents.append(button);
        }
        card.append(documents, element('p', 'small', '只读展示已校验稿件。全部保存在 test，尚未正式入库或发布。'));
      }
      const canRevoke = ['confirmed_waiting_writer', 'confirmed', 'sync_pending', 'pending_sync'].includes(record.status);
      const canSync = ['pending_sync', 'revocation_pending_sync', 'sync_pending'].includes(record.status) || record.synced === false;
      const canWrite = state.session && state.session.writing_available && record.synced &&
        ['confirmed_waiting_writer', 'confirmed'].includes(record.status) && ['not_started', 'paused'].includes(progress.status);
      if (canRevoke || canSync || canWrite) {
        const footer = element('div', 'card-footer');
        const buttons = element('div', 'record-buttons');
        if (canWrite) {
          const start = element('button', 'primary', record.writing_started ? '继续测试写作' : '开始测试写作');
          start.type = 'button';
          start.addEventListener('click', () => startWriting(record, start));
          buttons.append(start);
        }
        if (canSync) {
          const sync = element('button', 'primary', '重试同步');
          sync.type = 'button';
          sync.addEventListener('click', () => retrySync(record, sync));
          buttons.append(sync);
        }
        if (canRevoke) {
          const button = element('button', 'secondary', '撤回确认');
          button.type = 'button';
          button.addEventListener('click', () => openRevoke(record));
          buttons.append(button);
        }
        footer.append(element('span', 'small', canSync ? '本机记录已保留；同步完成前不会交给写作' : '每次派发最多新增 6 次会员请求；已完成结果会复用'), buttons);
        card.append(footer);
      }
      container.append(card);
    }
  }
  async function startWriting(record, button) {
    if (state.busy) return;
    state.busy = true;
    button.disabled = true;
    button.textContent = '正在派发…';
    showGlobalError('');
    try {
      const result = await api('/api/writing', {confirmation_id: record.id});
      if (!result.confirmation || result.confirmation.id !== record.id) throw new Error('未收到完整派发结果，请刷新记录或查看 GitHub 运行记录。');
      state.confirmations = state.confirmations.map(item => item.id === record.id ? result.confirmation : item);
      renderRecords();
      message('#records-message', '已派发测试写作。执行器将再次核对确认与证据，逐阶段生成并独立审阅；完成后刷新记录查看三稿。不会发布公众号。');
      announce('测试写作已派发。');
    } catch (error) {
      showGlobalError(`${error.message} 请先刷新核对，不要连续重复派发。`);
    } finally { state.busy = false; button.disabled = false; }
  }
  async function retrySync(record, button) {
    if (state.busy) return;
    state.busy = true;
    button.disabled = true;
    button.textContent = '正在同步…';
    showGlobalError('');
    try {
      const result = await api('/api/sync', {confirmation_id: record.id});
      if (!result.confirmation || !result.confirmation.id) throw new Error('未收到同步结果，请刷新记录核对状态。');
      const updated = result.confirmation;
      state.confirmations = state.confirmations.map(item => item.id === updated.id ? updated : item);
      renderRecords();
      message('#records-message', updated.synced ? '记录已同步。有效确认可以单独开始测试写作；同步本身不会启动模型。' : '记录仍待同步，现场已保留。请检查网络或仓库冲突后再重试，不要重复确认。');
      announce(updated.synced ? '记录已同步。' : '记录仍待同步。');
    } catch (error) { showGlobalError(error.message); }
    finally { state.busy = false; button.disabled = false; button.textContent = '重试同步'; }
  }
  function openRevoke(record) {
    if (state.busy) return;
    state.revokeId = record.id;
    setText('#revoke-title', record.title);
    $('#revoke-reason').value = '';
    message('#revoke-error', '');
    $('#revoke-dialog').showModal();
  }
  async function revoke(event) {
    event.preventDefault();
    if (state.busy || !state.revokeId) return;
    state.busy = true;
    $('#revoke-button').disabled = true;
    setText('#revoke-button', '正在保存撤回…');
    message('#revoke-error', '');
    try {
      const result = await api('/api/revoke', {confirmation_id: state.revokeId, reason: $('#revoke-reason').value.trim()});
      if (!result.confirmation || !result.confirmation.id) throw new Error('未收到完整撤回记录，请刷新确认记录核对结果。');
      const record = result.confirmation;
      state.confirmations = state.confirmations.map(item => item.id === record.id ? record : item);
      renderRecords();
      message('#records-message', record.synced === false ? '撤回已保存在本机，同步尚未完成。请保留记录并检查同步状态。' : '已撤回本次确认，原确认和研究资料已保留。');
      $('#revoke-dialog').close();
      state.revokeId = null;
      announce('已撤回写作确认。');
    } catch (error) {
      message('#revoke-error', `${error.message} 如保存结果不明确，请关闭此窗口并刷新确认记录核对。`);
    } finally {
      state.busy = false;
      $('#revoke-button').disabled = false;
      setText('#revoke-button', '确认撤回');
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-action]');
    if (!button || state.busy) return;
    switch (button.dataset.action) {
      case 'topics': showScreen('topics'); break;
      case 'records': showScreen('records'); break;
      case 'evidence': showScreen('evidence'); break;
      case 'edit':
        state.preview = null;
        $('#acknowledged').checked = false;
        showScreen('edit');
        break;
      case 'reload': load(); break;
      case 'reload-records': reloadRecords(); break;
      case 'cancel-revoke': $('#revoke-dialog').close(); state.revokeId = null; break;
      case 'close-document': $('#document-dialog').close(); break;
    }
  });
  Object.values(fields).forEach(field => field.addEventListener('input', updateDraft));
  $('#edit-form').addEventListener('submit', createPreview);
  $('#acknowledged').addEventListener('change', updateExpiry);
  $('#confirm-button').addEventListener('click', confirm);
  $('#revoke-form').addEventListener('submit', revoke);
  $('#revoke-dialog').addEventListener('cancel', event => {
    if (state.busy) event.preventDefault(); else state.revokeId = null;
  });
  setInterval(updateExpiry, 1000);
  load();
})();
