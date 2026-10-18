#!/usr/bin/env python3
"""Strict fictional inputs and explicit confirmation for offline Writing tests.

This module cannot approve an Insight result or access a membership backend.
It only reads a named fictional fixture and a matching test confirmation.
"""

import json
from pathlib import Path
import re

import researchdesk_offline as store
import researchdesk_batch_inputs as common


STAGES = ('outline', 'draft', 'candidate')
HASH = re.compile(r'[0-9a-f]{64}\Z')
UNSAFE_REFERENCE = re.compile(
    r'(?:[a-z][a-z0-9+.-]*://|(?:^|[\s(\["\'])(?:sources|reports|insights|articles|config|workflows)/|'
    r'(?:^|[\s(\["\'])/(?:Users|home|private|tmp|etc|var)/|[A-Za-z]:\\)', re.I)


def _fields(value, expected, name):
    common.fields(value, expected, name)


def _text(value, name, maximum=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise store.OfflineError(name + ' 必须是有界的非空文本')


def _strings(value, name, minimum=1, maximum=20):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise store.OfflineError(name + ' 必须是有界文本列表')
    for item in value:
        _text(item, name)


def _path(root, relative, expected_prefix, name, must_exist=True):
    if not isinstance(relative, str) or not relative:
        raise store.OfflineError(name + ' 必须是明确相对路径')
    path = Path(relative)
    prefix = tuple(expected_prefix)
    if (path.is_absolute() or '..' in path.parts or '\\' in relative
            or path.as_posix() != relative or path.parts[:len(prefix)] != prefix
            or len(path.parts) != len(prefix) + 1 or path.suffix != '.yaml'
            or not store.SAFE_ID.fullmatch(path.stem)):
        raise store.OfflineError(name + ' 必须位于本主题指定测试目录')
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise store.OfflineError(name + ' 不可包含符号链接')
    if must_exist and not current.is_file():
        raise store.OfflineError(name + ' 不存在')
    if current.exists() and not current.is_file():
        raise store.OfflineError(name + ' 必须是普通文件')
    if not current.resolve().is_relative_to(root):
        raise store.OfflineError(name + ' 超出选定工作台')
    return current


def _reject_references(value):
    if isinstance(value, str):
        if (UNSAFE_REFERENCE.search(value) or re.search(r'\[[^\]]*\]\([^)]*\)', value)
                or re.search(r'\[\[[^\]]+\]\]', value)):
            raise store.OfflineError('离线 Writing fixture 不得包含真实 URL 或文件引用')
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_references(key)
            _reject_references(item)
    elif isinstance(value, list):
        for item in value:
            _reject_references(item)


def load_config(root, path):
    root = Path(root).resolve()
    path = common.config_path(root, path)
    config = store.load_yaml(path)
    _fields(config, {'schema_version', 'mode', 'backend', 'topic', 'topics_file', 'models',
                     'budget', 'fixture', 'confirmation'}, '离线 Writing 配置')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise store.OfflineError('Writing 配置仅支持 schema_version: 1')
    if config['mode'] != 'writing_offline_test' or config['backend'] != 'mock':
        raise store.OfflineError('Writing 目前仅支持显式 mock 的 writing_offline_test')
    topic = config['topic']
    if (not isinstance(topic, str) or not store.SAFE_ID.fullmatch(topic)
            or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', topic)):
        raise store.OfflineError('研究主题必须是稳定的小写 ID')
    if (not isinstance(config['topics_file'], str) or Path(config['topics_file']).is_absolute()
            or Path(config['topics_file']).as_posix() != config['topics_file']):
        raise store.OfflineError('topics_file 必须是 config 下的规范相对路径')
    topics_path = common.config_path(root, config['topics_file'])
    topics = store.load_yaml(topics_path)
    if (type(topics.get('schema_version')) is not int or topics['schema_version'] != 1
            or not isinstance(topics.get('topics'), dict)):
        raise store.OfflineError('研究方向 YAML 无效')
    selected = topics['topics'].get(topic)
    if not isinstance(selected, dict) or selected.get('enabled') is not True:
        raise store.OfflineError('研究主题不存在或已停用')
    for key in ('name', 'description'):
        _text(selected.get(key), '研究方向 ' + key)
    for key in ('scope', 'keywords'):
        _strings(selected.get(key), '研究方向 ' + key)
    _fields(config['models'], {'writing', 'review'}, 'Writing 模型')
    if any(not isinstance(model, str) or not re.fullmatch(r'mock-[a-z0-9][a-z0-9-]{0,80}', model)
           for model in config['models'].values()):
        raise store.OfflineError('Writing 只允许明确的 mock-* 模型，无真实后端')
    if config['models']['writing'] == config['models']['review']:
        raise store.OfflineError('模拟写作和独立审阅必须使用不同模型')
    ranges = {'max_calls': (2, 12), 'max_calls_per_stage': (2, 4), 'max_revisions': (0, 1),
              'max_input_chars': (1000, 30000), 'max_output_chars': (1000, 12000)}
    _fields(config['budget'], ranges, 'Writing 预算')
    for key, (low, high) in ranges.items():
        common.positive(config['budget'][key], low, high, key)
    if config['budget']['max_calls'] > len(STAGES) * config['budget']['max_calls_per_stage']:
        raise store.OfflineError('总请求上限超过三阶段请求上限之和')
    _fields(config['fixture'], {'path', 'sha256'}, 'Writing fixture')
    fixture_path = _path(root, config['fixture']['path'], ('workflows', 'test', topic, 'fixtures'), 'Writing fixture')
    if not isinstance(config['fixture']['sha256'], str) or not HASH.fullmatch(config['fixture']['sha256']):
        raise store.OfflineError('Writing fixture 必须显式固定 SHA-256')
    if fixture_path.stat().st_size > 250000 or store.digest(fixture_path.read_bytes()) != config['fixture']['sha256']:
        raise store.OfflineError('Writing fixture 超过界限或与登记 SHA-256 不一致')
    if config['confirmation'] is not None:
        _path(root, config['confirmation'], ('reports', 'test', topic, 'writing-approvals'), 'Writing 确认', False)
    config.update(_config_path=path.relative_to(root).as_posix(), _config_sha256=store.digest(path.read_bytes()),
                  _topics_path=topics_path.relative_to(root).as_posix(), _topics_sha256=store.digest(topics_path.read_bytes()),
                  topic_name=selected['name'], topic_scope=selected['scope'], topic_keywords=selected['keywords'])
    return config


def _candidate(value, evidence_ids):
    _fields(value, {'title', 'summary', 'sections', 'limitations'}, '模拟阶段候选')
    _text(value['title'], '候选标题')
    _text(value['summary'], '候选摘要')
    _strings(value['limitations'], '候选局限')
    if not isinstance(value['sections'], list) or not 1 <= len(value['sections']) <= 10:
        raise store.OfflineError('候选必须有 1–10 个章节')
    for section in value['sections']:
        _fields(section, {'heading', 'paragraphs'}, '候选章节')
        _text(section['heading'], '章节标题')
        if not isinstance(section['paragraphs'], list) or not 1 <= len(section['paragraphs']) <= 20:
            raise store.OfflineError('章节必须有有界段落')
        for paragraph in section['paragraphs']:
            _fields(paragraph, {'kind', 'text', 'evidence_ids'}, '候选段落')
            if paragraph['kind'] not in {'fact', 'author_claim', 'inference', 'analogy'}:
                raise store.OfflineError('段落须区分事实、作者主张、推断和类比')
            _text(paragraph['text'], '段落正文')
            _strings(paragraph['evidence_ids'], '段落证据')
            if (len(set(paragraph['evidence_ids'])) != len(paragraph['evidence_ids'])
                    or set(paragraph['evidence_ids']) - evidence_ids):
                raise store.OfflineError('段落引用未知或重复证据')


def _review(value, evidence_ids):
    _fields(value, {'decision', 'coverage_acknowledged', 'issues', 'checks'}, '模拟独立审阅')
    if value['decision'] not in {'pass', 'revise', 'reject', 'blocked'} or type(value['coverage_acknowledged']) is not bool:
        raise store.OfflineError('模拟审阅状态或范围确认无效')
    if not isinstance(value['issues'], list) or len(value['issues']) > 20:
        raise store.OfflineError('审阅问题必须为有界列表')
    for issue in value['issues']:
        _fields(issue, {'severity', 'location', 'reason', 'suggestion'}, '审阅问题')
        if issue['severity'] not in {'info', 'warning', 'blocking', 'critical', 'error'}:
            raise store.OfflineError('未知审阅严重程度')
        for key in ('location', 'reason', 'suggestion'):
            _text(issue[key], '审阅问题 ' + key)
    if not isinstance(value['checks'], list) or len(value['checks']) > 200:
        raise store.OfflineError('逐段核查必须为有界列表')
    for check in value['checks']:
        _fields(check, {'section_index', 'paragraph_index', 'verdict', 'evidence_ids'}, '逐段核查')
        for key in ('section_index', 'paragraph_index'):
            common.positive(check[key], 0, 199, key)
        if check['verdict'] not in {'supported', 'unsupported'}:
            raise store.OfflineError('未知证据支持决定')
        _strings(check['evidence_ids'], '审阅证据')
        if set(check['evidence_ids']) - evidence_ids or len(set(check['evidence_ids'])) != len(check['evidence_ids']):
            raise store.OfflineError('审阅引用未知或重复证据')


def read_fixture(root, config):
    root = Path(root).resolve()
    path = _path(root, config['fixture']['path'], ('workflows', 'test', config['topic'], 'fixtures'), 'Writing fixture')
    if path.stat().st_size > 250000 or store.digest(path.read_bytes()) != config['fixture']['sha256']:
        raise store.OfflineError('Writing fixture 在加载后改变')
    fixture = store.load_yaml(path)
    _fields(fixture, {'schema_version', 'origin', 'topic', 'topic_card', 'evidence', 'responses', 'reviews'}, 'Writing fixture')
    if (type(fixture['schema_version']) is not int or fixture['schema_version'] != 1
            or fixture['origin'] != 'offline_fixture' or fixture['topic'] != config['topic']):
        raise store.OfflineError('Writing 仅接受同主题全虚构 offline_fixture')
    _reject_references(fixture)
    card = fixture['topic_card']
    _fields(card, {'id', 'title', 'angle', 'audience', 'status', 'approval_required', 'writing_started', 'publish_authorized'}, '虚构选题卡')
    if not isinstance(card['id'], str) or not store.SAFE_ID.fullmatch(card['id']):
        raise store.OfflineError('虚构选题 ID 无效')
    for key in ('title', 'angle', 'audience'):
        _text(card[key], '选题 ' + key)
    if (card['status'] != 'proposed' or card['approval_required'] is not True
            or card['writing_started'] is not False or card['publish_authorized'] is not False):
        raise store.OfflineError('fixture 只能提供待确认且未启动写作/发布的虚构选题')
    if not isinstance(fixture['evidence'], list) or not 1 <= len(fixture['evidence']) <= 20:
        raise store.OfflineError('fixture 必须包含有界虚构证据')
    ids = set()
    for evidence in fixture['evidence']:
        _fields(evidence, {'id', 'kind', 'text', 'coverage', 'source_label'}, '虚构证据')
        if (not isinstance(evidence['id'], str) or not re.fullmatch(r'E[1-9][0-9]{0,2}', evidence['id'])
                or evidence['id'] in ids or evidence['coverage'] != 'fixture'
                or evidence['kind'] not in {'fact', 'author_claim', 'inference'}):
            raise store.OfflineError('虚构证据身份、类型或范围无效')
        ids.add(evidence['id'])
        _text(evidence['text'], '虚构证据正文')
        _text(evidence['source_label'], '虚构来源标签')
    for key in ('responses', 'reviews'):
        _fields(fixture[key], STAGES, '模拟 ' + key)
    for stage in STAGES:
        responses, reviews = fixture['responses'][stage], fixture['reviews'][stage]
        if (not isinstance(responses, list) or not isinstance(reviews, list)
                or not 1 <= len(responses) <= 2 or len(responses) != len(reviews)):
            raise store.OfflineError('每个阶段必须有 1–2 组固定候选及审阅响应')
        for candidate, review in zip(responses, reviews):
            _candidate(candidate, ids)
            _review(review, ids)
    return fixture


def _confirmation(root, config, fixture, input_fingerprint):
    relative = config['confirmation']
    if relative is None:
        raise store.OfflineError('须先明确确认虚构选题、角度、受众与写作范围，不能自动批准真实选题')
    path = _path(root, relative, ('reports', 'test', config['topic'], 'writing-approvals'), 'Writing 确认')
    revoked = path.with_name(path.stem + '.revoked.yaml')
    # The marker path is intentionally not a confirmation ID; safe_path still
    # enforces every directory and rejects symlinks before reading its checksum.
    marker = store.safe_path(root, revoked.relative_to(root).as_posix())
    if marker.exists():
        revocation = store.checked_yaml(root, marker.relative_to(root))
        _fields(revocation, {'schema_version', 'mode', 'confirmation_id', 'confirmation_sha256', 'reason'}, '虚构确认撤回')
        if (type(revocation['schema_version']) is not int or revocation['schema_version'] != 1
                or revocation['mode'] != 'writing_fixture_revocation'
                or revocation['confirmation_id'] != path.stem
                or revocation['confirmation_sha256'] != store.digest(path.read_bytes())):
            raise store.OfflineError('撤回记录与该虚构确认不一致，保留现场并停止')
        _text(revocation['reason'], '撤回原因')
        raise store.OfflineError('该虚构写作确认已撤回，不得继续或重用旧结果')
    value = store.checked_yaml(root, relative)
    _fields(value, {'schema_version', 'mode', 'id', 'origin', 'topic', 'topic_card_id',
        'topic_card_sha256', 'fixture_sha256', 'input_fingerprint', 'decision', 'title', 'angle', 'audience',
        'target_words', 'writing_scope', 'writing_authorized', 'production_accepted', 'publish_authorized'}, '虚构写作确认')
    card = fixture['topic_card']
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['mode'] != 'writing_fixture_confirmation' or value['id'] != path.stem
            or value['origin'] != 'offline_fixture' or value['topic'] != config['topic']
            or value['topic_card_id'] != card['id'] or value['topic_card_sha256'] != store.digest(card)
            or value['fixture_sha256'] != config['fixture']['sha256']
            or value['input_fingerprint'] != input_fingerprint
            or value['production_accepted'] is not False or value['publish_authorized'] is not False):
        raise store.OfflineError('虚构写作确认的主题、选题、fixture 或范围绑定不一致')
    for key in ('title', 'angle', 'audience'):
        if value[key] != card[key]:
            raise store.OfflineError('确认的选题、角度和受众必须与当前虚构选题卡一致')
    common.positive(value['target_words'], 200, 5000, 'target_words')
    if value['writing_scope'] != list(STAGES):
        raise store.OfflineError('确认只允许 outline、draft、candidate 三阶段测试范围')
    if value['decision'] not in {'confirmed', 'pending', 'rejected', 'withdrawn'}:
        raise store.OfflineError('未知写作确认状态')
    if value['writing_authorized'] is not (value['decision'] == 'confirmed'):
        raise store.OfflineError('确认状态与写作授权必须严格一致')
    if value['decision'] != 'confirmed':
        raise store.OfflineError('该虚构选题尚未确认或已经拒绝/撤回')
    return value, store.digest(path.read_bytes())


def prepare_bundle(root, config):
    root = Path(root).resolve()
    if load_config(root, config['_config_path']) != config:
        raise store.OfflineError('Writing 配置或研究方向在准备输入前改变')
    fixture = read_fixture(root, config)
    fingerprint = store.digest({'topic_card': fixture['topic_card'], 'evidence': fixture['evidence']})
    confirmation, confirmation_sha = _confirmation(root, config, fixture, fingerprint)
    material = {'topic': config['topic'], 'topic_card': fixture['topic_card'], 'evidence': fixture['evidence'],
                'confirmation': confirmation}
    if len(json.dumps(material, ensure_ascii=False)) > config['budget']['max_input_chars']:
        raise store.OfflineError('确认及证据包超过输入预算，不截断虚构证据')
    return {'topic': config['topic'], 'topic_card': fixture['topic_card'], 'evidence': fixture['evidence'],
            'responses': fixture['responses'], 'reviews': fixture['reviews'], 'fixture_sha256': config['fixture']['sha256'],
            'topic_card_sha256': store.digest(fixture['topic_card']), 'input_fingerprint': fingerprint,
            'confirmation': confirmation, 'confirmation_sha256': confirmation_sha,
            'confirmation_path': config['confirmation']}
