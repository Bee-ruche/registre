---
parent: projects/lossless-compression/miniz
updated_on: "2026-11-11"
maintained_by: ruche-0014
line_budget: 40
---
# Compression: miniz_tdef.c
## Why this branch exists
miniz's Deflate: `tdefl_compress_normal` inserts each byte into the hash chains (`m_hash`, `m_next`), `tdefl_find_match`
searches them for the longest match, `tdefl_record_*` records the symbols, `tdefl_compress_lz_codes` and
`tdefl_flush_block` write the blocks. Metrics: `debit_compression_n1|n6|n9`.
## What matters here
Profile of the base 2948eeb, before the integrated tasks (the fork's bee/README.md; redo it: `bee/bench/profil.py`): n1
`tdefl_compress_normal` 48.2%, `tdefl_find_match` 22.7%, `tdefl_compress_lz_codes` 13.6%; n6 26.8%, 60.0%, 5.7%; n9
18.7%, 72.1%, 4.0%. The probes of `tdefl_find_match`: 42.4% at n6, 55.3% at n9 (miniz-0014).
Integrated (CI verdicts, GitHub's machines; judged commit: `verdict.sha` in `contributions/miniz/`): bits written in
64-bit words, n1 +11.4% (miniz-0011); match length in 64-bit words, n6 +4.3% (miniz-0015); probe end read in 16 bits, n9
+8.7%, instructions −2.7% (miniz-0014); insertion into the chains, n1 +2.2%, instructions −8.4% (miniz-0013). The
byte-by-byte comparison of `tdefl_find_match` is therefore only the fallback now: miniz-0010's context predates this.
Invariants (`compressed_output: identical`): the same matches chosen, hence the same insertion order in `m_hash` and
`m_next` (miniz-0013) and the same choice of probes; the same instant for each flush, which sets the split into blocks
(miniz-0019); `m_lz_code_buf` identical byte for byte (miniz-0020); a word read stays below `max_match_len`, inside
`m_dict` (miniz-0015); level 1: greedy parsing, with no pending match (miniz-0024).
Measured leads: enabling miniz's 16-bit variant changed 41 of the 305 fingerprints of the time (notes of 27 Oct on
miniz-0010 and miniz-0015; 488 since miniz-0024); `tdefl_compress_fast`: n1 throughput ×1.85, `ratio_n1` −8.7%
(miniz-0027's context, with no machine or commit). Note of 28 Oct on miniz-0020, with no machine or commit:
`tdefl_record_*`, ceiling around 1.5% of n1 instructions; best variant −0.73% of n1 instructions but a 4% drop on the
stopwatch (metric not stated); LZ state in locals in `tdefl_compress_normal` (miniz-0019's lead): +0.22%, quantity not
stated, registers spilled. These figures with no machine or commit are to be measured again.
Pitfalls: MINIZ_USE_UNALIGNED_LOADS_AND_STORES is 0 everywhere (miniz.h): its variants, `tdefl_compress_fast` included,
are not compiled; Bee's paths have their own gate (TDEFL_USE_64BIT_BITBUF, TDEFL_FIND_MATCH_64BIT), which can be forced
to 0 to test the fallback (R6). Manifests of miniz-0013 and miniz-0014 (virtualized 2.1 GHz Xeon, gcc 13.3; be1b54b,
6b368d8): `tdefl_find_match`, inlined into `tdefl_compress_normal`, gains depending on gcc's register allocation;
`debit_decompression` drops there by 1.1 to 2.5%, within the noise, with tinfl's code identical but shifted: compare the
disassembly before concluding. Outside the default strategy, only fuzzing tests (miniz-0023).
## What you can ignore here
Decompression (`inflate`); the hash function and the number of probes, excluded by the tasks; ZIP and PNG.
## Children
None.
