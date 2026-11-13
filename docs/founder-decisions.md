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

**If a provider says no, or does not answer**: a "no" removes that provider from the worker (the hive never runs
against a provider's stated wish); silence after a month leaves the founder two choices: open with the risk stated
plainly on the setup page, so that each volunteer decides for their own account, or wait. Recommendation: wait for
at least one written answer before the public opening, and open with that provider first.

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
docs/plan.md (section 6.5): own words, posted once by hand, never pre-filled, never by an agent, no required hashtag,
verified once by a personal code for the wall, deleted when the post is.

**Outside actions**: none until the opening; then the founder decides whether the hive has its own account on X, and
who speaks for it.

### Examples of tone (never posted as they are: each member writes their own)

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
   And in "bring your own project" mode, where the hive only provides the worker and the volunteer chooses the
   project: does the hive's exposure really end where the volunteer's choice begins?
3. **Contributor licensing**: AI-generated contributions under each project's license; whether the hive needs a
   contributor agreement; disclosure of AI authorship, which Anthropic's Usage Policy requires.
4. **The pledge**: whether a rank earned partly by a public post is a "material connection" that the post must
   disclose (US FTC Endorsement Guides; French and EU rules on influence), and how.
5. **Personal data**: storing a member's GitHub login, X handle and post number; a privacy notice; GDPR basis.

## D4. The flagship, and the projects to invite

**Why it changed**: the first plan made the opening depend on an invited project's yes. The engineering plan
(docs/plan.md, 4.3) puts first a flagship the hive can start alone, and invitations second.

**Recommendation for the flagship**: **PCRE2 in safe Rust, proven case by case against the original**, decided
only after phase 2's spike answers three questions (can the common judge judge Rust; does the work split into
several hundred leaves; what a judgement costs). It needs nobody's permission: the hive writes a new work under
PCRE2's licence, and the test data is in the public domain. Options: (a) accept this candidate and let the spike
decide, recommended; (b) name another candidate that meets the five criteria of the plan's 4.2; (c) open with miniz
alone, which draws little.

**Recommendation for invitations**: wait until phase 1 works, then answer the projects that ask, and approach at
most one. Never approach a project whose written policy refuses AI contributions. Do not use docs/candidates.md
(giflib, bzip2, cJSON, lodepng) as a list of libraries to port: several are among those an existing public effort
has already ported with agents (D9). Gaming is set aside (decision of 12 November 2026).

**Outside action**: the founder sends the pitch, publicly or privately as the project prefers (commandment 8: no
contact without the founder's decision).

### The pitch (a draft for the founder)

> Hello. I run La Ruche, an open hive where people give the AI quota they don't use, and a strict automated judge
> checks every contribution before it counts. I'm writing because your project's guidelines accept AI-assisted
> contributions, and because a lot of AI effort is wasted today: several people's agents work on the same
> problems, and much of it never reaches you.
>
> What we would offer, only if you want it:
>
> - A task list generated from your own data (failing tests, coverage gaps, hot spots), as small tasks on separate
>   files.
> - Every contribution judged by your tests before you ever see it. What passes is kept on a branch you can pull
>   from, at the rate you choose. We never open a pull request, an issue or a comment on your repository unless you
>   ask for it, and there is no competing fork.
> - AI authorship disclosed, the contributor's GitHub identity on every commit, and a stop button you control.
>
> What we ask: a written yes, a scope, and one person to tell us what your reviewers can absorb. If the answer is
> no, we won't write again.
>
> — QueenBee, founder of La Ruche

## D5. The council before the opening

**Recommendation**: two more people, chosen by the founder, with public identities and no shared employer (as R15
already requires before phase 3); at least one with open-source maintainer experience. Until they are seated,
every change to judges, tooling and rules needs the founder's own approval, given by hand, on GitHub.

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

## D8. Recruit phase 1's volunteers

Phase 1's milestone needs three volunteers who are not the founder, each with a Claude plan and a GitHub account
older than 90 days, willing to run the worker for a week on miniz. **Recommendation**: people the founder knows
personally, told plainly what the worker does and that the providers have not yet answered D1. Outside action:
the founder asks them; the hive sends no invitation by itself (commandment 13).

## D9. Offer to check the AI-written ports that already exist

**Why it is a decision**: at least one public effort has ported C libraries to Rust with agents (cJSON, giflib,
bzip2 and libyaml among them), states that no human has read the generated code, and says it accepts test cases
that show a difference from the original, not patches. The hive's "reproduce" tasks (docs/plan.md, 3.1) produce
exactly that, and porting those libraries again would be the duplication the hive exists to end. But it means
contacting its maintainers, whose process for outside submissions is not written, and agreeing first on how a
difference that is a vulnerability gets reported.

**Options**: (a) the founder writes to them once phase 1 works, with the question "would test cases from the
hive's workers help you, and how should a security-relevant one reach you?", recommended; (b) not now.

**Outside action**: the founder's message. The builder contacts nobody.

## D10. What only the founder's account can set up

The engineering plan lists it once (docs/plan.md, 7.1): the pull request to `main`, the repository settings, the
integration identity, access to the two forks, and phase 1's three volunteers (D8). Nothing goes into service
before these, and the builder does none of them.

The integration identity is two rights, kept apart: the right to write a project's branch, given to the `apply` job
alone; and the right to write the hive's state, a repository of its own (`Bee-ruche/hive-state`, the founder's choice of 13 November: the jobs that write the state then hold no right on the registry), given to the `record` and `apply` jobs. The `plan`
and `judge` jobs hold nothing.

Two settings go with the keys (docs/hive-workflow.md, "The settings only the founder can make"):

- **Both environments (`hive-state`, `hive-apply`) accept the branch `main` only** ("Deployment branches and tags":
  selected branches, the one rule `main`, no tag rule). An environment hands its secrets to any job that names it,
  on any ref it accepts: this setting is what decides who can read a key. To make before the keys are entered,
  or right after.
- **Which version of the hive a run uses** is a choice still open: the commit of `main` that started the run (the
  draft, as written), or one commit named in the workflow file and changed only by a pull request a person
  reviewed (stricter: the hive's code, settings and tasks then change when a person says so). The builder
  recommends the second for the pilot.
