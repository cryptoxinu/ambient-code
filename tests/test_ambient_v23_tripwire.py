"""P4 — credential tripwire hardening (F02, security, deterministic). A sensitive
keyword embedded in an ALL-CAPS env identifier before '='/':' with a high-entropy
value must be caught, even in an arbitrarily-named file. False positives (public
keys, short values) must NOT trip. Linear-time (no ReDoS). See
docs/plans/2026-07-06-stress-test-remediation.md."""
import importlib.machinery
import importlib.util
import os
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(os.path.dirname(_HERE), "bin", "ambient")


def _load_module():
    loader = importlib.machinery.SourceFileLoader("ambient_cli_tripwire", _BIN)
    spec = importlib.util.spec_from_loader("ambient_cli_tripwire", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


amb = _load_module()

_HI = "aQ7pR2xL9mZ4kT8vB1nC6wY3jD5sF0hG7uE2iO4a"  # 40 synthetic high-entropy chars


# --- the gap the stress test found: caught now, any filename -------------
@pytest.mark.parametrize("line", [
    f"AWS_SECRET_ACCESS_KEY={_HI}",
    f"DB_PASSWORD={_HI}",
    f"GITHUB_TOKEN={_HI}",
    f"export API_SECRET={_HI}",
    f"MY_APP_ACCESS_TOKEN = {_HI}",
    f'STRIPE_SECRET_KEY="{_HI}"',
    f"SERVICE_CREDENTIAL: {_HI}",
])
def test_env_secret_assignment_is_detected(line):
    assert amb._line_has_secret(line) is True


# --- false positives that must NOT trip ----------------------------------
@pytest.mark.parametrize("line", [
    f"PUBLIC_KEY={_HI}",            # a public key is not a secret
    f"RSA_PUBLIC_KEY={_HI}",
    "API_KEY=short",               # value too short / low entropy
    "MY_KEY=1",
    "SOME_TOKEN=todo",
    "def make_key(name):",         # not an assignment at all
    "the secret sauce is love",    # prose
])
def test_benign_lines_do_not_trip(line):
    assert amb._line_has_secret(line) is False


# --- Codex-found bypasses (must all be caught now) -----------------------
@pytest.mark.parametrize("line", [
    '{"secret": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"}',   # base64 / and +
    "DB_PASSWORD='p@ssw0rd-rotated-2026!'",                     # punctuated pw
    "REDIS_PASSWORD=prod-7k9!",                                 # short pw
    "NEXT_PUBLIC_AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG+bPxRfiCY",  # PUBLIC substring abuse
    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI\\",                    # backslash continuation (line 1)
])
def test_codex_bypasses_now_caught(line):
    assert amb._line_has_secret(line) is True


def test_real_public_key_still_excluded():
    # a genuine *_PUBLIC_KEY trailing component is still not a secret
    assert amb._line_has_secret(f"RSA_PUBLIC_KEY={_HI}") is False
    assert amb._line_has_secret(f"PUBLIC_KEY={_HI}") is False


def test_double_gutter_bypass_blocked(capsys):
    # attacker embeds a fake gutter so a single strip leaves "12| SECRET=…"
    chunks = [("x.txt", f"   1| 12| AWS_SECRET_ACCESS_KEY={_HI}\n")]
    with pytest.raises(SystemExit) as ei:
        amb.refuse_if_secrets(chunks, allow=False)
    assert "x.txt" in (str(ei.value.code) + capsys.readouterr().err)


# --- existing patterns still work (no regression) ------------------------
def test_existing_patterns_still_detected():
    assert amb._line_has_secret("api_key: 'abcdef1234567890XYZ'") is True
    assert amb._line_has_secret("AKIA1234567890ABCDEF") is True
    assert amb._line_has_secret("password = supersecret_value_123") is True


# --- refuse_if_secrets integration: creds.txt is now blocked -------------
def test_refuse_if_secrets_blocks_creds_txt(capsys):
    chunks = [("creds.txt", f"AWS_SECRET_ACCESS_KEY={_HI}\n")]
    with pytest.raises(SystemExit) as ei:
        amb.refuse_if_secrets(chunks, allow=False)
    # exit_code==1 exits with the prose message AS the SystemExit arg
    msg = str(ei.value.code) + capsys.readouterr().err
    assert "creds.txt" in msg
    assert "secrets" in msg.lower()


def test_refuse_if_secrets_blocks_gutter_prefixed_content(capsys):
    # Audit inputs are line-number-guttered BEFORE the tripwire — the exact
    # presentation that let creds.txt through live. Must still be caught.
    chunks = [("creds.txt", f"   1| AWS_SECRET_ACCESS_KEY={_HI}\n   2| ok\n")]
    with pytest.raises(SystemExit) as ei:
        amb.refuse_if_secrets(chunks, allow=False)
    msg = str(ei.value.code) + capsys.readouterr().err
    assert "creds.txt:1" in msg  # reports the true absolute (gutter) line


def test_allow_secrets_bypasses():
    chunks = [("creds.txt", f"AWS_SECRET_ACCESS_KEY={_HI}\n")]
    amb.refuse_if_secrets(chunks, allow=True)  # must NOT raise


# --- ReDoS: the new pattern stays linear on a huge adversarial line ------
def test_no_redos_on_pathological_line():
    line = "A" * 400_000  # no separator, no assignment — worst case for the anchor
    start = time.monotonic()
    amb._line_has_secret(line)
    assert time.monotonic() - start < 1.0
    line2 = ("KEY_" * 100_000) + "= " + _HI  # many underscore groups
    start = time.monotonic()
    amb._line_has_secret(line2)
    assert time.monotonic() - start < 1.0
