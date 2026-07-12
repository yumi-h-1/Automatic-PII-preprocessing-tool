"""NoteGuard as a Palantir Foundry transform — for the NHS Federated Data Platform.

The FDP is built on Palantir Foundry, where pipeline steps live in a Code Repository as
``transforms-python``. This file shows the whole integration: the NoteGuard engine is a plain
Python package, so "sanitise at source" becomes one ordinary transform between the raw notes
dataset and everything downstream.

To use it for real:
  1. In a Foundry Code Repository (transforms-python), add ``noteguard`` (this repo) and a
     spaCy model wheel to the environment (meta.yml / conda deps).
  2. Drop this file in, point Input/Output at your dataset RIDs, commit, and build.

This file is illustrative — it imports ``transforms.api``, which only exists inside Foundry,
so it is not imported by this repo's tests or app.
"""
from transforms.api import Input, Output, transform_df  # available inside Foundry only

TEXT_COL = "note_text"      # free-text column to de-identify
PATIENT_COL = "person_id"   # keeps pseudonyms patient-consistent; use a constant if absent
METHOD = "redaction"        # "redaction" or "pseudonym"


@transform_df(
    Output("/NHS/your-trust/datasets/clinical_notes_deidentified"),
    Input("/NHS/your-trust/datasets/clinical_notes_raw"),
)
def deidentify_notes(notes_df):
    """Replace the free-text column with its de-identified version; all other columns pass through.

    Detection + transformation run inside Foundry's governed compute — no external calls, and the
    in-memory pseudonym vault is never persisted. Downstream consumers branch off the output
    dataset, so nothing identifiable crosses the boundary.
    """
    from pyspark.sql import functions as F

    def deidentify_partition(rows):
        # One engine + one vault per executor partition: same patient -> same surrogate
        # within the partition. Repartition by PATIENT_COL upstream for global consistency.
        from src.detect import build_detector
        from src.pipeline import Pipeline
        from src.transform import PseudonymVault

        pipe = Pipeline(build_detector(use_presidio=True), PseudonymVault())
        for row in rows:
            d = row.asDict()
            text = d.get(TEXT_COL)
            if text:
                pid = str(d.get(PATIENT_COL) or "batch")
                d[TEXT_COL] = pipe.sanitise(str(text), METHOD, pid).sanitised
            yield d

    schema = notes_df.schema
    deid = notes_df.repartition(F.col(PATIENT_COL)).rdd.mapPartitions(deidentify_partition)
    return notes_df.sparkSession.createDataFrame(deid, schema)


# Assurance hook: the same package ships the evaluation harness (src/evaluate.py), so a second
# transform over a labelled sample can publish the miss-rate (false-negative) metric as its own
# Foundry dataset — the number an IG lead actually wants on a dashboard.
