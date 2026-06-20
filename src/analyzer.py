"""Build the Presidio AnalyzerEngine: spaCy NLP + all Global/UK predefined recognizers + our custom
NHS recognizers (and an optional per-Trust roster backstop)."""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Sequence

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .config import LANGUAGE, SCORE_THRESHOLD, SPACY_MODEL
from .recognizers import custom_recognizers


def build_analyzer(
    roster_person: Iterable[str] = (),
    roster_place: Iterable[str] = (),
    roster_nhs: Iterable[str] = (),
    roster_ids: Iterable[str] = (),
) -> AnalyzerEngine:
    """Construct an analyzer. The predefined recognizer (UK_NHS) is loaded automatically by
    AnalyzerEngine; we add the Layer-B custom recognizers (incl. the other UK entities, which this
    Presidio version does not ship) on top."""
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": LANGUAGE, "model_name": SPACY_MODEL}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[LANGUAGE])
    for recognizer in custom_recognizers(roster_person, roster_place, roster_nhs, roster_ids):
        analyzer.registry.add_recognizer(recognizer)
    return analyzer


@lru_cache(maxsize=1)
def get_default_analyzer() -> AnalyzerEngine:
    """Cached analyzer with no roster — for single-note / interactive use (spaCy load is slow)."""
    return build_analyzer()


def analyze(analyzer: AnalyzerEngine, text: str) -> list[RecognizerResult]:
    return analyzer.analyze(text=text, language=LANGUAGE, score_threshold=SCORE_THRESHOLD)
