"""Percentile reference curves built from the GLEE research dataset."""

from __future__ import annotations

import bisect
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "curves.parquet"


def _fmt(v) -> str:
    """Format values the way build_curves.py wrote them."""
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, str):
        return v
    try:
        return str(float(v))
    except (TypeError, ValueError):
        return str(v)


def key_of(**fields) -> str:
    return "|".join(f"{k}={_fmt(v)}" for k, v in fields.items())


class CurveStore:
    def __init__(self, path: Path = DATA):
        df = pd.read_parquet(path)
        self._cells: dict[tuple[str, str, str], np.ndarray] = {}
        for (fam, key, role), sub in df.groupby(["family", "key", "role"]):
            self._cells[(fam, key, role)] = np.sort(sub["payoff"].values)

    def percentile(self, family: str, key: str, role: str, payoff: float) -> float | None:
        """Midrank percentile of `payoff` in the cell's pool; None if no cell."""
        arr = self._cells.get((family, key, role))
        if arr is None or len(arr) == 0:
            return None
        lo = bisect.bisect_left(arr, payoff)
        hi = bisect.bisect_right(arr, payoff)
        return (lo + 0.5 * (hi - lo)) / len(arr)

    def has_data(self, family: str, keys_weights: list[tuple[str, float]], role: str) -> bool:
        """True if any candidate config cell is populated."""
        return any(w > 0 and (family, key, role) in self._cells
                   for key, w in keys_weights)

    def percentile_mix(self, family: str, keys_weights: list[tuple[str, float]],
                       role: str, payoff: float, default: float = 0.5) -> float:
        """Posterior-averaged percentile over candidate config cells."""
        total_w = num = 0.0
        for key, w in keys_weights:
            if w <= 0:
                continue
            p = self.percentile(family, key, role, payoff)
            num += w * (default if p is None else p)
            total_w += w
        return num / total_w if total_w else default
