"""Gửi thư bằng Gmail API qua OAuth 2.0 — đăng nhập Google trong trình duyệt,
không cần App Password và không bao giờ nhận mật khẩu Google.

Luồng "ứng dụng máy tính" (loopback + PKCE):
  1. Mở trình duyệt tới trang đồng ý của Google, chờ ở http://127.0.0.1:<cổng>.
  2. Đổi mã nhận được lấy refresh token, lưu vào Windows Credential Manager.
  3. Mỗi lần gửi, dùng refresh token lấy access token ngắn hạn rồi gọi Gmail API
     bằng HTTPS (cổng 443), không đi qua SMTP.

Chỉ dùng thư viện chuẩn của Python. Client ID/Secret do người dùng tạo trong
Google Cloud Console (loại "Desktop app") và lưu cùng chỗ với token.
"""

import base64
import hashlib
import http.server
import json
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from email.message import Message
from evolock.i18n import tr
from evolock.paths import ASSETS_DIR

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

BUNDLED_CLIENT_FILE = ASSETS_DIR / "oauth_client.json"
KEYRING_SERVICE = "EvoLock"
CLIENT_ID_KEY = "gmail_oauth_client_id"
CLIENT_SECRET_KEY = "gmail_oauth_client_secret"
REFRESH_TOKEN_KEY = "gmail_oauth_refresh_token"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPE = "https://www.googleapis.com/auth/gmail.send"

_access = {"token": "", "expires": 0.0}


class OAuthError(Exception):
    """Lỗi đã được viết thành câu hướng dẫn cho người dùng (tiếng Nhật)."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


# ── Kho bí mật (Windows Credential Manager) ─────────────────────────────

def _secret_get(name: str) -> str:
    if not KEYRING_AVAILABLE:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, name) or ""
    except Exception:
        return ""


def _secret_set(name: str, value: str) -> bool:
    if not KEYRING_AVAILABLE:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, name, value)
        return True
    except Exception:
        return False


def _secret_delete(name: str):
    if not KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except Exception:
        pass


def save_client(client_id: str, client_secret: str) -> bool:
    """Lưu Client ID/Secret. Trả về False nếu không lưu được vào Credential Manager."""
    client_id = "".join(client_id.split())
    client_secret = "".join(client_secret.split())
    if not client_id or not client_secret:
        return False
    ok = _secret_set(CLIENT_ID_KEY, client_id) and _secret_set(CLIENT_SECRET_KEY, client_secret)
    if ok:
        _access.update(token="", expires=0.0)
    return ok


def load_client_file(path) -> tuple[bool, str]:
    """Đọc file JSON "OAuth client" tải từ Google Cloud (loại Desktop app) rồi lưu Client
    vào Credential Manager. Không bao giờ đưa giá trị secret vào thông báo trả về."""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False, tr("ファイルを読み込めません。Google Cloudからダウンロードしたクライアント用JSONを選んでください。")
    section = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        if isinstance(data, dict) and isinstance(data.get("web"), dict):
            return False, tr("このJSONは「ウェブ アプリケーション」用です。「デスクトップ アプリ」のクライアントを作り直してください。")
        return False, tr("ファイルを読み込めません。Google Cloudからダウンロードしたクライアント用JSONを選んでください。")
    client_id = str(section.get("client_id") or "")
    client_secret = str(section.get("client_secret") or "")
    if not (client_id.strip() and client_secret.strip()):
        return False, tr("JSONにClient IDまたはClient Secretがありません。")
    if not save_client(client_id, client_secret):
        return False, tr("Client情報をWindows資格情報マネージャーに保存できませんでした。")
    return True, ""


def _bundled_client() -> tuple[str, str]:
    """Client do nhà phát hành đóng gói sẵn (assets/oauth_client.json, cùng định dạng file
    Google cho tải về). Người dùng cuối không phải nhập Client ID/Secret."""
    try:
        data = json.loads(BUNDLED_CLIENT_FILE.read_text(encoding="utf-8-sig"))
        section = data["installed"]
        return str(section["client_id"]).strip(), str(section["client_secret"]).strip()
    except (OSError, ValueError, KeyError, TypeError):
        return "", ""


def _client() -> tuple[str, str]:
    """(client_id, client_secret): bản đóng gói sẵn được ưu tiên, sau đó tới bản đã lưu."""
    bundled = _bundled_client()
    if all(bundled):
        return bundled
    return _secret_get(CLIENT_ID_KEY), _secret_get(CLIENT_SECRET_KEY)


def has_client() -> bool:
    return all(_client())


def uses_bundled_client() -> bool:
    return all(_bundled_client())


def is_connected() -> bool:
    """Đã lưu Client và đã đăng nhập Google (có refresh token)."""
    return has_client() and bool(_secret_get(REFRESH_TOKEN_KEY))


def disconnect(forget_client: bool = False):
    _secret_delete(REFRESH_TOKEN_KEY)
    if forget_client:
        _secret_delete(CLIENT_ID_KEY)
        _secret_delete(CLIENT_SECRET_KEY)
    _access.update(token="", expires=0.0)


# ── HTTP ─────────────────────────────────────────────────────────────────

def _error_text(exc: urllib.error.HTTPError) -> tuple[str, str]:
    """(mã lỗi, mô tả) lấy từ thân phản hồi của Google; không bao giờ ném lỗi."""
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
    except Exception:
        return "", ""
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("status", "")), str(err.get("message", ""))
    return str(err or ""), str(body.get("error_description", ""))


def _post_form(url: str, data: dict, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    return _open(req, timeout)


def _open(req: urllib.request.Request, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        code, desc = _error_text(exc)
        raise OAuthError(_describe_http_error(exc.code, code, desc), exc.code) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError):
        raise OAuthError(tr("Googleに接続できません。ネットワーク接続を確認してください。")) from None


def _describe_http_error(status: int, code: str, desc: str) -> str:
    if code == "invalid_grant":
        return tr("Googleのログインが無効になりました。「Googleでログイン」をやり直してください。")
    if code in ("invalid_client", "unauthorized_client"):
        return tr("Client IDまたはClient Secretが正しくありません。Google Cloud Consoleの値を確認してください。")
    if status == 403 and ("has not been used" in desc or "disabled" in desc.lower()):
        return tr("Gmail APIが有効になっていません。Google Cloud ConsoleでGmail APIを有効にしてください。")
    if status == 403:
        return tr("Gmailへの送信が許可されていません。ログイン時に「メールの送信」を許可してください。")
    if status == 429:
        return tr("Googleの送信回数制限に達しました。しばらく待ってからやり直してください。")
    return tr("Googleがエラーを返しました（{0}）{1}").format(status, (': ' + desc[:80]) if desc else '')


# ── ログイン（ブラウザ） ─────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


_DONE_PAGE = ("<html><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
              "<h3>EvoLock</h3><p>{msg}</p></body></html>")


def authorize(timeout: int = 180) -> tuple[bool, str]:
    """Mở trình duyệt để đăng nhập Google. Chặn tới khi xong hoặc hết `timeout`
    giây — gọi từ luồng nền, không gọi trên luồng giao diện."""
    client_id, client_secret = _client()
    if not client_id or not client_secret:
        return False, tr("先にClient IDとClient Secretを保存してください。")

    state = secrets.token_urlsafe(16)
    verifier, challenge = _pkce_pair()
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            if parsed.path != "/" or not ("code" in query or "error" in query):
                self.send_response(404)
                self.end_headers()
                return
            result.update(query)
            ok = "code" in query
            page = _DONE_PAGE.format(
                msg=tr("ログインが完了しました。このタブを閉じてEvoLockに戻ってください。") if ok
                else tr("ログインはキャンセルされました。このタブを閉じてください。"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))

        def log_message(self, *args):  # コードや状態をログに出さない
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    try:
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
        query = urllib.parse.urlencode({
            "client_id": client_id, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": SCOPE, "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "access_type": "offline", "prompt": "consent",
        })
        if not webbrowser.open(f"{AUTH_URL}?{query}"):
            return False, tr("ブラウザを開けませんでした。")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not ("code" in result or "error" in result):
            server.handle_request()
    finally:
        server.server_close()

    if "error" in result:
        return False, (tr("ログインがキャンセルされました。") if result["error"] == "access_denied"
                       else tr("Googleがログインを拒否しました（{0}）。").format(result['error'][:40]))
    if "code" not in result:
        return False, tr("ログインがタイムアウトしました。もう一度お試しください。")
    if not secrets.compare_digest(result.get("state", ""), state):
        return False, tr("ログイン応答を確認できませんでした（state不一致）。もう一度お試しください。")

    try:
        tokens = _post_form(TOKEN_URL, {
            "grant_type": "authorization_code", "code": result["code"],
            "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "code_verifier": verifier,
        })
    except OAuthError as exc:
        return False, str(exc)

    if SCOPE not in str(tokens.get("scope", "")).split():
        return False, tr("「メールの送信」が許可されていません。ログイン画面でチェックを入れてやり直してください。")
    refresh = tokens.get("refresh_token", "")
    if not refresh:
        return False, tr("Googleから更新トークンが返りませんでした。もう一度ログインしてください。")
    if not _secret_set(REFRESH_TOKEN_KEY, refresh):
        return False, tr("ログイン情報をWindows資格情報マネージャーに保存できませんでした。")
    _access.update(token=tokens.get("access_token", ""),
                   expires=time.time() + int(tokens.get("expires_in", 0) or 0))
    return True, ""


# ── 送信 ─────────────────────────────────────────────────────────────────

def _access_token() -> str:
    if _access["token"] and _access["expires"] - 60 > time.time():
        return _access["token"]
    refresh = _secret_get(REFRESH_TOKEN_KEY)
    if not refresh or not has_client():
        raise OAuthError(tr("Googleにログインしていません。「Googleでログイン」を押してください。"))
    try:
        tokens = _post_form(TOKEN_URL, {
            "grant_type": "refresh_token", "refresh_token": refresh,
            "client_id": _client()[0],
            "client_secret": _client()[1],
        })
    except OAuthError:
        _access.update(token="", expires=0.0)
        raise
    _access.update(token=tokens.get("access_token", ""),
                   expires=time.time() + int(tokens.get("expires_in", 0) or 0))
    if not _access["token"]:
        raise OAuthError(tr("Googleからアクセストークンを取得できませんでした。"))
    return _access["token"]


def send_message(msg: Message) -> tuple[bool, str]:
    """Gmail API で `msg` を送信。差出人は認証したアカウントになる。"""
    body = json.dumps({"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).encode()
    last = tr("送信に失敗しました。")
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(
                SEND_URL, data=body, method="POST",
                headers={"Authorization": f"Bearer {_access_token()}",
                         "Content-Type": "application/json"})
            _open(req, 20)
            return True, ""
        except OAuthError as exc:
            last = str(exc)
            if exc.status == 401 and attempt == 1:
                _access.update(token="", expires=0.0)  # 期限切れ — 取り直して1回だけ再試行
                continue
            break
    return False, last
