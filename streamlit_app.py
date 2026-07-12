"""NoteGuard — demo UI.

Run from the repo root:  streamlit run streamlit_app.py

Tabs:
  1. De-identify your data — upload a note/CSV/PDF, get de-identified data back. Nothing is stored.
  2. Get data by domain   — pick a clinical domain, download de-identified data (NHS + public sources).
  3. How safe is it?      — the missed-identifier (false-negative) evidence, in plain English, with a
                            live re-check that runs on this very deployment.

Built on the NoteGuard package (src/) — pluggable detectors + patient-consistent transforms.
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from pathlib import Path

import altair as alt
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
from src.transform import PSEUDONYM, REDACTION, PseudonymVault, redaction_label  # noqa: E402

ENTITY_COLORS = {
    "PERSON": "#ffd6e0", "UK_NHS": "#ffe9b3", "DATE_TIME": "#d4f4dd", "UK_POSTCODE": "#cfe8ff",
    "LOCATION": "#cfe8ff", "ORGANIZATION": "#cfe8ff", "RECORD_ID": "#ffd9c2",
    "PHONE_NUMBER": "#d4f4dd", "EMAIL_ADDRESS": "#d4f4dd",
    "UK_NINO": "#ffe9b3", "GMC": "#f0e0a0", "NMC": "#f0e0a0", "NHS_ODS": "#f0e0a0",
    "LLM_PII": "#e8d6ff",
}

# NHS-brand categorical palette for the donut chart
NHS_PALETTE = ["#005EB8", "#0072CE", "#41B6E6", "#00A499", "#007F3B",
               "#330072", "#7C2855", "#ED8B00", "#8A1538"]

NHS_BLUE, NHS_RED, NHS_GREEN = "#005EB8", "#DA291C", "#007f3b"

# Lay-reader names for entity types on the safety tab (plural, no jargon)
FRIENDLY_TYPE = {
    "PERSON": "Names", "UK_NHS": "NHS numbers", "DATE_TIME": "Dates of birth",
    "UK_POSTCODE": "Postcodes", "LOCATION": "Places", "GMC": "GMC numbers",
    "NMC": "NMC numbers", "NHS_ODS": "ODS codes", "RECORD_ID": "Record IDs",
    "PHONE_NUMBER": "Phone numbers", "EMAIL_ADDRESS": "Email addresses",
    "UK_NINO": "NI numbers", "URL": "Web addresses",
}

SNAPSHOT_PATH = REPO / "assets" / "metrics_snapshot.json"

st.set_page_config(page_title="NoteGuard", layout="wide")


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


# External catalog sets are streamed, not downloaded whole — this caps the fetch.
EXTERNAL_FETCH_ROWS = 500


@st.cache_resource(show_spinner="Loading the full NHS synthetic notes set…")
def load_all_notes():
    return load_notes()


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
            f'title="{s.entity_type} ({s.score:.2f}){" — review" if s.needs_review else ""}'
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


def render_single(text: str, method: str, detector, person_id: str, note_id: str):
    """Detect -> sanitise -> audit view for one document, with downloads."""
    result = Pipeline(detector, PseudonymVault()).sanitise(text, method, person_id)

    st.markdown("##### 1) Detected PII")
    scroll_box(highlight(text, result.spans))

    st.markdown(f"##### 2) Sanitised output — `{method}`")
    scroll_box(html.escape(result.sanitised).replace("\n", "<br>"))

    st.markdown("##### 3) Identifiers removed")
    pii_chart(Counter(s.entity_type for s in result.spans))

    if result.review_items:
        st.warning(
            f"**Human review suggested — {len(result.review_items)} low-confidence detection(s)**\n\n"
            "These spans were removed for safety but confidence was below the auto-confirm "
            "threshold (this includes any LLM-assurance hits). A reviewer should confirm them."
        )
    else:
        st.success("All detections auto-confirmed (score >= threshold). No human review needed.")

    with st.expander("Review what changed before you download", expanded=False):
        if result.replacements:
            st.dataframe(
                [{"type": redaction_label(r.entity_type), "original": r.original,
                  "replacement": r.replacement} for r in result.replacements],
                hide_index=True, use_container_width=True,
            )
            st.caption("Shown only in your browser session — the original text is never stored.")
        else:
            st.caption("No identifiers were found, so nothing was changed.")

    st.markdown("##### 4) Download this de-identified note")
    one = [{"note_id": note_id, "method": method, "sanitised_text": result.sanitised}]
    d1, d2 = st.columns(2)
    d1.download_button("Download JSON", json.dumps(one, ensure_ascii=False, indent=2),
                       file_name="noteguard_note.json", mime="application/json",
                       use_container_width=True)
    d2.download_button("Download CSV", pd.DataFrame(one).to_csv(index=False),
                       file_name="noteguard_note.csv", mime="text/csv",
                       use_container_width=True)


def deidentify_rows(records, method: str, detector) -> tuple[list[dict], Counter]:
    """De-identify many (record_id, text[, person_id]) records with one shared vault
    (patient-consistent). Returns (rows of sanitised text only — no PHI, counts by type)."""
    pipe = Pipeline(detector, PseudonymVault())
    rows: list[dict] = []
    counts: Counter = Counter()
    for r in records:
        if isinstance(r, tuple):                      # (record_id, text) from the catalog
            rid, text, pid = r[0], r[1], r[0]
        else:                                         # NoteRecord / IngestRecord
            rid = getattr(r, "record_id", None) or getattr(r, "note_id", "")
            pid = getattr(r, "person_id", rid)
            text = r.text
        if not text or not text.strip():
            continue
        res = pipe.sanitise(text, method, pid)
        rows.append({"record_id": rid, "method": method, "sanitised_text": res.sanitised})
        counts.update(s.entity_type for s in res.spans)
    return rows, counts


def pii_chart(counts: Counter):
    """Human-friendly donut chart of how many identifiers were detected, by type."""
    total = sum(counts.values())
    if not total:
        st.info("No identifiers detected.")
        return
    st.markdown(f"**{total} identifier{'s' if total != 1 else ''} detected**")
    df = pd.DataFrame({"type": [redaction_label(e) for e in counts],
                       "count": list(counts.values())})
    chart = (
        alt.Chart(df)
        .mark_arc(innerRadius=65, stroke="#ffffff", strokeWidth=2)
        .encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("type:N", scale=alt.Scale(range=NHS_PALETTE),
                            legend=alt.Legend(title="Identifier type")),
            tooltip=[alt.Tooltip("type:N", title="Type"),
                     alt.Tooltip("count:Q", title="Detected")],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)


def render_batch_result(rows: list[dict], counts: Counter, stem: str):
    """Chart + reviewable preview + downloads for a de-identified batch."""
    pii_chart(counts)
    with st.expander("Review the de-identified output before you download (first 10 rows)"):
        st.dataframe(pd.DataFrame(rows).head(10), hide_index=True, use_container_width=True)
    download_rows(rows, stem)


def download_rows(rows: list[dict], stem: str):
    st.success(f"{len(rows)} records de-identified — ready to download (sanitised text only).")
    e1, e2 = st.columns(2)
    e1.download_button("Download JSON", json.dumps(rows, ensure_ascii=False, indent=2),
                       file_name=f"{stem}.json", mime="application/json", use_container_width=True)
    e2.download_button("Download CSV", pd.DataFrame(rows).to_csv(index=False),
                       file_name=f"{stem}.csv", mime="text/csv", use_container_width=True)


# ---------------------------------------------------------------- safety-tab components
@st.cache_data
def load_snapshot() -> dict | None:
    """Published evaluation snapshot (aggregate numbers only — no note text).
    Regenerate with: python tests/run_eval.py --compare --snapshot"""
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def safety_tiles(leak: dict):
    """The headline, as three numbers a non-specialist can read."""
    known = leak["total_known_pii_occurrences"]
    missed = leak["residual_leaks_after_sanitisation"]
    hidden_pct = 100 - leak["leakage_rate_pct"]
    missed_color = NHS_RED if missed else NHS_GREEN
    st.markdown(
        f"""
        <div class="stat-grid">
          <div class="stat-card"><div class="num" style="color:{NHS_BLUE}">{known:,}</div>
            <p>identifiers we knew were hidden in the notes</p></div>
          <div class="stat-card"><div class="num" style="color:{missed_color}">{missed:,}</div>
            <p>still visible after de-identification — the misses we count</p></div>
          <div class="stat-card"><div class="num" style="color:{NHS_GREEN}">{hidden_pct:.1f}%</div>
            <p>successfully removed or disguised</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def caught_missed_chart(per_entity: dict):
    """Per identifier type at the detection stage: caught (blue) vs missed (red)."""
    rows = []
    for et, m in per_entity.items():
        support = m.get("support", 0)
        if not support:
            continue
        caught = m.get("caught", round(m.get("recall", 0) * support))
        rows.append({"type": FRIENDLY_TYPE.get(et, redaction_label(et)),
                     "status": "Caught", "count": caught, "support": support})
        rows.append({"type": FRIENDLY_TYPE.get(et, redaction_label(et)),
                     "status": "Missed", "count": support - caught, "support": support})
    if not rows:
        st.info("No known identifiers in this sample.")
        return
    df = pd.DataFrame(rows)
    order = (df.groupby("type")["support"].first().sort_values(ascending=False).index.tolist())
    chart = (
        alt.Chart(df)
        .mark_bar(height=22, stroke="#ffffff", strokeWidth=2)
        .encode(
            y=alt.Y("type:N", sort=order, title=None),
            x=alt.X("count:Q", title="Known identifier occurrences"),
            color=alt.Color("status:N",
                            scale=alt.Scale(domain=["Caught", "Missed"],
                                            range=[NHS_BLUE, NHS_RED]),
                            legend=alt.Legend(title=None, orient="top")),
            order=alt.Order("status:N", sort="ascending"),
            tooltip=[alt.Tooltip("type:N", title="Identifier type"),
                     alt.Tooltip("status:N", title="At detection"),
                     alt.Tooltip("count:Q", title="Occurrences")],
        )
        .properties(height=32 * df["type"].nunique() + 40)
    )
    st.altair_chart(chart, use_container_width=True)


st.markdown(
    """
    <style>
      .nhs-header {
        background:#005EB8; padding:18px 24px; border-radius:6px;
        font-family: Arial, Helvetica, sans-serif;
      }
      .nhs-header .brand { color:#ffffff; font-weight:700; font-size:32px; letter-spacing:.3px; }
      .nhs-tagline { color:#212b32; font-size:18px; font-style:italic; margin:16px 0 2px; }
      .nhs-sub { color:#4c6272; font-size:14px; margin-bottom:4px; }
      /* NHS green action buttons */
      div.stButton > button, div.stDownloadButton > button {
        background:#007f3b; color:#ffffff; border:0; border-radius:4px; font-weight:600;
      }
      div.stButton > button:hover, div.stDownloadButton > button:hover {
        background:#00401e; color:#ffffff;
      }
      /* "How it works" step cards (bento-style) */
      .how-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:18px 0 6px; }
      .step-card { background:#f0f4f5; border-radius:12px; padding:18px; border:1px solid #e8edee; }
      .step-card .num { color:#005EB8; font-weight:700; font-size:12px; letter-spacing:.6px; }
      .step-card h4 { margin:8px 0 4px; font-size:16px; color:#212b32; }
      .step-card p { margin:0; font-size:13.5px; color:#4c6272; line-height:1.45; }
      .step-card svg { width:28px; height:28px; stroke:#005EB8; fill:none; stroke-width:2;
                       stroke-linecap:round; stroke-linejoin:round; }
      /* Safety-tab stat tiles + mistake-type cards */
      .stat-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:10px 0 6px; }
      .stat-card { background:#f0f4f5; border-radius:12px; padding:18px; border:1px solid #e8edee;
                   text-align:center; }
      .stat-card .num { font-size:40px; font-weight:700; line-height:1.1; }
      .stat-card p { margin:6px 0 0; font-size:13.5px; color:#4c6272; line-height:1.4; }
      .mistake-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:14px; margin:10px 0 6px; }
      .mistake-card { border-radius:12px; padding:16px 18px; border:1px solid #e8edee; }
      .mistake-card h4 { margin:0 0 6px; font-size:15.5px; color:#212b32; }
      .mistake-card p { margin:0; font-size:13.5px; color:#4c6272; line-height:1.5; }
      .platform-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:12px 0 6px; }
      .platform-card { background:#ffffff; border:1px solid #d8dde0; border-radius:12px; padding:16px 18px; }
      .platform-card .where { color:#005EB8; font-weight:700; font-size:12px; letter-spacing:.6px; }
      .platform-card h4 { margin:8px 0 4px; font-size:15.5px; color:#212b32; }
      .platform-card p { margin:0; font-size:13px; color:#4c6272; line-height:1.5; }
      @media (max-width:800px){ .how-grid, .stat-grid, .mistake-grid, .platform-grid
                                { grid-template-columns:1fr; } }
    </style>
    <div class="nhs-header"><span class="brand">NoteGuard</span></div>
    <p class="nhs-tagline">Every clinical note is someone's story — NoteGuard keeps the person safe,
    so their data can still help others.</p>
    <p class="nhs-sub">Detect and remove patient and clinician identifiers from clinical text,
    so data can be shared and analysed safely.</p>
    """,
    unsafe_allow_html=True,
)

detector, NOTES = load_engine()

# ----- sidebar: de-identification mode + optional LLM assurance toggle -----
with st.sidebar:
    st.header("Options")
    from urllib.parse import urlparse

    llm_cfg = LLMAssurance()
    llm_host = urlparse(llm_cfg.base_url).netloc or llm_cfg.base_url
    use_llm = st.toggle("AI double-check", value=False,
                        help=f"A free external AI re-reads the text and flags anything the engine "
                             f"may have missed. Model: `{llm_cfg.model}` served by {llm_host}. "
                             "Its suggestions are marked for human review, never auto-trusted.")
    if use_llm:
        if llm_cfg.is_configured():
            st.success(f"AI double-check: ready — `{llm_cfg.model}` via {llm_host}")
        else:
            st.info("Set `LLM_ASSURE_API_KEY` (a free key) as a secret to enable. "
                    "Off until then — the engine runs deterministically.")
    method = st.radio("De-identification", [REDACTION, PSEUDONYM],
                      format_func=lambda m: "Redact ([type] tags)" if m == REDACTION
                      else "Pseudonymise (realistic, patient-consistent)")

det, llm_on = active_detector(detector, use_llm)

# ----- onboarding: how it works -----
st.markdown(
    """
    <div class="how-grid">
      <div class="step-card">
        <svg viewBox="0 0 24 24"><path d="M12 16V4M6 10l6-6 6 6"/><path d="M4 20h16"/></svg>
        <div class="num">STEP 1</div>
        <h4>Add your data</h4>
        <p>Paste a clinical note, upload a .txt / .csv / .pdf, or try a sample — or pick a clinical
        domain in the second tab.</p>
      </div>
      <div class="step-card">
        <svg viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 4-3 7-7 8-4-1-7-4-7-8V6z"/><path d="M9 12l2 2 4-4"/></svg>
        <div class="num">STEP 2</div>
        <h4>We find &amp; remove identifiers</h4>
        <p>Transparent rules plus a clinical NER model detect names, NHS numbers, dates and more, then
        redact or pseudonymise them — all in memory.</p>
      </div>
      <div class="step-card">
        <svg viewBox="0 0 24 24"><path d="M12 4v12M6 10l6 6 6-6"/><path d="M4 20h16"/></svg>
        <div class="num">STEP 3</div>
        <h4>Review &amp; download</h4>
        <p>See what was detected on a chart, review every change, then download the de-identified data.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("What is the optional AI double-check?"):
    st.markdown(
        "NoteGuard removes identifiers with transparent rules and a clinical NER model. You can "
        "optionally switch on the **AI double-check** (toggle in the left sidebar): a free external "
        "AI model re-reads the text and flags anything the engine might have missed.\n\n"
        "- It is a **safety net, not the decision-maker** — its suggestions are always marked for human "
        "review, never auto-trusted.\n"
        "- It is **off by default** and stays inert unless a free API key is configured.\n"
        "- Your text is sent to the external model **only while the toggle is on**.\n\n"
        f"The model in use is shown in the sidebar — currently `{LLMAssurance().model}` on an "
        "OpenAI-compatible endpoint (default: Meta Llama 3.3 70B served by Groq's free tier; "
        "override with `LLM_ASSURE_MODEL` / `LLM_ASSURE_BASE_URL`)."
    )

tab_try, tab_domain, tab_safety = st.tabs(
    ["De-identify your data", "Get data by domain", "How safe is it?"])

# ---------------------------------------------------------------- Tab 1: de-identify your data
with tab_try:
    st.info("Files are processed in memory and never stored — only the de-identified result is returned.")
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
        st.caption("AI double-check is on — extra spans (purple, dashed) are AI "
                   "suggestions flagged for human review.")

    if single:
        render_single(single[0], method, det, single[1], single[2])
    elif records:
        if st.button("Prepare de-identified batch", use_container_width=True):
            with st.spinner(f"De-identifying {len(records)} rows…"):
                st.session_state["upload_rows"] = deidentify_rows(records, method, det)
        if st.session_state.get("upload_rows"):
            rows, counts = st.session_state["upload_rows"]
            render_batch_result(rows, counts, "noteguard_upload")

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
        if st.button("Build de-identified cohort", use_container_width=True, key="dom_nhs_btn"):
            with st.spinner("Scanning all notes for the domain and de-identifying the full cohort…"):
                pool = load_all_notes()
                cohort = filter_by_domain(pool, domain)
                st.session_state["dom_cohort_counts"] = domain_counts(pool)
                st.session_state["dom_rows"] = deidentify_rows(cohort, method, det)
        if st.session_state.get("dom_cohort_counts"):
            st.caption("Cohort sizes across all notes (overlap = comorbidity): "
                       + " · ".join(f"{d}: {c}" for d, c in st.session_state["dom_cohort_counts"].items()))
        if st.session_state.get("dom_rows") is not None:
            rows, counts = st.session_state["dom_rows"]
            if rows:
                render_batch_result(rows, counts, f"noteguard_{domain.replace(' ', '_')}_nhs")
            else:
                st.warning("No notes matched this domain.")

    else:  # External public dataset
        loadable = [e for e in all_entries() if e.loadable]
        linkonly = [e for e in all_entries() if not e.loadable]
        labels = {e.name: e for e in loadable}
        choice = st.selectbox("Public dataset", list(labels))
        entry = labels[choice]
        st.caption(f"Provenance: {entry.provenance}  ·  Licence: {entry.license}  ·  [dataset card]({entry.url})")
        st.warning("External datasets are **not NHS data**; provenance is labelled honestly. "
                   "They are de-identified by the same gate before download.")
        if st.button("Fetch, filter & de-identify", use_container_width=True, key="ext_btn"):
            with st.spinner(f"Streaming {entry.name} (first {EXTERNAL_FETCH_ROWS} rows), "
                            f"filtering for '{domain}', de-identifying…"):
                try:
                    raw = entry.loader(EXTERNAL_FETCH_ROWS)
                except Exception as e:
                    st.error(f"Could not load dataset: {e}")
                    raw = []
                matched = [(rid, txt) for rid, txt in raw if note_matches_domain(txt, domain)]
                st.session_state["ext_rows"] = deidentify_rows(matched, method, det)
        if st.session_state.get("ext_rows") is not None:
            rows, counts = st.session_state["ext_rows"]
            if rows:
                render_batch_result(rows, counts, f"noteguard_{domain.replace(' ', '_')}_{entry.key}")
            else:
                st.warning(f"No rows matched this domain in the first {EXTERNAL_FETCH_ROWS} rows.")
        if linkonly:
            with st.expander("More public datasets (reference / link-only)"):
                for e in linkonly:
                    st.markdown(f"- **[{e.name}]({e.url})** — {e.provenance} · {e.license}")

# ---------------------------------------------------------------- Tab 3: how safe is it?
with tab_safety:
    st.markdown(
        "For a de-identification tool the question that matters most is not *\"how accurate is it?\"* "
        "— it is **\"what did it miss?\"** A tool can look impressive and still let one real name "
        "slip through. So the number we hold ourselves to is the **miss rate**: of the identifiers we "
        "*know* are in the notes, how many are still visible after de-identification?"
    )
    st.markdown(
        """
        <div class="mistake-grid">
          <div class="mistake-card" style="background:#fdf1f0;border-color:#f3c8c4;">
            <h4>A missed identifier — the mistake we count</h4>
            <p>A real name or NHS number stays visible in the output (a <em>false negative</em>).
            This is a privacy risk, so we measure it, publish it, and design the engine to keep it
            as close to zero as possible.</p>
          </div>
          <div class="mistake-card" style="background:#eef5f0;border-color:#c5ddcd;">
            <h4>Over-removal — the mistake we accept</h4>
            <p>A harmless word gets redacted by mistake (a <em>false positive</em>). That costs a
            little data quality but harms no one — a fair trade for fewer misses.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    snapshot = load_snapshot()
    if snapshot is None:
        st.warning("No published snapshot found (assets/metrics_snapshot.json). "
                   "Generate one with `python tests/run_eval.py --compare --snapshot`, "
                   "or use the live check below.")
    else:
        meta = snapshot.get("_meta", {})
        shipping = snapshot.get("presidio+rules") or next(
            (v for k, v in snapshot.items() if not k.startswith("_")), None)

        st.markdown("#### The test, in one sentence")
        st.markdown(
            f"We took **{meta.get('notes_evaluated', '?')} synthetic NHS notes** where every "
            "identifier is already known (the dataset keeps them in structured tables), ran "
            "NoteGuard, and then checked the output for every known identifier — counting each "
            "one still visible as a **miss**."
        )
        if shipping:
            safety_tiles(shipping["leakage"])
        st.caption(
            f"Measured on {meta.get('generated', '?')} · dataset: {meta.get('dataset', '?')} "
            f"(synthetic — no real patients) · spaCy model: {meta.get('spacy_model', '?')} · "
            f"transform: {meta.get('transform', '?')}. "
            "Reproduce with `python tests/run_eval.py --compare`."
        )

        if shipping:
            st.markdown("#### What gets caught, what gets missed — by identifier type")
            st.markdown(
                "At the *detection* stage, occurrence by occurrence (full engine). Missing a name "
                "once here does not always mean it leaks — the final-output check above is the "
                "authoritative privacy number — but this shows where the remaining risk lives:"
            )
            caught_missed_chart(shipping["detection"]["per_entity"])

    with st.expander("Honest caveats — read before quoting these numbers"):
        st.markdown(
            "- **The notes are synthetic** (NHSE-published test data). No real patient data is used "
            "or needed for this evaluation.\n"
            "- **The known-identifier list comes from the dataset's structured tables**, so the miss "
            "rate and recall are sound. Precision is a conservative lower bound: correctly removing "
            "a clinician's name that is *not* in the tables counts against us as over-removal.\n"
            "- **Low-confidence detections are redacted anyway** and flagged for human review — the "
            "engine fails safe.\n"
            "- The published snapshot was measured with the full-size model. A lighter deployment "
            "(like this free-tier demo) may run the small model — use the live check below to "
            "measure *this* deployment rather than trust the snapshot."
        )

    st.markdown("#### Don't take our word for it — re-run the check here")
    st.markdown(
        "This runs the same evaluation on the deployment you are using right now, with the model "
        "it actually has loaded. Aggregate numbers only — no note text is shown or stored."
    )
    n_eval = st.slider("Notes to test", 50, 300, 100, step=50, key="live_eval_n")
    if st.button("Run the live check", use_container_width=True, key="live_eval_btn"):
        with st.spinner(f"De-identifying {n_eval} notes and counting misses…"):
            try:
                recs = load_notes(limit=n_eval)
                live = evaluate(recs, detector, REDACTION)  # deterministic engine, no LLM
                st.session_state["live_eval"] = live.to_dict()
            except Exception as e:
                st.error(f"Could not run the live check (dataset unavailable?): {e}")
    if st.session_state.get("live_eval"):
        live = st.session_state["live_eval"]
        model = getattr(detector, "spacy_model", None)
        st.caption(f"Live result from this deployment — detector: {live.get('detector', '?')}"
                   + (f" · spaCy model: {model}" if model else "") + " · transform: redaction.")
        safety_tiles(live["leakage"])
        caught_missed_chart(live["detection"]["per_entity"])

# ---------------------------------------------------------------- runs where the NHS works
st.markdown("---")
st.markdown("#### Built to run where NHS teams already work")
st.markdown(
    "This public demo is hosted on Streamlit so anyone can try it at zero cost — but the engine is "
    "a plain, pip-installable Python package with no service dependencies, so the same pipeline "
    "drops into the platforms NHS analysts already use:"
)
st.markdown(
    """
    <div class="platform-grid">
      <div class="platform-card">
        <div class="where">MICROSOFT FABRIC / AZURE DATABRICKS</div>
        <h4>Lakehouse notebook</h4>
        <p>A ready-to-run notebook de-identifies a lakehouse table in place —
        <a href="https://github.com/yumi-h-1/Automatic-PII-preprocessing-tool/blob/main/integrations/fabric_deidentify.ipynb">
        integrations/fabric_deidentify.ipynb</a>.</p>
      </div>
      <div class="platform-card">
        <div class="where">PALANTIR FOUNDRY (FDP)</div>
        <h4>Foundry transform</h4>
        <p>The same pipeline as a Foundry code-repository transform, for the NHS Federated Data
        Platform —
        <a href="https://github.com/yumi-h-1/Automatic-PII-preprocessing-tool/blob/main/integrations/foundry_transform.py">
        integrations/foundry_transform.py</a>.</p>
      </div>
      <div class="platform-card">
        <div class="where">NHS SECURE DATA ENVIRONMENTS</div>
        <h4>Sanitise at source</h4>
        <p>Runs inside a Trust's own governance boundary so only de-identified text leaves — the
        platform notes are in
        <a href="https://github.com/yumi-h-1/Automatic-PII-preprocessing-tool/blob/main/docs/NHS_PLATFORMS.md">
        docs/NHS_PLATFORMS.md</a>.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
