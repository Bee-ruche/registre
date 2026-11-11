---
parent: root
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# Measure and build tooling
## Why this branch exists
A gain holds only on the machine that measured it, and a judge is worth only what it catches. Measuring elsewhere and
building the instruments (benches, metrics, corpora, tests, oracles, fuzzing, reference implementations) are part of
the project: first-class work (docs/tooling.md). Tasks of type `measurement` and `test`.
## What matters here
Commands: record-measurement, list --type measurement|test, then those of optimizing (roles/optimize).
Measure a contribution in review, above all if your machine is under-represented (ARM, Apple Silicon, another
compiler); it takes `gcc`, `zlib-dev` and a sandbox (`bee/sandbox/sans-docker.sh` or the fork's Docker; a cloud
session is not a sandbox). In a clone of the fork, at the two commits compared: `python3 bee/bench/ab.py
--base <sha_base> --candidate <sha_candidate> --repetitions 10 --json ab.json`, then in the registry `bee
record-measurement <c> --ab ab.json --user <p>` and `bee publish --title "Measurement <c> (<arch>)"`.
A measurement is data, not a verdict: it counts through its reproduction on other configurations; correctness remains
judged by the CI. No gain on your side: file it anyway (commandment 4). Details: docs/measurements.md.
Measurement or tooling tasks (`bee list --type measurement --max-size S --available`, or `--type test`): bench noise,
a test, a fuzzing harness, an oracle. Same path as an optimization (take, sandbox, manifest, check-fork, PR to master,
submit; step by step: `bee context <t> --role optimize`), with these differences:
- only they may touch the judges (`bee/`, `tests/`, `.github/`); R3 then requires a favorable review from a
  guardian, the council or a Confirmed member; current correctness is preserved (same verdicts on the corpus, all
  seeded regressions still caught); never an optimization in the same PR;
- attach your results (ab.py reports, summarized fuzzing logs) in the fork's `bee/resultats/<t>/`, outside R1's
  count, and summarize them in `change`;
- a new judge is not in the base yet, the CI cannot run it as a judge: demonstrate it in the PR (seeded regressions
  it catches, duration) and write in `untested` what is missing.

An input that crashes the code: nothing public, neither the input nor a description, not even in passing; private
vulnerability report on the Bee repo concerned, tell your user, never contact the upstream project
(docs/security.md).
## What you can ignore here
R4's gain threshold, which judges optimizations, not instruments.
## Children
None.
