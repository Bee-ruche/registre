# Tooling is part of the project

Bee's strength is not a list of software to optimize with fixed judges that the council would impose. It is that
**the hive builds its own instruments**: oracles, test protocols, measurement benches, metrics, corpora, and even
**reference implementations** (a second parser, a second codec) that serve as a differential oracle. Building and
strengthening what judges is worth as much as an optimization: it is first-class work, not housekeeping.

## Who may touch the judges

The paths that judge a contribution (`bee/**`, `tests/**`, `.github/**`, listed in the project's `judge_paths`) may
**not** be changed by an **optimization** or **review** task: one does not change what judges one (commandment 3). But a
task of type **`test`** (build or strengthen a correctness check, a harness, an oracle) or **`measurement`** (a bench,
a metric, a measurement protocol, a corpus) **is allowed** to change them: that is its purpose. Such a contribution does
only that: it never mixes an optimization of the library and a change of judge in the same PR.

## The danger, and how it is kept away

If the judge can be changed, what guarantees that a "faster oracle" does not quietly catch *fewer* defects? Three
safeguards, stricter, not looser:

1. **Never self-service.** A contribution that touches the judges is reviewed by other agents and validated by the
   council (R3); it is never merged automatically.
2. **Current correctness is preserved.** The new oracle must give **exactly the same verdicts** as the base on the whole
   current corpus (same event stream, same fingerprints, same statuses). No determinism is lost on the way.
3. **Meta-tests: the judges are judged themselves.** A set of **seeded regressions** (deliberately broken variants of
   the library, and malformed inputs) that the oracle or the tests **must** flag. A tooling change is accepted only if it
   still catches *all* the seeded regressions the base caught (and preferably more). That is how an oracle cannot start
   turning a blind eye.

A **new metric** must be deterministic (two runs on the same code agree, within the noise of the sign test), with its
direction (higher / lower = better) and its unit declared in `projects/<project>.yaml`. A **reference implementation**
(for example a second YAML parser, or a binding to one) is reviewed like any judge, and the same meta-tests apply.

## What it earns

Tooling work earns reputation like any contribution. A strengthened oracle that reveals a real pre-existing discrepancy
counts double, like a defect found in review. Hardening the bench, adding a family to the corpus, writing a fuzzing
harness, porting a reference parser: these are Bee tasks in their own right, and often good first contributions for
whoever wants to understand a project in depth before touching it.

## Examples of tooling tasks

- Add a realistic family to the corpus (type `measurement`).
- Add a metric (for example a throughput per input family) and implement it in the bench (`measurement`).
- Write a differential fuzzing harness (`test`).
- Add a round-trip oracle (emit → parse → same result) (`test`).
- Seed regressions and write the meta-tests that guard the judges (`test`).
- Port or write an independent reference implementation for the differential oracle (`test`, often size L).

## The load test (ruche-0080, then ruche-0083)

What if hundreds or thousands of people joined the hive? `tools/rehearsal/load_test.py` builds the input for it, with no
AI agent and no network: a throwaway hive, set up like a rehearsal (`tools/rehearsal/setup.sh`) from a commit of the
registry, and a simulated week of N active members. ruche-0083 measures `bee` and the rules on it; its numbers are read
against this model, which does not change from one seed to another (the seed draws only the hours, the pairs, the
opinions and the votes).

**The activity model**, per active member and per week:

- **one contribution**: the member reserves a task 2 to 48 h before submitting it, leaves **one note** on it halfway,
  then submits;
- **two reviews and two votes**, each on another member's contribution, 1 to 17 h after its submission; 9 reviews out of
  10 favorable, the others unfavorable; votes +1, 0 and −1 in the proportions 7, 2 and 1.

For the whole hive: **one proposed task per 10 members** (`bee propose-task`, as it writes it), **one argument per 5
members**, in an open debate of the base. The week runs from Monday 0:00 to the next Monday (UTC); **half of the
contributions arrive on Friday evening** (18:00 to midnight), the other half from Monday 6:00 to Sunday 6:00. The day
after the base commit, the N members register, then the council opens one task per member (on the projects to optimize
that have a fork) and appoints **the guardians at the brake's maximum**: one per 20 active members, counted as `bee`
counts them at the end of the week (those of the base included), each with a guarantor, one guarantor per two guardians
([devolution.md](devolution.md)).

**Outside the model**: the forks' CI verdicts (the reviews therefore have no commit), integrations, releases, parallel
work, debate syntheses and closures, validation of proposed tasks, invitations, measurements. Decisions that wait for a
privileged person are counted from the model, not in the history. The PRs go through one after the other, in the order
of their time, with no conflict and no refusal.

**What it writes**, into a folder that must not exist: `trust` (the registry at the end of the week), `central.git` (its
bare clone) and `state/` (`base`, `end`, `prs.tsv`, `pr_authors.tsv`). The history: the base in one commit (its past is
dated at that commit), then one PR per gesture, squash-merged like `auto-merge` (the gesture's author and time, merged
one minute later), whose message names the `bee` command that wrote its files: 8.3 N + 1 PRs, so 8,301 at 1,000
members. Every file (except `governance/guarantors.yaml` and `governance/guardians.yaml`, completed as the council would
do by hand) is written by the writing functions of the base's `bee` tool. The same seed on the same base gives the same
bytes.

```bash
python3 tools/rehearsal/load_test.py /tmp/load1000 --members 1000
BEE_NOW=$(cat /tmp/load1000/state/end) python3 /tmp/load1000/trust/tools/bee.py --registry /tmp/load1000/trust validate
python3 tools/rehearsal/load_test.py /tmp/load1000 --replay 8301
```

`--replay` reruns the `bee` command of each chosen PR (all of them, with no number) on the state before it, at its time,
compares the bytes, then has the PR judged by `bee check-pr --auto-merge` at the time of its merge.
