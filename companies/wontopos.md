# Wontopos

Long-term memory for AI agents, offered as a hosted API. Closed source, hosted only.

- https://wontopos.com
- https://github.com/wontopos

Wontopos administers this repository. What that role does and does not include is in
[GOVERNANCE.md](../GOVERNANCE.md).

## Claims

Produced by Wontopos. Not verified here.

| Model | Benchmark | Score | Runs | Reader | Judge | Record |
|---|---|---|---|---|---|---|
| tablet-2 | LongMemEval-S | 95.7% (σ 0.4) | 3 — 95.2 / 96.0 / 96.0 | claude-opus-5, max effort | in record | [beam1m-tablet-2](https://github.com/wontopos/beam1m-tablet-2) |
| tablet-2 | LongMemEval-S | 93.7% | same runs | gpt-5.6-sol | in record | [beam1m-tablet-2](https://github.com/wontopos/beam1m-tablet-2) |
| tablet-2 | BEAM 1M | 67.5% (σ 0.22) | 5, none dropped | claude-opus-5, max effort | gpt-4.1-mini, benchmark's own prompt | [beam1m-tablet-2](https://github.com/wontopos/beam1m-tablet-2) |
| scroll-1.2 | LongMemEval-S | 92.3% | 5 | not published | not published | — |
| scroll-1 | LongMemEval-S | 90.7% | 5 | not published | not published | — |
| tablet-1 | LongMemEval-S | 85.2% (σ 1.1) | 5, none dropped | not published | not published | — |

LongMemEval-S appears twice for tablet-2 because the same runs read by a different
frontier model score 93.7% instead of 95.7%. That gap belongs to the reader, in a
number usually reported as the memory system's.

The bottom three rows do not name a reader or a judge, so under
[CONTRIBUTING.md](../CONTRIBUTING.md) they would not be accepted as submissions.
They are listed because they are live public claims.
