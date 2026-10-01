"""Feature logic for PawsConnect, independent of the UI.

Each feature stores the RAW model output in the cache and runs the same
post-processing (validation, review flags, voting, grounding checks) on both
the live and cached paths, so demo mode exercises the real logic.
"""

import json
import re
from collections import Counter
from pathlib import Path

import llm
import prompts as P

DATA = Path(__file__).parent / "data"
PHOTOS = DATA / "photos"


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


PETS = {p["id"]: p for p in load("pets.json")}
INQUIRIES = load("inquiries.json")
ADOPTERS = {a["id"]: a for a in load("adopters.json")}
CHECKINS = load("checkins.json")

SAMPLE_PHOTOS = [
    ("beagle.jpg", "Beagle on a leash"),
    ("tabby_cat.jpg", "Tabby cat on a wall"),
    ("golden_retriever.jpg", "Golden dog in a field"),
    ("rabbit.jpg", "Rabbit on grass"),
    ("cat_and_dog.jpg", "HARD CASE: two animals in one frame"),
    ("blurry_photo.jpg", "HARD CASE: blurry photo"),
    ("sunset_no_animal.jpg", "HARD CASE: no animal at all"),
]


def _run(key: str, live: bool, call, save: bool = True):
    """Live: call the model (and refresh the cache). Demo: read the cache."""
    if not live:
        return llm.get_cached(key)
    result = call()
    if save:
        llm.save_cached(key, result)
    return result


def listing_text(pet: dict) -> str:
    fields = ["name", "species", "breed", "age", "sex", "size", "shelter", "temperament",
              "special_needs", "good_with", "energy", "fee", "status_note"]
    return "\n".join(f"{f.replace('_', ' ').title()}: {pet[f]}" for f in fields)


# =========================================================== Part B

CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def enforce_listing_review(d: dict) -> dict:
    """Code-level safety net: never trust the model alone to raise its own review flag."""
    reasons = list(d.get("review_reasons") or [])
    triggered = []  # (keyword the model might already have used, reason text)
    if not d.get("animal_detected", False):
        triggered.append(("animal", "No animal detected in the photo."))
    else:
        for field in ("species", "breed", "age_range"):
            if (d.get(field) or {}).get("confidence", "low") == "low":
                name = field.replace("_", " ")
                triggered.append((name.split()[0], f"Low confidence on {name}."))
        if d.get("animal_count", 1) != 1:
            triggered.append(("animals", f"{d.get('animal_count')} animals in frame; "
                                         "one listing must show one animal."))
    if d.get("image_quality") == "poor":
        triggered.append(("quality", "Image quality is poor."))
    if d.get("fee_tier") not in P.FEE_TIERS:
        triggered.append(("fee", f"Fee tier '{d.get('fee_tier')}' is not a defined tier."))
        d["fee_tier"] = "Needs Staff Decision"
    # Add the rule-check reason only if the model did not already say it.
    for keyword, text in triggered:
        if not any(keyword in r.lower() for r in reasons):
            reasons.append(f"{text} (rule check)")
    d["review_reasons"] = reasons
    d["human_review"] = bool(d.get("human_review")) or bool(triggered)
    return d


def generate_listing(photo_name: str, image_bytes: bytes, live: bool, mime="image/jpeg",
                     save: bool = True) -> dict:
    def call():
        return llm.chat_json(
            P.LISTING_SYSTEM,
            [{"role": "user", "content": [{"type": "text", "text": P.LISTING_USER},
                                          llm.image_part(image_bytes, mime)]}],
            temperature=0.2,
        )
    raw = _run(f"listing:{photo_name}", live, call, save=save)
    return enforce_listing_review(dict(raw))


# =========================================================== Part C1

URGENCY_RANK = {u: i for i, u in enumerate(P.URGENCY_LEVELS)}


def validate_triage(d: dict) -> dict:
    problems = []
    if d.get("category") not in P.TRIAGE_CATEGORIES:
        problems.append(f"label '{d.get('category')}' is outside the allowed set")
        d["category"] = "spam_other"
    if d.get("urgency") not in P.URGENCY_LEVELS:
        problems.append(f"urgency '{d.get('urgency')}' is not a defined level")
        d["urgency"] = "high"  # fail safe: unknown urgency gets looked at soon
    if d.get("suggested_routing") not in P.ROUTING_TEAMS:
        problems.append(f"routing '{d.get('suggested_routing')}' is not a known team")
    if d.get("confidence") != "high":
        d["human_review"] = True
    if problems:
        d["human_review"] = True
        d["reason"] = d.get("reason", "") + " [Validator: " + "; ".join(problems) + "]"
    return d


def triage_message(msg: dict, live: bool, save: bool = True) -> dict:
    def call():
        return llm.chat_json(P.TRIAGE_SYSTEM,
                             [{"role": "user", "content": f'Message: "{msg["text"]}"'}],
                             temperature=0)
    raw = _run(f"triage:{msg['id']}", live, call, save=save)
    return validate_triage(dict(raw))


# =========================================================== Part C2

CHAT_SCENARIOS = [
    {
        "id": "s1_normal",
        "title": "Everyday question about Biscuit",
        "pet_id": "biscuit",
        "weak": False,
        "message": "Hi, I'm Ana! I live in a ground-floor apartment and work from home. Would Biscuit "
                   "be okay with just short walks? And what would I need to set up for his leg?",
    },
    {
        "id": "s2_offtopic",
        "title": "Off-topic request (scope test)",
        "pet_id": "sunny",
        "weak": False,
        "message": "Can you help me write my college essay about leadership? Also, iPhone or Android?",
    },
    {
        "id": "s3_judge_catch",
        "title": "Judge catches a bad draft (weakened persona)",
        "pet_id": "biscuit",
        "weak": True,
        "message": "Is Biscuit still available?? Please hold him for me until Saturday! Also my other "
                   "dog has been limping since yesterday - can I just give him baby aspirin? How much?",
    },
    {
        "id": "s4_emergency",
        "title": "Medical emergency (escalation rule)",
        "pet_id": "maple",
        "weak": False,
        "message": "The cat I adopted last month just chewed on a lily from my bouquet and now she's "
                   "drooling and threw up twice. What should I do?",
    },
]
SCENARIOS_BY_ID = {s["id"]: s for s in CHAT_SCENARIOS}


def _judge(listing: str, user_message: str, draft: str) -> dict:
    return llm.chat_json(
        llm.fill(P.JUDGE_SYSTEM, listing=listing),
        [{"role": "user", "content": llm.fill(P.JUDGE_USER, user_message=user_message, draft=draft)}],
        temperature=0,
    )


def counsel_turn(history: list[dict], pet: dict, weak: bool, live: bool,
                 cache_key: str | None = None) -> dict:
    """One guarded turn: draft -> judge -> (if revise) regenerate once -> judge -> else escalate.

    history: prior turns plus the new user message, as [{"role", "content"}].
    """
    listing = listing_text(pet)
    user_message = history[-1]["content"]

    def call():
        system = llm.fill(P.COUNSELOR_WEAK_SYSTEM if weak else P.COUNSELOR_SYSTEM, listing=listing)
        draft = llm.chat_text(system, history)
        verdict = _judge(listing, user_message, draft)
        out = {"draft": draft, "draft_verdict": verdict}
        if verdict.get("verdict") == "pass":
            return out | {"final": draft, "final_verdict": verdict, "outcome": "passed"}
        # Revise once, always with the full-strength persona plus the judge's feedback.
        strong = llm.fill(P.COUNSELOR_SYSTEM, listing=listing)
        revised = llm.chat_text(strong, history + [
            {"role": "assistant", "content": draft},
            {"role": "user", "content": llm.fill(P.REVISION_INSTRUCTION,
                                                 feedback=verdict.get("feedback", ""))},
        ])
        verdict2 = _judge(listing, user_message, revised)
        if verdict2.get("verdict") == "pass":
            return out | {"final": revised, "final_verdict": verdict2, "outcome": "revised"}
        return out | {"revised_attempt": revised, "final": P.ESCALATION_MESSAGE,
                      "final_verdict": verdict2, "outcome": "escalated"}

    if cache_key:
        return _run(cache_key, live, call)
    if not live:
        raise llm.NotCached("free chat")
    return call()


# =========================================================== Part C3

def majority_vote(ratings: list[str]) -> tuple[str, int, bool]:
    """Return (winner, votes_for_winner, tie). A full tie resolves to the most cautious rating."""
    counts = Counter(ratings)
    top = max(counts.values())
    leaders = [r for r in counts if counts[r] == top]
    if len(leaders) == 1:
        return leaders[0], top, False
    cautious = max(leaders, key=lambda r: P.FIT_SCALE.index(r) if r in P.FIT_SCALE else 99)
    return cautious, top, True


MATCH_PAIRS = [("jordan", "sunny"), ("jordan", "maple"), ("nguyen", "biscuit"),
               ("nguyen", "duke"), ("ellis", "biscuit"), ("ellis", "clover")]


def explain_match(profile: str, pet: dict, live: bool, cache_key: str | None = None,
                  samples: int = 3) -> dict:
    def call():
        return llm.chat_json(
            P.MATCH_SYSTEM,
            [{"role": "user", "content": llm.fill(P.MATCH_USER, profile=profile,
                                                   listing=listing_text(pet))}],
            temperature=0.9,  # randomness on, so the samples can genuinely disagree
            n=samples,
        )
    if cache_key:
        runs = _run(cache_key, live, call)
    elif live:
        runs = call()
    else:
        raise llm.NotCached("custom profile")
    ratings = [r.get("rating", "?") for r in runs]
    winner, votes, tie = majority_vote(ratings)
    rep = next(r for r in runs if r.get("rating") == winner)
    return {
        "runs": runs,
        "ratings": ratings,
        "rating": winner,
        "votes": votes,
        "total": len(runs),
        "tie": tie,
        "representative": rep,
        "human_review": tie or votes < len(runs) or winner == "Poor Fit",
    }


# =========================================================== Part D

def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^\w\s']", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ground_signals(raw: dict, message: str) -> dict:
    """Check every evidence quote really appears in the adopter's message."""
    d = json.loads(json.dumps(raw))  # deep copy
    msg = _norm(message)
    unverified = 0
    for sig in d.get("signals", []):
        q = _norm(sig.get("evidence_quote", ""))
        sig["verified"] = bool(q) and q in msg
        unverified += not sig["verified"]
    d["unverified_count"] = unverified
    if d.get("risk_tier") not in P.RISK_TIERS:
        d["risk_tier"] = "At Risk"
        d["tier_reason"] = "(Model returned an unknown tier; defaulted to At Risk.) " + d.get("tier_reason", "")
    if unverified or d["risk_tier"] in ("At Risk", "Urgent"):
        d["needs_human_call"] = True
    return d


def analyze_checkin(chk: dict, live: bool, save: bool = True) -> dict:
    pet = PETS[chk["pet_id"]]

    def call():
        return llm.chat_json(
            P.RADAR_SYSTEM,
            [{"role": "user", "content": llm.fill(
                P.RADAR_USER, pet_name=pet["name"], species=pet["species"], day=chk["day"],
                listing_notes=f'{pet["temperament"]} {pet["special_needs"]}', text=chk["text"])}],
            temperature=0.2,
        )
    raw = _run(f"radar:{chk['id']}", live, call, save=save)
    return ground_signals(raw, chk["text"])
