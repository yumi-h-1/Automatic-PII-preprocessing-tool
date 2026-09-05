"""NoteGuard — automatic PII sanitisation for NHS clinical notes.

Clean data in, no identifiers out. Rule-based detection plus Presidio NER, with
redaction or patient-consistent pseudonymisation, so free-text clinical data can be
used without exposing the people in it.
"""

__version__ = "0.0.1"
