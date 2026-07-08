"""Fuzz-suite test configuration.

* Makes the backend package root importable when the suite is run directly
  (e.g. ``pytest fuzz``), mirroring how ``backend/tests`` resolves
  ``from services... import ...``.
* Registers Hypothesis profiles so the example budget can be scaled up in CI
  (``HYPOTHESIS_PROFILE=ci``) without slowing local runs. Guarded so this
  conftest still imports cleanly in the primary test job, which does not install
  Hypothesis (the property tests ``importorskip`` it and are skipped there).
"""

import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

try:  # pragma: no cover - depends on whether Hypothesis is installed
    from hypothesis import settings

    _ci_examples = int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", "1000"))
    settings.register_profile("dev", max_examples=50, deadline=None)
    settings.register_profile("ci", max_examples=_ci_examples, deadline=None)
    settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
except Exception:  # noqa: BLE001 - Hypothesis absent in the primary test job
    pass
