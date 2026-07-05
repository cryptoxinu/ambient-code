# Live API characterization — 2026-07-02

Real measurements from `tools/live_probe.py` against the live Ambient API through
the `ambient` CLI (v1.1.0). ~7 min, ~20 real calls. Reproduce: `python3 tools/live_probe.py`.

## Readiness
**3 of 16 models were serving at probe time** (READY):
`ambient/large` (GLM-5.1-FP8), `moonshotai/kimi-k2.7-code`, `z-ai/glm-5.2`.
The other 13 were not serving at that moment — normal for an on-demand network
(they spin up as demand arrives). `--fallback` / `ambient models` handle this.

## Per-model audit behavior (3 repeats each, planted div-by-zero + KeyError)

| Model | tiny ask | audit avg | valid JSON | **caught the bug** | stalls |
|---|---|---|---|---|---|
| moonshotai/kimi-k2.7-code | 1.5s | **16.5s** | 100% | **100%** | 0% |
| ambient/large (GLM-5.1) | 1.5s | 45.7s | 100% | **100%** | 0% |
| z-ai/glm-5.2 *(default at probe time; since replaced by Kimi — see below)* | 3.0s | 37.0s | 100% | **33%** | 0% |

**Two things stand out:**
1. **Reliability was excellent this run — 0% stalls, 100% valid JSON** across every
   audit. (Ambient's serving has been flaky in the past; it wasn't today. The
   stall/salvage/partial guards remain the safety net when it is.)
2. **Kimi is the best auditor and the current default is the weakest.** Kimi is
   ~2–3× faster *and* caught the planted bugs every time; `z-ai/glm-5.2` (the
   default the audit command uses) flagged them only 1 of 3 runs — it tended to
   judge an unhandled `ZeroDivisionError`/`KeyError` as acceptable and return a
   clean SHIP. Small sample (n=3) but consistent.

## Scale + cache
- **176,349-char input → 4-chunk map-reduce → 70s**, valid structured verdict.
- **Cache re-run: 0.8s — ~88× faster** (served from cache, no re-bill). The
  resumable-cache payoff (resumable-cache payoff) is large in practice.

## Consensus
- `--consensus` across the two GLM/Kimi models: 61.7s, ran and merged.

## Bug the probe caught (now fixed)
Local cost metering was **blind**: Ambient's streaming responses don't reliably
include a `usage` object, so `log_usage` almost never fired and `ambient usage`
under-reported nearly everything. Fixed: `complete()` now **estimates** tokens
from char counts (reasoning counted as output, marked `_estimated`) when the
backend omits usage, so `ambient usage` reflects real spend. Regression-tested.

## Recommendation
For **audits specifically, prefer `moonshotai/kimi-k2.7-code`** — faster and more
sensitive to real defects than `z-ai/glm-5.2`. Either audit with
`-m moonshotai/kimi-k2.7-code`, set it as the chat/audit default
(`ambient use moonshotai/kimi-k2.7-code --chat`), or keep GLM for chat and pass
`-m` for audits. (Deliberate design call — model choice is intentionally yours.)

**Decision (maintainer, 2026-07-03): accepted.** Kimi is now the built-in default
for both lanes (`DEFAULT_MODEL` + `DEFAULT_CODE_MODEL`). GLM stays fully
selectable and its weaker showing here is expected to improve — the network is
still building up GLM capacity, which is also the likely cause of its slower
latency in this run.
