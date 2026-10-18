#!/usr/bin/env python3
"""One bounded discovery -> Research -> Insight cycle, using existing reviewed stages."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import os
from pathlib import Path
import sys
import tempfile

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import researchdesk_offline as store
import researchdesk_batch_inputs as common
import researchdesk_batch as research
import researchdesk_insight as insight
import researchdesk_cycle_discovery as discovery


def load_config(root, path):
    root = Path(root).resolve()
    path = common.config_path(root, path)
    config = store.load_yaml(path)
    common.fields(config, {'schema_version', 'mode', 'backend', 'topic', 'topics_file', 'window',
                          'discovery', 'models', 'budget', 'history'}, '研究轮次配置')
    if type(config['schema_version']) is not int or config['schema_version'] != 1 or config['mode'] != 'research_cycle_test' or config['backend'] != 'chatgpt_plan':
        raise store.OfflineError('当前研究轮次只支持真实会员的 research_cycle_test')
    if not isinstance(config['topic'], str) or not store.SAFE_ID.fullmatch(config['topic']):
        raise store.OfflineError('研究方向ID无效')
    topic_path = common.config_path(root, config['topics_file'])
    topic = store.load_yaml(topic_path).get('topics', {}).get(config['topic'])
    if not isinstance(topic, dict) or topic.get('enabled') is not True:
        raise store.OfflineError('研究方向未启用')
    common.fields(config['models'], {'research', 'insight', 'review'}, '轮次模型')
    if any(not isinstance(x, str) or not x.strip() for x in config['models'].values()) or config['models']['review'] in {config['models']['research'], config['models']['insight']}:
        raise store.OfflineError('生成与独立审阅必须配置不同模型')
    common.fields(config['window'], {'initial_days', 'overlap_hours'}, '扫描时间窗')
    common.positive(config['window']['initial_days'], 1, 365, 'initial_days')
    common.positive(config['window']['overlap_hours'], 0, 168, 'overlap_hours')
    ranges = {'max_calls_per_cycle': (4, 20), 'research_max_calls': (2, 8), 'insight_max_calls': (2, 4),
              'max_input_chars': (1000, 30000), 'max_output_chars': (1000, 12000),
              'timeout_seconds': (1, 120), 'max_revisions': (0, 1)}
    common.fields(config['budget'], ranges, '轮次预算')
    for key, (low, high) in ranges.items():
        common.positive(config['budget'][key], low, high, key)
    if config['budget']['research_max_calls'] + config['budget']['insight_max_calls'] > config['budget']['max_calls_per_cycle']:
        raise store.OfflineError('子阶段预算之和超过轮次上限')
    common.fields(config['history'], {'max_documents'}, '历史选择')
    common.positive(config['history']['max_documents'], 1, 10, 'max_documents')
    common.fields(config['discovery'], {'max_candidates', 'max_documents', 'max_per_source', 'evidence_max_chars', 'sources'}, '资料发现')
    for key, bounds in {'max_candidates': (1,20), 'max_documents': (1,2), 'max_per_source': (1,1), 'evidence_max_chars': (200,10000)}.items():
        common.positive(config['discovery'][key], *bounds, key)
    config.update(_config_path=path.relative_to(root).as_posix(), _config_sha256=store.digest(path.read_bytes()),
                  _topics_sha256=store.digest(topic_path.read_bytes()))
    return config


@contextmanager
def cycle_lock(root, topic):
    path = Path(tempfile.gettempdir()) / ('researchdesk-cycle-' + store.digest([str(root), topic])[:24] + '.lock')
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise store.OfflineError('当前方向另有研究轮次运行') from exc
        yield
    finally:
        os.close(fd)


def base_path(config, cycle_id):
    if not isinstance(cycle_id, str) or not store.SAFE_ID.fullmatch(cycle_id):
        raise store.OfflineError('轮次ID无效')
    return 'reports/test/%s/cycles/%s' % (config['topic'], cycle_id)


def discover_cycle(root, config_path, cycle_id, fetcher=None):
    root = Path(root).resolve()
    config = load_config(root, config_path)
    base = base_path(config, cycle_id)
    manifest_path = base + '/manifest.yaml'
    if store.safe_path(root, manifest_path).exists():
        manifest = store.checked_yaml(root, manifest_path)
        if manifest['config'] != config:
            raise store.OfflineError('轮次已绑定配置与研究方向，不能重置')
    else:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=config['window']['initial_days'])
        # Resume from the last fully covered source window. Bounded publisher
        # listings never advance an unproven archive cursor.
        prior_receipts = sorted((root / ('reports/test/' + config['topic'] + '/cycles')).glob('*/receipt.yaml'))
        cursors = []
        for path in prior_receipts:
            previous = store.checked_yaml(root, path.relative_to(root))
            if previous.get('discovery_complete') and previous.get('window_end'):
                cursors.append(previous['window_end'])
        if cursors:
            start = datetime.fromisoformat(max(cursors)) - timedelta(hours=config['window']['overlap_hours'])
        manifest = {'schema_version':1, 'mode':'research_cycle_test', 'backend':'chatgpt_plan',
                    'cycle_id':cycle_id, 'topic':config['topic'], 'config':config,
                    'window_start':start.isoformat(), 'window_end':end.isoformat(),
                    'protected_notes':research.notes_snapshot(root), 'production_accepted':False}
        store.save_yaml(root, manifest_path, manifest)
    research.verify_notes(root, manifest['protected_notes'])
    snapshot_path = base + '/discovery.yaml'
    if not store.safe_path(root, snapshot_path).exists():
        resolved = dict(config, window_start=manifest['window_start'], window_end=manifest['window_end'])
        snapshot = discovery.discover(root, resolved, cycle_id, fetcher=fetcher)
        store.save_yaml(root, snapshot_path, snapshot)
    else:
        snapshot = store.checked_yaml(root, snapshot_path)
    return config, manifest, snapshot


def _cached(root, receipt):
    for path, expected in receipt.get('input_hashes', {}).items():
        if not (root/path).is_file() or store.digest((root/path).read_bytes()) != expected:
            raise store.OfflineError('轮次输入或下游回执已变化，保留现场: ' + path)
    for path, expected in receipt.get('output_hashes', {}).items():
        if not (root/path).is_file() or store.digest((root/path).read_bytes()) != expected:
            raise store.OfflineError('产物被人工修改，不覆盖: ' + path)
    return dict(receipt, cached=True)


def run(root, config_path, cycle_id, client=None, fetcher=None, fail_after=None):
    root = Path(root).resolve()
    initial = load_config(root, config_path)
    base = base_path(initial, cycle_id)
    if fail_after not in (None, 'after_research'):
        raise store.OfflineError('无效轮次断点')
    with cycle_lock(root, initial['topic']):
        config, manifest, snapshot = discover_cycle(root, config_path, cycle_id, fetcher=fetcher)
        receipt_path = base + '/receipt.yaml'
        if store.safe_path(root, receipt_path).exists():
            return _cached(root, store.checked_yaml(root, receipt_path))
        input_hashes = {base+'/manifest.yaml':store.digest((root/base/'manifest.yaml').read_bytes()),
                        base+'/discovery.yaml':store.digest((root/base/'discovery.yaml').read_bytes())}
        results, outputs, pending = {}, {}, list(snapshot.get('deferred', []))
        candidates = snapshot['candidates']
        status = 'no_new' if snapshot.get('status') == 'complete' else 'partial'
        if candidates:
            history_path = base + '/history.yaml'
            if store.safe_path(root, history_path).exists():
                historical = store.checked_yaml(root, history_path)['items']
            else:
                historical = discovery.select_history(root, config['topic'], config['history']['max_documents'])
                store.save_yaml(root, history_path, {'items':historical})
            if not historical:
                status = 'awaiting_history'
                pending += [dict(item, reason='history_unavailable') for item in candidates]
            else:
                for item in historical:
                    input_hashes[item['path']] = item['sha256']
                input_hashes[history_path] = store.digest((root/history_path).read_bytes())
                budget = config['budget']
                monthly_cap = research.membership_monthly_limit(root) or 10
                research_cfg = {'schema_version':1, 'mode':'research_batch_test', 'backend':'chatgpt_plan',
                    'topic':config['topic'], 'topics_file':config['topics_file'],
                    'models':{'research':config['models']['research'], 'review':config['models']['review']},
                    'budget':{'max_documents':len(candidates), 'max_calls_per_item':4,
                        'max_calls_per_batch':min(budget['research_max_calls'],len(candidates)*4), 'month_max_calls':monthly_cap,
                        **{key:budget[key] for key in ('max_input_chars','max_output_chars','timeout_seconds','max_revisions')}},
                    'prompts':{'version':'research-batch-v1'}, 'sources':[item['source'] for item in candidates]}
                research_path = base + '/configs/research.yaml'
                store.save_yaml(root, research_path, research_cfg)
                result_path = base + '/research-result.yaml'
                if store.safe_path(root, result_path).exists():
                    research_result = store.checked_yaml(root, result_path)
                else:
                    if client is None:
                        from researchdesk_membership import MembershipClient
                        client = MembershipClient(root=root)
                    research_result = research.run(root, Path(research_path), cycle_id, client, fetcher=fetcher)
                    research_result = {key:value for key,value in research_result.items() if key != 'cached'}
                    store.save_yaml(root, result_path, research_result)
                results['research'] = research_result
                input_hashes[result_path] = store.digest((root/result_path).read_bytes())
                input_hashes[research_path] = store.digest((root/research_path).read_bytes())
                original_receipt = research_result['receipt_path']
                input_hashes[original_receipt] = store.digest((root/original_receipt).read_bytes())
                if fail_after == 'after_research' and not store.safe_path(root, base+'/interruption.yaml').exists():
                    store.save_yaml(root, base+'/interruption.yaml', {'phase':'after_research','reserved_calls':research_result['reserved_calls']})
                    raise store.SimulatedInterruption('Research已保存；同轮补跑只继续Insight')
                keys = [item['key'] for item in research_result['items'] if item['status']=='test_accepted']
                for item in research_result['items']:
                    if item['status'] not in {'test_accepted','duplicate','rejected','reject','revise'}:
                        source = next(candidate for candidate in candidates if candidate['source']['id']==item['key'])
                        pending.append(dict(source, reason=item.get('reason',item['status'])))
                if keys:
                    insight_cfg = {'schema_version':1,'mode':'insight_test','backend':'chatgpt_plan','topic':config['topic'],
                        'topics_file':config['topics_file'],'models':{'generation':config['models']['insight'],'review':config['models']['review']},
                        'budget':{'max_calls':budget['insight_max_calls'],'month_max_calls':monthly_cap,
                                  **{key:budget[key] for key in ('max_input_chars','max_output_chars','timeout_seconds','max_revisions')}},
                        'prompts':{'version':'insight-v1'},'research_inputs':[{'receipt':original_receipt,'config':research_path,'item_keys':keys}],
                        'historical_inputs':historical}
                    insight_path = base+'/configs/insight.yaml'
                    store.save_yaml(root, insight_path, insight_cfg)
                    if client is None:
                        from researchdesk_membership import MembershipClient
                        client=MembershipClient(root=root)
                    insight_result = insight.run(root, Path(insight_path), cycle_id, client, fetcher=fetcher)
                    results['insight'] = {key:value for key,value in insight_result.items() if key!='cached'}
                    store.save_yaml(root, base+'/insight-result.yaml', results['insight'])
                    input_hashes[insight_path]=store.digest((root/insight_path).read_bytes())
                    input_hashes[base+'/insight-result.yaml']=store.digest((root/base/'insight-result.yaml').read_bytes())
                    child_receipt='reports/test/%s/insight-runs/%s/receipt.yaml'%(config['topic'],cycle_id)
                    if (root/child_receipt).is_file():input_hashes[child_receipt]=store.digest((root/child_receipt).read_bytes())
                    outputs=insight_result.get('output_hashes',{})
                    status='completed' if insight_result['status']=='test_accepted' else 'insight_blocked'
                    if status=='completed' and snapshot.get('status')!='complete':status='partial'
                else:
                    status='no_accepted_research'
        research.verify_notes(root, manifest['protected_notes'])
        store.save_yaml(root,base+'/pending.yaml',{'items':pending})
        receipt={'schema_version':1,'mode':'research_cycle_test','backend':'chatgpt_plan','topic':config['topic'],
                 'cycle_id':cycle_id,'status':status,'window_start':manifest['window_start'],'window_end':manifest['window_end'],
                 'discovery_complete':snapshot.get('status')=='complete','source_status':snapshot.get('source_status',[]),
                 'stages':{key:{'status':value['status'],'reserved_calls':value['reserved_calls']} for key,value in results.items()},
                 'reserved_calls':sum(value['reserved_calls'] for value in results.values()),'pending_count':len(pending),
                 'input_hashes':input_hashes,'output_hashes':outputs,'production_accepted':False,
                 'writing_started':False,'publish_authorized':False}
        store.save_yaml(root,receipt_path,receipt)
        return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('discover','run'):
        command=commands.add_parser(name)
        command.add_argument('--config',type=Path,required=True)
        command.add_argument('--cycle-id',required=True)
        command.add_argument('--profile',type=Path)
        command.add_argument('--fail-after',choices=['after_research'])
    args=parser.parse_args()
    try:
        if args.command=='discover':
            result=discover_cycle(args.root,args.config,args.cycle_id)[2]
        else:
            client=None
            if args.profile:
                from researchdesk_membership import MembershipClient
                client=MembershipClient(args.profile,args.root)
            result=run(args.root,args.config,args.cycle_id,client,fail_after=args.fail_after)
    except store.SimulatedInterruption as exc:
        print(str(exc),file=sys.stderr);return 3
    except Exception as exc:
        print('研究轮次停止：'+type(exc).__name__,file=sys.stderr);return 2
    print(yaml.safe_dump(result,allow_unicode=True,sort_keys=False))
    return 0 if result.get('status') in {'completed','no_new','partial','complete'} else 1


if __name__=='__main__':sys.exit(main())
