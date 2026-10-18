"""Read-only source identities and accepted test-to-formal mappings."""

from pathlib import Path
import re

import researchdesk_offline as store


SOURCE_ID = re.compile(r'(?:paper|blog)-[0-9a-f-]{36}\Z')


def comparison_metadata(metadata):
    """Normalize URL spelling only for comparisons, never persisted evidence.

    The shared URL policy removes known tracking parameters and fragments but
    preserves meaningful query values/order, paths and trailing slashes. An
    official arXiv URL may use abs/pdf/html for the same versioned paper; its
    explicit source_version remains a separate part of the metadata comparison.
    Historical candidates and their original metadata hashes stay immutable.
    """
    normalized = dict(metadata)
    url = store.canonical_url(metadata['source_url'])
    match = re.fullmatch(
        r'https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf|html)/'
        r'((?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7}))(v[1-9]\d*)?(?:\.pdf)?',
        url, re.I)
    version = metadata.get('source_version')
    if (match and isinstance(version, str) and re.fullmatch(r'v[1-9]\d*', version)
            and (not match.group(2) or match.group(2).lower() == version)):
        # identities() validates any explicit ID against the URL before this
        # comparison is used. Do not infer an unknown version from a URL.
        store.identities(metadata)
        url = 'https://arxiv.org/abs/' + match.group(1).lower()
    normalized['source_url'] = url
    return normalized


def accepted_records(root):
    root=Path(root).resolve()
    for path in sorted((root/'reports').glob('*/admissions/*/accepted.yaml')):
        if any(part.is_symlink() for part in (path,)+tuple(path.parents) if part!=root and root in part.parents):
            raise store.OfflineError('正式准入记录不能为符号链接')
        marker=Path(str(path)+'.sha256')
        if marker.is_symlink() or not marker.is_file() or marker.read_text().strip()!=store.digest(path.read_bytes()):
            raise store.OfflineError('正式准入记录散列无效')
        value=store.load_yaml(path)
        if value.get('production_accepted') is not True or value.get('status')!='accepted':
            raise store.OfflineError('正式准入记录未被接受')
        yield value


def aliases(root):
    result={}
    for record in accepted_records(root):
        for old,new in record.get('source_id_map',{}).items():
            if (not SOURCE_ID.fullmatch(old) or not isinstance(new,str) or not SOURCE_ID.fullmatch(new)
                    or old.split('-',1)[0]!=new.split('-',1)[0]):
                raise store.OfflineError('正式来源映射无效')
            if old==new:
                continue
            if old in result and result[old]!=new:
                raise store.OfflineError('正式来源映射冲突')
            result[old]=new
    return result


def resolve(identifier, mapping):
    seen=set()
    while identifier in mapping:
        if identifier in seen:
            raise store.OfflineError('正式来源映射形成循环')
        seen.add(identifier)
        identifier=mapping[identifier]
    return identifier


def source_index(root):
    index=store.source_index(root)
    mapping=aliases(root)
    for key,values in list(index.items()):
        formal={identifier:value for identifier,value in values.items() if Path(value[0]).parts[2:3]!=('test',)}
        if len(formal)==1:
            identifier=next(iter(formal))
            if all(resolve(old,mapping)==identifier for old in values):
                index[key]=formal
    return index
