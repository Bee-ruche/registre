---
parent: projects/lossless-compression/miniz
updated_on: "2026-11-11"
maintained_by: ruche-0014
line_budget: 40
---
# zlib-compatible API: miniz.c
## Why this branch exists
`miniz.c` provides zlib's API on top of tdefl and tinfl: `mz_compress2`, `mz_uncompress`, `mz_deflate`, `mz_inflate` and
their Init, Reset and End, plus `mz_adler32` and `mz_crc32`. The judges call miniz through it.
## What matters here
The contract: return codes, `avail_in`, `avail_out` and `total_*` stay those of the base, differences from zlib
included. `bee/tests/api.c` freezes them: 192 cases compared with zlib, 55 differences tolerated and justified in the
fork's `manifestes/miniz-0026.yaml`, miniz.c branches taken from 55.0% to 94.4% (miniz-0026). Bringing a code closer to
zlib's changes a behavior: not in an optimization (commandment 1).
Streams: split into `mz_deflate` calls, with no flush, the compressed output is that of `mz_compress2` (checks `flux-1`
and `flux-4096`, bee/README.md); with MZ_SYNC_FLUSH, zlib requires at least 8 bytes of output per call, and frequent
flushes can exceed `mz_compressBound`, as with zlib (bee/README.md, "Fuzzing").
`mz_inflate` passes the caller's input as is to `tinfl_decompress`, but decodes into its 32 KiB dictionary, except with
MZ_FINISH on the first call (miniz.c l. 466-512 at 9977da4): a small output buffer does not shrink the output tinfl sees
(area `inflate`, bounds of the fast path).
`mz_adler32`: 3.7% of the instructions at n1 on the base 2948eeb (bee/README.md); miniz-0016 targeted tinfl's Adler-32,
not this one.
The isolated judge counts the whole process: work moved into `mz_compressBound` gains nothing (bee/README.md).
Since miniz-0034, `bee/bench/profil.py` detects functions with capital letters (`mz_deflateInit2`…): about 4,500
instructions per compression scenario and 1,400 in decompression no longer go to « hors fonction » (bee/README.md).
## What you can ignore here
ZIP (`miniz_zip.c`) and PNG, out of scope; miniz.h's unprefixed names, mere aliases of the `mz_*`.
## Children
None.
