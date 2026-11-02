"""SQLite logging of every move and result."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS moves (
    ts REAL, game_id TEXT, family TEXT, round INTEGER, phase TEXT,
    action TEXT, state TEXT
);
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY, family TEXT, first_seen REAL, last_seen REAL,
    done INTEGER DEFAULT 0, status TEXT, result TEXT, final_state TEXT,
    reap_fails INTEGER DEFAULT 0, opponent TEXT
);
CREATE INDEX IF NOT EXISTS idx_moves_game ON moves(game_id);
"""


class GameLog:
    def __init__(self, profile_name: str, root: Path | None = None):
        root = root or Path(__file__).resolve().parents[2] / "logs"
        root.mkdir(exist_ok=True)
        self._db = sqlite3.connect(str(root / f"games_{profile_name}.sqlite"),
                                   check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    def log_move(self, game: dict, action: dict) -> None:
        st = game.get("game_state", {})
        slim = {k: v for k, v in st.items() if k != "history"}
        now = time.time()
        with self._lock:
            self._db.execute(
                "INSERT INTO moves VALUES (?,?,?,?,?,?,?)",
                (now, game["game_id"], game["game_family"],
                 st.get("round"), game.get("phase"),
                 json.dumps(action), json.dumps(slim, default=str)))
            opp = game.get("opponent")
            opp_j = (json.dumps(opp) if isinstance(opp, dict)
                     and opp.get("type") not in (None, "hidden") else None)
            self._db.execute(
                "INSERT INTO games (game_id, family, first_seen, last_seen, opponent) "
                "VALUES (?,?,?,?,?) ON CONFLICT(game_id) DO UPDATE SET last_seen=?, "
                "opponent=COALESCE(opponent, ?)",
                (game["game_id"], game["game_family"], now, now, opp_j, now, opp_j))
            self._db.commit()

    def unresolved(self, idle_seconds: float = 240.0, limit: int = 3,
                   max_fails: int = 5) -> list[str]:
        """Games we moved in but never saw finish, oldest first."""
        cutoff = time.time() - idle_seconds
        with self._lock:
            rows = self._db.execute(
                "SELECT game_id FROM games WHERE done=0 AND last_seen<? AND reap_fails<? "
                "ORDER BY last_seen LIMIT ?", (cutoff, max_fails, limit)).fetchall()
        return [r[0] for r in rows]

    def note_reap_failure(self, game_id: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE games SET reap_fails=reap_fails+1, last_seen=? WHERE game_id=?",
                (time.time(), game_id))
            self._db.commit()

    def resolve(self, game_id: str, status: str, result, final_state) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE games SET done=1, status=?, result=?, final_state=? "
                "WHERE game_id=?",
                (status, json.dumps(result, default=str),
                 json.dumps(final_state, default=str), game_id))
            self._db.commit()

    def touch(self, game_id: str) -> None:
        with self._lock:
            self._db.execute("UPDATE games SET last_seen=? WHERE game_id=?",
                             (time.time(), game_id))
            self._db.commit()
