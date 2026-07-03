# ambient-code — Claude Code plugin for the Ambient network

> **Community integration — not affiliated with or endorsed by Ambient.** An
> independent, open-source (MIT) plugin that talks to Ambient's public API.

Give Claude Code a second brain — at a fraction of the price. This plugin connects
Claude to [Ambient](https://ambient.xyz), the decentralized AI inference network
where independent miners serve open-source models (Kimi, GLM, GPT-OSS, Qwen,
Gemma…) behind one OpenAI-compatible API, paid per token — typically **10-40x
cheaper** than frontier models.

**You stay in control the whole time**: you pick the model, you decide when Ambient
is used, and Claude reviews everything Ambient produces before it lands.

## 30-second start

```bash
# in Claude Code
/plugin marketplace add cryptoxinu/ambient-code
/plugin install ambient-code@cryptoxinu
/ambient            # (completes to /ambient-code:ambient) — Claude walks you through the rest
```

The first time you use it, the CLI onboards you: it asks for an Ambient API key,
shows exactly how to get one (sign in at <https://app.ambient.xyz> → API Keys),
verifies the key with a real authenticated call, tells you *why* if it fails
(mistyped/revoked key vs out-of-funds vs busy model vs network — with an Ambient
support pointer), and finishes with a command showcase. Key entry happens in
**your** terminal with hidden input — the key never passes through the chat.

## The three moves

**1. Pre-commit second opinion, for about a penny**

```bash
git diff | ambient audit            # independent adversarial review of your changes
ambient audit src/auth.py --focus security --json
```

Independent eyes on every commit at a price where "always" is affordable — Claude
cross-checks the findings, so you get two reviewers for less than one.

**2. Plan with Claude, build with Kimi, review with Claude**

```bash
/ambient on                         # delegate mode
# You describe the feature. Claude writes a precise brief, then runs:
ambient build "FastAPI /users CRUD + pytest suite per the brief" --dir src/ --apply
# Claude reviews the manifest and every file, runs the tests, integrates.
```

Claude's judgment on every line, Kimi's price on every token — the bulk writing
lands on the ~10-40x cheaper lane. `ambient build` plans a file-set, generates it,
and writes only inside `--dir` after your confirmation. It **never executes
anything**.

**3. Digest cheap, reason expensive**

```bash
cat src/**/*.py | ambient ask "Digest: per file — purpose, public API, gotchas." - > digest.md
```

Claude reads the thousand-token digest instead of the hundred-thousand-token repo,
and reasons over it at full quality.

## Models

Availability fluctuates as miners come and go — usually 2-3 models are READY at any
moment; a cold model returns 429 until someone serves it (`ambient models` shows
what's live). The default for every lane is **`moonshotai/kimi-k2.7-code`** (the
live probe measured it fastest and most accurate at catching planted bugs — see
`docs/LIVE_PROBE_REPORT.md`). GLM-5.2 is fully selectable
(`ambient use z-ai/glm-5.2`) and improving as the network's capacity ramps up. You
can curate which models your menus show: `ambient curate only <ids>` /
`hide <glob>` / `note <id> "label"` — explicit `-m` always works regardless.

## Command reference

```text
ambient setup            store + verify your API key (--force rotate · --remove offboard)
ambient models           live model list (READY = serving now) · --all shows curated-out
ambient use [id]         sticky default model picker (--chat/--code scopes)
ambient curate …         choose which models the menus surface (hide/show/only/note)
ambient ask "q"          one-shot answer · pipe docs: cat doc.txt | ambient ask "sum" -
ambient audit [files]    adversarial code review · git diff | ambient audit · --consensus A,B
ambient code "task"      single-file code generation (-f context.py)
ambient build "task"     plan + generate a whole file-set (manifest-first, --apply writes)
ambient agent            interactive agentic terminal on Ambient (opencode)
ambient doctor           pinpoints key / funds / busy-model / network trouble
ambient usage            local spend summary (--days N)
ambient mode on|off      delegate mode for Claude Code sessions
ambient link             put a stable `ambient` launcher on your PATH
ambient cache …          inspect / clear the local chunk cache
ambient trust-url <url>  explicitly trust a self-hosted gateway (advanced)
```

Every model is auto-tuned from the live catalog (context window, output cap,
reasoning behavior) — **no input is refused for size**: anything past a model's
single-pass budget is automatically split, processed in parallel by the *same*
model, and merged, with failed pieces reported as explicit coverage gaps. Spend is
gated: estimates print up front, the default ceiling is $5 (`AMBIENT_MAX_SPEND`),
and jobs over $0.50 ask first (`--yes` skips, `--allow-cost` overrides).

## Agentic use (for scripts and orchestrators)

Exit codes: `0` ok · `1` diagnosed error (`ambient [category]: …`) · `2` **partial
result** (output delivered, coverage incomplete — never a clean pass) · `3` no key
configured · `64` usage error · `130` interrupted.

Every `--json` surface emits one envelope: `{"schema_version": 1, "kind":
"ask|code|audit|consensus|build", "status": "ok|partial", "model", "partial",
"coverage_gap", "exit_code", …}` plus `content`, or `findings`+`verdict`, or
`files[]`+`failed[]`+`advisory_steps[]`. The shape never depends on how the result
was computed (single-shot vs map-reduce).

## When something fails

Errors are pre-diagnosed, so you're never left guessing whether "Ambient is down":

| You see | It means | Fix |
|---|---|---|
| `ambient [key]` | Key revoked/expired/mistyped | `ambient setup --force` with a fresh key |
| `ambient [funds]` | Account out of credit/quota | Top up at app.ambient.xyz |
| `ambient [model]` | No miners serving that model right now | `ambient models`, pick a READY one |
| `ambient [rate]` | Rate limited | Wait and retry |
| `ambient [service]` | Ambient-side problem | Retry shortly — not your fault |
| `ambient [network]` | Can't reach the API at all | Check your own internet first |
| `ambient [setup]` | No API key configured yet | `ambient setup` |

`ambient doctor` runs the full checkup (config perms, key validity via a real
authenticated completion, model availability, launcher, agent lane, network) and
prints a one-line DIAGNOSIS.

## Security posture

- The key lives in the macOS Keychain / libsecret (0600 env-file fallback, written
  atomically, permissions self-healed); never in argv, never printed, redacted from
  every output path, verified with a real authenticated request before saving.
- Model output is treated as untrusted AND sanitized — ANSI/OSC terminal escapes
  are stripped so a malicious miner can't forge verdicts or fire clipboard writes.
- A built-in tripwire refuses to send credential-looking content or
  credential-named files (`.env`, `.netrc`, `id_rsa`, `*.pem`, `credentials.json`,
  …) — locations only, never values; `--allow-secrets` for false positives.
- `ambient build` writes only inside the target directory through a path-traversal
  firewall (no `..`, no symlink escapes, no `.git`, no credential files, byte caps)
  and never executes anything — suggested commands are printed as text.
- The key is only ever sent to `*.ambient.xyz`; any other endpoint requires an
  explicit, typed `ambient trust-url` confirmation.
- **One exception, by design:** `ambient agent` passes the key to the opencode
  subprocess via its environment — the standard credential model of `aws`/`gh`/
  `docker`. That lane reads files itself, outside the tripwire; keep credentials
  out of its working tree.
- No telemetry. Usage metering is local (`~/.config/ambient/usage.jsonl`, 0600).

## Uninstall

```bash
ambient setup --remove      # delete the stored key (Keychain + env file)
ambient cache clear         # drop cached model output
ambient link --remove       # remove the PATH launcher
/plugin uninstall ambient-code@cryptoxinu
```

`~/.config/ambient/` keeps only your sticky settings after that — delete it to
reset everything.

## Notes

- Codex CLI support is staged but blocked upstream: Codex ≥0.142 requires the
  OpenAI Responses API and Ambient's `/v1/responses` endpoint currently rejects
  Codex's tool schema. `ambient codex` explains; `ambient agent` is the working
  agentic lane meanwhile.
- Single-file stdlib-only Python CLI (`bin/ambient`, Python 3.8+); hermetic tests
  (`python3 -m unittest discover -s tests`), live battery (`tools/stress_test.sh`),
  CI on macOS/Linux/Windows × Python 3.8-3.13. Releases: `docs/RELEASING.md`.

MIT licensed. Ambient and ambient.xyz are trademarks of their respective owner.
