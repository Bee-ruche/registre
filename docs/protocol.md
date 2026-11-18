# The hive protocol, version 1

*How work reaches the hive. Implemented by `tools/hive/hive.py`, tested by `tools/hive/test_hive.py` and
`tools/hive/test_schedule.py`.*

> **Status: in service by invitation for two test projects** (miniz since 16 November 2026, cjson since
> 17 November, with one worker, the founder's own: [hive-workflow.md](hive-workflow.md)). **Nobody else is invited
> before a whole round of review by another model, on the code as it stands, finds nothing high or critical**
> ([plan.md](plan.md), 7.2). In an
> earlier draft, members competed for tasks and the hive decided who came first; review after review, by a model
> other than the one that wrote the collector, that decision was where the guarantees gave way. This version removes
> the competition: **the hive deals each task to one member at a time.**

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

**An ask**, on the fork's branch `hive/ready` (pushed over the previous one): a commit that holds no file and has
no parent, so that it carries its message and nothing else.

```
Hive-Action: ready
Hive-Member: alice
Hive-Tier: 2
Hive-Prefer: miniz_tdef.c
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
- `Hive-Prefer` (optional, on an ask): the part of the project the member prefers: one of the files the project's
  tasks name, exactly as the registry writes it (a folder with its final `/`). `hive.py ready --prefer <file>`
  writes it, from the volunteer's prompt and from nowhere else, and refuses any other value before it makes
  anything. The hive compares what the line says with the registry's own strings and takes nothing else from it: a
  value that is none of them is no preference, the ask is still an ask, and nothing of the value is kept anywhere.
  On a candidate the line means nothing. See "How tasks are dealt".
- `Hive-Task` and `Hive-Deal`: the task, and the instant of the deal the candidate answers, as the feed gives
  it. A submit for a task its member does not hold, or for another deal than the one it holds, **is not a
  candidate**: it is not judged, not answered, not recorded, and not read again.
- `Hive-Model` (optional): the model's identifier. It feeds the public statistics of which models succeed at
  what, for the models the project lists; any other is counted as undeclared. It is what the worker declares: a
  statistic, not a proof.

A key that appears twice, an unknown action or a malformed value means "no marker": the commit is ignored.
`hive.py ready` and `hive.py submit` write these commits and push them to the fork. `hive.py start`, before the
work, asks the project's own repository for its tip, puts the clone on the task's branch at that commit, and says
the task started only once it has shown that the work tree holds that commit's files and nothing else: it lists
them from the commit's folders, read as bytes it hashes itself, and reads each entry of the work tree as a plain
file. The commands push to one address,
`https://github.com/<login>/<the project's repository name>`, worked out from the member's login (every command is
given it, `hive.py setup` included) and the registry;
the address the clone gives its origin is only compared with it. `submit` commits the work (the task's files, and
nothing else of the work tree) and its marker, two commits made on the project's commit that the clone rests on:
whatever else the clone's branch held stays behind. Before it pushes, it asks the project's own repository for its
tip and shows, from commits and folders it reads as bytes and hashes itself, that the candidate starts from the
project's history and changes only the task's files; it then runs the same structural checks as the hive, so that
a worker learns of a refusal before spending a judgement. A refusal it prints names a path only if the project
holds it.

A candidate is identified by its commit id. The same commit is answered once as a candidate, whatever the number
of branches that carry it, and is not read again. A commit that was refused is judged a second time in one case
only: a guardian of the project admits it ("Guardians"). Of several candidates pushed for one deal, one stands (a
draw) and the others are ignored.

## Whose forks are read

Only the forks owned by **a person's GitHub account, older than the project's minimum (90 days by default) and
not banned**. The forks of other accounts (organizations, bots, young or banned accounts) are not read at all:
nothing is fetched from them and nothing is answered, so they cost the hive nothing. A ban names the account's
numeric id: it survives a change of login.

A project can be **open by invitation**: its file lists the numeric ids of the accounts whose forks are read
(`members.only`), and no other fork is. This is how a project starts, among people who are known.

**A fork is read whole or not at all**: one with more new branch tips than the hive reads at once (30), or whose
new branches hold more bytes than one fetch may write (four times what the project takes from one candidate: 128 MiB
unless the project says otherwise), is not read until it holds less, and for the hive it then holds nothing. A fetch
is bounded in time as well; one that does not end well leaves nothing on the hive's machine.

**What a fork's owner can bring about is never « could not be read »**. A fork counts as read once the hive has
listed its branches and its fetch ended well (a branch that moved since the listing is read at the next run), or was
stopped by the bound above, or failed while the fork's branches changed under it. It counts as not read, at no cost
to its member, only when the hive could not list it, or when its fetch failed on branches that stood still: then
GitHub or the network may be the cause.

**A guardian's fork is read for its rulings** ("Guardians"), in the same way and within the same bounds, whatever
this section says of its account as a member's: the project's file names a guardian by the account's number, as it
names a member it invites, and a project open by invitation, an age the account does not have or a ban on it as a
member change nothing to that. What such a fork holds as a member's (an ask, a candidate) is then nothing, as
before, and is not remembered either.

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
   tier. While two at least of those tasks are ones the member never held in vain (a candidate of its own
   refused, a deal it left without one), the draw is among these alone: a task that failed in a member's hands
   goes first to another member, or waits. With fewer than two, the draw is among all of them: the rule narrows
   a draw, it never names a task. An ending that was the hive's or the project's doing is not held against the
   task, and what a member held in vain stays so. The draws use a key drawn *after* the forks were
   read: nobody can push something that steers them. An ask is used once.

Between the candidates and the askers come the rulings of the project's guardians, where the project names any
("Guardians"): a ruling that stands is served when its task is free and every open task that shares a file with it
is; the commit it admits is then that task's one candidate in the run, and those tasks are dealt to nobody in it.

**A member may say which part of the project it prefers, and the hive follows it only when its own rules lose
nothing by it.** The project is already chosen by the fork the worker runs in; a part is one of the files the
project's tasks name. At the member's turn, among the tasks it could be dealt anyway (open, held by nobody, the
tasks that share a file with them free too, of a tier it takes, and those it never held in vain alone while two
of them are left: point 4 above), the preference is kept if and only if, decided in
this order:

1. the project offers preferences (`members.preferences` in its file, on by default);
2. the member's last deal that came to an end, in whatever way, ended with an accepted candidate (an ending that
   cost the member nothing, such as a task the project closed, is no accepted candidate either). For a member dealt
   in the run that answers its candidate (below), that is where it stood before that answer;
3. at least two of those tasks list the part: a preference chooses a part, never a task.

The task is then the same draw among those of these tasks that list the part. In every other case the plain draw
runs, unchanged, and the deal's line says why the preference was not kept: `not_offered`, `needs_an_accepted_deal`
(one word for a member that never had a deal come to an end and for one whose last deal ended otherwise: the line
names its member), `no_free_task` or `one_free_task` (one task alone listed the part: following the preference
would have chosen it). A member with several asks has a preference only if all of them name
the same part. Two things hold whatever an ask says: **a kept preference only ever gives a task the plain draw
could have given, and the order in which askers are served reads no preference.** Nor do the waits, the day's
deals, the tiers, or the rule on tasks that share a file.

**Tasks that may change the same file are never held by two members at once.** What a member pushes for its task
is public; someone holding another task on the same file could put that work into its own candidate. So such a task
is dealt only when the others are free. A project whose tasks name separate files loses nothing; one whose tasks share a file does them one at a time.

A member who pushes a candidate *and* an ask is dealt its next task **in the same run, when that candidate is
accepted**: a worker that runs every hour and succeeds gets a task per run. If the candidate is refused, whatever
the reason and even at no cost to its member, the ask stays, and is served at a later run, once any wait is over.

What ends a deal, and what it costs its member:

| The deal ends when | Cost to the member |
| --- | --- |
| its candidate is accepted | none; it clears any wait |
| the judge examined its candidate and refused it (`judge_refused`, `goal_not_met`, `requirement_not_met`) | a wait of two hours, each time, never doubled: a refusal there is ordinary, on tasks that ask for a measured gain |
| the judge examined its candidate, found it correct, nothing degraded and the figure the task asks for reached, and only the proof of it is missing or did not come out beyond the measure's noise (`not_proven`) | **no wait**: the hive does not charge a member for what its own stopwatch could not tell. It cost the hive a judgement all the same, and it is a deal that did not end in an acceptance: it counts in the day's limit and in the member's class |
| its candidate is refused before the judge could examine it: on a structural rule, because it does not merge or changes nothing, after three failures that are its own (`judge_failed`) or three pushes the project's repository declined (`push_refused`) | a wait that doubles |
| its time is up and the fork holds no candidate | the same wait that doubles |
| the hive could not answer it in six runs for no fault of the candidate's (`not_answered`), could not read the fork for a day, or the project closed the task | none: not the member's doing |

These are a project's defaults (two hours as the first wait); a project whose file names one account alone may
set the wait to nothing while it is tried, and then only the day's count is left of what follows.

**A deal that does not end in an accepted candidate costs something**, so that no way of ending a deal is free: a
wait, or, for a candidate that lacks a proof alone, its place in the day's limit. When the judge examined the
candidate, the wait is two hours; there is none when the candidate is correct, reaches the task's own figure and
lacks only a proof (`not_proven`): the hive cannot tell a gain the noise hid from no gain, so it neither accepts
nor charges. When the task was held for nothing (no candidate, or one
refused before the judge), it is two hours doubled at each such deal since the member's last accepted candidate,
seven days at most; an acceptance clears both, and nothing else does. A project also limits the deals an account
is given in a day (5 by default), **not counting those whose candidate was accepted**: the limit bounds what an
account can take and waste, never what it can contribute. (A deal whose candidate still waits for its answer
counts until it is accepted.)

So an account holds at most one task at a time, chosen by the hive, and one that takes tasks and leaves them is
dealt fewer and fewer.

## What the hive checks before judging

All of it is read from git objects, on **the difference between the project's tip and the candidate merged on
it**: exactly what would land.

| Reason code | Refused when |
| --- | --- |
| `unrelated`, `too_many_commits`, `history_too_big`, `conflict`, `empty` | the branch does not come from the project, is too long, holds commits that together weigh more than the project allows (32 MiB, unless the project says otherwise, as git packs them on the project's tip, which is how the hive carries them: whatever a commit added on the way counts, even removed since), does not merge on the tip, or changes nothing |
| `path_outside_task` | a changed path is not one of the task's files (a hard rule, not a warning) |
| `protected_path` | a changed path is protected, **at any depth of the tree**: CI and editor automation (`.github/`, `.vscode/`, `.devcontainer/`…), what steers git (`.gitattributes`, `.gitmodules`), **agent instruction files and folders** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.claude/`, `.cursor/`…), the hive's files (`hive/` at the root), and what the project adds (its tests, its judge) |
| `special_file`, `mode_change` | a symbolic link or submodule, an empty folder or a folder that is not, byte for byte, the one git writes for its entries (written by hand: an entry twice, entries out of order), a changed file mode |
| `bad_path` | a path that is not plain printable ASCII, or a **new** name that is not an identifier: letters, digits, `. _ + -`, 64 characters at most per part, not starting with a dot or a dash, not ending with a dot |
| `binary` | a file with a NUL byte anywhere (the hive reads the bytes itself), or one git calls binary |
| `too_many_files`, `too_large`, `file_too_big`, `line_too_long` | the project's size limits, among them the length of an added line. The hive lists what a candidate changes itself, folder by folder, and stops past the limit; no file is read before the entries are counted: what a candidate costs to refuse does not grow with what it sends, however many paths a few objects describe. A file larger than `file_bytes` is refused before the candidate is merged on the project's tip (git's merge reads whole each file that both sides changed), and a candidate one of whose own commits holds such a file, even removed since, is not carried to the judging at all: the plan asks git the size of each object those commits add. This holds whatever the project's own files weigh: a candidate whose commits bring a file larger than `file_bytes` is refused even where that file is the project's own, so a task on such a file waits until the project raises its limit |
| `stored_otherwise` | a changed file is not stored as the project's own rules store it (its `.gitattributes`: line ends, an encoding): once integrated, git would find it changed in every clone, where nobody changed it. The hive asks git, as a checkout does |
| `judge_refused`, `goal_not_met`, `requirement_not_met` | the judge refused; the candidate is correct but misses the task's goal; or it misses a figure the project requires of every contribution |
| `not_proven` | the candidate is correct, degrades nothing and reaches the figure the task's goal asks for, but a proof the project takes of it (`judge.confirm`) is missing or short: everything the goal asks is there except its proofs. Nothing is accepted without its proof, and nothing is held against the member: no wait |
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
| `plan` | nothing | no | **yes, once** | reads the forks; decides the deals whose time is up, the candidates and the new deals; writes **the plan** and a bundle of the candidates' git objects (1 GiB and two million objects at most: the candidates beyond either wait for the next run, oldest deal first; one whose own commits are too many or too heavy is refused without being carried); publishes the plan's SHA-256 |
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
- **Of a guardian's ruling, the jobs that write take from the plan what the plan job read in the guardian's fork**
  (that the fork holds the ruling at its task's branch and what the ruling says, the guardian's login, that the
  ruling carries its commit) **and hold everything else again by themselves**, against the project's file and the
  ledger as the plan read it, before they write or push anything ("Guardians", "What each job holds of a ruling"):
  a plan that says of a ruling what these do not bear out is not applied at all.

## How a candidate is judged and integrated

- The hive first lists, itself and up to the project's limit, what the candidate changed since it left the
  project's history; only then does it compute the merge, without a work tree (`git merge-tree`) and without
  looking for renames (a candidate that moves a file the project changed meanwhile is a `conflict`). It writes the
  two trees to disk **byte for byte, without git's checkout** (no hook, filter, attribute or end-of-line conversion applies), and hands them
  to the judge. A candidate can add or change plain files only; the project's own links and submodules are
  written as they are.
- **A project names its judge's kind** (`judge.kind` in its file). What a verdict is, where judged code runs and
  what may accept a candidate are the hive's, the same for every project; how a candidate is found right or wrong
  is a kind of judge's; what is asked of the judge's figures is the project's. A kind is code of the registry: a
  project's file can name one and never bring one, and a file that names a kind the tool does not hold is refused
  when it is loaded, at every step. Two kinds exist. `common`, which a project that names none has, is the
  registry's common judge (docs/common-judge.md): the candidate gives the same outputs as the project's tip, and
  is measured against it. `reference` (docs/reference-judge.md) is for a port or a rewrite: the unit a candidate
  writes answers exactly as the project's reference does, on cases drawn when it is judged. In both, candidate
  code builds and runs only in a container without network, and the verdict is derived on the host. Whatever the
  kind, code 0 is correct, 1 a refusal, 2 a failure to judge, and the project's tip judged against itself is
  answered 0.
- **A project's file is its own, and bears its name.** `hive/projects/<project>.json` names that project and no
  other: a file whose `project` is not its own name is refused, so two files never write one project's state. A
  step of the hive reads the file of the project it runs for and no other. A worker's command checks in full the
  project it is given; of every other project it reads the name and the repository, which it compares with the
  fork's, and nothing else: what one project's file asks of the tool does not stop another project's workers.
- **A failure to judge is the candidate's doing only if the machine works.** When the judge fails on a candidate,
  the hive asks it about the project's own tip against itself. If that fails too, the machine is down: the run
  stops judging and no candidate pays for the breakdown. If it passes, the failure is counted against the deal,
  whose candidate is judged again at the next run, three times at most. A run whose judge failed on the project's
  own tip ends as a failure once everything it could decide is written, so that a person sees it: the machine may be
  down, or the tip itself may no longer pass the project's check.
- **A measure accepts no candidate alone, whatever the project and whatever its judge.** A judge gives measures (a
  gain, a count) and proofs. A proof is a figure named `sure_<measure>`: 1 when the judge saw, by a comparison it
  made from outside the two programs and beyond its noise, that the candidate is better, else 0. A task may add a
  goal on a figure of the judge's report (for instance a minimum gain), and a project may require a figure of every
  contribution. A goal names figures the project lists, and it always holds one of the proofs the project takes
  (`judge.confirm`), with a minimum of 1: a task whose goal could never be met, or would rest on a measure alone,
  is refused when the project is loaded, at every step of the hive. The registry's judge gives a `sure_` figure for
  each measure of its report's « metrics »; a count made by a tool that runs the program inside itself is not one
  of them, and has no `sure_` figure under any name. Among those figures a project takes as proofs the ones the
  judged program cannot bear upon (the processor time the kernel reads, what the judge itself reads of the
  outputs), and its maintainers answer for that choice. What a project requires of every candidate
  (`judge.require`) can only refuse. **What the hive vouches for in an accepted contribution is its proof**: that
  the judge saw it better beyond its noise, with the same outputs. A bound on a measure that has no proof (in miniz,
  the count of instructions) is a bar that can only refuse: the hive does not vouch for that measure's size, and the
  ledger keeps it as the judge gave it. The page leads a contribution's card with a figure that has its `sure_`, and
  with no other: a measure without one is a row of its table. Told which proofs the project takes (its file, given
  to the page tool), the page leads with one of those measures only: a flag the project keeps and does not take as
  a proof leads nothing.
- **A refusal on the suspects says which of the judge's checks it was.** The registry's judge counts what its
  reading of the compiled code and of the source flags in a candidate and not in the base (`suspects`), and a
  project may bound that count for every contribution. Beside the count the hive takes from the judge's report one
  figure for each kind the judge counted at least one of, `suspects_<kind>`, under the judge's own word for the kind (`octets`: bytes that spell an instruction a computing
  library has no use for; `instruction`; `source`; `symbole_defini`, `appel_externe`, `appel_interdit`,
  `symbole_interdit`, `symbole`; `section`; `architecture`; `analyse_incomplete`). A project that keeps those
  figures has them on the refusal's line. A kind the judge counted none of has no figure, so these figures say and
  bound nothing: a project bounds the count itself. What was flagged (a name, bytes, a line) is text of the judged
  code: it stays in the judge's own report and reaches no line of the ledger.
- Candidates are judged one after the other on a tip that moves with each acceptance, so **what is integrated is
  exactly what was judged**. They are different tasks' candidates: there is one per task at most.
- **The order: oldest deal first**, so that a candidate the run had no time for moves up. After them come those a
  run already failed on, and last those the project's repository already declined.
- The integrated commit is a squash: its tree is the merged tree, its parent the tip, its author the fork's owner
  (`<id>+<login>@users.noreply.github.com`: the member is credited), its committer the hive, its date the instant of
  the run that judged it. Its message says what it is, in the hive's own fixed words: that an AI coding agent wrote
  it unattended, that the hive's judge accepted it and that no person read it before it was integrated; then the
  task, the member, the candidate and the model the worker declared (`Hive-Model`, or `undeclared`). It is
  deterministic: the same tip, candidate, task, member, model and instant always give the same commit id. The
  candidate's own commit messages and author fields never enter the project's history. A commit a guardian
  admitted says so: in place of the judge's acceptance and « no person read it », that the judge refused it for a
  figure the project lets its guardians waive, that a guardian of the project admitted it and that it was judged
  again in full; and in two lines more, `Hive-Guardian` (the guardian's login) and `Hive-Ruling` (the ruling's
  commit id).

## Guardians

Members are strangers, and nothing in this protocol trusts one. A project may also name **guardians**: a few
accounts that its own file trusts, by their GitHub account numbers (`guardians.accounts`). A guardian is honest
and may be wrong. It decides alone and at once, and what guards against its mistakes is that each decision is a
public line of the ledger, with its account on it. A project that names none takes no ruling, and everything
below is absent from its runs.

A guardian has one power: **to admit one commit that the hive refused for a figure alone that the project lets a
guardian waive.** What a project requires of every contribution (`judge.require`) can only refuse, and one such
bar may be a count of what the registry's judge flags in a candidate (`suspects`): a flagged construct is not a
fault in itself, it is what a guardian reviews (docs/common-judge.md). A ruling is the outcome of that review. It
relaxes nothing that is asked of members: the commit is judged again, in full, and the ruling changes one thing in
that judgement.

**What may be waived is the project's to say.** `guardians.waive` lists figures, each with a bound. A figure
there is one the project keeps and requires with a `max`, in one condition that asks nothing else; its bound, that
`max` at least, is the most a ruling may let the figure reach. A file that says anything else of its guardians
does not load.

**A ruling** is a commit at the tip of one branch of the guardian's own fork: `hive/rule/<task>`, the branch
`hive.py admit` writes for the task the ruling names. Its one parent is the commit it admits and its files are that
commit's, so that reading the guardian's fork brings the admitted commit itself, whatever its member's fork holds
since. Its message, each line alone on its line:

```
Hive-Action: admit
Hive-Member: gina
Hive-Task: miniz-0010
Hive-Commit: 3b1f0c9a5d2e4f60718293a4b5c6d7e8f9012345
Hive-Waive: suspects 2
```

- `Hive-Member`: the guardian's login. A ruling counts only in the fork of the account it names, and only if the
  project's file names that account (the number GitHub gives for the fork's owner).
- `Hive-Task` and `Hive-Commit`: the task, and the full id of the commit admitted, as the ledger's refusal names it.
  **A ruling counts at one branch, by its name**: the guardian's fork lists `hive/rule/<that task>` at that very
  commit. A guardian's fork holds other commits than those the guardian's command made (a commit fetched to be read,
  and pushed along with the rest): what one of them says is no decision of the guardian's, whatever it is shaped
  like.
- Anywhere else (a fork whose owner the project's file does not name, the member's own fork included; another
  account's name; any other branch of a guardian's fork) a commit shaped like a ruling is a commit without a
  marker: not read again while it stays there, and no line. That holds for good: a guardian the file names later,
  or one who meant a ruling that sits elsewhere, makes it anew (`hive.py admit` makes a new commit each time).
- `Hive-Waive`, once for each figure waived: the figure, and up to what, as a plain decimal number. The hive
  compares the figure's name with those the project's file lists and keeps the file's own string; a name the file
  does not hold is counted and goes no further.

`hive.py admit --project <project> --login <the guardian's login> --task <task> --commit <id> --waive
<figure>=<bound>`, run in a clone of the guardian's fork that holds the commit, makes the ruling and pushes it to
the fork's branch `hive/rule/<task>`, under the same checks of the clone as a worker's commands; `--withdraw`
deletes that branch. The guardian fetches the commit into that clone **by its id, as the ledger's refusal gives
it**, never as a branch of its member's fork: a branch is whatever its owner pushed there since, and what it holds
is data. The command decides nothing: whether a ruling stands is said by the hive.

**A ruling stands** only if all of this holds:

- the project's file names the account;
- the ruling carries the commit it names (its one parent, the same files);
- the task is one of the project's, open, and not done;
- the ledger holds the hive's answer to that commit as a candidate for that task, and that answer is a refusal
  `requirement_not_met` whose line keeps what the judge measured: every requirement that report fails is on a
  figure the project lets a guardian waive;
- the commit's member is an account the project takes today, by its file: not one it bans (by the account's
  number, or by the login of its deal's line), and, in a project open by invitation, one the file names. A ruling
  brings in no work of an account the project has turned away since;
- the commit is not the guardian's own, except in a project whose file names one account alone as its members: a
  trial with one person in it has nobody else to rule, and the line shows the same account twice;
- each figure the ruling waives is one the file lists, with a bound between what the project requires and the
  file's own bound, and the ruling covers what the commit failed: each failed figure, as far as it was measured;
- the ruling has no answer yet. Of several rulings that stand on one commit, one is taken, by the run's draw; the
  others are answered `duplicate` by the run that judges the commit under that one, and wait with it until then.

**What each job holds of a ruling.** The `plan` job is the only one that reads a fork, a guardian's as a member's.
Three things are its reading, and the jobs that write take them from the plan, as they take from it which commits
a member's fork held: that the fork of that account holds, at the task's ruling branch, a commit of that id that
says this (the task, the commit, each figure waived and its bound); the login GitHub gives for the account; and
that the ruling carries the commit it names. Everything else in the list above is read from the project's file,
its tasks and the ledger, and `record` and `apply` hold it again, by themselves, against the ledger as the plan
read it, before they write or push anything: the account is one the file names; the commit, its task, its member,
that member's login and fork, the deal and the model are the ledger's own for that refusal, field for field; the
refusal is one a guardian may lift; the member is one the project takes; what is waived lies within the file's
bounds and covers what the commit failed; the task was free, and no other candidate or deal of the plan takes it or
a task that shares a file with it; a void line names a task of the registry or none, for the reason those same
readings give; `duplicate` is said only in a plan that admits the same commit under another ruling; and no ruling
is named twice in a plan. A plan that says otherwise is not applied at all. (One case is no fault of the plan's: a
task the registry closed after the plan was made. The write job then answers the ruling void, as it refuses a
member's candidate whose task was closed meanwhile.)

**A ruling that stands is served when its task is free**, and every open task that shares a file with it: until
then it stays where it is, in the guardian's fork, and the hive keeps nothing of it. Then the commit joins the
run's candidates, for that task and in the name of the member who wrote it: the account of the refusal's line,
with the login and the fork that the line of its deal gives. **It is judged again as any candidate is**, merged on
the project's tip as it stands then: the limits, the structural rules, the judge's own answer, every requirement
of the project, the task's goal and its proofs. One thing differs: a requirement on a figure the ruling waives is
met when the figure is within the ruling's bound. What passes is integrated and credited to its member.

**Every ruling is answered once, on a line of the ledger, and a ruling that fails costs the commit's member
nothing.**

- *Accepted*: a `verdict` line like any other (the task is done, the member is credited, the statistics count
  it), with four fields more: `ruling` (the ruling's commit id), `guardian_id` and `guardian` (the account that
  admitted it, by number and by login), and `waived` (each figure waived with the ruling's bound). The line names
  the deal the commit answered when it was refused, and it is written when it is decided: after whatever the
  member's later deals came to. The ledger's endings are read in the order they were written, so **that acceptance
  is the member's latest ending**, whatever ended between the refusal and it: every wait the member had is
  cleared, a later failed deal's included; the member has the class, and what goes with it (a preference
  followed), of one whose last deal was accepted, until its next deal ends; and the deal the line names leaves the
  day's count. It is the most recent thing the hive said of that member's work, and it counts as that.
- *Anything else*: a line of type `ruling`, which is no verdict: the ruling's commit id, the guardian's number and
  login, the task (as the registry names it, or none), the commit, a `result` and a `reason`. It names no member
  and counts in nobody's deals, waits, refusals or statistics.

| `result` | `reason` | The ruling |
| --- | --- | --- |
| `void` | `malformed` | does not carry the commit it names |
| `void` | `task_closed`, `task_done` | names a task that is not the project's or is closed; or one that is done (by the commit of a member it was dealt to meanwhile, for instance) |
| `void` | `unknown_commit` | names a commit the ledger holds no answer to, as a candidate for that task |
| `void` | `not_reviewable` | names a commit that was not refused for figures alone that the project lets a guardian waive |
| `void` | `member_not_taken` | admits the commit of an account the project's file does not take today: one it bans, or one a project open by invitation does not name |
| `void` | `own_candidate` | admits the guardian's own commit, in a project whose file does not name one account alone as its members |
| `void` | `beyond_bound` | waives a figure the file does not list, or outside the file's bounds, or not as far as the figure the commit was refused for |
| `void` | `duplicate` | stands, and lost the draw to another ruling on the same commit: said in the run that judges the commit under that other ruling, never before |
| `refused` | a candidate's reason code (`conflict`, `judge_refused`, `requirement_not_met`…) | stood, and its commit, judged again, was refused: the line says whether the judge examined it (`judged`), and keeps `detail` and, for a figure, the judge's `report`, as a refusal's verdict does |

A run spent on an admitted commit without an answer is a mark of the ruling, not of the deal the commit once
answered; a ruling's marks end as a deal's do (`judge_failed`, `push_refused`, `not_answered`), on the ruling's
line and at no cost either. The write
job answers rulings, once it has seen the project's tip where the plan saw it; the `record` job holds them and
writes none. A ruling whose guardian the file no longer names is not applied, and at the next run it is a commit
like any other.

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
  hours if the judge examined and refused its candidate (nothing if all the candidate lacked was a proof),
  twice as long each time if it held the task for nothing.
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
(only the hardest tier they take, and a part of the project they would rather have, which the hive follows when
its rules lose nothing by it); an account that asks and never comes back holds one task for four hours, and
with it the tasks that share a file with that one.

## How the hive writes

- **It writes a branch of its own, never the one a project publishes.** A project's file names both: `branch`,
  where the hive integrates what its judge accepted, and `published`, the branch people take the project from. The
  hive pushes to the first and to no other; a file that names no published branch, or one branch for both, stops
  every step of the hive and every command of a worker. Each is written as a branch's own name, the one way: what
  git takes as a branch's name, with no `refs/` or `heads/` in front, not `HEAD` nor a name that ends in `_HEAD`,
  and not a commit's full id. The hive's own branch reaches git only inside a full reference (`refs/heads/<name>`
  on a repository, `refs/remotes/…/<name>` in a clone), never as a bare word; the published one reaches no git
  command: the hive only compares it. What is on the hive's branch was accepted by a judge and
  read by nobody: each of its commits says so. The published branch moves when a maintainer, having read what
  accumulated, moves it; a release, an offer to another project, anything that leaves the repository, is a
  maintainer's act. The judge's scan of a candidate's source is a filter, not a review of what a change does.
  What a maintainer commits on the published branch (a fix, a revert) the maintainer also brings to the hive's
  branch: the hive works on its own branch's tip and takes nothing from the other by itself. The file's two names
  are the registry's word: the host's own rule, which keeps the hive's key off the published branch, is what holds
  if that word is wrong (docs/hive-workflow.md, setting 4).
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

In the hive's state repository (`Bee-ruche/hive-state`), one folder per project. A project's run writes its own
folder and no other, so two projects' runs never conflict: a push that finds the repository moved takes what the
other run saved and pushes again, a bounded number of times. In each folder:

- `ledger.jsonl`: append-only, one JSON object per line: `deal`, `expired`, `verdict`, `error` (a mark, with its
  kind), `intent` and `void` (a promise, and a promise whose push never landed), `unused`, and `ruling` (a
  guardian's ruling that did not end in an integration: "Guardians"); each carries the key of
  its run. **It holds no text a fork wrote**: logins, the numeric ids of the account and of its fork, task ids of
  the project, commit ids, instants, reason codes, a model identifier the project lists, whole numbers under the
  hive's own keys, a file of the project as the registry names it, the judge's figures the project lists, and the
  bounds of a ruling under the project's own names for the figures. **A
  login is written beside a deal and beside an accepted candidate, which is a credit; a refusal, a run without an
  answer and an expired deal carry the account's number alone.** That is discretion, not secrecy: the deal names its
  member, and the candidate sits in a public fork. A guardian's login is written beside each of its rulings,
  whatever the answer: a guardian's decisions are public and named.

  A `verdict` line carries the task, the deal it answers, the candidate's commit id, the account's number and its
  fork's, the result, whether the judge examined the candidate (`judged`) and the model the worker declared. An
  accepted one adds its member's login, the integrated commit, what the hive counted of the change (`figures`) and
  the judge's figures the project lists (`report`). A refused one adds its reason code and `detail` (whole numbers
  under the hive's own keys), and no login on the line. **A candidate refused for a figure (`goal_not_met`,
  `requirement_not_met`, `not_proven`: the judge ran, the candidate is correct, a figure or a proof is short) keeps the same `report` as an
  accepted one**, the same numbers bounded the same way: how far it fell short is what its member needs to know,
  and whoever is dealt the task next. `judge_refused` and every refusal before the judge carry none. A refusal's
  line written before this rule has no `report`; it stays valid, and whatever reads the ledger takes both.

  A commit has one verdict as a candidate. One that a guardian admitted and the hive then accepted has a second,
  which names the ruling (`ruling`, `guardian_id`, `guardian`, `waived`: "Guardians") and is recorded once per
  ruling: the two lines stand side by side, the refusal as it was written and the acceptance that followed.

  A `deal` line carries the task, its member's login, the account's number and its fork's, when the deal starts
  and until when. When the member's ask named a part of the project it adds `prefer`: `{"file": <the part, as the
  registry writes it>, "kept": true}`, or `{"file": …, "kept": false, "because": <one of the four reasons of "How
  tasks are dealt">}`. An ask that named no part of the registry's leaves no `prefer` at all: a deal's line written
  before this rule, or for such an ask, stays valid, and whatever reads the ledger takes both. The jobs that write
  copy nothing of a preference from the plan: before they write or push anything, they hold that it has that shape
  and names a file of the project as the registry writes it, and they write the registry's own string.
- `feed.json`: the project's tasks with their status (`open`, `dealt`, `done`, `closed`), their tier, the number
  of judged refusals and the task's context; and, **under a hash of each login** that a worker computes for its
  own, the task a member holds, since when, until when and whether its candidate was seen (`deals`), and until
  when a member is dealt nothing (`wait`). It holds nothing a contributor wrote. The hash keeps sentences a login
  could spell out of the feed; it hides nobody, since the owners of forks are public.
- `stats.json`: candidates judged and accepted by declared model, and, for each account with accepted work, how many were accepted (what was refused is added up for a model, not for a member).
- `ignored.json`: fork by fork, the branch tips the hive does not read again (no marker, a marker for another
  member, an ask that was used, a submit that is not a candidate, a commit shaped like a ruling in a fork whose
  owner the project does not name a guardian, under another account's name, or at another branch than its task's
  ruling branch). A guardian's ruling at its branch is not listed there: it is read at each run until the ledger
  holds its answer. Only what is still at a tip of that fork is
  kept: what one fork pushes never costs another its entries.
- `accounts.json`: when each account that owns a fork was created, asked of GitHub once.

A task the judge keeps refusing asks for a stronger worker: the feed gives a `hint` that rises by one for every
three different members refused, among those the judge has accepted something from. It is a hint for people;
tasks are dealt by their own tier.

**What a worker believes.** The registry it runs `hive.py` from is the hive's own: a task's text and files, the
project's branch and its check come from there, never from the feed. The state is believed for what the hive did
for this member and nothing else: the task it dealt it and until when, its wait, whether its candidate was seen,
whether its ask was used (is the ask's commit id in `ignored.json`: an ask the hive still reads is not asked
again, and one that has waited six hours is reported to the volunteer), and whole numbers (how often a task was
refused). No text of the state is printed by the worker's commands: every line they print is one of a fixed list
(`hive.py`'s own documentation), followed by values the tool checked. The fork's clone is not trusted either, once
project code ran in it: each command first checks that its git settings are the ones a clone has (anything else
stops the command: a filter, a hook, a credential helper, another address to push to, an included file, a reference
that is neither a branch, a tag nor the stash), and starts the task, commits and pushes itself, so that the worker's
assistant runs no git command of its own in the fork's clone. What a command decides on is never a value the clone
holds: the fork's https address is worked out from the login and the registry, a task starts on the commit the
project's own address announces, and a candidate is pushed only once
the tool has shown, from bytes it hashed itself, that it starts from the project's history and changes only the
task's files. Nor does a task start on what git made of the clone: git does not hash an object again when it reads
one, and its index is a file of the clone, so `start` shows by its own reading that each file of the work tree
hashes to the id the project's tip lists, and that nothing else is there. A file the project's own rules convert
(line ends, an encoding) is compared, byte for byte, with what a checkout writes for the hashed file; a file that
is run or obeyed on the host (the sandbox's launcher, the CI's files, an agent's settings and instructions) is
taken only as the tip's very bytes. Otherwise the command stops, and nothing is run from the clone, not even its
sandbox. A worker must run at least every two hours to do the tasks it asks for: a deal lasts three
hours and a worker starts on one only if an hour of it is left.

Each fork is read with one listing and one fetch, both limited in time. When the time allowed to read all the
forks runs out, what is left waits for the next run; the forks are read in an order drawn anew each hour from the
hour and the fork's own number, which adding forks to the list does not shift.

## A project's files

- `hive/projects/<project>.json` in the registry: the repository, the hive's own branch in it (`branch`) and the
  branch the project publishes (`published`, which the hive never writes), the protected paths, the limits,
  the member rules (`min_account_age_days`, `deals_per_day`, `banned`, `only`, and `preferences`: whether the
  part of the project an ask prefers is followed, true unless the file says false), how long a deal lasts
  (`deal_hours`, `grace_hours`) and the first wait (`backoff_hours`: an hour at least, or none at all, `0`, for a
  project whose file names one account alone: a file that names a second one with that setting does not load),
  the models it keeps statistics for, the
  kind of its judge (`judge.kind`), the judge's options, the figures of the judge it keeps (`judge.metrics`) and
  requires (`judge.require`), the
  judge's proofs it takes (`judge.confirm`: figures it keeps, named `sure_<measure>`; every goal on a figure holds
  one of them, with a minimum of 1 or more, and a project that lists none has goals of the kind « correct » only;
  what the project requires of every candidate, `judge.require`, stays as the project wrote it), its guardians if
  it names any (`guardians`: `accounts`, their GitHub account numbers, and `waive`, the figures they may waive,
  each with the most a ruling may let it reach; a file without it takes no ruling: "Guardians"), and the project's pause
  (`"paused": true`). A run reads this file, and the tasks, at the commit of the registry the
  workflow names: a change acts once that line is moved to it.
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
