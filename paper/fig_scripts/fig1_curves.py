"""Figure 2: payoff-to-rating maps for one cell per family, from data/curves.parquet."""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style  # noqa: E402

style.setup()
HERE = os.path.dirname(os.path.abspath(__file__))
CURVES = os.path.join(HERE, "..", "..", "data", "curves.parquet")


def rating_curve(payoffs, norm):
    """x (normalized payoff) -> game rating via the empirical mid-rank CDF."""
    v = np.sort(np.asarray(payoffs, dtype=float))
    x = v / norm
    pct = (np.arange(len(v)) + 0.5) / len(v)
    return x, 2000 + 8000 * (pct - 0.5)


def pick(df, must):
    """Highest-n key containing every substring in `must`."""
    keys = df[df.key.apply(lambda k: all(m in k for m in must))]
    if keys.empty:
        raise SystemExit(f"no key matching {must}")
    key = keys.groupby("key").size().idxmax()
    return df[df.key == key], key


df = pd.read_parquet(CURVES)
fig, axes = plt.subplots(1, 3, figsize=(5.52, 1.5),
                         constrained_layout=True)

b, bkey = pick(df[df.family == "bargaining"],
               ["money=10000", "max_rounds=12", "delta_1=0.95", "delta_2=0.95",
                "complete_information=True"])
x, r = rating_curve(b[b.role == "alice"].payoff, 10000.0)
axes[0].step(x, r, where="post", color=style.BLUE)
axes[0].axvline(0.5, color=style.VERMILION, lw=0.8, ls=":")
axes[0].annotate("half", xy=(0.5, -1500), fontsize=6.5,
                 color=style.VERMILION, ha="left", xytext=(0.53, -1500))
axes[0].set_title("bargaining (share of pot)")
axes[0].set_ylabel("game rating")
zero_share = float((b[b.role == "alice"].payoff <= 0).mean())
axes[0].annotate(f"{zero_share:.1%} at 0", xy=(0.02, 0.90),
                 xycoords="axes fraction", fontsize=6.5, color="#666666")

n, nkey = pick(df[df.family == "negotiation"],
               ["complete_information=False", "seller_value=1.2",
                "buyer_value=1.5", "M=1000000"])
Mstr = [s for s in nkey.split("|") if s.startswith("M=")][0]
M = float(Mstr.split("=")[1])
pay = n[n.role == "seller"].payoff
x, r = rating_curve(pay, M)
keep = x <= float(np.quantile(x, 0.99))
axes[1].step(x[keep], r[keep], where="post", color=style.BLUE)
zero_share = float((pay <= 0).mean())
axes[1].annotate(f"{zero_share:.0%} at 0\n(no deal)", xy=(0.02, 0.72),
                 xycoords="axes fraction", fontsize=6.5, color="#666666")
axes[1].set_xlim(-0.35, 0.65)
axes[1].axvline(0, color="#999999", lw=0.6)
axes[1].set_title("negotiation (surplus / $M$)")

p, pkey = pick(df[df.family == "persuasion"], ["p=0.5"])
pricestr = [s for s in pkey.split("|") if s.startswith("price=")][0]
price = float(pricestr.split("=")[1])
x, r = rating_curve(p[p.role == "seller"].payoff, price)
axes[2].step(x, r, where="post", color=style.BLUE)
axes[2].set_title("persuasion (revenue / price)")

for ax in axes:
    ax.grid(axis="y", alpha=0.6)
    ax.set_ylim(-2200, 6200)
for ax in axes[1:]:
    ax.set_yticklabels([])

out = os.path.join(HERE, "..", "figures", "fig1_curves.pdf")
fig.savefig(out)
print("wrote", os.path.normpath(out))
print("keys used:")
print(" b:", bkey)
print(" n:", nkey)
print(" p:", pkey)
