"""NHS De-Identification Gate — demo UI.

Run from the repo root:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import html
import json
import sys
import time
from collections import Counter
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.analyzer import analyze, build_analyzer  # noqa: E402
from src.anonymize import MODE_PSEUDONYMISE, MODE_REDACT, Vault, anonymize_text  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.load_data import load_notes_with_known_pii  # noqa: E402

OUT_DIR = REPO / "data" / "out"

ENTITY_COLORS = {
    "PERSON": "#ffd6e0", "UK_NHS": "#ffe9b3", "DATE_TIME": "#d4f4dd", "UK_POSTCODE": "#cfe8ff",
    "LOCATION": "#cfe8ff", "ORGANIZATION": "#e3d7ff", "RECORD_ID": "#ffd9c2", "PHONE_NUMBER": "#d4f4dd",
    "UK_NINO": "#ffe9b3", "UK_PASSPORT": "#ffe9b3", "UK_VEHICLE_REGISTRATION": "#ffe9b3",
    "GMC": "#f0e0a0", "NMC": "#f0e0a0", "NHS_ODS": "#f0e0a0", "NRP": "#ffc2c2", "EMAIL_ADDRESS": "#d4f4dd",
}

st.set_page_config(page_title="NHS De-Identification Gate", page_icon="🛡️", layout="wide")


@st.cache_resource(show_spinner="Loading model + NHS recognizers…")
def get_analyzer_and_notes():
    notes = load_notes_with_known_pii()
    rp, rpl, rn, ri = set(), set(), set(), set()
    for n in notes:
        rp.update(n.known.get("names", []))
        rpl.update(n.known.get("places", []))
        rn.update(n.known.get("nhs_numbers", []))
        ri.update(n.known.get("ids", []))
    analyzer = build_analyzer(roster_person=rp, roster_place=rpl, roster_nhs=rn, roster_ids=ri)
    return analyzer, notes


def highlight(text: str, results) -> str:
    chosen, last_end = [], -1
    for r in sorted(results, key=lambda r: (r.start, -(r.end - r.start))):
        if r.start >= last_end:
            chosen.append(r)
            last_end = r.end
    out, idx = [], 0
    for r in chosen:
        out.append(html.escape(text[idx:r.start]))
        seg = html.escape(text[r.start:r.end])
        color = ENTITY_COLORS.get(r.entity_type, "#e0e0e0")
        out.append(
            f'<mark style="background:{color};padding:0 2px;border-radius:3px" '
            f'title="{r.entity_type} ({r.score:.2f})">{seg}</mark>'
        )
        idx = r.end
    out.append(html.escape(text[idx:]))
    return "".join(out).replace("\n", "<br>")


def scroll_box(inner_html: str, height: int = 360):
    st.markdown(
        f'<div style="height:{height}px;overflow:auto;border:1px solid #ddd;border-radius:8px;'
        f'padding:12px;font-family:ui-monospace,monospace;font-size:13px;line-height:1.5">{inner_html}</div>',
        unsafe_allow_html=True,
    )


def load_json(name: str):
    path = OUT_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


st.title("🛡️ NHS De-Identification Gate")
st.caption("Detect & remove PII from free-text clinical notes so only de-identified data leaves a Trust "
           "— the on-ramp to a Secure Data Environment. Microsoft Presidio + spaCy.")

try:
    analyzer, NOTES = get_analyzer_and_notes()
except Exception as exc:  # dataset not downloaded yet
    st.error(f"Could not load data/model: {exc}\n\nRun `python -m src.load_data` first.")
    st.stop()

tab_try, tab_metrics, tab_gov, tab_trust = st.tabs(
    ["🔎 Try it", "📊 Metrics & leakage test", "🏛️ Governance (Five Safes)", "🤝 Two-Trust sharing"]
)

# ---------------------------------------------------------------- Try it
with tab_try:
    c1, c2 = st.columns([3, 2])
    with c2:
        mode = st.radio("Anonymisation policy", [MODE_PSEUDONYMISE, MODE_REDACT],
                        format_func=lambda m: "Pseudonymise (realistic fakes)" if m == MODE_PSEUDONYMISE
                        else "Redact (<TYPE> tags)")
        source = st.radio("Input", ["Sample note from dataset", "Paste your own"])
    with c1:
        if source == "Sample note from dataset":
            idx = st.number_input("Note index", 0, len(NOTES) - 1, 0, step=1)
            text = NOTES[int(idx)].text
        else:
            text = st.text_area("Clinical note text", height=200,
                                value="Patient John Smith, NHS Number: 943 476 5919, DOB 02/03/1981, "
                                      "lives at SW1A 1AA. Admitted to Ward 9. Reviewed by Dr Lee, GMC 1234567.")

    if text.strip():
        results = analyze(analyzer, text)
        vault = Vault()
        clean = anonymize_text(text, results, mode=mode, vault=vault)
        st.markdown("##### Raw note — detected PII highlighted")
        scroll_box(highlight(text, results))
        st.markdown(f"##### De-identified output — `{mode}`")
        scroll_box(html.escape(clean).replace("\n", "<br>"))

        counts = Counter(r.entity_type for r in results)
        st.markdown("##### Audit record (counts only — no raw values leave)")
        st.dataframe({"entity": list(counts.keys()), "count": list(counts.values())},
                     width="stretch", hide_index=True)

# ---------------------------------------------------------------- Metrics
with tab_metrics:
    st.markdown("The pass/fail signal: using the note→patient oracle, every known identifier present in "
                "a raw note must be **detected** (and thus removed). Metric = detection coverage.")
    metrics = load_json("metrics.json")
    col_run, col_n = st.columns([1, 2])
    with col_n:
        n = st.slider("Notes to evaluate (live run)", 50, 1602, 300, step=50)
    with col_run:
        if st.button("▶ Run leakage test"):
            with st.spinner("Evaluating…"):
                metrics = evaluate(mode=MODE_PSEUDONYMISE, limit=n)
                OUT_DIR.mkdir(parents=True, exist_ok=True)
                (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if metrics:
        leaks = metrics["leaks"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Identifier leaks", leaks, delta="PASS" if leaks == 0 else "FAIL",
                  delta_color="normal" if leaks == 0 else "inverse")
        m2.metric("Overall recall", f"{metrics['overall_recall']:.1%}")
        m3.metric("Notes processed", metrics["notes_processed"])
        m4.metric("Throughput", f"{metrics.get('throughput_notes_per_sec', 0):.0f}/s")
        st.markdown("##### Recall by identifier type")
        rbc = metrics["recall_by_category"]
        pbc = metrics["present_by_category"]
        st.dataframe(
            {"category": list(rbc.keys()),
             "recall": [f"{v:.1%}" if v is not None else "—" for v in rbc.values()],
             "identifiers present": [pbc.get(k, 0) for k in rbc]},
            width="stretch", hide_index=True,
        )
    else:
        st.info("No metrics yet — click **Run leakage test** or run `python -m src.evaluate`.")

# ---------------------------------------------------------------- Governance
with tab_gov:
    st.markdown("### Mapped to the NHS **Five Safes** framework")
    safes = {
        "Safe data": "PII removed to DAPB1523/ICO standard — full Presidio Global+UK entity set plus "
                     "NHS identifiers (NHS number, clinician GMC/NMC, ODS, record UUIDs). NRP "
                     "(special-category) is always redacted.",
        "Safe settings": "Detection + anonymisation run **inside** the Trust. Raw CSVs and the vault are "
                         "gitignored and never leave.",
        "Safe outputs": "Only de-identified text + content-free audit logs are emitted; the leakage "
                        "test gates outputs at **0 leaks**.",
        "Safe people / projects": "Re-identification vault stays Trust-local. Pseudonymised (not "
                                  "anonymised) data is still personal data under UK GDPR — handled honestly.",
        "Adoption path": "Preprocessing layer for an NHS Secure Data Environment / Federated Data "
                         "Platform; next step is FLock.io federated training over the de-identified pools.",
    }
    for k, v in safes.items():
        st.markdown(f"**{k}** — {v}")
    st.divider()
    st.markdown("Audit logs are the governance artifact — they record *what kind* of PII was removed, "
                "in what counts, never the values. See `data/out/trust_*/manifest.json`.")

# ---------------------------------------------------------------- Two-Trust
with tab_trust:
    st.markdown("Two NHS Trusts collaborate **without sharing sensitive data**: each de-identifies "
                "locally and contributes only de-identified notes to a shared pool.")
    summary = load_json("trust_demo_summary.json")
    if st.button("▶ Run two-Trust demo"):
        from src.trust_demo import main as run_trust
        with st.spinner("De-identifying at each Trust…"):
            run_trust()
        summary = load_json("trust_demo_summary.json")

    if summary:
        cols = st.columns(len(summary["trusts"]) + 1)
        for col, t in zip(cols, summary["trusts"]):
            with col:
                st.markdown(f"#### 🏥 {t['trust'].split('(')[0].strip()}")
                st.metric("Notes de-identified", t["notes_deidentified"])
                st.metric("Raw records shared", t["raw_records_shared"])
                st.metric("Leaks", t["leaks"])
                st.caption("🔒 raw notes + vault stay local")
        with cols[-1]:
            st.markdown("#### 🟢 Shared SDE pool")
            st.metric("De-identified notes", summary["shared_pool_size"])
            st.metric("Raw records shared", summary["raw_records_shared"])
            st.metric("Total leaks", summary["total_leaks"])
            st.caption("→ ready for federated AI / FLock.io")
    else:
        st.info("Click **Run two-Trust demo** or run `python -m src.trust_demo`.")
