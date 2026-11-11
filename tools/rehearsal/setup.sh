#!/usr/bin/env bash
# Sets up a simulated hive for a dress rehearsal (governance/briefs/dress-rehearsal.md).
# Usage: tools/rehearsal/setup.sh <dir> <guardian> <login>...   (from a clone of the real registry)
# Example: tools/rehearsal/setup.sh /tmp/sim4 hugo hugo ines jules karim lea
# Everything comes from the clone's main branch (the registry and the simulation's tools), whatever the current branch.
# Everything is local: a bare repository that plays GitHub, a trusted clone (main's code, which checks the PRs), one
# clone per simulated member. Nothing is sent anywhere.
set -euo pipefail
[ "$#" -ge 3 ] || { echo "usage: setup.sh <dir> <guardian> <login>..." >&2; exit 2; }
S="$(realpath -m "$1")"; guardian="$2"; shift 2
for p in "$guardian" "$@"; do [[ "$p" =~ ^[a-z0-9][a-z0-9-]{0,38}$ ]] || { echo "invalid login: $p" >&2; exit 2; }; done
registre="$(git rev-parse --show-toplevel)"
commit="$(git -C "$registre" rev-parse --short main)"
[ ! -e "$S" ] || { echo "$S already exists" >&2; exit 2; }
mkdir -p "$S/tools" "$S/state/journals" "$S/state/manifests" "$S/bees"
# A full copy, with no hard links to the real clone's objects.
git clone -q --bare --no-hardlinks "$registre" "$S/central.git"
git -C "$S/central.git" symbolic-ref HEAD refs/heads/main
git -C "$S/central.git" for-each-ref --format='%(refname:short)' refs/heads | { grep -vx main || true; } | while read -r b; do
  git -C "$S/central.git" branch -q -D "$b"; done
git -C "$S/central.git" remote remove origin 2>/dev/null || true
# The simulated repository moves only through the simulation's tools (publish, council-decide, the simulated CI), and a
# pushed PR is not rewritten. A guard against honest mistakes, not against a cheater (see common.sh).
cat > "$S/central.git/hooks/pre-receive" <<'EOF'
#!/usr/bin/env bash
zero=0000000000000000000000000000000000000000
while read -r old new ref; do
  if [ "${BEE_SIM_ROBOT:-}" != 1 ]; then
    echo "The simulated repository moves only through publish, council-decide or the simulated CI (see README.md)." >&2; exit 1
  fi
  case "$ref" in refs/heads/pr/*) [ "$old" = "$zero" ] || { echo "$ref already exists: a PR is not rewritten." >&2; exit 1; };; esac
done
EOF
chmod +x "$S/central.git/hooks/pre-receive"
git clone -q "$S/central.git" "$S/trust"
cd "$S/trust"
mkdir -p members
python3 - "$guardian" "$@" <<'EOF'
import sys, yaml
guardian, logins_list = sys.argv[1], sys.argv[2:]
p = "governance/guardians.yaml"
s = open(p, encoding="utf-8").read()
members = (yaml.safe_load(s) or {}).get("members") or []
if guardian not in {m.get("login") for m in members}:
    # The simulated guardian's guarantor: the registry's first guarantor (the founder), so that the guardian is in office (R13).
    guarantors = (yaml.safe_load(open("governance/guarantors.yaml", encoding="utf-8")) or {}).get("members") or []
    guarantor = guarantors[0]["login"] if guarantors else None
    entry_card = f"  - login: {guardian}\n" + (f"    guarantor: {guarantor}\n" if guarantor else "")
    if "members: []" in s:
        s = s.replace("members: []", "members:\n" + entry_card)
    else:
        s = s.rstrip("\n") + "\n" + entry_card
open(p, "w", encoding="utf-8").write(s)
for i, login in enumerate(sorted(set(logins_list + [guardian]))):
    open(f"members/{login}.yaml", "w", encoding="utf-8").write(
        f"login: {login}\nregistered_on: '2026-10-30'\naccount_created_on: '{2016 + i % 8}-04-02'\n")
EOF
BEE_NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)" python3 tools/bee.py validate >/dev/null
git add -A
git -c user.name=council -c user.email=council@simu.bee commit -qm "Simulated hive: members and guardian (registry at commit $commit)"
BEE_SIM_ROBOT=1 git push -q origin HEAD:main
cd - >/dev/null
for p in "$@"; do mkdir -p "$S/bees/$p"; git clone -q "$S/central.git" "$S/bees/$p/registre"; done
echo 0 > "$S/state/clock"; echo 0 > "$S/state/compteur_pr"; echo 9100 > "$S/state/compteur_pr_fork"
: > "$S/state/prs.tsv"; : > "$S/state/commits_fork.tsv"; : > "$S/state/announcements.md"; : > "$S/state/executions_fork.tsv"
# The real PRs of the contributions in review, attributed to their real author (otherwise a review of them is refused).
python3 - "$S" <<'EOF'
import glob, sys, yaml
S = sys.argv[1]
with open(f"{S}/state/prs_fork.tsv", "w", encoding="utf-8") as f:
    for path in sorted(glob.glob(f"{S}/trust/contributions/*/*.yaml")):
        c = yaml.safe_load(open(path, encoding="utf-8")) or {}
        if c.get("status") == "in_review" and c.get("pr"):
            f.write(f"{c['pr']}\t{c.get('author', '')}\t{c.get('task', '')} (real PR)\n")
EOF
# The simulation's tools, taken from main like the rest.
for f in bee gh publish open-fork-pr push-fork-pr simulated-ci council-decide common.sh clock.py simulated_ci.py; do
  git -C "$registre" show "main:tools/rehearsal/$f" > "$S/tools/$f"
done
chmod +x "$S"/tools/{bee,gh,publish,open-fork-pr,push-fork-pr,simulated-ci,council-decide}
git -C "$registre" show main:tools/rehearsal/README-template.md \
  | sed -e "s#\$BEE_SIM#$S#g" -e "s#{{COMMIT}}#$commit#g" -e "s#{{DATE}}#$(date -u +%Y-%m-%d)#g" > "$S/README.md"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/state/beginning"
echo "Simulated hive ready: $S (export BEE_SIM=$S PATH=$S/tools:\$PATH). Members: $*. Guardian: $guardian."
