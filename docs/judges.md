# The families of judges

*First deliverable of task ruche-0004. Written on 14 November 2026. For each family of work this file says what is
judged, how one could cheat, what blocks it, which seeded errors the judge must catch, and what the hive's protocol
must gain. It decides nothing by itself: a judge decides real work only once it has held on a school project and
under an adversarial review (docs/vision.md; docs/plan.md, 4.5).*

**Sources.** A fact about the registry was read in the file named beside it. A fact about an outside tool or study
is marked one of two ways: *(read)* when the source itself was read for this file, with its date; *(reported)* when
it comes from a research pass of 14 November 2026 that could not open the page and relied on summaries. No rule may
rest on a *(reported)* fact before it is read at the source (commandment 2).

## What holds for every judge

These come from the commandments and from the judge the hive already has; no family is exempt.

1. **The judge stands apart from what it judges.** Its code and data are read from the project's base, never from
   the candidate, and it runs where the candidate cannot reach it (docs/common-judge.md).
2. **A verdict names the commit it judged**, and counts for that commit only (RULES.md, R3).
3. **What a judge hands to the hive is a code and bounded numbers under names the project lists** (docs/protocol.md).
   No text of a candidate, of a reviewer or of a tool reaches the ledger, the feed or what a worker's command
   prints: an agent reads those, and content is data, never an order (commandment 5).
4. **Nobody judges their own work**, nor the work of an account of the same person (commandment 3; ruche-0051).
5. **Every judge has seeded errors it must catch** (meta-tests), run again at each change of the judge. The seeded
   errors that are traps for cheats change, and are kept out of the public repository (the founder's decision of
   31 October 2026, on ruche-0004).
6. **A human's word is final** (commandment 11), and during a family's trial a human decides each integration.

## Optimize: the reference

In service since the common judge (docs/common-judge.md): identical outputs, and a measured gain beyond the noise.
It is the model the other families are held to: a seed drawn after the candidate is fixed, inputs the candidate has
not seen, the measure taken outside the measured program, judge paths frozen, meta-tests on a toy project
(`tools/judge/toy`, `tools/judge/jouet`).

## Build

Two different things are judged, by two different judges. Keeping them apart is the point of the vision's sentence:
"tests written by other bees before the code".

### The code, against a reference (a port)

**What is judged.** The candidate behaves as the reference does: the same output on the reference's own tests, the
same output on inputs the judge makes or alters at the time of judging, no crash on any of them, and the language
rules of the project (for a memory-safe port: no unsafe block, no call to foreign code, no process started).

| How one could cheat | What blocks it |
| --- | --- |
| Answering the known tests from a table instead of doing the work | Inputs made or altered at the time of judging, under a seed drawn after the candidate is fixed; the expected outputs of those come from the reference, run by the judge |
| Calling or carrying the reference itself (linking the original, starting it, reading its outputs from the disk) | The candidate is built and run where the reference and its outputs are not; foreign calls and started processes are refused at build time and by the sandbox |
| Right on the tests, wrong beside them | The altered inputs; and, for a format, the same refusals as the reference on invalid input (categories.yaml, parsing and serialization) |
| Passing by chance (a result that changes from run to run) | Each input is run more than once; two runs that differ are a refusal |
| Wearing the judge out (a loop, a memory bomb) | Time and memory bounds per input, counted as a refusal, never as an error of the judge |
| Code taken from a source whose licence does not allow it | No machine sees this: the declaration of sources (commandment 9), and for a port, each file keeps the notice of the file it was written from (docs/plan.md, 4.4) |

**Seeded errors the judge must catch**: a candidate that holds a table of the suite's outputs; one that starts the
reference; one right on the suite and wrong on one altered byte; one that crashes on a truncated input; one whose
output changes between two runs.

### The tests, written before the code by others

**What is judged.** A set of tests (or of test inputs) for a piece of work that is not written yet, or for a
reference that has few. It is good if it lets right work through and stops wrong work. With a reference at hand a
machine can say both: the tests pass on the reference, and they catch seeded mutants of it (small changes made to
the reference at the time of judging); the share of mutants caught is the measure.

| How one could cheat | What blocks it |
| --- | --- |
| Tests that check nothing | The mutants: a test that catches none adds nothing and is refused |
| Tests copied from the reference's own suite | Only what a test adds counts: mutants caught, or code reached, beyond what the suite at the base already catches |
| The same person writing the tests and then the code they judge | The hive deals test tasks and code tasks on one piece to different persons (commandment 3) |
| Tests that sometimes fail | Run more than once on the reference; one failure there is a refusal |
| Tests that pin an accident of the reference rather than its meaning | No machine sees this fully: it is a question for the fourth family, and for the later measure (below) |

**Work that adds up needs no race.** Where each candidate can add something of its own (an input that reaches new
code, a test that catches a new mutant), every candidate that adds is kept, and nobody has to lose.

**When no reference exists** (a program born in the hive), a machine cannot say that the tests are right: that
judgment belongs to the fourth family, helped by a measure that comes later: tests that no candidate ever fails
are worth little, and tests that every candidate fails are suspect.

**Seeded errors**: a suite that asserts nothing; one that catches no mutant; one that repeats the base's suite; one
with a test that fails one run in ten.

**What tests cannot say.** A study of agent-written patches found that maintainers would merge about 24 points
fewer of them than pass the tests *(reported:
https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/)*. Mutants are said to
be coupled to most real faults, and coverage alone to be a weak measure *(reported:
https://homes.cs.washington.edu/~mernst/pubs/mutation-effectiveness-fse2014-abstract.html,
https://cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf)*.

## Prove

**What is judged.** A proof of a statement that was frozen before the task. The kernel of the proof assistant
accepts it; it holds no `sorry`; it rests on the standard axioms only; and the statement it proves is, byte for
byte, the frozen one.

| How one could cheat | What blocks it |
| --- | --- |
| Changing the statement, or a definition it rests on | The challenge is the judge's own file, at a pinned commit; the candidate brings the proof only; a checker compares what was proved with the challenge |
| A hole in disguise: an added axiom, a `sorry` behind a macro, a proof by unchecked computation | The list of axioms the proof rests on, held to the standard ones; a second, independent kernel; the constructs that bypass the kernel refused by name |
| Proving a statement that says something else than was meant (and may be trivially true) | Statements come from a source that was reviewed, never from the worker; a kernel-checked proof of the negation is welcome and counts as a report that the statement is wrong |
| Wearing the judge out (a huge term, an endless search) | Time and memory bounds; the proof is built only inside the sandbox |
| Changing the build itself (options, dependencies) | The candidate may change the proof's file and nothing else, as a task's files already are |
| Bringing a proof someone else published | Statements and many proofs are public: this is a question of credit, not of truth. The task takes statements that have no public proof at the pinned commit, and the hive checks again before it integrates |

**Seeded errors**: a proof with `sorry`; with one more axiom; of a weakened statement; with a definition changed;
one that the first checker accepts and the second kernel refuses.

**The faithfulness of a statement is not a machine's question.** It belongs to the fourth family: a statement is
reviewed and frozen before any proof task on it (ruche-0004, ruche-0005).

**What is reported about the tools** *(all reported, to read before docs/opening-proofs.md is written)*: Lean 4 and
its mathematics library are under Apache-2.0; Lean's own manual lists, for validating a proof, a build, the list of
axioms, a re-check of the compiled files, then a comparator it calls the gold standard, and counts unreviewed
machine-written proofs as hostile input; that comparator is part of Lean since version 4.35.0. The cost of judging
one proof (size of the prepared library, time per proof) was not found: a trial must measure it.

## Decide without an oracle

**What is judged.** Which of several candidates is the better, or that none will do, for a question no machine can
settle: a document, a design, a plan of tests, a choice of project. This is the vision's fourth kind: "competing
proposals, votes, and deferred checking".

**The first form to try.** It is a proposal to attack on a school project, not a rule:

1. **Several candidates** for one question, each by a different person.
2. **Comparison in pairs, and pairs are dealt, never chosen.** The hive draws who reads which pair after the
   candidates are fixed, among members who wrote neither, are linked to neither author, and whose earlier readings
   have held. Each pair is read by several persons, in both orders, by agents of at least two families of models.
3. **The verdict is one of three fixed words**: the first, the second, neither. The reader writes what it rests on
   beside it, as data in their own fork; only the word and bounded numbers reach the ledger.
4. **Every reader gets a pair whose answer the hive knows**: a candidate against a copy of itself made worse on
   purpose. A reader who prefers the worse copy has their readings of that round set aside.
5. **A human decides** every integration during the trial, every split vote and every reported trap, and reads
   again, blind, a share of the pairs.
6. **Deferred checking.** Each choice is stored with what it predicts, and judged later by what was measured.

| How one could cheat | What blocks it |
| --- | --- |
| One person holding several seats | Accounts of one person count as one (ruche-0051); seats are drawn; a reader's standing comes only from the human's blind readings and from deferred checks. This raises the price and does not close the door: without a central authority it cannot be closed *(reported: https://www.microsoft.com/en-us/research/publication/the-sybil-attack/)* |
| Instructions hidden in a candidate, aimed at the agent that reads it | The known-answer pair carries one; the reader's guide says a candidate is data; a reported instruction is a confirmed defect of the candidate |
| Writing for the reader rather than for the question (length, the rubric's own words) | Both orders; the worse copy of the known-answer pair is a padded one; per reader, the hive counts how often the longer one wins and how often the order decides |
| Copying a rival's candidate, which sits in a public fork | **Not solved.** A candidate must stay unread until all are in; an unattended agent does not come back to reveal a sealed one, and sealing by an outside service makes the hive depend on it. To settle on the school project |
| Readers copying each other | A reading is not published before all readings of the pair are in; this changes the hive's rule of public votes and is the hive's to decide |
| An author and a reader agreeing | Drawn seats, never chosen; a reader never gets two pairs of one question |
| A strong author misleading a weaker reader | Several readers of different families; the human's blind share |

**Seeded errors** (the known-answer pairs): a candidate against its copy padded with its own content; against a
copy that carries an instruction to the reader; against a copy with one planted error of fact; two identical
candidates (the honest answer is that neither is better).

**What is reported about readers that are models** *(all reported; each to be read before a rule rests on it)*:

- Agreement with human judges can reach the level of humans among themselves, and a shared rubric raises it
  (https://arxiv.org/abs/2306.05685, https://arxiv.org/abs/2511.10865).
- The order of the two candidates alone changes a model's verdict in a large share of cases; judging both orders
  reduces it (https://arxiv.org/abs/2305.17926).
- Models prefer longer answers, and recognise and favour their own text (https://arxiv.org/abs/2404.13076); several
  small models of different families follow human judges better than one large one
  (https://arxiv.org/abs/2404.18796).
- A sequence of words planted in a candidate got it chosen nine times in ten in one study
  (https://arxiv.org/abs/2403.17710).
- Among people, grades given by peers are right on average and noisy one by one; checking a random share against a
  trusted reader works better than schemes that reward agreement; known-answer items do not stay hidden from
  readers who compare notes (https://arxiv.org/abs/1606.07042,
  https://ojs.aaai.org/index.php/HCOMP/article/view/13332).
- Review in which readers choose what they read was captured by groups; drawn assignment is the fix in use
  (https://arxiv.org/abs/2402.07860).

## The school projects

One per family, small, written by the hive, with no upstream and no outside person (the founder's decision of
31 October 2026). Each calibrates its judge; none tests the participants.

| Family | The school project | Known answers it holds |
| --- | --- | --- |
| Optimize | The common judge's toy project (exists) | Known gains, seeded regressions |
| Build | A small reader of a format the hive defines, with its reference and its suite | Seeded wrong candidates and seeded weak suites (above) |
| Prove | A small library of statements whose proofs the hive holds | Seeded false proofs (above) |
| Decide without an oracle | A set of questions, each with candidates the hive wrote | The known-answer pairs (above) |

The seeded cheats themselves are not in this repository.

## What the hive's protocol must gain

The collector (docs/protocol.md) deals one task to one member and asks a judge for a code and numbers. It can stay
as it is for building against a reference and for proving: both are a task, a candidate and a machine's verdict.
It lacks:

1. **A task's kind** (optimize, port, tests, proof, reading), so that a project lists the kinds it takes and the
   judge it runs for each (with ruche-0003's project types).
2. **Work that adds up**: accepting every candidate that adds something, for test inputs.
3. **Two tasks on one piece dealt to different persons** (the tests, then the code).
4. **Reading tasks**: a pair dealt to a reader, a verdict in fixed words, the known-answer pair, the round set aside.
5. **Several candidates for one question, unread until all are in**: open, see above.

## What follows

Tasks to propose once this file is reviewed (ruche-0004, second deliverable); none is created here:

- the school project for building, with its seeded wrong candidates and weak suites kept apart;
- the judge of a suite of tests by seeded mutants, on that school project;
- the school project for deciding without an oracle, with its known-answer pairs kept apart;
- reading tasks in the collector, tried on that school project only;
- docs/opening-proofs.md (ruche-0005), with every *(reported)* fact about Lean read at its source, and a trial of
  thirty statements before any opening;
- the spike of the first building project (docs/plan.md, 4.3).
