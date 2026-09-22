<!--
  Pull request template for the published repository (.github/pull_request_template.md).

  Not standard practice: of seven benchmark repositories checked on 2026-09-16, two had
  one (openai/evals, mem0). huggingface/datasets, lm-evaluation-harness, BIG-bench, HELM
  and zep had none. openai/evals is where people send new content, and its template is an
  acceptance checklist; this repository receives fixes to content, which is the same
  situation.

  It exists for one reason: the data files are generated, so a pull request that edits
  them would be overwritten on the next build and the contributor's work would be lost.
  The template sends data fixes to an issue instead.

  There is no rule that pull requests not following the template are closed. None has
  been received yet, and setting rules before seeing any means only what fits the rules
  gets in, while the most important reports tend to arrive in a shape nobody expected.
-->

## What this changes

<!-- One or two lines. -->

## Why

<!-- What was wrong. An issue number is enough if there is one. -->

## Evidence

<!--
  A turn number, or a sentence copied from the conversation.
  If you cite a turn number, say which tier: turn_id restarts at 1 in every tier,
  so turn 12 of core is not turn 12 of full.
-->

---

### Fixing a question, the conversation or a probe? Please open an issue instead

The data files (`questions_*.jsonl`, `glasshouse_v0.1_*.jsonl`) are generated from source
tables that are not published, because those tables contain the answers. A pull request
that edits them directly would be overwritten the next time they are generated. Open an
issue with the question id and the evidence; we fix it at the source and credit you in the
version that carries the fix.

Pull requests fit the things whose source is in this repository: the documents, the scorer
(`score.py`, `judge.py`, `ci_score.py`) and the baselines (`bm25_baseline.py`,
`vector_baseline.py`).

### Before sending

- [ ] If you changed the scorer, `python score.py <run file> --questions questions_medium.jsonl --mode dry` runs to the end
- [ ] No data file was touched. Turn counts are unchanged: 1,882 / 7,186 / 12,884 / 103,572
- [ ] Question count is unchanged: 2,847

<!--
  If any of these move, published scores stop being comparable. If a change has to move
  them, say why in the PR. This is to make it visible, not to block it.
-->

### Submitting a score?

**This is not the place.** See `SUBMITTING.md` and `CONTRIBUTING.md` in the
[glasshouse repository](https://github.com/wontopos/glasshouse). Pull requests here change
the benchmark itself.
