#!/usr/bin/env python3
"""Read-only checks for ResearchDesk files; never collects or rewrites content."""

import argparse
from datetime import date
from pathlib import Path
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


def check(root):
    errors, warnings = [], []

    def fail(path, message):
        errors.append(f"{path}: {message}")

    def load_yaml(text, label):
        try:
            data = yaml.load(text, Loader=UniqueKeyLoader)
        except yaml.YAMLError as exc:
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
        relative = Path(path)
        return (
            not relative.is_absolute() and ".." not in relative.parts
            and len(relative.parts) > 1 and relative.parts[0] in folders
            and relative.suffix == ".md" and relative.as_posix() == path
            and (root / relative).resolve().is_relative_to(root)
            and (root / relative).is_file()
        )

    for directory in ("config", "sources", "sources/papers", "sources/blogs", "reports", "insights", "articles", "workflows", "workflows/templates"):
        if not (root / directory).is_dir():
            fail(directory, "缺少目录")
    for path in ("README.md", ".gitignore", "sources/README.md", "reports/README.md", "insights/README.md", "articles/README.md", "workflows/README.md", "workflows/source-schema.md", "workflows/maintenance.md", "workflows/requirements.txt", "config/research_topics.yaml", "config/legacy_sources.yaml"):
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
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", topic_id):
            fail(label, "主题 ID 需使用小写字母、数字和连字符")
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

    records, ids, identities = [], {}, {}
    for folder, kind in (("papers", "paper"), ("blogs", "blog")):
        for file in sorted((root / "sources" / folder).rglob("*.md")):
            path = file.relative_to(root).as_posix()
            text = read(path)
            if path in legacy:
                if text.splitlines()[:1] == ["---"]:
                    fail(path, "已有 Frontmatter，请移除旧资料豁免后完整校验")
                else:
                    warnings.append(f"{path}: 按 legacy_sources.yaml 跳过旧资料 Schema 检查")
                continue
            data = frontmatter(text, path)
            records.append((path, data))
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
                    fail(path, f"重复 ID，已存在于 {ids[record_id]}")
                ids[record_id] = path
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
                if key in identities:
                    fail(path, f"重复来源 {key[0]}，已存在于 {identities[key]}")
                identities[key] = path

    # Resolve after collecting all IDs, so references do not depend on file order.
    for path, data in records:
        related = data.get("related_sources")
        for target in related if isinstance(related, list) else []:
            if not isinstance(target, str):
                continue  # Already reported by string_list.
            if target == data.get("id"):
                fail(path, "related_sources 不得自关联")
            elif target not in ids:
                fail(path, f"关联资料 ID 不存在：{target}")
        notes = data.get("related_notes")
        for note in notes if isinstance(notes, list) else []:
            if not local_note(note, {"reports", "insights", "articles"}):
                fail(path, f"关联研究文件无效或不存在：{note!r}")

    for warning in warnings:
        print(f"WARN {warning}")
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        print(f"检查失败：{len(errors)} 个问题。", file=sys.stderr)
        return 1
    print(f"检查通过：{len(topics)} 个主题，{len(records)} 条正式资料，{len(warnings)} 条旧资料豁免。")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="仓库根目录（默认由脚本位置确定）")
    args = parser.parse_args()
    return check(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())
