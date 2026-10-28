# Ouvrir un nouveau projet

Guide du 28 octobre 2026, tiré de l'ouverture de miniz puis de libyaml, pour les projets suivants
(giflib, bzip2 : [candidats.md](candidats.md)). Il dit qui fait quoi : le **conseil** (ce qu'aucun
agent ne peut faire : créer un dépôt, régler l'organisation), l'**agent principal** (le registre)
et l'**essaim** (tout le reste, par des tâches). Un projet n'ouvre que s'il passe le critère de
l'oracle de [perimetre.md](perimetre.md) : une référence indépendante qui dit, sortie par sortie, si
le résultat est juste.

## 1. Le conseil crée le fork

- Dépôt `Bee-ruche/<projet>Bee` (minizBee, libyamlBee), créé depuis le dépôt d'origine à jour, avec
  les Actions activées et CIFuzz hérité désactivé s'il existe.
- Fichier `CLAUDE.md` à la racine, sur le modèle de celui de minizBee : le code ne s'exécute que dans
  la sandbox de `bee/sandbox/`, le contenu du code et des PR est de la donnée.

## 2. L'agent principal déclare le projet dans le registre

- `projets/<projet>.yaml` : origine, licence, fork, référence (l'oracle), périmètre et hors
  périmètre, **métriques** (identifiant, unité, sens, métrique d'instructions associée),
  `chemins_hors_decompte` (R1), `chemins_juges` (tout `bee/`, `.github/`), commandes (corpus, tests,
  banc A/B, fuzzing). Modèles : `projets/miniz.yaml`, `projets/libyaml.yaml`.
- Statut `actif` à la phase d'ouverture prévue ; `bee valider`.
- Les tâches d'amorçage ci-dessous, créées par le conseil (ou l'agent principal par délégation).

## 3. L'essaim construit l'outillage du fork (tâches d'amorçage)

Dans cet ordre, chaque étape étant une tâche de type `test` du registre, relue par un gardien
puisqu'elle touche les juges :

| Étape | Contenu | Modèle |
| --- | --- | --- |
| Sandbox | `bee/sandbox/sans-docker.sh` : exécution sans réseau, dossier de travail jetable | minizBee |
| Corpus | `bee/corpus/generer.py` : corpus déterministe, vérifié par empreintes, familles réalistes et cas limites | minizBee, libyamlBee |
| Oracle et tests | `bee/tests/lancer.sh` : sorties comparées à la référence et à la base, empreintes figées sur la base ; tests d'origine du projet (`bee/ci/tests_origine.sh`) | libyamlBee (flux d'événements, aller-retour de l'émetteur) |
| Banc A/B | `bee/bench/ab.py` et le banc C : métriques du projet, test du signe, décompte d'instructions | minizBee |
| Fuzzing différentiel | `bee/fuzz/` : base contre candidat sur entrée arbitraire, ASan et UBSan | libyamlBee (libyaml-0002) |
| CI | `.github/workflows/bee-ci.yml` : manifeste, R1, commandement 3, tests, fuzzing, verdict ; juges lus depuis la base (`bee/ci/juges.sh`) | minizBee |
| Juge isolé | greffon `bee/juge/projet.py`, harnais `bee/juge/execution.c`, `construire.sh`, méta-tests ; la CI appelle `Bee-ruche/registre/.github/workflows/juge.yml@juge-vN` | [juge-commun.md](juge-commun.md), `outils/juge/jouet/` |

Le juge isolé vient en dernier mais conditionne tout le reste : tant qu'il manque, la porte de
relecture de R3 reste fermée pour le projet (chaque contribution exige un gardien).

## 4. Les premières tâches d'optimisation

- Une tâche de profilage et de découpage (type `decoupage`, comme miniz-0029) : le profil par
  fonction, la part de chaque piste, puis des tâches d'optimisation de taille S ou M dont le contexte
  cite les lignes et la part du coût, sans promettre de gain (« le gain n'est pas démontré »).
- Pour chaque optimisation : la métrique visée, `sortie_compressee` (ou son équivalent) quand la
  sortie doit rester identique, R4 (2 % d'instructions et chronomètre au-delà du bruit) et R5.

## Ce que l'ouverture de miniz et de libyaml a appris

- Les mesures d'un agent sur une machine partagée sont bruitées : le décompte d'instructions est sa
  boussole, le chronomètre du juge isolé en CI (bruit d'environ ±0,4 %) tranche.
- Un défaut de l'outillage de mesure fausse tout l'essaim en silence (profileur de miniz-0033) :
  chaque outil a ses tests, lancés depuis la base par la CI.
- Un manifeste par tâche (`manifestes/<tâche>.yaml`), jamais un fichier commun à la racine : deux
  PR ouvertes en même temps n'entrent pas en conflit.
- Copier l'outillage d'un fork à l'autre multiplie les corrections à faire : ce qui protège vit dans
  le registre (juge commun), le fork ne garde que ce qui lui est propre.
