"""P3 — build-lane adaptation: a model that won't emit a structured plan gets a
downgrade retry, an actionable error naming the reliable model, and its failure
is LEARNED. A capable model is recorded ok. No silent model swap. See
docs/plans/2026-07-06-stress-test-remediation.md."""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(os.path.dirname(_HERE), "bin", "ambient")


def _load_module():
    loader = importlib.machinery.SourceFileLoader("ambient_cli_build_adaptive", _BIN)
    spec = importlib.util.spec_from_loader("ambient_cli_build_adaptive", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


amb = _load_module()
KEY = "sk-test-key-abcdef1234567890"


@contextlib.contextmanager
def _patched(**attrs):
    old = {}
    missing = object()
    for k, v in attrs.items():
        old[k] = getattr(amb, k, missing)
        setattr(amb, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is missing:
                delattr(amb, k)
            else:
                setattr(amb, k, v)


def _catalog(mid):
    return lambda *a, **k: [
        {"id": mid, "context_length": 200000, "max_output_length": 200000,
         "is_ready": True, "supported_features": ["reasoning", "structured_outputs"],
         "output_modalities": ["text"], "pricing": {"input": 1.0, "output": 4.0}}]


def _build_args(model, d):
    return argparse.Namespace(
        model=model, task=["a", "tiny", "tool"], context=None, dir=d,
        apply=False, dry_run=False, plan_only=True, no_resume=True,
        max_files=20, max_file_bytes=200_000, max_tokens=None, temperature=0.1,
        timeout=30, raw=False, json=True, fallback=False, allow_partial=False,
        allow_secrets=False, allow_cost=True, yes=True, no_cache=True,
        cache_ttl=None, parallel=None, system=None, response_format=None)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(amb, "CAPABILITY_PATH", str(tmp_path / "caps.json"))
    monkeypatch.setattr(amb, "_CAP_CACHE", None)
    monkeypatch.delenv("AMBIENT_TELEMETRY", raising=False)
    yield
    monkeypatch.setattr(amb, "_CAP_CACHE", None)


def _run_build(model, complete_fn):
    d = tempfile.mkdtemp()
    args = _build_args(model, d)
    buf = io.StringIO()
    exit_code = None
    with _patched(safe_catalog=_catalog(model), cost_gate=lambda *a, **k: None,
                  complete=complete_fn), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        try:
            amb.cmd_build(args, KEY, "https://x", {})
        except SystemExit as e:
            exit_code = e.code
    return buf.getvalue(), exit_code


# --- downgrade helper ------------------------------------------------------
def test_downgrade_ladder_steps_down():
    class P:
        features = ["structured_outputs", "json_mode"]
    schema_rf = {"type": "json_schema", "json_schema": {"schema": {}}}
    step1 = amb.downgrade_response_format(schema_rf, P())
    assert step1 == {"type": "json_object"}          # schema -> json_object
    assert amb.downgrade_response_format(step1, P()) is None  # json_object -> None

    class P2:
        features = ["structured_outputs"]             # no json_mode
    assert amb.downgrade_response_format(schema_rf, P2()) is None  # straight to prompt-only


# --- build fails on a model that won't emit a plan -------------------------
def test_unparseable_plan_downgrades_then_errors_naming_reliable_model():
    calls = []

    def prose_only(api_key, api_url, model, messages, args, **kw):
        calls.append(getattr(args, "response_format", None))
        return ("I would create a file called tool.py that does the thing.", {}, {})

    out, code = _run_build("stubborn/model", prose_only)
    assert code == 1
    # it retried with a DIFFERENT (downgraded) response_format, not the same one
    assert len(calls) == 2 and calls[0] != calls[1]
    env = json.loads(out)
    assert env["kind"] == "build" and env["status"] == "error"
    assert env["category"] == "model"
    assert amb.DEFAULT_CODE_MODEL in env["diagnosis"]   # names the reliable model


def test_build_failure_is_learned():
    def prose_only(api_key, api_url, model, messages, args, **kw):
        return ("nope, just prose here", {}, {})

    _run_build("stubborn/model", prose_only)
    assert amb.cap_state("stubborn/model", "build_plan") != "ok"
    _run_build("stubborn/model", prose_only)  # second failure => unreliable
    assert amb.cap_state("stubborn/model", "build_plan") == "unreliable"


def test_valid_plan_is_recorded_ok():
    plan = json.dumps({"plan": [{"path": "tool.py", "purpose": "does the thing"}]})

    def good_plan(api_key, api_url, model, messages, args, **kw):
        return (plan, {}, {})

    _run_build("capable/model", good_plan)
    assert amb.cap_state("capable/model", "build_plan") == "ok"


def test_learned_unreliable_model_announces_but_does_not_swap():
    def prose_only(api_key, api_url, model, messages, args, **kw):
        return ("prose, no json", {}, {})

    # teach it unreliable
    for _ in range(amb.CAP_FAIL_THRESHOLD):
        _run_build("stubborn/model", prose_only)
    assert amb.cap_state("stubborn/model", "build_plan") == "unreliable"

    seen_models = []

    def track_model(api_key, api_url, model, messages, args, **kw):
        seen_models.append(model)
        return ("prose, no json", {}, {})

    out, _ = _run_build("stubborn/model", track_model)
    # the user's model is still the one called — NO silent swap
    assert set(seen_models) == {"stubborn/model"}
