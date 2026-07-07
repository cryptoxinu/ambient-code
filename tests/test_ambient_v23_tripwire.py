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
    "PASSWORD=p@ssw0rd!",                       # bare strong name, short value
    "TOKEN=p@ssw0rd!",
    "AWS_SECRET_PUBLIC_KEY=p@ssw0rd!",          # strong name, not exempted
    f"API_KEY={_HI}",                           # plain _KEY w/ high-entropy value
])
def test_env_secret_assignment_is_detected(line):
    assert amb._line_has_secret(line) is True


# --- false positives that must NOT trip ----------------------------------
@pytest.mark.parametrize("line", [
    f"PUBLIC_KEY={_HI}",            # a public key is not a secret
    f"RSA_PUBLIC_KEY={_HI}",
    "API_KEY=short",               # value too short / low entropy
    "MY_KEY=1",
    "SOME_TOKEN=todo",             # strong name but value < 8
    'PRIMARY_KEY = "customer_id"',  # schema column, not a secret
    'FOREIGN_KEY = "account_id"',
    "PARTITION_KEY = user_region",
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


# --- Codex round 3: JSON / lowercase / tab-gutter / hash-FP -------------
@pytest.mark.parametrize("line", [
    '{"AWS_SECRET_ACCESS_KEY":"wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"}',
    '{"password":"p@ssw0rd!"}',
    "db_password=p@ssw0rd!",
    "DbPassword=p@ssw0rd!",
    'password: "p@ssw0rd!"',
])
def test_round3_secret_shapes_are_caught(line):
    assert amb._line_has_secret(line) is True


@pytest.mark.parametrize("line", [
    "CACHE_KEY=0123456789abcdef0123456789abcdef01234567",  # git SHA, not a key
    "CACHE_KEY=550e8400e29b41d4a716446655440000",          # compact UUID
    "password = get_input()",                               # code, not a literal
    "foreign_key = other_table.id",                         # code reference
    "sort_key = compute(x)",
])
def test_round3_false_positives_do_not_trip(line):
    assert amb._line_has_secret(line) is False


# --- Codex round 4 ------------------------------------------------------
@pytest.mark.parametrize("line", [
    "ok=1 AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",  # 2nd assignment
    "DB_PASSWORD=p(ass)w0rd!2026",                    # real secret with brackets
    '{"password":"p(ass)w0rd!2026"}',
    "SESSION_KEY=abcdefabcdefabcdefabcdef",            # sensitive key, hex value
    "ACCESS_KEY=0123456789abcdef0123456789abcdef",
])
def test_round4_bypasses_now_caught(line):
    assert amb._line_has_secret(line) is True


@pytest.mark.parametrize("line", [
    "password = user.password_hash",       # code attribute reference
    "token = session.current_access_token",
    "CACHE_KEY=0123456789abcdef0123456789abcdef01234567",  # hash still not a key
])
def test_round4_false_positives_do_not_trip(line):
    assert amb._line_has_secret(line) is False


# --- Codex round 5 ------------------------------------------------------
@pytest.mark.parametrize("line", [
    "TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV",  # JWT
    "here is my key: AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",  # prose prefix
    "db_password: p(ass)w0rd!",                        # lowercase YAML w/ brackets
])
def test_round5_bypasses_now_caught(line):
    assert amb._line_has_secret(line) is True


@pytest.mark.parametrize("line", [
    "password = user.password_hash",        # still a code ref (lowercase)
    "token = session.current_access_token",
])
def test_round5_code_refs_still_clean(line):
    assert amb._line_has_secret(line) is False


# --- Codex round 6 ------------------------------------------------------
@pytest.mark.parametrize("line", [
    ('"AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=devstore;'
     'AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;'
     'EndpointSuffix=core.windows.net"'),
])
def test_round6_azure_connection_string_caught(line):
    assert amb._line_has_secret(line) is True


@pytest.mark.parametrize("line", [
    "const password = user.passwordHash;",      # JS/TS camelCase code ref
    "this.password = req.body.password;",
    "self.token = obj.session_token",
])
def test_round6_code_refs_not_false_positive(line):
    assert amb._line_has_secret(line) is False


# --- Codex round 7 ------------------------------------------------------
def test_round7_azure_sas_signature_caught():
    line = ('AZURE_STORAGE_CONNECTION_STRING="BlobEndpoint=https://acct.blob.core.'
            'windows.net/;SharedAccessSignature=sv=2020-08-04&ss=b&srt=sco&sp=rwdlac'
            '&se=2026-01-01T00:00:00Z&sig=abcDEF123%2Fghi%2BjklMNO456pqr%3D"')
    assert amb._line_has_secret(line) is True


def test_round8_http_basic_auth_caught():
    assert amb._line_has_secret("Authorization: Basic YWxpY2U6U3VwZXJTZWNyZXQxMjMheHl6") is True


def test_round8_basic_word_not_false_positive():
    assert amb._line_has_secret("Basic understanding of the system is required") is False


def test_round9_password_only_redis_url_caught():
    assert amb._line_has_secret("REDIS_URL=redis://:supersecret1@redis.example.com:6379/0") is True


def test_round11_gitlab_pat_caught():
    assert amb._line_has_secret("GITLAB_TOKEN=glpat-ABC123def456GHI789jkl0") is True
    assert amb._line_has_secret("glpat-ABC123def456GHI789jkl0") is True


@pytest.mark.parametrize("line", [
    "password = getPasswordFromEnvironment()",   # function call (code)
    "token = refreshTokenFromRequest()",
    "const secret = config.getSecret();",
    "password = req.body.password",
])
def test_round12_code_expression_values_not_false_positive(line):
    assert amb._line_has_secret(line) is False


@pytest.mark.parametrize("line", [
    "password = 'wJalrXUtnFEMI/K7MDENG+bPxRf'",   # quoted literal still caught
    "secret = supersecret_value_12345",           # bare high-entropy still caught
])
def test_round12_real_secrets_still_caught(line):
    assert amb._line_has_secret(line) is True


@pytest.mark.parametrize("line", [
    "DB_PASSWORD=prod.db.password",              # ALL-CAPS env w/ dotted value
    "JWT_SECRET=correct.horse.battery.staple",
    "API_TOKEN=abc.def.ghi.jkl",
])
def test_round13_dotted_env_secrets_caught(line):
    assert amb._line_has_secret(line) is True


def test_round13_lowercase_code_refs_still_cleared():
    assert amb._line_has_secret("password = user.password_hash") is False
    assert amb._line_has_secret("const password = user.passwordHash;") is False


@pytest.mark.parametrize("line", [
    "account_key = settings.account_key",       # code ref, not Azure key
    "shared_key = configuration.sharedKey",
])
def test_round14_azure_code_refs_not_false_positive(line):
    assert amb._line_has_secret(line) is False


def test_round14_real_account_key_still_caught():
    assert amb._line_has_secret(
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq==") is True


@pytest.mark.parametrize("line", [
    "SECRET_NAME=my-service-secret-name",       # config ABOUT a secret
    "SECRET_PATH=/etc/myapp/secret-file",
    "TOKEN_EXPIRATION=2026-12-31",
    "PASSWORD_POLICY=minimum_length_12",
    "PASSWORD_MIN_LENGTH=12",
])
def test_round15_config_about_secrets_not_false_positive(line):
    assert amb._line_has_secret(line) is False


@pytest.mark.parametrize("line", [
    "DB_PASSWORD=aQ7pR2xL9mZ4kT8v",             # real secret still caught
    "API_SECRET=wJalrXUtnFEMI123456",
])
def test_round15_real_secrets_still_caught(line):
    assert amb._line_has_secret(line) is True


def test_tab_gutter_bypass_blocked(capsys):
    # Codex round 3: an inner fake gutter with a TAB survived the space-only strip.
    chunks = [("x.txt", "   7| \t12| AWS_SECRET_ACCESS_KEY="
                        "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY\n")]
    with pytest.raises(SystemExit) as ei:
        amb.refuse_if_secrets(chunks, allow=False)
    assert "x.txt" in (str(ei.value.code) + capsys.readouterr().err)


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
