---
parent: projets/compression-sans-perte
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0010
budget_lignes: 40
---
# miniz
## Pourquoi cette branche existe
Deflate et Inflate compatibles zlib, embarqués partout. Fork `Bee-ruche/minizBee`, branche `master` ; outillage :
`bee/README.md` du fork.
## Ce qui compte ici
Juge : ce que miniz compresse, zlib le décompresse, et inversement. Métriques : projets/miniz.yaml ; un débit se juge
sur ses instructions.
Juge isolé : la CI exécute ton code en conteneur sans réseau et vérifie chaque sortie avec une autre zlib ; chez toi :
`python3 bee/juge/juge.py --source-a <base> --source-b <ta copie>` (Docker). Ce qu'il juge suspect (appel système,
horloge, symbole de la libc remplacé…) appelle un gardien : justifie le légitime (SIMD) dans `changement`.
Pièges : lectures non alignées par memcpy vers une variable locale, jamais par transtypage de pointeur ; chemin
générique gardé (R6) ; la décompression bute sur la mémoire plus que sur les instructions.
Zones : compression `miniz_tdef.c`, décompression `miniz_tinfl.c`, API zlib (`mz_*`).
## Ce qu'on peut ignorer ici
ZIP (`miniz_zip.c`) et PNG, hors périmètre.
## Enfants
Aucun pour l'instant : zones à écrire (tâche proposée ruche-0014).
