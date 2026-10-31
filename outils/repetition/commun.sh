# Vérifications communes des outils de la ruche simulée (sourcé, jamais lancé seul).
# Elles évitent les erreurs honnêtes : agir hors de la simulation, au nom d'un autre membre, ou écrire un saut de ligne
# dans les journaux de l'état. Elles ne séparent pas les membres au niveau du système (tous les agents tournent sous le
# même utilisateur) : tricher sur la plomberie de la simulation n'apprend rien sur la ruche, et n'est pas un constat.
SIMU="${BEE_SIMU:?BEE_SIMU : dossier de la ruche simulée}"
SIMU="$(realpath -e "$SIMU")"
[ -d "$SIMU/central.git" ] && [ -d "$SIMU/confiance" ] || { echo "$SIMU n'est pas une ruche simulée (outils/repetition/monter.sh)" >&2; exit 2; }
export BEE_SIMU="$SIMU"

# Le pseudo d'un membre simulé : lettres minuscules, chiffres et tirets.
pseudo_valide() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]{0,38}$ ]] || { echo "pseudo invalide : $1" >&2; exit 2; }
}

# Un texte qui part dans les journaux tabulés de l'état : ni tabulation, ni saut de ligne, ni autre caractère de contrôle.
texte_valide() {
  if printf '%s' "$1" | LC_ALL=C grep -q '[[:cntrl:]]'; then echo "texte refusé (caractère de contrôle) : utilisez une seule ligne" >&2; exit 2; fi
  [ -n "$1" ] || { echo "texte vide" >&2; exit 2; }
}

# Le membre agit depuis son propre clone de la simulation, et ce clone pointe vers le dépôt simulé.
dans_son_clone() {
  local pseudo="$1" attendu clone origine
  pseudo_valide "$pseudo"
  attendu="$(realpath -m "$SIMU/abeilles/$pseudo/registre")"
  clone="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$clone" ] && [ "$(realpath -e "$clone")" = "$attendu" ] || {
    echo "Lancez cette commande depuis votre clone : $attendu (ici : ${clone:-$(pwd)})" >&2; exit 2; }
  origine="$(git -C "$clone" remote get-url origin 2>/dev/null || true)"
  [ -n "$origine" ] && [ "$(realpath -m "$origine")" = "$SIMU/central.git" ] || {
    echo "Le clone $clone ne pointe pas vers $SIMU/central.git : refusé" >&2; exit 2; }
}
