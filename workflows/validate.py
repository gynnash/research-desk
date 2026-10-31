#!/usr/bin/env python3
"""Read-only checks for ResearchDesk files; never collects or rewrites content."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import posixpath
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML；请先安装 workflows/requirements.txt 中的依赖。")


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate or non-string mapping keys rather than losing values."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise yaml.constructor.ConstructorError(
                None, None, f"重复或非字符串 YAML 键：{key!r}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)

COMMON_FIELDS = {
    "schema_version", "id", "kind", "title", "source", "source_url", "authors",
    "published_at", "collected_at", "updated_at", "topics", "status",
    "related_sources", "related_notes",
}
PAPER_FIELDS = {"arxiv_id", "doi", "source_version"}
STATUSES = {"inbox", "reading", "analyzed", "archived"}
TRACKING_KEYS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid"}


def canonical_url(value):
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("必须是完整 HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL 不得包含账号密码")
    if re.search(r"\s", value):
        raise ValueError("URL 不得包含空白字符")
    host = parts.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    port = parts.port
    if port is not None and (parts.scheme.lower(), port) not in {("http", 80), ("https", 443)}:
        host += f":{port}"
    query = [
        (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(query), ""))


def check_workspace(root, topics, fail, frontmatter):
    """Check the two public reading trees against their existing fixed receipts."""
    identity = re.compile(r'[a-z0-9][a-z0-9_-]{0,100}\Z')
    digest = lambda payload: hashlib.sha256(payload).hexdigest()
    originals, summary_count = {}, 0

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def safe(relative):
        require(isinstance(relative, str), '文件路径必须是字符串')
        path = Path(relative)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in relative
                and path.as_posix() == relative and path.parts
                and path.parts[0] in {'collection', 'summary', 'reports'}, '文件路径越界或格式无效')
        current = root
        for part in path.parts:
            current = current / part
            require(not current.is_symlink(), '文件或上级目录不可为符号链接')
        require(current.resolve().is_relative_to(root) and current.is_file(), '文件不存在或越界')
        return current

    def checked(relative):
        path, marker = safe(relative), safe(relative + '.sha256')
        require(marker.read_text().strip() == digest(path.read_bytes()), '文件与配对散列不一致')
        data = yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueKeyLoader)
        require(isinstance(data, dict), 'YAML 顶层必须是映射')
        return data

    def verify_hashes(values, required):
        require(isinstance(values, dict) and required.issubset(values), '回执缺少必须绑定的输入或输出散列')
        for relative, expected in values.items():
            require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), '文件散列无效')
            require(digest(safe(relative).read_bytes()) == expected, '回执绑定文件已变化：' + relative)

    for directory in ('collection', 'summary'):
        tree = root / directory
        if tree.is_symlink():
            fail(directory, '资料目录不可为符号链接')
            continue
        for path in tree.rglob('*'):
            if path.is_symlink():
                fail(path.relative_to(root).as_posix(), '资料文件或目录不可为符号链接')

    collection_tree, summary_tree = root / 'collection', root / 'summary'
    for path in sorted(collection_tree.rglob('manifest.yaml')) if not collection_tree.is_symlink() else []:
        relative = path.relative_to(root).as_posix()
        try:
            parts = path.relative_to(root).parts
            require(len(parts) == 4 and parts[1] in topics and identity.fullmatch(parts[2]),
                    '采集索引必须位于 collection/<已配置主题>/<批次>/manifest.yaml')
            topic, cycle_id = parts[1:3]
            index = checked(relative)
            receipt_path = 'reports/test/%s/cycles/%s/collection.yaml' % (topic, cycle_id)
            require(type(index.get('schema_version')) is int and index.get('schema_version') == 1 and index.get('mode') == 'collection_index'
                    and index.get('topic') == topic and index.get('cycle_id') == cycle_id
                    and index.get('receipt_path') == receipt_path, '采集索引身份或回执路径无效')
            receipt = checked(receipt_path)
            require(index.get('receipt_sha256') == digest(safe(receipt_path).read_bytes()), '采集索引绑定的回执已变化')
            records = receipt.get('records')
            require(receipt.get('mode') == 'collection_only' and receipt.get('topic') == topic
                    and receipt.get('cycle_id') == cycle_id and receipt.get('collection_manifest_path') == relative
                    and isinstance(records, list) and records == index.get('records')
                    and receipt.get('status') == ('collected' if records else 'empty'), '采集索引与完成回执不一致')
            base = 'reports/test/%s/cycles/%s/' % (topic, cycle_id)
            verify_hashes(receipt.get('input_hashes'), {
                base + name + suffix for name in ('manifest', 'discovery', 'selection')
                for suffix in ('.yaml', '.yaml.sha256')})
            verify_hashes(receipt.get('output_hashes'), set())
            for record in records:
                require(isinstance(record, dict) and isinstance(record.get('key'), str)
                        and identity.fullmatch(record['key']), '采集来源标识无效')
                key = record['key']
                original = 'collection/%s/%s/items/%s/original' % (topic, cycle_id, key)
                plan = 'reports/test/%s/research-batches/%s/items/%s/candidate.yaml' % (topic, cycle_id, key)
                require(record.get('original_path') == original + '.yaml'
                        and record.get('original_markdown_path') == original + '.md'
                        and record.get('candidate_path') == plan and record.get('coverage') == 'full_text'
                        and (topic, cycle_id, key) not in originals, '采集来源路径、范围或身份不一致')
                require({plan, plan + '.sha256', original + '.yaml', original + '.yaml.sha256',
                         original + '.md'}.issubset(receipt['output_hashes']), '采集原文或候选缺少输出散列绑定')
                snapshot, candidate_plan = checked(original + '.yaml'), checked(plan)
                candidate = candidate_plan.get('candidate', {})
                require(isinstance(candidate, dict) and candidate.get('topic') == topic and candidate.get('key') == key
                        and candidate.get('content_hash') == record.get('content_hash')
                        and candidate.get('source_id') == record.get('source_id')
                        and candidate.get('evidence', {}).get('coverage') == 'full_text', '原文候选身份或全文范围无效')
                binding = candidate.get('archive', {})
                require(binding.get('path') == original + '.yaml' and binding.get('markdown_path') == original + '.md'
                        and binding.get('sha256') == digest(safe(original + '.yaml').read_bytes())
                        and binding.get('markdown_sha256') == digest(safe(original + '.md').read_bytes()), '原文归档绑定散列不一致')
                require(snapshot.get('candidate') == {name: value for name, value in candidate.items() if name != 'archive'},
                        '归档内容不对应已绑定候选')
                originals[topic, cycle_id, key] = record
        except (ValueError, OSError, UnicodeError, yaml.YAMLError, TypeError, KeyError, AttributeError) as exc:
            fail(relative, str(exc))

    known = {record['original_markdown_path'] for record in originals.values()}
    known.update(record['original_path'] for record in originals.values())
    collection_files = (sorted(collection_tree.rglob('*.md')) + sorted(collection_tree.rglob('original.yaml'))
                        if not collection_tree.is_symlink() else [])
    for path in collection_files:
        relative = path.relative_to(root).as_posix()
        if path.name != 'README.md' and relative not in known:
            fail(relative, '原文未被已完成采集索引引用')

    for path in sorted(summary_tree.rglob('*.md')) if not summary_tree.is_symlink() else []:
        if path.name == 'README.md':
            continue
        relative = path.relative_to(root).as_posix()
        summary_count += 1
        try:
            parts = path.relative_to(root).parts
            require(len(parts) == 4 and parts[1] in topics and identity.fullmatch(parts[2])
                    and identity.fullmatch(path.stem), '总结必须位于 summary/<已配置主题>/<批次>/<来源>.md')
            topic, cycle_id, key = parts[1], parts[2], path.stem
            text = safe(relative).read_text(encoding='utf-8')
            data = frontmatter(text, relative)
            require(type(data.get('schema_version')) is int and data.get('schema_version') == 1 and data.get('kind') == 'research_summary'
                    and data.get('topic') == topic and data.get('cycle_id') == cycle_id
                    and data.get('coverage') == 'full_text' and data.get('review_status') == 'passed',
                    '总结类型、主题、全文范围或审阅状态无效')
            models = {role: data.get(role + '_model') for role in ('research', 'review')}
            require(all(isinstance(value, str) and value.strip() for value in models.values())
                    and models['research'] != models['review'], '研究与独立审阅必须使用不同模型')
            canonical_url(data.get('source_url', ''))
            record = originals.get((topic, cycle_id, key))
            require(record is not None and data.get('source_id') == record['source_id']
                    and data.get('collection_original') == record['original_markdown_path'], '总结未关联同主题同批次的采集原文')
            safe(data['collection_original'])
            link = posixpath.relpath(data['collection_original'], posixpath.dirname(relative))
            require('](%s)' % link in text, '总结缺少可点击的已采集原文链接')
            prefix = 'reports/test/%s/research-batches/%s/items/%s/' % (topic, cycle_id, key)
            binding = checked(prefix + 'summary.yaml')
            require(binding.get('path') == relative and binding.get('sha256') == digest(path.read_bytes())
                    and binding.get('source_id') == data['source_id']
                    and binding.get('research_result_path') == prefix + 'result.yaml', '总结输出绑定无效或内容已变化')
            result = checked(prefix + 'result.yaml')
            require(binding.get('research_result_sha256') == digest(safe(prefix + 'result.yaml').read_bytes())
                    and result.get('key') == key and result.get('source_id') == data['source_id']
                    and result.get('status') == 'test_accepted' and result.get('coverage') == 'full_text'
                    and result.get('models') == models and result.get('revision_count') in (0, 1), '总结缺少对应的审阅通过结果证明')
            review = checked(prefix + 'checkpoints/review-%s.yaml' % result['revision_count'])
            review_body = json.loads(review.get('result', {}).get('text', ''))
            require(isinstance(review_body, dict) and review_body.get('decision') == 'pass', '独立审阅检查点没有通过')
        except (ValueError, OSError, UnicodeError, yaml.YAMLError, TypeError, KeyError, AttributeError) as exc:
            fail(relative, str(exc))
    return len(originals), summary_count


def check(root, include_test=False):
    root = Path(root).resolve()
    errors, warnings = [], []

    def fail(path, message):
        errors.append(f"{path}: {message}")

    def load_yaml(text, label):
        try:
            data = yaml.load(text, Loader=UniqueKeyLoader)
        except (yaml.YAMLError, ValueError, OverflowError) as exc:
            fail(label, f"YAML 无效：{exc}")
            return {}
        if not isinstance(data, dict):
            fail(label, "YAML 顶层必须为映射")
            return {}
        return data

    def read(path):
        try:
            return (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            fail(path, f"无法读取：{exc}")
            return ""

    def string_list(value, label, nonempty=False):
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            fail(label, "必须为非空字符串组成的列表")
            return []
        if nonempty and not value:
            fail(label, "列表不能为空")
        if len(value) != len(set(value)):
            fail(label, "列表中存在重复项")
        return value

    def frontmatter(text, path):
        lines = text.splitlines()
        if not lines or lines[0] != "---":
            fail(path, "缺少开头的 YAML Frontmatter")
            return {}
        try:
            end = lines.index("---", 1)
        except ValueError:
            fail(path, "缺少 Frontmatter 结束分隔符 ---")
            return {}
        return load_yaml("\n".join(lines[1:end]), path)

    def fields(data, required, optional, label):
        missing, unknown = required - data.keys(), data.keys() - required - optional
        if missing:
            fail(label, f"缺少字段：{', '.join(sorted(missing))}")
        if unknown:
            fail(label, f"未知字段：{', '.join(sorted(unknown))}")

    def local_note(path, folders):
        if not isinstance(path, str):
            return False
        try:
            relative = Path(path)
            return (
                not relative.is_absolute() and ".." not in relative.parts
                and len(relative.parts) > 1 and relative.parts[0] in folders
                and relative.suffix == ".md" and relative.as_posix() == path
                and (root / relative).resolve().is_relative_to(root)
                and (root / relative).is_file()
            )
        except (ValueError, OSError, RuntimeError):
            return False

    # A framework checkout contains no knowledge/output directories. Writers
    # create them when actual work starts; records are still validated below.
    for directory in ("config", "workflows", "workflows/templates"):
        if not (root / directory).is_dir():
            fail(directory, "缺少目录")
    for path in ("README.md", ".gitignore", "workflows/README.md", "workflows/source-schema.md", "workflows/maintenance.md", "workflows/requirements.txt", "config/research_topics.yaml", "config/legacy_sources.yaml"):
        if not (root / path).is_file():
            fail(path, "缺少文件")

    configs = {}
    for path in sorted((root / "config").rglob("*")):
        if path.is_file() and path.suffix in {".yaml", ".yml"}:
            relative = path.relative_to(root).as_posix()
            configs[relative] = load_yaml(read(relative), relative)

    topic_path = "config/research_topics.yaml"
    config = configs.get(topic_path, {})
    fields(config, {"schema_version", "topics"}, set(), topic_path)
    topics = config.get("topics")
    if type(config.get("schema_version")) is not int or config.get("schema_version") != 1:
        fail(topic_path, "schema_version 必须是整数 1")
    if not isinstance(topics, dict) or not topics:
        fail(topic_path, "topics 必须为非空映射")
        topics = {}
    for topic_id, topic in topics.items():
        label = f"{topic_path} [{topic_id}]"
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*", topic_id):
            fail(label, "主题 ID 需使用小写字母、数字、连字符或下划线")
        if not isinstance(topic, dict):
            fail(label, "主题必须为映射")
            continue
        fields(topic, {"name", "enabled", "description", "scope", "keywords"}, set(), label)
        for key in ("name", "description"):
            if not isinstance(topic.get(key), str) or not topic[key].strip():
                fail(label, f"{key} 必须为非空字符串")
        if type(topic.get("enabled")) is not bool:
            fail(label, "enabled 必须为布尔值")
        for key in ("scope", "keywords"):
            string_list(topic.get(key), f"{label}.{key}", nonempty=True)

    legacy_path = "config/legacy_sources.yaml"
    legacy_config = configs.get(legacy_path, {})
    fields(legacy_config, {"schema_version", "files"}, set(), legacy_path)
    if type(legacy_config.get("schema_version")) is not int or legacy_config.get("schema_version") != 1:
        fail(legacy_path, "schema_version 必须是整数 1")
    legacy_entries = legacy_config.get("files", [])
    if not isinstance(legacy_entries, list):
        fail(legacy_path, "files 必须为列表")
        legacy_entries = []
    legacy = set()
    for entry in legacy_entries:
        if not isinstance(entry, dict):
            fail(legacy_path, "files 条目必须为映射")
            continue
        fields(entry, {"path", "reason"}, set(), legacy_path)
        path, reason = entry.get("path"), entry.get("reason")
        if not local_note(path, {"sources"}) or not path.startswith(("sources/papers/", "sources/blogs/")):
            fail(legacy_path, f"旧资料路径无效或文件不存在：{path!r}")
            continue
        if len(Path(path).parts) > 3 and Path(path).parts[2] == "test":
            fail(legacy_path, "测试目录不得加入旧资料豁免清单")
            continue
        if not isinstance(reason, str) or not reason.strip():
            fail(legacy_path, "旧资料必须说明豁免原因")
        if path in legacy:
            fail(legacy_path, f"重复旧资料路径：{path}")
        legacy.add(path)

    for kind in ("paper", "blog"):
        path = f"workflows/templates/{kind}.md"
        data = frontmatter(read(path), path)
        fields(data, COMMON_FIELDS | (PAPER_FIELDS if kind == "paper" else set()), set(), path)
        if type(data.get("schema_version")) is not int or data.get("schema_version") != 1 or data.get("kind") != kind:
            fail(path, "模板 schema_version 或 kind 无效")

    # Tests have their own identity index, but never become a Schema exemption.
    # Only this exact directory convention marks a source as a test record;
    # names such as test.md or nested topic/test/ do not opt out of validation.
    records, ids, identities = [], {}, {}
    test_count = 0
    for folder, kind in (("papers", "paper"), ("blogs", "blog")):
        for file in sorted((root / "sources" / folder).rglob("*.md")):
            path = file.relative_to(root).as_posix()
            parts = Path(path).parts
            is_test = len(parts) > 3 and parts[2] == "test"
            zone = "test" if is_test else "formal"
            if is_test:
                if len(parts) != 5 or parts[3] not in topics:
                    fail(path, "测试来源路径必须为 sources/<papers|blogs>/test/<已配置主题>/<id>.md")
                    continue
                if not re.fullmatch(rf"{kind}-[0-9a-f]{{8}}(?:-[0-9a-f]{{4}}){{3}}-[0-9a-f]{{12}}\.md", parts[4]):
                    fail(path, "测试来源文件名必须为 <kind>-<小写标准 UUID v4>.md")
                if not include_test:
                    continue
            text = read(path)
            if path in legacy:
                if is_test:
                    fail(path, "测试资料不得通过 legacy_sources.yaml 豁免")
                    continue
                if text.splitlines()[:1] == ["---"]:
                    fail(path, "已有 Frontmatter，请移除旧资料豁免后完整校验")
                else:
                    warnings.append(f"{path}: 按 legacy_sources.yaml 跳过旧资料 Schema 检查")
                continue
            data = frontmatter(text, path)
            records.append((path, data, zone))
            test_count += int(is_test)
            if is_test:
                lines = text.splitlines()
                try:
                    body_lines = lines[lines.index("---", 1) + 1:]
                except ValueError:
                    body_lines = []
                banners = {"> TEST：离线虚构样例，不可作为正式研究证据。", "> TEST：真实来源采集，分析与审阅均为模拟，不可作为正式研究结论。"}
                if not banners.intersection(body_lines):
                    fail(path, "测试来源正文必须声明 TEST 资料性质及模拟分析边界")
            fields(data, COMMON_FIELDS, PAPER_FIELDS if kind == "paper" else set(), path)
            if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
                fail(path, "schema_version 必须是整数 1")
            if data.get("kind") != kind:
                fail(path, f"kind 必须为 {kind}，与目录一致")
            for key in ("title", "source", "source_url", "id"):
                if not isinstance(data.get(key), str) or not data[key].strip():
                    fail(path, f"{key} 必须为非空字符串")
            record_id = data.get("id")
            try:
                prefix = kind + "-"
                raw_uuid = record_id[len(prefix):] if isinstance(record_id, str) and record_id.startswith(prefix) else ""
                parsed = UUID(raw_uuid)
                if parsed.version != 4 or str(parsed) != raw_uuid:
                    raise ValueError()
            except (ValueError, AttributeError):
                fail(path, f"id 必须为 {kind}-<小写标准 UUID v4>")
            if isinstance(record_id, str) and record_id:
                if record_id in ids:
                    fail(path, f"重复 ID，已存在于 {ids[record_id][0]}")
                ids[record_id] = (path, zone)
            if is_test:
                if file.stem != record_id:
                    fail(path, "测试来源文件名必须与 Frontmatter id 一致")
                if not isinstance(data.get("topics"), list) or parts[3] not in data["topics"]:
                    fail(path, "测试来源 topics 必须包含所在目录的主题 ID")
            for key in ("authors", "topics", "related_sources", "related_notes"):
                values = string_list(data.get(key), f"{path}.{key}", nonempty=(key == "topics"))
                if key == "topics":
                    for value in values:
                        if value not in topics:
                            fail(path, f"未知研究主题：{value}")
            if not isinstance(data.get("status"), str) or data["status"] not in STATUSES:
                fail(path, "status 必须为 inbox/reading/analyzed/archived")
            dates = {}
            for key in ("published_at", "collected_at", "updated_at"):
                value = data.get(key)
                if key == "published_at" and value is None:
                    continue
                try:
                    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError()
                    dates[key] = date.fromisoformat(value)
                except ValueError:
                    fail(path, f"{key} 必须为带引号的有效 YYYY-MM-DD 日期")
            if "updated_at" in dates and "collected_at" in dates and dates["updated_at"] < dates["collected_at"]:
                fail(path, "updated_at 不能早于 collected_at")
            keys = []
            if isinstance(data.get("source_url"), str):
                try:
                    keys.append(("URL", canonical_url(data["source_url"])))
                except ValueError as exc:
                    fail(path, f"source_url 无效：{exc}")
            for key, pattern in (("arxiv_id", r"(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})"), ("doi", r"10\.\d{4,9}/\S+")):
                value = data.get(key)
                if value is None:
                    continue
                if not isinstance(value, str) or value != value.lower() or not re.fullmatch(pattern, value):
                    fail(path, f"{key} 必须为规范化的基础编号/裸标识字符串或 null")
                else:
                    keys.append((key, value))
            if data.get("source_version") is not None and (not isinstance(data["source_version"], str) or not data["source_version"].strip()):
                fail(path, "source_version 必须为非空字符串或 null")
            for key in keys:
                scoped_key = (zone, key)
                if scoped_key in identities:
                    fail(path, f"重复来源 {key[0]}，已存在于 {identities[scoped_key]}")
                identities[scoped_key] = path

    # Originals are extracted snapshots, not duplicate paper/blog identity cards.
    for file in sorted((root / 'sources/originals').glob('*/*.md')):
        path = file.relative_to(root).as_posix()
        if file.name == 'README.md':
            continue
        data = frontmatter(read(path), path)
        if not isinstance(data, dict):
            continue
        if (data.get('schema_version') != 1 or data.get('kind') != 'original_snapshot'
                or file.parent.name not in topics or data.get('topics') != [file.parent.name]):
            fail(path, '原文快照的类型、版本或方向无效')
        identifier = data.get('source_id', '')
        if (not isinstance(identifier, str) or not re.fullmatch(
                r'(?:paper|blog)-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identifier)
                or not re.fullmatch(re.escape(identifier) + r'-[0-9a-f]{64}\.md', file.name)):
            fail(path, '原文快照文件名或来源ID无效')
        for key in ('title', 'source_url', 'captured_at'):
            if not isinstance(data.get(key), str) or not data[key].strip():
                fail(path, f'原文快照缺少 {key}')
        if not isinstance(data.get('content_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', data['content_sha256']):
            fail(path, '原文内容散列无效')
        for key in ('coverage', 'research_coverage'):
            if data.get(key) not in {'full_text', 'excerpt', 'abstract_only'}:
                fail(path, f'{key} 必须如实标明全文、节选或摘要')

    # Resolve after collecting all IDs, so references do not depend on file order.
    for path, data, zone in records:
        related = data.get("related_sources")
        for target in related if isinstance(related, list) else []:
            if not isinstance(target, str):
                continue  # Already reported by string_list.
            if target == data.get("id"):
                fail(path, "related_sources 不得自关联")
            elif target not in ids:
                fail(path, f"关联资料 ID 不存在：{target}")
            elif ids[target][1] != zone:
                fail(path, "正式与测试资料不得通过 related_sources 互相引用")
        notes = data.get("related_notes")
        for note in notes if isinstance(notes, list) else []:
            if not local_note(note, {"reports", "insights", "articles"}):
                fail(path, f"关联研究文件无效或不存在：{note!r}")
                continue
            note_parts = Path(note).parts
            note_is_test = len(note_parts) > 2 and note_parts[1] == "test"
            if note_is_test != (zone == "test"):
                fail(path, "正式与测试资料不得通过 related_notes 互相引用")
            elif note_is_test and (len(note_parts) < 4 or note_parts[2] != Path(path).parts[3]):
                fail(path, "测试 related_notes 必须保存在同一主题的 <reports|insights|articles>/test/<topic>/ 下")

    collection_count, summary_count = check_workspace(root, topics, fail, frontmatter)

    for warning in warnings:
        print(f"WARN {warning}")
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        print(f"检查失败：{len(errors)} 个问题。", file=sys.stderr)
        return 1
    test_label = f"{test_count} 条测试资料" if include_test else "测试资料未检查（使用 --include-test 纳入）"
    print(f"检查通过：{len(topics)} 个主题，{len(records) - test_count} 条正式资料，{test_label}，{collection_count} 篇采集原文，{summary_count} 篇逐篇总结，{len(warnings)} 条旧资料豁免。")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="仓库根目录（默认由脚本位置确定）")
    parser.add_argument("--include-test", action="store_true", help="同时校验隔离测试资料；独立查重并禁止与正式资料互链")
    args = parser.parse_args()
    return check(args.root.resolve(), include_test=args.include_test)


if __name__ == "__main__":
    sys.exit(main())
