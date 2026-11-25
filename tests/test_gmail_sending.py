"""Gửi mã qua Gmail: OAuth (đăng nhập Google) và SMTP dự phòng.

Không chạm Credential Manager, không mở trình duyệt thật, không gọi Google:
kho bí mật, SMTP, HTTP và trình duyệt đều được thay bằng bản giả.
"""

import base64
import hashlib
import json
import smtplib
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from unittest import mock

from evolock.integrations import gmail_oauth, session_code


class FakeSecrets:
    def __init__(self, **initial):
        self.store = dict(initial)

    def __enter__(self):
        self._patches = [
            mock.patch.object(gmail_oauth, "_secret_get", lambda n: self.store.get(n, "")),
            mock.patch.object(gmail_oauth, "_secret_set",
                              lambda n, v: self.store.__setitem__(n, v) or True),
            mock.patch.object(gmail_oauth, "_secret_delete", lambda n: self.store.pop(n, None)),
        ]
        for p in self._patches:
            p.start()
        gmail_oauth._access.update(token="", expires=0.0)
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        gmail_oauth._access.update(token="", expires=0.0)


def connected_secrets():
    return FakeSecrets(**{
        gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "csecret",
        gmail_oauth.REFRESH_TOKEN_KEY: "refresh"})


def fake_browser(code="abc", state=None):
    """Thay webbrowser.open: gọi lại địa chỉ redirect như Google sau khi người dùng bấm Cho phép."""
    seen = {}

    def opener(url):
        query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
        seen.update(query)
        reply = {"state": state or query["state"]}
        reply.update({"code": code} if code else {"error": "access_denied"})
        target = query["redirect_uri"] + "/?" + urllib.parse.urlencode(reply)
        threading.Thread(target=lambda: urllib.request.urlopen(target, timeout=5).read(),
                         daemon=True).start()
        return True
    return opener, seen


class SmtpFallbackTests(unittest.TestCase):
    def test_app_password_spaces_are_removed(self):
        self.assertEqual(session_code.normalize_app_password("abcd efgh ijkl mnop"),
                         "abcdefghijklmnop")

    def test_saving_reports_failure_instead_of_staying_silent(self):
        broken = mock.Mock()
        broken.set_password.side_effect = RuntimeError("locked")
        with mock.patch.object(session_code, "KEYRING_AVAILABLE", True), \
                mock.patch.object(session_code, "keyring", broken, create=True):
            self.assertFalse(session_code.save_app_password("abcd efgh ijkl mnop"))
            self.assertFalse(session_code.save_local_password("pw"))
        with mock.patch.object(session_code, "KEYRING_AVAILABLE", False):
            self.assertFalse(session_code.save_app_password("abcd"))

    def _send(self, smtp=None, ssl=None):
        with FakeSecrets(), \
                mock.patch.object(session_code, "load_app_password", return_value="abcd efgh ijkl mnop"), \
                mock.patch.object(session_code.smtplib, "SMTP", smtp or mock.MagicMock()), \
                mock.patch.object(session_code.smtplib, "SMTP_SSL", ssl or mock.MagicMock()):
            return session_code.send_code_email("me@gmail.com", "123456", 25)

    def test_success_uses_stripped_password(self):
        smtp = mock.MagicMock()
        ok, err = self._send(smtp=smtp)
        self.assertTrue(ok, err)
        server = smtp.return_value.__enter__.return_value
        server.login.assert_called_once_with("me@gmail.com", "abcdefghijklmnop")

    def test_rejected_login_is_explained_and_not_retried_on_other_port(self):
        smtp, ssl = mock.MagicMock(), mock.MagicMock()
        smtp.return_value.__enter__.return_value.login.side_effect = \
            smtplib.SMTPAuthenticationError(535, b"bad")
        ok, err = self._send(smtp=smtp, ssl=ssl)
        self.assertFalse(ok)
        self.assertIn("アプリパスワード", err)
        ssl.assert_not_called()  # ログイン失敗を別ポートで繰り返さない

    def test_disconnect_during_login_is_explained_and_not_retried(self):
        smtp, ssl = mock.MagicMock(), mock.MagicMock()
        smtp.return_value.__enter__.return_value.login.side_effect = \
            smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
        ok, err = self._send(smtp=smtp, ssl=ssl)
        self.assertFalse(ok)
        self.assertIn("切断", err)
        self.assertNotIn("unexpectedly", err)
        ssl.assert_not_called()

    def test_connection_failure_falls_back_to_ssl_port(self):
        smtp = mock.MagicMock(side_effect=ConnectionRefusedError("blocked"))
        ssl = mock.MagicMock()
        ok, err = self._send(smtp=smtp, ssl=ssl)
        self.assertTrue(ok, err)
        ssl.assert_called_once()

    def test_not_configured_message(self):
        with FakeSecrets(), mock.patch.object(session_code, "load_app_password", return_value=""):
            ok, err = session_code.send_code_email("me@gmail.com", "123456", 25)
        self.assertFalse(ok)
        self.assertIn("未設定", err)

    def test_oauth_is_preferred_when_connected(self):
        smtp = mock.MagicMock()
        with connected_secrets(), \
                mock.patch.object(gmail_oauth, "send_message", return_value=(True, "")) as send, \
                mock.patch.object(session_code.smtplib, "SMTP", smtp):
            ok, _ = session_code.send_code_email("me@gmail.com", "123456", 25)
        self.assertTrue(ok)
        send.assert_called_once()
        smtp.assert_not_called()
        message = send.call_args.args[0]
        self.assertEqual(message["To"], "me@gmail.com")
        self.assertIn("123456", message.get_payload(decode=True).decode("utf-8"))


class ClientFileTests(unittest.TestCase):
    def _write(self, data):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        self.addCleanup(lambda: __import__("os").unlink(handle.name))
        json.dump(data, handle)
        handle.close()
        return handle.name

    def test_desktop_client_file_is_saved(self):
        path = self._write({"installed": {"client_id": "abc.apps.googleusercontent.com",
                                           "client_secret": "GOCSPX-xyz"}})
        with FakeSecrets() as secrets:
            ok, message = gmail_oauth.load_client_file(path)
            self.assertTrue(ok, message)
            self.assertEqual(secrets.store[gmail_oauth.CLIENT_ID_KEY], "abc.apps.googleusercontent.com")
            self.assertEqual(secrets.store[gmail_oauth.CLIENT_SECRET_KEY], "GOCSPX-xyz")

    def test_web_client_file_is_rejected_with_a_clear_reason(self):
        path = self._write({"web": {"client_id": "a", "client_secret": "b"}})
        with FakeSecrets() as secrets:
            ok, message = gmail_oauth.load_client_file(path)
            self.assertFalse(ok)
            self.assertIn("ウェブ", message)
            self.assertEqual(secrets.store, {})

    def test_missing_or_broken_file_and_missing_fields(self):
        with FakeSecrets() as secrets:
            self.assertFalse(gmail_oauth.load_client_file("khong-co-file.json")[0])
            self.assertFalse(gmail_oauth.load_client_file(self._write(["x"]))[0])
            ok, _ = gmail_oauth.load_client_file(self._write({"installed": {"client_id": "a"}}))
            self.assertFalse(ok)
            self.assertEqual(secrets.store, {})

    def test_error_messages_never_contain_the_secret(self):
        path = self._write({"installed": {"client_id": "a", "client_secret": "TOP-SECRET-VALUE"}})
        with FakeSecrets(), mock.patch.object(gmail_oauth, "_secret_set", lambda n, v: False):
            ok, message = gmail_oauth.load_client_file(path)
        self.assertFalse(ok)
        self.assertNotIn("TOP-SECRET-VALUE", message)


class BundledClientTests(unittest.TestCase):
    def _bundle(self, data):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        self.addCleanup(lambda: __import__("os").unlink(handle.name))
        json.dump(data, handle)
        handle.close()
        patcher = mock.patch.object(gmail_oauth, "BUNDLED_CLIENT_FILE", __import__("pathlib").Path(handle.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_bundled_client_is_used_without_any_saved_secret(self):
        self._bundle({"installed": {"client_id": "bundled-id", "client_secret": "bundled-secret"}})
        with FakeSecrets():
            self.assertTrue(gmail_oauth.has_client())
            self.assertTrue(gmail_oauth.uses_bundled_client())
            self.assertEqual(gmail_oauth._client(), ("bundled-id", "bundled-secret"))

    def test_bundled_client_wins_over_a_saved_one(self):
        self._bundle({"installed": {"client_id": "bundled-id", "client_secret": "bundled-secret"}})
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "saved", gmail_oauth.CLIENT_SECRET_KEY: "s"}):
            self.assertEqual(gmail_oauth._client()[0], "bundled-id")

    def test_missing_or_broken_bundle_falls_back_to_the_saved_client(self):
        self._bundle({"web": {}})
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "saved", gmail_oauth.CLIENT_SECRET_KEY: "s"}):
            self.assertFalse(gmail_oauth.uses_bundled_client())
            self.assertEqual(gmail_oauth._client(), ("saved", "s"))
        with FakeSecrets():
            self.assertFalse(gmail_oauth.has_client())


class OAuthLoginTests(unittest.TestCase):
    def test_pkce_challenge_matches_verifier(self):
        verifier, challenge = gmail_oauth._pkce_pair()
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(challenge, expected)
        self.assertGreaterEqual(len(verifier), 43)

    def test_requires_client_before_login(self):
        with FakeSecrets():
            ok, err = gmail_oauth.authorize(timeout=1)
        self.assertFalse(ok)
        self.assertIn("Client", err)

    def test_successful_login_stores_only_refresh_token(self):
        tokens = {"refresh_token": "R1", "access_token": "A1", "expires_in": 3600,
                  "scope": gmail_oauth.SCOPE}
        opener, seen = fake_browser()
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "cs"}) as fake, \
                mock.patch.object(gmail_oauth.webbrowser, "open", opener), \
                mock.patch.object(gmail_oauth, "_post_form", return_value=tokens) as post:
            ok, err = gmail_oauth.authorize(timeout=10)
        self.assertTrue(ok, err)
        self.assertEqual(fake.store[gmail_oauth.REFRESH_TOKEN_KEY], "R1")
        self.assertEqual(seen["scope"], gmail_oauth.SCOPE)
        self.assertEqual(seen["code_challenge_method"], "S256")
        self.assertEqual(seen["access_type"], "offline")
        sent = post.call_args.args[1]
        self.assertEqual(sent["code"], "abc")
        self.assertEqual(sent["redirect_uri"], seen["redirect_uri"])
        self.assertTrue(sent["redirect_uri"].startswith("http://127.0.0.1:"))
        self.assertEqual(hashlib.sha256(sent["code_verifier"].encode()).digest(),
                         base64.urlsafe_b64decode(seen["code_challenge"] + "=="))

    def test_state_mismatch_is_rejected(self):
        opener, _ = fake_browser(state="forged")
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "cs"}) as fake, \
                mock.patch.object(gmail_oauth.webbrowser, "open", opener), \
                mock.patch.object(gmail_oauth, "_post_form") as post:
            ok, err = gmail_oauth.authorize(timeout=10)
        self.assertFalse(ok)
        post.assert_not_called()
        self.assertNotIn(gmail_oauth.REFRESH_TOKEN_KEY, fake.store)

    def test_cancelled_login(self):
        opener, _ = fake_browser(code=None)
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "cs"}), \
                mock.patch.object(gmail_oauth.webbrowser, "open", opener):
            ok, err = gmail_oauth.authorize(timeout=10)
        self.assertFalse(ok)
        self.assertIn("キャンセル", err)

    def test_login_times_out_when_nobody_answers(self):
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "cs"}), \
                mock.patch.object(gmail_oauth.webbrowser, "open", return_value=True):
            ok, err = gmail_oauth.authorize(timeout=1)
        self.assertFalse(ok)
        self.assertIn("タイムアウト", err)

    def test_send_permission_must_be_granted(self):
        opener, _ = fake_browser()
        tokens = {"refresh_token": "R", "access_token": "A", "expires_in": 3600, "scope": "openid"}
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "cs"}) as fake, \
                mock.patch.object(gmail_oauth.webbrowser, "open", opener), \
                mock.patch.object(gmail_oauth, "_post_form", return_value=tokens):
            ok, err = gmail_oauth.authorize(timeout=10)
        self.assertFalse(ok)
        self.assertIn("メールの送信", err)
        self.assertNotIn(gmail_oauth.REFRESH_TOKEN_KEY, fake.store)


class OAuthSendTests(unittest.TestCase):
    def message(self):
        return session_code.build_code_message("me@gmail.com", "654321", 30)

    def test_send_posts_raw_message_with_bearer_token(self):
        sent = []
        with connected_secrets(), \
                mock.patch.object(gmail_oauth, "_post_form",
                                  return_value={"access_token": "AT", "expires_in": 3600}), \
                mock.patch.object(gmail_oauth, "_open", side_effect=lambda req, t: sent.append(req) or {}):
            ok, err = gmail_oauth.send_message(self.message())
        self.assertTrue(ok, err)
        req = sent[0]
        self.assertEqual(req.full_url, gmail_oauth.SEND_URL)
        self.assertEqual(req.get_header("Authorization"), "Bearer AT")
        raw = json.loads(req.data)["raw"]
        self.assertIn("654321", base64.urlsafe_b64decode(raw).decode("utf-8", "replace")
                      + base64.b64decode(base64.urlsafe_b64decode(raw).split(b"\n\n", 1)[1]).decode("utf-8", "replace"))

    def test_expired_token_is_refreshed_once_then_succeeds(self):
        calls = {"n": 0}

        def open_(req, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                raise gmail_oauth.OAuthError("expired", 401)
            return {}
        with connected_secrets(), \
                mock.patch.object(gmail_oauth, "_post_form",
                                  return_value={"access_token": "AT", "expires_in": 3600}) as post, \
                mock.patch.object(gmail_oauth, "_open", side_effect=open_):
            ok, err = gmail_oauth.send_message(self.message())
        self.assertTrue(ok, err)
        self.assertEqual(post.call_count, 2)

    def test_revoked_login_gives_actionable_message(self):
        with connected_secrets(), \
                mock.patch.object(gmail_oauth, "_post_form",
                                  side_effect=gmail_oauth.OAuthError(
                                      gmail_oauth._describe_http_error(400, "invalid_grant", ""), 400)):
            ok, err = gmail_oauth.send_message(self.message())
        self.assertFalse(ok)
        self.assertIn("やり直して", err)

    def test_not_logged_in(self):
        with FakeSecrets(**{gmail_oauth.CLIENT_ID_KEY: "cid", gmail_oauth.CLIENT_SECRET_KEY: "cs"}):
            ok, err = gmail_oauth.send_message(self.message())
        self.assertFalse(ok)
        self.assertIn("ログイン", err)

    def test_api_not_enabled_message(self):
        text = gmail_oauth._describe_http_error(
            403, "PERMISSION_DENIED", "Gmail API has not been used in project 1 before or it is disabled.")
        self.assertIn("Gmail APIが有効", text)

    def test_disconnect_forgets_login(self):
        with connected_secrets() as fake:
            self.assertTrue(gmail_oauth.is_connected())
            gmail_oauth.disconnect()
            self.assertFalse(gmail_oauth.is_connected())
            self.assertTrue(gmail_oauth.has_client())
            gmail_oauth.disconnect(forget_client=True)
            self.assertFalse(gmail_oauth.has_client())
            self.assertEqual(fake.store, {})


if __name__ == "__main__":
    unittest.main()
