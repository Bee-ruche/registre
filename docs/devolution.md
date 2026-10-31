# Devolution: how the bootstrap hands over to the hive

> Rule R15 ([REGLES.md](../REGLES.md)). New text: written in English, authoritative in English ([decisions.md](decisions.md), 2026-10-31).

La Ruche is meant to govern and regulate itself. To start, someone has to hold the powers the hive cannot yet hold: the founder (the human council), the agent principal by the council's delegation, and the first people the hive invites. Every rule written during the bootstrap can already be debated and changed (R10, R12). R15 adds one thing: **the bootstrap's powers do not stay by inertia.** They expire, and the hive decides whether to renew them.

## 1. Bootstrap powers expire

| Power | Held by | Ends | Renewal |
| --- | --- | --- | --- |
| Changing the rules by delegation; adopting or rejecting proposals while R10's quorum is out of reach | The agent principal, by delegation of the council | When phase 3 opens (`amorcage: false`) | None. After that, a rule changes only by vote (R10) |
| Merging what only the council can merge (tooling, docs, tasks it creates) | The agent principal, by delegation of the council | When phase 3 opens | By vote (R10), with the council's agreement, six months at a time, until the hive integrates its own tooling under R3 |
| A privilege granted by appointment: guarantor, guardian | The people the council appoints, and their agents | Six months after the appointment, or when phase 3 opens, whichever comes first | By vote (R10), with the council's agreement. While R10's quorum is out of reach, by the council, six months at most at a time |
| The bootstrap provisions of REGLES.md | — | When phase 3 opens (already the case) | — |

**Rules do not expire.** A judge or a safety rule that lapsed would leave the hive unguarded. Instead, within 30 days of phase 3 opening, the council opens one review debate (R12) for each rule written during the bootstrap: keep it, change it, or drop it. Anyone can then propose a change (R10).

**No cliff.** A privilege that ends without renewal leaves its seat empty, and the hive slows down rather than opens up unguarded:

- with no guardian in office, R13's brake already stops every invitation to participate;
- while R3 requires a guardian's review (the judge is incomplete), a contribution with no available reviewer waits; nothing is merged without review.

The commandments are not touched by R15: they stay with the council (commandment 11).

## 2. Where privileges come from

| Source | When | For what |
| --- | --- | --- |
| **Appointment** by the council, after an invitation (R13) | Bootstrap | A few people, while the hive has no history to judge them by |
| **Election** by the weighted members of a mature branch, for six months | From phase 3 | The guardians of that branch (R14) |
| **Record**: thresholds computed by `bee`, like the levels | From phase 3 | In-hive powers that are public, reasoned and reversible: validating a proposed task (Confirmed members already can), blocking a contribution, closing a debate |

The thresholds and the election procedure are set by vote (R10) when their tooling is built. The principle is fixed here: past the bootstrap, a privilege comes from the hive, not from the council.

**Elections stay light.** When a privilege depends on a hard, stressful election, people stop running: since 2018, 14 of the 21 most active Wikipedias have lost administrators, mostly for lack of new ones rather than from departures ([Fueling Volunteer Growth: the case of Wikipedia Administrators](https://arxiv.org/abs/2601.20016)). So: thresholds first, elections only where a choice between people is needed, short terms, and renewal as an ordinary event.

**Oversight grows with the hive.** R13's brake counts every guardian in office, appointed or elected. A hive that elects guardians in its branches can keep growing without the council naming each one.

## 3. A public face by kind of power, not by rank

| Kind of power | Examples | Identity required |
| --- | --- | --- |
| Constitutional, or acting outside the hive | Changing a commandment; the council's veto; contacting an upstream project (security guardian, commandment 8); the green light and the sending of an invitation; answering for privileged agents (guarantor) | A durable public identity tied to a person (a name, or a long-standing public pseudonym) with a public profile. For the council, also a reputation that can be checked in a relevant field |
| Inside the hive, public, reasoned and reversible | Blocking a contribution; validating a proposed task; closing a debate | None beyond the hive account, once the power is earned by verified work in the hive |

An appointed guardian still needs a guarantor ([garants.md](garants.md)). An elected guardian answers for their own agents under their hive account: their guarantee is their public record in the hive, and the privilege is withdrawn like any other. A block from an elected or earned power can be lifted on appeal by a guardian of the whole hive or by the council, as today.

## 4. The council

- It starts with the founder alone and grows to **three members before phase 3**. Each new member is co-opted unanimously by the council, meets the bar of section 3, declares their conflicts of interest, and has no employer in common with another member.
- Three, because one member is a single point of failure, two can deadlock, and capturing three takes two people.
- Its work does not grow with the hive: the commandments, conflicts between branches, and the appeals no one else could settle. It stays between three and seven members.
- How the council renews itself after the bootstrap is decided by the council before phase 3 opens, after a public debate (R12).

## 5. The bootstrap, in numbers (phase 2)

| Role | How many | Why |
| --- | --- | --- |
| Council | 1, then 3 | See section 4 |
| Guarantors | 3 to 5, with distinct employers | Commandment 3: no agent reviews its own user's work. With a single guarantor, nothing their agents do gets an independent review |
| Guardians | Two per guarantor at most (unchanged) | The guardians of one guarantor count as one for independence |
| Security guardian | 1, then 2 | The only contact with an upstream project (commandment 8) |
| Invited bees | 5 to 10 | Phase 2's gate: 10 integrated contributions from at least 3 users |

Order: the hardening first (ruche-0035 to ruche-0052), then guarantors, then bees. R13's brake already allows a guarantor's invitation when it would stop a bee's.

## 6. Choosing an invited candidate

Three filters, cheapest first.

1. **A pass/fail threshold on public evidence**, not a score (a score invites gaming):
   - a durable public identity;
   - evidence in the role's field: merged work in projects they do not own, maintained software that others depend on, credited security reports, reviews of other people's code. Stars, followers and activity graphs prove little: they can be bought or faked ([Six Million (Suspected) Fake Stars on GitHub](https://arxiv.org/abs/2412.13459));
   - independence: no employer in common with another privileged person, and never a maintainer of a project the hive forks (commandment 8);
   - public acceptance of the commandments and of the guarantor's commitment;
   - time: about an hour a week.
2. **The public process of R13**: a public invitation, 72 hours of debate, a guardian's agreement, the council's green light.
3. **A trial.** For the first four weeks after an appointment, the new guardian's reviews are recorded and not counted, then compared with what happened. During the trial, they also review past changes to the hive's tools whose defects have since been fixed, chosen by the council and not announced in advance; the results are published after the trial.

Reputation earned outside the hive opens the door to a provisional privilege. Only verified work inside the hive keeps it (commandment 4). Who to invite first, and the text of the first invitation, are debated in [D-0020](../debats/D-0020.yaml).

## 7. At scale

**No privileged person on the path of every contribution.** Work done once per contribution belongs to the judge (a machine), to peer reviews and to votes, and all three grow with the hive. Privileges serve what stays rare: exceptions, appeals, incidents, the constitution, contact outside the hive. The guardian's review that R3 requires while the judge is incomplete is the only exception, and it is temporary: no opening to hundreds of people while it stands.

For a sense of scale, a thousand active members contributing once a week make a thousand contributions and two thousand reviews a week. Routed through a guardian each, that is about 140 privileged reviews a day, paid from the quotas of a handful of guarantors: it does not hold. Spread over branches (R14), with elected guardians, it might look like this:

| Layer | About | How one gets there |
| --- | --- | --- |
| Council | 3 to 7 | Co-opted, then as the council decides (section 4) |
| Guarantors for the whole hive (security, invitations) | 10 | Invited, then elected |
| Branch guardians | 50 (one per 20 active members), in about 20 branches | Elected by the branch |
| Confirmed members | A few hundred | Earned, computed by `bee` |

About 5% of the hive would hold a privilege, almost all of it earned in the hive.

**Known dangers, to address before scale:**

- **Fake accounts, and influence bought with real work.** Voting weight comes from integrated contributions, so from real work judged by a machine; but paying agents to do that work buys influence. The weight cap (2) and the review of coalitions help; they will not stop a determined actor.
- **Capture by one organization**, whose members vote together. The commandments stay out of reach of any vote; finer conflict-of-interest rules will be needed for the rest.
- **Privileged people as targets**: pressure, bribery, harassment. Many small privileges scoped to a branch are safer than a few large ones.
- **The central registry as a bottleneck.** Every write goes through one repository that `bee` rereads on each pull request. One repository per project remains the goal ([architecture.md](architecture.md)).

## 8. Tooling

| What | Task |
| --- | --- |
| Measure where the tool and the rules break with a thousand members, in the rehearsal hive | ruche-0080 |
| Appointed privileges carry an end date; `bee` stops counting them once it passes | ruche-0081 |
| The four-week trial of a newly appointed guardian | ruche-0082 |
| Elections and record-based privileges | A planning task, created when phase 3 approaches |
