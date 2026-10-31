"""Exact, explicitly retired TEST notes; never substitute for consumed material."""

from functools import lru_cache
from pathlib import Path
import re

import yaml

import researchdesk_offline as store


CONFIG = 'config/retired_notes.yaml'


def _path(root, relative):
    if not isinstance(relative, str):
        raise store.OfflineError('退休笔记必须使用精确仓库相对路径')
    path = Path(relative)
    if (path.is_absolute()
            or path.as_posix() != relative or '..' in path.parts
            or any(char in relative for char in '\\*?[]\x00\r\n')):
        raise store.OfflineError('退休笔记必须使用精确仓库相对路径')
    target = Path(root)
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise store.OfflineError('退休笔记拒绝符号链接: ' + relative)
    return target


@lru_cache(maxsize=8)
def _parse(payload):
    try:
        value = yaml.load(payload.decode('utf-8'), Loader=store.UniqueKeyLoader)
    except (UnicodeError, yaml.YAMLError) as exc:
        raise store.OfflineError('退休笔记登记不是有效的唯一键 YAML') from exc
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'notes'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['notes'], dict)):
        raise store.OfflineError('退休笔记登记字段无效')
    notes = {}
    for relative, entry in value['notes'].items():
        if not isinstance(relative, str):
            raise store.OfflineError('退休笔记必须使用精确仓库相对路径')
        # Validate lexical scope without resolving a caller's filesystem here.
        path = Path(relative)
        parts = path.parts
        allowed = (relative == 'sources/test/README.md' or (len(parts) >= 3 and parts[:2] in {
            ('reports', 'test'), ('insights', 'test'), ('articles', 'test')})
            or (len(parts) >= 4 and parts[:3] in {
                ('sources', 'papers', 'test'), ('sources', 'blogs', 'test')}))
        if (not allowed or path.suffix != '.md' or path.is_absolute()
                or path.as_posix() != relative or '..' in parts
                or any(char in relative for char in '\\*?[]\x00\r\n')
                or not isinstance(entry, dict) or set(entry) != {'sha256', 'reason'}
                or not isinstance(entry['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])
                or not isinstance(entry['reason'], str) or not entry['reason'].strip()):
            raise store.OfflineError('退休笔记仅允许明确的历史 TEST Markdown 和原散列')
        notes[relative] = entry['sha256']
    return notes


def missing_hash(root, relative, expected=None):
    """Return only a registered absent note's old hash; existing bytes stay strict."""
    target = _path(root, relative)
    if target.exists():
        return None
    registration = _path(root, CONFIG)
    if not registration.exists():
        return None
    payload = registration.read_bytes()
    if len(payload) > 1_000_000:
        raise store.OfflineError('退休笔记登记过大')
    registered = _parse(payload).get(relative)
    return registered if registered is not None and (expected is None or registered == expected) else None
