"""Experiment assignment from the server's game id."""

import hashlib


def gid_int(game_id: str) -> int:
    """First 32 bits of md5(game_id); unlike hash(), the same in every process."""
    return int(hashlib.md5(game_id.encode("utf-8")).hexdigest()[:8], 16)
