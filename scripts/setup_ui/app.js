'use strict';

(() => {
  const byId = (id) => document.getElementById(id);
  const buttons = new Map(Array.from(document.querySelectorAll('button[data-action]'),
    (button) => [button.dataset.action, button]));
  const labels = {
    ready: '已就绪', needs_login: '待授权', needs_repository: '待连接仓库',
    needs_workflow_scope: '待补充授权',
    idle: '待配置', running: '处理中', blocked: '需要处理', needs_setup: '待设置',
    not_ready: '待准备', unavailable: '暂不可用', failed: '需要处理', error: '需要处理',
    missing_tool: '待安装',
  };
  const actionLabels = {
    check: '重新检查工作台', chatgpt_login: '等待 ChatGPT 授权', github_login: '等待 GitHub 授权',
    github_workflow_auth: '等待 GitHub 补充授权',
    github_create: '创建私有 GitHub 仓库', create_schedule: '正在配置定时研究',
    obsidian_sync: '更新阅读库', obsidian_open: '打开 Vault 管理器',
    save_topics: '正在保存研究方向',
  };
  const problemStates = new Set(['blocked', 'failed', 'error']);
  const defaultSchedule = {weekdays: [2, 5], time: '03:00', timezone: 'Asia/Shanghai'};
  const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  const maxTopics = 8;
  const maxTopicLength = 80;
  const topicInput = byId('topic-input');
  const topicTags = byId('topic-tags');
  const scheduleEditor = byId('schedule-editor');
  const scheduleDays = Array.from(scheduleEditor.querySelectorAll('input[name="weekday"]'));
  const scheduleClock = byId('schedule-clock');
  const scheduleZone = byId('schedule-zone');
  const githubAuthorizationWindow = byId('github-auth-window');
  let snapshot = null;
  let loadingStatus = null;
  let requestedAction = null;
  let connectionIssue = '';
  let actionIssue = '';
  let savedTopics = null;
  let draftTopics = [];
  let topicsEdited = false;
  let topicEntryOpen = false;
  let pendingTopics = null;
  let scheduleEdited = false;
  let scheduleEditorOpen = false;
  let pendingSchedule = null;
  let previewKey = '';
  let previewTimer;
  let announcementFade;
  let chatgptAuthorizationTab = null;

  function setText(id, value) {
    const element = byId(id);
    if (element.textContent !== value) element.textContent = value;
  }

  function setVisible(id, visible) {
    byId(id).hidden = !visible;
  }

  function valueOf(value) {
    return typeof value === 'string' ? value.trim() : '';
  }

  function setButton(action, visible, label) {
    const button = buttons.get(action);
    button.hidden = !visible;
    if (label && button.textContent !== label) button.textContent = label;
  }

  function externalLink(id, href) {
    const element = byId(id);
    element.hidden = !href;
    if (href) element.href = href;
    else element.removeAttribute('href');
  }

  function httpsUrl(value, accepts) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password && !url.port && accepts(url)
        ? url.href : '';
    } catch {
      return '';
    }
  }

  function githubPage(value) {
    return httpsUrl(value, ({hostname, pathname}) => hostname === 'github.com' && !pathname.startsWith('/login'));
  }

  function githubRepositoryUrl(repository) {
    return /^[A-Za-z0-9][A-Za-z0-9-]{0,38}\/(?!\.{1,2}$)[A-Za-z0-9_.-]{1,100}$/.test(repository)
      ? `https://github.com/${repository}` : '';
  }

  function setSection(name, data, readyLabel) {
    if (!data) return;
    const badge = byId(`${name}-state`);
    const status = data.state;
    badge.dataset.state = Object.hasOwn(labels, status) ? status : '';
    setText(`${name}-state`, (status === 'ready' && readyLabel) || labels[badge.dataset.state] || '等待检查');
    if (valueOf(data.message)) setText(`${name}-message`, data.message);
  }

  function isBusy() {
    return Boolean(requestedAction || snapshot?.operation);
  }

  function topicsFromSetup(setup) {
    if (Array.isArray(setup.topics)) {
      return setup.topics.filter((topic) => valueOf(topic?.id) && valueOf(topic?.name))
        .map(({id, name}) => ({id, name}));
    }
    const id = valueOf(setup.topic);
    return id ? [{id, name: id === 'agent_memory' ? 'Agent Memory' : id}] : null;
  }

  function normalizeTopicName(value) {
    return valueOf(value).normalize('NFKC').replace(/\s+/gu, ' ').trim();
  }

  function sameTopics(actual, expected, saved = false) {
    return actual.length === expected.length && actual.every(({id, name}, index) => {
      const other = expected[index];
      const sameName = saved ? normalizeTopicName(name).toLowerCase() === normalizeTopicName(other.name).toLowerCase()
        : name === other.name;
      return sameName && (id === other.id || (saved && !other.id));
    });
  }

  function topicError(message) {
    setText('topic-error', message);
    setVisible('topic-error', Boolean(message));
  }

  function renderTopicTags() {
    topicTags.replaceChildren(...draftTopics.map(({name}, index) => {
      const tag = document.createElement('li');
      tag.className = 'topic-tag';
      tag.textContent = name;
      const remove = document.createElement('button');
      remove.className = 'topic-remove';
      remove.type = 'button';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `移除研究方向 ${name}`);
      remove.addEventListener('click', () => {
        draftTopics.splice(index, 1);
        topicsEdited = true;
        topicError(draftTopics.length ? '' : '请至少添加一个研究方向。');
        renderTopicTags();
        renderTopicControls();
        const next = topicTags.children[Math.min(index, draftTopics.length - 1)];
        (next?.firstElementChild || (topicEntryOpen ? topicInput : byId('topic-toggle'))).focus();
      });
      tag.append(remove);
      return tag;
    }));
  }

  function reconcileTopics(setup) {
    const actual = topicsFromSetup(setup);
    if (!actual) return;
    savedTopics = actual;
    if (pendingTopics && requestedAction !== 'save_topics' && !snapshot.operation) {
      const notice = snapshot.notice;
      const confirmed = notice?.action === 'save_topics' && notice.state === 'ready';
      const failed = problemStates.has(notice?.state) && (!notice.action || notice.action === 'save_topics');
      if (!failed && (confirmed || sameTopics(actual, pendingTopics, true))) {
        topicsEdited = false;
        topicEntryOpen = Boolean(valueOf(topicInput.value));
      }
      pendingTopics = null;
    }
    if (!topicsEdited && !sameTopics(actual, draftTopics)) {
      draftTopics = actual.slice();
      renderTopicTags();
    }
  }

  function renderTopicControls() {
    const available = savedTopics !== null;
    const saving = Boolean(pendingTopics) || requestedAction === 'save_topics' || snapshot?.operation?.action === 'save_topics';
    const hasInput = topicEntryOpen && Boolean(valueOf(topicInput.value));
    const changed = available && !sameTopics(savedTopics, draftTopics);
    setVisible('topic-editor', available);
    setVisible('topic-entry', topicEntryOpen);
    setVisible('topic-save', available && (changed || hasInput));
    const toggle = byId('topic-toggle');
    toggle.setAttribute('aria-expanded', String(topicEntryOpen));
    setText('topic-toggle', topicEntryOpen ? '收起' : '添加方向');
    toggle.disabled = saving;
    byId('topic-editor').setAttribute('aria-busy', String(saving));
    topicInput.disabled = saving;
    byId('topic-add').disabled = saving || !hasInput;
    byId('topic-save').disabled = !snapshot?.csrf || isBusy() || saving
      || !(hasInput || (draftTopics.length > 0 && changed));
    for (const tag of topicTags.children) tag.firstElementChild.disabled = saving;
  }

  function addTopic() {
    const name = normalizeTopicName(topicInput.value);
    if (!name) return false;
    if (Array.from(name).length > maxTopicLength || !/[\p{L}\p{N}]/u.test(name) || /\p{C}/u.test(topicInput.value)) {
      topicError('研究方向名称须包含文字或数字，长度为 1 至 80 字符。');
      return false;
    }
    if (draftTopics.some((topic) => normalizeTopicName(topic.name).toLowerCase() === name.toLowerCase())) {
      topicError('这个研究方向已经添加。');
      return false;
    }
    if (draftTopics.length >= maxTopics) {
      topicError('最多可添加 8 个研究方向。');
      return false;
    }
    draftTopics.push({name});
    topicsEdited = true;
    topicInput.value = '';
    topicError('');
    renderTopicTags();
    renderTopicControls();
    return true;
  }

  function scheduleFromSetup(setup) {
    const weekly = setup.weekly;
    if (!Array.isArray(weekly?.weekdays) || !weekly.weekdays.length || !weekly.time || !weekly.timezone) {
      return defaultSchedule;
    }
    return {weekdays: weekly.weekdays.slice().sort((a, b) => a - b), time: weekly.time, timezone: weekly.timezone};
  }

  function scheduleDraft() {
    return {
      weekdays: scheduleDays.filter(({checked}) => checked).map(({value}) => Number(value)),
      time: scheduleClock.value,
      timezone: valueOf(scheduleZone.value),
    };
  }

  function sameSchedule(first, second) {
    return first.time === second.time && first.timezone === second.timezone
      && first.weekdays.join(',') === second.weekdays.join(',');
  }

  function scheduleError(message) {
    setText('schedule-error', message);
    setVisible('schedule-error', Boolean(message));
  }

  function describeSchedule({weekdays, time, timezone}) {
    const days = weekdays.map((weekday) => weekdayNames[weekday - 1]).join('、');
    const zone = timezone === 'Asia/Shanghai' ? '北京时间' : timezone;
    return `每${days} ${time}（${zone}）`;
  }

  function reconcileSchedule(actual, deployed) {
    if (pendingSchedule && requestedAction !== 'create_schedule' && !snapshot.operation) {
      const confirmed = snapshot.notice?.action === 'create_schedule' && snapshot.notice.state === 'ready';
      if (deployed && (confirmed || sameSchedule(actual, pendingSchedule))) {
        scheduleEdited = false;
        scheduleEditorOpen = false;
        scheduleError('');
      }
      pendingSchedule = null;
    }
    if (!scheduleEdited && !sameSchedule(actual, scheduleDraft())) {
      for (const input of scheduleDays) input.checked = actual.weekdays.includes(Number(input.value));
      scheduleClock.value = actual.time;
      scheduleZone.value = actual.timezone;
    }
  }

  function renderScheduleControls() {
    const {setup = {}, chatgpt = {}, github = {}, deployment = {}, operation} = snapshot || {};
    const actual = scheduleFromSetup(setup);
    const ready = deployment.state === 'ready';
    const accountsReady = chatgpt.state === 'ready' && github.state === 'ready';
    const workflowReady = github.workflow_scope === true;
    const canCreate = setup.state === 'ready' && accountsReady && workflowReady;
    const saving = Boolean(pendingSchedule) || requestedAction === 'create_schedule' || operation?.action === 'create_schedule';
    const editing = !ready || scheduleEditorOpen;
    setVisible('schedule-editor', editing);
    setVisible('schedule-edit', ready && !editing);
    setVisible('schedule-cancel', ready && editing);
    byId('schedule-edit').disabled = isBusy();
    byId('schedule-edit').setAttribute('aria-expanded', String(editing));
    byId('schedule-cancel').disabled = saving;
    for (const input of [...scheduleDays, scheduleClock, scheduleZone]) input.disabled = saving;
    scheduleEditor.setAttribute('aria-busy', String(saving));
    setText('schedule-submit', ready || setup.automation ? '保存修改' : '创建定时研究');
    byId('schedule-submit').disabled = !snapshot?.csrf || !canCreate || isBusy() || saving
      || deployment.state === 'running' || (ready && sameSchedule(actual, scheduleDraft()));
    setVisible('schedule-connection-hint', !accountsReady || !workflowReady);
    let connectionHint = '连接 ChatGPT 和 GitHub 后可创建。';
    if (github.workflow_scope === false) {
      connectionHint = '请在「连接账号」中补充 GitHub 工作流授权。';
    } else if (accountsReady && !workflowReady) {
      connectionHint = '请确认 GitHub 工作流权限后再创建日程。';
    }
    setText('schedule-connection-hint', connectionHint);
    renderSchedulePreview(editing && Boolean(snapshot));
  }

  function renderSchedulePreview(visible) {
    const weekly = scheduleDraft();
    const error = visible ? validateSchedule(weekly) : '';
    if (!visible || error) {
      window.clearTimeout(previewTimer);
      previewKey = '';
      setText('schedule-preview-summary', error);
      setText('schedule-preview-next', '');
      return;
    }
    const params = new URLSearchParams({
      weekdays: weekly.weekdays.join(','), time: weekly.time, timezone: weekly.timezone,
    });
    const key = `${params}/${Math.floor(Date.now() / 60000)}`;
    if (key === previewKey) return;
    previewKey = key;
    window.clearTimeout(previewTimer);
    setText('schedule-preview-summary', describeSchedule(weekly));
    setText('schedule-preview-next', '正在计算下一次运行时间…');
    previewTimer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/schedule-preview?${params}`, {cache: 'no-store'});
        const result = await response.json();
        if (key !== previewKey) return;
        if (response.status === 400 && valueOf(result.error)) {
          setText('schedule-preview-next', result.error);
          return;
        }
        if (!response.ok) throw new Error('schedule preview');
        const date = new Intl.DateTimeFormat('zh-CN', {
          timeZone: weekly.timezone, month: 'numeric', day: 'numeric', weekday: 'short',
          hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
        }).format(new Date(result.next_run));
        setText('schedule-preview-next', `下一次预计运行：${date}`);
      } catch {
        if (key === previewKey) setText('schedule-preview-next', '暂时无法预览下一次运行时间。');
      }
    }, 180);
  }

  function validateSchedule({weekdays, time, timezone}) {
    if (!weekdays.length) return '至少选择一个运行日。';
    if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(time)) return '请输入有效的时间（HH:MM）。';
    try {
      if (!/^[A-Za-z][A-Za-z0-9_.+-]*(?:\/[A-Za-z0-9_.+-]+)*$/.test(timezone)) throw new RangeError();
      new Intl.DateTimeFormat('zh-CN', {timeZone: timezone});
    } catch {
      return '请选择或输入有效的 IANA 时区，例如 Asia/Shanghai。';
    }
    return '';
  }

  function populateTimezones() {
    const common = ['Asia/Shanghai', 'UTC', 'Asia/Hong_Kong', 'Asia/Singapore', 'Asia/Tokyo',
      'Europe/London', 'Europe/Paris', 'America/New_York', 'America/Los_Angeles'];
    const supported = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];
    for (const timezone of new Set([...common, ...supported])) {
      const option = document.createElement('option');
      option.value = timezone;
      byId('schedule-zones').append(option);
    }
  }

  function takeChatgptAuthorizationTab() {
    const tab = chatgptAuthorizationTab;
    chatgptAuthorizationTab = null;
    try {
      return tab && !tab.closed && tab.location.href === 'about:blank' ? tab : null;
    } catch {
      return null;
    }
  }

  function renderAccounts(chatgpt, github, operation) {
    const chatgptRunning = operation?.action === 'chatgpt_login' ? operation : null;
    const chatgptLink = httpsUrl(chatgptRunning?.url || chatgpt.url, ({hostname}) => (
      hostname === 'chatgpt.com' || hostname === 'openai.com' || hostname.endsWith('.openai.com')
    ));
    if (chatgptAuthorizationTab && chatgptRunning?.url && chatgptLink) {
      takeChatgptAuthorizationTab()?.location.replace(chatgptLink);
    }
    const chatgptLogin = ['needs_login', 'not_ready', 'blocked', 'failed', 'error'].includes(chatgpt.state);
    setButton('chatgpt_login', chatgptLogin);
    externalLink('chatgpt-auth-url', chatgptLink);
    setVisible('chatgpt-actions', chatgptLogin || chatgptLink);

    const repo = valueOf(github.repository);
    const repositoryUrl = githubRepositoryUrl(repo);
    setText('github-repository', repo);
    externalLink('github-repository', repositoryUrl);
    setVisible('github-repository-row', Boolean(repo && repositoryUrl));
    const githubRunning = ['github_login', 'github_workflow_auth', 'github_create'].includes(operation?.action)
      ? operation : null;
    const code = [githubRunning?.user_code, githubRunning?.device_code, githubRunning?.code]
      .find((item) => /^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(valueOf(item)));
    setText('github-device-code', valueOf(code));
    setVisible('github-device', Boolean(code));

    const githubLogin = github.state === 'needs_login' || github.code === 'github_login_required';
    const needsWorkflowScope = !githubLogin && github.workflow_scope === false;
    const scopeMessage = valueOf(github.workflow_scope_message);
    const githubCreate = github.can_create === true && (github.state !== 'ready' || github.private === false);
    const toolUrl = httpsUrl(github.url, ({hostname}) => hostname === 'cli.github.com' || hostname === 'git-scm.com');
    const fixUrl = github.state === 'missing_tool' ? toolUrl
      : problemStates.has(github.state) ? githubPage(github.url) : '';
    const showLogin = githubLogin && !code && githubRunning?.action !== 'github_create';
    const showWorkflowAuth = needsWorkflowScope && !code;
    const showCreate = githubCreate && github.workflow_scope === true && !githubRunning;
    setButton('github_login', showLogin, githubRunning ? '正在获取设备码…' : '登录 GitHub');
    setButton('github_workflow_auth', showWorkflowAuth,
      githubRunning?.action === 'github_workflow_auth' ? '正在获取设备码…' : '补充授权');
    setButton('github_create', showCreate);
    setText('github-fix-link', toolUrl ? '查看安装说明 ↗' : '打开 GitHub 检查 ↗');
    externalLink('github-fix-link', fixUrl);
    setText('github-workflow-detail', scopeMessage || '创建或修改定时研究需要 GitHub 工作流权限（workflow）。');
    setVisible('github-workflow-detail', !githubLogin && (needsWorkflowScope || scopeMessage));
    setVisible('github-create-detail', githubCreate && github.workflow_scope === true);
    setVisible('github-connect-detail', github.state === 'needs_repository' && !githubCreate);
    setVisible('github-actions', showLogin || showWorkflowAuth || showCreate || fixUrl);
    byId('account-cards').classList.toggle('is-compact', chatgpt.state === 'ready' && github.state === 'ready'
      && github.workflow_scope === true && !chatgptLink && !code && !showLogin && !githubCreate && !fixUrl);
    return repositoryUrl;
  }

  function renderDeployment(setup, github, deployment, repositoryUrl) {
    const deployed = deployment.state === 'ready';
    const actual = scheduleFromSetup(setup);
    reconcileSchedule(actual, deployed);
    setSection('deployment', deployment, '已启用');
    setVisible('deployment-message', !deployed && (deployment.state !== 'needs_setup' || setup.automation));
    setVisible('schedule-current', deployed);
    setText('schedule-time', describeSchedule(actual));

    const actionsUrl = repositoryUrl ? `${repositoryUrl}/actions` : '';
    const failed = problemStates.has(deployment.state);
    const deploymentUrl = deployed && actionsUrl ? `${actionsUrl}/workflows/researchdesk-manual.yml`
      : failed ? actionsUrl : '';
    const diagnosticUrl = failed && repositoryUrl ? httpsUrl(deployment.url, ({hostname, pathname}) => {
      const repoPath = new URL(repositoryUrl).pathname.toLowerCase();
      const path = pathname.toLowerCase();
      return hostname === 'github.com' && path.startsWith(`${repoPath}/`)
        && /^\/(?:settings(?:\/actions|\/branches)?|tree\/main|actions\/(?:runs\/\d+|workflows\/[a-z0-9_.-]+))\/?$/
          .test(path.slice(repoPath.length));
    }) : '';
    setVisible('public-repository-notice', github.private === false);
    setText('deployment-url', deployed ? 'GitHub Action' : '检查 GitHub Actions ↗');
    externalLink('deployment-url', deploymentUrl);
    externalLink('deployment-diagnostic-url', diagnosticUrl);
    externalLink('github-actions-guide-link', actionsUrl);
    setVisible('schedule-result', deployed || Boolean(deploymentUrl));
    setVisible('deployment-actions', deployed || Boolean(deploymentUrl));
  }

  function renderObsidian(obsidian, github) {
    const path = typeof obsidian.path === 'string' ? obsidian.path : '';
    const ready = obsidian.state === 'ready';
    const canChoosePath = obsidian.can_choose_path === true;
    const canSync = github.state === 'ready' && obsidian.can_sync !== false;
    const canOpen = obsidian.can_open === true || (ready && obsidian.can_open !== false && obsidian.installed !== false);
    const showDownload = obsidian.installed === false;
    setSection('obsidian', obsidian, '阅读库就绪');
    setText('obsidian-path', path);
    setVisible('obsidian-path-row', Boolean(path));
    setButton('obsidian_choose_path', canChoosePath);
    setVisible('obsidian-path-hint', canChoosePath && Boolean(path));
    setButton('obsidian_sync', canSync, ready ? '从 GitHub 更新资料' : '准备阅读库');
    setButton('obsidian_open', canOpen);
    setVisible('obsidian-download', showDownload);
    setVisible('obsidian-first-open', ready && Boolean(path));
    setVisible('obsidian-actions', canSync || canOpen || showDownload);
  }

  function render() {
    if (chatgptAuthorizationTab && requestedAction !== 'chatgpt_login'
        && (snapshot || actionIssue) && snapshot?.operation?.action !== 'chatgpt_login') {
      takeChatgptAuthorizationTab()?.close();
    }
    const issue = connectionIssue || actionIssue;
    setText('connection-error', issue);
    setVisible('connection-error', Boolean(issue));
    const notice = snapshot?.notice;
    if (notice?.state === 'ready' && notice.attempt) {
      githubAuthorizationWindow.contentWindow?.finishGitHubAuthorization?.(notice.attempt);
    }
    const scheduleReady = notice?.action === 'create_schedule' && notice.state === 'ready'
      && snapshot?.deployment?.state === 'ready';
    const showNotice = Boolean(valueOf(notice?.message)) && !isBusy() && !scheduleReady;
    setText('result-notice', showNotice ? notice.message : '');
    setVisible('result-notice', showNotice);
    byId('result-notice').classList.toggle('error', problemStates.has(notice?.state));
    if (snapshot) {
      const {setup = {}, chatgpt = {}, github = {}, deployment = {}, obsidian = {}, operation} = snapshot;
      setSection('setup', setup);
      setSection('chatgpt', chatgpt, '已授权');
      const githubDisplay = github.state === 'ready' && github.workflow_scope === false
        ? {...github, state: 'needs_workflow_scope'} : github;
      setSection('github', githubDisplay, '已连接');
      reconcileTopics(setup);
      const repositoryUrl = renderAccounts(chatgpt, github, operation);
      renderDeployment(setup, github, deployment, repositoryUrl);
      renderObsidian(obsidian, github);
    }
    const activeAction = snapshot?.operation?.action || requestedAction;
    const activeMessage = valueOf(snapshot?.operation?.message) || actionLabels[activeAction] || '正在处理当前步骤…';
    setText('operation-message', activeMessage);
    setVisible('operation', isBusy() && activeAction !== 'obsidian_choose_path');
    for (const [action, button] of buttons) {
      button.disabled = isBusy() || (!snapshot?.csrf && action !== 'check')
        || (action === 'github_workflow_auth' && snapshot?.github?.can_authorize_workflow === false);
    }
    renderTopicControls();
    renderScheduleControls();
  }

  async function refresh() {
    if (loadingStatus) return loadingStatus;
    loadingStatus = (async () => {
      try {
        const response = await fetch('/api/status', {cache: 'no-store', headers: {Accept: 'application/json'}});
        if (!response.ok) throw new Error('status');
        const data = await response.json();
        if (!data || !valueOf(data.csrf) || !data.setup) throw new Error('status payload');
        snapshot = data;
        connectionIssue = '';
      } catch {
        connectionIssue = '暂时无法读取本地工作台。确认启动命令仍在运行，再点「重新检查」。';
        snapshot = null;
      } finally {
        loadingStatus = null;
        render();
      }
    })();
    return loadingStatus;
  }

  async function runAction(action, fields = {}) {
    if ((!buttons.has(action) && !['save_topics', 'create_schedule'].includes(action)) || isBusy()) return;
    actionIssue = '';
    if (!snapshot?.csrf) {
      await refresh();
      return;
    }
    if (action === 'chatgpt_login') {
      chatgptAuthorizationTab = window.open('about:blank', '_blank');
      if (chatgptAuthorizationTab) {
        chatgptAuthorizationTab.opener = null;
        chatgptAuthorizationTab.document.title = 'ResearchDesk · ChatGPT 授权';
        chatgptAuthorizationTab.document.body.textContent = '正在准备 ChatGPT 授权页面…';
      }
    }
    requestedAction = action;
    render();
    try {
      const response = await fetch('/api/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-ResearchDesk-CSRF': snapshot.csrf},
        body: JSON.stringify({action, ...fields}),
      });
      if (response.ok) {
        if (action === 'save_topics') pendingTopics = fields.topics;
        if (action === 'create_schedule') pendingSchedule = fields.schedule;
      } else if (response.status === 400 && ['save_topics', 'create_schedule'].includes(action)) {
        const result = await response.json().catch(() => null);
        const message = valueOf(result?.error);
        if (action === 'save_topics') topicError(message || '无法保存研究方向，请检查名称后重试。');
        else scheduleError(message || '无法保存日程，请检查星期、时间和时区后重试。');
      } else {
        actionIssue = '本地工作台暂时无法接受此操作。请查看当前状态，再重试。';
      }
    } catch {
      actionIssue = '暂时无法提交此操作。请确认本地设置服务仍在运行。';
    } finally {
      if (loadingStatus) await loadingStatus;
      await refresh();
      requestedAction = null;
      render();
    }
  }

  async function copyValue(id, copied) {
    const element = byId(id);
    const value = element.textContent;
    if (!value) return;
    let message = copied;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(element);
      selection?.removeAllRanges();
      selection?.addRange(range);
      message = '文字已选中，可用系统复制快捷键。';
    }
    announcementFade?.cancel();
    setText('announcement', message);
    const fade = byId('announcement').animate([{opacity: 1}, {opacity: 0}], {
      duration: 1000, easing: 'ease-in', fill: 'forwards',
    });
    announcementFade = fade;
    fade.onfinish = () => {
      if (announcementFade !== fade) return;
      setText('announcement', '');
      fade.cancel();
      announcementFade = null;
    };
  }

  for (const [action, button] of buttons) {
    button.addEventListener('click', () => runAction(action));
  }
  byId('topic-toggle').addEventListener('click', () => {
    topicEntryOpen = !topicEntryOpen;
    if (draftTopics.length) topicError('');
    renderTopicControls();
    if (topicEntryOpen) topicInput.focus();
  });
  topicInput.addEventListener('input', () => {
    topicError('');
    renderTopicControls();
  });
  topicInput.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    addTopic();
  });
  byId('topic-add').addEventListener('click', () => {
    addTopic();
    topicInput.focus();
  });
  byId('topic-editor').addEventListener('submit', (event) => {
    event.preventDefault();
    if (byId('topic-save').disabled) return;
    if (topicEntryOpen && valueOf(topicInput.value) && !addTopic()) return;
    if (draftTopics.length > 0) {
      topicError('');
      return runAction('save_topics', {topics: draftTopics.slice()});
    }
  });
  byId('schedule-edit').addEventListener('click', () => {
    scheduleEditorOpen = true;
    renderScheduleControls();
    scheduleDays[0].focus();
  });
  byId('schedule-cancel').addEventListener('click', () => {
    scheduleEditorOpen = false;
    scheduleEdited = false;
    scheduleError('');
    render();
    byId('schedule-edit').focus();
  });
  scheduleEditor.addEventListener('input', () => {
    scheduleEdited = true;
    scheduleError('');
    renderScheduleControls();
  });
  scheduleEditor.addEventListener('submit', (event) => {
    event.preventDefault();
    if (byId('schedule-submit').disabled) return;
    const weekly = scheduleDraft();
    const error = validateSchedule(weekly);
    scheduleError(error);
    if (!error) return runAction('create_schedule', {schedule: weekly});
  });
  byId('copy-and-authorize').addEventListener('click', () => {
    const attempt = snapshot?.operation?.attempt;
    if (!attempt || !byId('github-device-code').textContent) return;
    copyValue('github-device-code', '已复制 GitHub 设备码。');
    const opened = githubAuthorizationWindow.contentWindow?.openGitHubAuthorization?.(attempt);
    actionIssue = opened ? '' : '无法打开 GitHub 授权页。请允许向导打开新标签页后重试。';
    render();
  });
  byId('copy-path').addEventListener('click', () => copyValue('obsidian-path', '已复制阅读库路径。'));

  async function poll() {
    await refresh();
    const checking = snapshot?.operation?.action === 'check' || requestedAction === 'check';
    window.setTimeout(poll, checking ? 500 : isBusy() ? 1500 : 4000);
  }
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
  });
  populateTimezones();
  poll();
})();
