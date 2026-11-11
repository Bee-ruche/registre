---
parent: root
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# Parsing and serialization
## Why this branch exists
Parsers of text formats read configurations and data all over the web: every byte goes through them.
## What matters here
Proof required: the same tree as the reference on a conformance suite, and the same refusals on invalid inputs
(categories.yaml). A parse error is part of the result: it does not change either.
## What you can ignore here
cJSON, held in reserve for phase 4 (projects/cjson.yaml).
## Children
- `projects/parsing-serialization/libyaml`: libyaml, YAML parser and emitter
