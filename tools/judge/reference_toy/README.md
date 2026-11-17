# The toy project of the judge's second kind (`reference`)

A project's tip, as far as `tools/judge/reference.py` reads one: used by `tools/judge/test_reference.py`, honest and
hostile. Nothing here is a real project.

- `reference/original.c`: the ORIGINAL, two functions of bytes: `upper` (ASCII letters to capitals; it refuses a
  text that holds a byte above 127) and `squeeze` (runs of spaces become one space; it never refuses).
- `port/<unit>.c`: the unit a task writes. At this tip both are unwritten: they build, and abort when called.
- `harness/`: the reference's driver, the unit's driver, and the generator of cases (all the project's own).
- `bee/reference/project.json`: the manifest (data). `bee/reference/build-reference` and `build-unit`: the two
  build scripts, run in containers only. `build-unit` reads a nonce and makes the binary's layout follow it.
