# glasshouse

A place to put memory benchmark results where anyone can check them.

## Why

Zep reported 84% on LoCoMo. mem0 recomputed it and got 58.44%. Zep came back with
75.14%. Same system, same benchmark, three numbers.

LongMemEval and BEAM both ship a dataset and a script. Neither has a leaderboard or
anywhere to submit, so everyone reports their own. These systems go inside other
people's AI. There should be a standard.

## Rules

1. **Publish the reader, the judge, and the prompts.** A score without them is not a
   result, because nobody can get it again.
2. **Publish the per-question record.** Anyone can recompute the number from it. The
   aggregate is a claim; the record is the evidence.
3. **A company's proposal is added when three other companies agree.**
4. **An individual's proposal is added on public support.** The number is not
   settled.

Tear them up or add to them. That is the starting point, not the answer.

## Who runs this

Wontopos hosts it and keeps it running. That is the whole role.

We also build memory infrastructure, which means we compete in the thing we
administer. So the limits are written down rather than promised:

- Our submissions go through the same approval as everyone else's. We do not merge
  our own.
- We do not decide who is admitted. Rules 3 and 4 do.
- Our numbers are verified the same way as everyone else's.
- If other memory companies want to co-administer, that is better than us alone, and
  the offer is open.

Everything here is Apache 2.0, so if we ever become the problem, the whole thing can
be taken and run elsewhere without asking us.

## Layout

    companies/<company>.md   the company's own words, and its claims
    individuals/             corrections, objections, recomputations, harness work
    schema/                  the submission manifest format
    submissions/             verified results. Empty.

A company writes its own description and its own model entries. Nobody rewrites
another company's account of itself.

## The claims register

`companies/` holds numbers that are already public. **None of them were produced
here.** This repository has no benchmark of its own yet, and nothing in it has been
verified.

They are written down anyway, because a claim on a page is hard to check and a claim
in a table with its reader, its judge and its run count is not. Several rows say the reader
and judge are not published anywhere linkable, which under CONTRIBUTING.md would not
be accepted as a submission. Three of the six Wontopos rows say that.

## Submitting

Read [CONTRIBUTING.md](CONTRIBUTING.md). A submission is a manifest plus the record
it points at. If the record does not reproduce the number in the manifest, the
submission does not go in.

`submissions/` is empty. The rules went up first, and we have not submitted either.

## Open question

The threshold in rule 4 is not settled. What number is right?
