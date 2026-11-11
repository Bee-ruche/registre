# Common judge: one isolated judge for every project (specification)

Status: version 3 in service since 2 November 2026, tag `juge-v3`; version 2 from 2 November 2026, tag `juge-v2`;
version 1 from 28 October 2026, tag `juge-v1` (merge decided by the council). The forks move to it through the tasks miniz-0032 (after miniz-0031 is integrated) and
libyaml-0005 (after libyaml-0002).

## The problem

minizBee's isolated judge (the fork's `bee/juge/`) mixes two things:
- **what protects** and depends on no project: the image and the isolation in a container, the
  `chrono` launcher (times read by the kernel, Valgrind's summary), the safe reading of outputs, the analysis of
  compiled objects, the seed drawn after the build, the A/B statistics, the report;
- **what judges miniz**: the harness that calls the library, the inputs (corpus, randomly drawn
  data, zlib streams), the verification rule (outputs identical to the base, round trip through
  the host's zlib), the scenarios and their metrics.

Copying the whole into each fork would make as many copies to fix as there are projects. The adversarial
review of 27 October showed it: a flaw in the judge is fixed once, or it stays open elsewhere.

## The split

| In the registry (`tools/judge/`, tagged `juge-vN`) | In each fork (`bee/juge/`) |
| --- | --- |
| `Dockerfile.base` (pinned image, common packages) and the isolation (`isoler.sh`) | The project's own packages (one `RUN` line added to the common image) |
| `chrono.c`: launcher, measurements through `wait4`, token, reading of Valgrind's summary | `execution.c`: the harness, which reads `entrees/liste` and writes `sorties/` |
| `lecture.py`: safe reading of outputs (no link, no special file, bounded size) | `projet.py`: the plugin described below |
| `analyse.py`: suspicious constructs (list of allowed functions supplied by the plugin) | The corpus and its generator (`bee/corpus/`) |
| `juge.py`: the orchestration (build A and B, analyze, draw the seed, verify, measure, instructions, report in `ab.py`'s format + a `juge` section) | The project's own meta-tests (malicious variants of the project's code) |
| The common judge's meta-tests (on a toy project) and the reusable workflow `juge.yml` (`workflow_call`) | The workflow call, pinned to a tag's commit: `uses: Bee-ruche/registre/.github/workflows/juge.yml@<commit> # juge-vN` |

## A project's plugin (`bee/juge/projet.py`)

A `Projet` class with no state of its own (it receives the options `--option KEY=VALUE` when it is created),
read by the common judge **from the PR's base** (never from the PR). Full, commented model:
`tools/judge/jouet/bee/juge/projet.py` (the meta-tests' toy project).

| Element | Role |
| --- | --- |
| `NOM`, `PAQUETS` | the project's name; packages added to the common image (one `RUN` line, names checked) |
| `SOURCES`, `SOURCES_REQUISES` | glob patterns of the project's files copied into the container and compiled (`miniz.c`, `src/*.c`…); any symbolic link is refused; the text analysis reads these same files, whole |
| `OUTILLAGE`, `EN_TETES_BASE`, `CONSTRUIRE` | folders of the base mounted on `/outillage`; headers of the base copied into `/outillage/base/` (the harness is compiled with them); build script, which must produce `execution` and leave **each object of the project in `obj/`**, one `obj/<name>.o` per translation unit of `SOURCES` (`.c`, `.S`, `.cc`…), two units with the same name being refused (otherwise the judge stops) |
| `PREFIXES`, `PERMIS` | the project's namespace (at least one prefix, each a word ending in `_`: `mz_`, `yaml_`) and external functions allowed on top of the common list (64 at most). The functions that serve to fool the measurement (clock, processes, environment, signals, system calls: `analyse.JAMAIS_PERMIS`) are never allowed and are flagged by their exact name, before any exemption |
| `COTES` | input sides (`f`, `z`…): never two sides mounted together; in verification, one container per side; in the measurements, one per scenario (below) |
| `SCENARIOS`, `INSTRUCTIONS`, `METRIQUES`, `METHODE` | scenarios measured on the timer and their side; those whose instructions are counted; metrics (name, direction, unit); method texts added to the report |
| `corpus(outillage)` | the base's corpus, `[(name, bytes)]` (helper: `entrees.charger_corpus`) |
| `verification(rng, corpus)` | verification inputs (`entrees.Entree`): corpus, randomly drawn data, derived data (streams produced by the host), invalid inputs |
| `verifier(a, b, entrees)` | correctness rule on the outputs of the `verifier` mode; raises `Refus` at the first discrepancy, `Erreur` if the base itself is wrong; returns the number of outputs compared |
| `fixes(sorties, corpus)` | metrics that do not depend on time (compression ratio…), read on the verification outputs |
| `repetition(rng, corpus)`, `instructions(rng, corpus, prefixe)` | inputs of the measurements, perturbed at each call (the common judge mixes verification inputs into them, then renames everything) |
| `scenario(s, a, b, entrees, mesure)` | checks **each** output of a measured scenario by `verifier`'s rule, mixed-in verification inputs included (invalid ones too), and derives the metrics from them (from chrono's measurement); returns `(values, outputs compared)` |

The harness (`execution`) is called with no argument; its descriptor 0 carries 256 bytes: the line `<mode> /entrees /sorties`
(mode `verifier` or a scenario's name), padded with spaces and ended by a newline; `/entrees/liste` gives one line
`<side> <name> <integer>` per input, whose bytes are in `/entrees/<side>/<name>`. In a scenario, it treats any
input of its side as in verification.

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
depth in an order drawn for each container: since ruche-0136, each folder the judge mounts, in every container (executions and
builds), is given at a depth that no other mount of the container shares, from `conteneur.PROFONDEUR` (8) on, deeper than any
of Docker's own (4 at most: `/sys/fs/cgroup/cpu` under cgroup v1), through the image's link to its root
(`/.racine/…/.racine/variante` is `/variante`), so all are mounted in one order, whatever order Docker draws
(test_one_mount_order_whatever_docker_draws; with Docker, test_profondeurs). `/etc`'s three files stay at their depth. Identical scenarios thus find the same
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

Safety rules, checked by the common judge (adversarial review of 28 October):
- the analysis listings (`nm`, `objdump`) are produced by the common judge itself, in a container, on
  all the objects in `obj/`: a build script can neither omit them nor empty them;
- the plugin sees the outputs only through `lecture.Sorties`, which records what it has read: at each
  step, each input must have had at least one output of B read, otherwise the judge stops (code 2);
- the plugin runs nothing that the container produced and never puts bytes from the
  container into a message without `lecture.propre`; any unexpected exception is an error (code 2);
- a harness never sizes a buffer from the judged code alone (a known bound of the format, at the least);
- the instruction analysis covers only x86-64: on another architecture, the judge flags it as a
  suspicious construct (a guardian reviews);
- what the object analysis covers: suspicious instructions (system calls, counter reads, processor identification,
  Valgrind client requests…) are counted in the disassembly and, independently, in the executable bytes of every
  object and of the linked program, read from the files at every offset, each hit compared with A's by its object
  and surrounding bytes; undecodable bytes and writable and executable memory count too. A failure of `nm` or of
  the disassembler stops the judge (refusal or error), and unreadable bytes make it incomplete: never complete;
- the judged files (`SOURCES`) are scanned whole, each file of B against A's, line splices joined, without
  git: only a net, the objects show the code produced. A PR that modifies `bee/juge/` is a tooling
  task: the registry detects it and requires a guardian (R3).

**Machine failures and seeds (ruche-0136).** A failure of the machine that judges is an error of the environment, never a
refusal of the judged code: after each container, the judge reads Docker's own record of it (`docker inspect`, then the container
is removed), never its code or error stream, which the judged code writes; a container that was not created (daemon out of reach,
image or runtime missing), that its runtime failed to start, or whose recorded state is not « exited » with its process's code
stops the judge with code 2 (`lecture.Panne`, whose motif never quotes the container's error stream); at its deadline, a
container that never started is one too, one that ran a refusal. With `--json`, `juge.json` is written whole or not at all
(renamed into place) whatever the outcome: `juge.code` and `juge.issue` (`juste` 0, `refus` 1, `erreur_environnement` 2), and on a
stop `juge.motif` and `juge.panne_machine`, a refusal staying a refusal whatever its message holds; `rapport.py --code` publishes
0 only with its report, whole and checked, and a code only if the report does not say another (code 2 otherwise; a refusal needs
no report), and juge.yml's judging step annotates it: a notice for 0, a warning for a refusal of B, an error for an error of the
environment, which judges nothing.
`juge.origine_des_graines` says for each seed (`graine`, `graine_ordre`) whether the judge drew it (`tiree`) or it was given on
the command line (`donnee`, `--graine`, `--graine-ordre`: a local reproduction). `rapport.py --verifier` refuses any report
whose seeds were not both drawn, or that does not say: a reproduction is never taken for a judgement (its seed is no longer drawn
after the build). Refusing rather than marking keeps one rule on the verdict side: only a judgement passes.

## Versions

- The common judge is versioned by tag (`juge-v1`, `juge-v2`…) in the registry. A change
  goes through a tooling PR on the registry, with the common meta-tests (workflow
  `juge-commun.yml`) and those of each project that uses it, and the review of two guardians.
- The reusable workflow `.github/workflows/juge.yml` reads the common judge at the very commit of the called
  workflow (`job.workflow_sha`), never at a tag or a branch: the workflow must be
  `Bee-ruche/registre`'s (`job.workflow_repository`) and that commit must be on its main branch (compare API:
  `identical` or `behind`), otherwise the judge stops (checked by a test); `juge.json` names it (`juge.source`).
- Each fork pins a version in its workflow; it moves up a version through a PR (a tooling task
  of the fork), judged by the old version and by the new one.
- `verdict.json` carries `judge.version` (an integer: 2 for minizBee's judge of miniz-0031, 3 for the
  common judge, v1 to v3), `judge.common` (« juge-v1 », « juge-v2 », « juge-v3 »), `judge.project` and `judge.plugin` (SHA-256 fingerprint of the
  plugin): the registry knows by which judge each verdict was rendered, and requires a minimum
  version (`bee.yaml`, below).
- **Minimum version** (`common_judge_min` in `bee.yaml`, ruche-0086): with R3's gate at `if_judge_incomplete`, a verdict whose
  `judge.common` is not exactly `juge-vN` (N in ASCII digits, no leading zero) with N at least this minimum is not entirely
  judged: a guardian or the council must review it, as for any incomplete judge. Missing or malformed (not an integer from 1
  to 9999), no verdict is complete: the gate closes, never opens. It is read when R3 is checked, so it reaches contributions
  still in review, judged by an older judge, never those already integrated. **The council raises it**, after it has tagged
  the new version and every fork is pinned to it (each fork moves by a tooling PR); raised earlier, the forks' verdicts go to a
  guardian until they move. It checks the version of the judge's code (the label, `COMMON_VERSION` in `tools/judge/judge.py`),
  not the commit a fork pins: the council bumps `COMMON_VERSION` whenever a change to the judge or to its workflow's
  protections ships, then raises the minimum. `bee validate` reports a missing or malformed minimum.

## The `juge.yml` workflow, version 2 (ruche-0024)

- **Declared history**: the input `historique` (16 full commits at most, separated by blanks) names the
  commits whose git objects the plugin reads. Each must be an ancestor of the base (compare API of the calling
  repository: `identical` or `behind`), checked before any fetch; the workflow then fetches them into the
  base's copy, each with its tree and without its history, in a separate step, the only one to receive the token,
  before loading the plugin and before any file of the PR, in 10 minutes at most in all (otherwise an error, code 2). The judgement then refuses
  any git transport (`GIT_ALLOW_PROTOCOL`): an undeclared object is an error (code 2).
- **Safe log**: the last 40 lines of the log, which the PR can fill, are printed between
  `::stop-commands::<token>` and `::<token>::`, a token drawn after the judgement, and `##[` becomes `# #[` in them
  (ruche-0025): none of them becomes a workflow command.
- **The caller's inputs** (ruche-0038), checked first: `base_sha` and `tete_sha` are the event's pull request's
  (`github.event.pull_request.base.sha`, `.head.sha`, 40 hexadecimal digits), `repetitions` 10 to 50, `sans_instructions`
  false (a verdict needs the instruction count); otherwise the job fails before anything is checked out or judged.
- **Job outputs tied to the report** (ruche-0038): `code`, `empreinte` (SHA-256 of `juge.json`), `suspectes` (all of them),
  `sorties_comparees`, `greffon`, `graine`, `base`, `tete` (`tools/judge/report.py`; empty without a report). The verdict
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

## Three plugins side by side

The contract was checked on two real projects (miniz, with a trial plugin giving exactly the
results of miniz-0031's judge) and on the toy; for libyaml (libyaml-0005), it is filled in as follows:

| Element | toy | miniz | libyaml (planned) |
| --- | --- | --- | --- |
| `SOURCES` | `rle.c`, `rle.h` | `miniz*.c`, `miniz*.h` | `src/*.c`, `src/*.h`, `include/yaml.h` |
| `EN_TETES_BASE` | `rle.h` | `miniz*.h` | `include/yaml.h` (harness compiled with `-I/outillage/base/include`) |
| `COTES` | `f` raw, `z` streams | `f` raw, `z` zlib streams | `f` documents (no derived data) |
| `SCENARIOS` | compression, decompression | n1, n6, n9, decompression, memory | parsing, loading, emitting, memory |
| correctness | output identical to the base, reference codec in Python | identical to the base, the host's zlib | serialized event stream and emitter output identical to the base; invalid inputs: same error, same positions |
| `PREFIXES` | `rle_` | `mz_`, `tdefl_`, `tinfl_`, `miniz_`, `MZ_` | `yaml_` |

## Migration

1. Integrate miniz-0031 (minizBee's judge, version 2).
2. Extract the common part into the registry (`outils/juge/`, workflow `juge.yml`, tag
   `juge-v1`), with its meta-tests on a toy project. *Done on 28 October, tag `juge-v1` set.*
3. minizBee moves to a plugin (miniz-0032); with the same seed, it must give exactly the results
   of miniz-0031's judge.
4. libyaml (task libyaml-0005) writes its plugin and its harness instead of a copy.
5. New projects (giflib, bzip2) arrive directly with a plugin.
