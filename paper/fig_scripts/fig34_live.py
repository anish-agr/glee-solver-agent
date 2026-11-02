"""Figure 5, right (placebo readings against the threshold) and Figure 6 (round-one acceptance and rating by closing round)."""
import gzip
import hashlib
import json
import os
import random
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "analysis"))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import style  # noqa: E402
from scoring import score  # noqa: E402

style.setup()
FEAT = os.path.join(ROOT, "logs", "features.jsonl.gz")


def gid_int(gid):
    return int(hashlib.md5(gid.encode()).hexdigest()[:8], 16)


def st_of(d):
    fam, me = d["family"], d["me"]
    if fam == "bargaining":
        d1 = d.get("d_me") if me == 1 else d.get("d_opp")
        d2 = d.get("d_opp") if me == 1 else d.get("d_me")
        return dict(delta_1=d1, delta_2=d2, max_rounds=d.get("T"),
                    complete_information=d.get("complete_info", True),
                    messages_allowed=d.get("msgs", False),
                    money_to_divide=d.get("money"))
    if fam == "negotiation":
        v1 = d.get("my_value") if me == 1 else d.get("opp_value")
        v2 = d.get("opp_value") if me == 1 else d.get("my_value")
        return dict(player_1_value=v1, player_2_value=v2,
                    max_rounds=d.get("T"),
                    complete_information=d.get("complete_info", True),
                    messages_allowed=d.get("msgs", False))
    return dict(product_price=d.get("price"), v=None, p=d.get("p_high"),
                total_rounds=d.get("T") or 20,
                is_seller_know_cv=d.get("seller_knows_cv"),
                seller_message_type=d.get("msg_type") or "text")


scored = {"bargaining": [], "negotiation": [], "persuasion": []}   # (gidint, r)
cliff = {}          # share-to-opponent bucket -> [n, accepted_r1]
rounds_r = {}       # closing round -> ratings
for line in gzip.open(FEAT, "rt", encoding="utf-8"):
    d = json.loads(line)
    r = score(d["family"], st_of(d), d["me"],
              {f"player_{d['me']}_payoff": d["my_pay"]})
    if r is None:
        continue
    scored[d["family"]].append((gid_int(d["gid"]), r))
    if d["family"] == "bargaining":
        ar = d.get("agreed_round")
        if d.get("outcome") == "agreement" and ar:
            rounds_r.setdefault(min(ar, 8), []).append(r)
        if d["me"] == 1 and (d.get("my_offers") or []):
            to_them = 1.0 - d["my_offers"][0]
            b = round(to_them * 50) / 50.0
            e = cliff.setdefault(b, [0, 0])
            e[0] += 1
            e[1] += 1 if ar == 1 else 0

rng = random.Random(7)
pts = []
for _fam, rows in scored.items():
    for bit in (10, 11, 12, 13):
        a = [r for g, r in rows if (g >> bit) % 2 == 0]
        b = [r for g, r in rows if (g >> bit) % 2 == 1]
        for n in (200, 400, 800, 1600, 3200, 6400, 12800):
            if len(a) < n or len(b) < n:
                continue
            sa = rng.sample(a, n)
            sb = rng.sample(b, n)
            pts.append((n, abs(sum(sa) / n - sum(sb) / n)))

fig, ax = plt.subplots(figsize=(2.5, 1.75))
xs = np.array([p[0] for p in pts], dtype=float)
ys = np.array([p[1] for p in pts])
jit = xs * np.exp(np.array([rng.uniform(-0.06, 0.06) for _ in xs]))
ax.plot(jit, ys, "o", ms=2.6, color=style.BLUE, alpha=0.55, mew=0)
grid = np.geomspace(180, 16000, 100)
ax.plot(grid, 200.0 * np.sqrt(380.0 / grid), color=style.VERMILION, lw=1.2)
ax.annotate("decision threshold\n$200\\sqrt{380/n}$", xy=(0.97, 0.66),
            xycoords="axes fraction", ha="right", va="top",
            color=style.VERMILION, fontsize=6.5)

ax.set_xscale("log")
ax.set_xticks([200, 500, 1000, 2000, 5000, 10000])
ax.set_xticklabels(["200", "500", "1,000", "2,000", "5,000", "10,000"])
ax.minorticks_off()
top = 320.0
above = int((ys > top).sum())
if above:
    ax.set_ylim(0, top)
    ax.annotate(f"{above} split above {top:.0f}", xy=(0.98, 0.96),
                xycoords="axes fraction", ha="right", va="top",
                fontsize=6.5, color="#666666")
ax.set_xlabel("games per arm $n$")
ax.set_ylabel("|placebo split $\\Delta$| (rating)")
ax.grid(axis="y", alpha=0.6)
frac = float((ys <= 200.0 * np.sqrt(380.0 / xs)).mean())
print(f"fig3: {len(pts)} placebo splits, {frac:.1%} under the bar")
fig.savefig(os.path.join(HERE, "..", "figures", "fig3_placebo.pdf"))

fig, (a1, a2) = plt.subplots(1, 2, figsize=(5.52, 1.85),
                             constrained_layout=True)
bs = sorted(b for b, e in cliff.items() if e[0] >= 300 and 0.30 <= b <= 0.56)
ys4 = [100.0 * cliff[b][1] / cliff[b][0] for b in bs]
a1.plot(bs, ys4, "o", color=style.BLUE, ms=3.5)
for i in range(len(bs) - 1):          # no line across the missing 0.40 bucket
    if bs[i + 1] - bs[i] < 0.0201:
        a1.plot(bs[i:i + 2], ys4[i:i + 2], "-", color=style.BLUE, lw=1.4)
a1.set_xticks(bs)
a1.axvline(0.4999, color=style.VERMILION, lw=0.8, ls=":")
a1.annotate("exactly half", xy=(0.4955, 0.08), xycoords=("data", "axes fraction"),
            fontsize=6.5, color=style.VERMILION, ha="right")
a1.set_xlabel("share offered to opponent (our opening)")
a1.set_ylabel("accepted in round 1 (%)")
a1.grid(axis="y", alpha=0.6)
for b in bs:
    print(f"fig4a: {b:.2f} n={cliff[b][0]} acc={100.0*cliff[b][1]/cliff[b][0]:.1f}%")

ks = sorted(rounds_r)
means = [sum(rounds_r[k]) / len(rounds_r[k]) for k in ks]
a2.bar([str(k) if k < 8 else "8+" for k in ks], means, color=style.BLUE,
       width=0.62)
a2.axhline(0, color="#999999", lw=0.7)
a2.set_xlabel("round the bargain closed")
a2.set_ylabel("mean game rating")
a2.grid(axis="y", alpha=0.6)
fig.savefig(os.path.join(HERE, "..", "figures", "fig4_bargaining.pdf"))
print("wrote fig3_placebo.pdf, fig4_bargaining.pdf")
