# -*- coding: utf-8 -*-
u"""Re-check submissions in public CI.

**Why it exists.** "We measured it and got 62" and **GitHub recomputing it in front of
everyone** carry different weight. The same system on the same test ends up with three
different numbers in this field because everyone measures their own and publishes their
own.

**The format is set by the published repository, not invented here.** An earlier version
of this file invented a `.meta.json` format (2026-09-16), while the published repository
**already** had `schema/submission.schema.json` and a folder layout in CONTRIBUTING.md. If
this CI asked for something different, **a submission that followed the rules would be
rejected here.** The repository's rules come before this file.

    submissions/<version>/<system>/<date>/
      manifest.json      follows schema/submission.schema.json
      records/           per-question records (SUBMITTING.md)
      README.md

**The four rejection reasons set by the published repository** (CONTRIBUTING.md, "What
gets a submission rejected"), turned into what a machine can check:

    the records do not reproduce the manifest's numbers  -> recount and compare with headline
    the prompt is described instead of quoted             -> check prompts is not empty
    runs are missing, or only the good ones are there     -> check runs is not empty, and
                                                             that runs explain headline
    the reader or judge is not named                      -> check reader and judge are set

**What can be proven for free is kept apart from what cannot.** The reported score comes
from the judge LLM, which needs a key and money. A key in public CI would let any
submission spend the owner's money. Judge scoring runs only when a key is present, and
**when it is absent the skip is printed.** A silent skip is the same as no check.

    python ci_score.py                     everything under submissions/
    python ci_score.py <submission folder> one submission
"""
import codecs
import glob
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")

SUB_DIR = os.path.join(HERE, "submissions")
SCHEMA_P = os.path.join(HERE, "glasshouse_docs", "submission.schema.json")

# The tier is identified **by turn count,** to avoid adding a manifest field only we know
# about. corpus.turns already exists in the published schema.
TURNS = {1882: "core", 7186: "small", 12884: "medium", 103572: "full"}
MODES = ("memory", "answer")

CHARS_SLACK = 0.05
CHARS_MIN = 20
HEADLINE_SLACK = 0.5      # reject when the recount and headline differ by more than this


def fail(msg):
    print(u"  🔴 %s" % msg)
    return False


def load_schema():
    if not os.path.exists(SCHEMA_P):
        return None
    return json.load(io.open(SCHEMA_P, encoding="utf-8"))


def check_required(man, schema):
    u"""Check the published schema's required fields directly, without copying the list here."""
    ok = True
    for k in (schema.get("required") or []):
        if k not in man:
            ok = fail(u"the manifest has no `%s` (required by the schema)" % k)
            continue
        sub = ((schema.get("properties") or {}).get(k) or {}).get("required") or []
        for k2 in sub:
            if not isinstance(man[k], dict) or k2 not in man[k]:
                ok = fail(u"manifest `%s` has no `%s`" % (k, k2))
    return ok


def check_rules(man):
    u"""Check the rejection reasons listed in the published CONTRIBUTING."""
    # Field names **come from the schema.** This first read `name`, but the schema says
    # `model`, and a submission that followed the rules would have been rejected.
    ok = True
    for who in ("reader", "judge"):
        v = man.get(who) or {}
        if not str(v.get("model") or "").strip():
            ok = fail(u"%s.model is not stated. A number from an unnamed %s cannot be read"
                      % (who, who))
    if not str((man.get("judge") or {}).get("prompt") or "").strip():
        ok = fail(u"judge.prompt is empty. **A described prompt is not a published one.** "
                  u"Quote it, or give the path of a file inside this submission")
    if not str((man.get("prompts") or {}).get("reader") or "").strip():
        ok = fail(u"prompts.reader is empty. Quote exactly what the reader was given")
    runs = man.get("runs") or []
    if not runs:
        ok = fail(u"runs is empty. List **every run,** not just the one that went well")
    for i, r in enumerate(runs):
        for k in ("id", "n", "score"):
            if k not in r:
                ok = fail(u"runs[%d] has no `%s`" % (i, k))
    return ok


def tier_of(man):
    u"""Identify the tier from corpus.turns, a field already in the published schema."""
    t = (man.get("corpus") or {}).get("turns")
    if t in TURNS:
        return TURNS[t], None
    return None, (u"corpus.turns is %r. The tiers are %s"
                  % (t, " · ".join("%s=%d" % (v, k) for k, v in TURNS.items())))


def mode_of(man):
    u"""The scoring mode is read from runs[].config. The schema defines config as every
    setting that was used, so no new field is needed."""
    for r in (man.get("runs") or []):
        m = (r.get("config") or {}).get("mode")
        if m:
            return m, None
    return None, u"runs[].config.mode is missing (one of %s)" % " · ".join(MODES)


def load_jsonl(p):
    out = []
    for i, line in enumerate(io.open(p, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception as e:
            raise ValueError(u"%s: line %d is not JSON (%s)"
                             % (os.path.basename(p), i, type(e).__name__))
    return out


def find_records(d, man):
    u"""Read what the manifest's records field points at, a single file or a folder."""
    rel = str(man.get("records") or "records")
    p = os.path.join(d, rel)
    files = []
    if os.path.isdir(p):
        files = sorted(glob.glob(os.path.join(p, "*.jsonl")))
    elif os.path.exists(p):
        files = [p]
    if not files:
        return None, u"no file where records points: %s" % rel
    rows = []
    for f in files:
        rows += load_jsonl(f)
    return (rows, files), None


def check_shape(rows, tier):
    qs = {q["id"] for q in
          (json.loads(l) for l in
           io.open(os.path.join(HERE, "questions_%s.jsonl" % tier), encoding="utf-8")
           if l.strip())}
    turns = {t["turn_id"] for t in
             (json.loads(l) for l in
              io.open(os.path.join(HERE, "glasshouse_v0.1_%s.jsonl" % tier),
                      encoding="utf-8") if l.strip())}
    ok = True
    seen, dup, unknown, noans = set(), [], [], []
    badturn, mismatch, countonly = [], [], []
    for r in rows:
        i = r.get("id")
        if i in seen:
            dup.append(i)
        seen.add(i)
        if i not in qs:
            unknown.append(i)
        if not str(r.get("answer") or "").strip():
            noans.append(i)
        for t in (r.get("retrieved_turns") or []):
            if t not in turns:
                badturn.append((i, t))
                break
        mem = r.get("memories_returned")
        if isinstance(mem, list):
            actual = len(" ".join(str(x) for x in mem))
            said = r.get("chars_returned")
            if said and abs(said - actual) > max(CHARS_MIN, actual * CHARS_SLACK):
                mismatch.append((i, said, actual))
        elif mem is not None and not isinstance(mem, str):
            countonly.append(i)

    print(u"  %d record lines · %d distinct ids (question file: %d)"
          % (len(rows), len(seen), len(qs)))
    if dup:
        ok = fail(u"%d questions appear twice: %s" % (len(dup), dup[:5]))
    if unknown:
        ok = fail(u"%d ids not in the question file: %s" % (len(unknown), unknown[:5]))
    if noans:
        ok = fail(u"%d lines with an empty answer: %s" % (len(noans), noans[:5]))
    if badturn:
        ok = fail(u"%s tier: %d questions cite turn numbers that do not exist: %s  "
                  u"(turn numbers restart in every tier; were tiers mixed?)"
                  % (tier, len(badturn), badturn[:3]))
    if countonly:
        ok = fail(u"%d questions have a count instead of text in memories_returned. "
                  u"The text is needed to verify chars_returned" % len(countonly))
    if mismatch:
        ok = fail(u"%d questions report a chars_returned that differs from the actual text length: %s  "
                  u"(reported values are not trusted)"
                  % (len(mismatch), ["%s reported %d, actual %d" % x for x in mismatch[:3]]))
    missing = len(qs) - len(seen & qs)
    if missing:
        print(u"  🟡 %d questions not submitted. Unsolved ones still need an empty answer so the denominator is right"
              % missing)
    return ok


def run_score(run_p, qfile, mode, out=None):
    cmd = [sys.executable, os.path.join(HERE, "score.py"), run_p,
           "--questions", qfile, "--mode", mode, "--strict"]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.stderr:
        sys.stdout.write(r.stderr)
    return r.returncode, (r.stdout or "")


def headline_check(man, files):
    u"""**The published repository's first rejection reason.** Do the records add up to the
    manifest's numbers?

    This counts with `dry`, because it cannot call the judge LLM, so the score cannot match
    exactly. It compares **the n in runs with the number of record lines** instead, which
    is enough to catch "only the good runs were submitted".
    """
    ok = True
    runs = man.get("runs") or []
    n_rec = None
    try:
        n_rec = sum(len(load_jsonl(f)) for f in files)
    except Exception:
        return True
    ns = [r.get("n") for r in runs if isinstance(r.get("n"), int)]
    if ns and n_rec and all(n_rec < n for n in ns):
        ok = fail(u"the records have %d lines but runs claim %s questions. "
                  u"**The records do not reproduce the manifest's numbers**"
                  % (n_rec, "/".join(str(x) for x in ns)))
    hl = (man.get("headline") or {}).get("score")
    if hl is not None and ns:
        scores = [r.get("score") for r in runs if isinstance(r.get("score"), (int, float))]
        if scores:
            lo, hi = min(scores), max(scores)
            if not (lo - HEADLINE_SLACK <= hl <= hi + HEADLINE_SLACK):
                ok = fail(u"headline %.2f is outside the range of runs (%.2f to %.2f). "
                          u"**If it is an average, show what it averages**" % (hl, lo, hi))
    return ok


def one(d):
    print("─" * 70)
    print(u"submission: %s" % os.path.relpath(d, HERE))
    man_p = os.path.join(d, "manifest.json")
    if not os.path.exists(man_p):
        return fail(u"no manifest.json. Follow the folder layout in CONTRIBUTING.md")
    try:
        man = json.load(io.open(man_p, encoding="utf-8"))
    except Exception as e:
        return fail(u"could not read manifest.json (%s)" % type(e).__name__)

    schema = load_schema()
    if schema is None:
        return fail(u"schema copy not found: glasshouse_docs/submission.schema.json")
    ok = check_required(man, schema)
    ok = check_rules(man) and ok

    tier, why = tier_of(man)
    if why:
        ok = fail(why)
    mode, why2 = mode_of(man)
    if why2:
        ok = fail(why2)
    elif mode not in MODES:
        if mode == "dry":
            ok = fail(u"mode is dry. **Not accepted for a reported score.** "
                      u"It is string matching, and marks correct answers in other words as wrong")
        else:
            ok = fail(u"mode must be one of %s (got: %r)"
                      % (" · ".join(MODES), mode))
    if not ok:
        return False

    sysname = (man.get("system") or {}).get("name")
    print(u"  %s %s · tier %s · mode %s · reader %s · judge %s"
          % (sysname, (man.get("system") or {}).get("version"), tier, mode,
             (man.get("reader") or {}).get("model"),
             (man.get("judge") or {}).get("model")))

    got, why3 = find_records(d, man)
    if why3:
        return fail(why3)
    rows, files = got

    if not check_shape(rows, tier):
        return False
    if not headline_check(man, files):
        return False

    # several record files are merged into one run before scoring
    merged = os.path.join(d, "_merged_run.jsonl")
    with io.open(merged, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    try:
        print()
        print(u"  ── string-match scoring (free, for reproduction. **Not a reported score**) ──")
        rc, _ = run_score(merged, "questions_%s.jsonl" % tier, "dry")
        if rc != 0:
            return fail(u"the scorer rejected it. See the reason above")

        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        print()
        if not key:
            print(u"  ⏭️ judge LLM scoring **skipped**: no OPENROUTER_API_KEY.")
            print(u"     The reported score (%s) comes from the judge LLM and costs money." % mode)
            print(u"     What was proven here is **that the submission follows the rules,** no more.")
        else:
            print(u"  ── judge LLM scoring (%s, paid) ──" % mode)
            rc, _ = run_score(merged, "questions_%s.jsonl" % tier, mode)
            if rc != 0:
                return fail(u"judge scoring rejected it. See the reason above")
    finally:
        if os.path.exists(merged):
            os.remove(merged)
    print()
    print(u"  ✅ passed")
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        subs = [os.path.abspath(a) for a in args]
    else:
        subs = sorted(os.path.dirname(p) for p in
                      glob.glob(os.path.join(SUB_DIR, "*", "*", "*", "manifest.json")))

    print("=" * 70)
    print(u"Re-checking submissions: GitHub counts, not us")
    print("=" * 70)
    if not subs:
        print(u"  no submissions (submissions/<version>/<system>/<date>/manifest.json).")
        return 0

    bad = [d for d in subs if not one(d)]
    print("─" * 70)
    print(u"%d submissions · %d passed · %d rejected" % (len(subs), len(subs) - len(bad), len(bad)))
    for d in bad:
        print(u"  🔴 %s" % os.path.relpath(d, HERE))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
