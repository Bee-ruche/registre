# Juge commun : un juge isolé pour tous les projets (spécification)

Statut : version 3 (next tag `juge-v3`, created by the council once this is merged) ; version 2 en service depuis le 2 novembre 2026, étiquette `juge-v2` ;
version 1 depuis le 28 octobre 2026, étiquette `juge-v1` (fusion décidée par le conseil). Les forks passent à juge-v3 par miniz-0048 et libyaml-0020. Les forks y passent par les tâches miniz-0032 (après l'intégration de miniz-0031) et
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
| Les méta-tests du juge commun (sur un projet jouet) et le workflow réutilisable `juge.yml` (`workflow_call`) | L'appel du workflow, épinglé au commit d'une étiquette : `uses: Bee-ruche/registre/.github/workflows/juge.yml@<commit> # juge-vN` |

## Le greffon d'un projet (`bee/juge/projet.py`)

Une classe `Projet` sans état propre (elle reçoit les options `--option CLE=VALEUR` à sa création),
lue par le juge commun **depuis la base de la PR** (jamais depuis la PR). Modèle complet et commenté :
`outils/juge/jouet/bee/juge/projet.py` (projet jouet des méta-tests).

| Élément | Rôle |
| --- | --- |
| `NOM`, `PAQUETS` | nom du projet ; paquets ajoutés à l'image commune (une ligne `RUN`, noms vérifiés) |
| `SOURCES`, `SOURCES_REQUISES` | motifs glob des fichiers du projet copiés dans le conteneur et compilés (`miniz.c`, `src/*.c`…) ; tout lien symbolique est refusé ; the text analysis reads these same files, whole |
| `OUTILLAGE`, `EN_TETES_BASE`, `CONSTRUIRE` | dossiers de la base montés sur `/outillage` ; en-têtes de la base copiés dans `/outillage/base/` (le harnais se compile avec eux) ; script de construction, qui doit produire `execution` et laisser **chaque objet du projet dans `obj/`**, un `obj/<nom>.o` par unité de traduction des `SOURCES` (`.c`, `.S`, `.cc`…), deux unités homonymes étant refusées (le juge s'arrête sinon) |
| `PREFIXES`, `PERMIS` | espace de noms du projet (au moins un préfixe, chacun un mot terminé par `_` : `mz_`, `yaml_`) et fonctions externes permises en plus de la liste commune (64 au plus). Les fonctions qui servent à tromper la mesure (horloge, processus, environnement, signaux, appels système : `analyse.JAMAIS_PERMIS`) ne sont jamais permises et sont signalées par leur nom exact, avant toute exemption |
| `COTES` | côtés d'entrées (`f`, `z`…) : jamais deux côtés montés ensemble ; en vérification, un conteneur par côté ; dans les mesures, un par scénario (ci-dessous) |
| `SCENARIOS`, `INSTRUCTIONS`, `METRIQUES`, `METHODE` | scénarios mesurés au chronomètre et leur côté ; ceux dont on compte les instructions ; métriques (nom, sens, unité) ; textes de méthode ajoutés au rapport |
| `corpus(outillage)` | corpus de la base, `[(nom, octets)]` (aide : `entrees.charger_corpus`) |
| `verification(rng, corpus)` | entrées de vérification (`entrees.Entree`) : corpus, données tirées au hasard, dérivées (flux produits par l'hôte), invalides |
| `verifier(a, b, entrees)` | règle de justesse sur les sorties du mode `verifier` ; lève `Refus` au premier écart, `Erreur` si la base elle-même est fausse ; renvoie le nombre de sorties comparées |
| `fixes(sorties, corpus)` | métriques qui ne dépendent pas du temps (ratio de compression…), lues sur les sorties de vérification |
| `repetition(rng, corpus)`, `instructions(rng, corpus, prefixe)` | entrées des mesures, perturbées à chaque appel (le juge commun y mêle des entrées de vérification, puis renomme le tout) |
| `scenario(s, a, b, entrees, mesure)` | vérifie **chaque** sortie d'un scénario mesuré par la règle de `verifier`, entrées de vérification mêlées comprises (invalides aussi), et en tire les métriques (à partir de la mesure de chrono) ; renvoie `(valeurs, sorties comparées)` |

Le harnais (`execution`) est appelé sans argument ; son descripteur 0 porte 256 octets : la ligne `<mode> /entrees /sorties`
(mode `verifier` ou nom de scénario), complétée d'espaces et finie par une fin de ligne ; `/entrees/liste` donne une ligne
`<côté> <nom> <entier>` par entrée, dont les octets sont dans `/entrees/<côté>/<nom>`. Dans un scénario, il traite toute
entrée de son côté comme en vérification.

**What the harness guarantees the judged code (ruche-0037).** The same arguments, environment, descriptors, working directory
and mounts in every mode (verification, timer, instruction count), one container per scenario; the mode reaches the harness on
its descriptor 0, in a record of fixed length. The harness reads that record to its end, copies it, then erases it, its
arguments and its environment before any call to the judged code, and does the same work and writes the same outputs in every
mode. `/variante` holds the harness alone; inputs, harness, `chrono` and the output folder carry fixed times. Inputs are
shuffled and renamed (`e0000`…) in every mode; the plugin keeps its own names, translated by `Sorties`. These conditions do not
hide everything about the run: the wall clock stays readable, and the instruction count runs under Valgrind, which the judged
code can detect. Mixing is the backstop. Every verification input is verified; the verification inputs of each measured side are
also mixed into the measured ones and spread over the repetitions (⌈n/r⌉ per repetition, warm-up included, taken in turn in an
order drawn from the judge's seed; as many in the instruction count, within its prefix), the same for A and B. A wrong output
fails the judgement whatever the mode, and B's output of a mixed-in input must be, byte for byte, its own output in
verification. A measured side without verification inputs is an error. A scenario may return a fixed metric computed on its
timed outputs (the toy's ratio); it replaces the value `fixes()` reads on verification. `juge.json`:
`juge.verification.entrees_melees` (total), `melees_par_repetition` (per side), `instructions_sans_melange` (instruction-count
scenarios that got none). Since ruche-0117, the byte-for-byte check wants a comparable output in each scenario of the side, and
a fixed metric that no scenario returns, read on verification alone, is named in `fixes_sans_mesure`, marked
`verification_seulement` in `metriques` and never `au_dela_du_bruit`: its value is the same at every repetition.

**Each execution on its own tmpfs (ruche-0117).** Nothing the judge's setup shows a container depends on the run's progress
(its position, the variant pass, the repetition, the mode). Just before each container, the judge mounts a fresh tmpfs
(`conteneur.TMPFS`: 4 GiB, 262,144 files; as root or through `sudo -n`, as on juge.yml's runner, an error otherwise) and creates
there anew, in a fixed order with fixed access and modification times, all the container sees of it: `chrono`, the harness,
the inputs, `/etc/hostname`, `/etc/hosts`, `/etc/resolv.conf` (which Docker would write on the host's disk) and the outputs
folder; once the container ends, the outputs are copied out and the tmpfs unmounted. Docker (up to 29.0) mounts folders of equal
depth in an order drawn for each container: each of the judge's is given at its own depth, through the image's link to its root
(`/.racine/variante` is `/variante`), so all are mounted in one order. Identical scenarios thus find the same
inodes, devices, links, sizes, directory order, free space and mount lines, change and birth times as old (`f_fsid` is drawn by
the kernel at each mount), and no container's outputs share space with another's while it runs (test_memes_montures). What
still follows the progress, as the clock does: the container's root, Docker's overlay on the host's disk (its inode, free
space and, with the containerd image store, its layers' numbers in `/proc/self/mountinfo`), and kernel-wide counters (unique
mount ids, the inode numbers of each container's cgroup and message queues, the host's process count in `/proc`'s links).

**Per-scenario isolation (ruche-0036).** In the measurements and the instruction count, each scenario runs in its own
container (above), with a fresh `/tmp` and a fresh output folder mounted on `/sorties`: of all the outputs, it sees only its
own. Verification still runs one container per side, not per scenario.
- **Frozen outputs**: as soon as each container ends (verification included), its outputs are copied out of its tmpfs
  (`lecture.copier`: no link followed, size bounded, a link or special file left as a link) and the judge records the listing of
  that folder and the SHA-256 of each file (`lecture.figer`). The plugin (through `Sorties`) and the byte-for-byte comparison of
  mixed-in inputs read only what was frozen: a file changed, added or removed afterwards is a refusal, when it is read and at
  the check that ends each step; so is anything the judge cannot read while freezing (root or not).
- **Drawn order**: the order of the scenarios is drawn anew at each repetition (warm-up included) and for the instruction
  count, the same for A and B.
- **`juge.json`**: `juge.scenarios.graine_ordre` is the seed of that draw (from `secrets`, apart from the inputs' seed and
  generator; `--graine-ordre` reruns it); `juge.scenarios.deroulement` gives, per step (`chauffe`, `mesure`,
  `instructions`), the order of the variants and of the scenarios, and **each scenario's CPU time** for A and B (user +
  system, read by `chrono` with `wait4`; under Valgrind for `instructions`).
- Meta-test, on a copy of the toy with two scenarios per side: a candidate each of whose scenarios tries to read and to
  modify the others' outputs, before and after its own work, gets the honest toy's verdict and comparisons.

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
- what the object analysis covers: suspicious instructions (system calls, counter reads, processor identification,
  Valgrind client requests…) are counted in the disassembly and, independently, in the executable bytes of every
  object and of the linked program, read from the files at every offset, each hit compared with A's by its object
  and surrounding bytes; undecodable bytes and writable and executable memory count too. A failure of `nm` or of
  the disassembler stops the judge (refusal or error), and unreadable bytes make it incomplete: never complete;
- the judged files (`SOURCES`) are scanned whole, each file of B against A's, line splices joined, without
  git: only a net, the objects show the code produced. Une PR qui modifie `bee/juge/` est une tâche
  d'outillage : le registre le détecte et exige un gardien (R3).

## Versions

- Le juge commun est versionné par étiquette (`juge-v1`, `juge-v2`…) dans le registre. Un changement
  passe par une PR d'outillage sur le registre, avec les méta-tests communs (workflow
  `juge-commun.yml`) et ceux de chaque projet qui l'utilise, et la relecture de deux gardiens.
- Le workflow réutilisable `.github/workflows/juge.yml` lit le juge commun au commit même du workflow
  appelé (`job.workflow_sha`), jamais à une étiquette ni à une branche : le workflow doit être celui de
  `Bee-ruche/registre` (`job.workflow_repository`) et ce commit être sur sa branche principale (API compare :
  `identical` ou `behind`), sinon le juge s'arrête (vérifié par un test) ; `juge.json` le nomme (`juge.source`).
- Chaque fork épingle une version dans son workflow ; il monte de version par une PR (tâche
  d'outillage du fork), jugée par l'ancienne version et par la nouvelle.
- `verdict.json` porte `juge.version` (entier : 2 pour le juge de minizBee de miniz-0031, 3 pour le
  juge commun v1 et v2), `juge.commun` (« juge-v1 », « juge-v2 »), `juge.projet` et `juge.greffon` (empreinte SHA-256 du
  greffon) : le registre sait par quel juge chaque verdict a été rendu, et exige une version
  minimale (`bee.yaml`, ci-dessous).
- **Minimum version** (`juge_commun_min` in `bee.yaml`, ruche-0086): with R3's gate at `si_juge_incomplet`, a verdict whose
  `juge.commun` is not exactly `juge-vN` (N in ASCII digits, no leading zero) with N at least this minimum is not entirely
  judged: a guardian or the council must review it, as for any incomplete judge. Missing or malformed (not an integer from 1
  to 9999), no verdict is complete: the gate closes, never opens. It is read when R3 is checked, so it reaches contributions
  still in review, judged by an older judge, never those already integrated. **The council raises it**, after it has tagged
  the new version and every fork is pinned to it (each fork moves by a tooling PR); raised earlier, the forks' verdicts go to a
  guardian until they move. It checks the version of the judge's code (the label, `VERSION_COMMUNE` in `outils/juge/juge.py`),
  not the commit a fork pins: the council bumps `VERSION_COMMUNE` whenever a change to the judge or to its workflow's
  protections ships, then raises the minimum. `bee valider` reports a missing or malformed minimum.

## Le workflow `juge.yml`, version 2 (ruche-0024)

- **Historique déclaré** : l'entrée `historique` (16 commits complets au plus, séparés par des blancs) nomme les
  commits dont le greffon lit les objets git. Chacun doit être un ancêtre de la base (API compare du dépôt
  appelant : `identical` ou `behind`), vérifié avant toute récupération ; le workflow les récupère ensuite dans la
  copie de la base, chacun avec son arbre et sans son historique, dans une étape à part, seule à recevoir le jeton,
  avant de charger le greffon et avant tout fichier de la PR, en 10 minutes au plus en tout (sinon erreur, code 2). Le jugement refuse
  ensuite tout transport git (`GIT_ALLOW_PROTOCOL`) : un objet non déclaré est une erreur (code 2).
- **Journal sûr** : les 40 dernières lignes du journal, que la PR peut remplir, s'impriment entre
  `::stop-commands::<jeton>` et `::<jeton>::`, jeton tiré après le jugement, et `##[` y devient `# #[`
  (ruche-0025) : aucune ne devient une commande de workflow.
- **The caller's inputs** (ruche-0038), checked first: `base_sha` and `tete_sha` are the event's pull request's
  (`github.event.pull_request.base.sha`, `.head.sha`, 40 hexadecimal digits), `repetitions` 10 to 50, `sans_instructions`
  false (a verdict needs the instruction count); otherwise the job fails before anything is checked out or judged.
- **Job outputs tied to the report** (ruche-0038): `code`, `empreinte` (SHA-256 of `juge.json`), `suspectes` (all of them),
  `sorties_comparees`, `greffon`, `graine`, `base`, `tete` (`outils/juge/rapport.py`; empty without a report). The verdict
  job reads `juge.json` from the artifact « juge » and checks it against them, `python3 rapport.py juge.json --verifier
  sorties.json --base <the PR's base> --tete <its head>` (`toJSON(needs.<judging job>.outputs)`), refused (code 1) at any
  difference, a code other than 0 or other commits than the PR's (ruche-0117); any non-zero exit blocks the verdict. The judging
  step publishes the code only with the figures, once `rapport.py --code` has checked the report: code 2 if the report fails
  (none for a code 0, malformed). `juge.json` names `juge.base`,
  `juge.tete` and `juge.image_id`, the image's id, by which every container runs it.
- **Disk and reads bounded** (ruche-0038): the work folder is a tmpfs of 4 GiB and 262,144 files (`--travail`); containers
  run with `--ulimit fsize` at `lecture.TAILLE_MAX_SORTIE` (256 MiB) and no log on the host's disk, which keeps the first MiB
  of their standard output and the last of their error; no output is read beyond that size. Writing without end or filling the
  folder fails the judgement. `juge.json` lists 100 suspicious constructs at most (the rest: `constructions_suspectes_omises`),
  the most serious first (`juge.GRAVITE`), each kind counted (`constructions_suspectes_par_type`), each detail cut to 300
  characters as `analyse.analyser` builds the list (ruche-0117).

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
