"""Score logged games on the corpus curves. load() reads the per-agent databases, which are not published."""

from __future__ import annotations

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from glee_agent.curves import CurveStore, key_of      # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CURVES = CurveStore()

DELTA_GRID = [0.8, 0.9, 0.95, 1.0]
MULT_GRID = [0.8, 1.0, 1.2, 1.5]
SCALES = [100.0, 1e4, 1e6]


def rating(pct):
    return 2000 + 8000 * (pct - 0.5)


WINDOW = (float(os.environ.get("GLEE_FROM", 0)), float(os.environ.get("GLEE_TO", 1e18)))


def load(profile):
    """Completed games first seen in WINDOW (epoch seconds; set GLEE_FROM and GLEE_TO)."""
    path = os.path.join(ROOT, "logs", f"games_{profile}.sqlite")
    if not os.path.exists(path):
        return []
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    out = []
    for gid, fam, res_j, fs_j, ts in db.execute(
            "select game_id, family, result, final_state, first_seen from games "
            "where done=1 and first_seen > ? and first_seen <= ?", WINDOW):
        try:
            g = json.loads(fs_j)
            res = json.loads(res_j)
        except (TypeError, json.JSONDecodeError):
            continue
        st = g.get("game_state", {})
        me = 2 if g.get("your_player") == "player_2" else 1
        out.append(dict(gid=gid, fam=fam, res=res, st=st, me=me, ts=ts))
    return out


def score(fam, st, me, res):
    pay = res.get(f"player_{me}_payoff")
    if pay is None:
        return None
    pay = float(pay)
    if fam == "bargaining":
        role = "alice" if me == 1 else "bob"
        d1, d2 = st.get("delta_1"), st.get("delta_2")
        mr = st.get("max_rounds") or 99
        common = dict(complete_information=st.get("complete_information", True),
                      messages_allowed=st.get("messages_allowed", False))
        money = st.get("money_to_divide")
        if d1 is not None and d2 is not None:
            keys = [(key_of(money=money, max_rounds=mr, delta_1=d1, delta_2=d2,
                            **common), 1.0)]
        else:
            known = d1 if me == 1 else d2
            if known is None:
                return None
            keys = [(key_of(money=money, max_rounds=mr,
                            delta_1=(known if me == 1 else g),
                            delta_2=(g if me == 1 else known), **common), 0.25)
                    for g in DELTA_GRID]
    elif fam == "negotiation":
        role = "seller" if me == 1 else "buyer"
        v1, v2 = st.get("player_1_value"), st.get("player_2_value")
        my_v = v1 if me == 1 else v2
        if my_v is None:
            return None
        M = mult = None
        for MM in SCALES:
            for f in MULT_GRID:
                if abs(float(my_v) - f * MM) < 1e-6 * MM:
                    M, mult = MM, f
        if M is None:
            return None
        opp_v = v2 if me == 1 else v1
        base = dict(M=M, max_rounds=st.get("max_rounds") or 99,
                    complete_information=st.get("complete_information", True),
                    messages_allowed=st.get("messages_allowed", False))
        if opp_v is not None:
            of = round(float(opp_v) / M, 2)
            cands = [(of, 1.0)]
        else:
            cands = [(f, 0.25) for f in MULT_GRID]
        keys = []
        for f, w in cands:
            sv = mult if me == 1 else f
            bv = f if me == 1 else mult
            keys.append((key_of(M=M, seller_value=sv, buyer_value=bv,
                                max_rounds=base["max_rounds"],
                                complete_information=base["complete_information"],
                                messages_allowed=base["messages_allowed"]), w))
    else:
        role = "seller" if me == 1 else "buyer"
        price = st.get("product_price")
        v = st.get("v")
        if price is None:
            return None
        vm_cands = ([round((v if v > 10 else v * price) / price, 4)]
                    if v is not None else [1.2, 1.25, 2.0, 3.0, 4.0])
        keys = []
        for vm in vm_cands:
            for kcv in ([st["is_seller_know_cv"]] if st.get("is_seller_know_cv") is not None
                        else [True, False]):
                for myo in (False, True):
                    keys.append((key_of(p=st.get("p"), v=vm, price=price,
                                        total_rounds=st.get("total_rounds", 20),
                                        is_seller_know_cv=kcv,
                                        msg_type=st.get("seller_message_type", "text"),
                                        is_myopic=myo), 1.0))
    pct = CURVES.percentile_mix(fam, keys, role, pay, default=-1.0)
    if pct < 0:
        return None
    return rating(pct)
