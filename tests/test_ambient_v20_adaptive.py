"""P1 — adaptive capability core: learn per-model behavior from real outcomes,
recover on later success, honor AMBIENT_TELEMETRY=off. See
docs/plans/2026-07-06-stress-test-remediation.md."""
import importlib.machinery
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(os.path.dirname(_HERE), "bin", "ambient")


def _load_module():
    loader = importlib.machinery.SourceFileLoader("ambient_cli_adaptive", _BIN)
    spec = importlib.util.spec_from_loader("ambient_cli_adaptive", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


amb = _load_module()


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Point the capability store at a temp file and reset the process memo so
    each test starts from a clean, isolated store."""
    store = tmp_path / "capabilities.json"
    monkeypatch.setattr(amb, "CAPABILITY_PATH", str(store))
    monkeypatch.setattr(amb, "_CAP_CACHE", None)
    monkeypatch.delenv("AMBIENT_TELEMETRY", raising=False)
    yield store
    monkeypatch.setattr(amb, "_CAP_CACHE", None)


def test_unknown_before_any_history():
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unknown"


def test_becomes_unreliable_after_repeated_failures():
    for _ in range(amb.CAP_FAIL_THRESHOLD):
        amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unreliable"


def test_single_failure_is_not_yet_unreliable():
    amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") != "unreliable"


def test_recovers_to_ok_on_later_success():
    for _ in range(amb.CAP_FAIL_THRESHOLD + 1):
        amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unreliable"
    amb.record_cap("z-ai/glm-5.2", "structured_json", True)  # model improved
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "ok"


def test_dimensions_are_independent():
    for _ in range(amb.CAP_FAIL_THRESHOLD):
        amb.record_cap("z-ai/glm-5.2", "build_plan", False)
    assert amb.cap_state("z-ai/glm-5.2", "build_plan") == "unreliable"
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unknown"


def test_models_are_independent():
    for _ in range(amb.CAP_FAIL_THRESHOLD):
        amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    assert amb.cap_state("moonshotai/kimi-k2.7-code", "structured_json") == "unknown"


def test_persists_across_process_memo_reset(_isolate, monkeypatch):
    for _ in range(amb.CAP_FAIL_THRESHOLD):
        amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    assert os.path.exists(str(_isolate))
    monkeypatch.setattr(amb, "_CAP_CACHE", None)  # simulate a fresh process
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unreliable"


def test_telemetry_off_disables_learning(monkeypatch):
    monkeypatch.setenv("AMBIENT_TELEMETRY", "off")
    monkeypatch.setattr(amb, "_CAP_CACHE", None)
    for _ in range(amb.CAP_FAIL_THRESHOLD + 2):
        amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unknown"


def test_corrupt_store_is_not_fatal(_isolate, monkeypatch):
    _isolate.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(amb, "_CAP_CACHE", None)
    assert amb.cap_state("z-ai/glm-5.2", "structured_json") == "unknown"
    amb.record_cap("z-ai/glm-5.2", "structured_json", False)  # must not raise


def test_store_written_0600(_isolate):
    amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    mode = os.stat(str(_isolate)).st_mode & 0o777
    assert mode == 0o600


def test_adaptive_response_format_skips_schema_when_unreliable(monkeypatch):
    class _Prof:
        features = ["structured_outputs"]
    monkeypatch.setattr(amb, "_CAP_CACHE", None)
    for _ in range(amb.CAP_FAIL_THRESHOLD):
        amb.record_cap("z-ai/glm-5.2", "structured_json", False)
    # unreliable => no response_format (go straight to prose+parser)
    assert amb.adaptive_response_format("z-ai/glm-5.2", _Prof(), {"type": "object"}) is None
    # a capable/unknown model still gets the strict schema (optimistic)
    rf = amb.adaptive_response_format("moonshotai/kimi-k2.7-code", _Prof(), {"type": "object"})
    assert rf and rf.get("type") == "json_schema"
