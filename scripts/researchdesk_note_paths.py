"""Names for reviewed reading notes, with stable IDs for their proof files."""

from pathlib import PurePath, PurePosixPath
import re
import unicodedata


IDENTITY = re.compile(r'[a-z0-9][a-z0-9_-]{0,100}\Z')
LABEL_LENGTH = 22
DEVICE_NAME = re.compile(r'(?:con|prn|aux|nul|com[1-9]|lpt[1-9])\Z', re.IGNORECASE)
CLAUSE_BREAK = re.compile(r'[:,;。!?—–]')
QUOTATION_MARKS = str.maketrans('', '', '“”‘’「」『』《》')


def _label_words(text):
    return '-'.join(''.join(char if char.isalnum() else ' ' for char in text).split())


def note_label(*values):
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = unicodedata.normalize('NFKC', value).translate(QUOTATION_MARKS)
        label = _label_words(normalized)
        if len(label) > LABEL_LENGTH:
            leading = _label_words(CLAUSE_BREAK.split(normalized, maxsplit=1)[0])
            label = leading if 8 <= len(leading) <= LABEL_LENGTH else label[:LABEL_LENGTH].rstrip('-')
        if label:
            return '笔记-' + label if DEVICE_NAME.fullmatch(label) else label
    return ''


def _valid_label(label):
    return bool(label) and label == note_label(label)


def named_component(label, identity):
    if not _valid_label(label) or not IDENTITY.fullmatch(identity):
        raise ValueError('无效的可读文件名或固定标识')
    return label + '~' + identity


def component_identity(name):
    """Decode both the original ASCII ID and a labeled component."""
    if not isinstance(name, str):
        return None
    label, separator, identity = name.partition('~')
    if not separator:
        identity = label
    if IDENTITY.fullmatch(identity) and (not separator or _valid_label(label)):
        return identity
    return None


def _note_parts(relative, tree):
    if isinstance(relative, PurePath):
        relative = relative.as_posix()
    if not isinstance(relative, str):
        return None
    path = PurePosixPath(relative)
    parts = path.parts
    if (path.as_posix() == relative and len(parts) == 4 and parts[0] == tree
            and IDENTITY.fullmatch(parts[1]) and path.suffix == '.md'):
        return parts[1], parts[2], path.stem
    return None


def summary_ids(relative):
    parts = _note_parts(relative, 'summary')
    if parts:
        topic, folder, stem = parts
        cycle, key = component_identity(folder), component_identity(stem)
        if cycle and key:
            return topic, cycle, key
    return None


def insight_ids(relative):
    parts = _note_parts(relative, 'insights')
    if parts:
        topic, folder, stem = parts
        cycle = component_identity(folder)
        if cycle and (_valid_label(stem) if '~' in folder else stem == 'report'):
            return topic, cycle
    return None
