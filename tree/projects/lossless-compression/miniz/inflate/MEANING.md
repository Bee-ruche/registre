---
parent: projects/lossless-compression/miniz
updated_on: "2026-11-11"
maintained_by: ruche-0014
line_budget: 40
---
# Decompression: miniz_tinfl.c
## Why this branch exists
miniz's Inflate: `tinfl_decompress`, a coroutine that stops and resumes at any input or output byte (TINFL_CR_RETURN),
builds each block's Huffman tables, decodes literals, lengths and distances, copies the matches and computes the
Adler-32. Metric: `decompression_throughput`.
## What matters here
Profile of the base 2948eeb, before miniz-0012 and miniz-0016 (redo it: `bee/bench/profil.py`): `tinfl_decompress` 99.3%
of decompression (the fork's bee/README.md); match copy 23.0% (miniz-0012), literal loop 22.2% (miniz-0018), Adler-32
22.0% (miniz-0016), length and distance 19.1% (miniz-0017), tables 4.1% (miniz-0022).
Integrated (CI verdicts, GitHub's machines; judged commit: `verdict.sha` in `contributions/miniz/`): non-overlapping
copy by 4 or 8 bytes, instructions −7.4%, throughput +17.2% (miniz-0012); Adler-32 in blocks of 16 bytes, instructions
−4.9%, throughput +9.5% (miniz-0016).
Instructions and the stopwatch often diverge. In review, miniz-0017-c1 (instructions −5.1%) and miniz-0018-c1 (−3.7%)
stay within the noise on the stopwatch (their verdicts). The original 8-byte copy, enabled: instructions −1.9%,
throughput −2.2% (miniz-0012's context: virtualized 2.1 GHz Xeon, gcc 13.3, base 2948eeb). Local pointers to the tables:
instructions +0.9% (note of miniz-0018). libdeflate-style tables (manifest of the branch essai/miniz-0022-doublement:
af45a86 against 1c625c3, virtualized 2.1 GHz Xeon, gcc 13.3): instructions −2.8%; throughput on the full corpus +0.63%,
as much as an identical copy of the base (+0.60%); +44.6% on 1 KiB per file; stack from 448 to 1,120 bytes. R4 then asks
for another configuration that sees the gain.
Format of `m_look_up` (miniz_tinfl.c l. 363 at 9977da4): a positive entry is (code length << 9) | symbol, for codes of
10 bits at most (TINFL_FAST_LOOKUP_BITS); a negative one leads to `m_tree_*` for longer codes. Every fast path reads
this format as is, and the tables produced stay identical (miniz-0022).
A fast path is proven at its bounds too: that of the literal loop requires 4 bytes of input and 2 of output (l. 427),
and the `flux-1` check (one-byte buffers, bee/tests/differentiel.c l. 7) never exercises it (corrective note of
ruche-0014): "flux-1 with no difference" proves the slow paths, not the fast one. Show which input and output sizes, on
either side of the threshold, exercise it; the rest goes in `untested`.
Invariants: slow paths (end of buffer, resumption of the coroutine) intact, they alone allow byte-by-byte calls
(miniz-0017); on invalid input, the same statuses and the same bytes produced before stopping (miniz-0018), compared by
`fuzz_inflate` and the isolated judge; Adler-32 reduced modulo 65521 at least once every 5552 bytes (miniz-0016).
## What you can ignore here
Compression (`deflate`); error messages and codes, excluded by the tasks; ZIP and PNG.
## Children
None.
