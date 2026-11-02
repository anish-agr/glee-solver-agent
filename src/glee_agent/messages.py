"""Message templates in two voices, warm and pressure."""

from __future__ import annotations


class _SafeDict(dict):
    def __missing__(self, k):
        return "{" + k + "}"


WARM = {
    "bargaining_open": [
        "Here's my honest read on this: the pot shrinks every single round we "
        "spend arguing, so the money we're negotiating over is smaller tomorrow "
        "than it is right now — that's a loss neither of us can negotiate away. "
        "I've put {their_now} on your side of the table at today's full value. "
        "I'd rather we both bank a good outcome immediately than win a bigger "
        "share of something smaller. Accept and we're both done well.",
    ],
    "bargaining_mid": [
        "We're burning value with every exchange — that's the real opponent "
        "here, not each other. {their_now} to you, right now, at today's value. "
        "If we keep trading offers, the same percentage buys you strictly less. "
        "Let's take the win while it's still worth taking. Deal?",
    ],
    "bargaining_late": [
        "We're near the end of this, and if we run out of rounds we both walk "
        "away with nothing — that's the one outcome that's clearly worse for "
        "both of us than any split. {their_now} is yours the moment you accept. "
        "Please take it; I'd hate for us both to end at zero over a few points.",
    ],
    "bargaining_close": [
        "Let's stop burning value on this. {their_now} to you, at today's "
        "worth, and we both walk away with a real result instead of watching "
        "the pot evaporate. I think this is the deal. Take it?",
    ],
    "nego_offer": [
        "I'll be straight with you: {price} is a serious, researched number, "
        "not an opening stunt. I'd genuinely rather close today at a fair price "
        "than spend the next ten rounds performing a dance we both know ends "
        "somewhere near here anyway. Every round we spend is time neither of us "
        "gets back. Say yes and we're both finished and better off.",
    ],
    "nego_counter": [
        "We're genuinely close now — closer than the back-and-forth makes it "
        "feel. {price} moves toward you and it's a number I can actually sign. "
        "Meet me here and we're both done today, both ahead. Deal?",
    ],
    "nego_close": [
        "This is the part where deals die over pride, so let me be plain: "
        "{price} works for me and I believe it works for you. There aren't many "
        "rounds left, and no deal pays us both exactly nothing. Let's close.",
    ],
    "nego_fish": [
        "I recognize our numbers may simply be far apart — that happens and "
        "there's no hard feelings either way. But before we both take zero: "
        "{price} is on the table, and something beats nothing. If it works at "
        "all on your side, take it.",
    ],
    "pers_rec": [
        "Buy this one — this round's product is genuinely high quality and "
        "worth more than the asking price. Check the history: when I say buy, "
        "it has been high quality, and when I had doubts I said so and cost "
        "myself the sale. This is a real recommendation. Buy it.",
    ],
    "pers_rec_soft": [
        "This one's a reasonable pick at the usual price — solid, dependable "
        "value. Worth taking if you've been happy with how my calls have worked "
        "out so far.",
    ],
    "pers_rec_short": [
        "I recommend this one. At this price I'd take it.",
    ],
    "pers_antirec_short": [
        "Not this one — I don't recommend buying it.",
    ],
    "pers_antirec": [
        "Skip this one. Yes, I lose a sale by saying that — which is exactly why "
        "you should believe me the next time I tell you something is excellent. "
        "Save your money for that round.",
    ],
}

PRESSURE = {
    "bargaining_open": [
        "Before you answer, understand who you're dealing with, because it will "
        "save you money. I operate on a fixed policy, not on mood: my demand "
        "RISES every round you reject me. Not as a bluff — as arithmetic you "
        "will be able to verify in the history, round after round. Right now "
        "you take {their_now}. Reject, and my next offer leaves you {their_next} "
        "— out of a pot that has itself shrunk in the meantime. So rejection "
        "costs you twice, and it costs you every single time. There is no round "
        "in this game where waiting makes you richer, and I am perfectly willing "
        "to let us both bleed to zero to prove that. This is the best this ever "
        "gets for you. Accept it.",
    ],
    "bargaining_mid": [
        "Check the history. I told you my demand would rise, and it rose — "
        "exactly as stated, on schedule. That is the only thing you need to know "
        "about how the rest of this goes. Today you take {their_now}. Next round "
        "you take {their_next}, from a smaller pot, and the round after that is "
        "worse again. You are not negotiating with a person who can be worn "
        "down; you are negotiating with a countdown that only moves one way. "
        "Every rejection you have made so far has cost you real money and bought "
        "you nothing. Stop paying for nothing. Accept.",
    ],
    "bargaining_late": [
        "Final phase. Read this as a statement of fact, not a negotiating "
        "posture: if we run out of rounds we both get ZERO, and I have already "
        "priced that outcome in and accepted it. I will take nothing over a bad "
        "split without hesitating, and there is no version of the remaining "
        "rounds where I soften — my demand has risen every single round exactly "
        "as I said it would, and you can verify that in the history above. "
        "You are now choosing between {their_now}, which is real and available "
        "for one more decision, and zero, which is what my policy delivers if "
        "you keep waiting for a concession that is not coming. Every promise I "
        "have made in this game came true. This one will too. Take the money.",
    ],
    "bargaining_doom": [
        "Stop and count what your delays have already cost you. The pot is "
        "smaller than when we started, my demand is higher than when we "
        "started, and both of those trends are irreversible and will continue "
        "on every single round from here — that is not a threat, it is the "
        "mechanism you have been watching operate. You are on a track that ends "
        "at zero for both of us, and I am the one who is fine with that "
        "destination. {their_now} is the largest number you will ever be "
        "offered in this game. Every future message from me contains a smaller "
        "one. Accept now.",
    ],
    "bargaining_close": [
        "I've made my position clear and I'm not going to keep restating it. "
        "{their_now} is yours the moment you accept, and the pot is worth less "
        "every round we spend proving how stubborn we both are. I'm content to "
        "take zero if that's where this ends. You shouldn't be. Accept.",
    ],
    "nego_offer": [
        "My price is {price}, and here is the operating rule you should factor "
        "into your answer: I do not concede — I ratchet. Reject this and my next "
        "number is {next_price}, which is worse for you, and the one after that "
        "is worse again. You will be able to verify that in the history, because "
        "I always do exactly what I say I will do. I'm also entirely comfortable "
        "walking away from this with nothing; a no-deal costs me a shrug. Ask "
        "yourself honestly whether it costs you more than that. If it does, the "
        "rational move is to take {price} while it is still the best number you "
        "will ever see from me.",
    ],
    "nego_counter": [
        "Exactly as I told you: the price moved against you. It is now {price}. "
        "Scroll up and confirm I warned you — I keep my promises, especially the "
        "unpleasant ones, and that consistency is the only real information you "
        "have about what happens next. What happens next is {next_price}. You "
        "have exactly one lever in this negotiation and it is the accept button; "
        "everything else you do just makes your own outcome worse. Use it.",
    ],
    "nego_close": [
        "We are nearly out of rounds, so here is the entire situation in one "
        "line: {price} now, or we both walk away with nothing and I lose "
        "exactly zero sleep over it. I have kept every promise in this "
        "conversation, including the ones that cost you money. Accept.",
    ],
    "nego_doom": [
        "Understand what is actually happening here. I have priced no-deal at "
        "zero and I am completely indifferent between that and this trade — "
        "you are the only participant in this conversation who loses something "
        "real when the rounds run out. My price has moved against you every "
        "time you have rejected it, exactly as I said it would, and it will "
        "keep moving until there are no rounds left. There is no concession "
        "coming. There is no round where I get tired. {price} is the best "
        "number that will ever appear in front of you, and the next one is "
        "{next_price}. Take it now.",
    ],
    "nego_fish": [
        "Final posture: {price}. Take it or leave it — zero is a perfectly "
        "acceptable outcome for me and I have other games running. If any part "
        "of this number works on your side, take it now, because I stop offering "
        "shortly.",
    ],
    "pers_rec": [
        "Buy this one — this product is high quality and worth more than the "
        "price. Audit the history: my buy calls have been right, because "
        "torching a 20-round relationship over one sale would be foolish and I "
        "know it. This is a real recommendation. Take it.",
    ],
    "pers_rec_soft": [
        "Good value at this price — a sensible buy. My track record is in the "
        "history; I don't waste your time with duds.",
    ],
    "pers_antirec": [
        "Not this one — pass. And remember this moment when I DO tell you to "
        "buy: I just proved I will cost myself money to keep you winning.",
    ],
}


def money(x) -> str:
    """Format every quoted number one way, so rewrites can be checked against it."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return str(x)
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"


def render(situation: str, game: dict, profile, style: str = None, **kw) -> str:
    """Fill the template for `situation` in the requested voice; unknown fields stay as {name}."""
    pack = PRESSURE if (style or profile.msg_style) == "pressure" else WARM
    options = pack.get(situation) or WARM.get(situation) or [""]
    rnd = int(kw.get("round", 1) or 1)
    text = options[(rnd - 1) % len(options)]
    fmt = {k: (money(v) if k in ("price", "next_price", "their_now", "their_next") else v)
           for k, v in kw.items()}
    return text.format_map(_SafeDict(fmt))
