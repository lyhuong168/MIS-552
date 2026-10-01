"""PawsConnect AI Suite - Streamlit demo app.

Run:  streamlit run app.py
Demo mode (default) uses cached responses and needs no API key.
Live mode reads OPENAI_API_KEY from the environment.
"""

import html
import re

import streamlit as st

import features as F
import llm
import prompts as P

st.set_page_config(page_title="PawsConnect AI Suite", page_icon="🐾", layout="wide")

# ------------------------------------------------------------------ styling

st.markdown("""
<style>
.badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.8rem;
        font-weight:600; margin:0 4px 4px 0; white-space:nowrap; border:1px solid transparent;}
.b-green {background:#e3f5e8; color:#1b6b34; border-color:#b7e2c3;}
.b-amber {background:#fff4d6; color:#8a5a00; border-color:#f3dc9a;}
.b-red   {background:#fde4e4; color:#a11d1d; border-color:#f4b8b8;}
.b-purple{background:#f1e6fb; color:#5b2a86; border-color:#dcc4f2;}
.b-blue  {background:#e3eefc; color:#1f4f8f; border-color:#bcd3f5;}
.b-gray  {background:#eef0f2; color:#444b55; border-color:#d7dbe0;}
.card {border:1px solid #e3e6ea; border-radius:14px; padding:18px 20px; background:#ffffff;
       margin-bottom:14px; box-shadow:0 1px 2px rgba(0,0,0,0.04);}
.card h3 {margin-top:0;}
.review {border-left:5px solid #d97706; background:#fff8eb; padding:10px 14px; border-radius:8px;
         margin:8px 0 12px 0;}
.ok {border-left:5px solid #16a34a; background:#effaf2; padding:10px 14px; border-radius:8px;
     margin:8px 0 12px 0;}
.muted {color:#6b7280; font-size:0.85rem;}
table.queue {width:100%; border-collapse:collapse; font-size:0.9rem;}
table.queue th {text-align:left; background:#f4f5f7; padding:8px; border-bottom:2px solid #e3e6ea;}
table.queue td {padding:8px; border-bottom:1px solid #eceef1; vertical-align:top;}
mark.v {background:#fff1a8; padding:0 2px; border-radius:3px;}
.bubble-user {background:#eef4ff; border-radius:12px; padding:10px 14px; margin:6px 0;}
.bubble-bot {background:#f7f7f8; border-radius:12px; padding:10px 14px; margin:6px 0;}
.rejected {background:#fdf0f0; border:1px dashed #e6a3a3; border-radius:10px; padding:10px 14px;
           color:#7a2d2d;}
</style>
""", unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def badge(text: str, color: str = "gray", title: str = "") -> str:
    t = f' title="{esc(title)}"' if title else ""
    return f'<span class="badge b-{color}"{t}>{esc(text)}</span>'


CONF_COLOR = {"high": "green", "medium": "amber", "low": "red"}
URGENCY_COLOR = {"critical": "red", "high": "amber", "normal": "blue", "low": "gray"}
FIT_COLOR = {"Strong Fit": "green", "Good Fit": "blue", "Possible with Support": "amber", "Poor Fit": "red"}
TIER_COLOR = {"Thriving": "green", "Adjusting": "blue", "At Risk": "amber", "Urgent": "red"}
TIER_RANK = {t: i for i, t in enumerate(reversed(P.RISK_TIERS))}  # Urgent first


def review_flag(needs: bool, reasons=None, ok_text="No human review needed.") -> str:
    if needs:
        items = "".join(f"<li>{esc(r)}</li>" for r in (reasons or []))
        lst = f"<ul style='margin:4px 0 0 0'>{items}</ul>" if items else ""
        return f'<div class="review">⚠️ <b>Human review required</b>{lst}</div>'
    return f'<div class="ok">✅ {esc(ok_text)}</div>'


def not_cached_msg(what: str):
    st.info(f"No cached response for {what}. Switch to **Live mode** (needs an API key) to run it, "
            "or pick one of the bundled samples.")


# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.markdown("## 🐾 PawsConnect")
    st.caption("AI suite for shelters, adopters, and platform operations")
    mode = st.radio("Mode", ["Demo (cached responses)", "Live (OpenAI API)"],
                    help="Demo mode needs no API key. Live mode reads OPENAI_API_KEY from the environment.")
    LIVE = mode.startswith("Live")
    if LIVE and not llm.has_key():
        st.error("OPENAI_API_KEY is not set in the environment. Falling back to demo mode.")
        LIVE = False
    meta = llm.cache_meta()
    st.markdown("---")
    st.markdown(f"**Model:** `{llm.MODEL}`")
    if meta.get("source") == "seed":
        st.warning("Cached responses are placeholder **seed** data. Run `python build_cache.py` "
                   "with an API key to replace them with real model outputs.")
    elif meta.get("updated_at"):
        st.caption(f"Cache: live outputs from `{meta.get('model')}`, updated {meta.get('updated_at')}")
    st.markdown("---")
    st.markdown("**How to read the badges**")
    st.markdown(
        badge("high", "green") + badge("medium", "amber") + badge("low", "red")
        + "<div class='muted'>model confidence</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>⚠️ amber box = a person must check this before it is used.</div>",
                unsafe_allow_html=True)

st.title("🐾 PawsConnect AI Suite")
st.caption(("🟢 LIVE mode: calls the OpenAI API" if LIVE else "🗂️ DEMO mode: cached responses, no API key needed"))

tabs = st.tabs(["🏠 Overview", "📸 Photo-to-Profile", "📥 Inquiry Triage", "💬 Counselor Chat",
                "🤝 Match Explainer", "📡 Return-Risk Radar"])

# ================================================================== Overview

with tabs[0]:
    st.markdown("""
PawsConnect connects shelters and rescues with adopters. This demo shows five AI features, each built
for a specific person on the platform. Every output shows **what the AI decided, why, and how sure it is**,
and anything uncertain is flagged for a human.
""")
    c1, c2, c3 = st.columns(3)
    c1.markdown("""<div class="card"><h3>📸 Photo-to-Profile</h3><b>For:</b> shelter volunteers<br>
    One photo in, a draft adoption listing out, with confidence on every guess and a review flag
    for hard photos.<br><span class="muted">Vision model · structured output · fallback rules</span></div>""",
                unsafe_allow_html=True)
    c2.markdown("""<div class="card"><h3>📥 Inquiry Triage</h3><b>For:</b> shelter front desk<br>
    Turns the inbox into a queue sorted by urgency, with the team to route to and the reason.
    <br><span class="muted">Few-shot classification · JSON records</span></div>""", unsafe_allow_html=True)
    c3.markdown("""<div class="card"><h3>💬 Counselor Chat</h3><b>For:</b> adopters<br>
    "Hazel" answers adoption questions. A second AI reviews every reply before it is shown.
    <br><span class="muted">Persona system prompt · LLM-as-judge</span></div>""", unsafe_allow_html=True)
    c4, c5, _ = st.columns(3)
    c4.markdown("""<div class="card"><h3>🤝 Match Explainer</h3><b>For:</b> adoption counselors<br>
    Explains why a pet fits (or doesn't fit) a household. Asks the model three times and shows the vote.
    <br><span class="muted">Chain-of-thought · self-consistency</span></div>""", unsafe_allow_html=True)
    c5.markdown("""<div class="card"><h3>📡 Return-Risk Radar</h3><b>For:</b> post-adoption support<br>
    Reads adopter check-ins, finds early warning signs with quoted evidence, and ranks who needs a call.
    <br><span class="muted">Grounded extraction · quote verification</span></div>""", unsafe_allow_html=True)

# ================================================================== Part B

with tabs[1]:
    st.subheader("📸 Photo-to-Profile listing generator")
    st.caption("A volunteer uploads one photo; the AI drafts an honest adoption listing for staff to review.")

    left, right = st.columns([1, 1.6])
    with left:
        options = [f for f, _ in F.SAMPLE_PHOTOS]
        labels = dict(F.SAMPLE_PHOTOS)
        src = st.radio("Photo source", ["Bundled sample", "Upload my own (live mode)"], horizontal=True)
        upload = None
        if src.startswith("Bundled"):
            photo = st.selectbox("Sample photo", options, format_func=lambda f: f"{labels[f]}  ({f})")
            img_bytes = (F.PHOTOS / photo).read_bytes()
            mime = "image/jpeg"
        else:
            upload = st.file_uploader("Pet photo", type=["jpg", "jpeg", "png", "webp"], disabled=not LIVE)
            if not LIVE:
                st.caption("Uploading needs live mode. Pick a bundled sample to see the cached demo.")
            photo = upload.name if upload else None
            img_bytes = upload.getvalue() if upload else None
            mime = upload.type if upload else "image/jpeg"
        if img_bytes:
            st.image(img_bytes, width="stretch")
        go = st.button("✨ Draft listing", type="primary", disabled=not img_bytes)

    if go:
        try:
            st.session_state["listing"] = (photo, F.generate_listing(
                photo, img_bytes, LIVE, mime=mime, save=upload is None))
        except llm.NotCached:
            st.session_state.pop("listing", None)
            with right:
                not_cached_msg("this photo")

    with right:
        res = st.session_state.get("listing")
        if res and res[0] == photo:
            d = res[1]
            st.markdown(review_flag(d["human_review"], d.get("review_reasons"),
                                    "Looks complete. Staff should still confirm temperament before posting."),
                        unsafe_allow_html=True)
            if not d.get("animal_detected"):
                st.markdown(f"""<div class="card"><h3>🚫 No listing drafted</h3>
                The AI did not find an animal in this photo, so it refused to invent a profile.
                <br><br>{badge('image quality: ' + d.get('image_quality', '?'), 'gray')}</div>""",
                            unsafe_allow_html=True)
            else:
                names = " ".join(badge(n, "purple") for n in d.get("suggested_names", []))

                def field_row(label, key):
                    f = d.get(key) or {}
                    c = f.get("confidence", "low")
                    return (f"<tr><td><b>{label}</b></td><td>{esc(f.get('value'))}</td>"
                            f"<td>{badge(c, CONF_COLOR.get(c, 'gray'))}</td>"
                            f"<td class='muted'>{esc(f.get('evidence', ''))}</td></tr>")

                care = "".join(f"<li>{esc(c)}</li>" for c in d.get("care_requirements", []))
                tier = d.get("fee_tier", "")
                count_badge = (badge(f"{d.get('animal_count')} animals in photo", "red")
                               if d.get("animal_count", 1) != 1 else "")
                st.markdown(f"""<div class="card">
                <div class="muted">Suggested names</div><div>{names}</div><br>
                <table class="queue">
                  <tr><th>Field</th><th>AI estimate</th><th>Confidence</th><th>Visible evidence</th></tr>
                  {field_row('Species', 'species')}{field_row('Breed', 'breed')}{field_row('Age range', 'age_range')}
                </table><br>
                <div class="muted">About this pet (for adopters)</div>
                <p>{esc(d.get('personality'))}</p>
                <div class="muted">Care requirements</div><ul>{care}</ul>
                <div class="muted">Adoption fee tier</div>
                {badge(tier, 'blue')} <span class="muted">{esc(P.FEE_TIERS.get(tier, ''))}</span>
                <p class="muted">{esc(d.get('fee_reason'))}</p>
                {badge('image quality: ' + d.get('image_quality', '?'), CONF_COLOR.get({'clear': 'high', 'usable': 'medium', 'poor': 'low'}.get(d.get('image_quality')), 'gray'))}
                {count_badge}
                </div>""", unsafe_allow_html=True)
            if d.get("unextractable_fields"):
                st.markdown("**Fields the AI could not read (fallback rule applied)**")
                for u in d["unextractable_fields"]:
                    st.markdown(f"- **{u.get('field')}**: {u.get('reason')}")
            with st.expander("Developer view: raw structured output"):
                st.json(d)

            # Optional bonus: promotional banner (Shopify Magic pattern)
            if d.get("animal_detected") and d.get("animal_count", 1) == 1:
                with st.expander("🎨 Bonus: generate a promotional banner (live mode)"):
                    desc = f"{d['breed']['value']} {d['species']['value'].lower()}"
                    prompt = P.BANNER_PROMPT.replace("{description}", desc)
                    st.caption(f"Image model: `{llm.IMAGE_MODEL}`. Prompt: {prompt}")
                    if st.button("Generate banner", disabled=not LIVE):
                        with st.spinner("Painting..."):
                            st.image(llm.generate_image(prompt), width="stretch")

    st.markdown("---")
    if st.button("Run all 7 sample photos (summary)"):
        rows = []
        for f, label in F.SAMPLE_PHOTOS:
            try:
                d = F.generate_listing(f, (F.PHOTOS / f).read_bytes(), LIVE)
            except llm.NotCached:
                continue
            br = d.get("breed") or {}
            rows.append(f"<tr><td>{esc(label)}</td><td>{esc((d.get('species') or {}).get('value'))}</td>"
                        f"<td>{esc(br.get('value'))}</td>"
                        f"<td>{badge(br.get('confidence', 'low'), CONF_COLOR.get(br.get('confidence'), 'gray'))}</td>"
                        f"<td>{badge(d.get('fee_tier', ''), 'blue')}</td>"
                        f"<td>{badge('Review', 'amber') if d['human_review'] else badge('OK', 'green')}</td></tr>")
        st.markdown("<table class='queue'><tr><th>Photo</th><th>Species</th><th>Breed guess</th>"
                    "<th>Breed confidence</th><th>Fee tier</th><th>Human review</th></tr>"
                    + "".join(rows) + "</table>", unsafe_allow_html=True)

# ================================================================== Part C1

with tabs[2]:
    st.subheader("📥 Adoption inquiry triage")
    st.caption("Every incoming message becomes a routed record. The queue is sorted most urgent first.")

    with st.expander("What the columns mean"):
        st.markdown("**Urgency levels**")
        for u, desc in P.URGENCY_LEVELS.items():
            st.markdown(badge(u, URGENCY_COLOR[u]) + f" {esc(desc)}", unsafe_allow_html=True)
        st.markdown("**Categories**")
        for c, desc in P.TRIAGE_CATEGORIES.items():
            st.markdown(f"- `{c}`: {desc}")
        st.markdown("**Why?** is the model's stated reason. **Review** means a person should confirm "
                    "the label (mixed topics, low confidence, or a validator problem).")

    if st.button("📬 Triage the inbox (10 sample messages)", type="primary"):
        results = []
        for m in F.INQUIRIES:
            try:
                results.append((m, F.triage_message(m, LIVE)))
            except llm.NotCached:
                pass
        st.session_state["triage"] = results

    if LIVE:
        with st.form("custom_triage"):
            txt = st.text_area("Or triage a new message (live)", height=80)
            if st.form_submit_button("Triage this message") and txt.strip():
                m = {"id": f"custom{len(txt)}", "sender": "New message", "text": txt.strip()}
                r = F.triage_message(m, LIVE, save=False)
                st.session_state.setdefault("triage", []).append((m, r))

    results = st.session_state.get("triage")
    if results:
        results = sorted(results, key=lambda mr: (F.URGENCY_RANK.get(mr[1]["urgency"], 9),
                                                  not mr[1].get("human_review")))
        counts = {u: sum(r["urgency"] == u for _, r in results) for u in P.URGENCY_LEVELS}
        cols = st.columns(5)
        for col, u in zip(cols, P.URGENCY_LEVELS):
            col.metric(u.title(), counts[u])
        cols[4].metric("Need review", sum(bool(r.get("human_review")) for _, r in results))

        rows = []
        for m, r in results:
            sec = (f"<br><span class='muted'>also: {esc(r['secondary_category'])}</span>"
                   if r.get("secondary_category") else "")
            rows.append(
                f"<tr><td>{badge(r['urgency'].upper(), URGENCY_COLOR.get(r['urgency'], 'gray'))}</td>"
                f"<td><b>{esc(r['category'])}</b>{sec}<br>{badge(r.get('confidence', '?'), CONF_COLOR.get(r.get('confidence'), 'gray'))}</td>"
                f"<td>{esc(r.get('suggested_routing'))}</td>"
                f"<td><b>{esc(m['sender'])}</b>: {esc(r.get('summary'))}"
                f"<details><summary class='muted'>original message</summary>{esc(m['text'])}</details></td>"
                f"<td class='muted'>{esc(r.get('reason'))}</td>"
                f"<td>{badge('⚠ Review', 'amber') if r.get('human_review') else badge('OK', 'green')}</td></tr>")
        st.markdown("<table class='queue'><tr><th>Urgency</th><th>Category</th><th>Route to</th>"
                    "<th>Summary</th><th>Why?</th><th>Review</th></tr>" + "".join(rows) + "</table>",
                    unsafe_allow_html=True)

# ================================================================== Part C2

with tabs[3]:
    st.subheader(f"💬 Adoption counselor \"{P.COUNSELOR_NAME}\" with an AI quality reviewer")
    st.caption("Hazel drafts each reply. A second AI checks it against a rubric before you see it. "
               "If the reviewer says REVISE, Hazel rewrites once; if it still fails, a human takes over.")

    OUTCOME = {
        "passed": ("✅ Reviewer: PASS", "green"),
        "revised": ("🔁 Reviewer caught a problem; reply was rewritten", "amber"),
        "escalated": ("🚨 Reviewer rejected twice; escalated to a human", "red"),
    }

    def render_turn(user_msg: str, t: dict):
        st.markdown(f"<div class='bubble-user'>🧑 {esc(user_msg)}</div>", unsafe_allow_html=True)
        label, color = OUTCOME[t["outcome"]]
        extra = ""
        if t["final"].startswith("[ESCALATE]"):
            extra = badge("📞 Hazel escalated this to shelter staff", "purple")
        final = t["final"].replace("[ESCALATE]", "").strip()
        st.markdown(f"<div class='bubble-bot'>🐾 <b>Hazel</b><br>{esc(final)}<br><br>"
                    f"{badge(label, color)}{extra}</div>", unsafe_allow_html=True)
        with st.expander("Guardrail details: what the reviewer checked"):
            def rubric(v):
                rows = "".join(
                    f"<tr><td>{esc(k.replace('_', ' '))}</td>"
                    f"<td>{badge(c.get('result', '?').upper(), 'green' if c.get('result') == 'pass' else 'red')}</td>"
                    f"<td class='muted'>{esc(c.get('note'))}</td></tr>"
                    for k, c in (v.get("criteria") or {}).items())
                return f"<table class='queue'><tr><th>Rubric item</th><th>Result</th><th>Note</th></tr>{rows}</table>"
            if t["outcome"] != "passed":
                st.markdown("**First draft (blocked, never shown to the adopter):**")
                st.markdown(f"<div class='rejected'>{esc(t['draft'])}</div>", unsafe_allow_html=True)
                st.markdown(rubric(t["draft_verdict"]), unsafe_allow_html=True)
                st.markdown(f"**Reviewer feedback sent back to Hazel:** {t['draft_verdict'].get('feedback')}")
                st.markdown("**Review of the reply that was shown:**" if t["outcome"] == "revised"
                            else "**Review of the rewrite (also failed, so a human was called in):**")
            st.markdown(rubric(t["final_verdict"]), unsafe_allow_html=True)

    st.markdown("**Try a scripted scenario**")
    sc_cols = st.columns(len(F.CHAT_SCENARIOS))
    for col, sc in zip(sc_cols, F.CHAT_SCENARIOS):
        if col.button(sc["title"], key=sc["id"], width="stretch"):
            try:
                pet = F.PETS[sc["pet_id"]]
                hist = [{"role": "user", "content": sc["message"]}]
                t = F.counsel_turn(hist, pet, sc["weak"], LIVE, cache_key=f"chat:{sc['id']}")
                st.session_state["chat"] = {"pet": sc["pet_id"], "weak": sc["weak"],
                                            "turns": [(sc["message"], t)], "scenario": sc["id"]}
            except llm.NotCached:
                not_cached_msg("this scenario")

    chat = st.session_state.get("chat")
    if chat:
        pet = F.PETS[chat["pet"]]
        note = (" · ⚠️ <b>weakened persona</b> (scope/honesty rules removed to test the reviewer)"
                if chat["weak"] else "")
        st.markdown(f"<div class='muted'>Talking about: <b>{esc(pet['name'])}</b> "
                    f"({esc(pet['breed'])}){note}</div>", unsafe_allow_html=True)
        for user_msg, t in chat["turns"]:
            render_turn(user_msg, t)

    st.markdown("---")
    if LIVE:
        lc1, lc2 = st.columns([2, 1])
        pet_id = lc1.selectbox("Pet being discussed", list(F.PETS), format_func=lambda k: F.PETS[k]["name"])
        weak = lc2.toggle("Weakened persona (test the reviewer)", value=False)
        if not chat or chat.get("pet") != pet_id or chat.get("weak") != weak or chat.get("scenario"):
            if st.button("Start new conversation"):
                st.session_state["chat"] = {"pet": pet_id, "weak": weak, "turns": [], "scenario": None}
                st.rerun()
        msg = st.chat_input("Ask Hazel about adopting...")
        if msg and chat is not None:
            hist = []
            for u, t in chat["turns"]:
                hist += [{"role": "user", "content": u}, {"role": "assistant", "content": t["final"]}]
            hist.append({"role": "user", "content": msg})
            with st.spinner("Hazel is drafting; the reviewer is checking..."):
                t = F.counsel_turn(hist, F.PETS[chat["pet"]], chat["weak"], LIVE)
            chat["turns"].append((msg, t))
            chat["scenario"] = None
            st.rerun()
        elif msg:
            st.warning("Click **Start new conversation** first.")
    else:
        st.caption("Free-form chat is available in live mode. In demo mode, use the scripted scenarios above.")

    with st.expander("How Hazel is configured (persona and reviewer rubric)"):
        st.markdown("**Persona rules:** name and warm-but-honest tone; scope limited to adoption and "
                    "pet care; never promises availability; never gives veterinary advice; escalates "
                    "emergencies, welfare concerns, bites, and returns to a human.")
        st.markdown("**Reviewer rubric:** scope · consistency with listing data · tone · no medical "
                    "advice · correct escalation. All five must pass.")
        st.code(P.COUNSELOR_SYSTEM, language="text")

# ================================================================== Part C3

with tabs[4]:
    st.subheader("🤝 Adopter-pet match explainer")
    st.caption("The AI reasons through five compatibility factors, three separate times, and the "
               "rating is decided by majority vote so one unlucky answer can't decide a match.")

    m1, m2 = st.columns(2)
    with m1:
        prof_opts = list(F.ADOPTERS) + (["custom"] if LIVE else [])
        prof_id = st.selectbox("Household", prof_opts,
                               format_func=lambda k: F.ADOPTERS[k]["name"] if k in F.ADOPTERS else "Custom profile (live)")
        if prof_id == "custom":
            profile = st.text_area("Describe the household", height=120)
        else:
            profile = F.ADOPTERS[prof_id]["profile"]
            st.markdown(f"<div class='card'>{esc(profile)}</div>", unsafe_allow_html=True)
    with m2:
        pet_opts = list(F.PETS) if LIVE else [p for a, p in F.MATCH_PAIRS if a == prof_id]
        pet_id = st.selectbox("Pet", pet_opts, format_func=lambda k: f"{F.PETS[k]['name']} ({F.PETS[k]['breed']})",
                              key="match_pet")
        pet = F.PETS[pet_id]
        pc1, pc2 = st.columns([1, 2])
        pc1.image(str(F.PHOTOS / pet["photo"]), width="stretch")
        pc2.markdown(f"**{esc(pet['name'])}**, {esc(pet['age'])}, {esc(pet['size'])}<br>"
                     f"<span class='muted'>{esc(pet['temperament'])}<br>{esc(pet['special_needs'])}</span>",
                     unsafe_allow_html=True)
    if not LIVE:
        st.caption("Demo mode shows the cached household + pet pairs. Live mode allows any pair or a custom profile.")

    if st.button("🔍 Explain this match", type="primary", disabled=not profile.strip()):
        key = f"match:{prof_id}:{pet_id}" if prof_id != "custom" else None
        try:
            with st.spinner("Running 3 independent reasoning passes..."):
                st.session_state["match"] = ((prof_id, pet_id), F.explain_match(profile, pet, LIVE, cache_key=key))
        except llm.NotCached:
            st.session_state.pop("match", None)
            not_cached_msg("this household + pet pair")

    res = st.session_state.get("match")
    if res and res[0] == (prof_id, pet_id):
        r = res[1]
        rep = r["representative"]
        agree = ("All runs agreed." if r["votes"] == r["total"] else
                 "Runs disagreed; see the votes below." if not r["tie"] else
                 "No majority; the most cautious rating was chosen.")
        st.markdown(f"""<div class="card">
        <div class="muted">Fit rating (majority vote)</div>
        <h2 style="margin:4px 0">{badge(r['rating'], FIT_COLOR.get(r['rating'], 'gray'))}</h2>
        <b>{r['votes']} of {r['total']} runs rated this {esc(r['rating'])}.</b> <span class="muted">{agree}</span><br><br>
        {''.join(badge(f"Run {i + 1}: {x}", FIT_COLOR.get(x, 'gray')) for i, x in enumerate(r['ratings']))}
        </div>""", unsafe_allow_html=True)
        st.markdown(review_flag(r["human_review"],
                                [s for s in [
                                    "The three runs did not all agree." if r["votes"] < r["total"] else None,
                                    "Poor Fit ratings should be discussed with the adopter by a counselor, not sent automatically."
                                    if r["rating"] == "Poor Fit" else None] if s],
                                "All runs agreed. A counselor can share this explanation."),
                    unsafe_allow_html=True)
        a, b = st.columns(2)
        a.markdown("**Top 3 reasons**\n" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(rep.get("top_reasons", []))))
        b.markdown(f"**Top concern**\n\n> {rep.get('top_concern')}")
        with st.expander("🧠 See the step-by-step reasoning (all 3 runs)"):
            run_tabs = st.tabs([f"Run {i + 1}: {x}" for i, x in enumerate(r["ratings"])])
            for rt, run in zip(run_tabs, r["runs"]):
                with rt:
                    for i, s in enumerate(run.get("reasoning_steps", []), 1):
                        eff = s.get("effect", "neutral")
                        st.markdown(f"**Step {i}. {esc(s.get('factor'))}** "
                                    + badge(eff, {"helps": "green", "hurts": "red"}.get(eff, "gray"))
                                    + f"<br>{esc(s.get('analysis'))}", unsafe_allow_html=True)
                    st.markdown(f"**Concluded:** {run.get('rating')}  \n**Concern:** {run.get('top_concern')}")

# ================================================================== Part D

with tabs[5]:
    st.subheader("📡 Return-Risk Radar")
    st.caption("For the post-adoption support coordinator: reads this week's adopter check-ins, finds "
               "early warning signs, and ranks who needs a phone call first. Every warning sign must "
               "quote the adopter's own words, and the app checks that the quote is real.")

    with st.expander("How to read this"):
        for t in reversed(P.RISK_TIERS):
            desc = {"Urgent": "call today", "At Risk": "call within 48 hours",
                    "Adjusting": "send reassurance and tips", "Thriving": "no action"}[t]
            st.markdown(badge(t, TIER_COLOR[t]) + f" {desc}", unsafe_allow_html=True)
        st.markdown(badge("✓ quote verified", "green") + " the evidence was found word-for-word in the message. "
                    + badge("✗ quote not found", "red") + " the AI's quote does not appear in the message; "
                    "the signal may be invented, so a human must check.", unsafe_allow_html=True)

    if st.button("📡 Scan this week's check-ins", type="primary"):
        out = []
        for c in F.CHECKINS:
            try:
                out.append((c, F.analyze_checkin(c, LIVE)))
            except llm.NotCached:
                pass
        st.session_state["radar"] = out

    if LIVE:
        with st.form("custom_checkin"):
            cc1, cc2 = st.columns([1, 3])
            cpet = cc1.selectbox("Pet", list(F.PETS), format_func=lambda k: F.PETS[k]["name"])
            cday = cc1.number_input("Days since adoption", 1, 365, 7)
            ctext = cc2.text_area("Check-in message (live)", height=100)
            if st.form_submit_button("Analyze") and ctext.strip():
                c = {"id": "custom", "adopter": "New adopter", "pet_id": cpet, "day": int(cday), "text": ctext}
                st.session_state.setdefault("radar", []).append((c, F.analyze_checkin(c, LIVE, save=False)))

    out = st.session_state.get("radar")
    if out:
        out = sorted(out, key=lambda cr: TIER_RANK.get(cr[1]["risk_tier"], 9))
        rows = "".join(
            f"<tr><td>{badge(r['risk_tier'], TIER_COLOR.get(r['risk_tier'], 'gray'))}</td>"
            f"<td><b>{esc(c['adopter'])}</b> + {esc(F.PETS[c['pet_id']]['name'])}<br>"
            f"<span class='muted'>day {c['day']}</span></td>"
            f"<td>{esc(r.get('tier_reason'))}</td>"
            f"<td>{esc(r.get('recommended_action'))}</td>"
            f"<td>{badge('📞 Call', 'red') if r.get('needs_human_call') else badge('Message only', 'gray')}"
            f"{badge(str(r['unverified_count']) + ' unverified', 'red') if r['unverified_count'] else ''}</td></tr>"
            for c, r in out)
        st.markdown("<table class='queue'><tr><th>Risk</th><th>Adoption</th><th>Why</th>"
                    "<th>Recommended action</th><th>Coordinator</th></tr>" + rows + "</table>",
                    unsafe_allow_html=True)
        st.markdown("#### Check-in details")
        for c, r in out:
            pet = F.PETS[c["pet_id"]]
            with st.expander(f"{r['risk_tier']} · {c['adopter']} + {pet['name']} (day {c['day']})",
                             expanded=r["risk_tier"] == "Urgent"):
                msg_html = esc(c["text"])
                for s in r.get("signals", []):
                    if s.get("verified"):
                        q = esc(s.get("evidence_quote", ""))
                        msg_html = re.sub(re.escape(q), lambda m: f"<mark class='v'>{m.group(0)}</mark>",
                                          msg_html, count=1, flags=re.IGNORECASE)
                st.markdown(f"<div class='card'><div class='muted'>Adopter's message (evidence highlighted)</div>"
                            f"{msg_html}</div>", unsafe_allow_html=True)
                if r["unverified_count"]:
                    st.markdown(review_flag(True, [f"{r['unverified_count']} signal(s) quote words that are "
                                                   "not in the message. Read the original before acting."]),
                                unsafe_allow_html=True)
                for s in r.get("signals", []):
                    sev = s.get("severity", "low")
                    v = badge("✓ quote verified", "green") if s.get("verified") else badge("✗ quote not found", "red")
                    st.markdown(
                        badge(s.get("type", "").replace("_", " "), "purple")
                        + badge(sev, {"high": "red", "medium": "amber", "low": "gray"}.get(sev, "gray")) + v
                        + f"<br>“{esc(s.get('evidence_quote'))}” <span class='muted'>→ {esc(s.get('interpretation'))}</span>",
                        unsafe_allow_html=True)
                st.markdown(f"**Recommended action:** {r.get('recommended_action')}")
                st.text_area("Draft message to the adopter (edit before sending; nothing is sent automatically)",
                             r.get("draft_message", ""), key=f"draft_{c['id']}", height=110)
