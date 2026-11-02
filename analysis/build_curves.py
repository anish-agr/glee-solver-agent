"""Build percentile reference curves from the GLEE dataset."""

import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
g = pd.read_parquet(os.path.join(ROOT, "data", "games.parquet"))
rows = []


def emit(df, family, keycols, roles):
    for keyvals, sub in df.groupby(keycols, dropna=False):
        key = "|".join(f"{k}={v}" for k, v in zip(keycols, keyvals, strict=True))
        for role, col in roles.items():
            for x in sub[col].values:
                rows.append((family, key, role, float(x)))


b = g[g.family == "bargaining"]
emit(b, "bargaining",
     ["money", "max_rounds", "delta_1", "delta_2", "complete_information", "messages_allowed"],
     {"alice": "p1_payoff", "bob": "p2_payoff"})

n = g[g.family == "negotiation"]
emit(n, "negotiation",
     ["M", "seller_value", "buyer_value", "max_rounds", "complete_information", "messages_allowed"],
     {"seller": "p1_payoff", "buyer": "p2_payoff"})

p = g[g.family == "persuasion"]
emit(p, "persuasion",
     ["p", "v", "price", "total_rounds", "is_seller_know_cv", "msg_type", "is_myopic"],
     {"seller": "p1_payoff", "buyer": "p2_payoff"})

df = pd.DataFrame(rows, columns=["family", "key", "role", "payoff"])
df.to_parquet(os.path.join(ROOT, "data", "curves.parquet"), index=False)
print(df.groupby("family").agg(cells=("key", "nunique"), obs=("payoff", "size")))
