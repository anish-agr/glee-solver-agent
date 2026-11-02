"""Figure 1 (one bargaining offer) and Figure 3 (the same search under acceptance tables v1 and v4)."""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
import style  # noqa: E402
from glee_agent.engines.bargaining import p_accept  # noqa: E402

style.setup()
CURVES = os.path.join(HERE, "..", "..", "data", "curves.parquet")

MONEY, RND, D_ME, SOFTNESS = 10000.0, 1, 0.95, 0.5

df = pd.read_parquet(CURVES)
b = df[(df.family == "bargaining") & (df.role == "alice")]
keys = b[b.key.apply(lambda k: "money=10000" in k and "delta_1=0.95" in k
                     and "complete_information=True" in k)]
key = keys.groupby("key").size().idxmax()
payoffs = np.sort(np.asarray(b[b.key == key].payoff, dtype=float))


def F(x):
    """Midrank payoff percentile, as the curve store computes it."""
    lo = np.searchsorted(payoffs, x, side="left")
    hi = np.searchsorted(payoffs, x, side="right")
    return (lo + hi) / (2 * len(payoffs))


shares = np.array([0.42 + 0.02 * i for i in range(28)])
settle = np.array([F(s * MONEY * D_ME ** (RND - 1)) for s in shares])
cont = F(0.5 * MONEY * D_ME ** (RND + 1))


def ev_for(variant):
    pa = np.array([p_accept(1.0 - s, SOFTNESS, RND, variant) for s in shares])
    return pa, pa * settle + (1.0 - pa) * cont


pa_v1, ev_v1 = ev_for("v1")
pa_v4, ev_v4 = ev_for("v4")

fig, a1 = plt.subplots(figsize=(5.52, 1.45), constrained_layout=True)

a1.plot(shares, pa_v1, color=style.ORANGE, lw=1.3,
        label=r"$p(1{-}s)$: they accept")
a1.plot(shares, settle, color=style.GREY, lw=1.3, ls="--",
        label=r"$F_c$: percentile if they do")
a1.plot(shares, ev_v1, color=style.BLUE, lw=1.9,
        label="expected percentile")
a1.axhline(cont, color=style.GREEN, lw=0.9, ls=":")
a1.annotate("continuation if they refuse", xy=(0.86, cont),
            xytext=(0.80, 0.52), ha="center", fontsize=6.5,
            color=style.GREEN,
            arrowprops=dict(arrowstyle="-", color=style.GREEN, lw=0.6))
star = int(np.argmax(ev_v1))
a1.plot(shares[star], ev_v1[star], "o", color=style.BLUE, ms=5.5, zorder=5)
a1.annotate(f"argmax {shares[star]:.2f}", xy=(shares[star], ev_v1[star]),
            textcoords="offset points", xytext=(8, 4), fontsize=6.5,
            color=style.BLUE)
a1.set_xlabel("share of the pot we keep, $s$")
a1.set_ylabel("probability / percentile")
a1.set_ylim(0, 1.42)
a1.grid(axis="y", alpha=0.6)
a1.legend(frameon=False, loc="upper left", fontsize=6.5, ncol=3,
          handletextpad=0.5, borderaxespad=0.1, labelspacing=0.25)

fig.savefig(os.path.join(HERE, "..", "figures", "fig8_decision.pdf"))

fig, a2 = plt.subplots(figsize=(2.87, 2.05), constrained_layout=True)
a2.plot(shares, pa_v1, color=style.GREY, lw=1.1, ls="--",
        label="acceptance, v1 (shipped)")
a2.plot(shares, pa_v4, color=style.ORANGE, lw=1.1,
        label="acceptance, v4")
a2.plot(shares, ev_v1, color=style.GREY, lw=1.9,
        label="expected percentile, v1 (shipped)")
a2.plot(shares, ev_v4, color=style.BLUE, lw=1.9,
        label="expected percentile, v4")
for series, colour in ((ev_v1, style.GREY), (ev_v4, style.BLUE)):
    j = int(np.argmax(series))
    a2.plot(shares[j], series[j], "o", color=colour, ms=5.5, zorder=5)
a2.axvline(0.50, ymax=0.62, color=style.VERMILION, lw=0.8, ls=":")
a2.annotate("even split", xy=(0.495, 0.76), ha="right", fontsize=6.5,
            color=style.VERMILION)
a2.set_xlabel("share of the pot we keep, $s$")
a2.set_ylabel("probability / percentile")
a2.set_ylim(0, 1.42)
a2.grid(axis="y", alpha=0.6)
a2.legend(frameon=False, loc="upper left", fontsize=6.5,
          handletextpad=0.5, borderaxespad=0.1, labelspacing=0.25)
fig.savefig(os.path.join(HERE, "..", "figures", "fig9_refit.pdf"))

print(f"wrote fig8_decision.pdf and fig9_refit.pdf; cell {key}")
print(f"  continuation percentile {cont:.3f}")
for name, pa, ev in (("v1", pa_v1, ev_v1), ("v4", pa_v4, ev_v4)):
    j = int(np.argmax(ev))
    print(f"  {name}: argmax s={shares[j]:.2f} ev={ev[j]:.3f}; "
          f"p at 0.48/0.50/0.52 = {pa[3]:.2f}/{pa[4]:.2f}/{pa[5]:.2f}")
