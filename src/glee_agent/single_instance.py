"""Single-instance locks, so only one process runs per agent profile."""

from __future__ import annotations

import socket

_PROFILES = ("optima", "leviathan", "prospector", "velocity", "citadel")
_PORTS = {**{f"supervisor-{p}": 47761 + i for i, p in enumerate(_PROFILES)},
          **{f"agent-{p}": 47771 + i for i, p in enumerate(_PROFILES)}}
_held: list[socket.socket] = []  # keeps lock sockets open for the process lifetime


def acquire(name: str) -> bool:
    """Bind a loopback port as a lock; False if another process holds it."""
    port = _PORTS.get(name, 47790 + (sum(map(ord, name)) % 9))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
    except OSError:
        s.close()
        return False
    _held.append(s)
    return True
