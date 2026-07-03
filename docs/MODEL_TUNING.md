# Per-model tuning — all catalog models

Tuning in this CLI is **derived, not hand-coded**: `model_profile()` reads each
model's live catalog metadata (`context_length`, `max_output_length`, the
`reasoning` feature flag, structured-output capabilities) and derives its input
sizing, chunking, output budget, escalation ceiling, and JSON mode. New models
Ambient adds are tuned automatically the moment they appear in the catalog —
nothing to update client-side.

Snapshot generated live 2026-07-03 (`invariant failures: 0` across all models;
the same invariants are enforced in CI over `tests/catalog.json` + 3,000 fuzz
configs):

| model | reasoning | single-shot | chunk | output budget | JSON mode |
|---|---|---|---|---|---|
| ambient/large (GLM-5.1) | yes | 120,000 | 102,000 | 71,587 | json_schema |
| google/gemma-4-26b-a4b-it | yes | 120,000 | 102,000 | 71,587 | json_schema |
| google/gemma-4-31b-it | yes | **17,593** | 14,954 | **16,383** | json_schema |
| moonshotai/kimi-k2.5 | yes | 120,000 | 102,000 | 71,587 | json_schema |
| moonshotai/kimi-k2.6 | yes | 120,000 | 102,000 | 71,587 | json_schema |
| **moonshotai/kimi-k2.7-code** *(default)* | yes | 120,000 | 102,000 | 71,587 | json_schema |
| nvidia/nemotron-3-nano-30b-a3b | yes | 120,000 | 102,000 | 71,587 | **prompt-only** |
| openai/gpt-oss-120b | yes | 120,000 | 102,000 | 71,587 | json_schema |
| openai/gpt-oss-20b | yes | 120,000 | 102,000 | 71,587 | json_schema |
| qwen/qwen3-coder-30b-a3b-instruct | no | **382,771** | 325,355 | 16,384 | json_schema |
| qwen/qwen3-next-80b-a3b-instruct | no | **660,601** | 561,510 | 16,384 | json_schema |
| qwen/qwen3.5-35b-a3b | yes | 120,000 | 102,000 | 71,587 | json_schema |
| qwen/qwen3.6-27b | yes | 120,000 | 102,000 | 71,587 | json_schema |
| qwen/qwen3.6-35b-a3b | yes | 120,000 | 102,000 | 71,587 | json_schema |
| z-ai/glm-4.5-air | yes | 120,000 | 102,000 | 71,587 | json_schema |
| z-ai/glm-5.2 | yes | 120,000 | 102,000 | 71,587 | json_schema |
| zai-org/GLM-5.1-FP8 *(alias of ambient/large)* | yes | 120,000 | 102,000 | 71,587 | json_schema |

The bold cells show the derivation doing real work:
- **gemma-4-31b**'s hard 16,384 output cap shrinks its single-shot to what
  reasoning + answer can actually fit — instead of marathoning to an empty reply.
- The two **non-reasoning qwens** spend no tokens thinking, so they get huge
  single-shots sized off their real context windows.
- **nemotron** lacks structured-output support, so `--json` audits route through
  the prompt-instruction + tolerant-parse path instead of a 400-ing `response_format`.

## Selectability

Every model above is choosable: `ambient use <id>` (sticky), `-m <id>` (one
call), or the interactive `ambient use` picker. `ambient models` hides the one
true duplicate row (`zai-org/GLM-5.1-FP8` ≡ `ambient/large`) for clarity, but
the id still works everywhere if typed.

## What "tested" honestly means per model

- **Tuning math: all models** — verified live (table above) and continuously in
  CI (catalog-driven invariants + fuzz).
- **Live end-to-end behavior: only READY models can be exercised** (a
  decentralized network serves what miners choose; the rest 429 until picked
  up). As of 2026-07-03 that is Kimi-k2.7, ambient/large and z-ai/glm-5.2 —
  measured in `docs/LIVE_PROBE_REPORT.md`. When a new model goes READY, run
  `tools/live_probe.py` to characterize it in ~7 minutes.
