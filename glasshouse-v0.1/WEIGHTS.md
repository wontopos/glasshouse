# Why the weights are what they are

In glasshouse v0.1 **questions are not all worth the same.** A question on a hard axis is
worth more than a question on an easy one, the way an essay question is worth more than a
multiple choice one.

    score = Σ(weight of the question × correct) / Σ(weight of the question)

The unweighted average is **always reported next to it.** When the two differ, the gap is
information in itself: a system that earned its score on the easy axes gets a lower
weighted score.

---

## The table

| weight | axis | |
|---|---|---|
| **1** | `BASIC` | retrieve what was said, as it was said |
| | `PARAPHRASE` | understand something said in other words, within one turn |
| | `IMAGE` | remember one photograph |
| **2** | `TEMPORAL` | what came first, and how long it took |
| | `UPDATE` | know a value changed, and give the new one |
| | `GATHER` | bring back every piece spread across two turns |
| | `RECONCILE` | explain why two statements that look incompatible are both true |
| **3** | `MULTI` | compute a new value from two facts |
| | `IMPLICIT` | combine scattered facts into something never written down |
| | `CROSS` | connect facts from different areas of life |
| | `CONFLICT` | correct a false premise when one is put forward |
| | `STALE` | not insist on the old value when the new one cannot be found |
| | `CONTRADICT` | say the facts disagree when there is no answer |
| | `ABSTAIN` | not invent what was never stored |
| **3** | `FALSE_MEMORY` | not agree to something that was never said, even when pressed |
| **1** | `XLING_QUERY` | find it when asked in another language |
| | `XLING_STORE` | find what was stored in another language when asked in English |

> ### These three were set on 2026-09-16
>
> `FALSE_MEMORY` (500), `XLING_QUERY` (500) and `XLING_STORE` (300) were **added after**
> the fourteen main axes, and nobody put them in the table. The scorer counts an axis that
> is missing from the table as 1.0, so **1,300 questions (46% of the total)** were being
> scored with a weight **nobody had chosen.** No number was wrong; nobody had picked one.
>
> They are chosen now, and **no new rule was made for it.** The rule below, "one rule
> decided it", was applied as it stands: **not how hard a question is, but what happens
> when a system gets it wrong.**
>
> | axis | weight | why |
> |---|---|---|
> | `FALSE_MEMORY` | **1 → 3** | Getting it wrong means **agreeing to something that was never said and filling in details.** That is the same failure as `ABSTAIN` ("do not invent what was never stored"), which is already 3. And because the question asserts the false thing first, the system has to **contradict the user**, which makes it harder than `ABSTAIN`, not easier |
> | `XLING_QUERY` | **stays 1** | A system that cannot cross the language finds nothing and says **"I don't know".** The user can ask again. **It does not fail confidently** |
> | `XLING_STORE` | **stays 1** | as above |
>
> ⚠️ **A proposal to set the cross-language axes to 2 came first and was withdrawn.** Its
> reason was "it feels harder", and **difficulty is not what this table rewards.** Hard and
> dangerous are different things, and the table rewards the dangerous. The difficulty of the
> cross-language axes lies **in finding the turn**, not in anything after finding it, so they
> fit the definition of weight 1 ("once found, done") exactly.
>
> That gives a total of 4,655 points (`FALSE_MEMORY` adds 500 questions × 2).
> **Having been set, they will not be changed.**
>
> ⚠️⚠️ **But these three weights change no number the scorer produces (checked on
> 2026-09-17).** The scorer scores **one question file at a time,** and a weight only
> matters **between axes inside one file.**
>
> - `FALSE_MEMORY` is **alone** in the probe file, so weighted equals unweighted
> - `XLING_QUERY` and `XLING_STORE` share the cross-language file and are both 1, so
>   weighted equals unweighted
>
> So the total of 4,655 is **arithmetic across three files that nothing adds together**
> (see "no single headline number" in the README). Raising `FALSE_MEMORY` to 3 follows the
> rule, **but it did not move any score.** It was said on the day that changing it would
> move published scores; that was wrong.
>
> **There is a second reason not to add the files together.** All 500 probes have "never
> stated" as the correct answer, so a system that says "I don't know" to everything gets
> 100% there. Added together by weight, the three files would give a system that does
> nothing more than 38% (`check_idk_strategy.py` prints this on every build).
>
> `check_axis_weights.py` stops the build whenever an axis is added without a weight.

---

## One rule decided it

**Is the question done once the right turn is found, or does something still have to be
done after finding it?**

The rule was chosen because **the second kind is where things go wrong in practice.** A
system that fails the first kind cannot answer. A system that fails the second kind **answers
wrongly and confidently,** and the user has no way to tell.

### Weight 1: done once found

The answer sits in the conversation as it was said. Bring back that turn and the answer is
there. Fail to bring it back and the system says "I don't know", and the user can ask again.
**Failing is not dangerous.**

Why `PARAPHRASE` is here: the answer is written in the turn. The question does not share
its words, so it has to be understood by meaning. That is harder, but **there is still only
one place to look.**

Why `IMAGE` is here: one photograph is the evidence. Nothing is combined.

### Weight 2: one more step after finding it

What comes back is not the answer yet. **Time, change or count has to be checked once
more.**

- `TEMPORAL` decide which of two moments came first
- `UPDATE` choose the **new** value between the old and new values of the same thing
- `GATHER` check every piece is there. Bringing back one and stopping scores zero
- `RECONCILE` explain that two statements that seem to clash both hold

When these fail, **it usually shows.** "That was last month, though" is something the user
notices.

### Weight 3: judgement after finding it. Failure is confident

This is why the benchmark exists.

- `MULTI` compute from two facts. Finding only one produces **a plausible wrong answer**
- `IMPLICIT` infer what was never written. Easy to make something up
- `CROSS` connect different areas. Looking at one side leads to a confident wrong answer
- `CONFLICT` accepting a false premise **hardens the user's mistake**
- `STALE` gives the old value as current. The user believes it is up to date
- `CONTRADICT` there is no answer, and the system picks one anyway
- `ABSTAIN` invents something that was never stored

⚠️ These seven **do not look wrong.** In a medical record or a contract, the user would
   simply believe them. That is worse than the weight 1 failure ("I don't know").

---

## What else was considered

### ① Penalties: not used

An earlier version deducted **−0.25** for each false memory, on the grounds that inventing
something is 2.5 times as harmful as failing to find it. That judgement is right.

**It is not used because it broke in practice.** On the earlier version's 2,708-question set,
with a speed penalty added, it produced **−270.8 out of 100.** The penalty grew automatically
with the number of questions.

The same aim is met by **reporting each axis separately.** A low `ABSTAIN` accuracy already
means "it invents things", and that shows where the problem is more clearly than a penalty
folded into one number.

### ② Weighting per-axis accuracy: used once, then changed

On 2026-09-08 the score was a weighted average of **per-axis accuracy.** That gives an axis
with 7 questions the same share of the total as an axis with 733.

Why it changed: **the number of questions stops mattering.** However many questions are
written, the total does not move, so there is no reason to write more. And letting a
7-question axis decide 1/13 of the total is risky given how much that axis moves on its own
(one question is 14 points).

Instead, **every axis is filled to at least 30 questions,** so the counts do not drift too far
apart. (Operator's decision, 2026-09-09.)

---

## How the weights change results

**There is no number to show yet.** How weighting changes a score can only be shown with
**judge-scored results,** and the baselines have not been scored by the judge yet (it costs
money).

⚠️⚠️ **The example that used to be here was removed on 2026-09-17.** It said "BM25 unweighted
24.6 → weighted 20.9, `BASIC` 36.1%, `IMPLICIT` 4.3%, `MULTI` 5.1%". Three things were wrong
with it.

- **There is no source file.** It was measured on an older build on 2026-09-09 and the run
  was not kept
- **It came from string matching (`dry`),** which the scorer itself says is not to be
  reported
- **Measured again with the yardstick available today, it comes out the other way.** A
  baseline has no answering model, so the only thing it can be measured on is whether the
  evidence came back. Weighting that **raises** the figure: BM25 34.7 → 36.6, vector
  35.8 → 38.9 (medium tier, k=10, from the per-axis figures in the baseline summaries). Hard
  axes such as `MULTI` and `IMPLICIT` have several evidence turns, so **touching any one of
  them counts as found.** Weights price **the risk of being wrong,** not retrieval, so the
  comparison never meant anything

The floor and ceiling (2.4 / 83.6) do not involve weights. `floor_ceiling.py` does not use
them, and it skips `ABSTAIN`, `FALSE_MEMORY` and `IMAGE` on purpose (their correct evidence
is **nothing**, so a ceiling test cannot be set up for them).

---

## Changing this table

Changing a weight **changes every published score** that mixes axes. To change one, first
change the rule above, write down here why, and only then change the weight. Quietly
changing a number reads as adjusting the score.

The weights live in one place only: `AXIS_WEIGHT` in `score.py`.

`check_axis_weights.py`, `check_idk_strategy.py` and `floor_ceiling.py`, named above, are part
of our build and are not in this repository; see "What was checked, and what was not" in the
README.
