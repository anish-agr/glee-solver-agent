"""Figure 4: bargaining rating gap between the two seats in each configuration group."""
import collections
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "analysis"))
import style  # noqa: E402
from score_local import rows, rate, position  # noqa: E402

style.setup()

EXTRACT = os.path.join(HERE, "..", "..", "logs", "features.jsonl.gz")

SHORT = {"complete": "compl.", "incomplete": "incompl."}

cells = collections.defaultdict(lambda: collections.defaultdict(list))
beh = collections.defaultdict(lambda: collections.defaultdict(list))

for d in rows(EXTRACT, family="bargaining"):
    if d.get("profile") == "citadel":
        continue
    r = rate(d)
    if r is None:
        continue
    seat = 1 if int(d.get("me") or 1) == 1 else 2
    key = ("complete" if d.get("complete_info") else "incomplete",
           position(d), "capped" if d.get("T") else "uncapped")
    cells[key][seat].append(r)

    mp = float(d.get("my_pay") or 0)
    op = float(d.get("opp_pay") or 0)
    if mp + op > 0:
        beh[seat]["share"].append(mp / (mp + op))
    beh[seat]["nodeal"].append(0 if mp + op > 0 else 1)
    offers = d.get("my_offers") or []
    if offers and offers[0] is not None:
        beh[seat]["open"].append(float(offers[0]))

keep = [k for k in cells if min(len(cells[k][1]), len(cells[k][2])) >= 2000]
keep.sort(key=lambda k: sum(cells[k][1]) / len(cells[k][1]))
mean = lambda v: sum(v) / len(v)

fig, ax = plt.subplots(figsize=(5.52, 2.2), constrained_layout=True)

ys = list(range(len(keep)))
for y, k in zip(ys, keep, strict=True):
    p1, p2 = mean(cells[k][1]), mean(cells[k][2])
    ax.plot([p1, p2], [y, y], "-", color="#cfcfcf", lw=1.1, zorder=1)
    ax.plot(p1, y, "o", color=style.VERMILION, ms=3.6, zorder=2)
    ax.plot(p2, y, "s", color=style.BLUE, ms=3.2, zorder=2)
    ax.annotate(f"{p2 - p1:+.0f}", xy=(max(p1, p2), y),
                textcoords="offset points", xytext=(5, 0), va="center",
                fontsize=6.5, color="#666666")

ax.set_yticks(ys)
ax.set_yticklabels([f"{SHORT[a]}, {b}, {c}" for a, b, c in keep], fontsize=6.5)
ax.set_ylim(-0.6, len(keep) - 0.4)
ax.set_xlabel("mean game rating")
ax.set_xlim(1050, 3250)
ax.grid(axis="x", alpha=0.5)
ax.plot([], [], "o", color=style.VERMILION, ms=3.6, label="we move first")
ax.plot([], [], "s", color=style.BLUE, ms=3.2, label="we respond")
ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), frameon=False, ncol=2,
          handletextpad=0.3, columnspacing=1.0, fontsize=6.5,
          borderaxespad=0.1)

out = os.path.join(HERE, "..", "figures", "fig7_seat.pdf")
fig.savefig(out)
print("wrote", os.path.normpath(out))
for k in keep:
    print(f"  {k}: p1={mean(cells[k][1]):.0f} p2={mean(cells[k][2]):.0f} "
          f"gap={mean(cells[k][2]) - mean(cells[k][1]):+.0f}")
print(f"overall p1={mean([r for k in keep for r in cells[k][1]]):.0f} "
      f"p2={mean([r for k in keep for r in cells[k][2]]):.0f}")
print(f"open {mean(beh[1]['open']):.3f}/{mean(beh[2]['open']):.3f}  "
      f"share {mean(beh[1]['share']):.3f}/{mean(beh[2]['share']):.3f}  "
      f"nodeal {mean(beh[1]['nodeal'])*100:.2f}/{mean(beh[2]['nodeal'])*100:.2f}")
