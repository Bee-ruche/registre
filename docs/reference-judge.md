# The judge's second kind: `reference` (a candidate answers as a reference does)

Status: built in the registry (`tools/judge/reference.py`), tried on a toy project in its tests
(`tools/judge/reference_toy/`, `tools/judge/test_reference.py`). No project of the hive uses it yet.

A project names its judge's kind in its file (`judge.kind`, [protocol.md](protocol.md)). The first kind,
`common` ([common-judge.md](common-judge.md)), compares a candidate with the project's own tip and measures it.
This one serves projects of another nature: a **port**, or a rewrite against something that already runs. A
candidate is right when the unit it writes answers **exactly as the reference does**, on cases drawn when it is
judged: the same bytes, or the same refusal. Nothing is measured.

Nothing of a language, a format or a project is in the kind: it knows containers, files of bytes and an exact
comparison. What knows the project is the project's, at its tip.

## Who holds what

| Part | Where | Runs |
| --- | --- | --- |
| The kind: the steps below, the isolation (`container.py`), the safe reading (`lecture.py`), the draws, the comparison, the verdict | the registry | on the judge's machine |
| The image | the registry: the manifest names an image the registry holds (today `common`, the common judge's) and never brings one | — |
| The manifest `bee/reference/project.json`: data | the project's tip, a path no candidate can change | never: it is read, every field checked against a floor and a cap |
| `bee/reference/build-reference`, `bee/reference/build-unit`, the reference, the two drivers, the generator of cases, a blank unit | the project's tip, paths no candidate can change | in containers only |
| A unit's files | the candidate, for the unit of its task | read as bytes on the host; built and run in containers only |

Nothing of the tip and nothing of the candidate runs on the judge's machine itself.

## Words

- A **unit** is what one task writes: a name, its files, and a total function « bytes in → bytes out, or a
  refusal ». Units do not build on one another: a unit's binary holds the project's skeleton and that unit's files.
- A **case** is one input of one unit. An **answer** is a status (0 answered, 1 refused) and, when answered, bytes.
- A **driver** reads a file of cases of one unit and writes a file of answers, one per case, in order. The
  project holds two: the reference's (it calls the original) and the unit's (it calls the unit under judgement).
- The framing is the kind's, little-endian: cases `<u32 length><bytes>`…; answers `<u32 index><u8 status>
  <u32 length><bytes>`…; the index is the case's position; a refusal carries no bytes.
- A **nonce** is random bytes the kind gives each build of a unit. The project's build makes the binary's
  layout follow it.
- A **blank unit** is the project's own stand-in for a unit: files that build in the unit's place and do nothing
  (they abort if called). The judge builds its control with them.

## The two rules

1. **A candidate answers only for binaries of its own unit**, built from the skeleton at the tip and its own
   files. No other unit is built or run for it, and the rest of its tree must be the tip's, byte for byte.
   Nothing a candidate wrote is built or run in another candidate's judgement, nor in the question about the tip
   itself: a unit that was accepted is, from then on, only ever built again as a candidate's.
2. **A unit is right when it is right in every build and every run drawn for it**: several binaries built with
   different nonces, each run several times on the cases in orders the judge draws, every file of answers exactly
   the expected one and every exit status 0.

## One judgement

For a task whose unit is U, the tip's tree and the candidate's tree written out by the base:

0. **Budget.** The manifest's bounds, every container at its time, must fit the time the project's file gives a
   judgement (`judge.timeout_seconds`).
1. **Read and check.** The manifest; the task's files, which must be exactly U's files; the candidate's tree, which
   must equal the tip's everywhere else; U's files, which must be plain files within the manifest's bound.
2. **The reference** is built in its own container: its driver and the generator.
3. **The control.** The skeleton with the project's blank unit in U's place is built twice, with two nonces: the
   two binaries must differ; one is run on no case and must write nothing and exit 0. This tells a broken
   toolchain, skeleton or driver from a candidate that does not build. The unit the tip holds is not part of it.
4. **The candidate's binaries** of U are built, one per nonce, from the tip's skeleton and the candidate's files.
5. **The draw.** Only now a seed is drawn. The generator writes U's cases (exactly the manifest's count, each
   within its bound); the reference answers them. The host checks both files against the framing.
6. **The tip against itself** stops here, answered 0: nothing is asked of U, and nothing of U is built or run,
   whether the tip holds it, holds it unwritten, or does not hold it yet.
7. **The runs.** Each binary is run several times, each time on the cases in another order.
8. **The comparison**, on the host: each file of answers is read through the safe reader, no further than the
   expected length plus one byte, and must be exactly what the host built from the reference's answers.

The verdict:

- **0, correct**: every build, every run, every byte.
- **1, refused**: what the candidate brings or does: a tree that differs elsewhere, a unit that does not build
  within its bounds, a run that fails, passes its bounds or does not give exactly the expected file.
- **2, failure to judge**: what the candidate has no part in: the manifest, the task, the reference's side, the
  control, the machine. The base then asks about the tip itself ([protocol.md](protocol.md)); that question is
  asked with the seed of the judgement that failed, so that the same cases are drawn.

Of the judge's report the base keeps numbers only: `cases_compared`, `builds`, `runs` (what was done).

## The manifest

```json
{
  "image": "common",
  "reference": ["reference", "harness", "bee/reference"],
  "skeleton": ["harness/unit_driver.c", "harness/unit.h", "bee/reference/build-unit"],
  "units": {"upper": {"files": ["port/upper.c"], "blank": ["harness/blank_unit.c"],
                      "cases": 300, "case_bytes": 64, "answer_bytes": 64, "refuses": true}},
  "variants": 2, "runs": 2,
  "build_seconds": 60, "run_seconds": 10, "reference_seconds": 60,
  "memory_mb": 256, "build_processes": 64, "output_mb": 16, "unit_bytes": 65536
}
```

`reference`: what the reference's container is given. `skeleton`: what a unit's build is given beside the
unit's own files. `blank`: for each of the unit's files, the project's file that stands in its place in the
control. `refuses`: whether the unit refuses some inputs (the cases drawn must then hold a refusal and
an answer). `variants`: builds per candidate; `runs`: runs per build; both at least 2. A unit's file is a plain
file, never a path of `reference` or `skeleton`, never under `bee/`, never another unit's; a blank file is never
a unit's.

## What the project's programs are given

| Program | Container sees | Asked |
| --- | --- | --- |
| `sh /src/bee/reference/build-reference` | `/src` (the `reference` paths), `/out` | leave `/out/reference` and `/out/generate` |
| `/ref/generate <unit> <count>`, the seed (hexadecimal) on its input | `/ref`, `/cases` | write `/cases/cases` |
| `/ref/reference <unit>` | `/ref`, `/cases`, `/answers` | write `/answers/answers` |
| `sh /src/bee/reference/build-unit <unit>`, the nonce (hexadecimal) on its input | `/src` (skeleton and the unit's files), `/out` | leave `/out/driver` |
| `/unit/driver` | `/unit`, `/cases`, `/answers` | write `/answers/answers`, exit 0 |

Every container is without network, read-only, unprivileged, bounded in time, memory, processes and bytes
written; a run of a unit has room for its driver and no other process (the reference's own programs have the
room of a build); a folder a container writes in is a memory file
system of bounded size, gone when the step ends. A container's command also carries a time of its own, a little
after the judge's: it ends even if the judge is no longer there to stop it.

## For the base

A task of such a project names its unit (`options.unit`) and lists exactly that unit's files. The project's file
says `"kind": "reference"` under `judge`, and lists in `judge.metrics` the figures it keeps (`cases_compared`).
