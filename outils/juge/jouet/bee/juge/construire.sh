#!/bin/sh
# Construction d'une variante (A = base, B = PR) du projet jouet, DANS le conteneur sans réseau.
# Lancé par le juge commun (outils/juge/juge.py) : construire.sh <sources> <outillage_base> <sortie>
#   <sources>         rle.c et rle.h de la variante (lecture seule)
#   <outillage_base>  copie de la BASE : bee/juge/ et ses en-têtes dans base/
#   <sortie>          dossier inscriptible : obj/, execution, relevés d'analyse
# Le harnais est compilé avec rle.h de la BASE ; seul rle.c de la variante l'est avec ses propres en-têtes.
set -eu
umask 000
sources="$1"
outillage="$2"
sortie="$3"
mkdir -p "$sortie/obj"
cc -O2 -g -std=gnu99 -I"$sources" -c "$sources/rle.c" -o "$sortie/obj/rle.o"
cc -O2 -g -std=gnu99 -Wall -Wextra -I"$outillage/base" "$outillage/bee/juge/execution.c" "$sortie/obj/rle.o" -o "$sortie/execution"
nm -P -A "$sortie/obj/rle.o" > "$sortie/symboles.txt"
objdump -h "$sortie/obj/rle.o" > "$sortie/sections.txt"
objdump -d --no-show-raw-insn "$sortie/obj/rle.o" > "$sortie/desassemblage.txt"
echo "construction terminée"
