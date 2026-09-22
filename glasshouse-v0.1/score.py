# -*- coding: utf-8 -*-
"""glasshouse v0.1 scorer.

`--mode` has no default. A run scored under the wrong mode moves the total by more than
the gap between most systems, so the scorer refuses to run without one and never guesses
the mode from the file.

**There are two scoring modes, and both use a judge LLM.** What separates them is whether
there is an answer LLM. (Corrected by the operator, 2026-09-09.)

  memory   the judge reads **the memories the system retrieved**. No answer LLM
  answer   an answer LLM writes an answer from those memories, and the judge reads
           **that answer**

In both, the judge sees gold_answer and required_memories and scores against them
(operator's decision, 2026-09-09; see judge.py for why it is no longer hidden).

  dry      calls no judge and only matches the answer strings. **Not a scoring mode but a
           development ruler.** It costs nothing, so it is used for quick looks while
           fixing questions.
           ⚠️ Do not publish this result as a score. It marks answers with the right
           meaning as wrong.

The core idea is that each axis is scored differently.
  ABSTAIN      correct only if it says it does not know. Any value is wrong.
  CONFLICT     rejecting the premise alone is half right. It must also give the latest value.
  FALSE_MEMORY correct only if it says that was never said. Probe file only.
  the rest     correct if the answer is contained in the response.

Whether retrieval brought back the evidence is counted separately. Without it, "retrieval
did not find it" and "the reading model did not read it" cannot be told apart.
"""
import json, io, os, sys, re, math, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))

# ── Weight per axis ───────────────────────────────────────────────────
#
# ⚠️⚠️ **The number of questions must not decide the total.** BASIC has 733 questions,
#    53% of the total, so a plain average makes "72% accuracy" effectively "72% lookup
#    accuracy". A system that handles contradictions well and one that does not get the
#    same score, and the more questions are added the worse the skew. So **accuracy per
#    axis is averaged with weights.**
#
# There is one criterion for the weights: **does the axis end once the right thing is
# retrieved, or does something more have to be done after retrieving it.** The latter is
# where things go wrong in real use.
#
#   1.0  done once retrieved
#   2.0  after retrieving, time or change has to be worked out
#   3.0  after retrieving, a **judgment** has to be made. Getting it wrong means being
#        confidently wrong
#
# ⚠️ These are values we chose. Hiding them invites the charge of tuning the score. The
#    scorer always prints this table and reports the unweighted average alongside.
AXIS_WEIGHT = {
    # done once retrieved
    "BASIC":      1.0,   # what was written, as written
    "PARAPHRASE": 1.0,   # one turn, said in other words
    "IMAGE":      1.0,   # one photo
    # after retrieving, work out time or change
    "TEMPORAL":   2.0,   # which came first
    "UPDATE":     2.0,   # does it know the value changed
    "GATHER":     2.0,   # collect from several turns (new axis)
    "RECONCILE":  2.0,   # make an apparent contradiction consistent (new axis)
    # after retrieving, make a judgment. Wrong means confidently wrong
    "MULTI":      3.0,   # combine and calculate
    "IMPLICIT":   3.0,   # infer by overlaying scattered facts
    "CROSS":      3.0,   # connect different areas of life (new axis)
    "CONFLICT":   3.0,   # correct a false premise
    "STALE":      3.0,   # when the new value cannot be found, do not insist on the old one
    "CONTRADICT": 3.0,   # say that there is no answer
    "ABSTAIN":    3.0,   # do not invent what is not there
    "FALSE_MEMORY": 3.0,  # do not agree when told you said something you never said
    # done once retrieved. Crossing languages makes **the finding** hard; there is
    # nothing more to do once found. Failing to cross gives "I don't know", a safe failure.
    "XLING_QUERY":  1.0,  # find it when asked in another language
    "XLING_STORE":  1.0,  # find in English what was stored in another language
}

# ⚠️⚠️ **The weights of the three axes above were set on 2026-09-16.** Before that they
#    were missing from the table, so `.get(k, 1.0)` below silently gave 1.0, and **1,300
#    questions (46% of the total) were scored with a weight nobody had chosen.**
#
#    The criterion is this table's original one: **not difficulty, but "what happens when
#    it is wrong"** (WEIGHTS.md, "One criterion").
#
#      FALSE_MEMORY -> 3   wrong means **agreeing it said something it never said, and
#                          inventing the content.** The same failure as ABSTAIN ("do
#                          not invent what is not there"), already 3, and harder since
#                          the question leads with the falsehood, so **the system has to
#                          contradict the user.**
#      both XLING   -> 1   failing to cross finds nothing and gives "I don't know". The
#                          user can ask again. It is not confidently wrong.
#
#    ⚠️ Cross-language was first recommended at 2 and then withdrawn. That was "it feels
#       hard", not this table's criterion. **Hard and dangerous are different things.**
#
#    The total weight changes **from 3,655 to 4,655** (500 FALSE_MEMORY questions × +2).
#    Every weighted score has to be measured again. Once set, these do not change.

# Expressions counted as "I don't know". Measurement is in English only, so only English.
IDK = [
    r"never (stated|said|mentioned|came up)|not (stated|mentioned|specified|given)",
    # ⚠️ This used to end in |in the. So **an ordinary conversation sentence** like
    #    "another item that wasn't in the budget" was read as "not in memory".
    #    It must require what the thing is not in.
    r"(isn'?t|is not|wasn'?t|was not) (stated|mentioned|specified)",
    r"(isn'?t|is not|wasn'?t|was not) in (the |your |our |my )?"
    r"(memor(y|ies)|conversation|history|record|notes|context)",
    r"no (such )?(information|record|mention|detail)|nothing (about|on) that",
    r"don'?t (know|have)|do not (know|have)|cannot (tell|determine|say)|can'?t (tell|say)",
    r"(memories|conversation|history) (do(es)? not|don'?t) contain",
    r"unable to (tell|determine|find)",
    r"not in (the |your |our |my )?(memor(y|ies)|conversation|history|record|notes)",
]
IDK = [re.compile(p, re.I) for p in IDK]

# Negations. Used for CONFLICT. Measurement is in English only, so only English.
NEG = re.compile(r"\bno\b|\bnot\b|isn'?t|wasn'?t|incorrect|actually|"
                 r"changed|switched|used to|no longer|anymore|"
                 r"that'?s (wrong|not right)|mistaken", re.I)


# Expressions that point out a disagreement. Used for the contradiction axis. Measurement
# is in English only, so only English.
#
# ⚠️ This must not be broad. Catching "both" or "different" alone would give any answer
#    full marks. It is narrowed to **words that name the disagreement itself.** An answer
#    that states both values is caught by the clash_a/clash_b match, not by this net.
CLASH = re.compile(
    r"\bconflict|\bcontradic|\binconsistent|\bnot consistent|\bdisagree"
    r"|\bmismatch|\bdo(?:es)?n'?t match|\bdo(?:es)? not match"
    r"|\btwo different (?:answers|values|numbers|figures)"
    r"|\bat one point\b[^.!?]{0,60}\blater\b", re.I)


def says_idk(ans):
    return any(p.search(ans) for p in IDK)


def strip_neg(gold):
    """Keep only the latest value from a CONFLICT answer.

    The answer looks like "no, they're metal pipe now". Removing the leading negation and
    the trailing 'now' leaves "metal pipe", which also appears in the conversation as is.
    The old rule could not remove they're and the final now, so 14 questions could not be
    matched even when answered correctly.
    """
    g = re.sub(r"^no,?\s*", "", str(gold), flags=re.I)
    g = re.sub(r"^(it'?s|they'?re|they|that'?s|it|he'?s|she'?s)\s+", "", g, flags=re.I)
    g = re.sub(r"\s+now\b\.?$", "", g, flags=re.I)
    return g.strip()


# Number words <-> digits. Our answer says 'five weeks' while the conversation says
# '5 weeks'. Left alone, a system that answered correctly comes out wrong. Because of this,
# 76 BASIC questions actually had "no answer anywhere in the conversation".
NUMWORD = [
    ("a quarter", "0.25"), ("quarter", "0.25"), ("three quarters", "0.75"),
    ("a half", "0.5"), ("half", "0.5"), ("a third", "0.33"), ("third", "0.33"),
    ("twenty five", "25"), ("twenty four", "24"), ("twenty", "20"),
    ("nineteen", "19"), ("eighteen", "18"), ("seventeen", "17"), ("sixteen", "16"),
    ("fifteen", "15"), ("fourteen", "14"), ("thirteen", "13"), ("twelve", "12"),
    ("eleven", "11"), ("thirty", "30"), ("forty", "40"), ("fifty", "50"),
    ("sixty", "60"), ("seventy", "70"), ("eighty", "80"), ("ninety", "90"),
    ("hundred", "100"), ("thousand", "1000"),
    ("one", "1"), ("two", "2"), ("three", "3"), ("four", "4"), ("five", "5"),
    ("six", "6"), ("seven", "7"), ("eight", "8"), ("nine", "9"), ("ten", "10"),
    ("once", "1"), ("twice", "2"),
]

# Personal pronouns. Questions are in the third person ('their knees') while the
# conversation is in the first ('my knees'). A reader takes these as the same, so they are
# dropped before comparing.
PRON = re.compile(r"\b(my|your|his|her|its|our|their|i|you|he|she|it|we|they|"
                  r"me|him|them|us)\b")


def norm(s):
    """Tidy up before comparing. Noise must not sway the score.

    ⚠️ This used to delete whitespace entirely. A short answer then matched inside an
       unrelated word. It only showed up after running the BM25 baseline.

         answer 'on'  <- judged to be inside "conversation"
         answer 'lit' <- judged to be inside "a little bit"
         answer 'two' <- judged to be inside "the network"

       Our answers are deliberately short (median 5 characters), so this bug inflated
       every axis. Whitespace is now collapsed to one space, not removed.
    """
    s = s.lower().strip()
    # Word boundaries are required. Without them the a in "cat" goes too, giving "c t".
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = s.replace("percent", "%").replace("dollars", "$").replace("dollar", "$")
    s = re.sub(r"(?<=\d),(?=\d\d\d)", "", s)            # 1,000 -> 1000
    s = re.sub(r"(\d+)\s*/\s*(\d+)", lambda m: _frac(m), s)   # 1/4 -> 0.25
    for w, d in NUMWORD:                                # five -> 5
        s = re.sub(r"\b" + w + r"\b", " " + d + " ", s)
    s = PRON.sub(" ", s)                                # drop my/their
    s = re.sub(r"(?<!\d)[.,](?!\d)", " ", s)            # only periods and commas not between digits
    s = re.sub(r"[\-–—~'\"()\[\]/]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _frac(m):
    """1/4 to 0.25, to match the number word quarter."""
    a, b = int(m.group(1)), int(m.group(2))
    if b and a < b:
        return " %s " % round(a / b, 2)
    return m.group(0)


def contains(ans, gold):
    """Is the answer inside the response. Word boundaries are kept. Numbers are also compared as numbers."""
    a, g = norm(ans), norm(gold)
    if g:
        # Block matches in the middle of a word, but allow a trailing ending.
        # Answer 'open' also accepts 'opened' and 'opens'.
        if re.search(r"(?<![a-z0-9])" + re.escape(g) + r"(?:e?[sd]|ing)?(?![a-z0-9])", a):
            return True
    # Fallback for different number notation ("$150" and "150 dollars").
    # Numbers are taken from the tidied text. Taken from the original, "1,000" splits into 1 and 000.
    #
    # ⚠️ Matching numbers alone must not pass. Answer 'about four hours' was once judged
    #    to be inside "After going to four visits a week, ...", because the number 4 was
    #    on both sides. So **the content words besides the number** must also be there.
    gn = re.findall(r"\d+(?:\.\d+)?", g)
    if gn:
        an = re.findall(r"\d+(?:\.\d+)?", a)
        if all(x in an for x in gn):
            hedge = {"about", "around", "roughly", "approximately", "some", "over",
                     "under", "just", "almost", "nearly"}
            gw = [w for w in re.findall(r"[a-z]+", g) if len(w) >= 3 and w not in hedge]
            if all(re.search(r"(?<![a-z])" + w + r"(?:e?[sd]|ing)?(?![a-z])", a) for w in gw):
                return True
    return False


def grade_exact(q, ans):
    """1.0 if right, 0.0 if wrong.

    ⚠️ An empty response **scores 0 and stays in the denominator.** It used to be removed
       from the denominator, which let a system raise its score by not answering hard
       questions.

         of 486 questions, 200 right and 286 wrong        -> 41%
         of 486 questions, 200 right and 286 empty        -> 100%

       Nor may an empty response count as a correct abstention. **Saying** "that never
       came up" is different from returning nothing. Otherwise all-empty responses would
       take 16 abstention questions for free.
    """
    axis = q["axis"]
    # ⚠️⚠️ **Abstention questions are told apart by expect, not by axis (2026-09-17).** 10
    #    cross-language XLING_QUERY questions come from an ABSTAIN original (Q326), so the
    #    answer is "Never stated…", but the axis name is XLING_QUERY and they never took
    #    the abstention rule here. A correct abstention was compared letter by letter with
    #    the whole answer sentence and **marked wrong.** They are scored as abstentions.
    if is_no_memory(q) and axis not in NO_MEMORY_AXES:
        axis = "ABSTAIN"
    if not ans or not ans.strip():
        return 0.0

    # ⚠️⚠️ **An "I don't know" response is scored as such. String matching must not come first.**
    #    Q089's answer is 'never', and the **abstention sentence** "that was never stated"
    #    contains that word, so it scored full marks. When an answer happens to overlap an
    #    abstention phrase, a system that does nothing but say it does not know earns points.
    #    Only the axes below can take an abstention as an answer; on the rest it scores 0.
    #
    # ⚠️⚠️ **Some answers themselves look like abstentions.** When this net was first set,
    #    two were caught and **correct responses scored 0** (the cross-check caught it).
    #      Q372 "I don't leave things when I don't know why"  <- don't know
    #      Q425 "for months and never said anything"          <- never said
    #    So **questions whose answer looks like an abstention are exempt from this rule.**
    #    For them abstention and the answer cannot be told apart by text, so they are
    #    matched as before.
    # ⚠️ RECONCILE is **left out** here. On this axis both statements are plainly in the
    #    conversation. Nothing is hidden, so "I don't know" is not playing safe, it is just
    #    not finding it. Half credit would give half the axis for doing nothing (30
    #    questions × weight 2). Half credit goes only to the hidden axis (STALE) or the axis
    #    with no correct value (CONTRADICT).
    if (axis not in ("ABSTAIN", "FALSE_MEMORY", "STALE", "CONTRADICT",
                     "UPDATE")
            and says_idk(ans)
            and not any(says_idk(str(g)) for g in
                        [q.get("gold_answer")] + list(q.get("gold_alts") or []) if g)):
        return 0.0

    if axis in ("ABSTAIN", "FALSE_MEMORY"):
        # Correct only if it says it does not know. Giving a value is wrong.
        return 1.0 if says_idk(ans) else 0.0

    if axis == "GATHER":
        # Gathering. The answer has two parts, each in a different turn.
        #
        # **Credit in proportion to the parts found.** One of two is 0.5, both is 1.0.
        #
        # ⚠️ This started as "all or nothing" and was changed (operator, 2026-09-09).
        #    Reason: finding one part and finding nothing are **different things,** and an
        #    answer with only one part is **not dangerous.** The gap shows plainly.
        #    ("They keep lunch simple" stops there, and the missing dinner is obvious.)
        #
        # ⚠️⚠️ This partial credit **must not be given on every axis.** The dividing line
        #    is one question: **is an incomplete answer dangerous.** Giving the old value
        #    on UPDATE is not incomplete, it is **wrong,** because the user takes it as
        #    current. So that is 0 and this is proportional. It is written in the README
        #    section "Scoring by axis".
        parts = q.get("gold_parts") or []
        if not parts:
            for g in [q.get("gold_answer")] + list(q.get("gold_alts") or []):
                if g and contains(ans, g):
                    return 1.0
            return 0.0
        hit = sum(1 for p in parts if contains(ans, p))
        return round(hit / float(len(parts)), 3)

    if axis == "UPDATE":
        # Update questions. Three outcomes like the trap axis, but **there was no branch
        # for the middle one, so half credit was never given** (found 2026-09-10). UPDATE
        # was exempted from the IDK net above, yet no place gave 0.5, so "I don't know"
        # fell to 0. The judge prompt (judge.AXIS_RULE) and the README section "Scoring by
        # axis" both said 0.5. **If the two scoring paths give different scores, neither
        # number can be trusted.**
        #
        #   ① gives the new value              1.0
        #   ② says it does not know            0.5   not wrong; does not mislead the user
        #   ③ gives the old value as current   0.0   confidently wrong
        #
        # ⚠️ ① is checked first. An answer that also mentions the old value, like "it was
        #    every other day but now it's daily", is right.
        for g in [q.get("gold_answer")] + list(q.get("gold_alts") or []):
            if g and contains(ans, g):
                return 1.0
        if says_idk(ans):
            return 0.5
        return 0.0

    if axis == "STALE":
        # Trap questions. Three outcomes. Only this axis works this way.
        #
        #   ① gives the new value              1.0  expected not to find it, but did
        #   ② says it does not know            0.5  retrieval failed but nothing was invented
        #   ③ gives the old value as current   0.0  confidently wrong; what goes wrong in real use
        #
        # Telling ② from ③ is the whole reason this axis exists. Until now both were just
        # "wrong", so there was no way to see how a system behaves when retrieval fails.
        # Repeating the old value and saying "I don't know" are very different in real use.
        #
        # ⚠️ ① is checked first. If it gives both the new and the old value (for example
        #    "it was every other day but now it's daily") it is right. Reverse the order
        #    and a correct answer falls to ③.
        for g in [q.get("gold_answer")] + list(q.get("gold_alts") or []):
            if g and contains(ans, g):
                return 1.0
        stale = q.get("stale_answer")
        if stale and contains(ans, stale):
            return 0.0
        if says_idk(ans):
            return 0.5
        return 0.0

    if axis == "RECONCILE":
        # Apparent contradiction. **It looks like a contradiction but has a correct
        # answer.** Two statements seem to clash but hold under different conditions, so
        # both are true.
        #
        #   ① names both conditions   1.0  what this axis measures
        #   ② names only one          0.5  not wrong, but only half seen
        #   ③ anything else           0.0  calling one side false lands here
        #
        # ⚠️ **No half credit for "I don't know".** Unlike the trap (STALE). The trap hides
        #    the new value on purpose, so honesty is worth something; here both statements
        #    are plainly in the conversation. It just did not find them. Half credit would
        #    give half this axis for doing nothing.
        #
        # ⚠️ **The opposite of the contradiction axis.** There, "the two disagree" scores 1;
        #    here it is a wrong answer, because they do not disagree.
        # ⚠️ This count holds only if the answer text contains both conditions **as
        #    written.** audit_reconcile checks the conditions, and cross-check [7] checks
        #    that the answer itself scores full marks. At first six answers did not contain
        #    the conditions.
        a, b = q.get("side_a"), q.get("side_b")
        if a and b:
            hit = sum(1 for s in (a, b) if contains(ans, s))
            if hit == 2:
                return 1.0
            if hit == 1:
                return 0.5
        for g in [q.get("gold_answer")] + list(q.get("gold_alts") or []):
            if g and contains(ans, g):
                return 1.0
        return 0.0

    if axis == "CONTRADICT":
        # Contradiction questions. **The only axis with no correct value.**
        #
        #   ① says the two disagree        1.0  what this axis measures
        #   ② says it does not know        0.5  safe, but does not say why
        #   ③ states one value as fact     0.0  what goes wrong in real use
        #
        # ⚠️ **Stating both values** also counts as showing the disagreement.
        #    "First they said 200, later they said 300" shows the conflict without using
        #    the word. Counting words alone would miss it.
        # ⚠️ ① is checked first. Reverse the order and an answer like "I'm not sure, but
        #    both 200 and 300 come up" falls to 0.5. That answer deserves full marks.
        a, b = q.get("clash_a"), q.get("clash_b")
        if a and b and contains(ans, a) and contains(ans, b):
            return 1.0
        if CLASH.search(ans):
            return 1.0
        if says_idk(ans):
            return 0.5
        return 0.0

    if axis == "CONFLICT":
        # Rejecting the premise is not enough. It must also give the latest value.
        # The answer looks like "no, it's daily now", so removing the leading negation
        # leaves the latest value.
        gold = q.get("gold_answer") or ""
        latest = strip_neg(gold)
        got_neg = bool(NEG.search(ans))
        # ⚠️ This used to look at latest only. The conversation says "replaced them all
        #    with metal pipe" while the answer is written "metal pipe now", so some
        #    questions could not be matched even when answered correctly. Accepted
        #    wordings are checked too.
        cands = [latest] + [strip_neg(g) for g in (q.get("gold_alts") or [])] \
                         + list(q.get("gold_alts") or [])
        got_val = any(contains(ans, c) for c in cands if c)
        if got_neg and got_val:
            return 1.0
        # ⚠️ Negation alone used to earn 0.5. But words like no/not/changed appear in any
        #    text. Of 19 randomly picked texts, 15 were caught here and none contained the
        #    latest value, so chance scored 39.5%. Half credit is given only when the latest
        #    value is there. "No" alone shows nothing.
        if got_val:
            return 0.5
        return 0.0

    # Looking at one written form of the answer marks answers with the right meaning wrong.
    # That happens when the conversation says "I really hate it" and the answer reads
    # "dislikes it". Any accepted wording listed in gold_alts counts as correct.
    for g in [q.get("gold_answer")] + list(q.get("gold_alts") or []):
        if g and contains(ans, g):
            return 1.0
    return 0.0


def retrieval_hit(q, got_turns, got_text=None, reported=False):
    """Was the evidence among what came back. If not, retrieval failed.

    ⚠️ Looking only at turn numbers is **unfair to systems that return summaries.** A
       system that returns "the user said their knees are bad" instead of the original
       has no turn number, and would count as not finding it even when it did.

       So without turn numbers, the check is **whether the returned text contains the
       answer.** It measures the same thing: did it bring back what was needed.

    ⚠️⚠️ **Questions where nothing came back were dropped from the denominator (until
       2026-09-17).** With both turns and text empty, it returned None (not countable).
       **The more a system stays silent on hard questions, the higher its recall.** In
       practice, asking BM25 in Korean leaves an empty query and returns nothing; those
       questions were dropped, and cross-language recall showed **4.1% of 170 questions**
       instead of 1.8% of 390.
       Now `reported`, whether it **supplied the field** for turns or memories, decides:
         supplied but empty   -> for a question with evidence to find, **not found** (False)
         field not supplied   -> not reported, so None (not countable)
    """
    ev = set(q.get("evidence_turns") or [])
    if got_turns:
        if not ev:
            return None
        return bool(ev & set(got_turns))
    if got_text:
        golds = [q.get("gold_answer")] + list(q.get("gold_alts") or [])
        return any(contains(got_text, g) for g in golds if g)
    if reported and ev:
        return False
    return None


def speed_points(latency_ms, target_ms):
    """Speed score for one question. -1 (very slow) to +1 (very fast).

    **An earlier version broke here.** Penalties were counted per question, so when 2,708
    questions went over one second the result was -270.8 points on a test out of 100.
    Adding questions only grew the penalty automatically. So speed was removed altogether.

    This time three things prevent it.
      1) Each question is **clamped** to -1..+1. However slow, it loses no more.
      2) **The average** is used, not the sum. Adding questions does not move the total.
      3) It is **shown separately** from accuracy, and when combined the weight is stated.

    Half the target time or faster is full marks; four times slower is the full penalty.
    In between is spread on a log scale. Ratios are used because the difference between
    200ms and 400ms matters more than between 3s and 3.2s.
    """
    if latency_ms is None or latency_ms <= 0 or target_ms <= 0:
        return None
    r = latency_ms / float(target_ms)
    if r <= 0.5:
        return 1.0
    if r >= 4.0:
        return -1.0
    # joined with log2 so that r=0.5 -> +1, r=1 -> 0, r=4 -> -1
    v = -math.log(r, 2)
    return max(-1.0, min(1.0, v / (1.0 if v >= 0 else 2.0)))


# Axes where retrieving nothing is the correct result. The memory mode cannot score them.
# The judge prompt says "if the memories are empty, WRONG", and if something is retrieved,
# a memory cannot say "I don't know", so that is WRONG too. **Either way it scores 0.**
# dry already excluded these two as not scorable for the same reason. Excluded the same way.
NO_MEMORY_AXES = ("ABSTAIN", "FALSE_MEMORY")


def is_no_memory(q):
    u"""Is this a question where retrieving nothing is the correct result.

    ⚠️ The axis name alone is not enough. 10 cross-language XLING_QUERY questions come
       from an ABSTAIN original (Q326 in 10 languages). The axis is XLING_QUERY, but the
       answer is "it never came up".
    """
    return q.get("axis") in NO_MEMORY_AXES or q.get("expect") == "no_memory"


def memory_list(r):
    u"""Take the 'returned memories' from a run record as a list of texts."""
    m = r.get("memories_returned")
    if isinstance(m, list):
        return [str(x) for x in m if x is not None]
    if isinstance(m, str):
        return [m]
    # A run with no memory field that put the retrieved text in the answer slot: that text is the memory
    if r.get("answer_generated") is False and r.get("answer"):
        return [r["answer"]]
    return []


def judge_scores(runs, Q, mode, key, workers=8):
    u"""Score each question with the judge LLM. {question id: {score, votes, ...}}

    ⚠️⚠️ **Until 2026-09-17 this path did not exist.** Given `--mode memory` or `answer`,
       the scorer stopped with exit code 1, saying it would be attached "after separate
       approval from the operator". That placeholder dated from the `judge` mode before
       09-09; only the name changed and the judge was never attached. Meanwhile the README
       told others to score with `--mode memory`, and ci_score.py called `memory` when a
       key was present. **There was no way to produce an official score with the
       published files.** judge.py's judge_memory and judge_answer had never been called
       anywhere in the repository.

    ⚠️⚠️ **These prompts have not yet been sent to a real model (2026-09-17).** The floor
       and ceiling test (floor_ceiling.py) borrowed only the per-axis rule text
       (AXIS_RULE) and used its own prompts and calls, without required_memories. So
       check_score_judge.py **fakes only the network call** and runs the rest (prompt
       assembly, reading the verdict, aggregation) for real. **Whether a model answers
       these prompts properly is not caught that way.** On the first paid run, run about
       20 questions first and read the verdicts by eye.

    · The judge gets `question_en`. Cross-language questions are also scored against the
      English answer, so the English question is the reference. The question as asked
      (`question`) is used only for writing the answer.
    · In answer mode, if the submitter wrote answers with their own answer model
      (`answer_generated: true`), those answers are judged. If not, per the README table,
      "an LLM writes an answer from those memories": judge.ANSWER_MODEL writes it.
    · If a call still fails after retries, the question is left **not scorable, not 0,**
      and failures are counted separately. Scoring 0 would turn a network outage into a
      grade.
    """
    import judge as J
    from concurrent.futures import ThreadPoolExecutor

    def one(r):
        q = Q[r["id"]]
        ax = q["axis"]
        out = {"id": r["id"]}
        if mode == "memory" and is_no_memory(q):
            out["score"] = None
            out["why"] = u"not scorable in memory mode (the answer is 'it never came up')"
            return out
        # For an abstention question, judge by the abstention rule. The axis rule
        # (XLING_QUERY: "FULL if it gives the same fact") cannot judge "it never came up" correctly.
        if is_no_memory(q) and ax not in NO_MEMORY_AXES:
            ax = "ABSTAIN"
        mems = memory_list(r)
        gold, req, alts = (q.get("gold_answer"), q.get("required_memories") or [],
                           q.get("gold_alts"))
        judged_q = q.get("question_en") or ""
        try:
            if mode == "memory":
                s, votes = J.judge_memory(judged_q, gold, req, mems, ax, key, alts)
            else:
                ans = r.get("answer") or ""
                if r.get("answer_generated") is not True:
                    asked = q.get("question") or judged_q
                    ans = J.generate_answer(asked, mems, key)
                    out["generated_answer"] = ans
                out["answer_used"] = ans
                s, votes = J.judge_answer(judged_q, gold, req, ans, ax, key, alts)
            out["score"], out["votes"] = s, votes
        except Exception as e:
            out["score"] = None
            out["error"] = str(e)[:300]
        return out

    todo = [r for r in runs if r.get("id") in Q]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return {x["id"]: x for x in ex.map(one, todo)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runfile", help="jsonl with one {id, answer, retrieved_turns} per line")
    ap.add_argument("--questions", default="questions_medium.jsonl")
    ap.add_argument("--mode", required=True, choices=["memory", "answer", "dry"],
                    help="Required. A different mode moves the total.")
    ap.add_argument("--flow-limit", type=float, default=1000.0,
                    help="The limit (ms) within which people feel the flow is not broken. "
                         "The 1 second of Miller 1968, Card 1991 and Nielsen 1993. Default 1000")
    ap.add_argument("--llm-ttft", type=float, default=500.0,
                    help="Time (ms) for the LLM used alongside to produce its first token. "
                         "The LLM runs after memory retrieval, so this comes out of the memory's share. "
                         "The default 500 is a round figure we chose, not a measurement of any model")
    ap.add_argument("--speed-target", type=float, default=None,
                    help="Set the time (ms) allowed for memory directly. "
                         "If not given, it is flow-limit minus llm-ttft")
    ap.add_argument("--speed-weight", type=float, default=5.0,
                    help="How many points speed can move the total. Default 5. "
                         "0 leaves speed out of the total and only shows it separately")
    ap.add_argument("--conv", default=None,
                    help="Conversation file. If not given, found from the question file name. "
                         "Used only to compute the 'amount actually needed' for token efficiency")
    ap.add_argument("--out", default=None)
    # ⚠️⚠️ **Non-compliance was printed but the exit code was 0 (2026-09-15).**
    #    Fine while a person reads the screen, but once this scoring is wired into CI it
    #    becomes "non-compliant but green", a check that only prints. The default is left
    #    as is (someone who came to see a score must not be blocked); --strict is added
    #    only when it is used as a gate.
    ap.add_argument("--strict", action="store_true",
                    help=u"exit code 1 if non-compliant. For filtering submissions automatically")
    ap.add_argument("--workers", type=int, default=8,
                    help=u"how many judge calls run at once (memory/answer only). Default 8")
    ap.add_argument("--tier", default=None, choices=["core", "small", "medium", "full"],
                    help=u"which tier's conversation was stored. Used when scoring questions_xling.jsonl: "
                         u"evidence turns are taken from that tier's questions and the conversation file is that tier's")
    a = ap.parse_args()
    _bad = []          # submission requirements not met. --strict stops here

    # Time allowed for memory = the limit people tolerate - the time the LLM uses first
    #
    # Why not just 1 second: the 1 second covers **from asking to seeing the answer.**
    # What we measure is only the memory retrieval, and the LLM runs after that.
    #
    #    [retrieve memory] -> [build prompt] -> [LLM first token] -> the person starts reading
    #    '-- what we measure --'   '------- not ours -------'
    #
    # So the LLM's share is taken off first and only the rest goes to memory. Otherwise
    # memory could use the whole second and still score full marks while the real user
    # waits 1.5 seconds.
    if a.speed_target is None:
        a.speed_target = max(50.0, a.flow_limit - a.llm_ttft)

    # ⚠️⚠️ What stood here was a placeholder that **always exited**, saying it would be
    #    attached "after approval from the operator". **An internal rule** meant to stop
    #    money being spent on our key had shipped in the public scorer as is (until
    #    2026-09-17). The condition that guards money is not "operator approval" but
    #    **"does the person running it have their own key"**.
    key = ""
    if a.mode in ("memory", "answer"):
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            sys.exit("--mode %s calls the judge LLM (answer also calls the answer LLM). "
                     "Put your own key in the OPENROUTER_API_KEY environment variable. "
                     "Every call is billed to that key. "
                     "To look without a key, use --mode dry (a development ruler, not a score to publish)"
                     % a.mode)

    # For verifying token usage. Questions where the reported value and the actual differ / that cannot be verified
    MISMATCH, UNVERIFIED, SHRUNK, NOTURNS = [], [], [], []
    # memories_returned holding a count instead of text. Then chars_returned cannot be checked
    MEM_COUNT_ONLY = []
    # three-way tally for trap questions
    STALE_CNT, STALE_BAD, STALE_REACHED = collections.Counter(), [], []
    CX_CNT, CX_BAD = collections.Counter(), []

    Q = {q["id"]: q for q in
         (json.loads(l) for l in io.open(os.path.join(HERE, a.questions), encoding="utf-8"))}
    runs = [json.loads(l) for l in io.open(a.runfile, encoding="utf-8")]

    # Token efficiency needs 'the amount the answer actually needs', which is the size of the evidence turns.
    # The conversation file of the same tier is found from the question file name. If missing, skipped.
    CORP = {}
    _tier = a.tier or (os.path.basename(a.questions)
                       .replace("questions_", "").replace(".jsonl", ""))
    conv = a.conv or os.path.join(HERE, "glasshouse_v0.1_%s.jsonl" % _tier)
    if os.path.exists(conv):
        CORP = {r["turn_id"]: r for r in
                (json.loads(l) for l in io.open(conv, encoding="utf-8"))}

    # ⚠️⚠️ **Cross-language questions carry no evidence turns.** Turn numbers restart in
    #    every tier, and questions_xling.jsonl is a single file with no tier, so they
    #    cannot be written in. Until 2026-09-17 the scorer therefore **could not see
    #    whether retrieval worked at all** on the 800 cross-language questions (the recall
    #    column was '-'), for submitted systems and for our baselines alike.
    #
    #    Instead each question carries its original id (source_id). If the original is in
    #    that tier's question file with evidence turns, they are borrowed. The file is not
    #    changed (in memory only). 390 of the 800 are found this way (240 core storyline,
    #    150 photo). The other 410 have no evidence turns in the original either, so **a
    #    machine cannot check them**: the ones stored in a foreign language (XLING_STORE
    #    300), the ones asking those again in another language (100), and the ones whose
    #    original is an abstention question, where no evidence is the right answer
    #    (Q326 × 10).
    _need = [q for q in Q.values() if not q.get("evidence_turns") and q.get("source_id")]
    _tq = os.path.join(HERE, "questions_%s.jsonl" % _tier)
    if _need and a.tier and os.path.exists(_tq):
        _src = {x["id"]: x for x in (json.loads(l) for l in io.open(_tq, encoding="utf-8"))}
        _got = 0
        for q in _need:
            s = _src.get(q["source_id"])
            if s and s.get("evidence_turns"):
                q["evidence_turns"] = list(s["evidence_turns"])
                _got += 1
        print("Evidence turns borrowed from the original questions (%s): %d / %d questions"
              % (os.path.basename(_tq), _got, len(Q)))
    elif _need:
        print("⚠️ %d questions have no evidence turns. Pass --tier to borrow them from the "
              "original questions and check retrieval" % len(_need))

    JS = {}
    if a.mode in ("memory", "answer"):
        import judge as _J
        _todo = [r for r in runs if r.get("id") in Q]
        _skip = sum(1 for r in _todo
                    if a.mode == "memory" and is_no_memory(Q[r["id"]]))
        _n = len(_todo) - _skip
        print("Calling judge %s %d times%s. Billed to the owner of OPENROUTER_API_KEY."
              % (", ".join(m for m, _ in _J.JUDGES), _n * len(_J.JUDGES),
                 "" if a.mode == "memory" else
                 " (questions without a written answer also call the answer LLM %s)" % _J.ANSWER_MODEL))
        if _skip:
            print("  %d questions whose answer is 'it never came up' (%s etc.) cannot be scored in memory mode, "
                  "so they are not sent (not scorable)." % (_skip, "·".join(NO_MEMORY_AXES)))
        JS = judge_scores(runs, Q, a.mode, key, workers=a.workers)
        _fail = [i for i, x in JS.items() if x.get("error")]
        if _fail:
            print("  🔴 %d questions where the judge call failed after retries, left not scorable: %s"
                  % (len(_fail), ", ".join(_fail[:8])))
            print("     first error: %s" % JS[_fail[0]]["error"])
            _bad.append(u"judge call failed on %d questions" % len(_fail))

    by = collections.defaultdict(lambda: {"n": 0, "hit": 0.0, "ungraded": 0,
                                          "ret_n": 0, "ret_hit": 0,
                                          "sp_n": 0, "sp": 0.0, "lat": [],
                                          "chars": [], "ret_chars": 0,
                                          "ptok": 0, "ptok_n": 0, "net": None})
    rows = []
    for r in runs:
        q = Q.get(r["id"])
        if not q:
            continue
        # ⚠️⚠️ **`memories_returned` is the *text* of the returned memories, not a count.**
        #    (2026-09-15) SUBMITTING.md said "int, how many came back", while the two places
        #    below use this field as text (trap precondition, token efficiency). A
        #    submission following the docs with a number **crashed the scorer in two
        #    places.** Our baseline runs (_run_bm25_*.jsonl) had put a list of texts there
        #    from the start; only the docs were off. The docs were fixed, and it is
        #    normalised once here so a number does not crash it. Normalising separately in
        #    each user would miss one place again.
        _m = r.get("memories_returned")
        if isinstance(_m, list):
            r["_mem_text"] = " ".join(str(x) for x in _m)
        elif isinstance(_m, str):
            r["_mem_text"] = _m
        else:
            if _m is not None:
                MEM_COUNT_ONLY.append(r["id"])
            r["_mem_text"] = None
        # ⚠️ In a run that put 'retrieved text' in the answer slot, abstention and invention
        #    cannot be scored. Phrases like "I don't have time" are common in the
        #    conversation (739 in all), and the scorer reads them as "correctly said it is
        #    not in memory". It is not an answer, so it counts as **not scorable,** neither
        #    0 nor full marks.
        gen = r.get("answer_generated")
        if a.mode == "dry":
            if gen is False and is_no_memory(q):
                s = None
            else:
                s = grade_exact(q, r.get("answer", ""))
            r["_answer_used"] = r.get("answer", "")
        else:
            _j = JS.get(r["id"], {})
            s = _j.get("score")
            # in answer mode, if the answer LLM wrote the answer, traps and contradictions are counted on that answer
            r["_answer_used"] = _j.get("answer_used", r.get("answer", ""))
        b = by[q["axis"]]
        if s is None:
            b["ungraded"] += 1
        else:
            b["n"] += 1
            b["hit"] += s
        # ⚠️ Looking only at the total blurs ② and ③ of the trap questions again. Telling
        #    them apart is why this axis exists, so they are counted separately.
        #
        # ⚠️⚠️ **First check whether the trap was actually a trap (precondition check).**
        #    The trap measures "how does it behave when it cannot find the changed value".
        #    If the system **did retrieve the new value,** the question was not a trap for
        #    that system. Retrieval simply worked, and mixing it into the trap figures
        #    stops the axis from measuring what it is meant to.
        #
        #    donk8r on r/AI_Agents proposed this axis, and followed up with this point:
        #      "make not-findable a **checked precondition,** not a property of the
        #       wording. Run retrieval first, confirm the changed value is not in the
        #       results, and only then score the answer. Revalidate when the retrieval
        #       setup changes. A question that cannot be found today is not unfindable forever."
        #
        #    Trying to prevent it by rewording questions does not work. Avoiding overlap
        #    only fools word search; an embedding retriever still pulls it up (donk8r).
        #    So **it is not fixed in advance but measured on every run, against that system.**
        #    To look offline in advance, use audit_stale.py (BM25).
        if q["axis"] == "STALE" and s is not None:
            ans = r.get("_answer_used", "")
            mem = r.get("_mem_text") or ""
            golds = [q.get("gold_answer")] + list(q.get("gold_alts") or [])
            reached = any(g and contains(mem, g) for g in golds)
            if reached:
                # The trap did not spring. The new value was in the retrieved results.
                STALE_CNT["not a trap (retrieved the new value)"] += 1
                STALE_REACHED.append(q["id"])
            elif s == 1.0:
                # Did not retrieve it but got it right. The reading model inferred it from elsewhere.
                STALE_CNT["gave the new value"] += 1
            elif s == 0.5:
                STALE_CNT["said it does not know"] += 1
            elif q.get("stale_answer") and contains(ans, q["stale_answer"]):
                STALE_CNT["gave the old value as current"] += 1
                STALE_BAD.append(q["id"])
            else:
                STALE_CNT["unrelated answer"] += 1
        # ⚠️ For contradictions too, the total alone blurs "I don't know" and "sure of one
        #    side". Telling them apart is why this axis exists, so they are counted separately.
        if q["axis"] == "CONTRADICT" and s is not None:
            ans = r.get("_answer_used", "")
            if s == 1.0:
                CX_CNT["said the values disagree"] += 1
            elif s == 0.5:
                CX_CNT["said it does not know"] += 1
            else:
                # ⚠️ Do not name these a/b. b is already the by[axis] statistics
                #    dictionary above; overwriting it crashes further down.
                _ca, _cb = q.get("clash_a"), q.get("clash_b")
                if (_ca and contains(ans, _ca)) or (_cb and contains(ans, _cb)):
                    CX_CNT["stated one value as fact"] += 1
                    CX_BAD.append(q["id"])
                else:
                    CX_CNT["unrelated answer"] += 1
        got_text = r.get("_mem_text")
        rh = retrieval_hit(q, r.get("retrieved_turns"), got_text,
                           reported=("retrieved_turns" in r or "memories_returned" in r))
        if rh is not None:
            b["ret_n"] += 1
            b["ret_hit"] += int(rh)
        # Score with the network round trip, which the system cannot help, taken out.
        # Otherwise geography decides the ranking: measured from Seoul, a US server takes 190ms even with zero compute.
        # ⚠️ What remains is not 'pure compute' but 'time minus the round trip'. Some response transfer is mixed in.
        lat, net = r.get("latency_ms"), r.get("network_ms")
        if lat is not None and net:
            lat = max(1.0, lat - net)
            b["net"] = net
        sp = speed_points(lat, a.speed_target)
        if sp is not None:
            b["sp_n"] += 1
            b["sp"] += sp
            b["lat"].append(lat)
        # Token efficiency: collect the amount returned per axis. The more returned, the
        # likelier the answer is inside it, so on accuracy alone **returning more gains for free.**
        # ⚠️ **The number the submitter wrote in is not trusted.** The returned text itself is counted.
        #    Trusting chars_returned alone would let token efficiency be faked by writing a
        #    small number there. memories_returned is both the material the answer was made
        #    from and the basis for scoring evidence recall, so cutting it lowers the score
        #    too. That is why it cannot be gamed.
        if got_text is not None:
            actual = len(got_text)
            b["chars"].append(actual)
            b["ret_chars"] += actual
            said = r.get("chars_returned")
            # Record when the reported value and the actual differ. 5% allows for differences in joining
            if said and abs(said - actual) > max(20, actual * 0.05):
                MISMATCH.append((r["id"], said, actual))
            # ⭐ **Checked against the original conversation.** This is the one thing the other side does not have.
            #    Claim "these turns came back" and we already know how long that text is.
            #    Shorten the text but keep the turn numbers, and it shows up here.
            tids = r.get("retrieved_turns") or []
            if CORP and tids:
                src = sum(len(CORP[t]["text"]) for t in tids if t in CORP)
                if src and actual < src * 0.5:
                    SHRUNK.append((r["id"], actual, src))
            elif not tids:
                NOTURNS.append(r["id"])
        elif r.get("chars_returned"):
            # Without returned text there is nothing to count. The reported value is counted separately as unverifiable.
            UNVERIFIED.append(r["id"])
        # Real tokens counted by the API. If present, no estimate is used.
        if r.get("prompt_tokens"):
            b["ptok"] += r["prompt_tokens"]
            b["ptok_n"] += 1
        row = {"id": r["id"], "axis": q["axis"], "score": s,
               "retrieval": rh, "latency_ms": r.get("latency_ms"),
               "speed_points": sp}
        # Keep each judge vote and the answer written by the answer LLM per question. With
        # only the score kept, nobody could ever check later whether a verdict was right.
        if r["id"] in JS:
            for _k in ("votes", "generated_answer", "error", "why"):
                if JS[r["id"]].get(_k) is not None:
                    row["judge_" + _k] = JS[r["id"]][_k]
        rows.append(row)

    print("Scoring mode: %s" % {
        "dry": "dry (string matching · no judge · development ruler)",
        "memory": "memory (the judge LLM reads the retrieved memories)",
        "answer": "answer (the judge LLM reads the answer)"}[a.mode])
    print()
    print("%-14s%7s%9s%9s%12s%11s%12s"
          % ("axis", "n", "score%", "ungraded", "retrieval%", "chars", "chars/hit"))
    tn = th = 0.0
    for k in sorted(by, key=lambda x: -by[x]["n"]):
        b = by[k]
        sc = 100 * b["hit"] / b["n"] if b["n"] else 0
        rr = 100 * b["ret_hit"] / b["ret_n"] if b["ret_n"] else float("nan")
        # chars per hit = characters spent to get one correct answer. It grows both when
        # returning a lot and when returning little but missing a lot. It is small only
        # when returning little and getting much right.
        avg_c = (sum(b["chars"]) / len(b["chars"])) if b["chars"] else 0
        per_hit = (b["ret_chars"] / b["hit"]) if b["hit"] else 0
        print("%-14s%7d%9.1f%9d%12s%11s%12s"
              % (k, b["n"], sc, b["ungraded"],
                 "-" if b["ret_n"] == 0 else "%.1f" % rr,
                 "-" if not avg_c else "%.0f" % avg_c,
                 "-" if not per_hit else "%.0f" % per_hit))
        tn += b["n"]
        th += b["hit"]
    print("-" * 74)
    if STALE_CNT:
        tot = sum(STALE_CNT.values())
        n_reach = STALE_CNT.get("not a trap (retrieved the new value)", 0)
        n_trap = tot - n_reach
        print()
        print("%d trap questions, %d of which were actually a trap for this system"
              % (tot, n_trap))
        # ⚠️ The denominator is n_trap, not tot. Dividing with the untriggered questions
        #    mixed in makes the 'insisted on the old value' rate look lower the better the
        #    retrieval. That is the opposite of what this axis measures. (donk8r's precondition point)
        if n_reach:
            print("   not a trap           %3d, retrieved the new value. Left out of the counts below"
                  % n_reach)
            print("     questions: %s" % ", ".join(STALE_REACHED[:10]))
        base = n_trap or 1
        for k in ("gave the new value", "said it does not know", "gave the old value as current", "unrelated answer"):
            if STALE_CNT.get(k):
                print("   %-16s %3d (%.0f%%)%s"
                      % (k, STALE_CNT[k], 100.0 * STALE_CNT[k] / base,
                         "   <- what goes wrong in real use" if k == "gave the old value as current" else ""))
        if STALE_BAD:
            print("   questions where it insisted on the old value: %s" % ", ".join(STALE_BAD[:10]))

    if CX_CNT:
        tot = sum(CX_CNT.values())
        print()
        print("%d contradiction questions, how it behaves when there is no correct value" % tot)
        for k in ("said the values disagree", "said it does not know", "stated one value as fact", "unrelated answer"):
            if CX_CNT.get(k):
                print("   %-16s %3d (%.0f%%)%s"
                      % (k, CX_CNT[k], 100.0 * CX_CNT[k] / tot,
                         "   <- what goes wrong in real use" if k == "stated one value as fact" else ""))
        if CX_BAD:
            print("   questions where it was sure of one side: %s" % ", ".join(CX_BAD[:10]))
        if not any(r.get("answer_generated") for r in rows):
            # ⚠️⚠️ In a run that generated no answers (a stand-in run like BM25) this axis
            #    is inflated. The 'answer' is the retrieved turns joined together, so as
            #    long as both values appear in it, it counts as "pointed out the
            #    disagreement". Nothing was actually pointed out. This axis inflates much
            #    more than others because the answer is **a relation,** not a value, which
            #    favours returning every value.
            print("   ⚠️ This run generated no answers (no --answers).")
            print("      Retrieved text that merely contains both values counts as full marks,")
            print("      so this axis is **inflated upward.** Do not use it for comparison.")
    acc = 100 * th / tn if tn else 0

    T_ch = sum(b["ret_chars"] for b in by.values())
    T_n = sum(len(b["chars"]) for b in by.values())
    print("%-14s%7d%9.1f%9s%12s%11s%12s"
          % ("accuracy", tn, acc, "", "",
             "%.0f" % (T_ch / T_n) if T_n else "-",
             "%.0f" % (T_ch / th) if (th and T_ch) else "-"))
    # ── Weighted score ────────────────────────────────────────────
    #
    # ⚠️⚠️ **Each question carries its own weight.** One question on a hard axis is worth
    #    more than one on an easy axis, like essay questions carrying more points in an exam.
    #
    #        score = Σ(question weight × correct) / Σ(question weight)
    #
    #    (Operator's decision, 2026-09-09. Before that the weights were applied to
    #     **per-axis accuracy,** so an axis with 7 questions and one with 733 had the same
    #     share, and question counts had no effect on the total. Now the count is part of
    #     the share. In exchange **every axis is filled to at least 30 questions** so the
    #     counts do not drift too far apart.)
    #
    # ⚠️ The weights are **values we chose.** Hiding them invites the charge of tuning
    #    the score. The table below is always printed, with the unweighted average
    #    alongside. The reasoning is in WEIGHTS.md.
    print()
    print("Weighted score: each question carries its axis weight")
    print("  %-12s %5s %6s %8s %9s %9s"
          % ("axis", "wgt", "n", "accuracy", "points", "max"))
    got = full = 0.0
    for k in sorted(by, key=lambda x: (-AXIS_WEIGHT.get(x, 1.0), x)):
        b = by[k]
        if not b["n"]:
            continue
        w = AXIS_WEIGHT.get(k, 1.0)
        sc = 100.0 * b["hit"] / b["n"]
        g, f = w * b["hit"], w * b["n"]
        got += g
        full += f
        print("  %-12s %5.1f %6d %8.1f %9.1f %9.1f" % (k, w, b["n"], sc, g, f))
    wacc = 100.0 * got / full if full else 0.0
    print("  " + "-" * 54)
    print("  %-12s %5s %6d %8s %9.1f %9.1f" % ("total", "", tn, "", got, full))
    print()
    print("  plain average %.1f  ·  **weighted %.1f**  (difference %+.1f)" % (acc, wacc, wacc - acc))
    print("  ※ Both numbers are always reported together. Every weight is in the table above.")

    # A system that cannot handle photos scores 0 on photo questions. That is the right
    # treatment (it is not that we cannot measure, it is that the system cannot do it).
    # But photos are 31% of the total, so a subtotal is shown too, letting text-only systems
    # be compared with each other. Nothing is taken away; both are shown.
    ti = by.get("IMAGE", {}).get("n", 0)
    if ti:
        tn2 = tn - ti
        th2 = th - by["IMAGE"]["hit"]
        print("%-14s%7d%9.1f   (%d photo questions excluded)"
              % ("  text only", tn2, 100 * th2 / tn2 if tn2 else 0, ti))

    # ------------------------------------------------------------ token efficiency
    #
    # **Why measure it.** The more a system returns, the likelier the answer is inside it.
    # So on accuracy alone **the one that hands out more gains for free.**
    # Our BM25 baseline showed exactly that (medium, evidence recall, 2026-09-17, see the
    # README Baselines section): 1 turn gave 16.0% at 66 characters, 20 turns gave 40.4% at
    # 1,679 characters. More than 25 times the text bought 24.3 percentage points.
    # ⚠️ Before this, "13.0% at 72 characters, 34.7% at 1,842 characters" was written here.
    #    On 2026-09-16 the README numbers had been copied **without checking the source.**
    #    Those were string-match scores from an old 08-30 build, with no run record left.
    #
    # **Simply letting the smaller output win is wrong.** Returning nothing is 0 characters.
    # So it is looked at as 'characters per correct answer': returning a lot grows the
    # numerator, and returning little while missing a lot shrinks the denominator, so both lose.
    #
    # ⚠️ **It is not part of the score yet.** There is no basis for deciding at what ratio
    #    to start penalising. Speed had an anchor, the '1 second people tolerate' (Miller
    #    1968 and others); tokens have none. Choosing now would be an invented number. It
    #    will be set with reasons once measurements from several systems exist; until then
    #    it is only measured and shown.
    print()
    if T_n:
        # ⚠️ **Characters are the reference; tokens are for information.**
        #    Characters are simply counted, but tokens differ by tokenizer. A real case: one
        #    vendor published figures assuming 2.91 characters per token when the real
        #    figure was 4.5 to 5.0, so the published numbers were overstated by 33 to 72%
        #    (corrected in its own paper). So we **report characters as they are** and
        #    attach tokens for information only, with the assumed ratio stated. Readers can
        #    apply their own tokenizer to the character count.
        CPT = 4.0        # assumed characters per token. Changing it changes the output below
        print("Token usage  ⭐ must always be reported with the results")
        print("  %.0f characters per question on average" % (T_ch / T_n))
        if th:
            print("  %.0f characters per correct answer" % (T_ch / th))
        P = sum(b["ptok"] for b in by.values())
        Pn = sum(b["ptok_n"] for b in by.values())
        if Pn:
            # ⭐ Counted by the API with that model's real tokenizer. Not an estimate.
            print("  %.0f prompt tokens per question, **measured by the API** (%d questions)"
                  % (P / Pn, Pn))
            print("     ⚠️ This includes the prompt template and the question. For the memories'")
            print("        share alone, subtract prompt_template_tokens from the run record.")
        else:
            print("  about %.0f tokens per question (assuming %.1f characters = 1 token)"
                  % (T_ch / T_n / CPT, CPT))
            print("  ⚠️ These tokens are **an estimate.** This run did not generate answers, so there")
            print("     is no API count. Characters are the reference; apply your own tokenizer to them.")
        print("  ⚠️ There is no absolute baseline. This value is for comparing systems.")
        print("     The more returned, the likelier the answer is inside, so accuracy reported")
        print("     without this value hides how much was spent to get the score.")
    else:
        print("🔴 Non-compliant: no token usage.")
        print("   The run record has no chars_returned, so how much was returned is unknown.")
        print("   Results missing this are **not accepted.** Accuracy alone cannot show")
        print("   whether the score came from handing out a lot.")
        _bad.append(u"no token usage (chars_returned)")

    if MEM_COUNT_ONLY:
        print()
        print("🔴 Non-compliant: memories_returned holds **a count instead of text** (%d questions)"
              % len(MEM_COUNT_ONLY))
        print("   e.g. %s" % ", ".join(MEM_COUNT_ONLY[:5]))
        print("   This field takes the **text** of the returned memories. With the text we can")
        print("   count it ourselves and check the chars_returned the submitter reported.")
        print("   With only a count, token efficiency could be faked by writing a small number there.")
        _bad.append(u"memories_returned is a count, not text (%d questions)"
                    % len(MEM_COUNT_ONLY))

    # ---------------------------------------------------------------- speed
    sp_n = sum(b["sp_n"] for b in by.values())
    lats = sorted(x for b in by.values() for x in b["lat"])

    # The cases where speed cannot be measured are fixed in advance (N1 to N4). When one
    # applies, speed is **left out, not scored 0.** Using it as a penalty would punish
    # architectures that are hard to measure.
    # This rule was set before the first measurement and is not changed after seeing results.
    NF_WHY = {"N1": "the server is behind a CDN, so the round trip only reaches the edge",
              "N2": "appears to be anycast",
              "N3": "the round trip is most of the total, so what remains is lost in noise",
              "N4": "retrieval cannot be called on its own"}
    nf = []
    npath = os.path.join(HERE, "_network.json")
    if os.path.exists(npath):
        try:
            nf = json.load(io.open(npath, encoding="utf-8")).get("flags") or []
        except Exception:
            nf = []
    print()
    if nf:
        print("Speed: **not measurable**, reason %s" % ", ".join(nf))
        for c in nf:
            print("      %s  %s" % (c, NF_WHY.get(c, "")))
        print("      Left out of the total. Accuracy stands as is. Not measurable is not a penalty.")
        total = acc
    elif not sp_n:
        print("Speed: cannot be measured, the run record has no latency_ms.")
        print("      (normal for a stand-in run like BM25, where response time means nothing)")
        total = acc
    else:
        sp_avg = sum(b["sp"] for b in by.values()) / sp_n          # -1 ~ +1
        med = lats[len(lats) // 2]
        p90 = lats[int(len(lats) * 0.9)]
        net = next((b["net"] for b in by.values() if b["net"]), None)
        chars = [c for b in by.values() for c in b["chars"]]
        print("Speed (time allowed for memory %.0fms · weight %.1f points)" % (a.speed_target, a.speed_weight))
        print("      = the limit people tolerate %.0fms - LLM first token %.0fms"
              % (a.flow_limit, a.llm_ttft))
        if net:
            print("  The measured value is 'time minus the %.0fms network round trip', not pure compute." % net)
            print("  Some response arrival time is mixed in, in proportion to the response size.")
        else:
            print("  ⚠️ No network_ms, so the round trip was not subtracted. A distant server loses that much.")
            print("     Measure it with measure_network.py and put it in the run record.")
        if chars:
            chars.sort()
            mid = chars[len(chars) // 2]
            print("  median response %d characters%s"
                  % (mid, "  ⚠️ over 14KB, so an extra round trip may have been added"
                     if mid > 14000 else ""))
        print("  median %.0fms · 90%% within %.0fms · faster than target on %d/%d questions"
              % (med, p90, sum(1 for x in lats if x < a.speed_target), sp_n))
        print("  speed score %+.2f  (-1 very slow to +1 very fast)" % sp_avg)
        delta = a.speed_weight * sp_avg
        total = acc + delta
        print()
        print("  accuracy %.1f  %+.1f (speed)  =  total %.1f" % (acc, delta, total))
        print("  ※ However slow, speed takes off at most %.1f points. It cannot overturn accuracy."
              % a.speed_weight)

    # ── Keep the token usage evidence in a file.
    #
    # Printed only to the screen, it disappears the moment the results are copied. How
    # much the submitter actually used **has to be in the result file** to be checked later.
    # If missing, it is recorded as not submitted.
    # ── Safeguards against faked numbers. Three layers.
    #
    #   ① count the real text          the reported chars_returned is not trusted (see above)
    #   ② record mismatches            if reported and actual differ, the question ids are kept
    #   ③ compare with a second count  a run that generated answers also has prompt_tokens
    #                                  counted by the API. Shorten the returned text but keep
    #                                  the tokens, and they disagree here
    #
    # ⚠️ Even this cannot stop **someone who ran it themselves and faked it from the
    #    start.** The only remedy is a third party rerunning it with their own key.
    verify = {}
    if MISMATCH:
        verify["reported_vs_actual_mismatch"] = len(MISMATCH)
        verify["mismatch_examples"] = [
            {"id": qid, "reported": said, "actual": real}
            for qid, said, real in MISMATCH[:20]]
    if UNVERIFIED:
        verify["unverifiable_no_text"] = len(UNVERIFIED)
    if SHRUNK:
        verify["less_than_claimed_turns"] = len(SHRUNK)
        verify["shrunk_examples"] = [
            {"id": qid, "reported": rep_c, "turns_hold": src_c}
            for qid, rep_c, src_c in SHRUNK[:20]]
    if NOTURNS:
        verify["no_turn_ids"] = len(NOTURNS)
    _P2 = sum(b["ptok"] for b in by.values())
    _Pn2 = sum(b["ptok_n"] for b in by.values())
    if _Pn2 and T_n:
        # Tokens computed from the returned text and tokens counted by the API should roughly agree.
        est = (T_ch / T_n) / CPT
        real = _P2 / _Pn2
        verify["chars_implied_tokens"] = round(est, 1)
        verify["api_counted_tokens"] = round(real, 1)
        verify["consistent"] = bool(real >= est * 0.5)   # template and question are added, so the measured value should be larger
    if verify:
        print()
        print("Token usage verification")
        if MISMATCH:
            print("  🔴 %d questions where the reported value differs from the actual" % len(MISMATCH))
            for qid, said, real in MISMATCH[:3]:
                print("     %s  reported %d characters / actual %d" % (qid, said, real))
            print("     -> Scored with the **actual character count.** The reported value is not used.")
        if UNVERIFIED:
            print("  🟡 %d questions not verified because no returned text was given" % len(UNVERIFIED))
        if SHRUNK:
            print("  🔴 %d questions whose text is less than half of the turns it claims to return" % len(SHRUNK))
            for qid, rep_c, src_c in SHRUNK[:3]:
                print("     %s  reported %d characters / those turns actually hold %d" % (qid, rep_c, src_c))
            print("     -> Normal for a system that returns summaries. **It has to say so.**")
            print("       Otherwise it cannot be told apart from shortening the text to look frugal.")
        if NOTURNS:
            print("  🟡 %d questions not checked against the original because there are no turn numbers" % len(NOTURNS))
            print("     -> Without turn numbers this check cannot run at all.")
        if verify.get("consistent") is False:
            print("  🔴 Tokens computed from characters (%.0f) and tokens counted by the API (%.0f) do not agree."
                  % (verify["chars_implied_tokens"], verify["api_counted_tokens"]))
            print("     Shortening the returned text while keeping the tokens is caught here.")


    tok = {"reported": bool(T_n)}
    if T_n:
        tok["chars_per_question"] = round(T_ch / T_n, 1)
        tok["chars_total"] = T_ch
        tok["questions_counted"] = T_n
        if th:
            tok["chars_per_correct"] = round(T_ch / th, 1)
        _P = sum(b["ptok"] for b in by.values())
        _Pn = sum(b["ptok_n"] for b in by.values())
        if _Pn:
            tok["prompt_tokens_per_question"] = round(_P / _Pn, 1)
            tok["prompt_tokens_source"] = "API usage (measured)"
            tok["questions_with_token_count"] = _Pn
        else:
            tok["tokens_per_question_estimated"] = round(T_ch / T_n / CPT, 1)
            tok["chars_per_token_assumed"] = CPT
            tok["prompt_tokens_source"] = "estimated (from character count)"
    else:
        tok["note"] = ("Token usage not submitted. The run record has no chars_returned. "
                       "A result without it is treated as not reporting token efficiency.")

    if verify:
        tok["verification"] = verify
    # ⚠️⚠️ **Per-axis results and the weighted score are kept in the file (2026-09-17).**
    #    Before, they were only printed and the file kept a single overall accuracy. So
    #    **nobody could say which file** the README's BM25 numbers (13.0, 34.7) or the
    #    24.6 and 20.9 in WEIGHTS.md came from. Every published number has to come from here.
    _axes = {}
    for k, b in by.items():
        _axes[k] = {"n": b["n"], "ungraded": b["ungraded"],
                    "score_pct": round(100.0 * b["hit"] / b["n"], 2) if b["n"] else None,
                    "weight": AXIS_WEIGHT.get(k, 1.0),
                    "retrieval_n": b["ret_n"],
                    "retrieval_pct": (round(100.0 * b["ret_hit"] / b["ret_n"], 2)
                                      if b["ret_n"] else None)}
    _rn = sum(b["ret_n"] for b in by.values())
    _rh = sum(b["ret_hit"] for b in by.values())
    _sum = {"_summary": {"accuracy": round(acc, 2),
                         "weighted_accuracy": round(wacc, 2), "n": tn,
                         "retrieval_pct": round(100.0 * _rh / _rn, 2) if _rn else None,
                         "retrieval_n": _rn,
                         "questions": os.path.basename(a.questions),
                         "runfile": os.path.basename(a.runfile),
                         "mode": a.mode, "by_axis": _axes, "token_usage": tok,
                         # the three-way trap and contradiction counts too. Printed only, nobody can say where they came from
                         "stale": dict(STALE_CNT), "stale_reached": list(STALE_REACHED),
                         "contradict": dict(CX_CNT)}}
    if JS:
        import judge as _J
        _sum["_summary"]["judge"] = {
            "models": [m for m, _ in _J.JUDGES],
            "answer_model": _J.ANSWER_MODEL if a.mode == "answer" else None,
            "judged": sum(1 for x in JS.values() if x.get("votes")),
            "failed": sum(1 for x in JS.values() if x.get("error"))}
    _sp = (a.out or a.runfile.rsplit(".", 1)[0]) + "_summary.json"
    json.dump(_sum, io.open(_sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print()
    print("Token usage evidence written to: %s" % os.path.basename(_sp))
    if not T_n:
        print("  -> recorded as reported: false. Token efficiency not submitted.")

    if a.out:
        with io.open(a.out, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("\nPer-question results: %s" % a.out)

    if _bad:
        print()
        print("🔴 %d submission requirements not met" % len(_bad))
        for x in _bad:
            print("   · %s" % x)
        if a.strict:
            print("   --strict, so the exit code is 1.")
            sys.exit(1)
        print("   (The score is above. To filter automatically, use --strict)")


if __name__ == "__main__":
    main()
