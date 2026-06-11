from __future__ import annotations

import os
import sys


_ORIGINAL_MKDIR = os.mkdir


def _mkdir_with_windows_safe_mode(path, mode=0o777, *args, **kwargs):
    if sys.platform == "win32" and mode == 0o700:
        mode = 0o777
    return _ORIGINAL_MKDIR(path, mode, *args, **kwargs)


def pytest_configure(config):
    if sys.platform == "win32" and os.mkdir is _ORIGINAL_MKDIR:
        os.mkdir = _mkdir_with_windows_safe_mode


def pytest_unconfigure(config):
    if sys.platform == "win32" and os.mkdir is _mkdir_with_windows_safe_mode:
        os.mkdir = _ORIGINAL_MKDIR
