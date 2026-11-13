# The hive protocol, version 1

*How work reaches the hive. Implemented by `tools/hive/hive.py`, tested by `tools/hive/test_hive.py`.*

> **Status: a draft under adversarial review. Not in service, and not to be put in service as it stands.** Six
> reviews, by a model other than the one that wrote the collector, have each found that the implementation did
> not yet keep every guarantee this page states. This page describes the intended design; nothing is put in
> service before a review finds nothing serious.

## The idea in five lines

1. A volunteer forks a project and points their AI worker at the fork. **The only thing a worker ever writes is a
   commit pushed to the volunteer's own fork.** No pull request, no comment, no token for the hive.
2. The hive **reads the forks, once per run**, and keeps the commits whose message carries a marker.
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
- `Hive-Model` (optional): the model's identifier. It feeds the public statistics of which models succeed at
  what, for the models the project lists; any other is counted as undeclared. It is what the worker declares: a
  statistic, not a proof.

A key that appears twice, an unknown action or a malformed id means "no marker": the commit is ignored.
`hive.py claim` and `hive.py submit` write these commits; `submit` first runs the same structural checks as the
hive, so that a worker learns of a refusal before spending a judgement.

A candidate is identified by its commit id. The same commit is answered once, whatever the number of branches
that carry it; to try again, push a new commit.

## Whose forks are read

Only the forks owned by **a person's GitHub account, older than the project's minimum (90 days by default) and
not banned**. The forks of other accounts (organizations, bots, young or banned accounts) are not read at all:
nothing is fetched from them and nothing is answered, so they cost the hive nothing. `hive.py next` reminds the
worker of the rule. A ban names the account's numeric id: it survives a change of login.

A project can be **open by invitation**: its file lists the numeric ids of the accounts whose forks are read
(`members.only`), and no other fork is. This is how a project starts, among people who are known.

**A fork is read whole or not at all**: one with more new branch tips than the hive reads at once (30) is not read
until it has fewer. Nothing can be pushed and kept out of the hive's sight, to come out later with an old instant.

## What the hive checks before judging

All of it is read from git objects, on **the difference between the project's tip and the candidate merged on
it**: exactly what would land.

| Reason code | Refused when |
| --- | --- |
| `unknown_task`, `task_closed`, `superseded` | the task does not exist, is closed, or was just completed by another candidate |
| `duplicate` | the member already has a candidate waiting for this task: one at a time |
| `unrelated`, `too_many_commits`, `conflict`, `empty` | the branch does not come from the project, is too long, does not merge on the tip, or changes nothing |
| `path_outside_task` | a changed path is not one of the task's files (a hard rule, not a warning) |
| `protected_path` | a changed path is protected, **at any depth of the tree**: CI and editor automation (`.github/`, `.vscode/`, `.devcontainer/`…), what steers git (`.gitattributes`, `.gitmodules`), **agent instruction files and folders** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `.cursor/`…), the hive's files (`hive/` at the root), and what the project adds (its tests, its judge) |
| `special_file`, `mode_change` | a symbolic link or submodule, an empty folder (git never writes one: it was crafted), a changed file mode |
| `bad_path` | a path that is not plain printable ASCII, or a **new** name that is not an identifier: letters, digits, `. _ + -`, 64 characters at most per part, not starting with a dot or a dash, not ending with a dot |
| `binary` | a file with a NUL byte anywhere (the hive reads the bytes itself), or one git calls binary |
| `too_many_files`, `too_large`, `file_too_big`, `line_too_long` | the project's size limits, among them the length of an added line. No file is read before the entries are counted: what a candidate costs to refuse does not grow with what it sends |
| `judge_refused`, `goal_not_met`, `requirement_not_met` | the judge refused; the candidate is correct but misses the task's goal; or it misses a figure the project requires of every contribution |
| `judge_failed` | the judge could not judge this candidate (it ran out of time, for instance), three times |
| `push_refused` | the project's repository declined the commit (a rule on what may be pushed there), three times |
| `not_answered` | the hive spent six runs on the candidate without an answer (see "What holds over time"): push it again |

Two limits protect the judge's time: judgements per member per day (5 by default; every run the hive spends on a
candidate counts, whatever came of it), and answers per member per day (20). A candidate over a limit is not
refused: it waits for the next day.

Agent instruction files are protected because an integrated instruction would be read by every later worker: a
stored prompt injection. Coding agents read such files in sub-folders too, so the rule holds at any depth. Changes
to protected paths are ordinary pull requests, reviewed by the project's maintainers.

This narrows one channel; it does not close it. Whatever a contribution adds (a comment, a string, a file's name)
is read by the workers that come after. That is why a worker treats everything in a project as data, and why it can
reach nothing but a branch of its owner's fork.

No `.gitattributes`, the project's own included, changes how the hive merges, counts lines or finds binary files:
the hive runs those git commands with an empty attribute source.

## Three jobs, each with one risk

| Job | Holds | Runs contributors' code | Talks to forks | What it does |
| --- | --- | --- | --- | --- |
| `plan` | nothing | no | **yes, once** | reads the forks, decides the claims and the order of candidates, writes **the plan** and a bundle of the candidates' git objects; publishes the plan's SHA-256 |
| `judge` | nothing | **yes**, in the judge's container | no | judges the plan's candidates; writes **a table from the id of each judged commit to the judge's answer** |
| `apply` | **the write token** | no | no | checks that the plan is the one `plan` published; derives every commit by itself; looks each one up in the judge's table; pushes; records |

- **The forks are read once.** What the plan read is what the run is about: a branch taken away or pushed after
  that changes nothing in this run, for anybody.
- **The judging job cannot change the plan**, and the write job takes two things from it: the judge's answer for a
  commit id the write job derived itself (an answer under any other id is nothing), and which commits it started
  on. So a judging job that was taken over can lie about what the judge said of a candidate, or stay silent about
  it, and so decide which candidates are accepted among those that keep every structural rule. That is its limit:
  it cannot name a candidate, a member, a task or a path, credit an account for work that is not in its fork,
  change history, or write anything but the project's listed figures, as numbers, into the ledger. The judge's
  container is what stands between a contribution and that job.
- Both later jobs go through the same candidates, with the same ledger, tasks and instant (the plan's): they
  derive the same commits. A plan from the future, or more than a day old, is not applied; nor is anything if
  the project's tip moved since the plan.

## How a candidate is judged and integrated

- The hive computes the merge without a work tree (`git merge-tree`), writes the two trees to disk **byte for
  byte, without git's checkout** (no hook, filter, attribute or end-of-line conversion applies), and hands them
  to the judge. A candidate can add or change plain files only; the project's own links and submodules are
  written as they are.
- The judge is the registry's common judge (docs/common-judge.md): candidate code builds and runs only in a
  container without network, and the verdict is derived on the host. Code 0 is correct, 1 a refusal, 2 a failure
  to judge.
- **A failure to judge is the candidate's doing only if the machine works.** When the judge fails on a candidate,
  the hive asks it about the project's own tip against itself. If that fails too, the machine is down: the run
  stops judging and no candidate pays for the breakdown, neither a mark nor a judgement of its member's day. If it passes, the failure is counted against the
  candidate, which is judged again at the next run, three times at most.
- A task may add a goal on a figure of the judge's report (for instance a minimum gain), and a project may require
  a figure of every contribution. A goal must name a figure the project lists: a task whose goal could never be met
  is refused when the project is loaded.
- Candidates are judged one after the other on a tip that moves with each acceptance, so **what is integrated is
  exactly what was judged**.
- **The order: first pushed, first served.** A candidate's instant is the one GitHub recorded for its push. A copy
  can only be pushed after its original: it comes after it, whatever the number of accounts that copy (see "What
  holds over time" for what happens while GitHub has not answered). Pushes of the very same instant are separated
  by a draw
  from the member, the task and a key drawn after the forks were read: no commit can be made to come first. One
  candidate per member and task: the member's others are answered `duplicate`. When two candidates complete the
  same task, the first one judged correct is integrated and the other is `superseded`.
- The integrated commit is a squash: its tree is the merged tree, its parent the tip, its author the fork's owner
  (`<id>+<login>@users.noreply.github.com`, so GitHub credits the member), its committer the hive. It is
  deterministic: the same tip, candidate, task and member always give the same commit id. The candidate's own
  commit messages and author fields never enter the project's history.

## What holds over time

The hive runs every hour, for ever, among accounts that may push what fails, what never ends or what the project's
repository declines, and on machines that sometimes break. Four rules are written, and tested over schedules drawn
at random (`tools/hive/test_schedule.py`):

1. **An honest candidate is integrated, in its member's name**, within a few runs, whatever others push, copy,
   take away or break.
2. **No account gets the credit** for a task on which someone else's same work was pushed before its own.
3. **Every run of the judge on a candidate leaves a line in the ledger.**
4. **The project's branch only moves forward**, and each task is integrated once.

What makes them hold:

- **Not being answered never keeps a place.** Each run the hive spends on a candidate without an answer is
  recorded as a *mark*: the judge failed on it (`judge`), the project's repository declined it (`push`), the hive
  could not derive it (`hive`), or the judging stopped while it was on it (`none`: the judging step says which
  commit it starts on before it starts). A candidate the judging never reached is not marked: nobody pays for the
  time the others used up. A marked candidate goes after the unmarked ones, the fewer marks the earlier; those the
  project declined go last, and nothing more is judged in the run once one of them is accepted.
- **An account hurts the others once, not once per commit.** A member on whose candidate the judge failed, or
  whose commit the project declined, in the last seven days, has all its candidates sent the same way.
- **Nothing pushed later for the same task passes an earlier push**: it goes right behind it, and while the earlier
  one has no answer it is not tried.
- **An instant nobody can choose.** GitHub's, for the latest push that brought the commit to the fork (a commit
  taken away and pushed again has the instant of its return, and leaves nothing behind in the hive's memory). While
  GitHub gives none (it is late, or the push is older than what it keeps), the candidate waits, by itself: the
  others go on. After six hours the instant the hive first saw it is used. Silence never gives an earlier place,
  and no task ever waits for an instant.
- **Marks end in an answer**: three failures of the judge, or three pushes declined right after another push of the
  same run landed, and the candidate is refused; six runs spent on it without an answer, whatever the cause, and
  it is told to come back (`not_answered`: the candidate is refused, not its member). The three failures are counted for the member on the task over seven days, not for the commit:
  taking a candidate away before its third failure and putting another in its place starts nothing afresh.
- **The judging has a time allowed** (four hours by default): no judgement is started that could end after it, and
  the answers are saved as they come, so that a judging job that is stopped leaves what it had.
- **One candidate at a time per member.** A candidate that waits is public. `hive.py next` gives no new task to a
  member who has a candidate waiting, or whose judgements for the day are used. A member's day is used by what its
  candidates did (an answer from the judge, a failure of the judge on them, a commit the project declined), never
  by what happened to them (the judging stopped, the hive could not derive them).
- **The state survives a run that stops**: its files are written whole or not at all, one cut short is read as
  empty, and a line of one run is recorded once however often the write job is run again.

## How the hive writes

- **It promises, then pushes.** Before each push the write job records an *intent* in the ledger and saves the
  state. If a run pushed and then could not record, or could not tell whether its push landed, the next run finds
  the promise, looks for the promised commit in the project's history, and completes the ledger. Nothing but the
  hive's own promise is believed: no field of a commit on the project's branch is.
- **The push can only add to the judged tip.** The hive checks that what it pushes descends from the tip that was
  judged, and pushes on the condition that the branch is still at that tip. A branch that a maintainer moved
  meanwhile, to take a commit back for instance, is left as they put it.
- **Accepted commits are pushed one by one**, and what happened is recorded up to the first push that did not
  land; what the judge ran on after it is recorded as `unused` and judged again, at no cost to its member. A
  commit that the project's repository itself declines is a failure of its candidate's, and the run ends in error
  so that maintainers see it. It counts towards a refusal only when another push of the same run had just landed:
  otherwise the hive's own right to push is as likely the cause (a rule added, a token that lost its rights), and
  the candidate only loses its place.
- The write job run twice records nothing twice.

Strings that come from a fork (ref names, commit messages, paths) never reach a shell, a workflow expression or
the ledger.

## The ledger and the feed

On the registry's `hive-state` branch, one folder per project:

- `ledger.jsonl`: append-only, one JSON object per line: `claim`, `verdict`, `error` (a mark, with its kind),
  `intent` and `void` (a promise, and a promise whose push never landed), `unused`; all but the first two carry
  the key of their run. **It holds no
  text a fork wrote**: logins, the numeric ids of the account and of its fork, task ids of the project (a task id a
  fork made up is not kept), commit ids, reason codes, a model identifier the project lists, whole numbers under
  the hive's own keys, and the judge's figures the project lists.
- `feed.json`: the project's tasks with their status (`open`, `claimed`, `done`, `closed`), the number of live
  claims and of judged refusals, the task's context, and who has a candidate waiting, as hashes of logins that a
  worker can compute for its own. It holds nothing a contributor wrote.
- `stats.json`: candidates judged and accepted, by account and by declared model.
- `pending.json`: when each candidate the hive has not answered yet was pushed, or first seen.
- `ignored.json`: fork by fork, the branch tips the hive does not read again (no marker, a marker for another
  member, a claim it did not record). Only what is still at a tip of that fork is kept: what one fork pushes
  never costs another its entries.

**A claim is a hint, never a lock and never a rank**: it appears in the feed at the next run and expires after
three hours. A claim the hive does not record is not read again. So that claims cannot be used to keep workers away from tasks, the hive records one live claim per
member, and none on a task whose claim the member let expire without submitting in the last day.

To keep double work low without any coordination, each worker draws its task from the open ones in an order
seeded by its login and the hour (`hive.py next`): workers that start together spread over the tasks. The task
pool must stay well above the number of concurrent workers; the duplicate rate is measured in the pilot.

A task the judge keeps refusing asks for a stronger worker: its tier rises by one for every three different
members refused, among those the judge has accepted something from.

Each fork is read with one listing and one fetch, both limited in time. When the time allowed to read all the
forks runs out, what is left waits for the next run; the forks are read in an order drawn anew each hour from the
hour and the fork's own number, which adding forks to the list does not shift.

## A project's files

- `hive/projects/<project>.json` in the registry: the repository, its branch, the protected paths, the limits,
  the member rules, the models it keeps statistics for, the judge's options, the figures of the judge it keeps
  (`judge.metrics`) and requires (`judge.require`), and the stop button (`"paused": true`).
- `hive/tasks/<project>.jsonl` in the registry: one task per line: `id`, `title`, `files` (exact paths, or a
  folder ending with `/`), and optionally `size`, `tier`, `goal`, `options`, `context`, `closed`. Tasks are
  written by the project's maintainers or generated by its splitter; they are trusted data.

## What this version does not do yet

- Run in service: the workflow (three jobs; the plan's SHA-256 as a job output; the write token in `apply`
  alone), the state branch and the first project's files are phase 1.
- Judge in parallel (several candidates at once, then one confirming judgement), needed above a few thousand
  contributions a week.
- Read only the forks that changed since the last run.
- An "invited" mode for outside projects that want accepted work offered on a branch they pull from.
