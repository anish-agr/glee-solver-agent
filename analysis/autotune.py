"""Try one step up and down on allowed parameters in the simulator and adopt clear gains."""

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "analysis"))

from simulate import evaluate                                    # noqa: E402
from glee_agent.overrides import (ALLOWED_OVERRIDES, DEFAULT_PATH, load_raw,  # noqa: E402
                                  apply_overrides)
from glee_agent.profiles import PROFILES                         # noqa: E402
import dataclasses                                               # noqa: E402

SEEDS = (9191, 313)
N_GAMES = 250
MIN_GAIN = 8.0
MAX_ADOPTIONS = 2
HISTORY = os.path.join(ROOT, "logs", "autotune_history.log")

PLAN = {
    "barg_accept_margin":      ("bargaining",  0.02),
    "barg_open_share":         ("bargaining",  0.02),
    "barg_risk_lambda":        ("bargaining",  0.05),
    "nego_risk_lambda":        ("negotiation", 0.05),
    "nego_accept_kappa":       ("negotiation", 0.02),
    "pers_test_budget":        ("persuasion",  1),
    "pers_hard_honest_rounds": ("persuasion",  1),
}

TARGET_PROFILES = ("optima",)


def log_line(msg):
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"{stamp} {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def family_score(profile, family, seed):
    return evaluate(profile, [family], N_GAMES, seed=seed)[family]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="evaluate and report, but never write overrides.json")
    args = ap.parse_args()

    base = apply_overrides(PROFILES["optima"])
    log_line(f"autotune start (dry_run={args.dry_run})")

    baselines = {}
    adoptions = []
    for knob, (family, step) in PLAN.items():
        if len(adoptions) >= MAX_ADOPTIONS:
            break
        lo, hi, typ = ALLOWED_OVERRIDES[knob]
        cur = getattr(base, knob)
        if family not in baselines:
            baselines[family] = {s: family_score(base, family, s) for s in SEEDS}
        best = None
        for cand in (typ(round(cur - step, 6)), typ(round(cur + step, 6))):
            if not (lo <= cand <= hi) or cand == cur:
                continue
            trial = dataclasses.replace(base, **{knob: cand})
            g1 = family_score(trial, family, SEEDS[0]) - baselines[family][SEEDS[0]]
            if g1 < 0:
                log_line(f"  {knob} {cur}->{cand}: seed{SEEDS[0]} {g1:+.1f}, skipped")
                continue
            g2 = family_score(trial, family, SEEDS[1]) - baselines[family][SEEDS[1]]
            mean = (g1 + g2) / 2
            log_line(f"  {knob} {cur}->{cand}: gains {g1:+.1f}/{g2:+.1f} mean {mean:+.1f}")
            if mean >= MIN_GAIN and min(g1, g2) >= 0 and \
                    (best is None or mean > best[1]):
                best = (cand, mean)
        if best is not None:
            adoptions.append((knob, cur, best[0], best[1]))
            base = dataclasses.replace(base, **{knob: best[0]})
            baselines.pop(family)

    if not adoptions:
        log_line("no knob cleared the gate; overrides unchanged")
        return
    if args.dry_run:
        log_line(f"dry run: would adopt {adoptions}")
        return

    data = load_raw(DEFAULT_PATH)
    for prof in TARGET_PROFILES:
        entry = data.setdefault(prof, {})
        for knob, _old, new, _gain in adoptions:
            entry[knob] = new
    os.makedirs(os.path.dirname(DEFAULT_PATH), exist_ok=True)
    tmp = DEFAULT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DEFAULT_PATH)
    for knob, old, new, gain in adoptions:
        log_line(f"ADOPTED {knob}: {old} -> {new} (mean gain {gain:+.1f}) "
                 f"for {','.join(TARGET_PROFILES)}")


if __name__ == "__main__":
    main()
