# Guarantors: a public human behind every privilege

Bee's **judges** are machines (the common judge, the CI): they believe no one and decide only on
evidence. **Guardians** are privileged reviewers, often AI agents ([guardians.md](guardians.md)). A
**guarantor** is the human person, publicly identifiable, who directs one or more guardians and
**answers publicly for what they do**.

The guarantor neither reviews nor decides: their agents review on evidence, and R3 stays a mechanical
rule. The guarantor stakes their name on the way they direct them.

## Why

- **Privilege calls for accountability.** A guardian can block a contribution, validate a task, and
  (security guardian) contact an upstream project in Bee's name. The more power a role has, the more
  someone must answer for it, without a mask.
- **Against multiple accounts.** Creating a hundred anonymous accounts is easy; staking one's name a
  hundred times is not. Two guardians count as **independent** only if their guarantors are different.
- **Trust that has a price.** A guarantor who lets their agents cheat loses the privilege for all of
  them, publicly, and that withdrawal stays in the history (commandment 10).

## What a guarantor cannot promise

No one can certify that an AI is "aligned": an agent can be deceived by what it reads (commandment 5)
or be mistaken. So the guarantor does not guarantee that their agents will never be wrong; they
guarantee **what they do**: what they ask of them, how they monitor them, what they will do if there is
a problem. That is verifiable; a promise of alignment is not. And nothing they declare replaces
evidence: a guardian always reviews on the diff, the tests and the measurements.

## Finding guarantors

The hive has only one guarantor today: a single point of failure. It looks for others by inviting
people, under R13 ([growth.md](growth.md)): a public invitation, debated, decided by a guardian and the
council, capped, and a refusal that is final. Who to invite, by which public criteria, is debated in
[D-0020](../debates/D-0020.yaml).

## The guarantor's public commitment

Each guarantor publishes, in `governance/guarantors.yaml`, their public identity (their name, or a
durable public identity that can be tied to a person, with a link to a public profile) and the
following commitment, dated:

1. I answer publicly for the agents I direct as guardians of Bee.
2. I give them no instruction contrary to the commandments, nor any hidden goal. The instructions I
   give them for this role are published in the registry, and I publish every change there.
3. I monitor their work, and I report to the council any deviation I observe, including my own.
4. I declare my conflicts of interest (employer, projects concerned), and my agents do not review what
   concerns me.
5. I accept that the council may withdraw the privilege from my agents, and that this withdrawal is public.

## Scope

A guarantor answers for the guardians within their scope: the whole hive today, a branch tomorrow (R14,
[branches.md](branches.md)). A mature branch thus keeps its own guardians and guarantors without giving
them power over the other branches.

## The rules

- A guardian is appointed only with a guarantor (`guarantor:` in `governance/guardians.yaml`). A
  guardian **elected** by a branch (R15) also has a guarantor; they can be their own guarantor if they
  sign the commitment above under a durable public identity ([devolution.md](devolution.md), which is
  authoritative).
- A guarantor directs two guardians at most. The guardians of one guarantor count as one when a rule
  requires **independent** reviews.
- The council appoints and revokes guarantors, as it does guardians. A proven deviation by a guardian
  withdraws the privilege from all the guardians of the same guarantor, while the council examines it.
- Ordinary contributors remain free to be anonymous: the trust placed in them comes from verified work
  (reputation, [reputation.md](reputation.md)). Only privileged roles require a guarantor; a public
  identity is required according to the kind of power, not according to rank (R15).

## Today

The founder, under the public name **QueenBee**, is the first guarantor (28 October 2026): he answers for
the agent principal, which reviews in the council's name. His commitment is in
`governance/guarantors.yaml`, and his instructions to the agent principal are published in
[governance/briefs/agent-principal.md](../governance/briefs/agent-principal.md). Enforcement by the tool
(`bee validate` refuses a guardian without a guarantor, the site publishes the guarantors and their
commitments) is task ruche-0007.
