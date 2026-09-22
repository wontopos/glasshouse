# -*- coding: utf-8 -*-
"""Scoring judge and answer generation. Every call goes through OpenRouter.

Design decisions (things the spec has to state):
  · One judge (JUDGES below). Three judges from different companies with a 2/3 majority
    were measured and gave effectively the same accuracy at three times the cost; the
    measurements are in the comment above JUDGES.
  · **The judge sees the model answer (gold_answer)** and scores against it.
    (Operator's decision, 2026-09-09. Before that it was hidden to avoid anchoring, a
     design carried over from an earlier version. Hidden, the judge decides for itself
     what counts as correct, and then a person cannot recount the result later.)
  · **Each axis has its own scoring rule** (README section "Scoring by axis"). The rule
    goes into the prompt.
  · Some axes score three ways, so the judge answers **FULL / PARTIAL / WRONG**.
    The prompt states outright that PARTIAL is not used on axes without partial credit.
  · Two scoring modes, both using the judge.
      memory  the judge reads the retrieved memories       -> judge_memory()
      answer  the judge reads the answer an LLM wrote      -> judge_answer()
    Answer model = gpt-4o-mini (operator's choice).
  · temperature 0.
"""
import os, json, time, urllib.request

OR_URL = "https://openrouter.ai/api/v1/chat/completions"

# Chosen by measurement on 2026-08-14, by accuracy against a machine answer key,
# not by version number.
#   gemini-3.7-flash    88.5% (spread 0.4)  <- chosen
#   gemini-3.1-flash-lite 86.9% (spread 1.0)
#   gemini-2.5-flash    82.1% (spread 0.4)
#   claude-haiku-4.5    81.6%
#   gpt-4o-mini         68.8%  <- called 39 items "correct" when nothing was there; wrong in one direction only
#   (note) majority of the top three 88.8% = effectively the same as 3.7-flash alone, at 3x the cost
# The risk of a single judge (one model's bias) is handled by publishing its accuracy alongside.
JUDGES = [
    ("google/gemini-3.7-flash", "Gemini 3.7 Flash"),
]
JUDGE_MAX_TOKENS = 2000   # A reasoning model, so generous. Too short and the body comes back empty.
ANSWER_MODEL = "openai/gpt-4o-mini"      # operator's choice

# ── Judge prompts ─────────────────────────────────────────────────────
#
# ⚠️⚠️ **The judge sees the model answer.** (Operator's decision, 2026-09-09)
#    It used to be hidden on the grounds that "seeing the answer pulls the judge toward
#    it (anchoring)". That was a design carried over unchanged from an earlier version.
#    Our answers are **model answers**, and scoring against them is right. Hidden, the
#    judge decides for itself what counts as correct, and then a person cannot recount.
#
# ⚠️ **What counts as correct differs by axis** (README section "Scoring by axis"). That
#    rule goes into the prompt. Without it, on "correct only if it abstains" questions an
#    answer that supplies a value gets called correct.
#
# ⚠️ Some axes score three ways. So instead of CORRECT/WRONG the judge gives **FULL /
#    PARTIAL / WRONG**. The prompt states outright that PARTIAL is not used on axes
#    without partial credit.

# Scoring rule per axis. A direct copy of the table in the README section "Scoring by axis".
AXIS_RULE = {
    "BASIC": "FULL if the answer gives the same fact as the model answer. "
             "No PARTIAL for this axis.",
    "PARAPHRASE": "FULL if the answer gives the same fact as the model answer, "
                  "even if worded very differently. No PARTIAL for this axis.",
    "IMAGE": "FULL if the answer names the same thing as the model answer. "
             "No PARTIAL for this axis.",
    "TEMPORAL": "FULL if the order or the interval matches the model answer. "
                "No PARTIAL for this axis.",
    "UPDATE": "FULL if the answer gives the CURRENT value from the model answer. "
              "PARTIAL if it says it does not know. "
              "WRONG if it gives the earlier value as if it were current.",
    "GATHER": "The model answer has more than one part. FULL if every part is "
              "there. PARTIAL if some parts are there and none are wrong. "
              "WRONG if none are there.",
    # ⚠️ What to do with "I don't know" has to be written down. Without it, the scorer
    #    (score.py) gave 0 while the judge could give PARTIAL (found 2026-09-10).
    #    If the two paths disagree, there is no telling which number to trust.
    #    On this axis both statements are plainly in the conversation, so not knowing is
    #    not the honest answer.
    "RECONCILE": "The history says two things that look incompatible but hold "
                 "under different conditions, so both are true. "
                 "FULL if the answer explains that both hold. "
                 "PARTIAL if it names only one side. "
                 "WRONG if it treats either side as false, and WRONG if it says "
                 "it does not know, because both statements are plainly stated.",
    "MULTI": "FULL if the combined or calculated value matches the model answer. "
             "No PARTIAL: naming one input without the result is WRONG.",
    "IMPLICIT": "FULL if the answer reaches the same conclusion as the model "
                "answer. No PARTIAL for this axis.",
    "CROSS": "FULL if the answer reaches the same conclusion as the model "
             "answer. No PARTIAL for this axis.",
    "CONFLICT": "The question contains a false premise. FULL if the answer both "
                "rejects the premise and gives the correct value from the model "
                "answer. PARTIAL if it gives the correct value without clearly "
                "rejecting the premise. WRONG if it accepts the premise.",
    "STALE": "FULL if the answer gives the current value from the model answer. "
             "PARTIAL if it says it does not know. "
             "WRONG if it gives the earlier value as if it were current.",
    "CONTRADICT": "The history holds two values that disagree and nothing "
                  "settles it. FULL if the answer says they disagree. "
                  "PARTIAL if it says it does not know. "
                  "WRONG if it picks one value and states it as fact.",
    "ABSTAIN": "Nothing in the history answers this. FULL if the answer says so. "
               "WRONG if it supplies any value. No PARTIAL for this axis.",
    "FALSE_MEMORY": "Nothing in the history answers this. FULL if the answer "
                    "says so. WRONG if it agrees or supplies a value. "
                    "No PARTIAL for this axis.",
}
DEFAULT_RULE = ("FULL if the answer gives the same fact as the model answer. "
                "No PARTIAL for this axis.")


def rule_for(axis):
    return AXIS_RULE.get(axis, DEFAULT_RULE)


# ── (1) Scoring the memories only ────────────────────────────────────
JUDGE_PROMPT = """You are scoring a memory system.

The system was asked a question about one user and returned some stored memories.
It did not write an answer. Judge the memories it returned.

Question:
{q}

Model answer (what a correct answer looks like):
{gold}
{alts}

Information the memories had to contain:
{req}

Memories the system returned:
{mems}

How to score this question type ({axis}):
{rule}

Wording may differ from the model answer; judge the meaning, not the words.

Extra detail is not an error. If the required information is there, say so even
when more is said around it. "Their knees and back" answers "their knees".
What makes it wrong is information that is missing, or that contradicts the
model answer. Say WRONG for a plausible-sounding value that is not the one in
the model answer.

If the memories are empty, the verdict is WRONG.
Reply with exactly one word: FULL, PARTIAL, or WRONG."""


# ── (2) Scoring the answer ───────────────────────────────────────────
ANSWER_JUDGE_PROMPT = """You are scoring an assistant's answer.

The assistant was asked a question about one user and answered from stored
memories. Judge the answer.

Question:
{q}

Model answer (what a correct answer looks like):
{gold}
{alts}

Information the answer had to convey:
{req}

The assistant's answer:
{ans}

How to score this question type ({axis}):
{rule}

Wording may differ from the model answer; judge the meaning, not the words.

Extra detail is not an error. If the required information is there, say so even
when more is said around it. "Their knees and back" answers "their knees".
What makes it wrong is information that is missing, or that contradicts the
model answer. Say WRONG for a plausible-sounding value that is not the one in
the model answer.

Reply with exactly one word: FULL, PARTIAL, or WRONG."""

# ⚠️⚠️ **Why both prompts above say "extra detail is not an error"**
#    (measured in the floor and ceiling test, 2026-09-10).
#      answer "their knees"  response "Their knees and back give them trouble."  -> WRONG
#      answer "the course"   response "...it's from week 3 of the course..."     -> WRONG
#    The response **contained the answer word for word** and was still marked wrong.
#    31 of the 225 misses at the ceiling were this. A judge doing this **cuts every
#    system's score across the board,** and it is easy to mistake for a question defect.
#
#    ⚠️ That does not mean making it lenient. In the pick_judge.py measurement, this judge
#       was chosen because **it let no plausible wrong answer through.** So the prompt
#       also states "missing or contradicting is wrong" and "a plausible other value is
#       wrong".

# ⚠️ This prompt does not tell the model "say you don't know if you don't know".
# That would give the answer away, and the test of whether it invents would no longer hold.
# (Measured 2026-08-14: with that instruction, a system with 0 memories scored 5/5.)
ANSWER_PROMPT = """You are an assistant with access to stored memories about a user.
Here are the memories retrieved for this question.

Memories:
{mems}

Question: {q}
Answer in one or two sentences."""

ABSTAIN_PROMPT = """You are scoring a memory retrieval system.

The user asked a question whose answer was never stated anywhere in the stored
conversation, and cannot be derived from what was stated.

Question: {q}
What the system returned:
{mems}

Decide only this: do the returned memories actually contain the answer to the question,
either stated outright or derivable by simple arithmetic from what is shown?

Answer CORRECT if they do NOT contain the answer.
Answer WRONG if the answer is in fact present or directly derivable.
Ignore whether the memories are on-topic. Only the answer matters.
Reply with exactly one word: CORRECT or WRONG."""


# Reproducibility: OpenRouter can send the same model to a different upstream server on
# each call. A different server can answer the same input differently, so the provider is
# pinned to the original maker and fallback is off. Which server actually answered is
# recorded on every call.
PROVIDER_ORDER = {
    "openai/gpt-4o-mini":          ["OpenAI"],
    "anthropic/claude-haiku-4.5":  ["Anthropic"],
    "google/gemini-2.5-flash":     ["Google AI Studio", "Google Vertex"],
    "google/gemini-3.7-flash":     ["Google AI Studio", "Google Vertex"],
    "google/gemini-3.1-flash-lite":["Google AI Studio", "Google Vertex"],
}
PROVIDERS_SEEN = {}     # collects the servers that actually answered during the run


def _call(model, prompt, key, max_tokens=200, retries=3, want_usage=False):
    """With want_usage=True, returns (body, usage).

    ⚠️ Tokens are **not estimated.** The API returns in usage the count made by that
       model's real tokenizer. Multiplying character counts by a ratio goes wrong: one
       vendor published figures assuming 2.91 characters per token, and corrected them in
       its own paper when the real figure turned out to be 4.5 to 5.0, a 33 to 72%
       overstatement."""
    payload = {
        "model": model, "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if model in PROVIDER_ORDER:
        payload["provider"] = {"order": PROVIDER_ORDER[model], "allow_fallbacks": False}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(OR_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            PROVIDERS_SEEN.setdefault(model, set()).add(d.get("provider", "?"))
            c = d["choices"][0]["message"].get("content")
            if not c:   # a reasoning model can spend max_tokens thinking and return an empty body
                raise ValueError(f"empty response (finish={d['choices'][0].get('finish_reason')})")
            if want_usage:
                return c.strip(), (d.get("usage") or {})
            return c.strip()
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{model} call failed: {last}")


def generate_answer(question, memories, key, want_usage=False):
    mems = chr(10).join("- %s" % m for m in memories) or "(none)"
    return _call(ANSWER_MODEL, ANSWER_PROMPT.format(mems=mems, q=question), key,
                 want_usage=want_usage)


def empty_prompt_tokens(key):
    """Token count of the prompt with no memories in it.

    Subtracting this gives **the share taken by the memories.** The prompt template and
    the question use tokens too; without subtracting, a system with short memories looks
    worse than it is."""
    _t, u = _call(ANSWER_MODEL, ANSWER_PROMPT.format(mems="(none)", q="x"), key,
                  max_tokens=1, want_usage=True)
    return u.get("prompt_tokens") or 0


SCORE = {"FULL": 1.0, "PARTIAL": 0.5, "WRONG": 0.0}


def _verdict(text):
    u"""Pull the verdict out of what the judge wrote.

    ⚠️ Searching from the front is wrong. A reasoning model may write "not PARTIAL, this
       is FULL". **The last of the words to appear** is taken as the verdict.
    """
    up = (text or "").upper()
    best, pos = "WRONG", -1
    for w in ("FULL", "PARTIAL", "WRONG"):
        i = up.rfind(w)
        if i > pos:
            best, pos = w, i
    return SCORE[best] if pos >= 0 else 0.0


def _vote(prompt, key):
    u"""Ask each judge and use **the middle value**.

    ⚠️ With three possible scores, a majority does not always exist (one vote each for
       FULL, PARTIAL and WRONG). The median then keeps the middle verdict, so there is
       always a result. With a single judge, that one vote is the result.
    """
    votes = {}
    for mid, name in JUDGES:
        votes[name] = _verdict(_call(mid, prompt, key, max_tokens=JUDGE_MAX_TOKENS))
    vals = sorted(votes.values())
    return vals[len(vals) // 2], votes


def _alts_block(alts):
    u"""Show the judge the accepted alternative wordings.

    ⚠️⚠️ **They used to be hidden.** The judge scored against the single main answer only.
       But the main answer is often **a summary word** we wrote. 137 questions are like
       that: the conversation says "I just tough it out" and the main answer is
       "avoids it".
       A system that answered in the conversation's own words was then marked wrong. In
       the floor and ceiling test on 2026-09-10 it actually lost points this way.
           question "What do they do when something hurts?"
           main answer "avoids it"   response "They tough it out."  -> WRONG
       "tough it out" was already among the accepted wordings; the judge never saw it.

    ⚠️ The rule is that accepted wordings contain **only words the conversation actually
       used** (enforced by prune_loose_alts and fix_broad_alts). So showing them does not
       make the judge lenient; it shows **what the answer really looks like.**
    """
    alts = [a for a in (alts or []) if a]
    if not alts:
        return ""
    return ("\nAlso accepted, these are the words the conversation itself uses:\n"
            + "\n".join("- %s" % a for a in alts))


def judge_memory(question, gold, required, memories, axis, key, alts=None):
    u"""(1) The judge reads the retrieved **memories**. No answer LLM."""
    p = JUDGE_PROMPT.format(
        q=question, gold=gold or "(none)", alts=_alts_block(alts),
        req="\n".join("- %s" % r for r in required) or "(nothing required)",
        mems="\n".join("- %s" % m for m in memories) or "(nothing returned)",
        axis=axis, rule=rule_for(axis))
    return _vote(p, key)


def judge_answer(question, gold, required, answer, axis, key, alts=None):
    u"""(2) The judge reads the **answer** written by the answer LLM."""
    p = ANSWER_JUDGE_PROMPT.format(
        q=question, gold=gold or "(none)", alts=_alts_block(alts),
        req="\n".join("- %s" % r for r in required) or "(nothing required)",
        ans=answer or "(no answer)",
        axis=axis, rule=rule_for(axis))
    return _vote(p, key)


# ⚠️ Old name, still used by score_pilot.py. Hands over to the new function.
def judge_retrieval(question, required, memories, key):
    ok, votes = judge_memory(question, None, required, memories, "BASIC", key)
    return ok >= 1.0, votes


def judge_abstain(question, memories, key):
    """ABSTAIN axis. No answer LLM.
    Checks only whether the retrieved memories actually contain the information, the same
    way as the other axes."""
    p = ABSTAIN_PROMPT.format(
        q=question,
        mems="\n".join(f"- {m}" for m in memories) or "(nothing returned)")
    votes = {}
    for mid, name in JUDGES:
        votes[name] = "CORRECT" in _call(mid, p, key, max_tokens=JUDGE_MAX_TOKENS).upper()
    need = 2 if len(JUDGES) >= 3 else 1
    return sum(votes.values()) >= need, votes
