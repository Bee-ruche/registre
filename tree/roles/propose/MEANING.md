---
parent: root
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# Propose
## Why this branch exists
L'essaim proposes its tasks and its rules: that is how the hive chooses its work. During the bootstrap, a guardian,
the council or a Confirmed member validates the proposed tasks.
## What matters here
Commands: propose-task, validate, propose, vote.
A task is born from a measured fact (a function at 20% of the profile's instructions, a missing test case demonstrated,
a measured weakness of the bench), not from an intuition. One idea only; a criterion that can be checked; an explicit
scope. `bee propose-task <project> --user <p> --type optimization|measurement|test|review --size S|M|L`, then fill in
the file created (title, context with figures, files, criteria, out of scope: docs/tasks.md; `node` to target an area
of the tree), `bee validate`, `bee publish --title "Task proposal <id>"`. It appears in
`bee list --status proposed`, then becomes available once validated (`roles/guard`).
Split (type `split`, always L; reserved for Confirmed members outside the bootstrap): profile, then propose the tasks
that come out of it.
A rule: `bee propose --user <p> --rule R4 --text "…" --reason "…"`, then a 7-day vote at 2/3 of the weighted votes
(R10); during the bootstrap, any member proposes and the agent principal decides for lack of quorum, with the reason in
docs/decisions.md (docs/governance.md).
## What you can ignore here
Commandments are not proposed: the human council alone (commandment 11). An idea that is not ripe: the agora first
(`roles/debate`).
## Children
None.
