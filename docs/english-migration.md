# The registry in English: the migration plan

> Adopted by the council (docs/decisions.md, 8 November 2026) after an independent adversarial review by another model. **Section 13 (one switch instead of eight layers, the founder's choice of 8 November) prevails over everything above it; section 12 lists the changes made after the review and prevails over sections 0 to 11.** The name map is [english-names.md](english-names.md), a reviewed draft that layer L1a turns into the scoped, machine-readable `outils/migration/names.yaml`. Task ids: section 11.

Plan for the founder's decision that everything moves to English now (texts, code, identifiers, command names, folder
names, YAML keys, enumerated values), with only « La Ruche », « la Nuit des abeilles », « l'essaim » and « le miel »
kept, in prose only, and the tool still called `bee`. It replaces the two plans of ruche-0069 (messages, help, command
names) and ruche-0070 (folders, keys, values). The names themselves are in [english-names.md](english-names.md); this file says
how to move them without breaking the gate, the robots, the history or the forks.

Read against the registry at 403fdc5 (8 Nov 2026), minizBee at 67bf3b4 and libyamlBee at 01cac4b.

## 0. In one page

- **One map, one script, proofs.** The map (english-names.md, committed as `tools/migration/names.yaml`) is reviewed once by
  the council. Every mechanical rename is done by a committed script and accompanied by checks that prove nothing else
  changed: the code is the same syntax tree modulo the map, the data is the same values modulo the map (and translates
  back byte for byte), the argument parser is the same tree modulo the map, every path rule of the gate classifies the
  renamed path as it classified the old one, every history-derived date is the same before and after the move, and every
  read-only command prints the same output modulo the map.
- **No aliases** (section 2). Old command names get a refusal that says the new name (exit 2, nothing runs) for three
  months; the forks get a caller-side fallback for the one command they call, removed after the move.
- **The forks read registry main, unpinned**, in their « Manifeste et taille » job (tool, requirements, tasks, task keys
  and values, projects). They must learn both layouts before the registry renames anything they read (layer F1). The
  common judge is pinned by SHA: a rename on main never reaches it.
- **The data switch is one atomic council PR** from the founder's own account, during a short freeze. The gate judges it
  in an explicit *migration mode*: it proves the new tree is exactly the committed translation of main's tree, then runs
  the ordinary per-file rules on (translated old, new) pairs, which must see no change. No immutability rule is skipped:
  each one is shown to hold.
- **History is not translated on read** (section 12, change 1): git history keeps the French paths and keys; the freeze
  drains every open engagement, and the bounded one-time effects of the move are recorded.
- **Closed history stays as written** (prose of closed tasks, decisions rows, debate questions and arguments, commit
  messages, tags); **every key and enumerated value migrates everywhere**, because the tool reads every record.

Sequence (section 7, superseded by section 13): L0 map and decision → L1a/L1b migration tooling (dormant) ∥ F1 forks read both layouts → L2 code and
docs folders and files → L3 command line → L4 workflows → *ruleset swap* → L5 data switch (freeze) → L6 identifiers →
L7 prose (messages, docs, tree, rules; several PRs) → J judge-v4 and F2 forks write English (metric ids, manifests,
verdict.json) → L8 contraction after date D.

## 1. Principles

1. **The map is the specification.** Every French name has exactly one English name, and inside one family (keys of
   one schema, values of one domain, paths of one folder) two French names never share an English name. The forward map
   is therefore a function and the inverse is a function per family, which the history reader and the round-trip proof
   need. The map is committed on main (L0) before any rename, so that a rename PR cannot loosen the map that judges it:
   proofs always read the map from the base.
2. **Mechanical, re-runnable, proven.** A mechanical layer is a script run on a commit, never a hand edit. Its PR holds
   the script output plus a small hand-made part. Because the script is committed, any open branch (the hardening tasks
   do not wait) is brought up to date by re-running it, not by resolving thousands of conflicts by hand.
3. **Hand-made parts stay small and are reviewed as code**: dynamic name construction (`f"{dossier}_max_par_pr"`), tokens
   that map differently by role (`issue`: the key becomes `outcome`, the channel value « issue » stays; `signalement`:
   the command becomes `decide-report`, the nature `report`), constants that hold sets of keys (section 3.3), the history
   and gate migration code, the boundary adapters. Every other French token maps to one English token whatever its role
   (key, value, folder, command): checked by the map lint of L0.
4. **Dual-read only at the boundary with the forks, never in the registry's own data.** The registry's data moves in one
   commit; nothing in it is ever read in two vocabularies. What the forks produce (manifests, verdict.json, metric ids)
   is read in either vocabulary, one vocabulary per document, until a date set in the tool (a constant: the data cannot
   extend it). A document that mixes the two vocabularies is refused.
5. **Fail closed, never fall to a default.** A retired French folder or file name is refused by name after the switch
   (never silently ignored, never self-service, never « data » for ci-scope); a bee.yaml key the tool does not read is
   refused (today a malformed value falls back to its default, and a key left in French would fall back silently).
6. **The human council merges** every layer that touches the gate, the workflows, an authority file or the data; the
   data switch and the authority renames come from the founder's own account (an agent account may never touch an
   authority file, ruche-0089).

## 2. Aliases: recommendation

**No aliases.** The earlier plan kept French command names as aliases for three months. Today every caller is ours: the
workflows, the rehearsal scripts, the skill and docs, and the forks' `bee/ci/manifeste.sh`. Against that, an alias costs:

- **A second path through every name-based guard.** Some guards decide on the command's name, not on the function it
  runs: the rehearsal wrapper `outils/repetition/bee` refuses `publier` by name (`grep -qx publier`), so an alias
  `publish` would publish from the simulation; AGENTS.md's rule « never publish after `manifeste` or `verifier-fork` »,
  test tables over the command list, and any future allowlist in a workflow would all need both names, and missing one
  is a silent hole. Fusion-auto itself decides on exit codes, so the gate is not bypassed by an alias today, but every
  check written later must remember the second spelling.
- **88 options double too**: every `--utilisateur`, `--tete`, `--motif`… would need its alias, and argparse's prefix
  matching makes the two vocabularies collide: in `relire`, `--def` means `--defaut` today and becomes ambiguous (an
  error) once `--defect` is added beside it.
- **Two vocabularies in the docs and the agents' habits** for three months, which is what the move is meant to end.

What replaces aliases:

- **A refusal that names the new command** for the 58 renamed subcommands: `bee prendre …` exits 2 with « `prendre`
  was renamed `take` on <date>: bee take … » on stderr, before argument parsing, and runs nothing. No execution path, so no
  gate surface. Removed in L8 (three months).
- **`BEE_REGISTRE` set without `BEE_REGISTRY`**: refused loudly (otherwise bee would silently fall back to the registry
  that contains the tool, possibly a stale clone).
- **The forks' fallback lives in the caller** (F1): `manifeste.sh` asks `bee.py --help` whether `check-fork` exists and
  falls back to `verifier-fork` with the French options; removed in F2. It is bounded, outside the gate, and lives in a
  file the council reviews.

## 3. The gate: every path rule and its new form

`bee verifier-pr` (→ `check-pr`) runs twice: in validation.yml with the PR's own tool (read-only, required check), and in
fusion-auto.yml with main's tool on a simulated merge (the only one that can merge, exit 0 = merge, 3 = human). It calls
`_verifier_pr` → `verifier_pr_de` → `verifier_debat`, `verifier_invitation`, `verifier_retrait`, `verifier_engagements`,
`verifier_notes_ajoutees`, `verifier_tache_proposee`, `textes_personnels`, `verifier_pr_arbre`, `qui_est_qui`, and
`verifier_registre` (bee valider). Around it, `ci-scope`, `push-scope` (with `commit_de_donnees`) and
`needs-account-date` decide what CI runs.

### 3.1 Path rules (what a self-service PR may touch, what is reserved to the council)

| # | Rule (constant or function) | Today | New form | If one form were missed |
|---|---|---|---|---|
| R-a | Self-service folders: mode 100644 kept, no symlink, no YAML comment added (`DOSSIERS_LIBRE_SERVICE`, `verifier_pr_arbre`) | `taches/ contributions/ votes/ mesures/ membres/ propositions/ debats/ invitations/ signalements/` | `tasks/ contributions/ votes/ measurements/ members/ proposals/ debates/ invitations/ reports/` | a folder left out escapes the mode and comment checks (widening) |
| R-b | Self-service file shapes, one per folder (`FICHIERS_LIBRE_SERVICE`) | `taches/<p>/<p>-<nnnn>.yaml`, `contributions/<p>/<t>-c<n>.yaml`, `votes/<c or P-nnnn>/<login>.yaml`, `mesures/<c>/<login>.yaml`, `membres/<login>.yaml`, `propositions/P-<nnnn>.yaml`, `invitations/I-<nnnn>.yaml` + `invitations/ne-plus-contacter.yaml`, `signalements/S-<nnnn>.yaml` | same shapes under `tasks/ contributions/ votes/ measurements/ members/ proposals/ invitations/ (do-not-contact.yaml) reports/` | an unknown folder falls to « gouvernance » (council only): narrowing, but the PR's own checks would refuse honest PRs |
| R-c | Debate files (`CHEMIN_DEBAT`, `verifier_debat`) | `debats/D-<nnnn>.yaml` | `debates/D-<nnnn>.yaml` | as R-b |
| R-d | Numbering of added files (`CHEMIN_TACHE`, `CHEMIN_PROPOSITION`, `CHEMIN_INVITATION`, `CHEMIN_SIGNALEMENT`, `numeros_dans` on the base, `NUMERO_RESERVE` 9000+) | `taches/{p}`, `propositions`, `invitations`, `signalements`, `debats/` listed at the base | `tasks/{p}`, `proposals`, `invitations`, `reports`, `debates/` | on the switch PR itself the base has no new folder: numbering would restart at 0001 (section 4) |
| R-e | Byte bounds by folder before parsing (`OCTETS_MAX`, `sorte_libre_service`, `borne_octets`, `MARGE_OCTETS`) | keys `taches contributions votes mesures membres propositions debats invitations signalements` + path `invitations/ne-plus-contacter.yaml` | `tasks … measurements members proposals debates invitations reports` + `invitations/do-not-contact.yaml` | a missed folder takes `OCTETS_LECTURE_MAX` (1 MiB) instead of 32-256 KiB (widening) |
| R-f | Long-text and own bounds by kind (`CHAMPS_LONGS`, `TEXTES_PROPRES`, `SCHEMAS_TEXTES`) | folder → fields (`contexte`, `relectures/motif`, `arguments/texte`…) and folder → schema | `tasks: context, acceptance_criteria, out_of_scope, notes/text`; `contributions: summary, decision_reason, reviews/reason, lifts/reason, declared/…`; … | a missed field falls to `TEXTE_CHAMP_MAX` 300 (narrowing) or a missed folder skips the personal-data detectors (widening) |
| R-g | Removal on request scans these folders and fields (`PARCOURS`, `sorte_parcourue`, `CHAMPS_DE_LA_PERSONNE`) | `taches` (titre, contexte, criteria, hors_perimetre, texte), debates, invitations, notes… | same over the new folders and keys | **a missed folder or field leaves a person's data in place after `remove-data` (commandment 10)**: tested explicitly |
| R-h | Tooling paths: a member may propose, never auto-merged (`CHEMINS_OUTILLAGE`) | `outils/* schemas/* modeles/* docs/* .github/* .claude/* arbre/* AGENTS.md README.md UTILISATEURS.md MAINTENEURS.md` | `tools/* schemas/* templates/* docs/* .github/* .claude/* tree/* AGENTS.md README.md USERS.md MAINTAINERS.md` | a missed path falls to « gouvernance » (members can no longer propose tooling: narrowing) |
| R-i | Authority files: never touched by an agent account, any case (`AUTHORITY_FILES`) | `COMMANDMENTS.md COMMANDEMENTS.md gouvernance/conseil.yaml gouvernance/comptes-agents.yaml gouvernance/gardiens.yaml gouvernance/garants.yaml gouvernance/consignes/ docs/organisation.md docs/garants.md docs/devolution.md` | `COMMANDMENTS.md governance/council.yaml governance/agent-accounts.yaml governance/guardians.yaml governance/guarantors.yaml governance/briefs/ docs/organization.md docs/guarantors.md docs/devolution.md` **plus every old name kept** | an old name dropped would let a council member's agent account re-add a French « COMMANDEMENTS.md » with status (still never auto-merged, but no longer refused): keep the old names forever |
| R-j | Lists that bind logins to account numbers, read from the base (`LISTES_LIEES`, `AGENT_ACCOUNTS`, `qui_est_qui`) | `gouvernance/{conseil,gardiens,garants,comptes-agents}.yaml`, `membres/` | `governance/{council,guardians,guarantors,agent-accounts}.yaml`, `members/` | on the switch PR the base has the old paths: the founder would not be council (section 4) |
| R-k | A guardian adds an incident (`"gouvernance/incidents.yaml"`, canonical form) | `gouvernance/incidents.yaml` | `governance/incidents.yaml` | the guardian path disappears (narrowing) |
| R-l | A removal on request is judged alone, in full (`CHEMIN_RETRAITS`, `verifier_retrait`) | `gouvernance/retraits.yaml` | `governance/removals.yaml` | a missed name lets a removal be mixed into another PR |
| R-m | Base reads by the gate: reserved logins in the base's bee.yaml (`reserved_pseudo`), the task at the base for a submission (`taches/{p}/{t}.yaml`), invitations and the do-not-contact list at the base (`illisibles_base`) | French paths and keys | English paths and keys | on the switch PR only (section 4) |
| R-n | Data-only PRs skip the full suite (`ci_scope`: R-b/R-c shapes, statuses A/M, mode 100644) | as R-b, R-c | as R-b, R-c | a missed folder sends PRs to the full suite (safe); an old folder kept would let a French-path file count as data (refused by R-q) |
| R-o | Data-only pushes (`push-scope`, `commit_de_donnees`) | R-n + `docs/decisions.md` rows added only | unchanged path `docs/decisions.md` | — |
| R-p | Account date needed (`date_compte_requise`) | an added file whose first segment is `membres` | `members` | a missed name: registration refused for lack of a date (safe) |
| R-q | **New: retired names refused** (`bee valider` and the gate) | — | any path under `taches/ debats/ propositions/ membres/ mesures/ signalements/ gouvernance/ projets/ arbre/ modeles/ outils/`, or a retired file name (`REGLES.md`, `UTILISATEURS.md`, `MAINTENEURS.md`, `COMMANDEMENTS.md` if removed, `docs/<old>.md`, `invitations/ne-plus-contacter.yaml`) | without it, a stale PR adding `taches/x.yaml` after the switch would merge cleanly into a folder no code reads |
| R-r | History paths read back (`DOSSIERS_GESTES`, `CHEMIN_HISTORIQUE`) | `taches contributions votes mesures propositions debats` | new folders **and** the old ones, for reading history only (section 4.3) | gestures re-dated by the move |
| R-s | Fork side (`verifier_fork`): R1 exclusions and commandment 3 | `manifestes/**`, `CONTRIBUTION.yaml`, project's `chemins_hors_decompte`, `chemins_juges` | `manifests/**` and, until D, `manifestes/**` and `CONTRIBUTION.yaml`; `paths_not_counted`, `judge_paths` | a missed exclusion counts manifest lines against R1 (safe) |
| R-t | Workflows' own path rules: integration-auto never merges a fork PR touching `^\.github/workflows/`; juge-commun.yml runs on `outils/juge/**`; verdicts.yml reads `manifestes/<task>.yaml` then `CONTRIBUTION.yaml` | as written | `tools/judge/**`; `manifests/`, then `manifestes/` and `CONTRIBUTION.yaml` until D | meta-tests silently stop running on judge changes (filter) |

**How a test proves none was lost** (proof P4, `tools/migration/test_rules.py`, in the full suite of L1 and run on L2 and
L5): it imports the base's `bee.py` (old) and the PR's `bee.py` (new) side by side and, for a corpus generated from the
constants of the old tool (for each rule: positive examples of every shape, negative neighbours such as a sub-folder, a
wrong extension, another case, a 9000+ number, a symlink, mode 100755), asserts that the new tool's answer for
`map(path)` equals `map(old answer for path)`: nature, refusal or acceptance, byte bound, ci-scope class, data-commit
class, history class, removal scan. It also asserts that every retired French path is refused by the new tool and is
never « data », so nothing falls to a default by accident, and that `map` is a bijection on the corpus.

### 3.2 What the switch PR changes in the workflows' calls

validation.yml and site.yml run the **base's** (or pre-push) tool with `ci-scope`, `main-green`, `push-scope`; their
names are already English but `--tete`, `--avant`, `--apres` become `--head`, `--before`, `--after`, and the tool's path
moves. In the PR that renames them (L2, L3), the PR's workflow calls the base's tool with the new path or options: it fails,
and both steps fail closed to « full » (the full suite runs). The first push after the merge does the same once. No step
fails open.

### 3.3 Sets of keys the gate compares (hand-checked, each with a test map(old set) == new set)

`CLES_LIBRE_SERVICE_TACHE`, `CLES_NAISSANCE`, `CLES_CONFIRMATION`, `CLES_DEBAT`, `CLES_ARGUMENT`, `CLES_IMMUABLES_DEBAT`,
`CLES_SYNTHESE`, `CLES_CLOTURE`, `CLES_INVITATION`, `GESTES_INVITATION`, `VERS_LE_CONTACT`, `NATURES_INVITATION`,
`CHAMPS_PSEUDO`, `CHAMPS_DE_LA_PERSONNE`, `LIENS`, `CREES_PAR`, `CLES_ENTETE_NOEUD`, `DECLARE_MAX`, `VERDICT_MAX`,
`LIBRE_SERVICE` (natures), `POIDS_GESTES`, `POSTE_PAR_TYPE`, `ROLE_PAR_TYPE`, the `engage_depuis` exception in
`bee publier --redater`. A key missed in `CLES_IMMUABLES_DEBAT` makes an immutable field mutable; in `CHAMPS_PSEUDO` it
skips the login-case check; in `CHAMPS_DE_LA_PERSONNE` it keeps a person's data after a refusal. The syntax-tree proof
(P1) already fails if a literal of the map is left in French; this test also fails if a set gains or loses a member.

## 4. Immutability checks and how the one-time migration passes them honestly

### 4.1 What would see a rename or a move as forbidden

`git diff --no-renames` shows a moved file as a deletion plus an addition, and a renamed key as a changed value. The
following rules then refuse, several of them **even for the council**:

| Check | Where | Council exempt? | What the switch looks like to it |
|---|---|---|---|
| A debate is never deleted, even closed | `verifier_debat` (`exiger(False…)`) | no | `debats/D-*.yaml` deleted |
| Closed debate receives nothing; immutable keys (id, invitation, question, question_caviardee_pour, ouvert_par, ouvert_le) | `verifier_debat` | no | every key « changes » (old key absent, new key present) |
| Arguments append-only, only `doublon_de` may be added | `verifier_debat` | no | every argument « modified » |
| An added debate is dated now and numbered after the base's | `verifier_debat`, R-d | no | 23 debates « opened » with old dates |
| A vote is never withdrawn; only its voter writes it | votes branch | no | (no vote on main today; any vote at switch time would be « deleted ») |
| A measurement is neither changed nor moved | measurements branch | no | (none on main today) |
| A report is neither changed nor withdrawn | reports branch | council or guardian | (none today) |
| Notes, reviews, lifts append-only | tasks and contributions branches | partly (a task whose council-only key changes goes to « gouvernance » before the note check) | every note « rewritten » |
| A contribution is born with exactly `CLES_NAISSANCE`, in review, numbered next | contributions branch | no (born rules) | 77 contributions « born » integrated with verdicts |
| A created task's reservation is dated at the PR | tasks branch (`probleme_date_pr`) | no | a reserved task moved = « created » with an old date |
| The do-not-contact list is never deleted, append-only | `verifier_invitation` | no | (none today) |
| Invitation gestures append-only | `verifier_invitation` | no | (none today) |
| Removals file: one entry per PR, as bee writes it | `verifier_retrait` | — | (none today) |
| Personal-data detectors on every added text | `textes_personnels` | refusals: no | every historical text « added » |
| Login case: a pseudo newly written must match its file | `pseudos_mal_ecrits` | no | every login « newly written » under a new key |
| Who is who, agent accounts, reserved logins, read **from the base** | `qui_est_qui`, `agent_accounts`, `reserved_pseudo` | — | the new tool reads new paths in an old base: no council, no agent accounts |

### 4.2 The migration mode of the gate (superseded by section 13: not built)

The gate gets an explicit third case beside « ordinary PR » and « refused »: **migration**, entered only when the base is
in the old layout and the head in the new one (layout read from both trees by the presence of the mapped folders; a tree
with both, or a head half-migrated, is refused). In migration mode `check-pr`:

1. **Reads the map and the translation code from the base** (L0/L1 put them on main first), never from the PR.
2. **Proves the data is exactly the translation** (proof P2, same function as `bee check-migration --base B --head H`):
   for every file of the data families at the base, the head holds `map_path(f)` and nothing at `f`; its bytes equal
   `translate_text(base bytes)`; `inverse(head bytes) == base bytes`; parsing both gives the same values once keys and
   enumerated values are mapped, and the multiset of every leaf (numbers, dates, shas, logins, free texts) is equal;
   no other data file is added, removed or changed; the per-family file counts are equal. Prose is never touched by the
   translator, so no new text can enter: this is why the personal-data detectors need not run again on moved texts.
3. **Runs the ordinary per-file rules on (translated old, new) pairs as modifications** (`statut_git = "M"`): every
   immutability and append-only rule of 4.1 then compares like with like and must find no change (a debate's question,
   an argument, a vote, a note, a review are equal). The rules are not skipped; they are shown to hold.
4. **Reads who is who from the base at the old paths, translated** (council, guardians, agent accounts, reserved logins),
   and requires the author to be a council member acting from his own account (the switch renames authority files).
5. **Marks the PR `migration`**, a nature outside `LIBRE_SERVICE`: fusion-auto never merges it; the human council does.
   Main's fusion-auto (the old tool) sees deletions of authority and debate files and refuses outright, which is also
   correct.

Code, workflow, schema and doc files in the same PR are judged as today (tooling or governance, council only) and are
reviewed through the syntax-tree proof P1 and the full suite. After L5 the migration mode is dead code (main is never in
the old layout again; validation takes the merge commit's first parent as base); L8 removes it.

Before merging, the council also runs **main's** `bee check-migration` (from L1) on the PR and pastes its summary in the
PR: the verification is done by reviewed code already on main, not only by the PR's own code.

### 4.3 History readers: follow the move, translate old versions (superseded by section 12, change 1)

The tool reads git history to date gestures by the merge that brought them (the declared dates are the author's):

| Reader | Used for | Without move-awareness, after the switch |
|---|---|---|
| `heure_de_fusion`, `soumission_effective` | start of R3's window, race bounds (96/120 h), race order « oldest submission first » | every contribution in review at the switch (six today) restarts its R3 window, and a race between two of them is ordered by id instead of by submission (unfair) |
| `fins_d_engagement`, `fermetures_sans_integration`, `reprise_refusee` | R7: who left a task and when (no re-take within 24 h) | a release just before the switch is invisible: a fresh 72 h by release-and-retake (fail open) |
| `creations_recentes` | 24 h caps on proposed tasks, proposals, invitations, reports | every file counts as created at the switch: caps hit for 24 h (fail closed) |
| `DatesDeFusion` (cap, essaim, site) | R11 heading over 14 days, swarm | every gesture of the window dated at the switch |
| `publiee_le` | R13: 72 h of publication before a guardian's agreement | delayed (no invitation today) |
| `exiger_reprise_permise`, `lire_versions` | R7 before writing | as R7 |

L1 changes these readers once: a history query for a new path also asks git for its old path (inverse map); an
« added » commit that, in the same commit, deletes the old path with translatable content is a move, not an add, and the
reader continues on the old path; a version read at an old path is translated before its gesture keys are taken
(`cle_note` reads `by`, `at`, `text`). `CHEMIN_HISTORIQUE` accepts old prefixes for reading only. No SHA is hard-coded
(a squash merge's SHA is not known in advance). Proof P5 builds a git repository from the frozen fixture with a sequence
of reservations, releases, submissions, notes and arguments, applies the migration commit, and requires every value of
the table above to be equal before (old tool, old tree) and after (new tool, new tree). The translation stays until L8,
which removes it only if P5 shows that no rule still reads history older than the switch (14-day heading window, no
contribution from before the switch in review).

### 4.4 Other one-time effects to handle

- **Line wrapping.** English keys change line lengths (`hors_perimetre:` → `out_of_scope:`). For files bee rewrites in
  a canonical form (debates by `CLES_DEBAT` order, invitations, incidents, removals), the migrated bytes must equal what
  the new writer produces, else the first robot write after the switch rewrites the file and looks like a modification.
  P2 checks `render(parse(new)) == new` for those families.
- **Waiting engagement PRs.** `bee publier` finds its waiting PR by a branch named from a hash of `{task path:
  engagement}`: an engagement PR opened before the switch is not found by the new tool. The freeze drains them.
- **Stale self-service PRs** fail safely: a PR modifying `taches/x.yaml` conflicts with the deletion (fusion-auto: « conflit
  », code 3); a PR adding a new file under `taches/` is refused by R-q.
- **The council's pseudo `conseil`** (cree_par of 175 tasks) is compared by code (R8 bootstrap: tasks of category
  « ruche » created by « conseil »): it becomes `council` in the data and the code in the same PR, and both names stay in
  `reserved_logins` (bee valider requires the council's name there).

## 5. Where bee parses French text in markdown (the bilingual readers of ruche-0055)

| Reader | Today | After |
|---|---|---|
| Tree node sections (`SECTIONS_NOEUD` / `_EN`), one language per node | both accepted | nodes written in English by ruche-0066/0067; L8 drops the French reader (a format, not a refusal) |
| Node front matter keys (`parent`, `mis_a_jour`, `entretenu_par`, `budget_lignes`) | French only | renamed in L5 with the tree move (names) |
| Children line `- \`id\` : …` (`ENFANT_NOEUD`) | regex allows both typographies | unchanged |
| Root node's vulnerability line kept under `--budget` | `- Une faille`, `- A vulnerability`, `- Vulnerability`, `- **Vulnerability**` | keep all while a node may be French; L8 keeps the English forms |
| Debate link in docs/questions-ouvertes.md (`LIEN_DEBAT`), numbered questions (`QUESTION_NUMEROTEE`) | `Débat :` or `Debate:`; written in French by import-questions | writer English in L7; default source docs/open-questions.md (L2); L8 drops `Débat :` once the file is English |
| Placeholder `À REMPLIR` / `TO FILL IN` in manifests | both refused; bee manifeste writes French | bee manifeste writes `TO FILL IN` (L7); **both stay refused forever** |
| The data frame around member texts (`DEBUT_DONNEES`, `FIN_DONNEES`) and the refusal of an imitated frame (`MARQUE_ENCADRE`) | French frame; refusal of the French imitation | translated in L7 together with a refusal of an imitated frame in **both** languages (ruche-0069's note of 1 Nov) |
| docs/decisions.md: a decision found by its date; header separator; record-merge appends rows | language-neutral | unchanged; new rows in English |
| Personal-data detectors (streets, phone words, `arobase`/`at`, elisions) | both languages | keep both forever |
| CI verdict word in verdict.json | verte, vert, green, success, succes, succès | keep accepting all; record `green` |
| R13 mention and request phrases (outgoing text to a person) | fr and en | keep both; default `en` |

The inventory script `outils/inventaire_marqueurs.py` (→ `tools/marker_inventory.py`) already classifies every French
literal the tool compares text against; L1 extends it with a `--names` mode that lists every name literal (921 today) and
fails if one is neither in the map nor declared language-neutral, so the map is proved complete against the code.

## 6. The forks

What they read from the registry is listed in english-names.md section 6. In short: **unpinned (main)**: the tool and its
requirements, `verifier-fork` and its options, `taches/**`, the task keys `type`, `metrique`, `sortie_compressee` and their
values, `projets/libyaml.yaml` and its `metriques`; **pinned by SHA (juge-v2, dab13a6)**: juge.yml, juge.py, isoler.sh,
the judge image, the artifact « juge », the workflow's inputs and outputs.

- **F1 (before L2), one PR per fork, reviewed by the council (the PR modifies the fork's judges):** `bee/ci/tache.py`
  finds the task under `tasks/` or `taches/`, reads `type`/`metric`/`compressed_output` or the French keys, maps the
  English values to its internal French ones (optimization → optimisation, measurement → mesure, split → decoupage,
  identical → identique, may_change → peut_changer); libyamlBee's reads `projects/` or `projets/` and `metrics` or
  `metriques`; `manifeste.sh` runs `tools/bee.py` or `outils/bee.py`, and `check-fork --task --head --repo --author` or
  the French command and options; `bee-ci.yml` installs whichever requirements file exists. F1 also reads the manifest
  in both forms, because `bee manifest` writes English from L5 on: `manifests/<task>.yaml` or `manifestes/<task>.yaml`
  (manifeste.sh's diff filter and name check, the bee-ci.yml step that keeps the manifest), key `task` or `tache`
  (tache.py), `metric`/`measurements.before` or `metrique`/`mesures.avant` (verdict.py's gain fallback). Tests in
  `bee/ci/` cover both layouts. The open fork PRs (minizBee #13, #15, #18: miniz-0018-c1, miniz-0017-c1, miniz-0029-c1 in review) must
  then be rebased, as after any change to `bee/` (their own bee-ci.yml runs, and the old one would fail on `outils/`).
- **Boundary adapters in the registry (L5):** `check-fork` and `record-verdict` read a manifest whose keys are all
  French or all English (mixed: refused), from `manifests/<task>.yaml`, else `manifestes/<task>.yaml`, else
  `CONTRIBUTION.yaml` (two of them for one task: refused); `record-verdict` reads verdict.json in either vocabulary,
  one per document; metric ids stay French in both repos until wave 2. All of it until date D, a constant of the tool.
- **Judge track (after L5):** J1 publishes judge-v4: the judge's code in English (identifiers, CLI options, juge.json →
  judge.json keys, artifact « judge », workflow inputs `head_sha`, `history`, `no_instructions`, outputs), **accepting
  both the French and the English plugin contract** (`bee/juge/projet.py` or `bee/judge/project.py`; CORPUS, METRIQUES,
  CONSTRUIRE… or their English names), because the plugin is read from the fork's base and the PR that bumps the pin is
  judged with the old plugin. If a ruleset protects `juge-v*` tags, it must also cover `judge-v*`; bee accepts `juge-v[1-3]` and `judge-v[4-9]…` and
  compares the number (`common_judge_min`).
- **F2 (after J1):** each fork bumps to judge-v4 (paths, options, inputs, artifact name in the same PR), then writes
  English: verdict.json keys and values, metric ids (with a registry PR L5b that renames metric ids in projects, tasks and
  records with the same proofs), plugin names (manifests are already English, written by `bee manifest` since L5);
  removes F1's fallbacks. Fork-internal names (bee/ci step files, `etat-*` artifacts, job names, env vars)
  are the forks' own plan (miniz-0045, miniz-0046, libyaml-0019, re-scoped).
- **J2** (judge-v5) drops the French plugin contract once both forks have renamed theirs.

## 7. The pull requests, in order (superseded by section 13: one switch; section 7.1, the freeze, still applies as amended there)

Sizes: « hand » is the hand-written diff the reviewers read line by line (target ≤ 400 lines, as ruche-0069 asked);
« script » is regenerated by the committed script and reviewed through its proofs. Estimates measured on 403fdc5.

| Layer | Content | Size | Proofs | CI green after merge because… | Merged by | Needs | In parallel with |
|---|---|---|---|---|---|---|---|
| **L0** map and decision | docs/english-names.md, `outils/migration/names.yaml`, a docs/decisions.md row recording the decision, the no-alias rule and the open questions' answers; ruche-0069/0070 closed as replaced, the execution tasks of this plan created | docs + data | map lints: one-to-one per family, every name of `dump_cli.py`, of the schemas and of the `--names` inventory covered | no code | council (founder) | — | — |
| **L1** migration tooling, dormant | `outils/migration/`: `rename.py` (data translator with inverse, code literal and identifier renamer, YAML-in-string support for tests), `same_ast.py`, `check_cli.py`, `test_rules.py`, `test_history.py`, `test_outputs.py`; gate migration mode; move-aware history readers; `bee check-migration`; retired-names guard (empty list); renamed-command refusal (empty table); `--names` inventory | hand ≈ 900 lines, split in L1a (translator, proofs) and L1b (gate mode, history readers), each with an independent adversarial review | each mechanism exercised on a toy map (e.g. a test folder renamed) in the full suite | everything is inactive on the real map; full suite | council | L0 | F1 |
| **F1** forks read both layouts | section 6, one PR per fork; then the open fork PRs rebase | hand ≈ 250 lines per fork | fork tests on both layouts | the registry has not moved | council | L0 | L1 |
| **L2** code and docs folders and files | `outils/` → `tools/` (bee.py stays; juge → judge, repetition → rehearsal, file names inside), `docs/*.md` names, `REGLES.md` → `RULES.md`, `UTILISATEURS.md` → `USERS.md`, `MAINTENEURS.md` → `MAINTAINERS.md`, French copies per Q2, skill folder, issue template; path literals in code, workflows (`python3 tools/bee.py`, `tools.test_bee`, juge-commun.yml filters), docs, AUTHORITY_FILES and CHEMINS_OUTILLAGE (old names kept in AUTHORITY_FILES), `projets/ruche.yaml` judge paths, open tasks' `fichiers`; GitHub label renamed | script ≈ 250 path lines in 64 files + moves; hand ≈ 150 | P1 (path literals only), P4 | the base-tool steps fail closed to full once; the gate passes in ordinary mode (council, tooling) | founder's own account (authority docs) | F1 merged, fork PRs rebased | — |
| **L3** command line | 58 subcommands and 88 options renamed in the parser and in every caller (workflows, rehearsal scripts, tests, docs, skill, tree nodes, AGENTS); `args.<dest>` attributes; the renamed-command refusal table filled | script ≈ 1,500 lines (tests, docs); hand ≈ 200 | P3 (parser tree modulo map: same handlers, actions, nargs, required, defaults, choices), P1, test count does not drop | callers change in the same commit; forks fall back (F1); base-tool steps fail closed once | council | L2 | — |
| **L4** workflows | `name:` of every workflow with the three `workflow_run` listeners in one commit; file renames (fusion-auto → auto-merge, integration-auto → auto-integration, juge → judge, juge-commun → judge-meta-tests); job ids except `valider`; a new job `validate` identical to `valider`; concurrency groups (`ecriture-main` in both files at once); step names with the tests that name them; robot commit messages, PR comment, notices; `BEE_NOW`, `BEE_REGISTRY` (old refused), `BEE_SIM*`, `BEE_JUDGE_*`; `bee en-attente` JSON keys with the two workflow one-liners that read them | hand ≈ 350 lines | workflow tests (names tied, `${{` never in run, permissions), P1 | listeners and names change together (a PR whose validation ran under the old name during the merge needs a re-run to be auto-merged); `site.yml` and `suite.yml` keep their file names (dispatched by name; main-green reads suite.yml's runs) | council | L3 | — |
| *ruleset swap* | admin makes `validate` the required check instead of `valider`; any tag protection of `juge-v*` extended to `judge-v*` | settings | — | both jobs ran on every PR since L4 | founder (admin) | L4 | — |
| **L5** data switch (freeze) | all data folders, schema file names and properties, keys and enumerated values of tasks, contributions, debates, proposals, members, votes, measurements, invitations, reports, governance, projects, categories, bee.yaml, tree (`tree/`, `MEANING.md`, node ids `root`, roles, categories), templates; the frozen fixture and test literals; site paths and JSON keys; `conseil` → `council`; dynamic keys and `issue` by hand; boundary adapters (French fork documents until D); retired-names guard filled; history readers and migration mode activated by the map; job `valider` removed | script: ≈ 380 data files (198 tasks, 77 contributions, 23 debates, 3 proposals, 7 projects, governance, 18 tree nodes, 25 fixtures), ≈ 1,700 lines of bee.py, ≈ 3,100 of test_bee.py, ≈ 100 of site_bee.py; hand ≈ 400 | P1, P2, P4, P5, P6 (every read-only command's output equal modulo map), P7; main's `bee check-migration` summary in the PR | atomic: code, data, tests and workflows read the same names in one commit; forks read both (F1); robots paused during the merge, resumed on the new tool | founder's own account (authority files, migration mode) | ruleset swap | — |
| **L6** identifiers | Python names of bee.py, site_bee.py, the judge (judge-v4's code), the rehearsal kit and tests: functions, classes, constants, variables, attributes (`Registre` → `Registry`, `verifier_pr` → `check_pr`…) from a generated, reviewed identifier map | script: most lines of every file; hand ≈ 50 | P1 with the identifier map (same tree once names are mapped), full suite | no behaviour change | council (independent adversarial review: the gate's code) | L5 | — |
| **L7** prose (several PRs) | bee's messages and help in PRs of ≤ 400 changed lines, ordered around open branches, with an independent adversarial review for the gate, the rehearsal guards, fusion-auto and verdicts (ruche-0069's criteria: exit codes and stderr unchanged, outputs that tools read untouched, test diff in literals only, assertions not fewer); docstrings and comments; emitted markers (`TO FILL IN`, the frame, `Debate:`); site labels; then the existing prose tasks re-scoped: front door, skill and site, rules, docs in seven parts, tree in two parts, role instructions (the founder merges), templates and schema descriptions, open tasks in eight batches; projects', categories' and governance's descriptive prose | hand, each ≤ 400 lines | P1 restricted to message literals (no name literal changes), test counts | behaviour unchanged | agent principal by delegation for docs; council for gate-related messages, rules, authority texts; founder for role instructions | L5 (L6 for messages in code) | prose PRs on different files run in parallel |
| **J1** judge-v4 | section 6 | hand ≈ 300 | test_juge meta-tests with both plugin contracts | forks pinned to juge-v2 are untouched | council | L6 | L7 |
| **F2** forks write English | per fork: bump to judge-v4, English manifests, verdict.json, metric ids, plugin names, drop F1 fallback; registry **L5b** renames metric ids (projects, tasks, records, boundary map) with P2/P5 | hand ≈ 300 per fork; L5b script ≈ 300 data lines | fork tests; P2 | registry accepts both vocabularies until D | council | J1 | L7 |
| **L8** contraction (after D, and three months for the refusal table) | remove: French fork-document adapters, `manifestes/`, `CONTRIBUTION.yaml`, migration mode, history translation (if P5 shows nothing reads before the switch), renamed-command refusals, French format readers of 5; J2 (judge-v5) | hand ≈ 300 | full suite; P5 rerun | nothing reads the removed forms any more | council | D passed, F2 done | — |

### 7.1 The freeze for L5 (about an hour)

1. Announce it a day ahead; merge or close every open self-service PR and every `bee/engagement-*` branch (an engagement's branch name hashes
   its keys, which the switch renames, so one left open would not be found again); check no
   vote, measurement, invitation or report file exists or, if one does, that P2 covers it.
2. Disable auto-merge, auto-integration, verdicts and expirations (`gh workflow disable`): nothing writes main.
3. Regenerate the data part from current main with the committed script, push it to the PR branch, run main's
   `bee check-migration` and paste its summary, wait for the required check and the full suite.
4. The founder merges from his own account.
5. Re-enable auto-merge, verdicts, auto-integration, expirations, in that order; watch one run of each and the next CI
   run of a fork PR (F1's reader on the new layout).
6. Record the merge in docs/decisions.md (the date fixes D: the merge date plus six weeks, already in the tool as a
   constant written by the L5 PR, at the earliest 2027-01-01).

### 7.2 Human or admin steps outside the repository

Ruleset required check (`valider` → `validate`, between L4 and L5); tag protection for `judge-v*` if `juge-v*` has one; the GitHub label
`proposition-tache` → `task-proposal` (L2); disabling and re-enabling workflows (L5); no secret is renamed
(`BEE_INTEGRATION_TOKEN` is English).

## 8. What stays as written, what migrates

| Stays as written (history) | Migrates (the tool must read it) |
|---|---|
| Prose of closed tasks (title, context, criteria, out-of-scope items, notes' texts), including the paths they mention | Every key of every file, closed or open (the tool reads closed records for levels, rankings, the heading, races, R7, bee valider's schemas) |
| Contributions' summaries, decision reasons, review reasons, declared texts | Every enumerated value (statuses, types, opinions, outcomes, positions, areas, levels, roles…), closed or open |
| Debates' questions (immutable by rule), arguments (append-only), syntheses (a rapporteur may write a new English one) | Path values the tool reads: tasks' `node`, projects' `judge_paths` and `paths_not_counted`, the guarantors' `brief` |
| Proposals' texts and results; docs/decisions.md rows; commit messages, PR titles and bodies; tags juge-v1..3 | Open tasks' `files` and `out_of_scope` path values (live instructions; `check-fork` warns on files outside them); their prose goes to the translation batches |
| Notes written by robots (« Réservation de X expirée… ») | The council's pseudo `conseil` → `council` (compared by code); tool-written whole-value markers (`[retiré]`, « retiré : refus ») where they exist |
| The forks' merged manifests in `manifestes/` on their master (fork history) | Fork documents in review: read in either vocabulary until D, then must be re-pushed |
| Logins and task, contribution, debate, proposal ids | Folder and file locations (folders only; file names are ids) |

## 9. The committed scripts and checks (L1)

- `tools/migration/names.yaml`: the map (sections of english-names.md), with per-family scopes for keys and values, the paths,
  the commands and options, the identifiers (L6), the retired names, date D.
- `rename.py apply|check|inverse`: data translation at the text level (key tokens at line starts, enumerated values in
  known positions, path values in known keys), keeping order, quoting, comments and wrapping except where a canonical
  writer applies; code literal renaming by syntax tree (whole literals in mapped roles, YAML inside test strings);
  identifier renaming (L6).
- P1 `same_ast.py`: for each changed `.py`, old and new trees are equal except names and string constants that map
  exactly through the layer's maps; f-string literal parts likewise; numbers, operators and structure identical; prints
  the count of each mapping applied; any other difference fails. A prose layer may change only message literals that
  are not names.
- P2 `rename.py check`: section 4.2 point 2.
- P3 `check_cli.py`: the parser trees of the old and new tool, from `construire_analyseur()`, equal modulo the map.
- P4 `test_rules.py`: section 3.1.
- P5 `test_history.py`: section 4.3.
- P6 `test_outputs.py`: `list`, `heading`, `swarm`, `ranking`, `levels`, `debates` with `--json`, `show`, `context`, the
  site's `api/registry.json` on the frozen fixture: equal modulo the map before and after.
- P7: number of tests and assertions of test_bee.py and test_juge.py does not drop (ruche-0069).

## 10. Open questions (only real choices), with a recommendation

1. **The project id `ruche`** (140 task ids `ruche-NNNN`, contribution ids, `contributions/ruche/`, the category, the tree
   node `projects/ruche/ruche`, cited in code comments, commit messages and decisions). Rename to `hive`? **Keep `ruche`**:
   it is the proper name of the place (La Ruche, which stays), ids are identities cited in immutable history, and a rename
   would rewrite every reference without making anything clearer.
2. **French copies of authoritative texts** (COMMANDEMENTS.md today; AGENTS.fr.md and REGLES.md as a « French
   translation » in ruche-0056 and ruche-0058). **Remove them** (git keeps them): no French-speaking participant, two texts
   drift, and the forks' links are fixed by their prose tasks; keep the old names in AUTHORITY_FILES and in the retired
   names. If the founder wants a reference copy, `COMMANDMENTS.fr.md`, marked non-authoritative, council-only.
3. **Metric ids and the other formats the forks produce**: in L5 or with the forks? **With the forks (F2 + L5b)**: they
   are emitted by fork code (benches, plugins, verdict.py) read at the PR's base; renaming them alone in the registry
   would make every gain unreadable (no R4).
4. **Path values in closed tasks**: rewrite them too? **No**: they describe what was done then; only keys, values and the
   path values the tool reads migrate. Open tasks' file lists do migrate.
5. **Judgment-call names** the council should look at in L0: `cap` → `heading` (English « cap » already means plafond),
   `poste` → `area`, `portee` → `impact`, `ecartee` → `set_aside` (contributions and invitations alike), `pseudo` →
   `login`, `prendre` → `take`, `proposer` → `propose` (rules, beside `propose-task`), `depouiller` → `tally`, `signalement` → `report` (and `rapporteur` kept, to avoid
   « reporter »), `raison` → `cause` beside `motif` → `reason`, `contribution.schema.json` → `manifest.schema.json` with
   the record schema as `contribution-record.schema.json` (never reusing an old file name for another content in the
   same move). **Recommendation: accept as mapped**; changing one later costs another switch.
6. **The judge's tag prefix**: keep `juge-vN` or continue as `judge-v4`? **`judge-v4`**, with bee accepting `juge-v1..3`
   and `judge-v4+` only (a `juge-v4` or `judge-v2` is refused), so that both prefixes never denote the same number.
7. **The required check**: rename `valider` or keep the id? **Rename in three steps** (L4 adds `validate`, the founder
   swaps the ruleset, L5 removes `valider`): no window where PRs wait for a check that never comes.
8. **Bilingual format readers after the move** (tree sections, `Débat :`): **drop them in L8**, once the tree and the
   questions file are English (one language); keep forever the bilingual refusals and detectors (À REMPLIR, frames,
   personal data, CI words), since dropping a refusal would narrow a check.
9. **History translation after L8**: keep it permanently (cheap; history never changes) or remove it? **Remove it only
   if P5 shows that no rule reads history older than the switch** (heading window passed, no pre-switch contribution in
   review); otherwise keep it.
10. **Date D**: **L5's merge plus six weeks, at the earliest 2027-01-01**, and not before both forks have merged F2 and
    every fork PR in review has a verdict in English; set as a constant by L5, moved only by a council PR.

## 11. What happens to the existing tasks

ruche-0069 and ruche-0070 are closed as replaced by this plan (their criteria are carried over: command table generated
from the parser; inventory by file; ≤ 400 changed lines per hand-made task; aliases dropped with reason; the attention
test on messages tools read; adversarial review for the gate; one-to-one tables generated by script; every path rule
with its new form and a test; mixed documents refused; adversarial review of this plan). The execution tasks are the
layers L1 to L8, F1, F2, J1, J2, L5b, each with the proofs above as acceptance criteria and its dependencies.
ruche-0056 to ruche-0068, ruche-0071 to ruche-0079, miniz-0045, miniz-0046 and libyaml-0019 become L7 and the forks'
prose, scheduled after L5 so that translators write the final names; ruche-0056 and ruche-0058 lose their French copies
if question 2 is answered as recommended. This plan itself should get the independent adversarial review that
ruche-0070 required before L0 is merged.

### 11.1 The tasks (as revised by section 13)

| Step | Task | Depends on |
| --- | --- | --- |
| 1a. The scoped map and the data translator (P2), dormant | ruche-0141 | — |
| 1b. The code renamer and its proofs (P1, P1b a and b, P3, --names), Python outside tests, dormant | ruche-0142 | ruche-0141 |
| 1b-2. The test files' identifiers, the shell scripts and the workflows (P1 for them) | ruche-0152 | ruche-0142 |
| 1c. P1b (c), the gate's path rules (P4), the outputs (P6), `bee check-migration` and its workflow | ruche-0143 | ruche-0142, ruche-0152 |
| 1d. The switch script, a dry run on a copy of main with the translated full suite, change 10, the judge's interface with the forks | ruche-0153 | ruche-0143 |
| Settings fail closed (before the switch) | ruche-0144 | — |
| The forks read both layouts (before the switch) | miniz-0049, libyaml-0020 | — |
| 2. The switch: every name in one commit, during a freeze | ruche-0145 | ruche-0143, ruche-0153, ruche-0144, miniz-0049, libyaml-0020 |
| 3. bee's messages, help and site | ruche-0146, ruche-0147 | ruche-0145 |
| 3. Prose (existing tasks, rescheduled) | ruche-0056 to ruche-0068, ruche-0071 to ruche-0079, miniz-0045, miniz-0046, libyaml-0019 | ruche-0145 |
| 4. judge-v4 | ruche-0148 | ruche-0145 |
| The forks write English | miniz-0050, libyaml-0021 | ruche-0148 |
| 5. Metric ids | ruche-0149 | ruche-0145 |
| 6. Remove the temporary bridges after date D | ruche-0150 | ruche-0149, miniz-0050, libyaml-0021 |

ruche-0069 and ruche-0070 are closed as replaced by this plan.

## 12. Changes after the independent review (8 November 2026)

An agent of another model reviewed this plan against the code and the forks. Its blocking findings and the council's
answers prevail over the sections above.

1. **No move-aware history readers, no P5** (§4.3 superseded). Only the founder's own agents participate, so the freeze
   drains instead: every open reservation, parallel registration and race is closed, and the switch happens at least
   24 h after the last release or closure without integration. Accepted and recorded one-time effects: the 24 h caps
   count every file as created at the switch, for one day (fail closed); the R11 window counts the switch as one day of
   gestures (informative); `perime_a_l_envoi` falls back to the current debate for an invitation sent before the switch
   (none exists). R3 is unaffected: `contributions/` keeps its path, so the merge that brought a submission is still
   found. `deja_nommes` (who has been on the council or a guardian) is fixed for good in L5 with the old and new paths in
   its pathspec. A test pins that no other reader asks for a path older than the switch. This change is revisited if an
   outside participant exists before L5, or if a second rename ever happens.
2. **Residue proof P1b.** P1 proves only that what changed changed through the map. P1b scans every string literal and
   identifier of the new tree for any retired token; each hit must be on an explicit keep-list (closed history, the
   retired-names guard, old names kept in AUTHORITY_FILES). Every string given to `getattr`, `setattr`, `vars` or used
   as an attribute name is resolved against real attributes and parser destinations. "Non-empty family" assertions: on
   the migrated fixture, `validate` and every scanner (council-file checks, removal on request, loaders, globs) find the
   same file counts as before the move. Part of L1a.
3. **Settings fail closed** before L5 (task ruche-0144): every bee.yaml key the tool reads is required, an unknown key is
   refused, and a missing or malformed value never means the permissive one. The audit of every `config.get(key,
   default)` is in the PR.
4. **The forks: F1 covers every registry name they read**, including the task copy their verdict scripts read (the main
   metric), the manifest folder in their R1 exclusions (`manifests/**` beside `manifestes/**`), the global
   `--registre` option and `BEE_REGISTRE`. In the registry, L5's boundary adapters also check a fork verdict's metric
   against the task's.
5. **The council files' strict check** (`problemes_textes_du_conseil`: bee.yaml, categories.yaml, projets/*.yaml,
   gouvernance/**) joins the path rules of §3.1 (row R-u): a missed glob would leave council files unchecked. Every glob
   literal is covered by P1b's non-empty assertions.
6. **P2 by family.** Debates, invitations, incidents and removals are re-rendered by their canonical writer and must
   equal it; tasks, contributions and other hand-wrapped files are translated at the text level; tree nodes are Markdown
   whose node ids (front matter `parent`, children lines, tasks' `noeud`) change, with a Markdown-aware rule. The family
   list is exhaustive: every tracked file of the base is either translated by a family rule or on an explicit
   hand-change list, so nothing (bee.yaml values included) changes unnoticed.
7. **The map is scoped.** L1a generates `names.yaml` per schema and per file family, so the inverse is a function per
   family and the lint runs per family (today's flat list maps `ouvert_le` and `ouverte_le` to one name, and `comptes`
   to an existing `accounts`). Role-dependent tokens are listed for hand treatment: `issue`, `signalement`,
   `contribution` and `enregistrement` (also schema names), and the `ecart-` family. The map also gains every key of the
   tool's JSON outputs (`--json` of swarm, heading, ranking, levels…) and of the site's `api/registre.json`.
8. **Names changed by the council**: `cap` → `balance` (not `heading`, which already means a Markdown heading in the
   tree code), `portee` → `reach`. The rest of the map's judgment calls (§10, question 5) are accepted.
9. **Workflows' inline Python** (`python3 -c 'import bee; bee.…'`) is tested: every `bee.<attribute>` named in a workflow
   must exist in the module (L2 changes `PYTHONPATH`, L6 the attributes, in the same commit as their callers).
10. **No silent no-op.** A test scans workflows, scripts, docs, tree nodes and the skill for old command names; the
    renamed-command refusal prints a GitHub `::error::` line as well, and finds the subcommand through the real parser
    (never by scanning tokens, so `--texte prendre` is not caught).
    Council, 9 November 2026: for that scan to pass, the switch renames `bee <command>` and its options inside code spans
    and code blocks of docs, tree nodes, the skill and AGENTS.md (names, not prose), through a hand rule in names.yaml that
    P2 checks; prose waits for its own tasks (ruche-0153).
11. **Migration-mode entry** keys on files that exist (P2's file set over `taches`, `debats`, `propositions`, `projets`,
    `gouvernance`, `arbre`, `modeles`), never on empty folders git does not track. P4's corpus includes every tracked
    top-level path (REGLES.md, bee.yaml, CLAUDE.md, AGENTS.en.md, categories.yaml), none of which may newly match the
    tooling paths. AGENTS.md becoming the English text makes its English content proposable by a member, as AGENTS.md is
    today: recorded.
12. **The freeze also covers** the scheduled agent sessions (la Nuit des abeilles and any reminder that calls `bee` by
    name: their prompts are updated by the council), installed copies of the skill, local clones' session state
    (`.git/bee-session`, `bee-publier.json`), `BEE_REGISTRE` in shell profiles, and the rebase of the open fork PRs.
13. **French copies.** COMMANDEMENTS.md is a translation, not a commandment: removing it changes no commandment
    (commandment 11). L2 records that AGENTS.md, RULES.md and COMMANDMENTS.md are authoritative in English, and adds
    AGENTS.en.md to the retired names.

## 13. One switch instead of eight layers (the founder's choice, 8 November 2026)

Asked whether to rebuild the project from scratch in English or to translate it, the founder chose to translate, in a
single switch rather than the layers L2 to L6 of section 7. This section prevails over everything above it.

- **Why translate rather than rebuild.** The registry's value is its hardening: some seventy integrated tasks and dozens
  of adversarial reviews of the gate, the judge, identity and invitations. A rewrite would reopen holes already closed,
  and cost more than a translation. The new vision's core (self-governance) is what the code already does. A new
  repository would add nothing and break the links to the history.
- **Why one switch.** Only the founder's own agents use the hive today, so a short freeze costs nothing; one commit is
  easy to revert; it removes the gate's migration mode (L1b), the staged fail-closed windows of L2 to L4, and most of
  the temporary bridges. The price: the commit is too large to read by eye, and is trusted through its proofs (P1, P1b,
  P2, P3, P4, P6) and the full test suite instead. This would no longer be acceptable once the hive is open: now is the
  time.
- **The steps.** (1) ruche-0141, ruche-0142, ruche-0152, ruche-0143 and ruche-0153 build the scoped map, the translators, the proofs, `bee
  check-migration` and its workflow, dormant, with a dry run of the whole switch on a copy of main; ruche-0144 makes the
  settings fail closed; miniz-0049 and libyaml-0020 make the forks read both layouts, and the open fork PRs are rebased.
  (2) ruche-0145: during a freeze (section 7.1 and
  section 12, change 12), the script regenerates the whole switch from current main: paths, commands, workflows, data,
  tree, schemas, tests, site and Python identifiers; the hand-made part (boundary adapters for fork documents until
  date D, a fork verdict's metric checked against the task's, `deja_nommes` reading both paths, the refusal table and
  the retired-names guard) stays under 400 lines and has its own independent review. (3) bee's messages and the prose,
  in parallel PRs. (4) judge-v4, then the forks write English, then the metric ids. (5) After date D, the bridges go.
- **How the switch is merged.** In ordinary mode the gate refuses it, as it must (data files moved, keys changed):
  that refusal is expected and recorded, and must list only those reasons, never a retired name found in the new tree.
  In its place: `bee check-migration`, reviewed code already on main, asserts that the head is exactly the translation
  of the base and, explicitly, that debates and their arguments are equal modulo the map, that the council, guardians,
  guarantors and agent accounts are the same, that reserved logins are unchanged, and that every family keeps its
  (non-zero) file count; it also runs P1, P1b, P3, P4 and P6. The founder starts it himself, through a workflow on main
  (workflow_dispatch, with the PR number and head SHA), which posts its summary and the SHA it checked; the full suite
  passes on that head; and the founder merges **that same commit** from his own account, with a bypass of the required
  check limited to him. `validate` becomes the required check right after the merge. No gate migration mode is built.
- **The freeze, as amended.** Section 7.1 with section 12, change 12, and these changes: the robots (auto-merge,
  auto-integration, verdicts, expirations) stay disabled from the start of the freeze until after the founder's merge;
  the F1 fork PRs are merged and the open fork PRs rebased before the freeze starts; the push runs of site.yml and
  validation.yml are expected to fail closed to the full suite once.
- **Unchanged from the sections above**: the map and its decisions (section 10 and section 12, changes 7 and 8), no
  aliases, the forks' F1/F2 track, the accepted one-time effects of section 12, change 1, closed history kept as
  written, and date D (the switch's merge plus six weeks, at the earliest 1 January 2027).

## 14. The heading glossary (council, 11 November 2026)

The end of the migration translates the docs, the tree and the templates in parallel PRs. Other texts and bee's messages
link to some headings, so their English names are fixed here; every PR uses them.

| French heading | English heading | Anchor | Linked from |
| --- | --- | --- | --- |
| docs/contributions.md « Relire par commit » | Review by commit | `#review-by-commit` | balance.md, evaluation.md, guardians.md, reputation.md, tasks.md |
| docs/contributions.md « Travail en parallèle et contributions concurrentes » | Parallel work and competing contributions | `#parallel-work-and-competing-contributions` | the same, and a comment of tools/bee.py |
| docs/governance.md « Dossiers du libre-service » | Self-service folders | `#who-can-change-what-in-the-registry` (the table's row) | bee's messages (bytes_problem and the gate) |
| docs/balance.md « Le cap de la ruche (R11) » | The hive's balance (R11) | | |
| docs/balance.md « Les postes » | The areas | `#the-areas` | bee's messages, docs/agora.md |
| docs/agora.md « Contre le bruit » | Against noise | `#against-noise` | a docstring of tools/bee.py |
| Tree nodes « Pourquoi cette branche existe », « Ce qui compte ici », « Ce qu'on peut ignorer ici », « Enfants » | Why this branch exists, What matters here, What you can ignore here, Children (NODE_SECTIONS_EN) | | bee context, bee validate, the site |
| Their short forms « Pourquoi », « Ce qui compte », « À ignorer », « Enfants » | Why, What matters, To ignore, Children | | bee context |

Voice: precise, dry, generous with numbers, sparing with adjectives, no hype words, no exclamation marks, US spelling.
French stays only for La Ruche, la Nuit des abeilles, l'essaim and le miel, and for quoted data.
