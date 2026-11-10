"""Create-only extracted originals and exact offline reading replay.

This stores readable extracted text, not executable HTML or PDF binaries. The
archived extraction and the smaller model reading scope are kept distinct.
"""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re

import yaml

import offline as store


MAX_CHARS = 500_000
MAX_BYTES = 2_000_000
HASH = re.compile(r'[0-9a-f]{64}\Z')


def check_public_tokens(text):
    """Reject credential-shaped values even inside a verified public original.

    Public examples such as ``api_key: example`` or ``/tmp/cache/`` are not
    credential values. Long assignments and actual token shapes remain blocked
    before archiving or transfer, regardless of the public-content exception.
    """
    text = re.sub(r'\\[rnt]', ' ', text)
    token_key = r'(?:[a-z][a-z0-9_]*_)?(?:access_token|refresh_token|id_token|client_secret|code_verifier|api_key)'
    if (re.search(r'\bBearer\s+[A-Za-z0-9._-]{20,}|\beyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}\.', text)
            or re.search(r'\bsk-[A-Za-z0-9_-]{20,}', text)
            or re.search(r'(?i)\b' + token_key + r'\s*(?:\\?["\'])?\s*[:=]\s*(?:\\?["\'])?'
                         r'[A-Za-z0-9._~+/=-]{20,}', text)):
        raise store.OfflineError('公开原文包含疑似真实凭据，停止归档或传输')


def public_metadata(snapshot):
    """Return strict metadata after the caller has verified the full archive.

    The same reconstruction used by research/review validates every removed
    body, material and short quote. No field outside those public-text slots is
    exempted from the ordinary transfer checks.
    """
    _validate(snapshot, snapshot['candidate'])
    value = deepcopy(snapshot)
    value['material'] = '[verified public reading material]'
    value['record']['body_text'] = '[verified public extracted body]'
    if value['document'] is not None:
        for section in value['document']['sections']:
            section['text'] = '[verified public section]'
    for locator in value['candidate']['evidence']['locators']:
        locator['quote'] = '[verified public quote]'
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _without_archive(candidate):
    return {key: deepcopy(value) for key, value in candidate.items() if key != 'archive'}


def _paths(candidate, base=None):
    topic, key = candidate.get('topic'), candidate.get('key')
    if not isinstance(topic, str) or not store.SAFE_ID.fullmatch(topic) or not isinstance(key, str) or not store.SAFE_ID.fullmatch(key):
        raise store.OfflineError('原文归档身份无效')
    if base is None:
        relative = candidate.get('archive', {}).get('path', '')
        parts = Path(relative).parts
        legacy = (len(parts) == 8 and parts[:4] == ('reports', 'test', topic, 'research-batches')
                  and store.SAFE_ID.fullmatch(parts[4]) and parts[5:] == ('items', key, 'original.yaml'))
        collection = (len(parts) == 6 and parts[:2] == ('collection', topic)
                      and store.SAFE_ID.fullmatch(parts[2]) and parts[3:] == ('items', key, 'original.yaml'))
        if not (legacy or collection):
            raise store.OfflineError('原文归档必须绑定同主题同来源的批次目录')
        return relative, str(Path(relative).with_suffix('.md'))
    prefixes = ('reports/test/%s/research-batches/' % topic, 'collection/%s/' % topic)
    if not isinstance(base, str) or not any(
            base.startswith(prefix) and store.SAFE_ID.fullmatch(base[len(prefix):]) for prefix in prefixes):
        raise store.OfflineError('原文归档批次路径无效')
    prefix = '%s/items/%s/original' % (base, key)
    return prefix + '.yaml', prefix + '.md'


def relative_path(candidate, formal=True):
    """Return the create-only formal extracted-original path for admission."""
    if not formal:
        return _paths(candidate)[1]
    identifier, content = candidate.get('source_id', ''), candidate.get('archive', {}).get('sha256', '')
    if (not re.fullmatch(r'(?:paper|blog)-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identifier)
            or not HASH.fullmatch(content)):
        raise store.OfflineError('正式原文归档身份或内容散列无效')
    return 'sources/originals/%s/%s-%s.md' % (candidate['topic'], identifier, content)


def _validate(snapshot, candidate, source=None, config=None):
    from batch_inputs import project_material
    from fulltext import _digest
    if (not isinstance(snapshot, dict) or set(snapshot) != {
            'schema_version', 'mode', 'source', 'candidate', 'material', 'record',
            'document', 'responses', 'captured_at'}
            or snapshot['schema_version'] != 1 or snapshot['mode'] != 'extracted_original'
            or snapshot['candidate'] != _without_archive(candidate)
            or (source is not None and snapshot['source'] != source)):
        raise store.OfflineError('归档不对应原候选或来源配置')
    selected, record, document = snapshot['source'], snapshot['record'], snapshot['document']
    if (selected.get('archive') is not True or selected.get('id') != candidate['key']
            or selected.get('kind') != candidate['kind']
            or (config is not None and config.get('topic') != candidate['topic'])
            or not isinstance(record, dict) or record.get('metadata') != candidate['metadata']
            or record.get('kind') != candidate['kind']
            or record.get('upstream_updated_at') != candidate.get('upstream_updated_at')
            or candidate.get('identity_keys') != store.identities(candidate['metadata'])
            or candidate.get('metadata_hash') != store.digest({
                'metadata': candidate['metadata'], 'upstream_updated_at': candidate.get('upstream_updated_at')})):
        raise store.OfflineError('归档元数据或来源身份不一致')
    body = record.get('body_text')
    if (not isinstance(body, str) or not 30 <= len(body) <= MAX_CHARS
            or store.digest(body.encode()) != record.get('content_hash')):
        raise store.OfflineError('归档抽取正文内容散列不一致或超限')
    if document is not None:
        if not isinstance(document, dict) or not isinstance(document.get('sections'), list) or not document['sections']:
            raise store.OfflineError('归档章节无效')
        total = 0
        for index, section in enumerate(document['sections'], 1):
            if (not isinstance(section, dict) or set(section) != {'id', 'title', 'location', 'text'}
                    or section.get('id') != 'S%s' % index
                    or any(not isinstance(section.get(key), str) or not section[key] for key in ('title', 'location', 'text'))):
                raise store.OfflineError('归档章节缺失或定位无效')
            total += len(section['text'])
        if (total > MAX_CHARS or document.get('total_chars') != total
                or document.get('text_sha256') != _digest(document['sections'])
                or document.get('format') not in {'html', 'pdf', 'abstract'}
                or document.get('coverage') not in {'full_text', 'excerpt', 'abstract_only'}
                or document.get('attempts') != candidate.get('acquisition_attempts')):
            raise store.OfflineError('归档完整正文、获取记录或范围不一致')
    evidence, material, content_hash = project_material(record, document, selected)
    if (evidence != candidate['evidence'] or content_hash != candidate['content_hash']
            or material != snapshot.get('material')
            or store.digest(material.encode()) != candidate['evidence'].get('evidence_sha256')):
        raise store.OfflineError('归档不能重建原研究与审阅的精确阅读材料')
    if not isinstance(snapshot['responses'], list) or not snapshot['responses']:
        raise store.OfflineError('归档缺少公开来源获取记录')
    for response in snapshot['responses']:
        if (not isinstance(response, dict) or not isinstance(response.get('sha256'), str)
                or not HASH.fullmatch(response['sha256']) or response.get('status') != 200):
            raise store.OfflineError('归档响应来源记录无效')
    return material


def render_markdown(snapshot, formal=False):
    """Readable extracted text; full archive size never implies full model read."""
    candidate = snapshot['candidate']
    _validate(snapshot, candidate)
    record, document = snapshot['record'], snapshot['document']
    metadata = {'schema_version': 1, 'kind': 'original_snapshot',
        'title': record['metadata']['title'], 'source_id': candidate['source_id'],
        'source': record['metadata']['source'], 'authors': record['metadata'].get('authors', []),
        'published_at': record['metadata'].get('published_at'),
        'source_version': record['metadata'].get('source_version'),
        'topics': [candidate['topic']], 'source_url': record['metadata']['source_url'],
        'captured_at': snapshot['captured_at'], 'content_sha256': candidate['content_hash'],
        'coverage': document['coverage'] if document else
                    {'fulltext': 'full_text'}.get(record['coverage'], record['coverage']),
        'research_coverage': candidate['evidence']['coverage']}
    if record['metadata'].get('arxiv_id'):
        metadata['source_url'] = 'https://arxiv.org/abs/' + record['metadata']['arxiv_id'] + record['metadata']['source_version']
    lines = ['---', yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip(), '---', '',
        '# ' + metadata['title'], '',
        ('> 原文抽取归档，用于阅读及重放，内容不代表已核实的研究结论。' if formal else
         '> TEST：原文抽取归档，用于阅读及重放，不代表正式研究结论。'), '',
        '- [打开来源原文](%s)。' % metadata['source_url'],
        '- 原文归档保存完整可用抽取文本；绑定的模型材料范围为 `%s`，可小于本归档。' % candidate['evidence']['coverage'],
        '- 归档自身不表示已经执行研究或审阅；实际执行与审阅状态以对应研究回执为准。',
        '- 不保存可执行网页、PDF 版式或图片，不保证公式和图表的抽取完整性，未复现实验。']
    if candidate['evidence']['coverage'] == 'abstract_only':
        lines.append('- 当前仅有摘要；没有将摘要归档冒充全文，全文失败原因见取材记录。')
    if document:
        lines += ['- 抽取方式：`%s`；抽取范围：`%s`。' % (document['format'], document['coverage'])]
        for item in document.get('limitations', []):
            lines.append('- 抽取限制：' + item)
        for attempt in document.get('attempts', []):
            lines.append('- 取材：%s / %s / %s。' % (attempt['format'], attempt['status'], attempt['reason']))
    lines += ['', '## 获取记录', '']
    if record.get('publication_date_basis') == 'publisher_feed':
        feed = snapshot['source'].get('feed_metadata', {})
        lines += ['- 发布日期来自已配置发布者 Feed；文章页面未提供可解析日期。',
                  '- 日期依据：[Feed](%s)，响应 SHA-256：`%s`。' %
                  (feed.get('feed_url', ''), feed.get('response_sha256', ''))]
    for response in snapshot['responses']:
        lines.append('- [%s](%s)；响应 SHA-256：`%s`；抓取时间：%s。' % (
            response.get('content_type', '公开来源'), response.get('url', metadata['source_url']),
            response['sha256'], response.get('fetched_at', snapshot['captured_at'])))
    lines += ['', '## 抽取正文', '']
    if document:
        for section in document['sections']:
            lines += ['### %s · %s' % (section['id'], section['title']), '',
                      '[原文定位](%s)' % section['location'], '', section['text'], '']
    else:
        body = record['body_text']
        if candidate['kind'] == 'blog' and len(body) > 800:
            sentences = [part for part in re.split(r'(?<=[.!?])\s+|(?<=[。！？])\s*', body) if part]
            paragraphs, current = [], []
            for sentence in sentences:
                current.append(sentence)
                if len(' '.join(current)) >= 650:
                    paragraphs.append(' '.join(current))
                    current = []
            if current:
                paragraphs.append(' '.join(current))
            body = '\n\n'.join(paragraphs)
            lines += ['> 以下仅按句子整理阅读段落；精确原文与内容散列保留在不可变归档检查点。', '']
        lines += [body, '']
    return '\n'.join(lines).rstrip() + '\n'


def save(root, base, candidate, material, source, capture):
    """Create both replay and reading views before the first model request."""
    if 'archive' in candidate:
        return load(root, candidate, source=source)[0]
    yaml_path, markdown_path = _paths(candidate, base)
    snapshot = {'schema_version': 1, 'mode': 'extracted_original', 'source': deepcopy(source),
        'candidate': _without_archive(candidate), 'material': material,
        'record': deepcopy(capture.get('record')), 'document': deepcopy(capture.get('document')),
        'responses': deepcopy(capture.get('responses')), 'captured_at': datetime.now(timezone.utc).isoformat()}
    # Reuse an interrupted create-only snapshot, never replace its timestamp or
    # prose. Its candidate and source must still match before being adopted.
    target = store.safe_path(Path(root).resolve(), yaml_path)
    if target.exists():
        snapshot = store.checked_yaml(root, yaml_path)
        prior = snapshot.get('candidate', {})
        # A process can stop after saving the original and before the candidate
        # plan. Only the newly allocated UUID may differ on the next fetch.
        if dict(_without_archive(candidate), source_id=prior.get('source_id')) == prior:
            candidate = deepcopy(prior)
    _validate(snapshot, candidate, source=source)
    payload = yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False).encode()
    markdown = render_markdown(snapshot, formal=yaml_path.startswith('collection/')).encode()
    if max(len(payload), len(markdown)) > MAX_BYTES:
        raise store.OfflineError('原文归档超过可传输文件上限')
    # This runs before the first Research/model request can be reserved.
    check_public_tokens(payload.decode('utf-8'))
    check_public_tokens(markdown.decode('utf-8'))
    sha = store.save_yaml(root, yaml_path, snapshot)
    store.create(root, markdown_path, markdown.decode())
    result = deepcopy(candidate)
    result['archive'] = {'path': yaml_path, 'sha256': sha, 'markdown_path': markdown_path,
                         'markdown_sha256': store.digest(markdown)}
    return result


def load(root, candidate, source=None, config=None):
    """Validate and replay pinned originals with no network fallback."""
    root = Path(root).resolve()
    binding = candidate.get('archive')
    if (not isinstance(binding, dict) or set(binding) != {'path', 'sha256', 'markdown_path', 'markdown_sha256'}
            or any(not isinstance(binding.get(key), str) or not HASH.fullmatch(binding[key])
                   for key in ('sha256', 'markdown_sha256'))):
        raise store.OfflineError('原文归档绑定无效')
    yaml_path, markdown_path = _paths(candidate)
    if binding['markdown_path'] != markdown_path:
        raise store.OfflineError('原文可读视图不对应该归档')
    path, reading = store.safe_path(root, yaml_path), store.safe_path(root, markdown_path)
    if (not path.is_file() or not reading.is_file() or max(path.stat().st_size, reading.stat().st_size) > MAX_BYTES
            or store.digest(path.read_bytes()) != binding['sha256']
            or store.digest(reading.read_bytes()) != binding['markdown_sha256']):
        raise store.OfflineError('原文归档缺失或内容散列不一致，禁止联网替换')
    snapshot = store.checked_yaml(root, yaml_path)
    material = _validate(snapshot, candidate, source=source, config=config)
    if reading.read_text(encoding='utf-8') != render_markdown(
            snapshot, formal=yaml_path.startswith('collection/')):
        raise store.OfflineError('原文可读视图不对应已绑定抽取内容')
    return deepcopy(candidate), material, snapshot
