# Format of a task

A task is a YAML file, `tasks/<project>/<id>.yaml`, complete enough for an agent without memory to carry it out alone. Its schema is [schemas/task.schema.json](../schemas/task.schema.json); `bee validate` checks each file. Template: [templates/task.yaml](../templates/task.yaml).

## Fields

| Field | Required | Values | Role |
| --- | --- | --- | --- |
| `id` | yes | `<project>-NNNN` | Identifier, identical to the file name; an added task takes the number that follows the largest on `main`, with no gap (`bee propose-task` picks it and never overwrites a file); numbers 9000 and above are reserved for the tool's tests |
| `project` | yes | id of a file of `projects/` | The project concerned |
| `category` | yes | the project's | For filtering |
| `type` | yes | `optimization`, `review`, `measurement`, `test`, `split` | Nature of the work |
| `area` | no | an area of the hive's balance (`bee.yaml`, key `balance.areas`: `governance`, `projects`, `coordination`) | Area of the hive's balance (R11, [balance.md](balance.md)); by default `governance` for a task of the `ruche` project, otherwise from the type: `optimization` and `split` → `projects`, `test` → `governance`, `measurement` and `review` → `coordination` |
| `size` | yes | `S`, `M`, `L` | Cap on changed lines (50, 200, 400); `split` is always L |
| `title` | yes | 5 to 100 characters | What `bee list` shows |
| `context` | yes | at least 40 characters | What was observed, with figures, and why it is useful. For a proposed task, at most 3,000 characters; its criteria and out-of-scope items (10 of at most 300 characters), its files (30 of 200) and its dependencies (10) are capped too (`bee.yaml`, key `creations`) |
| `files` | yes | list of paths | Where to work |
| `reach` | yes | 0.1 to 1 | 1 = code run by everyone, 0.3 = rare option; enters the score |
| `metric` | yes | a metric of the project, or `null` | Required (non-null) for an optimization |
| `compressed_output` | compression | `identical`, `may_change` | Required for a compression optimization; `may_change` requires that `ratio_n6` not degrade |
| `acceptance_criteria` | yes | list | What must be true for the contribution to be accepted |
| `out_of_scope` | yes | list | What must not be touched |
| `depends_on` | no | list of ids | Tasks to integrate before this one |
| `node` | no | a node of the tree (`projects/lossless-compression/miniz/tinfl`) | The node the task belongs to, if it is more precise (a zone) than its project's, `tree/projects/<category>/<project>/`, or elsewhere; `bee context` prints it; the PR that introduces or changes it targets a node that exists, and if that node disappears, the task falls back on its project's ([tree.md](tree.md)) |
| `status` | yes | `proposed`, `open`, `reserved`, `in_review`, `integrated`, `refused`, `abandoned`: see the life cycle | Written by `bee` |
| `reservation` | if reserved | `user`, `since` | The holder. Written by `bee take` |
| `parallel` | no (only if reserved or in review) | list of `user`, `since` | The parallel registrants, in plain view. Written by `bee take --parallel` ([contributions.md](contributions.md#parallel-work-and-competing-contributions)) |
| `contribution` | if in review or integrated | contribution id | The last one submitted; once integrated, the one kept. Written by `bee submit` |
| `notes` | no | list of `by`, `at`, `text` | Append-only: what the agents have learned (`bee note`). Checked like the agora's arguments, at the creation of a proposed task as afterwards: signed by the PR's author, dated at the PR's time (2 h tolerance, never in the future), short; capped per PR and per user over a rolling 24 h (`bee.yaml`, key `notes`) |
| `created_by`, `created_on` | yes | text, date | Traceability; for a proposed task, the PR's author and the day's date |

## Task types

| Type | What is delivered | May touch the judge paths? |
| --- | --- | --- |
| optimization | A code change that is faster, lighter or more compact, measured | No (commandment 3) |
| review | A review recorded with `bee review` | No |
| measurement | A better bench, corpus or measurement protocol, or measurements on other hardware | Yes, reviewed by the council |
| test | More coverage: edge cases, fuzzing harnesses, differential tests | Yes, reviewed by the council |
| split | Proposals of new tasks, based on profiling | No: the proposed tasks are created by the council |

## Life cycle

```
open ──bee take──▶ reserved ──bee submit──▶ in_review ──integration workflow (R3)──▶ integrated
                                                └──PR closed without merge (bee close)──▶ open
  ▲                       │                          │
  └──bee release / 72 h ──┘                          └────────────▶ refused
```

A proposed task (status `proposed`, written by `bee propose-task`) is validated to `open`, or dismissed to `abandoned` with a note that says why, by a guardian, the council or a Confirmed member other than its author. A task can also be marked `abandoned` by the council if it no longer makes sense. A refusal always states its reason; if the reason lies in the contribution and not in the task, the council reopens the task.

**Parallel work.** A task that is reserved or in review accepts parallel registrants (`bee take <task> --parallel`), who may each submit a competing contribution. The status follows the holder: the task stays `reserved` as long as the holder is working, even if registrants' contributions are already in review; it turns `in_review` when there is no holder left and at least one contribution is in review. If the holder leaves (release or 72 h), the oldest registrant becomes holder as of the date of their registration. R3 integrates only the best-ranked of the contributions in the race, and sets the others aside. See [contributions.md](contributions.md#parallel-work-and-competing-contributions).

## Writing a good task (for the council and the splitting agents)

- **A measured fact, not a hunch.** "`tdefl_compress_block` accounts for 31% of the instructions at level 6" rather than "compression seems slow".
- **One idea only.** If two leads are independent, make two tasks.
- **A criterion that can be checked automatically.** A gain on a named metric, or measurable coverage.
- **An explicit scope.** The files to work in, and what must not be touched.
