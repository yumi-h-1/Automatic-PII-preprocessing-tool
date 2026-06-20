# Failed experiments / dead ends

Log approaches that did not work so we don't repeat them. One entry per attempt:
what we tried, why it failed, what we did instead.

## Assumed UK_POSTCODE / UK_NINO / UK_PASSPORT / UK_VEHICLE_REGISTRATION were Presidio built-ins
The supported-entities docs list these as UK entities, so the plan said "enable built-ins". But the
released `presidio-analyzer==2.2.362` only ships `UK_NHS` (verified via `get_supported_entities()` ->
only `UK_NHS` under UK). A leakage test caught `SW1A 1AA` surviving. Fix: added custom recognizers in
`src/recognizers/uk_entities.py` emitting the same entity names. Lesson: verify the installed version's
recognizers, don't trust the docs page (which tracks `main`).

<!-- Example:
## spaCy en_core_web_sm alone for names
Tried relying only on NER for PERSON detection. Missed "Surname, First Middle" forms common in the
notes, leaking names. Fix: added the roster lookup recognizer (src/recognizers/roster.py) as a backstop.
-->
