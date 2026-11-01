#!/usr/bin/env python3
"""Loopback topic confirmation, immutable events and bounded Git synchronization.

The page may dispatch a confirmed TEST Writing job; model execution stays on
the trusted worker. No membership credential or publishing interface is exposed.
Run setup once, then serve from a separate checkout outside the Obsidian vault.
"""

import argparse
from datetime import datetime, timezone
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import webbrowser

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import researchdesk_offline as store
import researchdesk_batch_inputs as common
import researchdesk_admission as admission
import researchdesk_confirmation_inputs as inputs


DEFAULT_CONFIG = 'config/confirmation-v2.yaml'


class ConfirmationError(store.OfflineError):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def configuration_path(root, relative):
    """Read generated private settings from the bound persistent workbench."""
    root = Path(root).resolve()
    from researchdesk_workbench import generated_config_paths
    allowed = set(generated_config_paths())
    if relative not in allowed:
        return admission._location(root, relative)
    marker = root / '.git/researchdesk-workbench.json'
    if not marker.is_file():
        return admission._location(root, relative)
    value = json.loads(marker.read_text(encoding='utf-8'))
    bound = Path(value.get('root', ''))
    if (set(value) != {'root'} or not bound.is_absolute()
            or any(p.is_symlink() for p in (bound, *bound.parents))
            or not (bound / 'config/local/workbench.yaml').is_file()):
        raise store.OfflineError('确认页面的持久工作台绑定无效')
    return admission._location(bound.resolve(), relative)


def bind_workbench(root, target):
    """Store a local path in Git metadata, never copy private YAML or tokens."""
    root, target = Path(root).resolve(), Path(target).resolve()
    if not (root / 'config/local/workbench.yaml').is_file():
        return
    marker = target / '.git/researchdesk-workbench.json'
    content = json.dumps({'root': str(root)}, sort_keys=True)
    if marker.exists() and marker.read_text(encoding='utf-8') != content:
        raise store.OfflineError('已有确认目录绑定其他工作台，保留原绑定')
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(content)


def load_config(root, path=DEFAULT_CONFIG):
    root = Path(root).resolve()
    target = configuration_path(root, path)
    common.config_path(target.parents[len(Path(path).parts) - 1], path)
    value = store.load_yaml(target)
    common.fields(value, {'schema_version', 'workbench_id', 'topics', 'server', 'workspace',
                          'preview_ttl_seconds', 'writing'}, '确认页面配置')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise store.OfflineError('确认页面只支持配置版本 1')
    if not isinstance(value['workbench_id'], str) or not store.SAFE_ID.fullmatch(value['workbench_id']):
        raise store.OfflineError('工作台 ID 无效')
    topics = value['topics']
    if (not isinstance(topics, list) or not topics or any(not isinstance(t, str) or
            not re.fullmatch(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*', t) for t in topics)
            or len(set(topics)) != len(topics)):
        raise store.OfflineError('确认页面的研究方向无效')
    common.fields(value['server'], {'host', 'port'}, '本地服务')
    if value['server']['host'] != '127.0.0.1':
        raise store.OfflineError('确认页面只能监听 127.0.0.1')
    common.positive(value['server']['port'], 1024, 65535, 'port')
    common.positive(value['preview_ttl_seconds'], 1, 1800, 'preview_ttl_seconds')
    if value['workspace'] is not None and (not isinstance(value['workspace'], str) or not value['workspace'].strip()):
        raise store.OfflineError('workspace 必须为空或主机本地目录')
    writing = value['writing']
    common.fields(writing, {'backend', 'models', 'budget', 'words'} |
                  ({'style_profile'} if 'style_profile' in writing else set()), '写作范围')
    if 'style_profile' in writing:
        inputs.style_profile(root, writing)
    if writing['backend'] != 'chatgpt_plan':
        raise store.OfflineError('确认只为未来真实会员写作准备，不接受模拟后端')
    common.fields(writing['models'], {'writing', 'review'}, '写作模型')
    models = writing['models']
    if (any(not isinstance(m, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,120}', m)
            or m.startswith('mock-') for m in models.values()) or models['writing'] == models['review']):
        raise store.OfflineError('写作和独立审阅须指定不同的真实模型')
    bounds = {'max_calls': (6, 12), 'max_calls_per_stage': (2, 4), 'max_revisions': (0, 1),
              'max_input_chars': (1000, 60000), 'max_output_chars': (1000, 12000), 'timeout_seconds': (1, 120)}
    common.fields(writing['budget'], bounds, '写作预算')
    for key, (low, high) in bounds.items():
        common.positive(writing['budget'][key], low, high, key)
    if writing['budget']['max_calls'] > 3 * writing['budget']['max_calls_per_stage']:
        raise store.OfflineError('写作总预算超过阶段预算之和')
    common.fields(writing['words'], {'min', 'max', 'default'}, '目标字数')
    for key in writing['words']:
        common.positive(writing['words'][key], 200, 5000, 'words.' + key)
    if not writing['words']['min'] <= writing['words']['default'] <= writing['words']['max']:
        raise store.OfflineError('默认字数须在配置范围内')
    return dict(value, _config_path=Path(path).as_posix(),
                _config_sha256=store.digest(target.read_bytes()))


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=45)
    if result.returncode:
        raise ConfirmationError('git_failed', 'Git 同步未完成，已保留现场；请检查网络或仓库冲突。', 503)
    return result.stdout.decode('utf-8').strip()


def _record_path(root, relative, config):
    parts = Path(relative).parts
    if (len(parts) not in {5, 7} or parts[0] != 'reports' or parts[1] not in config['topics']
            or parts[2] != 'writing-approvals' or not store.SAFE_ID.fullmatch(parts[3])):
        raise store.OfflineError('确认记录路径不在允许目录')
    name = parts[-1].removesuffix('.sha256')
    allowed = (len(parts) == 5 and name in {'preview.yaml', 'confirmed.yaml'}) or (
        len(parts) == 7 and parts[4] == 'revocations' and re.fullmatch(r'event-[a-f0-9]{32}', parts[5]) and name == 'event.yaml')
    if not allowed:
        raise store.OfflineError('确认记录文件名无效')
    return admission._location(root, relative)


class GitPublisher:
    def __init__(self, root, config):
        self.root, self.config = root, config

    def _clean(self):
        if git(self.root, 'branch', '--show-current') != 'main':
            raise ConfirmationError('main_required', '确认工作目录必须位于 main。')
        if git(self.root, 'status', '--porcelain'):
            raise ConfirmationError('workspace_dirty', '确认工作目录有未保存改动，已停止自动同步并保留文件。')

    def refresh(self):
        self._clean()
        git(self.root, 'fetch', '--quiet', 'origin', 'main')
        ahead, behind = map(int, git(self.root, 'rev-list', '--left-right', '--count', 'HEAD...origin/main').split())
        if ahead and behind:
            raise ConfirmationError('sync_conflict', '确认记录与远端发生并发冲突，已保留两侧内容，请先处理同步。')
        if behind:
            git(self.root, 'merge', '--ff-only', 'origin/main')
        return ahead == 0

    def pending_files(self):
        """Only complete, purely new records may recover a failed Git commit."""
        lines = git(self.root, 'status', '--porcelain', '--untracked-files=all').splitlines()
        if not lines:
            return []
        paths = []
        for line in lines:
            if line[:2] not in {'??', 'A '}:
                raise ConfirmationError('workspace_dirty', '存在人工修改或其他文件，拒绝自动处理。')
            relative = line[3:]
            _record_path(self.root, relative, self.config)
            yaml_path = relative.removesuffix('.sha256')
            admission._checked(self.root, yaml_path)
            paths.append(relative)
        return paths

    def _allowed_ahead(self):
        changed = set(git(self.root, 'log', '--format=', '--name-only', 'origin/main..HEAD').splitlines()) - {''}
        for relative in changed:
            _record_path(self.root, relative, self.config)
            # The confirmation service may append, but never modify a remote record.
            old = subprocess.run(['git', '-C', str(self.root), 'cat-file', '-e', 'origin/main:' + relative],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if old.returncode == 0:
                raise ConfirmationError('existing_record_changed', '已有远端记录发生改动，拒绝覆盖。')

    def publish(self, files, message):
        allowed = set(files)
        for relative in allowed:
            _record_path(self.root, relative, self.config)
        dirty = git(self.root, 'status', '--porcelain', '--untracked-files=all').splitlines()
        if any(line[3:] not in allowed or line[:2] not in {'??', 'A '} for line in dirty):
            raise ConfirmationError('workspace_dirty', '发现确认记录之外的改动，拒绝暂存。')
        if dirty:
            self.pending_files()
            git(self.root, 'add', '--', *sorted(allowed))
            git(self.root, '-c', 'user.name=ResearchDesk', '-c', 'user.email=researchdesk@users.noreply.github.com',
                'commit', '-m', message)
        self._allowed_ahead()
        try:
            git(self.root, 'push', 'origin', 'HEAD:refs/heads/main')
            git(self.root, 'fetch', '--quiet', 'origin', 'main')
        except ConfirmationError:
            return False
        return True

    def is_synced(self, relative):
        try:
            return git(self.root, 'rev-parse', 'origin/main:' + relative) == git(self.root, 'hash-object', '--', relative)
        except ConfirmationError:
            return False

    def retry(self, files):
        if git(self.root, 'status', '--porcelain'):
            return self.publish(files, 'Save ResearchDesk human confirmation records')
        self.refresh()
        return self.publish(files, 'Save ResearchDesk human confirmation records')


class ConfirmationStore:
    def __init__(self, root, config, publisher=None, clock=None):
        self.root, self.config = Path(root).resolve(), config
        self.publisher = publisher if publisher is not None else GitPublisher(self.root, config)
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.previews, self.published = {}, {}
        self.writing_dispatches = {}

    def _refresh(self):
        if hasattr(self.publisher, 'refresh') and not self.publisher.refresh():
            raise ConfirmationError('sync_pending', '有已保存但未同步的确认，请先重试同步。')

    def _publish(self, files, message, identifier):
        try:
            result = self.publisher.publish(files, message) if hasattr(self.publisher, 'publish') else self.publisher(self.root, files, message)
        except (store.OfflineError, OSError, subprocess.TimeoutExpired):
            result = False
        if result:
            self.published.update({p: store.digest((self.root / p).read_bytes()) for p in files})
        return bool(result)

    def _install_bundle(self, base, values):
        """Install a complete directory in one rename, never a half approval."""
        from researchdesk_job import check_text, JobError
        contents = {}
        for name, value in values.items():
            relative = base + '/' + name
            _record_path(self.root, relative, self.config)
            payload = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode('utf-8')
            try:
                check_text(payload, relative, formal=True)
            except JobError as exc:
                raise ConfirmationError('sensitive_text', '写作要求中可能包含凭据或本机路径，请移除后重新预览。', 400) from exc
            contents[name] = payload
            contents[name + '.sha256'] = (store.digest(payload) + '\n').encode()
        target = admission._location(self.root, base)
        if target.exists():
            raise ConfirmationError('record_exists', '已有确认目录，保留而不覆盖。')
        temporary = Path(tempfile.mkdtemp(prefix='.researchdesk-confirmation-stage-', dir=str(self.root.parent)))
        try:
            for name, payload in contents.items():
                with (temporary / name).open('xb') as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            target.parent.mkdir(parents=True, exist_ok=True)
            admission._location(self.root, base)
            if target.exists():
                raise ConfirmationError('record_exists', '确认目录已存在，拒绝覆盖。')
            os.rename(str(temporary), str(target))
            directory_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return [base + '/' + name for name in contents]

    def _read(self, relative):
        _record_path(self.root, relative, self.config)
        return admission._checked(self.root, relative)

    def _base(self, topic, identifier):
        if topic not in self.config['topics'] or not isinstance(identifier, str) or not store.SAFE_ID.fullmatch(identifier):
            raise store.OfflineError('确认 ID 或研究方向无效')
        return 'reports/%s/writing-approvals/%s' % (topic, identifier)

    def list_topics(self):
        with self.lock:
            # Keep pending records visible and recoverable even when push failed.
            try:
                self._refresh()
            except ConfirmationError as exc:
                if exc.code not in {'sync_pending', 'workspace_dirty'}:
                    raise
                if hasattr(self.publisher, 'pending_files'):
                    self.publisher.pending_files()
            cards = inputs.list_topics(self.root, self.config)
            active = {r['topic_id']: r for r in self.list_confirmations() if r['status'] not in {'revoked', 'invalidated'}}
            for card in cards:
                if card['id'] in active:
                    card['confirmation_id'] = active[card['id']]['id']
                    card['status'] = active[card['id']]['status']
            return cards

    def preview(self, topic_id, choices=None):
        with self.lock:
            self._refresh()
            payload = inputs.prepare_preview(self.root, self.config, topic_id, choices)
            key = secrets.token_urlsafe(32)
            created = self.clock()
            # Keep only bounded, expiring in-memory capabilities; no nonce enters Git.
            self.previews = {k: v for k, v in self.previews.items() if v['expires'] > created}
            if len(self.previews) >= 100:
                raise ConfirmationError('too_many_previews', '预览较多，请稍后再试。', 429)
            self.previews[key] = {'payload': payload, 'expires': created + self.config['preview_ttl_seconds'], 'consumed': False}
            return dict(payload, preview_id=key,
                        expires_at=datetime.fromtimestamp(self.previews[key]['expires'], timezone.utc).isoformat())

    def _locate(self, identifier):
        if not isinstance(identifier, str) or not store.SAFE_ID.fullmatch(identifier):
            raise store.OfflineError('确认 ID 无效')
        matches = [(topic, self._base(topic, identifier)) for topic in self.config['topics']
                   if admission._location(self.root, self._base(topic, identifier) + '/confirmed.yaml').exists()]
        if len(matches) != 1:
            raise store.OfflineError('未找到唯一确认记录')
        return matches[0]

    def _status(self, topic, base):
        record, preview = self._read(base + '/confirmed.yaml'), self._read(base + '/preview.yaml')
        if (record.get('mode') != 'human_topic_confirmation' or record.get('origin') != 'local_confirmation_page'
                or record.get('decision') != 'confirmed' or record.get('topic') != topic
                or record.get('id') != Path(base).name or record.get('topic_id') != preview.get('payload', {}).get('topic_id')
                or record.get('title') != preview.get('payload', {}).get('title')
                or preview.get('workbench_id') != self.config['workbench_id']
                or preview.get('mode') != 'human_topic_preview'
                or record.get('preview_sha256') != store.digest(preview)
                or record.get('writing_scope') != ['outline', 'draft', 'candidate']
                or record.get('writing_authorized') is not True or record.get('writing_started') is not False
                or record.get('publish_authorized') is not False):
            raise store.OfflineError('确认记录不是当前入口的有效人类确认')
        revoked = sorted(admission._location(self.root, base + '/revocations').glob('*/event.yaml'))
        status, reason = 'confirmed_waiting_writer', None
        for path in revoked:
            event = self._read(path.relative_to(self.root).as_posix())
            if (event.get('mode') != 'human_topic_revocation' or event.get('confirmation_id') != record['id']
                    or event.get('confirmation_sha256') != store.digest((self.root / (base + '/confirmed.yaml')).read_bytes())):
                raise store.OfflineError('撤回记录与原确认不一致')
        if revoked:
            status = 'revoked'
        else:
            try:
                frozen_config = inputs.frozen_config(self.root, self.config, preview['payload'])
                inputs.validate_preview(self.root, frozen_config, preview['payload'])
            except store.OfflineError:
                status, reason = 'invalidated', '选题、证据或写作配置已变化，需要重新预览确认。'
        files = [base + '/' + name for name in ('preview.yaml', 'preview.yaml.sha256', 'confirmed.yaml', 'confirmed.yaml.sha256')]
        for path in revoked:
            relative = path.relative_to(self.root).as_posix()
            files += [relative, relative + '.sha256']
        synced = all(self.publisher.is_synced(p) for p in files) if hasattr(self.publisher, 'is_synced') else all(
            self.published.get(p) == store.digest((self.root / p).read_bytes()) for p in files)
        if not synced and status != 'invalidated':
            status = 'revocation_pending_sync' if revoked else 'pending_sync'
        import researchdesk_writing_status as writing_status
        writing = writing_status.inspect(self.root, topic, record['id'], base + '/confirmed.yaml')
        dispatch = self.writing_dispatches.get(record['id'])
        if dispatch and self.clock() - dispatch['timestamp'] < 90 and writing['status'] == 'not_started':
            writing = dict(writing, status=dispatch['status'], dispatched_at=dispatch['at'])
        return {'id': record['id'], 'topic': topic, 'topic_id': record['topic_id'], 'title': record['title'],
                'created_at': record['created_at'], 'status': status, 'synced': synced, 'reason': reason,
                'choices': preview['payload']['choices'],
                'writing_started': writing['started'], 'writing': writing,
                'publish_authorized': False, 'record_path': base + '/confirmed.yaml'}

    def list_confirmations(self):
        with self.lock:
            result = []
            for topic in self.config['topics']:
                folder = admission._location(self.root, 'reports/%s/writing-approvals' % topic)
                for path in sorted(folder.glob('*/confirmed.yaml')):
                    result.append(self._status(topic, path.parent.relative_to(self.root).as_posix()))
            return list(reversed(result))

    def confirm(self, preview_id, acknowledged=False):
        with self.lock:
            if acknowledged is not True:
                raise ConfirmationError('acknowledgement_required', '请先明确勾选本次写作范围。', 400)
            item = self.previews.get(preview_id) if isinstance(preview_id, str) else None
            if not item or item['expires'] <= self.clock() or item['consumed']:
                raise ConfirmationError('preview_expired_or_used', '预览已过期或已使用，请重新预览。')
            self._refresh()
            payload = inputs.validate_preview(self.root, self.config, item['payload'])
            for old in self.list_confirmations():
                if old['topic_id'] == payload['topic_id'] and old['status'] not in {'revoked', 'invalidated'}:
                    raise ConfirmationError('already_confirmed', '这个选题已有有效确认，请查看记录或先撤回。')
            identifier = 'approval-' + datetime.fromtimestamp(self.clock(), timezone.utc).strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:12]
            base = self._base(payload['topic'], identifier)
            preview = {'schema_version': 1, 'mode': 'human_topic_preview', 'workbench_id': self.config['workbench_id'],
                       'base_commit': git(self.root, 'rev-parse', 'HEAD'), 'payload': payload}
            record = {'schema_version': 1, 'mode': 'human_topic_confirmation', 'origin': 'local_confirmation_page',
                      'id': identifier, 'topic': payload['topic'], 'topic_id': payload['topic_id'],
                      'title': payload['title'], 'created_at': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(),
                      'decision': 'confirmed', 'preview_sha256': store.digest(preview),
                      'writing_scope': ['outline', 'draft', 'candidate'], 'writing_authorized': True,
                      'writing_started': False, 'publish_authorized': False}
            item['consumed'] = True
            files = self._install_bundle(base, {'preview.yaml': preview, 'confirmed.yaml': record})
            self._publish(files, 'Save ResearchDesk human topic confirmation', identifier)
            return self._status(payload['topic'], base)

    def revoke(self, confirmation_id, reason):
        with self.lock:
            if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
                raise store.OfflineError('请填写不超过 1000 字的撤回原因')
            topic, base = self._locate(confirmation_id)
            previous = self._status(topic, base)
            if previous['status'] in {'revoked', 'revocation_pending_sync'}:
                return previous
            # Cancellation is allowed even while Git is offline. It takes effect
            # for remote execution only after synchronization and revalidation.
            event = {'schema_version': 1, 'mode': 'human_topic_revocation', 'confirmation_id': confirmation_id,
                     'confirmation_sha256': store.digest((self.root / (base + '/confirmed.yaml')).read_bytes()),
                     'created_at': datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(), 'reason': reason.strip()}
            files = self._install_bundle(base + '/revocations/event-' + uuid4().hex, {'event.yaml': event})
            self._publish(files, 'Revoke ResearchDesk human topic confirmation', confirmation_id)
            return self._status(topic, base)

    def retry_sync(self, confirmation_id):
        with self.lock:
            topic, base = self._locate(confirmation_id)
            self._status(topic, base)
            files = [p.relative_to(self.root).as_posix() for p in admission._location(self.root, base).rglob('*') if p.is_file()]
            if hasattr(self.publisher, 'retry'):
                self.publisher.retry(files)
            else:
                self._publish(files, 'Save ResearchDesk human confirmation records', confirmation_id)
            return self._status(topic, base)

    def start_writing(self, confirmation_id):
        """Dispatch only; the worker rechecks confirmation before every request."""
        with self.lock:
            self._refresh()
            topic, base = self._locate(confirmation_id)
            current = self._status(topic, base)
            if not current['synced'] or current['status'] != 'confirmed_waiting_writer':
                raise ConfirmationError('writing_confirmation_inactive', '请先同步有效确认；已撤回或失效的确认不能启动写作。')
            import researchdesk_writing_member_inputs as writing_inputs
            writing_inputs.prepare_bundle(self.root, approval_id=confirmation_id,
                                          config_path=self.config['_config_path'])
            progress = current['writing']
            if progress.get('formal', {}).get('status') != 'not_admitted':
                raise ConfirmationError('writing_already_admitted', '此批次已有正式准入记录，保留已有稿件，不能新增写作请求。')
            if progress['status'] in {'test_accepted', 'rejected', 'blocked', 'revision_required',
                                      'unknown_request', 'integrity_blocked'}:
                raise ConfirmationError('writing_stopped', '此批次已完成或需要检查执行记录，不能新增写作请求。')
            now = self.clock()
            previous = self.writing_dispatches.get(confirmation_id)
            if previous and now - previous['timestamp'] < 90:
                return self._status(topic, base)
            # Mark before dispatch: a timeout can mean GitHub accepted the job.
            self.writing_dispatches[confirmation_id] = {'timestamp': now, 'status': 'dispatch_unknown',
                'at': datetime.fromtimestamp(now, timezone.utc).isoformat()}
            try:
                response = subprocess.run(['gh', 'workflow', 'run', 'researchdesk-writing.yml', '--ref', 'main',
                    '-f', 'approval_id=' + confirmation_id, '-f', 'max_new_calls=6'], cwd=self.root,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ConfirmationError('writing_dispatch_unknown', '派发结果尚不明确，请先刷新记录或查看 GitHub 运行记录；同一确认会复用已有检查点。', 503) from exc
            if response.returncode:
                raise ConfirmationError('writing_dispatch_failed', '写作任务未能派发，请检查本机 GitHub CLI 授权及 Writing 工作流后重试。', 503)
            self.writing_dispatches[confirmation_id]['status'] = 'queued'
            return self._status(topic, base)

    def document(self, relative):
        for record in self.list_confirmations():
            writing = record.get('writing', {})
            allowed_documents = writing.get('documents', []) + writing.get('formal', {}).get('documents', [])
            for item in allowed_documents:
                if item['path'] == relative:
                    payload = admission._location(self.root, relative).read_bytes()
                    if store.digest(payload) != item['sha256']:
                        raise ConfirmationError('writing_document_changed', '稿件已变化，保留文件并停止展示。')
                    return {'path': relative, 'text': payload.decode('utf-8')}
        allowed = set()
        for card in inputs.list_topics(self.root, self.config):
            preview = inputs.prepare_preview(self.root, self.config, card['id'])
            allowed.add(preview['path'])
            for item in preview['evidence']:
                allowed.add(item['path'])
                allowed.update(item['source_paths'])
        if relative not in allowed:
            raise ConfirmationError('document_not_allowed', '此文件不属于可预览的选题证据。', 404)
        return {'path': relative, 'text': admission._location(self.root, relative).read_text(encoding='utf-8')}


def create_server(root, config, host='127.0.0.1', port=0, publisher=None):
    if host != '127.0.0.1':
        raise store.OfflineError('服务只能绑定本机环回地址')
    manager = ConfirmationStore(root, config, publisher=publisher)
    assets = Path(__file__).resolve().parent / 'confirmation_ui'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log request bodies, session secrets or user choices.

        def _headers(self, status, content_type, size):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(size))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'; object-src 'none'")
            self.end_headers()

        def _json(self, value, status=200):
            payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self._headers(status, 'application/json; charset=utf-8', len(payload))
            self.wfile.write(payload)

        def _guard(self, mutation=False):
            address = self.server.server_address[1]
            hosts = {'127.0.0.1:' + str(address), 'localhost:' + str(address)}
            host_value = self.headers.get('Host')
            if host_value not in hosts or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise ConfirmationError('host_forbidden', '仅允许从本机确认页面访问。', 403)
            if mutation:
                if self.headers.get('Origin') != 'http://' + host_value:
                    raise ConfirmationError('origin_forbidden', '请在本机页面重新打开本次操作。', 403)
                token = self.headers.get('X-ResearchDesk-CSRF', '')
                if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token) or not secrets.compare_digest(token, self.server.csrf_token):
                    raise ConfirmationError('csrf_forbidden', '页面会话已失效，请刷新后重试。', 403)
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ConfirmationError('json_required', '请求必须使用 JSON。', 415)

        def _dispatch(self, mutation=False):
            try:
                self._guard(mutation)
                parts = urlsplit(self.path)
                path = parts.path
                if not mutation:
                    if path == '/api/session':
                        return self._json({'csrf_token': self.server.csrf_token, 'writing_available': True,
                            'config': {'words': config['writing']['words'], 'writing': config['writing'],
                                       'preview_ttl_seconds': config['preview_ttl_seconds']}})
                    if path == '/api/topics':
                        return self._json({'topics': manager.list_topics()})
                    if path == '/api/confirmations':
                        return self._json({'confirmations': manager.list_confirmations()})
                    if path == '/api/document':
                        return self._json(manager.document(parse_qs(parts.query).get('path', [''])[0]))
                    asset = {'/': ('index.html', 'text/html; charset=utf-8'),
                             '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                             '/style.css': ('style.css', 'text/css; charset=utf-8')}.get(path)
                    if not asset:
                        raise ConfirmationError('not_found', '未找到页面。', 404)
                    data = (assets / asset[0]).read_bytes()
                    self._headers(200, asset[1], len(data))
                    return self.wfile.write(data)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 20000:
                    raise ConfirmationError('request_size', '请求内容为空或过长。', 413)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ConfirmationError('invalid_request', '请求格式无效。', 400)
                if path == '/api/preview':
                    common.fields(payload, {'topic_id', 'choices'}, '预览请求')
                    return self._json(manager.preview(payload['topic_id'], payload['choices']))
                if path == '/api/confirm':
                    common.fields(payload, {'preview_id', 'acknowledged'}, '确认请求')
                    return self._json({'confirmation': manager.confirm(payload['preview_id'], payload['acknowledged'])})
                if path == '/api/revoke':
                    common.fields(payload, {'confirmation_id', 'reason'}, '撤回请求')
                    return self._json({'confirmation': manager.revoke(payload['confirmation_id'], payload['reason'])})
                if path == '/api/sync':
                    common.fields(payload, {'confirmation_id'}, '同步请求')
                    return self._json({'confirmation': manager.retry_sync(payload['confirmation_id'])})
                if path == '/api/writing':
                    common.fields(payload, {'confirmation_id'}, 'Writing 派发请求')
                    return self._json({'confirmation': manager.start_writing(payload['confirmation_id'])})
                raise ConfirmationError('not_found', '未找到操作。', 404)
            except ConfirmationError as exc:
                self._json({'error': {'code': exc.code, 'message': exc.message}}, exc.status)
            except (store.OfflineError, ValueError, KeyError) as exc:
                self._json({'error': {'code': 'validation_failed', 'message': str(exc)}}, 409)
            except (OSError, subprocess.TimeoutExpired):
                self._json({'error': {'code': 'temporarily_unavailable', 'message': '本地服务或同步暂时不可用，已保留已有记录。'}}, 503)

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch(True)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.store, server.csrf_token = manager, secrets.token_urlsafe(32)
    return server


def workspace_path(root, config):
    if config['workspace']:
        result = Path(config['workspace']).expanduser()
        if not result.is_absolute():
            raise store.OfflineError('确认工作目录必须是主机绝对路径或 ~ 路径')
    elif sys.platform == 'darwin':
        result = Path.home() / 'Library/Application Support/ResearchDesk/confirmation-workspace'
    else:
        result = Path.home() / '.local/share/ResearchDesk/confirmation-workspace'
    current = result
    while current != current.parent:
        if current.is_symlink():
            raise store.OfflineError('确认工作目录不可包含符号链接')
        current = current.parent
    result = result.resolve()
    root = Path(root).resolve()
    if result.is_relative_to(root) or root.is_relative_to(result):
        raise store.OfflineError('确认工作目录必须与当前仓库和 Vault 分离')
    return result


def setup(root, config):
    target = workspace_path(root, config)
    remote = git(root, 'remote', 'get-url', 'origin')
    if remote.startswith(('http://', 'https://')) and (urlsplit(remote).username or urlsplit(remote).password):
        raise store.OfflineError('Git remote 不得包含账号或凭据')
    if target.exists():
        if not (target / '.git').is_dir() or git(target, 'remote', 'get-url', 'origin') != remote:
            raise store.OfflineError('已有确认工作目录不属于当前仓库，保留而不修改')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        git(root, 'clone', '--single-branch', '--branch', 'main', '--', remote, str(target))
    # Existing workspaces may predate this configuration file. Refresh their
    # clean main checkout before trying to load a newly introduced version.
    GitPublisher(target, config).refresh()
    bind_workbench(root, target)
    load_config(target, config['_config_path'])
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'serve'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--port', type=int)
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if (root / 'config/local/workbench.yaml').is_file():
            from researchdesk_workbench import apply
            apply(root)
        config = load_config(root, args.config)
        if args.command == 'setup':
            target = setup(root, config)
            print('确认页面的独立工作目录已就绪；没有创建确认或调用模型。')
            return 0
        target = workspace_path(root, config)
        if not (target / '.git').is_dir():
            raise store.OfflineError('请先执行 setup 准备独立工作目录')
        # Keep one confirmation service per workspace; session capabilities are
        # in memory, not stored in the vault or exposed in the startup URL.
        path = Path(tempfile.gettempdir()) / ('researchdesk-confirmation-' + store.digest(str(target).encode())[:24] + '.lock')
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        publisher = GitPublisher(target, config)
        try:
            publisher.refresh()
        except ConfirmationError:
            if not publisher.pending_files():
                raise
        target_config = load_config(target, args.config)
        port = args.port if args.port is not None else target_config['server']['port']
        if not 1024 <= port <= 65535:
            raise store.OfflineError('服务端口必须在 1024–65535')
        server = create_server(target, target_config, port=port)
        print('ResearchDesk 选题确认：http://127.0.0.1:%s' % server.server_port, flush=True)
        print('页面已接通真实资料、确认记录及 TEST Writing 派发；模型由独立执行器运行，不会发布公众号。', flush=True)
        if args.open_browser:
            webbrowser.open('http://127.0.0.1:%s' % server.server_port)
        try:
            server.serve_forever()
        finally:
            server.server_close()
            os.close(fd)
    except (store.OfflineError, OSError, subprocess.TimeoutExpired) as exc:
        print('确认页面未启动：' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
