"""Figure 8: persuasion rating four days either side of the 11 August deploy, by role and message type."""
import os
import sys

import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style  # noqa: E402

style.setup()


def _did_cells():
    """The four cells, computed from the committed extract."""
    import calendar
    import collections
    sys.path.insert(0, os.path.join(HERE, "..", "..", "analysis"))
    from score_local import rows, rate                    # noqa: E402

    extract = os.path.join(HERE, "..", "..", "logs", "features.jsonl.gz")
    deploy = calendar.timegm((2026, 8, 11, 22, 40, 0, 0, 0, 0))
    window = 4 * 86400.0
    agg = collections.defaultdict(list)
    for d in rows(extract, family="persuasion"):
        if d.get("profile") == "citadel":
            continue
        ts, r = d.get("ts"), rate(d)
        if ts is None or r is None or abs(ts - deploy) > window:
            continue
        agg[(d.get("my_role"), d.get("msg_type"),
             "post" if ts >= deploy else "pre")].append(r)

    mean = lambda v: sum(v) / len(v)
    notes = {("buyer", "text"): "classifier fix target",
             ("buyer", "binary"): "no change shipped (drift control)",
             ("seller", "text"): "flat-rec placebo (reverted)",
             ("seller", "binary"): "flat-rec placebo (reverted)"}
    out = []
    for side in ("buyer", "seller"):
        for mt in ("text", "binary"):
            pre, post = agg[(side, mt, "pre")], agg[(side, mt, "post")]
            out.append((f"{side} / {mt}", round(mean(pre)), round(mean(post)),
                        notes[(side, mt)]))
    return out


CELLS = _did_cells()
fig, ax = plt.subplots(figsize=(3.35, 2.15))
for i, (_name, pre, post, _note) in enumerate(CELLS):
    good = post >= pre
    col = style.BLUE if good else style.VERMILION
    ax.plot([i - 0.17, i + 0.17], [pre, post], "-", color=col, lw=1.3)
    ax.plot(i - 0.17, pre, "o", color="#999999", ms=4)
    ax.plot(i + 0.17, post, "o", color=col, ms=4)
    ax.annotate(f"{post - pre:+d}".replace("-", "\u2212"), xy=(i, max(pre, post)),
                textcoords="offset points", xytext=(0, 7), ha="center",
                fontsize=6.5, color=col, annotation_clip=False)
ax.set_xticks(range(len(CELLS)))
ax.set_xticklabels([c[0] for c in CELLS], fontsize=6.5)
ax.set_ylabel("curve-scored rating")
ax.set_ylim(2550, 4250)
ax.set_yticks([2800, 3200, 3600, 4000])
ax.grid(axis="y", alpha=0.6)
from matplotlib.lines import Line2D  # noqa: E402
ax.legend(handles=[
    Line2D([], [], marker="o", ls="none", color="#999999", ms=4,
           label="4 days pre"),
    Line2D([], [], marker="o", ls="none", color=style.BLUE, ms=4,
           label="post, higher"),
    Line2D([], [], marker="o", ls="none", color=style.VERMILION, ms=4,
           label="post, lower"),
], loc="lower center", bbox_to_anchor=(0.5, -0.03), frameon=False,
    handletextpad=0.4, ncol=3, columnspacing=0.9)
fig.savefig(os.path.join(HERE, "..", "figures", "fig5_did.pdf"))
print("wrote fig5_did.pdf")
