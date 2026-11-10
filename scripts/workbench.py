#!/usr/bin/env python3
"""Initialize a private workbench; no login, inference, Git writes or scheduling."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import sys
import tempfile

import yaml

import offline as store


REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATE = 'config/workbench.example.yaml'
SYSTEM_CONFIG = 'config/system.yaml'
LOCAL_CONFIG = 'config/local/workbench.yaml'
MANIFEST = 'config/local/generated.json'
MIGRATION_BACKUP = 'config/local/workbench.before-layers.yaml'
GENERATED_FILES = {
    'research_topics': 'config/research_topics.yaml',
    'research': 'config/cycles/default.yaml',
    'insight': 'config/local/codex-insight.yaml',
    'membership_budget': 'config/membership_budget.yaml',
    'runtime': 'config/runtime.yaml',
    'automation': 'config/automation.yaml',
    'confirmation': 'config/confirmation-v2.yaml',
    'admission': 'config/admission.yaml',
    'writing_admission': 'config/writing_admission.yaml',
    'writing_style': 'config/writing_style.md',
}
STATE = 'config/research_state.yaml'
SOURCES_PATH = ('research', 'discovery', 'sources')


def generated_config_paths():
    return set(GENERATED_FILES.values()) | {'config/confirmation.yaml'}


def _path(root, relative):
    path = root / relative
    for parent in (path,) + tuple(path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise store.OfflineError('本地配置拒绝符号链接: ' + relative)
    return path


def _read(path):
    try:
        value = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as exc:
        raise store.OfflineError('无法读取 YAML: ' + path.name) from exc
    if not isinstance(value, dict):
        raise store.OfflineError('配置须为 YAML 映射: ' + path.name)
    return value


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement, with owner-only permissions even on a shared machine.
    fd, temporary = tempfile.mkstemp(prefix='.workbench-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _yaml(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode('utf-8')


def _sources(values):
    if not isinstance(values, list):
        raise store.OfflineError('sources 必须是列表')
    result = {}
    for source in values:
        if (not isinstance(source, dict) or not isinstance(source.get('id'), str)
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', source['id'])
                or source['id'] in result):
            raise store.OfflineError('来源须有有效且不重复的 id')
        if 'enabled' in source and type(source['enabled']) is not bool:
            raise store.OfflineError('来源 enabled 必须为布尔值')
        result[source['id']] = deepcopy(source)
    return result


def merge_config(system, user, path=()):
    """Deep mappings, ID-keyed sources; other values/lists are user choices."""
    if path == SOURCES_PATH:
        entries = _sources(system)
        for identity, source in _sources(user).items():
            base = entries.get(identity, {})
            if 'adapter' in source and source['adapter'] != base.get('adapter', source['adapter']):
                entries[identity] = source
            else:
                entries[identity] = merge_config(base, source, path + (identity,))
        return list(entries.values())
    if isinstance(system, dict) and isinstance(user, dict):
        result = deepcopy(system)
        for key, value in user.items():
            if key in system:
                result[key] = merge_config(system[key], value, path + (key,))
            elif path + (key,) == SOURCES_PATH:
                result[key] = list(_sources(value).values())
            else:
                result[key] = deepcopy(value)
        return result
    return deepcopy(user)


def _defaults(root):
    path = _path(root, SYSTEM_CONFIG)
    return _read(path if path.is_file() else REPOSITORY / SYSTEM_CONFIG)


def _legacy_complete(value):
    return set(value) == {'schema_version', 'workbench_id'} | set(GENERATED_FILES)


def _expand_shortcuts(user):
    user = deepcopy(user)
    shortcuts = {}
    if 'topic' in user:
        topic = user.pop('topic')
        if not isinstance(topic, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*', topic):
            raise store.OfflineError('topic 必须是有效研究方向 ID')
        shortcuts = {'research': {'topic': topic}, 'insight': {'topic': topic},
                     'confirmation': {'topics': [topic]}, 'admission': {'topics': [topic]},
                     'writing_admission': {'topics': [topic]}}
    if 'models' in user:
        models = user.pop('models')
        if (not isinstance(models, dict) or set(models) - {'generation', 'review', 'writing'}
                or any(not isinstance(value, str) or not value.strip() for value in models.values())):
            raise store.OfflineError('模型快捷配置仅支持 generation、review、writing')
        roles = {'generation': [('research', 'research'), ('research', 'insight'), ('insight', 'generation')],
                 'review': [('research', 'review'), ('insight', 'review'), ('confirmation', 'review')],
                 'writing': [('confirmation', 'writing')]}
        for name, model in models.items():
            for section, role in roles[name]:
                destination = shortcuts.setdefault(section, {})
                if section == 'confirmation':
                    destination = destination.setdefault('writing', {})
                destination.setdefault('models', {})[role] = model
    # Explicit stage-specific settings are more specific than shortcuts.
    return merge_config(shortcuts, user)


def load_effective(root, overrides=None):
    root = Path(root).resolve()
    user = _read(_path(root, LOCAL_CONFIG)) if overrides is None else overrides
    if not isinstance(user, dict):
        raise store.OfflineError('用户配置须为 YAML 映射')
    if 'schema_version' in user and (type(user['schema_version']) is not int or user['schema_version'] != 1):
        raise store.OfflineError('用户配置仅支持 schema_version: 1')
    defaults = _defaults(root)
    # Validate source IDs in both layers, including an unmodified defaults list.
    _sources(defaults['research']['discovery']['sources'])
    if _legacy_complete(user):
        # Previous releases stored an entire source list. It was an explicit
        # selection, including absent optional features such as attention.
        # Inheriting them here would change a frozen legacy configuration.
        _sources(user['research']['discovery']['sources'])
        return deepcopy(user)
    return merge_config(defaults, _expand_shortcuts(user))


def _difference(system, effective, path=()):
    if path == SOURCES_PATH:
        base, selected = _sources(system), _sources(effective)
        result = []
        for identity, source in selected.items():
            if identity not in base or source.get('adapter') != base[identity].get('adapter'):
                result.append(source)
            elif source != base[identity]:
                result.append(dict(_difference(base[identity], source, path + (identity,)), id=identity))
        result.extend({'id': identity, 'enabled': False} for identity in base if identity not in selected)
        return result
    if isinstance(system, dict) and isinstance(effective, dict):
        return {key: _difference(system[key], value, path + (key,)) if key in system else deepcopy(value)
                for key, value in effective.items() if key not in system or system[key] != value}
    return deepcopy(effective)


def render(value):
    required = {'schema_version', 'workbench_id'} | set(GENERATED_FILES)
    if set(value) != required or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise store.OfflineError('配置字段无效，请参照 config/system.yaml 和用户模板')
    identity = value['workbench_id']
    if not isinstance(identity, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identity):
        raise store.OfflineError('workbench_id 必须是稳定的字母、数字、下划线或连字符')
    if not isinstance(value['writing_style'], str) or not value['writing_style'].strip():
        raise store.OfflineError('writing_style 不可为空')
    documents = {name: deepcopy(value[name]) for name in GENERATED_FILES if name != 'writing_style'}
    if any(not isinstance(document, dict) for document in documents.values()):
        raise store.OfflineError('各配置部分须为 YAML 映射')
    documents['research']['discovery']['sources'] = [
        {key: field for key, field in source.items() if key != 'enabled'}
        for source in _sources(documents['research']['discovery']['sources']).values()
        if source.get('enabled', True)]
    topics = documents['research_topics'].get('topics')
    if (not isinstance(topics, dict) or not topics or any(
            not isinstance(topic, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*', topic)
            for topic in topics)):
        raise store.OfflineError('主题 ID 无效')
    documents['confirmation']['workbench_id'] = identity
    documents['insight'].setdefault('runtime', {})['workbench_id'] = identity
    # These references are generated internally, never another editable entry.
    for name in ('research', 'insight'):
        documents[name]['topics_file'] = GENERATED_FILES['research_topics']
    documents['automation']['cycle_config'] = GENERATED_FILES['research']
    documents['automation']['admission_config'] = GENERATED_FILES['admission']
    documents['confirmation']['writing']['style_profile'] = GENERATED_FILES['writing_style']
    output = {GENERATED_FILES[name]: _yaml(document) for name, document in documents.items()}
    output[GENERATED_FILES['writing_style']] = value['writing_style'].encode('utf-8')
    legacy = deepcopy(documents['confirmation'])
    legacy['writing'].pop('style_profile', None)
    output['config/confirmation.yaml'] = _yaml(legacy)
    # Use existing parsers in a scratch directory before touching real settings.
    with tempfile.TemporaryDirectory(prefix='researchdesk-config-') as temporary:
        scratch = Path(temporary).resolve()
        for relative, payload in output.items():
            _write(scratch / relative, payload)
        import cycle
        import harness
        import confirmation
        import runner
        import schedule
        import batch
        import writing_admission
        cycle.load_config(scratch, GENERATED_FILES['research'])
        harness.load_config(scratch, GENERATED_FILES['insight'])
        confirmation.load_config(scratch)
        runner.load_config(scratch)
        schedule.load_config(scratch)
        batch.membership_monthly_limit(scratch)
        policy = documents['admission']
        if (set(policy) != {'schema_version', 'enabled', 'topics', 'require_independent_review',
                           'preserve_existing_files'} or type(policy['schema_version']) is not int
                or policy['schema_version'] != 1 or type(policy['enabled']) is not bool
                or policy['require_independent_review'] is not True
                or policy['preserve_existing_files'] is not True
                or not isinstance(policy['topics'], list) or not policy['topics']):
            raise store.OfflineError('正式准入配置无效')
        writing_admission._config(scratch, GENERATED_FILES['writing_admission'])
    return output


def _managed(root):
    path = _path(root, MANIFEST)
    if not path.exists():
        return {}
    try:
        result = json.loads(path.read_text())
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, OSError) as exc:
        raise store.OfflineError('生成配置记录无效，保留现有文件') from exc


def apply(root, check_only=False):
    root = Path(root).resolve()
    output = render(load_effective(root))
    managed = _managed(root)
    # Preflight every destination before writing any of them. Direct edits to
    # compatibility files are never silently overwritten, even during repair.
    changes = []
    for relative, payload in output.items():
        path = _path(root, relative)
        if path.exists():
            before = path.read_bytes()
            actual = _hash(before)
            if actual == _hash(payload):
                continue
            if managed.get(relative) != actual:
                raise store.OfflineError('兼容配置被手工修改，请先合入统一配置: ' + relative)
            if relative.endswith('.yaml') and _read(path) == yaml.safe_load(payload):
                # Preserve existing formatting/comments and historical hashes.
                continue
        changes.append((relative, payload))
    if check_only:
        if changes:
            raise store.OfflineError('本地配置尚未应用，请执行 apply')
    else:
        for relative, payload in changes:
            _write(_path(root, relative), payload)
        _write(_path(root, MANIFEST), json.dumps(
            {relative: _hash(_path(root, relative).read_bytes()) for relative in output}, indent=2).encode())
    return {'status': 'valid' if check_only else 'configured', 'config': LOCAL_CONFIG,
            'system_config': SYSTEM_CONFIG,
            'generated_files': len(output), 'model_calls': 0}


def initialize(root, adopt_existing=False):
    root = Path(root).resolve()
    local = _path(root, LOCAL_CONFIG)
    if local.exists():
        if adopt_existing:
            raise store.OfflineError('本地统一配置已存在，不覆盖；请编辑该文件后 apply')
        result = apply(root)
        _initialize_storage(root, load_effective(root))
        return result
    template = root / TEMPLATE
    template = template if template.is_file() else REPOSITORY / TEMPLATE
    value = load_effective(root, _read(template))
    existing = {name: _path(root, relative) for name, relative in GENERATED_FILES.items()
                if _path(root, relative).exists()}
    if existing and not adopt_existing:
        raise store.OfflineError('已有配置，请用 init --adopt-existing 保留并导入；不会清空用量或研究资料')
    if adopt_existing:
        for name, path in existing.items():
            value[name] = path.read_text() if name == 'writing_style' else _read(path)
        if 'insight' not in existing and (root / 'config/examples/codex-insight.yaml').is_file():
            value['insight'] = _read(root / 'config/examples/codex-insight.yaml')
        value['workbench_id'] = value['confirmation'].pop('workbench_id', value['workbench_id'])
        value['insight'].get('runtime', {}).pop('workbench_id', None)
    output = render(value)
    # Adoption must not change even whitespace in existing configuration files:
    # old research/confirmation snapshots may depend on those exact bytes.
    for relative, payload in list(output.items()):
        path = _path(root, relative)
        if not path.exists():
            continue
        equal = (path.read_text() == payload.decode() if relative.endswith('.md')
                 else _read(path) == yaml.safe_load(payload))
        if not equal:
            raise store.OfflineError('现有配置与统一入口不一致，需先人工合并，未写入: ' + relative)
        output[relative] = path.read_bytes()
    if adopt_existing:
        patch = _difference(_defaults(root), value)
        patch['schema_version'] = 1
        patch['workbench_id'] = value['workbench_id']
        if render(load_effective(root, patch)) != render(value):
            # Preserve unusual legacy source order that an ID merge cannot express.
            patch = value
        _write(local, _yaml(patch))
    else:
        _write(local, template.read_bytes())
    # Preserve byte-for-byte legacy configurations while recording ownership.
    for relative, payload in output.items():
        path = _path(root, relative)
        if not path.exists():
            _write(path, payload)
    _write(_path(root, MANIFEST), json.dumps(
        {relative: _hash(payload) for relative, payload in output.items()}, indent=2).encode())
    _initialize_storage(root, value)
    return {'status': 'adopted' if adopt_existing else 'initialized', 'config': LOCAL_CONFIG,
            'existing_usage_preserved': True, 'model_calls': 0}


def migrate(root):
    """Compact an old complete file without changing any active inputs/state."""
    root = Path(root).resolve()
    local = _path(root, LOCAL_CONFIG)
    user = _read(local)
    apply(root, check_only=True)
    if not _legacy_complete(user):
        return {'status': 'already_layered', 'config': LOCAL_CONFIG, 'model_calls': 0}
    effective = load_effective(root, user)
    patch = _difference(_defaults(root), effective)
    patch['schema_version'] = 1
    patch['workbench_id'] = effective['workbench_id']
    if render(load_effective(root, patch)) != render(effective):
        raise store.OfflineError('旧来源顺序无法无损压缩，保留原配置，可继续使用')
    backup = _path(root, MIGRATION_BACKUP)
    payload = local.read_bytes()
    if backup.exists() and backup.read_bytes() != payload:
        raise store.OfflineError('已存在不同的迁移备份，保留所有文件')
    if not backup.exists():
        _write(backup, payload)
    _write(local, _yaml(patch))
    return {'status': 'migrated', 'config': LOCAL_CONFIG, 'backup': MIGRATION_BACKUP, 'model_calls': 0}


def _initialize_storage(root, value):
    state = _path(root, STATE)
    if not state.exists():
        _write(state, _yaml({'schema_version': 1, 'usage_months': {}, 'selected_identity_keys': []}))
    for topic in value['research_topics']['topics']:
        for directory in ('collection', 'summary', 'insights', 'articles'):
            target = _path(root, directory + '/' + topic)
            target.mkdir(parents=True, exist_ok=True)


def start(root):
    """Register/start this host after the user has completed both sign-ins.

    This command never signs in, performs inference, changes the operator's
    research switch, or relocates existing research and membership records.
    """
    import runner
    from membership import MembershipClient

    root = Path(root).resolve()
    initialize(root)
    if platform.system() != 'Darwin':
        raise store.OfflineError('one_command_start_requires_macos_for_codex')
    config = runner.load_config(root)
    if 'researchdesk' not in config['runner']['labels']:
        raise store.OfflineError('runner_requires_researchdesk_label')
    effective = load_effective(root)
    client = MembershipClient(config['_profile'], root)
    authorization = client.status()
    if authorization.get('authenticated') is not True or authorization.get('plan_permission') is not True:
        raise store.OfflineError('chatgpt_login_and_plan_permission_required')
    catalog = client.models()
    selected = set(effective['research']['models'].values()) | set(effective['insight']['models'].values())
    selected |= set(effective['confirmation']['writing']['models'].values())
    if not selected.issubset({entry['slug'] for entry in catalog}):
        raise store.OfflineError('configured_models_unavailable_for_current_account')
    runner._run(['gh', 'auth', 'status', '--hostname', 'github.com'], root, 'github_login_required')
    repository = runner._repository(root)
    metadata = runner._api(root, 'repos/' + repository)
    if metadata.get('permissions', {}).get('admin') is not True:
        raise store.OfflineError('github_repository_runner_admin_permission_required')

    def sdk_preflight():
        result = runner._run([
            str(config['_venv'] / 'bin/python'), str(root / 'scripts/harness.py'),
            'preflight', '--root', str(root), '--config', GENERATED_FILES['insight']],
            root, 'configured_codex_preflight_failed')
        try:
            status = yaml.safe_load(result.stdout)
        except yaml.YAMLError:
            raise runner.RunnerError('configured_codex_preflight_invalid') from None
        if not isinstance(status, dict) or status.get('live_ready') is not True:
            raise runner.RunnerError('configured_codex_runtime_not_ready')

    result = runner.setup(root, config, pre_start=sdk_preflight)
    if result['runner'].get('registered') is not True or result['runner'].get('service') != 'running':
        raise runner.RunnerError('runner_service_not_ready')
    # The first successful deployment begins the catch-up horizon. A shared
    # template's historic activated_at must not spend calls on pre-install slots.
    # Persist it before opening the remote gate, including a cron/start race.
    started = _path(root, 'config/local/deployment-started-at.json')
    created_start = not started.exists()
    if created_start:
        descriptor = os.open(started, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump({'started_at': datetime.now(timezone.utc).isoformat()}, handle)
    # The sole remote value is this non-sensitive boolean; neither personal
    # configuration nor credential/path data leaves the execution host.
    try:
        runner._run(['gh', 'variable', 'set', 'RESEARCHDESK_DEPLOYED', '--repo', repository,
                     '--body', 'true'], root, 'github_deployment_gate_activation_failed')
    except Exception:
        if created_start:
            started.unlink()
        raise
    return {'status': 'started', 'runner': result['runner'],
            'config': LOCAL_CONFIG, 'system_config': SYSTEM_CONFIG,
            'research_enabled': effective['automation']['enabled'],
            'schedule_utc': effective['automation']['schedule_utc'],
            'configuration_reload': 'before_each_run',
            'github_deployment_gate': True,
            'workbench_binding': 'persistent_current_directory', 'model_calls': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPOSITORY)
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('init').add_argument('--adopt-existing', action='store_true')
    commands.add_parser('apply')
    commands.add_parser('check')
    commands.add_parser('migrate')
    commands.add_parser('start', help='应用配置、校验授权并注册启动执行器；保留用户研究开关')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'init':
            result = initialize(args.root, args.adopt_existing)
        elif args.operation == 'migrate':
            result = migrate(args.root)
        elif args.operation == 'start':
            result = start(args.root)
        else:
            result = apply(args.root, check_only=args.operation == 'check')
    except (store.OfflineError, OSError, ValueError, KeyError, TypeError) as exc:
        print('工作台配置停止：' + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # Network/provider or process failures can contain account data. Runner
        # errors deliberately expose fixed codes only; all other details stay local.
        import runner
        message = str(exc) if isinstance(exc, runner.RunnerError) else 'workbench_start_failed'
        print('工作台启动停止：' + message, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
