"""Pure presentation of already verified research fields; never new analysis.

The caller owns proof validation, metadata, paths and create-only storage.  These
functions reorganize existing model prose and resolve its current source aliases;
they do not fetch sources, add findings or upgrade a document's reading scope.
"""

import re
from urllib.parse import quote, urlsplit


_ALIAS = re.compile(r'(?<![A-Za-z0-9_-])([RH]\d+)(?![A-Za-z0-9_-])')
_RANGE = re.compile(r'(?<![A-Za-z0-9_-])([RH])(\d+)\s*(?:[–—~～-]|至)\s*([RH])?(\d+)(?![A-Za-z0-9_-])')
_OLD_ALIAS = re.compile(r'(?<![A-Za-z0-9_-])historical-[RH]\d+-[RH]\d+(?![A-Za-z0-9_-])')
_SCOPES = {
    'full_text': '已阅读完整抽取正文，未独立复现实验',
    'excerpt': '仅阅读正文节选，未覆盖全部原文',
    'abstract_only': '仅阅读摘要，未核验全文或复现实验',
    'historical_note': '历史资料，未经本轮原文复核',
    'fixture': '模拟材料，不构成真实研究证据',
}


def _title(record):
    value = (record.get('display_title') or record.get('title')
             or record.get('metadata', {}).get('title') or '来源资料')
    return ' '.join(str(value).split())


def _reference_title(record):
    """Use a literal leading title, never invent a method name or short alias."""
    title = _title(record)
    parts = re.split(r'[:：]', title, maxsplit=1)
    if len(parts) == 2:
        head = parts[0].strip()
        if (2 <= len(head) <= 100 and parts[1].strip()
                and re.search(r'[A-Za-z\u3400-\u9fff]', head)
                and head.lower() not in {'http', 'https'}):
            return head
    return title


def _source_kind(record):
    metadata = record.get('metadata') or {}
    kind = record.get('kind') or metadata.get('kind')
    if kind in {'paper', 'blog'}:
        return kind
    identifiers = record.get('source_ids') or [record.get('source_id', '')]
    if identifiers and all(identifier.startswith('paper-') for identifier in identifiers):
        return 'paper'
    if identifiers and all(identifier.startswith('blog-') for identifier in identifiers):
        return 'blog'
    return None


def _clean(value, evidence):
    """Resolve only this field's current namespace, preserving all other prose."""
    text = str(value)
    lookup = {record['id']: record for record in evidence if record.get('id')}
    short_names = {key: _reference_title(record) for key, record in lookup.items()}
    # Multiple syntheses may have the same generic title prefix; keep their
    # full titles rather than merge different documents into a vague alias.
    names = {key: (_title(lookup[key]) if
                  len({_title(lookup[other]) for other in short_names if short_names[other] == name}) > 1
                  else name) for key, name in short_names.items()}
    text = _OLD_ALIAS.sub('历史文档自身的来源编号', text)

    def span(match):
        prefix, start, last_prefix, end = match.groups()
        if last_prefix and last_prefix != prefix:
            # A mixed range is not a sequence of either current namespace.
            return match.group(0)
        start, end = int(start), int(end)
        if 0 <= end - start <= 100:
            keys = ['%s%s' % (prefix, number) for number in range(start, end + 1)]
            if all(key in lookup for key in keys):
                if prefix == 'H':
                    return '本轮采用的这些历史笔记'
                kinds = {_source_kind(lookup[key]) for key in keys}
                if kinds == {'paper'}:
                    return '这些论文'
                if kinds == {'blog'}:
                    return '这些博客'
                return '这些研究材料'
        # Do not invent identities for an incomplete historical input list or
        # turn a referenced subset into a claim about all research material.
        return '这里提及的历史资料' if prefix == 'H' else '这里提及的本轮研究资料'

    text = _RANGE.sub(span, text)
    text = _ALIAS.sub(lambda match: '《%s》' % names[match[1]]
                     if match[1] in lookup else
                     ('这里提及的历史资料' if match[1].startswith('H') else '这里提及的本轮研究资料'), text)
    for old, new in [('abstract_only', '仅摘要'), ('historical_note', '未经本轮原文复核的历史资料'),
                     ('human_baseline', '未经本轮原文复核的历史资料'),
                     ('reviewed_research', '已审阅研究'), ('full_text', '完整抽取正文'),
                     ('excerpt', '正文节选')]:
        text = re.sub(r'(?<![A-Za-z0-9_])`?' + old + r'`?(?![A-Za-z0-9_])', new, text)
    return text.strip()


def _texts(values, evidence):
    result = []
    for value in values or []:
        text = _clean(value, evidence)
        if text and text not in result:
            result.append(text)
    return result


def _paragraphs(lines, values, evidence):
    for value in _texts(values, evidence):
        lines += [value, '']


def _list(lines, values, evidence):
    values = _texts(values, evidence)
    lines += ['- ' + value for value in values]
    if values:
        lines.append('')


def _selected(evidence, refs):
    keys = set(refs)
    return [record for record in evidence if record.get('id') in keys] if keys else []


def _mentioned(value, evidence):
    """Collect sources named in scope prose as well as structured citations."""
    known = {record['id'] for record in evidence if record.get('id')}
    if isinstance(value, dict):
        return {key for part in value.values() for key in _mentioned(part, evidence)}
    if isinstance(value, list):
        return {key for part in value for key in _mentioned(part, evidence)}
    if not isinstance(value, str):
        return set()
    text = _OLD_ALIAS.sub('', value)
    refs = set()
    for match in _RANGE.finditer(text):
        prefix, start, last_prefix, end = match.groups()
        start, end = int(start), int(end)
        if (not last_prefix or prefix == last_prefix) and 0 <= end - start <= 100:
            refs.update('%s%s' % (prefix, number) for number in range(start, end + 1))
    refs.update(match[1] for match in _ALIAS.finditer(text))
    return refs & known


def _label(text):
    return re.sub(r'([\\\[\]*_`])', r'\\\1', text)


def _scope(record):
    if record.get('origin') == 'human_baseline':
        return _SCOPES['historical_note']
    return _SCOPES.get(record.get('coverage'), '实际阅读范围见原研究记录')


def _sources(lines, evidence):
    """List original URLs once, retaining different scopes for the same source."""
    sources = {}
    for record in evidence:
        urls = record.get('source_urls') or []
        if not urls:
            url = record.get('source_url') or record.get('metadata', {}).get('source_url')
            urls = [url] if url else []
        for url in urls or [None]:
            if url is not None:
                parsed = urlsplit(url)
                if (parsed.scheme not in {'https', 'http'} or not parsed.netloc
                        or parsed.username or parsed.password or re.search(r'[\r\n\t]', url)):
                    raise ValueError('阅读正文只接受已核验的原文 HTTP(S) 链接')
                url = quote(url, safe=":/?#[]@!$&'*+,;=%~._-")
            key = url or ('unlinked', _title(record))
            entry = sources.setdefault(key, {'title': _title(record), 'url': url, 'scopes': []})
            scope = _scope(record)
            if scope not in entry['scopes']:
                entry['scopes'].append(scope)
    if not sources:
        return
    lines += ['## 来源与阅读范围', '']
    for entry in sources.values():
        label = _label(entry['title'])
        source = '[%s](%s)' % (label, entry['url']) if entry['url'] else label
        lines += ['- %s：%s。' % (source, '；'.join(entry['scopes']))]
    lines.append('')


def _finish(lines):
    return '\n'.join(lines).rstrip() + '\n'


def research(evidence):
    """Present only the previously reviewed single-source summary and claims."""
    records = [evidence]
    lines = ['# ' + _title(evidence), '']
    _paragraphs(lines, [evidence.get('research_summary', '')], records)
    claims = evidence.get('research_claims') or []
    if claims:
        lines += ['## 问题、方法与结果', '']
        _paragraphs(lines, [claim['text'] for claim in claims], records)
    limitations = evidence.get('research_limitations') or []
    if limitations:
        lines += ['## 如何理解这些结论', '']
        _paragraphs(lines, limitations, records)
    _sources(lines, records)
    return _finish(lines)


def synthesis(candidate, evidence):
    """Combine a reviewed synthesis and all its insights, without new findings."""
    report = candidate['report']
    lines = ['# ' + report['title'], '']
    _paragraphs(lines, [report['summary']], evidence)
    comparisons = report.get('comparisons') or []
    if comparisons:
        lines += ['## 这些研究有哪些共同点与分歧', '']
        _paragraphs(lines, [claim['text'] for claim in comparisons], evidence)
    insights = candidate.get('insights') or []
    if insights:
        lines += ['## 值得深入研究的线索', '',
                  '以下是基于当前材料提出的研究线索与待验证判断，不能据此确认行业趋势。', '']
    for insight in insights:
        lines += ['### ' + _clean(insight['title'], evidence), '']
        _paragraphs(lines, [insight['hypothesis']], evidence)
        _paragraphs(lines, (insight.get('counterpoints') or []) + (insight.get('limitations') or []), evidence)
        if insight.get('validation'):
            lines += ['还需要怎样验证：', '']
            _list(lines, insight['validation'], evidence)
    if report.get('limitations'):
        lines += ['## 当前结论的边界', '']
        _paragraphs(lines, report['limitations'], evidence)
    if report.get('open_questions'):
        lines += ['## 接下来值得追问什么', '']
        _list(lines, report['open_questions'], evidence)
    if candidate.get('coverage_note'):
        lines += ['阅读说明：' + _clean(candidate['coverage_note'], evidence), '']
    refs = {key for claim in comparisons for key in claim.get('evidence_ids', [])}
    refs.update(key for insight in insights for key in insight.get('evidence_ids', []))
    refs.update(_mentioned([report, insights, candidate.get('coverage_note', '')], evidence))
    _sources(lines, _selected(evidence, refs))
    return _finish(lines)


def topic(card, evidence):
    """Keep proposal value and evidence gaps, not internal approval machinery."""
    lines = ['# ' + card['title'], '']
    _paragraphs(lines, [card.get('angle', ''), card.get('why_now', '')], evidence)
    if card.get('audience'):
        lines += ['## 适合谁读', '']
        _paragraphs(lines, [card['audience']], evidence)
    if card.get('key_questions'):
        lines += ['## 准备回答的问题', '']
        _list(lines, card['key_questions'], evidence)
    if card.get('evidence_gaps'):
        lines += ['## 写作前还需要补齐什么', '']
        _list(lines, card['evidence_gaps'], evidence)
    refs = set(card.get('evidence_ids', [])) | _mentioned(card, evidence)
    _sources(lines, _selected(evidence, refs))
    return _finish(lines)


def writing(candidate, bundle):
    """Retain legacy reviewed lead and body sentences, without audit headings."""
    evidence = bundle.get('evidence') or []
    lines = ['# ' + candidate['title'], '']
    # In legacy formal documents summary was a public lead, not only machine
    # metadata. Preserve it as a plain opening rather than silently drop prose.
    if candidate.get('summary'):
        lines += [_clean(candidate['summary'], evidence), '']
    refs = set()
    for section in candidate['sections']:
        if section.get('heading'):
            lines += ['## ' + _clean(section['heading'], evidence), '']
        # Do not deduplicate article paragraphs: intentional repetition belongs
        # to the reviewed prose and is not this presentation module's decision.
        for paragraph in section['paragraphs']:
            lines += [_clean(paragraph['text'], evidence), '']
            refs.update(paragraph.get('evidence_ids', []))
    if candidate.get('limitations'):
        lines += ['## 阅读时需要保留的边界', '']
        _paragraphs(lines, candidate['limitations'], evidence)
    refs.update(_mentioned([candidate.get('summary', ''), candidate['sections'],
                            candidate.get('limitations', [])], evidence))
    _sources(lines, _selected(evidence, refs))
    return _finish(lines)
