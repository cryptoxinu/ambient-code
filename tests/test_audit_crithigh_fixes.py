"""Regression tests for the CRIT/HIGH audit-remediation batch (2026-07-06).

Each test locks in a fix for a finding CONFIRMED by independent verification of
the best-of-3 self-audit. Phases are appended as they land.

No network, no live API. Run: python3 -m pytest tests/test_audit_crithigh_fixes.py
"""
import importlib.machinery
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "ambient")


def load_module():
    loader = importlib.machinery.SourceFileLoader("ambient_cli_crithigh", BIN)
    spec = importlib.util.spec_from_loader("ambient_cli_crithigh", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


amb = load_module()


# ---------------------------------------------------------- Phase 1: security

class TestA3StripsC1Controls(unittest.TestCase):
    """A3: the terminal-injection filter must strip C1 controls (0x80-0x9f)
    too — some terminals treat 0x9b/0x9d as CSI/OSC introducers."""

    def test_c1_controls_stripped(self):
        for c in ("\x80", "\x9b", "\x9d", "\x9f"):
            self.assertNotIn(c, amb.redact(f"a{c}b", ""))

    def test_tab_and_newline_still_kept(self):
        self.assertEqual(amb.redact("a\tb\nc", ""), "a\tb\nc")

    def test_cr_still_stripped(self):  # from the earlier F1 fix
        self.assertNotIn("\r", amb.redact("a\rb", ""))


class TestA12SanitizesCatalogStrings(unittest.TestCase):
    """A12: network-derived catalog model IDs / names must be sanitized before
    they reach the terminal."""

    def test_sanitize_strips_escapes(self):
        self.assertEqual(amb.sanitize("a\x1b[31m\x9bred"), "ared")

    def test_sanitize_handles_non_str(self):
        self.assertEqual(amb.sanitize(12345), "12345")
        self.assertIsNone(amb.sanitize(None))

    def test_format_model_line_has_no_escapes_for_malicious_id(self):
        m = {"id": "evil\x1b[2J\x9dhttp://x", "name": "n\x1b[31m",
             "context_length": 1000, "is_ready": True}
        line = amb.format_model_line(m, "chat/x", "code/x", note="no\x1bte")
        self.assertNotIn("\x1b", line)
        self.assertNotIn("\x9d", line)


class TestA2InsecureBypassLoopbackOnly(unittest.TestCase):
    """A2: AMBIENT_ALLOW_INSECURE may bypass host-pinning ONLY for a loopback
    host — never a private-LAN/link-local/public host."""

    def test_loopback_allowed(self):
        for h in ("127.0.0.1", "localhost", "::1", "dev.localhost", "127.5.5.5"):
            self.assertTrue(amb._is_local_host(h), h)

    def test_non_loopback_rejected(self):
        for h in ("192.168.1.5", "10.0.0.1", "169.254.1.1", "0.0.0.0",
                  "172.16.0.1", "evil.com", "api.ambient.xyz.evil.com", ""):
            self.assertFalse(amb._is_local_host(h), h)


if __name__ == "__main__":
    unittest.main()
