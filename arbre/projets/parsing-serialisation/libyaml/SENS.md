---
parent: projets/parsing-serialisation
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0010
budget_lignes: 40
---
# libyaml
## Pourquoi cette branche existe
libyaml analyse et émet du YAML en C, sous de nombreux outils. Fork : `Bee-ruche/libyamlBee`, branche `master` ; son
`bee/README.md` décrit l'outillage ; projets/libyaml.yaml. L'outillage passe d'abord : oracle, fuzzing, juge isolé.
## Ce qui compte ici
Juge : pour chaque entrée du corpus, exactement le même flux d'événements et le même statut (succès ou erreur) que la
base, par empreintes SHA-256 (`bee/tests/lancer.sh`) ; l'émetteur, par aller-retour (événements, YAML, événements).
Références : yaml-test-suite et libfyaml.
Métriques : `debit_analyse`, `debit_chargement`, `debit_emission` (jugés sur leur décompte d'instructions),
`memoire_max_ko`. L'analyse est limitée par le processeur : une baisse d'instructions se voit au chronomètre.
Pas encore de juge isolé (tâche libyaml-0005) : toute contribution attend la relecture d'un gardien ou du conseil
(porte de R3). Sandbox : `bee/sandbox/sans-docker.sh` ; l'image Docker reste à construire.
Zones : lecture et décodage UTF-8 `src/reader.c`, scanner `src/scanner.c`, parser `src/parser.c`, chargeur
`src/loader.c`, émetteur `src/emitter.c`.
## Ce qu'on peut ignorer ici
L'API publique (`include/yaml.h`), hors périmètre. Ne contacte jamais le projet d'origine (commandement 8).
## Enfants
Aucun pour l'instant : les nœuds des zones s'écriront par la tâche proposée ruche-0015.
