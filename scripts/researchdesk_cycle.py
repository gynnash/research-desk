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
from researchdesk_sources import SafeFetcher


def load_config(root, path, snapshot=None):
    root = Path(root).resolve()
    path = common.config_path(root, path)
    relative = path.relative_to(root).as_posix()
    if snapshot is None:
        config = store.load_yaml(path)
        config_sha256 = store.digest(path.read_bytes())
    else:
        # Only a caller holding a checked historical cycle manifest may supply
        # this snapshot. Revalidate its public configuration without replacing
        # the old budgets/config digest with today's live configuration.
        import re
        private = {'_config_path', '_config_sha256', '_topics_sha256'}
        if (not isinstance(snapshot, dict) or snapshot.get('_config_path') != relative
                or {key for key in snapshot if key.startswith('_')} != private
                or any(not isinstance(snapshot.get(key), str) or
                       not re.fullmatch(r'[0-9a-f]{64}', snapshot[key])
                       for key in ('_config_sha256', '_topics_sha256'))):
            raise store.OfflineError('历史轮次配置快照绑定无效')
        config = {key: value for key, value in snapshot.items() if key not in private}
        config_sha256 = snapshot['_config_sha256']
    common.fields(config, {'schema_version', 'mode', 'backend', 'topic', 'topics_file', 'window',
                          'discovery', 'models', 'budget', 'history'} |
                  ({'reading'} if 'reading' in config else set()) |
                  ({'selection'} if 'selection' in config else set()) |
                  ({'archive'} if 'archive' in config else set()) |
                  ({'presentation'} if 'presentation' in config else set()), '研究轮次配置')
    if 'presentation' in config and config['presentation'] != 'technical_article':
        raise store.OfflineError('presentation 仅支持 technical_article')
    if 'presentation' in config and 'lookback_days' not in config['history']:
        raise store.OfflineError('技术文章式输出须配置显式 history.lookback_days 时间窗')
    if 'archive' in config and type(config['archive']) is not bool:
        raise store.OfflineError('archive 必须是显式布尔值')
    if 'selection' in config:
        common.fields(config['selection'], {'mode', 'min_score', 'max_requests'}, '候选排序')
        if (config['selection']['mode'] != 'community_attention'
                or type(config['selection']['min_score']) not in (int, float)
                or not 0 < config['selection']['min_score'] <= 100):
            raise store.OfflineError('仅支持有可核实信号的社区关注度排序')
        common.positive(config['selection']['max_requests'], 1, 500, 'max_requests')
    if 'reading' in config:
        common.fields(config['reading'], {'mode', 'paper_max_chars'} |
                      ({'blog_max_chars'} if 'blog_max_chars' in config['reading'] else set()), '原文阅读配置')
        if config['reading']['mode'] not in {'full_text_preferred', 'full_text_required'}:
            raise store.OfflineError('论文阅读模式无效')
        common.positive(config['reading']['paper_max_chars'], 2000, 200000, 'paper_max_chars')
        if 'blog_max_chars' in config['reading']:
            common.positive(config['reading']['blog_max_chars'], 2000, 200000, 'blog_max_chars')
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
    if config['window'].get('mode') == 'rolling':
        common.fields(config['window'], {'mode', 'days'}, '滚动采集时间窗')
        common.positive(config['window']['days'], 1, 365, 'days')
    else:
        common.fields(config['window'], {'initial_days', 'overlap_hours'}, '扫描时间窗')
        common.positive(config['window']['initial_days'], 1, 365, 'initial_days')
        common.positive(config['window']['overlap_hours'], 0, 168, 'overlap_hours')
    ranges = {'max_calls_per_cycle': (4, 20), 'research_max_calls': (2, 16), 'insight_max_calls': (2, 4),
              'max_input_chars': (1000, 600000), 'max_output_chars': (1000, 24000),
              'timeout_seconds': (1, 300 if config.get('reading', {}).get('mode') == 'full_text_required' else 120),
              'max_revisions': (0, 1)}
    common.fields(config['budget'], ranges, '轮次预算')
    for key, (low, high) in ranges.items():
        common.positive(config['budget'][key], low, high, key)
    if config['budget']['research_max_calls'] + config['budget']['insight_max_calls'] > config['budget']['max_calls_per_cycle']:
        raise store.OfflineError('子阶段预算之和超过轮次上限')
    common.fields(config['history'], {'max_documents'} |
                  ({'lookback_days'} if 'lookback_days' in config['history'] else set()), '历史选择')
    if 'lookback_days' in config['history']:
        common.positive(config['history']['lookback_days'], 90, 180, 'history.lookback_days')
    common.positive(config['history']['max_documents'], 1,
                    40 if 'lookback_days' in config['history'] else 10, 'max_documents')
    common.fields(config['discovery'], {'max_candidates', 'max_documents', 'max_per_source', 'evidence_max_chars', 'sources'}, '资料发现')
    expanded = config['window'].get('mode') == 'rolling'
    for key, bounds in {'max_candidates': (1,100 if expanded else 20), 'max_documents': (1,5),
                        'max_per_source': (1,5 if expanded else 2), 'evidence_max_chars': (200,10000)}.items():
        common.positive(config['discovery'][key], *bounds, key)
    sources = config['discovery']['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= 12:
        raise store.OfflineError('发现来源须为1–12项')
    ids = set()
    from researchdesk_sources import approved_hosts, validate_url, SourceError
    for source in sources:
        if not isinstance(source, dict):
            raise store.OfflineError('发现来源必须为映射')
        expected = {'id', 'adapter', 'entry_url'}
        if source.get('adapter') == 'rss':
            expected |= {'publisher', 'allowed_hosts'}
        expected |= {key for key in ('sitemap_url', 'sitemap_max_pages') if key in source}
        common.fields(source, expected, '发现来源')
        if (not isinstance(source['id'], str) or not store.SAFE_ID.fullmatch(source['id'])
                or source['id'] in ids or source['adapter'] not in {'arxiv', 'letta', 'langchain', 'rss'}):
            raise store.OfflineError('发现来源身份重复或适配器无效')
        ids.add(source['id'])
        try:
            if source['adapter'] == 'rss':
                if not isinstance(source['allowed_hosts'], list) or not 1 <= len(source['allowed_hosts']) <= 20:
                    raise store.OfflineError('RSS每来源允许域名须为1–20项')
                hosts = approved_hosts(source['allowed_hosts'])
                if not isinstance(source['publisher'], str) or not source['publisher'].strip() or len(source['publisher']) > 120:
                    raise store.OfflineError('RSS出版商名称无效')
                validate_url(source['entry_url'], hosts)
                if 'sitemap_url' in source or 'sitemap_max_pages' in source:
                    raise store.OfflineError('RSS来源不使用sitemap配置')
            else:
                validate_url(source['entry_url'])
            if 'sitemap_url' in source:
                if source['adapter'] not in {'letta', 'langchain'}:
                    raise store.OfflineError('仅官方博客适配器使用sitemap')
                validate_url(source['sitemap_url'])
            if 'sitemap_max_pages' in source:
                common.positive(source['sitemap_max_pages'], 1, 10, 'sitemap_max_pages')
        except SourceError as exc:
            raise store.OfflineError(str(exc)) from exc
    topics_sha256 = store.digest(topic_path.read_bytes())
    if snapshot is not None and snapshot['_topics_sha256'] != topics_sha256:
        raise store.OfflineError('历史轮次的研究方向配置已变化，不能替换旧上下文')
    config.update(_config_path=relative, _config_sha256=config_sha256,
                  _topics_sha256=topics_sha256)
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
        if (manifest.get('topic') != config['topic'] or manifest.get('cycle_id') != cycle_id
                or manifest.get('config', {}).get('topic') != config['topic']
                or manifest.get('mode') != 'research_cycle_test'
                or manifest.get('backend') != 'chatgpt_plan'
                or manifest.get('production_accepted') is not False):
            raise store.OfflineError('旧轮次清单的主题、身份或运行模式不匹配')
        config = load_config(root, config_path, snapshot=manifest['config'])
        if manifest['config'] != config:
            raise store.OfflineError('轮次已绑定配置与研究方向，不能重置')
    else:
        end = datetime.now(timezone.utc)
        rolling = config['window'].get('mode') == 'rolling'
        start = end - timedelta(days=config['window']['days'] if rolling else config['window']['initial_days'])
        if not rolling:
            # Legacy cycles alone resume the last proven complete scan.
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


class CycleFetcher:
    """Keep a bounded cycle's source versions in memory, never in Git."""
    def __init__(self, delegate=None, sources=()):
        hosts = {host for source in sources for host in source.get('allowed_hosts', [])}
        self.delegate = delegate or SafeFetcher(retries=0, allowed_hosts=hosts or None)
        self.responses = {}

    def fetch(self, url):
        if url not in self.responses:
            self.responses[url] = self.delegate.fetch(url)
        return dict(self.responses[url])

    def fetch_pdf(self, url):
        if url not in self.responses:
            self.responses[url] = self.delegate.fetch_pdf(url)
        return dict(self.responses[url])

    def fetch_json(self, url):
        if url not in self.responses:
            self.responses[url] = self.delegate.fetch_json(url)
        return dict(self.responses[url])


def plan_candidates(root, config, cycle_id, snapshot, fetcher):
    base = base_path(config, cycle_id)
    path = base + '/selection.yaml'
    if store.safe_path(root,path).exists():
        return store.checked_yaml(root,path)
    rolling = config['window'].get('mode') == 'rolling'
    pool = []
    if not rolling:
        for pending_path in sorted((root/('reports/test/'+config['topic']+'/cycles')).glob('*/pending.yaml')):
            if pending_path.parent.name != cycle_id:
                pool += [item for item in store.checked_yaml(root,pending_path.relative_to(root)).get('items',[]) if item.get('source')]
    pool += snapshot['candidates'] + [item for item in snapshot.get('deferred',[]) if item.get('source')
        and (not rolling or item.get('reason') in {'per_source_limit', 'cycle_document_limit'})]
    # Prefer the newest discovery for a stable identity. Otherwise an old
    # version left in a previous pending list could hide every later update.
    latest = {}
    for item in pool:
        latest[item['source']['id']] = item
    if rolling:
        # Re-scan the same bounded rolling window each time. No cross-cycle
        # pending queue/cursor can smuggle expired or previously picked papers.
        used = discovery.previously_selected(root, config['topic'], cycle_id)
        latest = {key: item for key, item in latest.items()
                  if not set(item.get('identity_keys', [])).intersection(used)
                  and item.get('published_at')
                  and discovery._instant(snapshot['window_start']) <= discovery._instant(item['published_at'])
                      < discovery._instant(snapshot['window_end'])}
        if 'selection' in config:
            latest = dict(sorted(latest.items(), key=lambda pair: (
                -pair[1].get('attention', {}).get('community_attention_score', 0),
                pair[1].get('published_at', ''), pair[0])))
    selected, skipped, pending, per_source, seen = [], [], [], {}, set()
    child_config = {'topic':config['topic']}
    for item in list(latest.values())[:1000]:
        source = dict(item['source'])
        per_source_key = item.get('source_id', source['adapter'])
        if config.get('archive'):
            source['archive'] = True
        # Pending candidates from an older cycle adopt the new cycle's reading
        # policy, without mutating their frozen discovery/checkpoint records.
        if source['adapter'] == 'arxiv':
            if 'reading' in config:
                source.update(reading={'mode': config['reading']['mode']},
                              evidence_max_chars=config['reading']['paper_max_chars'])
            else:
                source.pop('reading', None)
                source['evidence_max_chars'] = config['discovery']['evidence_max_chars']
        elif config.get('reading', {}).get('mode') == 'full_text_required':
            source.update(reading={'mode': 'full_text_required'},
                          evidence_max_chars=config['reading'].get('blog_max_chars', 200000))
        item = dict(item, source=source)
        if len(selected)>=config['discovery']['max_documents'] or per_source.get(per_source_key,0)>=config['discovery']['max_per_source']:
            pending.append(dict(item,reason='cycle_capacity'))
            continue
        try:
            candidate, _ = common.fetch_candidate(root,child_config,source,fetcher)
            action = research.classify(root,'reports/test/%s/research-batches/%s'%(config['topic'],cycle_id),candidate,'chatgpt_plan',seen)
        except Exception as exc:
            from researchdesk_sources import SourceError
            details = {'error_reason': str(exc)[:600]} if isinstance(exc, SourceError) else {}
            pending.append(dict(item,reason='preflight_source_failed',error_type=type(exc).__name__, **details))
            continue
        if action['action'] in {'duplicate','blocked'}:
            skipped.append({'source':source,**action})
            continue
        selected.append(item)
        per_source[per_source_key]=per_source.get(per_source_key,0)+1
    result={'candidates':selected,'skipped':skipped,'pending':pending}
    store.save_yaml(root,path,result)
    return result


def collect_originals(root, config_path, cycle_id, fetcher=None, fail_after=None):
    """Discover and pin complete originals without starting a model stage.

    Candidate plans use Research's existing create-only layout, so an explicit
    later ``run`` can replay these exact originals instead of fetching again.
    No Research manifest, response, budget reservation or formal note is made.
    """
    from researchdesk_archive import save as save_archive, load as load_archive

    root = Path(root).resolve()
    initial = load_config(root, config_path)
    if (initial.get('archive') is not True
            or initial.get('reading', {}).get('mode') != 'full_text_required'
            or initial.get('window', {}).get('mode') != 'rolling'):
        raise store.OfflineError('独立采集仅支持 rolling、full_text_required 和 archive: true')
    if fail_after not in {None, 'after_first_original'}:
        raise store.OfflineError('无效采集中断点')
    base = base_path(initial, cycle_id)
    receipt_path = base + '/collection.yaml'
    transport = CycleFetcher(fetcher, initial['discovery']['sources'])
    with cycle_lock(root, initial['topic']), store.topic_lock(root, initial['topic']):
        previous = None
        if store.safe_path(root, receipt_path).exists():
            previous = store.checked_yaml(root, receipt_path)
            # Never let a missing discovery/selection trigger network repair of
            # an already completed collection. Read and verify all pins first.
            _cached(root, previous)
            for name in ('manifest', 'discovery', 'selection'):
                store.checked_yaml(root, base + '/' + name + '.yaml')
        config, manifest, snapshot = discover_cycle(root, config_path, cycle_id, fetcher=transport)
        if (config.get('archive') is not True
                or config.get('reading', {}).get('mode') != 'full_text_required'
                or config.get('window', {}).get('mode') != 'rolling'):
            raise store.OfflineError('旧轮次未绑定完整原文采集策略，不能重新解释')
        selection = (store.checked_yaml(root, base + '/selection.yaml') if previous is not None
                     else plan_candidates(root, config, cycle_id, snapshot, transport))
        batch_base = 'reports/test/%s/research-batches/%s' % (config['topic'], cycle_id)
        records, output_hashes, seen = [], {}, set()
        for item in selection['candidates']:
            source = item['source']
            plan_path = '%s/items/%s/candidate.yaml' % (batch_base, source['id'])
            if store.safe_path(root, plan_path).exists():
                plan = store.checked_yaml(root, plan_path)
                candidate, material, _ = load_archive(root, plan['candidate'], source=source, config=config)
            else:
                if previous is not None:
                    raise store.OfflineError('已完成采集的候选缺失，禁止联网替换')
                capture = {}
                candidate, material = common.fetch_candidate(
                    root, config, source, transport, capture=capture)
                action = research.classify(root, batch_base, candidate, config['backend'], seen)
                if action['action'] not in {'research', 'update'}:
                    raise store.OfflineError('采集选材的来源身份已变化，保留现场: ' + source['id'])
                candidate = save_archive(root, batch_base, candidate, material, source, capture)
                plan = {'candidate': candidate, 'material_sha256': store.digest(material.encode()), **action}
                store.save_yaml(root, plan_path, plan)
            if (plan.get('action') not in {'research', 'update'}
                    or plan.get('material_sha256') != store.digest(material.encode())
                    or candidate['key'] != source['id'] or candidate['topic'] != config['topic']
                    or candidate['evidence']['coverage'] != 'full_text'):
                raise store.OfflineError('已保存候选不对应完整原文采集计划')
            seen.update(candidate['identity_keys'])
            binding = candidate['archive']
            records.append({'key': candidate['key'], 'title': candidate['metadata']['title'],
                'source_url': candidate['metadata']['source_url'], 'source_id': candidate['source_id'],
                'candidate_path': plan_path, 'original_path': binding['path'],
                'original_markdown_path': binding['markdown_path'],
                'coverage': candidate['evidence']['coverage'], 'content_hash': candidate['content_hash']})
            for path in (plan_path, plan_path + '.sha256', binding['path'],
                         binding['path'] + '.sha256', binding['markdown_path']):
                output_hashes[path] = store.digest(store.safe_path(root, path).read_bytes())
            interrupted = base + '/collection-interruption.yaml'
            if (previous is None and fail_after == 'after_first_original' and len(records) == 1
                    and not store.safe_path(root, interrupted).exists()):
                store.save_yaml(root, interrupted, {'phase': 'after_first_original',
                    'candidate_path': plan_path, 'model_calls': 0})
                raise store.SimulatedInterruption('首篇原文已归档；同 ID 补跑复用已完成采集')
        research.verify_notes(root, manifest['protected_notes'])
        inputs = [base + '/' + name + suffix for name in ('manifest', 'discovery', 'selection')
                  for suffix in ('.yaml', '.yaml.sha256')]
        receipt = {'schema_version': 1, 'mode': 'collection_only', 'topic': config['topic'],
            'cycle_id': cycle_id, 'status': 'collected' if records else 'empty',
            'discovery_status': snapshot.get('status'), 'records': records,
            'model_calls': 0, 'research_started': False, 'insight_started': False,
            'writing_started': False, 'production_accepted': False, 'publish_authorized': False,
            'input_hashes': {path: store.digest(store.safe_path(root, path).read_bytes()) for path in inputs},
            'output_hashes': output_hashes}
        if previous is not None:
            if previous != receipt:
                raise store.OfflineError('采集回执与固定原文或选材不一致，保留文件')
            return dict(previous, cached=True)
        store.save_yaml(root, receipt_path, receipt)
        return receipt


def run(root, config_path, cycle_id, client=None, fetcher=None, fail_after=None):
    root = Path(root).resolve()
    initial = load_config(root, config_path)
    base = base_path(initial, cycle_id)
    if fail_after not in (None, 'after_research'):
        raise store.OfflineError('无效轮次断点')
    fetcher = CycleFetcher(fetcher, initial['discovery']['sources'])
    with cycle_lock(root, initial['topic']):
        config, manifest, snapshot = discover_cycle(root, config_path, cycle_id, fetcher=fetcher)
        receipt_path = base + '/receipt.yaml'
        if store.safe_path(root, receipt_path).exists():
            return _cached(root, store.checked_yaml(root, receipt_path))
        input_hashes = {base+'/manifest.yaml':store.digest((root/base/'manifest.yaml').read_bytes()),
                        base+'/discovery.yaml':store.digest((root/base/'discovery.yaml').read_bytes())}
        selection = plan_candidates(root,config,cycle_id,snapshot,fetcher)
        input_hashes[base+'/selection.yaml']=store.digest((root/base/'selection.yaml').read_bytes())
        results, outputs, pending = {}, {}, list(snapshot.get('deferred', [])) + selection['pending']
        candidates = selection['candidates']
        status = {'complete': 'no_new', 'failed': 'discovery_failed'}.get(snapshot.get('status'), 'partial')
        if candidates:
            history_path = base + '/history.yaml'
            if store.safe_path(root, history_path).exists():
                historical = store.checked_yaml(root, history_path)['items']
            else:
                history_options = ({'lookback_days': config['history']['lookback_days'],
                                    'as_of': manifest['window_end']}
                                   if 'lookback_days' in config['history'] else {})
                historical = discovery.select_history(root, config['topic'], config['history']['max_documents'],
                                                       **history_options)
                store.save_yaml(root, history_path, {'items':historical})
            if not historical and config.get('reading', {}).get('mode') != 'full_text_required':
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
                    'prompts':{'version':'research-batch-v4' if config.get('reading', {}).get('mode') == 'full_text_required' else
                                        'research-batch-v3' if config.get('presentation') == 'technical_article' else
                                        'research-batch-v2' if 'reading' in config else 'research-batch-v1'},
                    'sources':[item['source'] for item in candidates]}
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
                for item in research_result['items']:
                    original_path = 'reports/test/%s/research-batches/%s/items/%s/candidate.yaml' % (
                        config['topic'], cycle_id, item['key'])
                    if (root / original_path).is_file():
                        original = store.checked_yaml(root, original_path)['candidate']
                        if 'archive' in original:
                            from researchdesk_archive import load
                            load(root, original)
                            for path in (original_path, original_path + '.sha256', original['archive']['path'],
                                         original['archive']['path'] + '.sha256', original['archive']['markdown_path']):
                                input_hashes[path] = store.digest((root / path).read_bytes())
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
                        'prompts':{'version':'insight-v6' if config.get('reading', {}).get('mode') == 'full_text_required' else
                                            'insight-v5' if config.get('presentation') == 'technical_article' else
                                            'insight-v4' if 'lookback_days' in config['history'] else
                                            'insight-v3' if 'reading' in config else 'insight-v2'},
                        'research_inputs':[{'receipt':original_receipt,'config':research_path,'item_keys':keys}],
                        'historical_inputs':historical}
                    insight_path = base+'/configs/insight.yaml'
                    if store.safe_path(root, insight_path).exists():
                        # An interrupted pre-upgrade cycle owns its frozen v1
                        # config. Only new children default to v2; save_yaml
                        # still rejects changes to any other bound input.
                        previous = store.checked_yaml(root, insight_path)
                        version = previous.get('prompts', {}).get('version')
                        if version not in {'insight-v1', 'insight-v2', 'insight-v3', 'insight-v4', 'insight-v5', 'insight-v6'}:
                            raise store.OfflineError('已有 Insight 配置的提示词版本无效')
                        insight_cfg['prompts']['version'] = version
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
    for name in ('discover','collect','run'):
        command=commands.add_parser(name)
        command.add_argument('--config',type=Path,required=True)
        command.add_argument('--cycle-id',required=True)
        if name != 'collect':
            command.add_argument('--profile',type=Path)
        command.add_argument('--fail-after',choices=[
            'after_first_original' if name == 'collect' else 'after_research'])
    args=parser.parse_args()
    try:
        if args.command=='discover':
            result=discover_cycle(args.root,args.config,args.cycle_id)[2]
        elif args.command=='collect':
            result=collect_originals(args.root,args.config,args.cycle_id,fail_after=args.fail_after)
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
    if args.command == 'collect':
        return 0 if result['discovery_status'] != 'failed' else 1
    return 0 if result.get('status') in {'completed','no_new','partial','complete'} else 1


if __name__=='__main__':sys.exit(main())
