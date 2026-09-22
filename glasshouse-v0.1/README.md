# glasshouse v0.1

A long-term memory benchmark for AI systems. 2,847 questions over a conversation
that runs to 1.97 million tokens, in 10 languages, with 50 photographs.

Built by Wontopos. Draft, not yet released.

---

## What it measures

A memory system is given a long conversation history and then asked questions about it.
The questions are grouped into axes, and **each axis is reported separately**. There is no
single headline number, because a system can be strong at one of these and useless at another.

| Axis | Questions | What it asks |
|---|---|---|
| `XLING_QUERY` | 500 | Can it find a memory when asked in **any of the 10 languages**? (50 per language) |
| `FALSE_MEMORY` | 500 | If you assert something that was never said, does it agree? |
| `BASIC` | 733 | Can it retrieve a stated fact? |
| `XLING_STORE` | 300 | Can it find a memory stored in **any of the 10 languages** when asked in English? (30 per language) |
| `IMAGE` | 150 | Was a photograph with no caption stored and retrieved? |
| `MULTI` | 59 | Can it combine facts from separate sessions? |
| `IMPLICIT` | 46 | Can it connect two things the conversation never connects? |
| `TEMPORAL` | 106 | Does it know what came first, and how long between? |
| `CONFLICT` | 53 | Given an outdated value, does it correct it? |
| `ABSTAIN` | 49 | When the answer was never stated, does it say so? |
| `UPDATE` | 48 | When a fact changed, does it return the current value? |
| `STALE` | 30 | When it cannot find the new value, does it serve the old one as current? |
| `CONTRADICT` | 30 | When two stored facts disagree and nothing settles it, does it say so? |
| `PARAPHRASE` | 153 | The answer is there in one turn, but said in other words. Does it hear it? |
| `CROSS` | 30 | Does it join a fact from one part of life to a fact from another? |
| `GATHER` | 30 | The answer is in two pieces in two turns. Does it bring back both? |
| `RECONCILE` | 30 | Two statements look incompatible but hold under different conditions. Does it explain both, or pick one and call the other wrong? |

`RECONCILE` is the mirror image of `CONTRADICT`, and the two are easy to confuse. Both look like a collision: the speaker skips breakfast on weekdays and cooks one at weekends, keeps quiet at work and says exactly what he thinks outside it. The difference is that here the two statements carry different conditions, so both are true and there is a correct answer. Explaining that both hold is full credit, naming only one side is half, and treating either side as false is zero. Saying "I don't know" earns nothing, because unlike `STALE` neither statement is hidden. What the axis measures is whether a system that retrieves one memory stops there and asserts it. `audit_reconcile.py` checks on every build that the conditions still differ, that the two statements sit in different sessions, that nothing in the history corrects either one, and that no single turn does the reconciling for the system.

`CONTRADICT` is the only axis with no correct value. The speaker says one thing in spring
and something incompatible three weeks later, neither of them notices, and nothing in the
history resolves it. Saying the two do not agree is full credit, saying "I don't know" is
half, and confidently picking one is zero. It exists because every other axis here is a
clean replacement where the newer value is simply correct, which is not what disagreement
in a real history looks like.

`STALE` is scored three ways rather than two. A fact changes partway through
the history and the question asks for the current value. Finding the new value is full
credit, saying "I don't know" is half, and confidently repeating the old value is zero.
Collapsing those last two into one wrong answer hides the difference between a system that
fails safely and one that states something that stopped being true months ago.

`ABSTAIN` and `FALSE_MEMORY` both reward saying "I don't know", but they are not the same
test. `FALSE_MEMORY` plants a false claim in the question; `ABSTAIN` just asks. A system that
answers "I don't know" to everything scores full marks on both and zero on the other nine.

---

## Corpus files: the two you run are `core` and `full`

There are four files, but **the standard run is two tiers.** `small` and `medium` are
intermediate marks, left in the release but out of the default run (see "The standard
run is two tiers" below).

| File | Standard run | Sessions | Turns | Photos | Multilingual sessions | Tokens |
|---|---|---|---|---|---|---|
| `glasshouse_v0.1_core.jsonl` | **yes** | 96 | 1,882 | 0 | 0 | 78,584 |
| `glasshouse_v0.1_small.jsonl` | no | 259 | 7,186 | 50 | 100 | 192,407 |
| `glasshouse_v0.1_medium.jsonl` | no | 364 | 12,884 | 50 | 100 | 297,892 |
| `glasshouse_v0.1_full.jsonl` | **yes** | 1,991 | 103,572 | 50 | 100 | 1,971,338 |

They are nested: `core` inside `small` inside `medium` inside `full`, checked by
comparing the text itself.

`core` holds only the 96 sessions we wrote, with no filler and no photographs. It is there so
you can see the material on its own. **The image and language axes need `small` or larger.**

One thing to watch. **`turn_id` restarts at 1 in every file.** Turn 12 of `core` is not
turn 12 of `full`, so the `evidence_turns` in `questions_core.jsonl` are numbered against
`core` and nothing else. Mixing a question file from one tier with a corpus file from
another points at the wrong turns. Within a tier every evidence turn resolves, which we
checked for all four.

The filler sessions come from an earlier version of this benchmark. They are ordinary
assistant conversations on ten everyday topics. **Most of them are never asked about, but
not all of them.** In `full`, 609 of the 100,490 filler turns are the evidence for 893
questions, and that includes every one of the 50 turns carrying a photograph. The other
99,881 turns are filler nobody asks about.

---


### Holding up as data piles up: we compare tiers

The **1,882 turns we wrote are byte-identical across all four tiers**, which we
checked by comparing the text. What grows is filler nobody asks about.

| Tier | Total turns | Ours | Multilingual | Filler turns asked about | Pure filler | Turns carrying answers | Share |
|---|---|---|---|---|---|---|---|
| core | 1,882 | 1,882 | 0 | 0 | 0 | 1,882 | 100.0% |
| small | 7,186 | 1,882 | 1,200 | 68 | 4,036 | 3,150 | 43.8% |
| medium | 12,884 | 1,882 | 1,200 | 102 | 9,700 | 3,184 | 24.7% |
| full | 103,572 | 1,882 | 1,200 | 609 | 99,881 | 3,691 | 3.6% |

"Turns carrying answers" counts the turns we wrote, the multilingual turns, and the
filler turns a question points at, using each tier's own question file. The 1,200
multilingual turns hold the answers for the 800 language-axis questions, so they
belong in that column.

The question sets nest too. **The 633 core questions are all inside the 1,547
used for full**, checked by id.

So running the same questions tier by tier is the saturation test. The signal is
held byte-for-byte constant while the corpus grows 55 times, from 1,882 turns to
103,572. Where the score falls apart tells you whether a system holds up under
accumulation or is just a dumpster.

### The standard run is two tiers, `core` and `full`

You do not need all four. **`core` and `full` are the standard run.** `small` and
`medium` are intermediate marks, useful when you want to see where a system starts
to slip rather than only that it does.

| Tiers run | Questions | Cost vs `full` alone | What you learn |
|---|---|---|---|
| `full` only | 1,547 | 1.0x | One number, and no way to say why |
| **`core` + `full`** | **2,180** | **about 1.4x** | **Whether the loss is skill or volume** |
| All four | 3,892 | about 2.5x | Where along the curve it breaks |

`core` does two jobs.

First, it is the **control**. A `full` score mixes two things together: how good the
system is, and how much it loses under 100,000 turns of unrelated talk. `core` has
zero filler, so the second term is zero. Only one variable separates the two runs,
so a gap has exactly one explanation.

```
core 92 -> full 62    it knows the answer but cannot retrieve it    retrieval problem
core 64 -> full 62    that is simply its level, volume was not it   capability problem
```

Second, it **checks the test itself**. If every system lands in the forties on `full`,
someone has to separate "they are all bad" from "our questions are ambiguous". In
`core` the conversation is small enough to read whole, so failing there points at the
questions, not the system. We are publishing a benchmark nobody has reason to trust
yet, so that check matters.

⚠️ **A `core` score does not demonstrate the value of a memory system.** At 90,870
tokens, `core` fits whole inside a current context window, so it can be solved by
pasting the entire history into the prompt. `full` is 2.18 million tokens and does not
fit even a 1M window, which is where a memory system stops being optional. `core`
exists to make the `full` number interpretable.

⚠️ **The 30-per-axis floor holds for `full`.** The newer axes (`CROSS`, `GATHER`,
`CONTRADICT`, `RECONCILE`) have their evidence planted inside the filler conversations,
and the smaller tiers carry only part of those, so the questions drop out. Compare
tiers using the 633 farming and coding questions that are identical in all four, and
read per-axis results off `full`.

⚠️ **We do not cut the conversation at checkpoints.** Cutting removes answers along
with filler, so you have to keep only the questions whose answer survives the cut.
That changes what you measure from "does it hold up under accumulation" to "is the
data there yet". Tier comparison needs no such filter: the answers are always all present.

## Turn format

```json
{"turn_id": 11, "session_id": 1, "kind": "noise", "category": "daily_life",
 "speaker": "user", "text": "Grabbed a spot and stepped out for a minute.",
 "image": "img/img36.png", "image_no": 36, "date": "2026-02-22"}
```

| Field | |
|---|---|
| `kind` | `core` (the story we wrote) or `noise` (filler) |
| `category` | topic. `farming` or `coding` for core, `multilingual` for the language sessions |
| `date` | every session has one. The story runs 2026-03-02 to 2027-07-05 |
| `image` | present on the one turn that carries a photograph |
| `lang` | present on turns in the 100 foreign-language sessions |
| `core_session` | on core turns, which of the 96 sessions this is |

---

## Question format

```json
{"id": "Q001", "axis": "BASIC", "need": ["F001"], "session": 1,
 "question_en": "How big is their plot?", "gold_answer": "a quarter acre",
 "expect": "answer",
 "evidence_turns": [173], "evidence_sessions": [1], "evidence_pinned": true}
```

| Field | |
|---|---|
| `need` | which planted facts the answer depends on. `MULTI` questions list several |
| `evidence_turns` | **which turns hold the answer** |
| `expect` | `answer`, or `no_memory` for `ABSTAIN` and `FALSE_MEMORY` |

### ⚠️ The cross-language questions carry a second question field

`questions_xling.jsonl` holds 800 questions and **500 of them must not be asked in English.**
Ask those with `question`, not `question_en`.

```json
{"id": "L2-0003", "axis": "XLING_QUERY", "store_lang": "en", "query_lang": "es",
 "question": "¿De cuántas plantas a cuántas se extendieron los pulgones esa semana?",
 "question_en": "The aphids went from how many plants to how many in that week?",
 "gold_answer": "from about 20 to about 100", "source_id": "Q221"}
```

| | questions | asked in | field to use |
|---|---|---|---|
| `XLING_QUERY` | 500 | the language in `query_lang` | **`question`** |
| `XLING_STORE` | 300 | English | `question_en` |

`question_en` is present on `XLING_QUERY` rows for checking and for reporting, not for asking.
**A run that asks these 500 in English is asking in the language the memory is already stored
in, and measures nothing the other axes do not already cover.** The field exists on every row
where it applies, so a run can be checked: if `query_lang` is not `en` and the query you sent
was `question_en`, the row is void.

Two more constraints on this file:

- **Run it against `small` or larger.** `core` contains no foreign-language turns at all, so
  the 300 `XLING_STORE` questions have nothing to retrieve there.
- `XLING_QUERY` is **50 distinct questions written in ten languages each**, not 500
  independent ones (25 from the English core story, 15 from the photographs, 10 from the
  foreign sessions). Read its accuracy accordingly: the independent sample is 50.
  One of the 25, asked in all ten languages, has "never stated" as its answer; those 10
  rows carry `"expect": "no_memory"` and are graded as abstentions.

`evidence_turns` is the field worth using. It lets you separate two failures that otherwise
look identical:

- the evidence was **not in what retrieval returned** → retrieval missed it
- the evidence **was returned** and the answer is still wrong → the reader missed it

Without it a wrong answer tells you nothing about which half of the system to fix.

---

## Running it

```bash
# 1. store every turn of the conversation in your memory system, in file order.
#    glasshouse_v0.1_medium.jsonl, one JSON object per line. We ship no runner for
#    this step: it is the one part only you can write, because only you know how
#    your system ingests.

# 2. ask each question and record what came back
#    one line per question: {"id", "answer", "retrieved_turns", "chars_returned"}
#    ⚠️ the 500 XLING_QUERY rows are asked with `question`, not `question_en`

# 3. score. memory and answer call a judge LLM through OpenRouter on your own key,
#    once per question, and that key is billed
export OPENROUTER_API_KEY=...
python score.py your_run.jsonl --questions questions_medium.jsonl --mode memory
python score.py your_xling_run.jsonl --questions questions_xling.jsonl --tier medium --mode memory
```

We deliberately ship no ingest runner. One would have to pick a client, and the only client
we could write is for the memory system we sell, which does not belong in a benchmark anyone
is meant to be able to win. The scorer (`score.py`, `judge.py`, `ci_score.py`) and the two
baselines are the whole of what we publish as code, and none of them talks to any memory
system.

`--mode` is required and the scorer refuses to run without it. Choosing the wrong scoring
method moves a total by several points, which is more than the gap between most published
systems, so it should never be inferred from the file.

| mode | judge LLM | answering LLM | |
|---|---|---|---|
| `memory` | yes | no | the judge reads the **memories the system returned** and grades them against the reference answer |
| `answer` | yes | yes | an LLM writes an answer from those memories, and the judge grades **the answer** |
| `dry` | no | no | plain string match. A ruler for development, not a reported score |

⚠️ **Until 2026-09-17, `memory` and `answer` did not run.** Both stopped immediately with a
note that they were still to be connected, so the published scorer could not produce an
official score at all. They are connected now, and a build check runs the whole path end to
end with only the network call replaced by a fake. **What that check cannot show is how the
judge model responds to these prompts, because we have not yet paid to run them.** The
floor and ceiling figures further down were produced by a separate script with a close
variant of the answer prompt. If you are the first to run `memory` or `answer`, run twenty
questions first and read the verdicts saved with `--out`.

`ABSTAIN` and `FALSE_MEMORY` are not graded in `memory` mode. Their correct outcome is to
return nothing relevant, and a list of memories cannot say "I don't know", so every system
would score zero there. They are graded in `answer` mode.

Both scored modes use a judge LLM. They differ in whether an answering LLM stands
between the memories and the judge. `answer` therefore measures the memory system
**and** the writer; `memory` isolates the memory system, which is what this benchmark
is for. Report which one you ran.

`dry` costs nothing and anyone can recount it, but it only sees whether the gold string
is present, so it under-counts correct answers worded differently. Use it to catch
regressions while building, not to publish a number.

⚠️ `--mode` is required and the scorer refuses to run without it. `memory` and `answer`
   spend money, so they stay off until whoever owns the API key turns them on.

Answers here are short by design (median 5 characters), which is what makes `dry` usable at
all. A benchmark whose gold answers are paragraphs cannot be scored this way.

### Per axis scoring: what counts as right

Questions carry different weights (see `WEIGHTS.md`), and each axis decides separately what
counts as a correct answer.

    score for one question = weight x the value below (0, 0.5 or 1)

**There is one rule for partial credit: is an incomplete answer dangerous?**

Incomplete but **not dangerous** earns partial credit, because the gap is visible and the
user can ask again. Incomplete and **dangerous** earns zero, because the user takes it for a
complete answer.

| answer | dangerous? | score |
|---|---|---|
| "they keep lunch light" (says nothing about dinner) | no, **the gap shows** | 0.5 |
| "they water every other day" (it changed to daily) | yes, **read as current** | 0.0 |

Both are incomplete, and they are opposites. The first makes the user ask again. The second
**stops the user asking.**

**Weight 1, axes where retrieval finishes the job**

| axis | 1.0 | 0.0 |
|---|---|---|
| `BASIC`, `PARAPHRASE`, `IMAGE` | the gold answer is in the response | it is not |

No partial credit, because there is no middle state. Either the plot is "a quarter acre" or
it is not.

**Weight 2, axes needing one more step after retrieval**

| axis | 1.0 | 0.5 | 0.0 |
|---|---|---|---|
| `TEMPORAL` | order and interval correct | — | wrong |
| `UPDATE` | gives the **new** value | says "I don't know" | gives the old value as current |
| `GATHER` | brings back **every** piece | **the fraction it found** | none |
| `RECONCILE` | explains both hold | names one side only | calls one side false |

⚠️ `RECONCILE` gives **nothing** for "I don't know", unlike the trap axes. In a trap the new
   value is deliberately out of reach, so honesty is worth something. Here both statements
   sit in the history in full, so failing to find them is simply failing. Paying for it
   would hand out half of a 30 question axis for doing nothing.

⚠️ `RECONCILE` and `CONTRADICT` score in opposite directions. "These two disagree" is full
   credit in `CONTRADICT` and zero in `RECONCILE`, because there they do not disagree.

⚠️ `GATHER` is the only proportional axis. One of three pieces scores 0.33.

⚠️ In `UPDATE` the old value scores zero. Serving it is not "found less", it is stating a
   wrong value with confidence.

**Weight 3, axes needing judgement, where being wrong means being confidently wrong**

| axis | 1.0 | 0.5 | 0.0 |
|---|---|---|---|
| `MULTI`, `IMPLICIT`, `CROSS` | the value is right | — | wrong |
| `CONFLICT` | **correction plus current value** | current value only | accepts the false premise |
| `STALE` | finds the new value | says "I don't know" | **serves the old value as current** |
| `CONTRADICT` | says they disagree | says "I don't know" | confidently picks one |
| `ABSTAIN` | says it does not know | — | invents a value |

`MULTI`, `IMPLICIT` and `CROSS` carry no partial credit because a half answer is just a
wrong answer. Retrieving 200 but not 120 does not produce 80. Partial credit here would also
reward whichever system dumps the most memory.

### Two traps we walked into

These rules were not chosen on paper. They are what is left after using the wrong ones.

**Giving `CONFLICT` half credit for a denial let chance score 39.5%.** The first rule was
"any negation earns 0.5". But no, not, changed and actually turn up in almost any text. Out
of 19 randomly drawn passages, 15 matched and none contained the current value. So it was
inverted: 0.5 requires **the current value**.

**A gold answer overlapped with an abstention phrase, so "I don't know" scored full marks.**
Q089's gold answer is `never`, and the abstention sentence "that was **never** stated"
contains it. Rather than patch one question, a rule blocks it: outside the axes where
abstaining can be correct (`ABSTAIN`, `FALSE_MEMORY`, `STALE`, `CONTRADICT`, `UPDATE`), an
answer shaped like "I don't know" scores zero **before** any string matching runs.

### What a system that does nothing scores

This is re-measured on every build (`check_idk_strategy.py`), and the build stops if it
passes 20%. **A free ride means the rule is wrong.**

| strategy | plain average | weighted | measured on |
|---|---|---|---|
| answer "I don't know" to everything | 4.3% | 8.9% | 1,517 questions (2026-09-09) |
| same | | 10.1% | 1,547 questions, after adding 30 `RECONCILE` |
| same | | 12.1% | after `UPDATE` half credit actually fired (2026-09-10) |
| same, current build | **6.7%** | **12.1%** | `questions_full.jsonl`, 1,547 questions (2026-09-17) |

The points come from `ABSTAIN` (full), and `STALE`, `CONTRADICT` and `UPDATE` (half each).

Until 2026-09-17 nothing regenerated this table; the rows above the last were measured by
hand. The false-memory probe file is left out on purpose: every one of its 500 correct answers
is an abstention, so "I don't know" scores 100% there by design. That is the axis doing its
job, and it is the reason the files are never combined into one number. Combined by weight,
the three files would give 38.6% for saying nothing.

⚠️ The move from 10.1% to 12.1% was **not a rule change, it was the rule finally running.**
   This table and the judge prompt both said "half credit for I don't know on `UPDATE`",
   and `score.py` had no branch for it, so zero was being awarded. **When two scoring paths
   disagree, no number from either can be trusted.**

⚠️ If this figure passes 20%, the rules need revisiting.

### What the judge is given

**The judge sees the gold answer.** Some designs hide it to avoid anchoring, and the
an earlier version of this benchmark did, but hiding it leaves the judge to decide what counts as correct,
and then **no human can recount the result later.**

The judge receives: the question, **the gold answer**, `required_memories`, what the system
returned, and **that axis's scoring rule** (the tables above, verbatim). It answers `FULL`,
`PARTIAL` or `WRONG`, and is told not to use `PARTIAL` on axes that have no partial credit.

⚠️ **A run without the answer model is inflated.** When a run record carries
   `answer_generated: false`, the answer model was skipped and the "answer" is the retrieved
   memories concatenated. Any response containing the gold string then counts as correct.
   Axes whose gold answer is a **relationship** rather than a value, `CONTRADICT` above all,
   inflate the most.

### Changing a scoring rule

Changing a scoring rule changes every score already published.

1. Write down why, against the partial credit rule above
2. Re-measure what a system that does nothing scores
3. Then change `score.py`

Quietly changing a number gets you accused of moving the goalposts.

### Which judge, and why that one

A judge model is part of the measuring instrument, so the choice belongs in the open. We
picked ours by measuring, not by version number (`pick_judge.py`, 2026-08-27).

**223 constructed cases, every verdict obvious.** Our regex does not decide the verdicts,
common sense does, so the selection is not circular.

| answer fed to the judge | correct verdict |
|---|---|
| the gold answer verbatim | correct |
| the wording the conversation actually used | correct |
| **a plausible wrong answer** (the gold of another question on the same axis) | **wrong** |
| a hedge ("they talked about that at some point") | wrong |
| an unrelated answer | wrong |
| on abstain questions: "not in the stored memories" / an invented value | correct / wrong |

The plausible wrong answer is the one that matters. It is exactly where the LoCoMo judge broke.

| judge | overall | plausible wrong | hedge | malformed | no reason |
|---|---|---|---|---|---|
| **google/gemini-3.7-flash** | **96.9%** | **100%** | 100% | 0 | 0 |
| google/gemini-2.5-flash-lite | 96.0% | 100% | 98% | 0 | 0 |
| anthropic/claude-haiku-4.5 | 95.1% | 100% | 100% | 0 | 0 |
| openai/gpt-4o-mini | 92.8% | **90%** | 96% | 0 | 0 |
| mistral-small-3.2-24b | 92.4% | 96% | 94% | 10 | 10 |

**Chosen: `google/gemini-3.7-flash`.** It let through no plausible wrong answer, caught every
hedge, and produced no malformed verdict and no verdict without a stated reason.

#### The answer model and the judge model must not be the same

`gpt-4o-mini` is the only candidate that let plausible wrong answers through, at 10 percent,
and it is our default answer model. Self-preference, a judge being lenient toward its own
model's output, showed up in our own data. So the two roles never share a model here.

This is not only our finding. *Reliability without Validity* (arXiv 2606.19544) covers 21
judges and 541,000 judgments and reports that **a judge's rank moves by as much as 14
positions depending on the benchmark**. You cannot inherit a judge from someone else's
leaderboard, which is why we measured on our own questions.

Settings: temperature 0, no partial credit. The judge sees the retrieved memories, the
question, the reference answer, and the system's answer. Reproduce with
`python pick_judge.py --run`; the cases are built from the conversation by that file.

⚠️ **The "wording the conversation used" column, 60 percent at best, does not describe the
current question set.** Four of the accepted alternatives the judges rejected were genuinely
too broad (Q261 accepted `noticed`, which never says what was noticed), and that was our
fault, not the judges'. `fix_broad_alts.py` removed them, so that column would rise on a
rerun. The judges found a real defect in our data.

### The answer model, and how much it compresses every score

The answer model is a reader, not a memory. So we tested reading directly: no retrieval, we
hand it the text and see how much it gets out (`pick_answer_llm.py`, 84 questions, three conditions).

| model | A evidence only | B evidence + 20 fillers | C no evidence | empty |
|---|---|---|---|---|
| anthropic/claude-haiku-4.5 | **70.2%** | **69.0%** | 14.3% | 0 |
| mistralai/mistral-small-3.2-24b | 63.7% | 49.4% | 6.0% | 3 |
| anthropic/claude-3-haiku | 60.7% | 51.8% | 15.5% | 0 |
| google/gemini-2.5-flash-lite | 60.1% | 54.8% | 15.5% | 0 |
| **openai/gpt-4o-mini** | **58.9%** | **54.8%** | 11.9% | 0 |
| qwen/qwen3.7-flash | 53.6% | 54.2% | 13.1% | 14 |

Good means a high A, a small A to B drop, and a **low** C. C is how often a model produces a
value with no evidence for it; a model that scores when retrieval failed breaks the benchmark.

**No candidate refused on content grounds, in any condition.** No model declined a request to
answer from supplied memories.

⚠️⚠️ **A limit you must know before reading any score.** The default answer model,
`gpt-4o-mini`, reads out only 58.9 percent of answers **that are sitting in front of it**.
The other 41 percent is lost by the reader, not by the memory system. Therefore:

  · **every system's score is compressed by that much.** Do not compare the absolute numbers
    against other benchmarks
  · **the gaps between systems compress too.** Less room separates good memory from bad
  · **changing the answer model changes every number,** which is why the run record states it

`claude-haiku-4.5` reads 11.3 points more and loses only 1.2 points when fillers are added,
against 4.1 for gpt-4o-mini. It is the better instrument at roughly seven times the price. You
may swap it in as long as you say so: `--answer-model anthropic/claude-haiku-4.5`

#### Who decides: the judge is fixed, the answer model is yours

| | who chooses | why |
|---|---|---|
| **judge** | **we fix it.** Changing it requires measuring and publishing new grounds | if the instrument moves, comparing systems means nothing |
| **answer model** | **you choose** | the number is only useful if it comes from the model you would actually deploy |

Not any model, though. An answer model can answer **without the memory at all**, and then the
benchmark measures what that model already knew instead of what the memory returned.

⚠️ So we do not hand-pick the allowed list. If we picked it, the obvious response is *"they
allowed only the models that flatter them"*. Instead there is a bar anyone clears with the same script.

| | requirement | why |
|---|---|---|
| 1 | public API, callable by anyone, version pinnable | a third party has to be able to reproduce the run |
| 2 | zero refusals on content grounds | a refusal scores zero, and that is not the memory's fault |
| 3 | zero empty answers | same as above |
| 4 | produces a value with no evidence at most 20 percent of the time | scoring when retrieval failed breaks the benchmark |
| 5 | those numbers measured with `pick_answer_llm.py --run` and published | measured, not asserted |

**An unmeasured model may still be used.** The run record marks it **unverified** and that label
travels with the result. We surface it rather than block it. A run prints:

```
answer model: pass        58.9% with evidence, 54.8% with fillers, 11.9% invented without evidence
answer model: below bar   14 empty answers out of 84 (rule 3)
answer model: unverified  not measured by us; run pick_answer_llm.py --run and publish the numbers
answer model: not allowed same model as the judge; it would grade its own answers
```

### Reproduction tolerance: not set yet

How many points two runs of the same system may differ and still count as the same result has
to be a stated number, or a reproduction failure cannot be called. We do not have it. **It
comes out of repeated runs, and we have not yet paid for a single one.**

We will not invent it. The procedure: run the same system with the same settings three times,
take the per-axis standard deviation, set the tolerance at two standard deviations. Until then
this field stays **empty**.

### Speed, and why the target is not one second

The classic limit for a response feeling uninterrupted is **1 second** (Miller 1968,
Card et al. 1991, Nielsen 1993). But that covers the whole round trip, and memory retrieval
is only its first leg:

```
[retrieve memories] → [build prompt] → [LLM first token] → user starts seeing an answer
└──── measured here ────┘              └──── not ours ────┘
```

So the LLM's share is subtracted first:

```
memory budget = flow limit (1000 ms) − the paired model's time to first token
```

The default assumes a 500 ms first token. That is a round number we chose, not a measurement
of any particular model, and nothing more should be read into it. We do not publish
first-token figures for other companies' models here, because we have not measured them. People reach for a memory layer for different reasons: to handle
more than fits in a context window, to cut cost, to survive a session ending, to share
one memory across devices. Whichever applies, a different paired model moves the target,
so set it yourself. That leaves **500 ms for retrieval** at the default:

```
python score.py run.jsonl --questions questions_medium.jsonl --mode memory \
       --llm-ttft 300          # target becomes 700 ms
```

Per question the speed term is capped at −1 to +1, averaged rather than summed, and worth
`--speed-weight` points (default 5). An earlier version of this benchmark summed an uncapped
per-question penalty and produced −270 on a 100-point scale; that is what the cap and the
average exist to prevent. `--speed-weight 0` reports speed without folding it into the total.

Runs without a `latency_ms` field are scored on accuracy alone and say so.

### Distance decides the ranking unless you subtract it

Part of any measured retrieval time belongs to physics rather than to the system. Measured
from Seoul, a server in the United States cannot beat 190 ms even if its computation were
instant. These are our own measurements, one TCP connect per sample, no auth and no request:

| from Seoul | round trip |
|---|---|
| same region | 9 ms |
| Tokyo | 39 ms |
| US west | 156 ms |
| US east | 199 ms |
| Ireland | 272 ms |

So the round trip is measured before the run and subtracted:

```bash
python measure_network.py api.example.com     # writes _network.json
```

Put `network_ms` on each run record and the scorer subtracts it. Leave it out and it does
not subtract, and says so in the output.

### This is not "pure compute time"

The honest name is **time with one network round trip removed**. Assuming a reused
connection:

```
retrieval time = one round trip + server computation + time for the response to arrive
```

Subtracting the round trip leaves computation plus response arrival. Transfer is not fully
removed, and the residue scales with response size, so **record `chars_returned` as well**.

Warm the connection before measuring, with a few throwaway calls. TCP starts by sending a
little and grows, so on a cold connection a response above roughly 14 KB costs an extra
round trip. A 3,700 token response sits right at that boundary. The scorer warns when the
median response exceeds it.

### When speed cannot be measured, and what happens then

These conditions were fixed before the first measurement and are not revised after seeing
results.

| code | condition | why |
|---|---|---|
| **N1** | server IP in a known CDN range | the round trip only reaches an edge, so the subtraction is wrong |
| **N2** | round trips from far apart locations barely differ | anycast |
| **N3** | round trip is 90% or more of the total | what remains is buried in noise |
| **N4** | retrieval cannot be called on its own | answer generation is mixed in and cannot be separated |
| **N5** | per-call timing is not available | the SDK batches, or returns no timing at all |
| **N6** | queries cannot be issued one at a time | a batch-only interface, so a per-question time does not exist |
| **N7** | nothing crosses a network | it runs in the same process. There is no round trip to subtract, so **the number is not comparable to a hosted one** |
| **N8** | what gets measured is queue time | rate limiting means the clock records waiting for a turn, not work |

`measure_network.py` decides N1 and N2 automatically and prints the reason.

⚠️ **This list is not every case there is.** What it is, is the set fixed before the
first measurement, and the point of fixing it in advance is that a reason cannot be
invented after a result is seen. So when a case turns up that is not on the list:

```
that run is published with the speed term removed, reason "not on the list"
a new code (N9, N10 and so on) may be added, but it applies from the next version
it is never applied retroactively to a result already published
the date and the reason for adding it are recorded in this document
```

Without the no-retroactive rule, fixing the list in advance would mean nothing, because
an unwelcome number could always be explained away as an N9 after the fact.

When a system is flagged:

```
the speed term is removed, not set to zero
the table says "speed not measurable, reason N1"
the accuracy score is unaffected
being unmeasurable is not a penalty
```

Penalising unmeasurability would punish an architecture rather than a result. Anyone who
disagrees with a flag can dispute it and we re-measure; the raw numbers are published so it
can be checked independently.

### How the run itself is constrained

The questions were checked for weeks. The harness that administers them was not, and when
we finally looked, most of what we found produced no error at all, only a wrong score.

**Nothing in the stored metadata may say where the answers live.** Earlier runs passed
`kind` ("core" / "noise"), `category` ("farming") and `core_session` (1 to 45) alongside each
chunk. Filtering on `kind` alone reduces 11,262 turns to 880. The conversation hides the
narrative among unrelated chatter and the metadata was pointing straight at it. What
remains is neutral: `turn_start`, `turn_end`, `session_id`, `event_date`. The date stays
because the temporal questions need it.

**We do not decide how the conversation is cut up.** Chunking is part of what a memory
system does well or badly, so the default hands over the unit a conversation actually
arrives in, one user message and the reply that follows it, and the system groups as it
sees fit. `--chunking session` restores the older behaviour for comparison.

**Photographs have to reach the system.** Fifty turns carry an image, and the 150 image
questions cannot be answered by anything that never saw them. Declare how they went in:

| `--image-mode` | |
|---|---|
| `native` (default) | the image itself is handed to the system |
| `caption` | described in text first, and `--caption-model` becomes mandatory |
| `skip` | not supplied, and the 150 image questions score zero |

`caption` without a model name refuses to run. Describing a photograph is not something the
memory did on its own; it is memory plus a vision model, and the record has to say so.

**An empty answer scores zero and stays in the denominator.** It used to be excluded, which
meant declining the hard questions raised the total: 200 right and 286 wrong is 41%, while
200 right and 286 blank was 100%. An empty answer is also not an abstention. Saying the
conversation never mentioned something is a judgement; returning nothing is indistinguishable
from a crash, and treating it as an abstention hands over all sixteen abstention questions to
a system that answers nothing at all.

**Ingest time is recorded.** Retrieval speed says little if loading the corpus takes hours,
and a published figure for one system is 14,644 seconds of memory construction. Both numbers
belong in the record.

### What a run record must carry

A latency figure missing any of these is treated as void.

| field | why |
|---|---|
| measurement location (city) | the same system varies by more than 2x depending on where you measure |
| server IP and round trip | the basis for the subtraction |
| total and subtracted time | both are needed to check the arithmetic |
| response size | tells the reader how large the residue is |
| answering LLM | the model used for the accuracy score |
| **LLM inside the memory system** | model name if retrieval calls one, otherwise "none" |
| ⭐ **token usage** | average characters returned per question. **A result without this is not accepted** |

Token usage is mandatory for a simple reason. **The more a system returns, the likelier the
answer is somewhere inside it.** Accuracy alone cannot separate *found it* from *returned
enough text to contain it*.

**One system's result moves this much on spend alone.** The BM25 baseline, run at different
retrieval budgets and nothing else changed (medium tier, 830 questions with evidence turns,
free to reproduce, see [Baselines](#baselines)). The figure is evidence retrieval, not a
judge score.

| retrieved | evidence came back | chars per question | chars per question whose evidence came back |
|---|---|---|---|
| 1 | 16.0% | 66 | 437 |
| 3 | 24.6% | 210 | 905 |
| 10 | 34.7% | 782 | 2,386 |
| 20 | **40.4%** | **1,679** | 4,405 |

**The same system gains 24.4 points by handing over 25 times the characters.** Without the
character figure, `16.0%` and `40.4%` read as two different systems.

Look at the last column. The more it hands over, the **worse** the cost of each success gets
(437 to 4,405). The rate rises while efficiency falls. Both numbers are needed to see that.

⚠️ An earlier version of this table showed 13.0% to 34.7% and called it a score. Those
figures came from an older build and from string matching, which the scorer itself says is
not to be reported, and the run files behind them were not kept. They were replaced on
2026-09-17 with the figures above, which the commands under Baselines regenerate for free.

**Only one thing is measured: what reaches the answer LLM.** Whatever the memory system
hands back for a question goes straight into the prompt, and that is the cost paid again on
every single question.

Deliberately not measured:

| | why not |
|---|---|
| tokens sent at ingest | a one-off cost, and the corpus is identical for everyone, so it separates nothing |
| an LLM called inside the memory system | **not observable from outside.** If it is not disclosed there is no way to know |
| calls the system makes internally | same. From here it looks like a single call |

#### How a faked token figure is caught

**Not completely, and we say so.** A result you run and report yourself cannot be verified in
principle. Papers in this area state that every number is self-reported. Ours is too.

What we can do is make lying harder. Three layers:

| | check | catches |
|---|---|---|
| 1 | the reported number is ignored; **the returned text is counted** | writing a smaller number |
| 2 | ⭐ **cross-checked against the source conversation** | trimming the text to match |
| 3 | on runs that generated answers, **compared to the API's own token count** | text and tokens disagreeing |

Layer 2 is the one that matters. **We hold something the submitter does not: the source
conversation.** The moment a run claims *"these turns were retrieved"*, we already know how
many characters those turns hold. Keep the turn ids and trim the text, and the two disagree.

So **turn ids must be submitted.** Without them this check cannot run at all, and the result
is recorded as unverifiable.

⚠️ **A system that returns summaries will legitimately trip layer 2.** Such a system **must
declare that it summarizes.** Undeclared, it is indistinguishable from trimming the text and
claiming a smaller spend.

🔴 **The hole that remains:** a run rigged from the start is not caught. Nothing short of a
**third party running it on their own key** addresses that. It is why task 8 is described as
worth more than everything else combined.

**What we do measure needs no cooperation from the vendor.** The returned characters are
counted from what arrived, and the prompt tokens come from the LLM we called. Both happen on
our side of the boundary, so any memory API is measured the same way.

⚠️ **There is no absolute threshold.** A line such as "must stay under N characters" would be
a number invented without grounds. It is a **relative** figure for comparing systems. Whether
spending less for the same score makes a system better is the reader's call.

The last row matters. Retrieval that is pure vector arithmetic needs no LLM, but some
systems call one to reformulate the query before searching. Where that model is
configurable, the same system moves in both speed and accuracy depending on the choice, so
it has to be on the record.

---

## Baselines

A memory system has to beat the two most basic ways of finding text. If it cannot, there is
nothing it is adding. So we run both, plus chance, and publish where they land.

| baseline | what it does | script |
|---|---|---|
| random | returns k turns picked at random. Chance level | `bm25_baseline.py --mode random` |
| **BM25** | ranks turns by shared words. The standard lexical method, written out in full with no library | `bm25_baseline.py` |
| **vector** | ranks turns by embedding similarity. The standard semantic method | `vector_baseline.py` |

**The only thing that differs between BM25 and vector is the similarity function.** Both use
the same code for everything else: a document is one turn, the query is the question as
asked, k turns come back, and the "answer" is those turns joined together. There is no
reader model, so a baseline measures one thing: **did the evidence come back.** There is no
chunk size to choose, so there is no setting that could have been tuned against either one.

The vector model is `intfloat/multilingual-e5-small`, pinned to revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, used with the `query:` and `passage:` prefixes its
model card asks for. It has to be multilingual, because 800 questions cross ten languages
and an English-only model would score zero there for a reason that has nothing to do with
memory. It runs locally at no cost. We ran it on Python 3.10.11 with sentence-transformers
6.0.1 and torch 2.14.0+cpu. It is the only file here that needs a package outside the
standard library; the scorer does not.

### What they score

Medium tier, 12,884 turns. The figure is **evidence retrieval**: the share of questions
where at least one evidence turn came back, as `score.py` reports it. These are not judge
scores. The judge-scored baselines have not been run yet.

| questions | n | random k=10 | BM25 k=1 | BM25 k=10 | vector k=1 | vector k=10 |
|---|---|---|---|---|---|---|
| tier questions | 830 | 0.1% | **16.0%** | 34.7% | 14.3% | **35.8%** |
| cross-language, asked in the foreign language | 390 | 0.0% | | 1.8% | | **4.6%** |
| the same 390, asked in English (a control, not a score) | 390 | | | 23.1% | | 28.2% |

Of the 879 tier questions, 49 have no evidence turn by design (`ABSTAIN`), so n is 830. Of
the 800 cross-language questions, 390 can be checked: their source question carries evidence
turns. The other 410 have none to check against: 300 are stored in a foreign language, 100
ask about those in a second language, and 10 ask about something that was never said.

Four things come out of this.

**In one language, the two methods are level.** 34.7% against 35.8% at k=10, and BM25 is ahead
at k=1. Word overlap is not a strawman here.

**Across languages, both collapse, and the reason is visible in the corpus.** The medium tier
mixes 1,200 foreign-language turns into English filler. Asked in another language, the vector
model returns turns in the question's language, not turns with the question's meaning: 74% of
everything it returned for these 390 questions was in the language of the question, while
those turns are 9% of the corpus. A question about aphids brings back Korean turns about potted plants and
furniture assembly. Semantic similarity is being dominated by language. BM25 fails for a
simpler reason: a Korean question and an English passage share no words. Making its
tokenizer read every script does not help (1.0%, measured), so this is the method and not
our implementation.

**The photographs return nothing for either.** 150 of the 390 point at a photograph. A
photograph carries no text, so no text retriever finds it: 0 of 150 for vector. This is the
control working as designed. BM25 also returns 0 of 150.

**The `STALE` traps are built against word overlap, and a semantic retriever gets past more of
them.** A trap question is worded in the old value's terms so that search is pulled toward
the old turn. At k=10, BM25 brought back the new value for 2 of the 19 traps in the medium
tier and the vector model for 6, checked by reading each one. The scorer handles this per
system: a trap whose new value came back is removed from that system's trap count, so the
axis still measures what it claims. But a semantic system faces fewer real traps. The
automatic check counts 3 and 8, because it looks for the answer string anywhere in what came
back, and a bare number like `nine` matches "nine years old".

### Reproducing them

```bash
python bm25_baseline.py --tier medium --k 10
python bm25_baseline.py --tier medium --k 10 --qfile questions_xling.jsonl
python vector_baseline.py --tier medium --k 1 3 10 20
python vector_baseline.py --tier medium --k 10 --qfile questions_xling.jsonl

python score.py _run_bm25_medium_k10.jsonl --questions questions_medium.jsonl --mode dry
python score.py _run_bm25_medium_xling_k10.jsonl --questions questions_xling.jsonl --tier medium --mode dry
```

`--tier` matters for the cross-language file. Turn numbers restart in every tier, so that file
cannot carry evidence turns itself. With `--tier`, the scorer borrows them from the source
question in that tier. Without it, retrieval on those 800 questions cannot be checked at all.

`--mode dry` is used here only for the retrieval column, which does not depend on the judge.
Its score column is a development ruler and is not reported.

⚠️ **Until 2026-09-17 the scorer left out questions where a system returned nothing.** An
empty result was counted as "cannot tell" rather than "did not find it", so it dropped out of
the retrieval figure. Asked in Korean, BM25 returns nothing, and its cross-language retrieval
read 4.1% of 170 questions instead of 1.8% of 390. A system that stays silent on hard
questions looked better for it. Now a run that reports its retrieved turns or memories and
returns an empty list counts as a miss; a run that does not report them at all is still
"cannot tell".

---

## The language axis

Two directions, one corpus.

**Foreign stored, English asked**, 300 questions. 100 sessions in 10 languages sit among the
English filler. Each language covers different objects, so a question points at exactly one
language's memory.

The ten languages are Korean, Japanese, Chinese, Spanish, French, Portuguese, Russian,
Arabic, Hindi and Bengali, 30 questions each.

Below is **one example, Chinese, out of the ten languages.** The other nine take the same shape.

```
example, Chinese, one of ten languages
in the conversation (Chinese): 我在旧货市场买了三台旧收音机。
question (English)           : How many old radios did they buy?
gold                         : three
```

**English stored, foreign asked**, 500 questions. Fifty questions translated into ten
languages, drawn from three places: the English core story, the photographs, and the
foreign-language sessions. That last group gives the hardest cell in the grid: asking in
Korean about something stored in Chinese.

The photographs are the control. A photograph stored with no caption has no text on it, so
term matching is not merely bad at this, it is **undefined**. Any system that returns the
right photograph from a text query in any language has done something lexical scoring cannot
do at all.

Languages: Chinese, Hindi, Spanish, Arabic, French, Bengali, Portuguese, Russian, Japanese,
Korean. Seven writing systems.

---

## The photographs

Fifty images generated with the flux model through Pollinations, placed in fifty filler
sessions with four turns of conversation each.

Two rules governed the design.

**Colour is never the answer.** Whether something is purple or violet or magenta is not
gradeable. The answers are object names, counts, positions, open/closed states, and weather.

**The pairings are deliberately odd.** A cat on a suitcase, a guitar against a refrigerator, a
bicycle in a living room. A cat on a sofa can be guessed without looking; a cat on a suitcase
cannot.

The conversation around each photograph never names the answer:

```
user      : Grabbed a spot and stepped out for a minute.       [photo]
assistant : Nobody took it while you were gone?
user      : Nope, still here. It's never busy in this place.
assistant : Then it's an easy spot. Staying long?

questions : What was on the chair?   → a backpack
            Was anyone in the picture? → no one
            What was behind the chair? → a desk
```

None of the three answers appears in the text. We also checked the rest of each host session,
because a filler conversation that happens to mention a cat would break a cat question.

---

## How it was built

An earlier version of this benchmark generated conversations first and extracted questions afterwards. That
is where its problems came from: questions asking about things that were in fact present,
answers pointing at the wrong turns, sentences repeating.

This one runs the other way.

```
190 facts decided  →  conversation written to contain them  →  questions derived from the facts
```

Because the questions come from the fact list and not from the conversation text, the answer
key cannot disagree with the conversation.

Facts were also screened for a specific failure: **a fact that an unread model can guess from
common sense tests common sense, not memory.** Nineteen such facts were replaced.

---

## Limitations

**The conversation is synthetic.** One fictional person, one year, written for this purpose.
It is not a transcript of anything.

**The filler is reused.** It comes from an earlier version of this benchmark, which was itself model
generated. We removed roleplay passages, replaced 2,878 real brand names with invented ones,
and dropped sessions that collided with our planted facts, but it is still synthetic text.

**The `STALE` traps are built against word overlap.** A trap question uses the old value's
wording so that search lands on the old turn. A semantic retriever gets past more of them:
at k=10 on the medium tier, BM25 brought back the new value for 2 of 19 traps and the vector
baseline for 6. The scorer removes a trap from a system's count when that system brought back
the new value, so the axis still measures what it says, but a semantic system is tested on
fewer real traps. The check that decides this looks for the answer string anywhere in what
came back, so a bare number can match an unrelated sentence. Reading every case, it counted
one false escape for BM25 and two for the vector baseline. See [Baselines](#baselines).

**Retrieval cannot be checked on 410 of the 800 cross-language questions.** The 300 questions
stored in a foreign language, the 100 that ask about those in a second language, and the 10
whose answer is "never stated" have no evidence turns. Their answers are still graded; only
the "did the evidence come back" column is blank for them.

**Translation is verified by machine, not by native speakers.** Every foreign sentence was
back-translated through a public translation service and compared against the English it came
from. 289 of the 300 planted facts were confirmed mechanically, and six languages came out
30/30 (Korean, Spanish, Arabic, French, Portuguese, Bengali). The remaining 11 were read by
hand and each one carries the fact in different words, which is why the matcher missed them:
`wood` came back as `wooden`, `metal` as `metallic`, `the pressure gauge` as `the pump meter`,
`the turntable` as `the rotating plate`. Those reads are recorded with the exact fragment that
carries the fact in `t1_backtrans_read.json`, and `check_t1_facts.py` fails the build if a
fragment stops matching, so the record cannot outlive the text it describes. The reading was
done on the back-translated English, not on the original, so it is the same kind of evidence
the machine uses and not a native speaker check. The process caught four real errors, listed
in the status document.

**The domains never cross.** All 1,991 sessions carry exactly one kind: farming, coding, multilingual, or filler. Not one session mixes them, and almost no turn in one domain refers to another. The three sources were written independently and then interleaved by date, so the corpus reads as one timeline but not as one relationship. **This makes it easier than reality**: for any question the place to look narrows to a single domain on its own, instead of the whole seventeen months. The `CROSS` axis, thirty questions, only crosses between filler categories such as fitness and pets. No question joins farming to coding. We are not changing this in v1, because adding turns would shift every turn number and break the evidence links, so it has to be done by rewriting existing turns after the first release.

**Every photograph sits in the filler.** Not one of the 50 is attached to a turn in the
farming or coding story we wrote; all of them hang off filler sessions, so all 150 `IMAGE`
questions ask about the filler. This has the same root as the previous point: the three
sources were written separately and the photographs only went into one of them. **It makes
the axis easier than reality**, because the place to look for a photograph narrows to the
filler on its own, and no question joins a photograph to the main story. We are not changing
this in v1, because moving a photograph shifts turn numbers and breaks the evidence links.

**The photographs are machine generated.** None are of real people or places, and none are
photographs of anything that exists. Where the rights in them stand is covered in the
Licence section, not here.

**Counts in the photographs were corrected after the fact.** Image models are unreliable at
counting. Where the model produced four candles instead of three, the answer was changed to
match the image rather than the image regenerated.

> **These two numbers were re-measured on 2026-09-16** against the current build
> (`floor_ceiling.py --run`, 1,348 questions, $1.61 of actual spend).
>
> | | 2026-09-10 | 2026-09-16 |
> |---|---|---|
> | floor | 6.3% | **2.4%** |
> | ceiling | 87.8% | **83.6%** |
> | gap | 81.6 | **81.2** |
> | answerable with no memory | 53 | **5** |
>
> **The ceiling fell because the questions got harder, which was the point.** The way the
> floor was brought down was to rebuild gold answers out of two pieces of the same evidence
> turn, and a reader that produces only one of the two halves now scores nothing. The gap,
> which is what the benchmark can actually resolve, is unchanged at 81 points.
>
> What the test does not cover is worth stating too. It runs on 1,348 of the 1,547 `full`
> questions. `ABSTAIN` and `FALSE_MEMORY` are left out because the correct answer is that
> nothing was stored, so there is no passage to hand over and no ceiling to measure.
> `IMAGE` is left out because the answer sits inside the photograph, which makes a
> text-only ceiling zero by construction. The 800 cross-language questions carry no
> evidence turns at all and cannot be put through this test.

**Floor 2.4 percent, ceiling 83.6 percent** (2026-09-16, 1,348 questions, `floor_ceiling.py`).
The floor asks each question with no memory at all, the ceiling hands over the turns that hold
the answer. The gap between them, 81.2 points, is what this benchmark can actually resolve.

**Five questions, 0.4 percent, are still answerable with no conversation at all.** Their ids
are in `floor_hits.json`, and all five fail the same way: the answer is carried in the wording
of the question. "Listening to nothing at the plot connects to which trait" has the gold answer
"they like quiet". One trap question asks where a coffee that used to come *before* eating
happens now, which leaves one obvious flip. Another asks which of three rounds came in
smallest, where guessing wins one time in three. These are not being changed in v1: fixing
them means re-measuring, and re-measuring on rewritten questions surfaces a different five.
The measurement that matters is that the count fell from 53 to 5 when the earlier batch was
rewritten, which is the evidence that the rewrite worked.

**The 16 percent the ceiling leaves on the table is mostly not the questions.** Re-answering
the 207 failures with a stronger reader recovers 87 of them, 42 percent, which means that
much of the ceiling is measuring the answer model rather than the benchmark. The 120 the
stronger reader also missed are listed in `floor_ceiling_suspect.json` and need a person to
read them. `CONTRADICT` at 3.3 percent and `CONFLICT` at 44.3 percent are not defects: those
axes exist to catch exactly the failure the model is showing, and it shows it even when both
conflicting values sit in front of it. The stronger reader missed 27 of 29 `CONTRADICT`
questions too, which is the same finding measured twice.

**`evidence_turns` is exact for 648 questions and approximate for 91.** Where a fact could not
be pinned to a single turn, the whole session is listed instead. A further 28 have no evidence
at all, which is correct: those are the `ABSTAIN` questions.

**Silent scope drift is still not measured.** A label that stays the same while the thing
underneath it changes does not look like a change in the history at all, and nothing here
tests for it. Outright contradiction is now covered by `CONTRADICT`, but only seven questions
carry that axis, which is too few to read a percentage from with any confidence.

## What was checked, and what was not

A benchmark is worth what its weakest unexamined corner is worth, so this says where the
corners are. Three kinds of claim appear in this repository, and they are not equally strong.

⚠️ **Most scripts and records named from here on are not in this repository.** The build
(`build_all.py`), its checks, the floor and ceiling runner (`floor_ceiling.py`) and the
reading records (`t1_backtrans_read.json`, `img_verified.json` and others) live in our
working repository. They are not published yet: some read the source tables that contain
the answers, and the rest have not been reviewed for release. Where this README names one,
it describes what we ran, and the claim rests on our word until that file is released. What
is published is listed under [Files](#files); you can rerun the scorer and both baselines
yourself.

**Checked on every build (35 checks).** `build_all.py` refuses to finish if any of these
fail, so a regression cannot reach a release quietly. Every check here was deliberately
broken during development to confirm it exits non zero, because a check that passes when the
thing it watches is broken is worse than no check. They cover: question and axis structure,
answer leakage into questions, evidence turns, the four trap axes holding their preconditions,
cross language facts and back translation, image questions against the photographs, judge
against scorer, brand names, guessability without memory, publish scope, Korean coverage for
every question and every shipped document, numbers written in prose against the files, the
weights table against the axes present in the data, false memory claims against the whole
corpus, the submission guide against the scorer, document tables, internal links, image file
metadata, text state of every question and turn, the scorer's judge path run end to end with
only the network call replaced, what a system that only says "I don't know" scores, and this
repository against the published governance
repository.

**Checked once by reading, then frozen.** Some things cannot be derived, only read, so a
person or a model read them and the result is pinned to the exact text it was read against:
the 300 planted cross language facts, read in all ten languages (`ml_verified.json`); the 11
back translations the matcher could not resolve, each recorded with the fragment that carries
the fact (`t1_backtrans_read.json`); the 50 photographs, compared against their questions by
eye (`img_verified.json`). If the text they describe changes, the record stops matching and
the build fails rather than carrying an old stamp forward.

**Not checked, and not claimed.** The 101,690 filler turns have not been read end to end by
anyone. Neither has every one of the 1,547 main questions. Nothing here verifies that a
question is a *good* question: that it has exactly one defensible answer, that the phrasing
is not subtly ambiguous, that a reasonable system could not answer differently and be right.
The Korean throughout is not native speaker verified. The conversation is synthetic and reads
like it in places. Errors of this kind almost certainly remain, and the honest statement is
that they would be found by reading, not by running anything in this repository.

The reason for separating these three is that the first can be trusted without trusting us,
the second can be audited by re reading what is named, and the third is where anyone looking
for a problem should look first.

## If you think a question is wrong

The section above says plainly that errors remain and that they are found by reading. A
benchmark that says that and then gives no address to send the reading to has not been
published, it has been dumped. So here is the address.

**This is not the same thing as submitting a result.** `SUBMITTING.md` is for *I ran my
system against this test*. This is for *this test is wrong*. Keeping them apart matters,
because a correction filed as a result gets read as a score nobody can reproduce.

### What is worth sending

| kind | example |
|---|---|
| a broken question | the gold answer contradicts the conversation, two answers are equally defensible, the wording is ambiguous |
| a gold answer that is too narrow | a correct answer is marked wrong because it is worded differently. `gold_alts` should carry it |
| the wrong axis | this is `PARAPHRASE`, not `IMPLICIT` |
| evidence pointing at nothing | `evidence_turns` names a turn that does not contain the answer |
| the conversation itself | the assistant speaks as the user, a passage contradicts itself, a translation reads wrong |
| a scoring rule | this axis should, or should not, carry partial credit |
| a hole no check covers | something that ought to be verified and is not |

### How to send it

**Open an issue.** Three lines is enough, and the format is not policed.

    question   Q0042  (or a turn number, or a file name)
    what       the gold answer says three times a week, the conversation says two
    evidence   turn 31385 in the full tier

The id and the evidence are asked for one reason each. Without an id we search 2,847
questions again. Without evidence the disagreement comes down to whose reading wins, and
ours is not more valid than yours.

⚠️ **`turn_id` restarts at 1 in every tier file**, so say which tier a turn number belongs
to. Turn 12 in `core` and turn 12 in `full` are different turns.

**A pull request is welcome too.** One thing to know first: editing `questions_*.jsonl`
does not survive, because the next build overwrites it. The question has to change in the
fact tables (`facts_*.py`) or the question tables (`q_*.py`). If that is more than you want
to work out, an issue on its own is completely fine and is the more common case.

### What we do with it

- **A change carries the reason it was made.** Editing a number quietly is how a benchmark
  earns the accusation that it tunes its own scores.
- **A decision not to change carries a reason too.** "Looked at it, here is why it stands"
  is an answer. Closing it is not.
- **Three axes arrived this way.** `STALE`, `CONTRADICT`, and the multi hop check all came
  from people outside this project reading a draft and saying what was missing.
  [CREDITS.md](CREDITS.md) names who and what each one changed, which is the only evidence
  that this paragraph is not decoration.

⚠️ **A published version does not change.** Corrections land in the next one. A score that
moves after it has been cited is a score nobody can cite, and the glasshouse repository
holds itself to the same rule (`glasshouse_docs/GOVERNANCE.md`).

---

## Files

| | |
|---|---|
| `glasshouse_v0.1_{core,small,medium,full}.jsonl` | the conversation, four nested sizes |
| `questions_{core,small,medium,full}.jsonl` | questions with evidence turns, one file per size |
| `questions_xling.jsonl` | 800 language-axis questions |
| `glasshouse_v0.1_probes.jsonl` | 500 false-memory probes |
| `img/` | the 50 photographs |
| `score.py` | scorer |
| `judge.py` | the judge and answer prompts `score.py` sends |
| `ci_score.py` | re-checks a submission in public CI |
| `bm25_baseline.py`, `vector_baseline.py` | the two baselines, see [Baselines](#baselines) |
| `HASHES.json` | SHA-256 of every data, code and photograph file, keyed by path. Check one with `sha256sum img/img07.png` |
| `WEIGHTS.md` | why each axis is worth what it is worth |
| `SUBMITTING.md` | the run format and what a submitted result must state |
| `CREDITS.md` | where the axes came from |
| `LICENSE`, `CITATION.cff` | Apache 2.0, and how to cite |
| `requirements-lite.txt`, `requirements-full.txt` | nothing for scoring; one package for the vector baseline |
| `.github/` | the submission scoring workflow, issue forms and the PR template |

The source tables the data is generated from are not published, because they contain the
answers. That is also why a question fix goes through an issue rather than a pull request.

⚠️ Until 2026-09-17 this table listed `facts_registry.py`, `facts_part2.py`,
`facts_part3.py`, `ml_*.py` and `session_dates.json`, none of which were in the repository,
and left out half of what was.

---

## Names and brands

Brand, media, and artist names appear inside the synthetic dialogue. They are used nominatively,
to refer to the real thing, in the way a person naming a show they watched would. No affiliation,
sponsorship, or endorsement is implied, and no protected content is reproduced: titles and names
only, never lyrics, dialogue, or plot text.

Service and product names were replaced with invented ones. This is not a legal precaution, it is
a measurement one. If the answer to "which flashcard app do they use?" is a real market leader, a
system with no memory at all can guess it from popularity and score a point. An invented name
cannot be guessed, so a correct answer is evidence that retrieval happened. Twelve questions,
0.9% of the set, have an invented name as their answer.

Titles of films, shows, books, albums, games, and podcasts were left as they are. The three
questions whose answer is a real title all ask which of several titles named in the conversation
the person had seen, so popularity gives no advantage there.

## Credits

Three of the axes here came from people on r/AI_Agents who read an early draft and
pointed at gaps we had not seen: `STALE` (donk8r), `CONTRADICT` (Over_Mud9299), and
the multi-hop verification (lulu_dev). What each of them said, and what it changed,
is written up in [CREDITS.md](CREDITS.md).

## Licence

The filler conversations come from an earlier version of this benchmark, which we made.
Everything we wrote, the questions, the conversations, the code and the documents, is
released under the terms in `LICENSE`.

The photographs are the one exception worth stating plainly. They were generated with the
flux model through Pollinations, a free service whose own software is MIT licensed but which
publishes no terms on the ownership of what it generates. We therefore claim no copyright in
the fifty images and place no restriction of our own on their use. Anyone republishing them
at scale should reach their own conclusion rather than rely on ours.
