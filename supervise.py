"""Restart the agent process whenever it exits."""

import argparse
import datetime
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from glee_agent.profiles import PROFILES  # noqa: E402
from glee_agent.single_instance import acquire  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = ap.parse_args()

    logdir = os.path.join(ROOT, "logs")
    os.makedirs(logdir, exist_ok=True)
    slog = os.path.join(logdir, f"supervisor_{args.profile}.log")
    backoff = 60.0

    def note(msg):
        line = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
        print(line, flush=True)
        with open(slog, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    if not acquire(f"supervisor-{args.profile}"):
        note("another supervisor holds the lock for this profile; exiting")
        return 2
    note(f"supervisor start (pid {os.getpid()})")
    while True:
        start = time.time()
        note(f"launching run_agent --profile {args.profile}")
        proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run_agent.py"),
                                 "--profile", args.profile])
        rc = proc.wait()
        ran = time.time() - start
        note(f"run_agent exited rc={rc} after {ran:.0f}s")
        if rc == 0:
            note("agent exited cleanly; supervisor done")
            return 0
        if rc == 3:
            note("agent lock held elsewhere; retrying in 120s")
            time.sleep(120)
            continue
        if rc == 10:
            note("scheduled restart; relaunching")
            backoff = 60.0
            continue
        if rc == 99:
            note("logs/STOP present; supervisor done")
            return 0
        backoff = 60.0 if ran > 600 else min(backoff * 2, 900.0)
        note(f"restarting in {backoff:.0f}s")
        time.sleep(backoff)


if __name__ == "__main__":
    raise SystemExit(main())
