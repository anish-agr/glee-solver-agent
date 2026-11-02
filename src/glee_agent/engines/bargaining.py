"""Bargaining engine: alternating offers over a shrinking pot."""

from __future__ import annotations

from ..assignment import gid_int
from ..curves import key_of
from ..profiles import Profile

DELTA_GRID = [0.8, 0.9, 0.95, 1.0]
EDGE_GAP = 0.1499  # discount-factor gap that counts as a positional edge (0.15 less float slack)

ACCEPT_EARLY_V1 = [(0.20, 0.05), (0.35, 0.07), (0.42, 0.15), (0.475, 0.37),
                (0.50, 0.45), (0.55, 0.50), (1.01, 0.55)]
ACCEPT_LATE_V1 = [(0.35, 0.02), (0.42, 0.04), (0.475, 0.07), (0.50, 0.08),
               (0.55, 0.12), (1.01, 0.20)]

ACCEPT_EARLY_V4 = [(0.10, 0.12), (0.25, 0.07), (0.375, 0.30), (0.425, 0.38),
                   (0.4999, 0.47), (1.01, 0.70)]
ACCEPT_LATE_V4 = [(0.25, 0.09), (0.375, 0.05), (0.425, 0.10), (0.475, 0.06),
                  (0.52, 0.08), (1.01, 0.12)]


WALL_NAMES = {"wall-A", "wall-B", "wall-C", "wall-D",
              "wall-E", "wall-F", "wall-G"}
WALL_SOFTNESS_CAP = 0.25

SOFT_NAMES = {"soft-A", "soft-B", "soft-C", "soft-D", "soft-E", "soft-F"}
SOFT_SOFTNESS_FLOOR = 0.70


def _curve(table, share):
    for ub, p in table:
        if share <= ub:
            return p
    return table[-1][1]


DELTA_ACC_MULT = {0.80: 1.59, 0.90: 1.31, 0.95: 0.93, 1.00: 0.58}


def _delta_acc_mult(d_opp_raw) -> float:
    """Acceptance multiplier for a disclosed opponent discount factor."""
    if d_opp_raw is None:
        return 1.0
    d = float(d_opp_raw)
    near = min(DELTA_ACC_MULT, key=lambda k: abs(k - d))
    return DELTA_ACC_MULT[near] if abs(near - d) < 0.03 else 1.0


def p_accept(share_to_opp: float, softness: float, rnd: int = 1,
             variant: str = "v1") -> float:
    """Acceptance probability for a share, scaled by opponent softness in [0, 1]."""
    if variant == "v4":
        table = ACCEPT_EARLY_V4 if rnd <= 2 else ACCEPT_LATE_V4
    else:
        table = ACCEPT_EARLY_V1 if rnd <= 2 else ACCEPT_LATE_V1
    base = _curve(table, share_to_opp)
    return min(base * (0.5 + softness), 0.95)


def spe_proposer_share(d1: float, d2: float, T: int | None, rnd: int, proposer_is_p1: bool) -> float:
    """Nominal share of the pot the round-`rnd` proposer keeps in SPE."""
    d_prop = d1 if proposer_is_p1 else d2
    d_resp = d2 if proposer_is_p1 else d1
    if T is None or T >= 60:
        denom = 1.0 - d1 * d2
        return 1.0 if denom <= 1e-12 else min(1.0, (1.0 - d_resp) / denom)
    v = 1.0
    for t in range(T - 1, rnd - 1, -1):
        dr_t = d_resp if (t - rnd) % 2 == 0 else d_prop
        v = 1.0 - dr_t * v
    return min(max(v, 0.0), 1.0)


def _me_idx(game: dict) -> int:
    return 1 if game["your_player"] == "player_1" else 2


def _candidate_keys(state: dict, me: int) -> list[tuple[str, float]]:
    money = state["money_to_divide"]
    mr = state.get("max_rounds") or 99
    complete = state.get("complete_information", True)
    msgs = state.get("messages_allowed", False)
    d1, d2 = state.get("delta_1"), state.get("delta_2")
    if d1 is not None and d2 is not None:
        return [(key_of(money=money, max_rounds=mr, delta_1=d1, delta_2=d2,
                        complete_information=complete, messages_allowed=msgs), 1.0)]
    known = d1 if me == 1 else d2
    out = []
    for gdelta in DELTA_GRID:
        dd1 = known if me == 1 else gdelta
        dd2 = gdelta if me == 1 else known
        out.append((key_of(money=money, max_rounds=mr, delta_1=dd1, delta_2=dd2,
                           complete_information=complete, messages_allowed=msgs), 0.25))
    return out


def _update_softness(state: dict, me: int, mem: dict) -> float:
    """Opponent softness in [0, 1], estimated from the game history."""
    s = 0.5
    money = float(state["money_to_divide"]) or 1.0
    opp = 3 - me

    def gain_of(off: dict, player: int):
        """A player's gain from an offer, in either server format."""
        for k in (f"player_{player}_gain", "alice_gain" if player == 1 else "bob_gain"):
            if off.get(k) is not None:
                return float(off[k])
        return None

    for h in state.get("history", []):
        off = h.get("offer") or {}
        dec = (h.get("decision") or "").lower()
        prop = h.get("proposer")
        ours = prop in (f"player_{me}", "Alice" if me == 1 else "Bob")
        if ours:
            share = gain_of(off, opp)
            if share is None:
                continue
            share /= money
            if dec == "accept" and share < 0.45:
                s += 0.30
            elif dec == "reject":
                if share >= 0.50:
                    s -= 0.30
                elif share >= 0.45:
                    s -= 0.15
                elif share >= 0.35:
                    s -= 0.08
        else:
            g_self = gain_of(off, opp)
            if g_self is not None and g_self / money >= 0.65:
                s -= 0.05
    s = min(max(s, 0.0), 1.0)
    mem["softness"] = s
    return s


def act(game: dict, profile: Profile, ctx) -> dict:
    state = game["game_state"]
    me = _me_idx(game)
    money = float(state["money_to_divide"])
    rnd = int(state.get("round", 1))
    T = state.get("max_rounds")
    T = int(T) if T else None
    complete = state.get("complete_information", True)
    d_me = float(state.get(f"delta_{me}") or 1.0)
    d_opp_raw = state.get(f"delta_{3 - me}")
    d_opp = float(d_opp_raw) if d_opp_raw is not None else sum(DELTA_GRID) / len(DELTA_GRID)
    delta_acc_mult = (_delta_acc_mult(d_opp_raw)
            if (profile.barg_delta_acc_on
                or (profile.barg_delta_acc_ab
                    and (gid_int(game["game_id"]) >> 1) % 2 == 0))
            else 1.0)
    role = "alice" if me == 1 else "bob"
    keys = _candidate_keys(state, me)
    F = lambda x: ctx.curves.percentile_mix("bargaining", keys, role, x)
    mem = ctx.memory(game["game_id"])
    softness = _update_softness(state, me, mem)
    is_human = ctx.opponent_is_human(game)
    if is_human:
        softness = min(softness, WALL_SOFTNESS_CAP)
    opp_name = ctx.opponent_info(game).get("name")
    opp_is_wall = opp_name in WALL_NAMES
    if opp_is_wall:
        softness = min(softness, WALL_SOFTNESS_CAP)
    elif opp_name in SOFT_NAMES and not is_human:
        softness = max(softness, SOFT_SOFTNESS_FLOOR)

    curve_variant = profile.barg_curve_variant
    if profile.barg_curve_ab:
        curve_variant = "v4" if gid_int(game["game_id"]) % 2 == 0 else "v1"

    if "last_own_share" not in mem and money:
        for h in state.get("history", []):
            off = h.get("offer") or {}
            prop = h.get("proposer") or off.get("proposer")
            if prop in (f"player_{me}", "Alice" if me == 1 else "Bob"):
                for k in (f"player_{me}_gain", "alice_gain" if me == 1 else "bob_gain"):
                    if off.get(k) is not None:
                        mem["last_own_share"] = float(off[k]) / money
                        break

    my_decay = d_me ** (rnd - 1)
    d1 = d_me if me == 1 else d_opp
    d2 = d_opp if me == 1 else d_me

    if game["valid_actions"]["type"] == "offer":
        spe = spe_proposer_share(d1, d2, T, rnd, proposer_is_p1=(me == 1))

        cont_pay = 0.5 * money * d_me ** (rnd + 1)
        cont_pct = F(cont_pay) * profile.barg_risk_lambda
        have = ctx.curves.has_data("bargaining", keys, role)
        best_share, best_ev = 0.5, -1.0
        gridlo, gridhi = 0.42, 0.96
        cand = [gridlo + i * 0.02 for i in range(int((gridhi - gridlo) / 0.02) + 1)]
        for s in cand:
            pa = min(1.0, p_accept(1.0 - s, softness, rnd, curve_variant) * delta_acc_mult)
            ev = (pa * F(s * money * my_decay) + (1 - pa) * cont_pct if have
                  else pa * s * my_decay + (1 - pa) * 0.5 * d_me ** rnd)
            if ev > best_ev:
                best_share, best_ev = s, ev
        share = best_share

        no_self_decay = (d_me >= 0.999 and d_opp < 0.999
                         and (profile.barg_patience_on
                              or (profile.barg_patience_ab
                                  and (gid_int(game["game_id"]) >> 2) % 2 == 0)))
        if d_me - d_opp >= EDGE_GAP or no_self_decay:
            share = max(share, profile.barg_power_share, min(spe * 0.92, 0.92))
        elif d_opp - d_me >= EDGE_GAP:
            share = min(share, 0.52) if rnd >= 2 else max(share, 0.55)
        else:
            floor = profile.barg_min_open_share
            if (profile.barg_open_share_ab
                    and (gid_int(game["game_id"]) >> 8) % 2 == 0):
                floor = profile.barg_open_share_lo
            if rnd <= profile.barg_floor_rounds:
                share = max(share, floor)
            else:
                if profile.barg_uncapped_decay and not T:
                    decayed = 0.50 + (profile.barg_open_share - 0.50) * (d_me ** (rnd - 1))
                    share = min(share, max(0.50, decayed))
                over = rnd - profile.barg_floor_rounds
                settle = min(0.55, floor)
                share = min(share, max(settle, floor - 0.03 * over))
            if profile.barg_half_floor_on:
                half_floor = profile.barg_half_floor
                if (profile.barg_anchor_ab
                        and (gid_int(game["game_id"]) >> 5) % 2 == 0):
                    half_floor = profile.barg_anchor_hi
                share = max(share, half_floor)
        power = d_me - d_opp >= EDGE_GAP
        power_open = power and rnd <= 2
        if power_open:
            share = min(share, 0.55)
        horizon_open = bool(profile.barg_horizon_open_ab and T and rnd <= 2
                             and not power
                             and gid_int(game["game_id"]) % 2 == 0)
        if horizon_open:
            share = min(share, 0.50)
        even_fast_cell = (not T and rnd >= 3
                           and abs(d_me - d_opp) < EDGE_GAP
                           and state.get("complete_information", True))
        even_fast = bool(even_fast_cell and (
            profile.barg_even_fast_on
            or (profile.barg_even_fast_ab
                and (gid_int(game["game_id"]) >> 4) % 2 == 0)))
        if even_fast:
            share = min(share, 0.50)
        weak_open_cell = (not T and rnd <= 2
                           and d_opp - d_me >= EDGE_GAP
                           and state.get("complete_information", True))
        weak_open = bool(weak_open_cell and (
            profile.barg_weak_open_on
            or (profile.barg_weak_open_ab
                and (gid_int(game["game_id"]) >> 7) % 2 == 0)))
        if weak_open:
            share = min(share, 0.40)
        capped_open = bool(power_open or horizon_open or even_fast
                          or weak_open)
        if is_human:
            share = min(share, profile.barg_human_share)
            if rnd <= 2:
                share = min(share, 0.50)
                capped_open = True
        if opp_is_wall and rnd <= 2:
            capped_open = True
            share = min(share, 0.50)
        if T and rnd >= T:
            share = min(max(share, 0.80), 0.85)

        ratcheting = False
        if profile.barg_escalation > 0 and "last_own_share" in mem:
            near_end = bool(T) and rnd >= T - 2
            if softness >= profile.barg_ratchet_softness_min and not near_end:
                share = max(share, mem["last_own_share"] + profile.barg_escalation)
                ratcheting = True
        if (not ratcheting and mem.get("last_own_share") is not None
                and mem["last_own_share"] >= 0.50):
            share = min(share, mem["last_own_share"])
        share = min(max(share, 0.05), 0.95)
        mem["last_own_share"] = share

        mine = round(money * share, 2)
        if (profile.barg_tie_snap_ab and not capped_open
                and gid_int(game["game_id"]) % 2 == 0
                and share >= 0.4995 and money > 0.05):
            mine = max(mine, round(money / 2 + 0.01, 2))
        offer = {"alice_gain": mine if me == 1 else round(money - mine, 2),
                 "bob_gain": round(money - mine, 2) if me == 1 else mine}
        if state.get("messages_allowed") and share < 0.65:
            promises_ratchet = profile.barg_escalation > 0 and (ratcheting or rnd == 1)
            if T and rnd >= T - 2:
                situation = "bargaining_late"
            elif rnd == 1:
                situation = "bargaining_open"
            elif promises_ratchet and rnd >= 4:
                situation = "bargaining_doom"
            elif promises_ratchet:
                situation = "bargaining_mid"
            else:
                situation = "bargaining_close"
            next_share = min(share + max(profile.barg_escalation, 0.0), 0.95)
            offer["message"] = ctx.render_message(
                situation, game, profile, round=rnd,
                their_now=round(money * (1 - share), 2),
                their_next=round(money * (1 - next_share), 2),
                rounds_left=(T - rnd) if T else None)
        return offer

    lo = state.get("last_offer") or {}
    raw_gain = lo.get(f"player_{me}_gain")
    if raw_gain is None:
        raw_gain = lo.get("alice_gain" if me == 1 else "bob_gain", 0.0)
    my_gain = float(raw_gain or 0.0)
    now_pct = F(my_gain * my_decay)

    band_on = (profile.barg_band_accept_on
               or (profile.barg_band_accept_ab and gid_int(game["game_id"]) % 2 == 0))
    band_top = float("inf") if (profile.barg_band_top_ab
                       and gid_int(game["game_id"]) % 2 == 0) else 0.425
    if (band_on and rnd <= 2 and money
            and d_me - d_opp < 0.02
            and 0.385 <= my_gain / money < band_top):
        return {"decision": "accept"}

    if T and rnd >= T:
        return {"decision": "accept" if my_gain > 0 else "reject"}

    refused = mem.get("refused_value", 0.0)
    now_value = my_gain * my_decay

    floor_share = profile.barg_accept_floor
    if d_me - d_opp >= EDGE_GAP:
        floor_share = max(floor_share, profile.barg_accept_floor_power)
    early = (rnd < T - 1) if T else (rnd <= 6)
    if (profile.barg_half_accept_ab and early
            and d_opp - d_me < EDGE_GAP
            and (gid_int(game["game_id"]) >> 4) % 2 == 0):
        floor_share = max(floor_share, profile.barg_half_floor)
    below_floor = bool(money) and my_gain < floor_share * money

    def _bank():
        if below_floor:
            return _pass()
        return {"decision": "accept"}

    def _pass():
        mem["refused_value"] = max(refused, now_value)
        return {"decision": "reject"}

    dominated = now_value < refused - 1e-9

    role_floor = 0.45
    if profile.barg_role_floor_ab and me == 1 and gid_int(game["game_id"]) % 2 == 0:
        role_floor = 0.50
    spe_next = spe_proposer_share(d1, d2, T, rnd + 1, proposer_is_p1=(me == 1))
    if (spe_next > 0.05
            and my_gain >= 0.95 * d_me * spe_next * money
            and my_gain >= role_floor * money and not dominated):
        return _bank()

    share_next = min(max(0.5, (mem.get("last_own_share") or profile.barg_open_share)
                         + max(profile.barg_escalation, 0.0)), 0.9)

    stonewall_share = None
    if profile.barg_stonewall_cont_ab and d_me < 0.999 and money:
        their_shares = []
        for h in state.get("history", []):
            off = h.get("offer") or {}
            opp_idx = 3 - me
            if (h.get("proposer") or "") in (f"player_{opp_idx}",
                                              "Alice" if opp_idx == 1 else "Bob"):
                for k in (f"player_{me}_gain",
                           "alice_gain" if me == 1 else "bob_gain"):
                    if off.get(k) is not None:
                        their_shares.append(float(off[k]) / money)
                        break
        if len(their_shares) >= 2 and their_shares[1] - their_shares[0] <= 0.01:
            stonewall_share = max(0.35, min(share_next, max(their_shares)))
    if stonewall_share is not None and (gid_int(game["game_id"]) >> 3) % 2 == 0:
        share_next = stonewall_share
    else:
        stonewall_share = None
    weak_share = max(spe_next, 0.35) if 0.0 <= spe_next < 0.5 else None
    if (weak_share is not None and profile.barg_weak_cont_ab and complete
            and d_opp - d_me > 1e-9
            and (gid_int(game["game_id"]) >> 8) % 2 == 0):
        share_next = min(share_next, weak_share)
    else:
        weak_share = None
    pa = min(1.0, p_accept(1.0 - share_next, softness, rnd + 1, curve_variant) * delta_acc_mult)
    settle_next = share_next * money * d_me ** rnd
    later_share = stonewall_share if stonewall_share is not None else (weak_share if weak_share is not None else 0.5)
    settle_later = later_share * money * d_me ** (rnd + 1)
    cont_pct = pa * F(settle_next) + (1 - pa) * F(settle_later)

    if now_pct >= profile.barg_lock_in_pct and not dominated:
        return _bank()
    early_bonus = (profile.barg_early_close_bonus
                    if (rnd <= 2
                        and (profile.barg_early_close_on
                             or (profile.barg_early_close_ab
                                 and (gid_int(game["game_id"]) >> 6) % 2 == 0)))
                    else 0.0)
    if (now_pct + profile.barg_accept_margin + early_bonus >= cont_pct
            and not dominated):
        return _bank()
    if T and rnd >= T - 1 and my_gain > 0.15 * money:
        return _bank()
    return _pass()
