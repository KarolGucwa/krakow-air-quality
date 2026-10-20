"""Loading pipeline configuration and small text helpers shared across modules."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "pipeline.yml"


@dataclass(frozen=True)
class Settings:
    raw: dict[str, Any]

    @property
    def city(self) -> str:
        return self.raw["city"]

    @property
    def pollutants(self) -> list[str]:
        return list(self.raw["pollutants"])

    @property
    def raw_dir(self) -> Path:
        path = Path(self.raw["raw_dir"])
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def gios(self) -> dict[str, Any]:
        return self.raw["gios"]

    @property
    def weather(self) -> dict[str, Any]:
        return self.raw["weather"]


def load_settings(path: str | Path | None = None, raw_dir: str | Path | None = None) -> Settings:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if raw_dir is not None:
        data["raw_dir"] = str(raw_dir)
    return Settings(data)


def normalize_text(value: Any) -> str:
    """Lowercase, strip diacritics and collapse whitespace: 'Kraków ' -> 'krakow'.

    GIOŚ field names and values contain Polish characters (and even Greek letters in
    'WGS84 φ N'), so comparisons are done on a normalized form.
    """
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ł", "l").replace("Ł", "L")
    return " ".join(text.lower().split())


def find_field(record: dict[str, Any], *needles: str) -> Any:
    """Return the value of the first key whose normalized name contains all needles.

    Used for the few undocumented response fields (e.g. station/findAll), so that a
    renamed or re-cased key does not silently break the extraction.
    """
    normalized = {normalize_text(k): v for k, v in record.items()}
    wanted = [normalize_text(n) for n in needles]
    for key, value in normalized.items():
        if all(n in key for n in wanted):
            return value
    return None
