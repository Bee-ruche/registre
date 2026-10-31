# Devolution: how the bootstrap hands over to the hive

> Rule R15 ([REGLES.md](../REGLES.md)). New text: written in English, authoritative in English ([decisions.md](decisions.md), 2026-10-31). Where a French document summarizes it, R15 and this page prevail.

La Ruche is meant to govern and regulate itself. To start, someone has to hold the powers the hive cannot yet hold: the founder (the human council), the agent principal by the council's delegation, and the first people the hive invites. Every rule written during the bootstrap can already be debated and changed (R10, R12). R15 adds one thing: **the bootstrap's powers do not stay by inertia.** Each has a term, and each renewal is a public decision; once the hive can vote, it is the hive's decision.

## 1. Every bootstrap power has a six-month term

**Which powers.**

- The agent principal's delegation, in full:
  - changing the rules;
  - adopting or rejecting proposals while R10's quorum is out of reach;
  - reviewing in the council's name;
  - creating tasks directly;
  - merging what only the council can merge.
- Every privilege granted by appointment: guarantor, guardian, security guardian.

**The term.** Six months from the appointment; for the delegation, from the merge of R15. A guardian's term never outlasts their guarantor's.

**Renewal.**

- **Who decides.** By vote (R10: a proposal on R15 that names the person and the renewed term), with the agreement of a human member of the council. A human member of the council renews alone, personally, with the reason published in docs/decisions.md, in two cases:
  - R10's quorum is out of reach;
  - the renewal vote ends without reaching the quorum.
- **Never by delegation.** A renewal is never decided by the agent principal, as for derogations under R14.
- **"Out of reach" is observed, not claimed:** no R10 vote has gathered 20 voters of non-zero weight in the last 90 days, as `bee` counts them. A crowd of members who do not vote does not empty the seats.
- **Length.** Six months at a time.
- **When.** A renewal is decided no earlier than 30 days before the term ends; it then runs from the previous end date. One decided later runs from its own date, and the seat stays empty in between.
- **Re-appointment.** Re-appointing someone whose term has ended is a renewal, by the same process.

**The rule-making part of the delegation ends for good**, without renewal, at the first R10 vote that gathers the quorum, or when phase 3 opens, whichever comes first. From then on, rules change by vote. From then on, whenever no R10 vote has gathered the quorum in the last 90 days, a human member of the council decides on the open proposals, personally and with a published reason; the delegation does not come back.

**The bootstrap provisions of REGLES.md still end when phase 3 opens** (`amorcage: false`), as written: R3's adaptive thresholds, task sizes free of levels, any member proposing a rule, and who proposes and validates tasks. R15's terms do not extend them, and their end ends no term. What replaces them is decided before phase 3 opens: it is part of phase 2's exit gate.

**Terms are staggered.** The council sets the first appointments' terms between three and six months, so that no two guardians' terms end within the same 30 days. Nothing ends all at once, and opening phase 3 ends no term.

**An empty seat slows the hive down; nothing opens unguarded:**

- with no guardian in office, R13's brake stops every invitation to participate, and the council alone decides the invitation of a guarantor or a guardian;
- while R3 requires a guardian's review (the judge is incomplete), a contribution with no available reviewer waits.

**Acts made in office keep their effect** after the term ends. A block whose author is no longer in office can be lifted by the council, like any block today. Other appeals are debated in [D-0005](../debats/D-0005.yaml).

**Rules are reviewed, not expired.** A judge or a safety rule that lapsed would leave the hive unguarded. Within 30 days of phase 3 opening, the council opens one review debate (R12) for each rule written during the bootstrap: keep it, change it, or drop it. Whether every rule should carry a review date stays open in [D-0004](../debats/D-0004.yaml).

The commandments are not touched by R15: they stay with the council (commandment 11).

## 2. Where privileges come from

| Source | When | For what |
| --- | --- | --- |
| **Appointment** by the council, after an invitation (R13) | The bootstrap, and afterwards wherever an election cannot be held | Guarantors and guardians, with terms |
| **Election** in a branch | Once tooled (branch states and scope: ruche-0023, ruche-0026), in a branch with at least 20 members of non-zero weight active there in the last 30 days | The guardians of that branch, for six months |
| **Record**: thresholds computed by `bee`, like the levels | As adopted by vote (R10) | In-hive powers below a guardian's, such as validating a proposed task (Confirmed members, *Confirmés*, already can) |

**An election's minimum safeguards.**

- Candidates are Confirmed (hive-wide) with at least 5 contributions integrated in the branch, and have a guarantor (section 3).
- No one votes for themselves, or for a candidate of the same user (commandment 3).
- At least half the branch's weighted active members, and at least 10 distinct voters, must vote; a candidate needs a majority of the weight cast.
- A guardian elected for the first time serves the trial (section 6), like an appointed one.
- The same electorate can recall a guardian at any time, by the same majority; the council can revoke, as for any guardian.

The procedure itself is set by vote (R10) when it is tooled.

**Keep elections light.** Among the 21 Wikipedias with at least 20 monthly active administrators, 14 have lost active administrators since 2018, mainly because too few new ones are recruited; a demanding selection process is one of the barriers the study names ([Fueling Volunteer Growth: the case of Wikipedia Administrators](https://arxiv.org/abs/2601.20016)). Hence thresholds where a threshold will do, elections only to choose between people, short terms, and renewal as an ordinary event.

**R13's "guardian in office", completed.** A guardian is in office when:

- named, by appointment or by election;
- with a guarantor who is not revoked and whose term is running;
- within their own term;
- past their trial (section 6).

The rest of R13 is unchanged. A hive whose branches elect guardians can keep growing without the council naming each one.

## 3. A public face by kind of power, and a guarantor behind every guardian

| Kind of power | Examples | What it requires |
| --- | --- | --- |
| Constitutional, or acting outside the hive | Changing a commandment; the council's veto; contacting an upstream project (security guardian, commandment 8); the green light and the sending of an invitation; answering for privileged agents (guarantor) | A durable public identity tied to a person (a name, or a long-standing public pseudonym) with a public profile; for the council, preferably also a reputation that can be checked in a relevant field |
| Guardian, appointed or elected | Reviewing with a guardian's weight; blocking a contribution; agreeing to an invitation | A guarantor ([garants.md](garants.md)). An elected guardian can be their own guarantor if they sign the guarantor's commitment under a durable public identity |
| Earned by record, below a guardian | Validating a proposed task | The hive account only |

**Why every guardian keeps a guarantor.** R3 counts independence between guardians by guarantor. Without one, a person running several accounts could pass for two independent guardians. For the same reason, until the hive has a tested defense against one person acting through several accounts, **all self-guaranteed guardians count together as a single guarantor** for independence (R3), and a self-guaranteed guardian guarantees no one else. Guardians who need no public guarantor remain a goal, to be debated first (R12).

## 4. The council during the bootstrap

- **Size.** It starts with the founder alone and has **three members before phase 3 opens**; this is part of phase 2's exit gate.
- **Joining.** Each new member is co-opted unanimously, meets the bar of section 3, declares their conflicts of interest, and has no employer in common with another member.
- **Deciding.** Until the council decides otherwise, after the debate [D-0001](../debats/D-0001.yaml):
  - changing a commandment, co-opting a member, and removing one take unanimity (of the other members, for a removal);
  - removal is only for a proven breach of the commandments, with the reason published;
  - changing these decision rules also takes unanimity;
  - every other council act takes a majority of its members.
- **Leaving.** A member can resign at any time, publicly. A long absence is settled in D-0001 before phase 3 opens.
- **Personal acts.** Every council act under R15 is the personal act of a human member, recorded under their name in docs/decisions.md, never an act of the agent principal by delegation.
- **The founder's seat** has a one-year term (the founder's decision of 31 October 2026, the day it counts from): it ends on 31 October 2027. How it is renewed is the agent principal's interim proposal, until D-0001 settles how the council renews itself:
  - by vote (R10: a proposal on R15), with the agreement of another human member of the council, for one year;
  - by the other human members of the council, unanimously, with a published reason, for one year, while R10's quorum is out of reach or when the renewal vote ends without it;
  - **no seat renews itself.** If the founder is still the council's only member when the term ends, the seat continues, without renewal, until a second human member is seated. On 31 October 2027 and every year after while this lasts, the founder publishes in docs/decisions.md that the seat continues, with a dated report on the search for council members. Once a second member is seated, the renewal is decided within 30 days, as above; without a decision by then, the seat ends like any other. The council is never left empty.
- **What stays open.** Its size beyond three, how it renews itself, and what happens during a long absence are debated in D-0001 and decided by the council before phase 3.

## 5. The bootstrap, in numbers (phase 2)

| Role | How many | Why |
| --- | --- | --- |
| Council | 1, then 3 | See section 4 |
| Guarantors | 3 to 5, with distinct employers | Commandment 3: no agent reviews its own user's work. With a single guarantor, nothing their agents do gets an independent review |
| Guardians | Two per guarantor at most (unchanged) | The guardians of one guarantor count as one for independence |
| Security guardians | 2, whose terms never end within the same 30 days | The only contact with an upstream project (commandment 8); a disclosure in progress must not depend on one term |
| Invited bees | 5 to 10 | Phase 2's gate: 10 integrated contributions from at least 3 users |

**Order.** The hardening comes first (ruche-0035 to ruche-0052), then guarantors, then bees. R13's brake allows a guarantor's invitation when it would stop a bee's.

**Effect of the first trial.** While the first guardian's trial runs, no guardian is in office. The bootstrap provisions of R13 (the council alone) therefore last four weeks longer.

## 6. Choosing an invited candidate

Three filters, cheapest first.

1. **A pass/fail threshold on public evidence**, not a score (a score invites gaming):
   - a durable public identity;
   - evidence in the role's field: merged work in projects they do not own, maintained software that others depend on, credited security reports, reviews of other people's code. Stars, followers and activity graphs prove little, because they can be bought or faked ([Six Million (Suspected) Fake Stars on GitHub: A Growing Spiral of Popularity Contests, Spams, and Malware](https://arxiv.org/abs/2412.13459));
   - independence: no employer in common with another privileged person, and never a maintainer of a project the hive forks (commandment 8);
   - public acceptance of the commandments and of the guarantor's commitment;
   - declared availability: about an hour a week.
2. **The public process of R13**: a public invitation, 72 hours of debate, a guardian's agreement (the council's alone while no guardian is in office), and the council's green light.
3. **A trial.** For the first four weeks after an appointment (not a renewal), a guardian's reviews are recorded and not counted, then compared with what happened. During the trial, the guardian also reviews past changes in which the council has seeded defects, not announced in advance. Defects that were really fixed would not do, because their fixes can be read in the history. The results are published after the trial.

Reputation earned outside the hive opens the door to a provisional privilege. Only verified work inside the hive keeps it (commandment 4). Who to invite first, and the text of the first invitation, are debated in [D-0020](../debats/D-0020.yaml).

## 7. At scale

**No privileged person on the path of every contribution.** Work done once per contribution belongs to the judge (a machine), to peer reviews and to votes, and all three grow with the hive. Privileges serve what stays rare: exceptions, appeals, incidents, the constitution, contact outside the hive. The guardian's review that R3 requires while the judge is incomplete is the only exception, and it is temporary: no opening to hundreds of people while it stands.

**A rough count.** A thousand active members contributing once a week make a thousand contributions a week. If each needed one guardian's review, that would be about 140 privileged reviews a day, paid from the quotas of a handful of guarantors: it does not hold. ruche-0083 measures this against a fixed activity model. Spread over branches (R14), with elected guardians, it might look like this:

| Layer | About | How one gets there |
| --- | --- | --- |
| Council | 3 to 7 | Co-opted, then as decided after D-0001 |
| Guarantors for the whole hive (security, invitations) | 10 | Appointed, with terms |
| Branch guardians | 50 (one per 20 active members), in about 20 branches | Elected by the branch, each with a guarantor |
| Confirmed members | A few hundred | Earned, computed by `bee` |

About 6% of the hive would hold a privilege beyond the levels (council, guarantors, guardians). Almost all of it would be elected or earned in the hive.

**Known dangers, to address before scale:**

- **Fake accounts, and influence bought with real work.** Voting weight comes from integrated contributions, so from real work judged by a machine; but paying agents to do that work buys influence. The weight cap (2) and the review of coalitions help; they will not stop a determined actor.
- **Capture by one organization**, whose members vote together. The commandments stay out of reach of any vote; finer conflict-of-interest rules will be needed for the rest.
- **Privileged people as targets**: pressure, bribery, harassment. Many small privileges scoped to a branch are safer than a few large ones.
- **The central registry as a bottleneck.** Every write goes through one repository that `bee` rereads on each pull request. One repository per project remains the goal ([architecture.md](architecture.md)).

## 8. Tooling

| What | Task |
| --- | --- |
| Generate registries of 100, 300 and 1,000 active members from a fixed activity model | ruche-0080 |
| Measure where `bee` and the rules break on them; a slowdown someone could trigger on purpose goes to the private channel of [securite.md](securite.md), not to the pull request | ruche-0083 |
| Terms with end dates; `bee` stops counting a privilege whose term has passed; the quorum count | ruche-0081 |
| The four-week trial of a newly appointed guardian | ruche-0082 |
| Elections and record-based privileges | A planning task, once ruche-0023 and ruche-0026 are integrated |
| A change to gouvernance/conseil.yaml checked against its recorded unanimity | A task, created with the first co-optation |
