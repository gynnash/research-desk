#!/usr/bin/env python3
"""Official, local Sign in with ChatGPT public client; no imported login state.

Credentials belong outside the repository/Obsidian vault. Only ``login`` opens
the system browser. Model inference has no retries and succeeds only on the
Responses stream's completed event. See workflows/local-membership-analysis.md.
"""
import argparse
import base64
import contextlib
import fcntl
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser


ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
JWKS = ISSUER + "/.well-known/jwks.json"
DISCOVERY = ISSUER + "/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
DIRECT_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke " + DIRECT_SCOPE
DEFAULT_PROFILE = Path.home() / "Library/Application Support/ResearchDesk/chatgpt"
SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
CLIENT_ID = re.compile(r"^oaiapp_[A-Za-z0-9_-]{1,200}$")
_CALLBACK_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_CLOSE_SCRIPT = ("setTimeout(() => window.close(), 3000);"
                 "history.replaceState(null, '', '/auth/callback');")
_CLOSE_SCRIPT_HASH = base64.b64encode(hashlib.sha256(_CLOSE_SCRIPT.encode("utf-8")).digest()).decode("ascii")
_WIZARD_SUCCESS_HTML = (
    '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<title>ChatGPT 授权成功</title></head><body><h1>ChatGPT 授权成功</h1>'
    '<p>此页面将在 3 秒后关闭。如果页面仍然打开，请手动关闭并返回 ResearchDesk 向导。</p>'
    f'<script>{_CLOSE_SCRIPT}</script></body></html>'
).encode("utf-8")


class MembershipError(RuntimeError):
    """Safe-to-display machine code; never includes a response body or token."""

    def __init__(self, code, http_status=None, request_id=None, body_shape=None):
        self.code = code if SAFE_CODE.fullmatch(str(code)) else "membership_error"
        self.http_status = http_status
        self.request_id = (request_id if isinstance(request_id, str)
                           and re.fullmatch(r"[A-Za-z0-9_-]{1,160}", request_id) else None)
        self.body_shape = body_shape if body_shape in ("error", "detail", "unknown") else None
        super().__init__(self.code + (" (HTTP %s)" % http_status if http_status else ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _error_code(value, default):
    if isinstance(value, dict):
        value = value.get("code") or value.get("type")
    return value if isinstance(value, str) and SAFE_CODE.fullmatch(value) else default


class MembershipClient:
    def __init__(self, profile_dir=DEFAULT_PROFILE, root=None, opener=None, clock=None):
        self.root = Path(root or Path(__file__).resolve().parents[1]).resolve()
        self.profile = Path(profile_dir).expanduser().absolute()
        # Check before resolve: silently following a symlink would hide the risk.
        for entry in (self.profile,) + tuple(self.profile.parents):
            if entry.is_symlink():
                raise MembershipError("credential_path_symlink")
        try:
            self.profile.resolve().relative_to(self.root)
        except ValueError:
            pass
        else:
            raise MembershipError("credentials_inside_vault")
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.clock = clock or time.time
        self._catalog = None
        self._discovery = None
        self._jwks = None

    def _ensure_profile(self):
        self.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.profile.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise MembershipError("credential_directory_permissions")

    @contextlib.contextmanager
    def _lock(self):
        self._ensure_profile()
        descriptor = os.open(str(self.profile / ".lock"),
                             os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise MembershipError("credential_file_permissions")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)

    def _read(self, name, required=False):
        path = self.profile / name
        try:
            descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            if required:
                raise MembershipError("login_required") from None
            return None
        except OSError:
            raise MembershipError("credential_file_unsafe") from None
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 65536):
                raise MembershipError("credential_file_permissions")
            try:
                value = json.loads(handle.read())
            except (ValueError, UnicodeError):
                raise MembershipError("credential_file_invalid") from None
        if not isinstance(value, dict):
            raise MembershipError("credential_file_invalid")
        return value

    def _write(self, name, value):
        # Never follow an existing target, including a malicious dangling link.
        path = self.profile / name
        if path.is_symlink():
            raise MembershipError("credential_path_symlink")
        temporary = self.profile / (".write-" + secrets.token_hex(16))
        descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(_json_bytes(value))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary), str(path))
            directory = os.open(str(self.profile), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _open(self, url, data=None, bearer=None, timeout=30, content_type=None, extra_headers=None):
        # No caller-supplied base URL and no credential-bearing redirects.
        allowed = {DISCOVERY, JWKS, TOKEN, RESOURCE + "/models", RESOURCE + "/responses"}
        if url not in allowed:
            raise MembershipError("endpoint_not_allowed")
        headers = {"User-Agent": "ResearchDesk/0.1", "Accept": "application/json"}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        if content_type:
            headers["Content-Type"] = content_type
        if url.endswith("/responses"):
            headers["Accept"] = "text/event-stream"
        for key, value in (extra_headers or {}).items():
            if (url != RESOURCE + "/responses" or key.lower() not in {"originator", "user-agent"}
                    or not isinstance(value, str) or len(value) > 1024
                    or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise MembershipError("unsafe_forward_header")
            headers[{"originator": "Originator", "user-agent": "User-Agent"}[key.lower()]] = value
        try:
            return self.opener.open(urllib.request.Request(url, data=data, headers=headers),
                                    timeout=timeout)
        except urllib.error.HTTPError as exc:
            code = "redirect_refused" if 300 <= exc.code < 400 else "http_error"
            shape = "unknown"
            request_id = exc.headers.get("x-request-id") if exc.headers else None
            try:
                body = json.loads(exc.read(4096))
                if isinstance(body, dict):
                    shape = "error" if "error" in body else "detail" if "detail" in body else "unknown"
                if not 300 <= exc.code < 400:
                    code = _error_code(body.get("error"), code)
            except (ValueError, UnicodeError, AttributeError, OSError):
                pass
            finally:
                exc.close()
            raise MembershipError(code, exc.code, request_id, shape) from None
        except (OSError, urllib.error.URLError, ValueError):
            raise MembershipError("network_error") from None

    def forward_responses(self, payload, headers=None):
        """Forward one SDK request using this app's own SIWC authorization.

        The caller reserves its request budget before calling. No inference
        retry, configurable upstream URL, token return, or API-key fallback.
        """
        if not isinstance(payload, dict) or payload.get("store") is not False or payload.get("stream") is not True:
            raise MembershipError("invalid_forward_request")
        return self._open(RESOURCE + "/responses", _json_bytes(payload), self._access_token(),
                          timeout=240, content_type="application/json", extra_headers=headers)

    def _json(self, url, data=None, bearer=None, form=False):
        if data is None:
            encoded, content_type = None, None
        elif form:
            encoded = urllib.parse.urlencode(data).encode("ascii")
            content_type = "application/x-www-form-urlencoded"
        else:
            encoded, content_type = _json_bytes(data), "application/json"
        try:
            with self._open(url, encoded, bearer, content_type=content_type) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except (OSError, urllib.error.URLError):
            raise MembershipError("network_error") from None
        if len(raw) > 2 * 1024 * 1024:
            raise MembershipError("response_too_large")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise MembershipError("invalid_json_response") from None
        if not isinstance(result, dict):
            raise MembershipError("invalid_json_response")
        return result

    def _discover(self):
        if self._discovery is None:
            result = self._json(DISCOVERY)
            for key, expected in (("issuer", ISSUER), ("authorization_endpoint", AUTHORIZE),
                                  ("token_endpoint", TOKEN), ("jwks_uri", JWKS)):
                if result.get(key) != expected:
                    raise MembershipError("discovery_endpoint_mismatch")
            self._discovery = result
        return self._discovery

    def _identity(self, token, client_id, nonce=None):
        try:
            import jwt
        except ImportError:
            raise MembershipError("install_membership_requirements") from None
        discovery = self._discover()
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            allowed = {"RS256", "ES256", "PS256"}
            advertised = discovery.get("id_token_signing_alg_values_supported")
            if advertised:
                allowed.intersection_update(advertised)
            if algorithm not in allowed or not isinstance(header.get("kid"), str):
                raise MembershipError("invalid_id_token")
            for attempt in range(2):
                if self._jwks is None or attempt:
                    self._jwks = self._json(JWKS)
                keys = self._jwks.get("keys", [])
                if not isinstance(keys, list) or any(not isinstance(key, dict) for key in keys):
                    raise MembershipError("invalid_signing_keys")
                matches = [key for key in keys if key.get("kid") == header["kid"]]
                if matches:
                    break
            if len(matches) != 1:
                raise MembershipError("unknown_signing_key")
            key = jwt.PyJWK.from_dict(matches[0], algorithm=algorithm).key
            identity = jwt.decode(token, key, algorithms=[algorithm], issuer=ISSUER,
                                  audience=client_id, leeway=5,
                                  options={"require": ["sub", "exp", "iat", "iss", "aud"]})
            if not isinstance(identity.get("sub"), str) or not identity["sub"]:
                raise MembershipError("invalid_id_token")
            if nonce is not None and (not isinstance(identity.get("nonce"), str)
                                      or not secrets.compare_digest(identity["nonce"], nonce)):
                raise MembershipError("id_token_nonce_mismatch")
            return identity
        except MembershipError:
            raise
        except (ValueError, TypeError, KeyError, jwt.PyJWTError):
            raise MembershipError("invalid_id_token") from None

    def _token_record(self, tokens, client_id, identity, host_id, previous=None):
        if (not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]
                or str(tokens.get("token_type", "")).lower() != "bearer"):
            raise MembershipError("invalid_token_response")
        expiry = tokens.get("expires_in")
        if type(expiry) not in (int, float) or not 0 < expiry <= 86400:
            raise MembershipError("invalid_token_expiry")
        scope = tokens.get("scope")
        if not isinstance(scope, str):
            if previous is None:
                raise MembershipError("missing_granted_scopes")
            scope = " ".join(previous["scopes"])
        scopes = scope.split()
        refresh = tokens.get("refresh_token")
        if "offline_access" in scopes and (not isinstance(refresh, str) or not refresh):
            raise MembershipError("missing_refresh_token")
        record = {"issuer": ISSUER, "subject": identity["sub"], "client_id": client_id,
                  "ext_agent_host_id": host_id, "id_token": tokens.get("id_token")
                  or (previous or {}).get("id_token"), "access_token": tokens["access_token"],
                  "refresh_token": refresh, "token_type": "Bearer", "expires_in": expiry,
                  "expires_at": self.clock() + expiry, "saved_at": self.clock(),
                  "scopes": sorted(set(scopes)), "identity_verified": True}
        # Account hints stay in protected storage; they never appear in status/receipts.
        if isinstance(identity.get("email"), str):
            record["email"] = identity["email"]
        elif previous and "email" in previous:
            record["email"] = previous["email"]
        return record

    def status(self):
        if not self.profile.exists():
            return {"authenticated": False, "plan_permission": False, "reason": "login_required"}
        with self._lock():
            record = self._read("credentials.json")
        if not record:
            return {"authenticated": False, "plan_permission": False, "reason": "login_required"}
        fingerprint = _hash("|".join(str(record.get(key, ""))
                                     for key in ("issuer", "client_id", "subject")))[:16]
        return {"authenticated": record.get("identity_verified") is True,
                "plan_permission": DIRECT_SCOPE in record.get("scopes", []),
                "account_fingerprint": fingerprint,
                "access_token_expired": record.get("expires_at", 0) <= self.clock(),
                "renewable": bool(record.get("refresh_token")),
                "authorization": "official_chatgpt_oauth",
                "billing_fallback": False}

    def _access_token(self):
        with self._lock():
            record = self._read("credentials.json", required=True)
            if record.get("identity_verified") is not True:
                raise MembershipError("login_required")
            if DIRECT_SCOPE not in record.get("scopes", []):
                raise MembershipError("plan_permission_missing")
            if record.get("expires_at", 0) <= self.clock() + 60:
                if not record.get("refresh_token"):
                    raise MembershipError("login_required")
                try:
                    tokens = self._json(TOKEN, {"grant_type": "refresh_token",
                                               "client_id": record["client_id"],
                                               "refresh_token": record["refresh_token"],
                                               "resource": RESOURCE}, form=True)
                except MembershipError as exc:
                    unusable = {"invalid_grant", "invalid_refresh_token", "token_expired",
                                "refresh_token_expired", "refresh_token_invalidated",
                                "refresh_token_reused"}
                    if exc.code not in unusable:
                        raise
                    retained = {key: record[key] for key in (
                        "issuer", "subject", "client_id", "ext_agent_host_id")}
                    retained.update({"identity_verified": False, "expires_at": 0, "scopes": []})
                    self._write("credentials.json", retained)
                    self._write("registration.json", {"client_id": record["client_id"],
                                                       "subject": record["subject"]})
                    raise MembershipError("login_required", exc.http_status,
                                          exc.request_id, exc.body_shape) from None
                identity = {"sub": record["subject"]}
                if tokens.get("id_token"):
                    identity = self._identity(tokens["id_token"], record["client_id"])
                    if identity["sub"] != record["subject"]:
                        raise MembershipError("account_identity_mismatch")
                replacement = self._token_record(tokens, record["client_id"], identity,
                                                 record["ext_agent_host_id"], record)
                self._write("credentials.json", replacement)
                record = replacement
                if DIRECT_SCOPE not in record["scopes"]:
                    raise MembershipError("plan_permission_missing")
            return record["access_token"]

    def _prepare_login(self, redirect_uri):
        host = self._read("host.json")
        if host is None:
            host = {"ext_agent_host_id": "urn:uuid:" + str(uuid.uuid4())}
            self._write("host.json", host)
        registration = self._read("registration.json") or {}
        selected = registration.get("client_id")
        if selected and not CLIENT_ID.fullmatch(selected):
            raise MembershipError("invalid_saved_registration")
        pending = {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32),
                   "verifier": secrets.token_urlsafe(64), "redirect_uri": redirect_uri,
                   "client_id": selected, "subject": registration.get("subject"),
                   "host_id": host["ext_agent_host_id"], "expires_at": self.clock() + 600}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(
            pending["verifier"].encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        params = {"client_id": selected or "dynamic_agent_client", "response_type": "code",
                  "redirect_uri": redirect_uri, "scope": SCOPES, "resource": RESOURCE,
                  "state": pending["state"], "nonce": pending["nonce"],
                  "code_challenge_method": "S256", "code_challenge": challenge,
                  "ext_agent_host_id": pending["host_id"]}
        if not selected:
            params["agent_name_hint"] = "ResearchDesk"
        # No id_token_hint in a URL: the account selector is safer for CLI diagnostics.
        return pending, AUTHORIZE + "?" + urllib.parse.urlencode(params)

    def _finish_login(self, pending, query):
        if pending.get("used") or self.clock() > pending["expires_at"]:
            raise MembershipError("expired_authorization_attempt")
        pending["used"] = True
        try:
            values = urllib.parse.parse_qs(query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise MembershipError("invalid_callback") from None
        if any(len(value) != 1 for value in values.values()):
            raise MembershipError("duplicate_callback_parameter")
        value = lambda key: values.get(key, [None])[0]
        state = value("state")
        if not isinstance(state, str) or not secrets.compare_digest(state, pending["state"]):
            raise MembershipError("authorization_state_mismatch")
        if value("error"):
            raise MembershipError(_error_code(value("error"), "authorization_denied"))
        issued = value("client_id") or pending["client_id"]
        if not isinstance(issued, str) or not CLIENT_ID.fullmatch(issued):
            raise MembershipError("missing_issued_client_id")
        if pending["client_id"] and issued != pending["client_id"]:
            raise MembershipError("registration_client_mismatch")
        code = value("code")
        if not isinstance(code, str) or not code or len(code) > 8192:
            raise MembershipError("missing_authorization_code")
        # Retain issued registration on invalid_grant, but never mark it authenticated.
        registration = {"client_id": issued}
        if pending.get("subject"):
            registration["subject"] = pending["subject"]
        self._write("registration.json", registration)
        tokens = self._json(TOKEN, {"grant_type": "authorization_code", "client_id": issued,
                                   "code": code, "code_verifier": pending["verifier"],
                                   "redirect_uri": pending["redirect_uri"], "resource": RESOURCE},
                            form=True)
        if not isinstance(tokens.get("id_token"), str):
            raise MembershipError("missing_id_token")
        identity = self._identity(tokens["id_token"], issued, pending["nonce"])
        if pending.get("subject") and identity["sub"] != pending["subject"]:
            raise MembershipError("account_identity_mismatch")
        record = self._token_record(tokens, issued, identity, pending["host_id"])
        self._write("credentials.json", record)
        self._write("registration.json", {"client_id": issued, "subject": identity["sub"]})
        return {"authenticated": True, "identity_verified": True,
                "plan_permission": DIRECT_SCOPE in record["scopes"]}

    def login(self, timeout_seconds=600, open_browser=True, announce=None, *, open_authorization=None):
        """Wait for official login; manual mode exposes only a protected request file.

        The file contains the public authorization URL and expiry, never the PKCE
        verifier. It is removed on success, failure, timeout, or interruption.
        The setup wizard can supply a URL handoff to use its own browser tab.
        """
        wizard_browser = open_authorization is not None
        self._discover()
        with self._lock():
            result = {}

            class Handler(http.server.BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def do_GET(handler):
                    parsed = urllib.parse.urlsplit(handler.path)
                    if parsed.path != "/auth/callback":
                        handler.send_error(404)
                        return
                    if result:
                        handler.send_error(409)
                        return
                    content_type = "text/plain; charset=utf-8"
                    policy = _CALLBACK_CSP
                    try:
                        status = self._finish_login(pending, parsed.query)
                        result["status"] = status
                        if wizard_browser and status.get("authenticated") is True and status.get("plan_permission") is True:
                            content_type = "text/html; charset=utf-8"
                            policy += f"; script-src 'sha256-{_CLOSE_SCRIPT_HASH}'"
                            body = _WIZARD_SUCCESS_HTML
                        elif wizard_browser:
                            body = "缺少 ChatGPT 会员用量授权。请返回 ResearchDesk 向导。".encode("utf-8")
                        else:
                            body = b"ResearchDesk: authorization finished. You may close this tab."
                    except MembershipError as exc:
                        result["error"] = exc
                        body = b"ResearchDesk: authorization failed. Return to the local app."
                    handler.send_response(200)
                    handler.send_header("Content-Type", content_type)
                    handler.send_header("Content-Security-Policy", policy)
                    handler.send_header("X-Content-Type-Options", "nosniff")
                    handler.send_header("Cache-Control", "no-store")
                    handler.send_header("Referrer-Policy", "no-referrer")
                    handler.send_header("Content-Length", str(len(body)))
                    handler.end_headers()
                    handler.wfile.write(body)

            with http.server.HTTPServer(("127.0.0.1", 0), Handler) as server:
                server.timeout = 1
                redirect = "http://127.0.0.1:%s/auth/callback" % server.server_port
                pending, url = self._prepare_login(redirect)
                started = time.monotonic()
                request_file = self.profile / "authorization.json"
                manual_request_written = False
                try:
                    if wizard_browser:
                        open_authorization(url)
                    opened = webbrowser.open(url, new=1) if open_browser and not wizard_browser else False
                    announcement = {"state": "awaiting_official_browser_login",
                                    "browser_opened": bool(opened), "callback_host": "127.0.0.1",
                                    "timeout_seconds": timeout_seconds}
                    if not open_browser and not wizard_browser:
                        self._write("authorization.json", {"url": url, "expires_at": pending["expires_at"]})
                        manual_request_written = True
                        announcement["authorization_request_file"] = str(request_file)
                    if announce is not None:
                        announce(announcement)
                    elif not wizard_browser:
                        print(json.dumps(announcement), flush=True)
                    if open_browser and not wizard_browser and not opened:
                        raise MembershipError("system_browser_unavailable")
                    while not result and time.monotonic() - started < min(timeout_seconds, 600):
                        server.handle_request()
                    if not result:
                        raise MembershipError("authorization_timeout")
                    if "error" in result:
                        raise result["error"]
                    return result["status"]
                finally:
                    if manual_request_written:
                        try:
                            request_file.unlink()
                        except FileNotFoundError:
                            pass

    def models(self):
        value = self._json(RESOURCE + "/models", bearer=self._access_token())
        if not isinstance(value.get("models"), list):
            raise MembershipError("invalid_model_catalog")
        result, seen = [], set()
        for item in value["models"]:
            if not isinstance(item, dict) or item.get("visibility") != "list":
                continue
            slug, label = item.get("slug"), item.get("display_name")
            if (not isinstance(slug, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", slug)
                    or not isinstance(label, str) or not label or len(label) > 200 or slug in seen):
                raise MembershipError("invalid_model_catalog")
            result.append({"slug": slug, "display_name": label})
            seen.add(slug)
        self._catalog = result
        return result

    @staticmethod
    def _completed_output(response):
        chunks = []
        output = response.get("output")
        if not isinstance(output, list):
            raise MembershipError("invalid_completed_response")
        for item in output:
            if isinstance(item, dict) and item.get("type") == "message":
                contents = item.get("content")
                if not isinstance(contents, list):
                    raise MembershipError("invalid_completed_response")
                for content in contents:
                    if isinstance(content, dict) and content.get("type") == "output_text":
                        if not isinstance(content.get("text"), str):
                            raise MembershipError("invalid_completed_response")
                        chunks.append(content["text"])
        return "".join(chunks)

    def infer(self, model, instructions, input_text, max_output_chars=12000,
              timeout_seconds=120):
        if not isinstance(instructions, str) or not isinstance(input_text, str):
            raise MembershipError("invalid_inference_input")
        if not 1 <= max_output_chars <= 50000 or not 1 <= timeout_seconds <= 300:
            raise MembershipError("invalid_inference_limits")
        # Per-stage YAML budgets still preflight the exact JSON request. This
        # outer ceiling permits bounded multi-paper full-text Insight inputs.
        if len(instructions) + len(input_text) > 600000:
            raise MembershipError("input_too_large")
        catalog = self.models() if self._catalog is None else self._catalog
        if model not in {item["slug"] for item in catalog}:
            raise MembershipError("model_not_available")
        payload = {"model": model, "instructions": instructions,
                   "input": [{"role": "user", "content": input_text}],
                   "store": False, "stream": True}
        started = time.monotonic()
        token = self._access_token()
        response = self._open(RESOURCE + "/responses", _json_bytes(payload), token,
                              timeout=timeout_seconds, content_type="application/json")
        chunks, data_lines, size = [], [], 0
        completed = None

        def consume(lines):
            nonlocal completed
            data = "\n".join(lines)
            if not data or data == "[DONE]":
                return
            try:
                event = json.loads(data)
            except (ValueError, UnicodeError):
                raise MembershipError("invalid_stream_event") from None
            if not isinstance(event, dict):
                raise MembershipError("invalid_stream_event")
            kind = event.get("type")
            if kind == "response.output_text.delta":
                delta = event.get("delta")
                if not isinstance(delta, str):
                    raise MembershipError("invalid_stream_event")
                chunks.append(delta)
                if sum(len(chunk) for chunk in chunks) > max_output_chars:
                    raise MembershipError("output_limit_interrupted")
            elif kind in ("response.failed", "response.incomplete", "error"):
                failed_response = event.get("response")
                detail = failed_response.get("error") if isinstance(failed_response, dict) else None
                if kind == "error":
                    detail = event
                raise MembershipError(_error_code(detail, "inference_" + (
                    "incomplete" if kind == "response.incomplete" else "failed")))
            elif kind == "response.completed":
                value = event.get("response")
                if (not isinstance(value, dict) or value.get("status") != "completed"
                        or not isinstance(value.get("model"), str) or not value["model"]
                        or not isinstance(value.get("id"), str) or not value["id"]):
                    raise MembershipError("invalid_completed_response")
                completed = value

        try:
            with response:
                while completed is None:
                    remaining = timeout_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        raise MembershipError("inference_timeout")
                    # urllib's timeout is per read; reduce it against the total deadline.
                    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    raw = response.readline(1024 * 1024 + 1)
                    if not raw:
                        if data_lines:
                            consume(data_lines)
                        break
                    size += len(raw)
                    if len(raw) > 1024 * 1024 or size > 3 * 1024 * 1024:
                        raise MembershipError("stream_too_large")
                    try:
                        line = raw.decode("utf-8").rstrip("\r\n")
                    except UnicodeError:
                        raise MembershipError("invalid_stream_event") from None
                    if line == "":
                        consume(data_lines)
                        data_lines = []
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip(" "))
        except MembershipError:
            raise
        except (OSError, ValueError, urllib.error.URLError):
            raise MembershipError("stream_interrupted") from None
        if completed is None:
            raise MembershipError("stream_incomplete")
        if completed["model"] != model:
            raise MembershipError("actual_model_mismatch")
        text = self._completed_output(completed) or "".join(chunks)
        if not text or len(text) > max_output_chars:
            raise MembershipError("completed_output_invalid")
        usage = completed.get("usage")
        if not isinstance(usage, dict):
            usage = None
        return {"text": text, "model": completed["model"], "response_id": completed["id"],
                "usage": usage}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE))
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--manual-browser", action="store_true",
                        help="Keep the callback listener running and write a protected authorization request")
    parser.add_argument("command", choices=["login", "status", "models"])
    args = parser.parse_args(argv)
    try:
        client = MembershipClient(args.profile_dir, args.root)
        result = client.login(open_browser=not args.manual_browser) if args.command == "login" else getattr(client, args.command)()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except MembershipError as exc:
        print(json.dumps({"error": exc.code, "http_status": exc.http_status,
                          "request_id": exc.request_id, "body_shape": exc.body_shape}), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyboardInterrupt):
        print(json.dumps({"error": "local_membership_operation_failed"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
