"""Routes each game to its engine and validates the returned action."""

from __future__ import annotations

import logging
import threading
import time

from .assignment import gid_int
from .curves import CurveStore
from .profiles import Profile
from .engines import bargaining, negotiation, persuasion
from . import messages

logger = logging.getLogger("glee_agent")


class Context:
    """Per-process services shared by the engines."""

    def __init__(self, curves: CurveStore, profile: Profile, llm=None):
        self.curves = curves
        self.profile = profile
        self.llm = llm
        self._memory: dict[str, dict] = {}
        self._lock = threading.Lock()

    def memory(self, game_id: str) -> dict:
        with self._lock:
            return self._memory.setdefault(game_id, {})

    @staticmethod
    def opponent_info(game: dict) -> dict:
        """The server's opponent disclosure, or a hidden placeholder."""
        opp = game.get("opponent")
        if isinstance(opp, dict) and opp.get("type") not in (None, "hidden"):
            return opp
        return {"type": "hidden", "name": None}

    def opponent_is_human(self, game: dict) -> bool:
        """True only when the server discloses a human opponent."""
        return self.opponent_info(game)["type"] == "human"

    def maybe_human_for_tone(self, game: dict) -> bool:
        """Looser human test, used only to choose message tone."""
        if self.opponent_info(game)["type"] == "human":
            return True
        if self.opponent_info(game)["type"] == "agent":
            return False
        state = game.get("game_state") or {}
        times, texts = [], []
        for h in state.get("history", []):
            t = h.get("response_time_ms")
            if isinstance(t, (int, float)) and t > 0:
                times.append(float(t))
            m = ((h.get("offer") or {}).get("message")
                 if isinstance(h.get("offer"), dict) else h.get("message"))
            if isinstance(m, str) and m and m.lower() != "none":
                texts.append(m)
        if times:
            if max(times) > 45000 or (sum(times) / len(times)) > 15000:
                return True
            if max(times) < 12000:
                return False
        if texts:
            short = sum(1 for t in texts if len(t) < 25)
            if short / len(texts) > 0.6:
                return True
        return False

    def classify_seller_signal(self, h: dict) -> bool:
        """True if the seller's message or recommendation says buy."""
        m = h.get("seller_message")
        if m in ("yes", True):
            return True
        if m in ("no", False, None):
            return False
        if isinstance(m, str):
            ml = m.lower()
            for k in ("solid to me", "to put it in front of you",
                      "in my view"):
                if k in ml:
                    return False
            pos = ("worth buying", "worth your money", "i recommend",
                   "recommend this", "strong recommendation", "i'd take it",
                   "genuinely good", "high quality this round",
                   "worth the price", "buy this one", "worth taking")
            negators = ("do not ", "don't ", "cannot ", "can't ", "won't ",
                        "wouldn't ", "not ", "never ", "hardly ", "no ")
            for k in pos:
                i = ml.find(k)
                while i >= 0:
                    head = ml[max(0, i - 14):i]
                    if not any(head.endswith(x) for x in negators):
                        return True
                    i = ml.find(k, i + 1)
            neg = (" skip this", "skip this one", " pass on", "not this one",
                   "don't recommend", "do not recommend", "wouldn't", "avoid",
                   "low quality", "no recommendation", "i'd pass", "i would pass",
                   "cannot honestly", "ordinary unit", "i'd hold", "i'd understand",
                   "be straight with you", "nothing special", "isn't up to")
            return not any(k in ml for k in neg)
        return False

    def render_message(self, situation: str, game: dict, profile: Profile, **kw) -> str:
        style = profile.msg_style
        if style == "pressure" and self.maybe_human_for_tone(game):
            style = "warm"
        if game.get("game_family") == "persuasion":
            style = "warm"
        if game.get("game_family") == "negotiation" and profile.nego_warm_voice:
            style = "warm"
        draft = messages.render(situation, game, profile, style=style, **kw)[:1990]
        if self.llm is None or game.get("game_family") == "persuasion":
            return draft
        if profile.llm_rewrite_ab and (
                gid_int(game.get("game_id", "")) >> 10) % 2 == 0:
            return draft
        st = game.get("game_state", {})
        facts = {"game": game.get("game_family"), "round": st.get("round"),
                 "max rounds": st.get("max_rounds") or "no limit",
                 "goal of this message": situation}
        if game.get("game_family") == "bargaining":
            facts["the pot"] = messages.money(st.get("money_to_divide"))
            facts["the pot shrinks every round"] = "yes"
        protected = []
        for label, field in (("what they get if they accept now", "their_now"),
                             ("what they get after their next rejection", "their_next"),
                             ("price", "price"),
                             ("my next price if they reject", "next_price")):
            if kw.get(field) is not None:
                facts[label] = messages.money(kw[field])
                protected.append(facts[label])
        if kw.get("rounds_left") is not None:
            facts["rounds remaining"] = kw["rounds_left"]
        return self.llm.rewrite(draft, facts, style,
                                must_keep=tuple(protected))[:1990]


ENGINES = {"bargaining": bargaining.act, "negotiation": negotiation.act,
           "persuasion": persuasion.act}


def safe_action(game: dict) -> dict:
    """Conservative move used when the engine fails or was already rejected."""
    family = game["game_family"]
    action_type = game["valid_actions"]["type"]
    state = game["game_state"]
    me = 1 if game.get("your_player") == "player_1" else 2

    if action_type == "offer":
        if family == "bargaining":
            money = float(state["money_to_divide"])
            half = round(money / 2, 2)
            return {"alice_gain": half, "bob_gain": round(money - half, 2)}
        return {"product_price": float(state[f"player_{me}_value"])}
    if action_type == "seller_message":
        return {"message": "This product is available at the usual price."}
    if action_type == "seller_recommendation":
        return {"decision": "yes"}

    if family == "bargaining":
        gain = float((state.get("last_offer") or {}).get(f"player_{me}_gain", 0.0) or 0.0)
        return {"decision": "accept" if gain > 0 else "reject"}
    if family == "negotiation":
        my_value = float(state[f"player_{me}_value"])
        price = float((state.get("last_offer") or {})["price"])
        good = price >= my_value if state[f"player_{me}_role"] == "seller" else price <= my_value
        if good:
            return {"decision": "AcceptOffer"}
        T, rnd = state.get("max_rounds"), int(state.get("round", 1))
        if T and rnd >= int(T):
            return {"decision": "RejectOffer"}
        return {"decision": "RejectOffer", "product_price": my_value}
    return {"decision": "no"}


def last_resort(game: dict) -> dict:
    """A legally shaped action that tolerates missing or malformed state fields."""
    at = (game.get("valid_actions") or {}).get("type")
    family = game.get("game_family")
    state = game.get("game_state") or {}
    if at == "offer":
        if family == "bargaining":
            try:
                money = float(state.get("money_to_divide") or 0.0)
            except (TypeError, ValueError):
                money = 0.0
            half = round(money / 2, 2)
            return {"alice_gain": half, "bob_gain": round(money - half, 2)}
        me = 1 if game.get("your_player") == "player_1" else 2
        try:
            price = float(state.get(f"player_{me}_value") or 0.0)
        except (TypeError, ValueError):
            price = 0.0
        return {"product_price": price}
    if at == "seller_message":
        return {"message": "This product is available at the usual price."}
    if at == "seller_recommendation":
        return {"decision": "yes"}
    if family == "bargaining":
        return {"decision": "accept"}
    if family == "negotiation":
        return {"decision": "AcceptOffer"}
    return {"decision": "no"}


def _decision_fingerprint(game: dict) -> tuple:
    st = game["game_state"]
    return (game["game_id"], st.get("round"), game.get("phase"),
            str(st.get("last_offer")), str(st.get("seller_message")))


def _validate(game: dict, action: dict) -> dict:
    """Round and trim an action to the server's format before it is sent."""
    state = game["game_state"]
    at = game["valid_actions"]["type"]
    if at == "offer" and game["game_family"] == "bargaining":
        money = float(state["money_to_divide"])
        a = round(float(action["alice_gain"]), 2)
        action["alice_gain"], action["bob_gain"] = a, round(money - a, 2)
    if "message" in action:
        if not state.get("messages_allowed", True) and game["game_family"] != "persuasion":
            action.pop("message")
        elif isinstance(action.get("message"), str):
            action["message"] = action["message"][:1990]
    if at == "offer" and game["game_family"] == "negotiation":
        action["product_price"] = round(float(action["product_price"]), 2)
    return action


def make_strategy(profile: Profile, curves: CurveStore | None = None, gamelog=None, llm=None):
    ctx = Context(curves or CurveStore(), profile, llm=llm)
    seen: dict[tuple, int] = {}

    def strategy(game: dict) -> dict:
        t0 = time.monotonic()
        try:
            fp = _decision_fingerprint(game)
            attempt = seen.get(fp, 0)
            seen[fp] = attempt + 1
            if len(seen) > 20000:
                seen.clear()
        except Exception:
            attempt = 0
        try:
            if attempt >= 1:
                logger.warning("repeat decision point %s (attempt %d) -> safe action",
                               game.get("game_id", "?")[:8], attempt)
                return _validate(game, safe_action(game))
            action = ENGINES[game["game_family"]](game, profile, ctx)
            action = _validate(game, action)
            logger.info("%s %s r%s [%s] -> %s (%.0fms)",
                        game["game_family"], game["game_id"][:8],
                        game["game_state"].get("round"), profile.name, action,
                        1000 * (time.monotonic() - t0))
            if gamelog is not None:
                try:
                    gamelog.log_move(game, action)
                except Exception:
                    logger.exception("gamelog failure (non-fatal)")
            return action
        except Exception:
            logger.exception("engine error in %s %s -> safe action",
                             game.get("game_family"), str(game.get("game_id"))[:8])
        try:
            return _validate(game, safe_action(game))
        except Exception:
            logger.exception("safe_action failed -> last resort")
        try:
            return last_resort(game)
        except Exception:
            logger.exception("last_resort failed -> accept")
            return {"decision": "accept"}

    strategy.ctx = ctx
    return strategy
