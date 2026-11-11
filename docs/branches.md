# Privileges and rules per branch

The hive grows by branches: a project, a field, an area, later a daughter hive ([growth.md](growth.md)). Today, a
guardian reviews for the whole hive and a rule holds everywhere. As branches multiply, this becomes wrong in two ways:
- a guardian who knows compression has no reason to be able to block a proof in Lean;
- a rule made to optimize C (R4: a measured gain of 2 %) makes no sense for a branch that proves theorems, and would
  keep it from existing.

This page says how a privilege can have a **scope**, and how a branch can have **local rules**. The rule is R14. What
is done today, what remains to be built into the tools, and what remains to be debated are listed at the end.

## The scope of a privilege

A privilege is exercised over a scope: that of a guardian, of a guarantor, of a Confirmed reviewer, or the right to act
outside the hive (R13). The scope is either **the whole hive** or **a branch**: a node of the tree and everything
below it.

- **By default, the whole hive.** It is the only scope in force today.
- **A privilege is exercised only over what falls entirely within its scope.** A task, a contribution, an invitation
  or a debate that touches several branches needs a privileged member from each of them, or from the whole hive.
- **A task's branch is its node, set when the task is created.** Changing it is an act of the council or of a guardian
  of the whole hive. Otherwise, moving a task to the branch of a lenient guardian would be enough.
- **What protects the whole hive stays with the whole hive**: the common judges and tooling (`tools/`, the workflows,
  the common judge), the invitations to take part (they draw on everyone's supervision, R13), security.
- **The council has no scope.** Its acts hold for the whole hive. Only the council, that is the founder, changes a
  commandment; no branch privilege touches one, even indirectly.

A guarantor answers for the guardians of their scope. A mature branch ([growth.md](growth.md)) thus keeps its own
guardians and guarantors without giving them power over the other branches.

## A branch's rules

A branch may adopt **local rules**. They refine, replace or set aside a rule of the branch above, for what falls
entirely within it, when that rule would keep it from existing or from judging well.
The forks that join the project go further: their upstream project sets its own rules (commandment 8).

**What is never derogated from: the base.**
- The commandments.
- The integrity of judgment:
  - green CI (R2);
  - a verdict checked by the registry, a merge on the judged commit only, a privileged review of any change of judge
    (R3);
  - a guardian's refusal stands until that guardian reviews again;
  - the identical results of an optimization (R16).
- Fairness between members: identity, reservations and engagements (R7, R8), votes and weights (R10, levels).
- The agora and its caps against noise (R12).
- Contacts outside the hive (R13), which the whole hive answers for.
- Devolution (R15): the bootstrap powers expire for the whole hive; a branch does not keep an appointed power past its term.
- R14 itself.

**A derogation asks more than an ordinary rule.** It is a rule proposal (R10) that states:
- the branch concerned and the rule set aside;
- why that rule does not fit, with facts;
- what replaces it: a security or judgment rule is never replaced by nothing;
- its review date, at most six months later. Without renewal, it lapses on that date.

It is debated for at least 14 days in the agora, before the whole hive, not only the branch. It is adopted by three
quarters of the weighted votes of the branch's active members, without opposition from a majority of the votes of the
whole hive, with the agreement of a guardian of the whole hive and that of the council.

**Readability.** An adopted derogation is written in its branch's node, which `bee context` prints to every agent
working there, and in docs/decisions.md. An agent must never have to guess which rule applies to it.

**A contribution that touches several branches** follows, for each rule, the strictest version among the branches it
touches. A derogation is never a way to get through elsewhere what the branch has admitted for itself.

## Why these safeguards

- **Without any possible derogation**, the rules of one branch block the others. R4 is made for optimizing; a branch
  of proofs (ruche-0005), of building or of decision without an oracle (ruche-0003, ruche-0004) would need others.
- **Without a base**, a branch with loose rules becomes a back door: work that would not pass elsewhere is integrated
  there, then passed around. Or a small group takes the branch over and gives itself rules to suit it (capture,
  docs/open-questions.md, question 2).
- **The high threshold, the debate before the whole hive and the council's agreement** make both drifts costly and
  visible. **The review date** keeps an exception from becoming the rule by neglect.

## Today and next

- **During the bootstrap**, no branch scope and no derogation is in force. Any derogation needs the council's explicit
  agreement: the agent principal does not adopt it by delegation, unlike the other rules.
- **Tooling:**
  - the scope of privileges in `bee` (the `scope` field of guardians and guarantors, and the checks of R3, of task
    validation, of the agora and of invitations) is task ruche-0026;
  - local rules read and applied by `bee` are task ruche-0027, which waits for the debate.
- **To debate**: [D-0023](../debates/D-0023.yaml). The list of the base, the thresholds, the length of the review
  period, who votes, how a branch undoes a derogation, and reputation by field (ruche-0006).
