#!/usr/bin/env python3
"""Bounded, read-only client for the official Zhihu search and quota APIs.

Official contract: https://developer.zhihu.com/docs
Search ContentText is a summary, never evidence of complete original reading.
No model, scheduler, repository writer, browser session or payment fallback lives
here. A quota check is not a reservation and cannot guarantee zero billing when
other clients consume the same account quota concurrently.
"""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import math
import os
import time
import warnings
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ORIGIN = "https://developer.zhihu.com"
QUOTA_PATH = "/api/v1/quota"
SEARCH_PATH = "/api/v1/content/zhihu_search"
API_ID = "zhihu_search"
CONTENT_HOSTS = frozenset({"zhihu.com", "www.zhihu.com", "zhuanlan.zhihu.com"})


class ZhihuError(ValueError):
    """A stable local error code; never contains a remote error body or secret."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**63 - 1


def _public_url(value):
    if (not isinstance(value, str) or len(value) > 4096
            or any(character.isspace() or ord(character) < 32 for character in value)
            or "\\" in value):
        raise ZhihuError("invalid_content_url")
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.hostname not in CONTENT_HOSTS
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443)):
            raise ZhihuError("invalid_content_url")
        query = [(key, item) for key, item in parse_qsl(
            parts.query, keep_blank_values=True, max_num_fields=100)
                 if not key.lower().startswith("utm_")]
    except ValueError:
        raise ZhihuError("invalid_content_url") from None
    return urlunsplit(("https", parts.hostname, parts.path or "/", urlencode(query), ""))


def _iso(timestamp):
    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        raise ZhihuError("invalid_timestamp") from None


class ZhihuClient:
    def __init__(self, access_secret, opener=None, clock=None, timeout=20,
                 max_bytes=2_000_000):
        if not isinstance(access_secret, str) or not access_secret:
            raise ZhihuError("missing_access_secret")
        if (len(access_secret) > 8192
                or any(not 33 <= ord(character) <= 126 for character in access_secret)):
            raise ZhihuError("invalid_access_secret")
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            raise ZhihuError("invalid_timeout")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 4_000_000:
            raise ZhihuError("invalid_response_limit")
        self._secret = access_secret
        self.opener = opener or build_opener(_NoRedirect())
        self.clock = clock or time.time
        self.timeout, self.max_bytes = timeout, max_bytes

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ZhihuError("invalid_clock")
        value = int(value)
        if not _integer(value):
            raise ZhihuError("invalid_clock")
        return value

    def _request(self, path, parameters):
        if path not in {QUOTA_PATH, SEARCH_PATH}:
            raise ZhihuError("endpoint_not_allowed")
        url = ORIGIN + path + "?" + urlencode(parameters)
        request = Request(url, headers={
            "Authorization": "Bearer " + self._secret,
            "X-Request-Timestamp": str(self._now()),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "ResearchDesk/0.1 (official Zhihu API; read-only)",
        })
        response = None
        try:
            call = self.opener.open if hasattr(self.opener, "open") else self.opener
            response = call(request, timeout=self.timeout)
            status = getattr(response, "status", None) or response.getcode()
            if status in {301, 302, 303, 307, 308}:
                raise ZhihuError("redirect_rejected")
            if status != 200:
                raise ZhihuError("http_error")
            if hasattr(response, "geturl") and response.geturl() != url:
                raise ZhihuError("unvalidated_redirect")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if content_type != "application/json":
                raise ZhihuError("unexpected_content_type")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise ZhihuError("unexpected_content_encoding")
            length = response.headers.get("Content-Length")
            if length and (not length.isdigit() or int(length) > self.max_bytes):
                raise ZhihuError("response_too_large")
            raw = response.read(self.max_bytes + 1)
            if not isinstance(raw, bytes) or not raw or len(raw) > self.max_bytes:
                raise ZhihuError("invalid_response_size")
            # Fail rather than print a credential unexpectedly echoed by a server.
            if self._secret.encode() in raw:
                raise ZhihuError("credential_in_response")
            try:
                payload = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeError, ValueError):
                raise ZhihuError("invalid_json") from None
            if not isinstance(payload, dict) or type(payload.get("Code")) is not int:
                raise ZhihuError("invalid_api_response")
            code = payload["Code"]
            if code != 0:
                raise ZhihuError({10001: "invalid_api_parameters", 20001: "authentication_failed",
                                  30001: "rate_or_quota_limit", 90001: "upstream_internal_error"}.get(
                                      code, "upstream_api_error"))
            return payload.get("Data"), {
                "request_url": url, "status": 200,
                "observed_at": _iso(self._now()),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
            }
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status in {301, 302, 303, 307, 308}:
                raise ZhihuError("redirect_rejected") from None
            raise ZhihuError({401: "authentication_failed", 403: "access_denied",
                              429: "rate_or_quota_limit"}.get(status, "http_error")) from None
        except (URLError, OSError, TimeoutError):
            raise ZhihuError("network_error") from None
        finally:
            if response is not None:
                response.close()

    def quota(self):
        data, proof = self._request(QUOTA_PATH, {"APIIDs": API_ID})
        if not isinstance(data, list):
            raise ZhihuError("invalid_quota_response")
        matches = [item for item in data if isinstance(item, dict) and item.get("APIID") == API_ID]
        if len(matches) != 1:
            raise ZhihuError("search_quota_missing")
        item = matches[0]
        remaining = item.get("RemainingQuota")
        if not _integer(remaining):
            raise ZhihuError("search_quota_unknown")
        return {"mode": "quota", "provider": "zhihu_official_api", "api_id": API_ID,
                "remaining_quota": remaining,
                "total_quota": item.get("TotalQuota") if _integer(item.get("TotalQuota")) else None,
                "total_used": item.get("TotalUsed") if _integer(item.get("TotalUsed")) else None,
                "observation": proof, "quota_check_is_reservation": False}

    def search(self, query, count=5, days=60):
        if not isinstance(query, str) or not query.strip() or len(query) > 512:
            raise ZhihuError("invalid_query")
        if type(count) is not int or not 1 <= count <= 10:
            raise ZhihuError("invalid_count")
        if type(days) is not int or not 1 <= days <= 365:
            raise ZhihuError("invalid_days")
        now = self._now()
        since = max(0, now - days * 86400)
        quota = self.quota()
        if quota["remaining_quota"] <= 0:
            raise ZhihuError("search_quota_exhausted")
        data, proof = self._request(SEARCH_PATH, {
            "Query": query.strip(), "Count": count,
            "SortBy": "CreateTime:desc:(%s,%s)" % (since, now),
        })
        if (not isinstance(data, dict) or not isinstance(data.get("Items"), list)
                or len(data["Items"]) > count or data.get("HasMore") is not False):
            raise ZhihuError("invalid_search_response")
        excluded = {"missing_created_time": 0, "invalid_created_time": 0,
                    "outside_window": 0, "invalid_item": 0, "duplicate": 0}
        records, seen_ids, seen_urls = [], set(), set()
        for item in data["Items"]:
            if not isinstance(item, dict):
                excluded["invalid_item"] += 1
                continue
            created = item.get("CreateTime")
            if created is None:
                excluded["missing_created_time"] += 1
                continue
            if not _integer(created):
                excluded["invalid_created_time"] += 1
                continue
            if not since <= created <= now:
                excluded["outside_window"] += 1
                continue
            identifier = item.get("ContentID")
            if type(identifier) is int and identifier >= 0:
                identifier = str(identifier)
            elif isinstance(identifier, str) and identifier and len(identifier) <= 200:
                pass
            else:
                excluded["invalid_item"] += 1
                continue
            if any(not isinstance(item.get(key), str) or not item[key].strip()
                   for key in ("Title", "ContentType", "ContentText")):
                excluded["invalid_item"] += 1
                continue
            try:
                canonical = _public_url(item.get("Url"))
                created_at = _iso(created)
            except ZhihuError:
                excluded["invalid_item"] += 1
                continue
            identity = (item["ContentType"], identifier)
            if identity in seen_ids or canonical in seen_urls:
                excluded["duplicate"] += 1
                continue
            seen_ids.add(identity)
            seen_urls.add(canonical)
            edited = item.get("EditTime")
            record = {
                "content_id": identifier, "content_type": item["ContentType"],
                "title": item["Title"], "source_url": item["Url"], "canonical_url": canonical,
                "author_name": item.get("AuthorName") if isinstance(item.get("AuthorName"), str) else None,
                "create_time": created, "created_at": created_at,
                "edit_time": edited if _integer(edited) else None,
                "vote_up_count": item.get("VoteUpCount") if _integer(item.get("VoteUpCount")) else None,
                "comment_count": item.get("CommentCount") if _integer(item.get("CommentCount")) else None,
                "excerpt": item["ContentText"], "coverage": "excerpt",
                "content_scope": "official_search_summary", "original_fetched": False,
                "eligible_for_research": False,
            }
            records.append(record)
        records.sort(key=lambda item: (
            -(item["vote_up_count"] if item["vote_up_count"] is not None else -1),
            -(item["comment_count"] if item["comment_count"] is not None else -1),
            -item["create_time"], item["canonical_url"]))
        return {
            "mode": "discovery_only", "provider": "zhihu_official_api", "query": query.strip(),
            "window": {"since": _iso(since), "until": _iso(now), "days": days,
                       "basis": "CreateTime"},
            "requested_count": count, "returned_count": len(data["Items"]),
            "records": records, "excluded": excluded, "observation": proof,
            "search_hash_id": data.get("SearchHashId") if isinstance(data.get("SearchHashId"), str) else None,
            "search_complete": False, "has_more": False,
            "ranking_scope": "Vote and comment counts among returned in-window candidates only; not a platform-wide hot list.",
            "quota_before": quota, "quota_check_is_reservation": False,
            "paid_fallback_requested": False, "billing_guarantee": False,
            "model_calls": 0, "research_started": False, "files_written": False,
        }


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default includes raw argv, which could contain a pasted key.
        raise ZhihuError("invalid_arguments")


def main(argv=None):
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    quota = commands.add_parser("quota", help="Check search quota without running a search")
    search = commands.add_parser("search", help="Discover summaries; never fetch or research originals")
    for command in (quota, search):
        command.add_argument("--prompt-secret", action="store_true",
                             help="Prompt for access_secret for this invocation; do not store it")
    search.add_argument("--query", required=True)
    search.add_argument("--count", type=int, default=5)
    search.add_argument("--days", type=int, default=60,
                        help="Local lookback bound: 1–365 days (default: 60)")
    try:
        args = parser.parse_args(argv)
        if args.prompt_secret:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                secret = getpass.getpass("Zhihu access_secret (not saved): ")
        else:
            secret = os.environ.get("ZHIHU_ACCESS_SECRET")
        client = ZhihuClient(secret)
        result = (client.quota() if args.command == "quota"
                  else client.search(args.query, args.count, args.days))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ZhihuError as exc:
        import sys
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        import sys
        print(json.dumps({"error": "secret_input_cancelled"}), file=sys.stderr)
        return 2
    except getpass.GetPassWarning:
        import sys
        print(json.dumps({"error": "secret_input_requires_terminal"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
