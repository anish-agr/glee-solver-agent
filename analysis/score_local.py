"""Score games from the feature extract on the published curves."""

from __future__ import annotations

import collections
import gzip
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scoring import score                                 # noqa: E402

EXTRACT = os.path.join(ROOT, "logs", "features.jsonl.gz")


def rows(path: str = EXTRACT, family: str | None = None):
    """Stream the extract."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if family is None or row.get("family") == family:
                yield row


def _me(row) -> int:
    return int(row.get("me") or 1)


def game_state(row) -> dict | None:
    """The fields of the server's game_state that `scoring.score` reads."""
    fam = row.get("family")
    me = _me(row)
    common = {"complete_information": bool(row.get("complete_info")),
              "messages_allowed": bool(row.get("msgs")),
              "max_rounds": row.get("T")}
    if fam == "bargaining":
        d_me = row.get("d_me")
        d_me = 1.0 if d_me is None else float(d_me)
        d_opp = row.get("d_opp")
        if d_opp is None and common["complete_information"]:
            d_opp = 1.0
        elif d_opp is not None:
            d_opp = float(d_opp)
        st = dict(common)
        st["money_to_divide"] = row.get("money")
        st["delta_1"] = d_me if me == 1 else d_opp
        st["delta_2"] = d_opp if me == 1 else d_me
        return st
    if fam == "negotiation":
        my_v, opp_v = row.get("my_value"), row.get("opp_value")
        if my_v is None:
            return None
        st = dict(common)
        st[f"player_{me}_value"] = my_v
        if opp_v is not None:
            st[f"player_{3 - me}_value"] = opp_v
        return st
    if fam == "persuasion":
        price = row.get("price")
        if price is None:
            return None
        st = dict(common)
        st["product_price"] = float(price)
        st["p"] = row.get("p_high")
        st["total_rounds"] = row.get("rounds") or row.get("T") or 20
        st["is_seller_know_cv"] = row.get("seller_knows_cv")
        st["seller_message_type"] = row.get("msg_type") or "text"
        st["v"] = None
        return st
    return None


def rate(row) -> float | None:
    """Game rating earned, on this game's own curve."""
    st = game_state(row)
    if st is None:
        return None
    me = _me(row)
    return score(row["family"], st, me, {f"player_{me}_payoff": row.get("my_pay")})


def position(row) -> str:
    """Discount position, using the engine's 0.1499 threshold."""
    d_opp = row.get("d_opp")
    if d_opp is None and not row.get("complete_info"):
        return "unknown"
    d_me = row.get("d_me")
    d_me = 1.0 if d_me is None else float(d_me)
    d_opp = 1.0 if d_opp is None else float(d_opp)
    if d_me - d_opp >= 0.1499:
        return "power"
    if d_opp - d_me >= 0.1499:
        return "weak"
    return "even"


def _selfcheck(since: float = 1787000000.0) -> int:  # 2026-08-17 20:53 UTC
    cells = collections.defaultdict(list)
    for row in rows(family="bargaining"):
        if (row.get("ts") or 0) < since:
            continue
        if row.get("profile") == "citadel":
            continue
        r = rate(row)
        if r is None:
            continue
        cells[(bool(row.get("complete_info")), position(row),
               "capped" if row.get("T") else "uncapped")].append(r)

    total = sum(len(v) for v in cells.values())
    if not total:
        print("no rows scored; is logs/features.jsonl.gz present?")
        return 1
    print(f"bargaining cells, offline, n={total}\n")
    print(f'{"cell":<38} {"n":>7} {"%":>6} {"rating":>8}')
    for k in sorted(cells, key=lambda k: sum(cells[k]) / len(cells[k])):
        v = cells[k]
        if len(v) < 100:
            continue
        print(f'{str(k):<38} {len(v):>7} {len(v) / total * 100:>5.1f}% '
              f'{sum(v) / len(v):>8.0f}')
    return 0


if __name__ == "__main__":
    sys.exit(_selfcheck())
