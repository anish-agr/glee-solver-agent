"""Negotiation engine: bilateral trade with private values."""

from __future__ import annotations

from ..assignment import gid_int
from ..curves import key_of
from ..profiles import Profile

MULT_GRID = [0.8, 1.0, 1.2, 1.5]
SCALES = [100.0, 1e4, 1e6]

ACCEPT_PCT_FLOOR = 0.45

BUYER_ACC = [(0.70, 0.99), (0.80, 0.87), (0.90, 0.81), (0.95, 0.64), (1.00, 0.48), (9.99, 0.0)]
SELLER_ACC = [(1.00, 0.0), (1.05, 0.40), (1.10, 0.55), (1.20, 0.75), (1.30, 0.87), (99.0, 0.97)]

BUYER_ACC_LIVE = [(0.88, 0.96), (0.92, 0.75), (0.96, 0.45), (1.00, 0.08),
                  (9.99, 0.01)]
SELLER_ACC_LIVE = [(1.00, 0.01), (1.05, 0.35), (1.12, 0.50), (1.25, 0.65),
                   (99.0, 0.80)]


def _may_walk(profile: Profile, game: dict) -> bool:
    """Whether walking away is allowed in this game."""
    if profile.nego_never_walk_ab:
        return (gid_int(game["game_id"]) >> 3) % 2 == 1
    return not profile.nego_never_walk


def _post_quantile(post: dict, M: float, q: float) -> float:
    """q-quantile of the posterior over the opponent's value."""
    tot = sum(post.values()) or 1.0
    acc = 0.0
    for f in sorted(post):
        acc += post[f] / tot
        if acc >= q:
            return f * M
    return max(post) * M if post else M


def _tab(table, x):
    for ub, p in table:
        if x <= ub:
            return p
    return table[-1][1]


def p_opp_accepts(price: float, opp_value: float, opp_is_buyer: bool,
                  rnd: int, T: int | None, variant: str = "v1") -> float:
    ratio = price / max(opp_value, 1e-9)
    if variant == "live":
        base = _tab(BUYER_ACC_LIVE, ratio) if opp_is_buyer else _tab(SELLER_ACC_LIVE, ratio)
    else:
        base = _tab(BUYER_ACC, ratio) if opp_is_buyer else _tab(SELLER_ACC, ratio)
    if T is None:
        return base * 0.55
    left = T - rnd
    return base * (1.0 if left <= 0 else 0.6 if left >= 3 else 0.8)


def _scale_and_mult(value: float) -> tuple[float, float]:
    for M in SCALES:
        for f in MULT_GRID:
            if abs(value - f * M) < 1e-6 * M:
                return M, f
    for M in reversed(SCALES):
        if value >= 0.5 * M:
            return M, value / M
    return SCALES[0], value / SCALES[0]


def act(game: dict, profile: Profile, ctx) -> dict:
    state = game["game_state"]
    me = 1 if game["your_player"] == "player_1" else 2
    my_role = state[f"player_{me}_role"]
    my_value = float(state[f"player_{me}_value"])
    opp_value_raw = state.get(f"player_{3 - me}_value")
    M, my_mult = _scale_and_mult(my_value)
    rnd = int(state.get("round", 1))
    T = state.get("max_rounds")
    T = int(T) if T else None
    msgs = state.get("messages_allowed", False)
    complete = state.get("complete_information", opp_value_raw is not None)
    i_am_seller = my_role == "seller"

    jitter = 0.02 + ((gid_int(game["game_id"]) >> 6) % 100) / 1000.0
    seller_floor_mult, buyer_ceiling_mult = 1.0 + jitter, 1.0 - jitter

    mem = ctx.memory(game["game_id"])
    post = mem.setdefault("posterior", {f: 1.0 / len(MULT_GRID) for f in MULT_GRID})
    if opp_value_raw is not None:
        _, of = _scale_and_mult(float(opp_value_raw))
        post = {f: (1.0 if abs(f - of) < 1e-9 else 0.0) for f in MULT_GRID}
    else:
        for h in state.get("history", []):
            off = h.get("offer") or {}
            hp = off.get("price") if off.get("price") is not None else off.get("product_price")
            if hp is not None and off.get("from_player") != game["your_player"]:
                frac = float(hp) / M
                for f in list(post):
                    if i_am_seller and frac > f + 0.02:
                        post[f] *= 0.15
                    if not i_am_seller and frac < f - 0.02:
                        post[f] *= 0.15
        z = sum(post.values()) or 1.0
        post = {f: w / z for f, w in post.items()}
    mem["posterior"] = post

    def keys_for():
        out = []
        for f, w in post.items():
            sv = round(my_mult, 2) if i_am_seller else f
            bv = f if i_am_seller else round(my_mult, 2)
            out.append((key_of(M=M, seller_value=sv, buyer_value=bv,
                               max_rounds=T or 99, complete_information=complete,
                               messages_allowed=msgs), w))
        return out

    keys = keys_for()
    have_curve = ctx.curves.has_data("negotiation", keys, my_role)
    F = lambda x: ctx.curves.percentile_mix("negotiation", keys, my_role, x)
    surplus = (lambda price: price - my_value) if i_am_seller else (lambda price: my_value - price)

    p_trade_possible = sum(w for f, w in post.items()
                           if (f * M > my_value + 1e-9 if i_am_seller
                               else f * M < my_value - 1e-9))

    action_type = game["valid_actions"]["type"]
    lo = state.get("last_offer") or {}

    if "best_crossed" not in mem or "last_own_price" not in mem:
        best, own_last = 0.0, None
        for h in state.get("history", []):
            off = h.get("offer") or {}
            p = off.get("price") if off.get("price") is not None else off.get("product_price")
            if p is None:
                continue
            if off.get("from_player") == f"player_{me}":
                own_last = float(p)
            else:
                best = max(best, surplus(float(p)))
        mem.setdefault("best_crossed", best)
        if own_last is not None:
            mem.setdefault("last_own_price", own_last)

    kappa = profile.nego_accept_kappa
    if (profile.nego_accept_kappa_ab
            and (gid_int(game["game_id"]) >> 2) % 2 == 0):
        kappa = profile.nego_accept_kappa_lo
    risk_lambda = profile.nego_risk_lambda
    if profile.nego_close_ab and gid_int(game["game_id"]) % 2 == 0:
        kappa, risk_lambda = 0.80, 1.10

    acc_variant = profile.nego_acc_variant
    if profile.nego_quote_ab and gid_int(game["game_id"]) % 2 == 0:
        acc_variant = "live"

    step = profile.nego_ratchet_step
    if step > 0 and T and rnd > max(1, int(T * 0.6)):
        step = 0.0

    def offer(price, situation):
        price = round(max(price, 0.0), 2)
        if i_am_seller:
            price = min(price, max(1.5 * M, my_value * seller_floor_mult))
        else:
            price = max(price, min(0.8 * M, my_value * buyer_ceiling_mult))
        price = round(max(price, 0.0), 2)
        if step > 0 and "last_own_price" in mem:
            lp = mem["last_own_price"]
            price = max(price, lp * (1 + step)) if i_am_seller else min(price, lp * (1 - step))
            price = round(price, 2)
        mem["last_own_price"] = price
        a = {"product_price": price}
        if msgs:
            nxt = price * (1 + step) if i_am_seller else price * (1 - step)
            a["message"] = ctx.render_message(situation, game, profile,
                                              price=price, round=rnd,
                                              next_price=round(nxt, 2),
                                              rounds_left=(T - rnd) if T else None)
        return a

    if p_trade_possible < 0.05:
        fish_price = my_value * (1.10 if i_am_seller else 0.90)
        if action_type == "offer":
            return offer(fish_price, "nego_fish")
        their_p = (lo.get("price") if lo.get("price") is not None
                   else lo.get("product_price"))
        if their_p is not None and surplus(float(their_p)) > 0:
            return {"decision": "AcceptOffer"}
        if rnd <= profile.nego_fish_rounds and not (T and rnd >= T):
            return {"decision": "RejectOffer", **offer(fish_price, "nego_fish")}
        if T and rnd >= T:
            return {"decision": "RejectOffer"}
        if _may_walk(profile, game):
            return {"decision": "WalkAway"}
        return {"decision": "RejectOffer", **offer(fish_price, "nego_fish")}

    def best_price_by_search(final_shot: bool):
        vals = [f * M for f, w in post.items() if w > 1e-6]
        lo_p = min(min(vals), my_value)
        hi_p = max(max(vals), my_value) * (1.08 if i_am_seller else 1.0)
        n = 25
        cand = [lo_p + (hi_p - lo_p) * i / n for i in range(n + 1)]
        for f, w in post.items():
            if w > 1e-6:
                v = f * M
                cand += ([v * x for x in (0.88, 0.90, 0.93, 0.96)]
                         if i_am_seller else
                         [v * x for x in (1.03, 1.06, 1.10, 1.15)])
        cand = [c for c in cand if surplus(c) > 0]
        if not cand:
            return my_value * (seller_floor_mult if i_am_seller else buyer_ceiling_mult)
        cont = 0.0 if final_shot else cont_pct * risk_lambda
        best, best_ev = cand[0], -1.0
        for c in cand:
            pa = sum(w * p_opp_accepts(c, f * M, i_am_seller, rnd, T, acc_variant)
                     for f, w in post.items())
            ev = (pa * F(surplus(c)) + (1 - pa) * cont if have_curve
                  else pa * surplus(c))
            if ev > best_ev:
                best, best_ev = c, ev
        return best

    exp_opp = sum(f * w for f, w in post.items()) * M
    mid = 0.5 * (exp_opp + my_value)
    rho = 0.45 if acc_variant == "live" else 0.85
    cont_pct = rho * F(max(surplus(mid), 0.0))

    if T:
        my_offer_rounds_parity = rnd % 2 if action_type == "offer" else (rnd + 1) % 2
        i_have_last_offer = (T % 2) == my_offer_rounds_parity
    else:
        i_have_last_offer = False

    shaped: dict = {}

    def shaped_quote():
        """(price, situation) for our next quote, or None meaning walk away."""
        if "v" not in shaped:
            shaped["v"] = shape()
        return shaped["v"]

    def shape():
        final_shot = bool(T and rnd >= T - 1)
        if T == 1 and i_am_seller and acc_variant != "live":
            fracs = profile.t1_price_fracs
            frac = fracs[gid_int(game["game_id"]) % len(fracs)]
            price = max(exp_opp * frac, my_value * seller_floor_mult)
            return round(price, 2), "nego_offer"
        if final_shot and opp_value_raw is not None:
            ov = float(opp_value_raw)
            zopa = ov - my_value if i_am_seller else my_value - ov
            edge = (my_value + 0.93 * zopa) if i_am_seller else (my_value - 0.93 * zopa)
            floor = my_value * (seller_floor_mult if i_am_seller else buyer_ceiling_mult)
            price = max(edge, floor) if i_am_seller else min(edge, floor)
            if surplus(price) > 0:
                return round(price, 2), "nego_close"
        price = best_price_by_search(final_shot)

        opp_bids = []
        for h in state.get("history", []):
            off_h = h.get("offer") or {}
            bp = off_h.get("price", off_h.get("product_price"))
            if bp is not None and off_h.get("from_player") != game["your_player"]:
                opp_bids.append(float(bp))
        stonewalled = False
        if (profile.nego_stonewall and len(opp_bids) >= 4
                and not (T and rnd >= T - 1)):
            w = opp_bids[-3:]
            flat = (max(w) - min(w)) <= 0.005 * max(abs(w[0]), 1e-9)
            unpayable = (w[-1] <= my_value) if i_am_seller else (w[-1] >= my_value)
            if flat and unpayable:
                stonewalled = True
                mem["stonewall_quotes"] = mem.get("stonewall_quotes", 0) + 1
                if mem["stonewall_quotes"] > 3 and not T and _may_walk(profile, game):
                    return None

        sched_on = (profile.nego_schedule_on
                    or (profile.nego_schedule_ab
                        and gid_int(game["game_id"]) % 2 == 0))
        if sched_on and not final_shot and not stonewalled:
            T_eff = T or 10
            frac = (rnd - 1) / max(T_eff - 1, 1)
            frac = min(max(frac, 0.0), 1.0)
            opp_ref = (float(opp_value_raw) if opp_value_raw is not None
                       else _post_quantile(post, M, 0.85 if i_am_seller else 0.15))
            anchor = opp_ref * (profile.nego_anchor_frac if i_am_seller
                                else 2.0 - profile.nego_anchor_frac)
            reservation = my_value * (seller_floor_mult if i_am_seller else buyer_ceiling_mult)
            boulware_k = profile.nego_boulware_k
            if (profile.nego_boulware_k_ab
                    and (gid_int(game["game_id"]) >> 7) % 2 == 0):
                boulware_k = profile.nego_boulware_k_lo
            target = reservation + (anchor - reservation) * (1 - frac ** boulware_k)
            sched = min(price, target) if i_am_seller else max(price, target)
            if surplus(sched) > 0:
                price = sched

        if T and not i_have_last_offer and rnd >= T - 2:
            price = min(price, exp_opp * 0.98) if i_am_seller else max(price, exp_opp * 1.02)
            if surplus(price) <= 0:
                price = my_value * (seller_floor_mult if i_am_seller else buyer_ceiling_mult)
        if not complete and M > 0:
            rungs = [f * M for f in MULT_GRID]
            if i_am_seller:
                above = [r for r in rungs if r > price * 1.0005]
                if above:
                    snapped = min(above) * 0.996
                    if snapped > price and surplus(snapped) > 0:
                        price = snapped
            else:
                below = [r for r in rungs if r < price * 0.9995]
                if below:
                    snapped = max(below) * 1.004
                    if snapped < price and surplus(snapped) > 0:
                        price = snapped

        situation = ("nego_offer" if rnd == 1
                     else "nego_close" if (T and rnd >= T - 1)
                     else "nego_doom" if (step > 0 and rnd >= 4)
                     else "nego_counter")
        return price, situation

    def counter():
        """Reject-with-counteroffer using the fully shaped quote."""
        sq = shaped_quote()
        if sq is None:
            return {"decision": "WalkAway"}
        return {"decision": "RejectOffer", **offer(sq[0], sq[1])}

    if action_type == "offer":
        sq = shaped_quote()
        if sq is None:
            return {"decision": "WalkAway"}
        return offer(sq[0], sq[1])

    price = float(lo.get("price") if lo.get("price") is not None
                  else lo.get("product_price"))
    s_now = surplus(price)
    take_any = (profile.nego_take_any_profit
                or (profile.nego_take_any_ab
                    and gid_int(game["game_id"]) % 2 == 0))
    prev_best = mem.get("best_crossed", 0.0)
    if s_now > 0:
        mem["best_crossed"] = max(prev_best, s_now)
    if T and rnd >= T:
        return {"decision": "AcceptOffer"} if s_now > 0 else {"decision": "RejectOffer"}
    opp_prices = []
    for h in state.get("history", []):
        off_h = h.get("offer") or {}
        hp = off_h.get("price", off_h.get("product_price"))
        if hp is not None and off_h.get("from_player") != game["your_player"]:
            opp_prices.append(surplus(float(hp)))
    conceding = (len(opp_prices) >= 3
                 and opp_prices[-1] > opp_prices[-2] > opp_prices[-3]
                 and (opp_prices[-1] - opp_prices[-3]) >= 0.02 * my_value)
    max_surplus = (abs(float(opp_value_raw) - my_value)
                   if opp_value_raw is not None else None)
    if ((profile.nego_thin_guard_on
         or (profile.nego_thin_guard_ab and gid_int(game["game_id"]) % 2 == 0))
            and max_surplus is not None
            and not (T and rnd >= T) and s_now > 0):
        thin = max_surplus > 0 and s_now < 0.25 * max_surplus and rnd <= 2
        fold = max_surplus > 0 and s_now < 0.40 * max_surplus and conceding
        if thin or fold:
            return counter()
    if s_now > 0:
        if T and rnd >= T - 1 and i_have_last_offer:
            decent = ((max_surplus is not None and s_now >= 0.70 * max_surplus)
                      or (max_surplus is None and F(s_now) >= 0.45))
            if not decent:
                return counter()
        if take_any:
            return {"decision": "AcceptOffer"}
        now_pct = F(s_now)
        if now_pct >= 0.80:
            return {"decision": "AcceptOffer"}
        best_quote = shaped_quote()
        best_alt = surplus(best_quote[0]) if best_quote else 0.0
        if s_now >= kappa * max(best_alt, 0.0):
            return {"decision": "AcceptOffer"}
        if now_pct >= max(F(max(surplus(mid), 0.0)) - 0.05, ACCEPT_PCT_FLOOR):
            return {"decision": "AcceptOffer"}
        if T and rnd >= T - 1 and not i_have_last_offer:
            return {"decision": "AcceptOffer"}
        late = (rnd >= T - 2) if T else (rnd >= 8)
        if late and s_now >= 0.5 * prev_best:
            if max_surplus is None or s_now >= 0.35 * max_surplus:
                return {"decision": "AcceptOffer"}
    if (complete and not T and rnd >= 50 and s_now > 0
            and s_now >= prev_best):
        return {"decision": "AcceptOffer"}
    if (not T and rnd >= 12 and mem.get("best_crossed", 0.0) <= 0.0
            and _may_walk(profile, game)):
        return {"decision": "WalkAway"}
    return counter()
