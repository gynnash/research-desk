"""Read-only, offline proof and frozen previews for real topic confirmation.

Only an existing formal admission can supply a topic. This module never fetches
sources, creates admission plans, confirms a user choice, or invokes a model.
The confirmation service owns sessions, one-time nonces, Git and event writes.
"""

from pathlib import Path
import re

import researchdesk_note_paths as note_paths
import researchdesk_offline as store
import researchdesk_admission as admission


HASH = re.compile(r'[0-9a-f]{64}\Z')
TOPIC = re.compile(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*\Z')


def _path(root, relative, formal=False):
    if Path(relative).parts[:1] == ('config',):
        from researchdesk_confirmation import configuration_path
        path = configuration_path(root, relative)
    else:
        path = admission._location(root, relative)
    if not path.is_file():
        raise store.OfflineError('确认输入不存在: ' + relative)
    if formal and ('test' in Path(relative).parts or path.suffix != '.md'
                   or Path(relative).parts[0] not in {'sources', 'reports', 'insights', 'articles', 'collection', 'summary'}):
        raise store.OfflineError('选题预览只接受正式 Markdown 证据')
    return path


def _text(value, name, maximum=5000):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 and char not in '\n\t' for char in value)):
        raise store.OfflineError(name + ' 必须是有界非空文本')
    return value.strip()


def _config(root, config):
    relative, expected = config.get('_config_path'), config.get('_config_sha256')
    if (not isinstance(relative, str) or Path(relative).parts[:1] != ('config',)
            or not isinstance(expected, str) or not HASH.fullmatch(expected)):
        raise store.OfflineError('确认配置必须绑定 config 下的实际文件散列')
    if store.digest(_path(root, relative).read_bytes()) != expected:
        raise store.OfflineError('确认配置已变化，请重新加载并预览')
    topics = config.get('topics')
    if (not isinstance(topics, list) or not topics or len(set(topics)) != len(topics)
            or any(not isinstance(topic, str) or not TOPIC.fullmatch(topic) for topic in topics)):
        raise store.OfflineError('确认配置缺少有效研究方向')
    writing = config.get('writing')
    if not isinstance(writing, dict) or writing.get('backend') != 'chatgpt_plan':
        raise store.OfflineError('真实选题只允许配置官方会员 Writing 后端')
    models = writing.get('models', {})
    if (set(models) != {'writing', 'review'} or len(set(models.values())) != 2
            or any(not isinstance(value, str) or not value or value.startswith('mock-')
                   for value in models.values())):
        raise store.OfflineError('写作与独立审阅必须指定不同的真实模型')
    return config


def style_profile(root, writing):
    """Load a bounded, ordinary Markdown profile; absence retains v1 bytes."""
    relative = writing.get('style_profile')
    if relative is None and 'style_profile' not in writing:
        return None
    if (not isinstance(relative, str) or Path(relative).parts[:1] != ('config',)
            or Path(relative).suffix != '.md'):
        raise store.OfflineError('作者风格必须使用 config 下的 Markdown 文件')
    target = _path(root, relative)
    if target.stat().st_size > 50000:
        raise store.OfflineError('作者风格文件过大')
    payload = target.read_bytes()
    profile = {'version': 'writing-v2', 'path': relative,
               'sha256': store.digest(payload), 'text': payload.decode('utf-8')}
    from researchdesk_writing_style import validate_profile
    validate_profile(profile)
    return profile


def frozen_config(root, current, payload):
    """Historical page approvals keep their explicitly bound configuration."""
    relative = payload.get('config', {}).get('path')
    if (not isinstance(relative, str) or Path(relative).parts[:1] != ('config',)
            or Path(relative).suffix not in {'.yaml', '.yml'}):
        raise store.OfflineError('历史确认必须绑定 config 下的写作配置')
    if relative == current['_config_path']:
        return current
    from researchdesk_confirmation import load_config
    frozen = load_config(root, relative)
    if (frozen['workbench_id'] != current['workbench_id']
            or payload.get('topic') not in current['topics']
            or payload.get('topic') not in frozen['topics']):
        raise store.OfflineError('历史确认配置不属于当前工作台及研究方向')
    return frozen


def _original_excerpts(root, value, item, max_chars=2400):
    """Select only text already bound to this reviewed Research evidence."""
    if item['origin'] != 'reviewed_research':
        return [], '人工历史基线不提供已核验原文，不能升级为原始事实。', {}
    provenance = value['verification_bundle']['provenance']['research_inputs']
    matched = [entry for entry in provenance if entry['id'] == item['id']]
    if len(matched) != 1:
        raise store.OfflineError('原文节选缺少唯一 Research 绑定')
    proof = matched[0]
    candidate_path = proof['candidate_path']
    candidate_bytes = _path(root, candidate_path).read_bytes()
    if store.digest(candidate_bytes) != proof['candidate_sha256']:
        raise store.OfflineError('原文对应 Research 候选已变化')
    candidate = store.checked_yaml(root, candidate_path)['candidate']
    if candidate['evidence']['locators'] != item.get('locators', []):
        raise store.OfflineError('原文定位与已审阅 Research 不同')
    chunks, bindings, archive_path, archive_sha = {}, {}, None, None
    if 'archive' in candidate:
        import researchdesk_archive as archive
        _, material, snapshot = archive.load(root, candidate)
        if store.digest(material.encode()) != proof['original_material_sha256']:
            raise store.OfflineError('归档不是该 Research 实际阅读材料')
        # The archive may be longer than the reviewed material. Slice only the
        # exact locator offsets and hashes used by Research, never new sections.
        sections = {entry['id']: entry for entry in (snapshot.get('document') or {}).get('sections', [])}
        for locator in item.get('locators', []):
            section = sections.get(locator.get('section_id'))
            offsets = re.search(r'; chars ([0-9]+)-([0-9]+)$', locator.get('location', ''))
            if section and offsets:
                start, end = map(int, offsets.groups())
                chunk = section['text'][start - 1:end]
                if store.digest(chunk.encode()) != locator.get('text_sha256'):
                    raise store.OfflineError('原文节选与 Research 定位散列不同')
                chunks[locator['id']] = chunk
            elif not sections:
                match = re.search(r'(?:^|\n)' + re.escape(locator['id']) +
                                  r': (.*?)(?=\nA[0-9]+: |\Z)', material, re.S)
                if match and store.digest(match.group(1).encode()) == locator.get('text_sha256'):
                    chunks[locator['id']] = match.group(1)
        # Legacy sentence material has no section offsets. The immutable quote
        # remains useful without pretending that it is a complete paragraph.
        for relative in (candidate['archive']['path'], candidate['archive']['path'] + '.sha256',
                         candidate['archive']['markdown_path']):
            bindings[relative] = store.digest(_path(root, relative).read_bytes())
        formal = archive.relative_path(dict(candidate, source_id=value['source_id_map'].get(candidate['source_id'], candidate['source_id'])))
        if formal not in value['files']:
            raise store.OfflineError('原文归档尚未正式准入')
        expected = admission.effective_files(root, value)[formal]
        archived = _path(root, formal, formal=True).read_bytes()
        if archived != expected.encode():
            raise store.OfflineError('正式原文归档已变化')
        archive_path, archive_sha = formal, store.digest(archived)
        bindings[formal] = archive_sha
    locators = {locator['id']: locator for locator in item.get('locators', [])}
    preferred = list(dict.fromkeys(identifier for claim in item.get('research_claims', [])
                                  for identifier in claim.get('evidence_ids', [])))
    selected, remaining = [], min(2400, max_chars)
    for identifier in preferred:
        locator = locators.get(identifier)
        if locator is None:
            raise store.OfflineError('Research 论点引用未知原文定位')
        text = chunks.get(identifier) or locator.get('quote', '')
        if not text.strip() or remaining <= 0:
            continue
        excerpt = text[:remaining]
        selected.append({'locator_id': identifier, 'location': locator['location'],
                         'text': excerpt, 'reading_scope': item['coverage'],
                         'source_url': item.get('source_url') or next(iter(item.get('source_urls') or []), None),
                         'archive_path': archive_path,
                         'archive_sha256': archive_sha, 'excerpt_only': True})
        remaining -= len(excerpt)
    note = ('仅包含已审阅 Research 论点对应的原文节选，不扩大原阅读范围；不是独立复现实验。' if chunks else
            '无可重建正文归档，仅保留已审阅定位中的短引用；不等于已读取全文。')
    if not selected:
        note = '没有可安全提供的已审阅原文正文；仅使用研究结果并保留原阅读范围。'
    return selected, note, bindings


def _trusted_cycle(root, topic, cycle_id):
    base = admission._base(topic, cycle_id)
    marker = admission._checked(root, base + '/accepted.yaml')
    if marker.get('mode') == 'codex_insight_admission':
        import researchdesk_insight_admission as current
        value = current.load(root, topic, cycle_id)
        return value, value['files']
    # Refuse the creation branch of admission._plan: previews can only read a
    # complete, previously reviewed plan and its accepted marker.
    for relative in (base + '/plan.yaml', base + '/accepted.yaml'):
        _path(root, relative)
        _path(root, relative + '.sha256')
    # Call precisely the cached-plan verifier used by _plan, rather than its
    # create branch. Even a concurrent plan deletion cannot fall into fetching.
    value = admission._verify_plan(root, admission._checked(root, base + '/plan.yaml'), topic, cycle_id)
    accepted = admission._checked(root, base + '/accepted.yaml')
    if accepted != admission._receipt(root, value):
        raise store.OfflineError('正式准入回执没有绑定此计划与独立审阅')
    effective = admission.effective_files(root, value)
    for relative, content in effective.items():
        target = _path(root, relative, formal=True)
        if target.read_bytes() != content.encode('utf-8'):
            raise store.OfflineError('正式证据缺失、已变化或链接修复未完成: ' + relative)
    # _plan checks the complete cached Research/Insight ledger, distinct actual
    # models, final pass, input hashes, history and protected human notes.
    return value, effective


def _topic_entries(root, config):
    seen = set()
    for topic in config['topics']:
        folder = root / 'articles' / topic
        if folder.is_symlink():
            raise store.OfflineError('选题目录不可为符号链接')
        for target in sorted(folder.glob('*.md')):
            relative = target.relative_to(root).as_posix()
            _path(root, relative, formal=True)
            metadata = store.frontmatter(target)
            if not metadata or metadata.get('kind') != 'topic_proposal':
                continue
            identifier = metadata.get('id')
            if not isinstance(identifier, str) or not store.SAFE_ID.fullmatch(identifier):
                continue
            if identifier in seen:
                raise store.OfflineError('正式选题 ID 重复')
            seen.add(identifier)
            if (metadata.get('topic') != topic or metadata.get('topics') != [topic]
                    or metadata.get('status') != 'proposed'
                    or metadata.get('approval_required') is not True
                    or metadata.get('writing_started') is not False
                    or metadata.get('publish_authorized') is not False):
                continue
            match = re.fullmatch(r'(.+)-topic-([1-9][0-9]*)\.md', target.name)
            if not match or not store.SAFE_ID.fullmatch(match.group(1)):
                continue
            yield topic, match.group(1), int(match.group(2)) - 1, relative, metadata


def _load_topic(root, config, topic_id):
    _text(topic_id, '选题 ID', 101)
    found = [entry for entry in _topic_entries(root, config) if entry[4]['id'] == topic_id]
    if len(found) != 1:
        raise store.OfflineError('未找到可确认的正式待选题')
    topic, cycle_id, number, relative, metadata = found[0]
    value, effective = _trusted_cycle(root, topic, cycle_id)
    if relative not in effective:
        raise store.OfflineError('选题不属于此正式准入的有效输出')
    candidates = value['candidate']['topics']
    if not 0 <= number < len(candidates):
        raise store.OfflineError('选题序号不属于原审阅候选')
    card = candidates[number]
    if value.get('mode') == 'codex_insight_admission':
        card = dict(card, evidence_ids=card.get('source_ids') or [item['id'] for item in value['bundle']['sources']])
    expected_id = 'formal-topic-%s-%s-%s' % (topic, cycle_id, number + 1)
    if (metadata['id'] != expected_id or metadata.get('title') != card['title']
            or metadata.get('evidence_ids') != card['evidence_ids']):
        raise store.OfflineError('正式选题与已审阅的结构化候选不同')
    return topic, cycle_id, relative, metadata, value, effective, card


def _source_paths(root, identifiers):
    matches = {}
    wanted = set(identifiers)
    for folder in ('sources/papers', 'sources/blogs'):
        for target in sorted((root / folder).rglob('*.md')):
            relative = target.relative_to(root).as_posix()
            if 'test' in Path(relative).parts or target.name == 'README.md':
                continue
            _path(root, relative, formal=True)
            metadata = store.frontmatter(target)
            if not metadata or metadata.get('id') not in wanted:
                continue
            identifier = metadata['id']
            if identifier in matches:
                raise store.OfflineError('正式来源 ID 重复')
            matches[identifier] = relative
    if set(matches) != wanted:
        raise store.OfflineError('正式来源身份缺失')
    return [matches[identifier] for identifier in identifiers]


def _evidence(root, value, effective, selected, writing_v2=False):
    available = {item['id']: item for item in value['verification_bundle']['evidence']}
    result, original_hashes, remaining_chars = [], {}, 8000
    for identifier in selected:
        if identifier not in available:
            raise store.OfflineError('选题引用未知证据')
        item = available[identifier]
        source_ids = [value['source_id_map'].get(old, old) for old in item['source_ids']]
        source_paths = _source_paths(root, source_ids)
        if item['origin'] == 'reviewed_research':
            expected = source_ids[0]
            reports = [relative for relative in effective
                       if relative.startswith('reports/' + value['topic'] + '/')
                       and store.frontmatter(_path(root, relative)).get('source_id') == expected]
            if len(reports) != 1 or item.get('independently_reviewed') is not True:
                raise store.OfflineError('Research 证据无法映射到唯一正式报告')
            relative = reports[0]
        elif item['origin'] == 'human_baseline':
            relative = item['path']
            if store.digest(_path(root, relative, formal=True).read_bytes()) != item['sha256']:
                raise store.OfflineError('历史基线已变化，请返回 Insight 重新审阅')
        else:
            raise store.OfflineError('选题证据不是正式 Research 或人工历史基线')
        target = _path(root, relative, formal=True)
        metadata = store.frontmatter(target) or {}
        text = target.read_text(encoding='utf-8')
        if re.search(r'^> TEST[:：]', text, re.M) or metadata.get('backend') == 'mock':
            raise store.OfflineError('TEST 或模拟内容不能作为真实写作依据')
        urls = list(item.get('source_urls') or ([item['source_url']] if item.get('source_url') else []))
        result.append({'id': identifier, 'title': item.get('metadata', {}).get('title') or metadata.get('title', identifier),
            'path': relative, 'origin': item['origin'], 'coverage': item['coverage'],
            'source_ids': source_ids, 'source_paths': source_paths, 'source_urls': urls,
            'source_version': item.get('metadata', {}).get('source_version'),
            'independently_reviewed': item.get('independently_reviewed') is True,
            'can_support_original_facts': item.get('can_support_original_facts') is True,
            'sha256': store.digest(target.read_bytes()), 'text': text,
            'summary': item.get('research_summary') or item.get('historical_status') or '原始历史资料，未经本次独立原文审阅。',
            'claims': item.get('research_claims', []), 'limitations': item.get('research_limitations', []),
            'locators': item.get('locators', [])})
        if writing_v2:
            excerpts, note, bindings = _original_excerpts(root, value, item, remaining_chars)
            remaining_chars -= sum(len(excerpt['text']) for excerpt in excerpts)
            result[-1].update(original_excerpts=excerpts, original_excerpt_note=note)
            original_hashes.update(bindings)
    return result, original_hashes


def _choices(config, card, choices):
    choices = {} if choices is None else choices
    enabled = 'style_profile' in config['writing']
    allowed = {'title', 'angle', 'audience', 'target_words'} | ({'author_notes'} if enabled else set())
    if not isinstance(choices, dict) or set(choices) - allowed:
        raise store.OfflineError('写作选项只接受标题、角度、受众和目标字数')
    result = {name: _text(choices.get(name, card[name]), '写作' + name, 500 if name == 'title' else 5000)
              for name in ('title', 'angle', 'audience')}
    words = config['writing']['words']
    count = choices.get('target_words', words['default'])
    if type(count) is not int or not words['min'] <= count <= words['max']:
        raise store.OfflineError('目标字数超出配置范围')
    result['target_words'] = count
    if enabled:
        notes = choices.get('author_notes', '')
        if (not isinstance(notes, str) or len(notes) > 5000
                or any(ord(char) < 32 and char not in '\n\t' for char in notes)):
            raise store.OfflineError('作者补充必须是最多 5000 字的文本')
        result['author_notes'] = notes.strip()
    return result


def _sdk_evidence(root, value, selected, writing_v2=False):
    available = {item['id']: item for item in value['bundle']['sources']}
    result, remaining = [], 8000
    for identifier in selected:
        if identifier not in available:
            raise store.OfflineError('选题引用未知原文')
        item = available[identifier]
        summary = _path(root, item['summary_path'], formal=True)
        original = _path(root, item['original_path'], formal=True)
        if summary.read_text(encoding='utf-8') != item['summary_text'] or original.read_text(encoding='utf-8') != item['original_text']:
            raise store.OfflineError('已审阅原文或总结发生变化')
        summary_identity = note_paths.summary_ids(item['summary_path'])
        if summary_identity is None or summary_identity[0] != value['topic']:
            raise store.OfflineError('总结未绑定有效的研究批次')
        research_base = 'reports/test/%s/research-batches/%s/items/%s' % summary_identity
        research_result = store.checked_yaml(root, research_base + '/result.yaml')
        from researchdesk_batch import parse_result
        research = parse_result(store.checked_yaml(root, research_base + '/checkpoints/research-%s.yaml' % research_result['revision_count'])['result']['text'])
        evidence = {'id': identifier, 'title': item['title'], 'path': item['summary_path'],
            'origin': 'reviewed_research', 'coverage': item['coverage'],
            'source_ids': [item['source_id']], 'source_paths': [item['original_path']],
            'source_urls': [item['url']], 'source_version': None,
            'independently_reviewed': True, 'can_support_original_facts': True,
            'sha256': store.digest(summary.read_bytes()), 'text': item['summary_text'],
            'summary': research['summary'], 'claims': research['claims'], 'limitations': research['limitations'],
            'locators': []}
        if writing_v2:
            # Bound excerpts keep the confirmed Writing input manageable.
            original_text = item['original_text'][:min(2400, remaining)]
            remaining -= len(original_text)
            evidence.update(original_excerpts=[{'locator_id': identifier, 'location': '已归档原文',
                'text': original_text, 'reading_scope': item['coverage'],
                'source_url': item['url'], 'archive_path': item['original_path'],
                'archive_sha256': store.digest(original.read_bytes()), 'excerpt_only': True}] if original_text else [],
                original_excerpt_note='仅提供已审阅研究对应归档的有限正文节选；不是 Writing 对全文的重新审阅，未独立复现实验。')
        result.append(evidence)
    return result


def _sdk_preview(root, config, topic_id, choices=None, frozen=None):
    topic, cycle_id, relative, metadata, value, effective, raw = _load_topic(root, config, topic_id)
    sources = raw.get('source_ids') or [source['id'] for source in value['bundle']['sources']]
    card = dict(raw, evidence_ids=sources)
    selected = _choices(config, card, choices)
    profile = frozen.get('style_profile') if frozen is not None else style_profile(root, config['writing'])
    evidence = _sdk_evidence(root, value, sources, profile is not None)
    hashes = {path: expected for path, expected in value['input_hashes'].items()
              if Path(path).parts[:1] != ('config',)}
    hashes.update(value['output_hashes'])
    hashes.update(value['proof_hashes'])
    for item in evidence:
        for path in [item['path']] + item['source_paths']:
            hashes[path] = store.digest(_path(root, path, formal=True).read_bytes())
    hashes[config['_config_path']] = config['_config_sha256']
    if profile is not None:
        from researchdesk_writing_style import validate_profile
        validate_profile(profile)
        hashes[profile['path']] = profile['sha256']
    reports = [path for path in value['output_hashes']
               if note_paths.insight_ids(path) == (topic, cycle_id)]
    if len(reports) != 1:
        raise store.OfflineError('选题缺少已准入的洞察报告')
    insights = [dict(item, id='formal-insight-%s-%s-%s' % (topic, cycle_id, number), path=reports[0])
                for number, item in enumerate(value['candidate']['insights'], 1)]
    coverage_note = '基于已采集正文、独立审阅通过的逐篇总结及实际历史资料；未复现实验，不把研究线索写成已成立趋势。'
    result = {'schema_version': 1, 'mode': 'real_topic_preview', 'admission_mode': value['mode'],
        'workbench_id': config['workbench_id'], 'topic_id': topic_id, 'id': topic_id,
        'topic': topic, 'path': relative, 'cycle_id': cycle_id, 'status': 'proposed',
        'date': metadata.get('created_at'), **selected, 'choices': selected,
        'why_now': card.get('why_now', card['angle']),
        'questions': card.get('key_questions', []), 'key_questions': card.get('key_questions', []),
        'gaps': card.get('evidence_gaps', []), 'evidence_gaps': card.get('evidence_gaps', []),
        'coverage_note': coverage_note, 'evidence': evidence, 'insights': insights,
        'review': {'status': 'pass', 'models': value['models'], 'independent': True,
                   'accepted_path': value['accepted_path']},
        'writing': config['writing'], 'stages': ['outline', 'draft', 'candidate'],
        'output_mode': 'test_only', 'approval_required': True, 'writing_started': False,
        'publish_authorized': False, 'config': {'path': config['_config_path'], 'sha256': config['_config_sha256']},
        'snapshot': {'hashes': dict(sorted(hashes.items())), 'fingerprint': store.digest(hashes)}}
    if profile is not None:
        result['style_profile'] = profile
    result['preview_sha256'] = store.digest(result)
    return result


def validate_public_preview(root, preview):
    """Verify an already confirmed SDK preview without exporting private YAML."""
    if preview.get('admission_mode') != 'codex_insight_admission':
        raise store.OfflineError('仅新版准入支持公开冻结证明复核')
    config = {'workbench_id': preview['workbench_id'], 'topics': [preview['topic']],
              'writing': preview['writing'], '_config_path': preview['config']['path'],
              '_config_sha256': preview['config']['sha256']}
    fresh = _sdk_preview(root, config, preview['topic_id'], preview['choices'], frozen=preview)
    if fresh != preview:
        raise store.OfflineError('正式选题、原文或已确认写作范围发生变化')
    return fresh


def prepare_preview(root, config, topic_id, choices=None):
    """Return a JSON-safe immutable candidate; this grants no authorization."""
    root = Path(root).resolve()
    _config(root, config)
    entries = [entry for entry in _topic_entries(root, config) if entry[4]['id'] == topic_id]
    if len(entries) == 1:
        accepted = admission._checked(root, admission._base(entries[0][0], entries[0][1]) + '/accepted.yaml')
        if accepted.get('mode') == 'codex_insight_admission':
            return _sdk_preview(root, config, topic_id, choices)
    profile = style_profile(root, config['writing'])
    topic, cycle_id, relative, metadata, value, effective, card = _load_topic(root, config, topic_id)
    selected = _choices(config, card, choices)
    evidence, original_hashes = _evidence(root, value, effective, card['evidence_ids'], profile is not None)
    base = admission._base(topic, cycle_id)
    hashes = dict(value['input_hashes'])
    hashes.update(value['protected_notes'])
    hashes.update(original_hashes)
    hashes.update(admission.effective_output_hashes(root, value))
    proof_files = [base + '/plan.yaml', base + '/accepted.yaml']
    repair_path = base + '/link-repair.yaml'
    if admission._location(root, repair_path).exists():
        proof_files.append(repair_path)
    for path in list(hashes):
        if Path(path).suffix == '.yaml' and admission._location(root, path + '.sha256').is_file():
            proof_files.append(path + '.sha256')
    for path in proof_files:
        hashes[path] = store.digest(_path(root, path).read_bytes())
        if Path(path).suffix == '.yaml':
            hashes[path + '.sha256'] = store.digest(_path(root, path + '.sha256').read_bytes())
    for item in evidence:
        for path in [item['path']] + item['source_paths']:
            hashes[path] = store.digest(_path(root, path, formal=True).read_bytes())
    hashes[config['_config_path']] = config['_config_sha256']
    if profile is not None:
        hashes[profile['path']] = profile['sha256']
    generation_base = 'reports/test/%s/insight-runs/%s' % (topic, cycle_id)
    manifest = store.checked_yaml(root, generation_base + '/manifest.yaml')
    insights = [dict(value['candidate']['insights'][number],
                     id='formal-insight-%s-%s-%s' % (topic, cycle_id, number + 1),
                     path='insights/%s/%s-insight-%s.md' % (topic, cycle_id, number + 1))
                for number in card['insight_indices']]
    merged = 'insights/%s/%s-synthesis.md' % (topic, cycle_id)
    if merged in effective:
        for item in insights:
            item['path'] = merged
    result = {'schema_version': 1, 'mode': 'real_topic_preview', 'workbench_id': config['workbench_id'],
        'topic_id': topic_id, 'id': topic_id, 'topic': topic, 'path': relative,
        'cycle_id': cycle_id, 'status': 'proposed', 'date': metadata.get('created_at'),
        **selected, 'choices': selected, 'why_now': card['why_now'],
        'questions': card['key_questions'], 'key_questions': card['key_questions'],
        'gaps': card['evidence_gaps'], 'evidence_gaps': card['evidence_gaps'],
        'coverage_note': value['candidate']['coverage_note'],
        'evidence': evidence, 'insights': insights,
        'review': {'status': 'pass', 'models': manifest['models'],
                   'independent': True, 'accepted_path': base + '/accepted.yaml'},
        'writing': config['writing'], 'stages': ['outline', 'draft', 'candidate'],
        'output_mode': 'test_only', 'approval_required': True,
        'writing_started': False, 'publish_authorized': False,
        'config': {'path': config['_config_path'], 'sha256': config['_config_sha256']},
        'snapshot': {'hashes': dict(sorted(hashes.items())), 'fingerprint': store.digest(hashes)}}
    if profile is not None:
        result['style_profile'] = profile
    result['preview_sha256'] = store.digest(result)
    return result


def validate_preview(root, config, preview):
    """Recheck the exact current proof and options before consuming a nonce."""
    if (not isinstance(preview, dict) or preview.get('mode') != 'real_topic_preview'
            or not isinstance(preview.get('preview_sha256'), str)):
        raise store.OfflineError('预览包无效')
    expected = dict(preview)
    sha = expected.pop('preview_sha256')
    if store.digest(expected) != sha:
        raise store.OfflineError('冻结预览内容或选项发生变化')
    fresh = prepare_preview(root, config, preview.get('topic_id'), preview.get('choices'))
    if fresh != preview:
        raise store.OfflineError('选题、证据、历史资料、模型或配置已变化，请重新预览')
    return fresh


def list_topics(root, config):
    """List only currently verifiable formal proposals; never elevate fixtures."""
    root = Path(root).resolve()
    _config(root, config)
    result = []
    for _, _, _, _, metadata in _topic_entries(root, config):
        try:
            preview = prepare_preview(root, config, metadata['id'])
        except store.OfflineError:
            # A stale admitted topic is not eligible for a new confirmation.
            continue
        result.append({key: preview[key] for key in ('id', 'topic_id', 'topic', 'title', 'path', 'cycle_id',
            'status', 'date', 'angle', 'audience', 'target_words', 'evidence_gaps', 'key_questions', 'coverage_note')})
        result[-1].update(evidence_count=len(preview['evidence']),
            coverage=[{'id': item['id'], 'coverage': item['coverage'], 'origin': item['origin']}
                      for item in preview['evidence']],
            source_urls=list(dict.fromkeys(url for item in preview['evidence'] for url in item['source_urls'])))
    return result
