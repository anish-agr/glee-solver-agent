"""Bargaining rating by seat. Pass logs/features_through_29aug.jsonl.gz for the full-corpus figure."""

from __future__ import annotations

import collections
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_local import rows, rate, position          # noqa: E402

EXTRACT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "logs", "features.jsonl.gz")


def main() -> int:
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    mix = collections.defaultdict(collections.Counter)

    for d in rows(EXTRACT, family="bargaining"):
        if d.get("profile") == "citadel":
            continue
        r = rate(d)
        if r is None:
            continue
        seat = "p1 (moves first)" if int(d.get("me") or 1) == 1 else "p2 (responds)"
        a = agg[seat]
        a["rating"].append(r)
        mp = float(d.get("my_pay") or 0)
        op = float(d.get("opp_pay") or 0)
        a["nodeal"].append(1 if mp + op <= 0 else 0)
        a["round"].append(float(d.get("agreed_round") or d.get("rounds") or 0))
        if mp + op > 0:
            a["share"].append(mp / (mp + op))
        offers = d.get("my_offers") or []
        if offers and offers[0] is not None:
            a["open"].append(float(offers[0]))
        mix[seat][(bool(d.get("complete_info")), position(d),
                   "capped" if d.get("T") else "uncapped")] += 1

    if not agg:
        print("no rows scored -- is the extract present?")
        return 1

    m = lambda v: sum(v) / len(v) if v else float("nan")
    print("bargaining by seat\n")
    print(f'{"seat":<18}{"n":>8}{"rating":>8}{"our open":>10}{"realized":>10}'
          f'{"round":>8}{"no-deal":>9}')
    for s in sorted(agg):
        a = agg[s]
        print(f'{s:<18}{len(a["rating"]):>8}{m(a["rating"]):>8.0f}'
              f'{m(a["open"]):>10.3f}{m(a["share"]):>10.3f}'
              f'{m(a["round"]):>8.2f}{m(a["nodeal"]) * 100:>8.2f}%')

    print("\nconfiguration mix, as a share of each seat's games\n")
    seats = sorted(mix)
    totals = {s: sum(mix[s].values()) for s in seats}
    print(f'{"cell":<40}' + "".join(f"{s:>18}" for s in seats))
    worst = 0.0
    for c in sorted({c for s in seats for c in mix[s]}):
        if min(mix[s][c] for s in seats) < 500:
            continue
        pcts = [mix[s][c] / totals[s] * 100 for s in seats]
        worst = max(worst, max(pcts) - min(pcts))
        print(f"{str(c):<40}" + "".join(f"{p:>17.1f}%" for p in pcts))
    print(f"\nlargest imbalance across any cell: {worst:.2f} percentage points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
