---
parent: root
updated_on: "2026-11-11"
maintained_by: ruche-0010
line_budget: 40
---
# Lossless compression
## Why this branch exists
Compressors serve every transfer and every archive.
## What matters here
Proof: a bit-for-bit round trip, compatible with the reference both ways. An optimization task sets `compressed_output`:
`identical`, or `may_change` if `ratio_n6` does not drop.
## What you can ignore here
bzip2 (not open yet: ruche-0002).
## Children
- `projects/lossless-compression/miniz`: miniz, zlib-compatible Deflate and Inflate
