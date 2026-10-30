#!/usr/bin/env python3
"""Read accepted local proofs and maintain one Markdown reading index, offline."""

import argparse
import html
import os
from pathlib import Path
import posixpath
import re
import sys
import tempfile

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import researchdesk_admission as admission
import researchdesk_offline as store
import researchdesk_writing_admission as writing


TARGET = 'workbench/资料索引.md'
START = '<!-- researchdesk:catalog:start sha256='
END = '<!-- researchdesk:catalog:end -->'
LABELS = {'full_text': '完整抽取正文', 'excerpt': '节选', 'abstract_only': '摘要',
          'historical_note': '历史笔记'}
GROUPS = [('synthesis', '综合报告'), ('research', '单篇研究与更新'),
          ('insight', '洞察与趋势判断'), ('topic_proposal', '公众号选题提案'),
          ('writing', '文章稿件'), ('source', '正式来源卡'), ('original_snapshot', '原文归档')]


def _date(identifier):
    match = re.search(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)', identifier)
    return '-'.join(match.groups()) if match else '未注明'


def _text(value):
    return html.escape(str(value), quote=False).replace('\n', ' ').replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;')


def _entry(relative, content, identifier, topic, accepted):
    if not content.startswith('---\n') or '\n---\n' not in content[4:]:
        raise store.OfflineError('正式资料缺少 Frontmatter: ' + relative)
    metadata = yaml.load(content.split('\n---\n', 1)[0][4:], Loader=store.UniqueKeyLoader)
    if not isinstance(metadata, dict) or not isinstance(metadata.get('title'), str):
        raise store.OfflineError('正式资料缺少标题: ' + relative)
    kind = metadata.get('kind')
    group = ('research' if kind in {'research_report', 'research_update'} else
             'writing' if kind in {'writing_outline', 'writing_draft', 'writing_candidate'} else
             'source' if kind in {'paper', 'blog'} else kind)
    if group not in dict(GROUPS):
        raise store.OfflineError('未知正式资料类型: ' + relative)
    coverage = LABELS.get(metadata.get('coverage'), metadata.get('coverage'))
    if not coverage:
        coverage = ('来源卡，非原文副本' if group == 'source' else
                    '继承确认选题的证据范围；未发布' if group == 'writing' else
                    '多来源，范围见正文')
    if kind in {'writing_outline', 'writing_draft', 'writing_candidate'}:
        coverage = {'writing_outline': '大纲', 'writing_draft': '初稿',
                    'writing_candidate': '候选稿'}[kind] + '；' + coverage
    return {'path': relative, 'title': metadata['title'], 'group': group,
            'date': _date(identifier), 'topic': topic, 'coverage': coverage,
            'accepted': accepted}


def collect(root):
    """Fail closed on a damaged accepted proof; never fetch or call a provider."""
    root = Path(root).resolve()
    entries, proofs = {}, []
    for path in sorted(root.glob('reports/*/admissions/*/accepted.yaml')):
        relative = path.relative_to(root).as_posix()
        receipt = admission._checked(root, relative)
        topic, cycle_id = path.parts[-4], path.parts[-2]
        plan_path = admission._base(topic, cycle_id) + '/plan.yaml'
        if receipt.get('plan_path') != plan_path:
            raise store.OfflineError('索引准入计划路径不匹配: ' + relative)
        plan = admission._checked(root, plan_path)
        admission._verify_plan(root, plan, topic, cycle_id)
        if receipt != admission._receipt(root, plan):
            raise store.OfflineError('索引准入接受记录与计划不一致: ' + relative)
        files = admission.effective_files(root, plan)
        admission._verify_hashes(root, {name: store.digest(value.encode()) for name, value in files.items()})
        for name, content in files.items():
            entries[name] = _entry(name, content, cycle_id, topic, relative)
        proofs.append(relative)
    for path in sorted(root.glob('reports/*/writing-admissions/*/accepted.yaml')):
        relative = path.relative_to(root).as_posix()
        receipt = admission._checked(root, relative)
        topic = path.parts[-4]
        expected = writing._base(topic, receipt['approval_id']) + '/accepted.yaml'
        if relative != expected:
            raise store.OfflineError('索引 Writing 记录路径不匹配: ' + relative)
        writing.verify(root, topic, receipt['approval_id'], historical=True)
        plan = admission._checked(root, receipt['plan_path'])
        for name, content in plan['files'].items():
            entries[name] = _entry(name, content, receipt['batch_id'], topic, relative)
        proofs.append(relative)
    return sorted(entries.values(), key=lambda item: (item['date'], item['path']), reverse=True), proofs


def render(root):
    entries, proofs = collect(root)
    latest = max((item['date'] for item in entries), default='尚无正式入库资料')
    lines = ['# 正式资料索引', '', '[研究首页](../研究首页.md) · [使用说明](README.md) · '
             '[Obsidian 动态视图](动态资料库.md) · [我的研究问题](../notes/我的研究问题.md)', '',
             '最新已核验轮次：**%s**。本区只列本地接受记录、准入计划和正式文件校验通过的成果。' % latest,
             '日期是研究轮次，标题沿用已保存的原文或中文研究标题。同步到本机后才能显示新成果；未自动翻译标题。', '',
             '选题卡是历史提案，当前确认、撤回与执行状态请查看[当前 Mac 选题页](http://127.0.0.1:8765)。'
             '在 iPhone 上该地址指向手机本机。趋势判断须保留正文中的证据、不确定性和观察范围。', '']
    for group, heading in GROUPS:
        lines += ['## ' + heading, '']
        selected = [item for item in entries if item['group'] == group]
        if not selected:
            lines += ['暂无已核验的正式资料。', '']
            continue
        lines += ['| 研究轮次 | 方向 | 资料 | 阅读范围 / 类型 |', '| --- | --- | --- | --- |']
        for item in selected:
            link = posixpath.relpath(item['path'], 'workbench')
            lines.append('| %s | %s | [%s](%s) | %s |' %
                         (_text(item['date']), _text(item['topic']), _text(item['title']), link, _text(item['coverage'])))
        lines += ['']
    lines += ['## 核验依据', '', '索引不重新研究原文，也不批准写作或发布。正式内容和人工笔记均不由索引生成器修改。', '']
    for path in sorted(proofs, key=lambda path: (_date(path.split('/')[-2]), path), reverse=True):
        lines.append('- [%s](%s)' % (_text(path.split('/')[-2]), posixpath.relpath(path, 'workbench')))
    return '\n'.join(lines).rstrip() + '\n'


def managed_document(existing, body):
    """Only replace a self-hashed region; keep all text outside it byte-for-byte."""
    block = START + store.digest(body.encode()) + ' -->\n' + body + END
    if START not in existing and END not in existing:
        # Adopt an old manual index without deleting its metadata or prose.
        prefix, history = '', existing
        if existing.startswith('---\n') and '\n---\n' in existing[4:]:
            end = existing.index('\n---\n', 4) + len('\n---\n')
            prefix, history = existing[:end], existing[end:]
        history_label = '\n\n---\n\n## 历史手工索引（保留快照，以下不自动更新）\n\n' if history else ''
        return prefix + '\n' + block + history_label + history
    pattern = re.compile(re.escape(START) + r'([0-9a-f]{64}) -->\n(.*?)' + re.escape(END), re.S)
    matches = list(pattern.finditer(existing))
    if len(matches) != 1 or existing.count(START) != 1 or existing.count(END) != 1:
        raise store.OfflineError('资料索引自动区标记缺失、重复或损坏，保留人工内容')
    match = matches[0]
    if store.digest(match.group(2).encode()) != match.group(1):
        raise store.OfflineError('资料索引自动区已被人工修改，请先移到标记区外；未覆盖')
    return existing[:match.start()] + block + existing[match.end():]


def update(root, write=False, check=False):
    root = Path(root).resolve()
    path = admission._location(root, TARGET)
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    document = managed_document(original, render(root))
    if check:
        return document == original
    if not write:
        return document
    if document == original:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.researchdesk-catalog-', delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(document)
            handle.flush()
            os.fsync(handle.fileno())
            if (path.read_text(encoding='utf-8') if path.exists() else '') != original:
                raise store.OfflineError('资料索引在生成期间被修改，保留人工内容')
            admission._location(root, TARGET)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return document != original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--write', action='store_true', help='仅更新固定索引文件的自动区')
    mode.add_argument('--check', action='store_true', help='只检查索引是否最新，不写文件')
    args = parser.parse_args()
    try:
        result = update(args.root, write=args.write, check=args.check)
    except (store.OfflineError, OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        print('资料索引停止：' + str(exc), file=sys.stderr)
        return 2
    if args.check:
        print('资料索引已更新' if result else '资料索引待更新；可显式执行 --write')
        return 0 if result else 1
    if args.write:
        print('资料索引已写入' if result else '资料索引无需更新')
    else:
        print(result, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
