from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from evolock.storage import history, config
from evolock.services import gamification
from evolock.ui.app import EvoLockApp


class ExperienceTests(unittest.TestCase):
    def test_bad_duration_never_starts_or_changes_history(self):
        for value in ('', 'abc', '0', '-1', '1.5', '1441'):
            obj = EvoLockApp.__new__(EvoLockApp)
            obj.study_min_var = MagicMock()
            obj.study_min_var.get.return_value = value
            obj.unlock_min_var = MagicMock()
            obj.unlock_min_var.get.return_value = '5'
            obj.settings_msg = MagicMock()
            obj._begin_studying_state = MagicMock()
            obj.history = MagicMock()
            obj._enter_studying()
            obj._begin_studying_state.assert_not_called()
            obj.history.settle_rewards.assert_not_called()
            self.assertTrue(obj.settings_msg.config.call_args.kwargs['text'])

    def test_legacy_screen_setting_requires_destination_consent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(config, 'CONFIG_FILE', Path(tmp)/'config.json'):
            obj = EvoLockApp.__new__(EvoLockApp)
            obj.cfg = config.Config()
            obj.cfg.set('screen_enabled', True)
            obj.blocker = MagicMock(screen_ollama_model='vision', screen_api_key='')
            obj._sync_screen_settings()
            self.assertFalse(obj.blocker.screen_enabled)
            obj.cfg.set('screen_consent_destination', 'local')
            obj._sync_screen_settings()
            self.assertTrue(obj.blocker.screen_enabled)
            obj.blocker.screen_ollama_model = ''
            obj.blocker.screen_api_key = 'test-only'
            obj._sync_screen_settings()
            self.assertFalse(obj.blocker.screen_enabled)

    def test_pending_rewards_survive_restart_without_double_credit(self):
        for failure in ('stats', 'ack'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp, \
                 patch.object(history, 'HISTORY_FILE', Path(tmp)/'history.json'), \
                 patch.object(gamification, 'STATS_FILE', Path(tmp)/'stats.json'):
                hist, game = history.HistoryManager(), gamification.GameManager()
                end = datetime.now()
                hist.log('study', end - timedelta(minutes=30), end)
                module = gamification if failure == 'stats' else history
                with patch.object(module, 'atomic_write_text', side_effect=OSError):
                    with self.assertRaises(OSError):
                        hist.settle_rewards(game)
                hist, game = history.HistoryManager(), gamification.GameManager()
                hist.settle_rewards(game)
                self.assertEqual(game.stats.total_study_minutes, 30)
                self.assertFalse(hist.sessions[0].reward_pending)
                saved_exp = game.stats.exp
                hist.settle_rewards(game)
                self.assertEqual(game.stats.exp, saved_exp)
                self.assertEqual(len(game.stats.rewarded_sessions), 1)

    def test_legacy_history_is_not_rewarded_again(self):
        session = history.Session('study', '10:00', '10:30', 30, '2026-11-15')
        self.assertFalse(session.reward_pending)
