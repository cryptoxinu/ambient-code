"""Regression tests for the v1.0.1 backlog remediation (best-of-3 audit
MED/LOW findings, each independently verified). Phases appended as they land.

No network, no live API. Run: python3 -m pytest tests/test_v101_backlog_fixes.py
"""
import importlib.machinery
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "ambient")


def load_module():
    loader = importlib.machinery.SourceFileLoader("ambient_cli_v101", BIN)
    spec = importlib.util.spec_from_loader("ambient_cli_v101", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


amb = load_module()
KEY = "sk-abcdef1234567890XY"   # 20 chars, key-shaped


# ------------------------------------------------- Phase 1: security/redaction

class TestM16RedactOrder(unittest.TestCase):
    """M16: sanitize BEFORE key-replace so an escape-split key reassembles and
    is then redacted (raw-substring-first would miss it)."""

    def test_escape_split_key_is_redacted(self):
        poisoned = KEY[:6] + "\x1b[0m" + KEY[6:]   # ESC sequence inside the key
        out = amb.redact(poisoned, KEY)
        self.assertNotIn(KEY, out)
        self.assertIn("[AMBIENT_API_KEY]", out)

    def test_c1_split_key_is_redacted(self):
        poisoned = KEY[:8] + "\x9b" + KEY[8:]       # C1 CSI splitter
        self.assertNotIn(KEY, amb.redact(poisoned, KEY))

    def test_plain_text_unchanged(self):
        self.assertEqual(amb.redact("the quick brown fox", KEY),
                         "the quick brown fox")


class TestM43StreamRedactor(unittest.TestCase):
    """M43: a key split across streaming chunk boundaries must never reach the
    terminal — the stateful redactor holds a rolling tail and redacts complete
    keys anywhere in the buffer."""

    def _run(self, pieces):
        sr = amb._StreamRedactor(KEY)
        return "".join(sr.feed(p) for p in pieces) + sr.flush()

    def test_no_boundary_split_leaks_the_key(self):
        full = "hello " + KEY + " world"
        for cut in range(1, len(full)):
            out = self._run([full[:cut], full[cut:]])
            self.assertNotIn(KEY, out, f"leaked at cut={cut}")

    def test_three_way_split_through_key(self):
        out = self._run(["x" + KEY[:4], KEY[4:12], KEY[12:] + "y"])
        self.assertNotIn(KEY, out)

    def test_escape_split_across_feeds(self):
        out = self._run([KEY[:6], "\x1b[0m", KEY[6:]])
        self.assertNotIn(KEY, out)

    def test_normal_stream_passes_through_intact(self):
        self.assertEqual(self._run(["the quick ", "brown fox"]),
                         "the quick brown fox")

    def test_no_key_still_sanitizes(self):
        sr = amb._StreamRedactor("")
        out = "".join(sr.feed(p) for p in ["a\x1b[31m", "b\x9dc"]) + sr.flush()
        self.assertEqual(out, "abc")

    def test_streamed_equals_redact_of_whole_at_every_split(self):
        # The strong invariant: however the provider chunks the bytes, the
        # streamed output is byte-identical to redacting the full text at once
        # (covers escape-in-key splits — Codex's HIGH repro).
        raws = ["hi " + KEY[:5] + "\x1b[0m" + KEY[5:] + " bye",
                "x" + KEY + "y", "a" + KEY + "b" + KEY + "c",
                "plain \x1b[31mred\x1b[0m no key"]
        for raw in raws:
            for i in range(1, len(raw)):
                self.assertEqual(self._run([raw[:i], raw[i:]]),
                                 amb.redact(raw, KEY), f"2-way i={i} raw={raw!r}")
                for j in range(i + 1, len(raw)):
                    self.assertEqual(
                        self._run([raw[:i], raw[i:j], raw[j:]]),
                        amb.redact(raw, KEY), f"3-way {i},{j} raw={raw!r}")


# -------------------------------------------------- Phase 2: crash-hardening

class TestPhase2Hardening(unittest.TestCase):
    def test_M30_as_bool_rejects_false_string(self):
        self.assertFalse(amb._as_bool("false"))
        self.assertFalse(amb._as_bool("0"))
        self.assertFalse(amb._as_bool(""))
        self.assertTrue(amb._as_bool("true"))
        self.assertTrue(amb._as_bool(True))
        self.assertFalse(amb._as_bool(False))

    def test_M30_ready_model_ids_skips_false_string(self):
        cat = [{"id": "a", "is_ready": "false"}, {"id": "b", "is_ready": True},
               {"id": "c", "is_ready": "true"}]
        self.assertEqual(amb.ready_model_ids(cat), ["b", "c"])

    def test_M29_fetch_models_tolerates_non_dict_body(self):
        # body is a list/str/None instead of an object → [] not a crash
        for body in ([], "oops", None, 42):
            with _patch(amb, "api_request", lambda *a, **k: (200, body)):
                self.assertEqual(amb.fetch_models("https://x", "k"), [])

    def test_L12_run_map_reduce_empty_chunks(self):
        self.assertEqual(
            amb.run_map_reduce("k", "u", "m", "sys", [], None, "syn", 1000),
            ("", False, "no input"))


import contextlib


@contextlib.contextmanager
def _patch(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


if __name__ == "__main__":
    unittest.main()
