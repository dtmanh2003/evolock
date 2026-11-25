import hashlib
import secrets
import smtplib
import socket
from email.mime.text import MIMEText

from evolock.integrations import gmail_oauth
from evolock.i18n import tr

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

KEYRING_SERVICE = "EvoLock"
KEYRING_USER    = "gmail_app_password"

REASONS = ["急用", "休憩したい", "予定が変わった", "その他"]


def _hash(value: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 100_000).hex()


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_code(code: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    return _hash(code, salt), salt


def verify_code(code: str, code_hash: str, salt: str) -> bool:
    if not code or not code_hash or not salt:
        return False
    return _hash(code, salt) == code_hash


def normalize_app_password(app_password: str) -> str:
    """Google hiển thị App Password dạng 'abcd efgh ijkl mnop'; bỏ mọi khoảng trắng."""
    return "".join(app_password.split())


def save_app_password(app_password: str) -> bool:
    """Lưu Gmail App Password vào Windows Credential Manager — không bao giờ
    ghi vào config.json. Trả về False nếu không lưu được (keyring thiếu/bị khóa)
    để giao diện báo lỗi thay vì im lặng."""
    app_password = normalize_app_password(app_password)
    if not KEYRING_AVAILABLE or not app_password:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, app_password)
        return True
    except Exception:
        return False


def load_app_password() -> str:
    if not KEYRING_AVAILABLE:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception:
        return ""


def clear_app_password():
    if not KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass


LOCAL_PW_USER = "local_fallback_password"


def save_local_password(password: str) -> bool:
    """Lưu mật khẩu dự phòng (dùng khi Gmail lỗi) vào Windows Credential
    Manager — để xem lại được sau này, tránh việc quên mật khẩu tự sinh
    rồi bị khóa hẳn không còn cách nào vào app. False nếu không lưu được."""
    if not KEYRING_AVAILABLE:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, LOCAL_PW_USER, password)
        return True
    except Exception:
        return False


def load_local_password() -> str:
    if not KEYRING_AVAILABLE:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, LOCAL_PW_USER) or ""
    except Exception:
        return ""


def clear_local_password():
    if not KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, LOCAL_PW_USER)
    except Exception:
        pass


def build_code_message(address: str, code: str, session_minutes: int) -> MIMEText:
    body = (
        tr("解除コード: {0}\n\nこのセッションの予定時間: {1}分\n\n早めに学習を終わらせたい時、このコードが必要です。\nコードを取りに来た今、一度立ち止まって考えてみましょう:\n「本当に必要な用事か、それとも今の面倒さから逃げたいだけか？」").format(code, session_minutes)
    )
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = tr("EvoLock — 学習セッション解除コード")
    msg["To"] = address
    return msg


def has_sender_credentials() -> bool:
    """Đã có cách gửi thư: đăng nhập Google (OAuth) hoặc App Password."""
    return gmail_oauth.is_connected() or bool(load_app_password())


def describe_smtp_error(exc: Exception) -> str:
    """Chuyển lỗi SMTP thô thành câu hướng dẫn. Phải kiểm tra lớp SMTP trước
    vì SMTPException cũng là OSError."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (tr("Googleがログインを拒否しました。アプリパスワードを作り直すか、"
                "2段階認証が有効か確認してください。"))
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return (tr("ログイン中にGoogleが接続を切断しました。アカウント保護や試行回数制限の"
                "可能性があります。しばらく待つか、「Googleでログイン」を使ってください。"))
    if isinstance(exc, (smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused)):
        return tr("Googleが送信先または差出人を拒否しました。Gmailアドレスを確認してください。")
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return tr("Gmailサーバーの応答がありません（タイムアウト）。ネットワークを確認してください。")
    if isinstance(exc, (socket.gaierror, ConnectionError, OSError)) and not isinstance(exc, smtplib.SMTPException):
        return tr("Gmailサーバーに接続できません。ネットワークやファイアウォールを確認してください。")
    return tr("送信エラー: {0}").format(str(exc)[:80])


def _send_via_smtp(address: str, app_password: str, msg: MIMEText) -> tuple[bool, str]:
    msg["From"] = address
    # Port 587 (STARTTLS) rồi 465 (SSL): chỉ đổi cổng khi LỖI KẾT NỐI. Đã bắt đầu
    # đăng nhập mà thất bại thì dừng — thử lại trên cổng khác chỉ thêm lần đăng
    # nhập sai và có thể khiến Google khóa tạm tài khoản.
    last = tr("送信に失敗しました。")
    for use_starttls, port in ((True, 587), (False, 465)):
        logging_in = False
        try:
            factory = smtplib.SMTP if use_starttls else smtplib.SMTP_SSL
            with factory("smtp.gmail.com", port, timeout=15) as server:
                if use_starttls:
                    server.starttls()
                logging_in = True
                server.login(address, app_password)
                server.sendmail(address, [address], msg.as_string())
            return True, ""
        except Exception as exc:
            last = describe_smtp_error(exc)
            if logging_in:
                break
    return False, last


def send_code_email(gmail_address: str, code: str, session_minutes: int) -> tuple[bool, str]:
    """Gửi mã phiên học tới chính Gmail của người dùng. Trả về (thành công, lỗi).
    Ưu tiên đăng nhập Google (OAuth); nếu chưa có thì dùng App Password (SMTP)."""
    if not gmail_address:
        return False, tr("Gmailアドレスが設定されていません")
    msg = build_code_message(gmail_address, code, session_minutes)
    if gmail_oauth.is_connected():
        return gmail_oauth.send_message(msg)
    app_password = load_app_password()
    if not app_password:
        return False, tr("送信方法が未設定です。「Googleでログイン」またはアプリパスワードを設定してください。")
    return _send_via_smtp(gmail_address, normalize_app_password(app_password), msg)
