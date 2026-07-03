# ambient-code — Stress / QA Closing Plan

The repeatable acceptance battery for the plugin. Run it after any change to
`bin/ambient` before shipping. It exercises **every command and every Wave A–D
feature against the live API**, with *correctness* checks (the tool must actually
find planted bugs) and *robustness* checks (pathological input must not crash).

## How to run

```bash
# full battery (spends a few $ of Ambient credit; --yes skips cost prompts)
bash tools/stress_test.sh

# offline surface + robustness only (no spend, no key needed)
AMB_NO_LIVE=1 bash tools/stress_test.sh

# against a specific binary
AMB=/path/to/bin/ambient bash tools/stress_test.sh
```

Exit code is non-zero if any check FAILS. Each check prints `PASS`/`FAIL`/`SKIP`.

## What it covers

### Offline (cheap, no API)
| Check | Verifies |
|---|---|
| `--version`, `version`, bare banner | B4 version surface |
| `audit --help` lists `--consensus` etc. | all new flags wired into argparse |
| `--dry-run` prints a plan, makes no call | D6 |
| secrets tripwire blocks `sk_live_…` | credential guard |
| binary / empty file skipped, not crashed | robustness (read_files guards) |
| `--staged` outside a repo → clean error | D5 guard |

### Live — correctness (the tool must *find* real bugs)
| Check | Verifies |
|---|---|
| single-shot `--json` on a div-by-zero | A1 single-shot + A4/A5 structured findings actually flag the bug |
| `--format report` renders + verdict | A4 report renderer |
| map-reduce audit of a big multi-chunk file | A6/A7/A8 chunking returns a real structured verdict |
| `--consensus` across 2 models | D8 cross-model run + corroboration header |
| `ambient code` produces valid Python | code generation round-trips to a compilable function |

### Live — new plumbing
| Check | Verifies |
|---|---|
| 2nd audit run serves chunks from cache | D7 resumable cache (no re-bill) |
| `ask --json` stable envelope | D2 envelope shape + content |
| `ask` streams once on a TTY | D1 streaming (no double-print) |
| `models --json` valid array | D2 machine-readable list |
| `doctor` reports healthy | key/funds/network/auth end-to-end |

### Stress inputs used
- ~5.4 MB random text (map-reduce + cost-gate path)
- a single 400 KB line (minified hard-split)
- binary blob, empty file (skip-not-crash)
- a planted `.env`-style secret (tripwire)
- the plugin's own 140 KB source (real map-reduce)

## Also verified separately (not in the shell battery)
- **`tests/test_ambient.py`** — 27 hermetic unit tests (profile invariants over
  the real catalog + fuzz, pack_chunks budget guarantee incl. long labels, AST
  bias, `extract_json`/dedupe, config concurrency, cache key sensitivity incl.
  `response_format`, version sync). Run: `python3 -m unittest discover -s tests`.
- **CI** (`.github/workflows/ci.yml`) runs compile + import + the unit battery on
  macOS + Linux across Python 3.8–3.13, plus ruff. No live API in CI.
- **Two adversarial Codex audit rounds** (Wave A+B, Wave D) on snapshot copies —
  every HIGH/MED/LOW verified real and fixed; see `docs/EXECUTION_PLAN.md`.

## Last live run (2026-07-03, v2.0.0 — battery v2)

**40 passed, 0 failed, 1 skipped (soft code-gen style check). Exit 0.** First full
run of battery v2: sandbox HOME (operator config untouched), mechanical KEY-LEAK
tripwire over every byte of output (clean), exit-code contract asserts
(0/1/2/3/64), bogus-key diagnosis without traceback, host-pinning + key-in-argv
refusals, corrupt-config drill, and the new surfaces live: keyless models
storefront, `models --json` envelope, 4-chunk map-reduce with mandatory chunk
evidence, cache reuse, 2-model consensus, `ambient build` end-to-end (planned,
generated, --apply'd a real multi-file package; every generated .py parses;
nothing executable), build --dry-run, ask envelope + piped-once + pty streaming,
doctor healthy. The battery also CAUGHT a real product bug this cycle (the
stdin-ignored note fired on EOF-only stdin and polluted --json output — fixed
with an FIONREAD byte check) plus jassert/rc-blindness in its own harness
(fixed: envelope exit_code now asserted).

## Last live run (2026-07-03, v1.2.0 — Kimi default)

**18 passed, 0 failed, 0 skipped.** Clean sweep on the Kimi default, including
the TTY-streaming check after its harness fix (grep the pty capture file — piping
macOS `script` stdout is flaky headless; streaming itself was verified working by
raw pty capture + 3/3 repeats). Also passed same-day, supplemental to the battery:
766K-char stdin ask → map-reduce → correct needle retrieval, `--focus security`
(flagged shell injection), piped git-diff audit, `code -f` context use, unicode
audit. See `docs/MODEL_TUNING.md` for the all-models tuning table.

## Prior run (2026-07-02, v1.1.0)

**18 passed, 0 failed, 0 skipped.** Highlights:
- single-shot `--json` identified a planted bug; `--format report` gave a verdict.
- 176,355-char input → confirmed **4-chunk map-reduce** → structured verdict.
- D7 cache: the re-audit **served chunks from cache** (no re-bill).
- D8 consensus ran across GLM + Kimi; `ambient code` produced a **valid** `is_prime`.
- `ask --json` gave a clean envelope; streaming printed **once** (no double-print);
  `doctor` reported healthy.

A real bug the battery caught (now fixed): the backend doesn't always honor strict
`json_schema`, so a reply could close the findings array but drop the verdict/brace.
`extract_json` now repairs a cleanly-truncated outer object (recovering the real
findings), and `--json` always emits valid JSON as a last resort.
