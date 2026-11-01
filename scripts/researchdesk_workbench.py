#!/usr/bin/env python3
"""Initialize a private workbench; no login, inference, Git writes or scheduling."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import yaml

import researchdesk_offline as store


REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATE = 'config/workbench.example.yaml'
LOCAL_CONFIG = 'config/local/workbench.yaml'
MANIFEST = 'config/local/generated.json'
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


def render(value):
    required = {'schema_version', 'workbench_id'} | set(GENERATED_FILES)
    if set(value) != required or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise store.OfflineError('统一配置字段无效，请参照 workbench.example.yaml')
    identity = value['workbench_id']
    if not isinstance(identity, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identity):
        raise store.OfflineError('workbench_id 必须是稳定的字母、数字、下划线或连字符')
    if not isinstance(value['writing_style'], str) or not value['writing_style'].strip():
        raise store.OfflineError('writing_style 不可为空')
    documents = {name: deepcopy(value[name]) for name in GENERATED_FILES if name != 'writing_style'}
    if any(not isinstance(document, dict) for document in documents.values()):
        raise store.OfflineError('各配置部分须为 YAML 映射')
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
        import researchdesk_cycle as cycle
        import researchdesk_harness as harness
        import researchdesk_confirmation as confirmation
        import researchdesk_runner as runner
        import researchdesk_schedule as schedule
        import researchdesk_batch as batch
        import researchdesk_writing_admission as writing_admission
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
    output = render(_read(_path(root, LOCAL_CONFIG)))
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
            'generated_files': len(output), 'model_calls': 0}


def initialize(root, adopt_existing=False):
    root = Path(root).resolve()
    local = _path(root, LOCAL_CONFIG)
    if local.exists():
        if adopt_existing:
            raise store.OfflineError('本地统一配置已存在，不覆盖；请编辑该文件后 apply')
        result = apply(root)
        _initialize_storage(root, _read(local))
        return result
    template = root / TEMPLATE
    template = template if template.is_file() else REPOSITORY / TEMPLATE
    value = _read(template)
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
    _write(local, _yaml(value) if adopt_existing else template.read_bytes())
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


def _initialize_storage(root, value):
    state = _path(root, STATE)
    if not state.exists():
        _write(state, _yaml({'schema_version': 1, 'usage_months': {}, 'selected_identity_keys': []}))
    for topic in value['research_topics']['topics']:
        for directory in ('collection', 'summary', 'insights', 'articles'):
            target = _path(root, directory + '/' + topic)
            target.mkdir(parents=True, exist_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPOSITORY)
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('init').add_argument('--adopt-existing', action='store_true')
    commands.add_parser('apply')
    commands.add_parser('check')
    args = parser.parse_args(argv)
    try:
        result = (initialize(args.root, args.adopt_existing) if args.operation == 'init'
                  else apply(args.root, check_only=args.operation == 'check'))
    except (store.OfflineError, OSError, ValueError, KeyError, TypeError) as exc:
        print('工作台配置停止：' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
