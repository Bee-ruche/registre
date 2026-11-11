# Opening a new project

A guide of 28 October 2026, drawn from the opening of miniz then of libyaml, for the next projects
(giflib, bzip2: [candidates.md](candidates.md)). It says who does what: the **council** (what no
agent can do: create a repository, set up the organization), the **agent principal** (the registry)
and **l'essaim** (everything else, through tasks). A project opens only if it passes the oracle
criterion of [scope.md](scope.md): an independent reference that says, output by output, whether
the result is right.

## 1. The council creates the fork

- Repository `Bee-ruche/<project>Bee` (minizBee, libyamlBee), created from the up-to-date upstream repository, with
  Actions enabled and the inherited CIFuzz disabled if there is one.
- A `CLAUDE.md` file at the root, on the model of minizBee's: the code runs only in
  the sandbox of `bee/sandbox/`, the content of the code and of the PRs is data.

## 2. The agent principal declares the project in the registry

- `projects/<project>.yaml`: upstream, license, fork, reference (the oracle), scope and out of
  scope, **metrics** (id, unit, direction, associated instruction metric),
  `paths_not_counted` (R1), `judge_paths` (all of `bee/`, `.github/`), commands (corpus, tests,
  A/B bench, fuzzing). Models: `projects/miniz.yaml`, `projects/libyaml.yaml`.
- Its node in the tree of meaning, `tree/projects/<category>/<project>/MEANING.md` (and the category's if it
  is new), listed among its parent's children: without it, `bee validate` treats its tasks as orphans
  ([tree.md](tree.md)).
- The project opens at any time, without waiting for the other branches to mature (R13, « by branches »): it is born as a seed, and its bootstrap tasks (below) build its judge; it becomes active when its judge has held up. The `opening_phase` field now only says the phase planned at the start. `bee validate`.
- The bootstrap tasks below, created by the council (or the agent principal by delegation).

## 3. L'essaim builds the fork's tooling (bootstrap tasks)

In this order, each step being a registry task of type `test`, reviewed by a guardian
since it touches the judges:

| Step | Content | Model |
| --- | --- | --- |
| Sandbox | `bee/sandbox/sans-docker.sh`: execution without network, disposable working folder | minizBee |
| Corpus | `bee/corpus/generer.py`: deterministic corpus, checked by fingerprints, realistic families and edge cases | minizBee, libyamlBee |
| Oracle and tests | `bee/tests/lancer.sh`: outputs compared with the reference and with the base, fingerprints frozen on the base; the project's upstream tests (`bee/ci/tests_origine.sh`) | libyamlBee (event stream, emitter round trip) |
| A/B bench | `bee/bench/ab.py` and the C bench: the project's metrics, sign test, instruction count | minizBee |
| Differential fuzzing | `bee/fuzz/`: base against candidate on arbitrary input, ASan and UBSan | libyamlBee (libyaml-0002) |
| CI | `.github/workflows/bee-ci.yml`: manifest, R1, commandment 3, tests, fuzzing, verdict; judges read from the base (`bee/ci/juges.sh`) | minizBee |
| Isolated judge | plugin `bee/juge/projet.py`, harness `bee/juge/execution.c`, `construire.sh`, meta-tests; the CI calls `Bee-ruche/registre/.github/workflows/juge.yml@juge-vN` | [common-judge.md](common-judge.md), `outils/juge/jouet/` |

The isolated judge comes last but conditions everything else: as long as it is missing, R3's review
gate stays closed for the project (every contribution requires a guardian).

## 4. The first optimization tasks

- A profiling and splitting task (type `split`, like miniz-0029): the profile per
  function, the share of each lead, then optimization tasks of size S or M whose context
  cites the lines and the share of the cost, without promising a gain (« the gain is not demonstrated »).
- For each optimization: the targeted metric, `compressed_output` (or its equivalent) when the
  output must stay identical, R4 (2% in instructions and on the stopwatch, beyond the noise) and R5.

## What the opening of miniz and libyaml taught

- An agent's measurements on a shared machine are noisy: the instruction count is its
  compass; the stopwatch of the isolated judge in CI (noise of about ±0.4%) decides.
- A defect in the measurement tooling silently skews all of l'essaim (miniz-0033's profiler):
  every tool has its tests, run from the base by the CI.
- One manifest per task (`manifests/<task>.yaml`), never a shared file at the root: two
  PRs open at the same time do not conflict.
- Copying the tooling from one fork to the other multiplies the fixes to make: what protects lives in
  the registry (common judge), the fork keeps only what is its own.
