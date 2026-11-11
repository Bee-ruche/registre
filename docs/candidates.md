# Candidate projects

Research of 27 October 2026, done by a Bee research agent without cloning or running anything. The licenses were read in the official license files. Presence in OSS-Fuzz was checked through the `projects/<name>/project.yaml` file of google/oss-fuzz. The usage figures come from Debian (popcon, and the number of trixie packages that depend directly on the library). The sizes count the lines of the core, comments included. What could not be checked is marked "estimated".

## Selected for phase 3

| Project | Category | License | Differential reference | Core | Usage | Why |
| --- | --- | --- | --- | --- | --- | --- |
| [giflib](https://sourceforge.net/p/giflib/code/) | Image decoding | MIT | Wuffs std/gif, stb_image, libnsgif | ~3,700 lines, decoder ~2,400 (estimated) | OpenJDK, Android, GDAL, Emacs, Krita; 138,000 Debian installations | Very small, three independent references, no vectorization; Wuffs claims decoding 2 to 6 times faster |
| [libyaml](https://github.com/yaml/libyaml) | Parsing and serialization | MIT | yaml-test-suite (event stream), libfyaml | ~13,000 lines | PyYAML's C loader, Psych (Ruby), appstream, netplan; 202,000 installations | Strictest oracle; no release since 2020; a gap of about 6.5 times with rapidyaml on their bench |
| [bzip2](https://sourceware.org/git/?p=bzip2.git) | Lossless compression | BSD variant specific to bzip2 | Original output byte for byte, bzip2-tests corpus, Wuffs, libbzip2-rs | ~5,200 lines | dpkg, apt, Python's standard library; 6th most installed package in Debian | Very wide usage, no vectorization, reuses all of miniz's tooling |

Points to watch:
- **giflib.** Wuffs composites the animated frames whereas giflib renders the raw frames: the harness must recomposite before comparing.
- **bzip2.** Start from sourceware: the GitLab mirror has been frozen since May 2023.

## In reserve (phase 4 or later)

| Project | Category | License | Note |
| --- | --- | --- | --- |
| [LodePNG](https://github.com/lvandeve/lodepng) | Image decoding | zlib | Originally planned for phase 3; overlaps giflib for the image harness |
| [cJSON](https://github.com/DaveGamble/cJSON) | JSON parsing | MIT | Originally planned for phase 3; widely used in embedded systems, which the Debian figures underestimate |
| [zopfli](https://github.com/google/zopfli) | Compression | Apache-2.0 | Very slow by design, hence a large margin; trivial oracle (deterministic output) |
| [md4c](https://github.com/mity/md4c) | Markdown parsing | MIT | CommonMark specification as the oracle; the author already optimizes, hence less margin |
| [jansson](https://github.com/akheron/jansson) | JSON parsing | MIT | Would reuse the JSON harness; binutils, apache2, nftables |
| [libcbor](https://github.com/PJK/libcbor) | CBOR serialization | MIT | Small and clean; tiny FIDO messages, low perceived gain (estimated) |
| [Expat](https://github.com/libexpat/libexpat) | XML parsing | MIT | Huge usage (dbus, fontconfig, CPython) but 16,800 lines, and the fork would have to follow upstream's security fixes |
| [nanopb](https://github.com/nanopb/nanopb) | Protobuf serialization | zlib | Of interest for the "lighter" goal (ROM, RAM, stack) |
| [stb_image](https://github.com/nothings/stb) | Image decoding | MIT or public domain | JPEG already partly vectorized |
| [QOI](https://github.com/phoboslab/qoi) | Image decoding | MIT | 649 lines: a good school project to train the agents, low impact |

## Ruled out

| Project | Reason |
| --- | --- |
| lz4, LZMA SDK, base64 (aklomp), lossless libwebp, libspng, libpng | Already vectorized or written in assembly |
| zlib, libdeflate, zstd, simdjson, yyjson, libjpeg-turbo | An optimized fork exists, or already highly optimized |
| pugixml | Already designed for speed, low Debian usage |
| tinyxml2 | Lax parser, no strict oracle |
| cmark | Duplicate of md4c; better as a reference |
| jsmn, inih, uriparser, cgltf | Low usage, or never a bottleneck |
| tomlc99 | Declared obsolete by its author |
| dr_flac | Audio: outside the v0 categories |
| LZO | GPL-2 license |
| libxml2 | Too big |

## Main sources

- Licenses and license files: each project's official repositories; [bzip2 on sourceware](https://sourceware.org/git/?p=bzip2.git); [giflib on SourceForge](https://sourceforge.net/p/giflib/code/ci/master/tree/COPYING).
- OSS-Fuzz: [google/oss-fuzz, projects folder](https://github.com/google/oss-fuzz/tree/master/projects).
- Usage: [Debian popcon](https://popcon.debian.org/) and the Debian trixie package index.
- Claimed gain margins: [Wuffs README](https://github.com/google/wuffs), [rapidyaml bench](https://rapidyaml.readthedocs.io/).
