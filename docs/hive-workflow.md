# The hive's hourly run: the workflow, before it exists

*A draft for phase 1 (docs/plan.md, 7.2). It is a document on purpose, not a file under `.github/workflows/`: the
run it describes holds the right to write to a project, so it enters the repository only once the founder has made
the settings below, another model than the one that wrote it has reviewed it, and `tools/test_bee.py` lists its
permissions (`test_the_workflows_security_is_unchanged`). Nothing here has run: what could not be tried is listed
at the end.*

## What it must guarantee

The protocol (docs/protocol.md, "Four jobs, each with one risk") gives each job one risk. The workflow's only
task is to keep them apart:

| Job | Runs | May read | May write | Never |
| --- | --- | --- | --- | --- |
| `plan` | `hive.py plan` | the registry, the project, the forks (public) | nothing: it uploads `plan.json` and the bundle, and publishes the plan's SHA-256 as a job output | holds a key; runs code from a fork |
| `record` | `hive.py record` | the registry, the plan | the state repository (`Bee-ruche/hive-state`) | reads a fork; runs anyone's code; holds the project's key; unpacks another job's archive |
| `judge` | `hive.py judge` | the registry, the project, the plan and the bundle | nothing: it uploads `verdicts.json` | holds a key; talks to a fork; has the network while a candidate's code runs |
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
   **A run that a person cancels pushes nothing**: `apply` runs when the judging failed, never when the run was
   cancelled.

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
   secret, so the draft names them directly. It needs, in the registry's settings, their private keys:

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
7. **Which version of the hive a run uses** (a decision, not yet taken): the draft checks out the registry at
   the commit of `main` that started the run. The stricter choice is one commit named in the workflow file, for
   every job, changed only by a pull request a person reviewed: the hive's code, its settings and its tasks then
   change when a person says so, and at no other time.

## The draft

One project per run of the matrix; `miniz` is written in full where a name is needed.

```yaml
name: Hive
on:
  schedule:
    - cron: "17 * * * *"          # hourly, away from the hour
  workflow_dispatch:
permissions: {}                    # each job asks for what it needs
concurrency:
  group: hive-miniz
  cancel-in-progress: false

jobs:
  plan:
    if: vars.HIVE_PROJECTS != '' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    permissions:
      contents: read
    outputs:
      plan_sha256: ${{ steps.plan.outputs.plan_sha256 }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { path: registry, persist-credentials: false }
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { repository: Bee-ruche/hive-state, path: state, persist-credentials: false }
      - name: The project, in full (its branches under refs/remotes/origin)
        run: git clone --quiet https://github.com/Bee-ruche/minizBee project
      - name: Plan (reads the forks, once; no key, only the read-only token gh needs to list forks)
        id: plan
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          python3 registry/tools/hive/hive.py plan --registry registry --project miniz --state state \
            --repo project --out plan.json --bundle candidates.bundle >> "$GITHUB_OUTPUT"
          touch candidates.bundle
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with: { name: plan, path: plan.json, retention-days: 3 }
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with: { name: candidates, path: candidates.bundle, retention-days: 3 }

  record:
    needs: plan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    environment: hive-state          # the state App's key, and no other
    permissions:
      contents: read
      actions: read                  # to read this run's own artifacts
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { path: registry, persist-credentials: false }
      - name: Take the plan (one named file, before this job holds any key)
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          mkdir taken
          python3 registry/tools/hive/artifact.py take --name plan --member plan.json:67108864 --into taken/plan
      - name: A token of an hour for the state repository, and nothing else
        id: state
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: Iv23liBJswEbZCt56yvz   # the state App
          private-key: ${{ secrets.HIVESTATESECRET }}
          owner: Bee-ruche
          repositories: hive-state
          permission-contents: write
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { repository: Bee-ruche/hive-state, path: state, token: "${{ steps.state.outputs.token }}" }
      - name: Record the deals and publish the feed
        env:
          PLAN_SHA256: ${{ needs.plan.outputs.plan_sha256 }}
        run: |
          python3 registry/tools/hive/hive.py record --registry registry --project miniz --state state \
            --plan taken/plan/plan.json --plan-sha256 "$PLAN_SHA256" --commit-state

  judge:
    needs: [plan, record]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    timeout-minutes: 330             # the time allowed for judging (4 h), one last check of the machine (1 h), the setup
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { path: registry, persist-credentials: false }
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { repository: Bee-ruche/hive-state, path: state, persist-credentials: false }
      - name: The project
        run: git clone --quiet https://github.com/Bee-ruche/minizBee project
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with: { name: plan, path: taken/plan }
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with: { name: candidates, path: taken/candidates }
      - name: The judge's image (with network, before any candidate's file is on this machine's disk)
        run: python3 registry/tools/judge/judge.py --tooling project --image-only
      - name: Judge the plan's candidates (their code runs only in containers without network)
        run: |
          mkdir -p work judge-work
          python3 registry/tools/hive/hive.py judge --registry registry --project miniz --state state \
            --repo project --plan taken/plan/plan.json --bundle taken/candidates/candidates.bundle --workdir work \
            --judge-workdir judge-work --out verdicts.json
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        if: always()
        with: { name: verdicts, path: verdicts.json, retention-days: 3 }

  apply:
    needs: [plan, record, judge]
    # Even when the judging failed (what it left is used); never when a person cancelled the run.
    if: ${{ !cancelled() && needs.plan.result == 'success' && github.ref == 'refs/heads/main' }}
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    environment: hive-apply          # the only place the project App's key can be read (it also holds the state's)
    permissions:
      contents: read
      actions: read                  # to read this run's own artifacts
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { path: registry, persist-credentials: false }
      - name: Take the plan, the candidates and the judge's answers (named files, before this job holds any key)
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          mkdir taken
          python3 registry/tools/hive/artifact.py take --name plan --member plan.json:67108864 --into taken/plan
          python3 registry/tools/hive/artifact.py take --name candidates --member candidates.bundle:2147483648 \
            --into taken/candidates
          # No answers at all is a case the write step knows: an archive that is missing, or refused, is that case.
          python3 registry/tools/hive/artifact.py take --name verdicts --member verdicts.json:16777216 \
            --into taken/verdicts || { mkdir -p taken/verdicts && echo '{}' > taken/verdicts/verdicts.json; }
      - name: A token of an hour for the state repository
        id: state
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: Iv23liBJswEbZCt56yvz   # the state App
          private-key: ${{ secrets.HIVESTATESECRET }}
          owner: Bee-ruche
          repositories: hive-state
          permission-contents: write
      - name: A token of an hour for the project, and nothing else
        id: project
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: Iv23liKHEG0w2XgtSc9m   # the project App
          private-key: ${{ secrets.HIVEAPPLYSECRET }}
          owner: Bee-ruche
          repositories: minizBee
          permission-contents: write
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { repository: Bee-ruche/hive-state, path: state, token: "${{ steps.state.outputs.token }}" }
      - name: The project
        run: git clone --quiet https://github.com/Bee-ruche/minizBee project
      - name: Push what the judge accepted, and record (the only step that holds the project's token)
        env:
          PLAN_SHA256: ${{ needs.plan.outputs.plan_sha256 }}
          HIVE_PROJECT_TOKEN: ${{ steps.project.outputs.token }}
        run: |
          auth=$(printf 'x-access-token:%s' "$HIVE_PROJECT_TOKEN" | base64 -w0)
          git -C project config http.https://github.com/Bee-ruche/minizBee.extraheader "Authorization: Basic $auth"
          python3 registry/tools/hive/hive.py apply --registry registry --project miniz --state state \
            --repo project --plan taken/plan/plan.json --plan-sha256 "$PLAN_SHA256" \
            --bundle taken/candidates/candidates.bundle --verdicts taken/verdicts/verdicts.json --commit-state
```

Notes on the draft:

- **No expression appears in a `run:` line** (the registry's rule: a text never becomes code); expressions are
  passed through `env:`.
- `plan` prints `plan_sha256=…` on its standard output and its figures on its error output: the first goes to
  `$GITHUB_OUTPUT`.
- `record` and `apply` check out the state repository with a token of the state App, which `hive.py
  --commit-state` uses to push the state. `plan` and `judge` check it out without credentials. No job has a right
  to write to the registry.
- `judge` holds no key, so it may unpack the plan's archives with the common action; `record` and `apply` use
  `tools/hive/artifact.py` (tests: `tools/hive/test_artifact.py`), with the run's own read-only token.
- **To stop the hive**: cancel the run in flight (its `apply` then does not run), and empty `HIVE_PROJECTS` or set
  the project's `"paused": true` for the runs to come. A run reads the registry at the commit it started on.
- The rules above are held by a test of this very draft (`tools/test_bee.py`, `TestHiveWorkflowDraft`): which
  jobs name an environment, where a secret may appear, that no job with an environment uses the common download
  action, the guards on the ref and on a cancelled run, the pins.
- The page (`tools/hive/page.py`) is one more job after `apply`, without any right but to publish: it is not in
  this draft.
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
  is pushed meanwhile.
- That an environment restricted to `main` refuses a job started on another ref, and what `!cancelled()` gives
  when the judging job is stopped at its time limit rather than by a person.
- That the common judge builds its image from a clone of the project (`--tooling project --image-only`) outside
  the pull-request flow it was written for, and how long a judgement of miniz takes (the plan's phase 1 target is
  under ten minutes).
- GitHub's message when a rule declines a push (the code looks for "remote rejected" and "declined"), and whether
  commits authored under a member's no-reply address count on their profile.
- **How often miniz's judge refuses a candidate that is in fact better.** Its tasks ask for a gain beyond the
  noise (nine comparisons won in ten). A dry run, before any volunteer: judge the project's tip against itself
  twenty times (every one must be "correct", none "better"), and a known improvement twenty times (count the
  refusals). If good work is refused more than one time in ten, loosen `judge.require` before the pilot.
