"""Rationality tests for the engines on synthetic game states."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from glee_agent.assignment import gid_int
from glee_agent.dispatcher import make_strategy, safe_action
from glee_agent.profiles import (OPTIMA, LEVIATHAN, PROSPECTOR, VELOCITY,
                                 CITADEL)

CHECKS = []
_UID = [0]


def uid(prefix):
    _UID[0] += 1
    return f"{prefix}{_UID[0]:04d}" + "x" * 11


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def barg_game(phase, me="player_1", money=10000.0, rnd=1, T=12, d1=0.95, d2=0.8,
              last=None, complete=True, msgs=True):
    st = dict(phase=phase, current_player=me,
              round=rnd, max_rounds=T, horizon_known=T is not None,
              money_to_divide=money, delta_1=d1, delta_2=(d2 if complete else None),
              last_offer=last, history=[], messages_allowed=msgs,
              complete_information=complete)
    if not complete:
        st.pop("delta_2")
    return dict(game_id=uid("b"), game_family="bargaining", your_player=me,
                phase=phase, game_state=st,
                valid_actions={"type": "offer" if phase == "offer" else "decision",
                               "fields": {}}, prompt="")


def nego_game(phase, me="player_1", M=10000.0, myv=0.8, oppv=None, rnd=1, T=10,
              last=None, history=(), msgs=True):
    st = dict(phase=phase, current_player=me, player_1_role="seller",
              player_2_role="buyer", round=rnd, max_rounds=T, horizon_known=True,
              last_offer=last, history=list(history), messages_allowed=msgs,
              complete_information=oppv is not None)
    st[f"{me}_value"] = myv * M
    if oppv is not None:
        other = "player_2" if me == "player_1" else "player_1"
        st[f"{other}_value"] = oppv * M
    return dict(game_id=uid("n"), game_family="negotiation", your_player=me,
                phase=phase, game_state=st,
                valid_actions={"type": "offer" if phase == "offer" else "decision",
                               "fields": {}}, prompt="")


def pers_game(actor, mode="binary", p=0.5, v_mult=1.25, price=100.0, rnd=1, T=20,
              quality=None, history=(), cur_msg=None):
    st = dict(phase="seller_message" if actor == "seller" else "buyer_decision",
              current_player="player_1" if actor == "seller" else "player_2",
              product_price=price, p=p, v=v_mult * price, u=0.0, round=rnd,
              total_rounds=T, history=list(history),
              seller_message=cur_msg, seller_message_type=mode,
              seller_total_payoff=0.0, buyer_total_payoff=0.0)
    if actor == "seller":
        st["current_quality"] = quality
        at = "seller_recommendation" if mode == "binary" else "seller_message"
    else:
        at = "decision"
    return dict(game_id=uid("p"), game_family="persuasion",
                your_player="player_1" if actor == "seller" else "player_2",
                phase=st["phase"], game_state=st,
                valid_actions={"type": at, "fields": {}}, prompt="")


def _bit_gid(base, bit, want):
    """A game id whose md5 bit `bit` equals `want`."""
    for k in range(4096):
        cand = f"{base}-{k}"
        if (gid_int(cand) >> bit) % 2 == want:
            return cand
    raise AssertionError(f"no gid with bit {bit} == {want}")


def spe_tests():
    from glee_agent.engines.bargaining import spe_proposer_share
    s = spe_proposer_share(0.9, 0.9, None, 1, True)
    check("spe rubinstein sym", abs(s - 1 / 1.9) < 1e-9, s)
    s = spe_proposer_share(1.0, 1.0, 2, 1, True)
    check("spe T2 delta1", abs(s) < 1e-9, s)
    s = spe_proposer_share(0.5, 1.0, 3, 1, True)
    check("spe T3 asym", abs(s - 0.5) < 1e-9, s)
    s = spe_proposer_share(1.0, 0.8, 12, 1, True)
    check("spe T12 patient", abs(s - 0.73786) < 1e-3, s)


def upgrade_tests():
    s = make_strategy(LEVIATHAN)
    g1 = barg_game("offer")
    gid = g1["game_id"]
    a1 = s(g1)
    g2 = barg_game("offer", rnd=3)
    g2["game_id"] = gid
    a2 = s(g2)
    check("leviathan barg ratchet", a2["alice_gain"] >= a1["alice_gain"] + 100,
          (a1["alice_gain"], a2["alice_gain"]))

    g1 = nego_game("offer", myv=0.8)
    gid = g1["game_id"]
    a1 = s(g1)
    g2 = nego_game("offer", myv=0.8, rnd=3)
    g2["game_id"] = gid
    a2 = s(g2)
    check("leviathan nego ratchet", a2["product_price"] >= a1["product_price"],
          (a1["product_price"], a2["product_price"]))

    so = make_strategy(OPTIMA)
    g = pers_game("seller", quality="low", rnd=1)
    del g["game_state"]["v"]
    a = so(g)
    check("pers seller no-v honest early", a == {"decision": "no"}, a)
    g = pers_game("seller", quality="high", rnd=5)
    del g["game_state"]["v"]
    a = so(g)
    check("pers seller no-v recs high", a == {"decision": "yes"}, a)

    g = nego_game("decision", me="player_2", myv=1.2, rnd=10, T=10,
                  last={"price": 1.19 * 1.2 * 10000 / 1.2, "message": "",
                        "from_player": "player_1", "round": 10})
    a = so(g)
    check("nego final receiver takes positive", a["decision"] == "AcceptOffer", a)


def _arm_state(prof, ab_attr, on_attr):
    """Return "split", "committed" or "retired" for an experiment's two flags."""
    if getattr(prof, ab_attr):
        return "split"
    if getattr(prof, on_attr):
        return "committed"
    return "retired"


def power_open_arm_tests():
    """Power cell, uncapped horizon, committed."""
    for prof in (OPTIMA, LEVIATHAN, VELOCITY, CITADEL):
        s = make_strategy(prof)
        for parity in (0, 1):
            g = barg_game("offer", d1=1.0, d2=0.8, T=None)
            g["game_id"] = _bit_gid(f"up-{parity}", 4, parity)
            a = s(g)
            check(f"{prof.name}/power-open uncapped caps at 0.55 (bit={parity})",
                  5400 <= a["alice_gain"] <= 5500, a)


def even_fast_arm_tests():
    """Even footing, uncapped horizon: take the fairness step from round 3."""
    import dataclasses
    for prof in (VELOCITY, LEVIATHAN):
        state = _arm_state(prof, "barg_even_fast_ab", "barg_even_fast_on")
        if state == "retired":
            g = barg_game("offer", rnd=3, T=None, d1=0.9, d2=0.9, complete=True)
            g["game_id"] = _bit_gid("ef-retired", 4, 0)
            a = make_strategy(prof)(g)["alice_gain"]
            check(f"{prof.name}/even-fast retired is a no-op", a > 5000, a)
            continue
        if state == "committed":
            continue
        off = dataclasses.replace(prof, barg_even_fast_ab=False)

        def run(rnd, T, parity=0, tag="t", prof=prof, off=off):
            """One scenario, two strategies, fresh state on each side."""
            gid = _bit_gid(f"ef-{tag}-{rnd}-{T}", 4, parity)
            out = []
            for pr in (prof, off):
                g = barg_game("offer", rnd=rnd, T=T, d1=0.9, d2=0.9, complete=True)
                g["game_id"] = gid
                out.append(make_strategy(pr)(g)["alice_gain"])
            return out

        on3, off3 = run(3, None)
        check(f"{prof.name}/even-uncapped r3 treatment caps at the even split",
              on3 <= 5000 + 1e-6, on3)
        check(f"{prof.name}/even-uncapped r3 experiment changes the offer",
              on3 < off3, (on3, off3))
        a, b = run(1, None)
        check(f"{prof.name}/even-uncapped r1 untouched by the arm", abs(a - b) < 1e-6)
        a, b = run(3, 12)
        check(f"{prof.name}/even capped games untouched by the arm", abs(a - b) < 1e-6)
        a, b = run(3, None, parity=1, tag="c")
        check(f"{prof.name}/even-uncapped control half is unchanged", abs(a - b) < 1e-6)


def late_bank_tests():
    """Complete information, unknown horizon, round 50 or later: accept a standing offer."""
    so = make_strategy(OPTIMA)

    def at(price_mult, rnd):
        last = {"price": price_mult * 0.8 * 10000, "message": "",
                "from_player": "player_2", "round": rnd}
        g = nego_game("decision", me="player_1", myv=0.8, oppv=0.5, rnd=rnd,
                      T=None, last=last)
        return so(g)

    a = at(1.01, 50)
    check("nego r50 complete-info banks a positive standing offer",
          a.get("decision") == "AcceptOffer", a)
    b = at(0.90, 50)
    check("nego r50 never banks a negative-surplus offer",
          b.get("decision") != "AcceptOffer", b)


def weak_open_arm_tests():
    """Weak position, uncapped horizon, complete information."""
    import dataclasses
    for prof in (OPTIMA, LEVIATHAN, VELOCITY, CITADEL):
        state = _arm_state(prof, "barg_weak_open_ab", "barg_weak_open_on")
        if state == "retired":
            g = barg_game("offer", rnd=1, T=None, d1=0.8, d2=1.0, complete=True)
            g["game_id"] = _bit_gid("wo-retired", 7, 0)
            a = make_strategy(prof)(g)["alice_gain"]
            check(f"{prof.name}/weak-open retired is a no-op", a > 4000, a)
            continue
        if state == "committed":
            continue
        off = dataclasses.replace(prof, barg_weak_open_ab=False)

        def run(rnd, T, d1, d2, parity=0, tag="t", prof=prof, off=off):
            gid = _bit_gid(f"wo-{tag}-{rnd}-{T}-{d1}", 7, parity)
            out = []
            for pr in (prof, off):
                g = barg_game("offer", rnd=rnd, T=T, d1=d1, d2=d2, complete=True)
                g["game_id"] = gid
                out.append(make_strategy(pr)(g)["alice_gain"])
            return out

        on, offv = run(1, None, 0.8, 1.0)
        check(f"{prof.name}/weak-uncapped treatment opens at 0.40",
              on <= 4000 + 1e-6, on)
        check(f"{prof.name}/weak-uncapped experiment changes the offer", on < offv, (on, offv))
        on2, off2 = run(2, None, 0.8, 1.0)
        check(f"{prof.name}/weak-uncapped r2 not re-floored", on2 <= 4000 + 1e-6, on2)
        check(f"{prof.name}/weak-uncapped r2 arm binds", on2 < off2, (on2, off2))
        a, b = run(1, None, 1.0, 0.8)
        check(f"{prof.name}/power position untouched by the weak arm",
              abs(a - b) < 1e-6, (a, b))
        a, b = run(1, 12, 0.8, 1.0)
        check(f"{prof.name}/weak capped games untouched by the weak arm",
              abs(a - b) < 1e-6, (a, b))
        a, b = run(4, None, 0.8, 1.0)
        check(f"{prof.name}/weak-uncapped r4 untouched (opening rounds only)",
              abs(a - b) < 1e-6, (a, b))
        a, b = run(1, None, 0.8, 1.0, parity=1, tag="c")
        check(f"{prof.name}/weak-uncapped control half is unchanged",
              abs(a - b) < 1e-6, (a, b))


def committed_twin_tests():
    """Committed `_on` flags apply the treatment to both halves."""
    import dataclasses
    for prof in (OPTIMA, LEVIATHAN, PROSPECTOR, VELOCITY, CITADEL):
        on = dataclasses.replace(prof, barg_even_fast_on=True,
                                 barg_even_fast_ab=False)
        for parity in (0, 1):
            g = barg_game("offer", rnd=3, T=None, d1=0.9, d2=0.9, complete=True)
            g["game_id"] = _bit_gid(f"cm-e-{parity}", 4, parity)
            a = make_strategy(on)(g)
            check(f"{prof.name}/even-fast committed caps at 0.50 (bit={parity})",
                  a["alice_gain"] <= 5000 + 1e-6, a)
        on = dataclasses.replace(prof, barg_weak_open_on=True,
                                 barg_weak_open_ab=False)
        for parity in (0, 1):
            g = barg_game("offer", rnd=1, T=None, d1=0.8, d2=1.0, complete=True)
            g["game_id"] = _bit_gid(f"cm-w-{parity}", 7, parity)
            a = make_strategy(on)(g)
            check(f"{prof.name}/weak-open committed opens at 0.40 (bit={parity})",
                  a["alice_gain"] <= 4000 + 1e-6, a)
        off = dataclasses.replace(prof, barg_weak_open_on=False,
                                  barg_weak_open_ab=False)
        g = barg_game("offer", rnd=1, T=None, d1=0.8, d2=1.0, complete=True)
        g["game_id"] = _bit_gid("cm-w-0", 7, 0)
        b = make_strategy(off)(g)
        check(f"{prof.name}/weak-open both flags off is a no-op", b["alice_gain"] > 4000, b)


def main():
    spe_tests()
    upgrade_tests()
    power_open_arm_tests()
    even_fast_arm_tests()
    late_bank_tests()
    weak_open_arm_tests()
    committed_twin_tests()
    for prof in (OPTIMA, LEVIATHAN):
        s = make_strategy(prof)
        tag = prof.name

        a = s(barg_game("offer"))
        check(f"{tag}/barg offer sums", abs(a["alice_gain"] + a["bob_gain"] - 10000.0) < 1e-6, a)
        check(f"{tag}/barg offer demands >=55%", a["alice_gain"] >= 5500, a)

        for par in ("pp-a", "pp-b"):
            g_pp = barg_game("offer", d1=1.0, d2=0.8)
            g_pp["game_id"] = _bit_gid(par, 0, 0 if par == "pp-a" else 1)
            a = s(g_pp)
            check(f"{tag}/barg power cell opens at cap 0.55 ({par})",
                  5400 <= a["alice_gain"] <= 5500, a)

        a = s(barg_game("offer", d1=0.8, d2=1.0))
        check(f"{tag}/barg impatient closes fair", a["alice_gain"] <= 5600, a)

        a = s(barg_game("decision", rnd=2,
                        last={"player_1_gain": 5200.0, "player_2_gain": 4800.0,
                              "message": "", "proposer": "player_2", "round": 2}))
        check(f"{tag}/barg accepts good offer", a == {"decision": "accept"}, a)

        a = s(barg_game("decision", rnd=1, d1=0.95, d2=0.95,
                        last={"player_1_gain": 800.0, "player_2_gain": 9200.0,
                              "message": "", "proposer": "player_2", "round": 1}))
        check(f"{tag}/barg rejects lowball r1", a == {"decision": "reject"}, a)

        a = s(barg_game("decision", rnd=12, T=12,
                        last={"player_1_gain": 900.0, "player_2_gain": 9100.0,
                              "message": "", "proposer": "player_2", "round": 12}))
        check(f"{tag}/barg accepts anything final round", a == {"decision": "accept"}, a)

        a = s(barg_game("offer", complete=False))
        check(f"{tag}/barg incomplete info offer ok", "alice_gain" in a, a)

        a = s(nego_game("offer", myv=0.8))
        check(f"{tag}/nego seller quote profitable and closeable",
              8800 <= a["product_price"] <= 15000, a)

        a = s(nego_game("offer", me="player_2", myv=1.2))
        check(f"{tag}/nego buyer quotes profitably below value",
              6000 <= a["product_price"] <= 0.92 * 12000, a)

        g = nego_game("decision", me="player_2", myv=1.2, rnd=9, T=10,
                      last={"price": 0.90 * 1.2 * 10000, "message": "",
                            "from_player": "player_1", "round": 9})
        a = s(g)
        check(f"{tag}/nego buyer takes late good deal", a["decision"] == "AcceptOffer", a)

        hist = [{"round": r, "offer": {"price": 0.5 * 10000, "message": "",
                                       "from_player": "player_2"}, "decision": "RejectOffer"}
                for r in range(1, 8)]
        g = nego_game("decision", myv=1.5, rnd=8, T=10, history=hist,
                      last={"price": 5000.0, "message": "", "from_player": "player_2", "round": 8})
        a = s(g)
        check(f"{tag}/nego walks hopeless late", a["decision"] in ("WalkAway", "RejectOffer"), a)

        g = nego_game("decision", myv=1.5, oppv=0.8, rnd=3, T=10,
                      last={"price": 15600.0, "message": "", "from_player": "player_2", "round": 3})
        a = s(g)
        check(f"{tag}/nego hopeless banks crossing offer", a["decision"] == "AcceptOffer", a)
        g = nego_game("decision", myv=1.5, oppv=0.8, rnd=3, T=10,
                      last={"price": 14000.0, "message": "", "from_player": "player_2", "round": 3})
        a = s(g)
        check(f"{tag}/nego hopeless still rejects non-crossing", a["decision"] != "AcceptOffer", a)

        g = nego_game("decision", myv=1.2, rnd=5, T=10,
                      last={"price": 9000.0, "message": "", "from_player": "player_2", "round": 5})
        a = s(g)
        check(f"{tag}/nego seller never accepts loss", a["decision"] != "AcceptOffer", a)

        a = s(pers_game("seller", quality="high"))
        check(f"{tag}/pers seller recs high", a == {"decision": "yes"}, a)

        a = s(pers_game("seller", quality="low", rnd=1))
        check(f"{tag}/pers seller honest early low", a == {"decision": "no"}, a)

        a = s(pers_game("seller", quality="low", rnd=20))
        check(f"{tag}/pers seller harvests endgame", a == {"decision": "yes"}, a)

        a = s(pers_game("seller", quality="low", mode="text", rnd=20))
        check(f"{tag}/pers text seller returns message", "message" in a and len(a["message"]) > 0, a)

        a = s(pers_game("buyer", cur_msg="yes", rnd=1))
        check(f"{tag}/pers buyer tests early rec", a == {"decision": "yes"}, a)

        hist = [dict(round=r, seller_message="yes", buyer_decision="yes", bought=True,
                     quality="low", seller_payoff=100.0, buyer_payoff=-100.0)
                for r in (1, 2, 3)]
        a = s(pers_game("buyer", cur_msg="yes", rnd=4, history=hist))
        check(f"{tag}/pers buyer stops after burns", a == {"decision": "no"}, a)

        hist = [dict(round=r, seller_message="yes", buyer_decision="yes", bought=True,
                     quality="high", seller_payoff=100.0, buyer_payoff=25.0)
                for r in (1, 2, 3, 4)]
        a = s(pers_game("buyer", cur_msg="yes", rnd=5, history=hist))
        check(f"{tag}/pers buyer follows honest seller", a == {"decision": "yes"}, a)

        a = s(pers_game("buyer", p=0.8, v_mult=2.0, cur_msg="yes", rnd=1))
        check(f"{tag}/pers buyer buys easy config", a == {"decision": "yes"}, a)

    for g in (barg_game("offer"), barg_game("decision"),
              nego_game("offer"), nego_game("decision", me="player_2",
              last={"price": 1.0, "message": "", "from_player": "player_1", "round": 1}),
              pers_game("seller", quality="low"), pers_game("buyer", cur_msg="yes")):
        sa = safe_action(g)
        check(f"safe_action {g['game_family']}/{g['valid_actions']['type']}", isinstance(sa, dict), sa)

    fails = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(fails)}/{len(CHECKS)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
