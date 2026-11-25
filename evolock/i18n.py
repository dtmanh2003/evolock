"""Đa ngôn ngữ cho giao diện EvoLock.

Quy ước: văn bản gốc trong source là tiếng Nhật; ``tr("日本語")`` trả về bản dịch
của ngôn ngữ đang chọn, hoặc chính văn bản gốc nếu là tiếng Nhật / chưa có bản dịch.
Vì vậy một chuỗi bị thiếu bản dịch chỉ hiện tiếng Nhật, không bao giờ làm app lỗi.

Chuỗi có tham số dùng chỉ số: ``tr("学習 {0}分").format(n)``. Bản dịch phải giữ
đúng các placeholder (có test kiểm tra).

Đổi ngôn ngữ được lưu trong ``config.json`` (khóa ``language``) và có hiệu lực
sau khi khởi động lại, vì các widget Tk được dựng một lần lúc khởi động.
"""

DEFAULT_LANGUAGE = "ja"

# Tên mỗi ngôn ngữ luôn viết bằng chính ngôn ngữ đó để người dùng tìm ra được
# dù đang ở ngôn ngữ nào.
LANGUAGES = {
    "ja": "日本語",
    "vi": "Tiếng Việt",
    "en": "English",
}

_current = DEFAULT_LANGUAGE
_catalogs: dict[str, dict[str, str]] = {}


def _catalog(code: str) -> dict[str, str]:
    if code not in _catalogs:
        try:
            if code == "vi":
                from evolock.locales.vi import MESSAGES
            elif code == "en":
                from evolock.locales.en import MESSAGES
            else:
                MESSAGES = {}
        except ImportError:
            MESSAGES = {}
        _catalogs[code] = MESSAGES
    return _catalogs[code]


def normalize(code) -> str:
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def set_language(code) -> str:
    global _current
    _current = normalize(code)
    return _current


def get_language() -> str:
    return _current


def translate(code, text: str) -> str:
    """Dịch `text` sang ngôn ngữ `code` (không phụ thuộc ngôn ngữ đang chọn) —
    dùng để báo "đã đổi ngôn ngữ" bằng chính ngôn ngữ vừa chọn."""
    code = normalize(code)
    if code == DEFAULT_LANGUAGE:
        return text
    return _catalog(code).get(text, text)


def tr(text: str) -> str:
    return translate(_current, text)
