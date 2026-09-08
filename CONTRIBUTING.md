# Submitting a result

A submission is two things: a manifest that says how the number was produced, and
the per-question record it points at. Either one alone is not a result.

## Layout

    submissions/<system>/<benchmark>/<date>/
      manifest.json      what ran, and how it was scored
      records/           one file per question, or one file with one line per question
      README.md          anything a reader needs that the manifest cannot hold

## The manifest

See [schema/submission.schema.json](schema/submission.schema.json). Every field in
`required` has to be there. The parts that matter most:

- **reader** — the model that answers, its settings, and how it was invoked. A score
  is a property of the memory system *and* the reader. Reporting one without the
  other is the thing this repository exists to stop.
- **judge** — the model that grades, its temperature, and the grading prompt
  verbatim. If the benchmark does not name a judge, say so and say what you chose.
- **prompts** — the exact text, not a description of it.
- **scoring** — the rubric, and anything in the benchmark's own script you did not
  implement. Say what you left out. That is a normal thing to have to say.
- **runs** — every run you did, not the best one. If you report a mean, the runs it
  is a mean of have to be here.

## The record

One row per question, carrying at least: the question id, what the memory system
returned, the reader's answer, and the judge's grade. Enough that someone can add up
the grades and get your number without running anything.

## What gets a submission rejected

- The record does not reproduce the number in the manifest.
- A prompt is described instead of quoted.
- Runs are missing, or only the good ones are here.
- The reader or the judge is unnamed.

None of these are judgements about the system. They are all about whether anyone
else can check.

## Correcting a submission

Open a pull request against your own. Corrections keep the original in history. A
number that changed is more useful with the old one visible next to it.
