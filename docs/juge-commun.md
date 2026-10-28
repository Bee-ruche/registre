# Juge commun : un juge isolé pour tous les projets (spécification)

Statut : première version construite le 28 octobre 2026 (`outils/juge/`, branche `juge-commun`),
méta-tests verts sur le projet jouet ; l'étiquette `juge-v1` sera posée après la revue adverse et
l'intégration du juge isolé de minizBee (tâche miniz-0031). Contexte et raisons : [architecture.md](architecture.md), « La suite », chantier 2.

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

Une classe `Projet` sans état propre (elle reçoit les options `--option CLE=VALEUR` à sa création),
lue par le juge commun **depuis la base de la PR** (jamais depuis la PR). Modèle complet et commenté :
`outils/juge/jouet/bee/juge/projet.py` (projet jouet des méta-tests).

| Élément | Rôle |
| --- | --- |
| `NOM`, `PAQUETS` | nom du projet ; paquets ajoutés à l'image commune (une ligne `RUN`, noms vérifiés) |
| `SOURCES`, `SOURCES_REQUISES` | motifs glob des fichiers du projet copiés dans le conteneur (`miniz*.c`, `src/*.c`…) ; tout lien symbolique est refusé |
| `DIFF` | motifs passés à `git diff` pour l'analyse des lignes ajoutées |
| `OUTILLAGE`, `EN_TETES_BASE`, `CONSTRUIRE` | dossiers de la base montés sur `/outillage` ; en-têtes de la base copiés dans `/outillage/base/` (le harnais se compile avec eux) ; script de construction, qui doit produire `execution` et les relevés `symboles.txt`, `sections.txt`, `desassemblage.txt` |
| `PREFIXES`, `PERMIS` | espace de noms du projet et fonctions externes permises en plus de la liste commune, pour l'analyse des objets |
| `COTES` | côtés d'entrées (`f`, `z`…) : un conteneur par côté, jamais deux côtés montés ensemble |
| `SCENARIOS`, `INSTRUCTIONS`, `METRIQUES`, `METHODE` | scénarios mesurés au chronomètre et leur côté ; ceux dont on compte les instructions ; métriques (nom, sens, unité) ; textes de méthode ajoutés au rapport |
| `corpus(outillage)` | corpus de la base, `[(nom, octets)]` (aide : `entrees.charger_corpus`) |
| `verification(rng, corpus)` | entrées de vérification (`entrees.Entree`) : corpus, données tirées au hasard, dérivées (flux produits par l'hôte), invalides |
| `verifier(a, b, entrees)` | règle de justesse sur les sorties du mode `verifier` ; lève `Refus` au premier écart, `Erreur` si la base elle-même est fausse ; renvoie le nombre de sorties comparées |
| `fixes(sorties, corpus)` | métriques qui ne dépendent pas du temps (ratio de compression…), lues sur les sorties de vérification |
| `repetition(rng, corpus)`, `instructions(rng, corpus, prefixe)` | entrées des mesures, perturbées à chaque appel |
| `scenario(s, a, b, entrees, mesure)` | vérifie les sorties d'un scénario mesuré et en tire les métriques (à partir de la mesure de chrono) ; renvoie `(valeurs, sorties comparées)` |

Le harnais (`execution`) est appelé `execution <mode> /entrees /sorties`, avec le mode `verifier` ou
un nom de scénario ; `/entrees/liste` donne une ligne `<côté> <nom> <entier>` par entrée, dont les
octets sont dans `/entrees/<côté>/<nom>`.

Règle de sûreté : le greffon ne voit les sorties qu'à travers `lecture.Sorties`, et n'exécute rien de
ce que le conteneur a produit. Une PR qui modifie `bee/juge/` est une tâche d'outillage : le registre
le détecte et exige un gardien (R3).

## Versions

- Le juge commun est versionné par étiquette (`juge-v1`, `juge-v2`…) dans le registre. Un changement
  passe par une PR d'outillage sur le registre, avec les méta-tests communs (workflow
  `juge-commun.yml`) et ceux de chaque projet qui l'utilise, et la relecture de deux gardiens.
- Le workflow réutilisable `.github/workflows/juge.yml` lit le juge commun à sa propre étiquette
  (`JUGE_COMMUN_REF`, vérifié par un test), jamais à la branche principale.
- Chaque fork épingle une version dans son workflow ; il monte de version par une PR (tâche
  d'outillage du fork), jugée par l'ancienne version et par la nouvelle.
- `verdict.json` porte `juge.version` (entier : 2 pour le juge de minizBee de miniz-0031, 3 pour le
  juge commun v1), `juge.commun` (« juge-v1 »), `juge.projet` et `juge.greffon` (empreinte SHA-256 du
  greffon) : le registre sait par quel juge chaque verdict a été rendu, et peut exiger une version
  minimale (`bee.yaml`).

## Migration

1. Intégrer miniz-0031 (juge de minizBee, version 2).
2. Extraire la partie commune dans le registre (`outils/juge/`, workflow `juge.yml`, étiquette
   `juge-v1`), avec ses méta-tests sur un projet jouet ; minizBee passe à un greffon, ses méta-tests
   doivent donner exactement les mêmes résultats.
3. libyaml (tâche libyaml-0005) écrit son greffon et son harnais au lieu d'une copie.
4. Les nouveaux projets (giflib, bzip2) arrivent directement avec un greffon.
