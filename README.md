# PawsConnect AI Suite (MIS 552, Homework 1)

A Streamlit demo of five AI features for a pet adoption platform:

| Tab | Part | Technique |
|---|---|---|
| 📸 Photo-to-Profile | B | Vision model, structured JSON, fallback rules, code-enforced review flag |
| 📥 Inquiry Triage | C1 | Few-shot classification (4 examples), 8 defined labels, urgency-sorted queue |
| 💬 Counselor Chat | C2 | "Hazel" persona system prompt + LLM-as-judge (regenerate once, then escalate) |
| 🤝 Match Explainer | C3 | Chain-of-thought over 5 factors, 3 samples at temperature 0.9, majority vote |
| 📡 Return-Risk Radar | D | Grounded extraction from post-adoption check-ins with verbatim-quote verification |

## Run it (no API key needed)

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens in **Demo (cached responses)** mode. Every feature works from `cache/responses.json`:
click the primary button on each tab (e.g. "Draft listing", "Triage the inbox", a chat scenario,
"Explain this match", "Scan this week's check-ins").

## Live mode

Set your key as an environment variable (never in code), then pick **Live** in the sidebar:

```powershell
# PowerShell
$env:OPENAI_API_KEY = "sk-..."
streamlit run app.py
```
```bash
# macOS / Linux
export OPENAI_API_KEY=sk-...
streamlit run app.py
```

Live mode adds photo upload, free-form chat (with a "weakened persona" toggle), custom messages,
custom household profiles, custom check-ins, and the bonus banner image generator.
Optional overrides: `PAWS_MODEL` (default `gpt-4o-mini`), `PAWS_IMAGE_MODEL` (default `gpt-image-1`).

## Refresh the cached demo

```bash
python build_cache.py            # all features (~50 calls, a few cents on gpt-4o-mini)
python build_cache.py triage     # just one feature: listing | triage | chat | match | radar
```

## Files

```
app.py            Streamlit UI (tabs, cards, badges, expanders)
features.py       Feature logic: validation, review flags, voting, grounding checks
prompts.py        Every prompt (mirrored in prompts.md)
llm.py            OpenAI wrapper + cache read/write
build_cache.py    Regenerates cache/responses.json from the live API
cache/            Cached responses for demo mode
data/             pets.json, inquiries.json (10), adopters.json (3), checkins.json (5), photos/ (7)
prompts.md        Final prompts + iteration log
```

Sample data is synthetic. Photo licenses are listed in `data/photos/CREDITS.md`.
