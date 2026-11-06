"""GitHub authorization and Actions checks for the local setup wizard."""

from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import time
import webbrowser

import researchdesk_runner as runner


RESEARCH_WORKFLOW = 'researchdesk-manual.yml'
WRITING_WORKFLOW = 'researchdesk-writing.yml'
DISABLED_WORKFLOWS = {'disabled_fork', 'disabled_inactivity', 'disabled_manually'}
HOST = 'github.com'
DEVICE_URL = 'https://github.com/login/device'
CLI_INSTALL_URL = 'https://cli.github.com/'
LOGIN_TIMEOUT = 300
HEALTH_TIMEOUT = 240
HEALTH_STEP = 'Reload configuration and run the registered workbench'
PRIVATE_REPOSITORY_NAME = 'researchdesk-workbench'
_GIT_HELPER = ('-c', 'credential.https://github.com.helper=',
               '-c', 'credential.https://github.com.helper=!gh auth git-credential')
_DEVICE_CODE = re.compile(rb'one-time code[:(\s]+([A-Z0-9]{4}-[A-Z0-9]{4})(?![A-Z0-9-])', re.I)
_HTTP_STATUS = re.compile(r'\(HTTP ([1-5][0-9]{2})\)')
_OWNER = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}')
_REPOSITORY = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}')
_USES = re.compile(r'^\s*(?:-\s+)?uses:\s*[\'\"]?(actions/[\w.-]+@[\w./-]+)', re.M)


class GitHubSetupError(RuntimeError):
    """A diagnostic composed solely of fixed text and validated identifiers."""

    def __init__(self, message, *, code='github_error', url=None, http_status=None):
        super().__init__(message)
        self.code = code
        self.url = url
        self.http_status = http_status


def _environment():
    environment = dict(os.environ, GH_PROMPT_DISABLED='1', GIT_TERMINAL_PROMPT='0',
                       GIT_ASKPASS='/usr/bin/false', NO_COLOR='1')
    environment.pop('GH_FORCE_TTY', None)
    environment.pop('GH_DEBUG', None)
    return environment


def _repo_url(repository):
    return 'https://github.com/' + repository


class GitHubSetup:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def _run(self, arguments, message, *, payload=None, timeout=25):
        try:
            result = subprocess.run(
                arguments, cwd=self.root, env=_environment(), input=payload,
                capture_output=True, text=True, errors='replace', timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            raise GitHubSetupError(message + '连接超时，请检查网络后重试。', code='github_timeout') from None
        except OSError:
            raise GitHubSetupError(message, code='github_process_failed') from None
        if result.returncode:
            status = _HTTP_STATUS.search(result.stderr)
            raise GitHubSetupError(message, http_status=int(status[1]) if status else None)
        return result.stdout

    def _api(self, route, message, *, method='GET', data=None, json_response=True, timeout=25):
        arguments = ['gh', 'api', '--hostname', HOST, '--method', method,
                     '-H', 'X-GitHub-Api-Version: 2026-03-10', route]
        payload = None
        if data is not None:
            arguments.extend(['--input', '-'])
            payload = json.dumps(data)
        response = self._run(arguments, message, payload=payload, timeout=timeout)
        if not json_response:
            return None
        try:
            result = json.loads(response)
        except ValueError:
            raise GitHubSetupError(message, code='github_response_invalid') from None
        if not isinstance(result, dict):
            raise GitHubSetupError(message, code='github_response_invalid')
        return result

    def _git(self, *arguments, message, github_auth=False, timeout=25):
        helper = _GIT_HELPER if github_auth else ()
        return self._run(['git', *helper, *arguments], message, timeout=timeout).strip()

    def _repository(self):
        try:
            name = runner._repository(self.root)
        except (runner.RunnerError, ValueError):
            raise GitHubSetupError('请将当前工作台的 origin 指向你的 GitHub 仓库。',
                                   code='github_repository_required') from None
        if not _REPOSITORY.fullmatch(name) or name.split('/')[1] in {'.', '..'}:
            raise GitHubSetupError('当前 origin 的 GitHub 仓库名称无效。', code='github_repository_required')
        return name

    def _check_auth(self):
        try:
            self._run(['gh', 'auth', 'status', '--hostname', HOST], '当前 GitHub 授权不可用。')
        except GitHubSetupError as exc:
            if exc.code != 'github_error':
                raise
            raise GitHubSetupError('请通过浏览器登录 GitHub。若当前会话设置了 GitHub 环境令牌，请先确认它有效。',
                                   code='github_login_required') from None

    def _check_actions(self, repository):
        base = 'repos/' + repository + '/actions/permissions'
        settings = _repo_url(repository) + '/settings/actions'
        try:
            policy = self._api(base, '无法读取仓库的 GitHub Actions 设置。请检查账号权限和组织策略。')
        except GitHubSetupError as exc:
            exc.url = settings
            raise
        if policy.get('enabled') is not True:
            raise GitHubSetupError('请在仓库设置中启用 GitHub Actions。若组织已限制，请联系组织管理员。',
                                   code='github_actions_disabled', url=settings)

        uses = set()
        for name in (RESEARCH_WORKFLOW, WRITING_WORKFLOW):
            try:
                uses.update(_USES.findall((self.root / '.github' / 'workflows' / name).read_text(encoding='utf-8')))
            except (OSError, UnicodeError):
                raise GitHubSetupError('当前代码缺少 ResearchDesk 工作流。请更新工作台到最新版本。',
                                       code='github_local_workflow_missing') from None
        if uses and policy.get('allowed_actions') == 'local_only':
            raise GitHubSetupError('仓库只允许本组织的 actions。请由管理员为 ResearchDesk 工作流所用的 GitHub 官方 actions 授权。',
                                   code='github_actions_policy', url=settings)
        if policy.get('sha_pinning_required') is True and any(
            not re.fullmatch(r'[a-fA-F0-9]{40}', action.split('@')[1]) for action in uses
        ):
            raise GitHubSetupError('仓库要求用完整提交 SHA 固定 actions。请更新工作流以满足仓库策略。',
                                   code='github_actions_policy', url=settings)
        if uses and policy.get('allowed_actions') == 'selected':
            try:
                selected = self._api(base + '/selected-actions', '无法检查仓库允许的 actions。请在设置中核对。')
            except GitHubSetupError as exc:
                exc.url = settings
                raise
            patterns = selected.get('patterns_allowed')
            patterns = [item for item in patterns if isinstance(item, str)] if isinstance(patterns, list) else []
            for action in uses:
                denied = any(pattern.startswith('!') and fnmatchcase(action, pattern[1:]) for pattern in patterns)
                allowed = (selected.get('github_owned_allowed') is True or
                           any(not pattern.startswith('!') and fnmatchcase(action, pattern) for pattern in patterns))
                if denied or not allowed:
                    raise GitHubSetupError('仓库的允许列表未涵盖 ResearchDesk 工作流使用的官方 actions。请由管理员核对。',
                                           code='github_actions_policy', url=settings)

    def _workflow_state(self, repository, name):
        url = _repo_url(repository) + '/actions/workflows/' + name
        try:
            result = self._api('repos/' + repository + '/actions/workflows/' + name,
                               '无法读取工作流 ' + name + '。请检查 Actions 权限，并确认 main 上已有该文件。')
        except GitHubSetupError as exc:
            exc.url = url
            raise
        state = result.get('state')
        if not isinstance(state, str) or (state != 'active' and state not in DISABLED_WORKFLOWS):
            raise GitHubSetupError('工作流 ' + name + ' 不可启用。请检查 GitHub 上的工作流状态。',
                                   code='github_workflow_unavailable', url=url)
        return state

    def _inspect(self, repository):
        url = _repo_url(repository)
        try:
            metadata = self._api('repos/' + repository, '无法读取当前 GitHub 仓库。请确认 origin 和账号访问权限。')
        except GitHubSetupError as exc:
            exc.url = url
            if exc.http_status == 404:
                exc.code = 'github_repository_required'
            raise
        permissions = metadata.get('permissions')
        if not isinstance(permissions, dict) or permissions.get('admin') is not True:
            public_main = (metadata.get('private') is False and metadata.get('default_branch') == 'main'
                           and metadata.get('archived') is not True and metadata.get('disabled') is not True)
            raise GitHubSetupError('当前账号需要仓库管理员权限才能注册自托管执行器。请使用有权限的仓库。',
                                   code='github_public_upstream' if public_main else 'github_repository_required', url=url)
        if metadata.get('archived') is True or metadata.get('disabled') is True:
            raise GitHubSetupError('当前仓库已归档或被停用。请选择可写入的仓库。',
                                   code='github_repository_unavailable', url=url)
        if metadata.get('default_branch') != 'main':
            raise GitHubSetupError('请将已包含 ResearchDesk 工作流的 main 设为仓库默认分支。',
                                   code='github_default_branch', url=url + '/settings')
        private = metadata.get('private')
        if type(private) is not bool:
            raise GitHubSetupError('无法确认 GitHub 仓库的可见性。请在仓库设置中检查。', url=url + '/settings')
        self._check_actions(repository)
        states = {name: self._workflow_state(repository, name) for name in (RESEARCH_WORKFLOW, WRITING_WORKFLOW)}
        return private, states

    def status(self):
        """Check the active GitHub identity, repository, and workflows without writing."""
        if not shutil.which('gh'):
            return {'state': 'missing_tool', 'message': '请先安装 GitHub CLI。',
                    'code': 'github_cli_missing', 'url': CLI_INSTALL_URL}
        if not shutil.which('git'):
            return {'state': 'missing_tool', 'message': '请先安装 Git。', 'code': 'git_missing',
                    'url': 'https://git-scm.com/downloads'}
        repository = None
        try:
            self._check_auth()
            repository = self._repository()
            private, states = self._inspect(repository)
        except GitHubSetupError as exc:
            state = {'github_login_required': 'needs_login',
                     'github_repository_required': 'needs_repository',
                     'github_public_upstream': 'needs_repository'}.get(exc.code, 'blocked')
            result = {'state': state, 'message': str(exc), 'code': exc.code}
            if repository:
                result['repository'] = repository
                if exc.code == 'github_public_upstream' and self._can_create(repository):
                    result.update(can_create=True, message='当前连接的是公开上游。可以用这个版本创建你的私有工作台。')
            if exc.url:
                result['url'] = exc.url
            return result
        message = ('GitHub 仓库已连接。部署时将启用 ResearchDesk 的工作流。'
                   if any(state != 'active' for state in states.values()) else 'GitHub 仓库和工作流已就绪。')
        return {'state': 'ready', 'message': message, 'repository': repository,
                'private': private, 'can_create': not private and self._can_create(repository),
                'url': _repo_url(repository)}

    def login(self, notify):
        """Delegate device authorization to gh and expose only its one-time code."""
        if not shutil.which('gh'):
            raise GitHubSetupError('请先安装 GitHub CLI。', code='github_cli_missing', url=CLI_INSTALL_URL)
        try:
            self._check_auth()
            return
        except GitHubSetupError as exc:
            if exc.code != 'github_login_required':
                raise
        self._authorize_in_browser(['login', '--hostname', HOST, '--web'], notify,
                                   '正在获取 GitHub 设备码…')
        self._check_auth()

    def _authorize_in_browser(self, command, notify, message):
        notify(message)
        try:
            process = subprocess.Popen(
                ['gh', 'auth', *command], cwd=self.root,
                env=_environment(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
        except OSError:
            raise GitHubSetupError('无法启动 GitHub CLI 的浏览器登录。') from None
        deadline = time.monotonic() + LOGIN_TIMEOUT
        try:
            code = None
            tail = b''
            with process.stdout, selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if not selector.select(max(0, deadline - time.monotonic())):
                        break
                    output = os.read(process.stdout.fileno(), 4096)
                    if not output:
                        break
                    if code is None:
                        tail = (tail + output)[-4096:]
                        match = _DEVICE_CODE.search(tail)
                        if match:
                            code = match[1].decode('ascii').upper()
                            notify('在 GitHub 授权页面输入这个一次性设备码。', code=code)
                            # gh prints the verification URL in a noninteractive pipe.
                            try:
                                webbrowser.open(DEVICE_URL, new=2)
                            except (OSError, webbrowser.Error):
                                pass
            if process.wait(timeout=max(0, deadline - time.monotonic())) != 0:
                raise GitHubSetupError('GitHub 登录未完成。请检查浏览器中的授权结果后重试。')
        except subprocess.TimeoutExpired:
            raise GitHubSetupError('等待 GitHub 浏览器授权超时，请重新登录。', code='github_login_timeout') from None
        except OSError:
            raise GitHubSetupError('读取 GitHub 授权进度失败，请重新登录。') from None
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        notify('GitHub 浏览器授权已完成，正在检查权限…')

    def _workflow_scope(self):
        response = self._run(['gh', 'api', '--hostname', HOST, '--include', 'user'],
                             '无法确认 GitHub CLI 当前授权。')
        for header in response.splitlines():
            if not header:
                break
            name, _, value = header.partition(':')
            if name.casefold() == 'x-oauth-scopes':
                return 'workflow' in {scope.strip() for scope in value.split(',')}
        return False

    def _ensure_workflow_scope(self, notify):
        if self._workflow_scope():
            return
        message = '复制 GitHub Actions 文件需要 workflow 权限。请授权后再创建私有仓库。'
        if notify is not None:
            self._authorize_in_browser(['refresh', '--hostname', HOST, '--scopes', 'workflow'], notify, message)
            if self._workflow_scope():
                return
        raise GitHubSetupError(message + '可运行 gh auth refresh --hostname github.com --scopes workflow。',
                               code='github_workflow_scope_required')

    def prepare(self, expected_repository=None, require_private=False):
        """Check the target again and enable only the two deployed workflows."""
        self._check_auth()
        repository = self._repository()
        url = _repo_url(repository)
        if expected_repository is not None and repository.casefold() != expected_repository.casefold():
            raise GitHubSetupError('当前 GitHub 仓库与向导显示的仓库不同。请重新检查后再部署。',
                                   code='github_repository_changed', url=url)
        private, states = self._inspect(repository)
        if require_private and not private:
            raise GitHubSetupError('当前 GitHub 仓库已变为公开。请重新检查并确认后再部署。',
                                   code='github_visibility_changed', url=url + '/settings')
        message = '远端 main 缺少新版阅读同步入口。请把当前版本更新到 GitHub 的 main 后重试。'
        try:
            entry = self._api('repos/' + repository + '/contents/scripts/researchdesk_setup_obsidian.py?ref=main', message)
            if entry.get('type') != 'file':
                raise GitHubSetupError(message)
        except GitHubSetupError as exc:
            exc.url = url + '/tree/main'
            raise
        try:
            self._git('ls-remote', '--exit-code', '--heads', '--', url + '.git', 'refs/heads/main', github_auth=True,
                      message='Git 无法通过当前 GitHub 授权读取 main。请检查网络和账号的仓库读取权限。')
        except GitHubSetupError as exc:
            exc.url = url
            raise
        for name, state in states.items():
            if state == 'active':
                continue
            url = _repo_url(repository) + '/actions/workflows/' + name
            try:
                self._api('repos/' + repository + '/actions/workflows/' + name + '/enable',
                          '无法启用 ' + name + '。请在 GitHub 上检查工作流设置。',
                          method='PUT', json_response=False)
            except GitHubSetupError as exc:
                exc.url = url
                raise
            if self._workflow_state(repository, name) != 'active':
                raise GitHubSetupError('GitHub 尚未启用 ' + name + '。请在 GitHub 上检查工作流设置。', url=url)

    def _creation_source(self):
        message = '请从公开上游的干净 main 克隆创建工作台。现有工作台配置和文件已保留。'
        if not (self.root / '.git').is_dir() or (self.root / '.git').is_symlink():
            raise GitHubSetupError(message)
        if self._git('rev-parse', '--show-toplevel', message=message) != str(self.root):
            raise GitHubSetupError(message)
        worktrees = self._git('worktree', 'list', '--porcelain', message=message).splitlines()
        if (self._git('branch', '--show-current', message=message) != 'main'
                or self._git('remote', message=message).splitlines() != ['origin']
                or self._git('status', '--porcelain=v1', '--untracked-files=all', message=message)
                or self._git('rev-parse', '--is-shallow-repository', message=message) != 'false'
                or sum(line.startswith('worktree ') for line in worktrees) != 1):
            raise GitHubSetupError(message)
        self._git('cat-file', '-e', 'HEAD:scripts/researchdesk_setup_obsidian.py',
                  message='请先更新到包含新版向导的公开上游 main，再创建私有工作台。')
        try:
            config = runner.load_config(self.root)
        except (runner.RunnerError, OSError, ValueError, TypeError, KeyError):
            raise GitHubSetupError('请先完成本地工作台初始化。') from None
        if ((self.root / 'config/local/deployment-started-at.json').exists()
                or (config['_directory'] / '.runner').exists()):
            raise GitHubSetupError('这台 Mac 已配置 ResearchDesk 执行器。请保留现有绑定，并单独准备新的工作台。')
        source = self._repository()
        head = self._git('rev-parse', 'HEAD', message=message)
        if not re.fullmatch(r'[0-9a-f]{40}', head):
            raise GitHubSetupError(message)
        return source, head

    def _remote_head(self, repository, message):
        ref = self._api('repos/' + repository + '/git/ref/heads/main', message)
        commit = ref.get('object')
        sha = commit.get('sha') if isinstance(commit, dict) else None
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise GitHubSetupError(message)
        return sha

    def _can_create(self, repository):
        try:
            source, head = self._creation_source()
            return source == repository and head == self._remote_head(repository, '无法验证上游的 main。')
        except GitHubSetupError:
            return False

    def create_repository(self, notify=None):
        """Create an empty private personal repo, push upstream main, then bind origin."""
        self._check_auth()
        source, head = self._creation_source()
        metadata = self._api('repos/' + source, '无法读取公开上游仓库。请检查 origin 和当前授权。')
        if (metadata.get('private') is not False or metadata.get('default_branch') != 'main'
                or metadata.get('archived') is True or metadata.get('disabled') is True):
            raise GitHubSetupError('向导只能从公开上游的默认 main 创建私有工作台。', url=_repo_url(source))
        if self._remote_head(source, '无法验证公开上游的 main。') != head:
            raise GitHubSetupError('本地 main 与公开上游不同。请先同步上游，再创建私有工作台。', url=_repo_url(source))
        login = self._api('user', '无法确认当前 GitHub 账号。').get('login')
        if not isinstance(login, str) or not _OWNER.fullmatch(login):
            raise GitHubSetupError('无法确认当前 GitHub 账号。')
        target = login + '/' + PRIVATE_REPOSITORY_NAME
        url = _repo_url(target)
        base = 'repos/' + target
        try:
            self._api(base, '无法检查目标仓库是否已存在。')
        except GitHubSetupError as exc:
            if exc.http_status != 404:
                exc.url = url
                raise
        else:
            raise GitHubSetupError('目标私有仓库名称已存在。请检查该仓库，向导会保留它。', url=url)

        try:
            self._ensure_workflow_scope(notify)
            if self._api('user', '无法确认当前 GitHub 账号。').get('login') != login:
                raise GitHubSetupError('GitHub 登录账号在创建期间发生变化。请重新检查目标仓库。')
            created = self._api('user/repos', '无法确认私有仓库是否创建。请先在 GitHub 检查目标仓库。', method='POST',
                                data={'name': PRIVATE_REPOSITORY_NAME, 'private': True, 'auto_init': False})
            owner = created.get('owner')
            fullname = created.get('full_name')
            owner_login = owner.get('login') if isinstance(owner, dict) else None
            repository_id = created.get('id')
            if (type(repository_id) is not int or repository_id < 1
                    or not isinstance(fullname, str) or fullname.casefold() != target.casefold()
                    or not isinstance(owner_login, str) or owner_login.casefold() != login.casefold()
                    or created.get('private') is not True):
                raise GitHubSetupError('GitHub 未确认目标仓库是当前账号的私有仓库。请检查该仓库。')
            if self._creation_source() != (source, head):
                raise GitHubSetupError('本地工作台在创建期间发生变化。新仓库已创建，请检查两个仓库。')
            # An empty expected value requires main to be absent on the new repo.
            self._git('push', '--no-follow-tags', '--recurse-submodules=no', '--force-with-lease=refs/heads/main:', '--', url + '.git',
                      head + ':refs/heads/main', github_auth=True, timeout=90,
                      message='私有仓库已创建，但未确认 main 已推送。原 origin 已保留，请检查新仓库。')
            current = self._api(base, '无法验证已推送的私有仓库。原 origin 已保留。')
            if current.get('id') != repository_id or current.get('private') is not True:
                raise GitHubSetupError('私有仓库在创建期间发生变化。原 origin 已保留，请检查目标仓库。')
            if self._remote_head(target, '无法验证新仓库的 main。原 origin 已保留。') != head:
                raise GitHubSetupError('新仓库的 main 已变化。原 origin 已保留，请检查目标仓库。')
            if current.get('default_branch') != 'main':
                branch = self._api(base, '无法将新仓库的 main 设为默认分支。原 origin 已保留。',
                                   method='PATCH', data={'default_branch': 'main'})
                if branch.get('default_branch') != 'main':
                    raise GitHubSetupError('新仓库的默认分支还未更新。原 origin 已保留。')
            if self._creation_source() != (source, head):
                raise GitHubSetupError('本地工作台在推送期间发生变化。新仓库已创建，请检查两个仓库。')
            self._git('remote', 'rename', 'origin', 'upstream',
                      message='新仓库已创建，但无法把原 origin 保留为 upstream。请检查本地远端。')
            self._git('remote', 'add', 'origin', url + '.git',
                      message='新仓库已创建。原远端保存在 upstream，请在当前工作台添加新的 origin。')
            self._git('fetch', '--no-tags', '--no-recurse-submodules', 'origin', 'main', github_auth=True,
                      message='新仓库已绑定到 origin。请检查网络后获取 origin/main。')
            self._git('branch', '--set-upstream-to=origin/main', 'main',
                      message='新仓库已绑定到 origin。请将本地 main 的跟踪分支设为 origin/main。')
        except GitHubSetupError as exc:
            exc.url = url
            raise
        return target

    def health(self):
        """Dispatch one zero-inference health run and verify its worker job."""
        repository = self._repository()
        base = 'repos/' + repository + '/actions'
        actions_url = _repo_url(repository) + '/actions'
        try:
            expected_runner = runner.load_config(self.root)['runner']['name']
        except (runner.RunnerError, OSError, ValueError, TypeError, KeyError):
            raise GitHubSetupError('请先完成本机执行器配置，再运行 GitHub 健康检查。') from None
        response = self._api(base + '/workflows/' + RESEARCH_WORKFLOW + '/dispatches',
                             '无法确认 GitHub 已派发健康检查。请先在 Actions 中查看结果，再决定是否重试。',
                             method='POST', data={'ref': 'main', 'inputs': {'operation': 'health'}})
        run_id = response.get('workflow_run_id')
        if type(run_id) is not int or run_id < 1:
            raise GitHubSetupError('GitHub 未返回健康检查的运行编号。请先在 Actions 中查看结果。', url=actions_url)
        run_url = actions_url + '/runs/' + str(run_id)
        run_route = base + '/runs/' + str(run_id)
        deadline = time.monotonic() + HEALTH_TIMEOUT
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                run = self._api(run_route, '暂时无法读取健康检查结果。请在 GitHub Actions 中查看。',
                                timeout=min(remaining, 20))
            except GitHubSetupError as exc:
                exc.url = run_url
                if exc.code != 'github_timeout' and exc.http_status not in {404, 500, 502, 503, 504}:
                    raise
            else:
                if run.get('status') == 'completed':
                    if (run.get('id') != run_id or run.get('event') != 'workflow_dispatch'
                            or run.get('head_branch') != 'main' or run.get('run_attempt') != 1
                            or run.get('conclusion') != 'success'):
                        raise GitHubSetupError('GitHub 健康检查未通过。请打开该次运行检查失败原因。', url=run_url)
                    self._verify_health_job(run_route, run_url, expected_runner)
                    return
            time.sleep(min(4, max(0, deadline - time.monotonic())))
        raise GitHubSetupError('等待 GitHub 健康检查超时。请确认本机执行器在线，并打开该次运行查看进度。',
                               code='github_health_timeout', url=run_url)

    def _verify_health_job(self, route, url, expected_runner):
        try:
            result = self._api(route + '/attempts/1/jobs', '无法读取本次健康检查的任务结果。')
        except GitHubSetupError as exc:
            exc.url = url
            raise
        jobs = result.get('jobs')
        if not isinstance(jobs, list):
            raise GitHubSetupError('GitHub 未返回本次健康检查的任务结果。', url=url)
        research = [job for job in jobs if isinstance(job, dict) and job.get('name') == 'research']
        if len(research) != 1 or research[0].get('conclusion') != 'success':
            raise GitHubSetupError('健康检查未在执行器上成功运行。请检查部署变量和运行记录。', url=url)
        job = research[0]
        if job.get('runner_name') != expected_runner:
            raise GitHubSetupError('GitHub 将健康检查派发给了其他执行器。请核对仓库的 runner 配置。', url=url)
        steps = job.get('steps')
        if not isinstance(steps, list) or not any(
            isinstance(step, dict) and step.get('name') == HEALTH_STEP and step.get('conclusion') == 'success'
            for step in steps
        ):
            raise GitHubSetupError('本次运行没有完成 ResearchDesk 的健康检查步骤。', url=url)
