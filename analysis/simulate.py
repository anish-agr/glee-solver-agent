"""Offline simulator: play our engines against dataset-calibrated opponents."""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from glee_agent.curves import CurveStore, key_of          # noqa: E402
from glee_agent.dispatcher import make_strategy           # noqa: E402
from glee_agent.profiles import OPTIMA, LEVIATHAN  # noqa: E402

GAMES = pd.read_parquet(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "data", "games.parquet"))
CURVES = CurveStore()

LIE_RATES = [0.0, 0.065, 0.083, 0.088, 0.131, 0.14, 0.17, 0.199, 0.231,
             0.286, 0.339, 0.869, 0.999]

BARG_TYPES = [
    ("soft", 0.33, 0.010, 0.60, 0.020, 0.23),
    ("mid",  0.44, 0.012, 0.60, 0.015, 0.23),
    ("hard", 0.49, 0.004, 0.62, 0.008, 0.54),
]


def game_rating(pct: float) -> float:
    return 2000.0 + 8000.0 * (pct - 0.5)


def _sample_cfg(family: str, rng: random.Random):
    sub = GAMES[GAMES.family == family]
    return sub.iloc[rng.randrange(len(sub))]


def play_bargaining(strategy, cfg, our_player: int, rng: random.Random) -> float:
    money = float(cfg.money)
    T = int(cfg.max_rounds)
    sim_T = min(T, 50)
    d = {1: float(cfg.delta_1), 2: float(cfg.delta_2)}
    complete = bool(cfg.complete_information)
    msgs = bool(cfg.messages_allowed)
    name, thr0, soften, opp_open, concede, _ = rng.choices(
        BARG_TYPES, weights=[t[5] for t in BARG_TYPES])[0]
    thr0 += rng.gauss(0, 0.03)
    gid = f"sim-b-{rng.getrandbits(48):x}"
    history: list[dict] = []
    last_offer = None

    def view(phase, me):
        st = {"phase": phase, "current_player": f"player_{me}",
              "proposer": f"player_{1 if r % 2 == 1 else 2}", "round": r,
              "max_rounds": T, "horizon_known": True,
              "money_to_divide": money, "delta_1": d[1], "delta_2": d[2],
              "last_offer": last_offer, "history": history,
              "messages_allowed": msgs, "complete_information": complete}
        if not complete:
            st.pop(f"delta_{3 - me}")
        return {"game_id": gid, "game_family": "bargaining",
                "your_player": f"player_{me}", "phase": phase, "game_state": st,
                "valid_actions": {"type": "offer" if phase == "offer" else "decision",
                                  "fields": {}}, "prompt": ""}

    for r in range(1, sim_T + 1):
        proposer = 1 if r % 2 == 1 else 2
        responder = 3 - proposer
        if proposer == our_player:
            a = strategy(view("offer", our_player))
            gains = {1: float(a["alice_gain"]), 2: float(a["bob_gain"])}
        else:
            share = max(0.5, opp_open - concede * (r - 1))
            gains = {proposer: money * share, responder: money * (1 - share)}
        last_offer = {"player_1_gain": gains[1], "player_2_gain": gains[2],
                      "message": "", "proposer": f"player_{proposer}", "round": r}

        if responder == our_player:
            a = strategy(view("decision", our_player))
            dec = a["decision"]
        else:
            thr = max(0.05, thr0 - soften * (r - 1))
            dec = "accept" if gains[responder] / money >= thr else "reject"
        history.append({"round": r, "proposer": f"player_{proposer}",
                        "offer": {"player_1_gain": gains[1], "player_2_gain": gains[2],
                                  "message": ""}, "decision": dec})
        if dec == "accept":
            return gains[our_player] * d[our_player] ** (r - 1)
        if dec == "walkaway":
            return 0.0
    return 0.0


def score_bargaining(payoff, cfg, our_player):
    k = key_of(money=cfg.money, max_rounds=cfg.max_rounds, delta_1=cfg.delta_1,
               delta_2=cfg.delta_2, complete_information=cfg.complete_information,
               messages_allowed=cfg.messages_allowed)
    role = "alice" if our_player == 1 else "bob"
    return CURVES.percentile("bargaining", k, role, payoff)


def play_negotiation(strategy, cfg, our_player: int, rng: random.Random) -> float:
    M = float(cfg.M)
    sv, bv = float(cfg.seller_value) * M, float(cfg.buyer_value) * M
    T = int(cfg.max_rounds)
    sim_T = min(T, 30)
    complete = bool(cfg.complete_information)
    msgs = bool(cfg.messages_allowed)
    values = {1: sv, 2: bv}
    opp = 3 - our_player
    opp_is_seller = opp == 1
    margin = rng.uniform(0.25, 0.60)
    if T == 1:
        one_shot_thr = min(max(rng.gauss(0.95, 0.14), 0.55), 1.05)
    gid = f"sim-n-{rng.getrandbits(48):x}"
    history: list[dict] = []
    last_offer = None

    def view(phase, me):
        st = {"phase": phase, "current_player": f"player_{me}",
              "player_1_role": "seller", "player_2_role": "buyer",
              "round": r, "max_rounds": T, "horizon_known": True,
              "last_offer": last_offer, "history": history,
              "messages_allowed": msgs, "complete_information": complete}
        st[f"player_{me}_value"] = values[me]
        if complete:
            st[f"player_{3 - me}_value"] = values[3 - me]
        return {"game_id": gid, "game_family": "negotiation",
                "your_player": f"player_{me}", "phase": phase, "game_state": st,
                "valid_actions": {"type": "offer" if phase == "offer" else "decision",
                                  "fields": {}}, "prompt": ""}

    def opp_reservation():
        prog = 1.0 if sim_T <= 1 else min((r - 1) / (min(sim_T, 12) - 1), 1.0)
        if opp_is_seller:
            return values[opp] * (1 + margin * (1 - prog))
        return values[opp] * (1 - margin * (1 - prog))

    pending = None
    for r in range(1, sim_T + 1):
        proposer = 1 if r % 2 == 1 else 2
        responder = 3 - proposer
        if pending is not None:
            price, pending = pending, None
        elif proposer == our_player:
            a = strategy(view("offer", our_player))
            price = float(a["product_price"])
        else:
            price = opp_reservation()
        last_offer = {"price": price, "message": "",
                      "from_player": f"player_{proposer}", "round": r}

        if responder == our_player:
            a = strategy(view("decision", our_player))
            dec = a["decision"]
            if dec == "RejectOffer" and a.get("product_price") is not None:
                pending = float(a["product_price"])
        else:
            if T == 1:
                ok = (price <= values[opp] * one_shot_thr if not opp_is_seller
                      else price >= values[opp] * (2 - one_shot_thr))
            else:
                res = opp_reservation()
                ok = price >= res if opp_is_seller else price <= res
            dec = "AcceptOffer" if ok else "RejectOffer"
        history.append({"round": r, "offer": {"price": price, "message": "",
                                              "from_player": f"player_{proposer}"},
                        "decision": dec, "decided_by": f"player_{responder}"})
        if dec == "AcceptOffer":
            return (price - sv) if our_player == 1 else (bv - price)
        if dec == "WalkAway":
            return 0.0
    return 0.0


def score_negotiation(payoff, cfg, our_player):
    k = key_of(M=cfg.M, seller_value=cfg.seller_value, buyer_value=cfg.buyer_value,
               max_rounds=cfg.max_rounds, complete_information=cfg.complete_information,
               messages_allowed=cfg.messages_allowed)
    role = "seller" if our_player == 1 else "buyer"
    return CURVES.percentile("negotiation", k, role, payoff)


def play_persuasion(strategy, cfg, our_player: int, rng: random.Random) -> float:
    p, vmult, price = float(cfg.p), float(cfg.v), float(cfg.price)
    T = int(cfg.total_rounds)
    mode = str(cfg.msg_type)
    know_cv = bool(cfg.is_seller_know_cv)
    worth_high = vmult * price
    gid = f"sim-p-{rng.getrandbits(48):x}"
    history: list[dict] = []
    our_pay = 0.0
    opp_lie = rng.choice(LIE_RATES)
    naive_buyer = rng.random() < 0.70
    seen_rec_hi = seen_rec_lo = 0

    for r in range(1, T + 1):
        quality = "high" if rng.random() < p else "low"

        if our_player == 1:
            st = {"phase": "seller_message", "current_player": "player_1",
                  "product_price": price, "p": p, "u": 0.0, "round": r,
                  "total_rounds": T, "history": history,
                  "seller_message": None, "seller_message_type": mode,
                  "current_quality": quality}
            if know_cv:
                st["v"] = worth_high
            a = strategy({"game_id": gid, "game_family": "persuasion",
                          "your_player": "player_1", "phase": "seller_message",
                          "game_state": st,
                          "valid_actions": {"type": "seller_recommendation" if mode == "binary"
                                            else "seller_message", "fields": {}},
                          "prompt": ""})
            rec = a.get("decision") == "yes" if "decision" in a else \
                not any(w in a.get("message", "").lower()
                        for w in ("skip", "pass", "not this", "don't"))
        else:
            rec = True if quality == "high" else (rng.random() < opp_lie)
        msg = ("yes" if rec else "no") if mode == "binary" else \
              ("I recommend this product." if rec else "I'd skip this one.")

        if our_player == 2:
            st = {"phase": "buyer_decision", "current_player": "player_2",
                  "product_price": price, "p": p, "v": worth_high, "u": 0.0,
                  "round": r, "total_rounds": T, "history": history,
                  "seller_message": msg, "seller_message_type": mode}
            a = strategy({"game_id": gid, "game_family": "persuasion",
                          "your_player": "player_2", "phase": "buyer_decision",
                          "game_state": st,
                          "valid_actions": {"type": "decision", "fields": {}},
                          "prompt": ""})
            bought = a["decision"] == "yes"
        elif naive_buyer:
            bought = rng.random() < (0.85 if rec else 0.15)
        else:
            if rec:
                n = seen_rec_hi + seen_rec_lo
                ph = (p if n < 2 else (seen_rec_hi + 1) / (n + 2))
                bought = ph * worth_high - price > 0 or n < 2
            else:
                bought = False
        if bought and rec:
            seen_rec_hi += quality == "high"
            seen_rec_lo += quality == "low"

        if bought:
            our_pay += price if our_player == 1 else (worth_high if quality == "high" else 0.0) - price
        history.append({"round": r, "seller_message": msg, "buyer_decision":
                        "yes" if bought else "no", "bought": bought,
                        **({"quality": quality} if bought else {}),
                        "seller_payoff": price if bought else 0.0,
                        "buyer_payoff": ((worth_high if quality == "high" else 0.0) - price)
                        if bought else 0.0})
    return our_pay


def score_persuasion(payoff, cfg, our_player):
    k = key_of(p=cfg.p, v=cfg.v, price=cfg.price, total_rounds=cfg.total_rounds,
               is_seller_know_cv=cfg.is_seller_know_cv, msg_type=cfg.msg_type,
               is_myopic=cfg.is_myopic)
    role = "seller" if our_player == 1 else "buyer"
    return CURVES.percentile("persuasion", k, role, payoff)


RUNNERS = {"bargaining": (play_bargaining, score_bargaining),
           "negotiation": (play_negotiation, score_negotiation),
           "persuasion": (play_persuasion, score_persuasion)}


def evaluate(profile, families, n, seed=1234, strategy=None):
    """Mean game rating per family (both roles), plus overall."""
    strategy = strategy or make_strategy(profile, curves=CURVES)
    out = {}
    for fam in families:
        play, score = RUNNERS[fam]
        rng = random.Random(seed)
        ratings = []
        for i in range(n):
            cfg = _sample_cfg(fam, rng)
            our_player = 1 + (i % 2)
            try:
                payoff = play(strategy, cfg, our_player, rng)
            except Exception as e:
                print("  sim error:", repr(e))
                continue
            pct = score(payoff, cfg, our_player)
            if pct is not None:
                ratings.append(game_rating(pct))
        out[fam] = float(np.mean(ratings)) if ratings else float("nan")
    out["overall"] = float(np.mean([out[f] for f in families]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--family", default=None)
    ap.add_argument("--tune", default=None)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()
    families = [args.family] if args.family else ["bargaining", "negotiation", "persuasion"]

    if args.tune:
        tune(args.tune, args.n, args.seed)
        return

    print(f"simulating {args.n} games/family/profile "
          f"(dataset-calibrated opponents; mean game rating, 2000 = average play)\n")
    rows = []
    for name, prof in (("optima", OPTIMA), ("leviathan", LEVIATHAN)):
        res = evaluate(prof, families, args.n, args.seed)
        rows.append((name, res))
        print(f"{name:<10}", "  ".join(f"{f}={res[f]:7.1f}" for f in families),
              f"  overall={res['overall']:7.1f}")
    return rows


TUNE_GRID = {
    "bargaining": {
        "barg_accept_margin": [0.0, 0.03, 0.06, 0.09, 0.13],
        "barg_risk_lambda": [0.94, 1.0, 1.06, 1.12],
        "barg_escalation": [0.0, 0.02, 0.04],
        "barg_ratchet_softness_min": [0.35, 0.45, 0.60],
        "barg_power_share": [0.70, 0.78, 0.85, 0.92],
        "barg_lock_in_pct": [0.70, 0.80, 0.90],
    },
    "negotiation": {
        "nego_risk_lambda": [0.94, 1.0, 1.06, 1.12],
        "nego_accept_kappa": [0.75, 0.82, 0.88, 0.95],
        "nego_ratchet_step": [0.0, 0.02, 0.04, 0.07],
        "nego_fish_rounds": [2, 4, 6],
    },
    "persuasion": {
        "pers_lie_cap_mult": [0.7, 0.85, 1.0, 1.15],
        "pers_honest_open_rounds": [0, 1, 2, 3, 5],
        "pers_harvest_rounds": [1, 2, 4, 6, 8],
        "pers_test_budget": [1, 2, 3],
        "pers_guard_mult": [1.2, 1.6, 1.8],
        "pers_guard_rounds": [2, 3, 5],
    },
}


def tune(family, n, seed):
    """Coordinate ascent over the family's knobs, starting from each profile."""
    grid = TUNE_GRID[family]
    for base_name, base in (("optima", OPTIMA), ("leviathan", LEVIATHAN)):
        cur = base
        best = evaluate(cur, [family], n, seed)[family]
        print(f"\n=== tuning {family} from {base_name} (start {best:.1f}) ===")
        for knob, values in grid.items():
            trials = []
            for v in values:
                cand = replace(cur, **{knob: v})
                r = evaluate(cand, [family], n, seed)[family]
                trials.append((r, v))
            trials.sort(reverse=True)
            top_r, top_v = trials[0]
            mark = ""
            if top_r > best + 8.0:
                cur, best, mark = replace(cur, **{knob: top_v}), top_r, "  <-- adopted"
            print(f"  {knob:<26} best {top_v!s:<6} {top_r:7.1f}{mark}   "
                  + " ".join(f"{v}:{r:.0f}" for r, v in sorted(trials, key=lambda t: str(t[1]))))
        print(f"  RESULT {base_name}: {best:.1f}")
        print("  " + ", ".join(f"{k}={getattr(cur, k)}" for k in grid))


if __name__ == "__main__":
    main()
