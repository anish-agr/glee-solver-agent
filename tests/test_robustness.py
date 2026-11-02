"""Failure-path tests: every engine must return a legally shaped action."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dataclasses  # noqa: E402

from test_engines import barg_game, nego_game, pers_game  # noqa: E402
from glee_agent import messages  # noqa: E402
from glee_agent.assignment import gid_int  # noqa: E402
from glee_agent.curves import CurveStore  # noqa: E402
from glee_agent.dispatcher import Context, make_strategy, safe_action, last_resort  # noqa: E402
from glee_agent.engines import bargaining as B  # noqa: E402
from glee_agent.engines import negotiation as N  # noqa: E402
from glee_agent.profiles import (OPTIMA, LEVIATHAN, PROSPECTOR, VELOCITY,  # noqa: E402
                                 PROFILES, live_arms, arm_collisions)

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "" if cond else detail)


def is_legal_shape(game, a):
    if not isinstance(a, dict) or not a:
        return False
    at = game["valid_actions"]["type"]
    fam = game["game_family"]
    if at == "offer" and fam == "bargaining":
        return {"alice_gain", "bob_gain"} <= set(a)
    if at == "offer" and fam == "negotiation":
        return "product_price" in a
    if at == "seller_message":
        return isinstance(a.get("message"), str)
    return "decision" in a


def main():
    s = make_strategy(OPTIMA)

    mangles = []
    g = barg_game("offer"); del g["game_state"]["delta_1"]; mangles.append(("barg no delta_1", g))
    g = barg_game("offer"); g["game_state"]["money_to_divide"] = None; mangles.append(("barg null money", g))
    g = barg_game("offer"); g["game_state"]["max_rounds"] = None; mangles.append(("barg no horizon", g))
    g = barg_game("decision", last=None); mangles.append(("barg decision no last_offer", g))
    g = barg_game("decision", last={"player_1_gain": 0.0, "player_2_gain": 10000.0,
                                    "message": "", "proposer": "player_2", "round": 1})
    mangles.append(("barg offered exactly zero", g))
    g = barg_game("offer"); g["game_state"]["history"] = [{"round": 1}]
    mangles.append(("barg sparse history", g))
    g = nego_game("offer"); del g["game_state"]["player_1_value"]; mangles.append(("nego no own value", g))
    g = nego_game("decision", last={"price": None, "message": "", "from_player": "player_2", "round": 2})
    mangles.append(("nego null price", g))
    g = nego_game("decision", last=None); mangles.append(("nego decision no last_offer", g))
    g = nego_game("offer"); g["game_state"]["player_1_value"] = 12345.0
    mangles.append(("nego off-grid value", g))
    g = pers_game("seller", quality=None); mangles.append(("pers seller unknown quality", g))
    g = pers_game("buyer", cur_msg=None); mangles.append(("pers buyer no message", g))
    g = pers_game("buyer", cur_msg="yes"); g["game_state"]["p"] = 0.0
    mangles.append(("pers p=0", g))
    g = pers_game("buyer", cur_msg="yes"); g["game_state"]["history"] = [{"bought": True}]
    mangles.append(("pers history missing quality", g))
    g = pers_game("seller", quality="low"); g["game_state"]["total_rounds"] = None
    mangles.append(("pers null total_rounds", g))

    for name, game in mangles:
        try:
            a = s(game)
            check(f"mangled/{name}", is_legal_shape(game, a), a)
        except Exception as e:
            check(f"mangled/{name}", False, f"RAISED {e!r}")

    for name, game in mangles:
        try:
            last_resort(game)
            check(f"last_resort/{name}", True)
        except Exception as e:
            check(f"last_resort/{name}", False, f"RAISED {e!r}")

    g = nego_game("decision", me="player_1", myv=1.2, rnd=3, T=10,
                  last={"price": 5000.0, "message": "", "from_player": "player_2", "round": 3})
    a = safe_action(g)
    check("safe_action never accepts a loss", a["decision"] != "AcceptOffer", a)
    check("safe_action mid-game reject carries a counteroffer",
          "product_price" in a, a)
    g = nego_game("decision", me="player_1", myv=1.2, rnd=10, T=10,
                  last={"price": 5000.0, "message": "", "from_player": "player_2", "round": 10})
    check("safe_action final-round bare reject is allowed",
          "product_price" not in safe_action(g), safe_action(g))

    s2 = make_strategy(LEVIATHAN)
    g = barg_game("offer", money=10000.0)
    first = dict(s2(g))
    again = dict(s2(g))
    check("repeat -> safe action", again == safe_action(g), (first, again))
    check("repeat is still legal", is_legal_shape(g, again), again)

    import glee_agent.dispatcher as D
    original = D.ENGINES["bargaining"]
    D.ENGINES["bargaining"] = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        s3 = make_strategy(OPTIMA)
        g = barg_game("offer", money=10000.0)
        a = s3(g)
        check("engine crash -> legal fallback", is_legal_shape(g, a), a)
    finally:
        D.ENGINES["bargaining"] = original

    s4 = make_strategy(LEVIATHAN)
    for g in (barg_game("offer", msgs=True), nego_game("offer", msgs=True)):
        a = s4(g)
        check(f"message <=2000 chars ({g['game_family']})",
              len(a.get("message", "")) <= 2000, len(a.get("message", "")))

    s5 = make_strategy(OPTIMA)
    for money in (100.0, 10000.0, 1000000.0, 33333.33):
        a = s5(barg_game("offer", money=money))
        check(f"offer sums exactly ({money})",
              abs(a["alice_gain"] + a["bob_gain"] - money) < 1e-9,
              (a, a["alice_gain"] + a["bob_gain"]))

    ctx = Context(CurveStore(), LEVIATHAN, llm=None)
    human_g = barg_game("offer", rnd=3)
    human_g["game_state"]["history"] = [
        {"response_time_ms": 62000, "message": "hm let me think"},
        {"response_time_ms": 2100, "message": "counter"}]
    bot_g = barg_game("offer", rnd=3)
    bot_g["game_state"]["history"] = [
        {"response_time_ms": 2100, "message": "I propose a split."},
        {"response_time_ms": 3400, "message": "Here is my counteroffer."}]
    kw = dict(round=3, their_now=4000.0, their_next=3500.0)
    pressure_texts = {t for opts in messages.PRESSURE.values() for t in opts}
    warm_texts = {t for opts in messages.WARM.values() for t in opts}

    def source_pack(msg_kw, g):
        raw = ctx.render_message("bargaining_mid", g, LEVIATHAN, **msg_kw)
        fields = messages._SafeDict(
            {k: (messages.money(v) if k in ("price", "next_price", "their_now",
                                            "their_next") else v)
             for k, v in msg_kw.items()})
        in_p = any(raw == t.format_map(fields) for t in pressure_texts)
        in_w = any(raw == t.format_map(fields) for t in warm_texts)
        return in_p, in_w

    hp, hw = source_pack(kw, human_g)
    bp, bw = source_pack(kw, bot_g)
    check("a human opponent gets the warm voice", hw and not hp,
          (hw, hp))
    check("an agent opponent gets the pressure voice", bp, (bp, bw))

    check("no profile randomizes the acceptance table",
          not any(p.barg_curve_ab for p in (OPTIMA, LEVIATHAN, PROSPECTOR)))
    check("whole fleet on v1 curves",
          all(p.barg_curve_variant == "v1"
              for p in (OPTIMA, LEVIATHAN, PROSPECTOR)))
    check("default variant is v1",
          B.p_accept(0.40, 0.5, 1) == B.p_accept(0.40, 0.5, 1, "v1"))
    sp = make_strategy(PROSPECTOR)
    a = sp(barg_game("offer"))
    check("prospector offer is legal-shaped", is_legal_shape(barg_game("offer"), a), a)

    check("game-id hash is md5-based and the same in every process",
          gid_int("abc-123") == 0x6351623c, hex(gid_int("abc-123")))

    s6 = make_strategy(OPTIMA)
    g = nego_game("decision", myv=1.0, oppv=None, rnd=13, T=None)
    g["game_state"]["history"] = [
        {"round": 5, "offer": {"price": 13000.0, "from_player": "player_2",
                               "message": ""}, "decision": "RejectOffer",
         "decided_by": "player_1", "response_time_ms": 900}]
    g["game_state"]["last_offer"] = {"price": 9000.0, "from_player": "player_2"}
    a = s6(g)
    check("a restart keeps an earlier offer that crossed our value",
          a.get("decision") != "WalkAway", a)
    s7 = make_strategy(LEVIATHAN)
    gb = barg_game("offer", money=10000.0, rnd=3, d1=0.95, d2=0.95)
    gb["game_state"]["history"] = [
        {"round": 1, "proposer": "player_1",
         "offer": {"player_1_gain": 7000.0, "player_2_gain": 3000.0,
                   "message": ""}, "decision": "reject", "response_time_ms": 800}]
    ab = s7(gb)
    check("a restart does not undercut an earlier demand",
          ab["alice_gain"] >= 7000.0 - 1e-6, ab)

    pg = pers_game("seller", rnd=2)
    ctx2 = Context(CurveStore(), LEVIATHAN, llm=None)
    lev_msg = ctx2.render_message("pers_rec", pg, LEVIATHAN, round=2)
    warm_draft = messages.render("pers_rec", pg, LEVIATHAN, style="warm", round=2)
    check("persuasion templates are warm-pack for pressure profiles",
          lev_msg == warm_draft, (lev_msg[:60], warm_draft[:60]))

    check("optima and leviathan use the live acceptance tables",
          not OPTIMA.nego_quote_ab and OPTIMA.nego_acc_variant == "live"
          and LEVIATHAN.nego_acc_variant == "live")
    check("optima does not randomize the closer", not OPTIMA.nego_close_ab)
    check("every profile applies the thin-offer guard to all games",
          all(p.nego_thin_guard_on and not p.nego_thin_guard_ab
              for p in PROFILES.values()),
          {n: (p.nego_thin_guard_on, p.nego_thin_guard_ab) for n, p in PROFILES.items()})
    collisions = {n: arm_collisions(p) for n, p in PROFILES.items()}
    check("no two live experiments share a bit on any profile",
          not any(collisions.values()), {k: v for k, v in collisions.items() if v})
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
    import ab_arms
    readouts = {(a[1], a[2]): a[0] for a in ab_arms.ARMS}
    live = {(name, bit, fam) for p in PROFILES.values() for name, bit, fam, _ in live_arms(p)}
    unread = sorted((n, b, f) for n, b, f in live if b != 0 and (b, f) not in readouts)
    check("every live experiment on a nonzero bit has a readout for its bit and family",
          not unread, unread)
    undated = sorted(readouts[(b, f)] for n, b, f in live
                     if (b, f) in readouts and readouts[(b, f)] not in ab_arms.ARM_SINCE)
    check("every live experiment with a readout has a deploy date", not undated, undated)

    check("no profile walks away or randomizes walking away",
          all(p.nego_never_walk and not p.nego_never_walk_ab
              for p in PROFILES.values()),
          {n: (p.nego_never_walk, p.nego_never_walk_ab) for n, p in PROFILES.items()})

    def gid_with_parity(base, want_even):
        for k in range(64):
            cand = f"{base}-{k}"
            if (gid_int(cand) % 2 == 0) == want_even:
                return cand
        raise AssertionError("no parity match in 64 tries")

    check("live seller-view: buyer accepts below own value",
          N.p_opp_accepts(880.0, 1000.0, True, 1, 10, "live") > 0.5,
          N.p_opp_accepts(880.0, 1000.0, True, 1, 10, "live"))
    check("live seller-view: nothing above buyer value",
          N.p_opp_accepts(1050.0, 1000.0, True, 1, 10, "live") < 0.05,
          N.p_opp_accepts(1050.0, 1000.0, True, 1, 10, "live"))
    check("live buyer-view: sellers reject sub-value prices",
          N.p_opp_accepts(990.0, 1000.0, False, 1, 10, "live") < 0.05,
          N.p_opp_accepts(990.0, 1000.0, False, 1, 10, "live"))
    check("live buyer-view: profitable prices are plausible",
          N.p_opp_accepts(1080.0, 1000.0, False, 1, 10, "live") > 0.2,
          N.p_opp_accepts(1080.0, 1000.0, False, 1, 10, "live"))
    s_n = make_strategy(OPTIMA)
    legal = True
    for myv, T, rnd in ((1.2, 10, 3), (0.8, 10, 3), (1.0, None, 4)):
        g = nego_game("offer", myv=myv, oppv=1.5, rnd=rnd, T=T)
        g["game_id"] = f"livesweep-{myv}-{T}"
        a = s_n(g)
        legal = legal and is_legal_shape(g, a)
    check("live-belief sweep all legal", legal)

    def endgame_game(gid, price):
        g = nego_game("decision", me="player_2", myv=1.2, oppv=0.8, rnd=9, T=10,
                      last={"price": price, "message": "",
                            "from_player": "player_1", "round": 9})
        g["game_id"] = gid
        return g

    ae = s_n(endgame_game(gid_with_parity("eg-a", False), 11800.0))
    check("a thin offer in round T-1 is rejected when we make the last offer",
          ae.get("decision") == "RejectOffer", ae)
    ae2 = s_n(endgame_game(gid_with_parity("eg-b", False), 9000.0))
    check("a fair offer in round T-1 is accepted",
          ae2.get("decision") == "AcceptOffer", ae2)

    adv_hist = [{"round": r, "seller_message": "yes", "bought": True,
                 "quality": "low"} for r in range(1, 13)]
    adv_hist[2]["quality"] = "high"
    ga = pers_game("buyer", mode="binary", p=0.5, v_mult=1.6, cur_msg="yes",
                   history=adv_hist, rnd=14)
    check("the buyer stops following a seller whose recommendations were mostly low quality",
          make_strategy(OPTIMA)(ga).get("decision") == "no")

    check("leviathan applies band acceptance to every game", LEVIATHAN.barg_band_accept_on
          and not LEVIATHAN.barg_band_accept_ab)
    check("optima applies band acceptance", OPTIMA.barg_band_accept_on)
    s_l = make_strategy(LEVIATHAN)

    def resp_game(share, gid):
        g = barg_game("decision", money=10000.0, rnd=2, d1=0.9, d2=0.9)
        g["game_id"] = gid
        g["game_state"]["last_offer"] = {"player_1_gain": share * 10000.0,
                                         "player_2_gain": (1 - share) * 10000.0}
        return g

    even = gid_with_parity("rab-a", True)
    odd = gid_with_parity("rab-b", False)
    check("band offer accepted on even parity",
          s_l(resp_game(0.40, even)).get("decision") == "accept",
          s_l(resp_game(0.40, even)))
    check("band offer accepted on odd parity",
          s_l(resp_game(0.40, odd)).get("decision") == "accept",
          s_l(resp_game(0.40, odd)))
    check("above-band offer not blanket-accepted by the band rule",
          "decision" in s_l(resp_game(0.46, even)))
    check("below-band lowball still rejected",
          s_l(resp_game(0.10, even)).get("decision") == "reject",
          s_l(resp_game(0.10, even)))

    check("velocity registered", PROFILES.get("velocity") is VELOCITY)
    check("velocity on v1, no split",
          VELOCITY.barg_curve_variant == "v1" and not VELOCITY.barg_curve_ab)
    check("velocity band-accept is unconditional",
          VELOCITY.barg_band_accept_on and not VELOCITY.barg_band_accept_ab)
    check("velocity uses kappa 0.78 and risk weight 1.10",
          VELOCITY.nego_accept_kappa == 0.78 and VELOCITY.nego_risk_lambda == 1.10)
    check("velocity and prospector use the live acceptance tables",
          VELOCITY.nego_acc_variant == "live"
          and PROSPECTOR.nego_acc_variant == "live")

    gd = barg_game("offer")
    gd["opponent"] = {"type": "human", "name": "some person"}
    check("disclosed human detected without timing data",
          Context.opponent_info(gd)["type"] == "human"
          and ctx.opponent_is_human(gd))
    gd["opponent"] = {"type": "agent", "name": "o3-mini"}
    slow = dict(gd)
    slow["game_state"] = dict(gd["game_state"],
                              history=[{"response_time_ms": 70000,
                                        "message": "thinking..."}])
    check("disclosed agent overrides slow-timing false positive",
          not ctx.opponent_is_human(slow))
    gd["opponent"] = {"type": "hidden", "name": None}
    check("hidden falls back to timing heuristic",
          not ctx.opponent_is_human(gd))
    s_v = make_strategy(VELOCITY)
    odd_gid = gid_with_parity("vel-band", False)
    gv = barg_game("decision", money=10000.0, rnd=2, d1=0.9, d2=0.9)
    gv["game_id"] = odd_gid
    gv["game_state"]["last_offer"] = {"player_1_gain": 4000.0,
                                      "player_2_gain": 6000.0}
    check("velocity band-accept fires on any parity",
          s_v(gv).get("decision") == "accept", s_v(gv))
    go = barg_game("offer", money=10000.0, rnd=1, d1=0.9, d2=0.9)
    go["game_id"] = "vel-open-1"
    ao = s_v(go)
    check("velocity opens at the default share",
          ao["alice_gain"] <= 6000.0, ao)
    for g in (barg_game("offer"), nego_game("offer"), pers_game("buyer", cur_msg="yes")):
        check(f"velocity legal in {g['game_family']}",
              is_legal_shape(g, s_v(g)), g["game_family"])

    def lie_game(gid):
        g = pers_game("seller", mode="text", p=0.8, v_mult=2.0, quality="low",
                      rnd=3)
        g["game_id"] = gid
        return g

    def first_lie(strategy, **kw):
        """Message from the first game where the agent recommends a low-quality good."""
        for k in range(300):
            g = lie_game(f"lie-scan-{k}")
            g.update(kw)
            m = strategy(g).get("message", "")
            if m.startswith("Buy this one"):
                return m
        return ""

    s_o = make_strategy(OPTIMA)
    m = first_lie(s_o)
    check("optima sends confident lies", m.startswith("Buy this one"), m[:50])
    m = first_lie(s_v)
    check("velocity sends confident lies", m.startswith("Buy this one"), m[:50])
    m = first_lie(s_l)
    check("leviathan sends confident lies", m.startswith("Buy this one"), m[:50])
    g = pers_game("seller", mode="text", p=0.8, v_mult=2.0, quality="high")
    g["game_id"] = gid_with_parity("pcab-e", False)
    m = s_o(g).get("message", "")
    check("a true high-quality recommendation is confident", m.startswith("Buy this one"), m[:50])

    gt1 = nego_game("offer", myv=0.8, rnd=1, T=1)
    gt1["game_id"] = "t1-live-1"
    at1 = s_v(gt1)
    exp_opp = 1.125 * 10000.0
    rungs = {round(exp_opp * f, 2) for f in (0.72, 0.82)}
    check("velocity T=1 quote is search-priced, closable",
          8000.0 < at1["product_price"] <= 14400.0, at1)
    check("velocity T=1 quote is not a ladder rung",
          at1["product_price"] not in rungs, at1)
    gt2 = nego_game("offer", myv=0.8, rnd=1, T=1)
    gt2["game_id"] = gid_with_parity("t1-data", False)
    at2 = s_o(gt2)
    check("optima T=1 quote search-priced and closable",
          8000.0 < at2["product_price"] <= 14400.0, at2)

    s_p = make_strategy(PROSPECTOR)
    check("prospector does not randomize the short script", not PROSPECTOR.pers_short_ab)
    m = first_lie(s_p)
    check("prospector uses the confident pack on both parities",
          m.startswith("Buy this one"), m[:50])

    s_sched = make_strategy(VELOCITY)

    def multi_round_game(rnd, hist=()):
        g = nego_game("offer", myv=0.8, oppv=1.5, rnd=rnd, T=10, history=hist)
        g["game_id"] = f"sched-{rnd}"
        return g
    p_early = s_sched(multi_round_game(1))["product_price"]
    p_late = s_sched(multi_round_game(8))["product_price"]
    check("concession schedule moves the price over rounds",
          p_late < p_early - 1.0, (p_early, p_late))
    check("scheduled price stays profitable", p_late > 8000.0, p_late)

    sw_hist = [{"round": r, "offer": {"price": 8000.0, "from_player": "player_2"},
                "decision": "RejectOffer"} for r in (2, 4)]
    gsw2 = nego_game("offer", myv=0.8, oppv=1.5, rnd=5, T=10, history=sw_hist)
    gsw2["game_id"] = "stonewall-0"
    check("two flat bids do not trip the stonewall counter",
          s_sched(gsw2)["product_price"] > 9000.0, s_sched(gsw2))
    sw_hist4 = [{"round": r, "offer": {"price": 8000.0, "from_player": "player_2"},
                 "decision": "RejectOffer"} for r in (2, 4, 6, 8)]
    gsw = nego_game("offer", myv=0.8, oppv=1.5, rnd=9, T=14, history=sw_hist4)
    gsw["game_id"] = "stonewall-1"
    asw = s_sched(gsw)
    check("stonewalled quote holds well above our own value",
          asw["product_price"] > 9000.0, asw)
    mv_hist = [{"round": 2, "offer": {"price": 8000.0, "from_player": "player_2"}},
               {"round": 4, "offer": {"price": 9500.0, "from_player": "player_2"}}]
    gmv = nego_game("offer", myv=0.8, oppv=1.5, rnd=5, T=10, history=mv_hist)
    gmv["game_id"] = "stonewall-2"
    check("moving opponent does not trip stonewall",
          s_sched(gmv)["product_price"] > 9000.0, s_sched(gmv))

    gu_late = barg_game("offer", money=10000.0, rnd=8, T=None, d1=0.9, d2=0.9)
    gu_late["game_id"] = "unc-1"
    late_demand = s_v(gu_late)["alice_gain"]
    check("velocity's late uncapped demand decays toward half",
          late_demand <= 5600.0, late_demand)
    s_dec = make_strategy(dataclasses.replace(OPTIMA, barg_uncapped_decay=True))
    gd = barg_game("offer", money=10000.0, rnd=8, T=None, d1=0.9, d2=0.9)
    gd["game_id"] = "unc-2"
    decayed = s_dec(gd)["alice_gain"]
    check("the uncapped decay setting moves the demand toward half",
          decayed <= 5600.0, decayed)

    grid = [0.8, 1.0, 1.2, 1.5]
    for rr in (1, 3):
        a_snap = s_n(nego_game("offer", myv=0.8, oppv=None, rnd=rr, T=10))
        mult = a_snap["product_price"] / 10000.0
        gap = min(abs(mult - f) for f in grid)
        interior = [f for f in grid if f > mult]
        check(f"incomplete-info seller quote sits below a grid rung (r{rr})",
              (not interior) or (min(interior) - mult) <= 0.02, (mult, gap))
    check("rung snap keeps the quote profitable",
          s_n(nego_game("offer", myv=0.8, oppv=None, rnd=1, T=10))["product_price"] > 8000.0,
          s_n(nego_game("offer", myv=0.8, oppv=None, rnd=1, T=10)))

    gu = nego_game("offer", myv=0.8, oppv=1.5, rnd=1, T=1)
    gu["game_id"] = "ult-s1"
    au = s_n(gu)
    check("complete-info T=1 seller leaves 7% of the ZOPA",
          abs(au["product_price"] - (8000.0 + 0.93 * 7000.0)) < 1.0, au)
    gu2 = nego_game("offer", me="player_2", myv=1.5, oppv=0.8, rnd=1, T=1)
    gu2["game_id"] = "ult-b1"
    au2 = s_n(gu2)
    check("complete-info T=1 buyer leaves 7% of the ZOPA",
          abs(au2["product_price"] - (15000.0 - 0.93 * 7000.0)) < 1.0, au2)
    gu3 = nego_game("offer", myv=1.2, oppv=0.8, rnd=1, T=1)
    gu3["game_id"] = "ult-s2"
    au3 = s_n(gu3)
    check("no-trade config never quotes under our own value",
          au3["product_price"] >= 12000.0, au3)
    gu4 = nego_game("offer", myv=0.8, rnd=1, T=1)
    gu4["game_id"] = "ult-s3"
    check("incomplete-info T=1 still search-priced",
          8000.0 < s_n(gu4)["product_price"] <= 14400.0)

    easy_hist = [{"round": r, "seller_message": "yes", "bought": True,
                  "quality": "low"} for r in range(1, 13)]
    easy_hist[1]["quality"] = "high"
    easy_hist[4]["quality"] = "high"
    ge = pers_game("buyer", mode="binary", p=0.8, v_mult=3.0, cur_msg="yes",
                   history=easy_hist, rnd=14)
    check("where buying blind pays, the adverse-selection stop does not fire",
          make_strategy(OPTIMA)(ge).get("decision") == "yes",
          make_strategy(OPTIMA)(ge))
    hard_hist = [{"round": r, "seller_message": "yes", "bought": True,
                  "quality": "low"} for r in range(1, 13)]
    hard_g = pers_game("buyer", mode="binary", p=0.5, v_mult=1.6, cur_msg="yes",
                    history=hard_hist, rnd=14)
    check("where buying blind loses, a misleading seller is cut off",
          make_strategy(OPTIMA)(hard_g).get("decision") == "no")

    def human_game(gid, rnd=1):
        g = barg_game("offer", money=10000.0, rnd=rnd, d1=0.9, d2=0.9)
        g["game_id"] = gid
        g["opponent"] = {"type": "human", "name": "someone"}
        return g
    ah = s_l(human_game("hum-1"))
    check("a human opponent is asked for at most half",
          ah["alice_gain"] <= 5000.0 + 1e-6, ah)
    ab = s_l(barg_game("offer", money=10000.0, rnd=1, d1=0.9, d2=0.9))
    check("non-human still demands more than a human does",
          ab["alice_gain"] > ah["alice_gain"], (ab["alice_gain"], ah["alice_gain"]))

    def named_game(gid, name):
        g = barg_game("offer", money=10000.0, rnd=1, d1=0.9, d2=0.9)
        g["game_id"] = gid
        g["opponent"] = {"type": "agent", "name": name}
        return g
    a_soft = s_l(named_game("soft-1", "soft-D"))
    a_wall = s_l(named_game("wall-1", "wall-A"))
    check("soft name is asked for more than a wall name",
          a_soft["alice_gain"] > a_wall["alice_gain"],
          (a_soft["alice_gain"], a_wall["alice_gain"]))

    s_hz = make_strategy(PROFILES["citadel"])
    gh = barg_game("offer", money=10000.0, rnd=1, T=12, d1=0.9, d2=0.9)
    gh["game_id"] = gid_with_parity("hz-a", True)
    ahz = s_hz(gh)
    check("horizon experiment opens at the even split in capped games",
          ahz["bob_gain"] >= 5000.0 - 1e-6, ahz)
    gh2 = barg_game("offer", money=10000.0, rnd=1, T=None, d1=0.9, d2=0.9)
    gh2["game_id"] = gid_with_parity("hz-b", True)
    ahz2 = s_hz(gh2)
    check("horizon experiment does not touch uncapped games",
          ahz2["bob_gain"] < 5000.0, ahz2)

    def wall_game(name):
        g = barg_game("offer", money=10000.0, rnd=1, d1=0.9, d2=0.9)
        g["game_id"] = f"wall-test-{name}"
        g["opponent"] = {"type": "agent", "name": name}
        return g

    aw = s_l(wall_game("wall-A"))
    an = s_l(wall_game("SomeSoftBot"))
    check("a listed wall opponent is offered at least half",
          aw["bob_gain"] >= 5000.0 - 1e-6, aw)
    check("an unlisted opponent is offered less than half",
          an["bob_gain"] < 5000.0, an)
    check("the wall list matches exact names only",
          s_l(wall_game("wall-A2"))["bob_gain"] < 5000.0)

    check("optima does not randomize the band top", not OPTIMA.barg_band_top_ab)

    def fair_offer_game(gid, share):
        g = barg_game("decision", money=10000.0, rnd=1, d1=0.9, d2=0.9)
        g["game_id"] = gid
        g["game_state"]["last_offer"] = {"player_1_gain": share * 10000.0,
                                         "player_2_gain": (1 - share) * 10000.0,
                                         "proposer": "player_2", "round": 1}
        return g
    s_ot = make_strategy(OPTIMA)
    check("an in-band 0.40 first offer is accepted",
          s_ot(fair_offer_game(gid_with_parity("bt-c", True), 0.40))
          .get("decision") == "accept")
    check("a 0.30 first offer is rejected",
          s_ot(fair_offer_game(gid_with_parity("bt-b", True), 0.30))
          .get("decision") == "reject")

    def thin_game(gid):
        g = nego_game("decision", me="player_2", myv=1.2, oppv=0.8, rnd=1, T=10,
                      last={"price": 1.17 * 10000.0, "message": "",
                            "from_player": "player_1", "round": 1})
        g["game_id"] = gid
        return g
    a_thin = s_l(thin_game(gid_with_parity("tg-a", True)))
    check("thin-guard counters instead of accepting",
          a_thin.get("decision") == "RejectOffer" and "product_price" in a_thin,
          a_thin)
    kg = pers_game("buyer", mode="binary", p=0.5, v_mult=2.0, cur_msg="yes",
                   history=[{"round": r, "seller_message": "yes", "bought": True,
                             "quality": ("high" if r <= 2 else "low")}
                            for r in range(1, 13)], rnd=14)
    check("near break-even, the buyer refuses when recommendations underperform the prior",
          make_strategy(OPTIMA)(kg).get("decision") == "no",
          make_strategy(OPTIMA)(kg))

    hist_esc = [{"round": 1, "proposer": "player_1",
                 "offer": {"player_1_gain": 5600.0, "player_2_gain": 4400.0},
                 "decision": "reject"}]
    ge = barg_game("offer", money=10000.0, rnd=3, d1=0.9, d2=0.9)
    ge["game_state"]["history"] = hist_esc
    ge["game_id"] = "mono-1"
    check("non-ratchet offer never escalates past its anchor",
          make_strategy(OPTIMA)(ge)["alice_gain"] <= 5600.0 + 1e-6)
    check("the lie draw depends only on the game and the round",
          gid_int("g1:3") == gid_int("g1:3") and gid_int("g1:3") != gid_int("g1:4"))

    check("no profile uses take-any-profit acceptance",
          not any((LEVIATHAN.nego_take_any_ab, VELOCITY.nego_take_any_profit,
                   OPTIMA.nego_take_any_ab, OPTIMA.nego_take_any_profit)))
    check("leviathan uses the live acceptance tables",
          LEVIATHAN.nego_acc_variant == "live")

    def loss_game(gid):
        g = nego_game("decision", myv=1.2, oppv=1.5, rnd=3, T=10,
                      last={"price": 9000.0, "message": "",
                            "from_player": "player_2", "round": 3})
        g["game_id"] = gid
        return g
    for tag, strat in (("leviathan", s_l), ("velocity", s_v)):
        check(f"{tag} never accepts a loss",
              strat(loss_game(gid_with_parity("tap-loss", True))).get("decision")
              != "AcceptOffer")

    fails = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(fails)}/{len(CHECKS)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
