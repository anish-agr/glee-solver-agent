"""Parameter overrides, applied at each agent restart."""

from __future__ import annotations

import dataclasses
import json
import logging
import os

from .profiles import Profile

log = logging.getLogger("glee_agent.overrides")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PATH = os.path.join(ROOT, "data", "overrides.json")

ALLOWED_OVERRIDES = {
    "barg_accept_margin":      (0.00, 0.20, float),
    "barg_open_share":         (0.55, 0.75, float),
    "barg_risk_lambda":        (0.90, 1.30, float),
    "nego_risk_lambda":        (1.00, 1.60, float),
    "nego_accept_kappa":       (0.75, 0.95, float),
    "nego_fish_rounds":        (3,    8,    int),
    "pers_test_budget":        (0,    4,    int),
    "pers_hard_honest_rounds": (2,    8,    int),
    "pers_harvest_rounds":     (2,    6,    int),
}


def load_raw(path: str = DEFAULT_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        log.warning("overrides file unreadable (%s); ignoring", e)
        return {}


def apply_overrides(profile: Profile, path: str = DEFAULT_PATH) -> Profile:
    """Return `profile` with validated overrides applied."""
    entries = load_raw(path).get(profile.name)
    if not isinstance(entries, dict) or not entries:
        return profile
    accepted = {}
    for k, v in entries.items():
        spec = ALLOWED_OVERRIDES.get(k)
        if spec is None:
            log.warning("override %s.%s rejected: not an allowed override", profile.name, k)
            continue
        lo, hi, typ = spec
        try:
            v = typ(v)
        except (TypeError, ValueError):
            log.warning("override %s.%s rejected: bad value %r", profile.name, k, v)
            continue
        if not (lo <= v <= hi):
            log.warning("override %s.%s rejected: %s outside [%s, %s]",
                        profile.name, k, v, lo, hi)
            continue
        if getattr(profile, k) != v:
            accepted[k] = v
    if not accepted:
        return profile
    log.info("overrides applied to %s: %s", profile.name, accepted)
    return dataclasses.replace(profile, **accepted)
