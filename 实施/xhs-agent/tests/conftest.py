from __future__ import annotations

import os
import sys
from pathlib import Path


_ORIGINAL_MKDIR = os.mkdir
_PYTEST_SAFE_TMP_ROOT = Path("data") / "pytest_tmp_safe"


def _should_relax_windows_pytest_tmp_mode(path, mode) -> bool:
    if mode != 0o700:
        return False
    try:
        candidate = Path(path).resolve()
        safe_root = _PYTEST_SAFE_TMP_ROOT.resolve()
        return candidate == safe_root or safe_root in candidate.parents
    except (OSError, TypeError, ValueError):
        return False


def _mkdir_with_windows_safe_mode(path, mode=0o777, *args, **kwargs):
    if sys.platform == "win32" and _should_relax_windows_pytest_tmp_mode(path, mode):
        mode = 0o777
    return _ORIGINAL_MKDIR(path, mode, *args, **kwargs)


def pytest_configure(config):
    if sys.platform == "win32" and os.mkdir is _ORIGINAL_MKDIR:
        os.mkdir = _mkdir_with_windows_safe_mode


def pytest_unconfigure(config):
    if sys.platform == "win32" and os.mkdir is _mkdir_with_windows_safe_mode:
        os.mkdir = _ORIGINAL_MKDIR
