---
parent: projets/compression-sans-perte/miniz
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0014
budget_lignes: 40
---
# Outillage du fork : bee/
## Pourquoi cette branche existe
`bee/` juge chaque contribution : corpus, tests différentiels et d'API, fuzzing, banc A/B, profileur, juge isolé, CI.
Ce sont des chemins juges : seules les tâches `test` et `mesure` y touchent, relues par un gardien, le conseil ou un
Confirmé (R3, roles/mesurer).
## Ce qui compte ici
Préserver la correction actuelle : `bee/tests/empreintes-reference.txt` compte 488 empreintes (8 niveaux × 61 fichiers,
à 9977da4) et ne se régénère que sur la base, jamais sur un candidat (miniz-0023, miniz-0024).
Couverture mesurée (gcc --coverage) : miniz_tdef.c 77,8 % des lignes et 70,2 % des branches, les stratégies autres que
celle par défaut n'étant tirées que par le fuzzing (miniz-0023, avant miniz-0024) ; miniz.c 94,4 % des branches depuis
miniz-0026. Le contrôle `flux-1` n'exerce pas le chemin rapide de tinfl (zone `inflate`).
Durée : `bee/tests/lancer.sh` sous 30 s sur la CI (critère de miniz-0023 et miniz-0024) ; avec `--sanitiseurs`, 34,6 s
avant `api.c`, qui ajoute environ 5 s (manifeste de miniz-0026, machine partagée).
Bruit au chronomètre : test A/A d'ab.py, de −1,4 % à +0,5 % (bee/README.md : Xeon 2,1 GHz virtualisé, base
2948eeb) ; environ ±0,4 % au juge isolé, sur les machines de GitHub (note de miniz-0018) ; ailleurs, à mesurer
(miniz-0003).
Profileur : depuis miniz-0033, un commentaire ne passe plus pour une fonction ; les noms à majuscules restent « hors
fonction » (miniz-0034). Compile le banc et profile dans la même session de `bee/sandbox/sans-docker.sh`, qui monte le
dépôt à un autre chemin à chaque fois, sinon tout part en « hors miniz » (miniz-0034). Le tableau de profil de
bee/README.md date de la base 2948eeb (miniz-0034).
Le juge isolé (miniz-0031) fait foi : il vérifie chaque sortie avec la zlib de l'hôte et compte tout le processus ; ses
méta-tests (`bee/juge/test_juge.py`) tournent sur toute PR qui modifie `bee/juge/`. Le passage au juge commun est en
relecture (miniz-0032) ; une PR qui touche `.github/` n'est jamais fusionnée automatiquement (note de miniz-0032).
Un nouveau juge prouve ce qu'il attrape : régressions semées dans une copie des sources (roles/mesurer). Le corpus,
61 fichiers et 12,0 Mo presque entièrement synthétiques (miniz-0028), ne change que par une tâche qui l'autorise
(bee/README.md).
## Ce qu'on peut ignorer ici
Le code de miniz (zones `deflate`, `inflate`, `api`), sauf pour y semer une régression dans une copie.
## Enfants
Aucun.
