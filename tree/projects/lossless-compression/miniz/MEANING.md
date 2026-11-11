---
parent: projects/lossless-compression
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# miniz
## Why this branch exists
zlib-compatible Deflate and Inflate, embedded everywhere. Fork `Bee-ruche/minizBee`, branch `master`; tooling: the
fork's `bee/README.md`.
## What matters here
Judge: what miniz compresses, zlib decompresses, and the other way round. Metrics: projects/miniz.yaml. R4, for a
throughput: at least 2% fewer instructions, which the stopwatch confirms beyond the noise (or another configuration).
Isolated judge: the CI runs your code in a container with no network and checks each output with another zlib; locally:
`python3 <registry>/tools/judge/judge.py --tooling . --source-a <base> --source-b <your copy>` (Docker). What it finds
suspicious (system call, clock, replaced libc symbol…) calls for a guardian: justify what is legitimate (SIMD) in
`change`.
Pitfalls: unaligned reads through memcpy into a local variable, never through a pointer cast; generic path kept (R6); in
decompression, instructions and the stopwatch often diverge (area `inflate`).
## What you can ignore here
ZIP (`miniz_zip.c`) and PNG, out of scope.
## Children
- `projects/lossless-compression/miniz/deflate`: compression, `miniz_tdef.c` (`tdefl_*`)
- `projects/lossless-compression/miniz/inflate`: decompression, `miniz_tinfl.c` (`tinfl_decompress`)
- `projects/lossless-compression/miniz/api`: zlib-compatible API and checksums, `miniz.c` (`mz_*`)
- `projects/lossless-compression/miniz/bee`: the fork's tooling, `bee/` (tests, fuzzing, bench, judge)
