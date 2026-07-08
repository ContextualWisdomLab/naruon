"""Ensure the backend package root is importable when the fuzz suite is run
directly (e.g. ``pytest fuzz``), mirroring how ``backend/tests`` resolves
``from services... import ...``.
"""

import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
