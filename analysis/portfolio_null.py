"""Sequential null for the experiment portfolio, replayed on placebo splits."""
import collections
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEAT = os.path.join(ROOT, "logs", "features.jsonl.gz")
sys.path.insert(0, os.path.join(ROOT, "analysis"))
sys.path.insert(0, os.path.join(ROOT, "src"))
from score_local import rows, rate  # noqa: E402
from glee_agent.assignment import gid_int  # noqa: E402

BAR = lambda n: 200.0 * math.sqrt(380.0 / n)

# measured effect / threshold for the 22 experiments of the ledger table
ARM_RATIO = [-4.50, -2.00, -1.97, -1.79, -1.68, -1.52, -1.31, -1.26, -1.25,
         -1.24, -1.22, -1.00, -0.09, +0.04, +0.11, +0.49, +0.90, +1.33,
         +1.74, +1.82, +2.50, +4.80]


def ladder(k, lo=200, hi=16000):
    return [int(round(lo * (hi / lo) ** (i / (k - 1)))) for i in range(k)]


def main(looks=13):
    scored = collections.defaultdict(list)
    for d in rows(FEAT):
        r = rate(d)
        if r is not None:
            scored[d["family"]].append((gid_int(d["gid"]), r))

    steps = ladder(looks)
    rng = random.Random(2026)
    crossed = crossed_neg = splits = 0
    for rs in scored.values():
        for bit in range(14, 32):
            a = [r for g, r in rs if (g >> bit) % 2 == 0]
            b = [r for g, r in rs if (g >> bit) % 2 == 1]
            if min(len(a), len(b)) < steps[0]:
                continue
            rng.shuffle(a)
            rng.shuffle(b)
            splits += 1
            hit = hitneg = False
            for n in steps:
                if len(a) < n or len(b) < n:
                    break
                d = sum(a[:n]) / n - sum(b[:n]) / n
                if abs(d) > BAR(n):
                    hit = True
                if d < -BAR(n):
                    hitneg = True
            crossed += hit
            crossed_neg += hitneg
    q = crossed / splits
    q_neg = crossed_neg / splits

    # >= here, strict > in the replay above: a ratio of exactly -1.00 counts as crossing
    k = sum(1 for z in ARM_RATIO if abs(z) >= 1.0)
    neg = sum(1 for z in ARM_RATIO if z <= -1.0)
    n = len(ARM_RATIO)
    tail = lambda p: sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                         for i in range(k, n + 1))
    sign = sum(math.comb(k, i) for i in range(neg, k + 1)) / 2 ** k

    print(f"placebo splits            : {splits} (bits 14-31, {looks} looks)")
    print(f"crossing rate q           : {q:.3f}")
    print(f"arms crossing the bar     : {k} of {n} ({neg} negative)")
    tneg = lambda p: sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
                         for i in range(neg, n + 1))
    print(f"  of which cross negative : {q_neg:.3f}")
    print(f"P(>={k} of {n} cross | q={q:.3f}) : {tail(q):.3f}   [either direction]")
    print(f"P(>={neg} of {n} neg | q={q_neg:.3f})  : {tneg(q_neg):.3f}   [one direction]")
    print(f"sign test given crossing  : P(>={neg} of {k} negative) = {sign:.3f}")


if __name__ == "__main__":
    main()
