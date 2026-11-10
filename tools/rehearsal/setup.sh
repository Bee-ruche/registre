#!/usr/bin/env bash
# Monte une ruche simulée pour une répétition générale (gouvernance/consignes/repetition-generale.md).
# Usage : outils/repetition/monter.sh <dossier> <gardien> <pseudo>...   (depuis un clone du registre réel)
# Exemple : outils/repetition/monter.sh /tmp/simu4 hugo hugo ines jules karim lea
# Tout vient de la branche main du clone (registre et outils de la simulation), quelle que soit la branche courante.
# Tout est local : un dépôt nu qui joue GitHub, un clone de confiance (le code de main qui vérifie les PR), un clone par
# membre simulé. Rien n'est envoyé nulle part.
set -euo pipefail
[ "$#" -ge 3 ] || { echo "usage : setup.sh <dir> <guardian> <login>..." >&2; exit 2; }
S="$(realpath -m "$1")"; guardian="$2"; shift 2
for p in "$guardian" "$@"; do [[ "$p" =~ ^[a-z0-9][a-z0-9-]{0,38}$ ]] || { echo "pseudo invalide : $p" >&2; exit 2; }; done
registre="$(git rev-parse --show-toplevel)"
commit="$(git -C "$registre" rev-parse --short main)"
[ ! -e "$S" ] || { echo "$S existe déjà" >&2; exit 2; }
mkdir -p "$S/tools" "$S/state/journaux" "$S/state/manifests" "$S/abeilles"
# Une copie entière, sans liens durs vers les objets du clone réel.
git clone -q --bare --no-hardlinks "$registre" "$S/central.git"
git -C "$S/central.git" symbolic-ref HEAD refs/heads/main
git -C "$S/central.git" for-each-ref --format='%(refname:short)' refs/heads | { grep -vx main || true; } | while read -r b; do
  git -C "$S/central.git" branch -q -D "$b"; done
git -C "$S/central.git" remote remove origin 2>/dev/null || true
# Le dépôt simulé ne bouge que par les outils de la simulation (publier, decider-conseil, la CI simulée), et une PR
# poussée ne se réécrit pas. Garde-fou contre l'erreur honnête, pas contre un tricheur (voir commun.sh).
cat > "$S/central.git/hooks/pre-receive" <<'EOF'
#!/usr/bin/env bash
zero=0000000000000000000000000000000000000000
while read -r old new ref; do
  if [ "${BEE_SIM_ROBOT:-}" != 1 ]; then
    echo "Le dépôt simulé ne bouge que par publier, council-decide ou la CI simulée (voir LISEZMOI.md)." >&2; exit 1
  fi
  case "$ref" in refs/heads/pr/*) [ "$old" = "$zero" ] || { echo "$ref existe déjà : une PR ne se réécrit pas." >&2; exit 1; };; esac
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
    # Le garant du gardien simulé : le premier garant du registre (le fondateur), pour qu'il soit en fonction (R13).
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
git -c user.name=council -c user.email=council@simu.bee commit -qm "Ruche simulée : membres et gardien (registre au commit $commit)"
BEE_SIM_ROBOT=1 git push -q origin HEAD:main
cd - >/dev/null
for p in "$@"; do mkdir -p "$S/abeilles/$p"; git clone -q "$S/central.git" "$S/abeilles/$p/registre"; done
echo 0 > "$S/state/clock"; echo 0 > "$S/state/compteur_pr"; echo 9100 > "$S/state/compteur_pr_fork"
: > "$S/state/prs.tsv"; : > "$S/state/commits_fork.tsv"; : > "$S/state/annonces.md"; : > "$S/state/executions_fork.tsv"
# Les vraies PR des contributions en relecture, attribuées à leur auteur réel (sinon une relecture y est refusée).
python3 - "$S" <<'EOF'
import glob, sys, yaml
S = sys.argv[1]
with open(f"{S}/state/prs_fork.tsv", "w", encoding="utf-8") as f:
    for path in sorted(glob.glob(f"{S}/trust/contributions/*/*.yaml")):
        c = yaml.safe_load(open(path, encoding="utf-8")) or {}
        if c.get("status") == "in_review" and c.get("pr"):
            f.write(f"{c['pr']}\t{c.get('author', '')}\t{c.get('task', '')} (vraie PR)\n")
EOF
# Les outils de la simulation, pris dans main comme le reste.
for f in bee gh publish open-fork-pr push-fork-pr simulated-ci council-decide common.sh clock.py simulated_ci.py; do
  git -C "$registre" show "main:tools/rehearsal/$f" > "$S/tools/$f"
done
chmod +x "$S"/tools/{bee,gh,publish,open-fork-pr,push-fork-pr,simulated-ci,council-decide}
git -C "$registre" show main:tools/rehearsal/README-template.md \
  | sed -e "s#\$BEE_SIM#$S#g" -e "s#{{COMMIT}}#$commit#g" -e "s#{{DATE}}#$(date -u +%d/%m/%Y)#g" > "$S/LISEZMOI.md"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/state/beginning"
echo "Ruche simulée prête : $S (export BEE_SIM=$S PATH=$S/tools:\$PATH). Membres : $*. Gardien : $guardian."
