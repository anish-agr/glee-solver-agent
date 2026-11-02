"""Horizon-open experiment split by discount cell. Needs logs/games_<agent>.sqlite (not published)."""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from scoring import load, score  # noqa: E402
from glee_agent.assignment import gid_int  # noqa: E402

ARM_BOTS = ("velocity", "citadel")
SINCE = 1786043400  # 2026-08-06 19:10 UTC, deploy of horizon-open


def main():
    cells = defaultdict(lambda: defaultdict(list))
    for prof in ARM_BOTS:
        for g in load(prof):
            if g["fam"] != "bargaining" or g["ts"] < SINCE:
                continue
            st, me = g["st"], g["me"]
            if not st.get("max_rounds"):
                continue
            d_me = st.get("delta_1" if me == 1 else "delta_2")
            d_op = st.get("delta_2" if me == 1 else "delta_1")
            if d_me is None or d_op is None:
                continue
            if float(d_op) - float(d_me) >= 0.1499:
                cell = "disadvantaged (opens 0.50)"
            elif float(d_me) - float(d_op) >= 0.1499:
                cell = "power (opens 0.45)"
            else:
                cell = "even (opens 0.50)"
            r = score(g["fam"], st, me, g["res"])
            if r is None:
                continue
            arm = "treat" if gid_int(g["gid"]) % 2 == 0 else "control"
            cells[cell][arm].append(r)

    print(f"{'cell':<28}{'arm':>8}{'n':>8}{'rating':>9}   verdict")
    for cell in sorted(cells):
        t, c = cells[cell]["treat"], cells[cell]["control"]
        if not t or not c:
            continue
        mt, mc = sum(t) / len(t), sum(c) / len(c)
        n = min(len(t), len(c))
        bar = 200 * (380 / n) ** 0.5
        d = mt - mc
        v = ("adopt" if d > bar else
             "decline" if d < -bar else "within threshold")
        print(f"{cell:<28}{'treat':>8}{len(t):>8}{mt:>9.0f}")
        print(f"{'':<28}{'control':>8}{len(c):>8}{mc:>9.0f}   "
              f"delta={d:+.0f}  bar=+/-{bar:.0f}  -> {v}")


if __name__ == "__main__":
    main()
