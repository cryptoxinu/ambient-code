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
  # Heal ONLY this well-known path, and ONLY when it is a SYMLINK that is
  # ours to fix:
  #  - dangling (a plugin update GC'd the old versioned dir it pointed at), or
  #  - a stale ambient launcher (target exists, is named `ambient`, but is not
  #    the ACTIVE install).
  # A real (non-symlink) file, or a symlink to some other tool, is NEVER
  # touched — never clobber a foreign `ambient` the user installed themselves.
  if [ -L "$link" ]; then
    if [ ! -e "$link" ]; then
      # Dangling: recreate quietly — but ONLY if its stored target basename is
      # `ambient` (readlink still reports the target of a broken symlink), so a
      # dangling FOREIGN symlink at this path is never replaced. Symmetric with
      # the stale-symlink guard below.
      case "$(readlink "$link" 2>/dev/null || true)" in
        */ambient|ambient)
          "$real" link >/dev/null 2>&1 || true
          ;;
      esac
    else
      target="$(readlink "$link" 2>/dev/null || true)"
      if [ -n "$target" ] && [ "$target" != "$real" ]; then
        case "$target" in
          */ambient)
            # Stale ambient launcher — repoint at the ACTIVE install.
            "$real" link >/dev/null 2>&1 || true
            ;;
        esac
      fi
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
