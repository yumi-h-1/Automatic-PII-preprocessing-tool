"""NoteGuard — demo UI.

Run from the repo root:  streamlit run streamlit_app.py

Tabs:
  1. De-identify your data — upload a note/CSV/PDF, get de-identified data back. Nothing is stored.
  2. Get data by domain   — pick a clinical domain, download de-identified data (NHS + public sources).
  3. Metrics & Leakage     — measured residual leakage + data-quality report.
  4. Governance            — NHS Five Safes + Caldicott Principles + DPA 2018.
  5. Two-Trust sharing     — sanitise-at-source federation demo.

Built on the NoteGuard package (src/) — pluggable detectors + patient-consistent transforms.
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from src.catalog import all_entries  # noqa: E402
from src.cohorts import DOMAINS, domain_counts, filter_by_domain, note_matches_domain  # noqa: E402
from src.data import load_notes  # noqa: E402
from src.detect import ComposedDetector, build_detector  # noqa: E402
from src.evaluate import evaluate  # noqa: E402
from src.ingest import SUPPORTED, csv_columns, records_from_upload  # noqa: E402
from src.llm_assure import LLMAssurance  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.quality import data_quality_report  # noqa: E402
from src.transform import PSEUDONYM, REDACTION, PseudonymVault  # noqa: E402

OUT_DIR = REPO / "outputs"
RESULTS = REPO / "outputs" / "results.json"

ENTITY_COLORS = {
    "PERSON": "#ffd6e0", "UK_NHS": "#ffe9b3", "DATE_TIME": "#d4f4dd", "UK_POSTCODE": "#cfe8ff",
    "LOCATION": "#cfe8ff", "ORGANIZATION": "#cfe8ff", "RECORD_ID": "#ffd9c2",
    "PHONE_NUMBER": "#d4f4dd", "EMAIL_ADDRESS": "#d4f4dd",
    "UK_NINO": "#ffe9b3", "GMC": "#f0e0a0", "NMC": "#f0e0a0", "NHS_ODS": "#f0e0a0",
    "LLM_PII": "#e8d6ff",
}

st.set_page_config(page_title="NoteGuard", page_icon="🛡️", layout="wide")


def _bridge_secrets_to_env():
    """Streamlit Cloud exposes config via st.secrets; our engine/LLM client read os.environ.
    Copy the known keys across so secrets configured in the dashboard take effect."""
    import os
    for key in ("PII_SPACY_MODEL", "LLM_ASSURE_API_KEY", "LLM_ASSURE_BASE_URL", "LLM_ASSURE_MODEL"):
        try:
            if key in st.secrets and key not in os.environ:
                os.environ[key] = str(st.secrets[key])
        except Exception:  # no secrets file configured — fine
            break


_bridge_secrets_to_env()


@st.cache_resource(show_spinner="Loading the de-identification engine + sample notes…")
def load_engine():
    detector = build_detector(use_presidio=True)
    try:
        notes = load_notes(limit=50)
    except Exception:
        notes = []
    return detector, notes


def active_detector(base, use_llm: bool):
    """Compose the optional LLM assurance pass onto the base detector when enabled+configured."""
    if use_llm:
        llm = LLMAssurance()
        if llm.is_configured():
            return ComposedDetector(base, llm), True
    return base, False


def highlight(text: str, spans) -> str:
    chosen, last_end = [], -1
    for s in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if s.start >= last_end:
            chosen.append(s)
            last_end = s.end
    out, idx = [], 0
    for s in chosen:
        out.append(html.escape(text[idx:s.start]))
        color = ENTITY_COLORS.get(s.entity_type, "#e0e0e0")
        border = "2px dashed #e67e00" if s.needs_review else "none"
        out.append(
            f'<mark style="background:{color};padding:0 2px;border-radius:3px;border:{border}" '
            f'title="{s.entity_type} ({s.score:.2f}){" ⚠ review" if s.needs_review else ""}'
            f'">{html.escape(text[s.start:s.end])}</mark>'
        )
        idx = s.end
    out.append(html.escape(text[idx:]))
    return "".join(out).replace("\n", "<br>")


def scroll_box(inner_html: str, height: int = 340):
    st.markdown(
        f'<div style="height:{height}px;overflow:auto;border:1px solid #ddd;border-radius:8px;'
        f'padding:12px;font-family:ui-monospace,monospace;font-size:13px;line-height:1.5">{inner_html}</div>',
        unsafe_allow_html=True,
    )


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def render_single(text: str, method: str, detector, person_id: str, note_id: str):
    """Detect → sanitise → audit view for one document, with downloads."""
    result = Pipeline(detector, PseudonymVault()).sanitise(text, method, person_id)

    st.markdown("##### 1) Detected PII")
    scroll_box(highlight(text, result.spans))

    st.markdown(f"##### 2) Sanitised output — `{method}`")
    scroll_box(html.escape(result.sanitised).replace("\n", "<br>"))

    st.markdown("##### 3) Audit log (counts only — no raw values leave the gate)")
    confirmed = [s for s in result.spans if not s.needs_review]
    counts = Counter(s.entity_type for s in confirmed)
    st.dataframe({"entity": list(counts), "auto-removed": list(counts.values())},
                 hide_index=True, use_container_width=True)

    if result.review_items:
        st.warning(
            f"**Human review required — {len(result.review_items)} low-confidence detection(s)**\n\n"
            "These spans were redacted for safety but confidence was below the auto-confirm "
            "threshold (this includes any LLM-assurance hits). An IG analyst should confirm "
            "before the note enters the SDE pool.",
            icon="⚠️",
        )
    else:
        st.success("All detections auto-confirmed (score ≥ threshold). No human review needed.", icon="✅")

    st.markdown("##### 4) Download this de-identified note")
    one = [{"note_id": note_id, "method": method, "sanitised_text": result.sanitised}]
    d1, d2 = st.columns(2)
    d1.download_button("⬇ Download JSON", json.dumps(one, ensure_ascii=False, indent=2),
                       file_name="noteguard_note.json", mime="application/json",
                       use_container_width=True)
    d2.download_button("⬇ Download CSV", pd.DataFrame(one).to_csv(index=False),
                       file_name="noteguard_note.csv", mime="text/csv",
                       use_container_width=True)


def deidentify_rows(records, method: str, detector) -> list[dict]:
    """De-identify many (record_id, text[, person_id]) records with one shared vault
    (patient-consistent). Returns rows of sanitised text only — no PHI."""
    pipe = Pipeline(detector, PseudonymVault())
    rows = []
    for r in records:
        if isinstance(r, tuple):                      # (record_id, text) from the catalog
            rid, text, pid = r[0], r[1], r[0]
        else:                                         # NoteRecord / IngestRecord
            rid = getattr(r, "record_id", None) or getattr(r, "note_id", "")
            pid = getattr(r, "person_id", rid)
            text = r.text
        if not text or not text.strip():
            continue
        rows.append({"record_id": rid, "method": method,
                     "sanitised_text": pipe.sanitise(text, method, pid).sanitised})
    return rows


def download_rows(rows: list[dict], stem: str):
    st.success(f"{len(rows)} records de-identified — ready to download (sanitised text only).")
    e1, e2 = st.columns(2)
    e1.download_button("⬇ Download JSON", json.dumps(rows, ensure_ascii=False, indent=2),
                       file_name=f"{stem}.json", mime="application/json", use_container_width=True)
    e2.download_button("⬇ Download CSV", pd.DataFrame(rows).to_csv(index=False),
                       file_name=f"{stem}.csv", mime="text/csv", use_container_width=True)


st.title("🛡️ NoteGuard — NHS De-Identification Gate")
st.caption("AI detects patient and clinician PII, humans review, audit logs account.")

detector, NOTES = load_engine()

# ----- sidebar: optional LLM assurance toggle -----
with st.sidebar:
    st.header("⚙️ Options")
    use_llm = st.toggle("LLM assurance pass", value=False,
                        help="Adds a free LLM as a recall-oriented safety net over the engine. "
                             "Its hits are flagged for human review, never auto-trusted.")
    if use_llm:
        if LLMAssurance().is_configured():
            st.success("LLM assurance: configured ✓")
        else:
            st.info("Set `LLM_ASSURE_API_KEY` (free Groq/Gemini/HF key) as an env var / Space "
                    "secret to enable. Off until then — the engine runs deterministically.")
    method = st.radio("De-identification", [PSEUDONYM, REDACTION],
                      format_func=lambda m: "Pseudonymise (realistic, patient-consistent)"
                      if m == PSEUDONYM else "Redact ([type] tags)")

det, llm_on = active_detector(detector, use_llm)

tab_try, tab_domain, tab_metrics, tab_gov, tab_trust = st.tabs(
    ["🧹 De-identify your data", "📚 Get data by domain", "📊 Metrics & Leakage",
     "🏛️ Governance", "🤝 Two-Trust sharing"]
)

# ---------------------------------------------------------------- Tab 1: de-identify your data
with tab_try:
    st.info(
        "🔒 **Your data is never stored.** Uploads are processed **in memory only** — no temp files "
        "are written to disk, the original text is never saved, and the re-identification vault never "
        "leaves this session. Only the de-identified result is kept in your browser session cache so "
        "you can download it. This is asserted by an automated test (`tests/test_privacy.py`).",
        icon="🔒",
    )
    source = st.radio("Input", ["Upload a file", "Paste text", "Sample note"], horizontal=True)

    records = None      # batch (CSV) path
    single = None       # (text, person_id, note_id) for the rich single view

    if source == "Upload a file":
        up = st.file_uploader(f"Upload a clinical note or patient file ({', '.join(SUPPORTED)})",
                              type=[s.lstrip(".") for s in SUPPORTED])
        if up is not None:
            data = up.getvalue()
            text_col = None
            if up.name.lower().endswith(".csv"):
                try:
                    cols = csv_columns(data)
                    text_col = st.selectbox("Which column holds the free text?", cols)
                except Exception as e:
                    st.error(f"Could not read CSV header: {e}")
            try:
                recs = records_from_upload(up.name, data, text_col)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                recs = []
            if len(recs) == 1:
                single = (recs[0].text, recs[0].record_id, recs[0].record_id)
            elif len(recs) > 1:
                records = recs
                st.caption(f"{len(recs)} rows found — they'll be de-identified as a batch below.")

    elif source == "Paste text":
        text = st.text_area("Clinical note (messy free-text)", height=200,
                            value="Pt John Smith, NHS no 943 476 5919, DOB 02/03/1981, lives SW1A 1AA. "
                                  "Admitted Manchester Royal Infirmary Ward 9. "
                                  "Reviewed by Dr Lee, GMC 1234567.")
        if text.strip():
            single = (text, "pasted", "pasted")

    else:  # Sample note
        if NOTES:
            idx = st.number_input("Note index", 1, len(NOTES), 1, step=1)
            rec = NOTES[int(idx) - 1]
            single = (rec.text, rec.person_id, rec.note_id)
        else:
            st.info("Sample notes unavailable (dataset not loaded). Try Paste or Upload.")

    if llm_on:
        st.caption("🧠 LLM assurance pass is **on** — extra spans (purple, dashed) are model "
                   "suggestions flagged for human review.")

    if single:
        render_single(single[0], method, det, single[1], single[2])
    elif records:
        if st.button("Prepare de-identified batch", use_container_width=True):
            with st.spinner(f"De-identifying {len(records)} rows…"):
                st.session_state["upload_rows"] = deidentify_rows(records, method, det)
        if st.session_state.get("upload_rows"):
            download_rows(st.session_state["upload_rows"], "noteguard_upload")

# ---------------------------------------------------------------- Tab 2: get data by domain
with tab_domain:
    st.markdown(
        "Pick a clinical domain and download **de-identified** data for analysis. Every record is "
        "run through the same de-identification gate before it can be downloaded."
    )
    src = st.radio("Source", ["NHS synthetic notes (primary)", "External public dataset"],
                   horizontal=True)
    domain = st.selectbox("Clinical domain", DOMAINS)

    if src == "NHS synthetic notes (primary)":
        st.caption("Provenance: **NHS-made** — NHSE synthetic clinical notes. Domain cohorts are derived "
                   "by clinical-concept keyword matching over the note text (high-recall tagging, not a "
                   "validated phenotype).")
        n_pool = st.slider("Notes to scan", 100, 1600, 400, step=100, key="dom_pool")
        n_cap = st.slider("Max cohort size to de-identify", 20, 500, 100, step=20, key="dom_cap")
        if st.button("Build de-identified cohort", use_container_width=True, key="dom_nhs_btn"):
            with st.spinner("Loading notes, filtering by domain, de-identifying…"):
                pool = load_notes(limit=n_pool)
                cohort = filter_by_domain(pool, domain, limit=n_cap)
                counts = domain_counts(pool)
                rows = deidentify_rows(cohort, method, det)
                st.session_state["dom_rows"] = rows
                st.session_state["dom_counts"] = counts
        if st.session_state.get("dom_counts"):
            st.caption("Cohort sizes in the scanned pool (overlap = comorbidity): "
                       + " · ".join(f"{d}: {c}" for d, c in st.session_state["dom_counts"].items()))
        if st.session_state.get("dom_rows") is not None:
            rows = st.session_state["dom_rows"]
            if rows:
                download_rows(rows, f"noteguard_{domain.replace(' ', '_')}_nhs")
            else:
                st.warning("No notes matched this domain in the scanned pool — try scanning more notes.")

    else:  # External public dataset
        loadable = [e for e in all_entries() if e.loadable]
        linkonly = [e for e in all_entries() if not e.loadable]
        labels = {e.name: e for e in loadable}
        choice = st.selectbox("Public dataset", list(labels))
        entry = labels[choice]
        st.caption(f"Provenance: {entry.provenance}  ·  Licence: {entry.license}  ·  [dataset card]({entry.url})")
        st.warning("External datasets are **not NHS data**; provenance is labelled honestly. "
                   "They are de-identified by the same gate before download.", icon="ℹ️")
        n_scan = st.slider("Rows to fetch & scan", 50, 500, 150, step=50, key="ext_scan")
        if st.button("Fetch, filter & de-identify", use_container_width=True, key="ext_btn"):
            with st.spinner(f"Streaming {entry.name}, filtering for '{domain}', de-identifying…"):
                try:
                    raw = entry.loader(n_scan)
                except Exception as e:
                    st.error(f"Could not load dataset: {e}")
                    raw = []
                matched = [(rid, txt) for rid, txt in raw if note_matches_domain(txt, domain)]
                st.session_state["ext_rows"] = deidentify_rows(matched, method, det)
        if st.session_state.get("ext_rows") is not None:
            rows = st.session_state["ext_rows"]
            if rows:
                download_rows(rows, f"noteguard_{domain.replace(' ', '_')}_{entry.key}")
            else:
                st.warning("No rows matched this domain in the fetched sample — fetch more rows.")
        if linkonly:
            with st.expander("More public datasets (reference / link-only)"):
                for e in linkonly:
                    st.markdown(f"- **[{e.name}]({e.url})** — {e.provenance} · {e.license}")

# ---------------------------------------------------------------- Tab 3: metrics
with tab_metrics:
    st.markdown(
        "**Leakage rate** is the headline SDE gate metric: after sanitisation, what fraction of known "
        "patient identifiers still appear in the output text? Ground truth is **joined from the "
        "dataset's structured tables** — every note's identifiers are known in advance, so this is "
        "a real, measurable re-identification risk, not an estimate."
    )
    st.markdown(
        "> **Target for SDE admission:** leakage = 0. Any note with a non-zero leakage score "
        "must be held back from the shared pool until reviewed."
    )
    data = load_json(RESULTS)
    n = st.slider("Notes to evaluate (live run)", 50, 1000, 200, step=50)
    if st.button("▶ Run evaluation"):
        with st.spinner("Evaluating…"):
            recs = load_notes(limit=n)
            res = evaluate(recs, det, PSEUDONYM).to_dict()
            data = {res["detector"]: res}
            RESULTS.write_text(json.dumps(data, indent=2), encoding="utf-8")

    if data:
        name = "presidio+rules" if "presidio+rules" in data else next(iter(data))
        r = data[name]
        leak = r["leakage"]["leakage_rate_pct"]
        m1, m2, m3 = st.columns(3)
        m1.metric("Identifiers removed", f"{100 - leak:.1f}%", help="Known PII not present in output")
        m2.metric("Residual leakage", f"{leak:.2f}%",
                  help="Fraction of known PII surviving sanitisation — target: 0%")
        m3.metric("Notes evaluated", r["notes_evaluated"])
        st.markdown("##### Detection recall by entity type")
        pe = r["detection"]["per_entity"]
        st.dataframe(
            {"entity": list(pe),
             "recall": [f"{m['recall']:.0%}" for m in pe.values()],
             "precision": [f"{m['precision']:.0%}" for m in pe.values()],
             "support": [m["support"] for m in pe.values()]},
            hide_index=True, use_container_width=True,
        )
        st.caption(
            "Precision is a conservative lower bound. Clinician names and unlisted locations "
            "detected correctly are counted as false positives."
        )
    else:
        st.info("No metrics yet — click **Run evaluation** above.")

    st.divider()
    st.markdown("### Data-quality report")
    st.caption("Routine quality checks every data wrangler runs *before* modelling — completeness, "
               "encoding integrity, and key-field validity.")
    if st.button("▶ Run data-quality checks"):
        with st.spinner("Profiling the dataset…"):
            q = data_quality_report(load_notes(limit=n)).to_dict()
            st.session_state["quality"] = q
    q = st.session_state.get("quality")
    if q:
        qa, qb, qc = st.columns(3)
        qa.metric("Notes profiled", q["notes_total"])
        qb.metric("Empty notes", f"{q['empty_rate_pct']:.1f}%")
        qc.metric("Ground-truth coverage", f"{q['ground_truth_coverage_pct']:.1f}%")
        qd, qe, qf = st.columns(3)
        qd.metric("Mojibake-affected", f"{q['mojibake_rate_pct']:.1f}%",
                  help="Residual double-encoding after _fix_mojibake remediation")
        qe.metric("Median note length", f"{q['median_chars']:.0f} chars")
        qf.metric("NHS-number mod-11 pass", f"{q['nhs_checksum_pass_pct']:.1f}%",
                  help="Low is EXPECTED: the synthetic set uses 9-digit numbers with no valid "
                       "checksum — which is why detection is context-anchored, not checksum-only.")

# ---------------------------------------------------------------- Tab 4: governance
with tab_gov:
    st.markdown("### NHS Five Safes — How NoteGuard maps")
    st.markdown(
        "The Five Safes framework is the standard NHS governance model for data access. "
        "NoteGuard is designed as the **Safe Data** layer that makes the other four safes cheaper to achieve."
    )

    five_safes = [
        ("✅ Safe Data",
         "DAPB1523 / ICO standard",
         "Names · NHS number · DOB · postcode → outward code · "
         "GMC/NMC clinician IDs · ODS org codes · record UUIDs · site names. "
         "NRP (nationality/religion) always redacted, never pseudonymised (UK GDPR Art. 9)."),
        ("✅ Safe Settings",
         "Processing inside the Trust",
         "Detection and sanitisation run locally. Raw notes, vault (re-id key), and CSVs "
         "are gitignored and never leave the Trust boundary. Only de-identified text is exported."),
        ("✅ Safe Outputs",
         "Leakage-gated release",
         "Residual leakage is measured against ground-truth identifiers before any note enters "
         "the SDE pool. Target: 0 known identifiers surviving sanitisation. "
         "Low-confidence spans are held in a human review queue rather than auto-released."),
        ("⚠️ Safe People",
         "Human-in-the-loop required",
         "The re-identification vault stays Trust-local. Pseudonymised data is still personal "
         "data under UK GDPR (stated honestly — no over-claim of anonymisation). "
         "An IG analyst reviews low-confidence detections before pool admission."),
        ("⚠️ Safe Projects",
         "Project-level approval not covered here",
         "NoteGuard provides the technical de-identification layer; "
         "project-level data access approval (Data Access Request / DARS) remains a Trust process."),
    ]
    for safe, standard, detail in five_safes:
        with st.expander(f"**{safe}** — {standard}"):
            st.markdown(detail)

    st.divider()
    st.markdown("### Caldicott Principles — where NoteGuard helps")
    st.markdown(
        "The 8 Caldicott Principles govern the use of confidential patient information in health "
        "and care. NoteGuard directly supports the data-minimisation principles:"
    )
    caldicott = [
        ("3 — Use the minimum necessary confidential information",
         "De-identification removes direct identifiers so downstream analysis uses the minimum PII needed."),
        ("4 — Access on a strict need-to-know basis",
         "Raw notes + re-id vault stay Trust-local; only de-identified text is shared."),
        ("5 — Everyone must be aware of their responsibilities",
         "Per-note audit log + human review queue make every removal accountable."),
        ("7 — The duty to share can be as important as the duty to protect",
         "By making data safe to share, NoteGuard enables lawful research/federation rather than blocking it."),
    ]
    for principle, detail in caldicott:
        with st.expander(f"**Principle {principle}**"):
            st.markdown(detail)

    st.divider()
    st.markdown("### Data Protection Act 2018 / UK GDPR")
    st.markdown(
        "- **Pseudonymised data is still personal data** (UK GDPR Recital 26) — NoteGuard states this "
        "honestly and keeps the re-identification vault Trust-local; it does **not** over-claim anonymisation.\n"
        "- **Data minimisation (Art. 5(1)(c))** and **storage limitation (Art. 5(1)(e))** — direct "
        "identifiers are stripped, and in the live demo uploads are processed in memory only and never stored.\n"
        "- **Special category data (Art. 9)** — nationality/religion are always redacted, never "
        "pseudonymised, given the heightened risk."
    )

    st.divider()
    st.markdown("### Adoption path — NHS SDE on-ramp")
    st.markdown("""
```
NHS Trust (raw notes)
    │
    ▼  NoteGuard gate (runs inside Trust)
    │   clean → detect PII → sanitise → leakage check
    │   low-confidence spans → IG analyst review queue
    │
    ▼  de-identified notes + audit log  (no PHI crosses boundary)
    │
    ▼  NHS Secure Data Environment / Federated Data Platform pool
    │   (same model as OpenSAFELY: code comes to data, data never leaves)
    │
    ▼  Federated AI training
        each Trust trains locally; only model gradients are shared
```
    """)

# ---------------------------------------------------------------- Tab 5: two-trust
with tab_trust:
    st.markdown(
        "### Sanitise-at-source: two Trusts sharing without sharing\n\n"
        "Each Trust runs the NoteGuard gate locally — raw notes and the re-identification vault "
        "**never leave**. Only de-identified text and a content-free audit manifest go into the "
        "shared SDE pool. This is the same privacy model behind OpenSAFELY and the NHS Federated "
        "Data Platform: *code comes to the data, data never leaves*."
    )
    summary = load_json(OUT_DIR / "trust_demo_summary.json")
    if st.button("▶ Run two-Trust demo"):
        from src.trust_demo import main as run_trust
        with st.spinner("Sanitising at each Trust…"):
            run_trust()
        summary = load_json(OUT_DIR / "trust_demo_summary.json")

    if summary:
        cols = st.columns(len(summary["trusts"]) + 1)
        for col, t in zip(cols, summary["trusts"], strict=False):
            with col:
                st.markdown(f"#### 🏥 {t['trust'].split('(')[0].strip()}")
                st.metric("Notes de-identified", t["notes_deidentified"])
                st.metric("Raw records shared", t["raw_records_shared"])
                st.metric("Residual leaks", t["residual_leaks"])
                st.caption("🔒 raw notes + vault stay local")
        with cols[-1]:
            st.markdown("#### 🟢 Shared SDE pool")
            st.metric("De-identified notes", summary["shared_pool_size"])
            st.metric("Raw records shared", summary["raw_records_shared"])
            st.metric("Total residual leaks", summary["total_residual_leaks"])
            st.caption("→ ready for federated AI training")
    else:
        st.info("Click **Run two-Trust demo** above.")

# ---------------------------------------------------------------- Footer (all tabs)
st.divider()
st.caption(
    "Live demo for the **FLock Sovereign AI Challenge** at the Encode Vibe Coding Hackathon, "
    "hosted by Encode Hub."
)
