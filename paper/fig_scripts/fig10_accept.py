"""Figure 7: round-one acceptance against the responder's continuation share, and the step at the even split."""
import collections
import gzip
import json
import math
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style  # noqa: E402

style.setup()
FEAT = os.path.join(HERE, "..", "..", "logs", "features.jsonl.gz")
MAXR = 2


def c_opp(dm, do):
    """Responder's continuation share under infinite-horizon Rubinstein. It
    depends on OUR discount, which a responder can only use by doing the
    strategic calculation; a norm defined on the split cannot see it."""
    den = 1.0 - dm * do
    return None if den <= 1e-12 else do * (1.0 - dm) / den


cells = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
with gzip.open(FEAT, "rt", encoding="utf-8") as fh:
    for line in fh:
        d = json.loads(line)
        if d.get("family") != "bargaining" or not d.get("complete_info"):
            continue
        dm, do = d.get("d_me"), d.get("d_opp")
        if dm is None or do is None:
            continue
        me = int(d.get("me") or 1)
        dec = d.get("decisions") or []
        for k, s_me in enumerate(d.get("my_offers") or []):
            if s_me is None:
                continue
            t = 2 * k + 1 if me == 1 else 2 * k + 2
            if t > MAXR or t - 1 >= len(dec):
                continue
            v = dec[t - 1]
            if v not in ("accept", "reject"):
                continue
            to_them = round((1.0 - float(s_me)) * 50) / 50.0
            e = cells[(dm, do)][to_them]
            e[0] += 1
            e[1] += 1 if v == "accept" else 0


def wilson(a, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = a / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


pts = []
for (dm, do), bk in cells.items():
    n, a = bk.get(0.48, [0, 0])
    c = c_opp(dm, do)
    if n < 100 or c is None:
        continue
    p, lo, hi = wilson(a, n)
    pts.append((c, p, lo, hi, n))
pts.sort()

mx = sum(q[0] for q in pts) / len(pts)
my = sum(q[1] for q in pts) / len(pts)
sxy = sum((q[0] - mx) * (q[1] - my) for q in pts)
sxx = sum((q[0] - mx) ** 2 for q in pts)
syy = sum((q[1] - my) ** 2 for q in pts)
r = sxy / math.sqrt(sxx * syy)
slope = sxy / sxx

fig, (a1, a2) = plt.subplots(1, 2, figsize=(5.52, 1.95),
                             constrained_layout=True)
xs = [q[0] for q in pts]
a1.errorbar(xs, [q[1] for q in pts],
            yerr=[[q[1] - q[2] for q in pts], [q[3] - q[1] for q in pts]],
            fmt="o", ms=2.8, lw=1.0, color=style.BLUE, ecolor="#5c93bd",
            capsize=0)
lo, hi = min(xs), max(xs)
a1.plot([lo, hi], [my + slope * (lo - mx), my + slope * (hi - mx)],
        color=style.VERMILION, lw=1.0, ls="--")
a1.annotate(f"$r={r:.2f}$", xy=(0.62, 0.80), xycoords="axes fraction",
            fontsize=6.5, color=style.VERMILION)
a1.set_xlabel("responder's continuation share $c_{\\mathrm{opp}}$")
a1.set_ylabel("P(accept) at $0.48$")
a1.set_ylim(0, 1.0)
a1.grid(axis="y", alpha=0.6)

steps = [(0.44, 0.46), (0.46, 0.48), (0.48, 0.50)]
bars = []
for b0, b1 in steps:
    num = den = 0.0
    tot = 0
    for bk in cells.values():
        n0, a0 = bk.get(b0, [0, 0])
        n1, a1_ = bk.get(b1, [0, 0])
        if n0 < 100 or n1 < 100:
            continue
        p0, p1 = a0 / n0, a1_ / n1
        var = p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1
        if var <= 0:
            continue
        num += (p1 - p0) / var
        den += 1.0 / var
        tot += n0 + n1
    bars.append((num / den, 1.96 / math.sqrt(den), tot))

labels = [f"${b0:.2f}\\!\\to\\!{b1:.2f}$" for b0, b1 in steps]
cols = ["#9ec6e0", "#9ec6e0", style.BLUE]
a2.bar(range(3), [b[0] for b in bars], yerr=[b[1] for b in bars],
       color=cols, width=0.6, ecolor="#666666", capsize=2.5, lw=0)
a2.set_xticks(range(3))
a2.set_xticklabels(labels, fontsize=6.5)
a2.set_xlabel("share offered to the opponent")
a2.set_ylabel("jump in P(accept)")
a2.axhline(0, color="#666666", lw=0.6)
a2.grid(axis="y", alpha=0.6)
a2.annotate("lands on\nthe even split", xy=(2, bars[2][0]),
            textcoords="offset points", xytext=(0, 12), ha="center",
            fontsize=6.5, color=style.BLUE)
a2.set_ylim(0, max(b[0] + b[1] for b in bars) * 1.55)

fig.savefig(os.path.join(HERE, "..", "figures", "fig10_accept.pdf"))
print(f"wrote fig10_accept.pdf; {len(pts)} cells, r={r:.3f}, slope={slope:.3f}")
for c, p, lo_, hi_, n in pts:
    print(f"  c_opp={c:.3f}  P={p:.3f} [{lo_:.3f},{hi_:.3f}]  n={n}")
for (b0, b1), (d, e, tot) in zip(steps, bars, strict=True):
    print(f"  step {b0:.2f}->{b1:.2f}: {d:+.3f} +/- {e:.3f}  N={tot}")
