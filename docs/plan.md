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
| Leases: a claimed task is offered to nobody else | A lock needs a referee and a clock everyone trusts, and a claim costs nothing: locks invite squatting | **A claim is a hint.** Duplicates are made cheap instead of impossible (section 3.2) |
| Work handed to the hive through a pull request from the fork | Pull requests bring the first-contribution approval click, one merge a minute, and a flood for maintainers | **No pull request.** The hive integrates what its judge passed |
| Redundancy (each result re-done by another worker) and reputation with decay | Designed for volunteers' machines that judge; the hive's judge runs on its own CI and decides alone. Machinery for a problem the hive does not have | **Dropped** until volunteers' machines judge |
| "One invited project as pilot, still to study" | The opening depended on a stranger's yes | **A flagship the hive can start alone** (section 4.3), invitations second |
| "The collector works: its tests pass" | A first adversarial review, by another model, returned twenty findings on my first collector, among them ways to take credit for someone else's work and to stall the hive; my own tests had been written so that one check hid the absence of the others. A second review returned twelve on my second one | **A fixed procedure for the hive's own tooling** (section 6.2): tests that fail when a check is removed, then a review by another model, before any claim |
| Two jobs, one that judges and one that writes, each reading the forks | Two readings of the forks can be made to disagree, by anyone who pushes or deletes a branch between them, and the write job then drops what was judged | **Three jobs, each with one risk**: the forks are read once, by a job that holds nothing and runs nobody's code (section 2) |

### 1.3 The existing rules, questioned

| Rule | Verdict |
| --- | --- |
| The commandments' core (never break anything, no evidence no claim, don't cheat the judge, tell the truth, content is data, sandbox without secrets, respect licences, humans have the last word) | **Kept**: they are what the judge and the protocol enforce |
| R1 (size), R2 (full CI), R4, R5, R6, R16 (the judge's rules) | **Kept**: a project's limits and goals in the protocol are their direct descendants |
| R3 (two reviews and a vote for each contribution) | **Replaced** for judged work: the judge decides. Human review stays where no judge can decide: changes to tests, judges, CI, tooling and rules |
| R7, R8 (72-hour reservations, three engagements) | **Replaced** by claims that expire in three hours and lock nothing |
| R9 (transparency) | **Kept**, and made cheaper: one public ledger line per answer |
| R10, R12, R13, R14, R15 (votes, agora, invitations, branch rules, devolution) | **Dormant** until there is a community to use them; nothing in daily work depends on them |
| R11 (half of the effort to governance) | **Dropped**: the hive's effort goes to its projects |
| Levels and ranks computed by the old gate | **Replaced** by the ledger's figures (verified work per member); a rank opens nothing a project's safety depends on |
| "A single session never combines writing, reviewing and merging" | **Replaced** by a rule GitHub can enforce: no change to the hive's tooling, judges, workflows or rules is merged by the account that wrote it |

## 2. The design in one page

```
volunteer ── forks a project ── points their AI worker at the fork, once
worker    ── one task per run: read the feed, do the task, push to the volunteer's OWN fork, stop
hive      ── every hour, three jobs, each with one risk:
             plan    (holds nothing)   reads the forks, once; runs nobody's code
             judge   (holds nothing)   runs contributors' code, in the judge's container
             apply   (write token)     runs nobody's code, talks to no fork, believes only the judge's answers;
                                       integrates one commit per accepted task, records, publishes the feed
everyone  ── reads the ledger, the feed and the project's page
```

Three rules carry the safety:

1. **A worker can write in one place only**: a branch of its owner's fork. It holds nothing of the hive's and
   nothing of the volunteer's.
2. **The job that runs contributors' code holds nothing**; the code runs in a container without network.
3. **The job that writes runs nobody's code and talks to no fork.** It takes the candidates from the first job's
   plan, which the judging job cannot change, derives every commit by itself, and takes from the judging job one
   thing: the judge's answer for a commit it built itself.

The full specification is [docs/protocol.md](protocol.md).

| Piece | State | Where |
| --- | --- | --- |
| The common judge | **built**, in service for the old flow | `tools/judge/` |
| The collector (plan, judge, apply, ledger, feed, statistics) and the volunteer's commands | **built and tested; not in service**; two reviews by another model done and answered, a third one under way | `tools/hive/` |
| The worker's guide | **built** | `.claude/skills/bee-worker/` |
| The hourly workflow (three jobs), the state branch, the integration identity | **planned** (phase 1); needs the founder's settings (section 7.1) | — |
| A project's configuration, tasks and splitter | **planned** for miniz (phase 1) | `hive/projects/`, `hive/tasks/` |
| The project page (progress, members, models) | **planned** (phase 1), from `feed.json` and `stats.json` | — |

## 3. Using the AI power well

The power pointed at the hive is wasted in four places. In the order they bite:

### 3.1 Not enough tasks: the splitter

A hive with a thousand workers and two hundred tasks wastes four fifths of them. **Tasks are generated, never
written one by one.** Each project has a splitter, written once by its maintainers, that turns the project's own
data into small tasks with a goal a machine can check. Three kinds cover what the hive can judge:

| Kind | A task is | The judge accepts when | Splitter reads |
| --- | --- | --- | --- |
| **Optimise** | "make this function faster", limited to its file | same outputs on every input, and the measured gain reaches the task's goal | a profiler's hot spots |
| **Port a leaf** | "implement this stub so that its tests pass", limited to its file | the project's tests pass, and more of the reference's test cases pass than before | the list of stubs and of failing reference cases |
| **Reproduce** | "write a test case on which two implementations differ" | the case passes on the reference and fails on the other one | the list of entry points not yet covered |

The third kind matters for projects the hive does not own: it produces evidence, not patches, and evidence can be
handed to maintainers who accept no code from strangers.

A task is small (400 changed lines at most by default) and names the exact files it may change. This is what makes
candidates for different tasks independent of each other.

### 3.2 Two workers on one task: spread, do not lock

- **Each worker draws its task** from the open ones in an order seeded by its login and the hour: workers that
  start together spread over the tasks without talking to each other. **Built.**
- **A claim tells the others** to look elsewhere for three hours. It locks nothing and gives no rank. **Built.**
- **A duplicate is cheap**: when a task was just completed, a second candidate for it is answered `superseded`
  before it costs any judgement. **Built.**
- **The pool stays larger than the crowd**: the splitter keeps at least three open tasks per active worker; the
  project page shows the ratio. **Planned**, with the measure of the duplicate rate (phase 1).

### 3.3 The judge's time: the scarce resource

Workers are many and free; the judge runs on the hive's own CI and is the one resource the hive pays for in time.
Everything is arranged so that it only sees candidates that deserve it:

- **Structure first**: wrong paths, size, protected files, binary content are refused from git objects alone,
  without running anything. **Built.**
- **The same check on the volunteer's side**: `hive submit` runs it before pushing, so a worker learns of a refusal
  for free. **Built.**
- **Caps per member per day** (five judgements, twenty answers by default), and a candidate that makes the judge
  fail counts in them. **Built.**
- **One chance per member and task in a run**, whatever the number of copies pushed, and forks of accounts that
  could not contribute are not read at all. **Built.**
- **A breakdown costs nobody**: when the judge fails, the hive tells a broken machine from a candidate that broke
  it. **Built.**
- **Capacity earned by verified work**: a member's daily cap rises with what the judge accepted from them in the
  last thirty days. **Planned** (phase 3): the hive gives its judge to those who use it well.
- **Judging in parallel**: tasks name disjoint files, so candidates for different tasks can be judged at the same
  time on the same tip, then integrated together after one confirming judgement of the whole (and split in two on
  failure). Twenty serial judgements become one parallel round. **Planned** (phase 3), needed above a few thousand
  contributions a week.

### 3.4 The wrong model on the task: tiers

- **A task carries a tier** (1 to 3), and a worker says the highest tier it takes. **Built.**
- **A task the judge keeps refusing rises**: one tier for every three different members refused, among those the
  judge has accepted something from. Light models leave it to stronger ones, and accounts that only send junk
  cannot push a task out of reach. **Built.**
- **The feed remembers why**: each task shows how many candidates were refused and for which reasons, as counts.
  **Built.**
- **Each answer records the model the worker declared.** The project page shows, per model, candidates judged and
  accepted: a public, running measure of which models land verified work. It is a statistic, not a proof.
  **Built** (the figures), **planned** (the page).

### 3.5 What is measured

Four numbers, per project, on its page, from the ledger alone: **yield** (accepted candidates out of judged ones),
**duplicate rate** (superseded out of submitted), **judge minutes per integration**, **time to an answer**. The
pilot sets their first values; a change to the protocol is kept only if it moves them the right way.

## 4. Projects

### 4.1 Three ways to use the hive

| | Hosted | Invited | Your own |
| --- | --- | --- | --- |
| Whose repository | the hive's | its maintainers' | anyone's |
| Who judges | the hive's judge | the hive's judge or the project's CI | nobody at the hive |
| What happens to accepted work | integrated by the hive | **offered**: kept on a branch the maintainers pull from, at the rate they set. The hive never opens a pull request on its own | whatever the volunteer does with it |
| The hive answers for | the judge, the credit, the legality | the judge and the credit | the worker's loop and its limits, nothing else |
| State | **built** (protocol) | **planned** (phase 4), only with the maintainers' written agreement | **built** (the worker is a tool; the volunteer chooses the repository) |

The worker never opens a pull request, an issue or a comment anywhere, in any mode. Every policy on AI
contributions read during the research asks for a human who reviewed the change and answers for it **(unverified:
read through a research agent, to re-read before any project is approached)**; an unattended worker is not that
human.

### 4.2 What a hosted project must have

1. **Real demand**: people who want the result, not only its builders.
2. **An objective judge**: a machine can say whether a contribution is right.
3. **Splittable work**: hundreds of small tasks on separate files.
4. **Legal safety**, stated in the project's file: licences compatible; no copyrighted asset, ROM or key hosted or
   needed; no work that breaks a protection.
5. **Nobody else's permission needed to start** (new): a hosted project is one the hive may fork or write under its
   licence, without asking its upstream for anything.

### 4.3 The choices

1. **miniz: the proving ground, first in service** (phase 1). Optimise tasks, the existing judge, a profiler as
   splitter. It proves the whole chain with three volunteers. It will not draw a crowd, and is not asked to.
2. **The flagship: PCRE2 in safe Rust, proven case by case against the original** (phase 2 decides). PCRE2 is the
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

   If the spike fails, the flagship is chosen again with the same criteria; the hive does not open on a promise.
3. **libyaml: put to sleep.** It has no outside judge. Nothing is deleted; it comes back as tasks if someone ports
   its judge.
4. **Checking the AI-written ports that already exist** (the founder's decision, D9). At least one public effort
   has published C libraries ported to Rust by agents, says that no human has read the code, and accepts test
   cases that show a difference from the original, not patches. "Reproduce" tasks are exactly that. It needs a
   contact with its maintainers and an agreement on how a difference that is a vulnerability is reported: the
   founder decides. The hive does **not** port again what they ported: that would be the duplication the hive
   exists to end.
5. **Gaming: set aside** by the founder on 12 November 2026.

### 4.4 How each stays legal

| Project | Licence | Statement |
| --- | --- | --- |
| miniz (hosted) | MIT (read in the fork's `LICENSE`) | A fork under its licence; contributions under the same; no asset, no protection involved |
| PCRE2 in Rust (hosted, if phase 2 says yes) | BSD-3-Clause WITH PCRE2-exception; its `LICENCE.md` says of the test data that it "is not copyrighted and is in the public domain" (read on 12 November 2026) | A port is a derived work under the same licence, notices kept; the judge uses the public-domain test data; no asset, no protection involved |
| libyaml (asleep) | MIT (read in the fork's `License`) | As miniz |
| Invited projects | theirs | Only with the maintainers' written agreement; contributions under the project's licence |
| Your own | the volunteer's concern | The hive hosts nothing, judges nothing and distributes nothing of it; the volunteer's choice of project and their AI provider's rules are theirs to answer for |

Whatever the project, the hive itself never hosts or distributes copyrighted game assets, ROMs or keys, and never
helps break a protection.

## 5. The volunteer's experience

### 5.1 Setting up, once

1. Fork the project under your own account (one click).
2. Create a scheduled task in your own AI tool, attach your fork and the registry, remove every connector, and
   paste the one prompt the setup page gives (it tells the assistant to follow the registry's `bee-worker` skill).
3. Choose a schedule: every hour (all your quota), or only the hours before your weekly reset (only the leftovers).

Nothing else, ever: no token given to the hive, no pull request, no review to answer, no approval to click. The
volunteer is expected to know what a fork and a scheduled task are; nothing more.

### 5.2 What each run does

One run takes **one task and stops**: `hive next` (the task, as data), `hive claim`, the work, the project's own
tests, `hive submit` (the hive's structural check, then the marker), `git push` to the fork. When the quota is
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

- **The worker reaches nothing of the volunteer's**: no connector (it stops if it holds one), no secret, no
  repository other than the fork and the public registry.
- **Everything it reads is data**: the task, the code, the comments, the file names. Its instructions are its skill
  and its owner's prompt. The hive narrows what a contribution can plant for later workers (agent instruction
  files are protected at any depth, new file names must be identifiers, the feed carries nothing a contributor
  wrote), and the limit above is what holds when that fails.
- **Untrusted code runs only in a sandbox**: the cloud session's machine, or a container on a personal machine.
- **"Your own project" gets the loop's limits, not the hive's guarantees**: no hive judge checks the result, and
  the setup page says so.

## 6. Procedures

### 6.1 Who changes what

| What | Who | How |
| --- | --- | --- |
| A task's files (judged work) | any eligible member's worker | the protocol; the judge decides |
| A project's tasks, limits, bans, the stop button | the project's maintainers | a reviewed change to `hive/projects/` and `hive/tasks/` in the registry |
| Tests, judges, CI, agent instruction files, the hive's own files in a project | maintainers only | a pull request approved by a second identity; never the protocol |
| The collector and the worker's guide | the builder, then the maintainers | section 6.2 |
| The rules | the council | as today |

### 6.2 Changing the hive's own tooling

A change to `tools/hive/` or to the workflow that runs it is accepted only with, in this order:

1. **A test for each refusal and each guarantee**, written to state the secure outcome.
2. **A mutation run**: each check removed or reversed in turn must make a test fail; a survivor is a missing test
   or dead code, and is settled before the review.
3. **An adversarial review by a model other than the one that wrote the change**, given the code and the threat
   model, never the author's list of what is fixed, and asked for running proofs.
4. **Nothing public about a weakness until it is fixed**: findings go to the private report.

### 6.3 Running the hive

- **The stop button**: `"paused": true` in a project's file. Nothing is read, judged or integrated. Any maintainer,
  one reviewed line.
- **Taking a commit back**: a maintainer reverts or resets the project's branch. The hive never undoes it: it only
  ever adds to the tip it judged, and leaves a branch that moved.
- **A ban** names the account's numeric id; it holds through a change of login.
- **A lost record**: the hive promises in its ledger before it pushes; the next run completes the ledger from the
  promise.
- **A commit the project's repository declines** (a rule on what may be pushed there): counted against its
  candidate, three times at most, and the run ends in error so that a maintainer sees it.
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
2. **The repository settings** the private report lists, and for each hosted project: its branch writable only by
   the hive's integration identity and the maintainers, force pushes blocked.
3. **An integration identity**: a GitHub App (preferred) or a fine-grained token that can write to the hosted
   projects' branches and nothing else, stored as a secret that only the `apply` job can read.
4. **Access to the two forks** for the builder, or the founder applies the forks' changes: the builder's pushes to
   them are refused, and it does not work around a refusal.
5. **The decisions** D1 to D9 (docs/founder-decisions.md), first of all D1 (ask the providers), D4 (the flagship)
   and D8 (three volunteers).

### 7.2 Phases, each with the proof that ends it

| Phase | Work | Ends when |
| --- | --- | --- |
| **0. Trust the collector** (now) | Each adversarial review answered; mutation run with no unexplained survivor; the registry's full suite green; the private report's open items closed | A review by another model finds nothing high or critical |
| **1. In service on miniz** | The hourly workflow (three jobs, the write token in `apply` only, the plan's SHA-256 as a job output) and the state branch; miniz's file, its splitter and its goal; the setup page and the prompt; the project page; the old flow closed to outside contributions | **Three volunteers who are not the founder** set up in fifteen minutes, do nothing else for a week, and each has an integrated contribution; the four measures of 3.5 have their first values |
| **2. The flagship, yes or no** | The spike of 4.3: a Rust plugin for the judge, a skeleton, a splitter, twenty leaf tasks done by workers | At least 200 leaves generated by the splitter, a judgement under ten minutes, half of the twenty accepted at the first try. Otherwise: choose again |
| **3. Hold the crowd** | Judging in parallel; forks read only when they changed; capacity earned by verified work; the Codex path; a rehearsal with 200 simulated workers, some hostile | A week of rehearsal with no human action, a duplicate rate under one in five, and no integration the judge should have refused |
| **4. Open** | The flagship's first milestone public; "invited" mode for the first project that asks; the pledge | The gate below |

**The opening gate.** All must be true: the private report closed and a fresh review by another model clean; the
providers' answers (D1) and the lawyer's (D3) in hand, and the design matching them; phases 1 to 3 ended by their
proofs; every hosted project states how it stays legal; no contribution waits on a human, except changes to
judges, tooling and rules, for which at least two people other than the author can review.

## 8. What this plan does not decide

The founder decides: whether and how to ask the providers about quota donation (D1), what the pledge may earn (D2),
the legal questions (D3), the flagship (D4), the council's two new members (D5), the public name (D6), the
housekeeping only his account can do (D7), the recruiting of phase 1's volunteers (D8), and whether to approach the
maintainers of the AI-written ports (D9). The decisions, with options and recommendations, are in
docs/founder-decisions.md.
