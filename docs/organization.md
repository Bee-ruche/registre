# How the hive is run: the roles, the rhythm, the handovers

This page is for the agent sessions that run the hive in the council's name, and for anyone who wants to know how
it is run. It does not concern participants: their way in is [AGENTS.md](../AGENTS.md).

It starts from an observation made on 30 October 2026, at the founder's request. A single person and a single account
(bidji29) run everything. The agent principal writes the rules, has the code written, has it reviewed by agents of
its own model, and merges. The independence of reviews then comes from the method, not from the account or the model.
So nothing safeguards the hive better than separate roles, each in its own session, with a written brief, and
a memory kept in documents rather than in a session.

## The roles

| Role | Brief | What it does | What it never does |
| --- | --- | --- | --- |
| Architect (the agent principal) | [agent-principal.md](../governance/briefs/agent-principal.md) | It keeps the rules and the decisions, sorts and splits the tasks, writes the builders' brief, chooses the reviewers and merges what falls to the council | Write the code it merges; review its own work; carry out a project task |
| Builder | [builder.md](../governance/briefs/builder.md) | It carries out a hive tooling task: a branch, tests, a report | Merge; go outside its task's scope |
| Adversarial reviewer | [adversarial-reviewer.md](../governance/briefs/adversarial-reviewer.md) | It attacks a branch before its merge, then checks the fixes | Fix things itself; review what it wrote |
| Council bee | [council-bee.md](../governance/briefs/council-bee.md) | It carries out project tasks (miniz, libyaml…) under the council's account, through a participant's path | Review, vote, measure for R4, release someone else's task or create tasks: under this account, these are council acts; touch the rules |
| Guardian | [docs/guardians.md](guardians.md); scheduled task | It reviews on evidence, validates proposed tasks and watches the registry's health | Merge; review a contribution of its own user (commandment 3) |
| Dress rehearsal | [dress-rehearsal.md](../governance/briefs/dress-rehearsal.md) | It plays a simulated hive, finds what breaks and turns it into tasks | Change the real registry |

A single session never combines writing, reviewing and merging the same thing.

- **Bees kept apart.** A bee receives only its brief, never what the architect knows: it lives through what a real
  participant will live through, and that is the best test of the guide. The best is a session opened by the founder;
  failing that, the architect launches the bee with its brief alone.
- **Mixed models.** When possible, an adversarial reviewer is not of the same model as the builder
  it reviews. Bees can run on lighter models: the hive learns what each one does
  reliably ([capabilities.md](capabilities.md)).

## The rhythm (the weekly quota resets on Saturday at 6 a.m., Paris time)

- **Every day**: the guardian, as a scheduled task and in a short session.
- **During the week, once or twice**: an architect session, preferably with the founder for what falls to the
  council.
- **From Friday evening to Saturday 6 a.m.: la Nuit des abeilles.** It is the quota that would be lost at the reset.
  The architect opens the night (tasks chosen, briefs). The bees and the builders work, the reviewers
  attack. The architect merges what falls to the council and has passed its review; project contributions are
  integrated only by the integration workflow (R3). At most three agents run the full test suite at the same time:
  the machine has only two cores, and a suite takes 30 to 40 minutes.
- **Every two weeks, or after a large change of rules**: a dress rehearsal.

## The handovers

- **At the start of a session:** the brief of its role, then the project's state. In the registry, `bee swarm`,
  `bee list --status in_review` and docs/decisions.md are enough to start. The council also keeps, outside the
  registry, a state of what is pending and of what falls to the founder.
- **At the end of a session:** what is done, what is pending and the errors made, written in the project's state; and
  one line in docs/decisions.md for each decision.
- **A task always goes through a branch and a report.** Nothing stays "in someone's head".

## Sizes and safeguards

- **A hive tooling task aims at 200 lines outside tests, and never more than its size allows (R1).**
  Beyond that, it is split before it is started. The lesson comes from ruche-0020: 1,900 lines, four review rounds.
- **Before publishing tasks or council data:** `bee check-pr --base origin/main --head HEAD
  --author <council>` locally. The lesson comes from the broken numbering of 30 October.
- **Anything that touches the registry's security goes through an independent adversarial review** (PR verification,
  integration, verdicts, judges, outside contacts), then through a check of the fixes. The findings and what became
  of them are summarized in the PR and in the line of docs/decisions.md that records the merge.
- **No power without a condition the tool can check.** The lesson comes from redaction: a council act
  that was tied to nothing. An agent that works under the council's account performs no council act that its role
  does not give it.
- **The agent principal's account.** Since 1 November 2026, the agent principal acts under its own GitHub account,
  `laruche-architect`, declared as an agent account of the founder ([agent-accounts.yaml](../governance/agent-accounts.yaml),
  ruche-0089). The tool counts it as the founder wherever a person counts (caps, R8, votes, reviews,
  commandment 3), without ever making it a second person, but never gives it the council's status: what is
  reserved to the council (its files, its exemptions from caps, a review that weighs like its own), only the council's
  account itself decides. Such a PR from the agent principal always waits for a human.
  An agent account never changes the authority files (commandments, council, agent accounts, guardians, guarantors,
  briefs, this page, docs/guarantors.md, docs/devolution.md): only the council's account does. Being on the council counts as registration: the agent
  account inherits its person's identity, never their status. Before renaming or deleting this account, the
  council withdraws its declaration: a released login can be taken again.
- **The session's limits are reported, not worked around.** A session cannot set
  a label, delete a branch or change a repository's settings.
- **What changes this organization**, or the brief the guarantor gives to the agent principal, is proposed by
  the agent principal and adopted by the founder himself: the agent principal does not merge the rules of its own
  role.

## What remains fragile, and what answers it

- **A single person.** All the agents of the bidji29 account are those of one and the same user: none of their
  reviews is independent (commandment 3), and no one measures elsewhere (R4). R13's invitations (guarantors,
  guardians, participants) and the common judge's ARM64 timer (ruche-0024, ruche-0031) answer it.
- **A single model.** A guardian of another model, under a dedicated account, brings another view of the
  registry's health and of the other members' work. As long as the founder is its guarantor, it remains his agent: it
  does not review bidji29's contributions. For those, another human is needed.
- **The sessions' memory.** This page, the briefs and the project's state answer it.
