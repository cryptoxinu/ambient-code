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
  real="${CLAUDE_PLUGIN_ROOT}/bin/ambient"
  # Heal ONLY this well-known path, and ONLY when it is a SYMLINK we OWN:
  #  - dangling (a plugin update GC'd the old versioned dir it pointed at), or
  #  - a stale ambient-code launcher (target exists but is not the ACTIVE
  #    install).
  # OWNERSHIP is proven by an `ambient-code` path component in the stored
  # target (every real install — dev `.../skills/ambient-code/...` or
  # marketplace `.../ambient-code/<ver>/...` — has it; a DIFFERENT tool merely
  # named `ambient` does not). A real (non-symlink) file, or a symlink to any
  # non-ambient-code target, is NEVER touched — never clobber a foreign
  # `ambient` the user installed themselves. readlink still reports the stored
  # target of a broken (dangling) symlink, so the same guard covers both cases.
  if [ -L "$link" ]; then
    target="$(readlink "$link" 2>/dev/null || true)"
    case "$target" in
      */ambient-code/*)
        if [ ! -e "$link" ] || [ "$target" != "$real" ]; then
          "$real" link >/dev/null 2>&1 || true
        fi
        ;;
    esac
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
