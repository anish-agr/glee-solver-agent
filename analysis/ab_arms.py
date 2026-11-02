"""Readout for the randomized experiments, scored on the published curves.

Reads logs/games_<agent>.sqlite, which is not published.
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from scoring import score                                 # noqa: E402
from glee_agent.assignment import gid_int                 # noqa: E402
from glee_agent.profiles import PROFILES                   # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _d(gs, me):
    a, b = gs.get(f"delta_{me}"), gs.get(f"delta_{3 - me}")
    return (float(a) if a is not None else None,
            float(b) if b is not None else None)


def elig_patience(gs, me):
    dm, do = _d(gs, me)
    return dm is not None and do is not None and dm >= 0.999 and do < 0.999


def elig_neverwalk(gs, me):
    return not gs.get("max_rounds")


def elig_even(gs, me):
    dm, do = _d(gs, me)
    if dm is None or do is None:
        return False
    return abs(dm - do) < 0.1499


def elig_weak_cont(gs, me):
    dm, do = _d(gs, me)
    return (bool(gs.get("complete_information"))
            and dm is not None and do is not None and do > dm)


def elig_stonewall(gs, me):
    """Games the stonewall-continuation experiment can change."""
    dm, _ = _d(gs, me)
    if dm is None or dm >= 0.999:
        return False
    money = float(gs.get("money_to_divide") or 0.0)
    if not money:
        return False
    opp = 3 - me
    theirs = []
    for h in gs.get("history", []):
        off = h.get("offer") or {}
        if (h.get("proposer") or "") in (f"player_{opp}",
                                         "Alice" if opp == 1 else "Bob"):
            for k in (f"player_{me}_gain", "alice_gain" if me == 1 else "bob_gain"):
                if off.get(k) is not None:
                    theirs.append(float(off[k]) / money)
                    break
    return len(theirs) >= 2 and theirs[1] - theirs[0] <= 0.01


def elig_any(gs, me):
    return True


def elig_seller(gs, me):
    return gs.get(f"player_{me}_role") == "seller"


def elig_buyer(gs, me):
    if gs.get(f"player_{me}_role") != "buyer":
        return False
    v, price = gs.get("v"), gs.get("product_price")
    if v is None or not price:
        return False
    v = float(v) * (price if float(v) <= 10 else 1.0)
    return v <= 2.0 * float(price)


def elig_power_uncapped(gs, me):
    """Power cell with an uncapped horizon."""
    dm, do = _d(gs, me)
    if dm is None or do is None:
        return False
    if gs.get("max_rounds"):
        return False
    return dm - do >= 0.1499


def elig_not_disadv(gs, me):
    dm, do = _d(gs, me)
    if dm is None or do is None:
        return False
    return do - dm < 0.1499


ARMS = [
    ("half-floor (offer)", 1, "bargaining", None,
     elig_even, "half-floor", None),
    ("patience d_me=1.00", 2, "bargaining", "barg_patience_ab",
     elig_patience, "patient-power", None),
    ("never-walk", 3, "negotiation", "nego_never_walk_ab",
     elig_neverwalk, "never-walk", None),
    ("hold-for-half", 4, "bargaining", "barg_half_accept_ab",
     elig_not_disadv, "hold-half", None),
    ("anchor 0.54 vs 0.50", 5, "bargaining", "barg_anchor_ab",
     elig_even, "floor-0.54", 1),
    ("early close r1-2", 6, "bargaining", "barg_early_close_ab",
     elig_any, "early-close", None),
    ("accept-kappa 0.78", 2, "negotiation", "nego_accept_kappa_ab",
     elig_any, "kappa-0.78", None),
    ("flat rec schedule", 5, "persuasion", "pers_flat_rec_ab",
     elig_seller, "flat-rec", None),
    ("buyer margin (low v)", 6, "persuasion", "pers_buyer_margin_ab",
     elig_buyer, "margin", None),
    ("concession speed k=1.5", 7, "negotiation", "nego_boulware_k_ab",
     elig_any, "k-1.5", None),
    ("stonewall continuation", 3, "bargaining", "barg_stonewall_cont_ab",
     elig_stonewall, "stonewall", None),
    ("horizon-open (bit 0)", 0, "bargaining", "barg_horizon_open_ab",
     elig_any, "horizon-open", None),
    ("power-open uncapped (bit 4)", 4, "bargaining", "barg_power_open_ab",
     elig_power_uncapped, "power-open", None),
    ("weak-position continuation", 8, "bargaining", "barg_weak_cont_ab",
     elig_weak_cont, "weak-cont", None),
    ("credibility 3 vs 6", 9, "persuasion", "pers_hard_honest_ab",
     elig_seller, "honest-3", None),
    ("llm-rewrite (bit 10)", 10, "bargaining", "llm_rewrite_ab",
     elig_any, "llm-off", None),
    ("llm-rewrite nego (bit 10)", 10, "negotiation", "llm_rewrite_ab",
     elig_any, "llm-off", None),
]


ARM_SINCE = {
    "hold-for-half": 1786043400,  # 2026-08-06 19:10 UTC
    "horizon-open (bit 0)": 1786043400,  # 2026-08-06 19:10 UTC
    "accept-kappa 0.78": 1786304700,  # 2026-08-09 19:45 UTC
    "flat rec schedule": 1786307200,  # 2026-08-09 20:26 UTC
    "buyer margin (low v)": 1786307200,  # 2026-08-09 20:26 UTC
    "concession speed k=1.5": 1786307200,  # 2026-08-09 20:26 UTC
    "credibility 3 vs 6": 1786307200,  # 2026-08-09 20:26 UTC
    "weak-position continuation": 1786515000,  # 2026-08-12 06:10 UTC
    "stonewall continuation": 1786912977,  # 2026-08-16 20:42 UTC
    "power-open uncapped (bit 4)": 1787131002,  # 2026-08-19 09:16 UTC
    "llm-rewrite (bit 10)": 1787252318,  # 2026-08-20 18:58 UTC
    "llm-rewrite nego (bit 10)": 1787252318,  # 2026-08-20 18:58 UTC
}


def _llm_capable():
    """Agents that held a language-model key; on the others both halves of bit 10 play the same policy."""
    names = set()
    for path in (os.path.join(ROOT, ".env"),):
        try:
            with io.open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    k = line.split("=", 1)[0].strip()
                    if k.startswith("GEMINI_API_KEY_"):
                        names.add(k[len("GEMINI_API_KEY_"):].lower())
        except OSError:
            pass
    for k in os.environ:
        if k.startswith("GEMINI_API_KEY_"):
            names.add(k[len("GEMINI_API_KEY_"):].lower())
    if not names:
        try:
            with io.open(os.path.join(ROOT, "data", "llm_capable_profiles.json"),
                         encoding="utf-8") as fh:
                names = set(json.load(fh)["llm_capable"])
        except (OSError, KeyError, ValueError):
            pass
    return names


def main(since_ts=0.0):
    missing, stale = [], []
    for prof in sorted(PROFILES):
        db_p = os.path.join(ROOT, "logs", f"games_{prof}.sqlite")
        if not os.path.exists(db_p):
            print(f"{prof}: no database at {db_p}")
            missing.append(prof)
            continue
        db = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
        row = db.execute("select max(first_seen), count(*) from games "
                         "where done=1").fetchone()
        db.close()
        age_h = (time.time() - (row[0] or 0)) / 3600.0
        flag = "  STALE: newest game is more than 24 h old" if age_h > 24 else ""
        if age_h > 24:
            stale.append(prof)
        print(f"data: {prof:<11} {row[1]:>7} games, newest {age_h:>6.1f}h old{flag}")
    print()
    if missing or stale:
        print(f"refusing to report: missing={missing} stale={stale}")
        return 2
    report_arms(since_ts)
    return 0


def report_arms(since_ts=0.0):
    for key, bit, fam, flag, elig, lab0, nest in ARMS:
        profs = ([p for p, pr in PROFILES.items() if getattr(pr, flag, False)]
                 if flag else list(PROFILES))
        if flag == "llm_rewrite_ab":
            cap = _llm_capable()
            dropped = sorted(set(profs) - cap)
            profs = [p for p in profs if p in cap]
            if dropped:
                print(f"\n   [bit 10] excluding {', '.join(dropped)}: no language-model "
                      f"key, so both halves play the same policy")
        if not profs:
            print(f"\n== {key}: no profile carries {flag} ==")
            continue
        arms = {0: [], 1: []}
        for prof in profs:
            path = os.path.join(ROOT, "logs", f"games_{prof}.sqlite")
            if not os.path.exists(path):
                continue
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            cur = db.execute(
                "select game_id, result, final_state from games "
                "where done=1 and family=? and first_seen>?",
                (fam, max(since_ts, ARM_SINCE.get(key, 0.0))))
            while True:
                batch = cur.fetchmany(400)
                if not batch:
                    break
                for gid, rj, fj in batch:
                    try:
                        g = json.loads(fj)
                        res = json.loads(rj) if rj else {}
                    except (TypeError, ValueError):
                        continue
                    gs = g.get("game_state") or {}
                    me = 1 if g.get("your_player") == "player_1" else 2
                    try:
                        if not elig(gs, me):
                            continue
                    except Exception:
                        continue
                    r = score(fam, gs, me, res)
                    if r is None:
                        continue
                    if nest is not None and (gid_int(gid) >> nest) % 2 != 0:
                        continue
                    arms[(gid_int(gid) >> bit) % 2].append(r)
            db.close()
        m = lambda v: sum(v) / len(v) if v else float("nan")
        a, b = arms[0], arms[1]
        delta = m(a) - m(b)
        n = min(len(a), len(b))
        if n == 0:
            print(f"\n== {key}: no eligible games ==")
            continue
        bar = 200.0 * (380.0 / n) ** 0.5
        call = ("adopt" if delta > bar else
                "decline" if delta < -bar else "within threshold")
        print(f"\n== {key} (bit {bit}, {fam}, {'+'.join(sorted(profs))}) ==")
        print(f"  {lab0:>14}: n={len(a):>5}  rating={m(a):>8.0f}")
        print(f"  {'control':>14}: n={len(b):>5}  rating={m(b):>8.0f}")
        print(f"  delta = {delta:+.0f}   bar=+/-{bar:.0f} at n={n}   -> {call}")


if __name__ == "__main__":
    raise SystemExit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0))
