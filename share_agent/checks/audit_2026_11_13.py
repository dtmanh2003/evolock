"""Run the regression suite replacing the original defect-reproduction script.

The original findings remain in changes/2026-11-13-codex-audit-and-launcher.md.
Success now means the corrected behavior passes, not that defects still exist.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / 'tests'), pattern='test_audit_regressions.py'
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
