# Name map: French → English (registry Bee-ruche/registre and what the forks see)

The name map for the founder's decision of 8 November 2026 that every name moves to English (it replaces the plans of ruche-0069 and ruche-0070; the plan is [english-migration.md](english-migration.md)). A reviewed draft, generated on 2026-11-08 from the map's seed with the parser tree, the schema properties and the data's keys and values, against the registry at commit 403fdc5, minizBee at 67bf3b4 and libyamlBee at 01cac4b. Layer L1a (ruche-0141) turns it into the scoped, machine-readable `outils/migration/names.yaml` (plan, section 12, change 7), completes it with the tool's JSON output keys, and proves it complete against the code.

How to read the tables. **Used in**: number of tracked files of the registry that contain the French name in the form searched (command after `bee`, option with its dashes, key as `"key"` in code or as a YAML key in data, value as a literal), then the files with most occurrences (`taches/…` stands for many task files). **Forks**: files of minizBee and libyamlBee outside upstream code (`.github/`, `bee/`, `manifestes/`, guides) that contain it. A note marks what matters for the move: who calls the name from outside the commit that renames it, and what fails if it is missed. English equal to French means the name stays. The map has to be one-to-one inside each family (a French name never maps to two English names, two French names of one family never to the same English name), so that the migration script can translate back for history and prove nothing was lost. Beyond that, every French token maps to one English token whatever its role (key, value, folder, command), so that a literal in the code can be renamed without knowing its role; the two exceptions are renamed by hand: `issue` (key → `outcome`, channel value « issue » kept) and `signalement` (command → `decide-report`, nature → `report`).

Conventions used for new names: lower_snake_case keys and values, kebab-case commands, options and file names (as today); an instant is `*_at`, a date `*_on` (precedent: `declared_on` in gouvernance/comptes-agents.yaml); the vocabulary of COMMANDMENTS.md, docs/devolution.md and R15 (council, guardian, security guardian, guarantor, agent principal, judge, common judge, gate, task, contribution, review, debate, proposal, member, engagement, reservation, branch, seed, tree of meaning, bootstrap). French words kept, in prose only: La Ruche, la Nuit des abeilles, l'essaim, le miel. Proper names stay: bee, the project ids (miniz, libyaml, ruche: see the open question in migration-plan.md), logins, task ids.

## 1. Command line

### 1.1 Subcommands of `bee` (outils/bee.py)

68 subcommands as the argument parser builds them (53 top level, 7 `debattre` actions, 8 `invitation` actions), read from `construire_analyseur()` by `dump_cli.py`, not typed by hand.

| # | French | English | Used in (files) | Forks | Note |
|---|---|---|---|---|---|
| 1 | `valider` | `validate` | 100 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 | run by every writing workflow (validation, integration-auto, verdicts, expirations) |
| 2 | `lister` | `list` | 17 (outils/test_bee.py, AGENTS.md, taches/…) | 0 |  |
| 3 | `cap` | `balance` | 21 (outils/test_bee.py, outils/bee.py, docs/cap.md) | 0 | R11: compares target shares per area with the activity; not « heading » (a Markdown heading in the tree code), not « cap » (plafond) |
| 4 | `essaim` | `swarm` | 57 (outils/test_bee.py, outils/bee.py, docs/decisions.md) | 1 (minizBee:bee/tests/api.c) | « l'essaim » stays in prose only |
| 5 | `voir` | `show` | 24 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| 6 | `contexte` | `context` | 39 (outils/test_bee.py, outils/bee.py, docs/arbre.md) | 0 | named in every tree node and in the skill |
| 7 | `inscrire` | `register` | 16 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| 8 | `renommer` | `rename` | 6 (outils/test_bee.py, outils/bee.py, REGLES.md) | 0 |  |
| 9 | `lier` | `link` | 5 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 |  |
| 10 | `signaler` | `report` | 6 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | signalement = report |
| 11 | `signalement` | `decide-report` | 5 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | the council's decision on a report; the literal « signalement » is also a nature (-> report): renamed by context, by hand |
| 12 | `prendre` | `take` | 24 (outils/test_bee.py, outils/bee.py, docs/taches.md) | 0 | reserves, or registers in parallel with --parallel |
| 13 | `proposer-tache` | `propose-task` | 22 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| 14 | `liberer` | `release` | 11 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| 15 | `noter` | `note` | 15 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| 16 | `liberer-expirees` | `release-expired` | 6 (outils/test_bee.py, .github/workflows/expirations.yml, docs/contributions.md) | 0 | expirations.yml |
| 17 | `manifeste` | `manifest` | 15 (outils/test_bee.py, outils/bee.py, AGENTS.en.md) | 9 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | writes the fork's manifest |
| 18 | `valider-contribution` | `validate-manifest` | 6 (outils/test_bee.py, outils/bee.py, AGENTS.en.md) | 0 | it validates the manifest, not the contribution record |
| 19 | `soumettre` | `submit` | 21 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| 20 | `relire` | `review` | 23 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| 21 | `confirmer-defaut` | `confirm-defect` | 5 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| 22 | `enregistrer-mesure` | `record-measurement` | 12 (outils/test_bee.py, outils/bee.py, docs/mesures.md) | 1 (libyamlBee:bee/README.md) |  |
| 23 | `voter` | `vote` | 14 (outils/test_bee.py, outils/bee.py, taches/…) | 0 |  |
| 24 | `proposer` | `propose` | 19 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | a rule change; same pair as French (proposer / proposer-tache) and same token as the role « propose » |
| 25 | `depouiller` | `tally` | 5 (outils/bee.py, REGLES.md, docs/gouvernance.md) | 0 |  |
| 26 | `debattre` | `debate` | 18 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 |  |
| 27 | `debattre ouvrir` | `debate open` | 11 (outils/test_bee.py, outils/bee.py, arbre/roles/debattre/SENS.md) | 3 (libyamlBee:bee/commun/corpus.c, libyamlBee:bee/tests/oracle.c) |  |
| 28 | `debattre argumenter` | `debate argue` | 10 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 |  |
| 29 | `debattre synthetiser` | `debate synthesize` | 4 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 |  |
| 30 | `debattre doublon` | `debate duplicate` | 8 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 |  |
| 31 | `debattre caviarder` | `debate redact` | 5 (outils/test_bee.py, outils/bee.py, arbre/roles/debattre/SENS.md) | 0 |  |
| 32 | `debattre clore` | `debate close` | 4 (outils/test_bee.py, outils/bee.py, arbre/roles/debattre/SENS.md) | 0 |  |
| 33 | `debattre importer-questions` | `debate import-questions` | 4 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 | reads docs/questions-ouvertes.md (bilingual reader) |
| 34 | `debats` | `debates` | 17 (outils/test_bee.py, outils/bee.py, docs/questions-ouvertes.md) | 0 |  |
| 35 | `inviter` | `invite` | 13 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 | R13 |
| 36 | `invitation` | `invitation` | 15 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 | keep |
| 37 | `invitation accord-gardien` | `invitation guardian-approval` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 | same word as the record key and nature guardian_approval |
| 38 | `invitation accord-conseil` | `invitation council-approval` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 39 | `invitation consigner-envoi` | `invitation record-sent` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 40 | `invitation consigner-relance` | `invitation record-reminder` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 41 | `invitation consigner-reponse` | `invitation record-answer` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 42 | `invitation ecarter` | `invitation dismiss` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 43 | `invitation retirer` | `invitation withdraw` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 44 | `invitation renouveler` | `invitation renew` | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| 45 | `retirer-donnees` | `remove-data` | 7 (outils/bee.py, outils/test_bee.py, docs/croissance.md) | 0 | commandment 10; PARCOURS must cover every renamed folder (privacy) |
| 46 | `incident` | `incident` | 4 (outils/test_bee.py, outils/bee.py, arbre/roles/garder/SENS.md) | 0 | keep |
| 47 | `niveaux` | `levels` | 6 (UTILISATEURS.md, docs/reputation.md, outils/bee.py) | 0 |  |
| 48 | `classement` | `ranking` | 12 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| 49 | `verifier-acceptation` | `check-acceptance` | 15 (outils/test_bee.py, docs/contributions.md, docs/architecture.md) | 0 | integration-auto (R3) |
| 50 | `integrer` | `integrate` | 5 (outils/test_bee.py, docs/contributions.md, .github/workflows/integration-auto.yml) | 0 | integration-auto |
| 51 | `record-merge` | `record-merge` | 6 (outils/test_bee.py, .github/workflows/integration-auto.yml, docs/contributions.md) | 0 | already English |
| 52 | `cloturer` | `close` | 6 (outils/test_bee.py, docs/contributions.md, .github/workflows/integration-auto.yml) | 0 | integration-auto; no clash with `debate close` (another level) |
| 53 | `ecartees` | `set-aside` | 2 (outils/bee.py, .github/workflows/integration-auto.yml) | 0 | integration-auto reads its TSV output |
| 54 | `verifier-pr` | `check-pr` | 50 (outils/test_bee.py, docs/contributions.md, docs/gouvernance.md) | 0 | THE GATE: validation.yml (PR's tool) and fusion-auto.yml (main's tool, exit codes 0/3) |
| 55 | `prs-declarees` | `declared-prs` | 3 (outils/test_bee.py, .github/workflows/fusion-auto.yml, outils/bee.py) | 0 | fusion-auto |
| 56 | `ci-scope` | `ci-scope` | 4 (outils/test_bee.py, docs/architecture.md, docs/contributions.md) | 0 | already English; called with the BASE's tool |
| 57 | `push-scope` | `push-scope` | 3 (outils/test_bee.py, docs/contributions.md, outils/bee.py) | 0 | already English; called with the pre-push tool |
| 58 | `needs-account-date` | `needs-account-date` | 4 (outils/test_bee.py, .github/workflows/fusion-auto.yml, .github/workflows/validation.yml) | 0 | already English |
| 59 | `api-budget` | `api-budget` | 8 (outils/test_bee.py, .github/workflows/expirations.yml, .github/workflows/fusion-auto.yml) | 0 | already English |
| 60 | `main-green` | `main-green` | 5 (outils/test_bee.py, docs/contributions.md, .github/workflows/suite.yml) | 0 | already English; called with the BASE's tool |
| 61 | `acts-for` | `acts-for` | 5 (outils/test_bee.py, .github/workflows/integration-auto.yml, .github/workflows/verdicts.yml) | 0 | already English |
| 62 | `verifier-fork` | `check-fork` | 10 (outils/test_bee.py, AGENTS.en.md, COMMANDEMENTS.md) | 5 (libyamlBee:.github/workflows/bee-ci.yml, libyamlBee:bee/ci/manifeste.sh) | CALLED BY BOTH FORKS' CI from registry main, unpinned (bee/ci/manifeste.sh) |
| 63 | `enregistrer-verdict` | `record-verdict` | 16 (outils/test_bee.py, docs/contributions.md, .github/workflows/verdicts.yml) | 3 (libyamlBee:bee/ci/verdict.py, minizBee:bee/README.md) | verdicts.yml |
| 64 | `choisir-execution` | `pick-run` | 2 (.github/workflows/verdicts.yml, outils/bee.py) | 0 | verdicts.yml |
| 65 | `bases-declarees` | `declared-bases` | 3 (outils/test_bee.py, .github/workflows/verdicts.yml, outils/bee.py) | 0 | verdicts.yml |
| 66 | `publier` | `publish` | 32 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 | the rehearsal wrapper refuses it by name (outils/repetition/bee) |
| 67 | `en-attente` | `pending` | 5 (outils/test_bee.py, .github/workflows/integration-auto.yml, .github/workflows/verdicts.yml) | 0 | integration-auto and verdicts parse its JSON |
| 68 | `site` | `site` | 10 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 | keep |

Renamed: 58 of 68.

### 1.2 Options and positionals of `bee`

120 distinct options and positionals over all subcommands (an option keeps one English name whatever the subcommand). Choices of an option are enumerated values (section 4).

| French | English | Subcommands | Used in (files) | Forks | Note |
|---|---|---|---|---|---|
| `--registre` | `--registry` | (global) | 12 (outils/test_bee.py, .github/workflows/validation.yml, .github/workflows/fusion-auto.yml) | 4 (libyamlBee:bee/ci/manifeste.sh, libyamlBee:bee/ci/tache.py) | global; help names $BEE_REGISTRE |
| `--version` | `--version` | (global) | 3 (outils/bee.py, outils/juge/stats.py, outils/test_bee.py) | 3 (libyamlBee:.github/workflows/main.yml, libyamlBee:bee/bench/ab.py) |  |
| `--a-blanc` | `--dry-run` | debattre importer-questions, publier | 9 (outils/test_bee.py, outils/bee.py, AGENTS.en.md) | 0 | publier already accepts --dry-run as a second spelling: keep only --dry-run |
| `--dry-run` | `--dry-run` | publier | 2 (outils/test_bee.py, outils/bee.py) | 0 | already English |
| `--ab` | `--ab` | enregistrer-mesure | 4 (outils/test_bee.py, arbre/roles/mesurer/SENS.md, docs/mesures.md) | 2 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | keep (ab.py report) |
| `--amont` | `--upstream` | publier | 2 (taches/…, outils/bee.py) | 0 |  |
| `--ancien` | `--old` | renommer | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `--api` | `--api` | choisir-execution, record-merge | 4 (outils/test_bee.py, outils/bee.py, .github/workflows/integration-auto.yml) | 0 |  |
| `--apres` | `--after` | push-scope | 4 (.github/workflows/site.yml, .github/workflows/validation.yml, outils/bee.py) | 0 | push-scope, validation.yml and site.yml call it with the pre-push tool: fails closed (full) once |
| `--arbre` | `--tree` | enregistrer-verdict | 4 (outils/test_bee.py, .github/workflows/verdicts.yml, outils/bee.py) | 0 | git tree sha (verdicts.yml) |
| `--argument` | `--argument` | debattre doublon | 3 (outils/test_bee.py, docs/agora.md, outils/bee.py) | 0 |  |
| `--auteur` | `--author` | verifier-fork, verifier-pr | 10 (outils/test_bee.py, outils/bee.py, .github/workflows/fusion-auto.yml) | 2 (libyamlBee:bee/ci/manifeste.sh, minizBee:bee/ci/manifeste.sh) | verifier-pr in validation and fusion-auto; verifier-fork in the forks |
| `--auteurs-pr` | `--pr-authors` | verifier-pr | 7 (outils/test_bee.py, outils/bee.py, .github/workflows/fusion-auto.yml) | 0 | fusion-auto |
| `--autre-compte` | `--other-account` | lier | 3 (outils/test_bee.py, outils/bee.py, docs/reputation.md) | 0 |  |
| `--autre-identite` | `--other-identity` | inviter | 3 (outils/test_bee.py, docs/croissance.md, outils/bee.py) | 0 |  |
| `--avant` | `--before` | push-scope | 4 (outils/test_bee.py, .github/workflows/site.yml, .github/workflows/validation.yml) | 0 | push-scope (pre-push tool) |
| `--avis` | `--opinion` | relire | 7 (outils/test_bee.py, AGENTS.en.md, arbre/roles/relire/SENS.md) | 0 | values favorable \| unfavorable \| abstention |
| `--base` | `--base` | 7 subcommands | 19 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 17 (minizBee:bee/README.md, libyamlBee:.github/workflows/bee-ci.yml) |  |
| `--bases` | `--bases` | enregistrer-verdict | 4 (outils/test_bee.py, outils/bee.py, .github/workflows/verdicts.yml) | 0 |  |
| `--budget` | `--budget` | contexte | 9 (outils/test_bee.py, outils/bee.py, docs/arbre.md) | 0 |  |
| `--canal` | `--channel` | inviter, retirer-donnees | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| `--candidat` | `--candidate` | enregistrer-mesure | 1 (outils/bee.py) | 0 |  |
| `--categorie` | `--category` | lister | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `--categories` | `--categories` | inscrire | 1 (outils/bee.py) | 0 |  |
| `--commit` | `--commit` | relire | 10 (outils/test_bee.py, outils/bee.py, arbre/roles/relire/SENS.md) | 0 |  |
| `--compte-cree-le` | `--account-created-on` | inscrire, verifier-pr | 10 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | validation and fusion-auto |
| `--compte-de` | `--account-of` | lier | 3 (outils/test_bee.py, outils/bee.py, docs/reputation.md) | 0 |  |
| `--comptes` | `--accounts` | signaler | 3 (outils/test_bee.py, docs/gouvernance.md, outils/bee.py) | 0 |  |
| `--confirmer` | `--confirm` | retirer-donnees | 3 (outils/bee.py, docs/croissance.md, outils/test_bee.py) | 0 |  |
| `--conteste` | `--contest` | debattre argumenter | 4 (outils/test_bee.py, docs/agora.md, outils/bee.py) | 0 |  |
| `--corps` | `--body` | publier | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `--de` | `--of` | debattre doublon | 3 (outils/test_bee.py, docs/agora.md, outils/bee.py) | 0 |  |
| `--defaut` | `--defect` | relire | 4 (outils/test_bee.py, arbre/roles/relire/SENS.md, docs/gardiens.md) | 0 |  |
| `--deja-lu` | `--already-read` | contexte | 6 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| `--delai` | `--timeout` | publier | 3 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 |  |
| `--demande` | `--request` | inviter | 3 (outils/test_bee.py, docs/croissance.md, outils/bee.py) | 0 |  |
| `--demande-le` | `--requested-on` | retirer-donnees | 3 (outils/test_bee.py, docs/croissance.md, outils/bee.py) | 0 |  |
| `--depot` | `--repo` | verifier-fork | 4 (outils/test_bee.py, AGENTS.en.md, arbre/roles/optimiser/SENS.md) | 8 (libyamlBee:.github/workflows/bee-ci.yml, libyamlBee:bee/ci/verdict.py) | verifier-fork in the forks |
| `--disponibles` | `--available` | lister | 8 (AGENTS.md, outils/test_bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| `--dossier` | `--dir` | api-budget | 8 (outils/test_bee.py, .github/workflows/expirations.yml, .github/workflows/fusion-auto.yml) | 0 | api-budget in every workflow |
| `--ecarter` | `--dismiss` | signalement | 3 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 |  |
| `--en-parallele` | `--parallel` | prendre | 14 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| `--execution` | `--run` | enregistrer-verdict | 4 (.github/workflows/verdicts.yml, outils/bee.py, outils/repetition/ci_simulee.py) | 0 | verdicts.yml |
| `--fait` | `--fact` | inviter | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| `--fichier` | `--file` | debattre synthetiser, inviter | 2 (outils/bee.py, docs/agora.md) | 0 |  |
| `--fichiers` | `--files` | enregistrer-verdict | 5 (outils/test_bee.py, .github/workflows/verdicts.yml, outils/bee.py) | 0 | verdicts.yml |
| `--fusion-auto` | `--auto-merge` | verifier-pr | 9 (outils/test_bee.py, outils/repetition/load_test.py, .github/workflows/fusion-auto.yml) | 0 | fusion-auto relies on exit codes 0 and 3, never on the printed line |
| `--fusion-sha` | `--merge-sha` | integrer | 3 (outils/test_bee.py, .github/workflows/integration-auto.yml, outils/bee.py) | 0 | integration-auto |
| `--fusionnees` | `--merged` | cloturer | 3 (.github/workflows/integration-auto.yml, outils/bee.py, outils/test_bee.py) | 0 | integration-auto |
| `--github-id` | `--github-id` | inscrire, verifier-pr | 8 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `--homonyme` | `--namesake` | inviter | 1 (outils/bee.py) | 0 |  |
| `--identifiant` | `--identifier` | inviter | 3 (outils/test_bee.py, docs/croissance.md, outils/bee.py) | 0 |  |
| `--identifiants-de` | `--identifiers-from` | retirer-donnees | 3 (outils/test_bee.py, docs/croissance.md, outils/bee.py) | 0 |  |
| `--instant-pr` | `--pr-time` | verifier-pr | 5 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | validation and fusion-auto |
| `--intervalle` | `--interval` | publier | 2 (outils/test_bee.py, outils/bee.py) | 0 | hidden |
| `--invitation` | `--invitation` | debattre caviarder | 4 (outils/test_bee.py, docs/agora.md, docs/croissance.md) | 0 |  |
| `--issue` | `--outcome` | debattre clore | 4 (outils/test_bee.py, arbre/roles/debattre/SENS.md, docs/agora.md) | 0 | French issue = outcome; English « issue » means a GitHub issue |
| `--jeton` | `--token` | api-budget | 8 (outils/test_bee.py, .github/workflows/integration-auto.yml, .github/workflows/expirations.yml) | 0 | api-budget in every workflow |
| `--jours` | `--days` | cap, ecartees | 2 (outils/bee.py, .github/workflows/integration-auto.yml) | 0 |  |
| `--json` | `--json` | 6 subcommands | 11 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 6 (libyamlBee:bee/bench/ab.py, minizBee:bee/README.md) |  |
| `--langue` | `--language` | inviter | 2 (docs/croissance.md, outils/bee.py) | 0 | values en \| fr (the R13 mention may stay bilingual: outgoing text, not a name) |
| `--lier` | `--link` | signalement | 3 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 |  |
| `--lignes` | `--lines` | enregistrer-verdict | 1 (outils/bee.py) | 0 |  |
| `--manifeste` | `--manifest` | enregistrer-verdict | 7 (outils/test_bee.py, docs/contributions.md, .github/workflows/verdicts.yml) | 6 (libyamlBee:bee/ci/tache.py, libyamlBee:bee/ci/verdict.py) | verdicts.yml |
| `--message` | `--message` | inviter | 3 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| `--metrique` | `--metric` | proposer-tache | 1 (outils/bee.py) | 0 |  |
| `--mettre-a-jour` | `--update` | soumettre | 5 (outils/test_bee.py, outils/bee.py, docs/contributions.md) | 0 |  |
| `--modele` | `--model` | manifeste | 4 (AGENTS.en.md, arbre/roles/optimiser/SENS.md, outils/bee.py) | 0 |  |
| `--motif` | `--reason` | 8 subcommands | 11 (outils/test_bee.py, outils/bee.py, arbre/roles/relire/SENS.md) | 0 |  |
| `--non-contact` | `--no-contact` | retirer-donnees | 3 (outils/bee.py, docs/croissance.md, outils/test_bee.py) | 0 |  |
| `--note` | `--note` | liberer | 8 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| `--outil` | `--tool` | enregistrer-mesure | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `--par` | `--by` | cloturer | 1 (outils/bee.py) | 0 | integration-auto passes the default |
| `--position` | `--position` | debattre argumenter | 7 (outils/test_bee.py, AGENTS.en.md, docs/agora.md) | 0 |  |
| `--poste` | `--area` | cap, lister | 2 (outils/bee.py, outils/test_bee.py) | 0 | R11 area (see cap -> balance) |
| `--pr` | `--pr` | soumettre | 8 (outils/test_bee.py, outils/bee.py, AGENTS.en.md) | 0 |  |
| `--pr-states` | `--pr-states` | en-attente | 5 (outils/test_bee.py, .github/workflows/verdicts.yml, .github/workflows/integration-auto.yml) | 0 |  |
| `--projet` | `--project` | classement, lister | 1 (outils/bee.py) | 0 |  |
| `--pseudo` | `--login` | inscrire, renommer | 6 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 | a pseudo is the GitHub login |
| `--question` | `--question` | debattre ouvrir | 6 (outils/test_bee.py, outils/bee.py, arbre/roles/debattre/SENS.md) | 0 |  |
| `--raison` | `--cause` | invitation retirer | 3 (outils/test_bee.py, outils/bee.py, taches/…) | 0 | kept distinct from --reason (motif) so that the token map stays one-to-one |
| `--redater` | `--redate` | publier | 6 (outils/test_bee.py, outils/bee.py, taches/…) | 0 |  |
| `--reference` | `--reference` | debattre clore, retirer-donnees | 9 (outils/test_bee.py, outils/bee.py, contributions/…) | 11 (libyamlBee:bee/fuzz/lancer.sh, minizBee:bee/fuzz/lancer.sh) |  |
| `--regle` | `--rule` | proposer | 4 (outils/test_bee.py, arbre/roles/proposer/SENS.md, docs/gouvernance.md) | 0 |  |
| `--relecteur` | `--reviewer` | confirmer-defaut | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `--repond-a` | `--replies-to` | debattre argumenter | 5 (outils/test_bee.py, arbre/roles/debattre/SENS.md, docs/agora.md) | 0 |  |
| `--resume` | `--summary` | soumettre | 6 (outils/test_bee.py, outils/bee.py, AGENTS.en.md) | 0 |  |
| `--role` | `--role` | contexte | 16 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 | values change: optimize, review, measure, debate, guard, propose, invite |
| `--runs` | `--runs` | main-green | 3 (.github/workflows/validation.yml, outils/test_bee.py, outils/bee.py) | 0 |  |
| `--sans-attendre` | `--no-wait` | publier | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `--sha` | `--sha` | choisir-execution, enregistrer-verdict | 4 (outils/test_bee.py, .github/workflows/verdicts.yml, outils/bee.py) | 0 |  |
| `--sortie` | `--output` | manifeste, site | 5 (outils/test_bee.py, outils/bee.py, .github/workflows/site.yml) | 15 (libyamlBee:bee/ci/tache.py, libyamlBee:bee/ci/verdict.py) |  |
| `--source` | `--source` | debattre argumenter, debattre importer-questions, inviter | 7 (outils/test_bee.py, outils/bee.py, AGENTS.en.md) | 12 (libyamlBee:bee/ci/tests.sh, libyamlBee:bee/fuzz/lancer.sh) |  |
| `--statut` | `--status` | classement, debats, lister | 11 (outils/bee.py, outils/test_bee.py, arbre/roles/garder/SENS.md) | 0 |  |
| `--suivant` | `--next` | debattre clore, debattre synthetiser | 3 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 |  |
| `--synthese` | `--synthesis` | debattre clore, debattre ouvrir | 3 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 |  |
| `--tache` | `--task` | verifier-fork | 4 (outils/test_bee.py, AGENTS.en.md, arbre/roles/optimiser/SENS.md) | 4 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | verifier-fork in the forks |
| `--taille` | `--size` | proposer-tache | 3 (arbre/roles/proposer/SENS.md, outils/bee.py, outils/test_bee.py) | 0 |  |
| `--taille-max` | `--max-size` | lister | 7 (AGENTS.md, .claude/skills/bee-contributeur/SKILL.md, AGENTS.en.md) | 0 |  |
| `--tete` | `--head` | 5 subcommands | 12 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 6 (libyamlBee:bee/ci/verdict.py, minizBee:.github/workflows/bee-ci.yml) | ci-scope (BASE's tool), verifier-pr, verifier-fork (forks) |
| `--texte` | `--text` | debattre argumenter, debattre synthetiser, noter, proposer | 9 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| `--titre` | `--title` | incident, publier | 17 (outils/test_bee.py, outils/bee.py, .claude/skills/bee-contributeur/SKILL.md) | 0 |  |
| `--type` | `--type` | lister, proposer-tache | 5 (outils/test_bee.py, arbre/roles/mesurer/SENS.md, outils/bee.py) | 0 |  |
| `--utilisateur` | `--user` | 32 subcommands | 26 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 | 32 subcommands |
| `--valeur` | `--value` | invitation consigner-reponse, voter | 7 (outils/test_bee.py, outils/bee.py, arbre/roles/relire/SENS.md) | 0 |  |
| `--verdict` | `--verdict` | enregistrer-verdict | 4 (outils/test_bee.py, .github/workflows/verdicts.yml, outils/bee.py) | 0 |  |
| `--voir` | `--show` | debats | 10 (docs/questions-ouvertes.md, outils/bee.py, outils/test_bee.py) | 0 |  |
| `<argument>` | `<argument>` | debattre caviarder | (positional) |  |  |
| `<contribution>` | `<contribution>` | 9 subcommands | (positional) |  |  |
| `<debat>` | `<debate>` | 5 subcommands | (positional) |  |  |
| `<fichier>` | `<file>` | valider-contribution | (positional) |  |  |
| `<invitation>` | `<invitation>` | 8 subcommands | (positional) |  |  |
| `<login>` | `<login>` | acts-for | (positional) |  |  |
| `<moment>` | `<moment>` | api-budget | (positional) |  | values start \| end |
| `<projet>` | `<project>` | proposer-tache | (positional) |  |  |
| `<proposition>` | `<proposal>` | depouiller | (positional) |  |  |
| `<signalement>` | `<report>` | signalement | (positional) |  |  |
| `<sujet>` | `<subject>` | voter | (positional) |  |  |
| `<tache>` | `<task>` | 7 subcommands | (positional) |  |  |
| `<verdict>` | `<verdict>` | bases-declarees | (positional) |  |  |

Renamed: 88 of 120.

### 1.3 Other scripts invoked by workflows, forks or docs

| Script | French | English | Used in (files) | Forks | Note |
|---|---|---|---|---|---|
| outils/juge/juge.py | `--outillage` | `--tooling` | 3 (outils/juge/test_juge.py, outils/juge/juge.py, .github/workflows/juge.yml) | 3 (minizBee:.github/workflows/bee-ci.yml, minizBee:bee/README.md) | forks call it at the PINNED judge commit: unaffected until they bump |
| outils/juge/juge.py | `--source-a` | `--source-a` | 5 (outils/juge/test_juge.py, outils/juge/juge.py, .github/workflows/juge.yml) | 3 (minizBee:.github/workflows/bee-ci.yml, minizBee:bee/README.md) |  |
| outils/juge/juge.py | `--source-b` | `--source-b` | 5 (outils/juge/test_juge.py, outils/juge/juge.py, .github/workflows/juge.yml) | 3 (minizBee:.github/workflows/bee-ci.yml, minizBee:bee/README.md) |  |
| outils/juge/juge.py | `--image-seulement` | `--image-only` | 4 (outils/juge/test_juge.py, outils/juge/juge.py, .github/workflows/juge.yml) | 1 (minizBee:.github/workflows/bee-ci.yml) | forks (BEE_IMAGE), juge.yml |
| outils/juge/juge.py | `--historique-seulement` | `--history-only` | 3 (outils/juge/test_juge.py, outils/juge/juge.py, .github/workflows/juge.yml) | 0 | juge.yml |
| outils/juge/juge.py | `--historique` | `--history` | 3 (outils/juge/test_juge.py, outils/juge/juge.py, .github/workflows/juge.yml) | 0 | juge.yml |
| outils/juge/juge.py | `--source-juge` | `--judge-source` | 3 (.github/workflows/juge.yml, outils/juge/juge.py, outils/juge/test_juge.py) | 0 | juge.yml |
| outils/juge/juge.py | `--base` | `--base` | 19 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 17 (minizBee:bee/README.md, libyamlBee:.github/workflows/bee-ci.yml) |  |
| outils/juge/juge.py | `--tete` | `--head` | 12 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 6 (libyamlBee:bee/ci/verdict.py, minizBee:.github/workflows/bee-ci.yml) | juge.yml |
| outils/juge/juge.py | `--travail` | `--workdir` | 4 (outils/juge/test_juge.py, .github/workflows/juge.yml, docs/juge-commun.md) | 0 | juge.yml |
| outils/juge/juge.py | `--option` | `--option` | 4 (outils/juge/juge.py, .github/workflows/juge.yml, docs/juge-commun.md) | 0 | juge.yml |
| outils/juge/juge.py | `--repetitions` | `--repetitions` | 6 (outils/juge/test_juge.py, outils/juge/juge.py, contributions/…) | 14 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| outils/juge/juge.py | `--chauffe` | `--warmup` | 2 (outils/juge/test_juge.py, outils/juge/juge.py) | 5 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| outils/juge/juge.py | `--sans-instructions` | `--no-instructions` | 2 (outils/juge/test_juge.py, outils/juge/juge.py) | 1 (minizBee:bee/juge/test_juge.py) |  |
| outils/juge/juge.py | `--prefixe-instructions` | `--instructions-prefix` | 2 (outils/juge/juge.py, outils/juge/test_juge.py) | 2 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| outils/juge/juge.py | `--seuil-instructions` | `--instructions-threshold` | 1 (outils/juge/juge.py) | 2 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| outils/juge/juge.py | `--json` | `--json` | 11 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 6 (libyamlBee:bee/bench/ab.py, minizBee:bee/README.md) |  |
| outils/juge/juge.py | `--graine` | `--seed` | 6 (outils/juge/test_juge.py, outils/juge/juge.py, outils/repetition/load_test.py) | 1 (minizBee:bee/README.md) |  |
| outils/juge/juge.py | `--graine-ordre` | `--order-seed` | 3 (outils/juge/test_juge.py, docs/juge-commun.md, outils/juge/juge.py) | 0 |  |
| outils/juge/juge.py | `--reseau-construction` | `--build-network` | 2 (outils/juge/test_juge.py, outils/juge/juge.py) | 2 (minizBee:bee/README.md, minizBee:bee/juge/test_juge.py) | fork README documents it |
| outils/juge/juge.py | `--memoire` | `--memory` | 2 (outils/juge/isoler.sh, outils/juge/juge.py) | 0 |  |
| outils/juge/juge.py | `--garder` | `--keep` | 1 (outils/juge/juge.py) | 2 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| outils/juge/rapport.py | `--code` | `--code` | 6 (outils/site_bee.py, docs/juge-commun.md, outils/juge/rapport.py) | 0 | juge.yml |
| outils/juge/rapport.py | `--verifier` | `--verify` | 6 (outils/juge/test_juge.py, docs/juge-commun.md, outils/juge/rapport.py) | 0 |  |
| outils/juge/rapport.py | `--base` | `--base` | 19 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 17 (minizBee:bee/README.md, libyamlBee:.github/workflows/bee-ci.yml) |  |
| outils/juge/rapport.py | `--tete` | `--head` | 12 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 6 (libyamlBee:bee/ci/verdict.py, minizBee:.github/workflows/bee-ci.yml) |  |
| outils/test_bee.py | `--processus` | `--processes` | 3 (outils/test_bee.py, .github/workflows/suite.yml, docs/contributions.md) | 0 | suite.yml; a test pins the exact command line |
| outils/repetition/load_test.py | `<dossier>` | `<dir>` |  |  |  |
| outils/repetition/load_test.py | `--membres` | `--members` | 4 (outils/repetition/load_test.py, docs/outillage.md, outils/repetition/test_load_test.py) | 0 |  |
| outils/repetition/load_test.py | `--graine` | `--seed` | 6 (outils/juge/test_juge.py, outils/juge/juge.py, outils/repetition/load_test.py) | 1 (minizBee:bee/README.md) |  |
| outils/repetition/load_test.py | `--registre` | `--registry` | 12 (outils/test_bee.py, .github/workflows/validation.yml, .github/workflows/fusion-auto.yml) | 4 (libyamlBee:bee/ci/manifeste.sh, libyamlBee:bee/ci/tache.py) |  |
| outils/repetition/load_test.py | `--base` | `--base` | 19 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 17 (minizBee:bee/README.md, libyamlBee:.github/workflows/bee-ci.yml) |  |
| outils/repetition/load_test.py | `--rejouer` | `--replay` | 2 (outils/repetition/load_test.py, docs/outillage.md) | 0 |  |
| outils/inventaire_marqueurs.py | `--all` | `--all` | 2 (outils/inventaire_marqueurs.py, outils/test_bee.py) | 4 (minizBee:.github/workflows/bee-ci.yml, minizBee:bee/ci/test_verdict.py) | already English |
| outils/repetition/publier (script) | `<pseudo> <titre>` | `<login> <title>` |  |  | rehearsal wrapper |
| forks: bee/ci/tache.py (fork code, reads the registry) | `--manifeste` | `--manifest` | 7 (outils/test_bee.py, docs/contributions.md, .github/workflows/verdicts.yml) | 6 (libyamlBee:bee/ci/tache.py, libyamlBee:bee/ci/verdict.py) | fork-side: wave 2 |
| forks: bee/ci/tache.py (fork code, reads the registry) | `--registre` | `--registry` | 12 (outils/test_bee.py, .github/workflows/validation.yml, .github/workflows/fusion-auto.yml) | 4 (libyamlBee:bee/ci/manifeste.sh, libyamlBee:bee/ci/tache.py) | fork-side: wave 2 |
| forks: bee/ci/tache.py (fork code, reads the registry) | `--sortie` | `--output` | 5 (outils/test_bee.py, outils/bee.py, .github/workflows/site.yml) | 15 (libyamlBee:bee/ci/tache.py, libyamlBee:bee/ci/verdict.py) | fork-side: wave 2 |

## 2. Folders and files

| French | English | Used in (files) | Forks | Note |
|---|---|---|---|---|
| `taches/` | `tasks/` | 27 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 1 (minizBee:bee/corpus/generer.py) | self-service; forks glob it from main (tache.py); CHEMIN_TACHE, history paths |
| `contributions/` | `contributions/` | 14 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 | keep |
| `debats/` | `debates/` | 17 (outils/test_bee.py, docs/questions-ouvertes.md, outils/bee.py) | 0 | self-service; a debate file is never deleted, even by the council: needs the migration path |
| `propositions/` | `proposals/` | 10 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | self-service |
| `membres/` | `members/` | 15 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | self-service; no file on main today (code and fixtures only) |
| `votes/` | `votes/` | 10 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | keep (no file on main today) |
| `mesures/` | `measurements/` | 7 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | self-service; a measurement is never changed or moved, even by the council; none on main today |
| `invitations/` | `invitations/` | 9 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 | keep (no file on main today) |
| `invitations/ne-plus-contacter.yaml` | `invitations/do-not-contact.yaml` | 7 (outils/test_bee.py, docs/croissance.md, docs/gouvernance.md) | 0 | R13 list; byte bound by path in OCTETS_MAX |
| `signalements/` | `reports/` | 5 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | self-service (ruche-0118); none on main today |
| `gouvernance/` | `governance/` | 36 (outils/test_bee.py, outils/bee.py, docs/decisions.md) | 0 | council-only; AUTHORITY_FILES and LISTES_LIEES name files in it |
| `gouvernance/conseil.yaml` | `governance/council.yaml` | 5 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 0 | authority file |
| `gouvernance/gardiens.yaml` | `governance/guardians.yaml` | 16 (outils/test_bee.py, outils/bee.py, REGLES.md) | 0 | authority file |
| `gouvernance/garants.yaml` | `governance/guarantors.yaml` | 11 (outils/test_bee.py, taches/…, outils/bee.py) | 0 | authority file |
| `gouvernance/comptes-agents.yaml` | `governance/agent-accounts.yaml` | 7 (outils/test_bee.py, outils/bee.py, taches/…) | 0 | authority file; already English inside |
| `gouvernance/incidents.yaml` | `governance/incidents.yaml` | 4 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 | a guardian's own path rule (bee incident) |
| `gouvernance/retraits.yaml` | `governance/removals.yaml` | 4 (outils/bee.py, docs/croissance.md, schemas/retraits.schema.json) | 0 | a PR touching it is judged alone (verifier_retrait) |
| `gouvernance/consignes/` | `governance/briefs/` | 11 (outils/test_bee.py, docs/decisions.md, docs/organisation.md) | 0 | authority prefix; garants.yaml points into it |
| `gouvernance/consignes/abeille-du-conseil.md` | `governance/briefs/council-bee.md` | 2 (docs/organisation.md, gouvernance/consignes/agent-principal.md) | 0 |  |
| `gouvernance/consignes/agent-principal.md` | `governance/briefs/agent-principal.md` | 5 (docs/decisions.md, docs/garants.md, docs/organisation.md) | 0 | « agent principal » is the English term already |
| `gouvernance/consignes/constructeur.md` | `governance/briefs/builder.md` | 3 (docs/organisation.md, gouvernance/consignes/agent-principal.md, outils/test_bee.py) | 0 |  |
| `gouvernance/consignes/relecteur-adverse.md` | `governance/briefs/adversarial-reviewer.md` | 2 (docs/organisation.md, gouvernance/consignes/agent-principal.md) | 0 |  |
| `gouvernance/consignes/repetition-generale.md` | `governance/briefs/dress-rehearsal.md` | 2 (docs/organisation.md, outils/repetition/monter.sh) | 0 |  |
| `projets/` | `projects/` | 208 (outils/test_bee.py, outils/bee.py, README.md) | 7 (libyamlBee:bee/ci/tache.py, libyamlBee:bee/bench/ab.py) | council-only; libyamlBee's tache.py reads projets/libyaml.yaml from main |
| `projets/<id>.yaml` | `projects/<id>.yaml` | 0 | 0 | file names are project ids: unchanged |
| `modeles/` | `templates/` | 5 (taches/…, MAINTENEURS.md, docs/taches.md) | 0 | tooling path (CHEMINS_OUTILLAGE) |
| `modeles/tache.yaml` | `templates/task.yaml` | 3 (docs/taches.md, outils/bee.py, taches/…) | 0 |  |
| `modeles/BEE.md` | `templates/BEE.md` | 2 (MAINTENEURS.md, taches/…) | 0 |  |
| `arbre/` | `tree/` | 29 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 | tooling path; node ids are paths under it |
| `arbre/SENS.md (and every */SENS.md)` | `tree/MEANING.md` | 5 (outils/test_bee.py, outils/bee.py, taches/…) | 0 | FICHIER_NOEUD; 18 nodes |
| `arbre/roles/` | `tree/roles/` | 21 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 | RANGEMENTS_ARBRE |
| `arbre/roles/debattre` | `tree/roles/debate` | 24 (outils/test_bee.py, outils/bee.py, docs/agora.md) | 0 | role names = --role values |
| `arbre/roles/garder` | `tree/roles/guard` | 21 (outils/test_bee.py, outils/juge/chrono.c, AGENTS.md) | 7 (libyamlBee:bee/bench/ab.py, libyamlBee:bee/fuzz/lancer.sh) |  |
| `arbre/roles/inviter` | `tree/roles/invite` | 18 (outils/test_bee.py, outils/bee.py, docs/croissance.md) | 0 |  |
| `arbre/roles/mesurer` | `tree/roles/measure` | 39 (outils/test_bee.py, AGENTS.md, outils/bee.py) | 6 (libyamlBee:bee/bench/banc.c, libyamlBee:bee/sandbox/sans-docker.sh) |  |
| `arbre/roles/optimiser` | `tree/roles/optimize` | 30 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 |  |
| `arbre/roles/proposer` | `tree/roles/propose` | 30 (outils/test_bee.py, outils/bee.py, docs/gouvernance.md) | 1 (libyamlBee:CONTRIBUTION.yaml) |  |
| `arbre/roles/relire` | `tree/roles/review` | 46 (outils/test_bee.py, outils/bee.py, docs/decisions.md) | 1 (libyamlBee:bee/tests/aller_retour.c) |  |
| `arbre/projets/` | `tree/projects/` | 225 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 9 (libyamlBee:bee/ci/tache.py, minizBee:bee/README.md) | RANGEMENTS_ARBRE; prefix of every task's noeud value |
| `arbre/projets/compression-sans-perte` | `tree/projects/lossless-compression` | 66 (outils/test_bee.py, arbre/projets/compression-sans-perte/miniz/SENS.md, outils/bee.py) | 0 | category id |
| `arbre/projets/parsing-serialisation` | `tree/projects/parsing-serialization` | 32 (outils/test_bee.py, taches/…, outils/tests/registre/taches/libyaml/libyaml-0013.yaml) | 0 | category id |
| `arbre/projets/ruche, arbre/projets/ruche/ruche` | `tree/projects/ruche, .../ruche` | 229 (outils/test_bee.py, outils/bee.py, docs/decisions.md) | 5 (libyamlBee:bee/corpus/generer.py, libyamlBee:bee/README.md) | keep: project id (see open question) |
| `arbre/projets/*/miniz/{api,bee,deflate,inflate}, .../libyaml` | `unchanged` | 0 | 0 | zone and project ids |
| `outils/` | `tools/` | 197 (outils/test_bee.py, projets/ruche.yaml, .github/workflows/integration-auto.yml) | 8 (minizBee:.github/workflows/bee-ci.yml, minizBee:bee/README.md) | forks run registre/outils/bee.py and outils/requirements.txt from MAIN; juge.yml paths |
| `outils/bee.py, site_bee.py, test_bee.py, requirements.txt` | `tools/ (same names)` | 125 (outils/test_bee.py, .github/workflows/integration-auto.yml, .github/workflows/validation.yml) | 2 (libyamlBee:bee/ci/manifeste.sh, minizBee:bee/ci/manifeste.sh) |  |
| `outils/inventaire_marqueurs.py` | `tools/marker_inventory.py` | 2 (outils/inventaire_marqueurs.py, outils/test_bee.py) | 0 |  |
| `outils/tests/registre/` | `tools/tests/registry/` | 186 (outils/bee.py, outils/test_bee.py, outils/juge/test_juge.py) | 29 (minizBee:bee/README.md, minizBee:.github/workflows/bee-ci.yml) | frozen fixture (ruche-0093); migrated by the same script |
| `outils/tests/registre/taches/` | `tools/tests/registry/tasks/` | 35 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 3 (libyamlBee:bee/ci/tache.py, minizBee:bee/ci/tache.py) |  |
| `outils/tests/textes-0047/` | `tools/tests/texts-0047/` | 1 (outils/test_bee.py) | 0 |  |
| `outils/juge/` | `tools/judge/` | 155 (outils/juge/test_juge.py, docs/juge-commun.md, outils/test_bee.py) | 25 (minizBee:bee/ci/test_verdict.py, minizBee:.github/workflows/bee-ci.yml) | forks read it at a PINNED commit (juge-v2): unaffected until they bump |
| `outils/juge/juge.py` | `tools/judge/judge.py` | 17 (outils/juge/test_juge.py, .github/workflows/juge.yml, outils/juge/juge.py) | 12 (minizBee:.github/workflows/bee-ci.yml, minizBee:bee/ci/test_verdict.py) |  |
| `outils/juge/analyse.py` | `tools/judge/analysis.py` | 5 (outils/juge/juge.py, contributions/…) | 3 (minizBee:bee/README.md, minizBee:manifestes/miniz-0031.yaml) |  |
| `outils/juge/chrono.c` | `tools/judge/stopwatch.c` | 5 (outils/juge/conteneur.py, contributions/…) | 3 (minizBee:bee/README.md, minizBee:manifestes/miniz-0031.yaml) |  |
| `outils/juge/conteneur.py` | `tools/judge/container.py` | 1 (outils/juge/Dockerfile.base) | 0 |  |
| `outils/juge/entrees.py` | `tools/judge/inputs.py` | 0 | 0 |  |
| `outils/juge/isoler.sh` | `tools/judge/isolate.sh` | 6 (contributions/…, outils/juge/isoler.sh, taches/…) | 7 (minizBee:manifestes/miniz-0032.yaml, minizBee:.github/workflows/bee-ci.yml) | forks call it (ISOLER) at the pinned commit |
| `outils/juge/lecture.py` | `tools/judge/reader.py` | 2 (docs/juge-commun.md, outils/juge/juge.py) | 0 |  |
| `outils/juge/rapport.py` | `tools/judge/report.py` | 7 (outils/juge/test_juge.py, docs/juge-commun.md, outils/juge/rapport.py) | 0 | juge.yml |
| `outils/juge/stats.py` | `tools/judge/stats.py` | 0 | 0 |  |
| `outils/juge/test_juge.py` | `tools/judge/test_judge.py` | 25 (outils/juge/test_juge.py, outils/tests/registre/taches/libyaml/libyaml-0014.yaml, projets/ruche.yaml) | 6 (minizBee:bee/README.md, minizBee:.github/workflows/bee-ci.yml) | suite.yml, juge-commun.yml |
| `outils/juge/Dockerfile.base` | `tools/judge/Dockerfile.base` | 2 (outils/juge/conteneur.py, docs/juge-commun.md) | 1 (minizBee:bee/README.md) |  |
| `outils/juge/jouet/` | `tools/judge/toy/` | 24 (outils/juge/test_juge.py, docs/juge-commun.md, taches/…) | 1 (minizBee:bee/README.md) | toy project for meta-tests |
| `outils/juge/jouet/bee/juge/projet.py` | `tools/judge/toy/bee/judge/project.py` | 20 (outils/juge/test_juge.py, outils/juge/juge.py, outils/tests/registre/taches/libyaml/libyaml-0014.yaml) | 9 (minizBee:bee/ci/test_verdict.py, minizBee:.github/workflows/bee-ci.yml) | mirrors the forks' plugin path: judge track only |
| `outils/juge/jouet/bee/juge/construire.sh` | `tools/judge/toy/bee/judge/build.sh` | 9 (outils/tests/registre/taches/libyaml/libyaml-0013.yaml, taches/…, outils/juge/test_juge.py) | 6 (minizBee:bee/README.md, minizBee:bee/juge/projet.py) | judge track only |
| `outils/juge/jouet/bee/juge/execution.c` | `tools/judge/toy/bee/judge/execution.c` | 14 (outils/tests/registre/taches/libyaml/libyaml-0013.yaml, taches/…, outils/juge/test_juge.py) | 5 (minizBee:bee/README.md, minizBee:bee/juge/construire.sh) | judge track only |
| `outils/repetition/` | `tools/rehearsal/` | 23 (outils/juge/test_juge.py, docs/juge-commun.md, outils/test_bee.py) | 2 (minizBee:bee/juge/test_juge.py, minizBee:bee/juge/projet.py) | dress rehearsal kit |
| `outils/repetition/LISEZMOI-modele.md` | `tools/rehearsal/README-template.md` | 1 (outils/repetition/monter.sh) | 0 |  |
| `outils/repetition/bee` | `tools/rehearsal/bee` | 345 (outils/test_bee.py, outils/bee.py, docs/architecture.md) | 80 (minizBee:bee/README.md, minizBee:.github/workflows/bee-ci.yml) | refuses `publier` by name |
| `outils/repetition/ci-simulee, ci_simulee.py` | `tools/rehearsal/simulated-ci, simulated_ci.py` | 5 (outils/repetition/ci-simulee, outils/repetition/ci_simulee.py, outils/repetition/monter.sh) | 0 |  |
| `outils/repetition/commun.sh` | `tools/rehearsal/common.sh` | 7 (outils/repetition/monter.sh, outils/repetition/bee, outils/repetition/ci-simulee) | 0 |  |
| `outils/repetition/decider-conseil` | `tools/rehearsal/council-decide` | 3 (outils/repetition/monter.sh, outils/repetition/decider-conseil, gouvernance/consignes/repetition-generale.md) | 0 |  |
| `outils/repetition/gh` | `tools/rehearsal/gh` | 32 (outils/test_bee.py, outils/bee.py, .github/workflows/verdicts.yml) | 4 (minizBee:bee/README.md, libyamlBee:bee/README.md) |  |
| `outils/repetition/horloge.py` | `tools/rehearsal/clock.py` | 6 (outils/repetition/bee, outils/repetition/ci_simulee.py, outils/repetition/decider-conseil) | 0 |  |
| `outils/repetition/load_test.py, test_load_test.py` | `tools/rehearsal/ (same names)` | 5 (docs/outillage.md, outils/repetition/load_test.py, outils/test_bee.py) | 0 |  |
| `outils/repetition/monter.sh` | `tools/rehearsal/setup.sh` | 6 (outils/repetition/monter.sh, outils/repetition/load_test.py, docs/outillage.md) | 0 |  |
| `outils/repetition/ouvrir-pr-fork` | `tools/rehearsal/open-fork-pr` | 5 (outils/repetition/monter.sh, outils/repetition/ouvrir-pr-fork, gouvernance/consignes/repetition-generale.md) | 0 |  |
| `outils/repetition/pousser-pr-fork` | `tools/rehearsal/push-fork-pr` | 5 (outils/repetition/monter.sh, outils/repetition/pousser-pr-fork, gouvernance/consignes/repetition-generale.md) | 0 |  |
| `outils/repetition/publier` | `tools/rehearsal/publish` | 43 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 |  |
| `schemas/` | `schemas/` | 66 (outils/test_bee.py, taches/…, docs/croissance.md) | 0 | keep; loaded from the tool's own folder, never from the data |
| `schemas/contribution.schema.json` | `schemas/manifest.schema.json` | 3 (docs/contributions.md, schemas/contribution.schema.json, taches/…) | 0 | it validates the fork MANIFEST |
| `schemas/enregistrement.schema.json` | `schemas/contribution-record.schema.json` | 8 (outils/test_bee.py, taches/…, outils/tests/textes-0047/ruche-0028.yaml) | 0 | never reuse « contribution.schema.json » for another content in the same move |
| `schemas/debat.schema.json` | `schemas/debate.schema.json` | 4 (docs/agora.md, outils/test_bee.py, schemas/debat.schema.json) | 0 |  |
| `schemas/incidents.schema.json` | `schemas/incidents.schema.json` | 2 (docs/croissance.md, schemas/incidents.schema.json) | 0 |  |
| `schemas/invitation.schema.json` | `schemas/invitation.schema.json` | 5 (docs/croissance.md, outils/test_bee.py, schemas/invitation.schema.json) | 0 |  |
| `schemas/membre.schema.json` | `schemas/member.schema.json` | 3 (schemas/membre.schema.json, taches/…) | 0 |  |
| `schemas/mesure.schema.json` | `schemas/measurement.schema.json` | 3 (docs/mesures.md, schemas/mesure.schema.json, taches/…) | 0 |  |
| `schemas/ne-plus-contacter.schema.json` | `schemas/do-not-contact.schema.json` | 1 (schemas/ne-plus-contacter.schema.json) | 0 |  |
| `schemas/projet.schema.json` | `schemas/project.schema.json` | 4 (taches/…, schemas/projet.schema.json) | 0 |  |
| `schemas/proposition.schema.json` | `schemas/proposal.schema.json` | 1 (schemas/proposition.schema.json) | 0 |  |
| `schemas/retraits.schema.json` | `schemas/removals.schema.json` | 2 (docs/croissance.md, schemas/retraits.schema.json) | 0 |  |
| `schemas/signalement.schema.json` | `schemas/report.schema.json` | 2 (schemas/signalement.schema.json, taches/…) | 0 |  |
| `schemas/tache.schema.json` | `schemas/task.schema.json` | 7 (docs/taches.md, contributions/…, outils/tests/registre/taches/ruche/ruche-0001.yaml) | 0 |  |
| `schemas/vote.schema.json` | `schemas/vote.schema.json` | 1 (schemas/vote.schema.json) | 0 |  |
| `REGLES.md` | `RULES.md` | 66 (outils/test_bee.py, taches/…, docs/gouvernance.md) | 0 | ruche-0058 planned RULES.md; French copy: see open question |
| `COMMANDEMENTS.md` | `(removed) or COMMANDMENTS.fr.md` | 66 (outils/test_bee.py, AGENTS.md, COMMANDMENTS.md) | 3 (libyamlBee:AGENTS.md, minizBee:AGENTS.md) | authority file; COMMANDMENTS.md is authoritative; forks link to it |
| `COMMANDMENTS.md` | `COMMANDMENTS.md` | 68 (outils/test_bee.py, AGENTS.en.md, AGENTS.md) | 0 | keep |
| `UTILISATEURS.md` | `USERS.md` | 4 (README.md, taches/…, outils/bee.py) | 0 | tooling path list names it |
| `MAINTENEURS.md` | `MAINTAINERS.md` | 3 (README.md, taches/…, outils/bee.py) | 0 | tooling path list names it |
| `AGENTS.md (French) + AGENTS.en.md` | `AGENTS.md (English)` | 36 (outils/test_bee.py, outils/bee.py, taches/…) | 8 (libyamlBee:CLAUDE.md, minizBee:CLAUDE.md) | forks and CLAUDE.md link AGENTS.md: the name stays, the language changes |
| `README.md, CLAUDE.md` | `README.md, CLAUDE.md` | 38 (outils/test_bee.py, arbre/projets/compression-sans-perte/miniz/api/SENS.md, arbre/projets/compression-sans-perte/miniz/bee/SENS.md) | 16 (libyamlBee:bee/sandbox/sans-docker.sh, minizBee:bee/sandbox/sans-docker.sh) | keep names; translate content |
| `bee.yaml, categories.yaml` | `bee.yaml, categories.yaml` | 48 (outils/bee.py, outils/test_bee.py, REGLES.md) | 0 | keep names; keys and values change |
| `docs/agora.md` | `docs/agora.md` | 12 (outils/bee.py, AGENTS.md, outils/site_bee.py) | 0 | keep |
| `docs/arbre.md` | `docs/tree.md` | 16 (outils/bee.py, AGENTS.md, outils/site_bee.py) | 0 |  |
| `docs/architecture.md` | `docs/architecture.md` | 27 (docs/decisions.md, taches/…) | 0 | keep |
| `docs/branches.md` | `docs/branches.md` | 10 (REGLES.md, README.md, taches/…) | 0 | keep |
| `docs/candidats.md` | `docs/candidates.md` | 3 (README.md, taches/…) | 0 |  |
| `docs/cap.md` | `docs/balance.md` | 14 (outils/bee.py, AGENTS.md, outils/test_bee.py) | 0 |  |
| `docs/capacites.md` | `docs/capabilities.md` | 4 (taches/…, debats/…) | 0 |  |
| `docs/contributions.md` | `docs/contributions.md` | 24 (AGENTS.md, REGLES.md, outils/bee.py) | 0 | keep |
| `docs/croissance.md` | `docs/growth.md` | 33 (outils/test_bee.py, outils/bee.py, AGENTS.md) | 0 |  |
| `docs/decisions.md` | `docs/decisions.md` | 63 (outils/test_bee.py, REGLES.md, outils/bee.py) | 0 | keep: DECISIONS constant; additions-only commits count as data (push-scope) |
| `docs/devolution.md` | `docs/devolution.md` | 14 (REGLES.md, taches/…, README.md) | 0 | keep (authority file) |
| `docs/evaluation.md` | `docs/evaluation.md` | 7 (AGENTS.md, MAINTENEURS.md, outils/bee.py) | 2 (libyamlBee:.github/workflows/bee-ci.yml, minizBee:.github/workflows/bee-ci.yml) | keep; forks cite it |
| `docs/garants.md` | `docs/guarantors.md` | 14 (outils/bee.py, gouvernance/garants.yaml, docs/croissance.md) | 0 | authority file; garants.yaml cites it |
| `docs/gardiens.md` | `docs/guardians.md` | 15 (REGLES.md, docs/decisions.md, README.md) | 0 |  |
| `docs/gouvernance.md` | `docs/governance.md` | 23 (AGENTS.md, taches/…) | 0 |  |
| `docs/juge-commun.md` | `docs/common-judge.md` | 27 (taches/…, outils/bee.py) | 2 (minizBee:bee/README.md, minizBee:bee/juge/projet.py) | forks cite it |
| `docs/mesures.md` | `docs/measurements.md` | 5 (taches/…, arbre/roles/mesurer/SENS.md, docs/gouvernance.md) | 0 |  |
| `docs/nouveau-projet.md` | `docs/new-project.md` | 7 (taches/…, REGLES.md, outils/bee.py) | 0 |  |
| `docs/organisation.md` | `docs/organization.md` | 11 (docs/decisions.md, gouvernance/consignes/abeille-du-conseil.md, gouvernance/consignes/agent-principal.md) | 0 | authority file |
| `docs/outillage.md` | `docs/tooling.md` | 15 (README.md, docs/architecture.md, taches/…) | 0 |  |
| `docs/perimetre.md` | `docs/scope.md` | 7 (README.md, taches/…, arbre/roles/garder/SENS.md) | 0 |  |
| `docs/questions-ouvertes.md` | `docs/open-questions.md` | 28 (outils/bee.py, outils/test_bee.py, outils/tests/registre/taches/ruche/ruche-0008.yaml) | 0 | default --source of debate import-questions |
| `docs/reputation.md` | `docs/reputation.md` | 16 (outils/bee.py, AGENTS.md, outils/test_bee.py) | 0 | keep |
| `docs/securite.md` | `docs/security.md` | 23 (outils/test_bee.py, AGENTS.md, docs/decisions.md) | 5 (libyamlBee:bee/fuzz/lancer.sh, minizBee:bee/fuzz/lancer.sh) | forks cite it in CI messages and README |
| `docs/taches.md` | `docs/tasks.md` | 7 (AGENTS.md, outils/bee.py, taches/…) | 0 |  |
| `docs/vision.md` | `docs/vision.md` | 7 (README.md, docs/decisions.md, taches/…) | 0 | keep |
| `.github/ISSUE_TEMPLATE/proposition-tache.md` | `.github/ISSUE_TEMPLATE/task-proposal.md` | 0 | 0 | label proposition-tache |
| `.github/pull_request_template.md` | `.github/pull_request_template.md` | 1 (taches/…) | 0 | keep; content lists PR title natures |
| `.claude/skills/bee-contributeur/` | `.claude/skills/bee-contributor/` | 11 (taches/…, UTILISATEURS.md, outils/tests/registre/taches/ruche/ruche-0010.yaml) | 0 | skill name as users invoke it; CLAUDE.md names it |
| `<fork>/manifestes/<task>.yaml` | `<fork>/manifests/<task>.yaml` | 0 | 0 | registry: verifier-fork, verdicts.yml, R1 exclusions; wave 2 with a dated dual-read |
| `<fork>/CONTRIBUTION.yaml` | `(dropped at the end of the window)` | 12 (outils/test_bee.py, outils/bee.py, .github/workflows/verdicts.yml) | 12 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | old manifest place, still accepted |
| `<fork>/bee/juge/projet.py` | `<fork>/bee/judge/project.py` | 20 (outils/juge/test_juge.py, outils/juge/juge.py, outils/tests/registre/taches/libyaml/libyaml-0014.yaml) | 9 (minizBee:bee/ci/test_verdict.py, minizBee:.github/workflows/bee-ci.yml) | plugin read by the judge from the fork BASE: judge track (dual path in judge-v4) |
| `<fork>/bee/bench/ab.py` | `<fork>/bee/bench/ab.py` | 34 (outils/bee.py, contributions/…) | 22 (minizBee:bee/README.md, minizBee:manifestes/miniz-0039.yaml) | keep |
| `<fork>/.github/workflows/bee-ci.yml` | `<fork>/.github/workflows/bee-ci.yml` | 40 (outils/test_bee.py, taches/…) | 17 (minizBee:bee/ci/test_verdict.py, minizBee:.github/workflows/bee-ci.yml) | keep: verdicts.yml reads runs of this file name |

Tree nodes (18 files `SENS.md`, ids = their folder under `arbre/`):

| French node file | English node file | Node id after the move |
|---|---|---|
| `arbre/SENS.md` | `tree/MEANING.md` | `root` |
| `arbre/projets/compression-sans-perte/SENS.md` | `tree/projects/lossless-compression/MEANING.md` | `projects/lossless-compression` |
| `arbre/projets/compression-sans-perte/miniz/SENS.md` | `tree/projects/lossless-compression/miniz/MEANING.md` | `projects/lossless-compression/miniz` |
| `arbre/projets/compression-sans-perte/miniz/api/SENS.md` | `tree/projects/lossless-compression/miniz/api/MEANING.md` | `projects/lossless-compression/miniz/api` |
| `arbre/projets/compression-sans-perte/miniz/bee/SENS.md` | `tree/projects/lossless-compression/miniz/bee/MEANING.md` | `projects/lossless-compression/miniz/bee` |
| `arbre/projets/compression-sans-perte/miniz/deflate/SENS.md` | `tree/projects/lossless-compression/miniz/deflate/MEANING.md` | `projects/lossless-compression/miniz/deflate` |
| `arbre/projets/compression-sans-perte/miniz/inflate/SENS.md` | `tree/projects/lossless-compression/miniz/inflate/MEANING.md` | `projects/lossless-compression/miniz/inflate` |
| `arbre/projets/parsing-serialisation/SENS.md` | `tree/projects/parsing-serialization/MEANING.md` | `projects/parsing-serialization` |
| `arbre/projets/parsing-serialisation/libyaml/SENS.md` | `tree/projects/parsing-serialization/libyaml/MEANING.md` | `projects/parsing-serialization/libyaml` |
| `arbre/projets/ruche/SENS.md` | `tree/projects/ruche/MEANING.md` | `projects/ruche` |
| `arbre/projets/ruche/ruche/SENS.md` | `tree/projects/ruche/ruche/MEANING.md` | `projects/ruche/ruche` |
| `arbre/roles/debattre/SENS.md` | `tree/roles/debate/MEANING.md` | `roles/debate` |
| `arbre/roles/garder/SENS.md` | `tree/roles/guard/MEANING.md` | `roles/guard` |
| `arbre/roles/inviter/SENS.md` | `tree/roles/invite/MEANING.md` | `roles/invite` |
| `arbre/roles/mesurer/SENS.md` | `tree/roles/measure/MEANING.md` | `roles/measure` |
| `arbre/roles/optimiser/SENS.md` | `tree/roles/optimize/MEANING.md` | `roles/optimize` |
| `arbre/roles/proposer/SENS.md` | `tree/roles/propose/MEANING.md` | `roles/propose` |
| `arbre/roles/relire/SENS.md` | `tree/roles/review/MEANING.md` | `roles/review` |

Docs list kept as is: every `docs/*.md` row above. Data files keep their names (task, contribution, debate, proposal ids; logins); only their folders move.

## 3. YAML keys and JSON-schema properties

Families: `tache` (taches/), `enregistrement` (contributions/), `debat`, `proposition`, `projet`, `membre`, `vote`, `mesure`, `invitation`, `signalement`, `incidents`, `retraits`, `ne-plus-contacter` are schema names; `contribution` is the fork manifest's schema. Data counts are files of the registry (and of the forks' manifests) that carry the key.

| French key | English key | Schemas | Data files carrying it | Code files (`"key"` literal) | Forks | Note |
|---|---|---|---|---|---|---|
| `A` | `A` | enregistrement | contributions 70, fixture:contributions 7 | 6 (outils/bee.py, outils/juge/juge.py, outils/juge/test_juge.py) | 14 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `accord_conseil` | `council_approval` | invitation | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | invitation gesture |
| `accord_gardien` | `guardian_approval` | invitation | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | invitation gesture |
| `account` | `account` |  | gouvernance/comptes-agents.yaml 1 | 2 (outils/bee.py, outils/test_bee.py) | 0 | already English |
| `accounts` | `accounts` |  | gouvernance/comptes-agents.yaml 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 | already English |
| `acts_for` | `acts_for` |  | gouvernance/comptes-agents.yaml 1 | 2 (outils/bee.py, outils/test_bee.py) | 0 | already English |
| `agent` | `agent` | contribution | minizBee:manifest 12, libyamlBee:manifest 2 | 2 (outils/test_bee.py, outils/bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) |  |
| `amorcage` | `bootstrap` | enregistrement | contributions 3, bee.yaml 1, fixture:contributions 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 5 (minizBee:bee/ci/test_verdict.py, libyamlBee:bee/ci/verdict.py) | bee.yaml and verdict |
| `anciens_logins` | `former_logins` | membre | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `apres` | `after` | contribution | minizBee:manifest 5 | 2 (outils/test_bee.py, outils/bee.py) | 5 (minizBee:manifestes/miniz-0003.yaml, minizBee:manifestes/miniz-0012.yaml) | manifest measurements |
| `arbre` | `tree` | enregistrement | contributions 8 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 | verdict: git tree sha |
| `architecture` | `architecture` | mesure | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/juge/juge.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `arguments` | `arguments` | debat | debats 23 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `attente_verdict` | `awaiting_verdict` | enregistrement | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | values are codes (ATTENTE_VERDICT) |
| `au_dela_du_bruit` | `beyond_noise` | enregistrement, mesure | contributions 21, fixture:contributions 3 | 6 (outils/test_bee.py, outils/bee.py, outils/juge/juge.py) | 15 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) | also in fork verdict.json (wave 2) |
| `auteur` | `author` | enregistrement, proposition | contributions 77, fixture:contributions 7, propositions 3 | 7 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 | CHAMPS_PSEUDO; CREES_PAR (proposals) |
| `autres_comptes` | `other_accounts` | membre | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | LIENS (ruche-0051) |
| `autres_identites` | `other_identities` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | CHAMPS_DE_LA_PERSONNE (removal on request) |
| `avant` | `before` | contribution | minizBee:manifest 5 | 2 (outils/test_bee.py, outils/bee.py) | 7 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | manifest measurements |
| `avis` | `opinion` | enregistrement | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `B` | `B` | enregistrement | contributions 70, fixture:contributions 7 | 6 (outils/juge/test_juge.py, outils/juge/juge.py, outils/test_bee.py) | 14 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `banc_ab` | `ab_bench` |  | projets 2 | 0 | 1 (libyamlBee:bee/ci/verdict.py) | project command |
| `base` | `base` | enregistrement, mesure | contributions 1 | 8 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 13 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| `budget_lignes` | `line_budget` |  | 0 | 1 (outils/bee.py) | 0 | node header |
| `canal` | `channel` | invitation, retraits | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `candidat` | `candidate` | mesure | 0 | 2 (outils/test_bee.py, outils/bee.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `categorie` | `category` | projet, tache | taches 198, fixture:taches 16, projets 7, modeles/tache.yaml 1 | 4 (outils/bee.py, outils/repetition/load_test.py, outils/site_bee.py) | 0 | council-only task key |
| `categories_preferees` | `preferred_categories` | membre | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `caviarde_pour` | `redacted_for` | debat | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `changement` | `change` | contribution | minizBee:manifest 12, libyamlBee:manifest 2 | 0 | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) | manifest |
| `chemins_hors_decompte` | `paths_not_counted` | projet | projets 7 | 1 (outils/bee.py) | 0 | R1; values are fork paths (unchanged) |
| `chemins_juges` | `judge_paths` | projet | projets 7 | 3 (outils/bee.py, outils/site_bee.py, outils/test_bee.py) | 0 | commandment 3; ruche.yaml lists outils/** -> tools/** |
| `ci` | `ci` | enregistrement | contributions 21, fixture:contributions 3 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/ci_simulee.py) | 5 (minizBee:bee/ci/test_verdict.py, minizBee:.github/workflows/bee-ci.yml) |  |
| `client` | `client` | contribution | minizBee:manifest 12, libyamlBee:manifest 2 | 0 | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) |  |
| `clos_le` | `closed_at` | debat, incidents | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | debate, incident |
| `clos_par` | `closed_by` | debat | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | CHAMPS_PSEUDO |
| `coeurs` | `cores` | mesure | 0 | 3 (outils/bee.py, outils/juge/stats.py, outils/test_bee.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `commande` | `command` | contribution | minizBee:manifest 5 | 1 (outils/bee.py) | 5 (minizBee:manifestes/miniz-0003.yaml, minizBee:manifestes/miniz-0012.yaml) | manifest |
| `commandes` | `commands` | projet | projets 3 | 1 (outils/bee.py) | 0 | project |
| `commun` | `common` | enregistrement | contributions 8 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/juge.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) | verdict.judge.common holds the tag name juge-vN |
| `compilateur` | `compiler` | mesure | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/juge/stats.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `compte_cree_le` | `account_created_on` | membre | 0 | 3 (outils/test_bee.py, outils/repetition/load_test.py, outils/bee.py) | 0 | date |
| `compte_de` | `account_of` | membre | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | LIENS |
| `comptes` | `accounts` | signalement | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | report; same word as comptes-agents.yaml's accounts |
| `config` | `config` | mesure | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `confirme_par` | `confirmed_by` | enregistrement | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | CHAMPS_PSEUDO, CLES_CONFIRMATION |
| `conflits` | `conflicts` |  | gouvernance/garants.yaml 1 | 0 | 0 | guarantors |
| `consignes` | `brief` |  | gouvernance/garants.yaml 1 | 0 | 0 | guarantors: path into governance/briefs/ |
| `constructions_suspectes` | `suspicious_constructs` | enregistrement | contributions 9 | 7 (outils/juge/test_juge.py, outils/test_bee.py, outils/bee.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:bee/juge/test_juge.py) |  |
| `conteste` | `contested_by` | debat | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `contexte` | `context` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | CHAMPS_LONGS |
| `contribution` | `contribution` | mesure, tache | taches 77, fixture:taches 7, fixture:ruche-0028.yaml 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `corpus` | `corpus` |  | projets 2 | 1 (outils/juge/juge.py) | 4 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) | project command |
| `cree_le` | `created_on` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | date; CREES_PAR |
| `cree_par` | `created_by` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 4 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 | CHAMPS_PSEUDO; R8 bootstrap reads « conseil » in it |
| `critere_acceptation` | `acceptance_criteria` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 4 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 |  |
| `debat` | `debate` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `decidee_le` | `decided_at` | enregistrement | contributions 71, fixture:contributions 7 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `decision` | `decision` | signalement | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| `declare` | `declared` | enregistrement | contributions 7 | 2 (outils/test_bee.py, outils/bee.py) | 0 | contribution: copy of the manifest at the verdict |
| `declared_on` | `declared_on` |  | gouvernance/comptes-agents.yaml 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 | already English |
| `defaut_confirme` | `confirmed_defect` | enregistrement | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | CLES_CONFIRMATION |
| `defaut_signale` | `reported_defect` | enregistrement | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `degradations` | `degradations` | enregistrement | contributions 17, fixture:contributions 2 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/ci_simulee.py) | 5 (minizBee:bee/ci/test_verdict.py, libyamlBee:bee/ci/verdict.py) |  |
| `demande` | `request` | invitation, retraits | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | invitation (what is asked) and removals |
| `depend_de` | `depends_on` | tache | taches 163, fixture:taches 13, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 3 (outils/bee.py, outils/site_bee.py, outils/test_bee.py) | 0 |  |
| `depot_origine` | `upstream_repo` | projet | projets 7 | 1 (outils/bee.py) | 0 |  |
| `depuis` | `since` | tache | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | reservation, parallel registrations |
| `description` | `description` |  | projets 6 | 0 | 0 |  |
| `detail` | `detail` | enregistrement | 0 | 6 (outils/juge/test_juge.py, outils/juge/analyse.py, outils/test_bee.py) | 3 (minizBee:bee/ci/verdict.py, minizBee:bee/ci/test_verdict.py) |  |
| `doublon_de` | `duplicate_of` | debat | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `doublon_par` | `duplicate_marked_by` | debat | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `doutes` | `doubts` | contribution, enregistrement | minizBee:manifest 12, contributions 7, libyamlBee:manifest 2 | 2 (outils/test_bee.py, outils/bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) | manifest (forks) and declared/ |
| `ecart_declare` | `declared_gap` | enregistrement | contributions 13, fixture:contributions 2 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| `ecartee` | `set_aside` | invitation | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 | invitation gesture key; same token as the status value |
| `empreintes` | `fingerprints` | ne-plus-contacter, retraits | 0 | 2 (outils/test_bee.py, outils/bee.py) | 1 (minizBee:bee/tests/differentiel.c) | do-not-contact, removals |
| `engage_depuis` | `engaged_since` | enregistrement | contributions 64, fixture:contributions 3 | 3 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 | CLES_NAISSANCE |
| `engagement` | `engagement` |  | gouvernance/garants.yaml 1 | 1 (outils/bee.py) | 0 | guarantors (already English) |
| `entretenu_par` | `maintained_by` |  | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 | node header |
| `envoi` | `sent` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | invitation gesture |
| `etape_en_echec` | `failed_step` | enregistrement | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/repetition/ci_simulee.py) | 5 (minizBee:bee/ci/test_verdict.py, libyamlBee:bee/ci/verdict.py) | also fork verdict.json (wave 2) |
| `execution` | `run` | enregistrement | contributions 20, fixture:contributions 3 | 6 (outils/juge/test_juge.py, outils/juge/juge.py, outils/test_bee.py) | 0 | CI run URL |
| `fait` | `fact` | invitation | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 | invitation why/fact |
| `fichiers` | `files` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 5 (outils/test_bee.py, outils/bee.py, outils/repetition/ci_simulee.py) | 0 | task; closed tasks keep their path values as written |
| `fichiers_controles` | `checked_files` | enregistrement | contributions 17, fixture:contributions 2 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `fork` | `fork` | projet | projets 7 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/analyse.py) | 0 |  |
| `fusion_sha` | `merge_sha` | enregistrement | contributions 68, fixture:contributions 6 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `fuzz` | `fuzz` |  | projets 2 | 0 | 0 | project command |
| `gain` | `gain` | enregistrement, mesure | contributions 98, fixture:contributions 10 | 6 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 14 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| `garant` | `guarantor` |  | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 | guardians list entry; CHAMPS_PSEUDO |
| `github_id` | `github_id` | membre | gouvernance/comptes-agents.yaml 1, gouvernance/garants.yaml 1, gouvernance/conseil.yaml 1 | 3 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 |  |
| `homonyme` | `namesake` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `hors_perimetre` | `out_of_scope` | projet, tache | taches 198, fixture:taches 16, projets 7, modeles/tache.yaml 1 | 2 (outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `id` | `id` | debat, enregistrement, incidents, invitation, projet, proposition, tache | taches 198, contributions 77, debats 24, fixture:taches 16 | 9 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 6 (minizBee:.github/workflows/bee-ci.yml, minizBee:.github/workflows/release.yml) |  |
| `identifiant` | `identifier` | invitation | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | invitation person |
| `identite_publique` | `public_identity` |  | gouvernance/garants.yaml 1 | 0 | 0 | guarantors |
| `incidents` | `incidents` | incidents | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `inscrit_le` | `registered_on` | membre | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 1 (minizBee:bee/corpus/generer.py) | date |
| `instructions` | `instructions` | enregistrement, projet | contributions 18, projets 2, fixture:contributions 2 | 8 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 11 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| `invitation` | `invitation` | debat | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `issue` | `outcome` | debat, incidents, signalement | 0 | 6 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 0 | debate, report decision, incident; NOT the value « issue » (a GitHub issue channel) |
| `jamais_integree` | `never_integrated` | enregistrement | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `juge` | `judge` | enregistrement | contributions 9 | 8 (outils/juge/test_juge.py, outils/test_bee.py, outils/bee.py) | 4 (minizBee:bee/ci/test_verdict.py, minizBee:bee/juge/test_juge.py) | verdict section; fork verdict.json (wave 2) |
| `juges_modifies` | `modified_judges` | enregistrement | contributions 10, fixture:contributions 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `le` | `at` | debat, enregistrement, invitation, mesure, retraits, signalement, tache, vote | taches 48, fixture:taches 4, fixture:ruche-0028.yaml 1, debats 1 | 5 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | every note, argument, review, vote, measurement, gesture |
| `levees` | `lifts` | enregistrement | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | council lifts of a reviewer's reviews (ruche-0012) |
| `licence` | `license` | projet | projets 7 | 0 | 0 |  |
| `lignes_modifiees` | `changed_lines` | enregistrement | contributions 21, fixture:contributions 3 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/ci_simulee.py) | 4 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | fork verdict.json (wave 2) |
| `machine` | `machine` | contribution | minizBee:manifest 5 | 4 (outils/test_bee.py, outils/bee.py, outils/juge/juge.py) | 17 (libyamlBee:.github/workflows/bee-ci.yml, libyamlBee:bee/ci/verdict.py) |  |
| `membres` | `members` |  | gouvernance/garants.yaml 1, gouvernance/conseil.yaml 1, gouvernance/gardiens.yaml 1 | 6 (outils/bee.py, outils/test_bee.py, outils/repetition/test_load_test.py) | 0 | council.yaml, guardians.yaml, guarantors.yaml lists |
| `message` | `message` | invitation | 0 | 3 (outils/test_bee.py, outils/inventaire_marqueurs.py, outils/bee.py) | 0 |  |
| `mesures` | `measurements` | contribution | minizBee:manifest 5 | 3 (outils/test_bee.py, outils/bee.py, outils/juge/juge.py) | 18 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | manifest; fork verdict.json (wave 2) |
| `metrique` | `metric` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 5 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 7 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) | task; fork tache.py reads it from main |
| `metriques` | `metrics` | mesure, projet | projets 7 | 8 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 13 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) | project, measurement; libyamlBee reads projets/libyaml.yaml metriques |
| `mis_a_jour` | `updated_on` |  | 0 | 1 (outils/bee.py) | 0 | node header (date) |
| `modele` | `model` | contribution, enregistrement | minizBee:manifest 12, contributions 7, libyamlBee:manifest 2 | 2 (outils/test_bee.py, outils/bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) |  |
| `motif` | `reason` | enregistrement, invitation, mesure, proposition, signalement, vote | propositions 3 | 4 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 0 |  |
| `motif_decision` | `decision_reason` | enregistrement | contributions 71, fixture:contributions 7 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `noeud` | `node` | tache | taches 163, fixture:taches 9, fixture:ruche-0028.yaml 1, fixture:ruche-0100.yaml 1 | 2 (outils/bee.py, outils/test_bee.py) | 0 | task; values are tree paths (projets/... -> projects/...) |
| `nom` | `name` | projet | projets 7, bee.yaml 1, categories.yaml 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 1 (minizBee:bee/corpus/generer.py) | bee.yaml, project, category |
| `non_contact` | `no_contact` | retraits | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `non_teste` | `untested` | contribution, enregistrement | minizBee:manifest 12, contributions 7, libyamlBee:manifest 2 | 2 (outils/test_bee.py, outils/bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) | manifest (forks) |
| `notes` | `notes` | tache | taches 48, fixture:taches 4, bee.yaml 1, fixture:ruche-0028.yaml 1 | 4 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `organisation` | `organization` |  | bee.yaml 1 | 2 (outils/bee.py, outils/site_bee.py) | 0 | bee.yaml |
| `outil` | `tool` | mesure | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `ouvert_le` | `opened_at` | debat, incidents | debats 23 | 2 (outils/bee.py, outils/test_bee.py) | 0 | debate, incident |
| `ouvert_par` | `opened_by` | debat | debats 23 | 2 (outils/bee.py, outils/test_bee.py) | 0 | CHAMPS_PSEUDO |
| `ouverte_le` | `opened_at` | proposition | propositions 3 | 2 (outils/test_bee.py, outils/bee.py) | 0 | proposal (same English as ouvert_le; one family each) |
| `paires` | `pairs` | mesure | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/juge/stats.py) | 10 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| `palier_mainteneur` | `maintainer_tier` | projet | projets 7 | 0 | 0 |  |
| `par` | `by` | debat, enregistrement, invitation, retraits, signalement, tache | taches 48, fixture:taches 4, fixture:ruche-0028.yaml 1, debats 1 | 5 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 | notes, arguments, gestures; CHAMPS_PSEUDO |
| `paralleles` | `parallel` | tache | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | CLES_LIBRE_SERVICE_TACHE |
| `parent` | `parent` |  | 0 | 3 (outils/bee.py, outils/site_bee.py, outils/test_bee.py) | 0 | node header |
| `passages` | `passages` | retraits | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `perimetre` | `scope` | projet | projets 7 | 0 | 0 | project |
| `personne` | `person` | invitation | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | invitation; CHAMPS_DE_LA_PERSONNE |
| `phase` | `phase` |  | bee.yaml 1 | 1 (outils/site_bee.py) | 0 |  |
| `phase_ouverture` | `opening_phase` | projet | projets 7 | 1 (outils/site_bee.py) | 0 |  |
| `portee` | `reach` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | task weight 0.1-1 (not the workflows' « portee » = scope output) |
| `position` | `position` | debat | debats 1 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 1 (minizBee:bee/corpus/generer.py) |  |
| `poste` | `area` | tache | taches 143, fixture:taches 5, fixture:ruche-0028.yaml 1, fixture:ruche-0100.yaml 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 | R11 |
| `pourquoi` | `why` | invitation | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | invitation; list of {fact, source} |
| `pr` | `pr` | enregistrement | contributions 77, fixture:contributions 7 | 7 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:.github/workflows/bee-ci.yml) |  |
| `preuve` | `proof` |  | categories.yaml 1 | 0 | 0 | category |
| `processeur` | `processor` | mesure | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/juge/stats.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `profil` | `profile` |  | gouvernance/garants.yaml 1 | 2 (outils/test_bee.py, outils/bee.py) | 3 (minizBee:bee/bench/profil.py, minizBee:bee/bench/test_profil.py) | guarantors |
| `projet` | `project` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 6 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| `propose_le` | `proposed_at` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | CREES_PAR (invitations) |
| `propose_par` | `proposed_by` | invitation | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | CHAMPS_PSEUDO |
| `pseudo` | `login` | debat, invitation, membre | gouvernance/garants.yaml 1, gouvernance/conseil.yaml 1 | 6 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 | member, council, guardians, guarantors |
| `purpose` | `purpose` |  | gouvernance/comptes-agents.yaml 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 | already English |
| `question` | `question` | debat | debats 23 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `question_caviardee_pour` | `question_redacted_for` | debat | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `raison` | `cause` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | invitation withdrawal (kept apart from motif -> reason) |
| `rapporteur` | `rapporteur` | debat | debats 2 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | English word; not « reporter » (a report's author) |
| `reference` | `reference` | debat, projet, retraits | projets 7 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| `regle` | `rule` | proposition | propositions 3 | 2 (outils/test_bee.py, outils/bee.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| `relance` | `reminder` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | invitation gesture |
| `relecteur` | `reviewer` | enregistrement | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 |  |
| `relectures` | `reviews` | enregistrement | contributions 77, fixture:contributions 7 | 5 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 | CLES_NAISSANCE |
| `renomme_le` | `renamed_on` | membre | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | date |
| `renouvellement` | `renewal` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | invitation gesture |
| `repetitions` | `repetitions` | contribution, mesure | minizBee:manifest 5 | 4 (outils/bee.py, outils/test_bee.py, outils/juge/juge.py) | 15 (libyamlBee:bee/ci/verdict.py, minizBee:bee/ci/verdict.py) |  |
| `repond_a` | `replies_to` | debat | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `reponse` | `answer` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | invitation gesture |
| `reservation` | `reservation` | tache | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `resultat` | `result` | proposition | propositions 3 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `resume` | `summary` | contribution, enregistrement | contributions 77, minizBee:manifest 12, fixture:contributions 7, libyamlBee:manifest 2 | 3 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) | CLES_NAISSANCE |
| `resume_sha` | `summary_sha` | enregistrement | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `retenue` | `kept` | enregistrement | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 | the contribution R3 kept |
| `retrait` | `withdrawal` | invitation | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | invitation gesture |
| `retraits` | `removals` | retraits | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | removals file |
| `revoque_le` | `revoked_on` |  | 0 | 1 (outils/bee.py) | 0 | guarantors |
| `robots` | `robots` |  | bee.yaml 1 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `role` | `role` |  | gouvernance/garants.yaml 1, gouvernance/conseil.yaml 1 | 3 (outils/bee.py, outils/site_bee.py, outils/test_bee.py) | 0 |  |
| `sens` | `direction` | projet | projets 6 | 2 (outils/juge/juge.py, outils/bee.py) | 8 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) | metric: higher \| lower |
| `sha` | `sha` | enregistrement | contributions 21, fixture:contributions 3 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `signe_le` | `signed_on` |  | gouvernance/garants.yaml 1 | 0 | 0 | guarantors |
| `sortie_compressee` | `compressed_output` | tache | taches 20, modeles/tache.yaml 1, fixture:taches 1 | 5 (outils/bee.py, outils/juge/jouet/bee/juge/projet.py, outils/repetition/load_test.py) | 6 (minizBee:bee/juge/test_juge.py, libyamlBee:bee/ci/tache.py) | task; fork tache.py reads it from main |
| `sorties_comparees` | `outputs_compared` | enregistrement | contributions 9 | 7 (outils/juge/test_juge.py, outils/test_bee.py, outils/bee.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| `soumise_le` | `submitted_at` | enregistrement | contributions 77, fixture:contributions 7 | 4 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 | R3 window, race order |
| `soumise_par` | `submitted_by` | mesure | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | CHAMPS_PSEUDO |
| `source` | `source` | invitation | 0 | 6 (outils/test_bee.py, outils/juge/test_juge.py, outils/bee.py) | 0 |  |
| `sources` | `sources` | debat | debats 1 | 4 (outils/bee.py, outils/test_bee.py, outils/juge/test_juge.py) | 0 |  |
| `statut` | `status` | debat, enregistrement, invitation, projet, proposition, tache | taches 198, contributions 77, debats 23, fixture:taches 16 | 7 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 | every family |
| `sujet` | `subject` | vote | 0 | 5 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `synthese` | `synthesis` | debat | debats 23 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| `synthese_caviardee_pour` | `synthesis_redacted_for` | debat | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `synthese_couvre` | `synthesis_covers` | debat | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| `synthese_le` | `synthesis_at` | debat | debats 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `synthese_par` | `synthesis_by` | debat | debats 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 | CHAMPS_PSEUDO |
| `systeme` | `system` | mesure | 0 | 3 (outils/bee.py, outils/juge/stats.py, outils/test_bee.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) |  |
| `tache` | `task` | contribution, enregistrement | contributions 77, minizBee:manifest 12, fixture:contributions 7, libyamlBee:manifest 2 | 5 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 20 (libyamlBee:.github/workflows/bee-ci.yml, libyamlBee:CONTRIBUTION.yaml) | contribution, manifest (forks) |
| `taille` | `size` | tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 3 (outils/bee.py, outils/repetition/load_test.py, outils/test_bee.py) | 0 |  |
| `taille_reelle` | `actual_size` | contribution | minizBee:manifest 12, libyamlBee:manifest 2 | 1 (outils/bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) | manifest (forks) |
| `teste` | `tested` | contribution, enregistrement | minizBee:manifest 12, contributions 7, libyamlBee:manifest 2 | 2 (outils/test_bee.py, outils/bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) | manifest (forks) |
| `tests` | `tests` |  | projets 3 | 2 (outils/test_bee.py, outils/repetition/ci_simulee.py) | 0 | project command |
| `texte` | `text` | debat, invitation, tache | taches 48, fixture:taches 4, fixture:ruche-0028.yaml 1, debats 1 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `texte_propose` | `proposed_text` | proposition | propositions 3 | 2 (outils/test_bee.py, outils/bee.py) | 0 | TEXTES_PROPRES |
| `titre` | `title` | incidents, tache | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 4 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| `type` | `type` |  | taches 198, fixture:taches 16, modeles/tache.yaml 1, fixture:ruche-0028.yaml 1 | 8 (outils/juge/test_juge.py, outils/bee.py, outils/test_bee.py) | 7 (minizBee:bee/ci/verdict.py, libyamlBee:bee/ci/tache.py) |  |
| `unite` | `unit` | projet | projets 6 | 1 (outils/juge/juge.py) | 8 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| `utilisateur` | `user` | contribution, tache | minizBee:manifest 12, libyamlBee:manifest 2 | 4 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 14 (libyamlBee:CONTRIBUTION.yaml, libyamlBee:manifestes/libyaml-0003.yaml) |  |
| `valeur` | `value` | invitation, vote | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| `valider` | `validate` |  | projets 1 | 4 (outils/test_bee.py, outils/repetition/test_load_test.py, outils/bee.py) | 0 | project command (ruche) |
| `verdict` | `verdict` | enregistrement | contributions 20, fixture:contributions 3 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/ci_simulee.py) | 3 (minizBee:bee/ci/test_verdict.py, libyamlBee:.github/workflows/bee-ci.yml) |  |
| `verdict_exige_base_juge` | `verdict_requires_judge_base` | projet | projets 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `verdicts` | `verdicts` | enregistrement | contributions 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| `verdicts_oublies` | `dropped_verdicts` | enregistrement | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | verdicts past the 20 kept |
| `version` | `version` | enregistrement | contributions 9 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/juge.py) | 2 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| `victoires_b` | `b_wins` | mesure | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | also read as victoires_B from ab.py reports (wave 2) |
| `votant` | `voter` | vote | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 | CHAMPS_PSEUDO |

212 key names (each listed once; a key keeps one English name in every family it appears in).

### 3.1 bee.yaml (council-only)

| French key | English key | Code files | Note |
|---|---|---|---|
| `nom` | `name` | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) |  |
| `organisation` | `organization` | 2 (outils/bee.py, outils/site_bee.py) | read to build fork and upstream URLs |
| `phase` | `phase` | 1 (outils/site_bee.py) |  |
| `amorcage` | `bootstrap` | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) |  |
| `reservation_max_heures` | `reservation_max_hours` | 1 (outils/bee.py) | R7 |
| `reprise_apres_liberation_heures` | `retake_after_release_hours` | 1 (outils/bee.py) | R7 |
| `reservations_max_par_utilisateur` | `reservations_max_per_user` | 2 (outils/test_bee.py, outils/bee.py) | R8 |
| `r8_amorcage` | `r8_bootstrap` | 2 (outils/bee.py, outils/test_bee.py) | R8 bootstrap |
| `r8_amorcage/max` | `r8_bootstrap/max` | 4 (outils/test_bee.py, outils/juge/juge.py, outils/juge/stats.py) |  |
| `r8_amorcage/jusqu_au` | `r8_bootstrap/until` | 2 (outils/test_bee.py, outils/bee.py) | only the human council moves it |
| `gain_minimal` | `min_gain` | 1 (outils/bee.py) | R4 |
| `degradation_max_autres` | `max_other_degradation` | 1 (outils/bee.py) | R5 |
| `relectures_requises` | `reviews_required` | 1 (outils/bee.py) | R3 |
| `vote_net_min` | `min_net_vote` | 1 (outils/bee.py) | R3 |
| `fenetre_acceptation_heures` | `acceptance_window_hours` | 1 (outils/bee.py) | R3 |
| `relecture_gardien_requise` | `guardian_review_required` | 1 (outils/bee.py) | R3 gate; values true \| if_judge_incomplete \| false |
| `juge_commun_min` | `common_judge_min` | 1 (outils/bee.py) | R3; compared with the N of juge-vN / judge-vN |
| `duree_vote_jours` | `vote_duration_days` | 1 (outils/bee.py) | R10 |
| `quorum_votants` | `voter_quorum` | 1 (outils/bee.py) | R10 |
| `majorite_requise` | `required_majority` | 1 (outils/bee.py) | R10 |
| `anciennete_compte_min_jours` | `min_account_age_days` | 1 (outils/bee.py) |  |
| `ecart_declare_max` | `max_declared_gap` | 1 (outils/bee.py) |  |
| `cap` | `balance` | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | R11 |
| `cap/fenetre_jours` | `balance/window_days` | 1 (outils/bee.py) |  |
| `cap/poids_max_par_utilisateur_et_jour` | `balance/max_weight_per_user_per_day` | 1 (outils/bee.py) |  |
| `cap/postes` | `balance/areas` | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | children are area values: governance, projects, coordination |
| `agora` | `agora` | 2 (outils/bee.py, outils/site_bee.py) |  |
| `agora/texte_max` | `agora/text_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `agora/synthese_max` | `agora/synthesis_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `agora/question_max` | `agora/question_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `agora/sources_par_argument_max` | `agora/sources_per_argument_max` | 1 (outils/bee.py) |  |
| `agora/source_max` | `agora/source_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `agora/arguments_max_par_24h` | `agora/arguments_max_per_24h` | 1 (outils/bee.py) |  |
| `agora/arguments_max_par_24h_tous_debats` | `agora/arguments_max_per_24h_all_debates` | 1 (outils/bee.py) |  |
| `agora/arguments_max_par_pr` | `agora/arguments_max_per_pr` | 1 (outils/bee.py) |  |
| `agora/ouvertures_max_par_24h` | `agora/openings_max_per_24h` | 1 (outils/bee.py) |  |
| `agora/silence_avant_cloture_heures` | `agora/silence_before_close_hours` | 1 (outils/bee.py) |  |
| `agora/releve_rapporteur_heures` | `agora/rapporteur_relief_hours` | 1 (outils/bee.py) |  |
| `notes/texte_max` | `notes/text_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `notes/max_par_pr` | `notes/max_per_pr` | 1 (outils/bee.py) |  |
| `notes/max_par_24h` | `notes/max_per_24h` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations` | `creations` | 2 (outils/bee.py, outils/test_bee.py) | keys built as f"{folder}_max_par_pr": the folder AND the suffix change (hand-made) |
| `creations/taches_max_par_pr` | `creations/tasks_max_per_pr` | 1 (outils/bee.py) |  |
| `creations/taches_max_par_24h` | `creations/tasks_max_per_24h` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/propositions_max_par_pr` | `creations/proposals_max_per_pr` | 1 (outils/bee.py) |  |
| `creations/propositions_max_par_24h` | `creations/proposals_max_per_24h` | 1 (outils/bee.py) |  |
| `creations/invitations_max_par_pr` | `creations/invitations_max_per_pr` | 1 (outils/bee.py) |  |
| `creations/invitations_max_par_24h` | `creations/invitations_max_per_24h` | 1 (outils/bee.py) |  |
| `creations/signalements_max_par_pr` | `creations/reports_max_per_pr` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/signalements_max_par_24h` | `creations/reports_max_per_24h` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/signalements_ouverts_max` | `creations/reports_open_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/signalements_nommant_max` | `creations/reports_naming_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/signalements_au_plafond_par_24h` | `creations/reports_at_cap_per_24h` | 1 (outils/bee.py) | default only (CREATIONS_DEFAUT) |
| `creations/contexte_max` | `creations/context_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/elements_max` | `creations/items_max` | 1 (outils/bee.py) |  |
| `creations/element_max` | `creations/item_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `creations/fichiers_max` | `creations/files_max` | 1 (outils/bee.py) |  |
| `creations/chemin_max` | `creations/path_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `croissance` | `growth` | 1 (outils/bee.py) | R13 |
| `croissance/invitations_par_semaine` | `growth/invitations_per_week` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `croissance/relances_max` | `growth/reminders_max` | 1 (outils/bee.py) |  |
| `croissance/delai_relance_jours` | `growth/reminder_delay_days` | 1 (outils/bee.py) |  |
| `croissance/debat_min_heures` | `growth/debate_min_hours` | 1 (outils/bee.py) |  |
| `croissance/membres_actifs_par_gardien_max` | `growth/active_members_per_guardian_max` | 1 (outils/bee.py) | brake |
| `croissance/message_max` | `growth/message_max` | 2 (outils/bee.py, outils/test_bee.py) |  |
| `croissance/encadrement_par_semaine_sous_frein` | `growth/oversight_per_week_under_brake` | 1 (outils/bee.py) |  |
| `croissance/expiration_jours` | `growth/expiry_days` | 1 (outils/bee.py) |  |
| `croissance/membres_actifs_jours` | `growth/active_member_days` | 1 (outils/bee.py) |  |
| `croissance/branche_dormante_jours` | `growth/dormant_branch_days` | 1 (outils/bee.py) |  |
| `pseudos_reserves` | `reserved_logins` | 2 (outils/test_bee.py, outils/bee.py) | keep every French name in the list as well (a login « conseil » must stay unavailable) |
| `robots` | `robots` | 2 (outils/bee.py, outils/test_bee.py) |  |

71 keys. bee valider must keep refusing an unknown or misspelled key in bee.yaml once renamed (today a malformed value falls back to its default: a key left in French would silently fall back too, which is why the switch adds a check that every key bee.yaml carries is one the tool reads).

### 3.2 Keys at the boundary (files the registry reads or writes but does not hold)

| Document | French | English | Note |
|---|---|---|---|
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `ci` | `ci` | values verte\|rouge -> green\|red; bee already normalises green/success on read |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `etape_en_echec` | `failed_step` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `gain` | `gain` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `metrique` | `metric` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `au_dela_du_bruit` | `beyond_noise` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `mesures` | `measurements` | {A, B}: metric ids (wave 2) |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `instructions` | `instructions` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `degradations` | `degradations` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `lignes_modifiees` | `changed_lines` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `amorcage` | `bootstrap` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `base_juge` | `judge_base` | {base_juge, regle, depart} -> {judge_base, rule, start} |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `base_juge/regle` | `judge_base/rule` | values point_de_depart, introduction, refus_* -> start_point, introduction, refused_* |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `base_juge/depart` | `judge_base/start` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `juge` | `judge` | {version, commun, projet, greffon, graine, sorties_comparees, constructions_suspectes, source} |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `juge/commun` | `judge/common` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `juge/projet` | `judge/project` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `juge/greffon` | `judge/plugin` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `juge/graine` | `judge/seed` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `etapes` | `steps` |  |
| fork verdict.json (bee/ci/verdict.py, fork code at the PR's base) | `details` | `details` |  |
| juge.json (common judge report, produced at the PINNED judge commit) | `juge/verification/sorties_comparees` | `judge/verification/outputs_compared` | rapport.py reads it |
| juge.json (common judge report, produced at the PINNED judge commit) | `juge/code, juge/issue` | `judge/code, judge/outcome` |  |
| juge.json (common judge report, produced at the PINNED judge commit) | `juge/origine_des_graines` | `judge/seed_origin` | values tiree -> drawn |
| juge.json (common judge report, produced at the PINNED judge commit) | `metriques, mesures, methode, repetitions, chauffe, ordre` | `metrics, measurements, method, repetitions, warmup, order` |  |
| ab.py report (enregistrer-mesure --ab) | `config, metriques, base, candidat, repetitions` | `config, metrics, base, candidate, repetitions` |  |
| ab.py report (enregistrer-mesure --ab) | `victoires_B / victoires_b, paires, paires_utiles, test_du_signe` | `b_wins, pairs, useful_pairs, sign_test` |  |
| bee en-attente --pr-states (JSON read by integration-auto.yml and verdicts.yml) | `id, pr` | `id, pr` |  |
| bee en-attente --pr-states (JSON read by integration-auto.yml and verdicts.yml) | `sha_verdict` | `verdict_sha` | renamed with the workflows' one-liners, same PR |
| bee en-attente --pr-states (JSON read by integration-auto.yml and verdicts.yml) | `ci_verdict` | `verdict_ci` |  |
| bee en-attente --pr-states (JSON read by integration-auto.yml and verdicts.yml) | `auteur` | `author` |  |
| bee en-attente --pr-states (JSON read by integration-auto.yml and verdicts.yml) | `sha_attente` | `awaiting_sha` |  |
| bee en-attente --pr-states (JSON read by integration-auto.yml and verdicts.yml) | `pr_state, pr_head, pr_merge, pr_author, pr_author_id, pr_person` | `unchanged` | already English |
| site: api/registre.json top-level keys | `genere_le` | `generated_at` |  |
| site: api/registre.json top-level keys | `organisation` | `organization` |  |
| site: api/registre.json top-level keys | `registre` | `registry` |  |
| site: api/registre.json top-level keys | `guide_agent` | `agent_guide` |  |
| site: api/registre.json top-level keys | `projets, taches, membres, debats, arbre` | `projects, tasks, members, debates, tree` |  |
| site: api/registre.json top-level keys | `cap, essaim` | `balance, swarm` |  |
| site: api/registre.json top-level keys | `poste, bloquee_par, noeud_rattache, role, page, score, etat, fichier, lignes, sections, enfants` | `area, blocked_by, attached_node, role, page, score, state, file, lines, sections, children` |  |

## 4. Enumerated values

From the schemas' `enum`/`const`, the tool's constants (POSITIONS, ISSUES, DEMANDES, REPONSES, RETIRE, MOTIFS_*, ECARTS_SIGNALEMENT, POSTE_PAR_TYPE, ROLE_PAR_TYPE, POIDS_VOTE, LIBRE_SERVICE…) and the values found in the data.

| Domain | French | English | Data occurrences | Code files (literal) | Forks | Note |
|---|---|---|---|---|---|---|
| task status | `proposee` | `proposed` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| task status | `ouverte` | `open` | 135 | 4 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| task status | `reservee` | `reserved` | 0 | 4 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| task status | `en_relecture` | `in_review` | 12 | 6 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| task status | `integree` | `integrated` | 157 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| task status | `refusee` | `refused` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| task status | `abandonnee` | `abandoned` | 1 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| CLI --status filter | `toutes / tous` | `all` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | lister, debats |
| task type | `optimisation` | `optimization` | 25 | 3 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 2 (libyamlBee:bee/ci/tache.py, minizBee:bee/ci/tache.py) | fork tache.py: closed list read from main |
| task type | `relecture` | `review` | 2 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| task type | `mesure` | `measurement` | 8 | 4 (outils/bee.py, outils/test_bee.py, outils/juge/test_juge.py) | 2 (libyamlBee:bee/ci/tache.py, minizBee:bee/ci/tache.py) | fork tache.py |
| task type | `test` | `test` | 175 | 2 (outils/test_bee.py, outils/bee.py) | 2 (libyamlBee:bee/ci/tache.py, minizBee:bee/ci/tache.py) |  |
| task type | `decoupage` | `split` | 7 | 1 (outils/bee.py) | 2 (libyamlBee:bee/ci/tache.py, minizBee:bee/ci/tache.py) | fork tache.py |
| task size | `S / M / L` | `S / M / L` | 231 | 4 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 0 | keep |
| task compressed_output | `identique` | `identical` | 22 | 2 (outils/juge/jouet/bee/juge/projet.py, outils/repetition/load_test.py) | 5 (minizBee:bee/juge/projet.py, libyamlBee:bee/ci/tache.py) | fork tache.py, judge option sortie_compressee=identique (wave 2) |
| task compressed_output | `peut_changer` | `may_change` | 0 | 1 (outils/juge/jouet/bee/juge/projet.py) | 4 (minizBee:bee/juge/test_juge.py, libyamlBee:bee/ci/tache.py) |  |
| R11 area (poste, cap.postes) | `gouvernance` | `governance` | 111 | 5 (outils/bee.py, outils/test_bee.py, outils/repetition/test_load_test.py) | 0 | same token as the folder and the nature |
| R11 area | `projets` | `projects` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 1 (libyamlBee:bee/ci/tache.py) |  |
| R11 area | `coordination` | `coordination` | 39 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| contribution status | `en_relecture` | `in_review` | 12 | 6 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| contribution status | `integree` | `integrated` | 157 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| contribution status | `refusee` | `refused` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| contribution status | `annulee` | `cancelled` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| contribution status | `ecartee` | `set_aside` | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 | glossary: « set aside because a rival was kept » |
| verdict ci | `verte` | `green` | 24 | 4 (outils/test_bee.py, outils/bee.py, .github/workflows/verdicts.yml) | 4 (minizBee:bee/ci/test_verdict.py, libyamlBee:bee/ci/verdict.py) | on read, bee keeps accepting verte, vert, green, success, succes, succès |
| verdict ci | `rouge` | `red` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/ci_simulee.py) | 5 (minizBee:bee/ci/test_verdict.py, libyamlBee:.github/workflows/bee-ci.yml) |  |
| review opinion | `favorable` | `favorable` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| review opinion | `defavorable` | `unfavorable` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| review opinion | `abstention` | `abstention` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| vote value | `-1 / 0 / 1` | `-1 / 0 / 1` | 0 | 7 (outils/test_bee.py, outils/juge/test_juge.py, outils/juge/rapport.py) | 9 (minizBee:bee/ci/test_verdict.py, minizBee:bee/juge/test_juge.py) | keep |
| debate status | `ouvert` | `open` | 23 | 4 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| debate status | `clos` | `closed` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| debate outcome | `proposition` | `proposal` | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| debate outcome | `tache` | `task` | 0 | 5 (outils/bee.py, outils/test_bee.py, outils/repetition/load_test.py) | 4 (libyamlBee:bee/ci/tache.py, libyamlBee:bee/ci/verdict.py) |  |
| debate outcome | `decision` | `decision` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| debate outcome | `sans_suite` | `no_follow_up` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| argument position | `pour` | `for` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| argument position | `contre` | `against` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| argument position | `question` | `question` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| argument position | `fait` | `fact` | 1 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| debate computed state | `arguments_apres_synthese, dernier_argument, derniere_activite, participants` | `arguments_after_synthesis, last_argument, last_activity, participants` | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 | output only (debates --json, site) |
| proposal status | `ouverte` | `open` | 135 | 4 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| proposal status | `adoptee` | `adopted` | 3 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| proposal status | `rejetee` | `rejected` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| proposal status | `veto` | `veto` | 0 | 0 | 0 |  |
| invitation status | `proposee` | `proposed` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| invitation status | `decidee` | `decided` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| invitation status | `envoyee` | `sent` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| invitation status | `relancee` | `reminded` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| invitation status | `acceptee` | `accepted` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| invitation status | `refusee` | `refused` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| invitation status | `sans_reponse` | `no_answer` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| invitation status | `ecartee` | `set_aside` | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| invitation status | `retiree` | `withdrawn` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| invitation computed state | `expiree, a_redecider` | `expired, to_redecide` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | output only |
| invitation request | `garant` | `guarantor` | 1 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 |  |
| invitation request | `gardien` | `guardian` | 1 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| invitation request | `participer` | `participate` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| invitation request | `projet` | `project` | 1 | 6 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 3 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| invitation answer | `acceptee / refusee / sans_reponse` | `accepted / refused / no_answer` | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/site_bee.py) | 0 |  |
| withdrawal cause / redaction reason | `refus` | `refusal` | 0 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 0 |  |
| withdrawal cause / redaction reason | `demande` | `request` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| withdrawal cause / redaction reason | `sans_reponse` | `no_answer` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| text written in place of a person's data (RETIRE) | `retiré : refus / retiré : demande / retiré : sans réponse` | `withdrawn: refusal / withdrawn: request / withdrawn: no answer` | 0 | 0 | 0 | written into debates and invitations; schema const |
| marker written in place of a removed passage | `[retiré]` | `[removed]` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | MARQUE_RETRAIT; schema const |
| marker for a neutralised frame | `[marque d'encadré neutralisée]` | `[frame marker neutralised]` | 0 | 1 (outils/bee.py) | 0 | MARQUE_NEUTRALISEE |
| R13 mention language (--langue) | `fr (default) / en` | `en (default) / fr` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 | outgoing text to a person, not a name |
| removal channel | `courriel` | `email` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 1 (minizBee:bee/corpus/generer.py) |  |
| removal channel | `message_prive` | `private_message` | 0 | 1 (outils/bee.py) | 0 |  |
| removal channel | `issue` | `issue` | 0 | 6 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 0 | KEEP: a GitHub issue (the key issue becomes outcome) |
| removal channel | `discussion` | `discussion` | 0 | 1 (outils/bee.py) | 0 |  |
| removal channel | `autre` | `other` | 0 | 4 (outils/test_bee.py, outils/juge/lecture.py, outils/juge/test_juge.py) | 0 |  |
| report reason | `relectures_croisees` | `cross_reviews` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| report reason | `votes_croises` | `cross_votes` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| report reason | `relais_d_engagements` | `engagement_relay` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| report reason | `copie_de_contribution` | `copied_contribution` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| report decision outcome | `lies` | `linked` | 0 | 2 (outils/bee.py, outils/test_bee.py) | 0 |  |
| report decision outcome | `sans_indice` | `no_evidence` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| report decision outcome | `personnes_distinctes` | `distinct_persons` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| report decision outcome | `deja_lies` | `already_linked` | 0 | 1 (outils/bee.py) | 0 |  |
| report decision outcome | `doublon` | `duplicate` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| project status | `actif` | `active` | 3 | 3 (outils/bee.py, outils/repetition/load_test.py, outils/site_bee.py) | 1 (minizBee:bee/corpus/generer.py) |  |
| project status | `a_venir` | `upcoming` | 4 | 0 | 0 |  |
| project status | `archive` | `archived` | 0 | 2 (outils/repetition/load_test.py, outils/repetition/test_load_test.py) | 0 |  |
| maintainer tier | `aucun` | `none` | 7 | 1 (outils/bee.py) | 0 |  |
| maintainer tier | `observateur` | `observer` | 0 | 0 | 0 |  |
| maintainer tier | `partenaire` | `partner` | 0 | 0 | 0 |  |
| maintainer tier | `integration` | `integration` | 0 | 1 (outils/test_bee.py) | 0 |  |
| maintainer tier | `refus` | `refusal` | 0 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 0 |  |
| metric direction | `plus_haut` | `higher` | 16 | 4 (outils/juge/test_juge.py, outils/juge/jouet/bee/juge/projet.py, outils/bee.py) | 11 (libyamlBee:bee/bench/test_ab.py, minizBee:bee/bench/test_ab.py) |  |
| metric direction | `plus_bas` | `lower` | 8 | 3 (outils/juge/juge.py, outils/juge/jouet/bee/juge/projet.py, outils/juge/test_juge.py) | 11 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| metric unit (display) | `Mo/s, Ko, Mpixels/s, trames/s` | `MB/s, KB, Mpixels/s, frames/s` | 9 | 2 (outils/juge/test_juge.py, outils/juge/jouet/bee/juge/projet.py) | 10 (minizBee:bee/juge/execution.c, libyamlBee:bee/bench/ab.py) |  |
| metric id (wave 2, with the forks) | `debit_compression_n1/n6/n9` | `compression_throughput_n1/n6/n9` | 0 | 0 | 0 | emitted by fork benches and judges; registry keeps ids until wave 2 |
| metric id (wave 2) | `debit_decompression` | `decompression_throughput` | 11 | 3 (outils/juge/jouet/bee/juge/projet.py, outils/juge/test_juge.py, outils/repetition/ci_simulee.py) | 13 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| metric id (wave 2) | `memoire_max_ko` | `max_memory_kb` | 6 | 3 (outils/test_bee.py, outils/juge/jouet/bee/juge/projet.py, outils/juge/test_juge.py) | 14 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) |  |
| metric id (wave 2) | `ratio_n6` | `ratio_n6` | 1 | 1 (outils/test_bee.py) | 13 (minizBee:bee/resultats/miniz-0003/aa-instructions-1.json, minizBee:bee/resultats/miniz-0003/aa-instructions-2.json) | keep |
| metric id (wave 2) | `debit_analyse` | `parse_throughput` | 5 | 0 | 2 (libyamlBee:bee/bench/ab.py, libyamlBee:bee/ci/verdict.py) | libyaml; other projects' ids likewise |
| metric id (wave 2) | `instructions_analyse / _chargement / _emission` | `instructions_parse / _load / _emit` | 1 | 0 | 0 |  |
| category id | `compression-sans-perte` | `lossless-compression` | 50 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | also tree folder and task category |
| category id | `decodage-images` | `image-decoding` | 3 | 1 (outils/test_bee.py) | 0 |  |
| category id | `parsing-serialisation` | `parsing-serialization` | 27 | 0 | 0 |  |
| category id | `cryptographie` | `cryptography` | 1 | 0 | 0 |  |
| category id | `encodeurs-avec-perte` | `lossy-encoders` | 1 | 0 | 0 |  |
| category id | `systeme` | `system` | 1 | 3 (outils/bee.py, outils/juge/stats.py, outils/test_bee.py) | 8 (libyamlBee:bee/bench/ab.py, minizBee:bee/bench/ab.py) | same token as the key systeme -> system |
| category id / project id | `ruche` | `ruche` | 295 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 | keep (see open question) |
| category status | `ouverte` | `open` | 135 | 4 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| category status | `exclue` | `excluded` | 3 | 0 | 0 |  |
| member level (computed) | `Nouveau` | `New` | 0 | 3 (outils/bee.py, outils/test_bee.py, outils/inventaire_marqueurs.py) | 0 | glossary of AGENTS.en.md |
| member level | `Contributeur` | `Contributor` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/inventaire_marqueurs.py) | 0 |  |
| member level | `Confirmé` | `Confirmed` | 0 | 2 (outils/bee.py, outils/inventaire_marqueurs.py) | 0 |  |
| role (--role, tree/roles, ROLE_PAR_TYPE) | `optimiser` | `optimize` | 2 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| role | `relire` | `review` | 1 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| role | `mesurer` | `measure` | 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| role | `debattre` | `debate` | 0 | 4 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 |  |
| role | `garder` | `guard` | 0 | 1 (outils/test_bee.py) | 0 |  |
| role | `proposer` | `propose` | 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| role | `inviter` | `invite` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| tree root node id | `racine` | `root` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 | RACINE_ARBRE; task noeud value |
| bee.yaml guardian_review_required | `si_juge_incomplet` | `if_judge_incomplete` | 1 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| council role | `fondateur` | `founder` | 2 | 0 | 0 |  |
| pseudo written by the council and robots | `conseil` | `council` | 192 | 3 (outils/test_bee.py, outils/bee.py, outils/repetition/load_test.py) | 0 | cree_par of 175 tasks; R8 bootstrap compares it (code) |
| robot note signature | `bee, github-actions[bot]` | `unchanged` | 13 | 8 (outils/juge/test_juge.py, outils/test_bee.py, outils/bee.py) | 1 (minizBee:bee/ci/test_verdict.py) |  |
| verdict wait code (attente_verdict.motif) | `autre_base, base_changee, pr_ouverte, pr_fermee, base, base_juge` | `other_base, base_changed, pr_open, pr_closed, base, judge_base` | 0 | 8 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 13 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) |  |
| gate nature (printed by verifier-pr; LIBRE_SERVICE) | `reservation, liberation, soumission, mise_a_jour, note, relecture, vote, mesure, inscription, profil, proposition` | `reservation, release, submission, update, note, review, vote, measurement, registration, profile, proposal` | 10 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 5 (libyamlBee:bee/ci/tache.py, minizBee:bee/bench/profil.py) | internal + printed; tests |
| gate nature | `proposition_tache, validation_tache, renommage, inscription_parallele, retrait_parallele, soumission_parallele, promotion` | `task_proposal, task_validation, rename, parallel_registration, parallel_withdrawal, parallel_submission, promotion` | 0 | 2 (outils/test_bee.py, outils/bee.py) | 0 |  |
| gate nature | `ouverture_debat, argument, prise_de_plume, synthese, doublon, cloture_debat, accord_gardien, ecartement_invitation, signalement` | `debate_opening, argument, pen_takeover, synthesis, duplicate, debate_closing, guardian_approval, invitation_dismissal, report` | 0 | 3 (outils/test_bee.py, outils/bee.py, outils/site_bee.py) | 0 |  |
| gate nature (never self-service) | `gouvernance, creation_tache, decision, outillage, incident, caviardage, retrait_demande, relecture_humaine, agent_account` | `governance, task_creation, decision, tooling, incident, redaction, requested_removal, human_review, agent_account` | 111 | 7 (outils/test_bee.py, outils/bee.py, outils/repetition/test_load_test.py) | 0 | + new: migration |
| cap weights (POIDS_GESTES) | `relecture, mesure, note, proposition, vote, creation_tache, ouverture_debat, argument, synthese` | `review, measurement, note, proposal, vote, task_creation, debate_opening, argument, synthesis` | 10 | 5 (outils/test_bee.py, outils/bee.py, outils/juge/test_juge.py) | 2 (libyamlBee:bee/ci/tache.py, minizBee:bee/ci/tache.py) |  |
| fork judge base rule (wave 2) | `point_de_depart, introduction, refus_point_de_depart, refus_rebase, refus_introduction_miniz` | `start_point, introduction, refused_start_point, refused_rebase, refused_introduction_miniz` | 0 | 0 | 2 (minizBee:bee/ci/test_verdict.py, minizBee:bee/ci/verdict.py) | fork verdict.py |
| judge tag | `juge-v1, juge-v2, juge-v3` | `unchanged (immutable); next: judge-v4` | 7 | 3 (outils/test_bee.py, outils/juge/test_juge.py, outils/repetition/ci_simulee.py) | 1 (minizBee:bee/ci/test_verdict.py) | bee accepts (juge\|judge)-vN, compares N |

About 201 values in 130 rows (grouped rows list several values).

## 5. Names visible outside the repository

### 5.1 Workflow files and names

| File | New file | `name:` | New `name:` | Note |
|---|---|---|---|---|
| `validation.yml` | `validation.yml` | Validation du registre | Registry validation | fusion-auto listens to this name (workflow_run) |
| `fusion-auto.yml` | `auto-merge.yml` | Fusion automatique | Auto-merge | verdicts and integration-auto listen to this name |
| `integration-auto.yml` | `auto-integration.yml` | Intégration automatique | Auto-integration |  |
| `verdicts.yml` | `verdicts.yml` | Verdicts des forks | Fork verdicts | integration-auto listens to this name |
| `expirations.yml` | `expirations.yml` | Réservations expirées | Expired reservations |  |
| `site.yml` | `site.yml` | Site | Site | dispatched by file name from 5 places: keep the file name |
| `suite.yml` | `suite.yml` | Suite complète | Full suite | dispatched by file name; bee main-green reads its runs by file name and run-name |
| `juge.yml` | `judge.yml` | Juge commun | Common judge | forks call <repo>/.github/workflows/juge.yml@<sha>: pinned, unaffected; new pins use judge.yml |
| `juge-commun.yml` | `judge-meta-tests.yml` | Juge commun (méta-tests) | Common judge (meta-tests) |  |

`workflow_run` listens by `name:` (fusion-auto → « Validation du registre »; verdicts → « Fusion automatique »; integration-auto → « Fusion automatique », « Verdicts des forks »): the three names and the three listeners change in one commit, with the existing test that ties them. Workflows are dispatched by file name (`site.yml` from five places, `suite.yml` from validation.yml; bee main-green reads `actions/workflows/suite.yml/runs`), hence those file names stay.

### 5.2 Jobs (check names) and concurrency groups

| Workflow | Job id | New id | Note |
|---|---|---|---|
| `validation.yml` | `controles` | `checks` |  |
| `validation.yml` | `suite` | `suite` |  |
| `validation.yml` | `relancer` | `dispatch-suite` |  |
| `validation.yml` | `valider` | `validate` | REQUIRED CHECK of main's ruleset: rename only with the ruleset (three steps) |
| `fusion-auto.yml` | `fusionner` | `merge` |  |
| `integration-auto.yml` | `integrer` | `integrate` |  |
| `integration-auto.yml, verdicts.yml, site.yml` | `pause` | `pause` |  |
| `verdicts.yml` | `verdicts` | `verdicts` |  |
| `expirations.yml` | `liberer` | `release` |  |
| `site.yml` | `portee` | `scope` |  |
| `site.yml` | `construire` | `build` |  |
| `site.yml` | `deployer` | `deploy` |  |
| `juge.yml` | `juge` | `judge` | its outputs are the reusable workflow's outputs |
| `juge-commun.yml` | `meta-tests` | `meta-tests` |  |
| `suite.yml` | `tests` | `tests` |  |

| Concurrency group | New | Note |
|---|---|---|
| `fusion-auto` | `auto-merge` |  |
| `integration` | `integration` |  |
| `ecriture-main` | `main-writes` | shared by integration-auto's job and expirations.yml: rename both at once |
| `verdicts` | `verdicts` |  |
| `pages / site-push-<run>` | `pages / site-push-<run>` |  |

Step names (« Dépendances », « Règles de la pull request », « Publier », « Juger »…) are display text for GitHub, and no ruleset or other repository names them; but tests find some steps by name (test_juge.py: the steps of juge.yml such as « Conserver le rapport »; test_bee.py: « Dépendances », « Retrouver la pull request », « Dispatch the full suite »…). They are renamed in the workflow layer together with the tests that name them.

### 5.3 The reusable common judge (`juge.yml`, called by the forks)

| French | English | Note |
|---|---|---|
| input base_sha | base_sha | keep (English) |
| input tete_sha | head_sha | a fork changes it when it bumps its pin |
| input options (CLE=VALEUR, e.g. sortie_compressee=identique) | options (KEY=VALUE, compressed_output=identical) | the option names are the plugin's: judge track |
| input historique | history |  |
| input repetitions | repetitions |  |
| input sans_instructions | no_instructions |  |
| output code | code |  |
| output empreinte | fingerprint |  |
| output suspectes | suspicious |  |
| output sorties_comparees | outputs_compared |  |
| output greffon | plugin |  |
| output graine | seed |  |
| output base / tete | base / head |  |
| artifact « juge » (juge.json, journal.txt, code, sorties) | artifact « judge » (judge.json, log.txt, code, outputs) | the forks download « juge »: produced at the pinned commit, so the old name stays until they bump |
| artifact « verdict » (forks) | verdict | keep: verdicts.yml downloads -n verdict |

### 5.4 Commit messages, PR titles and bodies, robot texts

| French | English | Note |
|---|---|---|
| Intégrations et clôtures automatiques (R3) | Automatic integrations and closures (R3) | integration-auto; nothing parses it (push-scope reads diffs); a test commits it as a fixture |
| Verdicts des forks | Fork verdicts | verdicts.yml |
| Libération des réservations expirées (R7) | Release of expired reservations (R7) | expirations.yml |
| PR body « Publié avec `bee publier`.\n\nNature : <titre>. » | « Published with `bee publish`.\n\nNature: <title>. » | bee publier writes it; nothing parses it |
| PR titles bee suggests: « Réservation <t> », « Soumission <c> », « Inscription <login> », « Inscription en parallèle <t> », « Libération », « Relecture », « Vote », « Proposition » | « Reservation <t> », « Submission <c> », « Registration <login> », « Parallel registration <t> », « Release », « Review », « Vote », « Proposal » | free text; branch names derive from it (bee/<slug>-<date>) and from a hash of {task path: engagement} (bee/engagement-<hash>) |
| PR comment « Écartée au profit de … retenue par la règle R3 » | « Set aside in favor of …, kept by rule R3 » | integration-auto; site and record use the same sentence |
| Robot notes « Réservation de X expirée après 72 h (R7). » | « X's reservation expired after 72 h (R7). » | written into task notes (prose: old notes stay) |
| Council commit prefix « Council record: » | unchanged | already English |

No code parses a commit subject, PR title or PR body: push-scope classifies commits by their diff (docs/decisions.md rows added only count as data), fusion-auto and integration-auto decide from bee's exit codes and the files. The only parsed display string is suite.yml's `run-name` (« Full suite on <sha> », TITRE_SUITE), already English.

### 5.5 Environment variables and secrets

| French | English | Note |
|---|---|---|
| `BEE_REGISTRE` | `BEE_REGISTRY` | user-facing default of --registre: if only the old one is set, refuse loudly (never fall back silently to another registry) |
| `BEE_MAINTENANT` | `BEE_NOW` | tests (≈90 uses) and the rehearsal clock |
| `BEE_SIMU, BEE_SIMU_ROBOT` | `BEE_SIM, BEE_SIM_ROBOT` | rehearsal |
| `BEE_JUGE_RESEAU` | `BEE_JUDGE_NETWORK` | judge; forks' README documents it (judge track) |
| `BEE_JUGE_INTEGRATION` | `BEE_JUDGE_INTEGRATION` | juge-commun.yml and the forks' meta-tests (judge track) |
| `BEE_JUGE_COMMUN (forks)` | `BEE_COMMON_JUDGE` | fork-side (judge track) |
| `BEE_FLUX_SEUL, BEE_SECRET` | `BEE_STREAM_ONLY, BEE_SECRET` | tests |
| `BEE_INTEGRATION_TOKEN (secret)` | `BEE_INTEGRATION_TOKEN` | keep: a repository secret's name |
| `workflow step env: AVANT, APRES, BASE_EVENEMENT, AUTEUR, NUMERO, INSTANT_PR, TETE, TETE_EVENEMENT, CONTROLES, PORTEE, RELANCE, DEPOT, HISTORIQUE, SANS_INSTRUCTIONS` | `BEFORE, AFTER, EVENT_BASE, AUTHOR, NUMBER, PR_TIME, HEAD, EVENT_HEAD, CHECKS, SCOPE, DISPATCH, REPO, HISTORY, NO_INSTRUCTIONS` | internal to each workflow |
| `step outputs: portee, numero, auteur, verif` | `scope, number, author, check` | internal; `portee` is read across jobs (needs.controles.outputs.portee) |
| `FAUX_GH_*, FAUX_DOCKER_*, PANNE_* (test doubles)` | `FAKE_GH_*, FAKE_DOCKER_*, FAULT_*` | tests only |
| `fork-side: REGISTRE, ETATS, JUGE_COMMUN_SHA, BEE_JUGES, BEE_IMAGE, BEE_TRAVAIL, BEE_COMMIT_AMORCAGE, BEE_SORTIE_TACHE, BEE_FUZZ_SORTIES, BEE_FUZZ_DISCRET` | `fork plan (miniz-0046, libyaml-0019)` | not registry names |

### 5.6 Site paths (GitHub Pages)

| French | English | Note |
|---|---|---|
| `index.html, agora.html` | `index.html, agora.html` | keep |
| `arbre.html` | `tree.html` | anchors are node ids |
| `taches/<id>.html` | `tasks/<id>.html` |  |
| `projets/<id>.html` | `projects/<id>.html` |  |
| `contributions/<id>.html` | `contributions/<id>.html` |  |
| `debats/<id>.html` | `debates/<id>.html` |  |
| `api/registre.json` | `api/registry.json` | README links it; no outside consumer known |
| `index.html#taches, #contributions, #participer` | `#tasks, #contributions, #participate` | UTILISATEURS.md links #participer |

### 5.7 Labels, tags, rulesets, branch names

| French | English | Note |
|---|---|---|
| label proposition-tache (issue template) | task-proposal | rename the GitHub label (gh label edit) with the template |
| git tags juge-v1 (821647d), juge-v2 (dab13a6), juge-v3 (3b21e97) | unchanged; next tag judge-v4 | immutable; minizBee pins juge-v2 by SHA; extend any juge-v* tag protection to judge-v* |
| ruleset: required check « valider » | « validate » | admin step |
| branch names written by bee publier: bee/engagement-<hash>, bee/<slug>-<date> | unchanged pattern | the hash covers the task path, the PR's title and keys: a waiting PR from before the switch is not found again; ruche-0155: one waiting under the French title kept until then (« Réservation <t> », « Inscription en parallèle <t> ») is found again, by bee-publish.json or by its branch, until date D (`DATE_D` in bee.py), and not after |
| fork branches tache/<task> (AGENTS.md convention) | task/<task> | fork convention; nothing in the registry parses it |

### 5.8 Markers bee parses in human-written markdown (bilingual since ruche-0055)

| Marker | Where | French form | English form | After the move |
|---|---|---|---|---|
| Tree node sections | tree nodes (SECTIONS_NOEUD / _EN), one language per node | Pourquoi cette branche existe · Ce qui compte ici · Ce qu'on peut ignorer ici · Enfants | Why this branch exists · What matters here · What you can ignore here · Children | write English; drop the French reader once ruche-0066/0067 have translated every node (format reader, not a refusal) |
| Node front matter keys | tree nodes (CLES_ENTETE_NOEUD) | parent, mis_a_jour, entretenu_par, budget_lignes | parent, updated_on, maintained_by, line_budget | renamed with the tree move (names, not prose) |
| Children line | tree nodes (ENFANT_NOEUD) | - `id` : texte | - `id`: text | the regex already allows both |
| Vulnerability line kept under --budget | root node | - Une faille | - A vulnerability / - Vulnerability / - **Vulnerability** | keep both while any node is French |
| Debate link | docs/questions-ouvertes.md (LIEN_DEBAT), written by debate import-questions | Débat : [D-nnnn] | Debate: [D-nnnn] | writer switches to English; reader keeps both until the file is translated |
| Numbered question | docs/questions-ouvertes.md (QUESTION_NUMEROTEE) | 1. **…** | same | language-neutral |
| Placeholder to fill | manifests (A_REMPLIR), written by bee manifeste | À REMPLIR | TO FILL IN | writer switches to English; BOTH stay refused forever (a refusal list never narrows) |
| Data frame around member texts | bee contexte / voir (DEBUT_DONNEES, FIN_DONNEES, MARQUE_ENCADRE) | === DONNÉES de la tâche … === / === FIN DES DONNÉES === | === DATA of task … === / === END OF DATA === | ruche-0069 note of 1 Nov: refuse an imitated frame in BOTH languages in the same change |
| Personal-data detectors | free texts (VOIES_FR/_EN, arobase/at, phone words, elisions) | French forms | English forms | keep both forever (detectors) |
| CI verdict word | fork verdict.json `ci` (normalised on read) | verte, vert, succes, succès | green, success | keep accepting all; record `green` |
| R13 mention and request phrases | outgoing invitation text (MENTION_INVITATION, PHRASE_DEMANDE) | fr | en | keep both languages: text for people, default en |

## 6. What the forks reference in the registry

Cloned read-only: https://github.com/Bee-ruche/minizBee (master 67bf3b4) and https://github.com/Bee-ruche/libyamlBee (master 01cac4b).

| Reference | minizBee | libyamlBee | Pinned? | A rename on registry main… |
|---|---|---|---|---|
| Registry checkout `ref: main` in the « Manifeste et taille » job (`REGISTRE: Bee-ruche/registre`) | bee-ci.yml | bee-ci.yml | **no: main** | is seen by the next CI run of every fork PR |
| `registre/outils/requirements.txt` (pip install) | bee-ci.yml | bee-ci.yml | no (main) | BREAKS the job if outils/ moves (the step runs from the PR's own bee-ci.yml) |
| `registre/outils/bee.py --registre registre verifier-fork --tache --base --tete --depot [--auteur]` | bee/ci/manifeste.sh | bee/ci/manifeste.sh | no (main) | BREAKS on outils/ → tools/, verifier-fork → check-fork, or any of its five options |
| `taches/**/<task>.yaml` (glob) / `taches/libyaml/<task>.yaml` | bee/ci/tache.py | bee/ci/tache.py | no (main) | BREAKS: « tâche introuvable », CI red |
| Task keys `type`, `metrique`, `sortie_compressee` | bee/ci/tache.py | bee/ci/tache.py | no (main) | SILENT: unknown key → type « inconnu », metric « aucune » (gain null, no R4), output « identique » |
| Task values optimisation, mesure, test, decoupage; identique, peut_changer | bee/ci/tache.py | bee/ci/tache.py | no (main) | SILENT, as above |
| `projets/libyaml.yaml`, key `metriques[].id` | — | bee/ci/tache.py | no (main) | BREAKS (« descripteur illisible ») or empties the metric list |
| Metric ids (debit_*, ratio_n6, memoire_max_ko, instructions_*) | tache.py, verdict.py, ab.py, bee/juge/projet.py | verdict.py, ab.py | fork code | registry and forks must agree: wave 2 only |
| Manifest `manifestes/<task>.yaml`, else `CONTRIBUTION.yaml`; keys tache, utilisateur, agent{modele, client}, resume, changement, mesures{machine, commande, repetitions, avant, apres}, teste, non_teste, doutes, taille_reelle | 12 manifests on master | 1 manifest + CONTRIBUTION.yaml on master | validated by registry main | BREAKS open PRs' manifests if verifier-fork stops reading French keys or manifestes/: dual-read until a dated end |
| `verdict.json` (artifact « verdict »): ci verte\|rouge, etape_en_echec, gain, metrique, au_dela_du_bruit, mesures{A,B}, instructions, degradations, lignes_modifiees, amorcage, base_juge, juge{…} | bee/ci/verdict.py | bee/ci/verdict.py | fork code at the PR's base | read by verdicts.yml + record-verdict: dual-read until the forks write English |
| Workflow file name `bee-ci.yml`, artifact `verdict` | yes | yes | — | registry reads `actions/workflows/bee-ci.yml/runs`: keep both names |
| `uses: Bee-ruche/registre/.github/workflows/juge.yml@dab13a6…` (juge-v2) and `JUGE_COMMUN_SHA` checkout | bee-ci.yml (3 jobs + juge) | — (own bench) | **yes, by SHA** | nothing breaks: the old commit keeps juge.yml, outils/juge/juge.py, isoler.sh. juge.yml only checks the commit is an ancestor of main (identical or behind) |
| `juge-commun/outils/juge/juge.py --outillage --image-seulement`, `isoler.sh`, artifact « juge », outputs, inputs base_sha/tete_sha/options/historique | bee-ci.yml | — | yes (SHA) | unaffected until the fork bumps to judge-v4; the bump PR updates paths, options, inputs and the artifact name |
| Plugin contract `bee/juge/projet.py` (CORPUS, VERIFICATION, METRIQUES, CONSTRUIRE, EN_TETES_BASE…, methods corpus/verification/verifier/fixes/repetition/instructions/scenario) | bee/juge/ | — | read from the fork BASE by the pinned judge | judge track: judge-v4 accepts both names, then the fork renames, then judge-v5 drops French |
| Tag names juge-v1/juge-v2 in comments, tests and manifests | bee-ci.yml, README, test_verdict.py, manifests | — | comments | nothing (tags are immutable) |
| Links to registry docs: AGENTS.md, COMMANDEMENTS.md, docs/securite.md, docs/evaluation.md, docs/juge-commun.md, projets/miniz.yaml, verdicts.yml | AGENTS.md, CLAUDE.md, bee/README.md, bee-ci.yml, lancer.sh | AGENTS.md, CLAUDE.md, bee-ci.yml, lancer.sh | URLs to blob/main | dead links (COMMANDEMENTS.md, docs/securite.md…); fixed by the forks' prose tasks |
| Commands named in fork docs: bee manifeste, verifier-fork, enregistrer-verdict, enregistrer-mesure | AGENTS.md, README, tache.py | AGENTS.md, README, tache.py | docs | stale instructions until the forks' prose tasks |

Conclusion: the judge is pinned by SHA, so a rename on main never reaches it; everything the « Manifeste et taille » job does is unpinned (main), so the forks must learn both layouts **before** the registry renames the tool's folder, its commands, the tasks' folder, keys or values, or the projects' folder; and since `bee manifest` writes English manifests (in `manifests/`) from the data switch on, they must read both manifest forms too (fork layer F1 of migration-plan.md).

## 7. Counts

| Table | Names | Renamed |
|---|---|---|
| 1.1 subcommands | 68 | 58 |
| 1.2 options and positionals of bee | 120 | 88 |
| 1.3 options of other scripts | 38 | 28 |
| 2 folders and files (rows; + 18 node files) | 135 | 113 |
| 3 keys | 212 | 160 |
| 3.1 bee.yaml keys | 71 | 65 |
| 3.2 boundary keys (rows) | 39 | — |
| 4 values (rows / values) | 130 / ≈201 | — |
| 5 outside names (rows) | 77 | — |

