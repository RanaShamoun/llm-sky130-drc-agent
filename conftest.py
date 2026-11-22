"""Test harness compatibility for Windows temp-directory cleanup.

Pytest on Windows may raise PermissionError while resolving a stale symlink in the
temporary directory created for test fixtures. That cleanup failure happens after
all tests complete and does not reflect a product bug; swallow only this cleanup
error so the suite can report the real pass/fail status.
"""

from __future__ import annotations

import _pytest.pathlib as pytest_pathlib


_original_cleanup_dead_symlinks = pytest_pathlib.cleanup_dead_symlinks


def _safe_cleanup_dead_symlinks(root):
    try:
        return _original_cleanup_dead_symlinks(root)
    except OSError:
        # Windows can deny access while resolving stale temp symlinks during
        # pytest teardown; the test results are already complete at this point.
        return None


pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
