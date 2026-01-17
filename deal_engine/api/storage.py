"""
Mandate storage with in-memory and JSON file persistence.

Phase 5: Simple storage layer for mandate management.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from deal_engine.core import (
    Mandate,
    AssetClass,
    InvestorType,
    RiskProfile,
    GeographicCriteria,
    FinancialCriteria,
    PropertyCriteria,
    DealCriteria,
    ScoringWeights,
)


class MandateStorage:
    """
    In-memory mandate storage with optional JSON file persistence.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize storage.

        Args:
            storage_path: Optional path to JSON file for persistence.
                         If None, storage is in-memory only.
        """
        self._mandates: dict[str, Mandate] = {}
        self._storage_path = storage_path
        self._load()

    def _load(self) -> None:
        """Load mandates from JSON file if path is set."""
        if not self._storage_path:
            return

        path = Path(self._storage_path)
        if not path.exists():
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            for mandate_data in data.get("mandates", []):
                mandate = Mandate.from_dict(mandate_data)
                self._mandates[mandate.mandate_id] = mandate

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load mandates from {path}: {e}")

    def _save(self) -> None:
        """Save mandates to JSON file if path is set."""
        if not self._storage_path:
            return

        path = Path(self._storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "mandates": [m.to_dict() for m in self._mandates.values()],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def create(self, mandate: Mandate) -> Mandate:
        """
        Create a new mandate.

        Args:
            mandate: The mandate to create

        Returns:
            The created mandate

        Raises:
            ValueError: If mandate_id already exists
        """
        if mandate.mandate_id in self._mandates:
            raise ValueError(f"Mandate '{mandate.mandate_id}' already exists")

        self._mandates[mandate.mandate_id] = mandate
        self._save()
        return mandate

    def get(self, mandate_id: str) -> Optional[Mandate]:
        """Get a mandate by ID."""
        return self._mandates.get(mandate_id)

    def get_all(self) -> list[Mandate]:
        """Get all mandates."""
        return list(self._mandates.values())

    def update(self, mandate: Mandate) -> Mandate:
        """
        Update an existing mandate.

        Args:
            mandate: The mandate to update

        Returns:
            The updated mandate

        Raises:
            ValueError: If mandate doesn't exist
        """
        if mandate.mandate_id not in self._mandates:
            raise ValueError(f"Mandate '{mandate.mandate_id}' not found")

        self._mandates[mandate.mandate_id] = mandate
        self._save()
        return mandate

    def delete(self, mandate_id: str) -> bool:
        """
        Delete a mandate.

        Args:
            mandate_id: ID of mandate to delete

        Returns:
            True if deleted, False if not found
        """
        if mandate_id not in self._mandates:
            return False

        del self._mandates[mandate_id]
        self._save()
        return True

    def count(self) -> int:
        """Get count of mandates."""
        return len(self._mandates)

    def search(
        self,
        investor_type: Optional[InvestorType] = None,
        asset_class: Optional[AssetClass] = None,
        is_active: Optional[bool] = None,
    ) -> list[Mandate]:
        """
        Search mandates with filters.

        Args:
            investor_type: Filter by investor type
            asset_class: Filter by asset class
            is_active: Filter by active status

        Returns:
            List of matching mandates
        """
        results = []

        for mandate in self._mandates.values():
            # Apply filters
            if investor_type and mandate.investor_type != investor_type:
                continue
            if asset_class and asset_class not in mandate.asset_classes:
                continue
            if is_active is not None and mandate.is_active != is_active:
                continue

            results.append(mandate)

        return results

    def generate_id(self) -> str:
        """Generate a unique mandate ID."""
        import uuid
        return f"MND-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def create_sample_mandates(storage: MandateStorage) -> None:
    """Create sample mandates for demo purposes."""

    # Sample 1: Core residential investor
    mandate1 = Mandate(
        mandate_id=storage.generate_id(),
        investor_name="Sterling Capital Partners",
        investor_type=InvestorType.INSTITUTIONAL,
        asset_classes=[AssetClass.RESIDENTIAL, AssetClass.BTR],
        risk_profile=RiskProfile.CORE,
        geographic=GeographicCriteria(
            regions=["Greater London", "South East"],
            postcodes=["SW", "SE", "E", "N", "W"],
        ),
        financial=FinancialCriteria(
            min_deal_size=1000000,
            max_deal_size=10000000,
            min_yield=4.5,
            target_yield=5.5,
        ),
        property=PropertyCriteria(
            min_units=5,
            accept_refurbishment=False,
            accept_development=False,
        ),
        deal_criteria=DealCriteria(
            pursue_score_threshold=80.0,
            consider_score_threshold=70.0,
        ),
        priority=1,
        notes="Core strategy - stabilized assets only",
    )

    # Sample 2: Value-add HMO specialist
    mandate2 = Mandate(
        mandate_id=storage.generate_id(),
        investor_name="Yield Hunters Fund",
        investor_type=InvestorType.PRIVATE_EQUITY,
        asset_classes=[AssetClass.HMO, AssetClass.RESIDENTIAL],
        risk_profile=RiskProfile.VALUE_ADD,
        geographic=GeographicCriteria(
            regions=["Greater London", "West Midlands", "North West"],
        ),
        financial=FinancialCriteria(
            min_deal_size=300000,
            max_deal_size=2000000,
            min_yield=7.0,
            target_yield=9.0,
        ),
        property=PropertyCriteria(
            min_units=1,
            max_units=15,
            accept_refurbishment=True,
            accept_development=False,
        ),
        scoring_weights=ScoringWeights(
            yield_minimum=0.25,
            yield_target=0.20,
            price_range=0.15,
            location_region=0.10,
        ),
        deal_criteria=DealCriteria(
            min_bmv_percent=10.0,
            pursue_score_threshold=75.0,
        ),
        priority=2,
        notes="Focus on high-yielding HMOs with value-add potential",
    )

    # Sample 3: Family office - mixed use
    mandate3 = Mandate(
        mandate_id=storage.generate_id(),
        investor_name="Ashford Family Office",
        investor_type=InvestorType.FAMILY_OFFICE,
        asset_classes=[AssetClass.MIXED_USE, AssetClass.RESIDENTIAL, AssetClass.RETAIL],
        risk_profile=RiskProfile.CORE_PLUS,
        geographic=GeographicCriteria(
            regions=["Greater London"],
            postcodes=["W1", "W2", "SW1", "SW3", "SW7"],
            exclude_postcodes=["E", "SE"],
        ),
        financial=FinancialCriteria(
            min_deal_size=2000000,
            max_deal_size=15000000,
            min_yield=4.0,
            target_yield=5.0,
            max_price_psf=1500.0,
        ),
        property=PropertyCriteria(
            freehold_only=True,
            accept_refurbishment=True,
        ),
        priority=1,
        notes="Prime central London focus - freehold only",
    )

    for mandate in [mandate1, mandate2, mandate3]:
        try:
            storage.create(mandate)
        except ValueError:
            pass  # Already exists
