#!/usr/bin/env python3
"""One Markdown reading home, derived only from existing formal admissions.

Old proof files stay byte-identical. Legacy prose gets immutable, create-only
reading notes; new narrative outputs are linked directly. No model or fetcher.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import posixpath
import re
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit

import yaml

import researchdesk_admission as admission
import researchdesk_offline as store
import researchdesk_reading_text as prose


HOME = '研究首页.md'
START = '<!-- researchdesk:reading:start -->'
END = '<!-- researchdesk:reading:end -->'
SCOPES = {'abstract_only': '仅摘要', 'excerpt': '正文节选', 'full_text': '完整抽取正文',
          'historical_note': '历史笔记，未在本轮复核'}


def link(title, target):
    title = str(title).replace('[', '［').replace(']', '］').replace('|', '｜').replace('\n', ' ')
    return '[%s](%s)' % (title, quote(target, safe='/:?&=._-#%'))


def _slug(title):
    value = re.sub(r'[\\/:*?"<>|#%\x00-\x1f]', ' ', title)
    value = ' '.join(value.split()).strip('. ')
    value = value.encode('utf-8')[:160].decode('utf-8', errors='ignore').rstrip()
    return value or '研究内容'


def _day(value):
    match = re.search(r'(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)', str(value))
    return '-'.join(match.groups()) if match else '日期未记录'


def _frontmatter(text):
    return yaml.safe_load(text.split('---', 2)[1]) if text.startswith('---\n') else {}


def _identity(metadata):
    keys = store.identities(metadata)
    return next((key for key in keys if key.startswith('arxiv:')), 'url:' + store.canonical_url(metadata['source_url']))


def _enrich(root, record):
    item = dict(record)
    metadata = dict(item.get('metadata') or {})
    target = item.get('path')
    if not metadata.get('title') and target and admission._location(root, target).is_file():
        metadata.update(store.frontmatter(root / target) or {})
    item['title'] = item.get('title') or metadata.get('title') or '历史综合笔记'
    item['display_title'] = item['title']
    item['metadata'] = metadata
    item['source_urls'] = item.get('source_urls') or ([item['source_url']] if item.get('source_url') else [])
    return item


def _reading(root, path, body, origin, title, topic, source_text):
    metadata = {'title': title, 'kind': 'reading_note', 'topics': [topic]}
    binding = {'derived_from': origin, 'original_sha256': store.digest(source_text.encode()),
               'presentation': 'reviewed_content_reformatted'}
    existing = admission._location(root, path)
    if existing.is_file() and (store.frontmatter(existing) or {}).get('editorial') is True:
        text = existing.read_text(encoding='utf-8')
        match = re.search(r'<!-- researchdesk-reading (\{[^\n]+\}) -->', text)
        if not match or json.loads(match[1]) != binding:
            raise store.OfflineError('编辑阅读笔记与原研究绑定不同，保留文件: ' + path)
        if any((store.frontmatter(existing) or {}).get(key) != value for key, value in metadata.items()):
            raise store.OfflineError('编辑阅读笔记的身份已变化，保留文件: ' + path)
        return text
    provenance = json.dumps(binding, ensure_ascii=False)
    home = link('返回研究首页', posixpath.relpath(HOME, posixpath.dirname(path)))
    return ('---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---\n\n'
            + '<!-- researchdesk-reading ' + provenance + ' -->\n\n' + home + '\n\n' + body)


def _research_cycles(root, files, warnings):
    cycles = []
    for marker in sorted((root / 'reports').glob('*/admissions/*/accepted.yaml')):
        topic, cycle_id = marker.parts[-4], marker.parts[-2]
        base = 'reports/%s/admissions/%s' % (topic, cycle_id)
        try:
            value = admission._checked(root, base + '/plan.yaml')
            receipt = admission._checked(root, base + '/accepted.yaml')
            if receipt != admission._receipt(root, value):
                raise store.OfflineError('准入计划与回执不一致')
            admission._verify_plan(root, value, topic, cycle_id)
            effective = admission.effective_files(root, value)
            for path, content in effective.items():
                if admission._location(root, path).read_bytes() != content.encode():
                    raise store.OfflineError('正式资料内容已变化')
        except (store.OfflineError, OSError, ValueError, KeyError):
            warnings.append('%s：资料完整性待核对，未作为可读研究列出。' % cycle_id)
            continue
        evidence = [_enrich(root, item) for item in value['verification_bundle']['evidence']]
        current = [item for item in evidence if item['origin'] == 'reviewed_research']
        entries = []
        for item in current:
            source_id = value['source_id_map'].get(item['source_id'], item['source_id'])
            matches = [path for path, content in effective.items() if path.startswith('reports/')
                       and _frontmatter(content).get('source_id') == source_id]
            if len(matches) != 1:
                raise store.OfflineError('阅读入口缺少唯一正式单篇总结')
            original = matches[0]
            metadata = _frontmatter(effective[original])
            # New Research prose is already the canonical reading document.
            legacy = '## 主张与证据' in effective[original]
            path = original
            if legacy:
                path = 'reports/%s/解读/%s/%s-%s.md' % (topic, cycle_id, _slug(item['title']), source_id[-8:])
                files[path] = _reading(root, path, prose.research(item), original, item['title'], topic, effective[original])
            entries.append({'title': item['title'], 'metadata': item['metadata'],
                'kind': '论文' if source_id.startswith('paper-') else '博客',
                'coverage': SCOPES.get(item['coverage'], '范围见正文'), 'report': path,
                'source_url': item['source_url'], 'source_id': source_id,
                'updated': metadata.get('kind') == 'research_update'})
        candidate = value['candidate']
        summaries = [path for path, content in effective.items()
                     if _frontmatter(content).get('kind') == 'synthesis']
        if len(summaries) != 1:
            raise store.OfflineError('阅读入口缺少唯一正式综合')
        original = summaries[0]
        synthesis = original
        narrative = store.load_yaml(admission._location(root, value['insight_config']))['prompts']['version'] == 'insight-v5'
        if not narrative:
            synthesis = 'insights/%s/综述/%s-%s.md' % (topic, cycle_id, _slug(candidate['report']['title']))
            files[synthesis] = _reading(root, synthesis, prose.synthesis(candidate, evidence), original,
                candidate['report']['title'], topic, effective[original])
        topics = []
        for index, card in enumerate(candidate['topics']):
            original = 'articles/%s/%s-topic-%s.md' % (topic, cycle_id, index + 1)
            if original not in effective:
                raise store.OfflineError('阅读入口引用未准入选题')
            path = original
            if not narrative:
                path = 'articles/%s/选题/%s-%s-%s.md' % (topic, cycle_id, index + 1, _slug(card['title']))
                body = prose.topic(card, evidence)
                body += '\n' + link('本轮综合思考', posixpath.relpath(synthesis, posixpath.dirname(path))) + '\n'
                files[path] = _reading(root, path, body, original, card['title'], topic, effective[original])
            topics.append({'title': card['title'], 'path': path})
        actual = None
        provenance = value['verification_bundle'].get('provenance', {}).get('research_inputs', [])
        if provenance:
            manifest = store.checked_yaml(root, provenance[0]['manifest'])
            try:
                actual = datetime.fromisoformat(manifest['created_at'].replace('Z', '+00:00')).astimezone(
                    timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')
            except (ValueError, KeyError):
                pass
        cycles.append({'topic': topic, 'cycle_id': cycle_id, 'date': _day(cycle_id),
            'actual': actual, 'entries': entries, 'title': candidate['report']['title'],
            'synthesis': synthesis, 'topics': topics, 'insights': candidate['insights']})
    return sorted(cycles, key=lambda value: (value['date'], value['cycle_id']), reverse=True)


def _writings(root, files, warnings):
    import researchdesk_writing_admission as writing
    results = []
    for marker in sorted((root / 'reports').glob('*/writing-admissions/*/accepted.yaml')):
        topic, batch = marker.parts[-4], marker.parts[-2]
        approval = batch.removeprefix('writing-')
        try:
            writing.verify(root, topic, approval, historical=True)
            plan = admission._checked(root, str(marker.parent.relative_to(root)) + '/plan.yaml')
            bundle = plan['verification_bundle']
        except (store.OfflineError, OSError, ValueError, KeyError):
            warnings.append('%s：稿件完整性待核对，未列为已审阅文章。' % approval)
            continue
        docs = {}
        for original, content in plan['files'].items():
            metadata = _frontmatter(content)
            stage = metadata['stage']
            path = original
            label = {'outline': '大纲', 'draft': '初稿', 'candidate': '候选稿'}[stage]
            if metadata.get('writing_version') != 'writing-v2':
                checkpoint = 'reports/test/%s/writing-runs/%s/stages/%s.yaml' % (topic, batch, stage)
                candidate = store.checked_yaml(root, checkpoint)['candidate']
                path = 'articles/%s/稿件/%s-%s-%s.md' % (topic, approval, _slug(metadata['title']), label)
                body = prose.writing(candidate, bundle)
                files[path] = _reading(root, path, body, original, metadata['title'] + ' · ' + label, topic, content)
            docs[stage] = path
        results.append({'title': bundle['topic_card']['title'], 'topic': topic,
                        'date': _day(approval), 'documents': docs})
    return sorted(results, key=lambda item: item['date'], reverse=True)


def _library(root, cycles):
    sources = {}
    for cycle in reversed(cycles):
        for entry in cycle['entries']:
            key = _identity(entry['metadata'])
            value = sources.setdefault(key, dict(entry, first_seen=cycle['date']))
            value.update(entry, last_seen=cycle['date'])
    for folder in ('sources/papers', 'sources/blogs'):
        for path in sorted((root / folder).rglob('*.md')):
            if 'test' in path.relative_to(root).parts or path.name == 'README.md':
                continue
            metadata = store.frontmatter(path)
            if not metadata or metadata.get('kind') not in {'paper', 'blog'}:
                continue
            key = _identity(metadata)
            if key not in sources:
                related = [note for note in metadata.get('related_notes', [])
                           if note.startswith('reports/') and 'test' not in Path(note).parts
                           and admission._location(root, note).is_file()
                           and not store.frontmatter(root / note)]
                sources[key] = {'title': metadata['title'], 'metadata': metadata,
                    'source_url': metadata['source_url'], 'kind': '论文' if metadata['kind'] == 'paper' else '博客',
                    'report': related[0] if related else None, 'coverage': '历史人工整理' if related else '未关联可核验总结',
                    'first_seen': str(metadata.get('collected_at', '未记录'))[:10],
                    'last_seen': '历史人工整理' if related else '来源卡，暂无关联总结'}
    archives = []
    for path in sorted((root / 'sources/originals').glob('*/*.md')):
        if path.name == 'README.md':
            continue
        metadata = store.frontmatter(path)
        if not metadata or metadata.get('kind') != 'original_snapshot':
            continue
        relative = path.relative_to(root).as_posix()
        archives.append({'title': metadata['title'], 'path': relative, 'url': metadata['source_url'],
                         'reviewed': metadata.get('research_performed') is not False,
                         'date': str(metadata.get('captured_at', '未记录'))[:10]})
        key = _identity(metadata)
        if key not in sources:
            sources[key] = {'title': metadata['title'], 'metadata': metadata,
                'source_url': metadata['source_url'],
                'kind': '论文' if metadata['source_id'].startswith('paper-') else '博客',
                'report': None, 'coverage': '已采集，待研究', 'first_seen': archives[-1]['date'],
                'last_seen': '已采集，待研究'}
    return sources, archives


def _cycle_section(cycle, level=2):
    papers = sum(entry['kind'] == '论文' for entry in cycle['entries'])
    blogs = len(cycle['entries']) - papers
    label = cycle['date'] + ('（补跑）' if 'recovery' in cycle['cycle_id'] else '')
    lines = ['#' * level + ' ' + label + ' · ' + cycle['title'], '',
             '本轮研究 %s 篇论文、%s 篇博客。%s' % (papers, blogs,
                '实际执行：%s（北京时间）。' % cycle['actual'] if cycle['actual'] else '实际执行时间未单独记录。'), '',
             '| 类型 | 论文 / 博客 | 方法、思路与总结 | 本轮阅读范围 |',
             '| --- | --- | --- | --- |']
    for item in cycle['entries']:
        lines.append('| %s%s | %s | %s | %s |' % (
            item['kind'], '更新' if item['updated'] else '', link(item['title'], item['source_url']),
            link('方法与总结', item['report']), item['coverage']))
    lines += ['', '综合、洞察与趋势线索：' + link(cycle['title'], cycle['synthesis']), '']
    for item in cycle['insights']:
        lines.append('- 洞察与研究线索：' + link(item['title'], cycle['synthesis']))
    lines.append('')
    for item in cycle['topics']:
        lines.append('- 公众号选题：' + link(item['title'], item['path']))
    return lines + ['']


def _home(cycles, writings, sources, archives, warnings, manual=None):
    lines = ['# 研究工作台', '',
        '从这里看本轮与历史研究。文章标题打开原文，“方法与总结”打开每篇解读；综合文章包含与历史资料的比较、洞察、趋势线索和待验证问题。', '',
        '已整理 %s 个正式批次，实际研究轮次覆盖 %s 至 %s；不能把配置的历史窗口当成已经积累的时间。' % (
            len(cycles), min(item['date'] for item in cycles), max(item['date'] for item in cycles)), '',
        '[最新研究](#最新研究) · [历史批次](#历史批次) · [全部论文与博客](#全部论文与博客) · [公众号选题](#公众号选题) · [已生成文章](#已生成文章)', '',
        '## 最新研究', '']
    if warnings:
        lines[4:4] = ['部分记录的完整性待核对，未列为已审阅成果；详见末尾“待核对记录”。', '']
    latest = {}
    for cycle in cycles:
        latest.setdefault(cycle['topic'], cycle)
    for cycle in latest.values():
        lines += _cycle_section(cycle, 3)
    lines += ['## 历史批次', '']
    for cycle in cycles:
        if latest[cycle['topic']] is not cycle:
            lines += _cycle_section(cycle, 3)
    if len(cycles) == len(latest):
        lines += ['还没有更早的自动研究批次。', '']
    lines += ['## 全部论文与博客', '', '按原文 URL / arXiv 身份归并；同一篇文章的后续研究仍可在历史批次中查看。', '',
              '| 类型 | 原文 | 发表日期 | 最近研究与总结 |', '| --- | --- | --- | --- |']
    for item in sorted(sources.values(), key=lambda value: (str(value['last_seen']), value['title']), reverse=True):
        report = link(item['last_seen'] + ' · 解读', item['report']) if item['report'] else item['last_seen']
        lines.append('| %s | %s | %s | %s |' % (item['kind'], link(item['title'], item['source_url']),
            str(item['metadata'].get('published_at', '未记录'))[:10], report))
    if archives:
        lines += ['', '### 可以在库内打开的原文', '', '归档只表示正文已保存，不代表对应旧研究已经完成全文分析。', '']
        for item in archives:
            lines.append('- %s · %s%s' % (link(item['title'], item['path']), item['date'],
                ' · 已归档，尚未完成此正文的研究' if not item['reviewed'] else ''))
    lines += ['', '## 公众号选题', '',
        '选题卡说明价值、角度、读者、拟回答的问题和证据缺口。确认状态以' +
        link('Mac 选题页', 'http://127.0.0.1:8765') + '为准；阅读或点击链接不会启动写作。', '']
    for cycle in cycles:
        for item in cycle['topics']:
            lines.append('- %s · %s' % (cycle['date'], link(item['title'], item['path'])))
    lines += ['', '## 已生成文章', '', '以下为已正式准入的大纲、初稿与候选稿，尚未发布公众号。', '']
    for item in writings:
        docs = item['documents']
        lines += ['### ' + item['title'], '', item['date'] + ' · ' + ' · '.join(
            link(label, docs[stage]) for stage, label in [('outline', '大纲'), ('draft', '初稿'), ('candidate', '候选稿')]
            if stage in docs), '']
    if not writings:
        lines += ['尚无正式准入稿件。', '']
    if manual:
        lines += ['## 早期人工整理', '', '这些是已有人工研究与稿件，保留原状态，不计作新一轮自动研究。', '']
        lines += ['- ' + link(item['title'], item['path']) for item in manual]
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n' + (
        '\n## 待核对记录\n\n' + '\n'.join('- ' + item for item in warnings) + '\n' if warnings else '')


def build(root):
    """Return exact derived files without changing the vault or Git state."""
    root = Path(root).resolve()
    files, warnings = {}, []
    cycles = _research_cycles(root, files, warnings)
    if not cycles:
        if warnings:
            raise store.OfflineError('已有准入记录未通过校验，不能把旧首页当作当前结果')
        return {}
    writings = _writings(root, files, warnings)
    sources, archives = _library(root, cycles)
    manual = {}
    for item in sources.values():
        for path in item['metadata'].get('related_notes', []):
            target = admission._location(root, path)
            if 'test' in Path(path).parts or not target.is_file() or target.suffix != '.md' or store.frontmatter(target):
                continue
            heading = re.search(r'^#\s+(.+)$', target.read_text(encoding='utf-8'), re.M)
            if heading:
                stage = next((label for suffix, label in (
                    ('-release-candidate.md', '候选稿'), ('-draft.md', '初稿'),
                    ('-outline.md', '大纲')) if path.endswith(suffix)), None)
                title = heading[1] + (' · ' + stage if stage else '')
                manual[path] = {'title': title, 'path': path}
    managed = START + '\n\n' + _home(cycles, writings, sources, archives, warnings,
                                    list(manual.values())) + '\n' + END
    target = admission._location(root, HOME)
    if target.is_file() and START in target.read_text(encoding='utf-8'):
        previous = target.read_text(encoding='utf-8')
        if previous.count(START) != 1 or previous.count(END) != 1:
            raise store.OfflineError('研究首页生成区标记已变化，保留人工内容')
        prefix, rest = previous.split(START)
        _, suffix = rest.split(END)
        files[HOME] = prefix + managed + suffix
    else:
        if target.is_file() and (store.frontmatter(target) or {}).get('generated_by') == 'researchdesk-reading':
            raise store.OfflineError('研究首页生成区已被移除，保留人工内容')
        previous = target.read_text(encoding='utf-8') if target.is_file() else ''
        front = {'title': 'ResearchDesk · 研究工作台', 'kind': 'research_home', 'generated_by': 'researchdesk-reading'}
        files[HOME] = '---\n' + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + '---\n\n' + managed + '\n\n## 我的研究笔记\n\n'
        note = 'insights/agent-memory/我的研究问题.md'
        if (root / note).is_file():
            files[HOME] += link('我的研究问题与批注', note) + '\n\n'
        files[HOME] += '这一节可自由记录。自动刷新只更新上面的研究清单，保留这里的内容。\n'
        if previous:
            previous_body = previous.split('---', 2)[2].lstrip() if previous.startswith('---\n') else previous
            files[HOME] += '\n<details>\n<summary>原首页说明（历史保留）</summary>\n\n' + previous_body.rstrip() + '\n\n</details>\n'
    _check_links(root, files)
    return files


def _check_links(root, files):
    for relative, content in files.items():
        if relative == HOME:
            content = content.split(START, 1)[1].split(END, 1)[0]
        for destination in re.findall(r'\]\(([^)]+)\)', content):
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or destination.startswith('#'):
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(relative), unquote(parsed.path)))
            if 'test' in Path(target).parts:
                raise store.OfflineError('阅读入口不能指向测试资料')
            if target not in files and not admission._location(root, target).is_file():
                raise store.OfflineError('阅读入口链接缺失: ' + target)


def refresh(root):
    """Create legacy reading prose, update only the managed root-home block."""
    root = Path(root).resolve()
    files = build(root)
    changes, before = [], {}
    for relative, content in files.items():
        target = admission._location(root, relative)
        payload = content.encode('utf-8')
        original = target.read_bytes() if target.is_file() else None
        if original == payload:
            continue
        if original is not None and relative != HOME:
            raise store.OfflineError('保留已有人工修改，阅读稿未覆盖: ' + relative)
        before[relative] = original
        changes.append(relative)
    for relative in changes:
        target = admission._location(root, relative)
        payload = files[relative].encode('utf-8')
        current = target.read_bytes() if target.is_file() else None
        if current != before[relative]:
            raise store.OfflineError('阅读资料并发变化，保留文件')
        if relative != HOME or current is None:
            admission._create(root, relative, payload)
        else:
            with tempfile.NamedTemporaryFile(dir=root, prefix='.researchdesk-home-', suffix='.tmp', delete=False) as handle:
                handle.write(payload)
                temporary = handle.name
            try:
                os.replace(temporary, target)
            finally:
                if Path(temporary).exists():
                    Path(temporary).unlink()
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check', action='store_true', help='只读检查首页、阅读正文和链接是否为当前正式结果')
    args = parser.parse_args()
    try:
        if args.check:
            files = build(args.root)
            stale = [path for path, content in files.items() if not (args.root / path).is_file()
                     or (args.root / path).read_bytes() != content.encode()]
            if stale:
                print('阅读资料待刷新：' + '、'.join(stale), file=sys.stderr)
                return 1
            print('阅读首页、正文与链接检查通过。')
        else:
            changed = refresh(args.root)
            print('阅读首页已更新；新增或刷新 %s 个文件，未调用模型。' % len(changed))
        return 0
    except (store.OfflineError, OSError, ValueError, KeyError) as exc:
        print('保留现有资料，阅读整理停止：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
