"""Persuasion engine: repeated sales with asymmetric quality information."""

from __future__ import annotations

import math

from ..assignment import gid_int
from ..profiles import Profile

LIE_RATES = [0.0, 0.15, 0.30, 0.50, 0.70, 1.0]
LIE_RATE_PRIOR = [0.28, 0.30, 0.17, 0.08, 0.05, 0.12]
P_HIGH_UNRECOMMENDED = 0.02  # chance a high-quality good goes unrecommended


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    if n <= 0:
        return 1.0
    p = min(max(p, 1e-9), 1 - 1e-9)
    total = 0.0
    for i in range(0, min(k, n) + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return min(max(total, 0.0), 1.0)


def _norm(state: dict) -> dict:
    price = float(state["product_price"])
    v_raw = state.get("v")
    if v_raw is None:
        v_mult, v, v_known = 2.0, 2.0 * price, False
    else:
        v_raw = float(v_raw)
        v_mult = v_raw / price if v_raw > 10 else v_raw
        v = v_raw if v_raw > 10 else v_raw * price
        v_known = True
    u_raw = state.get("u", 0.0) or 0.0
    u = float(u_raw) if float(u_raw) > 10 else float(u_raw) * price
    return dict(price=price, p=float(state["p"]), v=v, u=u, v_mult=round(v_mult, 4),
                v_known=v_known, T=int(state.get("total_rounds", 20)),
                rnd=int(state.get("round", 1)))


def act(game: dict, profile: Profile, ctx) -> dict:
    state = game["game_state"]
    cfg = _norm(state)
    action_type = game["valid_actions"]["type"]
    p, price, v, u, T, rnd = cfg["p"], cfg["price"], cfg["v"], cfg["u"], cfg["T"], cfg["rnd"]
    ev_blind = p * v + (1 - p) * u - price
    from_end = T - rnd

    if action_type in ("seller_message", "seller_recommendation"):
        quality = state.get("current_quality")
        hist = state.get("history", [])

        ev_blind_adjusted = ev_blind
        if not cfg["v_known"] and rnd >= 5 and p >= 0.75:
            if sum(1 for h in hist[:4] if h.get("bought")) <= 2:
                ev_blind_adjusted = p * (1.2 * price) + (1 - p) * u - price

        recs = [h for h in hist
                if h.get("bought") is not None and ctx.classify_seller_signal(h)]
        rec_follow = (sum(1 for h in recs if h.get("bought")) / len(recs)) if recs else None
        burned = [h for h in hist if h.get("bought") and h.get("quality") == "low"]
        post_burn = [h for h in hist if burned and h["round"] > burned[0]["round"]]
        forgiving = (sum(1 for h in post_burn if h.get("bought")) / len(post_burn)) > 0.5 if post_burn else False
        distrusting = burned and post_burn and \
            (sum(1 for h in post_burn if h.get("bought")) / len(post_burn)) < 0.25

        if quality == "high":
            rec = True
        else:
            v_cap = v if cfg["v_known"] else 1.25 * price
            q_star = max(0.0, min(1.0, p * (v_cap - price) / max((1 - p) * price, 1e-9)))
            q = q_star * profile.pers_lie_cap_mult
            if ev_blind_adjusted > 0:
                q = 1.0
            elif rnd <= (profile.pers_hard_honest_lo
                         if (profile.pers_hard_honest_ab
                             and (gid_int(game["game_id"]) >> 9) % 2 == 0)
                         else profile.pers_hard_honest_rounds):
                q = 0.0
            if rnd <= profile.pers_honest_open_rounds and ev_blind_adjusted <= 0:
                q = 0.0
            if distrusting:
                q = 0.0
            if (rnd > profile.pers_honest_open_rounds
                    and rec_follow is not None and rec_follow > 0.90
                    and len(recs) >= 10):
                q = max(q, 0.9)
            if profile.pers_exploit_forgiving and forgiving:
                q = max(q, 0.85)
            n_sales = sum(1 for h in hist if h.get("bought"))
            n_offers = len(hist)
            give_up_at = max(profile.pers_hard_honest_rounds + 4, 8)
            if rnd >= give_up_at and n_sales == 0:
                q = 1.0
            elif n_offers >= 4 and n_sales >= 0.8 * n_offers:
                q = 1.0
            if from_end < profile.pers_harvest_rounds:
                q = 1.0
            if (profile.pers_flat_rec_ab
                    and (gid_int(game["game_id"]) >> 5) % 2 == 0):
                flat_cap = (profile.pers_flat_rec_target - p) / max(1.0 - p, 1e-9)
                q = min(q, max(0.0, min(1.0, flat_cap)))
            n_lows = sum(1 for h in hist if h.get("quality") == "low") + 1
            draw = gid_int(f"{game['game_id']}:{n_lows}") % 1000
            rec = draw < q * 1000.0

        if action_type == "seller_recommendation":
            return {"decision": "yes" if rec else "no"}
        conf_lies = (profile.pers_conf_always
                     or (profile.pers_conf_ab
                         and gid_int(game["game_id"]) % 2 == 0))
        if rec and (quality == "high" or conf_lies):
            situation = "pers_rec"
        elif rec:
            situation = "pers_rec_soft"
        else:
            situation = "pers_antirec"
        if profile.pers_short_ab and gid_int(game["game_id"]) % 2 == 0:
            situation = "pers_rec_short" if rec else "pers_antirec_short"
        return {"message": ctx.render_message(situation, game, profile, round=rnd)}

    hist = state.get("history", [])
    rec_hi = rec_lo = 0
    for h in hist:
        if not h.get("bought") or h.get("quality") is None:
            continue
        if ctx.classify_seller_signal(h):
            if h["quality"] == "high":
                rec_hi += 1
            else:
                rec_lo += 1

    cur_rec = ctx.classify_seller_signal({"seller_message": state.get("seller_message")})

    weights = []
    for q, w in zip(LIE_RATES, LIE_RATE_PRIOR, strict=True):
        ph = p / (p + (1 - p) * q)
        weights.append(w * (ph ** rec_hi) * ((1 - ph) ** rec_lo))
    z = sum(weights) or 1.0
    weights = [w / z for w in weights]
    if (cur_rec and from_end < profile.pers_guard_rounds
            and not (rec_lo == 0 and rec_hi >= 5)):
        shift = min(0.5, (profile.pers_guard_mult - 1.0) / 2)
        weights = [w * (1 - shift) for w in weights]
        weights[-1] += shift

    if cur_rec:
        p_high = sum(w * (p / (p + (1 - p) * q))
                     for q, w in zip(LIE_RATES, weights, strict=True))
    else:
        lik = [w * ((1 - p) * (1 - q) + p * P_HIGH_UNRECOMMENDED)
               for q, w in zip(LIE_RATES, weights, strict=True)]
        zl = sum(lik) or 1.0
        lik = [x / zl for x in lik]
        p_high = sum(w * (p * P_HIGH_UNRECOMMENDED
                          / (p * P_HIGH_UNRECOMMENDED + (1 - p) * (1 - q) + 1e-9))
                     for q, w in zip(LIE_RATES, lik, strict=True))

    ev = p_high * v - price
    near_break_even = abs(ev_blind) <= 0.05 * price
    n_rec_obs = rec_hi + rec_lo
    if (cur_rec and ev_blind <= 0 and n_rec_obs >= 10 and rnd % 5 != 0
            and _binom_cdf(rec_hi, n_rec_obs, p) < 0.05):
        return {"decision": "no"}
    edge = 0.03 * price if near_break_even else 0.0
    if (profile.pers_buyer_margin_ab
            and v <= profile.pers_buyer_margin_vmax * price
            and (gid_int(game["game_id"]) >> 6) % 2 == 0):
        edge = max(edge, profile.pers_buyer_margin * price)
    if ev > edge:
        return {"decision": "yes"}
    if cur_rec and rec_lo == 0 and rec_hi < profile.pers_test_budget and rnd <= 5 \
            and v >= 1.35 * price:
        return {"decision": "yes"}
    if ev_blind > 0 and cur_rec:
        return {"decision": "yes"}
    return {"decision": "no"}
