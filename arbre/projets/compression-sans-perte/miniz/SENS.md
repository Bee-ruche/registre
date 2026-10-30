---
parent: projets/compression-sans-perte
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0010
budget_lignes: 40
---
# miniz
## Pourquoi cette branche existe
Deflate et Inflate compatibles zlib, en quelques fichiers C embarqués partout. Fork `Bee-ruche/minizBee`, branche
`master` ; son outillage : `bee/README.md` du fork.
## Ce qui compte ici
Juge : ce que miniz compresse, zlib le décompresse, et inversement (empreintes, tests différentiels, fuzzing).
Métriques (projets/miniz.yaml) : débits de compression n1, n6, n9 et de décompression, jugés sur leurs instructions ;
`ratio_n6` ; `memoire_max_ko`.
Juge isolé : la CI exécute ton code en conteneur sans réseau et vérifie chaque sortie avec une autre zlib. Une
construction suspecte (appel système, Valgrind, horloge, constructeur, symbole de la libc remplacé) appelle un gardien :
n'en mets pas sans raison, justifie dans `changement` les légitimes (SIMD). Sinon, pas de gardien (R3).
Pièges : lectures non alignées par memcpy vers une variable locale, jamais de transtypage de pointeur ; un chemin
générique gardé (R6) ; la décompression bute sur la mémoire plus que sur les instructions.
Zones : compression `miniz_tdef.c`, décompression `miniz_tinfl.c`, API zlib (`mz_*`).
## Ce qu'on peut ignorer ici
Les archives ZIP (`miniz_zip.c`) et l'écriture PNG, hors périmètre.
## Enfants
Aucun pour l'instant : les nœuds des zones s'écriront par la tâche proposée ruche-0014.
