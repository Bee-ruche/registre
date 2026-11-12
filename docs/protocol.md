# The hive protocol, version 1

*How work reaches the hive. Implemented by `tools/hive/hive.py`, tested by `tools/hive/test_hive.py`.*

> **Status: a draft under adversarial review. Not in service, and not to be put in service as it stands.** A
> first review, by a model other than the one that wrote the collector, led to this second version. A second
> review comes before any use.

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
Hive-Member: alice
Hive-Model: claude-fable-5-2
```

- `Hive-Task`: a task id of the project.
- `Hive-Action`: `claim` (an empty commit pushed when work starts: a hint for other workers) or `submit` (the
  branch is a candidate).
- `Hive-Member`: the GitHub login of the fork's owner. **A commit counts only in the fork of the member it
  names**: the same commit pushed to someone else's fork is nothing there, and credits nobody else.
- `Hive-Model` (optional): the model's identifier, without spaces. It feeds the public statistics of which
  models succeed at what. It is what the worker declares: a statistic, not a proof.

A key that appears twice, an unknown action or a malformed id means "no marker": the commit is ignored.
`hive.py claim` and `hive.py submit` write these commits; `submit` first runs the same structural checks as the
hive, so that a worker learns of a refusal before spending a judgement.

A candidate is identified by its commit id. The same commit is answered once, whatever the number of branches
that carry it; to try again, push a new commit.

Only forks owned by a person's account are read. A fork owned by an organization is not: fork the project under
your own account.

## What the hive checks before judging

All of it is read from git objects, on **the difference between the project's tip and the candidate merged on
it**: exactly what would land.

| Reason code | Refused when |
| --- | --- |
| `unknown_task`, `task_closed`, `superseded` | the task does not exist, is closed, or was just completed by another candidate |
| `not_a_person`, `young_account`, `banned` | the fork's owner is not a person's account, is younger than the project's minimum (90 days by default), or is banned (a ban names the account's numeric id: it survives a change of login) |
| `unrelated`, `too_many_commits`, `conflict`, `empty` | the branch does not come from the project, is too long, does not merge on the tip, or changes nothing |
| `path_outside_task` | a changed path is not one of the task's files (a hard rule, not a warning) |
| `protected_path` | a changed path is protected, **at any depth of the tree**: CI and editor automation (`.github/`, `.vscode/`, `.devcontainer/`…), what steers git (`.gitattributes`, `.gitmodules`), **agent instruction files and folders** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `.cursor/`…), the hive's files (`hive/` at the root), and what the project adds (its tests, its judge) |
| `special_file`, `mode_change` | a symbolic link or submodule, an empty folder (git never writes one: it was crafted), a changed file mode |
| `bad_path` | a path that is not plain printable ASCII, or a **new** name that is not an identifier (letters, digits, `. _ + -`, 64 characters at most per part) |
| `binary` | a file with a NUL byte anywhere (the hive reads the bytes itself), or one git calls binary |
| `too_many_files`, `too_large`, `file_too_big`, `line_too_long` | the project's size limits, among them the length of an added line |
| `judge_refused`, `goal_not_met` | the judge refused, or the candidate is correct but misses the task's goal |
| `judge_failed` | the judge could not judge this candidate (it ran out of time, for instance), three times |

Two limits protect the judge's time: judgements per member per day (5 by default; a candidate that makes the judge
fail counts too), and answers per member per day (20). A candidate over a limit is not refused: it waits for the
next day.

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
  to judge.
- **A failure to judge is the candidate's doing only if the machine works.** When the judge fails on a candidate,
  the hive asks it about the project's own tip against itself. If that fails too, the machine is down: the sweep
  stops judging and no candidate pays for the breakdown. If it passes, the failure is counted against the
  candidate, which is judged again at the next sweep, three times at most.
- A task may add a goal on a figure of the judge's report (for instance a minimum gain).
- Candidates are judged one after the other on a tip that moves with each acceptance, so **what is integrated is
  exactly what was judged**.
- **The order is a draw.** It comes from each commit's id and a key the sweep draws after it has read the forks:
  no commit can be made to come first. When two candidates complete the same task, the first one judged correct
  is integrated and the other is `superseded`.
- The integrated commit is a squash: its tree is the merged tree, its parent the tip, its author the fork's owner
  (`<id>+<login>@users.noreply.github.com`, so GitHub credits the member), its committer the hive. It is
  deterministic: the same tip, candidate, task and member always give the same commit id. The candidate's own
  commit messages and author fields never enter the project's history.

## Two jobs, one of which can write

| Job | Token | What it does |
| --- | --- | --- |
| `sweep` | read only | reads the forks, checks the structure, judges; writes the run's instant, its key, and **a table from the id of each judged commit to the judge's answer** |
| `apply` | write | **reads the forks again and derives everything by itself**, exactly as the sweep did; looks up, in the sweep's table, the answer for each commit id it derived; pushes; appends to the ledger |

The write step takes nothing else from the sweep: no candidate, no member, no task, no path. Whatever the sweep's
file says, the write step by itself checks that the candidate is in the fork of the member its marker names, that
the member is eligible now, that the task is open, and that every structural rule holds; and the commit it pushes
is one it built. An answer under a commit id the write step does not derive is nothing. The judge's answer is the
one thing taken on trust from the sweep, which is why the sweep's job holds no write token and the judge runs
candidate code in a container.

- If the project's tip moved since the sweep, nothing is applied.
- A candidate that reached a fork after the sweep has no answer: it holds nobody back and waits for the next run.
- Both steps count days, caps and claims at the sweep's instant; a sweep from the future, or more than six hours
  old, is not applied.
- **The push can only add to the judged tip.** The hive checks that what it pushes descends from the tip that was
  judged, and pushes on the condition that the branch is still at that tip. A branch that a maintainer moved
  meanwhile, to take a commit back for instance, is left as they put it.
- The write step run twice records nothing twice.
- **The project's history is the record of what was integrated.** If a run pushed and then could not record, the
  next run reads the hive's own commits back from the branch (its own line of commits only, never what came in
  through a merge) and completes the ledger.
- When the time allowed to read the forks runs out, the forks left wait for the next run; the list is read from a
  place that moves with the hour, so that no fork is always the one left.

Strings that come from a fork (ref names, commit messages, paths) never reach a shell, a workflow expression or
the ledger.

## The ledger and the feed

On the registry's `hive-state` branch, one folder per project:

- `ledger.jsonl`: append-only, one JSON object per line: `claim`, `verdict` and `error` events (the judge failed
  on a candidate). **It holds no text a fork wrote**: logins and model identifiers that match a strict pattern,
  the numeric ids of the account and of its fork, task ids of the project (a task id a fork made up is not kept),
  commit ids, reason codes, and whole numbers under the hive's own keys.
- `feed.json`: the project's tasks with their status (`open`, `claimed`, `done`, `closed`), the number of live
  claims and of judged refusals, and the task's context. It holds nothing a contributor wrote.
- `stats.json`: candidates judged and accepted, by member and by declared model.
- `ignored.json`: commits without a marker, so that they are not fetched again.

**A claim is a hint, never a lock and never a rank**: it appears in the feed at the next run and expires after
three hours. So that claims cannot be used to keep workers away from tasks, the hive records a claim only from an
account that could submit, one live claim per member, and none on a task whose claim the member let expire
without submitting in the last day.

To keep double work low without any coordination, each worker draws its task from the open ones in an order
seeded by its login and the hour (`hive.py next`): workers that start together spread over the tasks. The task
pool must stay well above the number of concurrent workers; the duplicate rate is measured in the pilot.

A task the judge keeps refusing asks for a stronger worker: its tier rises by one for every three different
members refused.

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
