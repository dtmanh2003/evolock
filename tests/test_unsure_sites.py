"""AI không chắc -> không chặn, ghi danh sách chờ; nhãn của phụ huynh được ưu tiên hơn AI."""

import json
import tempfile
from datetime import datetime
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from evolock.services import blocker
from evolock.storage import site_labels
from evolock.storage.json_file import DataFileError


class SiteKeyTests(unittest.TestCase):
    def test_site_name_is_taken_from_the_end_of_the_title(self):
        self.assertEqual(blocker.site_key("Python list - Stack Overflow - Google Chrome"), "stack overflow")

    def test_youtube_channel_is_used_and_generic_youtube_is_not_merged(self):
        self.assertEqual(blocker.site_key("Funny - SomeChannel - YouTube - Google Chrome"), "youtube:somechannel")
        self.assertNotEqual(blocker.site_key("Lofi hip hop radio - YouTube"), "youtube")

    def test_plain_title_is_used_whole_and_empty_is_safe(self):
        self.assertEqual(blocker.site_key("Facebook"), "facebook")
        self.assertEqual(blocker.site_key(""), "")


class SiteLabelsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "site_labels.json"
        patcher = patch.object(site_labels, "LABELS_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_pending_is_recorded_once_and_survives_restart(self):
        store = site_labels.SiteLabels()
        self.assertTrue(store.add_pending("lofi", "Lofi radio"))
        self.assertFalse(store.add_pending("lofi", "Lofi radio"))
        self.assertEqual(site_labels.SiteLabels().pending_items(), [("lofi", "Lofi radio", 1)])
        store.add_pending("lofi", "Lofi radio")
        self.assertEqual(store.pending_items()[0][2], 3)  # đếm số lần gặp (3 lần ghi)

    def test_labelling_moves_the_site_out_of_pending(self):
        store = site_labels.SiteLabels()
        store.add_pending("lofi", "Lofi radio")
        store.set_label("lofi", "study")
        self.assertEqual(store.pending_items(), [])
        self.assertEqual(site_labels.SiteLabels().label_for("lofi"), "study")
        self.assertFalse(store.add_pending("lofi", "Lofi radio"))  # đã có nhãn thì không hỏi lại
        store.remove_label("lofi")
        self.assertIsNone(site_labels.SiteLabels().label_for("lofi"))

    def test_invalid_label_is_rejected_and_pending_is_capped(self):
        store = site_labels.SiteLabels()
        with self.assertRaises(ValueError):
            store.set_label("x", "maybe")
        for index in range(site_labels.MAX_PENDING + 10):
            store.add_pending(f"site{index}", "t")
        self.assertEqual(len(store.pending_items()), site_labels.MAX_PENDING)

    def test_old_pending_sites_expire_but_saved_decisions_stay(self):
        self.path.write_text(json.dumps({
            "labels": {"stack overflow": "study"},
            "pending": {"old": {"title": "Old", "last": "2020-01-01T00:00:00", "count": 1},
                        "new": {"title": "New", "last": datetime.now().isoformat(timespec="seconds"),
                                "count": 1}}}), encoding="utf-8")
        store = site_labels.SiteLabels()
        self.assertEqual([k for k, _, _ in store.pending_items()], ["new"])
        self.assertEqual(store.label_for("stack overflow"), "study")

    def test_corrupt_file_is_reported_not_reset(self):
        self.path.write_text('{"labels": {"a": "maybe"}}', encoding="utf-8")
        with self.assertRaises(DataFileError):
            site_labels.SiteLabels()


def fake_blocker(labels):
    obj = blocker.Blocker.__new__(blocker.Blocker)
    obj.running = True
    obj._lock = threading.Lock()
    obj._stop_event = threading.Event()
    obj._thread = None
    obj._cached_blocked = ["chrome.exe"]
    obj.smart_enabled = True
    obj.screen_enabled = False
    obj.screen_ollama_model = ""
    obj.screen_api_key = ""
    obj.screen = MagicMock(consecutive_errors=0, verdict="ok")
    obj.smart = MagicMock(ready=True)
    obj.whitelist = MagicMock()
    obj.whitelist.is_whitelisted.return_value = False
    obj.labels = labels
    obj.on_kill_callback = MagicMock()
    obj.on_allow_callback = MagicMock()
    obj._title_laziness = {}
    return obj


class UnsureBlockingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(site_labels, "LABELS_FILE", Path(directory.name) / "site_labels.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.labels = site_labels.SiteLabels()

    def scan(self, obj, title, scans=1):
        process = MagicMock(info={"name": "chrome.exe", "pid": 7})
        for _ in range(scans):
            event = obj._stop_event
            with patch.object(blocker, "get_pid_to_title", return_value={7: title}), \
                 patch.object(blocker.psutil, "process_iter", return_value=[process]), \
                 patch.object(event, "wait", side_effect=lambda _: event.set()):
                obj._loop(event)
            obj._stop_event = threading.Event()
        return process

    def test_unsure_title_is_not_killed_and_is_queued_for_the_parent(self):
        obj = fake_blocker(self.labels)
        obj.smart.is_study.return_value = (True, 0.38, 0.36)  # chênh < UNSURE_MARGIN
        process = self.scan(obj, "Lofi hip hop radio - YouTube", scans=5)
        process.kill.assert_not_called()
        self.assertEqual(len(self.labels.pending_items()), 1)
        layers = [item[2] for call in obj.on_allow_callback.call_args_list for item in call.args[0]]
        self.assertEqual(layers.count("unsure"), 1)  # chỉ báo một lần, không báo mỗi lần quét

    def test_clear_entertainment_is_still_killed_after_repeated_scans(self):
        obj = fake_blocker(self.labels)
        obj.smart.is_study.return_value = (False, 0.1, 0.6)
        process = self.scan(obj, "Minecraft funny moments - YouTube", scans=4)
        process.kill.assert_called()
        self.assertEqual(self.labels.pending_items(), [])

    def test_parent_label_overrides_the_ai(self):
        obj = fake_blocker(self.labels)
        obj.smart.is_study.return_value = (False, 0.1, 0.6)  # AI nói giải trí
        self.labels.set_label(blocker.site_key("Algebra - Khan Academy"), "study")
        process = self.scan(obj, "Algebra - Khan Academy", scans=4)
        process.kill.assert_not_called()
        obj.smart.is_study.assert_not_called()

        obj2 = fake_blocker(self.labels)
        obj2.smart.is_study.return_value = (True, 0.6, 0.1)  # AI nói học
        self.labels.set_label(blocker.site_key("Funny Cats - Meme Site"), "block")
        process2 = self.scan(obj2, "Funny Cats - Meme Site", scans=4)
        process2.kill.assert_called()


if __name__ == "__main__":
    unittest.main()
