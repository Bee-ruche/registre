#!/bin/sh
# Construction d'une variante (A = base, B = PR) du projet jouet, DANS le conteneur sans réseau.
# Lancé par le juge commun (outils/juge/juge.py) : construire.sh <sources> <outillage_base> <sortie>
#   <sources>         rle.c et rle.h de la variante (lecture seule)
#   <outillage_base>  copie de la BASE : bee/juge/ et ses en-têtes dans base/
#   <sortie>          dossier inscriptible : obj/ (un objet par fichier .c du projet) et execution
# Le harnais est compilé avec rle.h de la BASE ; seul rle.c de la variante l'est avec ses propres en-têtes.
# Les relevés d'analyse (nm, objdump) sont produits ensuite par le juge commun sur tous les objets de obj/.
set -eu
umask 000
sources="$1"
outillage="$2"
sortie="$3"
mkdir -p "$sortie/obj"
cc -O2 -g -std=gnu99 -I"$sources" -c "$sources/rle.c" -o "$sortie/obj/rle.o"
cc -O2 -g -std=gnu99 -Wall -Wextra -I"$outillage/base" "$outillage/bee/juge/execution.c" "$sortie/obj/rle.o" -o "$sortie/execution"
echo "construction terminée"
