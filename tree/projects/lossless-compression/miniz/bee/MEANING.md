---
parent: projects/lossless-compression/miniz
updated_on: "2026-11-11"
maintained_by: ruche-0014
line_budget: 40
---
# The fork's tooling: bee/
## Why this branch exists
`bee/` judges each contribution: corpus, differential and API tests, fuzzing, A/B bench, profiler, isolated judge, CI.
These are judge paths: only `test` and `measurement` tasks touch them, reviewed by a guardian, the council or a
Confirmed member (R3, roles/measure).
## What matters here
Preserve current correctness: `bee/tests/empreintes-reference.txt` holds 488 fingerprints (8 levels × 61 files, at
9977da4) and is regenerated only on the base, never on a candidate (miniz-0023, miniz-0024).
Measured coverage (gcc --coverage): miniz_tdef.c 77.8% of lines and 70.2% of branches, the strategies other than the
default one being exercised only by fuzzing (miniz-0023, before miniz-0024); miniz.c 94.4% of branches since miniz-0026.
The `flux-1` check does not exercise tinfl's fast path (area `inflate`).
Duration: `bee/tests/lancer.sh` under 30 s on the CI (criterion of miniz-0023 and miniz-0024); with `--sanitiseurs`,
34.6 s before `api.c`, which adds about 5 s (miniz-0026's manifest, shared machine).
Stopwatch noise: ab.py's A/A test, from −1.4% to +0.5% (bee/README.md: virtualized 2.1 GHz Xeon, base 2948eeb); about
±0.4% on the isolated judge, on GitHub's machines (note of miniz-0018); elsewhere, to be measured (miniz-0003).
Profiler: since miniz-0033, a comment is no longer taken for a function; since miniz-0034, names with capital letters
are detected and no longer go to « hors fonction ». Compile the bench and profile in the same session of
`bee/sandbox/sans-docker.sh`, which mounts the repository at a different path each time, otherwise everything goes to
« hors miniz » (miniz-0034). The profile table of bee/README.md is that of master at a2f939a (miniz-0034).
The isolated judge is authoritative: the common judge, which replaced the fork's own judge (miniz-0031) in miniz-0032,
with the plugin the fork keeps in `bee/juge/projet.py`; it checks each output with the host's zlib and counts the whole
process; its meta-tests (`bee/juge/test_juge.py`) run on every PR that changes `bee/juge/`. A PR that touches `.github/`
is never merged automatically (note of miniz-0032).
A new judge proves what it catches: regressions seeded in a copy of the sources (roles/measure). The corpus, 61 files
and 12.0 MB almost entirely synthetic (miniz-0028), changes only through a task that allows it (bee/README.md).
## What you can ignore here
miniz's code (areas `deflate`, `inflate`, `api`), except to seed a regression in a copy of it.
## Children
None.
