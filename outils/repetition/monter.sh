#!/usr/bin/env bash
# Monte une ruche simulée pour une répétition générale (gouvernance/consignes/repetition-generale.md).
# Usage : outils/repetition/monter.sh <dossier> <gardien> <pseudo>...   (depuis un clone du registre réel, sur main)
# Exemple : outils/repetition/monter.sh /tmp/simu4 hugo hugo ines jules karim lea
# Tout est local : un dépôt nu qui joue GitHub, un clone de confiance (le code de main qui vérifie les PR),
# un clone par membre simulé. Rien n'est envoyé nulle part.
set -euo pipefail
S="$1"; gardien="$2"; shift 2
[ "$#" -ge 1 ] || { echo "au moins un pseudo" >&2; exit 2; }
registre="$(git rev-parse --show-toplevel)"
[ ! -e "$S" ] || { echo "$S existe déjà" >&2; exit 2; }
mkdir -p "$S/outils" "$S/etat/journaux" "$S/etat/manifestes" "$S/abeilles"
git clone -q --bare "$registre" "$S/central.git"
git -C "$S/central.git" symbolic-ref HEAD refs/heads/main
git -C "$S/central.git" for-each-ref --format='%(refname:short)' refs/heads | grep -vx main | while read -r b; do
  git -C "$S/central.git" branch -q -D "$b"; done
git -C "$S/central.git" remote remove origin 2>/dev/null || true
git clone -q "$S/central.git" "$S/confiance"
cd "$S/confiance"
mkdir -p membres
python3 - "$gardien" "$@" <<'EOF'
import sys
gardien, pseudos = sys.argv[1], sys.argv[2:]
p = "gouvernance/gardiens.yaml"
s = open(p, encoding="utf-8").read()
if "membres: []" in s:
    s = s.replace("membres: []", f"membres:\n  - pseudo: {gardien}")
open(p, "w", encoding="utf-8").write(s)
for i, pseudo in enumerate(sorted(set(pseudos + ["bruno"]))):
    open(f"membres/{pseudo}.yaml", "w", encoding="utf-8").write(
        f"pseudo: {pseudo}\ninscrit_le: '2026-10-30'\ncompte_cree_le: '{2016 + i % 8}-04-02'\n")
EOF
BEE_MAINTENANT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" python3 outils/bee.py valider >/dev/null
git add -A
git -c user.name=conseil -c user.email=conseil@simu.bee commit -qm "Ruche simulée : membres et gardien ($(git -C "$registre" rev-parse --short HEAD))"
git push -q origin HEAD:main
cd - >/dev/null
for p in "$@"; do mkdir -p "$S/abeilles/$p"; git clone -q "$S/central.git" "$S/abeilles/$p/registre"; done
echo 0 > "$S/etat/horloge"; echo 0 > "$S/etat/compteur_pr"; echo 9100 > "$S/etat/compteur_pr_fork"
: > "$S/etat/prs.tsv"; : > "$S/etat/commits_fork.tsv"; : > "$S/etat/annonces.md"
# Les vraies PR des contributions en relecture, attribuées à leur auteur réel (sinon une relecture y est refusée).
python3 - "$S" <<'EOF'
import glob, sys, yaml
S = sys.argv[1]
with open(f"{S}/etat/prs_fork.tsv", "w", encoding="utf-8") as f:
    for chemin in sorted(glob.glob(f"{S}/confiance/contributions/*/*.yaml")):
        c = yaml.safe_load(open(chemin, encoding="utf-8")) or {}
        if c.get("statut") == "en_relecture" and c.get("pr"):
            f.write(f"{c['pr']}\t{c.get('auteur', '')}\t{c.get('tache', '')} (vraie PR)\n")
EOF
cp "$registre"/outils/repetition/{bee,publier,ouvrir-pr-fork,pousser-pr-fork,ci-simulee,decider-conseil,horloge.py,ci_simulee.py} "$S/outils/"
chmod +x "$S"/outils/{bee,publier,ouvrir-pr-fork,pousser-pr-fork,ci-simulee,decider-conseil}
sed "s#\$BEE_SIMU#$S#g" "$registre/outils/repetition/LISEZMOI-modele.md" > "$S/LISEZMOI.md"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/etat/debut"
echo "Ruche simulée prête : $S (export BEE_SIMU=$S ; PATH=$S/outils:\$PATH). Membres : $*. Gardien : $gardien."
