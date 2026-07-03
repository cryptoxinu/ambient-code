#!/usr/bin/env bash
# SessionStart hook (startup|resume|clear|compact):
#  1. Self-heal the ~/.local/bin/ambient launcher — plugin updates move the
#     versioned install dir, and the old dir is garbage-collected later, which
#     would leave the user's terminal `ambient` dangling.
#  2. Remind Claude when Ambient delegate mode is ON.
# Prints nothing (adds no context) in the normal case.
set -eu

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "${CLAUDE_PLUGIN_ROOT}/bin/ambient" ]; then
  link="$HOME/.local/bin/ambient"
  if [ -L "$link" ]; then
    target="$(readlink "$link" 2>/dev/null || true)"
    real="${CLAUDE_PLUGIN_ROOT}/bin/ambient"
    if [ "$target" != "$real" ]; then
      # Repair quietly: the launcher must always point at the ACTIVE install.
      "${CLAUDE_PLUGIN_ROOT}/bin/ambient" link >/dev/null 2>&1 || true
    fi
  fi
fi

conf="$HOME/.config/ambient/env"
[ -f "$conf" ] || exit 0
# Last assignment wins, matching the CLI's config parser — a duplicate
# AMBIENT_DELEGATE line must not make the hook disagree with `ambient mode`.
if [ "$(sed -n 's/^AMBIENT_DELEGATE=//p' "$conf" 2>/dev/null | tail -1)" = "on" ]; then
  cat <<'MSG'
Ambient delegate mode is ON (persisted setting). Per the ambient skill's delegate
contract: the user plans with Claude, Ambient (default Kimi) writes the code, Claude
reviews and integrates. Route substantive code writing through `ambient build`
(multi-file, manifest + --apply) or `ambient code` (single file); review every
generated diff and run the tests yourself. Trivial edits stay with Claude. The user
toggles this with /ambient off.
MSG
fi
exit 0
