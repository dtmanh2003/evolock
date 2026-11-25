from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
import copy
import hashlib
import secrets
import string
from evolock.paths import DATA_DIR

CONFIG_FILE = DATA_DIR / "config.json"

_DEFAULTS = {
    "protection_enabled": False,
    "gmail_protection_enabled": False,  # Bảo vệ bằng mã gửi tới Gmail (thay mã cục bộ)
    "language": "ja",             # ja / vi / en — có hiệu lực sau khi khởi động lại
    "smart_enabled": True,
    "screen_enabled": False,
    "screen_consent_destination": "",
    "password_hash": "",
    "startup_enabled": False,
    "anthropic_api_key": "",
    "ollama_model": "",           # Screen AI用（速さ優先の小型ビジョンモデル）
    "coach_ollama_model": "",     # AIコーチ用（テキスト生成、速度より質を優先。空なら ollama_model を流用）
    "daily_goal_minutes": 120,
    "password_note": "",
    "gmail_address": "",          # Gmail nhận mã phiên học (App Password lưu ở Windows Credential Manager)
    "session_code_hash": "",
    "session_code_salt": "",
    "coach_last_result": "",      # Kết quả phân tích AI Coach gần nhất — hiện ngay khi mở tab, khỏi đợi gọi AI lại
    "coach_last_analyzed_at": "",
    "developer_mode": False,  # Hiện phần cấu hình nội bộ (Client OAuth) trong Cài đặt
    "coach_last_language": "ja",  # Ngôn ngữ của kết quả Coach đã lưu (kết quả cũ = tiếng Nhật)
    "task_name_suggestions": {},  # {loại: [tên đã dùng...]} — độc lập với lịch sử task thật, xóa được qua UI
}


@committed_state("data", defaults=_DEFAULTS, path=lambda: CONFIG_FILE)
class Config:
    def __init__(self):
        self.data = copy.deepcopy(_DEFAULTS)
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                self.data.update(read_json(CONFIG_FILE))
            except Exception as exc:
                raise DataFileError(CONFIG_FILE) from exc

    def _save(self):
        atomic_write_text(CONFIG_FILE, json.dumps(self.data, ensure_ascii=False, indent=2))

    def set_many(self, values):
        self.data.update(values)
        self._save()

    def get(self, key):
        return self.data.get(key, _DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self._save()

    @staticmethod
    def _hash(value: str, salt: str) -> str:
        """PBKDF2-HMAC-SHA256 với salt."""
        return hashlib.pbkdf2_hmac(
            "sha256", value.encode(), salt.encode(), 100_000
        ).hex()

    @staticmethod
    def _legacy_hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def set_password(self, password: str):
        if not password:
            self.data["password_hash"] = ""
            self.data["password_salt"] = ""
        else:
            salt = secrets.token_hex(16)
            self.data["password_salt"] = salt
            self.data["password_hash"] = self._hash(password, salt)
        self._save()

    def verify_password(self, password: str) -> bool:
        stored = self.data.get("password_hash", "")
        if not stored:
            return True
        salt = self.data.get("password_salt", "")
        if salt:
            return self._hash(password, salt) == stored
        # Tương thích ngược: config cũ dùng SHA-256 không salt
        if self._legacy_hash(password) == stored:
            self.set_password(password)  # Nâng cấp lên PBKDF2
            return True
        return False

    def has_password(self) -> bool:
        return bool(self.data.get("password_hash", ""))

    def generate_random_password(self, length: int = 10) -> tuple[str, str]:
        alphabet = string.ascii_letters + string.digits
        password       = ''.join(secrets.choice(alphabet) for _ in range(length))
        emergency_code = ''.join(secrets.choice(string.digits) for _ in range(6))
        self.set_password(password)
        em_salt = secrets.token_hex(16)
        self.data["emergency_salt"] = em_salt
        self.data["emergency_hash"] = self._hash(emergency_code, em_salt)
        self._save()
        return password, emergency_code

    def set_session_code(self, code: str):
        salt = secrets.token_hex(16)
        self.data["session_code_salt"] = salt
        self.data["session_code_hash"] = self._hash(code, salt)
        self._save()

    def verify_session_code(self, code: str) -> bool:
        stored = self.data.get("session_code_hash", "")
        salt   = self.data.get("session_code_salt", "")
        if not stored or not salt:
            return False
        return self._hash(code, salt) == stored

    def clear_session_code(self):
        self.data["session_code_hash"] = ""
        self.data["session_code_salt"] = ""
        self._save()

    def has_gmail_configured(self) -> bool:
        from evolock.integrations import session_code
        return bool(self.data.get("gmail_address")) and session_code.has_sender_credentials()

    def verify_emergency(self, code: str) -> bool:
        stored = self.data.get("emergency_hash", "")
        if not stored:
            return False
        salt = self.data.get("emergency_salt", "")
        if salt:
            return self._hash(code, salt) == stored
        # Tương thích ngược
        if self._legacy_hash(code) == stored:
            em_salt = secrets.token_hex(16)
            self.data["emergency_salt"] = em_salt
            self.data["emergency_hash"] = self._hash(code, em_salt)
            self._save()
            return True
        return False

