"""
Catalogue service for resolving human-readable business references.
"""

import os
import json
import functools
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CatalogueResult:
    status: str
    data: dict[str, Any] | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.status == "success":
            return {"status": "success", "data": self.data}
        return {"status": "error", "message": self.message}


class CatalogueService:
    """Service class responsible for querying the business reference catalogue."""

    def __init__(self, catalogue_path: str | None = None):
        self.custom_path = catalogue_path

    def _candidate_paths(self) -> list[str]:
        if self.custom_path:
            return [self.custom_path]
        root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        mod_dir = os.path.dirname(os.path.abspath(__file__))
        return [
            os.path.join(root_dir, "catalogue.json"),
            os.path.join(mod_dir, "catalogue.json"),
            "catalogue.json",
        ]

    @functools.lru_cache(maxsize=1)
    def _load_catalogue(self) -> dict[str, Any]:
        for path in self._candidate_paths():
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return {}

    @functools.lru_cache(maxsize=128)
    def lookup(self, reference: str) -> dict[str, Any]:
        """Looks up a business reference and returns associated technical names."""
        try:
            catalogue = self._load_catalogue()
            if not catalogue:
                return CatalogueResult(
                    status="error",
                    message=f"Catalogue file not found at any of {self._candidate_paths()}",
                ).to_dict()

            ref_lower = reference.lower()

            # 1. Check for exact key match (case-insensitive)
            for key in catalogue:
                if key.lower() == ref_lower:
                    return CatalogueResult(
                        status="success", data=catalogue[key]
                    ).to_dict()

            # 2. Check if reference is contained in key or description
            for key, data in catalogue.items():
                desc = str(data.get("description", "")).lower()
                if ref_lower in key.lower() or ref_lower in desc:
                    return CatalogueResult(status="success", data=data).to_dict()

            return CatalogueResult(
                status="error",
                message=f"Reference '{reference}' not found in catalogue.",
            ).to_dict()
        except Exception as e:
            return CatalogueResult(
                status="error",
                message=f"Failed to read catalogue: {str(e)}",
            ).to_dict()
