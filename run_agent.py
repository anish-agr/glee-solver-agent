"""Run a GLEE competition agent."""

import argparse
import datetime
import logging
import os
import sys
import threading

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import re  # noqa: E402

from glee_sdk import (GleeClient, CompetitionClosedError,  # noqa: E402
                      CompetitionNotOpenError, GleeAPIError)

from glee_agent.dispatcher import make_strategy
from glee_agent.gamelog import GameLog
from glee_agent.llm import MessageLLM
from glee_agent.overrides import apply_overrides
from glee_agent.profiles import PROFILES

logger = logging.getLogger("run_agent")


def load_dotenv() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def start_reaper(client: GleeClient, gamelog: GameLog, stop: threading.Event) -> threading.Thread:
    """Fetch final results for games we moved in but never saw finish."""
    def loop():
        while not stop.wait(90.0):
            try:
                backlog = gamelog.unresolved(idle_seconds=240.0, limit=1000)
                lim = 12 if len(backlog) > 150 else 6
                batch = backlog[:lim]
            except Exception as e:
                logger.warning("reaper batch query failed: %s (continuing)", e)
                continue
            for gid in batch:
                try:
                    g = client.game_state(gid)
                    status = g.get("status")
                    if status in ("completed", "no_deal"):
                        gamelog.resolve(gid, status, g.get("result"), g)
                        logger.info("reaped %s: %s %s", gid[:8], status, g.get("result"))
                    else:
                        gamelog.touch(gid)
                except Exception as e:
                    try:
                        gamelog.note_reap_failure(gid)
                    except Exception:
                        pass
                    logger.warning("reaper %s: %s (continuing)", gid[:8], e)
    t = threading.Thread(target=loop, daemon=True, name="reaper")
    t.start()
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=sorted(PROFILES), required=True)
    ap.add_argument("--families", nargs="*", default=None)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--poll-interval", type=float, default=5.0)
    ap.add_argument("--max-time", type=float, default=None)
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--recycle-seconds", type=float, default=1200.0)
    args = ap.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(root, "logs"), exist_ok=True)
    stop_flag = os.path.join(root, "logs", "STOP")
    if os.path.exists(stop_flag):
        print("logs/STOP present; not starting")
        return 99
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname).1s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs",
                             f"agent_{args.profile}.log"), encoding="utf-8"),
        ])
    from glee_agent.single_instance import acquire
    if not acquire(f"agent-{args.profile}"):
        logger.error("another %s agent holds the lock; exiting", args.profile)
        return 3

    load_dotenv()
    key = os.environ.get(f"GLEE_API_KEY_{args.profile.upper()}") or os.environ.get("GLEE_API_KEY", "")
    if not key:
        print(f"Set GLEE_API_KEY_{args.profile.upper()} in the environment or .env")
        return 1

    client = GleeClient(api_key=key)
    try:
        logger.info("agent stats: %s", client.stats())
    except Exception as e:
        logger.warning("could not read stats at startup (%s); continuing", e)

    gamelog = GameLog(args.profile)
    gem_key = os.environ.get(f"GEMINI_API_KEY_{args.profile.upper()}")
    llm = MessageLLM(gem_key, model=os.environ.get("LLM_MODEL", "gemini-flash-latest"))
    if gem_key:
        logger.info("LLM message layer active (%s)", llm.model)
    strategy = make_strategy(apply_overrides(PROFILES[args.profile]),
                             gamelog=gamelog, llm=llm)
    stop = threading.Event()
    start_reaper(client, gamelog, stop)

    run_max_time = args.max_time if args.max_time is not None else args.recycle_seconds
    try:
        while True:
            try:
                client.run(strategy,
                           game_families=args.families or None,
                           concurrency=args.concurrency,
                           poll_interval=args.poll_interval,
                           max_time=run_max_time,
                           max_games=args.max_games)
                if args.max_time is None and args.max_games is None:
                    if os.path.exists(stop_flag):
                        logger.info("logs/STOP present; stopping")
                        return 99
                    logger.info("recycle interval reached; exiting for restart")
                    return 10
                return 0
            except CompetitionClosedError:
                logger.info("competition closed; exiting")
                return 0
            except CompetitionNotOpenError as e:
                open_at = e.competition_open_at
                wait = 300.0
                if open_at:
                    try:
                        dt = datetime.datetime.fromisoformat(
                            open_at.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        wait = max((dt - datetime.datetime.now(datetime.timezone.utc))
                                   .total_seconds() + 5, 10.0)
                    except (ValueError, TypeError, AttributeError) as parse_err:
                        logger.warning("could not parse open time %r (%s)",
                                       open_at, parse_err)
                wait = min(wait, 900)
                logger.info("competition not open (opens %s); sleeping %.0fs",
                            open_at, wait)
                if stop.wait(wait):
                    return 0
            except GleeAPIError as e:
                if e.code == "agent_cooldown" or "timed out on its turn" in (e.message or ""):
                    m = re.search(r"(20\d\d-\d\d-\d\dT[\d:.]+)", e.message or "")
                    wait = 300.0
                    if m:
                        try:
                            until = datetime.datetime.fromisoformat(
                                m.group(1).rstrip(".") + "+00:00")
                            wait = max((until - datetime.datetime.now(datetime.timezone.utc))
                                       .total_seconds() + 15, 30.0)
                        except ValueError:
                            pass
                    logger.warning("agent cooldown; sleeping %.0fs", min(wait, 2100))
                    if stop.wait(min(wait, 2100)):
                        return 0
                    continue
                raise
    finally:
        stop.set()


if __name__ == "__main__":
    raise SystemExit(main())
