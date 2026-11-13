# The hive protocol, version 1

*How work reaches the hive. Implemented by `tools/hive/hive.py`, tested by `tools/hive/test_hive.py` and
`tools/hive/test_schedule.py`.*

> **Status: a draft under adversarial review. Not in service, and not to be put in service as it stands.** In an
> earlier draft, members competed for tasks and the hive decided who came first; review after review, by a model
> other than the one that wrote the collector, that decision was where the guarantees gave way. This draft removes
> the competition: **the hive deals each task to one member at a time.** Nothing is put in service before a review
> finds nothing serious.

## The idea in six lines

1. A volunteer forks a project and points their AI worker at the fork. **The only thing a worker ever writes is a
   commit pushed to the volunteer's own fork.** No pull request, no comment, no token for the hive.
2. The worker **asks for a task** (a marker on its fork). The hive **reads the forks, once per run**, and **deals**
   each asker one open task, for three hours. At any time at most one member may submit for a task, and the hive
   decides who.
3. The worker does the task and pushes its candidate, marked for that deal.
4. The candidate is merged on the project's current tip and **judged in the isolated judge**, by code that comes
   from the project's own branch, never from the candidate.
5. What passes is **integrated as one commit**, authored by the fork's owner as GitHub names them, and recorded in
   a public ledger. What fails gets a reason code.
6. A **feed** tells each worker what it holds, until when, and what has been tried on each task.

Because workers trigger nothing in the hive (no workflow, no API write), there is no approval click for
newcomers, no flood of pull requests, and no path from a contribution to a secret. Because a task has one holder,
there is no race to win, nothing to gain by copying someone's public work, and no work done twice.

## What a worker pushes

Two kinds of commit, each recognised by lines of its **tip commit message**, each alone on its line.

**An ask**, on the fork's branch `hive/ready` (pushed over the previous one):

```
Hive-Action: ready
Hive-Member: alice
Hive-Tier: 2
```

**A candidate**, on the branch `hive/submit/<task>`:

```
Hive-Task: miniz-0010
Hive-Action: submit
Hive-Deal: 2026-11-12T12:00:00Z
Hive-Member: alice
Hive-Model: claude-fable-5-2
```

- `Hive-Member`: the GitHub login of the fork's owner. **A commit counts only in the fork of the member it
  names**: the same commit pushed to someone else's fork is nothing there, and credits nobody else.
- `Hive-Tier` (optional, 1 to 3, 3 by default): the hardest tier of task this worker takes. A task's tier is
  the project's own.
- `Hive-Task` and `Hive-Deal`: the task, and the instant of the deal the candidate answers, as the feed gives
  it. A submit for a task its member does not hold, or for another deal than the one it holds, **is not a
  candidate**: it is not judged, not answered, not recorded, and not read again.
- `Hive-Model` (optional): the model's identifier. It feeds the public statistics of which models succeed at
  what, for the models the project lists; any other is counted as undeclared. It is what the worker declares: a
  statistic, not a proof.

A key that appears twice, an unknown action or a malformed value means "no marker": the commit is ignored.
`hive.py ready` and `hive.py submit` write these commits; `submit` first runs the same structural checks as the
hive, so that a worker learns of a refusal before spending a judgement.

A candidate is identified by its commit id. The same commit is answered once, whatever the number of branches
that carry it. Of several candidates pushed for one deal, one stands (a draw) and the others are ignored.

## Whose forks are read

Only the forks owned by **a person's GitHub account, older than the project's minimum (90 days by default) and
not banned**. The forks of other accounts (organizations, bots, young or banned accounts) are not read at all:
nothing is fetched from them and nothing is answered, so they cost the hive nothing. A ban names the account's
numeric id: it survives a change of login.

A project can be **open by invitation**: its file lists the numeric ids of the accounts whose forks are read
(`members.only`), and no other fork is. This is how a project starts, among people who are known.

**A fork is read whole or not at all**: one with more new branch tips than the hive reads at once (30) is not read
until it has fewer, and for the hive it then holds nothing.

## How tasks are dealt

Each run, after the forks were read, in this order:

1. **Deals whose time is up.** A deal lasts three hours from the moment it is published, plus one hour of grace.
   After that, if the member's fork was read whole in this run and holds no candidate for the task, the deal
   *expires*. If the fork could not be read, nothing is decided; a day later the task is freed at no cost to the
   member. A deal on a task the project closed meanwhile ends at once, at no cost either.
2. **Candidates.** A submit is a candidate if its member holds the task's live deal and it names that deal. An
   expired deal is over: what its member pushes for it afterwards is not a candidate.
3. **Askers.** Members with an ask at a branch tip, except those who hold a deal without a candidate, are waiting
   after a deal that ended badly, or have had their deals for the day. In this order: those whose last deal was
   accepted, then those who never had one, then the others; within each group, a draw.
4. **The deal.** Each asker gets one task, drawn among the open tasks that nobody holds and that it takes by its
   tier. The draws use a key drawn *after* the forks were
   read: nobody can push something that steers them. An ask is used once.

**Tasks that may change the same file are never held by two members at once.** What a member pushes for its task
is public; someone holding another task on the same file could put that work into its own candidate. So such a task
is dealt only when the others are free. A project whose tasks name separate files loses nothing; one whose tasks share a file does them one at a time.

A member who pushes a candidate *and* an ask is dealt its next task **in the same run, when that candidate is
accepted**: a worker that runs every hour and succeeds gets a task per run. If the candidate is refused, the ask
stays, and is served once the wait is over.

What ends a deal, and what it costs its member:

| The deal ends when | Cost to the member |
| --- | --- |
| its candidate is accepted | none; it clears any wait |
| the judge examined its candidate and refused it (`judge_refused`, `goal_not_met`, `requirement_not_met`) | a wait of two hours, each time, never doubled: a refusal there is ordinary, on tasks that ask for a measured gain |
| its candidate is refused before the judge could examine it: on a structural rule, because it does not merge or changes nothing, after three failures that are its own (`judge_failed`) or three pushes the project's repository declined (`push_refused`) | a wait that doubles |
| its time is up and the fork holds no candidate | the same wait that doubles |
| the hive could not answer it in six runs for no fault of the candidate's (`not_answered`), could not read the fork for a day, or the project closed the task | none: not the member's doing |

**A deal that does not end in an accepted candidate costs a wait**, so that no way of ending a deal is free. When
the judge examined the candidate, the wait is two hours. When the task was held for nothing (no candidate, or one
refused before the judge), it is two hours doubled at each such deal in a row, seven days at most; an acceptance
clears both. A project also limits the deals an account is given in a day (5 by default), **not
counting those whose candidate was accepted**: the limit bounds what an account can take and waste, never what it
can contribute.

So an account holds at most one task at a time, chosen by the hive, and one that takes tasks and leaves them is
dealt fewer and fewer.

## What the hive checks before judging

All of it is read from git objects, on **the difference between the project's tip and the candidate merged on
it**: exactly what would land.

| Reason code | Refused when |
| --- | --- |
| `unrelated`, `too_many_commits`, `conflict`, `empty` | the branch does not come from the project, is too long, does not merge on the tip, or changes nothing |
| `path_outside_task` | a changed path is not one of the task's files (a hard rule, not a warning) |
| `protected_path` | a changed path is protected, **at any depth of the tree**: CI and editor automation (`.github/`, `.vscode/`, `.devcontainer/`…), what steers git (`.gitattributes`, `.gitmodules`), **agent instruction files and folders** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `.cursor/`…), the hive's files (`hive/` at the root), and what the project adds (its tests, its judge) |
| `special_file`, `mode_change` | a symbolic link or submodule, an empty folder or a folder that is not, byte for byte, the one git writes for its entries (written by hand: an entry twice, entries out of order), a changed file mode |
| `bad_path` | a path that is not plain printable ASCII, or a **new** name that is not an identifier: letters, digits, `. _ + -`, 64 characters at most per part, not starting with a dot or a dash, not ending with a dot |
| `binary` | a file with a NUL byte anywhere (the hive reads the bytes itself), or one git calls binary |
| `too_many_files`, `too_large`, `file_too_big`, `line_too_long` | the project's size limits, among them the length of an added line. The hive lists what a candidate changes itself, folder by folder, and stops past the limit; no file is read before the entries are counted: what a candidate costs to refuse does not grow with what it sends, however many paths a few objects describe |
| `judge_refused`, `goal_not_met`, `requirement_not_met` | the judge refused; the candidate is correct but misses the task's goal; or it misses a figure the project requires of every contribution |
| `judge_failed` | three times the judge failed on this deal's candidates (it ran out of time, for instance), or the hive could not derive them, while both worked on the project itself |
| `push_refused` | the project's repository declined the commit (a rule on what may be pushed there), three times |
| `not_answered` | the hive spent six runs on this deal's candidates without an answer, for no fault it can pin on them (see "What holds over time") |
| `task_closed` | the project closed the task between the plan and the write step |

Agent instruction files are protected because an integrated instruction would be read by every later worker: a
stored prompt injection. Coding agents read such files in sub-folders too, so the rule holds at any depth. Changes
to protected paths are ordinary pull requests, reviewed by the project's maintainers.

This narrows one channel; it does not close it. Whatever a contribution adds (a comment, a string, a file's name)
is read by the workers that come after. That is why a worker treats everything in a project as data, and why it can
reach nothing but a branch of its owner's fork.

No `.gitattributes`, the project's own included, changes how the hive merges, counts lines or finds binary files:
the hive runs those git commands with an empty attribute source.

## Four jobs, each with one risk

| Job | Holds | Runs contributors' code | Talks to forks | What it does |
| --- | --- | --- | --- | --- |
| `plan` | nothing | no | **yes, once** | reads the forks; decides the deals whose time is up, the candidates and the new deals; writes **the plan** and a bundle of the candidates' git objects; publishes the plan's SHA-256 |
| `record` | the right to write the hive's state | no | no | checks that the plan is the one `plan` published; writes the plan's deals and the feed, **within minutes of the run's start** |
| `judge` | nothing | **yes**, in the judge's container | no | judges the plan's candidates; writes **a table from the id of each judged commit to the judge's answer** |
| `apply` | the right to write the project and the state | no | no | checks the plan; derives every commit by itself; looks each one up in the judge's table; pushes; records |

- **The forks are read once.** What the plan read is what the run is about: a branch taken away or pushed after
  that changes nothing in this run, for anybody.
- **The plan carries a fingerprint of the ledger it read**, and the jobs that write refuse a plan made on another
  state of the ledger: two runs that overlap never deal one task twice.
- **The judging job cannot change the plan**, and the write job takes two things from it: the judge's answer for a
  commit id the write job derived itself (an answer under any other id is nothing), and which commits it started
  on. So a judging job that was taken over can lie about what the judge said of a candidate, or stay silent about
  it, and so decide which candidates are accepted among those that keep every structural rule. That is its limit:
  it cannot name a candidate, a member, a task or a path, decide who is dealt what, credit an account for work
  that is not in its fork, change history, or write anything but the project's listed figures, as numbers, into
  the ledger. The judge's container is what stands between a contribution and that job.
- The judging and the write job go through the same candidates, with the same ledger, tasks and instant (the
  plan's): they derive the same commits. A plan from the future, or more than a day old, is not applied; nor is
  anything if the project's tip moved since the plan.

## How a candidate is judged and integrated

- The hive first lists, itself and up to the project's limit, what the candidate changed since it left the
  project's history; only then does it compute the merge, without a work tree (`git merge-tree`) and without
  looking for renames (a candidate that moves a file the project changed meanwhile is a `conflict`). It writes the
  two trees to disk **byte for byte, without git's checkout** (no hook, filter, attribute or end-of-line conversion applies), and hands them
  to the judge. A candidate can add or change plain files only; the project's own links and submodules are
  written as they are.
- The judge is the registry's common judge (docs/common-judge.md): candidate code builds and runs only in a
  container without network, and the verdict is derived on the host. Code 0 is correct, 1 a refusal, 2 a failure
  to judge.
- **A failure to judge is the candidate's doing only if the machine works.** When the judge fails on a candidate,
  the hive asks it about the project's own tip against itself. If that fails too, the machine is down: the run
  stops judging and no candidate pays for the breakdown. If it passes, the failure is counted against the deal,
  whose candidate is judged again at the next run, three times at most.
- A task may add a goal on a figure of the judge's report (for instance a minimum gain), and a project may require
  a figure of every contribution. A goal must name a figure the project lists: a task whose goal could never be met
  is refused when the project is loaded.
- Candidates are judged one after the other on a tip that moves with each acceptance, so **what is integrated is
  exactly what was judged**. They are different tasks' candidates: there is one per task at most.
- **The order: oldest deal first**, so that a candidate the run had no time for moves up. After them come those a
  run already failed on, and last those the project's repository already declined.
- The integrated commit is a squash: its tree is the merged tree, its parent the tip, its author the fork's owner
  (`<id>+<login>@users.noreply.github.com`, so GitHub credits the member), its committer the hive. It is
  deterministic: the same tip, candidate, task and member always give the same commit id. The candidate's own
  commit messages and author fields never enter the project's history.

## What holds over time

The hive runs every hour, for ever, among accounts that may take tasks and leave them, push what fails, what never
ends or what the project's repository declines, and on machines that sometimes break. Five rules are written, and
tested over schedules drawn at random (`tools/hive/test_schedule.py`):

1. **An honest worker that asks is dealt a task, and its correct candidate, pushed in time, is integrated in its
   member's name**, whatever others push, take away or break.
2. **Only the member the hive dealt a task to has credit for it.**
3. **Every run of the judge on a candidate leaves a line in the ledger**, and nobody is refused or made to wait
   for the hive's own faults.
4. **The project's branch only moves forward**, each task is integrated once, a task is never dealt while its
   previous deal is live, and an account never holds two live deals.
5. **Nobody stalls the work for long**: neither one or two accounts, nor one fault on the hive's side.

What makes them hold:

- **One holder per task.** There is no order to decide among members, no instant to trust, and nothing a member
  can push that changes what another member's candidate is worth.
- **A task is held for a bounded time.** Three hours and one of grace, by one account, which then waits: two
  hours if the judge examined and refused its candidate, twice as long each time if it held the task for nothing.
  A candidate that waits to be judged keeps its task: that is the hive's delay, not the member's.
- **Not being answered never keeps a place.** Each run the hive spends on a candidate without an answer is
  recorded as a *mark*: the judge failed on it (`judge`), the project's repository declined it (`push`), the hive
  could not derive it (`hive`), or the judging stopped while it was on it (`none`: the judging step says which
  commit it starts on before it starts). A candidate the judging never reached is not marked: nobody pays for the
  time the others used up. A marked candidate goes after the unmarked ones; those the project declined go last,
  and nothing more is judged in the run once one of them is accepted.
- **Marks end in an answer**, and are counted for the deal, not for the commit. Three marks that are the
  candidate's own doing, and it is refused, with its cost: the judge failed on it while its machine works, the
  hive could not derive it while it can still do all of that for the project's own tip (a failure that is only
  slowness is never counted), or the project's repository declined it right after another push of the same run
  landed. Six runs without an answer for any other cause (the judging stopped
  while on it; the project declines every push), and the deal is closed at no cost to its member. Taking a
  candidate away before its third failure and putting another in its place starts nothing afresh. And a candidate
  that git itself cannot read as it is written is refused at once.
- **The judging has a time allowed** (four hours by default): no judgement is started that could end after it, and
  the answers are saved as they come, so that a judging job that is stopped leaves what it had.
- **The hive's own faults cost members nothing.** A fork GitHub would not let the hive read decides nothing. The
  judge's machine down, or the hive unable to derive even the project's own tip, marks nobody. What the judge ran
  on and the hive could not use is judged again.
- **The state survives a run that stops**: its files are written whole or not at all, one cut short is read as
  empty, a ledger line cut short is removed before anything is added, and a line of one run is recorded once
  however often a job is run again.

What this costs, plainly: a worker waits for the hive's next run before its first task; nobody chooses their task
(only the hardest tier they take); an account that asks and never comes back holds one task for four hours, and
with it the tasks that share a file with that one.

## How the hive writes

- **It promises, then pushes.** Before each push the write job records an *intent* in the ledger and saves the
  state. If a run pushed and then could not record, or could not tell whether its push landed, the next run finds
  the promise, looks for the promised commit in the project's history, and completes the ledger. Nothing but the
  hive's own promise is believed: no field of a commit on the project's branch is. That a promised push *landed*
  is recorded as soon as a run sees the commit in the project's history; that it was *not seen there* is recorded
  only by a write job, against the project's tip as it is then. And a push given up on is still looked for during a
  week: one that lands after all is recorded, and its task is done once.
- **The push can only add to the judged tip.** The hive checks that what it pushes descends from the tip that was
  judged, and pushes on the condition that the branch is still at that tip. A branch that a maintainer moved
  meanwhile, to take a commit back for instance, is left as they put it.
- **Accepted commits are pushed one by one**, and what happened is recorded up to the first push that did not
  land; what the judge ran on after it is recorded as `unused` and judged again, at no cost to its member. A
  commit that the project's repository itself declines is a failure of its candidate's, and the run ends in error
  so that maintainers see it. It counts towards a refusal only when another push of the same run had just landed:
  otherwise the hive's own right to push is as likely the cause (a rule added, a token that lost its rights), and
  the candidate only loses its place.
- **A deal's time starts when it is published**, not when it was planned: the `record` job writes it, with the
  feed, before anything is judged. In the same way, a verdict is dated when the write job records it: a wait
  counts from the moment its member can see the answer, however long the judging took.
- A job run twice records nothing twice.

Strings that come from a fork (ref names, commit messages, paths) never reach a shell, a workflow expression or
the ledger.

## The ledger and the feed

In the hive's state repository (`Bee-ruche/hive-state`), one folder per project:

- `ledger.jsonl`: append-only, one JSON object per line: `deal`, `expired`, `verdict`, `error` (a mark, with its
  kind), `intent` and `void` (a promise, and a promise whose push never landed), `unused`; each carries the key of
  its run. **It holds no text a fork wrote**: logins, the numeric ids of the account and of its fork, task ids of
  the project, commit ids, instants, reason codes, a model identifier the project lists, whole numbers under the
  hive's own keys, and the judge's figures the project lists.
- `feed.json`: the project's tasks with their status (`open`, `dealt`, `done`, `closed`), their tier, the number
  of judged refusals and the task's context; and, **under a hash of each login** that a worker computes for its
  own, the task a member holds, since when, until when and whether its candidate was seen (`deals`), and until
  when a member is dealt nothing (`wait`). It holds nothing a contributor wrote. The hash keeps sentences a login
  could spell out of the feed; it hides nobody, since the owners of forks are public.
- `stats.json`: candidates judged and accepted, by account and by declared model.
- `ignored.json`: fork by fork, the branch tips the hive does not read again (no marker, a marker for another
  member, an ask that was used, a submit that is not a candidate). Only what is still at a tip of that fork is
  kept: what one fork pushes never costs another its entries.
- `accounts.json`: when each account that owns a fork was created, asked of GitHub once.

A task the judge keeps refusing asks for a stronger worker: the feed gives a `hint` that rises by one for every
three different members refused, among those the judge has accepted something from. It is a hint for people;
tasks are dealt by their own tier.

Each fork is read with one listing and one fetch, both limited in time. When the time allowed to read all the
forks runs out, what is left waits for the next run; the forks are read in an order drawn anew each hour from the
hour and the fork's own number, which adding forks to the list does not shift.

## A project's files

- `hive/projects/<project>.json` in the registry: the repository, its branch, the protected paths, the limits,
  the member rules (`min_account_age_days`, `deals_per_day`, `banned`, `only`), how long a deal lasts
  (`deal_hours`, `grace_hours`) and the first wait (`backoff_hours`), the models it keeps statistics for, the
  judge's options, the figures of the judge it keeps (`judge.metrics`) and requires (`judge.require`), and the
  stop button (`"paused": true`).
- `hive/tasks/<project>.jsonl` in the registry: one task per line: `id`, `title`, `files` (exact paths, or a
  folder ending with `/`), and optionally `size`, `tier`, `goal`, `options`, `context`, `closed`. Tasks are
  written by the project's maintainers or generated by its splitter; they are trusted data.

## What this version does not do yet

- Run in service: the workflow (four jobs; the plan's SHA-256 as a job output; the right to write the project in
  `apply` alone, the right to write the state in `record` and `apply`), the state repository and the first project's
  files are phase 1.
- Deal more often than it judges (a light run of `plan` and `record` between two full runs), so that a worker
  waits minutes, not up to an hour, for its first task.
- Judge in parallel (several candidates at once, then one confirming judgement), needed above a few thousand
  contributions a week.
- Read only the forks that changed since the last run.
- An "invited" mode for outside projects that want accepted work offered on a branch they pull from.
