'use strict';

(() => {
  const byId = (id) => document.getElementById(id);
  const buttons = new Map(Array.from(document.querySelectorAll('button[data-action]'),
    (button) => [button.dataset.action, button]));
  const labels = {
    ready: '已就绪', needs_login: '待授权', needs_repository: '待连接仓库',
    idle: '待配置', running: '处理中', blocked: '需要处理', needs_setup: '待设置',
    not_ready: '待准备', unavailable: '暂不可用', failed: '需要处理', error: '需要处理',
    missing_tool: '待安装',
  };
  const actionLabels = {
    check: '重新检查工作台', chatgpt_login: '等待 ChatGPT 授权', github_login: '等待 GitHub 授权',
    github_create: '创建私有 GitHub 仓库', deploy: '配置定时研究',
    obsidian_sync: '更新阅读库', obsidian_open: '打开 Vault 管理器',
    confirmation_open: '打开选题确认页', save_topics: '正在保存研究方向',
  };
  const problemStates = new Set(['blocked', 'failed', 'error']);
  const defaultSchedule = '每周二、周五 03:00 北京时间';
  const githubDeviceUrl = 'https://github.com/login/device';
  const maxTopics = 8;
  const maxTopicLength = 80;
  const topicInput = byId('topic-input');
  const topicTags = byId('topic-tags');
  let snapshot = null;
  let loadingStatus = null;
  let requestedAction = null;
  let connectionIssue = '';
  let actionIssue = '';
  let savedTopics = null;
  let draftTopics = [];
  let topicsEdited = false;
  let pendingTopics = null;

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
        topicError('');
        renderTopicTags();
        renderTopicControls();
        const next = topicTags.children[Math.min(index, draftTopics.length - 1)];
        (next?.firstElementChild || topicInput).focus();
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
      if (!failed && (confirmed || sameTopics(actual, pendingTopics, true))) topicsEdited = false;
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
    const hasInput = Boolean(valueOf(topicInput.value));
    const changed = available && !sameTopics(savedTopics, draftTopics);
    setVisible('topic-editor', available);
    setVisible('topic-save', available);
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

  function renderAccounts(chatgpt, github, operation) {
    const chatgptRunning = operation?.action === 'chatgpt_login' ? operation : null;
    const chatgptLink = httpsUrl(chatgptRunning?.url || chatgpt.url, ({hostname}) => (
      hostname === 'chatgpt.com' || hostname === 'openai.com' || hostname.endsWith('.openai.com')
    ));
    const chatgptLogin = ['needs_login', 'not_ready', 'blocked', 'failed', 'error'].includes(chatgpt.state);
    setButton('chatgpt_login', chatgptLogin);
    externalLink('chatgpt-auth-url', chatgptLink);
    setVisible('chatgpt-actions', chatgptLogin || chatgptLink);

    const repo = valueOf(github.repository);
    const repositoryUrl = /^[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repo)
      ? `https://github.com/${repo}` : githubPage(github.url);
    setText('github-repository', repo);
    externalLink('github-repository', repositoryUrl);
    setVisible('github-repository-row', Boolean(repo && repositoryUrl));
    const githubRunning = ['github_login', 'github_create'].includes(operation?.action) ? operation : null;
    const code = [githubRunning?.user_code, githubRunning?.device_code, githubRunning?.code]
      .find((item) => /^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(valueOf(item)));
    setText('github-device-code', valueOf(code));
    setVisible('github-device', Boolean(code));
    externalLink('github-auth-url', code ? githubDeviceUrl : '');

    const githubLogin = github.state === 'needs_login' || github.code === 'github_login_required';
    const githubCreate = github.can_create === true && (github.state !== 'ready' || github.private === false);
    const toolUrl = httpsUrl(github.url, ({hostname}) => hostname === 'cli.github.com' || hostname === 'git-scm.com');
    const fixUrl = github.state === 'missing_tool' ? toolUrl
      : problemStates.has(github.state) ? githubPage(github.url) : '';
    const showLogin = githubLogin && !code && githubRunning?.action !== 'github_create';
    const showCreate = githubCreate && !githubRunning;
    setButton('github_login', showLogin, githubRunning ? '正在获取设备码…' : '登录 GitHub');
    setButton('github_create', showCreate);
    setText('github-fix-link', toolUrl ? '查看安装说明 ↗' : '打开 GitHub 检查 ↗');
    externalLink('github-fix-link', fixUrl);
    setVisible('github-create-detail', githubCreate);
    setVisible('github-connect-detail', github.state === 'needs_repository' && !githubCreate);
    setVisible('github-actions', showLogin || showCreate || fixUrl);
    return repositoryUrl;
  }

  function renderDeployment(setup, chatgpt, github, deployment, repositoryUrl) {
    const deployed = deployment.state === 'ready';
    const enabled = deployed && setup.automation === true;
    setSection('deployment', deployment, enabled ? '已启用' : '已部署');
    setText('schedule-label', enabled ? '自动运行时间' : '计划运行时间');
    const schedule = valueOf(setup.schedule);
    setText('schedule-time', schedule && !/^[0-9* ,/-]+$/.test(schedule) ? schedule : defaultSchedule);

    const canDeploy = setup.state === 'ready' && chatgpt.state === 'ready' && github.state === 'ready'
      && !enabled && deployment.state !== 'running';
    const deploymentUrl = githubPage(deployment.url) || (repositoryUrl ? `${repositoryUrl}/actions` : '');
    const showDeploymentLink = deployed || problemStates.has(deployment.state);
    const canConfirm = deployed && deployment.can_confirm !== false;
    const isPublic = github.private === false;
    const deployLabel = isPublic ? '继续使用公开仓库'
      : problemStates.has(deployment.state) ? '重试部署' : '配置自动研究';
    setVisible('public-repository-notice', isPublic);
    setButton('deploy', canDeploy, deployLabel);
    setButton('confirmation_open', canConfirm);
    setText('deployment-url', deployed ? '查看 GitHub Actions ↗' : '检查 GitHub Actions ↗');
    externalLink('deployment-url', showDeploymentLink ? deploymentUrl : '');
    externalLink('github-actions-guide-link', deploymentUrl);
    setVisible('deployment-actions', canDeploy || canConfirm || (showDeploymentLink && deploymentUrl));
  }

  function renderObsidian(obsidian, github) {
    const path = valueOf(obsidian.path);
    const ready = obsidian.state === 'ready';
    const canSync = github.state === 'ready' && obsidian.can_sync !== false;
    const canOpen = obsidian.can_open === true || (ready && obsidian.can_open !== false && obsidian.installed !== false);
    const showDownload = obsidian.installed === false;
    setSection('obsidian', obsidian, '阅读库就绪');
    setText('obsidian-path', path);
    setVisible('obsidian-path-row', Boolean(path));
    setButton('obsidian_sync', canSync, ready ? '从 GitHub 更新资料' : '准备阅读库');
    setButton('obsidian_open', canOpen);
    setVisible('obsidian-download', showDownload);
    setVisible('obsidian-first-open', ready && Boolean(path));
    setVisible('obsidian-actions', canSync || canOpen || showDownload);
  }

  function render() {
    const issue = connectionIssue || actionIssue;
    setText('connection-error', issue);
    setVisible('connection-error', Boolean(issue));
    const notice = snapshot?.notice;
    const showNotice = Boolean(valueOf(notice?.message)) && !isBusy();
    setText('result-notice', showNotice ? notice.message : '');
    setVisible('result-notice', showNotice);
    byId('result-notice').classList.toggle('error', problemStates.has(notice?.state));
    if (snapshot) {
      const {setup = {}, chatgpt = {}, github = {}, deployment = {}, obsidian = {}, operation} = snapshot;
      setSection('setup', setup);
      setSection('chatgpt', chatgpt, '已授权');
      setSection('github', github, '已连接');
      reconcileTopics(setup);
      const repositoryUrl = renderAccounts(chatgpt, github, operation);
      renderDeployment(setup, chatgpt, github, deployment, repositoryUrl);
      renderObsidian(obsidian, github);
    }
    const activeAction = snapshot?.operation?.action || requestedAction;
    const activeMessage = valueOf(snapshot?.operation?.message) || actionLabels[activeAction] || '正在处理当前步骤…';
    setText('operation-message', activeMessage);
    setVisible('operation', isBusy());
    for (const [action, button] of buttons) {
      button.disabled = isBusy() || (!snapshot?.csrf && action !== 'check');
    }
    renderTopicControls();
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
    if ((!buttons.has(action) && action !== 'save_topics') || isBusy()) return;
    actionIssue = '';
    if (!snapshot?.csrf) {
      await refresh();
      return;
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
      } else if (action === 'save_topics' && response.status === 400) {
        const result = await response.json().catch(() => null);
        topicError(valueOf(result?.error) || '无法保存研究方向，请检查名称后重试。');
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
    setText('announcement', '');
    try {
      await navigator.clipboard.writeText(value);
      setText('announcement', copied);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(element);
      selection?.removeAllRanges();
      selection?.addRange(range);
      setText('announcement', '文字已选中，可用系统复制快捷键。');
    }
  }

  for (const [action, button] of buttons) {
    button.addEventListener('click', () => runAction(action));
  }
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
    if (valueOf(topicInput.value) && !addTopic()) return;
    if (draftTopics.length > 0) {
      topicError('');
      return runAction('save_topics', {topics: draftTopics.slice()});
    }
  });
  byId('copy-code').addEventListener('click', () => copyValue('github-device-code', '已复制 GitHub 设备码。'));
  byId('copy-path').addEventListener('click', () => copyValue('obsidian-path', '已复制阅读库路径。'));

  async function poll() {
    await refresh();
    window.setTimeout(poll, isBusy() ? 1500 : 4000);
  }
  poll();
})();
