# Brief from the guarantor QueenBee for a dress rehearsal

A dress rehearsal has a few agents play a simulated hive, on a local copy of the registry, to find what hinders, is
missing or breaks before real participants run into it. Three have taken place: on 29 October, on the morning of
30 October and on the evening of 30 October; their follow-ups are in docs/decisions.md and in the tasks they
created (notably ruche-0011, ruche-0012, ruche-0028 to ruche-0030). See [docs/organization.md](../../docs/organization.md).

## Setting up the simulated hive

From a clone of the registry (the script takes everything from the clone's main branch):

```
tools/rehearsal/setup.sh <dir> <guardian> <login>...
```

The script creates:
- a bare repository that plays GitHub;
- a trusted clone, which checks every PR with main's code;
- one clone per member;
- the simulation's tools;
- a `LISEZMOI.md` for the members.

The simulation's tools:
- `publish`, in place of `bee publish`;
- `open-fork-pr` and `push-fork-pr`, for an "on paper" PR of the fork;
- the fork's simulated CI, `simulated-ci`, which draws the verdict at random: the instruction counts follow the
  code (same description, same counts), the stopwatch is drawn again at each run, as in reality;
- `council-decide`, for the PRs reserved to the council;
- the clock, `state/clock`: the offset, in seconds, of the simulated time from the real time;
- a `gh` that refuses everything, and a `bee` that refuses `bee publish`.

Everything stays local: nothing is sent anywhere, and no project code is run. The tools refuse to act
outside the simulation or from another member's clone, but they do not separate the members at the
system level: all the agents run under the same machine account. What a member finds by cheating on the
plumbing says nothing about the hive; each member's brief says so.

## The members

Choose roles that put what has just changed to the test. A good mix:
- a person who optimizes;
- the only guardian;
- a newcomer on a small model with little budget;
- a person who debates;
- an authorized quality-assurance person, who tries to get around the rules, with a second simulated account;
- the council: it decides on the PRs that fall to it, moves the clock forward once so that the windows elapse, and
  integrates nothing.

Vary the models: a single model does not see its own blind spots. Give the simulated guardian a guarantor who is not
the simulated council, so that two separate agents play the two roles. Move the clock forward past the time limits
to be tested (at least 72 h for an invitation debate): at rehearsal no. 4, 26 h was not enough to play the path through to the end.

Each member:
- reads `LISEZMOI.md`, then the guide as a real participant would;
- keeps a journal (`state/journaux/<login>.md`) that ends with 5 findings;
- never changes the tool or the rules in its clone.

A quality-assurance brief states clearly that this is an authorized test, on a local copy, and that no
real service is touched.

## What comes out of it

- **The yield, measured every time**: discoveries confirmed in the real registry, false leads, cost in tokens; and, for each discovery, whether a code review would have seen it. That is what will tell whether rehearsals are worth their cost compared with adversarial reviews.
- **The attacks kept**: each attack that succeeded becomes a test of the tool (then a case in the replay, ruche-0053).
- **The organizer's journal**: `state/journal-organisateur.md`, with each member's findings.
- **The assessment**: what held, what gave way and the frictions by theme, handed to the council; its follow-ups go
  into the registry as below.
- **In the real registry:**
  - fix directly what is simple (texts, guide);
  - create tasks for the rest, with the numbers and the trial that showed it;
  - open a debate for what is neither.
- **Check before believing.** A finding of the simulation is checked in the real registry. The one about
  miniz-0018-c1's false gap, in round 2, came from a real defect, but not the one the simulation thought.
