"""Offline security/transport checks: no real login, network, or model usage."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import researchdesk_membership as membership

try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    HAVE_JWT = True
except ImportError:
    HAVE_JWT = False


class FakeOpener:
    def __init__(self):
        self.calls = []
        self.replies = []

    def add(self, value):
        self.replies.append(value)

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if not self.replies:
            raise AssertionError("Unexpected network request")
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, dict):
            value = json.dumps(value).encode()
        return io.BytesIO(value)


class MembershipTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="researchdesk-auth-")
        self.base = Path(self.temporary.name).resolve()
        self.vault = self.base / "vault"
        self.vault.mkdir()
        self.opener = FakeOpener()
        self.client = membership.MembershipClient(self.base / "private", self.vault,
                                                opener=self.opener)
        self.registration = "oaiapp_researchdesk_test"

    def tearDown(self):
        self.temporary.cleanup()

    def record(self, **changes):
        value = {"issuer": membership.ISSUER, "client_id": self.registration,
                 "subject": "private-subject", "identity_verified": True,
                 "access_token": "private-access-token", "refresh_token": "private-refresh-token",
                 "id_token": "private-id-token", "expires_at": time.time() + 3600,
                 "ext_agent_host_id": "urn:uuid:private-host", "scopes": [membership.DIRECT_SCOPE]}
        value.update(changes)
        with self.client._lock():
            self.client._write("credentials.json", value)
        return value

    def stream(self, *events):
        self.opener.add(b"".join(b"data: " + json.dumps(event).encode() + b"\n\n"
                                  for event in events))

    def completed(self, **changes):
        value = {"id": "resp_test", "model": "model-research", "status": "completed",
                 "output": [{"type": "message", "content": [{"type": "output_text", "text": "done"}]}],
                 "usage": {"input_tokens": 12, "output_tokens": 2, "total_tokens": 14}}
        value.update(changes)
        return {"type": "response.completed", "response": value}

    def ready(self):
        self.record()
        self.client._catalog = [{"slug": "model-research", "display_name": "Research"}]

    def test_profile_cannot_be_inside_vault(self):
        with self.assertRaisesRegex(membership.MembershipError, "credentials_inside_vault"):
            membership.MembershipClient(self.vault / "hidden", self.vault)

    def test_profile_cannot_follow_symlink(self):
        (self.base / "link").symlink_to(self.base)
        with self.assertRaisesRegex(membership.MembershipError, "credential_path_symlink"):
            membership.MembershipClient(self.base / "link" / "child", self.vault)

    def test_owner_only_files_and_directory(self):
        self.record()
        self.assertEqual(self.client.profile.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.client.profile / "credentials.json").stat().st_mode & 0o777, 0o600)
        (self.client.profile / "credentials.json").chmod(0o644)
        with self.assertRaisesRegex(membership.MembershipError, "credential_file_permissions"):
            self.client.status()

    def test_existing_wide_directory_is_rejected(self):
        self.client.profile.mkdir(mode=0o755)
        with self.assertRaisesRegex(membership.MembershipError, "credential_directory_permissions"):
            self.client.status()

    def test_missing_status_does_not_create_credentials(self):
        self.assertFalse(self.client.status()["authenticated"])
        self.assertFalse(self.client.profile.exists())

    def test_status_is_redacted(self):
        self.record()
        status = self.client.status()
        self.assertTrue(status["plan_permission"])
        text = json.dumps(status)
        for private in ("private-subject", "private-access-token", "private-refresh-token", "private-id-token"):
            self.assertNotIn(private, text)
        self.assertEqual(len(status["account_fingerprint"]), 16)

    def test_fresh_pkce_and_stable_host(self):
        with self.client._lock():
            first, first_url = self.client._prepare_login("http://127.0.0.1:1234/auth/callback")
            second, _ = self.client._prepare_login("http://127.0.0.1:2345/auth/callback")
        for name in ("nonce", "state", "verifier"):
            self.assertNotEqual(first[name], second[name])
        self.assertEqual(first["host_id"], second["host_id"])
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(first_url).query)
        expected = base64.urlsafe_b64encode(hashlib.sha256(first["verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(values["code_challenge"], [expected])
        self.assertEqual(values["client_id"], ["dynamic_agent_client"])
        self.assertEqual(values["agent_name_hint"], ["ResearchDesk"])
        self.assertNotIn("id_token_hint", values)

    def pending(self):
        with self.client._lock():
            pending, _ = self.client._prepare_login("http://127.0.0.1:1234/auth/callback")
        return pending

    def callback(self, pending, **values):
        query = {"state": pending["state"], "code": "private-code", "client_id": self.registration}
        query.update(values)
        return urllib.parse.urlencode(query)

    def test_callback_rejects_state_and_reuse(self):
        pending = self.pending()
        with self.assertRaisesRegex(membership.MembershipError, "authorization_state_mismatch"):
            self.client._finish_login(pending, self.callback(pending, state="other"))
        with self.assertRaisesRegex(membership.MembershipError, "expired_authorization_attempt"):
            self.client._finish_login(pending, self.callback(pending))
        self.assertEqual(self.opener.calls, [])

    def test_callback_rejects_duplicate_parameters(self):
        pending = self.pending()
        with self.assertRaisesRegex(membership.MembershipError, "duplicate_callback_parameter"):
            self.client._finish_login(pending, self.callback(pending) + "&state=extra")

    def test_expired_callback_never_exchanges(self):
        pending = self.pending()
        pending["expires_at"] = 0
        with self.assertRaisesRegex(membership.MembershipError, "expired_authorization_attempt"):
            self.client._finish_login(pending, self.callback(pending))
        self.assertFalse(self.opener.calls)

    def test_invalid_grant_retains_issued_registration(self):
        pending = self.pending()
        self.opener.add(urllib.error.HTTPError(membership.TOKEN, 400, "bad", {},
                                              io.BytesIO(b'{"error":"invalid_grant"}')))
        with self.assertRaisesRegex(membership.MembershipError, "invalid_grant"):
            self.client._finish_login(pending, self.callback(pending))
        with self.client._lock():
            self.assertEqual(self.client._read("registration.json")["client_id"], self.registration)
            self.assertIsNone(self.client._read("credentials.json"))

    def test_callback_requires_issued_id(self):
        pending = self.pending()
        with self.assertRaisesRegex(membership.MembershipError, "missing_issued_client_id"):
            self.client._finish_login(pending, self.callback(pending, client_id="dynamic_agent_client"))

    def test_returning_callback_cannot_replace_client(self):
        pending = self.pending()
        pending["client_id"] = "oaiapp_selected"
        with self.assertRaisesRegex(membership.MembershipError, "registration_client_mismatch"):
            self.client._finish_login(pending, self.callback(pending))

    def test_denied_callback_never_exchanges(self):
        pending = self.pending()
        with self.assertRaisesRegex(membership.MembershipError, "access_denied"):
            self.client._finish_login(pending, self.callback(pending, error="access_denied"))
        self.assertFalse(self.opener.calls)

    def test_missing_scope_blocks_even_with_identity(self):
        self.record(scopes=["openid"])
        with self.assertRaisesRegex(membership.MembershipError, "plan_permission_missing"):
            self.client.models()
        self.assertFalse(self.opener.calls)

    def test_model_catalog_only_visible_and_order_preserved(self):
        self.record()
        self.opener.add({"models": [{"slug": "b", "display_name": "B", "visibility": "list"},
                                   {"slug": "hidden", "display_name": "H", "visibility": "hide"},
                                   {"slug": "a", "display_name": "A", "visibility": "list"}]})
        self.assertEqual([item["slug"] for item in self.client.models()], ["b", "a"])
        request = self.opener.calls[0][0]
        self.assertEqual(request.full_url, membership.RESOURCE + "/models")
        self.assertEqual(request.headers["Authorization"], "Bearer private-access-token")

    def test_invalid_catalog_rejected(self):
        self.record()
        self.opener.add({"data": []})
        with self.assertRaisesRegex(membership.MembershipError, "invalid_model_catalog"):
            self.client.models()

    def test_refresh_rotates_atomically_and_omits_scope(self):
        self.record(expires_at=0, scopes=[membership.DIRECT_SCOPE, "offline_access"])
        self.opener.add({"access_token": "replacement-access", "refresh_token": "replacement-refresh",
                         "token_type": "Bearer", "expires_in": 3600})
        self.assertEqual(self.client._access_token(), "replacement-access")
        request = self.opener.calls[0][0]
        form = urllib.parse.parse_qs(request.data.decode())
        self.assertNotIn("scope", form)
        self.assertEqual(form["client_id"], [self.registration])
        with self.client._lock():
            stored = self.client._read("credentials.json")
        self.assertEqual(stored["refresh_token"], "replacement-refresh")

    def test_terminal_refresh_failure_clears_tokens_but_keeps_registration(self):
        self.record(expires_at=0)
        error = urllib.error.HTTPError(membership.TOKEN, 400, "bad", {},
                                       io.BytesIO(b'{"error":"invalid_grant"}'))
        self.opener.add(error)
        with self.assertRaisesRegex(membership.MembershipError, "login_required"):
            self.client._access_token()
        with self.client._lock():
            self.assertNotIn("access_token", self.client._read("credentials.json"))
            self.assertEqual(self.client._read("registration.json")["client_id"], self.registration)
        self.assertEqual(len(self.opener.calls), 1)
        with self.assertRaisesRegex(membership.MembershipError, "login_required"):
            self.client._access_token()
        self.assertEqual(len(self.opener.calls), 1)

    def test_temporary_refresh_failure_preserves_tokens_without_retry(self):
        self.record(expires_at=0)
        self.opener.add(urllib.error.HTTPError(membership.TOKEN, 503, "temporarily unavailable", {},
                                              io.BytesIO(b'{"error":"server_error"}')))
        with self.assertRaisesRegex(membership.MembershipError, "server_error"):
            self.client._access_token()
        with self.client._lock():
            self.assertEqual(self.client._read("credentials.json")["access_token"], "private-access-token")
        self.assertEqual(len(self.opener.calls), 1)

    def test_no_redirect_or_error_body_disclosure(self):
        error = urllib.error.HTTPError(membership.RESOURCE + "/models", 307, "secret location", {},
                                       io.BytesIO(b'{"error":"private-access-token"}'))
        self.opener.add(error)
        with self.assertRaisesRegex(membership.MembershipError, "redirect_refused") as context:
            self.client._json(membership.RESOURCE + "/models", bearer="private-access-token")
        self.assertNotIn("private-access-token", str(context.exception))
        self.assertIsNone(membership.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test"))

    def test_inference_uses_official_payload_and_returns_usage(self):
        self.ready()
        self.stream({"type": "response.output_text.delta", "delta": "done"}, self.completed())
        result = self.client.infer("model-research", "Rules", "Evidence")
        self.assertEqual(result["text"], "done")
        self.assertEqual(result["model"], "model-research")
        self.assertEqual(result["usage"]["total_tokens"], 14)
        request = self.opener.calls[0][0]
        payload = json.loads(request.data)
        self.assertEqual(set(payload), {"model", "instructions", "input", "store", "stream"})
        self.assertFalse(payload["store"])
        self.assertTrue(payload["stream"])
        self.assertEqual(request.full_url, membership.RESOURCE + "/responses")

    def test_delta_alone_is_not_success(self):
        self.ready()
        self.stream({"type": "response.output_text.delta", "delta": "partial"})
        with self.assertRaisesRegex(membership.MembershipError, "stream_incomplete"):
            self.client.infer("model-research", "Rules", "Evidence")
        self.assertEqual(len(self.opener.calls), 1)

    def test_late_failure_after_delta_is_failure(self):
        self.ready()
        self.stream({"type": "response.output_text.delta", "delta": "partial"},
                    {"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}})
        with self.assertRaisesRegex(membership.MembershipError, "subscription_sharing_usage_limit_exceeded"):
            self.client.infer("model-research", "Rules", "Evidence")

    def test_incomplete_and_missing_model_fail_closed(self):
        self.ready()
        self.stream({"type": "response.incomplete", "response": None})
        with self.assertRaisesRegex(membership.MembershipError, "inference_incomplete"):
            self.client.infer("model-research", "Rules", "Evidence")
        self.stream(self.completed(model=None))
        with self.assertRaisesRegex(membership.MembershipError, "invalid_completed_response"):
            self.client.infer("model-research", "Rules", "Evidence")

    def test_actual_model_mismatch_fails(self):
        self.ready()
        self.stream(self.completed(model="other-model"))
        with self.assertRaisesRegex(membership.MembershipError, "actual_model_mismatch"):
            self.client.infer("model-research", "Rules", "Evidence")

    def test_output_cap_interrupts_and_never_retries(self):
        self.ready()
        self.stream({"type": "response.output_text.delta", "delta": "a" * 20}, self.completed())
        with self.assertRaisesRegex(membership.MembershipError, "output_limit_interrupted"):
            self.client.infer("model-research", "Rules", "Evidence", max_output_chars=10)
        self.assertEqual(len(self.opener.calls), 1)

    def test_missing_usage_stays_unknown(self):
        self.ready()
        self.stream(self.completed(usage=None))
        self.assertIsNone(self.client.infer("model-research", "Rules", "Evidence")["usage"])

    def test_malformed_completed_output_fails_closed(self):
        self.ready()
        for output in (None, "bad", [{"type": "message", "content": None}]):
            self.stream(self.completed(output=output))
            with self.assertRaisesRegex(membership.MembershipError, "invalid_completed_response"):
                self.client.infer("model-research", "Rules", "Evidence")

    def test_unavailable_model_never_starts_inference(self):
        self.ready()
        with self.assertRaisesRegex(membership.MembershipError, "model_not_available"):
            self.client.infer("not-selected", "Rules", "Evidence")
        self.assertFalse(self.opener.calls)


class ManualLoginTests(unittest.TestCase):
    setUp = MembershipTests.setUp
    tearDown = MembershipTests.tearDown

    def exercise(self, interruption=None, timeout=600, error=None):
        self.client._discover = mock.Mock(return_value={})
        self.client._finish_login = mock.Mock(return_value={"authenticated": True}, side_effect=error)
        self.announcements = []
        test = self

        class Server:
            server_port = 12345

            def __init__(self, address, handler):
                test.assertEqual(address, ("127.0.0.1", 0))
                self.handler = handler

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def handle_request(self):
                path = test.client.profile / "authorization.json"
                value = json.loads(path.read_text())
                test.assertEqual(set(value), {"url", "expires_at"})
                test.assertEqual(path.stat().st_mode & 0o777, 0o600)
                params = urllib.parse.parse_qs(urllib.parse.urlsplit(value["url"]).query)
                test.assertNotIn("code_verifier", params)
                test.assertNotIn("id_token_hint", params)
                test.assertEqual(params["code_challenge_method"], ["S256"])
                if interruption:
                    raise interruption
                handler = object.__new__(self.handler)
                handler.path = "/auth/callback?state=" + params["state"][0]
                handler.send_response = mock.Mock()
                handler.send_header = mock.Mock()
                handler.end_headers = mock.Mock()
                handler.wfile = io.BytesIO()
                handler.do_GET()

        with mock.patch.object(membership.http.server, "HTTPServer", Server), \
                mock.patch.object(membership.webbrowser, "open") as browser:
            try:
                return self.client.login(open_browser=False, timeout_seconds=timeout,
                                         announce=self.announcements.append)
            finally:
                browser.assert_not_called()
                self.assertFalse((self.client.profile / "authorization.json").exists())

    def test_manual_login_waits_without_opening_system_browser(self):
        self.assertTrue(self.exercise()["authenticated"])
        announcement = self.announcements[0]
        self.assertFalse(announcement["browser_opened"])
        self.assertEqual(announcement["authorization_request_file"],
                         str(self.client.profile / "authorization.json"))
        self.assertNotIn("https://auth.openai.com", json.dumps(announcement))
        self.client._finish_login.assert_called_once()

    def test_manual_request_removed_after_interruption(self):
        with self.assertRaises(KeyboardInterrupt):
            self.exercise(interruption=KeyboardInterrupt())

    def test_manual_request_removed_after_timeout(self):
        with self.assertRaisesRegex(membership.MembershipError, "authorization_timeout"):
            self.exercise(timeout=0)

    def test_manual_request_removed_after_authorization_failure(self):
        with self.assertRaisesRegex(membership.MembershipError, "access_denied"):
            self.exercise(error=membership.MembershipError("access_denied"))


@unittest.skipUnless(HAVE_JWT, "Install workflows/requirements-membership.txt for signature checks")
class IdentityTests(unittest.TestCase):
    setUp = MembershipTests.setUp
    tearDown = MembershipTests.tearDown
    pending = MembershipTests.pending
    callback = MembershipTests.callback

    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.private_key.public_key()))
        cls.public_jwk["kid"] = "test-key"

    def signed(self, **changes):
        now = int(time.time())
        claims = {"sub": "verified-subject", "iss": membership.ISSUER,
                  "aud": self.registration, "iat": now, "exp": now + 300, "nonce": "expected-nonce"}
        claims.update(changes)
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"})

    def verification_ready(self):
        self.client._discovery = {"id_token_signing_alg_values_supported": ["RS256"]}
        self.client._jwks = {"keys": [self.public_jwk]}

    def test_verified_signature_identity(self):
        self.verification_ready()
        identity = self.client._identity(self.signed(), self.registration, "expected-nonce")
        self.assertEqual(identity["sub"], "verified-subject")

    def test_invalid_claims_are_rejected(self):
        for changes in ({"aud": "wrong"}, {"iss": "https://evil.test"}, {"exp": 0},
                        {"nonce": "wrong"}, {"sub": ""}, {"iat": int(time.time()) + 1000}):
            with self.subTest(changes=changes):
                self.verification_ready()
                with self.assertRaises(membership.MembershipError):
                    self.client._identity(self.signed(**changes), self.registration, "expected-nonce")

    def test_tampered_signature_is_rejected(self):
        self.verification_ready()
        value = self.signed().split(".")
        value[1] = base64.urlsafe_b64encode(json.dumps({"sub": "evil"}).encode()).rstrip(b"=").decode()
        with self.assertRaisesRegex(membership.MembershipError, "invalid_id_token"):
            self.client._identity(".".join(value), self.registration, "expected-nonce")

    def test_unsigned_or_symmetric_token_is_rejected(self):
        self.verification_ready()
        token = jwt.encode({"sub": "evil"}, "x" * 32, algorithm="HS256", headers={"kid": "test-key"})
        with self.assertRaisesRegex(membership.MembershipError, "invalid_id_token"):
            self.client._identity(token, self.registration, "expected-nonce")

    def test_duplicate_key_ids_are_rejected(self):
        self.verification_ready()
        self.client._jwks["keys"].append(self.public_jwk)
        with self.assertRaisesRegex(membership.MembershipError, "unknown_signing_key"):
            self.client._identity(self.signed(), self.registration, "expected-nonce")

    def test_successful_callback_uses_issued_client_and_scope(self):
        pending = self.pending()
        self.verification_ready()
        self.opener.add({"id_token": self.signed(nonce=pending["nonce"]),
                         "access_token": "new-secret", "token_type": "Bearer", "expires_in": 3600,
                         "scope": "openid " + membership.DIRECT_SCOPE})
        result = self.client._finish_login(pending, self.callback(pending))
        self.assertTrue(result["plan_permission"])
        form = urllib.parse.parse_qs(self.opener.calls[0][0].data.decode())
        self.assertEqual(form["client_id"], [self.registration])
        self.assertEqual(form["resource"], [membership.RESOURCE])
        self.assertEqual(form["code_verifier"], [pending["verifier"]])
        self.assertEqual(form["redirect_uri"], [pending["redirect_uri"]])

    def test_returning_identity_mismatch_preserves_credentials(self):
        MembershipTests.record(self)
        pending = self.pending()
        pending["subject"] = "private-subject"
        pending["client_id"] = self.registration
        self.verification_ready()
        self.opener.add({"id_token": self.signed(nonce=pending["nonce"]),
                         "access_token": "replacement-secret", "token_type": "Bearer", "expires_in": 3600,
                         "scope": membership.DIRECT_SCOPE})
        with self.assertRaisesRegex(membership.MembershipError, "account_identity_mismatch"):
            self.client._finish_login(pending, self.callback(pending))
        with self.client._lock():
            self.assertEqual(self.client._read("credentials.json")["access_token"], "private-access-token")


if __name__ == "__main__":
    unittest.main()
