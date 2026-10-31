#!/usr/bin/env bash
# Monte une ruche simulée pour une répétition générale (gouvernance/consignes/repetition-generale.md).
# Usage : outils/repetition/monter.sh <dossier> <gardien> <pseudo>...   (depuis un clone du registre réel)
# Exemple : outils/repetition/monter.sh /tmp/simu4 hugo hugo ines jules karim lea
# Tout vient de la branche main du clone (registre et outils de la simulation), quelle que soit la branche courante.
# Tout est local : un dépôt nu qui joue GitHub, un clone de confiance (le code de main qui vérifie les PR), un clone par
# membre simulé. Rien n'est envoyé nulle part.
set -euo pipefail
[ "$#" -ge 3 ] || { echo "usage : monter.sh <dossier> <gardien> <pseudo>..." >&2; exit 2; }
S="$(realpath -m "$1")"; gardien="$2"; shift 2
for p in "$gardien" "$@"; do [[ "$p" =~ ^[a-z0-9][a-z0-9-]{0,38}$ ]] || { echo "pseudo invalide : $p" >&2; exit 2; }; done
registre="$(git rev-parse --show-toplevel)"
commit="$(git -C "$registre" rev-parse --short main)"
[ ! -e "$S" ] || { echo "$S existe déjà" >&2; exit 2; }
mkdir -p "$S/outils" "$S/etat/journaux" "$S/etat/manifestes" "$S/abeilles"
# Une copie entière, sans liens durs vers les objets du clone réel.
git clone -q --bare --no-hardlinks "$registre" "$S/central.git"
git -C "$S/central.git" symbolic-ref HEAD refs/heads/main
git -C "$S/central.git" for-each-ref --format='%(refname:short)' refs/heads | grep -vx main | while read -r b; do
  git -C "$S/central.git" branch -q -D "$b"; done
git -C "$S/central.git" remote remove origin 2>/dev/null || true
# main n'avance que par les outils de la simulation (publier, decider-conseil, la CI simulée) : un membre qui pousse
# directement sur main est refusé. Garde-fou contre l'erreur honnête, pas contre un tricheur (voir commun.sh).
cat > "$S/central.git/hooks/pre-receive" <<'EOF'
#!/usr/bin/env bash
while read -r ancien nouveau ref; do
  if [ "$ref" = refs/heads/main ] && [ "${BEE_SIMU_ROBOT:-}" != 1 ]; then
    echo "main n'avance que par publier, decider-conseil ou la CI simulée (voir LISEZMOI.md)." >&2; exit 1
  fi
done
EOF
chmod +x "$S/central.git/hooks/pre-receive"
git clone -q "$S/central.git" "$S/confiance"
cd "$S/confiance"
mkdir -p membres
python3 - "$gardien" "$@" <<'EOF'
import sys, yaml
gardien, pseudos = sys.argv[1], sys.argv[2:]
p = "gouvernance/gardiens.yaml"
s = open(p, encoding="utf-8").read()
membres = (yaml.safe_load(s) or {}).get("membres") or []
if gardien not in {m.get("pseudo") for m in membres}:
    # Le garant du gardien simulé : le premier garant du registre (le fondateur), pour qu'il soit en fonction (R13).
    garants = (yaml.safe_load(open("gouvernance/garants.yaml", encoding="utf-8")) or {}).get("membres") or []
    garant = garants[0]["pseudo"] if garants else None
    fiche = f"  - pseudo: {gardien}\n" + (f"    garant: {garant}\n" if garant else "")
    if "membres: []" in s:
        s = s.replace("membres: []", "membres:\n" + fiche)
    else:
        s = s.rstrip("\n") + "\n" + fiche
open(p, "w", encoding="utf-8").write(s)
for i, pseudo in enumerate(sorted(set(pseudos + [gardien]))):
    open(f"membres/{pseudo}.yaml", "w", encoding="utf-8").write(
        f"pseudo: {pseudo}\ninscrit_le: '2026-10-30'\ncompte_cree_le: '{2016 + i % 8}-04-02'\n")
EOF
BEE_MAINTENANT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" python3 outils/bee.py valider >/dev/null
git add -A
git -c user.name=conseil -c user.email=conseil@simu.bee commit -qm "Ruche simulée : membres et gardien (registre au commit $commit)"
BEE_SIMU_ROBOT=1 git push -q origin HEAD:main
cd - >/dev/null
for p in "$@"; do mkdir -p "$S/abeilles/$p"; git clone -q "$S/central.git" "$S/abeilles/$p/registre"; done
echo 0 > "$S/etat/horloge"; echo 0 > "$S/etat/compteur_pr"; echo 9100 > "$S/etat/compteur_pr_fork"
: > "$S/etat/prs.tsv"; : > "$S/etat/commits_fork.tsv"; : > "$S/etat/annonces.md"; : > "$S/etat/executions_fork.tsv"
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
# Les outils de la simulation, pris dans main comme le reste.
for f in bee gh publier ouvrir-pr-fork pousser-pr-fork ci-simulee decider-conseil commun.sh horloge.py ci_simulee.py; do
  git -C "$registre" show "main:outils/repetition/$f" > "$S/outils/$f"
done
chmod +x "$S"/outils/{bee,gh,publier,ouvrir-pr-fork,pousser-pr-fork,ci-simulee,decider-conseil}
git -C "$registre" show main:outils/repetition/LISEZMOI-modele.md \
  | sed -e "s#\$BEE_SIMU#$S#g" -e "s#{{COMMIT}}#$commit#g" -e "s#{{DATE}}#$(date -u +%d/%m/%Y)#g" > "$S/LISEZMOI.md"
date -u +%Y-%m-%dT%H:%M:%SZ > "$S/etat/debut"
echo "Ruche simulée prête : $S (export BEE_SIMU=$S PATH=$S/outils:\$PATH). Membres : $*. Gardien : $gardien."
