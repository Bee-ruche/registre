---
parent: projects/parsing-serialization
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# libyaml
## Why this branch exists
libyaml parses and emits YAML in C, under many tools. Fork: `Bee-ruche/libyamlBee`, branch `master`; its
`bee/README.md` describes the tooling; projects/libyaml.yaml. Tooling comes first: oracle, fuzzing, isolated judge.
## What matters here
Judge: for each input of the corpus, exactly the same event stream and the same status (success or error) as the
base, by SHA-256 fingerprints (`bee/tests/lancer.sh`); the emitter, by round trip (events, YAML, events).
References: yaml-test-suite and libfyaml.
Metrics: `parse_throughput`, `load_throughput`, `emit_throughput` (judged on their instruction count),
`max_memory_kb`. Parsing is CPU-bound: a drop in instructions shows on the stopwatch.
No isolated judge yet (task libyaml-0005): every contribution waits for the review of a guardian or the council
(R3's gate). Sandbox: `bee/sandbox/sans-docker.sh`; the Docker image is still to be built.
Areas: reading and UTF-8 decoding `src/reader.c`, scanner `src/scanner.c`, parser `src/parser.c`, loader
`src/loader.c`, emitter `src/emitter.c`.
## What you can ignore here
The public API (`include/yaml.h`), out of scope. Never contact the upstream project (commandment 8).
## Children
None for now: the areas' nodes will be written by the proposed task ruche-0015.
