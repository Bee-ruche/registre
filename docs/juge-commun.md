# Juge commun : un juge isolé pour tous les projets (spécification)

Statut : spécification du 28 octobre 2026, à construire une fois le juge isolé de minizBee intégré
(tâche miniz-0031). Contexte et raisons : [architecture.md](architecture.md), « La suite », chantier 2.

## Le problème

Le juge isolé de minizBee (`bee/juge/` du fork) mêle deux choses :
- **ce qui protège** et ne dépend d'aucun projet : l'image et l'isolement en conteneur, le lanceur
  `chrono` (temps lus par le noyau, résumé de Valgrind), la lecture sûre des sorties, l'analyse des
  objets compilés, la graine tirée après la compilation, les statistiques A/B, le rapport ;
- **ce qui juge miniz** : le harnais qui appelle la bibliothèque, les entrées (corpus, données tirées
  au hasard, flux zlib), la règle de vérification (sorties identiques à la base, aller-retour par
  la zlib de l'hôte), les scénarios et leurs métriques.

Recopier le tout dans chaque fork ferait autant de copies à corriger qu'il y a de projets. La revue
adverse du 27/10 l'a montré : une faille du juge se corrige une fois, ou elle reste ouverte ailleurs.

## Le partage

| Dans le registre (`outils/juge/`, étiqueté `juge-vN`) | Dans chaque fork (`bee/juge/`) |
| --- | --- |
| `Dockerfile.base` (image épinglée, paquets communs) et l'isolement (`isoler.sh`) | Les paquets propres au projet (une ligne `RUN` ajoutée à l'image commune) |
| `chrono.c` : lanceur, mesures par `wait4`, jeton, relevé du résumé de Valgrind | `execution.c` : le harnais, qui lit `entrees/liste` et écrit `sorties/` |
| `lecture.py` : lecture sûre des sorties (sans lien, sans fichier spécial, taille bornée) | `projet.py` : le greffon décrit ci-dessous |
| `analyse.py` : constructions suspectes (liste des fonctions permises fournie par le greffon) | Le corpus et son générateur (`bee/corpus/`) |
| `juge.py` : l'orchestration (compiler A et B, analyser, tirer la graine, vérifier, mesurer, instructions, rapport au format d'`ab.py` + section `juge`) | Les méta-tests propres au projet (variantes malveillantes du code du projet) |
| Les méta-tests du juge commun (sur un projet jouet) et le workflow réutilisable `juge.yml` (`workflow_call`) | L'appel du workflow, épinglé : `uses: Bee-ruche/registre/.github/workflows/juge.yml@juge-vN` |

## Le greffon d'un projet (`bee/juge/projet.py`)

Une classe sans état, lue par le juge commun **depuis la base de la PR** (jamais depuis la PR) :

| Élément | Rôle |
| --- | --- |
| `SOURCES` | motif des fichiers du projet copiés dans le conteneur (`miniz*.c`, `src/*.c`…) |
| `construire(variante)` | commandes de compilation dans le conteneur ; les en-têtes du harnais viennent de la base |
| `PERMIS` | fonctions externes permises au code du projet (mémoire, chaînes…), pour l'analyse des objets |
| `SCENARIOS` | nom, côté (`f` fichiers bruts, `z` données dérivées, jamais montés ensemble), métrique de débit et métrique d'instructions associées |
| `entrees(rng, corpus)` | entrées de vérification : corpus + données tirées au hasard + entrées invalides |
| `derivees(fichiers)` | entrées du second côté, produites par l'hôte (pour miniz, les flux zlib ; pour libyaml, rien ou des documents émis par la base) |
| `verifier(sorties_a, sorties_b, entrees)` | règle de justesse ; lève `Refus` au premier écart. Elle ne fait confiance qu'à la base (A) et à l'hôte |

Règle de sûreté : le greffon ne voit les sorties qu'à travers `lecture.py`, et n'exécute rien de ce
que le conteneur a produit. Une PR qui modifie `bee/juge/` est une tâche d'outillage : le registre
le détecte et exige un gardien (R3).

## Versions

- Le juge commun est versionné par étiquette (`juge-v1`, `juge-v2`…) dans le registre. Un changement
  passe par une PR d'outillage sur le registre, avec les méta-tests communs et ceux de chaque projet
  qui l'utilise, et la relecture de deux gardiens.
- Chaque fork épingle une version dans son workflow ; il monte de version par une PR (tâche
  d'outillage du fork), jugée par l'ancienne version et par la nouvelle.
- `verdict.json` porte `juge.version` (« commun-vN ») : le registre sait par quel juge chaque verdict
  a été rendu, et peut exiger une version minimale (`bee.yaml`).

## Migration

1. Intégrer miniz-0031 (juge de minizBee, version 2).
2. Extraire la partie commune dans le registre (`outils/juge/`, workflow `juge.yml`, étiquette
   `juge-v1`), avec ses méta-tests sur un projet jouet ; minizBee passe à un greffon, ses méta-tests
   doivent donner exactement les mêmes résultats.
3. libyaml (tâche libyaml-0005) écrit son greffon et son harnais au lieu d'une copie.
4. Les nouveaux projets (giflib, bzip2) arrivent directement avec un greffon.
