#!/usr/bin/env bash
# Exécute une commande dans le conteneur du juge (bee/juge/Dockerfile), sans réseau, sur un dossier de
# travail jetable : c'est ainsi que la CI lance tout ce qui exécute le code de la PR (tests d'origine,
# tests différentiels, fuzzing). Mêmes protections que bee/juge/juge.py : réseau coupé, système de
# fichiers en lecture seule, aucun privilège, utilisateur 65534. Le seul dossier visible est <travail>,
# monté sur /travail ; l'hôte ne réexécute jamais rien de ce que le conteneur y laisse.
#
# Usage : bee/juge/isoler.sh <image> <travail> [--pids N] [--memoire M] -- <commande> [arguments…]
#   <image>    étiquette de l'image (python3 bee/juge/juge.py --image-seulement)
#   <travail>  dossier de travail ; le préparer avec des COPIES fraîches (cp -a base pr …) pour chaque
#              étape : une étape précédente a pu y écrire n'importe quoi.
# Le code de sortie est celui de la commande.
set -euo pipefail

if [ $# -lt 4 ]; then
  sed -n '2,14p' "$0" >&2
  exit 2
fi
image="$1"
travail="$(cd "$2" && pwd)"
shift 2
pids=512
memoire=6g
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  case "$1" in
    --pids) pids="$2"; shift 2 ;;
    --memoire) memoire="$2"; shift 2 ;;
    *) echo "isoler.sh : option inconnue : $1" >&2; exit 2 ;;
  esac
done
[ "${1:-}" = "--" ] || { echo "isoler.sh : « -- » attendu avant la commande" >&2; exit 2; }
shift

# Le conteneur tourne sous l'utilisateur 65534 : il doit pouvoir écrire dans sa copie de travail.
chmod -R a+rwX "$travail"
exec docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 65534:65534 --pids-limit "$pids" --memory "$memoire" --memory-swap "$memoire" \
  --tmpfs /tmp:rw,noexec,nosuid,size=1g -e HOME=/tmp -e LC_ALL=C.UTF-8 \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  --mount "type=bind,source=$travail,target=/travail" -w /travail \
  "$image" "$@"
