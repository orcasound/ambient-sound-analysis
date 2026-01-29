"""
Pytest configuration.

This repo uses a `src/` layout. Adding `src/` to `sys.path` allows running tests
without requiring an editable install (`pip install -e .`).
"""

import os
import sys


_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.path.join(_REPO_ROOT, "src")

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

