# Shared checks of the simulated hive's tools (sourced, never run alone).
# They prevent honest mistakes: acting outside the simulation, in another member's name, or writing a line break
# into the state's logs. They do not separate the members at the system level (all the agents run under the same
# user): cheating on the simulation's plumbing teaches nothing about the hive, and is not a finding.
SIM="${BEE_SIM:?BEE_SIM: folder of the simulated hive}"
SIM="$(realpath -e "$SIM")"
[ -d "$SIM/central.git" ] && [ -d "$SIM/trust" ] || { echo "$SIM is not a simulated hive (tools/rehearsal/setup.sh)" >&2; exit 2; }
export BEE_SIM="$SIM"

# A simulated member's login: lowercase letters, digits and hyphens.
valid_login() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]{0,38}$ ]] || { echo "invalid login: $1" >&2; exit 2; }
}

# A text that goes into the state's tab-separated logs: no tab, no line break, no other control character.
valid_text() {
  if [[ "$1" == *[[:cntrl:]]* ]]; then echo "text refused (control character): use a single line" >&2; exit 2; fi
  [ -n "$1" ] || { echo "empty text" >&2; exit 2; }
}

# The member acts from their own clone of the simulation, and this clone points to the simulated repository.
in_own_clone() {
  local login="$1" expected clone origin_of
  valid_login "$login"
  expected="$(realpath -m "$SIM/bees/$login/registre")"
  clone="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$clone" ] && [ "$(realpath -e "$clone")" = "$expected" ] || {
    echo "Run this command from your clone: $expected (here: ${clone:-$(pwd)})" >&2; exit 2; }
  origin_of="$(git -C "$clone" remote get-url origin 2>/dev/null || true)"
  [ -n "$origin_of" ] && [ "$(realpath -m "$origin_of")" = "$SIM/central.git" ] || {
    echo "The clone $clone does not point to $SIM/central.git: refused" >&2; exit 2; }
}
