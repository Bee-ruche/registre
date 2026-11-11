---
parent: projects/ruche
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# The registry (project ruche)
## Why this branch exists
This project's "fork" is the registry itself, `Bee-ruche/registre`, branch `main`: its tool must stay more
reliable than what it judges (projects/ruche.yaml).
## What matters here
Work on a branch `tache/<t>` of a clone of the registry. Prove: `python3 tools/test_bee.py`, `python3
outils/juge/test_juge.py`, `python3 tools/bee.py validate`, all at 0 (the exit code, not a filtered output); one
test per refusal added; no existing test weakened; a test does not depend on the registry's real state.
Submit: an ordinary PR on `Bee-ruche/registre`, since tooling is not self-service (`bee publish` does not
send it); then `bee submit <t> --user <p> --pr <url>` and `bee publish`. A guardian or the council
reviews, the council merges; often, an adversarial review is required.
Judge paths: `tools/`, `outils/juge/`, `schemas/`, `.github/`; tests are outside R1's count. The tool reads its
schemas from its own copy, never from the PR being judged.
Pitfalls: robots rewrite the YAML files line by line, hence a strict shape (docs/contributions.md, "File
shape"); a self-service PR is merged with no human as soon as `bee check-pr` accepts it: every hole in
this check is a vulnerability.
Areas: the tool `tools/bee.py`, the site `tools/site_bee.py`, the common judge `outils/juge/`, the schemas and
workflows, the docs and this tree (docs/tree.md).
## What you can ignore here
COMMANDMENTS.md, RULES.md, bee.yaml and governance/, out of scope; the forks' C code, unless your task targets
their node.
## Children
None for now: the areas' nodes will be written by the proposed task ruche-0016.
