from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from evolock.storage import config
from evolock.ui import app


class OptionalProtectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.patch = patch.object(config, 'CONFIG_FILE', Path(self.directory.name)/'config.json')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.ui = app.EvoLockApp.__new__(app.EvoLockApp)
        self.ui.cfg = config.Config()
        self.ui.root = MagicMock()
        self.ui.state = 'idle'
        self.ui._refresh_settings = MagicMock()

    def test_legacy_password_is_preserved_but_protection_defaults_off(self):
        self.ui.cfg.set_password('old-secret')
        loaded = config.Config()
        self.assertFalse(loaded.get('protection_enabled'))
        self.assertTrue(loaded.verify_password('old-secret'))

    def test_default_start_does_not_send_email_or_generate_password(self):
        ui = self.ui
        ui.study_min_var = MagicMock()
        ui.study_min_var.get.return_value = "25"
        ui.unlock_min_var = MagicMock()
        ui.unlock_min_var.get.return_value = "5"
        ui.settings_msg = MagicMock()
        ui.history = MagicMock()
        ui.game = MagicMock()
        ui._get_study_seconds = lambda: 1500
        ui._begin_studying_state = MagicMock()
        ui._send_session_code_then_start = MagicMock()
        with patch.object(ui.cfg, 'generate_random_password') as generate:
            ui._enter_studying()
        ui._begin_studying_state.assert_called_once_with(1500)
        ui._send_session_code_then_start.assert_not_called()
        generate.assert_not_called()

    def test_unprotected_stop_and_quit_require_confirmation(self):
        self.ui.state = 'studying'
        self.ui._session_protected = False
        self.ui._confirm_early_stop = MagicMock(return_value=False)
        for action in ('stop_study', 'quit_app'):
            self.assertFalse(self.ui._check_override(action))
        self.ui._confirm_early_stop.return_value = True
        self.assertTrue(self.ui._check_override('stop_study'))

    def test_protected_session_uses_code_not_legacy_mail_hash(self):
        self.ui.state = 'studying'
        self.ui._session_protected = True
        self.ui._check_password = MagicMock(return_value=False)
        self.ui.cfg.set_session_code('111111')
        self.assertFalse(self.ui._check_override('stop_study'))
        self.ui._check_password.assert_called_once_with('stop_study')

    def test_matching_code_enables_protection_and_is_persisted(self):
        with patch.object(app.simpledialog, 'askstring', side_effect=['123456', '123456']):
            self.assertTrue(self.ui._setup_protection_code())
        loaded = config.Config()
        self.assertTrue(loaded.get('protection_enabled'))
        self.assertTrue(loaded.verify_password('123456'))
        self.assertNotIn('123456', config.CONFIG_FILE.read_text())

    def test_cancel_mismatch_and_invalid_code_do_not_change_configuration(self):
        for values in ([None], ['abc'], ['123456', None], ['123456', '654321']):
            with self.subTest(values=values), patch.object(app.simpledialog, 'askstring', side_effect=values), \
                 patch.object(app.messagebox, 'showerror'):
                self.assertFalse(self.ui._setup_protection_code())
                self.assertFalse(self.ui.cfg.get('protection_enabled'))
                self.assertFalse(self.ui.cfg.has_password())

    def test_cannot_change_protection_during_study(self):
        self.ui.state = 'studying'
        with patch.object(app.messagebox, 'showinfo'), patch.object(app.simpledialog, 'askstring') as prompt:
            self.assertFalse(self.ui._setup_protection_code())
            self.ui._toggle_protection()
        prompt.assert_not_called()

    def test_disabling_protection_requires_current_code(self):
        self.ui.cfg.set('protection_enabled', True)
        self.ui.protection_var = MagicMock()
        self.ui.protection_var.get.return_value = False
        self.ui._check_password = MagicMock(return_value=False)
        self.ui._toggle_protection()
        self.assertTrue(self.ui.cfg.get('protection_enabled'))
        self.ui._check_password.return_value = True
        self.ui._toggle_protection()
        self.assertFalse(config.Config().get('protection_enabled'))


if __name__ == '__main__':
    unittest.main()
