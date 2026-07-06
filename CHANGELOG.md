# Changelog

All notable changes to ambient-code. Format loosely follows Keep a Changelog.

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
