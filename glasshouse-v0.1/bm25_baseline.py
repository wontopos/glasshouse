# -*- coding: utf-8 -*-
"""BM25 baseline: plain word-overlap search, no AI involved.

Why it runs. Two reasons.

  1) **Does the pipeline run end to end.** Store the conversation, ask the questions,
     score. If this does not run, passing the checks means nothing.

  2) **Do the questions discriminate.** If word overlap alone gets them right, the test
     measures search, not memory. In particular this should hold:

       IMAGE   close to 0. A photograph has no words, so nothing can overlap.
               Anything above 0 means an answer is leaking from somewhere.
       ABSTAIN 0. BM25 always returns something, so it can never say "I don't know".
               This shows whether the questions that catch invention do their job.
       Scores should fall as the tier grows. More filler should make it harder.

BM25 is written out here with no library, using the standard formula.

  score(D,Q) = Σ IDF(q) · f(q,D)·(k1+1) / (f(q,D) + k1·(1-b+b·|D|/avgdl))

There is no reader model, so the "answer" is the text of the retrieved turns joined
together. The figure is therefore **the ceiling reachable by retrieval alone,** not real
performance. If the answer is not in what came back, no model could get it right.
"""
import json, io, os, sys, re, math, random, collections, argparse

HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN = re.compile(r"[a-z0-9]+")
STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "is", "was", "were",
        "are", "did", "do", "does", "and", "or", "that", "this", "with", "it",
        "they", "them", "their", "he", "his", "she", "her", "i", "my", "you",
        "your", "we", "our", "be", "been", "have", "has", "had", "there", "from",
        "what", "how", "when", "where", "which", "who", "why", "s", "t"}


def tok(s):
    return [w for w in TOKEN.findall(s.lower()) if w not in STOP and len(w) > 1]


class BM25:
    """Standard BM25. k1=1.5 and b=0.75 are the common defaults."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = docs
        self.dl = [len(d) for d in docs]
        self.avgdl = sum(self.dl) / max(1, len(docs))
        self.tf = [collections.Counter(d) for d in docs]
        df = collections.Counter()
        for t in self.tf:
            for w in t:
                df[w] += 1
        N = len(docs)
        # Standard BM25 IDF, with +1 inside so common words never go negative.
        self.idf = {w: math.log(1 + (N - n + 0.5) / (n + 0.5)) for w, n in df.items()}
        # word -> ids of the documents containing it, so the whole corpus is not scanned.
        self.inv = collections.defaultdict(list)
        for i, t in enumerate(self.tf):
            for w in t:
                self.inv[w].append(i)

    def top(self, query, k=5):
        q = tok(query)
        sc = collections.defaultdict(float)
        for w in q:
            if w not in self.idf:
                continue
            idf = self.idf[w]
            for i in self.inv[w]:
                f = self.tf[i][w]
                denom = f + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl)
                sc[i] += idf * f * (self.k1 + 1) / denom
        return sorted(sc.items(), key=lambda x: -x[1])[:k]


# ── Shared by both baselines ──────────────────────────────────────────────
#
# vector_baseline.py imports the three functions below rather than copying them. That
# makes "the only difference between BM25 and vector is the similarity function" true
# in code: the document unit (one turn), what is asked, how many come back and what is
# returned are decided in one place only.

def load_inputs(tier, qfile=None):
    u"""(conversation turns, questions). Without a question file, the tier's own."""
    corpus = os.path.join(HERE, "glasshouse_v0.1_%s.jsonl" % tier)
    qpath = os.path.join(HERE, qfile or ("questions_%s.jsonl" % tier))
    rows = [json.loads(l) for l in io.open(corpus, encoding="utf-8")]
    Q = [json.loads(l) for l in io.open(qpath, encoding="utf-8")]
    return rows, Q


def asked(q, english=False):
    u"""What the question is asked with.

    The 500 cross-language XLING_QUERY questions are asked with `question`, the foreign
    language one. Until 2026-09-16 this baseline asked everything with `question_en`,
    and it had never been run on the cross-language file at all. A question that carries
    that field is asked with it.
    `english=True` is **a control**: the same question asked in English, to see how much
    is lost to the language. It is not a score.
    """
    if english:
        return q["question_en"]
    return q.get("question") or q["question_en"]


def write_run(path, rows, Q, picked_per_q):
    u"""Write the run record in the SUBMITTING.md format."""
    with io.open(path, "w", encoding="utf-8") as fh:
        for q, picked in zip(Q, picked_per_q):
            text = " ".join(rows[i]["text"] for i in picked)
            fh.write(json.dumps({
                "id": q["id"],
                "answer": text,
                # There is no reader model. This field holds retrieved text, not an answer.
                "answer_generated": False,
                # For token efficiency: the scorer needs to know how much came back.
                "chars_returned": len(text),
                # For verification: the scorer counts this text, not the reported figure.
                "memories_returned": [rows[i]["text"] for i in picked],
                "retrieved_turns": [rows[i]["turn_id"] for i in picked]},
                ensure_ascii=False) + "\n")


def run_name(method, tier, k, qfile=None, english=False):
    tag = ""
    if qfile:
        tag = "_" + os.path.basename(qfile).replace("questions_", "").replace(".jsonl", "")
    return os.path.join(HERE, "_run_%s_%s%s%s_k%d.jsonl"
                        % (method, tier, tag, "_en" if english else "", k))


def run(tier, k, mode, seed=20260825, qfile=None, english=False):
    rows, Q = load_inputs(tier, qfile)

    # A document is one turn. Photo turns carry only a little text, so they rarely match.
    idx = BM25([tok(r["text"]) for r in rows]) if mode == "bm25" else None
    rnd = random.Random(seed)

    picked = []
    for q in Q:
        if mode == "bm25":
            picked.append([h[0] for h in idx.top(asked(q, english), k)])
        else:                                   # random picks = chance level
            picked.append(rnd.sample(range(len(rows)), min(k, len(rows))))

    rf = run_name(mode, tier, k, qfile, english)
    write_run(rf, rows, Q, picked)
    return rf, len(rows), len(Q)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="medium")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--mode", default="bm25", choices=["bm25", "random"])
    ap.add_argument("--qfile", default=None,
                    help=u"another question file (for example questions_xling.jsonl); "
                         u"the conversation is the --tier tier")
    ap.add_argument("--ask-english", action="store_true",
                    help=u"control: ask foreign-language questions in English. Not a score")
    a = ap.parse_args()
    rf, n, nq = run(a.tier, a.k, a.mode, qfile=a.qfile, english=a.ask_english)
    print("%s · %s · turns %d · questions %d · top %d retrieved -> %s"
          % (a.tier, a.mode, n, nq, a.k, os.path.basename(rf)))
