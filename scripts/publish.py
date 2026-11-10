#!/usr/bin/env python3
"""Create-only transfer of new collection, Research and SDK Insight results.

Private configuration and native sessions never enter the payload. The public
frozen research context is reconstructed only in a temporary validation overlay.
No provider, credential or model operation is performed by this module.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

import archive
import harness
import insight_inputs as inputs
import note_paths as notes
import offline as store
from schedule import MAX_TOPICS


class PublishError(store.OfflineError):
    pass


IDENTITY = re.compile(r'[a-z0-9][a-z0-9_-]{0,100}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
MAX_BYTES = 12_000_000
BATCH_MODE = 'scheduled_research_transfer_batch'
TRANSFER_ERRORS = (store.OfflineError, OSError, ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError)


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _safe(root, relative):
    if root.is_symlink():
        raise PublishError('transfer_symlink_forbidden')
    path = Path(relative)
    if (not isinstance(relative, str) or not path.parts or path.is_absolute()
            or path.as_posix() != relative or '..' in path.parts or '\\' in relative
            or any(part.startswith('.') for part in path.parts)):
        raise PublishError('transfer_path_invalid')
    target = root / path
    for parent in (target,) + tuple(target.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise PublishError('transfer_symlink_forbidden')
    return target


def _prefixes(topic, cycle):
    return [('collection', topic, cycle),
            ('insights', 'test', topic, cycle), ('articles', 'test', topic, cycle),
            ('reports', topic, 'admissions', cycle)] + [
        ('reports', 'test', topic, stage, cycle)
        for stage in ('cycles', 'research-batches', 'codex-insight', 'automation')]


def _reading_prefixes(root, family, topic, cycle):
    parent = _safe(root, family + '/' + topic)
    if parent.is_dir():
        for path in sorted(parent.iterdir()):
            if notes.component_identity(path.name) == cycle:
                yield family, topic, path.name


def _workspace_prefixes(root, topic, cycle):
    yield from _prefixes(topic, cycle)
    for family in ('summary', 'insights'):
        yield from _reading_prefixes(root, family, topic, cycle)


def allowed(relative, topic, cycle):
    parts = Path(relative).parts
    summary = notes.summary_ids(relative)
    if summary is not None:
        return summary[:2] == (topic, cycle)
    insight = notes.insight_ids(relative)
    if insight is not None:
        return insight == (topic, cycle)
    if (Path(relative).as_posix() == relative and len(parts) == 3 and parts[:2] == ('articles', topic)
            and re.fullmatch(re.escape(cycle) + r'-topic-[1-9][0-9]*\.md', parts[-1])):
        return True
    valid = (Path(relative).suffix in {'.yaml', '.md', '.sha256'}
            and not any(part.startswith('.') for part in parts)
            and any(parts[:len(prefix)] == prefix and len(parts) > len(prefix)
                    for prefix in _prefixes(topic, cycle)))
    if not valid:
        return False
    if parts[0] == 'collection':
        tail = '/'.join(parts[3:])
        return bool(re.fullmatch(r'manifest\.yaml(?:\.sha256)?|items/[a-z0-9_-]+/original\.(?:md|yaml(?:\.sha256)?)', tail))
    if parts[0] == 'insights':
        return len(parts) == 5 and parts[1] == 'test' and parts[-1] == 'report.md'
    if parts[0] == 'articles':
        return len(parts) == 5 and bool(re.fullmatch(r'topic-[1-9][0-9]*\.md', parts[-1]))
    if parts[:4] == ('reports', topic, 'admissions', cycle):
        return len(parts) == 5 and parts[-1] in {
            'plan.yaml', 'plan.yaml.sha256', 'accepted.yaml', 'accepted.yaml.sha256'}
    return True


def _identity(topic, cycle):
    if any(not isinstance(value, str) or not IDENTITY.fullmatch(value) for value in (topic, cycle)):
        raise PublishError('transfer_identity_invalid')


def _read(root, relative):
    path = _safe(root, relative)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise PublishError('transfer_file_missing_or_too_large')
    return path.read_bytes()


def _checked(root, relative):
    payload = _read(root, relative)
    if _read(root, relative + '.sha256').decode().strip() != _hash(payload):
        raise PublishError('transfer_digest_invalid: ' + relative)
    value = yaml.load(payload.decode('utf-8'), Loader=store.UniqueKeyLoader)
    if not isinstance(value, dict):
        raise PublishError('transfer_yaml_invalid')
    return value


def _plain_yaml(root, relative):
    value = yaml.load(_read(root, relative).decode(), Loader=store.UniqueKeyLoader)
    if not isinstance(value, dict):
        raise PublishError('transfer_yaml_invalid')
    return value


def _write_new(path, payload):
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise PublishError('existing_content_conflict_preserve_both')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(payload)


def _copy_public_topic(source, destination, topic, cycle):
    # Only this direction is required. Never copy local account request ledgers,
    # smoke receipts, configuration directories or native runtime state.
    roots = [(folder, topic) for folder in ('collection', 'summary', 'insights', 'articles', 'reports')]
    roots += [(folder, 'test', topic) for folder in ('insights', 'articles', 'reports')]
    for parts in roots:
        base = _safe(source, '/'.join(parts))
        if not base.exists():
            continue
        if base.is_symlink():
            raise PublishError('transfer_symlink_forbidden')
        for path in base.rglob('*'):
            relative = path.relative_to(source).as_posix()
            if allowed(relative, topic, cycle):
                continue
            if any(p in {'codex-requests', 'codex-sdk-smoke'} or p.startswith('.') for p in path.relative_to(base).parts):
                continue
            if path.is_symlink():
                raise PublishError('transfer_symlink_forbidden')
            if path.is_file():
                _write_new(_safe(destination, relative), path.read_bytes())


def _context(root, topic, cycle):
    context = _checked(root, 'reports/test/%s/automation/%s/context.yaml' % (topic, cycle))
    if context.get('topic') != topic or context.get('cycle_id') != cycle or context.get('schema_version') != 1:
        raise PublishError('frozen_context_identity_invalid')
    return context


def _restore_context(root, context, topic, cycle):
    topics_path = context.get('topics_path')
    cycle_path = context.get('research_config_path')
    expected_prefix = 'config/local/automation/' + cycle + '/'
    if topics_path not in {'config/research_topics.yaml', expected_prefix + 'topics.yaml'}:
        raise PublishError('frozen_topics_path_invalid')
    if cycle_path not in {'config/cycles/default.yaml', expected_prefix + 'cycle.yaml'}:
        raise PublishError('frozen_cycle_path_invalid')
    restored = {}
    for name, path in [('topics', topics_path), ('research_config', cycle_path)]:
        text = context.get(name + '_yaml_text')
        digest = context.get(name + '_sha256')
        if not isinstance(text, str) or not isinstance(digest, str) or _hash(text.encode()) != digest:
            raise PublishError('frozen_context_digest_invalid')
        value = yaml.load(text, Loader=store.UniqueKeyLoader)
        if not isinstance(value, dict):
            raise PublishError('frozen_context_yaml_invalid')
        _write_new(_safe(root, path), text.encode())
        restored[name] = value
    if (restored['topics'].get('schema_version') != 1
            or set(restored['topics'].get('topics', {})) != {topic}
            or restored['research_config'].get('topic') != topic
            or restored['research_config'].get('topics_file') != topics_path):
        raise PublishError('frozen_context_direction_invalid')
    direction = restored['topics']['topics'][topic]
    if not isinstance(direction, dict) or set(direction) != {'name', 'enabled', 'description', 'scope', 'keywords'}:
        raise PublishError('frozen_context_topic_fields_invalid')
    public_insight = context.get('insight_config')
    allowed_insight = {'schema_version', 'mode', 'backend', 'topic', 'topics_file', 'models', 'codex',
                       'review_policy', 'history', 'generation', 'limits'}
    if (not isinstance(public_insight, dict) or set(public_insight) - {'prompts'} != allowed_insight
            or public_insight.get('topic') != topic):
        raise PublishError('frozen_context_insight_fields_invalid')
    harness._prompt_version(public_insight)
    if 'selected_topic' in context and context['selected_topic'] != restored['topics']:
        raise PublishError('frozen_context_direction_invalid')
    if 'research_config' in context and context['research_config'] != restored['research_config']:
        raise PublishError('frozen_context_cycle_changed')
    if 'insight_config_yaml_text' in context:
        text = context['insight_config_yaml_text']
        if (not isinstance(text, str) or _hash(text.encode()) != context.get('insight_config_sha256')
                or yaml.load(text, Loader=store.UniqueKeyLoader) != public_insight):
            raise PublishError('frozen_context_insight_changed')
    manifest_path = 'reports/test/%s/cycles/%s/manifest.yaml' % (topic, cycle)
    if _safe(root, manifest_path).is_file():
        manifest = _checked(root, manifest_path)
        snapshot = manifest.get('config', {})
        if (snapshot.get('_config_path') != cycle_path
                or snapshot.get('_config_sha256') != context['research_config_sha256']
                or snapshot.get('_topics_sha256') != context['topics_sha256']):
            raise PublishError('frozen_context_collection_binding_changed')
    return restored['topics']['topics'], cycle_path


def _restore_historical_contexts(root, topic, cycle):
    """Rebuild bound public snapshots, never the host's ignored originals."""
    accepted_path = 'reports/test/%s/codex-insight/%s/accepted.yaml' % (topic, cycle)
    if not _safe(root, accepted_path).exists():
        return
    receipt = _checked(root, accepted_path)
    hashes = receipt.get('input_hashes')
    if not isinstance(hashes, dict):
        raise PublishError('insight_binding_missing')
    required, explicit = set(), set()
    for relative in hashes:
        frozen = re.fullmatch(r'config/local/automation/([a-z0-9_-]+)/topics\.yaml', relative)
        if frozen and frozen[1] != cycle:
            required.add(frozen[1])
            explicit.add(frozen[1])
        summary = notes.summary_ids(relative)
        if summary and summary[0] == topic and summary[1] != cycle:
            required.add(summary[1])
    import cycle as research_cycle
    for previous in sorted(required):
        path = 'reports/test/%s/automation/%s/context.yaml' % (topic, previous)
        if not _safe(root, path).exists():
            if previous in explicit:
                raise PublishError('historical_context_missing_preserve_artifact')
            # Legacy summaries already carry independently checked historical
            # topic digests and may predate per-cycle public contexts.
            continue
        context = _context(root, topic, previous)
        if context.get('topics_path') != 'config/local/automation/%s/topics.yaml' % previous:
            if previous in explicit:
                raise PublishError('historical_context_snapshot_invalid')
            continue
        _, config_path = _restore_context(root, context, topic, previous)
        research_cycle.load_config(root, config_path)


def _validate_workspace(root, topic, cycle, topics):
    # The source framework supplies the verifier; an artifact cannot replace it.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from workflows import validate
    errors = []

    def fail(path, message):
        errors.append(path + ': ' + message)

    def frontmatter(text, relative):
        if not text.startswith('---\n'):
            raise PublishError('summary_frontmatter_missing')
        return yaml.load(text.split('---', 2)[1], Loader=store.UniqueKeyLoader)

    # Check completed collection indexes and source summaries only for this run;
    # unrelated historical handwritten notes are never regraded or modified.
    with tempfile.TemporaryDirectory(prefix='researchdesk-reading-proof-') as temporary:
        current = Path(temporary).resolve()
        for prefix in _workspace_prefixes(root, topic, cycle):
            source = root.joinpath(*prefix)
            if source.is_dir() and prefix[0] in {'collection', 'summary', 'reports'}:
                shutil.copytree(source, current.joinpath(*prefix), dirs_exist_ok=True)
        validate.check_workspace(current, topics, fail, frontmatter)
    if errors:
        raise PublishError('collection_or_summary_proof_invalid: ' + errors[0])
    for prefix in _reading_prefixes(root, 'summary', topic, cycle):
        for path in sorted(root.joinpath(*prefix).glob('*.md')):
            inputs._codex_summary(root, path.relative_to(root).as_posix(), topic, {})


def _verify_insight(root, context, topic, cycle):
    base = 'reports/test/%s/codex-insight/%s/' % (topic, cycle)
    if not _safe(root, base + 'accepted.yaml').is_file():
        if any((root / folder / 'test' / topic / cycle).exists() for folder in ('insights', 'articles')):
            raise PublishError('insight_has_no_accepted_receipt')
        return
    receipt = _checked(root, base + 'accepted.yaml')
    if (receipt.get('topic') != topic or receipt.get('cycle_id') != cycle
            or receipt.get('status') not in {'complete', 'no_insight'}
            or receipt.get('review_policy') != 'accuracy_only' or receipt.get('review_decision') != 'pass'
            or receipt.get('writing_started') is not False or receipt.get('production_accepted') is not False):
        raise PublishError('insight_receipt_invalid')
    hashes = receipt.get('input_hashes')
    output_hashes = receipt.get('output_hashes')
    if not isinstance(hashes, dict) or not isinstance(output_hashes, dict) or set(receipt.get('outputs', [])) != set(output_hashes):
        raise PublishError('insight_binding_missing')
    for bindings in (hashes, output_hashes):
        for relative, expected in bindings.items():
            if not isinstance(expected, str) or not SHA.fullmatch(expected) or _hash(_read(root, relative)) != expected:
                raise PublishError('insight_bound_content_changed: ' + relative)
    current, history = [], []
    for relative in sorted(hashes):
        if relative.startswith('summary/' + topic + '/') and relative.endswith('.md'):
            source = inputs._codex_summary(root, relative, topic, {})
            source.pop('_identities', None)
            (current if notes.summary_ids(relative)[1] == cycle else history).append(source)
    if not current:
        raise PublishError('insight_missing_current_research')
    history.sort(key=lambda item: (item['research_date'], item['summary_path']), reverse=True)
    sources = []
    for role, values in [('current', current), ('history', history)]:
        for number, source in enumerate(values, 1):
            sources.append(dict(source, id=('R' if role == 'current' else 'H') + str(number), role=role))
    bundle = {'topic': topic, 'cycle_id': cycle, 'sources': sources}
    if not {base + 'candidate.yaml', base + 'review.yaml'}.issubset(output_hashes):
        raise PublishError('insight_binding_missing')
    # The portable SDK proofs are bound by accepted.output_hashes; only the
    # accepted receipt itself has a separate SHA marker in existing harnesses.
    candidate = _plain_yaml(root, base + 'candidate.yaml')
    review = _plain_yaml(root, base + 'review.yaml')
    if review.get('policy') != 'accuracy_only' or review.get('candidate_sha256') != harness._sha(candidate):
        raise PublishError('insight_review_candidate_changed')
    decision = harness._review(json.dumps(review.get('review'), ensure_ascii=False))
    if decision.get('decision') != 'pass':
        raise PublishError('insight_accuracy_review_not_passed')
    config = context.get('insight_config', {})
    models = config.get('models', {})
    if (not models.get('generation') or not models.get('review') or models['generation'] == models['review']
            or review.get('requested_model') != models['review']):
        raise PublishError('insight_independent_model_binding_invalid')
    actual_models = receipt.get('models', {})
    known = [actual_models.get(role, {}).get('observed_model') for role in ('generation', 'review')]
    if all(known) and known[0] == known[1]:
        raise PublishError('insight_independent_model_collision')
    checked_candidate = harness._candidate(json.dumps(candidate, ensure_ascii=False), bundle)
    if checked_candidate != candidate:
        raise PublishError('insight_candidate_invalid')
    state = {'backend': receipt['backend'], 'review': decision, 'tasks': {'review': {'result': {
        'requested_model': review.get('requested_model'), 'observed_model': review.get('observed_model'),
        'thread_id': review.get('thread_id'), 'turn_id': review.get('turn_id'), 'final_response': '{}'}}}}
    rendered = harness._render(candidate, bundle, state, receipt.get('simulation') is True)
    markdown = {path: text.encode() for path, text in rendered.items() if path.endswith('.md')}
    if set(rendered) != set(output_hashes):
        raise PublishError('insight_rendered_outputs_changed')
    for relative, payload in markdown.items():
        if _read(root, relative) != payload:
            raise PublishError('insight_rendered_content_changed: ' + relative)


@contextmanager
def _overlay(root, files, topic, cycle):
    with tempfile.TemporaryDirectory(prefix='researchdesk-publish-') as temporary:
        overlay = Path(temporary).resolve()
        _copy_public_topic(root, overlay, topic, cycle)
        for relative, payload in files.items():
            _write_new(_safe(overlay, relative), payload)
        context = _context(overlay, topic, cycle)
        topics, cycle_path = _restore_context(overlay, context, topic, cycle)
        import cycle as research_cycle
        research_cycle.load_config(overlay, cycle_path)
        _restore_historical_contexts(overlay, topic, cycle)
        _validate_workspace(overlay, topic, cycle, topics)
        _verify_insight(overlay, context, topic, cycle)
        formal = 'reports/%s/admissions/%s/accepted.yaml' % (topic, cycle)
        if (_safe(overlay, formal).exists()
                or any(_reading_prefixes(overlay, 'insights', topic, cycle))
                or any((overlay / 'articles' / topic).glob(cycle + '-topic-*.md'))):
            import insight_admission as admission
            accepted = admission.load(overlay, topic, cycle)
            formal_insights = {relative for relative in files if notes.insight_ids(relative) == (topic, cycle)}
            if formal_insights - accepted['output_hashes'].keys():
                raise PublishError('formal_insight_has_no_accepted_binding')
        yield overlay


def _guard(payload, relative, root):
    if len(payload) > MAX_BYTES:
        raise PublishError('transfer_file_too_large')
    text = payload.decode('utf-8')
    archive.check_public_tokens(text)
    # Fully verified public originals may contain literal code paths. All other
    # records must not accidentally carry the execution host's private paths.
    if not relative.startswith('collection/') and re.search(r'(?<![\w:])/(?:Users|home|private|var|root)/', text):
        raise PublishError('private_host_path_in_transfer')
    if relative.endswith('.yaml'):
        sdk_proof = '/codex-insight/' in relative and Path(relative).name in {'candidate.yaml', 'review.yaml'}
        value = _plain_yaml(root, relative) if sdk_proof else _checked(root, relative)
        if not isinstance(value, dict):
            raise PublishError('transfer_yaml_invalid')


def export(root, destination, topic, cycle_id, base_commit):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    _identity(topic, cycle_id)
    if not isinstance(base_commit, str) or not COMMIT.fullmatch(base_commit):
        raise PublishError('transfer_base_commit_invalid')
    files = {}
    collection_complete = _safe(root, 'collection/%s/%s/manifest.yaml' % (topic, cycle_id)).is_file()
    insight_complete = _safe(root, 'reports/test/%s/codex-insight/%s/accepted.yaml' % (topic, cycle_id)).is_file()
    formal_complete = _safe(root, 'reports/%s/admissions/%s/accepted.yaml' % (topic, cycle_id)).is_file()
    for prefix in _workspace_prefixes(root, topic, cycle_id):
        is_formal = prefix[:2] == ('insights', topic) or prefix == ('reports', topic, 'admissions', cycle_id)
        if is_formal and not formal_complete:
            continue
        if prefix[0] in {'collection', 'summary'} and not collection_complete:
            continue
        if (prefix[0] in {'insights', 'articles'} or 'codex-insight' in prefix) and not insight_complete:
            continue
        base = _safe(root, '/'.join(prefix))
        if base.is_symlink():
            raise PublishError('transfer_symlink_forbidden')
        for path in sorted(base.rglob('*')) if base.is_dir() else []:
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not allowed(relative, topic, cycle_id):
                if path.is_symlink() or path.is_file():
                    raise PublishError('transfer_path_not_allowed')
                continue
            if path.is_file():
                files[relative] = _read(root, relative)
    if formal_complete:
        for path in sorted((root / 'articles' / topic).glob(cycle_id + '-topic-*.md')):
            relative = path.relative_to(root).as_posix()
            if not allowed(relative, topic, cycle_id):
                raise PublishError('transfer_path_not_allowed')
            files[relative] = _read(root, relative)
    with _overlay(root, files, topic, cycle_id) as overlay:
        for relative, payload in files.items():
            _guard(payload, relative, overlay)
    manifest = {'schema_version': 1, 'mode': 'scheduled_research_transfer', 'topic': topic,
                'cycle_id': cycle_id, 'base_commit': base_commit,
                'files': {relative: _hash(payload) for relative, payload in sorted(files.items())}}
    for relative, payload in files.items():
        _write_new(_safe(destination / 'payload', relative), payload)
    _write_new(destination / 'manifest.json', json.dumps(manifest, sort_keys=True, indent=2).encode())
    return {'cycle_id': cycle_id, 'exported_files': len(files), 'production_accepted': formal_complete}


def _batch_identities(cycles):
    if not 1 <= len(cycles) <= MAX_TOPICS:
        raise PublishError('transfer_batch_size_invalid')
    for topic, cycle in cycles:
        _identity(topic, cycle)
    if len({topic for topic, _ in cycles}) != len(cycles) or len({cycle for _, cycle in cycles}) != len(cycles):
        raise PublishError('transfer_batch_identity_repeated')


def _batch_path(topic, cycle):
    return 'cycles/%s/%s' % (topic, cycle)


def export_many(root, destination, cycles, base_commit, exporter=None):
    """Build one artifact from independently verified topic packages."""
    cycles = list(cycles)
    _batch_identities(cycles)
    if not isinstance(base_commit, str) or not COMMIT.fullmatch(base_commit):
        raise PublishError('transfer_base_commit_invalid')
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise PublishError('transfer_batch_destination_exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries, failures = [], []
    with tempfile.TemporaryDirectory(prefix='researchdesk-topic-export-', dir=destination.parent) as temporary:
        staging = Path(temporary)
        for topic, cycle in cycles:
            child = _safe(staging, _batch_path(topic, cycle))
            try:
                (exporter or export)(root, child, topic, cycle, base_commit)
                digest = _hash(_read(child, 'manifest.json'))
            except TRANSFER_ERRORS as exc:
                failures.append({'topic': topic, 'cycle_id': cycle, 'failure_type': type(exc).__name__})
                shutil.rmtree(child, ignore_errors=True)
                continue
            entries.append({'topic': topic, 'cycle_id': cycle, 'manifest_sha256': digest})
        if entries:
            destination.mkdir()
            (staging / 'cycles').rename(destination / 'cycles')
            manifest = {'schema_version': 1, 'mode': BATCH_MODE, 'base_commit': base_commit, 'cycles': entries}
            _write_new(destination / 'manifest.json', json.dumps(manifest, sort_keys=True, indent=2).encode())
    return {'exported_cycles': len(entries), 'failures': failures}


def _git(root, *arguments):
    result = subprocess.run(['git', *arguments], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise PublishError('publisher_git_operation_failed')
    return result.stdout.decode().strip()


def _ancestor(root, base, head):
    result = subprocess.run(['git', 'merge-base', '--is-ancestor', base, head],
                            cwd=root, capture_output=True, check=False)
    return result.returncode == 0


def _apply_one(root, artifact, manifest, push):
    if (set(manifest) != {'schema_version', 'mode', 'topic', 'cycle_id', 'base_commit', 'files'}
            or manifest['schema_version'] != 1 or manifest['mode'] != 'scheduled_research_transfer'
            or not isinstance(manifest['base_commit'], str) or not COMMIT.fullmatch(manifest['base_commit'])
            or not isinstance(manifest['files'], dict)):
        raise PublishError('transfer_manifest_invalid')
    topic, cycle = manifest['topic'], manifest['cycle_id']
    _identity(topic, cycle)
    if (root / '.git').exists():
        head = _git(root, 'rev-parse', 'HEAD')
        # Unrelated notes and normal main commits may advance during research.
        # Content bindings below decide whether the actual evidence changed.
        if head != manifest['base_commit'] and not _ancestor(root, manifest['base_commit'], head):
            raise PublishError('main_history_changed_preserve_artifact')
        if push and _git(root, 'diff', '--cached', '--name-only'):
            raise PublishError('publisher_has_staged_changes')
    elif push:
        raise PublishError('publisher_requires_git_repository')
    files = {}
    for relative, expected in manifest['files'].items():
        if not allowed(relative, topic, cycle) or not isinstance(expected, str) or not SHA.fullmatch(expected):
            raise PublishError('transfer_path_not_allowed')
        payload = _read(artifact / 'payload', relative)
        if _hash(payload) != expected:
            raise PublishError('transfer_content_changed')
        destination = _safe(root, relative)
        for parent in destination.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise PublishError('existing_parent_conflict_preserve_both: ' + relative)
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != payload):
            raise PublishError('existing_content_conflict_preserve_both: ' + relative)
        files[relative] = payload
    # Validate all bindings and conflicts before creating any repository files.
    with _overlay(root, files, topic, cycle) as overlay:
        for relative, payload in files.items():
            _guard(payload, relative, overlay)
    additions = [relative for relative in files if not _safe(root, relative).exists()]
    for relative in additions:
        _write_new(_safe(root, relative), files[relative])
    pushed = False
    if push and files:
        _git(root, 'add', '--', *sorted(files))
        staged = set(_git(root, 'diff', '--cached', '--name-only', '-z').split('\0')) - {''}
        if staged - files.keys():
            raise PublishError('unexpected_staged_changes')
        if staged:
            _git(root, '-c', 'user.name=github-actions[bot]', '-c',
                 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                 'commit', '-m', 'Save reviewed ResearchDesk results: ' + cycle)
            _git(root, 'push', 'origin', 'HEAD:refs/heads/main')
            pushed = True
    formal = 'reports/%s/admissions/%s/accepted.yaml' % (topic, cycle)
    return {'cycle_id': cycle, 'saved_files': len(additions),
            'production_accepted': formal in files, 'pushed': pushed}


def _apply_many(root, artifact, manifest, push):
    if (set(manifest) != {'schema_version', 'mode', 'base_commit', 'cycles'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or not isinstance(manifest['base_commit'], str) or not COMMIT.fullmatch(manifest['base_commit'])
            or not isinstance(manifest['cycles'], list)):
        raise PublishError('transfer_batch_manifest_invalid')
    entries = manifest['cycles']
    if any(not isinstance(entry, dict) or set(entry) != {'topic', 'cycle_id', 'manifest_sha256'}
           or not isinstance(entry['manifest_sha256'], str) or not SHA.fullmatch(entry['manifest_sha256'])
           for entry in entries):
        raise PublishError('transfer_batch_entry_invalid')
    _batch_identities([(entry['topic'], entry['cycle_id']) for entry in entries])
    results = []
    for entry in entries:
        topic, cycle = entry['topic'], entry['cycle_id']
        try:
            child = _safe(artifact, _batch_path(topic, cycle))
            payload = _read(child, 'manifest.json')
            if _hash(payload) != entry['manifest_sha256']:
                raise PublishError('transfer_child_manifest_changed')
            child_manifest = json.loads(payload)
            if (not isinstance(child_manifest, dict) or child_manifest.get('topic') != topic
                    or child_manifest.get('cycle_id') != cycle
                    or child_manifest.get('base_commit') != manifest['base_commit']):
                raise PublishError('transfer_child_binding_invalid')
            saved = _apply_one(root, child, child_manifest, push)
        except TRANSFER_ERRORS as exc:
            results.append({'topic': topic, 'cycle_id': cycle, 'status': 'failed',
                            'error': str(exc) if isinstance(exc, PublishError) else 'publish_validation_failed'})
            continue
        results.append({'topic': topic, 'status': 'complete', **saved})
    successful = [result for result in results if result['status'] == 'complete']
    return {'status': 'complete' if len(successful) == len(results) else 'partial' if successful else 'failed',
            'saved_files': sum(result['saved_files'] for result in successful),
            'pushed': any(result['pushed'] for result in successful), 'results': results}


def apply(root, artifact, push=False):
    root, artifact = Path(root).resolve(), Path(artifact).absolute()
    manifest = json.loads(_read(artifact, 'manifest.json'))
    if not isinstance(manifest, dict):
        raise PublishError('transfer_manifest_invalid')
    if manifest.get('mode') == BATCH_MODE:
        return _apply_many(root, artifact, manifest, push)
    return _apply_one(root, artifact, manifest, push)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    pack = commands.add_parser('export')
    pack.add_argument('--destination', type=Path, required=True)
    pack.add_argument('--topic', required=True)
    pack.add_argument('--cycle-id', required=True)
    pack.add_argument('--base-commit', required=True)
    save = commands.add_parser('apply')
    save.add_argument('--artifact', type=Path, required=True)
    save.add_argument('--push', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = (export(args.root, args.destination, args.topic, args.cycle_id, args.base_commit)
                  if args.command == 'export' else apply(args.root, args.artifact, args.push))
    except TRANSFER_ERRORS as exc:
        print(json.dumps({'error': str(exc) if isinstance(exc, PublishError) else 'publish_validation_failed'}))
        return 1
    print(json.dumps(result))
    if result.get('status') == 'partial':
        failed_topics = ', '.join(item['topic'] for item in result['results'] if item['status'] == 'failed')
        prefix = '::warning::' if os.environ.get('GITHUB_ACTIONS') == 'true' else ''
        print(prefix + '部分研究方向未能回存，已保留其产物：' + failed_topics, file=sys.stderr)
    return 1 if result.get('status') == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
