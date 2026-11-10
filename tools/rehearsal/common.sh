# Vérifications communes des outils de la ruche simulée (sourcé, jamais lancé seul).
# Elles évitent les erreurs honnêtes : agir hors de la simulation, au nom d'un autre membre, ou écrire un saut de ligne
# dans les journaux de l'état. Elles ne séparent pas les membres au niveau du système (tous les agents tournent sous le
# même utilisateur) : tricher sur la plomberie de la simulation n'apprend rien sur la ruche, et n'est pas un constat.
SIM="${BEE_SIM:?BEE_SIM : dossier de la ruche simulée}"
SIM="$(realpath -e "$SIM")"
[ -d "$SIM/central.git" ] && [ -d "$SIM/trust" ] || { echo "$SIM n'est pas une ruche simulée (tools/rehearsal/setup.sh)" >&2; exit 2; }
export BEE_SIM="$SIM"

# Le pseudo d'un membre simulé : lettres minuscules, chiffres et tirets.
valid_login() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9-]{0,38}$ ]] || { echo "pseudo invalide : $1" >&2; exit 2; }
}

# Un texte qui part dans les journaux tabulés de l'état : ni tabulation, ni saut de ligne, ni autre caractère de contrôle.
valid_text() {
  if [[ "$1" == *[[:cntrl:]]* ]]; then echo "texte refusé (caractère de contrôle) : utilisez une seule ligne" >&2; exit 2; fi
  [ -n "$1" ] || { echo "texte vide" >&2; exit 2; }
}

# Le membre agit depuis son propre clone de la simulation, et ce clone pointe vers le dépôt simulé.
in_own_clone() {
  local login="$1" expected clone origin_of
  valid_login "$login"
  expected="$(realpath -m "$SIM/abeilles/$login/registre")"
  clone="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$clone" ] && [ "$(realpath -e "$clone")" = "$expected" ] || {
    echo "Lancez cette commande depuis votre clone : $expected (ici : ${clone:-$(pwd)})" >&2; exit 2; }
  origin_of="$(git -C "$clone" remote get-url origin 2>/dev/null || true)"
  [ -n "$origin_of" ] && [ "$(realpath -m "$origin_of")" = "$SIM/central.git" ] || {
    echo "Le clone $clone ne pointe pas vers $SIM/central.git : refusé" >&2; exit 2; }
}
