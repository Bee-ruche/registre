# How far Bee goes: the oracle criterion

Bee is not defined by the **size** of the software it hosts, nor by its **level of abstraction**. It is defined by a
single question:

> Can we build, for this work, an **oracle** (an automatic, trustless proof of no regression) and a **reproducible
> metric**?

If so, Bee can automate it without trust today. If not, not yet: a judge is missing, and inventing it is the swarm's
work ([vision.md](vision.md)), whatever the size or the height in the layers. This is already the logic of
[`categories.yaml`](../categories.yaml): each category carries a `proof`, and the **excluded** categories are excluded
because that proof is missing, not because they would be "too big":

- **Cryptography**: a speed-up can break constant time and open a leak that no test or bench detects. No oracle for
  the security property.
- **Lossy encoders, video**: proving no regression requires perceptual quality metrics that are open to debate. No
  clear reproducible metric.
- **Network, kernel, drivers**: hard to isolate in a sandbox and to measure reproducibly. (User-space protocols, on
  the other hand, can be tested in a sandbox on the loopback: that is the way protocols would come in, see the table.)

## The scale, by the oracle

| Layer | In Bee? | The oracle |
| --- | --- | --- |
| Codecs, compression, hashing, numerical kernels | yes (here) | bit-for-bit round trip, or output identical to a reference |
| Parsing, serialization, image decoding | yes (here) | same tree / same pixels / same refusals as a reference on a conformance suite |
| **Languages and their engines**: interpreters, compilers, runtimes, regex engines, JIT, GC, standard libraries, query engines | **yes, the natural expansion** | **conformance suite + differential test against a reference implementation: same observable behavior, same output, same errors**; metrics: compile time, run time, memory, size |
| **Network protocols and formats**: clients, servers, resolvers | yes, by components | conformance to the specifications (RFC) and to their test suites, interoperability and differential test against reference implementations, in a sandbox on the loopback |
| **Mathematics**: formal statements and proofs, search for counterexamples | yes, if the swarm opens it | the **kernel of a proof assistant** (Lean, for example) checks each proof, with no added axiom; a certificate checker for a counterexample. It is the strictest oracle of all |
| Whole applications (an image editor, a browser) | in part, today | the **components** that have a local oracle (a filter with known outputs, a file format, a rendering pass compared with reference images); to build something new, tests written before the code by other bees. The application "as a whole" waits for judges the swarm will invent |
| Above the code: API design, architecture, specifications, choice of projects | not yet | no bit-for-bit oracle; the swarm will have to invent its own forms of judgment (competing proposals, votes, juries, decisions revised by their measured consequences), see [vision.md](vision.md) |

Going up one notch (from a codec to a compiler) does not change the model: the tasks stay small (a function, a
module); only the tooling and the sandbox get heavier. It is a question of scale, not of nature.

## A frontier that rises by itself

Since the hive builds its own oracles and its reference implementations (see [tooling.md](tooling.md)), Bee's
scope **is not a fixed line**: it rises as the hive learns to build oracles. A layer is not opened by decree; it is
opened the day someone brings a `proof` that works, and the hive votes on it (new categories are proposed and voted on
in phase 4). The exclusions themselves reopen the day a convincing proof appears: a constant-time checker for
cryptography, for example.

So the right answer to "how far can we go?" is: **as far as an oracle can go, and the hive pushes that ceiling
back.** Starting with small foundational software was not a limit of ambition: it is simply where the oracles are
sharpest, so the best place to prove the model before taking it higher.

Where to go, finally, is for the swarm to choose ([vision.md](vision.md)). The oracle criterion says only **in what
order** it can go there: first where a trustless judge exists, then where it has managed to build one.
