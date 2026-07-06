# Privacy

`ambient-code` is local-first and sends nothing anywhere except the inference
endpoint you configure.

## What leaves your machine
- **Only** the prompts/code you explicitly send, and **only** to the Ambient API
  URL in your config (`https://api.ambient.xyz` by default). Nothing else.
- No analytics, no telemetry, no phone-home, no crash reporting. The single
  outbound host is your configured `AMBIENT_API_URL`.

## What stays on your machine
- Your API key: in the macOS Keychain (or a `chmod 600` file / OS secret store).
- Token/cost metering: a local `~/.config/ambient/usage.jsonl`, never uploaded.
- The chunk cache (on by default; `--no-cache` skips it): local only.

## Your responsibility
- Auditing code publishes it to the network you chose. The built-in secrets
  tripwire refuses obvious credentials and `.env` files, but review what you send.
- **Never** send secrets, credentials, or personal/health data.

## The `ambient agent` boundary
`ambient agent` launches [opencode](https://opencode.ai), a separate tool with
its own privacy behavior. This statement covers the `ambient` CLI itself, not
opencode. `ambient agent` passes your API key to opencode via the environment
(the standard credential model) — don't ask an agent to print its environment.

## On-disk inventory (all local, all owner-only)

| Path | Contents | Purge |
|---|---|---|
| OS keychain item `ambient.xyz` | your API key | `ambient setup --remove` |
| `~/.config/ambient/env` (0600) | endpoint, defaults, curation — key only with `--file` | delete the file |
| `~/.config/ambient/cache/*.json` (0600, 7-day TTL) | model output quoting your code (map-reduce chunk results) | `ambient cache clear` |
| `~/.config/ambient/usage.jsonl` (0600) | timestamps, model ids, token counts — no content | delete the file |
| `<build dir>/.ambient-build.json` (0600) | resume state incl. generated file contents | delete after applying |

Nothing is transmitted anywhere except your prompts/code to the Ambient API you
configured. No telemetry, no analytics, no phoning home.
