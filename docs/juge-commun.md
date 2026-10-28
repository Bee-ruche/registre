# Juge commun : un juge isolé pour tous les projets (spécification)

Statut : version 1 en service depuis le 28 octobre 2026, étiquette `juge-v1` (fusion décidée par le
conseil). Les forks y passent par les tâches miniz-0032 (après l'intégration de miniz-0031) et
libyaml-0005 (après libyaml-0002).

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
| `SOURCES`, `SOURCES_REQUISES` | motifs glob des fichiers du projet copiés dans le conteneur et compilés (`miniz.c`, `src/*.c`…) ; tout lien symbolique est refusé ; le diff analysé est celui de ces mêmes motifs |
| `OUTILLAGE`, `EN_TETES_BASE`, `CONSTRUIRE` | dossiers de la base montés sur `/outillage` ; en-têtes de la base copiés dans `/outillage/base/` (le harnais se compile avec eux) ; script de construction, qui doit produire `execution` et laisser **chaque objet du projet dans `obj/`**, un `obj/<nom>.o` par unité de traduction des `SOURCES` (`.c`, `.S`, `.cc`…), deux unités homonymes étant refusées (le juge s'arrête sinon) |
| `PREFIXES`, `PERMIS` | espace de noms du projet (au moins un préfixe, chacun un mot terminé par `_` : `mz_`, `yaml_`) et fonctions externes permises en plus de la liste commune (64 au plus). Les fonctions qui servent à tromper la mesure (horloge, processus, environnement, signaux, appels système : `analyse.JAMAIS_PERMIS`) ne sont jamais permises et sont signalées par leur nom exact, avant toute exemption |
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

Règles de sûreté, vérifiées par le juge commun (revue adverse du 28/10) :
- les relevés d'analyse (`nm`, `objdump`) sont produits par le juge commun lui-même, dans un conteneur, sur
  tous les objets de `obj/` : un script de construction ne peut ni les omettre ni les vider ;
- le greffon ne voit les sorties qu'à travers `lecture.Sorties`, qui retient ce qu'il a lu : à chaque
  étape, chaque entrée doit avoir eu au moins une sortie de B lue, sinon le juge s'arrête (code 2) ;
- le greffon n'exécute rien de ce que le conteneur a produit et ne met jamais d'octets venus du
  conteneur dans un message sans `lecture.propre` ; toute exception imprévue est une erreur (code 2) ;
- un harnais ne dimensionne jamais un tampon d'après le seul code jugé (borne connue du format, au minimum) ;
- l'analyse des instructions ne couvre que x86-64 : sur une autre architecture, le juge le signale comme
  construction suspecte (un gardien relit) ;
- le balayage du texte du diff (assembleur, en-têtes système, concaténation de jetons, lignes
  recollées après `\`…) n'est qu'un filet : c'est l'analyse des objets qui voit le code réellement
  produit. Une PR qui modifie `bee/juge/` est une tâche d'outillage : le registre
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

## Trois greffons côte à côte

Le contrat a été vérifié sur deux projets réels (miniz, avec un greffon d'essai rendant exactement les
résultats du juge de miniz-0031) et sur le jouet ; pour libyaml (libyaml-0005), il se remplit ainsi :

| Élément | jouet | miniz | libyaml (prévu) |
| --- | --- | --- | --- |
| `SOURCES` | `rle.c`, `rle.h` | `miniz*.c`, `miniz*.h` | `src/*.c`, `src/*.h`, `include/yaml.h` |
| `EN_TETES_BASE` | `rle.h` | `miniz*.h` | `include/yaml.h` (harnais compilé avec `-I/outillage/base/include`) |
| `COTES` | `f` bruts, `z` flux | `f` bruts, `z` flux zlib | `f` documents (aucune donnée dérivée) |
| `SCENARIOS` | compression, décompression | n1, n6, n9, décompression, mémoire | analyse, chargement, émission, mémoire |
| justesse | sortie identique à la base, codec de référence en Python | identique à la base, zlib de l'hôte | flux d'événements sérialisé et sortie de l'émetteur identiques à la base ; entrées invalides : même erreur, mêmes positions |
| `PREFIXES` | `rle_` | `mz_`, `tdefl_`, `tinfl_`, `miniz_`, `MZ_` | `yaml_` |

## Migration

1. Intégrer miniz-0031 (juge de minizBee, version 2).
2. Extraire la partie commune dans le registre (`outils/juge/`, workflow `juge.yml`, étiquette
   `juge-v1`), avec ses méta-tests sur un projet jouet. *Fait le 28/10, étiquette `juge-v1` posée.*
3. minizBee passe à un greffon (miniz-0032) ; à graine égale, il doit rendre exactement les résultats
   du juge de miniz-0031.
4. libyaml (tâche libyaml-0005) écrit son greffon et son harnais au lieu d'une copie.
5. Les nouveaux projets (giflib, bzip2) arrivent directement avec un greffon.
