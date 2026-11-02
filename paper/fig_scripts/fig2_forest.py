"""Figure 5, left: the experiments live on 15 August and the placebo row, read before and after deploy gating. Values are typed in from the readouts of that date."""
import os
import sys

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style  # noqa: E402

style.setup()

# name, stale delta, gated delta, gated bar, verdict, stale note
ARMS = [
    ("flat rec. schedule",      +301, -225,  50, "reverted", ""),
    ("hold-for-half",           +297,  -56,  45, "declined", ""),
    ("horizon-open",            +118,  +27,  30, "within threshold", ""),
    ("concession $k{=}1.5$",     +60,  -70,  35, "declined", ""),
    ("credibility 3 vs 6",        +0,  +24,  49, "within threshold", ""),
    ("buyer margin",             -31,   +7,  65, "within threshold", ""),
    ("accept $\\kappa$ 0.78",   -167,  +61,  35, "adopted", ""),
    ("weak-position cont.",     None, -159, 121, "declined", ""),
    ("placebo (unused bit)",    None,  -14,  27, "noise gauge", ""),
]

COLOUR = {"adopted": style.GREEN, "reverted": style.VERMILION,
          "declined": style.VERMILION, "within threshold": "#6b6b6b",
          "noise gauge": "#6b6b6b"}

fig, ax = plt.subplots(figsize=(2.85, 2.5))
ys = list(range(len(ARMS) - 1, -1, -1))

for y, (name, stale, gated, bar, _verdict, _note) in zip(ys, ARMS, strict=True):
    placebo = name.startswith("placebo")
    col = "#8a8a8a" if placebo else style.BLUE
    ax.errorbar(gated, y, xerr=bar, fmt="o", ms=4.2, color=col, ecolor=col,
                elinewidth=1.0, capsize=2, zorder=3)
    if stale is not None:
        ax.plot([stale, gated], [y, y], color="#d0d0d0", lw=0.7, zorder=1)
        ax.plot(stale, y, marker="x", ms=5, mew=1.4, color=style.VERMILION,
                ls="none", zorder=2)

RIGHT = 345
for y, (_name, _stale, _gated, _bar, verdict, note) in zip(ys, ARMS, strict=True):
    ax.text(RIGHT, y, note if note else verdict, fontsize=6.5, va="center",
            ha="left", color=COLOUR.get(verdict, "#6b6b6b"))

ax.axvline(0, color="#aaaaaa", lw=0.7, ls="--", zorder=0)
ax.set_yticks(ys)
ax.set_yticklabels([a[0] for a in ARMS])
ax.set_ylim(-0.7, len(ARMS) - 0.3)
ax.set_xlabel("estimated effect on game rating")
ax.set_xticks([-300, -150, 0, 150, 300])
ax.set_xlim(-380, 620)          # right margin is the verdict column
ax.spines["bottom"].set_bounds(-380, 360)

ax.legend(handles=[
    Line2D([], [], marker="x", ls="none", color=style.VERMILION, ms=5,
           mew=1.4, label="as originally read"),
    Line2D([], [], marker="o", ls="none", color=style.BLUE, ms=4.2,
           label="deploy-gated $\\pm$ threshold"),
], loc="lower left", bbox_to_anchor=(0.0, 1.0), frameon=False,
    handletextpad=0.4, ncol=2, columnspacing=1.0, borderaxespad=0.15)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "figures", "fig2_forest.pdf")
fig.savefig(out)
print("wrote", os.path.normpath(out))
