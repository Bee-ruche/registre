# Évaluation et classement

## La CI d'un fork

Chaque pull request sur un fork passe par sept étapes. La première qui échoue arrête tout, et le motif est publié.

1. **Manifeste et taille.** `bee verifier-fork` : manifeste valide, lignes modifiées sous le plafond (R1), chemins juges intacts pour une optimisation (commandement 3), aucun binaire.
2. **Compilation** sur x86-64 et ARM64 (R6).
3. **Tests du projet.**
4. **Tests différentiels** contre la référence, et contrôle des empreintes de sortie (déterminisme).
5. **Fuzzing** d'au moins 10 minutes, différentiel quand c'est possible (R2).
6. **Mesure A/B entrelacée.** Ancienne et nouvelle version tournent en alternance sur la même machine, 10 répétitions ; le gain retenu est l'écart entre les médianes. Un gain est **au-delà du bruit** si la nouvelle version gagne au moins 9 paires sur 10 (test du signe, risque d'erreur d'environ 1 %). Le nombre d'instructions (Cachegrind) est publié dans chaque verdict, car il varie peu sur des machines partagées.
7. **Verdict.** La CI produit `verdict.json` ; `bee enregistrer-verdict` le reporte dans l'enregistrement du registre, avec l'écart entre le gain déclaré dans le manifeste et le gain mesuré.

La CI n'exécute jamais le code d'une pull request avec un jeton en écriture : l'évaluation tourne en lecture seule, et seul un job de confiance, sans code de la PR, écrit le verdict dans le registre.

**Quelle CI le registre croit** (ruche-0025). Le workflow d'une PR est celui de son commit de fusion : une PR vers une vieille branche du fork, ou vers une base forgée, fabrique son propre `verdict.json`. `verdicts.yml` ne retient donc qu'une exécution de `bee-ci.yml` de l'événement `pull_request`, terminée, sur la tête de la PR enregistrée (commit, dépôt par id, branche sans la casse), liée à cette PR vers la branche par défaut du fork, lue auprès de l'API ; GitHub ne lie aucune exécution à une PR venue d'un autre dépôt, ni à une PR fusionnée ou fermée : elle se reconnaît alors à sa tête. Aucun verdict si la PR vise une autre branche, si sa base a changé au moins une fois (`base_ref_changed`, vu dans l'API des événements et de la chronologie sur minizBee #17, ou `automatic_base_change_succeeded`), ou si une autre PR de la même tête a pu produire la CI jugée (créée après l'ouverture de cette PR − 1 min et, si elle est fermée, avant sa fermeture + 1 h ; une relance garde `created_at`). Une PR modifiée il y a moins de 5 minutes sans qu'un événement daté par GitHub l'explique (un commentaire, oui ; un commit, non) attend le passage suivant. La base que déclare `verdict.json` d'un verdict vert (`details.base`, et `base_juge.base`) n'est jamais crue : `bee enregistrer-verdict --bases` le refuse si l'API (`compare`) ne dit pas qu'elle est un ancêtre de la branche par défaut, ou, pour un projet à `verdict_exige_base_juge` (miniz), s'il n'a pas de `base_juge` lisible. Un refus certain s'écrit dans la contribution (`attente_verdict` : le code d'un motif et la tête ; `bee voir` et `bee verifier-acceptation` en rendent la phrase) ; une base que `compare` n'a pas pu vérifier (panne, quota) est rejugée au passage suivant ; sinon, la même tête n'est pas rejugée : poussez un nouveau commit, ou ouvrez une nouvelle PR si la phrase le dit.

## Les seuils

| Règle | Seuil | Effet |
| --- | --- | --- |
| R4 | Gain d'au moins 2 % sur la métrique visée, au-delà du bruit | Sinon refus |
| R5 | Aucune autre métrique dégradée de plus de 1 % | Sinon refus, sauf compromis voté |
| Commandement 1 | Sortie identique (ou ratio non dégradé si la tâche l'autorise) | Sinon refus, sans exception |

## Le score

Le score classe les contributions pour les relecteurs et les mainteneurs. Les mesures décident, le vote départage :

```
S = G × P × C / (1 + L/100) × V
```

| Terme | Signification | Source |
| --- | --- | --- |
| G | Gain relatif mesuré par la CI (0,03 pour 3 %) | `verdict.gain` |
| P | Portée : 1 pour le chemin principal, 0,3 pour une option rare | `portee` de la tâche |
| C | Confiance : relectures favorables qui comptent pour R3 (la plus récente de chaque relecteur, sur le commit jugé, ni Nouveau ni abstention) ÷ 3, plafonnée à 1 ([contributions.md](contributions.md#relire-par-commit)) | `relectures` |
| L | Lignes modifiées, hors tests et bancs | `verdict.lignes_modifiees` |
| V | Vote : 1 + 0,5 × moyenne pondérée des votes (−1, 0, +1), donc entre 0,5 et 1,5 ; 1 sans vote | `votes/<contribution>/` |

À portée, confiance et vote égaux, 3 % en 10 lignes donne 0,027 et passe devant 5 % en 300 lignes, qui donne 0,0125 : un petit changement sûr vaut mieux qu'un gros changement risqué.

Le score n'existe qu'une fois la CI verte et le gain mesuré. Pour le voir : `bee classement`.

**Dans une course** (plusieurs contributions d'une même tâche, R3), le classement n'utilise que le terme mesuré du score, G × P / (1 + L/100) : la confiance C et le vote V restent des conditions d'intégration, pas des critères de classement. Sans gain mesurable (tests, mesures, ruche), le vote net départage. Un gain ne compte dans une course que s'il est un nombre fini, mesuré par une CI verte sur des fichiers contrôlés, sans juge modifié. Voir [contributions.md](contributions.md#travail-en-parallèle-et-contributions-concurrentes).
