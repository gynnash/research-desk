"""Official Zhihu client contract checks; no network, credentials or model calls."""

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import zhihu


NOW = int(datetime(2026, 10, 31, 12, tzinfo=timezone.utc).timestamp())
SECRET = "fictional-test-secret-not-a-real-key"


class Response:
    def __init__(self, payload, status=200, url=None):
        self.raw = json.dumps(payload, ensure_ascii=False).encode()
        self.status, self.url = status, url
        self.headers = {"Content-Type": "application/json; charset=utf-8",
                        "Content-Length": str(len(self.raw))}
        self.closed = False

    def read(self, limit):
        return self.raw[:limit]

    def close(self):
        self.closed = True

    def geturl(self):
        return self.url


class Transport:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def open(self, request, timeout):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("Unexpected request; no network transport is available")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if response.url is None:
            response.url = request.full_url
        return response


def quota(remaining=5):
    return Response({"Code": 0, "Data": [{"APIID": "zhihu_search", "APIName": "知乎搜索",
        "TotalQuota": 10, "TotalUsed": 10 - remaining, "RemainingQuota": remaining}]})


def item(identifier="1", votes=10, created=NOW - 100):
    return {"Title": "Fictional agent memory article", "ContentType": "answer",
        "ContentID": identifier, "ContentText": "A search summary, not the complete original.",
        "Url": "https://www.zhihu.com/question/100/answer/%s?utm_source=test&utm_medium=api&view=full" % identifier,
        "CommentCount": 2, "VoteUpCount": votes, "AuthorName": "Fixture Author",
        "EditTime": NOW - 10, "CreateTime": created}


def search_response(items):
    return Response({"Code": 0, "Data": {"HasMore": False,
        "SearchHashId": "fixture-search", "Items": items}})


class ZhihuTests(unittest.TestCase):
    def client(self, *responses):
        transport = Transport(*responses)
        return zhihu.ZhihuClient(SECRET, opener=transport, clock=lambda: NOW + 0.75), transport

    def test_fixed_endpoints_auth_headers_and_seconds_timestamp(self):
        client, transport = self.client(quota(), search_response([item()]))
        result = client.search("Agent Memory")
        self.assertEqual(len(transport.requests), 2)
        first, second = transport.requests
        self.assertEqual(urlsplit(first.full_url).netloc, "developer.zhihu.com")
        self.assertEqual(urlsplit(first.full_url).path, "/api/v1/quota")
        self.assertEqual(parse_qs(urlsplit(first.full_url).query), {"APIIDs": ["zhihu_search"]})
        self.assertEqual(urlsplit(second.full_url).path, "/api/v1/content/zhihu_search")
        parameters = parse_qs(urlsplit(second.full_url).query)
        self.assertEqual(parameters["Count"], ["5"])
        self.assertEqual(parameters["Query"], ["Agent Memory"])
        self.assertEqual(parameters["SortBy"], ["CreateTime:desc:(%s,%s)" % (NOW - 60 * 86400, NOW)])
        for request in transport.requests:
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertEqual(headers["authorization"], "Bearer " + SECRET)
            self.assertEqual(headers["x-request-timestamp"], str(NOW))
            self.assertEqual(headers["content-type"], "application/json")
            self.assertNotIn(SECRET, request.full_url)
        self.assertNotIn(SECRET, json.dumps(result))

    def test_precision_provenance_excerpt_only_and_bounded_ranking(self):
        identifier = 123456789012345678901234567890
        higher, lower = item(str(identifier), 40), item("2", 5)
        # JSON integer identifiers retain their exact decimal representation.
        higher["ContentID"] = identifier
        client, _ = self.client(quota(), search_response([lower, higher]))
        result = client.search("memory")
        self.assertEqual(result["mode"], "discovery_only")
        self.assertEqual(result["records"][0]["content_id"], str(identifier))
        self.assertIn("utm_source=test", result["records"][0]["source_url"])
        self.assertEqual(result["records"][0]["canonical_url"],
            "https://www.zhihu.com/question/100/answer/%s?view=full" % identifier)
        self.assertFalse(result["search_complete"])
        self.assertFalse(result["billing_guarantee"])
        self.assertFalse(result["quota_check_is_reservation"])
        self.assertEqual(result["model_calls"], 0)
        for record in result["records"]:
            self.assertEqual(record["coverage"], "excerpt")
            self.assertEqual(record["content_scope"], "official_search_summary")
            self.assertFalse(record["eligible_for_research"])
            self.assertFalse(record["original_fetched"])

    def test_missing_created_time_is_not_replaced_by_recent_edit_time(self):
        missing = item("1")
        del missing["CreateTime"]
        outside = item("2", created=NOW - 61 * 86400)
        invalid_url = item("3")
        invalid_url["Url"] = "https://other.example/article"
        client, _ = self.client(quota(), search_response([missing, outside, invalid_url]))
        result = client.search("memory")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["excluded"]["missing_created_time"], 1)
        self.assertEqual(result["excluded"]["outside_window"], 1)
        self.assertEqual(result["excluded"]["invalid_item"], 1)
        self.assertEqual(result["returned_count"], 3)

    def test_no_or_unknown_quota_never_requests_search(self):
        absent = quota()
        absent_data = json.loads(absent.raw)
        del absent_data["Data"][0]["RemainingQuota"]
        for response, expected in ((quota(0), "search_quota_exhausted"),
                                   (Response(absent_data), "search_quota_unknown")):
            client, transport = self.client(response)
            with self.assertRaisesRegex(zhihu.ZhihuError, expected):
                client.search("memory")
            self.assertEqual(len(transport.requests), 1)

    def test_redirect_and_api_errors_never_leak_remote_body_or_retry(self):
        failures = [
            HTTPError(zhihu.ORIGIN + zhihu.QUOTA_PATH, 302, "redirect " + SECRET,
                      {"Location": "https://other.example/?secret=" + SECRET}, io.BytesIO(SECRET.encode())),
            Response({"Code": 20001, "Message": "do not expose this upstream error"}),
            Response({"Code": 90001, "Message": SECRET}),
        ]
        for response in failures:
            client, transport = self.client(response)
            with self.assertRaises(zhihu.ZhihuError) as context:
                client.quota()
            self.assertNotIn(SECRET, str(context.exception))
            self.assertNotIn("upstream error", str(context.exception))
            self.assertEqual(len(transport.requests), 1)
        self.assertIsNone(zhihu._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example"))

    def test_missing_key_and_invalid_arguments_use_no_network_or_secret_echo(self):
        with mock.patch.object(zhihu, "build_opener") as build:
            with self.assertRaisesRegex(zhihu.ZhihuError, "missing_access_secret"):
                zhihu.ZhihuClient(None)
            build.assert_not_called()
        with mock.patch.dict(zhihu.os.environ, {}, clear=True), \
             mock.patch.object(zhihu, "build_opener") as build, \
             mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(zhihu.main(["quota"]), 2)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(json.loads(err.getvalue())["error"], "missing_access_secret")
            build.assert_not_called()
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertEqual(zhihu.main(["quota", "--secret", SECRET]), 2)
            self.assertEqual(json.loads(err.getvalue())["error"], "invalid_arguments")
            self.assertNotIn(SECRET, err.getvalue())

    def test_invalid_limits_stop_before_quota_and_response_bound_is_enforced(self):
        client, transport = self.client()
        for count, days in ((11, 60), (True, 60), (5, 0)):
            with self.assertRaises(zhihu.ZhihuError):
                client.search("memory", count, days)
        self.assertEqual(transport.requests, [])
        response = quota()
        response.headers["Content-Length"] = "2000001"
        client, transport = self.client(response)
        with self.assertRaisesRegex(zhihu.ZhihuError, "response_too_large"):
            client.quota()
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
