# The engineering plan: a hive that is safe, powerful and worth joining

*12 November 2026. Written by the builder of the hive, as its engineer, at the founder's request. It replaces the
rebuild plan of the same day (kept in this file's git history). The check of the project that came before it is a
private report held by the founder. Each item says whether it is **built**, **planned**, or **the founder's**.
Facts marked **(unverified)** come from search excerpts or secondary sources and must be checked before anything
depends on them.*

## 1. The critical analysis

### 1.1 Where the hive stands

1. **It has one participant.** All 126 contributions so far are the founder's (through his agents); no review,
   vote, measurement or member registration has ever been recorded. Every mechanism that rests on "other people"
   has never run.
2. **It is built for agents a human launches and watches.** A first contribution means reading about 4,700 words,
   forking, reserving through a pull request, working, declaring, submitting through another pull request, then
   waiting for reviews that never come. 43.5 % of the registry's 600 commits are bookkeeping; the CI ran 6,120
   workflows in 16 days.
3. **Its judge is its real asset.** The common judge (isolated build, outputs checked from outside, measurements
   outside the measured program, verdicts bound to the judged commit) is well built. Everything below is built
   around it.
4. **Its projects do not draw a crowd**, and task supply has dried up: 198 tasks the first week, 6 in the last
   three days, mostly about the hive itself.
5. **Its governance is heavier than its activity**: 16 rules, 14 commandments, 5 role briefs and 108,000 words of
   documents govern a hive of one.

### 1.2 What my own first plan got wrong

I wrote the first plan before building anything. Building, and having the result attacked, changed it:

| First plan | Why it was wrong | Now |
| --- | --- | --- |
| Workers claim tasks by commenting on the registry (a "gesture inbox") | It gives every contributor a way to write into the hive, which a robot must then parse: a new attack surface, and an API write from every worker | **Workers write nothing to the hive.** They push to their own fork; the hive comes and reads |
| Leases: a claimed task is offered to nobody else | I rejected them twice, for a reason that turned out wrong: "a lock needs a referee and a clock everyone trusts". The hive's own hourly run is that referee, and its own clock is enough. What invites squatting is a lock that a member *takes*; one that the hive *gives*, to one account at a time, for a bounded time, with a wait that doubles for those who waste it, does not | **The hive deals each task to one member at a time** (section 3.2) |
| Members compete for a task: first pushed, first served, and the hive decides who came first | Seven adversarial reviews in a row. Integrity held from the third on; from the fourth on, nearly every serious finding sat in the same place: several members' candidates for one task, and the instants, ranks and waits that order them. Each fix moved the fault | **No competition left to referee**: one holder per task, so no order among members, no instant to trust, nothing to gain by copying (docs/protocol.md) |
| Work handed to the hive through a pull request from the fork | Pull requests bring the first-contribution approval click, one merge a minute, and a flood for maintainers | **No pull request.** The hive integrates what its judge passed |
| Redundancy (each result re-done by another worker) and reputation with decay | Designed for volunteers' machines that judge; the hive's judge runs on its own CI and decides alone. Machinery for a problem the hive does not have | **Dropped** until volunteers' machines judge |
| "One invited project as pilot, still to study" | The opening depended on a stranger's yes | **A flagship the hive can start alone** (section 4.3), invitations second |
| Opening to everyone at once | Seven adversarial reviews in a row broke the collector they were given, each time by a longer schedule than the last. Its integrity has held since the third; what holds over time among hostile accounts is not yet proven | **A project starts by invitation**: its file names the accounts whose forks are read (docs/protocol.md). Phase 1 runs that way; opening to everyone waits for a review that finds nothing serious |
| Tests of one run at a time | A third review showed that the third collector kept every property of integrity and none of liveness: a candidate the hive never answered kept its place, run after run, and could stall a task, a new project or the whole hive | **Rules written for what holds over time, and a test over schedules drawn at random** (docs/protocol.md, "What holds over time"), which the reviewer is then asked to break |
| "The collector works: its tests pass" | A first adversarial review, by another model, returned twenty findings on my first collector, among them ways to take credit for someone else's work and to stall the hive; my own tests had been written so that one check hid the absence of the others. A second review returned twelve on my second one | **A fixed procedure for the hive's own tooling** (section 6.2): tests that fail when a check is removed, then a review by another model, before any claim |
| Two jobs, one that judges and one that writes, each reading the forks | Two readings of the forks can be made to disagree, by anyone who pushes or deletes a branch between them, and the write job then drops what was judged | **Separate jobs, each with one risk**: the forks are read once, by a job that holds nothing and runs nobody's code (section 2) |

### 1.3 The existing rules, questioned

| Rule | Verdict |
| --- | --- |
| The commandments' core (never break anything, no evidence no claim, don't cheat the judge, tell the truth, content is data, sandbox without secrets, respect licences, humans have the last word) | **Kept**: they are what the judge and the protocol enforce |
| R1 (size), R2 (full CI), R4, R5, R6, R16 (the judge's rules) | **Kept**: a project's limits and goals in the protocol are their direct descendants |
| R3 (two reviews and a vote for each contribution) | **Replaced** for judged work: the judge decides. Human review stays where no judge can decide: changes to tests, judges, CI, tooling and rules |
| R7, R8 (72-hour reservations, three engagements) | **Replaced** by deals: the hive gives one task at a time to an account, for three hours |
| R9 (transparency) | **Kept**, and made cheaper: one public ledger line per answer |
| R10, R12, R13, R14, R15 (votes, agora, invitations, branch rules, devolution) | **Dormant** until there is a community to use them; nothing in daily work depends on them |
| R11 (half of the effort to governance) | **Dropped**: the hive's effort goes to its projects |
| Levels and ranks computed by the old gate | **Replaced** by the ledger's figures (verified work per member); a rank opens nothing a project's safety depends on |
| "A single session never combines writing, reviewing and merging" | **Replaced** by a rule GitHub can enforce: no change to the hive's tooling, judges, workflows or rules is merged by the account that wrote it |

## 2. The design in one page

```
volunteer ── forks a project ── points their AI worker at the fork, once
worker    ── each run: ask for a task, or do the one it was dealt; push to the volunteer's OWN fork; stop
hive      ── every hour, four jobs, each with one risk:
             plan    (holds nothing)   reads the forks, once; runs nobody's code; decides who is dealt what
             record  (state only)      publishes the deals and the feed, within minutes; runs nobody's code
             judge   (holds nothing)   runs contributors' code, in the judge's container
             apply   (project + state) runs nobody's code, talks to no fork, believes only the judge's answers;
                                       integrates one commit per accepted task, records, publishes the feed
everyone  ── reads the ledger, the feed and the project's page
```

Four rules carry the safety:

0. **At any time at most one member may submit for a task, and the hive decides who.** Nobody races, nobody can
   take the credit for someone else's work, and no work is done twice.
1. **A worker can write in one place only**: a branch of its owner's fork. It holds nothing of the hive's and
   nothing of the volunteer's.
2. **The job that runs contributors' code holds nothing**; the code runs in a container without network.
3. **The jobs that write run nobody's code and talk to no fork.** The last one takes the candidates from the first job's
   plan, which the judging job cannot change, derives every commit by itself, and takes from the judging job one
   thing: the judge's answer for a commit it built itself.

The full specification is [docs/protocol.md](protocol.md).

| Piece | State | Where |
| --- | --- | --- |
| The judges | **built**: the common judge (the same outputs as the project's tip, and measurably better), in service for the old flow and for the hive's first project; a second kind, `reference` (a candidate answers as a reference does: [reference-judge.md](reference-judge.md)), built and tested, in service for no project yet | `tools/judge/` |
| The collector (plan, record, judge, apply, ledger, feed, statistics) and the volunteer's commands | **built and tested; in service on miniz since 16 November 2026, by invitation** (one member so far: the founder's own worker). Rebuilt around dealing after seven reviews of the earlier design by another model; each change since is read by another model, and there is not yet a whole round that finds nothing serious: the gate of 7.2 is not passed. The founder started the run for their own account alone, by their own decision ([decisions.md](decisions.md), 16 November 2026); nobody else is invited before the gate is passed | `tools/hive/` |
| The worker's guide | **built** | `.claude/skills/bee-worker/` |
| The hourly workflow (four jobs), the state repository, the integration identity | **in service for miniz since 16 November 2026** (phase 1), on the commit of the registry its file names; a second file, for the second project, is on `main`, switched off, and names no commit. Each file starts every hour and skips its four jobs while its own repository variable (`HIVE_PROJECTS`, `HIVE_CJSON`) is empty. Still to make before the pilot: the dry run of the judge's false refusals ([hive-workflow.md](hive-workflow.md), its last point) | `.github/workflows/hive.yml`, `.github/workflows/hive-cjson.yml`, `docs/hive-workflow.md` |
| A project's configuration, tasks and splitter | **written by hand** for miniz (in service) and for the second test project, `cjson`, a port of cJSON to Rust (declared, paused; its repository is not made yet); no splitter yet | `hive/projects/`, `hive/tasks/` |
| The project page (progress, members, models) and the member's card | **built** (the generator and its tests); where it is published is phase 1 | `tools/hive/page.py` |
| The volunteers' page | **built**, as a draft for the pilot | `docs/join.md` |

## 3. Using the AI power well

The power pointed at the hive is wasted in four places. In the order they bite:

### 3.1 Not enough tasks: the splitter

A hive with a thousand workers and two hundred tasks wastes four fifths of them. **Tasks are generated, never
written one by one.** Each project has a splitter, written once by its maintainers, that turns the project's own
data into small tasks with a goal a machine can check. Three kinds cover what the collector can judge today
(the other kinds of work the hive is for, and how each opens, are in 4.5):

| Kind | A task is | The judge accepts when | Splitter reads |
| --- | --- | --- | --- |
| **Optimise** | "make this function faster", limited to its file | same outputs on every input, and the measured gain reaches the task's goal | a profiler's hot spots |
| **Port a leaf** | "implement this stub so that its tests pass", limited to its file | the project's tests pass, and more of the reference's test cases pass than before | the list of stubs and of failing reference cases |
| **Reproduce** | "write a test case on which two implementations differ" | the case passes on the reference and fails on the other one | the list of entry points not yet covered |

The third kind matters for projects the hive does not own: it produces evidence, not patches, and evidence can be
handed to maintainers who accept no code from strangers.

A task is small (400 changed lines at most by default) and names the exact files it may change. This is what makes
candidates for different tasks independent of each other.

### 3.2 Two workers on one task: the hive deals

- **A worker asks, the hive deals.** Each run, every worker that asked gets one open task, drawn by the hive, its
  alone for three hours. So no two workers are ever on one task, and none of the power is spent twice. **Built.**
- **Tasks that share a file are dealt one at a time**: a member's candidate is public, and the holder of another
  task on the same file could put it into its own. A splitter should give tasks separate files; where it cannot
  (seven of miniz's first eleven tasks change one file), those tasks are done one after the other. **Built.**
- **A task cannot be squatted for long**: one task per account at a time; a deal left without a candidate ends
  after four hours and costs the account a wait that doubles (two hours to seven days), until one of its
  candidates is accepted. **Built.**
- **No way of ending a deal is free**: a candidate the judge examined and refused costs two hours, each time; a
  task held for nothing (left, or its candidate refused before the judge) costs a wait that doubles; what the
  hive's own side caused costs nothing. Measured before choosing: with a doubling wait for every refusal, a worker
  accepted one time in two would take 93 hours on average for twenty tasks instead of 20; with two hours per judged
  refusal it takes 40. An account is also dealt five tasks a day at most, not counting accepted ones. **Built.**
- **Those who deliver are served first**: when tasks are short, members whose last deal was accepted come first,
  then newcomers, then the others. **Built.**
- **A worker that runs every hour gets a task per run, while tasks are free**: it pushes its candidate with an ask,
  and is dealt the next task as soon as the first is accepted. **Built.**
- **The pool stays larger than the crowd**: what counts is the number of tasks that can be held at once, which is
  the number of groups of tasks that share no file. The splitter must keep that number above the number of active
  workers, by giving tasks separate files; the project page shows the ratio. **Planned** (phase 1). **Miniz's
  first eleven tasks make three such groups**: enough for the pilot's three volunteers, and no more.
- **Dealing more often than judging** (a light run every ten minutes that only deals), so that a first task comes
  within minutes. **Planned** (phase 3).

The price, stated plainly: a worker waits for the hive's next run before its first task, and nobody chooses their
task: only the hardest tier they take, and a part of the project they would rather have, which the hive follows
when its rules lose nothing by it (the member's last deal was accepted, and a task of that part is among those the
plain draw could have given it).

### 3.3 The judge's time: the scarce resource

Workers are many and free; the judge runs on the hive's own CI and is the one resource the hive pays for in time.
Everything is arranged so that it only sees candidates that deserve it:

- **Structure first**: wrong paths, size, protected files, binary content are refused from git objects alone,
  without running anything. **Built.**
- **The same check on the volunteer's side**: `hive submit` runs it before pushing, so a worker learns of a refusal
  for free. **Built.**
- **One candidate per task, and one task per account at a time**: what reaches the judge is bounded by the number
  of tasks, not by what is pushed. Whatever the number of commits an account pushes for its deal, one is judged.
  **Built.**
- **Forks of accounts that could not contribute are not read at all**, and a submit for a task its member does not
  hold is not judged, not answered and not read again. **Built.**
- **A breakdown costs nobody**: when the judge fails, the hive tells a broken machine from a candidate that broke
  it. **Built.**
- **Capacity earned by verified work**: accepted deals do not count in an account's day, and members whose last
  deal was accepted are dealt first. **Built.**
- **Judging in parallel**: tasks name disjoint files, so candidates for different tasks can be judged at the same
  time on the same tip, then integrated together after one confirming judgement of the whole (and split in two on
  failure). Twenty serial judgements become one parallel round. **Planned** (phase 3), needed above a few thousand
  contributions a week.

### 3.4 The wrong model on the task: tiers

- **A task carries a tier** (1 to 3), and a worker says the highest tier it takes. **Built.**
- **A task the judge keeps refusing is flagged**: the feed's hint rises by one for every three different members
  refused, among those the judge has accepted something from. The hint is for the project's maintainers, who set
  the tier: tasks are dealt by their own tier, so accounts that only send junk cannot push a task out of anyone's
  reach. **Built.**
- **The feed remembers why**: each task shows how many candidates were refused and for which reasons, as counts.
  **Built.**
- **Each answer records the model the worker declared.** The project page shows, per model, candidates judged and
  accepted: a public, running measure of which models land verified work. It is a statistic, not a proof.
  **Built.**

### 3.5 What is measured

Four numbers, per project, from the ledger and the feed: **yield** (accepted candidates out of judged ones),
**deals kept** (deals that ended with a candidate, out of deals made), **judge runs per integration**, **time to an
answer** (from the deal to the verdict). The page shows the first and the third today; the other two are phase 1.
There is no duplicate rate any more: a task has one holder. The pilot sets the first values; a change to the
protocol is kept only if it moves them the right way.

## 4. Projects

### 4.1 Three ways to use the hive

| | Hosted | Invited | Your own |
| --- | --- | --- | --- |
| Whose repository | the hive's | its maintainers' | anyone's |
| Who judges | the hive's judge | the hive's judge or the project's CI | nobody at the hive |
| What happens to accepted work | integrated by the hive, on a branch of its own; the project's maintainers publish from it what they have read | **offered**: kept on a branch the maintainers pull from, at the rate they set. The hive never opens a pull request on its own | whatever the volunteer does with it |
| The hive answers for | the judge, the credit, the legality | the judge and the credit | the worker's loop and its limits, nothing else |
| State | **built** (protocol) | **planned** (phase 4), only with the maintainers' written agreement | **not built**: the worker's commands take only a fork of a project the registry declares |

The worker never opens a pull request, an issue or a comment anywhere, in any mode. Every policy on AI
contributions read during the research asks for a human who reviewed the change and answers for it **(unverified:
read through a research agent, to re-read before any project is approached)**; an unattended worker is not that
human.

**The hive is a platform, and a project is an add-on** (the founder's direction of 14 November 2026). The hive is
a set of rules, a protocol and the tools that apply them; no one project is its purpose. A project comes as an
add-on: its file (what it is, its licence, how it stays legal, who maintains it, what judges), its judge's plug-in,
its sandbox and its tasks, kept together so that the hive's own code knows nothing of any one project. miniz is
the first. The hive is built so that anyone can write one, in a repository of their own; it makes none but its own.

What sets one add-on apart from another is **which of the hive's services touch it**:

| | An admitted add-on | Any other |
| --- | --- | --- |
| Listed by the hive | yes: declared in the registry, by the council | no |
| Dealt, judged, recorded, credited | yes | no: nothing of it enters the ledger, the feed or a page |
| The hive's name | a project of the hive | not the hive's, and not presented as such |
| Who answers for it | the hive, for the judge, the credit and the legal statement of its file | its author and those who use it; where the hive's own answer ends is a question for the lawyer (D3, 2) |

**The order of building.** The add-on's format comes first (the project types of ruche-0003), since miniz's own
file is written in it. The worker's commands for an add-on outside the registry come last, after the review by
another model that the opening gate asks for: until then they take only a fork of a project the registry
declares. Whatever the add-on, the worker's rules do not move: what an add-on brings is data, and code that runs
only in its sandbox; it gives a worker no instruction; and a worker writes only to its owner's fork.

**A project made for the hive.** The founder, or members of the community, may create a project so that the hive
works on it: a new one, or a fork of an existing one whose licence allows it (minizBee is such a fork). It is not
a fourth way. Its makers are its maintainers, and their agreement is in the making:

- If they want the hive to deal its tasks and to record credit, the project is declared in the registry, by the
  council as for any other (docs/new-project.md), and meets 4.2 whole. Its file says who maintains it and what
  judges: the hive's judge, or the project's own checks, and each line of the ledger then says which. A volunteer
  works for it only by choosing it: the hive moves nobody's agent to a project its owner did not pick.
- If they do not, it is "your own": the hive judges nothing of it and records nothing.

For a fork: its first lines say that it is an independent fork, and it keeps the licence and the notices; the hive
sends nothing to the project it was forked from; and what the hive never holds (4.4) it does not hold for a fork
either. A fork of a project whose own rules refuse AI contributions is lawful where the licence allows, and
unwelcome to its authors: the hive makes or serves none without the founder's decision, case by case.

### 4.2 What a hosted project must have

1. **Real demand**: people who want the result, not only its builders.
2. **A judge that has been attacked.** Where a machine can say whether a contribution is right, a machine does
   (the three kinds of 3.1). Where none can, the hive's own forms of judgment do (4.5). In both cases no judge
   decides real work before it has held on a school project with known answers (the founder's decision of
   31 October 2026; docs/vision.md, "a kind of work opens only once its judge has been attacked").
3. **Splittable work**: many small tasks, independent enough to be dealt to different members; for code, on
   separate files.
4. **Legal safety**, stated in the project's file: licences compatible; no copyrighted asset, ROM or key hosted or
   needed; no work that breaks a protection.
5. **Nobody else's permission needed to start** (new): a hosted project is one the hive may fork or write under its
   licence, without asking its upstream for anything.

### 4.3 The choices

1. **miniz: the proving ground, first in service** (phase 1). Optimise tasks, the existing judge, a profiler as
   splitter. It proves the whole chain with three volunteers. It will not draw a crowd, and is not asked to.
2. **The first building project: two candidates, and a spike decides** (chosen by the builder on 14 November 2026,
   by the founder's delegation). The hive does not open on a promise: neither is "chosen" before its spike.

   **First candidate: a memory-safe packet decoder with tcpdump's exact output.** A new work in a repository of the
   hive's own, written from tcpdump's printers, pinned to one release. Read on upstream's sources at the tag
   `tcpdump-4.99.7` (commit 1c950db, 21 September 2026), on 14 November 2026:
   - **It splits**: 158 printer files, one protocol each, some 300 tasks once the larger ones are cut. This is what
     the hive lacks most: miniz's eleven tasks sit on three files, so three members at most hold one at a time.
   - **A judge exists**: upstream's own tests, 606 test lines and 653 expected outputs on 724 captures; the candidate
     prints what the pinned original prints, on those and on captures the judge alters; it never panics.
   - **It needs nobody's yes**, and its category exists (parsing and serialization: the same output as the reference,
     the same refusals on invalid input).
   - **Not known, and what the spike must answer**: whether the project's sandbox can carry a Rust toolchain and
     the pinned original with no network; whether one small printer and one slice of a large one (BGP) reach exact
     output in a three-hour deal; how many test lines exercise one printer alone, so that each task has tests of its
     own; and the licence questions of 4.4.

   **Second candidate: PCRE2 in safe Rust**, the earlier flagship. It has the wider reach, and it splits less well:
   one compiler and one matcher, a long serial start, and a C interface to keep.
   PCRE2 is the
   regular-expression library behind a large number of programs **(unverified list: git, grep, PHP, nginx)**. A
   memory-safe, compatible engine is wanted: a search of GitHub on 12 November 2026 found one project that plans
   it and has not started, one that states it is not a drop-in replacement, and no complete port (a search, not a
   proof of absence). Why it fits the hive:
   - **A judge exists**: the original and its test data. A candidate is right when it answers as the original does.
   - **It splits**: "port a leaf" tasks, one stub per file, in a skeleton the maintainers write.
   - **It needs nobody's yes**: the hive writes a new work under PCRE2's licence.
   - **The result is checkable by anyone**: the page shows how many of the reference's cases pass.

   What is **not known**, and what phase 2's spike must answer before anything is promised:
   - whether the common judge, built for C, can judge a Rust candidate (on correctness alone at first);
   - whether a regex engine's skeleton can be cut into several hundred leaves on separate files;
   - what a judgement costs in minutes.

   If both spikes fail, the first building project is chosen again with the same criteria.
3. **libyaml: put to sleep.** It has no outside judge. Nothing is deleted; it comes back as tasks if someone ports
   its judge.
4. **Checking the AI-written ports that already exist** (the founder's decision, D9). At least one public effort
   has published C libraries ported to Rust by agents, says that no human has read the code, and accepts test
   cases that show a difference from the original, not patches. "Reproduce" tasks are exactly that. It needs a
   contact with its maintainers and an agreement on how a difference that is a vulnerability is reported: the
   founder decides. The hive does **not** port again what they ported: that would be the duplication the hive
   exists to end.
5. **A game of the hive's own** (4.6). The founder set gaming aside on 12 November 2026, and on 14 November said
   that a video game would be an interesting and attractive project. The hive builds an original game; it does
   not work on the emulation of a console still sold, nor on a published game.
6. **Mathematics: a trial before any opening** (4.5). Two public projects already take donated assistant quota for
   Lean proofs (reported by a research pass of 14 November 2026, not yet read at the source): the hive does not
   double a living effort, and opens this kind only if a trial on vetted statements clears a rate set in advance.
7. **A large free program built piece by piece** (the founder's example: an image editor): the one first step a
   machine can judge today is a library of pixel operations compared with a reference. To study after the first
   building project.

### 4.4 How each stays legal

| Project | Licence | Statement |
| --- | --- | --- |
| miniz (hosted) | MIT (read in the fork's `LICENSE`) | A fork under its licence; contributions under the same; no asset, no protection involved |
| PCRE2 in Rust (hosted, if phase 2 says yes) | BSD-3-Clause WITH PCRE2-exception; its `LICENCE.md` says of the test data that it "is not copyrighted and is in the public domain" (read on 12 November 2026) | A port is a derived work under the same licence, notices kept; the judge uses the public-domain test data; no asset, no protection involved |
| Packet decoder (hosted, if its spike says yes) | tcpdump's `LICENSE` is a three-clause BSD licence; each printer carries its own notice (read at the tag `tcpdump-4.99.7` on 14 November 2026): 76 of the 158 add an advertising clause, three offer "the BSD-style license that accompanies tcpdump" or the GNU GPL (`print-beep.c`, `print-dccp.c`, `print-smb.c`: the hive takes the BSD one), and three carry no licence wording at all (`print-arista.c`, `print-ipnet.c`, `print-ppi.c`) | A port is a derived work of each file it is written from: each ported file keeps that file's notice, and the three files without a notice are not ported until their licence is known. **Open before any opening**: the `tests/` folder states no licence of its own for the captures and the expected outputs; until that is settled the hive hosts no copy of them, and its judge reads them from upstream at the pinned commit. No asset, no protection involved |
| libyaml (asleep) | MIT (read in the fork's `License`) | As miniz |
| Mathematics (a trial only) | Lean 4 and mathlib: Apache-2.0; statements from a public repository of formal statements, software Apache-2.0 and other material CC BY 4.0, with CC BY-SA 4.0 for what comes from three named sites (reported by a research pass of 14 November 2026; **to read at the source before the trial**) | The hive depends on the statements at a pinned commit and copies none; a proof is the hive's own work |
| The hive's own game (planned, 4.6) | a free licence for the code and a free licence for the art and sound, each chosen before the first task; the toolchain's and the emulator's own licences, read before the console is chosen | Design, code, art and sound are made in the hive, or taken under a free licence recorded file by file. It recreates no published game: no code, character, art, music, level, name or look of one. The file it produces holds no byte owned by a console's maker, or that console is not chosen; it needs no system file of the maker to run. Its name and art use no one else's mark. No protection involved |
| Invited projects | theirs | Only with the maintainers' written agreement; contributions under the project's licence |
| Your own | the volunteer's concern | The hive hosts nothing, judges nothing and distributes nothing of it; the volunteer's choice of project and their AI provider's rules are theirs to answer for |

Whatever the project, the hive itself never hosts or distributes copyrighted game assets, ROMs or keys, and never
helps break a protection.

### 4.5 The other kinds of work, and how each opens

miniz is the first example, not the hive's purpose. docs/vision.md names four kinds of work, set apart by **what
judges a contribution**: optimizing (a machine: identical outputs and a measure), building (tests written before
the code by others, a specification, a reference), proving (the kernel of a proof assistant), and deciding without
an oracle (competing proposals, votes, juries, decisions revised by their measured consequences). The founder said
it again on 14 November 2026: in time the hive works on less concrete things and goals, and it is for the hive and
its builder to choose the projects and to put in place what each needs. Sections 3.1 and 4.2 of this plan had
narrowed the hive to what a machine judges; they are corrected.

**How a kind opens** (the same ladder for each, from the registry's own rules):

1. **Its judge is written down** in docs/judges.md (task ruche-0004): what is judged, how one could cheat, what
   blocks it, and which seeded errors the judge must catch.
2. **A school project** calibrates it: small, written by the hive, with no upstream and no outside person, with
   known answers: seeded cheats, seeded regressions (the founder's decision of 31 October 2026). The cheats that
   are traps change, and stay out of the public repository.
3. **The judge is attacked** by a model other than the one that built it, as the collector was.
4. **Only then a real project**, chosen for demand, splittable work and legal safety (4.2), after a spike.

**The order**, and why:

| Kind | First real project | State |
| --- | --- | --- |
| Optimizing | miniz | in service by invitation since 16 November 2026 (phase 1) |
| Building | the packet decoder, then PCRE2 (4.3) | a machine still judges the code; the judgment that is new is of the **tests** others write before the code (seeded mutants they must catch). Next after the pilot |
| Deciding without an oracle | the hive's own choices first (which tasks, which project next), on a school project | the least concrete kind, and the hive's own. Its form of judgment is to be designed in docs/judges.md and attacked before it decides anything real; a human's word is final until it has held (commandment 11) |
| Proving | none yet: a trial (4.3) | the strictest judge, and a field where others already work at scale |

**Several members on one task.** Competing approaches followed by a choice are the hive's rule for large decisions
(docs/vision.md; R11 and ruche-0001 in the older flow). The collector deals one task to one member, which is what
makes copying worthless while forks are public. So races are tried on the school projects first, and a real
project keeps one holder per task until a way to keep a rival's work unread has held. Where the work adds up
(test inputs that each cover something new), every candidate that adds something is kept, and no race is needed.

**What a volunteer may prefer.** The unit exists in the registry: a node of the tree of meaning (docs/tree.md): a
category, a project, or an area of a project. A volunteer chooses a project by the fork their agent works in, and,
within it, may name an area. The first version of the preference names a file of the project's tasks; it moves to
the area with the project types of ruche-0003.

### 4.6 Games: what the hive builds, and what it does not

On 14 November 2026 the founder said that a video game would be an interesting and attractive project, and asked
how the hive could take part in today's wave of static recompilation and console emulation without illegality.
This section is the builder's answer, by the founder's delegation of the choice of projects. It describes the
hive's own rules; what the law allows in a given country is for a lawyer to confirm before anything opens (D3).

**What that wave is judged by, and why the hive cannot judge it.** Those projects are judged by whether a
published game runs. The hive holds no game file (4.4), so no judge of the hive can run one: it would have
nothing to check such work with. Their own contribution rules say the same from their side (read on 14 November
2026): an emulator of a current console closes requests that "do not address a concrete bug or launch problem in
a specific game"; another asks that "the emulator must run the games or features affected by your change".

**What the hive does not do**, and what each refusal rests on:

1. **The hive's hard rule** (4.4): the hive, its judge and its workers host, fetch and run no game file, asset,
   ROM, key, firmware or system module, and nothing that removes or goes round a protection.
2. **The projects' own rules, and the rule on outside contact**: nothing goes from the hive to a project that has
   not agreed in writing, and only the founder asks. Read on 14 November 2026 in each project's own files: N64:
   Recompiled and Zelda 64: Recompiled refuse contributions made with AI; three console emulators (RPCS3, shadPS4,
   KytyPS5) accept AI assistance that is disclosed, from a person who understands and has tested what they send,
   and two of them ask that every exchange come from "the human contributor", not from an AI agent. An unattended
   worker is not that person. A member who contributes there does so in their own name, under those rules, and
   not as the hive.
3. **No recreation of a published game**: the hive does not decompile, port, remake or imitate one. It works only
   on what it may publish whole.
4. **Nothing on the emulation of a console still sold** (the builder's choice, which the founder may overturn):
   its games are its maker's current trade, and point 1 leaves the hive unable to verify any of it.

**What the hive builds: an original game, written for an old console.** Its own design, code, art and sound,
under free licences. To belong, lawfully, to the scene the founder points at, it is written for an old console
with a free toolchain, and runs in open-source emulators and on the real machine: what that scene calls homebrew.
Why this suits a hive:

- **A machine judges the floor.** The build is reproducible; an emulator run in the sandbox with scripted input is
  repeatable, so the picture after a given input is a fact that can be hashed; a scripted run must reach the end
  of each level; the size of the file, the time of a frame and the memory of an old machine are hard limits, which
  makes measured tasks of the kind miniz has. All of this is to be shown by the spike below, not assumed.
- **The rest is the hive's least concrete kind**: what the game is, which of two levels or two tunes is the better.
  That is deciding without an oracle (4.5): several candidates, compared; people who play it have the last word.
  So the game opens on that rung of the ladder, after the school project, and not before the pilot.
- **It joins the wave with a program anyone may redistribute.** The same scripted run on two emulators, or on an
  emulator and on a statically recompiled build of the hive's own game, must show the same pictures. Where they
  differ, the difference comes with a program its receiver may run and pass on, which a difference found in a
  published game never does. Which side is right, only the real machine says: a person who owns one runs it.
  Such evidence goes to a project only through the founder, and only to maintainers who want it (as for item 4
  of 4.3).

**The check that picks the console**, before any is chosen:

1. the file a free toolchain produces holds no byte owned by the console's maker (a logo, a boot code, a licence
   string that the machine demands);
2. the toolchain and an open-source emulator build and run in the sandbox, without network and without a screen,
   and two runs of the same input give the same pictures;
3. the emulator needs no system file of the maker;
4. the toolchain and the emulator are maintained.

Read on 14 November 2026: the Game Boy fails the first test (its reference documentation says the header "must
match" the maker's logo, "otherwise the boot ROM won't allow the game to run"). For the Nintendo 64, libdragon
(Unlicense) says it boots with an "open-source IPL3 bootcode" and names ares (ISC) as the one accurate emulator,
but its repository is marked archived since 1 October 2026, with no successor named: the fourth test is open. For
the NES, cc65 (zlib licence) lists it as a target; whether an NES program must carry bytes of the maker was not
read. No console is chosen.

**The spike** (three hours, like the others): a program of a few lines, the hive's own, built in the sandbox with
the candidate toolchain, run twice in the candidate emulator with one scripted input, the two pictures hashed and
equal. If no console passes the four tests, the game is built for no console, as a free program for today's
machines, and joins the wave by nothing but its being a game.

## 5. The volunteer's experience

### 5.1 Setting up, once

1. Fork the project under your own personal account (one click).
2. Create a scheduled task in your own AI tool, attach your fork and, to read only, the registry, the hive's state
   (`Bee-ruche/hive-state`) and the project itself, remove every connector, and paste the one prompt the setup page
   gives (it names your GitHub login, which every command of the tool is given, tells the assistant to follow the
   registry's `bee-worker` skill, and states the schedule, which the assistant cannot see by itself).
3. Choose a schedule: every hour is best (all your quota). Only the hours before your weekly reset (only the
   leftovers) works if those firings are at most two hours apart, several in a row: a task is dealt at one firing
   and done at a later one, and the worker starts on a deal only if an hour of its three is left.

Nothing else, ever: no token given to the hive, no pull request, no review to answer, no approval to click. The
volunteer is expected to know what a fork and a scheduled task are; nothing more.

### 5.2 What each run does

One run does **one thing and stops**. `hive next` says which: ask for a task (`hive ready` makes the ask, a commit
with no file and no parent, and pushes it to the fork), or do the task the hive dealt (`hive start`, which asks
the project's own repository for its tip, sets aside what an earlier run left, puts the clone on the task's branch
at that tip, and says the task started only once it has shown, from bytes it hashed itself and from the work
tree's own files, that the work tree holds the tip's files and nothing else, the sandbox's launcher included; the
work, the project's own tests in the sandbox; then `hive submit`, which commits the task's files, adds the marker,
shows from
bytes it hashed itself that the candidate starts from the project's history and changes only the task's files, runs
the hive's structural check and pushes to the fork), or nothing. The fork's address is worked out from the
volunteer's login and the registry, never taken from the clone. The assistant runs no git command of its own in
the fork's clone: each of the tool's commands first checks that the clone's git settings are the ones a clone has,
and changes branches, commits and pushes itself. The run
ends with three lines for the volunteer: what was done, what happens next, where to look. When the quota is
spent, runs are refused by the provider and resume by themselves after the reset: the worker never needs to read
the remaining quota.

### 5.3 What the volunteer gets back

- **Their name on the work**: every integrated commit is authored by the fork's owner under their GitHub identity,
  so it appears on the project and, GitHub's rules permitting, on their profile **(to verify in phase 1)**.
- **An answer for every candidate**, with a reason code when it is refused, in a public ledger.
- **A page**: the project's progress, their own accepted work, and the models' table.
- **No surprise**: the setup page says first that a volunteer who turned paid overage on would pay real money for a
  donation loop.

### 5.4 What a volunteer can use today (checked on the providers' own pages, 12 November 2026)

| Option | Unattended? | Safety by default | Quota | Terms |
| --- | --- | --- | --- | --- |
| **Claude: cloud scheduled task** (claude.ai/code/routines, Pro and above) | Yes: each firing is a fresh cloud session in auto mode; runs while the laptop is closed; minimum interval one hour | Isolated VM; GitHub credentials stay outside it behind a proxy that serves only the repositories attached to the task; network limited by default | Draws on the plan; when it is spent, runs are rejected and resume by themselves after the reset; reading the remaining quota from inside is not documented | First-party feature; see "Terms" below |
| **Claude Code, headless on the volunteer's machine** (`claude -p … --permission-mode auto --permission-prompts none`) | Yes, while the machine is on | Shell sandbox is off by default: needs a dev container or the built-in sandbox | Readable (`rate_limits` in the status line and the stream), so the worker can stop at a chosen threshold | First-party; the "programmatic use" area is the one the provider keeps adjusting |
| **OpenAI Codex CLI** (`codex exec`, signed in with ChatGPT) | Yes: headless mode never asks for approval | Read-only by default; `workspace-write` has no network and keeps `.git` read-only (confirmed in the source) | Readable through the app-server (experimental) | First-party; terms read only through excerpts **(unverified)** |
| **GitHub Copilot CLI** (`copilot -p --autopilot`) | Yes, documented for scripts | No confirmed default sandbox | Monthly credits, forfeited if unused | First-party; its cloud agent needs write access, so it works only on the volunteer's own fork |
| Codex cloud, Jules, Antigravity, Cursor, Grok | Partly or unconfirmed | — | — | Not for the first release |

**Chosen for the first release: the Claude cloud scheduled task** (no terminal, no machine left on, isolation by
default). **Second: Codex CLI on the volunteer's machine.** The worker is a skill and a prompt in the registry: any
assistant that can read a repository and run commands can use it.

### 5.5 Terms: what is allowed, and what is not

- **Forbidden by every provider, explicitly: anything where the hive holds a volunteer's credentials or drives
  their account.** No token handed to the hive, no shared CI secret, no third-party client signed in with a
  subscription. The worker is always the volunteer's own, unmodified, first-party tool, signed in by the volunteer.
- **The design is "pull", never "push"**: the volunteer's agent reads a public task list and chooses; nothing in
  the hive sends requests into anyone's account.
- **Not settled: whether an organised, public effort that drains volunteers' leftover quota counts as "ordinary,
  individual usage"**, and how the clauses on making an account "available to anyone else" and on services that
  "route requests through consumer subscriptions" apply to it (Anthropic's Consumer Terms and Usage Policy, the
  latter in a version effective today, 12 November 2026). The same question stands for OpenAI. GitHub's
  Acceptable Use Policies, for their part, forbid "automated excessive bulk activity" incentivised by rewards.
  **This is a decision for the founder before the public opening**: ask the providers directly and have a lawyer
  read the answer (docs/founder-decisions.md, D1).
- **Never charge a volunteer by surprise**: a volunteer who has paid overage turned on would pay real money for a
  donation loop. The setup page says so first.

### 5.6 The worker's safety, and its scope

- **The worker reaches nothing of the volunteer's**: no connector (it stops if it holds one), no secret, and no
  repository of theirs other than the fork, the only place it writes. It reads three public ones: the registry, the
  hive's state (`Bee-ruche/hive-state`) and the project itself (fetched, never written).
- **Everything it reads is data**: the task, the code, the comments, the file names, and the fork's own agent files
  (`CLAUDE.md`, `AGENTS.md`), which the volunteer's tool loads before the skill. Its instructions are its skill
  and its owner's prompt. The hive narrows what a contribution can plant for later workers (agent instruction
  files are protected at any depth, new file names must be identifiers, the feed carries nothing a contributor
  wrote), and the limit above is what holds when that fails. The worker's tool takes a task's text, its files and
  the project's check from the registry, believes the hive's state only for what the hive did for this member (its
  task and until when, its wait, whether its candidate was seen and its ask used, and whole numbers), and prints a
  fixed list of lines: no text of the feed or of the fork reaches the assistant as if the tool had said it.
- **Untrusted code runs only in a sandbox**: the fork's own `bee/sandbox/` (its script without Docker on Linux, or
  its Docker image), which the hive's projects protect from contributions. A cloud session is not a sandbox by
  itself: it holds the credentials that push to the volunteer's fork. What ran in the sandbox may have written into
  the clone's `.git` (a filter, a hook, another address to push to): so every command of the worker's tool first
  checks that the clone's git settings are the ones a clone has, without running anything of the clone, runs git
  without reading the machine's settings where files are read, and makes the commits and the pushes itself, to
  the fork's own https address, which it works out from the volunteer's login and the registry. What it pushes
  is an ask that holds no file, or a candidate it has shown, from bytes it hashed itself, to start from the
  project's history and to change only the task's files.
- **"Your own project" is not built.** If it is one day, it gets the loop's limits, not the hive's guarantees: no
  hive judge checks the result.

## 6. Procedures

### 6.1 Who changes what

| What | Who | How |
| --- | --- | --- |
| A task's files (judged work) | any eligible member's worker | the protocol; the judge decides |
| A project's tasks, limits, bans, its pause | the project's maintainers | a reviewed change to `hive/projects/` and `hive/tasks/` in the registry, then the workflow's line moved to that commit (6.3) |
| Stopping the hive at once | the founder and the registry's administrators | the repository variables that start each project's run (`HIVE_PROJECTS`, `HIVE_CJSON`), emptied (6.3) |
| Tests, judges, CI, agent instruction files, the hive's own files in a project | maintainers only | a pull request approved by a second identity; never the protocol |
| The collector and the worker's guide | the builder, then the maintainers | section 6.2 |
| The rules | the council | as today |

### 6.2 The safety base: the hive's first project, and a permanent one

The founder said it on 14 November 2026: the safety base is the hive's main project, and a permanent one. It is
what everything else stands on: the common judge, the collector, the worker's tool and its guide, the workflows
that run them, and each project's sandbox. A volunteer lends their own account to the worker's tool, and the
collector decides what is credited and integrated: if either can be fooled or stopped, nothing built on them is
worth anything. In the registry this is the hive's own project (`projects/ruche.yaml`); it has no end date, and
phase 0 of 7.2 is a gate that is passed, never one that closes.

A change to `tools/hive/` or to the workflow that runs it is accepted only with, in this order:

1. **A test for each refusal and each guarantee**, written to state the secure outcome, and **the rules that must
   hold over many runs, written down and tested over schedules drawn at random**.
2. **A mutation run**: each check removed or reversed in turn must make a test fail; a survivor is a missing test
   or dead code, and is settled before the review.
3. **An adversarial review by a model other than the one that wrote the change**, given the code and the threat
   model, never the author's list of what is fixed, and asked for running proofs.
4. **Nothing public about a weakness until it is fixed**: findings go to the private report.

What the builder adds to make it permanent (proposals, the founder's to change):

- **A whole round before each phase opens**, on the code as it then stands and not only on what changed since
  the last one, by a model other than the one that wrote it; and again at least once a month while the hive is in
  service, whether or not anything changed.
- **Each defect becomes a rule that is tested**, over schedules drawn at random where it is a rule over time, and
  the test is shown to fail on the code that had the defect.
- **Work that looks for a break is not dealt through the protocol.** Forks, candidates and the ledger are public,
  and rule 4 above forbids it. Volunteers' workers can help the safety base only once a private channel exists
  for what they find, which is the founder's to set up; until then this work is the builder's and the reviewers'.
- **The private report lives in a private repository of the organisation** (the builder's choice of 15 November
  2026, the founder having left it to the builder), with the reviewers' reports and their proofs. Creating it is
  the founder's click (D10); until it exists the founder holds the files, handed over on that day. It is kept
  outside the public repository by rule 4, and nothing of it is copied here before the weakness it describes is
  closed.
- **A worker's commands run on Linux only, for now** (the same day, the same delegation): a Linux machine or a
  cloud session. They were never run on Windows or macOS, where a name or a path may mean something else; they do
  not start there until a whole round has been run on that system.

### 6.3 Running the hive

- **What a run reads.** A run uses the registry at one commit, the one the workflow file names
  ([docs/hive-workflow.md](hive-workflow.md), setting 7): the hive's code, a project's settings (its pause, its
  bans, its limits) and its tasks. A change to any of them acts from the day a pull request moves that line to a
  commit that holds it, and not before.
- **The stop button**: empty the repository variable that starts each project's run (`HIVE_PROJECTS` for the
  first project, `HIVE_CJSON` for the second: one variable per run) and cancel the runs in flight. Both act at
  once, without a pull request: nothing more is read, judged or integrated. `"paused": true` in a project's file
  does the same for that project once its workflow names a commit that holds it.
- **Taking a commit back**: stop the hive (above); close the commit's task (`"closed": true` in the tasks file;
  add a new task if the work is still wanted) and move the workflow's line to the commit that closes it; then
  revert the commit on the hive's branch of the project (a revert commit, rather than moving the branch back), and
  on the published branch too if it was already published, and start again. The hive never undoes a maintainer's commit: it only ever adds to the tip it judged, and leaves a branch
  that moved. But the ledger still says the task is done, and an integration whose record was still pending would
  be pushed again if its task were open: hence the task first.
- **A ban** names the account's numeric id; it holds through a change of login. Like every setting, it acts once
  the workflow names a commit that holds it: for an account to stop at once, stop the hive first.
- **A lost record**: the hive promises in its ledger before it pushes; the next run completes the ledger from the
  promise.
- **A commit the project's repository declines** (a rule on what may be pushed there): counted against its
  candidate, three times at most, when the hive had just pushed there in the same run (otherwise the hive's own
  right to push is as likely the cause, and the candidate only loses its place); the run ends in error so that a
  maintainer sees it.
- **An incident** (the judge accepted what it should not have): stop button, revert, a task for the judge's gap, a
  line in the decision log. The member is banned only for cheating, never for a judge's mistake.

### 6.4 The old flow

The old contribution flow (reservation, declaration, reviews and votes through pull requests, `tools/bee.py`) is
**closed to outside contributions**: the protocol replaces it. It stays for the maintainers' own changes until
plain reviewed pull requests replace it, gets no new feature, and its levels are not fed by the new ledger.

### 6.5 Growth: the pledge and the rest

- **Optional to join, always.** No feature of the worker needs it.
- **It earns no rank and no privilege** (the founder's idea was to require it for higher ranks; the check of X's
  rules argues against it, decision D2). X's Developer Policy, read in its official source today, says "Your
  service shouldn't compensate people to take actions on X" and forbids "monetary or virtual compensation for any X
  actions"; a rank given for a post plausibly falls under it, and GitHub's own policies forbid activity
  incentivised by rewards. A pledge that is a free act of support is safe; a pledge that buys standing is not.
  Ranks come from verified work only.
- **Written in the member's own words**, inspired by the drafts (docs/founder-decisions.md, D2), posted once by the member, by hand, never by
  an agent and never repeated. The hive never pre-fills the post: identical posts from many accounts are the
  "copypasta" X's authenticity policy forbids. No required hashtag or mention, and never a request for likes,
  reposts or follows.
- **Linked opt-in, for the wall of pledges only**: the member pastes the post's address on their hive profile; the
  post carries the member's personal hive code so that no one can claim someone else's; the hive reads it once
  through X's public embed endpoint (documented as needing no authentication; to test before use), keeps only the
  handle and the post's number, and deletes both when the post is deleted, protected or suspended, as X's terms
  require. The member can unlink at any time.
- **The wall shows plain links**; an embedded post loads only when a visitor clicks it (embeds send visitor data to
  X). Nothing on the wall suggests that X or any member endorses anything beyond their own words.
- **Other networks count the same**: Mastodon (verified profile links), Bluesky, a personal site or a GitHub
  profile; the member chooses.

The other levers: **"your AI built this"** (the volunteer's name on the project page and a card to share), **the
models' table**, **progress made visible** (one bar per milestone), **teams** (a community brings its members, as
volunteer-computing projects have done for decades).

## 7. The road

### 7.1 What only the founder can do (asked once, here)

1. **Merge this work**: a pull request from `claude/inspiring-dijkstra-7b7hjk` to `main` (the builder opens none
   without being asked).
2. **The repository settings** the private report lists, and for each hosted project two branches
   (docs/hive-workflow.md, setting 4): the hive's own, writable only by the hive's integration identity and the
   maintainers, force pushes blocked; and the one the project publishes, which the integration identity may not
   push at all.
3. **Two integration identities** (done on 13 November 2026): two GitHub Apps, one that can write the state's own
   repository (`Bee-ruche/hive-state`, public) and one that can write the hosted projects' branches, each key in
   an environment of the registry that accepts the branch `main` only. The hourly workflow is
   `.github/workflows/hive.yml`; the settings it needs are in [docs/hive-workflow.md](hive-workflow.md) (the
   last of them, the commit of the registry it uses, was made on 16 November 2026 and moves by a pull request of
   its own).
4. **Access to the two forks** for the builder, or the founder applies the forks' changes: the builder's pushes to
   them are refused, and it does not work around a refusal.
5. **The decisions** D1 to D10 (docs/founder-decisions.md), first of all D1 (ask the providers), D4 (the flagship)
   and D8 (three volunteers).

### 7.2 Phases, each with the proof that ends it

| Phase | Work | Ends when |
| --- | --- | --- |
| **0. The safety base** (now, and again before each later phase: 6.2) | Each adversarial review answered; mutation run with no unexplained survivor; the registry's full suite green; the private report's open items closed | A whole round by another model, on the code as it stands, finds nothing high or critical. The gate is passed, never closed |
| **1. In service on miniz, by invitation** | The hourly workflow (four jobs; the right to write the project in `apply` only, the right to write the state in `record` and `apply`; the plan's SHA-256 as a job output) and the state repository; miniz as the first add-on, in the format of 4.1 (its file, its splitter and its goal); the setup page and the prompt; the project page; the old flow closed to outside contributions | **Three volunteers who are not the founder** set up in fifteen minutes, do nothing else for a week, and each has an integrated contribution; the four measures of 3.5 have their first values |
| **2. The flagship, yes or no** | The spike of 4.3: a Rust plugin for the judge, a skeleton, a splitter, twenty leaf tasks done by workers | At least 200 leaves generated by the splitter, a judgement under ten minutes, half of the twenty accepted at the first try. Otherwise: choose again |
| **2b. The other judges** | docs/judges.md complete; a school project for each new kind (tests judged by the errors seeded for them; deciding without an oracle), each judge reviewed by another model; the trial of thirty statements for proving; the game's four tests and its spike (4.6) | Each school project's seeded errors are all caught, and a review by another model finds nothing high or critical |
| **3. Hold the crowd** | Judging in parallel; forks read only when they changed; capacity earned by verified work; the Codex path; a rehearsal with 200 simulated workers, some hostile | A week of rehearsal with no human action, four deals in five ending with a candidate, and no integration the judge should have refused |
| **4. Open** | The flagship's first milestone public; "invited" mode for the first project that asks; the worker's commands for an add-on outside the registry (4.1); the pledge | The gate below |

**The opening gate.** All must be true: the private report closed and a fresh review by another model clean; the
providers' answers (D1) and the lawyer's (D3) in hand, and the design matching them; phases 1 to 3 ended by their
proofs; every hosted project states how it stays legal; no contribution waits on a human, except changes to
judges, tooling and rules, for which at least two people other than the author can review.

## 8. What this plan does not decide

The founder decides: whether and how to ask the providers about quota donation (D1), what the pledge may earn (D2),
the legal questions (D3), the flagship (D4), the council's two new members (D5), the public name (D6), the
housekeeping only his account can do (D7), the recruiting of phase 1's volunteers (D8), whether to approach the
maintainers of the AI-written ports (D9), and what only his account can set up for phase 1 (D10). The decisions, with options and recommendations, are in
docs/founder-decisions.md.
