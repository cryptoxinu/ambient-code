"""Test-suite hermeticity guard (v3 Phase 8a).

The telemetry-EWMA routing learns each model's observed chars-per-token from
the REAL user ledger (~/.config/ambient/usage.jsonl). Exact-value estimation
tests would silently start depending on whatever history the developer's
machine has accumulated — so the suite defaults telemetry OFF at import time
(before any test module loads bin/ambient). Telemetry tests that exercise the
feature opt back in explicitly by patching the environment.
"""
import os

os.environ.setdefault("AMBIENT_TELEMETRY", "off")
