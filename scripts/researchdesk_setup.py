#!/usr/bin/env python3
"""Configure a recurring ResearchDesk workbench from one local browser page."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import re
import secrets
import select
import subprocess
import sys
import tempfile
import threading
import unicodedata
from urllib.parse import parse_qs, urlsplit
import webbrowser

import researchdesk_automatic as automatic
from researchdesk_membership import MembershipClient, MembershipError
import researchdesk_offline as store
import researchdesk_runner as runner
import researchdesk_schedule as schedule
from researchdesk_setup_github import GitHubSetup, GitHubSetupError
from researchdesk_setup_obsidian import ObsidianSetup, ObsidianSetupError
import researchdesk_workbench as workbench


ACTIONS = {
    'check': '正在检查已有配置和授权…',
    'save_topics': '正在保存研究方向…',
    'chatgpt_login': '请在浏览器中的 OpenAI 页面授权…',
    'github_login': '请在浏览器中的 GitHub 页面授权…',
    'github_workflow_auth': '请在浏览器中补充 GitHub Actions 授权…',
    'github_create': '正在准备你的私有 GitHub 仓库…',
    'create_schedule': '正在检查 GitHub Actions…',
    'obsidian_sync': '正在从 GitHub 更新独立阅读库…',
    'obsidian_open': '正在打开 Obsidian…',
    'confirmation_open': '正在准备选题确认页…',
}
GITHUB_WORKFLOW_REQUIRED = '请在「连接账号」中完成 GitHub Actions 授权。'
START_ERRORS = {
    'github_repository_runner_admin_permission_required': '当前 GitHub 账号没有目标仓库的管理员权限。',
    'existing_runner_registration_mismatch': '这台机器上的 runner 已登记到其他仓库或使用了其他名称。',
    'runner_workbench_binding_mismatch': '现有 runner 已绑定其他运行目录。请到那个目录重新打开向导。',
    'runtime_dependencies_install_failed': 'SDK 依赖安装失败。请检查网络后重试。',
    'configured_codex_preflight_failed': '本机 Codex SDK 检查失败。请检查运行环境后重试。',
    'configured_codex_runtime_not_ready': '本机 Codex SDK 尚未就绪。请检查运行环境后重试。',
    'github_deployment_gate_activation_failed': 'GitHub 未能保存部署变量。请核对仓库权限后重试。',
    'configured_models_unavailable_for_current_account': 'ChatGPT 可用模型有变化。请重新检查授权和模型。',
    'required_runner_tools_missing': '本机缺少 Git、GitHub CLI、curl 或 tar。安装后重新检查。',
}


class SetupError(ValueError):
    pass


def section(state, message, **fields):
    return {'state': state, 'message': message, **fields}


def save_user_config(root, user):
    path = workbench._path(root, workbench.LOCAL_CONFIG)
    if workbench._read(path) == user:
        return
    workbench.apply(root, check_only=True)
    workbench.render(workbench.load_effective(root, user))
    backup = workbench._path(root, 'config/local/workbench.before-setup.yaml')
    if not backup.exists():
        workbench._write(backup, path.read_bytes())
    workbench._write(path, workbench._yaml(user))
    workbench.apply(root)


def configure_models(root, catalog):
    available = list(dict.fromkeys(entry['slug'] for entry in catalog
                                  if not entry['slug'].startswith('mock-')))
    if len(available) < 2:
        raise SetupError('此账号当前需要至少两个可用模型，分别用于生成和独立审阅。')
    user = workbench._read(workbench._path(root, workbench.LOCAL_CONFIG))
    shortcuts = user.get('models', {})
    if shortcuts:
        generation = shortcuts.get('generation')
        if generation not in available:
            generation = available[0]
        review = shortcuts.get('review')
        if review not in available or review == generation:
            review = next(model for model in available if model != generation)
        writing = shortcuts.get('writing')
        if writing not in available or writing == review:
            writing = generation
        for key, model in (('generation', generation), ('review', review), ('writing', writing)):
            if key in shortcuts:
                shortcuts[key] = model
    effective = workbench.load_effective(root, user)
    groups = [
        ('research', effective['research']['models'], ('research', 'insight')),
        ('insight', effective['insight']['models'], ('generation',)),
        ('confirmation', effective['confirmation']['writing']['models'], ('writing',)),
    ]
    for name, models, generators in groups:
        updated = dict(models)
        review = models['review']
        for role in generators:
            if updated[role] not in available:
                updated[role] = next(model for model in available if model != review)
        used = {updated[role] for role in generators}
        if review not in available or review in used:
            if len(used) == len(available):
                updated[generators[-1]] = updated[generators[0]]
                used = {updated[role] for role in generators}
            updated['review'] = next(model for model in available if model not in used)
        if models != updated:
            target = user.setdefault(name, {})
            if name == 'confirmation':
                target = target.setdefault('writing', {})
            target['models'] = updated
    save_user_config(root, user)


def schedule_config(root, weekly):
    user = workbench._read(workbench._path(root, workbench.LOCAL_CONFIG))
    current = workbench.load_effective(root, user)['automation']
    automation = user.setdefault('automation', {})
    if not current['enabled'] or schedule.weekly(current) != weekly:
        activated = max(datetime.now(timezone.utc), schedule.instant(current['activated_at']))
        automation['activated_at'] = activated.isoformat()
    automation.update(enabled=True, weekly=weekly)
    user.setdefault('admission', {})['enabled'] = True
    return user


def schedule_text(weekly):
    days = '一二三四五六日'
    selected = '、'.join('周' + days[day - 1] for day in weekly['weekdays'])
    return f"每{selected} {weekly['time']}（{weekly['timezone']}）"


def schedule_preview(query, root=None):
    try:
        fields = parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
    except ValueError:
        raise SetupError('请输入星期、时间和时区。') from None
    if set(fields) != {'weekdays', 'time', 'timezone'} or any(len(values) != 1 for values in fields.values()):
        raise SetupError('请输入星期、时间和时区。')
    days, clock, zone = (fields[key][0] for key in ('weekdays', 'time', 'timezone'))
    if not re.fullmatch(r'[1-7](?:,[1-7]){0,6}', days):
        raise SetupError('请选择 1–7 个不同的星期，星期一为 1，星期日为 7。')
    rule = {'weekdays': [int(day) for day in days.split(',')], 'time': clock, 'timezone': zone}
    activated_at = None
    if isinstance(root, Path):
        try:
            config = workbench.load_effective(root)['automation']
            value = automatic._activation(root, config)['activated_at']
            schedule.instant(value)
            activated_at = value
        except (OSError, ValueError, KeyError, TypeError):
            # Preview is available before a workbench is initialized.
            pass
    return {'next_run': schedule.next_run(rule, activated_at=activated_at).isoformat()}


def topic_name(value):
    if not isinstance(value, str) or any(unicodedata.category(char).startswith('C') for char in value):
        raise SetupError('请输入有效的研究方向名称。')
    name = ' '.join(unicodedata.normalize('NFKC', value).split())
    if not 1 <= len(name) <= 80 or not any(char.isalnum() for char in name):
        raise SetupError('研究方向名称须包含文字或数字，长度为 1–80 个字符。')
    return name


def topic_choices(value):
    if not isinstance(value, list) or not 1 <= len(value) <= schedule.MAX_TOPICS:
        raise SetupError(f'请保留 1–{schedule.MAX_TOPICS} 个研究方向。')
    selected, names, ids = [], set(), set()
    for item in value:
        if not isinstance(item, dict) or set(item) not in ({'name'}, {'id', 'name'}):
            raise SetupError('研究方向格式无效。')
        name = topic_name(item['name'])
        identity = item.get('id')
        if 'id' in item and (not isinstance(identity, str) or not store.SAFE_ID.fullmatch(identity)):
            raise SetupError('研究方向 ID 无效。')
        if name.casefold() in names or identity in ids:
            raise SetupError('研究方向有重复项，请移除重复项再保存。')
        names.add(name.casefold())
        if identity is not None:
            ids.add(identity)
        selected.append((identity, name))
    return selected


def configure_topics(root, choices):
    user = workbench._read(workbench._path(root, workbench.LOCAL_CONFIG))
    effective = workbench.load_effective(root, user)
    definitions = effective['research_topics']['topics']
    by_name = {}
    for identity, definition in definitions.items():
        try:
            normalized = topic_name(definition.get('name'))
        except SetupError:
            continue
        by_name.setdefault(normalized.casefold(), identity)
    overrides = user.setdefault('research_topics', {}).setdefault('topics', {})
    selected = []
    for identity, name in choices:
        if identity is not None:
            if identity not in definitions or topic_name(definitions[identity].get('name')).casefold() != name.casefold():
                raise SetupError('已有研究方向已变化，请重新检查工作台后保存。')
        else:
            identity = by_name.get(name.casefold())
        if identity is None:
            slug = re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')[:55].rstrip('-')
            identity = slug if re.match(r'[a-z]', slug) and slug not in definitions and slug not in selected else (
                'topic-' + store.digest(name.casefold())[:20])
            if identity in definitions:
                raise SetupError('此研究方向与现有标识冲突，请换一个名称。')
            overrides[identity] = {
                'name': name,
                'enabled': True,
                'description': f'研究与{name}直接相关的公开论文和技术文章。',
                'scope': [f'梳理{name}相关的方法、证据、实现与适用边界。'],
                'keywords': [name],
            }
        else:
            overrides.setdefault(identity, {})['enabled'] = True
        if identity in selected:
            raise SetupError('研究方向有重复项，请移除重复项再保存。')
        selected.append(identity)
    previous = effective['automation'].get('topics', [effective['research']['topic']])
    for identity in set(previous) - set(selected):
        overrides.setdefault(identity, {})['enabled'] = False
    if 'topic' in user:
        user['topic'] = selected[0]
    for stage in ('research', 'insight'):
        user.setdefault(stage, {})['topic'] = selected[0]
    for stage in ('automation', 'admission', 'confirmation', 'writing_admission'):
        user.setdefault(stage, {})['topics'] = selected
    save_user_config(root, user)


class SetupWizard:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.github = GitHubSetup(self.root)
        self.obsidian = ObsidianSetup(self.root)
        self.lock = threading.Lock()
        self.state = {
            'setup': section('idle', '正在准备本地工作台。'),
            'chatgpt': section('idle', '正在检查 ChatGPT 授权。'),
            'github': section('idle', '正在检查 GitHub 授权。'),
            'deployment': section('idle', '连接账号后，选择时间并创建定时研究。'),
            'obsidian': section('idle', 'GitHub 就绪后准备独立阅读库。'),
            'operation': None,
        }
        self.return_url = None
        self.confirmation_process = None
        self.confirmation_url = None

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def update(self, name, value):
        with self.lock:
            self.state[name] = value

    def notify(self, message, code=None):
        with self.lock:
            operation = self.state['operation']
            if operation is not None:
                operation['message'] = message
                if code is not None:
                    operation['code'] = code
                else:
                    operation.pop('code', None)

    def submit(self, action, payload=None):
        if action not in ACTIONS:
            raise SetupError('未知操作。')
        with self.lock:
            if self.state['operation'] is not None:
                return False
            self.state.pop('notice', None)
            self.state['operation'] = {'action': action, 'message': ACTIONS[action]}
        threading.Thread(target=self.perform, args=(action, payload), daemon=True).start()
        return True

    def client(self):
        host = runner.load_config(self.root)
        return MembershipClient(host['_profile'], self.root)

    def check_chatgpt(self):
        try:
            client = self.client()
            status = client.status()
            if not status.get('authenticated') or not status.get('plan_permission'):
                return section('needs_login', '请授权 ResearchDesk 使用你的 ChatGPT 会员用量。')
            catalog = client.models()
            with automatic.pipeline_lock(self.root):
                configure_models(self.root, catalog)
            return section('ready', 'ChatGPT 授权和独立审阅模型已就绪。')
        except MembershipError as exc:
            if exc.code in {'login_required', 'plan_permission_missing'}:
                return section('needs_login', 'ChatGPT 授权需要更新，请重新连接。')
            return section('blocked', '无法确认 ChatGPT 模型权限。请检查网络或重新连接。')
        except SetupError as exc:
            return section('blocked', str(exc))

    def update_setup(self):
        value = workbench.load_effective(self.root)
        topic = value['research']['topic']
        definitions = value['research_topics']['topics']
        selected = value['automation'].get('topics', [topic])
        weekly = schedule.weekly(value['automation'])
        self.update('setup', section(
            'ready', '已准备本地主题、资料来源和用量上限。',
            topic=topic, topics=[{'id': identity, 'name': definitions[identity]['name']} for identity in selected],
            schedule=schedule_text(weekly), weekly=weekly,
            automation=value['automation']['enabled'], admission=value['admission']['enabled'],
        ))

    def inspect(self):
        with automatic.pipeline_lock(self.root):
            adopt = not workbench._path(self.root, workbench.LOCAL_CONFIG).exists() and any(
                workbench._path(self.root, name).exists() for name in workbench.generated_config_paths())
            workbench.initialize(self.root, adopt_existing=adopt)
        self.update_setup()
        self.update('chatgpt', self.check_chatgpt())
        self.update('github', self.github.status())
        self.update('obsidian', self.obsidian.status())

    def refresh_schedule(self):
        current = self.snapshot()
        if any(current[key]['state'] != 'ready' for key in ('setup', 'chatgpt', 'github')):
            self.update('deployment', section('needs_setup', '连接 ChatGPT 和 GitHub 后即可创建。'))
            return
        repo = current['github']['repository']
        url = f'https://github.com/{repo}/actions/workflows/researchdesk-manual.yml'
        automation = workbench.load_effective(self.root)['automation']
        if automation['enabled']:
            if 'weekly' in automation:
                weekly = schedule.weekly(automation)
                cron, zone = schedule.workflow_cron(weekly), weekly['timezone']
            else:
                cron, zone = automation['schedule_utc'], 'UTC'
            try:
                if self.github.schedule_matches(cron, zone, expected_repository=repo):
                    self.update('deployment', section('ready', '定时研究已创建。', url=url, repository=repo))
                    return
            except GitHubSetupError as exc:
                self.update('deployment', section('blocked', str(exc), url=exc.url or url))
                return
            self.update('deployment', section('needs_setup', '本地日程与 GitHub 不一致，请选择时间并重新创建。'))
            return
        message = ('选择运行时间，然后点击「创建定时研究」。' if current['github'].get('workflow_scope') is True
                   else GITHUB_WORKFLOW_REQUIRED)
        self.update('deployment', section('needs_setup', message))

    def create_schedule(self, weekly):
        current = self.snapshot()
        if any(current[key]['state'] != 'ready' for key in ('setup', 'chatgpt', 'github')):
            self.update('deployment', section('needs_setup', '连接 ChatGPT 和 GitHub 后即可创建。'))
            return
        if current['github'].get('workflow_scope') is not True:
            self.update('notice', section('blocked', GITHUB_WORKFLOW_REQUIRED))
            return
        if platform.system() != 'Darwin':
            self.update('deployment', section('blocked', '请在执行每周研究的 Mac 上运行 ./setup。'))
            return
        repo = current['github']['repository']
        url = f'https://github.com/{repo}/actions/workflows/researchdesk-manual.yml'
        require_private = current['github'].get('private') is not False
        try:
            self.github.require_workflow_scope()
            self.update('deployment', section('running', '正在检查仓库与两个工作流。', url=url))
            self.notify('正在检查仓库与两个工作流…')
            self.github.prepare(expected_repository=repo, require_private=require_private, require_schedule=True)
            self.notify('正在安装 Codex SDK、配置并启动 Mac 执行器…')
            with automatic.pipeline_lock(self.root):
                if runner._repository(self.root).casefold() != repo.casefold():
                    raise SetupError('工作台的 GitHub 远端已变化，请重新检查。')
                workbench.start(self.root)
            self.notify('等待 GitHub 健康检查完成…')
            self.github.health()
            self.notify('正在创建 GitHub Actions 定时触发…')
            with automatic.pipeline_lock(self.root):
                workbench.apply(self.root, check_only=True)
                workbench.render(workbench.load_effective(self.root, schedule_config(self.root, weekly)))
                url = self.github.configure_schedule(schedule.workflow_cron(weekly), weekly['timezone'],
                                                     expected_repository=repo, require_private=require_private)
                save_user_config(self.root, schedule_config(self.root, weekly))
            self.update_setup()
        except GitHubSetupError as exc:
            if exc.code == 'github_workflow_scope_required':
                self.update('deployment', current['deployment'])
                raise
            self.update('deployment', section('blocked', str(exc), url=getattr(exc, 'url', None) or url))
            return
        except (runner.RunnerError, store.OfflineError) as exc:
            message = START_ERRORS.get(str(exc), '部署未完成。请检查本机运行环境和仓库设置后重试。')
            self.update('deployment', section('blocked', message, url=url))
            return
        self.update('deployment', section(
            'ready', '定时研究已创建。健康检查通过，任务将按所选时间运行。', url=url, repository=repo))
        self.notify('正在准备 Obsidian 阅读库…')
        self.obsidian_action('obsidian_sync')

    def obsidian_action(self, action):
        try:
            if action == 'obsidian_sync':
                self.update('obsidian', {**self.snapshot()['obsidian'], 'state': 'running',
                                         'message': '正在从 GitHub 同步阅读副本…'})
                self.obsidian.sync()
            else:
                self.obsidian.open()
            self.update('obsidian', self.obsidian.status())
        except ObsidianSetupError as exc:
            self.update('obsidian', {**self.obsidian.status(), 'state': 'blocked', 'message': str(exc)})

    def open_confirmation(self):
        if self.snapshot()['deployment']['state'] != 'ready':
            raise SetupError('请先完成 GitHub 部署，正式选题回存后可在确认页查看。')
        if self.confirmation_process is not None and self.confirmation_process.poll() is None:
            webbrowser.open(self.confirmation_url, new=1)
            return
        # Reuse the selected gh account in this subprocess only, including a
        # checkout originally cloned over SSH. Never change global Git config.
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GH_PROMPT_DISABLED='1', GIT_CONFIG_COUNT='3')
        for index, (key, value) in enumerate([
            ('credential.https://github.com.helper', ''),
            ('credential.https://github.com.helper', '!gh auth git-credential'),
            ('url.https://github.com/.insteadOf', 'git@github.com:'),
        ]):
            env['GIT_CONFIG_KEY_' + str(index)] = key
            env['GIT_CONFIG_VALUE_' + str(index)] = value
        command = [sys.executable, '-B', str(self.root / 'scripts/researchdesk_confirmation.py')]
        configured = subprocess.run(command + ['setup'], cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, check=False, timeout=90)
        if configured.returncode:
            raise SetupError('选题确认目录未能准备好。请检查 GitHub 权限和现有确认目录。')
        process = subprocess.Popen(command + ['serve'], cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        with process.stdout:
            if select.select([process.stdout], [], [], 45)[0]:
                prefix, separator, value = process.stdout.readline().decode('utf-8', 'replace').strip().partition('http://')
                if (prefix == 'ResearchDesk 选题确认：' and separator and re.fullmatch(r'127\.0\.0\.1:[0-9]{4,5}', value)
                        and process.stdout.readline().decode('utf-8', 'replace').startswith('页面已接通')):
                    self.confirmation_process = process
                    self.confirmation_url = 'http://' + value
        if self.confirmation_process is not process:
            if process.poll() is None:
                process.terminate()
            raise SetupError('确认页未能启动。请检查该端口是否已被占用，或返回已经打开的确认页。')
        webbrowser.open(self.confirmation_url, new=1)

    def perform(self, action, payload=None):
        stage = 'setup'
        return_to_wizard = False
        try:
            if action == 'check':
                self.inspect()
            elif action == 'save_topics':
                stage = 'notice'
                with automatic.pipeline_lock(self.root):
                    configure_topics(self.root, payload)
                self.update_setup()
                self.update(stage, section('ready', '研究方向已保存，下次定时研究会使用这份列表。',
                                           action='save_topics'))
                return
            elif action == 'chatgpt_login':
                stage = 'chatgpt'
                self.client().login(announce=lambda _: self.notify(ACTIONS[action]))
                self.update(stage, self.check_chatgpt())
            elif action in ('github_login', 'github_workflow_auth'):
                stage = 'github' if action == 'github_login' else 'notice'
                authorize = self.github.login if action == 'github_login' else self.github.authorize_workflow
                authorize(self.notify)
                github = self.github.status()
                self.update('github', github)
                return_to_wizard = github['state'] != 'needs_login'
            elif action == 'github_create':
                stage = 'github'
                github = self.github.status()
                self.update(stage, github)
                if not github.get('can_create'):
                    raise SetupError('请在 GitHub 创建自己的仓库，然后返回检查。')
                if github.get('workflow_scope') is not True:
                    self.update('notice', section('blocked', GITHUB_WORKFLOW_REQUIRED))
                    return
                self.github.create_repository()
                self.update(stage, self.github.status())
            elif action in {'obsidian_sync', 'obsidian_open'}:
                stage = 'obsidian'
                self.obsidian_action(action)
                return
            elif action == 'confirmation_open':
                stage = 'notice'
                self.open_confirmation()
                self.update(stage, section('ready', '已请求打开选题确认页。正式选题回存后可在页面查看。'))
                return
            elif action == 'create_schedule':
                stage = 'deployment'
                self.create_schedule(payload)
                return
            stage = 'deployment'
            self.refresh_schedule()
        except GitHubSetupError as exc:
            if action in ('create_schedule', 'github_create') and exc.code == 'github_workflow_scope_required':
                self.update('github', {**self.snapshot()['github'], 'workflow_scope': False})
                self.update('notice', section('blocked', str(exc)))
                return
            details = {**self.snapshot().get(stage, {}), 'code': exc.code}
            if exc.url:
                details['url'] = exc.url
            details.update(state='needs_login' if action == 'github_login' else 'blocked', message=str(exc))
            self.update(stage, details)
        except (ObsidianSetupError, SetupError) as exc:
            self.update(stage, {**self.snapshot().get(stage, {}), 'state': 'blocked', 'message': str(exc)})
        except MembershipError as exc:
            message = {
                'authorization_timeout': '授权超时。请重新点击连接 ChatGPT。',
                'system_browser_unavailable': '无法打开系统浏览器。请设定默认浏览器后重试。',
                'access_denied': '授权未完成。准备好后可重新连接。',
            }.get(exc.code, 'ChatGPT 授权未完成。请检查浏览器或网络后重试。')
            self.update('chatgpt', section('needs_login', message))
            if stage == 'deployment':
                self.update('deployment', section('needs_setup', '重新连接 ChatGPT 后继续部署。'))
        except store.OfflineError as exc:
            if str(exc).startswith(('兼容配置被手工修改', '已有配置', '当前持久工作台已有')):
                message = str(exc)
            else:
                message = '工作台配置未通过检查。请检查本地配置后重试。'
            self.update(stage, {**self.snapshot().get(stage, {}), 'state': 'blocked', 'message': message})
        except Exception:
            self.update(stage, {**self.snapshot().get(stage, {}), 'state': 'blocked',
                                'message': '此步骤暂时无法完成，请检查本机环境和网络后重试。'})
        finally:
            self.update('operation', None)
            if return_to_wizard and self.return_url:
                try:
                    webbrowser.open(self.return_url)
                except (OSError, webbrowser.Error):
                    pass


def create_server(wizard, port=0):
    assets = Path(__file__).resolve().parent / 'setup_ui'
    routes = {'/': ('index.html', 'text/html; charset=utf-8'),
              '/style.css': ('style.css', 'text/css; charset=utf-8'),
              '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def reply(self, status, payload, content_type='application/json; charset=utf-8'):
            if isinstance(payload, dict):
                payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy',
                             "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def trusted(self, mutation=False):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return False
            return not mutation or (
                self.headers.get('Origin') == 'http://' + host
                and secrets.compare_digest(self.headers.get('X-ResearchDesk-CSRF', '').encode('utf-8'),
                                           token.encode('ascii'))
            )

        def do_GET(self):
            if not self.trusted():
                return self.reply(403, {'error': '请从本机向导地址访问。'})
            url = urlsplit(self.path)
            path = url.path
            if path == '/api/status':
                return self.reply(200, {**wizard.snapshot(), 'csrf': token})
            if path == '/api/schedule-preview':
                try:
                    preview = schedule_preview(url.query, getattr(wizard, 'root', None))
                except (SetupError, store.OfflineError) as exc:
                    return self.reply(400, {'error': str(exc)})
                return self.reply(200, preview)
            if path not in routes:
                return self.reply(404, {'error': '未找到此页面。'})
            name, content_type = routes[path]
            self.reply(200, (assets / name).read_bytes(), content_type)

        def do_POST(self):
            if not self.trusted(mutation=True):
                return self.reply(403, {'error': '请刷新本机向导页面后重试。'})
            if self.path != '/api/action':
                return self.reply(404, {'error': '未找到此操作。'})
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                return self.reply(415, {'error': '请求需要 JSON。'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError()
                data = json.loads(self.rfile.read(length))
                action = data.get('action') if isinstance(data, dict) else None
                if not isinstance(action, str) or action not in ACTIONS:
                    raise ValueError()
                payload = None
                if action == 'save_topics' and set(data) == {'action', 'topics'}:
                    payload = topic_choices(data['topics'])
                elif action == 'create_schedule' and set(data) == {'action', 'schedule'}:
                    try:
                        payload = schedule.validate_weekly(data['schedule'])
                    except store.OfflineError as exc:
                        raise SetupError(str(exc)) from exc
                elif action in {'save_topics', 'create_schedule'} or set(data) != {'action'}:
                    raise ValueError()
            except SetupError as exc:
                return self.reply(400, {'error': str(exc)})
            except (ValueError, OSError):
                return self.reply(400, {'error': '请求格式或操作无效。'})
            accepted = wizard.submit(action) if payload is None else wizard.submit(action, payload)
            if not accepted:
                return self.reply(409, {'error': '向导正在处理另一步，请稍后再试。'})
            self.reply(202, {'accepted': True})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true', help='仅显示向导地址')
    args = parser.parse_args(argv)
    root = workbench.REPOSITORY
    path = Path(tempfile.gettempdir()) / ('researchdesk-setup-' + store.digest(str(root))[:24] + '.lock')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            existing = os.read(fd, 128).decode('ascii', 'replace')
            if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}', existing):
                print('此工作台的向导正在启动，请稍后重试。', file=sys.stderr)
                return 1
            print('ResearchDesk 配置向导 ' + existing, flush=True)
            if not args.no_browser:
                webbrowser.open(existing, new=1)
            return 0
        wizard = SetupWizard(root)
        with create_server(wizard) as server:
            url = f'http://127.0.0.1:{server.server_port}'
            if not args.no_browser:
                wizard.return_url = f'{url}/#accounts-heading'
            os.ftruncate(fd, 0)
            os.write(fd, url.encode('ascii'))
            print('ResearchDesk 配置向导 ' + url, flush=True)
            wizard.submit('check')
            if not args.no_browser:
                webbrowser.open(url, new=1)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    finally:
        os.close(fd)


if __name__ == '__main__':
    raise SystemExit(main())
