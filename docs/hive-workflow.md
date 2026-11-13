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
| `plan` | `hive.py plan` | the registry, the project, the forks (public) | nothing: it uploads `plan.json` and the bundle, and publishes the plan's SHA-256 as a job output | holds a secret; runs code from a fork |
| `record` | `hive.py record` | the registry, the plan | the state repository (`Bee-ruche/hive-state`) | reads a fork; runs anyone's code; holds the project's token |
| `judge` | `hive.py judge` | the registry, the project, the plan and the bundle | nothing: it uploads `verdicts.json` | holds a secret; talks to a fork; has the network while a candidate's code runs |
| `apply` | `hive.py apply` | the registry, the project, the plan, the bundle, the verdicts | the project's branch (integration identity) and the state repository | reads a fork; runs anyone's code |

Three things carry it:

1. **The plan's SHA-256 is a job output**, not a file: `record` and `apply` receive it from GitHub, not from an
   artifact a later job could have replaced, and refuse a plan that does not match.
2. **The project's token is given to one step of one job** (`apply`), through that step's environment. It is
   asked of GitHub for that run, lasts an hour and reaches one repository; the key that obtains it is readable in
   one environment only.
3. **One run at a time per project** (`concurrency`, never cancelled in progress): two runs overlapping are safe
   by the protocol (the jobs that write check the ledger the plan read), and wasteful.

## The settings only the founder can make

1. **The state repository**: `Bee-ruche/hive-state`, public (the founder's choice: a repository of its own, so
   that the jobs that write the state hold no right on the registry at all). It needs one first commit (a README),
   so that it has a branch to check out.
2. **Two integration identities, kept apart**: two GitHub Apps of the organization, each with the repository
   permission "Contents: read and write" and nothing else, no webhook:
   - a *state* App, installed on `hive-state` only;
   - a *project* App, installed on the hosted projects only (`minizBee`).

   The workflow asks GitHub, at each run, for a token of an hour for one repository
   (`actions/create-github-app-token`, pinned to a commit). It needs, in the registry's settings:

   | Name | Kind | Where | Holds |
   | --- | --- | --- | --- |
   | `HIVE_STATE_APP_CLIENT_ID` | variable | repository | the state App's client id (not a secret) |
   | `HIVE_PROJECT_APP_CLIENT_ID` | variable | repository | the project App's client id (not a secret) |
   | `HIVE_STATE_APP_PRIVATE_KEY` | secret | environments `hive-state` and `hive-apply` | the state App's private key |
   | `HIVE_PROJECT_APP_PRIVATE_KEY` | secret | environment `hive-apply` only | the project App's private key |

   `record` runs in the environment `hive-state`, `apply` in `hive-apply` (a job has one environment, and `apply`
   writes both the project and the state). No other job names an environment, so no other job can read a key.
3. **Each hosted project's branch**: pushes allowed to the integration identity and the maintainers, force pushes
   blocked, no required pull request for the identity.
4. **The repository variable `HIVE_PROJECTS`** (for instance `miniz`): the run does nothing while it is empty, in
   addition to each project's own `"paused": true`.
5. **Actions settings**: workflows may not approve pull requests; artifacts kept a few days.

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
    if: vars.HIVE_PROJECTS != ''
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
      - name: Plan (reads the forks, once; no secret but the read-only token gh needs to list forks)
        id: plan
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          python3 registry/tools/hive/hive.py plan --registry registry --project miniz --state state \
            --repo project --out plan.json --bundle candidates.bundle >> "$GITHUB_OUTPUT"
          touch candidates.bundle
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with: { name: plan, path: "plan.json\ncandidates.bundle", retention-days: 3 }

  record:
    needs: plan
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    environment: hive-state          # the state App's key, and no other
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { path: registry, persist-credentials: false }
      - name: A token of an hour for the state repository, and nothing else
        id: state
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: ${{ vars.HIVE_STATE_APP_CLIENT_ID }}
          private-key: ${{ secrets.HIVE_STATE_APP_PRIVATE_KEY }}
          owner: Bee-ruche
          repositories: hive-state
          permission-contents: write
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { repository: Bee-ruche/hive-state, path: state, token: "${{ steps.state.outputs.token }}" }
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with: { name: plan }
      - name: Record the deals and publish the feed
        env:
          PLAN_SHA256: ${{ needs.plan.outputs.plan_sha256 }}
        run: |
          python3 registry/tools/hive/hive.py record --registry registry --project miniz --state state \
            --plan plan.json --plan-sha256 "$PLAN_SHA256" --commit-state

  judge:
    needs: [plan, record]
    runs-on: ubuntu-24.04
    timeout-minutes: 300
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
        with: { name: plan }
      - name: The judge's image (with network, before any candidate's file is on this machine's disk)
        run: python3 registry/tools/judge/judge.py --tooling project --image-only
      - name: Judge the plan's candidates (their code runs only in containers without network)
        run: |
          mkdir -p work judge-work
          python3 registry/tools/hive/hive.py judge --registry registry --project miniz --state state \
            --repo project --plan plan.json --bundle candidates.bundle --workdir work \
            --judge-workdir judge-work --out verdicts.json
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        if: always()
        with: { name: verdicts, path: verdicts.json, retention-days: 3 }

  apply:
    needs: [plan, record, judge]
    if: always() && needs.plan.result == 'success'   # even when the judging failed: what it left is used
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    environment: hive-apply          # the only place the project App's key can be read (it also holds the state's)
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { path: registry, persist-credentials: false }
      - name: A token of an hour for the state repository
        id: state
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: ${{ vars.HIVE_STATE_APP_CLIENT_ID }}
          private-key: ${{ secrets.HIVE_STATE_APP_PRIVATE_KEY }}
          owner: Bee-ruche
          repositories: hive-state
          permission-contents: write
      - name: A token of an hour for the project, and nothing else
        id: project
        uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
        with:
          client-id: ${{ vars.HIVE_PROJECT_APP_CLIENT_ID }}
          private-key: ${{ secrets.HIVE_PROJECT_APP_PRIVATE_KEY }}
          owner: Bee-ruche
          repositories: minizBee
          permission-contents: write
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with: { repository: Bee-ruche/hive-state, path: state, token: "${{ steps.state.outputs.token }}" }
      - name: The project
        run: git clone --quiet https://github.com/Bee-ruche/minizBee project
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with: { name: plan }
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0
        with: { name: verdicts }
        continue-on-error: true      # no answers at all is a case the write step knows
      - name: Push what the judge accepted, and record (the only step that holds the project's token)
        env:
          PLAN_SHA256: ${{ needs.plan.outputs.plan_sha256 }}
          HIVE_PROJECT_TOKEN: ${{ steps.project.outputs.token }}
        run: |
          auth=$(printf 'x-access-token:%s' "$HIVE_PROJECT_TOKEN" | base64 -w0)
          git -C project config http.https://github.com/Bee-ruche/minizBee.extraheader "Authorization: Basic $auth"
          test -f verdicts.json || echo '{}' > verdicts.json
          python3 registry/tools/hive/hive.py apply --registry registry --project miniz --state state \
            --repo project --plan plan.json --plan-sha256 "$PLAN_SHA256" --bundle candidates.bundle \
            --verdicts verdicts.json --commit-state
```

Notes on the draft:

- **No expression appears in a `run:` line** (the registry's rule: a text never becomes code); expressions are
  passed through `env:`.
- `plan` prints `plan_sha256=…` on its standard output and its figures on its error output: the first goes to
  `$GITHUB_OUTPUT`.
- `record` and `apply` check out the state repository with a token of the state App, which `hive.py
  --commit-state` uses to push the state. `plan` and `judge` check it out without credentials. No job has a right to write to
  the registry.
- The page (`tools/hive/page.py`) is one more job after `apply`, without any right but to publish: it is not in
  this draft.
- A second, lighter workflow that runs `plan` and `record` only, every ten minutes, would deal tasks sooner
  (docs/plan.md, 3.2). It needs nothing new: the same two jobs, in the same concurrency group.

## What could not be tried here

- The whole run: there is no Docker in the builder's environment, no integration identity, no state repository.
- That `gh api` lists a public repository's forks with the workflow's read-only token (it should: the data is
  public).
- That the common judge builds its image from a clone of the project (`--tooling project --image-only`) outside
  the pull-request flow it was written for, and how long a judgement of miniz takes (the plan's phase 1 target is
  under ten minutes).
- GitHub's message when a rule declines a push (the code looks for "remote rejected" and "declined"), and whether
  commits authored under a member's no-reply address count on their profile.
- **How often miniz's judge refuses a candidate that is in fact better.** Its tasks ask for a gain beyond the
  noise (nine comparisons won in ten). A dry run, before any volunteer: judge the project's tip against itself
  twenty times (every one must be "correct", none "better"), and a known improvement twenty times (count the
  refusals). If good work is refused more than one time in ten, loosen `judge.require` before the pilot.
