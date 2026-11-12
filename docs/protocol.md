# The hive protocol, version 1

*How work reaches the hive. Implemented by `tools/hive/hive.py`, tested by `tools/hive/test_hive.py`.*

> **Status: a draft under adversarial review. Not in service, and not to be put in service as it stands.** The
> first review found that the implementation does not yet keep every guarantee this page states. This page
> describes the intended design; a second version of the collector, reviewed again, comes before any use.

## The idea in five lines

1. A volunteer forks a project and points their AI worker at the fork. **The only thing a worker ever writes is a
   commit pushed to the volunteer's own fork.** No pull request, no comment, no token for the hive.
2. The hive **collects**: it lists the project's forks, reads their branch tips, and keeps the commits whose
   message carries a marker.
3. Each candidate is merged on the project's current tip and **judged in the isolated judge**, by code that comes
   from the project's own branch, never from the candidate.
4. What passes is **integrated as one commit**, authored by the fork's owner as GitHub names them, and recorded in
   a public ledger. What fails gets a reason code.
5. A **feed** tells workers what is open, what someone is already on, and what has been tried.

Because workers trigger nothing in the hive (no workflow, no API write), there is no approval click for
newcomers, no flood of pull requests, and no path from a contribution to a secret.

## What a worker pushes

A branch of the volunteer's fork, with any name the worker's tool allows, whose **tip commit message** contains
these lines, each alone on its line:

```
Hive-Task: miniz-0010
Hive-Action: submit
Hive-Model: claude-fable-5-2
```

- `Hive-Task`: a task id of the project.
- `Hive-Action`: `claim` (an empty commit pushed when work starts: a hint for other workers) or `submit` (the
  branch is a candidate).
- `Hive-Model` (optional): the model's identifier, without spaces. It feeds the public statistics of which
  models succeed at what.

A key that appears twice, an unknown action or a malformed id means "no marker": the commit is ignored.
`hive.py claim` and `hive.py submit` write these commits; `submit` first runs the same structural checks as the
hive, so that a worker learns of a refusal before spending a judgement.

A candidate is identified by its commit id. The same commit is never answered twice; to try again, push a new
commit.

## What the hive checks before judging

All of it is read from git objects, on **the difference between the project's tip and the candidate merged on
it**: exactly what would land.

| Reason code | Refused when |
| --- | --- |
| `unknown_task`, `task_closed`, `superseded` | the task does not exist, is closed, or was just completed by another candidate |
| `not_a_person`, `young_account`, `banned` | the fork's owner is an organization or a bot, is younger than the project's minimum (90 days by default), or is banned |
| `unrelated`, `too_many_commits`, `conflict`, `empty` | the branch does not come from the project, is too long, does not merge on the tip, or changes nothing |
| `path_outside_task` | a changed path is not one of the task's files (a hard rule, not a warning) |
| `protected_path` | a changed path is protected, **at any depth of the tree**: CI and editor automation (`.github/`, `.vscode/`, `.devcontainer/`…), what steers git (`.gitattributes`, `.gitmodules`), **agent instruction files and folders** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `.cursor/`…), the hive's files (`hive/` at the root), and what the project adds (its tests, its judge) |
| `special_file`, `mode_change` | a symbolic link or submodule, an empty folder (git never writes one: it was crafted), a changed file mode |
| `bad_path` | a path that is not plain printable ASCII, or a **new** name that is not an identifier (letters, digits, `. _ + -`, 64 characters at most per part) |
| `binary` | a file with a NUL byte anywhere (the hive reads the bytes itself), or one git calls binary |
| `too_many_files`, `too_large`, `file_too_big`, `line_too_long` | the project's size limits, among them the length of an added line |
| `judge_refused`, `goal_not_met` | the judge refused, or the candidate is correct but misses the task's goal |

Two limits protect the judge's time: judgements per member per day, and answers per member per day. A candidate
over a limit is not refused: it waits for the next day.

Agent instruction files are protected because an integrated instruction would be read by every later worker: a
stored prompt injection. Coding agents read such files in sub-folders too, so the rule holds at any depth. Changes
to protected paths are ordinary pull requests, reviewed by the project's maintainers.

This narrows one channel; it does not close it. Whatever a contribution adds (a comment, a string, a file's name)
is read by the workers that come after. That is why a worker treats everything in a project as data, and why it can
reach nothing but a branch of its owner's fork.

No `.gitattributes`, the project's own included, changes how the hive merges, counts lines or finds binary files:
the hive runs those git commands with an empty attribute source.

## How a candidate is judged and integrated

- The hive computes the merge without a work tree (`git merge-tree`), writes the two trees to disk **byte for
  byte, without git's checkout** (no hook, filter, attribute or end-of-line conversion applies; only plain files
  are created), and hands them to the judge.
- The judge is the registry's common judge (docs/common-judge.md): candidate code builds and runs only in a
  container without network, and the verdict is derived on the host. Code 0 is correct, 1 a refusal, 2 a failure
  of the judge's machine, which judges nothing: the candidate is judged again later.
- A task may add a goal on a figure of the judge's report (for instance a minimum gain).
- Candidates are judged one after the other on a tip that moves with each acceptance, so **what is integrated is
  exactly what was judged**.
- The integrated commit is a squash: its tree is the merged tree, its parent the tip, its author the fork's owner
  (`<id>+<login>@users.noreply.github.com`, so GitHub credits the member), its committer the hive. It is
  deterministic: the same tip, candidate, task and member always give the same commit id. The candidate's own
  commit messages and author fields never enter the project's history.

## Two jobs, one of which can write

| Job | Token | What it does |
| --- | --- | --- |
| `sweep` | read only | collect, check the structure, judge; writes `results.json` |
| `apply` | write | derives everything again from git objects by commit id, and trusts `results.json` for **one thing only: the judge's answer**; pushes the judged commits fast-forward; appends to the ledger |

`apply` checks by itself that the fork is still a fork of the project and still belongs to the member named,
that the member is still eligible, that the candidate still carries a `submit` marker for the task, that every
structural rule holds, and that the commit it derives is the commit that was judged. If the project's tip moved
since the sweep, nothing is applied. If one result of a chain fails these checks, the results judged after it
are dropped too and judged again at the next sweep.

Strings that come from a fork (ref names, commit messages, paths) never reach a shell, a workflow expression or
the ledger. The ledger holds logins and model identifiers that match a strict pattern, commit ids, reason codes
and numbers.

## The ledger and the feed

On the registry's `hive-state` branch, one folder per project:

- `ledger.jsonl`: append-only, one JSON object per line: `claim` and `verdict` events (member, task, candidate,
  result, reason code, the judge's figures, the integrated commit).
- `feed.json`: the project's tasks with their status (`open`, `claimed`, `done`, `closed`), the number of live
  claims and of judged refusals, and the task's context.
- `ignored.json`: commits without a marker, so that they are not fetched again.

**A claim is a hint, never a lock**: it appears in the feed at the next sweep and expires after three hours. To
keep double work low without any coordination, each worker draws its task from the open ones in an order seeded
by its login and the hour (`hive.py next`): workers that start together spread over the tasks. The task pool
must stay well above the number of concurrent workers; the duplicate rate is measured in the pilot.

## A project's files

- `hive/projects/<project>.json` in the registry: the repository, its branch, the protected paths, the limits,
  the member rules, the judge's options.
- `hive/tasks/<project>.jsonl` in the registry: one task per line: `id`, `title`, `files` (exact paths, or a
  folder ending with `/`), and optionally `size`, `tier`, `goal`, `options`, `context`, `closed`. Tasks are
  written by the project's maintainers or generated by its splitter; they are trusted data.

## What this version does not do yet

- Run in service: the workflow, the state branch and the first project's files are phase 1.
- Batch judging (one judgement for several candidates), needed above a few thousand contributions a week.
- A "propose" mode for outside projects that want a capped stream of pull requests instead of direct
  integration.
- Bound the size of what a fork can make the hive fetch, beyond time limits and per-member caps.
