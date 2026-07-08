# Changelog

All notable changes to ambient-code. Format loosely follows Keep a Changelog.

## 1.3.0 — 2026-07-08

A single settings home so users never edit environment variables or the config
file by hand. No breaking changes.

### Added

- **`ambient config`** — one place to view and change your preferences:
  - `ambient config` prints an aligned status table (API-key state, model, delegate
    mode, curation — with pointers to the commands that own them — then the
    config-owned knobs with their current values and how to change each).
  - `ambient config set <name> <value>` / `ambient config unset <name>` change a
    knob with validation and a one-line confirmation. Friendly names:
    `streaming` (progress display on/off), `fallback`, `fleet-budget`, `spend-cap`,
    `reference-price`. Every write persists to `~/.config/ambient/env` (0600) via
    the existing atomic writer and is honored by the same env-or-config resolvers.
  - Keyless and zero-network — works before a key exists; the API key value is
    never printed. Booleans accept on/off/true/false/1/0/yes/no. A `set`/`unset`
    can only touch the five whitelisted knobs — it can never clobber your model,
    delegate mode, curation, or endpoint. The API key is not a config value:
    `config` points you to `ambient setup --force` / `--remove` for that.
  - When an exported `AMBIENT_*` env var shadows the file, the status view and
    `set` say so, so a change that "doesn't take" is never a mystery.
- A **Settings** sub-panel in the `/ambient` skill (`/ambient settings`) that drives
  `ambient config` — change streaming, model fallback, and other prefs, and see
  your API-key status — without the user touching env vars.

### Security

- `config` refuses a key-shaped argument without echoing it: a mistyped
  `config set key=<SECRET>` (or `config --key=<SECRET>`) is caught by the same
  pre-argparse guard that protects `setup`, and any secret-looking setting name is
  redacted in error output. The API key can still only be entered via `ambient
  setup` (hidden input, in your own terminal).

## 1.2.0 — 2026-07-08

Three founder-requested features. No breaking changes; every prior default is
byte-identical unless you opt in.

### Added

- **Ambient Takeover mode** (`ambient mode takeover`, or `/ambient takeover` in
  Claude Code) — a full-delegate level above `on` (ordered: off < on < takeover).
  Claude routes every substantive turn through Ambient (chat → `ask`, code →
  `build`, review → `audit`) so you spend Ambient tokens, not Claude's; Claude
  stays a thin router/safety/integration layer. Always shows how to leave
  (`/ambient off`), which turns off both delegate and takeover.
- **Streamed build/audit progress** — `ambient build` prints a per-batch
  `generating <paths> [X/Y of the plan done]` line alongside the existing char
  heartbeat, so a long generation never looks stuck. The skill now dispatches long
  jobs (`build`, `audit --repo`, `map`) in the background so they are never killed
  by an outer tool timeout.
- **User-toggleable progress display** — silence the heartbeat + phase lines per
  call with `--no-progress` (force on with `--progress`) on any streaming command
  (ask/audit/map/code/chat/build), or persistently with `AMBIENT_PROGRESS=off`
  (env or config). Gates ONLY the display — the smart stall / hard-wall timeout
  always runs, so a quiet build can never silently hang.

### Changed

- The smart streaming timeout is now tunable: `AMBIENT_HARD_WALL_S` (default 5400,
  floor 60) and `AMBIENT_NOPROGRESS_S` (default 150, floor 10) let a very long
  build raise the ceilings. The floors mean a mistyped `0` can never disable a
  guard.

## 1.1.2 — 2026-07-08

Production-hardening pass (from a Codex + team-share audit) before wider sharing.
No breaking changes.

### Security

- `AMBIENT_ALLOW_INSECURE=1` now relaxes the HTTPS requirement ONLY for a LOCAL
  endpoint (127.0.0.1 / localhost) — never a real/public host, so the API key
  can never ride plaintext HTTP to `api.ambient.xyz` or an attacker's box.
- The outbound secret tripwire now also scans `--system` on `ask`/`chat` (it is
  sent to the network) — a credential in a system prompt is no longer transmitted.

### Robustness

- `ambient audit --repo` over the input ceiling now reports coverage as PARTIAL
  as a fact when files are excluded (exit 2 / not-clean), instead of trusting the
  model to self-declare it — a clean SHIP can't be issued over skipped files.
- A streamed response can no longer hang the client: the socket read now runs in
  a background reader while the main loop enforces the hard-wall and no-progress
  limits on a fixed cadence, so a peer that dribbles bytes and never sends a
  newline is aborted on schedule (previously a blocking read could own the clock
  and delay every limit). The per-line read is also capped against unbounded
  buffering. Groundwork for a truly progress-aware timeout.
- Piped stdin no longer hangs forever when `select()` is unavailable (some
  Windows/IDE/CI wrappers) — the read is time-bounded.

### Windows

- `ambient agent` now launches opencode as a child process (handles the
  `opencode.cmd` shim and keeps the console attached) instead of `os.execvpe`.
- No more spurious `tightened … permissions (666 → 600)` on every command (the
  POSIX-only mode heal is now guarded; Windows secures the file via profile ACLs).
- `ambient link` writes a shim that uses the running interpreter (`sys.executable`)
  instead of a bare `python` (off-PATH on stock Windows), and shows the PATH note.

## 1.1.1 — 2026-07-08

Test-suite/CI hotfix — no behavior change to the CLI.

- The v1.1.0 test files (`test_ambient_v20`–`v25`) were written with `pytest`,
  but the canonical, hermetic CI runner is stdlib `python -m unittest discover`
  with no third-party dependencies. Under that runner those modules failed to
  import (no `pytest`), turning the whole CI matrix red and leaving ~150 of the
  new tests uncollected. All six files are now pure `unittest` (`TestCase`
  classes, `subTest` for the parametrized cases, `assertRaises`/`assertIs`,
  `setUp`/`tearDown` for the old autouse fixtures) — the full suite (805 tests)
  now runs and passes under the canonical runner, and `ruff check` is clean.
- Corrected the `${CLAUDE_PLUGIN_ROOT}` note in the skill (it is substituted
  inline in skill content, not a Bash environment variable).

## 1.1.0 — 2026-07-07

Makes the tool work correctly across DIFFERENT models — not just the default —
plus a deep security/robustness pass driven by four rounds of adversarial
verification. Backward compatible; no new required flags. `AMBIENT_TELEMETRY=off`
opts out of the new learning, byte-identical to before.

### Added — adaptive per-model capability layer

- Catalog capabilities are treated as a hypothesis; the tool now LEARNS each
  model's observed behavior and adapts. When a model ignores the strict JSON
  schema and answers in prose (e.g. GLM on Ambient), `ambient audit --json` now
  **recovers the findings from that prose** instead of returning empty — so
  structured audits work on any reasoning model, not only ones that honor
  `json_schema`. The outcome is recorded per model
  (`~/.config/ambient/capabilities.json`, 0600) and reused, with recovery on a
  later success. `ambient build` downgrades the output demand
  (json_schema → json_object → prompt-only) and, when a model genuinely can't
  drive a build plan, names a model that can — never a silent model swap.

### Security

- **Credential tripwire** broadened far beyond `.env`-filename matching: catches
  env/JSON/YAML/dotenv/properties secrets in any case, connection-string and URL
  passwords (ADO.NET / JDBC / Spring), vendor keys (Stripe `sk_live_`, SendGrid,
  JWT, GitLab, AWS, Azure SAS), `MYSQL_PWD`/glued `PGPASSWORD`, and now scans the
  **chat** REPL. False positives on normal code are actively guarded: env
  plumbing (`os.environ["K"]`, `process.env.X || ""`, `$(cmd)`, `${{ }}`/`{{ }}`),
  config ABOUT secrets, schema columns, type annotations, credential PATHS, and
  k8s Secret references are not flagged. Still a documented backstop — never send
  secrets. Savings/consensus/chat receipts are redacted before stderr.

### Robustness

- `ambient audit --json` on a non-JSON model no longer returns empty findings +
  exit 2; it recovers the model's prose findings. A self-contradicting reply (a
  finding + `SHIP`) is forced to a non-clean verdict so a pre-commit hook can't
  wave a defect through. Every realistic finding shape — inline/field-list/table/
  heading/XML, any separator/notation/severity taxonomy, and empty-JSON-plus-prose
  mixes — is handled; a clean audit that quotes an example or recalls a resolved
  finding is NOT mis-flagged.
- `ambient ask "…" -m MODEL -` (natural argument order) reads stdin instead of
  erroring on `unrecognized arguments: -`.
- Prose recovery and tripwire scanning are linear-time (ReDoS-hardened).

## 1.0.1 — 2026-07-06

Reliability and robustness pass. No breaking changes; no new flags. Every fix is
backward compatible.

### Security

- **Streaming output redaction** is now boundary-safe: an API key or terminal
  escape that a compromised endpoint splits across streamed chunks can no longer
  reach your terminal, and redaction of long streamed answers is now linear-time
  (a hostile stream of tiny chunks or a never-terminating escape can't burn CPU).
- **`ambient setup --key-stdin`** refuses a TTY (which would echo the key); use
  the interactive `ambient setup` for hidden entry.
- **`ambient trust-url`** prompts and status now go to stderr, keeping stdout
  clean for scripted callers.

### Robustness

- The client no longer crashes on a malformed but successful response from an
  endpoint — non-object bodies, wrong-typed `choices`/`message`/`delta`/`usage`,
  reasoning-only replies, and malformed `/v1/models` rows are all tolerated.
- **`ambient build`** hardening: rejects a non-positive `--max-files` /
  `--max-file-bytes` up front; a resumed build re-enforces the current caps on
  the saved state and can only apply files that are within the plan and the
  size/count limits; a changed cap invalidates a stale resume; the generation
  prompt is kept within the model's context window by trimming its inputs.
- Path-containment checks are now correct when `--dir` is the filesystem root.
- Negative `--older-than` (cache) and non-positive `--days` (usage) are rejected
  instead of silently wiping or returning nothing.
- Catalog readiness now treats a string `"false"` as not-ready; audit
  de-duplication keeps the richest finding and no longer merges files that
  differ only by path case; a binary file with a text-looking header is skipped.

### Metering & cost

- The spend gate never under-reserves on an inconsistent per-call estimate.
- Reasoning-only responses are metered; the fallback fit-check and cross-file
  confirmation pass account for the served model and any truncation.

## 1.0.0 — 2026-07-06

First public release. A single stdlib-only Python CLI (`ambient`) plus a Claude
Code skill (`/ambient`) that put the Ambient decentralized-inference network at
Claude's side — Claude plans and reviews, cheaper open models do the heavy token
work. No breaking changes are expected after this line.

### Core

- **`ambient ask` / `ambient code`** — one-shot completion and single-file code
  generation, streamed, with a per-run savings receipt (actual cost vs a frontier
  reference, engineered never to over-state a saving).
- **`ambient audit`** — a second opinion on your code: a file, a `git diff` piped
  in, or a whole repository (`--repo`) with a git-aware walker and the plan + cost
  shown before anything is sent. Structured findings (`--json` / `--format report`)
  with severity, confidence, file, line, scenario, fix, and verdict.
- **`ambient map`** — bulk lane: one prompt run independently over many items
  (files, or one item per stdin line), one JSON envelope per item, a single
  up-front cost gate, and content-addressed cache resume. The cheapest fan-out.
- **`ambient build`** — native agentic lane: plan → generate a whole file-set →
  manifest. Writes only inside `--dir` through a path-traversal firewall, resumes
  safely, and **never executes** generated code.
- **`ambient chat`** — an interactive REPL; **`ambient agent`** — an Ambient-powered
  agentic terminal (via opencode).

### Quality from cheapness

- **`--best-of K`** corroboration-ranked sampling, **`ask --consensus A,B`**
  multi-model triangulation with an honest agreement note, and
  **`audit --install-hook`** for a fixed pre-commit/pre-push audit gate.

### Routing, curation & cost control

- **Advisory routing** — `-m auto[:cheapest|:largest]`, a pre-flight
  readiness/fit/price hint, `--reduce-model`, `AMBIENT_MODEL_MAP` per-phase
  defaults, and ranked `--fallback`. Your explicit model choice is never silently
  swapped.
- **Model curation** — `ambient curate hide/show/only/note/reset` shapes what the
  menus surface; an explicit `-m` always works.
- **Fleet spend ceiling** — `AMBIENT_MAX_SPEND` is enforced as an aggregate
  ceiling across every concurrently-running `ambient` process; every lane reserves
  against it up front, so nothing escapes the budget.
- **Savings receipts** — every run reports its real cost, and `ambient usage`
  gains a savings column with honest disclosures.

### Onboarding, packaging & safety

- **First-run onboarding** — any command on a fresh terminal walks you through
  getting and validating a key, with live verification and clear per-category
  failure reasons. `setup --remove` offboards cleanly.
- **The `/ambient` skill** — a control panel and model picker that surfaces only
  models serving right now and frames on-demand scaling as normal, while real
  failures still surface loudly.
- **Exit-code contract** — `0` ok · `1` error · `2` partial · `3` unconfigured ·
  `64` usage · `130` interrupt. One `--json` envelope (`schema_version` 1) across
  ask/code/audit/consensus/build.
- **Security** — cross-platform key storage (macOS Keychain / Linux secret-tool /
  0600 fallback), API host pinning, key-in-argv refusal, a credential tripwire on
  outbound content, ANSI/OSC output sanitization, and `0700/0600` cache + usage.
- **Packaging** — single stdlib-only file, `pip`/`pipx` installable, a
  self-hosting marketplace, and CI with a version-sync + lint gate.

This is a community integration and is not affiliated with Ambient.
