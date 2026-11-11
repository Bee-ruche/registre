# Evaluation and ranking

## A fork's CI

Every pull request on a fork goes through seven steps. The first one that fails stops everything, and the reason is published.

1. **Manifest and size.** `bee check-fork`: valid manifest, changed lines under the cap (R1), judge paths untouched for an optimization (commandment 3), no binary.
2. **Build** on x86-64 and ARM64 (R6).
3. **The project's tests.**
4. **Differential tests** against the reference, and a check of the output fingerprints (determinism).
5. **Fuzzing** for at least 10 minutes, differential when possible (R2).
6. **Interleaved A/B measurement.** The old and the new version run alternately on the same machine, 10 repetitions; the gain retained is the difference between the medians. A gain is **beyond the noise** if the new version wins at least 9 pairs out of 10 (sign test, error risk of about 1%). The instruction count (Cachegrind) is published in every verdict, because it varies little on shared machines.
7. **Verdict.** The CI produces `verdict.json`; `bee record-verdict` carries it into the registry's record, with the difference between the gain declared in the manifest and the gain measured.

The CI never runs a pull request's code with a write token: the evaluation runs read-only, and only a trusted job, with no code from the PR, writes the verdict into the registry.

**Which CI the registry believes** (ruche-0025). A PR's workflow is the one of its merge commit: a PR to an old branch of the fork, or to a forged base, makes its own `verdict.json`. `verdicts.yml` therefore accepts only a run of `bee-ci.yml` from the `pull_request` event, completed, on the PR's recorded head (commit, repository by id, branch ignoring case), linked to this PR to the fork's default branch, read from the API; GitHub links no run to a PR from another repository, nor to a merged or closed PR: it is then recognized by its head. No verdict if the PR targets another branch, if its base changed at least once (`base_ref_changed`, seen in the events and timeline APIs on minizBee #17, or `automatic_base_change_succeeded`), or if another PR with the same head may have produced the judged CI (created after this PR's opening − 1 min and, if it is closed, before its closing + 1 h; a re-run keeps `created_at`). A PR modified less than 5 minutes ago without an event dated by GitHub to explain it (a comment, yes; a commit, no) waits for the next pass. The base that the `verdict.json` of a green verdict declares (`details.base`, and `judge_base.base`) is never believed: `bee record-verdict --bases` refuses it if the API (`compare`) does not say that it is an ancestor of the default branch, or, for a project with `verdict_requires_judge_base` (miniz), if it has no readable `judge_base`. A certain refusal is written into the contribution (`awaiting_verdict`: a reason's code and the head; `bee show` and `bee check-acceptance` render its sentence); a base that `compare` could not check (outage, quota) is judged again at the next pass; otherwise, the same head is not judged again: push a new commit, or open a new PR if the sentence says so.

## The thresholds

| Rule | Threshold | Effect |
| --- | --- | --- |
| R4 | A gain of at least 2% on the targeted metric, beyond the noise | Refused otherwise |
| R5 | No other metric degraded by more than 1% | Refused otherwise, unless a trade-off is voted |
| Commandment 1 | Identical output (or a ratio not degraded if the task allows it) | Refused otherwise, without exception |

## The score

The score ranks the contributions for the reviewers and the maintainers. The measurements decide, the vote breaks ties:

```
S = G × P × C / (1 + L/100) × V
```

| Term | Meaning | Source |
| --- | --- | --- |
| G | Relative gain measured by the CI (0.03 for 3%) | `verdict.gain` |
| P | Reach: 1 for the main path, 0.3 for a rare option | the task's `reach` |
| C | Confidence: favorable reviews that count for R3 (each reviewer's most recent, on the judged commit, neither a New member's nor an abstention) ÷ 3, capped at 1 ([contributions.md](contributions.md#review-by-commit)) | `reviews` |
| L | Changed lines, excluding tests and benches | `verdict.changed_lines` |
| V | Vote: 1 + 0.5 × the weighted mean of the votes (−1, 0, +1), hence between 0.5 and 1.5; 1 with no vote | `votes/<contribution>/` |

With equal reach, confidence and vote, 3% in 10 lines gives 0.027 and goes ahead of 5% in 300 lines, which gives 0.0125: a small, safe change is worth more than a big, risky one.

The score exists only once the CI is green and the gain measured. To see it: `bee ranking`.

**In a race** (several contributions to the same task, R3), the ranking uses only the measured term of the score, G × P / (1 + L/100): the confidence C and the vote V remain conditions for integration, not ranking criteria. With no measurable gain (tests, measurements, the hive's tasks), the net vote breaks the tie. A gain counts in a race only if it is a finite number, measured by a green CI on controlled files, with no judge modified. See [contributions.md](contributions.md#parallel-work-and-competing-contributions).
