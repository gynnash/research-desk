"""Read-only, hash-checked Writing progress for the confirmation page.

Reading historical results does not grant execution authority. Revoked approvals
can still expose their existing verified TEST drafts; dispatch uses active proof.
"""

from pathlib import Path

import researchdesk_offline as store
import researchdesk_admission as admission
import researchdesk_writing_member as writing
import researchdesk_writing_member_inputs as inputs


def _frozen(root, approval_id, confirmation_path, manifest):
    record = admission._checked(root, confirmation_path)
    preview = admission._checked(root, str(Path(confirmation_path).parent / 'preview.yaml'))
    payload = preview.get('payload', {})
    if (record.get('id') != approval_id or record.get('origin') != 'local_confirmation_page'
            or record.get('mode') != 'human_topic_confirmation' or record.get('decision') != 'confirmed'
            or record.get('preview_sha256') != store.digest(preview)
            or manifest.get('confirmation_path') != confirmation_path
            or manifest.get('confirmation_sha256') != store.digest((root / confirmation_path).read_bytes())
            or manifest.get('models') != payload.get('writing', {}).get('models')
            or manifest.get('topic') != record.get('topic')):
        raise store.OfflineError('Writing 结果不属于原始页面确认')
    checked = dict(payload)
    sha = checked.pop('preview_sha256', None)
    if store.digest(checked) != sha:
        raise store.OfflineError('原始写作预览已变化')
    material = inputs._material(payload)
    original_budget = payload['writing']['budget']
    if {key: manifest['budget'].get(key) for key in original_budget} != original_budget:
        raise store.OfflineError('Writing 结果的预算超出原确认范围')
    return {'approval_id': approval_id, 'topic': record['topic'], 'topic_card': material['topic_card'],
            'evidence': material['evidence'], 'models': manifest['models'],
            'input_fingerprint': manifest['input_fingerprint'], 'confirmation_path': confirmation_path,
            'material': material, 'coverage_note': payload['coverage_note'],
            'insights': payload['insights'], 'gaps': payload['evidence_gaps']}


def inspect(root, topic, approval_id, confirmation_path):
    root = Path(root).resolve()
    batch_id = writing.stable_batch_id(approval_id)
    base = 'reports/test/%s/writing-runs/%s' % (topic, batch_id)
    result = {'status': 'not_started', 'batch_id': batch_id, 'started': False,
              'stages': {}, 'reserved_calls': 0, 'completed_calls': 0, 'documents': [],
              'publish_authorized': False}
    if not store.safe_path(root, base + '/manifest.yaml').exists():
        return result
    result.update(started=True, status='in_progress')
    try:
        manifest = store.checked_yaml(root, base + '/manifest.yaml')
        if (manifest.get('mode') != 'writing_member_test' or manifest.get('backend') != 'chatgpt_plan'
                or manifest.get('approval_id') != approval_id or manifest.get('batch_id') != batch_id
                or manifest.get('topic') != topic or manifest.get('publish_authorized') is not False):
            raise store.OfflineError('Writing 清单身份无效')
        bundle = _frozen(root, approval_id, confirmation_path, manifest)
        events = store.read_events(root, base)
        known = writing.verify_ledger(root, base, events, manifest, bundle)
        from researchdesk_writing_job import _verify_bindings
        _verify_bindings(root, base, events, manifest, bundle)
        result['reserved_calls'] = sum(event['type'] == 'call_reserved' for event in events)
        result['completed_calls'] = sum(event['type'] == 'call_completed' for event in events)
        for event in events:
            if event['type'] == 'stage_accepted':
                result['stages'][event['stage']] = {'status': 'test_accepted', 'revision_count': event['revision']}
        if not known:
            result.update(status='unknown_request', reason='有真实请求结果未知，系统不会自动重发。')
            return result
        receipt_path = base + '/receipt.yaml'
        if not store.safe_path(root, receipt_path).exists():
            if list(store.safe_path(root, base + '/partial').glob('*.yaml')):
                result.update(status='paused', reason='已有检查点，待恢复同一批次；不会重复已完成的模型请求。')
            return result
        receipt = store.checked_yaml(root, receipt_path)
        if (receipt.get('mode') != 'writing_member_test' or receipt.get('backend') != 'chatgpt_plan'
                or receipt.get('approval_id') != approval_id or receipt.get('batch_id') != batch_id
                or receipt.get('topic') != topic or receipt.get('models') != manifest['models']
                or receipt.get('confirmation_path') != confirmation_path
                or receipt.get('reserved_calls') != result['reserved_calls']
                or receipt.get('completed_calls') != result['completed_calls']
                or receipt.get('publish_authorized') is not False
                or receipt.get('production_accepted') is not False):
            raise store.OfflineError('Writing 回执与完整账本不一致')
        status = receipt.get('status')
        if status != 'test_accepted':
            if status not in {'revision_required', 'rejected', 'blocked'} or receipt.get('output_hashes'):
                raise store.OfflineError('未审阅通过的 Writing 不能有文章产物')
            result['status'] = status
            return result
        if set(result['stages']) != set(writing.STAGES):
            raise store.OfflineError('Writing 缺少三个独立审阅通过的阶段')
        expected, documents = {}, []
        names = {'outline': '文章大纲', 'draft': '文章初稿', 'candidate': '发布候选稿（TEST）'}
        for stage in writing.STAGES:
            candidate = store.checked_yaml(root, '%s/stages/%s.yaml' % (base, stage))['candidate']
            path, content = writing.render(stage, candidate, bundle, batch_id)
            target = admission._location(root, path)
            if not target.is_file() or target.read_bytes() != content.encode('utf-8'):
                raise store.OfflineError('已有 Writing 稿件被修改或缺失，保留原文件')
            expected[path] = store.digest(target.read_bytes())
            documents.append({'stage': stage, 'label': names[stage], 'path': path, 'sha256': expected[path]})
        if (store.checked_yaml(root, base + '/artifact-plan.yaml') != {'files': expected}
                or receipt.get('output_hashes') != expected):
            raise store.OfflineError('Writing 三稿与原产物清单散列不同')
        result.update(status='test_accepted', documents=documents)
        return result
    except (store.OfflineError, OSError, ValueError, KeyError, TypeError, RuntimeError):
        result.update(status='integrity_blocked', reason='写作记录或稿件校验未通过，已保留文件，暂停派发与展示。')
        return result
