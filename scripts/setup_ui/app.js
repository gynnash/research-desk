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
    confirmation_open: '打开选题确认页',
  };
  const problemStates = new Set(['blocked', 'failed', 'error']);
  const defaultSchedule = '每周二、周五 03:00 北京时间';
  let snapshot = null;
  let loadingStatus = null;
  let requestedAction = null;
  let connectionIssue = '';
  let actionIssue = '';

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

  function githubAuthUrl(value) {
    return httpsUrl(value, ({hostname, pathname}) => hostname === 'github.com'
      && (pathname === '/login/device' || pathname === '/login/oauth/authorize'));
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
    const code = [githubRunning?.user_code, githubRunning?.device_code, githubRunning?.code,
      github.user_code, github.device_code, github.code].find((item) => /^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(valueOf(item)));
    const authorizationUrl = [githubRunning?.verification_uri, githubRunning?.url,
      github.verification_uri, github.url].map(githubAuthUrl).find(Boolean);
    setText('github-device-code', valueOf(code));
    setVisible('github-device', Boolean(code));
    externalLink('github-auth-url', code ? authorizationUrl || 'https://github.com/login/device' : '');
    externalLink('github-auth-link', code ? '' : authorizationUrl);

    const githubLogin = github.state === 'needs_login' || github.code === 'github_login_required';
    const githubCreate = github.can_create === true && (github.state !== 'ready' || github.private === false);
    const toolUrl = httpsUrl(github.url, ({hostname}) => hostname === 'cli.github.com' || hostname === 'git-scm.com');
    const fixUrl = github.state === 'missing_tool' ? toolUrl
      : problemStates.has(github.state) ? githubPage(github.url) : '';
    setButton('github_login', githubLogin && !githubRunning);
    setButton('github_create', githubCreate);
    setText('github-fix-link', toolUrl ? '查看安装说明 ↗' : '打开 GitHub 检查 ↗');
    externalLink('github-fix-link', fixUrl);
    setVisible('github-create-detail', githubCreate);
    setVisible('github-connect-detail', github.state === 'needs_repository' && !githubCreate);
    setVisible('github-actions', (githubLogin && !githubRunning) || githubCreate || (!code && authorizationUrl) || fixUrl);
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
      const topic = valueOf(setup.topic);
      setText('topic-name', topic);
      setVisible('setup-topic', Boolean(topic));
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

  async function runAction(action) {
    if (!buttons.has(action) || isBusy()) return;
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
        body: JSON.stringify({action}),
      });
      if (!response.ok) actionIssue = '本地工作台暂时无法接受此操作。请查看当前状态，再重试。';
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
  byId('copy-code').addEventListener('click', () => copyValue('github-device-code', '已复制 GitHub 设备码。'));
  byId('copy-path').addEventListener('click', () => copyValue('obsidian-path', '已复制阅读库路径。'));

  async function poll() {
    await refresh();
    window.setTimeout(poll, isBusy() ? 1500 : 4000);
  }
  poll();
})();
