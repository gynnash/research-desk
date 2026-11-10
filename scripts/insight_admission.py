#!/usr/bin/env python3
"""Create-only formal admission of independently reviewed Codex Insight prose.

Admission reuses the exact SDK candidate, original Research proofs and review.
It never invokes a model, opens credentials, or fetches sources. Portable topic
configuration snapshots let a clean checkout verify historical results without
copying the operator's private configuration into that checkout.
"""

import argparse
import json
from pathlib import Path
import re

import yaml

import admission as legacy
import archive
import harness
import insight_inputs as inputs
import note_paths
import offline as store


MODE = 'codex_insight_admission'
PATH_SCHEME = 'descriptive-v1'
HASH = re.compile(r'[0-9a-f]{64}\Z')
CONFIG = re.compile(r'config/(?:research_topics\.yaml|local/automation/[a-z0-9_-]+/topics\.yaml)\Z')


def base_path(topic, cycle_id):
    return legacy._base(topic, cycle_id)


def _read(root, relative):
    target = legacy._location(root, relative)
    if not target.is_file():
        raise store.OfflineError('正式准入所需文件不存在: ' + relative)
    return target.read_bytes()


def _checked(root, relative):
    return legacy._checked(root, relative)


def _verify_bindings(root, bindings, snapshots=None):
    if not isinstance(bindings, dict) or not bindings:
        raise store.OfflineError('Insight 缺少已绑定的输入或输出')
    for relative, expected in bindings.items():
        if not isinstance(relative, str) or not isinstance(expected, str) or not HASH.fullmatch(expected):
            raise store.OfflineError('Insight 内容散列绑定无效')
        # These are immutable research-topic inputs, not today's user settings.
        # All source prose and actual review proofs must still exist on disk.
        if snapshots is not None and relative in snapshots:
            payload = snapshots[relative].encode('utf-8')
        else:
            payload = _read(root, relative)
        if store.digest(payload) != expected:
            raise store.OfflineError('Insight 已绑定内容发生变化: ' + relative)


def _snapshots(root, hashes, supplied=None):
    names = {relative for relative in hashes if CONFIG.fullmatch(relative)}
    if supplied is not None and (not isinstance(supplied, dict) or set(supplied) != names):
        raise store.OfflineError('正式准入主题快照范围无效')
    result = {}
    for relative in sorted(names):
        text = supplied[relative] if supplied is not None else _read(root, relative).decode('utf-8')
        if not isinstance(text, str) or store.digest(text.encode()) != hashes[relative]:
            raise store.OfflineError('正式准入主题快照散列无效')
        archive.check_public_tokens(text)
        try:
            value = yaml.load(text, Loader=store.UniqueKeyLoader)
        except yaml.YAMLError as exc:
            raise store.OfflineError('正式准入主题快照不是有效 YAML') from exc
        if not isinstance(value, dict) or set(value) != {'schema_version', 'topics'}:
            raise store.OfflineError('只允许携带公开研究主题快照，不能携带私人运行配置')
        result[relative] = text
    return result


def _verify_sdk(root, topic, cycle_id, supplied_snapshots=None):
    """Validate portable evidence without consulting current private settings."""
    base_path(topic, cycle_id)
    prefix = 'reports/test/%s/codex-insight/%s/' % (topic, cycle_id)
    accepted_path = prefix + 'accepted.yaml'
    receipt = _checked(root, accepted_path)
    if (receipt.get('topic') != topic or receipt.get('cycle_id') != cycle_id
            or receipt.get('backend') != 'codex' or receipt.get('simulation') is not False
            or receipt.get('status') not in {'complete', 'no_insight'}
            or receipt.get('review_policy') != 'accuracy_only'
            or receipt.get('review_decision') != 'pass'
            or receipt.get('writing_started') is not False
            or receipt.get('production_accepted') is not False):
        raise store.OfflineError('只有真实后端且独立审阅通过的 Insight 可以正式准入')
    input_hashes, output_hashes = receipt.get('input_hashes'), receipt.get('output_hashes')
    if (not isinstance(input_hashes, dict) or not isinstance(output_hashes, dict)
            or set(receipt.get('outputs', [])) != set(output_hashes)):
        raise store.OfflineError('Insight 输入输出未完整绑定')
    snapshots = _snapshots(root, input_hashes, supplied_snapshots)
    _verify_bindings(root, input_hashes, snapshots)
    _verify_bindings(root, output_hashes)
    if not {prefix + 'candidate.yaml', prefix + 'review.yaml'}.issubset(output_hashes):
        raise store.OfflineError('Insight 候选或独立审阅证明缺失')
    candidate = store.load_yaml(legacy._location(root, prefix + 'candidate.yaml'))
    review = store.load_yaml(legacy._location(root, prefix + 'review.yaml'))
    decision = harness._review(json.dumps(review.get('review'), ensure_ascii=False))
    if (review.get('policy') != 'accuracy_only' or decision.get('decision') != 'pass'
            or review.get('candidate_sha256') != harness._sha(candidate)):
        raise store.OfflineError('独立准确性审阅没有绑定此 Insight 候选')
    model_proofs = receipt.get('models', {})
    models = {role: model_proofs.get(role, {}).get('requested_model') for role in ('generation', 'review')}
    if (any(not isinstance(value, str) or not value or value.startswith('mock-') for value in models.values())
            or models['generation'] == models['review'] or review.get('requested_model') != models['review']):
        raise store.OfflineError('Insight 生成与独立审阅模型绑定无效')
    observed = [model_proofs.get(role, {}).get('observed_model') for role in ('generation', 'review')]
    if all(observed) and observed[0] == observed[1]:
        raise store.OfflineError('Insight 生成与审阅实际使用了相同模型')
    if review.get('observed_model') != observed[1]:
        raise store.OfflineError('Insight 审阅响应模型与回执不一致')
    current, historical = [], []
    for relative in sorted(input_hashes):
        if relative.startswith('summary/' + topic + '/') and relative.endswith('.md'):
            proof = {}
            source = inputs._codex_summary(root, relative, topic, proof)
            if any(input_hashes.get(path) != value for path, value in proof.items()):
                raise store.OfflineError('Research 证明未纳入 Insight 固定输入')
            source.pop('_identities', None)
            (current if note_paths.summary_ids(relative)[1] == cycle_id else historical).append(source)
    if not current:
        raise store.OfflineError('Insight 没有本批已独立审阅的 Research 输入')
    historical.sort(key=lambda item: (item['research_date'], item['summary_path']), reverse=True)
    sources = [dict(source, id=('R' if role == 'current' else 'H') + str(number), role=role)
               for role, values in [('current', current), ('history', historical)]
               for number, source in enumerate(values, 1)]
    bundle = {'topic': topic, 'cycle_id': cycle_id, 'sources': sources}
    if harness._candidate(json.dumps(candidate, ensure_ascii=False), bundle) != candidate:
        raise store.OfflineError('Insight 候选不符合其固定原文集合')
    state = {'backend': 'codex', 'review': decision, 'tasks': {'review': {'result': {
        'requested_model': review.get('requested_model'), 'observed_model': review.get('observed_model'),
        'thread_id': review.get('thread_id'), 'turn_id': review.get('turn_id'), 'final_response': '{}'}}}}
    rendered = harness._render(candidate, bundle, state, False)
    if set(rendered) != set(output_hashes):
        raise store.OfflineError('Insight 输出不对应原候选渲染')
    for relative, text in rendered.items():
        if relative.endswith('.md') and _read(root, relative) != text.encode():
            raise store.OfflineError('Insight 可读输出已变化，保留人工内容')
    return {'candidate': candidate, 'bundle': bundle, 'models': models,
            'input_hashes': input_hashes, 'sdk_output_hashes': output_hashes,
            'configuration_snapshots': snapshots, 'sdk_accepted_path': accepted_path,
            'sdk_proof_paths': [accepted_path, accepted_path + '.sha256',
                                prefix + 'candidate.yaml', prefix + 'review.yaml']}


def _render(value):
    topic, cycle = value['topic'], value['cycle_id']
    bundle, candidate = value['bundle'], value['candidate']
    dates = [source.get('research_date') for source in bundle['sources'] if source.get('research_date')]
    common = {'schema_version': 2, 'topic': topic, 'topics': [topic], 'cycle_id': cycle,
              'backend': 'codex', 'review_status': 'passed', 'review_policy': 'accuracy_only',
              'production_accepted': True, 'created_at': max(dates) if dates else None}

    def markdown(metadata, body):
        return '---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---\n\n' + body.rstrip() + '\n'

    report = candidate['report']
    if value.get('path_scheme') == PATH_SCHEME:
        heading = candidate['insights'][0]['title'] if candidate['insights'] else report['title']
        folder = note_paths.named_component(note_paths.note_label(heading, report['title'], '研究洞察'), cycle)
        name = note_paths.note_label(report['title'], heading, '综合洞察')
        report_path = 'insights/%s/%s/%s.md' % (topic, folder, name)
    else:
        report_path = 'insights/%s/%s/report.md' % (topic, cycle)
    body = '# ' + report['title'] + '\n\n' + report['body']
    for insight in candidate['insights']:
        body += '\n\n## ' + insight['title'] + '\n\n' + insight['body']
    body += '\n\n' + harness._sources(bundle, report_path)
    files = {report_path: markdown({**common, 'kind': 'insight_report', 'title': report['title'],
                                   'outcome': candidate['outcome']}, body)}
    for number, card in enumerate(candidate['topics'], 1):
        relative = 'articles/%s/%s-topic-%s.md' % (topic, cycle, number)
        identifiers = card.get('source_ids') or [source['id'] for source in bundle['sources']]
        body = '# ' + card['title'] + '\n\n' + card['angle'] + '\n\n目标读者：' + card['audience']
        for key, label in [('key_questions', '拟回答的问题'), ('evidence_gaps', '写作前待核实')]:
            if isinstance(card.get(key), list) and card[key]:
                body += '\n\n## ' + label + '\n\n' + '\n'.join('- ' + str(item) for item in card[key])
        body += '\n\n' + harness._sources(bundle, relative, identifiers)
        files[relative] = markdown({**common, 'kind': 'topic_proposal',
            'id': 'formal-topic-%s-%s-%s' % (topic, cycle, number), 'title': card['title'],
            'status': 'proposed', 'evidence_ids': identifiers, 'approval_required': True,
            'writing_started': False, 'publish_authorized': False}, body)
    return files


def _plan(root, topic, cycle_id, configuration_snapshots=None, *, path_scheme=PATH_SCHEME):
    if path_scheme not in (None, PATH_SCHEME):
        raise store.OfflineError('无法识别正式洞察文件命名方式')
    verified = _verify_sdk(root, topic, cycle_id, configuration_snapshots)
    # Originals already have a single canonical home in collection/. Keep the
    # portable plan small instead of duplicating six months of full text here.
    verified['bundle']['sources'] = [{key: field for key, field in source.items()
                                     if key not in {'summary_text', 'original_text'}}
                                    for source in verified['bundle']['sources']]
    value = {'schema_version': 2, 'mode': MODE, 'topic': topic, 'cycle_id': cycle_id, **verified}
    if path_scheme is not None:
        value['path_scheme'] = path_scheme
    files = _render(value)
    value['files'] = files
    value['output_hashes'] = {relative: store.digest(text.encode()) for relative, text in files.items()}
    value['proof_hashes'] = {relative: store.digest(_read(root, relative))
                             for relative in value['sdk_proof_paths']}
    return value


def _receipt(plan, plan_path, plan_sha256):
    return {'schema_version': 2, 'mode': MODE, 'topic': plan['topic'], 'cycle_id': plan['cycle_id'],
            'status': 'accepted', 'production_accepted': True, 'simulation': False,
            'review_policy': 'accuracy_only', 'review_decision': 'pass', 'models': plan['models'],
            'plan_path': plan_path, 'plan_sha256': plan_sha256,
            'input_hashes': plan['input_hashes'], 'output_hashes': plan['output_hashes'],
            'proof_hashes': plan['proof_hashes'], 'writing_started': False, 'publish_authorized': False}


def load(root, topic, cycle_id):
    """Read and fully revalidate a formal admission; never create missing files."""
    root = Path(root).resolve()
    base = base_path(topic, cycle_id)
    plan_path, accepted_path = base + '/plan.yaml', base + '/accepted.yaml'
    saved = _checked(root, plan_path)
    if saved.get('mode') != MODE or saved.get('schema_version') != 2:
        raise store.OfflineError('不是新版 Codex Insight 准入')
    expected = _plan(root, topic, cycle_id, saved.get('configuration_snapshots'),
                     path_scheme=saved.get('path_scheme'))
    if saved != expected:
        raise store.OfflineError('正式准入计划与固定原文、候选或独立审阅不一致')
    expected_receipt = _receipt(saved, plan_path, store.digest(_read(root, plan_path)))
    if _checked(root, accepted_path) != expected_receipt:
        raise store.OfflineError('正式准入回执未绑定本计划')
    _verify_bindings(root, saved['output_hashes'])
    proof_paths = [plan_path, plan_path + '.sha256', accepted_path, accepted_path + '.sha256'] + saved['sdk_proof_paths']
    proof_hashes = {relative: store.digest(_read(root, relative)) for relative in proof_paths}
    bundle = {**saved['bundle'], 'sources': [dict(source,
        summary_text=_read(root, source['summary_path']).decode('utf-8'),
        original_text=_read(root, source['original_path']).decode('utf-8'))
        for source in saved['bundle']['sources']]}
    return {**saved, 'bundle': bundle, 'accepted_path': accepted_path,
            'proof_paths': proof_paths, 'proof_hashes': proof_hashes}


def admit(root, topic, cycle_id):
    """Verify first, then add formal prose and the receipt without overwriting."""
    root = Path(root).resolve()
    base = base_path(topic, cycle_id)
    accepted_path = base + '/accepted.yaml'
    if (legacy._location(root, accepted_path).exists()
            and legacy._location(root, accepted_path + '.sha256').exists()):
        value = load(root, topic, cycle_id)
        return {'status': 'accepted', 'accepted_path': accepted_path,
                'receipt_path': accepted_path, 'production_accepted': True,
                'outputs': list(value['output_hashes']), 'model_calls': 0, 'cached': True}
    plan_path = base + '/plan.yaml'
    old_plan = None
    if legacy._location(root, plan_path).exists():
        # A process may stop between a YAML write and its SHA sidecar. Its
        # contents are trusted only after full reconstruction against SDK proof.
        old_plan = (_checked(root, plan_path)
                    if legacy._location(root, plan_path + '.sha256').exists()
                    else store.load_yaml(legacy._location(root, plan_path)))
    if old_plan is None:
        plan = _plan(root, topic, cycle_id)
    else:
        plan = _plan(root, topic, cycle_id, old_plan.get('configuration_snapshots'),
                     path_scheme=old_plan.get('path_scheme'))
        if old_plan != plan:
            raise store.OfflineError('未完成准入计划已有变化，保留现场')
    plan_text = yaml.safe_dump(plan, allow_unicode=True, sort_keys=False)
    plan_sha = store.digest(plan_text.encode())
    receipt_text = yaml.safe_dump(_receipt(plan, plan_path, plan_sha), allow_unicode=True, sort_keys=False)
    outputs = {**plan['files'], plan_path: plan_text, plan_path + '.sha256': plan_sha + '\n',
               accepted_path: receipt_text, accepted_path + '.sha256': store.digest(receipt_text.encode()) + '\n'}
    # Check the entire set before writing anything, including marker conflicts.
    for relative, text in outputs.items():
        target = legacy._location(root, relative)
        for parent in target.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise store.OfflineError('正式输出父目录已有人工文件，保留内容: ' + relative)
        if target.exists() and (not target.is_file() or target.read_bytes() != text.encode()):
            raise store.OfflineError('正式输出位置已有人工修改，保留内容: ' + relative)
    for relative, text in outputs.items():
        legacy._create(root, relative, text)
    return {'status': 'accepted', 'accepted_path': accepted_path,
            'receipt_path': accepted_path, 'production_accepted': True,
            'outputs': list(plan['output_hashes']), 'model_calls': 0, 'cached': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('admit', 'check'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--topic', required=True)
    parser.add_argument('--cycle-id', required=True)
    args = parser.parse_args()
    try:
        result = (admit(args.root, args.topic, args.cycle_id) if args.operation == 'admit' else
                  {'status': 'verified', 'accepted_path': load(args.root, args.topic, args.cycle_id)['accepted_path'],
                   'model_calls': 0})
    except (store.OfflineError, OSError, ValueError) as exc:
        parser.exit(1, 'Insight 准入停止：' + str(exc) + '\n')
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))


if __name__ == '__main__':
    main()
