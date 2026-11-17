# The hive's hourly run

*The workflow of phase 1 (docs/plan.md, 7.2): [`.github/workflows/hive.yml`](../.github/workflows/hive.yml). The run
holds the right to write to a project, so it entered the repository only after another model than the one that
wrote it had reviewed it, with `tools/test_bee.py` listing its permissions
(`test_the_workflows_security_is_unchanged`) and holding its rules (`TestHiveWorkflow`). **It has been running for
the first project since 16 November 2026**, by invitation (the founder's own worker). On
`main` it starts every hour and all four jobs are skipped, as long as the repository variable `HIVE_PROJECTS` is
empty; and the commit of the registry it checks out is the one its file names: forty zeros until 16 November
2026, then, the same day, the commits `main` reached by pull requests 372 (the founder's own first run), 375 (the
correction that run called for) and 377 (a refusal for a proof alone), and from 17 November the one reached by
pull request 384 (the base as it stands before a second project runs). A pull request of its
own changes that line (setting 7 below). What could not be tried is listed at the end.*

## What it must guarantee

The protocol (docs/protocol.md, "Four jobs, each with one risk") gives each job one risk. The workflow's only
task is to keep them apart:

| Job | Runs | May read | May write | Never |
| --- | --- | --- | --- | --- |
| `plan` | `hive.py plan` | the registry, the project, the forks (public), the state repository (without credentials) | nothing: it uploads `plan.json` and the bundle, and publishes the plan's SHA-256 as a job output | holds a key; runs code from a fork |
| `record` | `hive.py record` | the registry, the plan | the state repository (`Bee-ruche/hive-state`) | reads a fork; runs anyone's code; holds the project's key; unpacks another job's archive |
| `judge` | `hive.py judge` | the registry, the project, the plan and the bundle, the state repository (without credentials) | nothing: it uploads `verdicts.json` | holds a key; talks to a fork; has the network while a candidate's code runs |
| `apply` | `hive.py apply` | the registry, the project, the plan, the bundle, the verdicts | the project's branch (integration identity) and the state repository | reads a fork; runs anyone's code; unpacks another job's archive |

Five things carry it:

1. **The plan's SHA-256 is a job output**, not a file: `record` and `apply` receive it from GitHub, not from an
   artifact a later job could have replaced, and refuse a plan that does not match. The bundle's SHA-256 is in
   the plan.
2. **A job that will hold a key takes the earlier jobs' files itself, by name, before it holds the key**
   (`tools/hive/artifact.py take`). It asks GitHub for the archive, reads from it the members it expects (their
   exact names, up to a size) and writes each under that name in a folder of its own. It reads the archive itself,
   byte by byte accounted for: the members expected, the directory that lists them, the end, and nothing else,
   so an archive that holds anything more is refused whole, and what reading it costs is set by the sizes asked
   for. No general tool unpacks an archive in such a job: an archive names its own paths, and a file written
   where code is later run from is run.
3. **The project's token is given to one step of one job** (`apply`), through that step's environment. It is
   asked of GitHub for that run, lasts an hour and reaches one repository; the key that obtains it is readable in
   one environment only.
4. **The keys are readable from `main` only.** The two environments accept the branch `main` and nothing else
   (a setting, below), and the jobs that name them run on that ref only.
5. **One run at a time per project** (`concurrency`, never cancelled in progress by a newer run): two runs
   overlapping are safe by the protocol (the jobs that write check the ledger the plan read), and wasteful.
   **A run that a person cancels pushes nothing**: `apply` runs unless the run was cancelled or `plan` did not
   succeed, so also when `record` or `judge` failed (the deals `record` did not write are then written by nobody:
   those workers' asks stay, and the next run serves them).

## The settings only the founder can make

1. **The state repository**: `Bee-ruche/hive-state`, public (the founder's choice: a repository of its own, so
   that the jobs that write the state hold no right on the registry at all). It exists, with a README that says
   what it is.
2. **Two integration identities, kept apart**: two GitHub Apps of the organization, each with the repository
   permission "Contents: read and write" and nothing else, no webhook:
   - a *state* App, installed on `hive-state` only;
   - a *project* App, installed on the hosted projects only (`minizBee`, `cjsonRustBee`).

   The workflow asks GitHub, at each run, for a token of an hour for one repository
   (`actions/create-github-app-token`, pinned to a commit). The Apps exist since 13 November 2026: the state App
   (client id `Iv23liBJswEbZCt56yvz`) and the project App (client id `Iv23liKHEG0w2XgtSc9m`); a client id is not a
   secret, so the file names them directly. It needs, in the registry's settings, their private keys:

   | Name | Kind | Where | Holds |
   | --- | --- | --- | --- |
   | `HIVESTATESECRET` | secret | environments `hive-state` and `hive-apply` | the state App's private key (the whole `.pem` file GitHub gives under "Private keys"; not the "Client secret") |
   | `HIVEAPPLYSECRET` | secret | environment `hive-apply` only | the project App's private key (the same kind of file) |

   (The names are the founder's, as entered in the registry's settings.)

   `record` runs in the environment `hive-state`, `apply` in `hive-apply` (a job has one environment, and `apply`
   writes both the project and the state).
3. **Both environments accept the branch `main` only**: in each environment's settings, "Deployment branches and
   tags" set to "Selected branches and tags", with the one rule `main` (a branch) and no tag rule. An environment
   gives its secrets to any job that names it, in any workflow, on any ref it accepts: this setting, and not the
   text of one workflow file, is what decides who can read a key. **To make before the keys are entered, or
   right after.**
4. **Each hosted project's two branches.** On the hive's own branch (`branch` in the project's file: `hive` for
   miniz), pushes allowed to the integration identity and the maintainers, force pushes blocked, no required pull
   request for the identity. On the branch the project publishes (`published`: `master` for miniz), no push by the
   integration identity at all. The hive's own branch is made once, by a maintainer, from the published one.
5. **The repository variable `HIVE_PROJECTS`** (for instance `miniz`): the run does nothing while it is empty, in
   addition to each project's own `"paused": true`.
6. **Actions settings**: workflows may not approve pull requests; artifacts kept a few days.
7. **Which version of the hive a run uses: one commit, named in the workflow file** (decided 13 November 2026).
   Every job checks out the registry at that commit and at no other: the hive's code, its settings and its tasks
   change when a pull request that a person reviewed changes that line, and at no other time. A new file holds
   forty zeros in its place, which no checkout can find (the first project's did until 16 November 2026, the second
   project's until 17 November): the line is set, by a pull request of its own, to the commit of `main` that the founder
   accepted, after the file is on `main`. A new batch of tasks is such a pull request too.
   The tests fail unless the commit named is one that `main` itself has been at (the line of first parents of its
   tip): GitHub serves any commit of a repository by its id, a pull request's included, and a commit inside a pull
   request that was merged is in `main`'s history without ever having been its state.
8. **A second project has a run of its own** (`.github/workflows/hive-cjson.yml`, for the project `cjson`): the same
   four jobs, held by the same tests line for line; what differs is named in one place
   (`TestHiveWorkflowOfTheSecondProject`): the project and its repository, how its judge's image is made (the
   judge's second kind, [reference-judge.md](reference-judge.md)), its minute of the hour, its group (one run of a
   project at a time; the two projects' runs do not wait for each other) and **its own switch, the repository
   variable `HIVE_CJSON`**. The state repository, the two environments and the two Apps are the hive's, the same for
   both runs. What only the founder can make for it: the project's repository, with its two branches as in point 4;
   the project App installed on it; the variable; and the commit its file names (point 7). On 17 November 2026 the
   repository, its branches and their rules were made and the App was given it, and the file names the commit the
   first project's file names (`3cd46a2`), where the project is declared paused. The founder then had the variable
   set, and the first run was made with the project paused: its four jobs succeeded, the two that hold a key took
   their tokens, the judge's image was made (the one the manifest in the project's repository names), and nothing was written
   to the state repository or to the project's. The project's file then left its pause (pull request
   388), and the workflow file names that commit (`5091c9c`) since, on the founder's decision: from the run after,
   the hive reads the forks of the one invited account, deals, judges and integrates for this project. The two
   projects' files name two commits of the registry; between the two, the documents, the two workflow files and
   their test, and the second project's own file differ, and nothing of `tools/hive/` or `tools/judge/`.

## The file

[`.github/workflows/hive.yml`](../.github/workflows/hive.yml) is the run, and the only text of it: this document
explains it and does not repeat it. One project per workflow file: `miniz` is written in full where a name is
needed. `HIVE_PROJECTS` is a switch, not a list the run reads: the run does nothing while it is empty. The second
project's run is a file of its own, [`hive-cjson.yml`](../.github/workflows/hive-cjson.yml), the same text for
another project, with its own switch (setting 8 above).

Notes on the file:

- **No expression appears in a `run:` line** (the registry's rule: a text never becomes code); expressions are
  passed through `env:`.
- `plan` prints `plan_sha256=…` on its standard output and its figures on its error output: the first goes to
  `$GITHUB_OUTPUT`.
- `record` and `apply` check out the state repository with a token of the state App, which `hive.py
  --commit-state` uses to push the state. `plan` and `judge` check it out without credentials. No job has a right
  to write to the registry.
- `judge` holds no key, so it may unpack the plan's archives with the common action; `record` and `apply` use
  `tools/hive/artifact.py` (tests: `tools/hive/test_artifact.py`), with the run's own read-only token.
- **To stop the hive**: cancel every run in flight (its `apply` then does not run), and empty the switch of each
  project's run for the runs to come: `HIVE_PROJECTS` for the first project's (`hive.yml`) and `HIVE_CJSON` for
  the second's (`hive-cjson.yml`). Both take effect at once, and neither needs a pull request. Emptying one
  switch stops that project's run and no other. A project's `"paused": true` stops its work and not its run: no fork is
  read, nothing is dealt, judged, integrated or written to the state, while the four jobs still start, take the
  project's repository and their tokens, and make the judge's image. And it does so only from the
  day its workflow file names a commit of the registry that holds it: a run reads the registry at the commit
  the file names, not at `main`.
- The rules above are held by a test of the file itself (`tools/test_bee.py`, `TestHiveWorkflow`): the four jobs
  are held word for word (whoever changes a line of one changes the test in the same commit, in sight of a
  reviewer), and the rules they obey are stated beside them: which jobs name an environment, where a secret may
  appear, that no job with an environment uses the common download action, the guards on the ref and on a
  cancelled run, the pins, the schedule. The test reads the file with one reader and GitHub with another: so every
  number and every yes-or-no of the file is written the one way every reader reads alike (`true`, `false`, plain
  decimal digits), and the test fails on any other spelling: a text that a tag turns into a number, a character
  that is neither printable ASCII nor a line feed, a root key other than `on`, a 0 where a yes-or-no goes.
- The project's token reaches git as a header of its requests to the project alone; the form it is sent in is
  masked in the run's log, like the token itself.
- The page (`tools/hive/page.py`) is one more job after `apply`, without any right but to publish: it is not in
  this file.
- A second, lighter workflow that runs `plan` and `record` only, more often, would deal tasks sooner
  (docs/plan.md, 3.2). It is not designed: GitHub keeps one waiting run per concurrency group, so two workflows
  sharing the group would replace each other's waiting runs.

## What could not be tried here

**Since the first real runs (16 November 2026)**, for the first project, these points of the list below have been
met for real: the whole run, with both keys; the forks listed with the read-only token; `artifact.py` on GitHub's
own archives; the judge's image made from a clone of the project, and miniz's judge on the trees the hive hands it
(a run with one candidate ends in about three to four minutes, by GitHub's own record of the runs); a push the
project's repository declined, which the hive recorded as a declined push. The list is kept as it was written before
those runs. Still untried in it: an environment restricted to `main` refusing a job started on another ref; what
`!cancelled()` gives when the judging job is stopped at its time limit; whether commits authored under a member's
no-reply address count on their profile. The dry run of its last point was not made: the second real candidate
showed the case (a correct candidate short of a proof alone), and a rule of the same day removes its cost to the
member ([decisions.md](decisions.md), 16 November); how often the judge refuses work that is in fact better is
still unmeasured. One point that list does not hold: a run that finds the state repository moved by another
project's run takes what that run saved and pushes again (setting 8 above, [decisions.md](decisions.md), 17
November); no run has met that case yet, and it has run in the tests only. The second project's file (setting 8
above) ran out of its pause on 17 November 2026, started by hand seven times: the first of those runs wrote the
project's folder in the state repository, and in the six after it the project's five tasks were dealt one after
another to the founder's worker, judged by the judge's second kind on a hosted runner and integrated, every one
accepted (for each candidate: three builds of its leaf, executed six times in all, and 18,000 to 36,000 cases
compared). Untried there: a candidate that kind refuses, and a failure to judge.

- The whole run: there is no Docker in the builder's environment, and the builder holds neither App's key (on
  purpose: the keys are the founder's to enter, in the registry's settings, and nowhere else).
- That `gh api` lists a public repository's forks with the workflow's read-only token (it should: the data is
  public).
- **How `artifact.py` meets GitHub**: that a job's own token, with `actions: read`, lists and downloads the
  artifacts of the run it belongs to while that run is in progress (GitHub's documentation says so), and that
  the archive GitHub hands over is, byte for byte, the one the upload action wrote. The tool reads the layout
  that action's code writes for one file (a header, the deflated data, sixteen bytes of sizes, a directory of one
  entry, the end record, no comment and no extra field); it was tested on archives its tests make that way,
  never on one of GitHub's. If the layout differs in anything, it refuses: the first real run tells, and nothing
  is pushed meanwhile. (The upload steps must keep the action's default compression: at `compression-level: 0`
  the action stores members instead of deflating them, a layout the tool refuses.)
- That an environment restricted to `main` refuses a job started on another ref, and what `!cancelled()` gives
  when the judging job is stopped at its time limit rather than by a person.
- That miniz's own judge works on the trees the hive hands it. It reads files of the project frozen at an old
  commit by their git id; the hive now puts the commits the project's file lists (`judge.history`) in the base tree
  it writes, which was tested with a stand-in judge, never with miniz's.
- That the common judge builds its image from a clone of the project (`--tooling project --image-only`) outside
  the pull-request flow it was written for, and how long a judgement of miniz takes (the plan's phase 1 target is
  under ten minutes).
- GitHub's message when a rule declines a push (the code looks for "remote rejected" and "declined"), and whether
  commits authored under a member's no-reply address count on their profile.
- **How often miniz's judge refuses a candidate that is in fact better.** Its tasks ask for a gain beyond the
  noise (nine comparisons won in ten). A dry run, before any volunteer: judge the project's tip against itself
  twenty times (every one must be "correct", none "better"), and a known improvement twenty times (count the
  refusals). If good work is refused more than one time in ten, loosen `judge.require` before the pilot.
