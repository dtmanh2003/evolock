"""Bảo vệ phiên học bằng mã gửi tới Gmail (thay cho mã cục bộ tự đặt)."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from evolock.storage import config
from evolock.ui import app


class GmailProtectionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(config, 'CONFIG_FILE', Path(directory.name) / 'config.json')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ui = app.EvoLockApp.__new__(app.EvoLockApp)
        self.ui.cfg = config.Config()
        self.ui.root = MagicMock()
        self.ui.state = 'idle'
        self.ui._log = MagicMock()
        self.ui._refresh_gmail_status = MagicMock()

    def enable(self, address='parent@gmail.com'):
        self.ui.cfg.set('gmail_address', address)
        self.ui.cfg.set('gmail_protection_enabled', True)
        sender = patch.object(config.Config, 'has_gmail_configured', return_value=True)
        sender.start()
        self.addCleanup(sender.stop)

    def test_mode_needs_both_the_switch_and_a_working_sender(self):
        self.assertFalse(self.ui._gmail_mode())
        self.ui.cfg.set('gmail_protection_enabled', True)
        with patch.object(config.Config, 'has_gmail_configured', return_value=False):
            self.assertFalse(self.ui._gmail_mode())
        with patch.object(config.Config, 'has_gmail_configured', return_value=True):
            self.assertTrue(self.ui._gmail_mode())

    def test_email_is_masked_for_display(self):
        self.assertEqual(app.EvoLockApp._mask_email('parent@gmail.com'), 'pa****@gmail.com')
        self.assertEqual(app.EvoLockApp._mask_email(''), '')

    def test_starting_a_session_sends_the_code_first(self):
        self.enable()
        ui = self.ui
        ui.study_min_var = MagicMock(); ui.study_min_var.get.return_value = '25'
        ui.unlock_min_var = MagicMock(); ui.unlock_min_var.get.return_value = '5'
        ui.settings_msg = MagicMock(); ui.history = MagicMock(); ui.game = MagicMock()
        ui._get_study_seconds = lambda: 1500
        ui._begin_studying_state = MagicMock()
        ui._send_session_code_then_start = MagicMock()
        ui._enter_studying()
        ui._send_session_code_then_start.assert_called_once_with(1500)
        ui._begin_studying_state.assert_not_called()

    def test_management_actions_use_an_emailed_code(self):
        self.enable()
        self.ui._verify_emailed_code = MagicMock(return_value=True)
        self.assertTrue(self.ui._check_password('manage_blocklist'))
        self.ui._verify_emailed_code.assert_called_once_with('manage_blocklist')

    def test_correct_emailed_code_is_accepted(self):
        self.enable()
        self.ui._send_code_blocking = MagicMock(return_value=(True, ''))
        with patch.object(app.session_code, 'generate_code', return_value='123456'), \
                patch.object(app, 'ask_password', return_value=' 123456 ') as ask:
            self.assertTrue(self.ui._verify_emailed_code('manage'))
        self.assertIn('pa****@gmail.com', ask.call_args.kwargs['hint'])
        self.assertNotIn('parent@gmail.com', ask.call_args.kwargs['hint'])

    def test_wrong_code_is_rejected_after_three_tries(self):
        self.enable()
        self.ui._send_code_blocking = MagicMock(return_value=(True, ''))
        with patch.object(app.session_code, 'generate_code', return_value='123456'), \
                patch.object(app, 'ask_password', return_value='000000') as ask, \
                patch.object(app.messagebox, 'showerror') as error:
            self.assertFalse(self.ui._verify_emailed_code('manage'))
        self.assertEqual(ask.call_count, 3)
        self.assertEqual(error.call_count, 3)

    def test_cancel_and_send_failure_both_deny(self):
        self.enable()
        self.ui._send_code_blocking = MagicMock(return_value=(True, ''))
        with patch.object(app, 'ask_password', return_value=None):
            self.assertFalse(self.ui._verify_emailed_code('manage'))
        self.ui._send_code_blocking.return_value = (False, 'offline')
        with patch.object(app, 'ask_password') as ask, patch.object(app.messagebox, 'showerror') as error:
            self.assertFalse(self.ui._verify_emailed_code('manage'))
        ask.assert_not_called()
        self.assertEqual(error.call_args.args[1], 'offline')

    def test_changing_the_recipient_requires_a_code_sent_to_the_current_address(self):
        self.enable('parent@gmail.com')
        self.ui.gmail_addr_var = MagicMock(); self.ui.gmail_addr_var.get.return_value = 'child@gmail.com'
        self.ui.gmail_app_pw_var = MagicMock(); self.ui.gmail_app_pw_var.get.return_value = ''
        self.ui.oauth_client_id_var = MagicMock(); self.ui.oauth_client_id_var.get.return_value = ''
        self.ui.oauth_client_secret_var = MagicMock(); self.ui.oauth_client_secret_var.get.return_value = ''
        self.ui._test_gmail_send = MagicMock()
        self.ui._check_password = MagicMock(return_value=False)
        self.ui._save_gmail_settings()
        self.ui._check_password.assert_called_once_with('change_gmail')
        self.assertEqual(config.Config().get('gmail_address'), 'parent@gmail.com')
        self.ui._check_password.return_value = True
        self.ui._save_gmail_settings()
        self.assertEqual(config.Config().get('gmail_address'), 'child@gmail.com')

    def test_first_save_turns_protection_on_and_sends_a_test(self):
        self.ui.gmail_addr_var = MagicMock(); self.ui.gmail_addr_var.get.return_value = 'parent@gmail.com'
        self.ui.gmail_app_pw_var = MagicMock(); self.ui.gmail_app_pw_var.get.return_value = ''
        self.ui.oauth_client_id_var = MagicMock(); self.ui.oauth_client_id_var.get.return_value = ''
        self.ui.oauth_client_secret_var = MagicMock(); self.ui.oauth_client_secret_var.get.return_value = ''
        self.ui._test_gmail_send = MagicMock()
        with patch.object(config.Config, 'has_gmail_configured', return_value=True):
            self.ui._save_gmail_settings()
        self.assertTrue(config.Config().get('gmail_protection_enabled'))
        self.ui._test_gmail_send.assert_called_once()

    def test_without_a_sender_protection_stays_off(self):
        self.ui.gmail_addr_var = MagicMock(); self.ui.gmail_addr_var.get.return_value = 'parent@gmail.com'
        self.ui.gmail_app_pw_var = MagicMock(); self.ui.gmail_app_pw_var.get.return_value = ''
        self.ui.oauth_client_id_var = MagicMock(); self.ui.oauth_client_id_var.get.return_value = ''
        self.ui.oauth_client_secret_var = MagicMock(); self.ui.oauth_client_secret_var.get.return_value = ''
        self.ui._test_gmail_send = MagicMock()
        with patch.object(config.Config, 'has_gmail_configured', return_value=False):
            self.ui._save_gmail_settings()
        self.assertFalse(config.Config().get('gmail_protection_enabled'))
        self.ui._test_gmail_send.assert_not_called()

    def test_turning_protection_off_requires_a_code(self):
        self.enable()
        self.ui.gmail_addr_var = MagicMock()
        self.ui._check_password = MagicMock(return_value=False)
        self.ui._clear_gmail_settings()
        self.assertTrue(config.Config().get('gmail_protection_enabled'))
        self.ui._check_password.return_value = True
        self.ui._clear_gmail_settings()
        saved = config.Config()
        self.assertFalse(saved.get('gmail_protection_enabled'))
        self.assertEqual(saved.get('gmail_address'), '')

    def test_protection_cannot_be_removed_during_a_session(self):
        self.enable()
        self.ui.state = 'studying'
        self.ui._check_password = MagicMock()
        with patch.object(app.messagebox, 'showinfo'):
            self.ui._clear_gmail_settings()
        self.ui._check_password.assert_not_called()
        self.assertTrue(config.Config().get('gmail_protection_enabled'))

    def test_send_failure_can_start_without_protection_and_drops_old_code(self):
        self.enable()
        self.ui.cfg.set_session_code('111111')
        self.ui._ask_send_failed = MagicMock(return_value='unprotected')
        self.ui._begin_studying_state = MagicMock()
        dialog = MagicMock()
        self.ui._on_session_code_sent(False, 'offline', '222222', 1500, dialog)
        self.ui._begin_studying_state.assert_called_once_with(1500)
        self.assertFalse(self.ui._has_session_code())

    def test_send_failure_cancel_does_not_start(self):
        self.enable()
        self.ui._ask_send_failed = MagicMock(return_value='cancel')
        self.ui._begin_studying_state = MagicMock()
        self.ui._on_session_code_sent(False, 'offline', '222222', 1500, MagicMock())
        self.ui._begin_studying_state.assert_not_called()

    def test_stopping_early_needs_the_code_that_was_emailed(self):
        self.enable()
        ui = self.ui
        ui.state = 'studying'
        ui._session_protected = True
        ui._study_started_at = None
        ui._get_study_seconds = lambda: 1500
        ui.override_log = MagicMock()
        ui.cfg.set_session_code('654321')
        with patch.object(app, 'ask_override',
                          return_value={'reason': '急用', 'note': '', 'code': '000000'}), \
                patch.object(app.messagebox, 'showerror'):
            self.assertFalse(ui._check_override('stop_study'))
        self.assertTrue(ui._has_session_code())
        ui.override_log.log.assert_not_called()
        with patch.object(app, 'ask_override',
                          return_value={'reason': '急用', 'note': '', 'code': '654321'}):
            self.assertTrue(ui._check_override('stop_study'))
        ui.override_log.log.assert_called_once()
        self.assertFalse(ui._has_session_code())


if __name__ == '__main__':
    unittest.main()
