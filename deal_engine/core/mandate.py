"""
Mandate data model and schema.

Defines the structure for investor capital mandates including:
- Asset class preferences
- Geographic targets
- Financial parameters (size, yield, LTV)
- Investor classification
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AssetClass(Enum):
    """Supported asset classes for investment mandates."""

    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"
    INDUSTRIAL = "industrial"
    RETAIL = "retail"
    OFFICE = "office"
    HOSPITALITY = "hospitality"
    STUDENT_HOUSING = "student_housing"
    SENIOR_LIVING = "senior_living"
    BTR = "build_to_rent"  # Build-to-Rent
    HMO = "hmo"  # House in Multiple Occupation


class InvestorType(Enum):
    """Classification of investor entities."""

    INSTITUTIONAL = "institutional"
    FAMILY_OFFICE = "family_office"
    PRIVATE_EQUITY = "private_equity"
    REIT = "reit"
    HNWI = "hnwi"  # High Net Worth Individual
    PENSION_FUND = "pension_fund"
    INSURANCE = "insurance"
    SOVEREIGN_WEALTH = "sovereign_wealth"
    OTHER = "other"


class RiskProfile(Enum):
    """Investment risk appetite classification."""

    CORE = "core"  # Stabilized, low-risk assets
    CORE_PLUS = "core_plus"  # Core with light value-add
    VALUE_ADD = "value_add"  # Repositioning opportunities
    OPPORTUNISTIC = "opportunistic"  # Development, distressed


@dataclass
class GeographicCriteria:
    """Geographic targeting for mandate."""

    regions: list[str] = field(default_factory=list)  # e.g., ["London", "South East"]
    postcodes: list[str] = field(default_factory=list)  # e.g., ["SW1", "EC1"]
    exclude_regions: list[str] = field(default_factory=list)
    exclude_postcodes: list[str] = field(default_factory=list)


@dataclass
class FinancialCriteria:
    """Financial parameters for mandate."""

    # Deal size (GBP)
    min_deal_size: Optional[int] = None  # Minimum single deal size
    max_deal_size: Optional[int] = None  # Maximum single deal size
    total_allocation: Optional[int] = None  # Total capital to deploy

    # Returns
    min_yield: Optional[float] = None  # Minimum gross yield %
    target_yield: Optional[float] = None  # Target gross yield %
    min_irr: Optional[float] = None  # Minimum IRR %
    target_irr: Optional[float] = None  # Target IRR %

    # Leverage
    max_ltv: Optional[float] = None  # Maximum loan-to-value %
    preferred_ltv: Optional[float] = None  # Preferred LTV %

    # Pricing
    max_price_psf: Optional[float] = None  # Max price per sq ft


@dataclass
class PropertyCriteria:
    """Property-specific requirements."""

    min_units: Optional[int] = None  # Minimum unit count
    max_units: Optional[int] = None  # Maximum unit count
    min_sqft: Optional[int] = None  # Minimum total sq ft
    max_sqft: Optional[int] = None  # Maximum total sq ft
    min_bedrooms: Optional[int] = None  # Per-unit minimum
    max_bedrooms: Optional[int] = None  # Per-unit maximum

    # Condition preferences
    accept_refurbishment: bool = True
    accept_development: bool = False
    accept_turnkey: bool = True

    # Tenure
    freehold_only: bool = False
    min_lease_years: Optional[int] = None  # For leasehold

    # Property type preferences (Phase 4)
    preferred_property_types: list[str] = field(default_factory=list)  # e.g., ["terraced", "semi-detached"]


@dataclass
class ScoringWeights:
    """
    Per-mandate weighting controls for scoring factors.

    All weights should sum to 1.0 for normalized scoring.
    If not specified, default weights are used.
    """

    location_region: float = 0.15
    location_postcode: float = 0.10
    price_range: float = 0.20
    price_psf: float = 0.05
    yield_minimum: float = 0.15
    yield_target: float = 0.10
    property_size: float = 0.05
    property_condition: float = 0.10
    property_tenure: float = 0.05
    risk_profile: float = 0.05

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for scoring module."""
        return {
            "location_region": self.location_region,
            "location_postcode": self.location_postcode,
            "price_range": self.price_range,
            "price_psf": self.price_psf,
            "yield_minimum": self.yield_minimum,
            "yield_target": self.yield_target,
            "property_size": self.property_size,
            "property_condition": self.property_condition,
            "property_tenure": self.property_tenure,
            "risk_profile": self.risk_profile,
        }

    @property
    def total_weight(self) -> float:
        """Calculate sum of all weights (should be ~1.0)."""
        return sum(self.to_dict().values())

    def normalize(self) -> "ScoringWeights":
        """Return a normalized copy where weights sum to 1.0."""
        total = self.total_weight
        if total == 0:
            return self
        factor = 1.0 / total
        return ScoringWeights(
            location_region=self.location_region * factor,
            location_postcode=self.location_postcode * factor,
            price_range=self.price_range * factor,
            price_psf=self.price_psf * factor,
            yield_minimum=self.yield_minimum * factor,
            yield_target=self.yield_target * factor,
            property_size=self.property_size * factor,
            property_condition=self.property_condition * factor,
            property_tenure=self.property_tenure * factor,
            risk_profile=self.risk_profile * factor,
        )


@dataclass
class DealCriteria:
    """
    Configurable deal evaluation parameters (Phase 4).

    Controls thresholds for scoring, filtering, and recommendation logic.
    """

    # Below Market Value requirement
    min_bmv_percent: Optional[float] = None  # e.g., 15.0 for 15% BMV

    # Score thresholds
    min_overall_score: float = 40.0  # Minimum score to pass
    pursue_score_threshold: float = 75.0  # Score needed for PURSUE recommendation
    consider_score_threshold: float = 60.0  # Score needed for CONSIDER recommendation

    # Market timing
    max_days_on_market: Optional[int] = None  # e.g., 90 days max
    prefer_fresh_listings: bool = True  # Bonus for listings < 14 days
    fresh_listing_days: int = 14  # What counts as "fresh"

    # Conviction thresholds (override defaults)
    high_conviction_threshold: float = 0.80
    medium_conviction_threshold: float = 0.60
    low_conviction_threshold: float = 0.40

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "min_bmv_percent": self.min_bmv_percent,
            "min_overall_score": self.min_overall_score,
            "pursue_score_threshold": self.pursue_score_threshold,
            "consider_score_threshold": self.consider_score_threshold,
            "max_days_on_market": self.max_days_on_market,
            "prefer_fresh_listings": self.prefer_fresh_listings,
            "fresh_listing_days": self.fresh_listing_days,
            "high_conviction_threshold": self.high_conviction_threshold,
            "medium_conviction_threshold": self.medium_conviction_threshold,
            "low_conviction_threshold": self.low_conviction_threshold,
        }


@dataclass
class Mandate:
    """
    Investor capital mandate.

    Represents a qualified investor's criteria for property investments.
    Used to filter and score potential deal opportunities.
    """

    # Identification
    mandate_id: str
    investor_name: str
    investor_type: InvestorType

    # Investment focus
    asset_classes: list[AssetClass] = field(default_factory=list)
    risk_profile: RiskProfile = RiskProfile.CORE_PLUS

    # Criteria
    geographic: GeographicCriteria = field(default_factory=GeographicCriteria)
    financial: FinancialCriteria = field(default_factory=FinancialCriteria)
    property: PropertyCriteria = field(default_factory=PropertyCriteria)

    # Phase 4: Configurable deal parameters
    deal_criteria: DealCriteria = field(default_factory=DealCriteria)
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)

    # Status
    is_active: bool = True
    priority: int = 1  # 1 = highest priority

    # Notes
    notes: str = ""

    def accepts_asset_class(self, asset_class: AssetClass) -> bool:
        """Check if mandate accepts a given asset class."""
        if not self.asset_classes:
            return True  # No restriction means all accepted
        return asset_class in self.asset_classes

    def accepts_location(self, region: str, postcode: str) -> bool:
        """Check if mandate accepts a given location."""
        geo = self.geographic

        # Check exclusions first
        if region in geo.exclude_regions:
            return False
        if any(postcode.upper().startswith(exc.upper()) for exc in geo.exclude_postcodes):
            return False

        # If no inclusions specified, accept all (minus exclusions)
        if not geo.regions and not geo.postcodes:
            return True

        # Check inclusions
        region_match = not geo.regions or region in geo.regions
        postcode_match = not geo.postcodes or any(
            postcode.upper().startswith(pc.upper()) for pc in geo.postcodes
        )

        return region_match or postcode_match

    def accepts_price(self, price: int) -> bool:
        """Check if deal price falls within mandate range."""
        fin = self.financial

        if fin.min_deal_size and price < fin.min_deal_size:
            return False
        if fin.max_deal_size and price > fin.max_deal_size:
            return False

        return True

    def to_dict(self) -> dict:
        """Convert mandate to dictionary representation."""
        return {
            "mandate_id": self.mandate_id,
            "investor_name": self.investor_name,
            "investor_type": self.investor_type.value,
            "asset_classes": [ac.value for ac in self.asset_classes],
            "risk_profile": self.risk_profile.value,
            "geographic": {
                "regions": self.geographic.regions,
                "postcodes": self.geographic.postcodes,
                "exclude_regions": self.geographic.exclude_regions,
                "exclude_postcodes": self.geographic.exclude_postcodes,
            },
            "financial": {
                "min_deal_size": self.financial.min_deal_size,
                "max_deal_size": self.financial.max_deal_size,
                "total_allocation": self.financial.total_allocation,
                "min_yield": self.financial.min_yield,
                "target_yield": self.financial.target_yield,
                "min_irr": self.financial.min_irr,
                "target_irr": self.financial.target_irr,
                "max_ltv": self.financial.max_ltv,
                "preferred_ltv": self.financial.preferred_ltv,
                "max_price_psf": self.financial.max_price_psf,
            },
            "property": {
                "min_units": self.property.min_units,
                "max_units": self.property.max_units,
                "min_sqft": self.property.min_sqft,
                "max_sqft": self.property.max_sqft,
                "min_bedrooms": self.property.min_bedrooms,
                "max_bedrooms": self.property.max_bedrooms,
                "accept_refurbishment": self.property.accept_refurbishment,
                "accept_development": self.property.accept_development,
                "accept_turnkey": self.property.accept_turnkey,
                "freehold_only": self.property.freehold_only,
                "min_lease_years": self.property.min_lease_years,
                "preferred_property_types": self.property.preferred_property_types,
            },
            "deal_criteria": self.deal_criteria.to_dict(),
            "scoring_weights": self.scoring_weights.to_dict(),
            "is_active": self.is_active,
            "priority": self.priority,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Mandate":
        """Create mandate from dictionary representation."""
        geographic = GeographicCriteria(
            regions=data.get("geographic", {}).get("regions", []),
            postcodes=data.get("geographic", {}).get("postcodes", []),
            exclude_regions=data.get("geographic", {}).get("exclude_regions", []),
            exclude_postcodes=data.get("geographic", {}).get("exclude_postcodes", []),
        )

        fin_data = data.get("financial", {})
        financial = FinancialCriteria(
            min_deal_size=fin_data.get("min_deal_size"),
            max_deal_size=fin_data.get("max_deal_size"),
            total_allocation=fin_data.get("total_allocation"),
            min_yield=fin_data.get("min_yield"),
            target_yield=fin_data.get("target_yield"),
            min_irr=fin_data.get("min_irr"),
            target_irr=fin_data.get("target_irr"),
            max_ltv=fin_data.get("max_ltv"),
            preferred_ltv=fin_data.get("preferred_ltv"),
            max_price_psf=fin_data.get("max_price_psf"),
        )

        prop_data = data.get("property", {})
        property_criteria = PropertyCriteria(
            min_units=prop_data.get("min_units"),
            max_units=prop_data.get("max_units"),
            min_sqft=prop_data.get("min_sqft"),
            max_sqft=prop_data.get("max_sqft"),
            min_bedrooms=prop_data.get("min_bedrooms"),
            max_bedrooms=prop_data.get("max_bedrooms"),
            accept_refurbishment=prop_data.get("accept_refurbishment", True),
            accept_development=prop_data.get("accept_development", False),
            accept_turnkey=prop_data.get("accept_turnkey", True),
            freehold_only=prop_data.get("freehold_only", False),
            min_lease_years=prop_data.get("min_lease_years"),
            preferred_property_types=prop_data.get("preferred_property_types", []),
        )

        # Phase 4: Deal criteria
        deal_data = data.get("deal_criteria", {})
        deal_criteria = DealCriteria(
            min_bmv_percent=deal_data.get("min_bmv_percent"),
            min_overall_score=deal_data.get("min_overall_score", 40.0),
            pursue_score_threshold=deal_data.get("pursue_score_threshold", 75.0),
            consider_score_threshold=deal_data.get("consider_score_threshold", 60.0),
            max_days_on_market=deal_data.get("max_days_on_market"),
            prefer_fresh_listings=deal_data.get("prefer_fresh_listings", True),
            fresh_listing_days=deal_data.get("fresh_listing_days", 14),
            high_conviction_threshold=deal_data.get("high_conviction_threshold", 0.80),
            medium_conviction_threshold=deal_data.get("medium_conviction_threshold", 0.60),
            low_conviction_threshold=deal_data.get("low_conviction_threshold", 0.40),
        )

        # Phase 4: Scoring weights
        weight_data = data.get("scoring_weights", {})
        scoring_weights = ScoringWeights(
            location_region=weight_data.get("location_region", 0.15),
            location_postcode=weight_data.get("location_postcode", 0.10),
            price_range=weight_data.get("price_range", 0.20),
            price_psf=weight_data.get("price_psf", 0.05),
            yield_minimum=weight_data.get("yield_minimum", 0.15),
            yield_target=weight_data.get("yield_target", 0.10),
            property_size=weight_data.get("property_size", 0.05),
            property_condition=weight_data.get("property_condition", 0.10),
            property_tenure=weight_data.get("property_tenure", 0.05),
            risk_profile=weight_data.get("risk_profile", 0.05),
        )

        asset_classes = [
            AssetClass(ac) for ac in data.get("asset_classes", [])
        ]

        return cls(
            mandate_id=data["mandate_id"],
            investor_name=data["investor_name"],
            investor_type=InvestorType(data["investor_type"]),
            asset_classes=asset_classes,
            risk_profile=RiskProfile(data.get("risk_profile", "core_plus")),
            geographic=geographic,
            financial=financial,
            property=property_criteria,
            deal_criteria=deal_criteria,
            scoring_weights=scoring_weights,
            is_active=data.get("is_active", True),
            priority=data.get("priority", 1),
            notes=data.get("notes", ""),
        )
