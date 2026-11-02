"""Stream the GLEE research-dataset archive into the parquet tables in data/.

usage: python analysis/build_dataset.py <archive.tar.gz>
"""

import csv
import io
import json
import os
import sys
import tarfile
import time
from collections import defaultdict

import pandas as pd

GAMES = []
BARG_DEC = []
NEGO_DEC = []
PERS_ROUNDS = []
SKIPPED = defaultdict(int)


def parse_bargaining(gid, src, cfg, rows):
    ga = cfg["game_args"]
    d1, d2 = float(ga["delta_1"]), float(ga["delta_2"])
    money = float(ga["money_to_divide"])
    first_share = None
    last_offer = None
    outcome, accept_round = "no_agreement", None
    a_pay = b_pay = 0.0
    n_rounds = 0
    for r in rows:
        rnd = int(r["round"]) if r.get("round") else n_rounds
        n_rounds = max(n_rounds, rnd)
        if r.get("alice_gain") not in (None, "", "None"):
            ag, bg = float(r["alice_gain"]), float(r["bob_gain"])
            last_offer = (ag, bg, r["player"], rnd)
            if first_share is None:
                first_share = ag / money if money else None
        dec = (r.get("decision") or "").strip().lower()
        if dec and dec != "none":
            if last_offer:
                responder = r["player"]
                share = (last_offer[0] if responder == "Alice" else last_offer[1]) / money
                BARG_DEC.append(dict(
                    game_id=gid, source=src, responder=responder,
                    responder_model=(cfg["player_1_args"]["model_name"] if responder == "Alice"
                                     else cfg["player_2_args"]["model_name"]),
                    round=rnd, share_offered=share, decision=dec,
                    money=money, max_rounds=ga.get("max_rounds"),
                    delta_1=d1, delta_2=d2,
                    complete_information=ga.get("complete_information"),
                    messages_allowed=ga.get("messages_allowed"),
                ))
            if dec == "accept" and last_offer:
                outcome, accept_round = "agreement", rnd
                a_pay = last_offer[0] * d1 ** (rnd - 1)
                b_pay = last_offer[1] * d2 ** (rnd - 1)
            elif dec == "walkaway":
                outcome = "walkaway"
    GAMES.append(dict(
        game_id=gid, source=src, family="bargaining",
        p1_model=cfg["player_1_args"]["model_name"],
        p2_model=cfg["player_2_args"]["model_name"],
        money=money, max_rounds=ga.get("max_rounds"), delta_1=d1, delta_2=d2,
        complete_information=ga.get("complete_information"),
        messages_allowed=ga.get("messages_allowed"),
        n_rounds=n_rounds, outcome=outcome, accept_round=accept_round,
        first_offer_alice_share=first_share,
        p1_payoff=a_pay, p2_payoff=b_pay,
    ))


def parse_negotiation(gid, src, cfg, rows):
    ga = cfg["game_args"]
    M = float(ga["product_price_order"])
    sv, bv = float(ga["seller_value"]), float(ga["buyer_value"])
    last_price = None
    outcome, final_price, n_rounds = "no_agreement", None, 0
    for r in rows:
        rnd = int(r["round"]) if r.get("round") else n_rounds
        n_rounds = max(n_rounds, rnd)
        price_raw = r.get("product_price")
        if price_raw not in (None, "", "None"):
            last_price = (float(price_raw), r["player"], rnd)
        dec = (r.get("decision") or "").strip()
        if dec and dec.lower() != "none" and last_price is not None:
            decider = r["player"]
            role = "seller" if decider == "Alice" else "buyer"
            NEGO_DEC.append(dict(
                game_id=gid, source=src, decider=decider, role=role,
                decider_model=(cfg["player_1_args"]["model_name"] if decider == "Alice"
                               else cfg["player_2_args"]["model_name"]),
                round=rnd, price_frac=last_price[0] / M,
                own_value=(sv if role == "seller" else bv),
                other_value_hidden=not ga.get("complete_information", True),
                decision=dec, M=M, max_rounds=ga.get("max_rounds"),
                messages_allowed=ga.get("messages_allowed"),
            ))
            if dec == "AcceptOffer":
                outcome, final_price = "agreement", last_price[0]
            elif dec == "WalkAway":
                outcome = "walkaway"
    s_pay = (final_price - sv * M) if final_price is not None else 0.0
    b_pay = (bv * M - final_price) if final_price is not None else 0.0
    GAMES.append(dict(
        game_id=gid, source=src, family="negotiation",
        p1_model=cfg["player_1_args"]["model_name"],
        p2_model=cfg["player_2_args"]["model_name"],
        M=M, seller_value=sv, buyer_value=bv,
        max_rounds=ga.get("max_rounds"),
        complete_information=ga.get("complete_information"),
        messages_allowed=ga.get("messages_allowed"),
        n_rounds=n_rounds, outcome=outcome,
        final_price_frac=(final_price / M if final_price is not None else None),
        p1_payoff=s_pay, p2_payoff=b_pay,
    ))


def parse_persuasion(gid, src, cfg, rows):
    ga = cfg["game_args"]
    price = float(ga["product_price"])
    quality = worth = None
    seller_msg = seller_rec = None
    rnd = 0
    s_pay = b_pay = 0.0
    n_high = n_low = sold_high = sold_low = 0
    per_round = []
    for r in rows:
        player = r.get("player")
        if player == "Nature":
            quality = r.get("round_quality")
            worth = float(r["product_worth"]) if r.get("product_worth") not in (None, "", "None") else 0.0
            rnd = int(r["round"])
            seller_msg = seller_rec = None
        elif player == "Alice":
            msg = r.get("message")
            dec = (r.get("decision") or "").strip().lower()
            if msg not in (None, "", "None"):
                seller_msg = msg
            if dec and dec != "none":
                seller_rec = dec
        elif player == "Bob":
            dec = (r.get("decision") or "").strip().lower()
            bought = dec == "yes"
            hi = quality == "high-quality"
            if hi:
                n_high += 1
                sold_high += bought
            else:
                n_low += 1
                sold_low += bought
            if bought:
                s_pay += price
                b_pay += worth - price
            per_round.append(dict(
                game_id=gid, source=src, round=rnd,
                quality=("high" if hi else "low"),
                seller_rec=seller_rec,
                seller_msg_len=(len(seller_msg) if seller_msg else 0),
                bought=bought,
                seller_model=cfg["player_1_args"]["model_name"],
                buyer_model=cfg["player_2_args"]["model_name"],
                p=float(ga["p"]), v=float(ga["v"]), price=price,
                total_rounds=ga.get("total_rounds"),
                msg_type=ga.get("seller_message_type"),
                is_myopic=ga.get("is_myopic"),
            ))
    PERS_ROUNDS.extend(per_round)
    GAMES.append(dict(
        game_id=gid, source=src, family="persuasion",
        p1_model=cfg["player_1_args"]["model_name"],
        p2_model=cfg["player_2_args"]["model_name"],
        p=float(ga["p"]), v=float(ga["v"]), c=float(ga.get("c", 0.0)),
        price=price, total_rounds=ga.get("total_rounds"),
        is_seller_know_cv=ga.get("is_seller_know_cv"),
        msg_type=ga.get("seller_message_type"), is_myopic=ga.get("is_myopic"),
        n_rounds=len(per_round), n_high=n_high, n_low=n_low,
        sold_high=sold_high, sold_low=sold_low,
        p1_payoff=s_pay, p2_payoff=b_pay,
    ))


PARSERS = {"bargaining": parse_bargaining, "negotiation": parse_negotiation,
           "persuasion": parse_persuasion}


def main(tar_path):
    t0 = time.time()
    pending = {}
    n = 0
    with tarfile.open(tar_path, "r:gz") as tar:
        for m in tar:
            if not m.isfile() or "/Data/" not in m.name:
                continue
            parts = m.name.split("/")
            try:
                src, fam, gid, fname = parts[2], parts[3], parts[-2], parts[-1]
            except IndexError:
                SKIPPED["bad_path"] += 1
                continue
            if fam not in PARSERS:
                SKIPPED["bad_family"] += 1
                continue
            key = (src, fam, gid)
            slot = pending.setdefault(key, {})
            try:
                raw = tar.extractfile(m).read()
                if fname == "config.json":
                    slot["config"] = json.loads(raw)
                elif fname == "game.csv":
                    slot["rows"] = list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
            except Exception:
                SKIPPED[f"unreadable_{fname}"] += 1
                pending.pop(key, None)
                continue
            if "config" in slot and "rows" in slot:
                pending.pop(key)
                try:
                    PARSERS[fam](gid, src, slot["config"], slot["rows"])
                    n += 1
                    if n % 20000 == 0:
                        print(f"{n} games parsed, {time.time()-t0:.0f}s", flush=True)
                except Exception:
                    SKIPPED[f"parse_error_{fam}"] += 1
    print(f"done: {n} games in {time.time()-t0:.0f}s; leftovers {len(pending)}; skipped {dict(SKIPPED)}")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    pd.DataFrame(GAMES).to_parquet(f"{out}/games.parquet", index=False)
    pd.DataFrame(BARG_DEC).to_parquet(f"{out}/bargaining_decisions.parquet", index=False)
    pd.DataFrame(NEGO_DEC).to_parquet(f"{out}/negotiation_decisions.parquet", index=False)
    pd.DataFrame(PERS_ROUNDS).to_parquet(f"{out}/persuasion_rounds.parquet", index=False)
    df = pd.DataFrame(GAMES)
    print(df.groupby(["source", "family"]).size())


if __name__ == "__main__":
    main(sys.argv[1])
