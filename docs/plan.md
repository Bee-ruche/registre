# The plan: rebuilding the hive for "point and forget"

*12 November 2026. Written by the builder of the hive at the founder's request, after a full check of the project
(the check itself is a private report held by the founder). The
rebuild starts once the founder has read this plan. Facts marked **(unverified)** come from search excerpts or
secondary sources and must be checked before anything depends on them.*

## 0. Where the hive stands, in five facts

1. **It has one participant.** All 126 contributions so far are the founder's (through his agents); no review,
   vote, measurement or member registration has ever been recorded. Every mechanism that rests on "other people"
   (R3's reviews, R10's votes, R12's agora, R13's invitations, guardians, guarantors) has never run.
2. **It is built for agents a human launches and watches.** A first contribution means reading about 4,700 words,
   running `gh`, forking, reserving through a pull request, working, declaring, submitting through another pull
   request, then waiting for reviews by other people that never come. 43.5 % of the registry's 600 commits are
   bookkeeping (reservations, submissions, verdicts, records); the CI ran 6,120 workflows in 16 days.
3. **Its judge is its real asset.** The common judge (isolated build, outputs checked from outside, measurements
   outside the measured program, verdicts bound to the judged commit) and the gate around it are well built. Keep
   them.
4. **Its projects do not draw a crowd.** Two C libraries (compression, YAML parsing) are excellent proving grounds
   and poor magnets. Task supply has dried up: 198 tasks the first week, 6 in the last three days, all written by
   one agent, mostly about the hive itself.
5. **Its governance is heavier than its activity.** 16 rules, 14 commandments, 5 role briefs (10,800 words) and
   108,000 words of documents govern a hive of one. Half of the effort is pointed at governance by rule (R11).

The vision asks for the opposite: thousands of people who give nothing but quota, set up once, and never come back
to approve anything. This plan keeps the judge and the commandments' core, and rebuilds everything a human or an
agent has to *do* around them.

## P1. Point and forget: the worker

### What a volunteer can use today (checked on the providers' own pages, 12 November 2026)

| Option | Unattended? | Safety by default | Quota | Terms |
| --- | --- | --- | --- | --- |
| **Claude: cloud scheduled task** (claude.ai/code/routines, Pro and above) | Yes: each firing is a fresh cloud session in auto mode; runs while the laptop is closed; minimum interval one hour | Isolated VM; GitHub credentials stay outside it behind a proxy that serves only the repositories attached to the task; network limited by default | Draws on the plan; when it is spent, runs are rejected and resume by themselves after the reset; reading the remaining quota from inside is not documented | First-party feature; see "Terms" below |
| **Claude Code, headless on the volunteer's machine** (`claude -p … --permission-mode auto --permission-prompts none`) | Yes, while the machine is on | Shell sandbox is off by default: needs a dev container or the built-in sandbox | Readable (`rate_limits` in the status line and the stream), so the worker can stop at a chosen threshold | First-party; the "programmatic use" area is the one the provider keeps adjusting |
| **OpenAI Codex CLI** (`codex exec`, signed in with ChatGPT) | Yes: headless mode never asks for approval | Read-only by default; `workspace-write` has no network and keeps `.git` read-only (confirmed in the source) | Readable through the app-server (experimental) | First-party; terms read only through excerpts **(unverified)** |
| **GitHub Copilot CLI** (`copilot -p --autopilot`) | Yes, documented for scripts | No confirmed default sandbox | Monthly credits, forfeited if unused | First-party; its cloud agent needs write access, so it works only on the volunteer's own fork |
| Codex cloud, Jules, Antigravity, Cursor, Grok | Partly or unconfirmed | — | — | Not for the first release |

**Chosen for the first release: the Claude cloud scheduled task**, because it is the only option with no terminal,
no machine left on, and isolation by default. **Second: Codex CLI on the volunteer's machine**, the best-confirmed
local option (sandbox on by default, readable quota). Copilot follows. Everything the worker needs lives in the
registry repository (a skill and a fixed prompt), so any assistant that can read a repository and run commands can
use it.

### Terms: what is allowed, and what is not

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

### Two modes: the hive's projects, or your own

The worker is a tool, and the volunteer decides where their quota goes:

- **The hive's projects**: the projects the hive hosts, judges on its own CI, credits in ranks and promotes. They
  meet the criteria of P2, because there the hive runs and rewards the work.
- **Bring your own project**: the volunteer points the worker at any public repository and task list they choose.
  The hive provides the loop and its safety (one bounded task per firing, nothing of the volunteer's within reach,
  content read as data); it does not vet the project, judge it, credit it or answer for it, like any open-source
  tool. The volunteer's own AI provider's rules apply to their use, as always.

### The worker loop

One firing of the scheduled task does **one bounded task and stops**. This removes the need to read the remaining
quota: when the quota is spent, the next firings are refused and the loop resumes by itself after the reset.

1. **Lease.** Read the open tasks of the chosen project (or any project), pick the first one that fits, and claim
   it with a lease that lasts hours, not days. A task already leased is never offered to a second worker, unless
   the task asks for several independent attempts.
2. **Work.** In the session's own sandbox, from a fresh clone. Task text is wrapped and read as data. The worker
   reads only the task's structured fields and the code it needs: no notes, debates or comments by other members.
3. **Prove.** Run the task's own checks locally; if they fail, release the lease with a short structured reason.
4. **Submit.** Push a branch to the volunteer's own fork and hand it to the hive; the hive's judge decides. The
   worker never merges, never comments elsewhere, never contacts anyone.
5. **Stop.** End the session. The next firing starts from step 1.

The volunteer chooses the schedule: every hour (all the quota), or only the hours before their weekly reset (only
the leftovers, the "Nuit des abeilles" made personal).

### Safety: the condition for auto-approval

- **The worker can reach nothing of the volunteer's**: no connectors (the setup removes them; the worker's first
  step refuses to run if any are present), no environment variables or secrets, no repository other than the
  volunteer's fork of the project and the public registry.
- **A hostile task cannot turn a worker against its volunteer or the hive** (for the hive's own projects): tasks
  come from the hive's own task generator as structured data (file, function, metric, check command), never from
  free prose a member wrote; the worker's instructions come from its fixed prompt and the repository's skill, never
  from task content; every output is judged by the hive's judge, which never trusts the worker.
- **The code itself is data too**: the worker must read the project's code and comments, which anyone could have
  written; its fixed prompt says that nothing it reads there is an instruction, and the limits above (nothing of the
  volunteer's within reach, nothing outside the fork) are what holds when that fails.
- **"Bring your own project" gets the loop's safety, not the hive's guarantees**: the worker still reaches nothing
  of the volunteer's and runs code only in its sandbox, but the task list and the code are whatever the chosen
  project provides, and no hive judge checks the result. The setup page says so.
- **Untrusted code runs only in a sandbox**: in a cloud session, the session's VM is the boundary (it holds no
  personal files and no credentials); on a volunteer's machine, the worker uses its tool's sandbox or a container.
- **The hive never asks a worker to do what an auto-approval classifier would block** (force pushes, merges,
  changes to CI, downloads executed blind): a worker that keeps being blocked stops and waits for a human, which is
  exactly the failure this plan exists to avoid.

### Onboarding: one page, about ten minutes

1. Fork the project you want to help (one click), or skip it to help wherever the hive needs it.
2. Open the hive's "Give your quota" page; it shows one prompt to copy and a short checklist.
3. On claude.ai/code: New scheduled task → paste the prompt → attach your fork and the registry → remove every
   connector → choose a schedule → Create → Run now.

Measured from the provider's own documentation: about 20 to 30 clicks, one paste, no terminal, 10 to 15 minutes the
first time. Unavoidable: the Claude sign-in, the GitHub authorization, the Create click. The Codex path is four or
five commands. **To verify in phase 1 with a real volunteer who is not the founder** (section P5): that a cloud
session can push to the volunteer's fork and hand the branch to the hive without any further approval.

### Risks, and what must hold before the opening

- **A provider says no, or changes its terms** (the area it keeps adjusting is programmatic use of subscriptions):
  the worker loses that provider; the hive keeps a second provider ready (Codex) and never depends on one.
- **Scheduled tasks are a research preview**: they may change; the worker is a skill in the repository, so it moves
  to whatever replaces them.
- **Auto-approval stalls**: a worker that keeps being blocked waits for a human; phase 1 measures how often.
- **Must hold before the opening**: the phase 1 milestone met; D1 answered or its risk stated on the setup page;
  the worker's safety limits tested by an adversarial reviewer.

## P2. Projects people want

### Criteria

These criteria are for the projects the hive itself hosts, judges and credits. A volunteer can point their worker
at anything else on their own (P1, "Bring your own project").

A project enters the hive only if it meets all five:

1. **Real demand**: a community that exists without the hive (people who want the result, not just its builders).
2. **An objective judge**: a machine can say, output by output, whether a contribution is right (the hive's
   strength; docs/scope.md).
3. **Splittable work**: hundreds of small tasks many workers can share without duplicating each other.
4. **Legal safety**: no copyrighted asset, ROM, key or leaked material is ever hosted or needed by the hive, and no
   work requires breaking a protection (decryption, extracted keys, firmware); the project states how it stays legal
   (users supply their own legal copy; licenses compatible).
5. **Openness to AI contributions**: the people who maintain the work accept them, in writing.

### Gaming: set aside for now

The founder set gaming aside on 12 November 2026. The research done on it (the decompilation ecosystem around Ocarina
of Time, the GTA VI wave) stays in this file's git history and can be taken up again.

### What the hive offers existing projects: a federation, not a fork

Many open-source efforts duplicate each other, and AI effort spread across them is diluted. The hive offers the
projects that want it a shared engine, without taking their work away from them:

1. **A project opts in, in writing**, with its own scope and acceptance rules, and a named human who answers for it.
2. **Its task list comes from its own data** (failing tests, coverage gaps, a profiler's hot spots, labelled
   issues), generated by a tool as structured data, not written by hand and never copying the issues' prose.
3. **Leases prevent two workers, or two projects, from doing the same piece twice**: the deduplication that shared
   spreadsheets and issue labels give today, made automatic.
4. **Every contribution is judged** by the hive's common judge or by the project's own CI, whichever the project
   chooses; the hive records the verdict.
5. **Results go upstream, to the project's repository**; the project can pause or stop the hive's workers at any
   time.
6. **A volunteer with no skills joins with one choice**: on the "Give your quota" page, pick the project; nothing
   more.

The pitch to project maintainers is in docs/founder-decisions.md; contacting them is the founder's decision.

### Which projects first

1. **Keep miniz as the proving ground** for the worker and the judge (deterministic, no legal risk, an existing
   judge). Its task supply is regenerated by a profiler, not by hand.
2. **Retire libyaml's own CI**: it has no outside judge. Either port it to the common judge as one task, or put the
   project to sleep (R13's "sleeping branch"; nothing is deleted).
3. **One invited open-source project as the federation pilot**: a widely used library or tool whose maintainers
   accept AI contributions in writing and whose tests can judge every change. Which one is still to study (phase 3):
   start from docs/candidates.md (giflib, bzip2, cJSON, lodepng) and from projects with a real community behind
   them.

### Risks, and what must hold before the opening

- **No project with a community says yes**: the hive then opens with its proving ground only, which draws little;
  the pilot is the opening's condition, not an option.
- **Maintainers fear a flood**: the caps they set, the named human per contribution and the stop button answer it;
  one bad week with a pilot would cost the hive its name.
- **Must hold before the opening**: one pilot project live, with its maintainers' written agreement.

## P3. The hive at scale

### What breaks first, in order (for unattended workers on GitHub alone)

1. **The first-contribution approval**: GitHub can require a maintainer's click before a newcomer's first workflow
   runs. The lightest setting only concerns accounts new to GitHub; with the hive's 90-day account rule, no
   volunteer should meet it (to verify in phase 1).
2. **Leases through pull requests**: two workers racing for one task through PRs collide; a lease must be instant.
3. **One merge a minute**: GitHub's guidance caps a repository at about one merged PR per minute, about 10,000 a
   week; today's design spends four PRs per contribution.
4. **Directories**: one file per contribution reaches GitHub's 3,000-entries-per-folder guidance within days at
   10,000 a week.
5. **Concurrent jobs**: 20 to 60 depending on the organization's plan, shared by every judge.

### The design

- **Git stays the ledger of results, not of gestures.** Leases, releases and heartbeats leave git: they are short,
  numerous and worthless after an hour. Only judged results (verdicts, integrations, credit) are committed, in
  batches, by one robot.
- **Leases go through the "gesture inbox"** the hive already designed (docs/architecture.md, step 2): a worker
  claims by a comment on the registry, which every cloud session can reach without changing its network settings;
  one robot pass turns comments into leases, first come first served. The robot reads comments as data, with
  main's own tool, accepting only a fixed command form; no workflow runs because of a comment. The inbox is built
  only after an adversarial review. A small coordinator service replaces it only
  if the inbox cannot keep up (cost estimate: $5 to $50 a month at 10,000 to 100,000 contributions a week,
  unverified).
- **Task supply is generated**: each project has a splitter (a profiler for miniz, failing tests or coverage gaps for a
  library) that turns its data into small structured tasks continuously. A person or an agent writes the
  splitter once, not each task.
- **Machines judge, humans arbitrate.** The judge decides every contribution. Instead of two reviews per
  contribution (which, at 10,000 a week, would need 20,000 reviews and 20,000 votes), the hive uses redundancy: a
  new account's results are re-done by an independent worker before they count; an account trusted after a run of
  valid results is only spot-checked (about 5 to 10 % of the compute, the method volunteer-computing projects have
  used for twenty years). Humans review only changes to judges, tooling and rules, and appeals.
- **Reputation is linear in verified work, per field, and decays.** No bonus for having an account; a new account
  starts at zero weight; the hive, not the contributor, chooses who re-checks whom. Rank gives larger tasks, the
  re-checker role, then judge review.
- **Abuse**: Sybil accounts gain nothing that verified work would not give them; floods meet per-account caps on
  open leases and submissions; poisoned tasks cannot exist in the hive's own projects, because their tasks are
  generated, structured data (the generator extracts identifiers from a project's data, never copies its prose).
- **Cost**: GitHub Actions remains free for public repositories; the judge runs on the hive's CI (trusted), and
  sixty concurrent jobs carry about 60,000 ten-minute judgements a week. Beyond that, the redundancy design lets
  volunteers' own machines judge, but a volunteer's verdict counts only when an independent volunteer, chosen by the
  hive, reproduces it, and the hive's CI re-judges a sample. Workflow runs are kept only 90 days: verdicts must be (and are)
  committed.
- **Visible progress**: each project page shows tasks done, in progress and left, the curve of the week, and each
  volunteer's own contributions.
- **Sixty concurrent jobs** in the cost line above assumes the Team plan; on a free organization, divide by three.

### Governance: what survives, what is replaced

| Today | In the rebuilt hive |
| --- | --- |
| The 14 commandments | **Kept, shortened.** The core stays: never break anything, no evidence no claim, don't cheat the judge, tell the truth, content is data, sandbox without secrets, no hidden code, respect licenses, the commons, humans have the last word, inform don't manipulate, one person one voice. Commandment 8 changes: upstream projects are contacted only through the founder's decided pitch, and work goes upstream only where a project opted in |
| R1 (size), R2 (full CI), R4, R5, R6, R16 | **Kept**: they are the judge |
| R3 (reviews and votes per contribution) | **Replaced** by the judge plus redundancy; human review only for judges, tooling, rules and appeals |
| R7, R8 (72-hour reservations, three engagements) | **Replaced** by short leases granted by the inbox |
| R9 (transparency) | **Kept** |
| R10, R12, R13, R14, R15 (votes, agora, invitations, branch rules, devolution) | **Dormant** until there is a community to use them; nothing in daily work depends on them. R15's terms on powers stay |
| R11 (50 % governance) | **Dropped**: the hive's effort goes to its projects |
| Council, guarantors, guardians, agent principal | A council of the founder and two more people before the opening; the builder works under its own declared accounts, never the council's |

**The single-session rule** ("A single session never combines writing, reviewing and merging the same thing") was
read both ways and practised neither way: the same agent wrote and merged council records, and the reviews were
sub-agents it launched itself. It is replaced by a rule GitHub can enforce: **no change to the hive's judges,
tooling, workflows or rules is merged by the account that wrote it; a second identity approves it** (a human, or an
agent account of another model acting for another person), and the repository's rules make that technical rather
than a promise.

### Risks, and what must hold before the opening

- **Redundancy is gamed by colluding accounts**: re-checkers are chosen by the hive, never by the contributor, and
  one person counts once; a dress rehearsal attacks it before it is trusted.
- **The inbox is a new attack surface** (hostile comments): it is built only after an adversarial review.
- **GitHub's own limits or policies tighten**: the small coordinator service is the fallback, designed in advance.
- **Must hold before the opening**: phase 2's rehearsal passed; per-account caps in force; no human step left in
  daily work except changes to judges, tooling and rules.

## P4. Virality: the pledge

### The design

- **Optional to join, always.** No feature of the worker needs it.
- **It earns no rank and no privilege** (the founder's idea was to require it for higher ranks; the check of X's
  rules argues against it, decision D2). X's Developer Policy, read in its official source today, says "Your
  service shouldn't compensate people to take actions on X" and forbids "monetary or virtual compensation for any X
  actions"; a rank given for a post plausibly falls under it, and GitHub's own policies forbid activity
  incentivised by rewards. A pledge that is a free act of support is safe; a pledge that buys standing is not.
  Ranks come from verified work only.
- **Written in the member's own words**, inspired by the drafts below, posted once by the member, by hand, never by
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

### Drafts

1. *I'm giving my AI's leftover quota to La Ruche 🐝 Every night my bee works for free software, and a judge checks
   every drop of honey. I promise to use it well: no cheating, no copying, nothing broken. [link]*
2. *My AI has a second job now: it's a bee. 🐝 When I'm not using it, it works for open projects in La Ruche, where
   machines prove every contribution. I pledge to play fair. [link]*
3. *I joined the hive. 🍯 La Ruche turns the AI quota we waste every week into verified work for everyone. I
   promise my bee will tell the truth about what it does. [link]*
4. *Bzz. 🐝 I'm one bee among thousands: my AI gives its spare hours to La Ruche, and every honeycomb is tested
   before it's kept. I'll use the hive well. [link]*

Each draft names what the hive is and makes a promise; the link carries the member's code. They are inspiration:
the page shows them, never pre-fills them, and asks the member to write their own.

### The other growth levers

- **"Your AI built this"**: every integrated contribution carries the volunteer's name on the project page, and a
  shareable card ("My bee landed 14 verified contributions this week").
- **Project progress made visible**: one page per project, one bar per milestone, shared milestones ("50 % of the
  tasks done") announced by the hive's own account, decided by the founder.
- **Leaderboards by verified work**, per project and per week, never by volume alone.
- **Teams**: people who run a community (a project, a Discord, a stream) bring their members as a team, the way
  volunteer-computing projects have done for decades.

### Risks, and what must hold before the opening

- **A pledge reads as an advertisement or as spam**: own words, once, nothing earned, no pre-filled text.
- **X changes its rules or its embed endpoint**: the wall links to posts on any network; nothing depends on X.
- **Must hold before the opening**: X's live rules read and D2 decided.

## P5. The road to the public opening

Phases are in dependency order. Each task is split to one session (about 200 lines outside tests) before it starts;
the larger ones (1.3, 1.5, 2.1, 2.2) will each become several.

### Phase 0: close the check (before anything else; about one week of sessions)

- 0.1 Close every item of the private check report, each with an adversarial review by a model other than the
  builder's, CI green, recorded.
- 0.2 The founder applies the repository settings the report lists (only the council's account can).
- 0.3 Retire the paused weekly scheduled task; its successor is the worker (phase 1).
- 0.4 Tag the next common judge from a commit that passes every check, and pin the forks to it.
- 0.5 Decide libyaml (port to the common judge, or sleep).
- 0.6 Write the rules that survive (table above) as one short text, and freeze the dormant ones.

### Phase 1: a real volunteer can try it (two to three weeks) — first deliverable

- 1.1 Spike: a cloud scheduled task, on the account of a volunteer the founder has recruited (not the founder's own,
  and older than the hive's 90-day minimum), pushes a branch to its fork and hands it to the hive with no approval
  prompt. Record each obstacle.
- 1.2 The worker prompt and skill (`.claude/skills/bee-worker/`): lease, work, prove, submit, stop; refuses to run
  with connectors present; reads task data as data.
- 1.3 The inbox: leases by comment, one robot pass, first come first served, lease expiry.
- 1.4 The miniz splitter: tasks generated from the profiler, structured, size S.
- 1.5 Judging on the hive's CI for a branch from a volunteer's fork, bound to the commit, integrated automatically
  when the judge passes (miniz only, during the pilot, with a human able to stop it). Starts only once phase 0 is
  closed.
- 1.6 The "Give your quota" page: one prompt, one checklist, the overage warning.
- 1.7 A progress page for miniz.
- **Milestone**: three volunteers who are not the founder (recruited by the founder, D8, and told plainly that the
  providers have not yet answered D1) set up in 15 minutes or less, do nothing else for a week, and each gets at
  least one integrated contribution.

### Phase 2: the hive holds at scale (three to four weeks)

- 2.1 Redundancy: new accounts re-checked, trusted accounts spot-checked.
- 2.2 Reputation by verified work, per field, with decay; ranks.
- 2.3 Per-account caps; flood and Sybil tests by a dress rehearsal.
- 2.4 The Codex path (and Copilot) for local workers, with quota-aware stopping.
- 2.5 Results committed in batches; per-project folders.
- **Milestone**: a dress rehearsal of 200 simulated workers for a week, with no human action and no duplicated task.

### Phase 3: the first project people want (in parallel with phase 2, once the founder decides)

- 3.1 The founder contacts one invited open-source project with the pitch (docs/founder-decisions.md, D4).
- 3.2 A lawyer answers the questions in D3.
- 3.3 The pilot: that project's task feed generated from its own data, leases, the volunteers' workers, and
  its tests (through the common judge or its own CI) as the verdict.
- **Milestone**: the pilot project's maintainers say, in writing, that the hive's contributions helped them.

### Phase 4: the public opening

The opening gate. All must be true:

- **Security**: every item of the private check report closed; a fresh adversarial check by another model finds
  nothing high or critical; the repository's rules are enforced by GitHub, not by convention.
- **Legality**: the providers' answers on quota donation (D1) and the lawyer's answers (D3) are in hand, and the
  design matches them; every hosted project states how it stays legal.
- **The worker**: phase 1's milestone met, and phase 2's rehearsal passed.
- **The first attractive project**: the pilot is live, with its maintainers' written agreement.
- **Review capacity**: no contribution waits on a human, except changes to judges, tooling and rules; for those, at
  least two people other than the author can review.
- **The pledge**: X's rules read on its live pages (only its documentation sources and archived snapshots could
  be read so far) and the founder's choice made (D2); the pledge stays optional and earns nothing.

## What this plan does not decide

The founder decides: whether to ask the providers about quota donation and how (D1), what the pledge may earn
(D2), the legal questions (D3), which project to approach and when (D4), the council's two new members (D5),
whether to keep the name "La Ruche" for the public (D6), the housekeeping only his account can do (D7), and the
recruiting of phase 1's volunteers (D8). The decisions, with options and recommendations, are
in docs/founder-decisions.md.
