"""Anonymisation: turn analyzer results into de-identified text.

Two modes:
- ``redact``      -> every entity becomes ``<ENTITY_TYPE>`` (Presidio's default replace).
- ``pseudonymise`` (default) -> "pseudonymisation at source": each identifier is swapped for a
  realistic but fake value via a per-run ``Vault``. The Vault caches original->fake so the same person
  reads coherently across notes (preserving within-TRE linkage), generates *valid* fake NHS numbers,
  reduces postcodes to the outward code, and shifts dates by one consistent offset (preserving
  intervals). The Vault IS the re-identification key — it stays Trust-local and is gitignored.
"""
from __future__ import annotations

import random
import re
import string
from functools import lru_cache

from faker import Faker
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from .config import PSEUDONYMISE_STRATEGY

try:
    from dateutil import parser as _date_parser
except Exception:  # pragma: no cover - dateutil ships with pandas
    _date_parser = None

MODE_REDACT = "redact"
MODE_PSEUDONYMISE = "pseudonymise"

_POSTCODE_INWARD = re.compile(r"\s*\d[A-Za-z]{2}\s*$")
_NON_DIGIT = re.compile(r"\D")


class Vault:
    """Consistent original->fake mapping (the local re-identification key)."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._faker = Faker("en_GB")
        if seed is not None:
            self._faker.seed_instance(seed)
        self._cache: dict[tuple[str, str], str] = {}
        # One offset for the whole run -> dates move together, intervals preserved.
        self.date_offset_days = self._rng.randint(31, 365) * self._rng.choice((-1, 1))

    # -- generic memoised lookup -------------------------------------------------
    def _get(self, strategy: str, original: str, generate) -> str:
        key = (strategy, original.strip().lower())
        if key not in self._cache:
            self._cache[key] = generate()
        return self._cache[key]

    # -- per-strategy fake generators -------------------------------------------
    def name(self, original: str) -> str:
        return self._get("name", original, self._faker.name)

    def place(self, original: str) -> str:
        return self._get("place", original, self._faker.city)

    def org(self, original: str) -> str:
        return self._get("org", original, self._faker.company)

    def email(self, original: str) -> str:
        return self._get("email", original, self._faker.safe_email)

    def phone(self, original: str) -> str:
        return self._get("phone", original, self._faker.phone_number)

    def nhs(self, original: str) -> str:
        return self._get("nhs", original, self._fake_nhs_number)

    def nino(self, original: str) -> str:
        return self._get("nino", original, self._fake_nino)

    def passport(self, original: str) -> str:
        return self._get("passport", original, lambda: "".join(self._rng.choices(string.digits, k=9)))

    def vehicle(self, original: str) -> str:
        return self._get("vehicle", original, self._fake_vehicle)

    def postcode(self, original: str) -> str:
        outward = _POSTCODE_INWARD.sub("", original).strip()
        return outward or "<UK_POSTCODE>"

    def date(self, original: str) -> str:
        if _date_parser is None:
            return "<DATE_TIME>"
        try:
            dt = _date_parser.parse(original, dayfirst=True, fuzzy=True)
        except Exception:
            return "<DATE_TIME>"
        from datetime import timedelta

        return (dt + timedelta(days=self.date_offset_days)).strftime("%d/%m/%Y")

    # -- helpers ----------------------------------------------------------------
    def _fake_nhs_number(self) -> str:
        from .recognizers import nhs_check_digit

        while True:
            first9 = "".join(self._rng.choices(string.digits, k=9))
            check = nhs_check_digit(first9)
            if check is not None:
                return f"{first9[:3]} {first9[3:6]} {first9[6:]}{check}"

    def _fake_nino(self) -> str:
        letters = "".join(self._rng.choices(string.ascii_uppercase, k=2))
        digits = "".join(self._rng.choices(string.digits, k=6))
        return f"{letters}{digits}{self._rng.choice('ABCD')}"

    def _fake_vehicle(self) -> str:
        a = "".join(self._rng.choices(string.ascii_uppercase, k=2))
        n = "".join(self._rng.choices(string.digits, k=2))
        b = "".join(self._rng.choices(string.ascii_uppercase, k=3))
        return f"{a}{n} {b}"


# Strategy name -> Vault method used by the "custom" operator.
_STRATEGY_FN = {
    "name": "name", "place": "place", "org": "org", "email": "email", "phone": "phone",
    "nhs": "nhs", "nino": "nino", "passport": "passport", "vehicle": "vehicle",
    "postcode": "postcode", "date": "date",
}


@lru_cache(maxsize=1)
def _engine() -> AnonymizerEngine:
    return AnonymizerEngine()


def build_operators(mode: str, vault: Vault) -> dict[str, OperatorConfig]:
    """Map each entity to an OperatorConfig for the chosen mode."""
    if mode == MODE_REDACT:
        # Empty -> Presidio's default operator replaces every entity with <ENTITY_TYPE>.
        return {}

    operators: dict[str, OperatorConfig] = {}
    for entity, strategy in PSEUDONYMISE_STRATEGY.items():
        fn_name = _STRATEGY_FN.get(strategy)
        if fn_name is None:  # "redact" or unknown -> tag it
            operators[entity] = OperatorConfig("replace", {"new_value": f"<{entity}>"})
        else:
            method = getattr(vault, fn_name)
            operators[entity] = OperatorConfig("custom", {"lambda": method})
    return operators


def anonymize_text(text, analyzer_results, mode: str = MODE_PSEUDONYMISE, vault: Vault | None = None) -> str:
    """Return de-identified text. Pass a shared Vault across notes for cross-note consistency."""
    if vault is None:
        vault = Vault()
    operators = build_operators(mode, vault)
    result = _engine().anonymize(text=text, analyzer_results=analyzer_results, operators=operators)
    return result.text
