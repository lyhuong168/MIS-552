"""Regenerate cache/responses.json from the live API for every bundled sample input.

Usage (PowerShell):   $env:OPENAI_API_KEY="sk-..." ; python build_cache.py
Usage (bash):         OPENAI_API_KEY=sk-... python build_cache.py
Optional:             python build_cache.py listing triage   (only some features)

With gpt-4o-mini the full run is roughly 50 API calls and costs a few cents.
"""

import json
import sys

import features as F
import llm

if not llm.has_key():
    sys.exit("Set OPENAI_API_KEY in the environment first.")

only = set(sys.argv[1:]) or {"listing", "triage", "chat", "match", "radar"}

# Start from a clean cache so no seed/placeholder entries survive.
if only == {"listing", "triage", "chat", "match", "radar"}:
    llm.CACHE_PATH.parent.mkdir(exist_ok=True)
    llm.CACHE_PATH.write_text(json.dumps({"_meta": {}, "entries": {}}), encoding="utf-8")

if "listing" in only:
    for photo, label in F.SAMPLE_PHOTOS:
        d = F.generate_listing(photo, (F.PHOTOS / photo).read_bytes(), live=True)
        print(f"[listing] {photo:22s} breed={d['breed']['value']!r} review={d['human_review']}")

if "triage" in only:
    for m in F.INQUIRIES:
        r = F.triage_message(m, live=True)
        print(f"[triage]  {m['id']} {r['urgency']:8s} {r['category']:22s} review={r['human_review']}")

if "chat" in only:
    for sc in F.CHAT_SCENARIOS:
        t = F.counsel_turn([{"role": "user", "content": sc["message"]}], F.PETS[sc["pet_id"]],
                           sc["weak"], live=True, cache_key=f"chat:{sc['id']}")
        print(f"[chat]    {sc['id']:16s} draft={t['draft_verdict'].get('verdict')} outcome={t['outcome']}")

if "match" in only:
    for a, p in F.MATCH_PAIRS:
        r = F.explain_match(F.ADOPTERS[a]["profile"], F.PETS[p], live=True, cache_key=f"match:{a}:{p}")
        print(f"[match]   {a:7s}+{p:8s} votes={r['ratings']} -> {r['rating']}")

if "radar" in only:
    for c in F.CHECKINS:
        r = F.analyze_checkin(c, live=True)
        print(f"[radar]   {c['id']} {r['risk_tier']:10s} unverified={r['unverified_count']}")

print(f"\nCache written to {llm.CACHE_PATH}")
