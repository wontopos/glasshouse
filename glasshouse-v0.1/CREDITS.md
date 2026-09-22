# Credits

glasshouse v0.1 did not come only from us. It owes two things.

1. **People who read the draft and pointed at gaps.** Three axes and one check came from them.
2. **Public posts that set the direction.** What to measure was decided there.

**About the wording below.** The comments were written in English on Reddit. What we kept was
a translated summary, not the original text, and Reddit blocks automated fetching, so we
cannot reproduce anyone's exact words. Each point below is therefore **our paraphrase,
labelled as such,** with a link to the original. Nothing here is a quotation.

The links were copied from the operator's browser on 2026-09-11.

---

## People who corrected the draft

These came from posting the draft to r/AI_Agents. All three touched places **we believed
were already covered.** Every check was passing; the checks were simply not asking these
questions.

### donk8r: the `STALE` axis

r/AI_Agents, 2026-09-01, [Been building a long term memory benchmark, what would you add to it](https://www.reddit.com/r/AI_Agents/comments/1w402xm/been_building_a_long_term_memory_benchmark_what/)

**The point (paraphrased).** Value changes and "I don't know" were already covered; the gap
is between them. A system that gets "the value changed" right may just be good at search.
Add cases where a newer value exists but is deliberately hard to find, and see whether the
system says it does not know or presents the old value as current. The second failure is
the one that hurts in practice, and the design could not tell it apart from good search.

**What it changed.** The `STALE` axis, 30 questions (11 farming, 7 coding, 12 filler). Each
question is worded in the old value's terms, so search is pulled toward the old turn. It is
the only axis with three outcomes.

| answer | score | |
|---|---|---|
| gives the new value | 1.0 | found it although it was hard to find |
| says it does not know | 0.5 | search failed, nothing was invented |
| gives the old value as current | 0.0 | confidently wrong |

**A second point changed the scoring.** Counting traps that did not catch a system in the
denominator makes a system with better search look less prone to insisting on the old value.
So a question whose new value the system actually retrieved is removed from that system's
trap count. Counting it the old way had understated the failure.

donk8r also noted that this holds for a word-overlap retriever, and that an embedding
retriever might simply find the new value. That warning is in the scorer's output and in the
README, and the vector baseline has since measured it: at k=10 on the medium tier it
retrieved the new value for 6 of 19 traps, against 2 for BM25.

### Over_Mud9299: the `CONTRADICT` axis

r/AI_Agents, 2026-09-07, [What's in the memory benchmark I've been building, and what I might still be missing](https://www.reddit.com/r/AI_Agents/comments/1w9m56g/whats_in_the_memory_benchmark_ive_been_building/)

**The point (paraphrased).** Contradiction handling was missing: when two stored facts
directly conflict, check whether the system flags the conflict instead of confidently
picking one.

**What it changed.** The `CONTRADICT` axis, 30 questions (7 farming, 23 planted in the
filler). **It is the only axis with no correct value.** In spring the user says 200 seeds, a
few weeks later 300, nobody notices, and nothing in the conversation says which is right.
Saying the two disagree scores 1.0.

A build check confirms every time that **nothing in the conversation corrects either
side.** The moment someone says "I said that wrong earlier", it is an update, not a
contradiction.

The mirror image, `RECONCILE` (30 questions), grew out of the same point: two statements
that look like a collision but are both true under different conditions.

⚠️ `core` and `medium` hold only 7 of these, too few to read as a rate at those tiers.
`full` holds all 30.

### lulu_dev: the multi-hop check

r/AI_Agents, 2026-09-01, [Been building a long term memory benchmark, what would you add to it](https://www.reddit.com/r/AI_Agents/comments/1w402xm/been_building_a_long_term_memory_benchmark_what/)
(the same thread as donk8r)

**The point (paraphrased).** A multi-hop question only measures multi-hop if no single hop
gives the answer on its own. If a hint leaks into one side, a system takes the shortcut and
it gets scored as multi-hop success.

**What it changed.** Not an axis, **a check.** Its first runs found the same shape again and
again: the user states a value and **the assistant finishes the arithmetic in the very next
turn** ("so about $320 for eight"). One assistant turn was enough to answer. 11 questions
turned out to be single-hop and were moved to `BASIC` rather than dropped (`MULTI` went from
70 to 59).

It also **changed how evidence turns are attached.** The code that picked evidence was
searching for "the turn that contains the answer text", but a real multi-hop answer is in no
single turn, so it pinned the wrong turns. Q217 (answer $150) was pinned to a turn that
mentioned **$150 for seedlings** instead of the savings turns. The number matched by chance.

---

## Public posts that set the direction

From 144 memory-related posts the operator collected between 2026-07-26 and 2026-08-11,
these are the Reddit posts that actually reached the design.

⚠️ **Every number in the "the point" column is the author's own report, and we have not
re-measured any of them.** They are not our results and they are not verified. They are
listed to show **where the design came from,** not as evidence. Nothing in this repository
cites them to support a claim.

⚠️ The starting point for `IMPLICIT` and `CROSS` did not come from Reddit, so they are not in
this table.

| person | post | the point (paraphrased, self-reported, unverified) | what it became |
|---|---|---|---|
| **fanaticalspectre0294** | [Been building a long term memory benchmark, what would you add to it](https://www.reddit.com/r/AI_Agents/comments/1w402xm/) (2026-09-01, a comment on our post) | **Multi-hop where the clues are weeks apart.** A favourite band is named in April, a concert comes up in July, and the band is never named again | the multi-hop question type |
| **Future_AGI** | [every agent memory system is benchmarked on...](https://www.reddit.com/r/AI_Agents/comments/1vfbda5/every_agent_memory_system_is_benchmarked_on/) (2026-08-05) | Every system reports recall, but nobody asks whether what it recalls **is still true.** Self-reported: after changing 40 of 50 facts, an append-only vector store returned the stale value 68% of the time | the starting point for `UPDATE` and `STALE` |
| **Major-Shirt-8227** | [i ran 8 ai agent memory systems through 2176...](https://www.reddit.com/r/AI_Agents/comments/1veeix3/i_ran_8_ai_agent_memory_systems_through_2176/) (2026-08-04) | Mixed in 72 questions about facts that were never stored, to **catch invented memories.** Self-reported: the winner was not a product but a markdown wiki the agent wrote for itself | `ABSTAIN` and the 500 false-memory probes |
| **san2build** | [how ai memory should behave](https://www.reddit.com/r/AI_Agents/comments/1var236/how_ai_memory_should_behave/) (2026-07-31) | How to measure long-term quality **after months of real conversation,** rather than on a benchmark | why the corpus spans 490 to 530 days and over 100,000 turns |
| **gimalay** | [every agent memory tutorial starts with a vector](https://www.reddit.com/r/AI_Agents/comments/1vd6l4s/every_agent_memory_tutorial_starts_with_a_vector/) (2026-08-02) | Most of what an agent needs to recall is **a WHERE clause, not a similarity search** | background; it did not become a specific axis |

⚠️ **Two claims that came out of that survey were wrong.** "Nobody measures whether stale
information is filtered" and "nobody measures whether a system invents things" are both
already items in LongMemEval. The operator caught them in a fact check. The lesson at the time
was that **claims that cited a paper held up, and claims made on instinct did not.**

---

## Summary

⚠️ **The published glasshouse repository's `individuals/v0.1/2026-09.md` is the reference for
this table.** Checked against it on 2026-09-15, two things were brought in line.

- **fanaticalspectre0294 was missing from our record.** The published file has them.
- **Future AGI is listed there as a company, not an individual** (`companies/future-agi.md`).
  On 2026-09-08 they offered to contribute an execution layer. Giving an idea and taking part
  as a company are different things, so this table keeps only the idea.

| | the gap | the result |
|---|---|---|
| donk8r | a search failure could not be told apart | `STALE`, 30 questions, and the per-system trap precondition |
| fanaticalspectre0294 | multi-hop with clues weeks apart | the multi-hop question type |
| Over_Mud9299 | contradiction handling was missing | `CONTRADICT`, 30 questions, and its check; the mirror image `RECONCILE`, 30 questions, came from the same point |
| lulu_dev | the multi-hop was not really multi-hop | the multi-hop check, and 11 questions reclassified |
| Future_AGI | recall is measured, whether it is still true is not | `UPDATE` and `STALE` |
| Major-Shirt-8227 | invented memories need catching | `ABSTAIN` and the 500 probes |
| san2build | measure on months of real conversation | a corpus of 103,572 turns spanning 490 days (core) to 530 days (full) |
