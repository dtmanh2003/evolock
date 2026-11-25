"""Shared paths, resolved from the source tree rather than the working directory."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
MASCOT_FRAMES_DIR = ASSETS_DIR / "mascot_frames"

DATA_DIR.mkdir(parents=True, exist_ok=True)
