"""Khung đa ngôn ngữ (chưa gắn vào giao diện): tiếng Nhật mặc định, thiếu bản dịch thì giữ nguyên."""

import ast
import re
import unittest
from pathlib import Path
from unittest import mock

from evolock import i18n


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("ja")

    def test_japanese_is_the_default_and_returns_text_unchanged(self):
        i18n.set_language("ja")
        self.assertEqual(i18n.tr("学習開始"), "学習開始")

    def test_unknown_language_falls_back_to_japanese(self):
        self.assertEqual(i18n.set_language("xx"), "ja")
        self.assertEqual(i18n.set_language(None), "ja")

    def test_translation_is_used_and_missing_keys_keep_the_original(self):
        with mock.patch.dict(i18n._catalogs, {"vi": {"学習開始": "Bắt đầu học"}}):
            i18n.set_language("vi")
            self.assertEqual(i18n.tr("学習開始"), "Bắt đầu học")
            self.assertEqual(i18n.tr("未翻訳の文"), "未翻訳の文")

    def test_language_names_are_written_in_their_own_language(self):
        self.assertEqual(i18n.LANGUAGES["vi"], "Tiếng Việt")
        self.assertEqual(i18n.LANGUAGES["ja"], "日本語")


PACKAGE = Path(__file__).resolve().parent.parent / "evolock"
PLACEHOLDER = re.compile(r"\{(\d+)[^}]*\}")


def used_keys() -> dict[str, str]:
    """Mọi chuỗi mà source đưa vào tr(...) / translate(code, ...), kèm nơi dùng."""
    found: dict[str, str] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            index = 1 if name == "translate" else 0
            if name in ("tr", "translate") and len(node.args) > index \
                    and isinstance(node.args[index], ast.Constant) and isinstance(node.args[index].value, str):
                found.setdefault(node.args[index].value, f"{path.name}:{node.lineno}")
    return found


def displayed_constants() -> list[str]:
    """Chuỗi hằng số được dịch lúc hiển thị (không nằm trong lời gọi tr() trực tiếp)."""
    from evolock.services import gamification
    from evolock.storage import tasks
    from evolock.integrations import session_code
    from evolock.ui import app
    from evolock.services import ai_coach
    values = list(session_code.REASONS) + list(tasks.TASK_TYPES) + list(app.MASCOT_LINES)
    values += list(ai_coach.BUCKET_ORDER) + list(ai_coach._OVERRIDE_HINTS.values())
    values.append(ai_coach.OVERRIDE_HINT_DEFAULT)
    values += [ai_coach._time_bucket(f"{hour:02d}:00") for hour in (6, 13, 20, 2)]
    values += [name for _, name in gamification.RANKS]
    for _, name, description in gamification.ACHIEVEMENTS:
        values += [name, description]
    return values


class CatalogTests(unittest.TestCase):
    def catalogs(self):
        from evolock.locales import en, vi
        return {"vi": vi.MESSAGES, "en": en.MESSAGES}

    def test_every_string_shown_to_users_is_translated(self):
        wanted = {key: where for key, where in used_keys().items()}
        wanted.update({key: "constant" for key in displayed_constants()})
        for language, messages in self.catalogs().items():
            missing = [f"{where}: {key[:40]}" for key, where in wanted.items() if key not in messages]
            self.assertEqual(missing, [], f"{language} is missing translations")

    def test_placeholders_match_the_japanese_original(self):
        for language, messages in self.catalogs().items():
            for key, value in messages.items():
                self.assertEqual(sorted(PLACEHOLDER.findall(key)), sorted(PLACEHOLDER.findall(value)),
                                 f"{language}: placeholders differ for {key[:40]!r}")

    def test_translations_are_not_empty_and_formatting_works(self):
        for language, messages in self.catalogs().items():
            for key, value in messages.items():
                self.assertTrue(value.strip(), f"{language}: empty translation for {key[:40]!r}")
                count = len(set(PLACEHOLDER.findall(key)))
                value.format(*range(count))  # không ném lỗi (ngoặc {} sai)

    def test_no_translation_without_a_use(self):
        """Bản dịch thừa là dấu hiệu khóa bị gõ sai hoặc chuỗi gốc đã đổi."""
        known = set(used_keys()) | set(displayed_constants())
        for language, messages in self.catalogs().items():
            stale = [key[:40] for key in messages if key not in known]
            self.assertEqual(stale, [], f"{language} has translations nothing uses")

    def test_switching_language_translates_and_restores(self):
        i18n.set_language("vi")
        self.assertEqual(i18n.tr("学習開始"), "Bắt đầu học")
        i18n.set_language("en")
        self.assertEqual(i18n.tr("学習開始"), "Start studying")
        i18n.set_language("ja")
        self.assertEqual(i18n.tr("学習開始"), "学習開始")

    def test_translate_is_independent_of_the_current_language(self):
        i18n.set_language("ja")
        self.assertEqual(i18n.translate("en", "言語"), "Language")
        self.assertEqual(i18n.translate("vi", "言語"), "Ngôn ngữ")


if __name__ == "__main__":
    unittest.main()
