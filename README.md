# glasshouse

A place to put memory benchmark results where anyone can check them.

## Why

Zep reported 84% on LoCoMo. mem0 recomputed it and got 58.44%. Zep came back with
75.14%. Same system, same benchmark, three numbers.

LongMemEval and BEAM both ship a dataset and a script. Neither has a leaderboard or
anywhere to submit, so everyone reports their own. These systems go inside other
people's AI. There should be a standard.

## Rules

1. **Publish the per-question record.** Anyone can recompute the number from it. The
   aggregate is a claim; the record is the evidence.
2. **A company's proposal is added when three other companies agree.**
3. **An individual's proposal is added on public support.** There is no number, on
   purpose. A count passes anything with one viral post behind it and turns away a
   quiet correction that happens to be right.
4. **The reader, the judge and the prompts are set by the version.** Each version of
   the benchmark fixes them. A submitter does not choose them.
5. **A submission carries its runs, its harness, and which version's reader, judge
   and prompts it used.**
6. **The harness has to be one a customer could use**, the product's own SDK for
   instance. A number produced through a path only its author can reach is not a
   number anyone else can get.
7. **The engine stays closed if you want.** Nothing here asks how a system works.
8. **Three runs is a result. Five is certified.**
9. **A glasshouse score is one measured here.** Take the benchmark and run it
   anywhere you like; that is what the licence is for. What cannot travel is the
   name.
10. **What the vote picks goes into the next version.** Comments and pull requests
    arrive against a version that is already out and cannot change. They are voted on,
    and what wins is in the next one.
11. **Wontopos publishes nothing on a new version for fourteen days.**

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

    glasshouse-v0.1/         the benchmark. One directory per version, kept.
                             v0.1 is not drafted yet
    companies/<company>.md   the company's own words, and its claims
    individuals/             corrections, objections, recomputations, harness work
    schema/                  the submission manifest format
    submissions/<version>/   verified results. Empty.

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
