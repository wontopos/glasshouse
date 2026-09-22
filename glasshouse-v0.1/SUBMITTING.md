# Submitting a run

One JSON object per line, one line per question. The scorer reads exactly the fields
listed here and ignores anything else, so extra keys are safe to leave in.

```bash
python score.py your_run.jsonl --questions questions_full.jsonl --mode memory
```

`--mode` has no default. A run scored under the wrong mode moves the total by more than the
gap between most systems, so the scorer refuses to guess.

---

## Required on every line

| field | type | what it is |
|---|---|---|
| `id` | string | the question id, exactly as it appears in the question file (`Q001`, `I042`, `P0123`, `L2-0007`) |
| `answer` | string | what your system produced for that question |

That is the whole minimum. A run with only these two fields scores correctly.

```json
{"id": "Q001", "answer": "a quarter acre"}
{"id": "Q002", "answer": "I don't have that in my notes"}
```

## Strongly recommended

| field | type | what it does |
|---|---|---|
| `answer_generated` | bool | `true` if an answer model wrote the text, `false` if `answer` is the retrieved memories concatenated. **Leaving this out hides an inflated run.** See "A run without the answer model is inflated" in the README |
| `retrieved_turns` | list of int | the turn ids your system pulled, in the corpus tier you ran. This is what separates "retrieval missed it" from "retrieval found it and the reader failed" |
| `chars_returned` | int | characters handed to the answer model for this question. Cost per correct answer needs it |
| `memories_returned` | list of strings | the memories themselves, as text, one string per item. **Not a count.** The scorer measures this text and compares it against your `chars_returned`, which is the only way a token efficiency number can be checked rather than taken on trust. A run that sends a number here is scored, but marked non compliant for token efficiency |

## Optional, for the speed and cost columns

| field | type | notes |
|---|---|---|
| `latency_ms` | number | end to end for this question |
| `network_ms` | number | round trip to subtract. Without it, distance to the server decides the ranking |
| `prompt_tokens` | int | tokens handed to the answer model |
| `turn_id` | int | for ingestion side records |

---

## Which question file goes with which corpus file

**`turn_id` restarts at 1 in every corpus tier.** Turn 12 of `core` is not turn 12 of
`full`. Mixing a question file from one tier with a corpus file from another points every
evidence link at the wrong turn.

| you ran | use |
|---|---|
| `glasshouse_v0.1_core.jsonl` | `questions_core.jsonl` |
| `glasshouse_v0.1_small.jsonl` | `questions_small.jsonl` |
| `glasshouse_v0.1_medium.jsonl` | `questions_medium.jsonl` |
| `glasshouse_v0.1_full.jsonl` | `questions_full.jsonl` |

The probe and language axis files (`glasshouse_v0.1_probes.jsonl`, `questions_xling.jsonl`) are
scored against whichever tier you stored, and need `small` or larger because `core` carries
no filler, no photographs and no multilingual sessions.

⚠️ **The 500 `XLING_QUERY` rows must be asked with `question`, not `question_en`.** Those rows
carry both fields; `question` is the foreign-language one named by `query_lang`, and it is the
question. `question_en` is there for checking and reporting. A run that asks these in English
is asking in the language the memory is already stored in, so the axis measures nothing, and
the result is not accepted. The 300 `XLING_STORE` rows have no `question` field and are asked
in English as normal. See "The language axis" in the README.

---

## What a submitted result must state

A number with none of this attached cannot be checked by anyone, so it is not accepted.

1. **which tier** you ran, and which question file
2. **which mode** (`memory`, `answer` or `dry`)
3. **which answer model**, if `answer_generated` is true
4. **the retrieval budget** you used
5. **the date** and the version of the benchmark

`dry` is a string match for development. It counts a correctly worded answer as wrong when
the wording differs, so it is never a published number.

---

## Sending it

Open a pull request that adds a directory laid out the way `CONTRIBUTING.md` in
`glasshouse_docs/` describes:

    submissions/<version>/<system>/<date>/
      manifest.json      what ran, and how it was scored
      records/           the per-question record this page describes
      README.md          anything a reader needs that the manifest cannot hold

`manifest.json` follows `schema/submission.schema.json`, and every field its `required`
list names has to be there. `GOVERNANCE.md` has who has to agree before it merges.

Results are kept in the repository rather than regenerated. A score with no record behind it
is a claim, not a measurement.

## What happens when you open the pull request

A GitHub action runs `ci_score.py` over the files you added. We do not score your run by hand
and then tell you the number, because the whole problem this benchmark exists to address is
that everyone in this field measures their own system and publishes their own figure. You can
run the same script yourself before you send anything.

Everything the action needs is in the `manifest.json` described above, which follows
`schema/submission.schema.json`. Two fields in it are read for glasshouse specifically:

- `corpus.turns` tells the action which tier you ran. It has to be 1,882, 7,186, 12,884 or
  103,572, and it decides which question file your ids are checked against.
- `runs[].config.mode` is `memory` or `answer`. `dry` is not accepted, for the reason given
  above.

Neither is a field invented for this benchmark. They are the schema's own, so a manifest
written for the repository works here without anything added.

The action rejects the pull request for any of these, and each one is printed with the ids:

| | why it is rejected |
|---|---|
| a question id appears twice, or is not in the question file | the denominator would be wrong |
| `answer` is empty | send the empty answer as an empty string, not as a missing line |
| a turn id in `retrieved_turns` is not in the tier you named | turn ids restart at 1 in every tier file, so this usually means two tiers got mixed |
| `chars_returned` disagrees with the length of the text in `memories_returned` | this is the number that decides token efficiency, and a claimed figure nobody checks is not evidence |
| `memories_returned` holds a count instead of the text | same reason: without the text there is nothing to check the claim against |

It then scores the run in `dry` mode, which needs no key and which anyone can reproduce line
for line. **That is not the published number.** It is there to show that the same file gives
the same result every time. The published number comes from the judge model, which costs
money to run, so the action only produces it when the repository has a key configured, and
says plainly when it skipped that step.
