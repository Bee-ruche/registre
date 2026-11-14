# The hive's hourly run

*The workflow of phase 1 (docs/plan.md, 7.2): [`.github/workflows/hive.yml`](../.github/workflows/hive.yml). The run
holds the right to write to a project, so it entered the repository only after another model than the one that
wrote it had reviewed it, with `tools/test_bee.py` listing its permissions
(`test_the_workflows_security_is_unchanged`) and holding its rules (`TestHiveWorkflow`). **It has never run.** On
`main` it starts every hour and all four jobs are skipped, as long as the repository variable `HIVE_PROJECTS` is
empty; and the commit of the registry it would check out is forty zeros until a pull request of the founder names
one (setting 7 below). What could not be tried is listed at the end.*

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
   - a *project* App, installed on the hosted projects only (`minizBee`).

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
4. **Each hosted project's branch**: pushes allowed to the integration identity and the maintainers, force pushes
   blocked, no required pull request for the identity.
5. **The repository variable `HIVE_PROJECTS`** (for instance `miniz`): the run does nothing while it is empty, in
   addition to each project's own `"paused": true`.
6. **Actions settings**: workflows may not approve pull requests; artifacts kept a few days.
7. **Which version of the hive a run uses: one commit, named in the workflow file** (decided 13 November 2026).
   Every job checks out the registry at that commit and at no other: the hive's code, its settings and its tasks
   change when a pull request that a person reviewed changes that line, and at no other time. The file holds forty
   zeros in its place, which no checkout can find: the line is set, by a pull request of its own, to the commit of
   `main` that the founder accepted, after this file is on `main`. A new batch of tasks is such a pull request too.

## The file

[`.github/workflows/hive.yml`](../.github/workflows/hive.yml) is the run, and the only text of it: this document
explains it and does not repeat it. One project per workflow file: `miniz` is written in full where a name is
needed. `HIVE_PROJECTS` is a switch, not a list the run reads: the run does nothing while it is empty.

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
- **To stop the hive**: cancel the run in flight (its `apply` then does not run), and empty `HIVE_PROJECTS` for the
  runs to come: both take effect at once, and neither needs a pull request. A project's `"paused": true` stops
  it too, but only from the day the workflow file names a commit of the registry that holds it: a run reads the
  registry at the commit the file names, not at `main`.
- The rules above are held by a test of the file itself (`tools/test_bee.py`, `TestHiveWorkflow`): the four jobs
  are held word for word (whoever changes a line of one changes the test in the same commit, in sight of a
  reviewer), and the rules they obey are stated beside them: which jobs name an environment, where a secret may
  appear, that no job with an environment uses the common download action, the guards on the ref and on a
  cancelled run, the pins, the schedule.
- The project's token reaches git as a header of its requests to the project alone; the form it is sent in is
  masked in the run's log, like the token itself.
- The page (`tools/hive/page.py`) is one more job after `apply`, without any right but to publish: it is not in
  this file.
- A second, lighter workflow that runs `plan` and `record` only, more often, would deal tasks sooner
  (docs/plan.md, 3.2). It is not designed: GitHub keeps one waiting run per concurrency group, so two workflows
  sharing the group would replace each other's waiting runs.

## What could not be tried here

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
