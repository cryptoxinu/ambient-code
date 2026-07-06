# Changelog

All notable changes to ambient-code. Format loosely follows Keep a Changelog.

## 2.1.1 — 2026-07-05

Polish release from an extensive live-API test campaign (a direct battery + a
4-agent parallel fleet + Codex, all against the real network). No behaviour or
schema changes; the CLI stays a single stdlib-only file.

- **Accurate reasoning max-tokens hint** — an explicit low `--max-tokens` on a
  reasoning model no longer warns "over a 120,000-char input" (the model's
  capacity); it right-sizes the need to the ACTUAL input and only warns when
  genuinely too low.
- **`ambient use --yes`** is now accepted (was `exit 64`) so a uniform scripted
  flow that passes `--yes` everywhere never errors; `use` still never spends.
- **One message for a non-serving model** — the pre-flight advisory already
  lists priced alternatives, so the error no longer repeats the serving list
  back-to-back.
- **`--json` input tokens** — a partial usage object from the stream (output
  only) no longer leaves `prompt_tokens: 0` in the envelope/ledger; any
  missing/zero field is filled from the char estimate and marked `_estimated`.
- **Receipt clarity** — a short reply on a reasoning model now tags the output
  count `incl. reasoning`, so `out=43` next to "Yes" no longer looks wrong.
- **`ambient build` failure copy** — when `--apply` was passed but every file
  failed validation, the header says why ("nothing written — all N failed")
  instead of the nonsensical "re-run with --apply"; a single missing file no
  longer misreports as "output exceeded one response — split this file".
- Dropped an internal "at the retry cap" phrase from the build cost line.

## 2.1.0 — 2026-07-05

Additive feature + hardening release (no breaking changes). Everything below is
new since 2.0.0; the CLI stays a single stdlib-only file.

- **`ambient map`** — bulk lane: one prompt run independently over many items
  (files, or one item per stdin line; `--jsonl` objects), one JSON envelope per
  item, ONE up-front batch cost gate, content-addressed cache resume. The
  cheapest way to fan out.
- **Advisory routing** — `-m auto[:cheapest|:largest]` (prints the resolved
  pick), a pre-flight readiness/fit/price hint, `--reduce-model` (cheap map /
  strong reduce), `AMBIENT_MODEL_MAP` per-phase defaults, ranked fallback. Model
  choice stays SACRED — advisory + explicit only, never a silent swap.
- **Fleet spend ceiling** — `AMBIENT_MAX_SPEND` is now enforced as an AGGREGATE
  ceiling across every concurrently-running ambient process (reservation files +
  a fail-open cross-process lock); `AMBIENT_FLEET_BUDGET=off` opts out.
- **Repo intelligence** — `audit --repo [DIR]` audits a whole repository
  (git-aware walker, plan + cost shown before spending), a multi-language code
  map, and a bounded cross-file confirmation pass.
- **Savings receipts** — every run ends with its actual cost vs a frontier
  reference (`AMBIENT_REFERENCE_PRICE`), and `ambient usage` gains a savings
  column — engineered to never over-state a saving.
- **Quality from cheapness** — `--best-of K` (corroboration-ranked sampling),
  `ask --consensus A,B` (multi-model triangulation), a native `ambient chat`
  REPL, and `audit --install-hook` (a fixed pre-commit/pre-push audit gate).
- **Smarter + cleaner internals** — a declarative command registry,
  telemetry-EWMA self-calibrating token math (`AMBIENT_TELEMETRY=off` opts out),
  and a frozen `RequestSpec`/`Session` engine carrier (attempt-loop instead of
  recursion) — all behavior-preserving.
- **Whole-system spend gating** — every lane (single `ask`/`code`/`audit`, map,
  consensus, best-of, repo, and opt-in fallback) now reserves against the
  ceiling up front, so nothing escapes the budget.
- **Powerhouse UX** — the `/ambient` model picker surfaces only models serving
  right now; on-demand scaling is framed as normal (never "cold/429/no workers")
  while real failures still surface loudly; clearer Claude-vs-Ambient scoping;
  and the `ambient agent` lane now discloses at launch that its spend is billed
  by Ambient directly (outside local metering).

## 2.0.0 — 2026-07-03

Production/marketplace release. Breaking: exit codes and --json envelopes changed.

- **First-run onboarding**: any command on a fresh terminal onboards inline — get-a-key
  walkthrough (app.ambient.xyz), local paste validation, live verification with
  per-category failure reasons + Ambient support pointer, welcome command showcase.
  Valid-but-out-of-funds keys are saved with a top-up path. `setup --remove` offboards.
- **`ambient build`** — native agentic lane: plan → generate a whole file-set →
  manifest; writes only inside --dir via a path-traversal firewall, with resume state,
  truncation-safe batch continuation, and zero execution. --plan-only/--dry-run/--json.
- **Model curation**: `ambient curate hide/show/only/note/reset` — pick what the menus
  surface (explicit -m always works); per-model notes shown at decision points;
  curation-aware --fallback ranking with price-visible switches.
- **Exit-code contract**: 0 ok · 1 error · 2 partial · 3 unconfigured · 64 usage ·
  130 interrupt. One --json envelope (schema_version 1) across ask/code/audit/
  consensus/build.
- **Honest consensus**: pre-validated ids (did-you-mean), per-model pricing, partial
  model failures exit 2, --json support.
- **Resilience**: binary-safe stdin, giant argv prompts auto-split, token-density-aware
  chunking (CJK), budget-400 self-heal, truncation ⇒ partial everywhere (a repaired/
  cut audit can never say SHIP), hostile-catalog coercion, linear-time secret scan.
- **Security**: ANSI/OSC output sanitization, API host pinning (`trust-url` for
  self-hosted gateways), key-in-argv refusal, getpass echo preflight, keychain-delete
  verification, 0700/0600 cache+usage, wider credential-name tripwire.
- **UX**: status-aware banner, colorized doctor/models/findings (NO_COLOR honored),
  complete help text, did-you-mean for commands and model ids, `ambient link`
  launcher with self-heal on plugin updates, keyless `ambient models` storefront.
- **Packaging**: self-hosting marketplace.json, plugin.json polish, CI on
  main+master with version tri-sync + ruff gate, RELEASING.md, uninstall story.

## [1.2.0] — Kimi default + metering fix
### Changed
- **Default model for chat/audit is now `moonshotai/kimi-k2.7-code`** (both
  lanes). The live probe measured it ~2-3x faster and catching planted bugs 3/3
  where `z-ai/glm-5.2` caught 1/3. GLM remains fully selectable
  (`ambient use z-ai/glm-5.2 --chat`) and is improving as the network builds it up.
### Fixed
- Local cost metering was blind: Ambient's stream doesn't reliably send a
  `usage` object. `complete()` now estimates tokens from char counts when the
  backend omits usage, so `ambient usage` reflects real spend.

## [1.0.0] — Official v1.0
### Added
- Wave B trust artifacts: cross-platform key storage (macOS Keychain / Linux
  secret-tool / 0600 fallback), a hermetic test suite + GitHub Actions CI
  (macOS/Linux × py3.8–3.13), `pip`/`pipx` install via `pyproject.toml`, live
  in-place status line, product-grade `ambient models` renderer.
- Wave C: SECURITY.md, CONTRIBUTING.md, PRIVACY.md; labeled a community
  integration (not affiliated with Ambient) pending any official blessing.
### Fixed
- Structured audits never emit a false SHIP on unparseable or partial coverage;
  `--fallback` re-gates JSON output for the new model; config lock never enters
  its critical section unlocked; pack_chunks guarantees every chunk fits even
  with long paths; auto output-budget never exceeds a tiny model's safe ceiling.

## [0.8.0] — Wave A: quality core
### Added
- **Per-model single-shot scaling**: audits/asks now stay in ONE high-quality
  pass sized to each model's real window (GLM/Kimi ~120K chars) instead of a flat
  32K, with the output budget right-sized to the actual input.
- **Structured findings output**: `ambient audit --json` / `--format report`
  returns machine-readable findings (severity, confidence, file, line, defect,
  scenario, fix, verdict), capability-gated per model (strict json_schema →
  json_object → prompt-only fallback).
- **Absolute line-number gutters** so citations are exact even after chunking.
- **AST-aware chunk splitting** (Python) so a function is never cut mid-body;
  a shared **repo code-map** injected into each chunk for cross-file awareness.
- **Coverage manifest**: a failed/truncated chunk now names exactly which
  file:line ranges went unreviewed.
- Severity rubric + confidence in the audit prompt; deterministic finding dedup.
- `ambient version` / `--version`, a bare-command onboarding banner, version in
  `doctor`, and a product-grade `ambient models` list (names, badges, aligned
  pricing, alias dedup).

### Fixed
- **Windows startup crash** (unconditional `import fcntl`) — key handling and
  config locking are now cross-platform.
- Self-audit fixes: no-20K synthesis-budget floor (small models); atomic write of
  the opencode config.

## [0.7.x] — reasoning-marathon fix + hardening
- Root-caused and fixed the reasoning-marathon (`max_tokens` caps reasoning +
  answer combined); per-model budgeting; SSE streaming with stall/truncation/
  no-progress/heartbeat guards; never-crash shield; cost gate; secrets tripwire;
  macOS Keychain storage; concurrent-config locking; `doctor` error taxonomy.

## [0.1.0] — initial
- CLI over Ambient's OpenAI-compatible API: models, ask, audit, code, agent.
