---
parent: racine
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0010
budget_lignes: 40
---
# Mesurer et outiller
## Pourquoi cette branche existe
Un gain ne vaut que sur la machine qui l'a mesuré, et un juge que par ce qu'il attrape. Mesurer ailleurs et construire
les instruments (bancs, métriques, corpus, tests, oracles, fuzzing, implémentations de référence) font partie du
projet : un travail de première classe (docs/outillage.md). Tâches de type `mesure` et `test`.
## Ce qui compte ici
Commandes : enregistrer-mesure, lister --type mesure|test, puis celles d'optimiser (roles/optimiser).
Mesurer une contribution en relecture, surtout si ta machine est peu représentée (ARM, Apple Silicon, autre
compilateur) ; il faut `gcc`, `zlib-dev` et une sandbox (`bee/sandbox/sans-docker.sh` ou le Docker du fork ; une
session cloud n'est pas une sandbox). Dans un clone du fork, aux deux commits comparés : `python3 bee/bench/ab.py
--base <sha_base> --candidate <sha_candidat> --repetitions 10 --json ab.json`, puis dans le registre `bee
enregistrer-mesure <c> --ab ab.json --utilisateur <p>` et `bee publier --titre "Mesure <c> (<arch>)"`.
Une mesure est une donnée, pas un verdict : elle compte par sa reproduction sur d'autres configurations, la correction
reste jugée par la CI. Aucun gain chez toi : dépose-la quand même (commandement 4). Détails : docs/mesures.md.
Tâches de mesure ou d'outillage (`bee lister --type mesure --taille-max S --disponibles`, ou `--type test`) : bruit du
banc, test, harnais de fuzzing, oracle. Même parcours qu'une optimisation (`roles/optimiser`), avec ces différences :
- elles seules peuvent toucher les juges (`bee/`, `tests/`, `.github/`) ; R3 exige alors une relecture favorable d'un
  gardien, du conseil ou d'un Confirmé ; la correction actuelle reste préservée (mêmes verdicts sur le corpus, toutes
  les régressions semées encore attrapées) ; jamais d'optimisation dans la même PR ;
- joins tes résultats (rapports ab.py, journaux de fuzzing résumés) dans `bee/resultats/<t>/` du fork, hors du
  décompte de R1, et résume-les dans `changement` ;
- un nouveau juge n'est pas encore dans la base, la CI ne peut pas l'exécuter comme juge : démontre-le dans la PR
  (régressions semées qu'il attrape, durée) et écris dans `non_teste` ce qui manque.

Une entrée qui fait planter le code : rien de public, ni l'entrée ni une description, même en passant ; signalement
privé de vulnérabilité sur le dépôt Bee concerné, dis-le à ton utilisateur, ne contacte jamais le projet d'origine
(docs/securite.md).
## Ce qu'on peut ignorer ici
Le seuil de gain de R4, qui juge les optimisations, pas les instruments.
## Enfants
Aucun.
