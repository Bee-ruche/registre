---
parent: racine
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0010
budget_lignes: 40
---
# Compression sans perte
## Pourquoi cette branche existe
Les compresseurs servent à chaque transfert et à chaque archive.
## Ce qui compte ici
Preuve : aller-retour bit à bit, compatible avec la référence dans les deux sens. Une tâche d'optimisation fixe
`sortie_compressee` : `identique`, ou `peut_changer` si `ratio_n6` ne baisse pas.
## Ce qu'on peut ignorer ici
bzip2 (pas encore ouvert : ruche-0002).
## Enfants
- `projets/compression-sans-perte/miniz` : miniz, Deflate et Inflate compatibles zlib
