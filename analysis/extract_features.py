"""Write one feature row per completed game."""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PROFILES = ("optima", "leviathan", "prospector", "velocity", "citadel")


def _num(x):
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return None


def bargaining_row(gs, me, row):
    money = gs.get("money_to_divide") or 0.0
    row["money"] = money
    row["T"] = gs.get("max_rounds")
    row["horizon_known"] = gs.get("horizon_known")
    row["d_me"] = _num(gs.get(f"delta_{me}"))
    row["d_opp"] = _num(gs.get(f"delta_{3 - me}"))
    row["complete_info"] = gs.get("complete_information")
    row["msgs"] = gs.get("messages_allowed")
    mine, theirs, decisions = [], [], []
    for h in gs.get("history", []):
        off = h.get("offer") or {}
        prop = h.get("proposer") or off.get("proposer")
        gain = off.get(f"player_{me}_gain")
        if gain is None or not money:
            continue
        share_to_me = float(gain) / money
        (mine if prop == f"player_{me}" else theirs).append(round(share_to_me, 4))
        decisions.append(h.get("decision"))
    row["my_offers"] = mine
    row["opp_offers"] = theirs
    row["decisions"] = decisions
    res = gs.get("result") or {}
    row["agreed_round"] = res.get("agreed_round")
    return row


def negotiation_row(gs, me, row):
    row["T"] = gs.get("max_rounds")
    row["horizon_known"] = gs.get("horizon_known")
    row["my_role"] = gs.get(f"player_{me}_role")
    row["my_value"] = _num(gs.get(f"player_{me}_value"))
    row["opp_value"] = _num(gs.get(f"player_{3 - me}_value"))
    row["complete_info"] = gs.get("complete_information")
    row["msgs"] = gs.get("messages_allowed")
    mine, theirs = [], []
    for h in gs.get("history", []):
        off = h.get("offer") or {}
        price = _num(off.get("price"))
        frm = off.get("from_player")
        if price is not None:
            (mine if frm == f"player_{me}" else theirs).append(price)
        co = _num(h.get("counteroffer"))
        if co is not None:
            (theirs if frm == f"player_{me}" else mine).append(co)
    row["my_prices"] = mine
    row["opp_prices"] = theirs
    res = gs.get("result") or {}
    row["walked_by"] = res.get("walked_away_by")
    row["agreed_round"] = res.get("agreed_round") or gs.get("round")
    return row


def persuasion_row(gs, me, row):
    row["my_role"] = gs.get(f"player_{me}_role")
    row["T"] = gs.get("total_rounds")
    row["price"] = _num(gs.get("product_price"))
    row["p_high"] = _num(gs.get("p"))
    row["seller_knows_cv"] = gs.get("is_seller_know_cv")
    row["msg_type"] = gs.get("seller_message_type")
    quals, recs, buys = [], [], []
    for h in gs.get("history", []):
        quals.append(1 if h.get("quality") == "high" else 0)
        msg = h.get("seller_message")
        if isinstance(msg, bool):
            recs.append(1 if msg else 0)
        elif isinstance(msg, str):
            recs.append(msg)
        else:
            recs.append(None)
        d = h.get("buyer_decision", h.get("decision"))
        buys.append(1 if d in (True, "buy", "Buy", "yes") else 0)
    row["quality"] = quals
    row["recs"] = recs
    row["buys"] = buys
    res = gs.get("result") or {}
    for k in ("rounds_bought", "bought_high", "bought_low",
              "passed_high", "passed_low", "rounds_played"):
        if res.get(k) is not None:
            row[k] = res[k]
    return row


HANDLERS = {"bargaining": bargaining_row,
            "negotiation": negotiation_row,
            "persuasion": persuasion_row}


def main(out_path):
    if not any(os.path.exists(os.path.join(ROOT, "logs", f"games_{p}.sqlite")) for p in PROFILES):
        sys.exit("no logs/games_*.sqlite found; refusing to overwrite " + out_path)
    n_ok = n_bad = 0
    with gzip.open(out_path, "wt", encoding="utf-8") as out:
        for prof in PROFILES:
            db_path = os.path.join(ROOT, "logs", f"games_{prof}.sqlite")
            if not os.path.exists(db_path):
                continue
            db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = db.execute(
                "select game_id, family, first_seen, result, final_state, opponent "
                "from games where done=1")
            while True:
                batch = cur.fetchmany(500)
                if not batch:
                    break
                for gid, fam, ts, res_j, fs_j, opp in batch:
                    try:
                        g = json.loads(fs_j)
                        res = json.loads(res_j) if res_j else {}
                    except (TypeError, ValueError):
                        n_bad += 1
                        continue
                    gs = g.get("game_state") or {}
                    me = 1 if g.get("your_player") == "player_1" else 2
                    disc = g.get("opponent") or {}
                    row = {
                        "profile": prof, "family": fam, "gid": gid, "ts": ts,
                        "me": me,
                        "opp_name": disc.get("name") or (opp or None),
                        "opp_type": disc.get("type"),
                        "outcome": res.get("outcome") or (gs.get("result") or {}).get("outcome"),
                        "my_pay": _num(res.get(f"player_{me}_payoff")),
                        "opp_pay": _num(res.get(f"player_{3 - me}_payoff")),
                        "rounds": gs.get("round"),
                    }
                    fn = HANDLERS.get(fam)
                    if fn is None:
                        n_bad += 1
                        continue
                    try:
                        row = fn(gs, me, row)
                    except Exception:
                        n_bad += 1
                        continue
                    out.write(json.dumps(row, separators=(",", ":")) + "\n")
                    n_ok += 1
            db.close()
            print(f"{prof}: cumulative rows={n_ok}", flush=True)
    print(f"wrote {n_ok} rows ({n_bad} skipped) -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "logs", "features.jsonl.gz"))
