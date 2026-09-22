# -*- coding: utf-8 -*-
u"""Vector baseline: find the turns closest in meaning. The most basic form of a modern
memory system.

**Why it exists (2026-09-17).** With BM25 as the only baseline, the benchmark is open to
"all you tested was word search". Retrieval comes in two basic kinds:

    do the words overlap       BM25              bm25_baseline.py
    is the meaning close       embeddings        this file

A memory system has to **beat both.** If it cannot beat the two most basic methods,
there is nothing to call a memory system.

**The only thing that differs from BM25 is the similarity function.** The document unit
(one turn), what the question is asked with, how many turns come back and what is
returned are all decided by **importing** the functions in bm25_baseline.py. Copies
drift apart, and once they do, "the vector baseline was set up to lose" becomes true.
There is no chunk size to choose either, since a turn is already a natural unit, so there
is no setting that could have been tuned against either method.

**Why this model.**
  - **It has to be multilingual.** 800 questions cross ten languages. An English-only
    model would score zero there by construction, which would amount to choosing a
    model that is bound to lose
  - **It has to be a widely used standard.** An unusual model would make the baseline an
    experiment
  - **It has to run locally at no cost.** API embeddings need a key and money, and the
    model behind them can change silently, at which point the baseline stops being one
  - The prefixes the model card asks for ("query: " / "passage: ") are used as given.
    They are not a setting we chose; leaving them out would handicap the model

**The exact revision is pinned.** If a model changes under the same name, the numbers
move without anyone noticing.

    intfloat/multilingual-e5-small @ 614241f622f53c4eeff9890bdc4f31cfecc418b3
    environment actually used on 2026-09-17:
      Python 3.10.11 · sentence-transformers 6.0.1 · torch 2.14.0+cpu
      transformers 5.17.0 · numpy 2.2.6

Only this file needs `sentence-transformers`. The scorer (score.py) still uses only the
standard library. If torch will not install on your Python, run just this file with a
Python it does install on; the run file it writes can be scored with any Python.

**There is no reader model,** as with the BM25 baseline. The "answer" is the retrieved
turns joined together, so what this baseline measures ends at **"did the evidence come
back".**

    python vector_baseline.py --tier medium --k 10
    python vector_baseline.py --tier medium --k 10 --qfile questions_xling.jsonl
    python vector_baseline.py --tier medium --k 10 --qfile questions_xling.jsonl --ask-english
"""
import argparse, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bm25_baseline as B        # noqa: E402  document unit, questions and run format come from here

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


def encoder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL, revision=REVISION, device="cpu")


def corpus_vectors(m, tier, rows):
    u"""Embed the conversation turns, keeping the result on disk for reuse.

    The cache is used only when it matches **the current conversation file's turn count
    and model revision.** An old cache after the conversation changed would give silently
    wrong results with shifted turn numbers.
    """
    import numpy as np
    stamp = "%s|%s|%d|%d" % (MODEL, REVISION, len(rows),
                             sum(len(r["text"]) for r in rows))
    cache = os.path.join(HERE, "_emb_%s_e5small.npy" % tier)
    meta = cache + ".stamp"
    if os.path.exists(cache) and os.path.exists(meta) \
            and io.open(meta, encoding="utf-8").read() == stamp:
        return np.load(cache)
    t0 = time.time()
    E = m.encode(["passage: " + r["text"] for r in rows], batch_size=64,
                 normalize_embeddings=True, show_progress_bar=False,
                 convert_to_numpy=True).astype("float32")
    np.save(cache, E)
    io.open(meta, "w", encoding="utf-8").write(stamp)
    print(u"  embedded %s, %d turns, in %.0fs" % (tier, len(rows), time.time() - t0))
    return E


def run(tier, k, qfile=None, english=False, m=None, E=None):
    import numpy as np
    rows, Q = B.load_inputs(tier, qfile)
    m = m or encoder()
    if E is None:
        E = corpus_vectors(m, tier, rows)
    QV = m.encode(["query: " + B.asked(q, english) for q in Q], batch_size=64,
                  normalize_embeddings=True, show_progress_bar=False,
                  convert_to_numpy=True).astype("float32")
    picked = []
    for i in range(0, len(Q), 256):
        S = QV[i:i + 256] @ E.T                          # normalised, so dot product = cosine
        for row in S:
            # On equal scores the earlier turn comes first, so the order never changes between runs
            top = np.argsort(-row, kind="stable")[:k]
            picked.append([int(j) for j in top])
    rf = B.run_name("vector", tier, k, qfile, english)
    B.write_run(rf, rows, Q, picked)
    return rf, len(rows), len(Q)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="medium")
    ap.add_argument("--k", type=int, nargs="+", default=[10],
                    help=u"several values embed once and then run each in turn")
    ap.add_argument("--qfile", default=None,
                    help=u"another question file (for example questions_xling.jsonl); "
                         u"the conversation is the --tier tier")
    ap.add_argument("--ask-english", action="store_true",
                    help=u"control: ask foreign-language questions in English. Not a score")
    a = ap.parse_args()
    m = encoder()
    rows, _ = B.load_inputs(a.tier, a.qfile)
    E = corpus_vectors(m, a.tier, rows)
    for k in a.k:
        rf, n, nq = run(a.tier, k, a.qfile, a.ask_english, m=m, E=E)
        print(u"%s · vector · turns %d · questions %d · top %d retrieved -> %s"
              % (a.tier, n, nq, k, os.path.basename(rf)))
