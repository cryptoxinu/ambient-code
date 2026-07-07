"""P6 — polish batch: F05a (unknown-model classification), F05b (near-duplicate
finding merge), F05d (savings receipt under --json), F04 (catalog count
consistency). See docs/plans/2026-07-06-stress-test-remediation.md."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(os.path.dirname(_HERE), "bin", "ambient")


def _load_module():
    loader = importlib.machinery.SourceFileLoader("ambient_cli_polish", _BIN)
    spec = importlib.util.spec_from_loader("ambient_cli_polish", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


amb = _load_module()


# --- F05a: a mistyped -m is a MODEL error, not opaque 'unknown' -----------
def test_unknown_model_400_classifies_as_model():
    body = json.dumps({"error": {"message": "Unknown model: 'foo/bar'"}})
    cat, diag = amb.classify_error(400, body, "")
    assert cat == "model"
    assert "ambient models" in diag


def test_other_400_still_unknown():
    cat, _ = amb.classify_error(400, json.dumps({"error": {"message": "weird"}}), "")
    assert cat == "unknown"


# --- F05b: the same bug phrased two ways merges --------------------------
def test_reworded_same_bug_merges():
    a = ("top_k", "returns", "one", "fewer")
    b = ("top_k", "returns", "k", "1")
    assert amb._titles_match(a, b) is True


def test_distinct_bugs_stay_separate():
    assert amb._titles_match(("missing", "null", "check"),
                             ("missing", "rate", "limit")) is False


def test_dedupe_merges_reworded_duplicate_on_same_line():
    findings = [
        {"severity": "HIGH", "file": "s.py", "line": 10,
         "title": "top_k returns one fewer element", "scenario": "x"},
        {"severity": "HIGH", "file": "s.py", "line": 10,
         "title": "top_k returns k-1 elements instead of k", "scenario": "yy"},
    ]
    assert len(amb.dedupe_findings(findings)) == 1


# --- F05d: savings receipt appears on stderr in --json mode --------------
def test_json_emits_savings_receipt_on_stderr():
    err = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        amb.emit_json("ask", model="z-ai/glm-5.2", api_key="", content="hi",
                      usage={"prompt_tokens": 10, "completion_tokens": 5},
                      exit_now=False)
    # stdout is clean JSON; the receipt rode stderr
    json.loads(out.getvalue())
    assert "[ambient z-ai/glm-5.2" in err.getvalue()


def test_json_without_usage_has_no_receipt():
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        amb.emit_json("ask", model="z-ai/glm-5.2", api_key="", content="hi",
                      exit_now=False)
    assert "[ambient" not in err.getvalue()


# --- F04: catalog count is consistent across surfaces --------------------
def test_alias_id_deduped_from_count():
    ids = ["ambient/large", "zai-org/GLM-5.1-FP8", "moonshotai/kimi-k2.7-code"]
    deduped = amb._dedupe_catalog_ids(ids)
    assert "zai-org/GLM-5.1-FP8" not in deduped
    assert len(deduped) == 2


def test_alias_kept_when_primary_absent():
    ids = ["zai-org/GLM-5.1-FP8", "moonshotai/kimi-k2.7-code"]
    assert "zai-org/GLM-5.1-FP8" in amb._dedupe_catalog_ids(ids)
