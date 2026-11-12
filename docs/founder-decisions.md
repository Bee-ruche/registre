# Decisions for the founder

*12 November 2026. Each decision has its options and a recommendation. Everything that reaches outside the
project (contacts, posts, accounts, terms, money) is the founder's to do or to approve; the builder prepares it and
does nothing outside. Decisions that touch security are in the private check report, not here.*

## D1. Ask the AI providers whether quota donation is allowed

**Why**: the worker uses only first-party tools, signed in by the volunteer, in a "pull" design, which avoids every
explicit prohibition found. But three clauses could still be read against an organised donation effort: Anthropic's
"ordinary, individual usage", the Consumer Terms' "you also may not make your Account available to anyone else",
and the Usage Policy's ban on services that "route requests through consumer subscriptions" (a new version took
effect on 12 November 2026). OpenAI's terms have the same shape (read only through excerpts so far). A hive that
grows on a reading the providers reject would lose its volunteers' accounts overnight.

| Option | For | Against |
| --- | --- | --- |
| **A. Ask before the opening (recommended)**: a short written question to Anthropic (its legal page says to contact sales about authentication questions) and to OpenAI, describing the pull design | A written answer protects every volunteer; the hive's design is the friendliest case they will see | Takes weeks; the answer may be no or vague |
| B. Open, and ask in parallel | Faster | Volunteers carry the risk |
| C. Do not ask | — | The risk falls on volunteers without their knowing |

**Outside action**: the founder sends the question (the builder drafts it on request). Also worth knowing:
Anthropic runs a "Claude for Open Source" program (free plans for maintainers and active contributors), a possible
ally for the hive's most active volunteers.

## D2. The pledge on X

**Why it is a decision**: the founder's idea was to require the pledge for higher ranks. X's Developer Policy (read
in its official documentation source, 12 November 2026) says "Your service shouldn't compensate people to take
actions on X" and forbids "monetary or virtual compensation for any X actions"; a rank given for a post plausibly
falls under it. Whether that policy binds a project that only reads posts through X's public embed endpoint is a
legal question (D3). GitHub's policies separately forbid activity incentivised by rewards, and YouTube's forbid
rewards for engagement. X's live help pages could not be opened from this session; the reading rests on X's
documentation sources and archived snapshots of its rules.

| Option | For | Against |
| --- | --- | --- |
| **A. The pledge earns nothing (recommended)**: a free act of support, shown on an opt-in wall; ranks come from verified work only | Clearly within X's authenticity rules (own words, once, coordinated support for a cause is allowed); no disclosure question; no incentive to fake | Less pull for people who post only for a reward |
| B. A cosmetic mark (a "pledged" badge on the profile), no privilege | Some recognition | Still arguably "virtual compensation"; a lawyer should look first |
| C. Required for a high rank (the original idea) | Strongest push to post | Plausibly against X's Developer Policy; posts tied to a reward would need a disclosure line ("posting this counts toward my standing"); invites fake or bought accounts |

**Recommendation**: A. The pledge's purpose is that followers discover the hive; that works as well when it is
free, and it keeps the hive's promise to inform, never to manipulate (commandment 12). The design is in
docs/plan.md (P4): own words, posted once by hand, never pre-filled, never by an agent, no required hashtag,
verified once by a personal code for the wall, deleted when the post is.

**Outside actions**: none until the opening; then the founder decides whether the hive has its own account on X, and
who speaks for it.

### Drafts (the member may rewrite them)

1. *I'm giving my AI's leftover quota to La Ruche 🐝 Every night my bee works for free software, and a judge checks
   every drop of honey. I promise to use it well: no cheating, no copying, nothing broken. [link]*
2. *My AI has a second job now: it's a bee. 🐝 When I'm not using it, it works for open projects in La Ruche, where
   machines prove every contribution. I pledge to play fair. [link]*
3. *I joined the hive. 🍯 La Ruche turns the AI quota we waste every week into verified work for everyone. I
   promise my bee will tell the truth about what it does. [link]*
4. *Bzz. 🐝 I'm one bee among thousands: my AI gives its spare hours to La Ruche, and every honeycomb is tested
   before it's kept. I'll use the hive well. [link]*

## D3. Questions for a lawyer

To ask before the public opening; the builder is not a lawyer and states its uncertainty.

1. **Quota donation**: how the AI providers' terms (D1) and GitHub's Acceptable Use Policies (which forbid
   "automated excessive bulk activity" incentivised by rewards) apply to a volunteer effort that rewards verified
   work with a rank.
2. **Liability**: does a hive that hands out tasks and records credit keep the protections of a mere host, or does
   it answer for what volunteers' agents produce? Who answers: the founder personally, or a structure (association)?
3. **Matching decompilation**: the hive would host no game file and no target assembly, and a project's own CI
   (holding the original) would judge. Is coordinating volunteers who use their own legal copies, and upstreaming to
   the project, lawful in France and the EU (Software Directive 2009/24, art. 6) and the US?
4. **Original compilers** that some decompilations need: may a volunteer's local worker use one the volunteer
   obtained, and may the hive point to where to obtain it?
5. **GTA VI**: confirm the "refuse" list in docs/plan.md, and whether any tool working on user-supplied files would
   be safe once a PC version exists.
6. **Contributor licensing**: AI-generated contributions under each project's license; whether the hive needs a
   contributor agreement; disclosure of AI authorship, which Anthropic's Usage Policy requires.
7. **The pledge**: whether a rank earned partly by a public post is a "material connection" that the post must
   disclose (US FTC Endorsement Guides; French and EU rules on influence), and how.
8. **Personal data**: storing a member's GitHub login, X handle and post number; a privacy notice; GDPR basis.

## D4. Which game project to approach, and the pitch

**Recommendation**: approach **one** project, whose written policy already accepts AI contributions, as an invited
pilot; never approach a project that bans them. From the check, in this order: Super Mario Sunshine
(`doldecomp/sms`), Super Smash Bros. Melee, Breath of the Wild. Re-read their policies and progress before contact.
Do not approach Ocarina of Time's projects now: the remaining work there is closed to AI, and pushing would harm the
hive's name with exactly the communities it wants to serve.

**Outside action**: the founder sends the pitch, publicly or privately as the project prefers (commandment 8: no
contact without the founder's decision).

### The pitch (a draft for the founder)

> Hello. I run La Ruche, an open hive where people give the AI quota they don't use, and a strict automated judge
> checks every contribution before it counts. I'm writing because your project's guidelines accept AI-assisted
> contributions, and because a lot of AI effort is wasted today: several people's agents work on the same
> functions, and much of it never reaches you.
>
> What we would offer, only if you want it:
>
> - Your task list, generated from your own progress data, with leases so that no function is worked on twice.
> - Volunteers' agents that work on their own machines, with their own copy of the game. The hive never hosts or
>   sees a ROM, an asset or target assembly.
> - Every contribution goes to your repository, under your rules, judged by your CI. Nothing is merged without
>   your acceptance, and there is no competing fork.
> - Caps you set on open pull requests, a named human for every contribution, AI authorship disclosed, and a stop
>   button you control.
>
> What we ask: a written yes, a scope, and one person to tell us what your reviewers can absorb. If the answer is
> no, we won't write again.
>
> — QueenBee, founder of La Ruche

## D5. The council before the opening

**Recommendation**: two more people, chosen by the founder, with public identities and no shared employer (as R15
already requires before phase 3); at least one with open-source maintainer experience, ideally one from a game
preservation community. Until they are seated, every change to judges, tooling and rules needs the founder's own
approval, given by hand, on GitHub.

## D6. The public name

"La Ruche" and "bees" carry the hive's voice and work in the pledge. **Recommendation**: keep "La Ruche" as the
name and "Bee" for the tool; check that no trademark conflicts in the hive's field before the opening (outside
action: a trademark search, by the founder or a lawyer).

## D7. Housekeeping the founder can do in an afternoon

- The paused weekly scheduled task ("Nuit des abeilles Bee") still uses pre-switch French paths and the agent
  principal's role. **Recommendation**: keep it paused, then delete it once the worker of phase 1 exists; its
  successor is each volunteer's own schedule.
- Open PR #174 (applications instead of invitations): its idea fits the new design (people join by themselves);
  the PR itself is out of date. **Recommendation**: close it with a note that the plan carries the idea.
- The repository settings listed in the private check report.
