"""Parameter profiles for the five agents."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """Engine parameters. Fields ending in _ab split games on one md5 bit (see ARM_REGISTRY);
    fields ending in _on apply a rule to every game."""

    name: str

    barg_risk_lambda: float = 1.0
    nego_risk_lambda: float = 1.25

    barg_open_share: float = 0.62
    barg_min_open_share: float = 0.50
    barg_floor_rounds: int = 3
    barg_escalation: float = -0.02
    barg_ratchet_softness_min: float = 0.45
    barg_accept_margin: float = 0.09
    barg_lock_in_pct: float = 0.80
    barg_power_share: float = 0.85
    barg_human_share: float = 0.68

    nego_anchor_frac: float = 0.97
    nego_boulware_k: float = 3.0
    nego_accept_kappa: float = 0.78
    nego_fish_rounds: int = 6
    nego_ratchet_step: float = 0.0
    nego_accept_kappa_lo: float = 0.78
    nego_accept_kappa_ab: bool = False

    pers_flat_rec_target: float = 0.85
    pers_flat_rec_ab: bool = False

    pers_buyer_margin_ab: bool = False
    pers_buyer_margin: float = 0.08
    pers_buyer_margin_vmax: float = 2.0

    nego_boulware_k_lo: float = 1.5
    nego_boulware_k_ab: bool = False

    barg_open_share_lo: float = 0.46
    barg_open_share_ab: bool = False

    pers_hard_honest_lo: int = 3
    pers_hard_honest_ab: bool = False

    pers_honest_open_rounds: int = 1
    pers_hard_honest_rounds: int = 6
    pers_lie_cap_mult: float = 1.0
    pers_harvest_rounds: int = 4
    pers_exploit_forgiving: bool = True
    pers_conf_ab: bool = False
    pers_conf_always: bool = False
    pers_short_ab: bool = False

    pers_test_budget: int = 2
    pers_guard_rounds: int = 3
    pers_guard_mult: float = 1.6

    t1_price_fracs: tuple = (0.82,)

    barg_curve_variant: str = "v1"
    barg_curve_ab: bool = False

    barg_band_accept_ab: bool = False
    barg_band_accept_on: bool = False
    barg_band_top_ab: bool = False
    barg_horizon_open_ab: bool = False
    barg_power_open_ab: bool = False
    barg_even_fast_ab: bool = False
    barg_even_fast_on: bool = False

    barg_weak_open_ab: bool = False
    barg_weak_open_on: bool = True
    llm_rewrite_ab: bool = False
    barg_role_floor_ab: bool = False
    barg_tie_snap_ab: bool = False
    barg_uncapped_decay: bool = False

    barg_weak_cont_ab: bool = False
    barg_stonewall_cont_ab: bool = False
    barg_accept_floor: float = 0.30
    barg_accept_floor_power: float = 0.40

    barg_patience_ab: bool = False
    barg_patience_on: bool = False

    barg_delta_acc_ab: bool = False
    barg_delta_acc_on: bool = False

    barg_half_floor: float = 0.50
    barg_half_accept_ab: bool = False
    barg_early_close_ab: bool = False
    barg_early_close_on: bool = False
    barg_early_close_bonus: float = 0.12
    barg_half_floor_on: bool = False
    barg_anchor_hi: float = 0.54
    barg_anchor_ab: bool = False

    nego_schedule_on: bool = False
    nego_schedule_ab: bool = False
    nego_stonewall: bool = True

    nego_never_walk: bool = True
    nego_never_walk_ab: bool = False

    nego_warm_voice: bool = False

    nego_close_ab: bool = False

    nego_take_any_profit: bool = False
    nego_take_any_ab: bool = False
    nego_thin_guard_on: bool = True
    nego_thin_guard_ab: bool = False

    nego_acc_variant: str = "v1"
    nego_quote_ab: bool = False

    msg_style: str = "warm"


OPTIMA = Profile(
    name="optima",
    llm_rewrite_ab=True,
    t1_price_fracs=(0.72, 0.82, 0.92),
    nego_acc_variant="live",
    pers_conf_always=True,
    barg_band_accept_on=True,
)

LEVIATHAN = Profile(
    name="leviathan",
    llm_rewrite_ab=True,
    barg_open_share=0.70,
    barg_escalation=+0.02,
    barg_power_share=0.92,
    barg_human_share=0.72,
    barg_min_open_share=0.54,
    nego_anchor_frac=1.00,
    nego_warm_voice=True,
    barg_band_accept_on=True,
    nego_acc_variant="live",
    nego_schedule_on=True,
    pers_conf_always=True,
    msg_style="pressure",
)

PROSPECTOR = Profile(
    name="prospector",
    llm_rewrite_ab=True,
    t1_price_fracs=(0.55, 0.65, 0.75, 0.85, 0.95),
    pers_conf_always=True,
    barg_band_accept_on=True,
    nego_acc_variant="live",
)

VELOCITY = Profile(
    name="velocity",
    nego_accept_kappa_ab=True,
    pers_buyer_margin_ab=True,
    pers_hard_honest_ab=True,
    llm_rewrite_ab=True,
    barg_stonewall_cont_ab=True,
    barg_band_accept_on=True,
    nego_risk_lambda=1.10,
    nego_acc_variant="live",
    t1_price_fracs=(0.72, 0.82),
    pers_conf_always=True,
    nego_schedule_on=True,
    barg_uncapped_decay=True,
    barg_horizon_open_ab=True,
    pers_lie_cap_mult=1.4,
    pers_harvest_rounds=6,
    pers_hard_honest_rounds=3,
)

CITADEL = Profile(
    name="citadel",
    nego_accept_kappa_ab=True,
    pers_buyer_margin_ab=True,
    pers_hard_honest_ab=True,
    llm_rewrite_ab=True,
    barg_stonewall_cont_ab=True,
    nego_schedule_on=True,
    nego_acc_variant="live",
    nego_fish_rounds=8,
    barg_band_accept_on=True,
    t1_price_fracs=(0.72, 0.82),
    pers_conf_always=True,
    barg_horizon_open_ab=True,
)

PROFILES = {p.name: p for p in (OPTIMA, LEVIATHAN, PROSPECTOR, VELOCITY, CITADEL)}


# (name, bit, family, is_live(profile), nested_in_bit)
ARM_REGISTRY = (
    ("horizon-open",   0, "bargaining",  lambda p: p.barg_horizon_open_ab, None),
    ("role-floor",     0, "bargaining",  lambda p: p.barg_role_floor_ab, None),
    ("tie-snap",       0, "bargaining",  lambda p: p.barg_tie_snap_ab, None),
    ("curve-v1v4",     0, "bargaining",  lambda p: p.barg_curve_ab, None),
    ("band-accept",    0, "bargaining",  lambda p: p.barg_band_accept_ab, None),
    ("band-top",       0, "bargaining",  lambda p: p.barg_band_top_ab, None),
    ("delta-accept",   1, "bargaining",  lambda p: p.barg_delta_acc_ab, None),
    ("patience",       2, "bargaining",  lambda p: p.barg_patience_ab, None),
    ("power-open",     4, "bargaining",  lambda p: p.barg_power_open_ab, None),
    ("even-fast",      4, "bargaining",  lambda p: p.barg_even_fast_ab, None),
    ("hold-for-half",  4, "bargaining",  lambda p: p.barg_half_accept_ab, None),
    ("weak-open",      7, "bargaining",  lambda p: p.barg_weak_open_ab, None),
    ("stonewall-cont", 3, "bargaining",  lambda p: p.barg_stonewall_cont_ab, None),
    ("anchor-0.54",    5, "bargaining",  lambda p: p.barg_anchor_ab, None),
    ("early-close",    6, "bargaining",  lambda p: p.barg_early_close_ab, None),
    ("nego-schedule",  0, "negotiation", lambda p: p.nego_schedule_ab, None),
    ("take-any",       0, "negotiation", lambda p: p.nego_take_any_ab, None),
    ("quote-belief",   0, "negotiation", lambda p: p.nego_quote_ab, None),
    ("closer",         0, "negotiation", lambda p: p.nego_close_ab, None),
    ("thin-guard",     0, "negotiation", lambda p: p.nego_thin_guard_ab, None),
    ("never-walk",     3, "negotiation", lambda p: p.nego_never_walk_ab, None),
    ("accept-kappa",   2, "negotiation", lambda p: p.nego_accept_kappa_ab, None),
    ("flat-rec",       5, "persuasion",  lambda p: p.pers_flat_rec_ab, None),
    ("buyer-margin",   6, "persuasion",  lambda p: p.pers_buyer_margin_ab, None),
    ("concession-speed", 7, "negotiation", lambda p: p.nego_boulware_k_ab, None),
    ("open-floor",     8, "bargaining",  lambda p: p.barg_open_share_ab, None),
    ("weak-cont",      8, "bargaining",  lambda p: p.barg_weak_cont_ab, None),
    ("credibility",    9, "persuasion",  lambda p: p.pers_hard_honest_ab, None),
    ("confident-lie",  0, "persuasion",  lambda p: p.pers_conf_ab, None),
    ("short-plain",    0, "persuasion",  lambda p: p.pers_short_ab, None),
    ("llm-rewrite",   10, "bargaining",  lambda p: p.llm_rewrite_ab, None),
    ("llm-rewrite",   10, "negotiation", lambda p: p.llm_rewrite_ab, None),
)


def live_arms(profile):
    """Experiments randomized on this profile, as (name, bit, family, nested_in)."""
    return [(n, b, f, nest) for n, b, f, pred, nest in ARM_REGISTRY if pred(profile)]


def arm_collisions(profile):
    """Any (family, bit) with more than one live experiment."""
    seen = {}
    for n, b, f, _ in live_arms(profile):
        seen.setdefault((f, b), []).append(n)
    return {kk: v for kk, v in seen.items() if len(v) > 1}
