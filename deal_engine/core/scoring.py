"""
Scoring module for matching listings against mandates.

Provides a multi-factor scoring system to rank how well
a property listing matches an investor's mandate criteria.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .mandate import Mandate, RiskProfile, ScoringWeights
from .listing import Listing, Condition, Tenure


class ScoreCategory(Enum):
    """Categories of scoring factors."""

    LOCATION = "location"
    PRICE = "price"
    YIELD = "yield"
    PROPERTY = "property"
    RISK = "risk"


@dataclass
class ScoreFactor:
    """Individual scoring factor result."""

    category: ScoreCategory
    name: str
    score: float  # 0.0 to 1.0
    weight: float  # Importance weight
    weighted_score: float  # score * weight
    explanation: str


@dataclass
class ScoringResult:
    """
    Complete scoring result for a listing against a mandate.

    Contains overall score, individual factors, and explanations.
    """

    listing_id: str
    mandate_id: str

    # Overall scores
    total_score: float  # 0.0 to 100.0
    match_grade: str  # A, B, C, D, F

    # Breakdown
    factors: list[ScoreFactor] = field(default_factory=list)

    # Pass/fail indicators
    passes_hard_filters: bool = True
    disqualification_reasons: list[str] = field(default_factory=list)

    @property
    def is_match(self) -> bool:
        """Check if this is a viable match (passes filters and scores above threshold)."""
        return self.passes_hard_filters and self.total_score >= 40.0

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "listing_id": self.listing_id,
            "mandate_id": self.mandate_id,
            "total_score": round(self.total_score, 2),
            "match_grade": self.match_grade,
            "is_match": self.is_match,
            "passes_hard_filters": self.passes_hard_filters,
            "disqualification_reasons": self.disqualification_reasons,
            "factors": [
                {
                    "category": f.category.value,
                    "name": f.name,
                    "score": round(f.score, 3),
                    "weight": f.weight,
                    "weighted_score": round(f.weighted_score, 3),
                    "explanation": f.explanation,
                }
                for f in self.factors
            ],
        }


# Default weights for scoring factors
DEFAULT_WEIGHTS = {
    "location_region": 0.15,
    "location_postcode": 0.10,
    "price_range": 0.20,
    "price_psf": 0.05,
    "yield_minimum": 0.15,
    "yield_target": 0.10,
    "property_size": 0.05,
    "property_condition": 0.10,
    "property_tenure": 0.05,
    "risk_profile": 0.05,
}


def _calculate_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


def _score_location(listing: Listing, mandate: Mandate, weights: dict[str, float]) -> list[ScoreFactor]:
    """Score location match."""
    factors = []
    geo = mandate.geographic

    # Region scoring
    region_score = 0.0
    region_explanation = ""

    if not geo.regions:
        region_score = 1.0
        region_explanation = "No region restrictions"
    elif listing.region in geo.regions:
        region_score = 1.0
        region_explanation = f"Region '{listing.region}' matches mandate"
    elif listing.region in geo.exclude_regions:
        region_score = 0.0
        region_explanation = f"Region '{listing.region}' is excluded"
    else:
        region_score = 0.3
        region_explanation = f"Region '{listing.region}' not in preferred list"

    factors.append(ScoreFactor(
        category=ScoreCategory.LOCATION,
        name="region_match",
        score=region_score,
        weight=weights["location_region"],
        weighted_score=region_score * weights["location_region"],
        explanation=region_explanation,
    ))

    # Postcode scoring
    postcode_score = 0.0
    postcode_explanation = ""
    postcode_area = listing.postcode_area

    if not geo.postcodes:
        postcode_score = 1.0
        postcode_explanation = "No postcode restrictions"
    elif any(postcode_area.startswith(pc.upper()) for pc in geo.postcodes):
        postcode_score = 1.0
        postcode_explanation = f"Postcode '{postcode_area}' matches mandate"
    elif any(postcode_area.startswith(pc.upper()) for pc in geo.exclude_postcodes):
        postcode_score = 0.0
        postcode_explanation = f"Postcode '{postcode_area}' is excluded"
    else:
        postcode_score = 0.5
        postcode_explanation = f"Postcode '{postcode_area}' not in preferred list"

    factors.append(ScoreFactor(
        category=ScoreCategory.LOCATION,
        name="postcode_match",
        score=postcode_score,
        weight=weights["location_postcode"],
        weighted_score=postcode_score * weights["location_postcode"],
        explanation=postcode_explanation,
    ))

    return factors


def _score_price(listing: Listing, mandate: Mandate, weights: dict[str, float]) -> list[ScoreFactor]:
    """Score price/deal size match."""
    factors = []
    fin = mandate.financial
    price = listing.asking_price

    # Price range scoring
    price_score = 1.0
    price_explanation = ""

    min_size = fin.min_deal_size
    max_size = fin.max_deal_size

    if min_size and max_size:
        if min_size <= price <= max_size:
            # Score higher for being in the middle of the range
            range_position = (price - min_size) / (max_size - min_size)
            # Prefer middle of range
            price_score = 1.0 - abs(0.5 - range_position) * 0.4
            price_explanation = f"Price £{price:,} within range £{min_size:,}-£{max_size:,}"
        elif price < min_size:
            # Below minimum - partial score based on how close
            shortfall = (min_size - price) / min_size
            price_score = max(0.0, 0.5 - shortfall)
            price_explanation = f"Price £{price:,} below minimum £{min_size:,}"
        else:
            # Above maximum
            excess = (price - max_size) / max_size
            price_score = max(0.0, 0.5 - excess)
            price_explanation = f"Price £{price:,} above maximum £{max_size:,}"
    elif min_size:
        if price >= min_size:
            price_score = 1.0
            price_explanation = f"Price £{price:,} meets minimum £{min_size:,}"
        else:
            shortfall = (min_size - price) / min_size
            price_score = max(0.0, 0.7 - shortfall)
            price_explanation = f"Price £{price:,} below minimum £{min_size:,}"
    elif max_size:
        if price <= max_size:
            price_score = 1.0
            price_explanation = f"Price £{price:,} within maximum £{max_size:,}"
        else:
            excess = (price - max_size) / max_size
            price_score = max(0.0, 0.5 - excess)
            price_explanation = f"Price £{price:,} above maximum £{max_size:,}"
    else:
        price_score = 1.0
        price_explanation = "No price constraints"

    factors.append(ScoreFactor(
        category=ScoreCategory.PRICE,
        name="price_range",
        score=price_score,
        weight=weights["price_range"],
        weighted_score=price_score * weights["price_range"],
        explanation=price_explanation,
    ))

    # Price per sq ft scoring (if available)
    psf_score = 1.0
    psf_explanation = "Price per sq ft not evaluated"

    if fin.max_price_psf and listing.financial.price_per_sqft:
        psf = listing.financial.price_per_sqft
        if psf <= fin.max_price_psf:
            psf_score = 1.0
            psf_explanation = f"Price/sqft £{psf:.0f} within max £{fin.max_price_psf:.0f}"
        else:
            excess = (psf - fin.max_price_psf) / fin.max_price_psf
            psf_score = max(0.0, 0.8 - excess)
            psf_explanation = f"Price/sqft £{psf:.0f} above max £{fin.max_price_psf:.0f}"

    factors.append(ScoreFactor(
        category=ScoreCategory.PRICE,
        name="price_psf",
        score=psf_score,
        weight=weights["price_psf"],
        weighted_score=psf_score * weights["price_psf"],
        explanation=psf_explanation,
    ))

    return factors


def _score_yield(listing: Listing, mandate: Mandate, weights: dict[str, float]) -> list[ScoreFactor]:
    """Score yield match."""
    factors = []
    fin = mandate.financial
    listing_yield = listing.gross_yield

    # Minimum yield scoring
    min_yield_score = 1.0
    min_yield_explanation = ""

    if fin.min_yield:
        if listing_yield is None:
            min_yield_score = 0.5
            min_yield_explanation = "Yield data not available"
        elif listing_yield >= fin.min_yield:
            min_yield_score = 1.0
            min_yield_explanation = f"Yield {listing_yield:.1f}% meets minimum {fin.min_yield:.1f}%"
        else:
            shortfall = (fin.min_yield - listing_yield) / fin.min_yield
            min_yield_score = max(0.0, 0.7 - shortfall)
            min_yield_explanation = f"Yield {listing_yield:.1f}% below minimum {fin.min_yield:.1f}%"
    else:
        min_yield_explanation = "No minimum yield requirement"

    factors.append(ScoreFactor(
        category=ScoreCategory.YIELD,
        name="yield_minimum",
        score=min_yield_score,
        weight=weights["yield_minimum"],
        weighted_score=min_yield_score * weights["yield_minimum"],
        explanation=min_yield_explanation,
    ))

    # Target yield scoring
    target_yield_score = 1.0
    target_yield_explanation = ""

    if fin.target_yield:
        if listing_yield is None:
            target_yield_score = 0.5
            target_yield_explanation = "Yield data not available"
        elif listing_yield >= fin.target_yield:
            # Bonus for exceeding target
            excess = (listing_yield - fin.target_yield) / fin.target_yield
            target_yield_score = min(1.0, 0.9 + excess * 0.2)
            target_yield_explanation = f"Yield {listing_yield:.1f}% meets/exceeds target {fin.target_yield:.1f}%"
        else:
            shortfall = (fin.target_yield - listing_yield) / fin.target_yield
            target_yield_score = max(0.3, 0.9 - shortfall)
            target_yield_explanation = f"Yield {listing_yield:.1f}% below target {fin.target_yield:.1f}%"
    else:
        target_yield_explanation = "No target yield specified"

    factors.append(ScoreFactor(
        category=ScoreCategory.YIELD,
        name="yield_target",
        score=target_yield_score,
        weight=weights["yield_target"],
        weighted_score=target_yield_score * weights["yield_target"],
        explanation=target_yield_explanation,
    ))

    return factors


def _score_property(listing: Listing, mandate: Mandate, weights: dict[str, float]) -> list[ScoreFactor]:
    """Score property characteristics match."""
    factors = []
    prop_mandate = mandate.property
    prop_listing = listing.property_details

    # Size/unit scoring
    size_score = 1.0
    size_explanation = ""

    if prop_mandate.min_units or prop_mandate.max_units:
        units = prop_listing.unit_count
        if prop_mandate.min_units and units < prop_mandate.min_units:
            size_score = 0.5
            size_explanation = f"Unit count {units} below minimum {prop_mandate.min_units}"
        elif prop_mandate.max_units and units > prop_mandate.max_units:
            size_score = 0.5
            size_explanation = f"Unit count {units} above maximum {prop_mandate.max_units}"
        else:
            size_score = 1.0
            size_explanation = f"Unit count {units} within requirements"
    else:
        size_explanation = "No unit count requirements"

    factors.append(ScoreFactor(
        category=ScoreCategory.PROPERTY,
        name="property_size",
        score=size_score,
        weight=weights["property_size"],
        weighted_score=size_score * weights["property_size"],
        explanation=size_explanation,
    ))

    # Condition scoring
    condition_score = 1.0
    condition_explanation = ""
    condition = prop_listing.condition

    if condition == Condition.TURNKEY:
        if prop_mandate.accept_turnkey:
            condition_score = 1.0
            condition_explanation = "Turnkey property accepted"
        else:
            condition_score = 0.3
            condition_explanation = "Turnkey not preferred"
    elif condition in (Condition.LIGHT_REFURB, Condition.HEAVY_REFURB):
        if prop_mandate.accept_refurbishment:
            condition_score = 1.0
            condition_explanation = "Refurbishment opportunity accepted"
        else:
            condition_score = 0.3
            condition_explanation = "Refurbishment not preferred"
    elif condition == Condition.DEVELOPMENT:
        if prop_mandate.accept_development:
            condition_score = 1.0
            condition_explanation = "Development opportunity accepted"
        else:
            condition_score = 0.2
            condition_explanation = "Development not accepted"
    else:
        condition_score = 0.7
        condition_explanation = "Condition unknown"

    factors.append(ScoreFactor(
        category=ScoreCategory.PROPERTY,
        name="property_condition",
        score=condition_score,
        weight=weights["property_condition"],
        weighted_score=condition_score * weights["property_condition"],
        explanation=condition_explanation,
    ))

    # Tenure scoring
    tenure_score = 1.0
    tenure_explanation = ""

    if prop_mandate.freehold_only:
        if listing.tenure == Tenure.FREEHOLD:
            tenure_score = 1.0
            tenure_explanation = "Freehold as required"
        elif listing.tenure == Tenure.SHARE_OF_FREEHOLD:
            tenure_score = 0.8
            tenure_explanation = "Share of freehold (close to requirement)"
        else:
            tenure_score = 0.2
            tenure_explanation = "Leasehold but freehold required"
    elif prop_mandate.min_lease_years and listing.tenure == Tenure.LEASEHOLD:
        remaining = listing.financial.lease_years_remaining
        if remaining is None:
            tenure_score = 0.6
            tenure_explanation = "Lease length unknown"
        elif remaining >= prop_mandate.min_lease_years:
            tenure_score = 1.0
            tenure_explanation = f"Lease {remaining} years meets minimum {prop_mandate.min_lease_years}"
        else:
            tenure_score = 0.4
            tenure_explanation = f"Lease {remaining} years below minimum {prop_mandate.min_lease_years}"
    else:
        tenure_score = 1.0
        tenure_explanation = "Tenure acceptable"

    factors.append(ScoreFactor(
        category=ScoreCategory.PROPERTY,
        name="property_tenure",
        score=tenure_score,
        weight=weights["property_tenure"],
        weighted_score=tenure_score * weights["property_tenure"],
        explanation=tenure_explanation,
    ))

    return factors


def _score_risk(listing: Listing, mandate: Mandate, weights: dict[str, float]) -> list[ScoreFactor]:
    """Score risk profile alignment."""
    factors = []

    risk_score = 1.0
    risk_explanation = ""

    # Map condition to risk profile
    condition = listing.property_details.condition
    risk_profile = mandate.risk_profile

    condition_risk_map = {
        Condition.TURNKEY: RiskProfile.CORE,
        Condition.LIGHT_REFURB: RiskProfile.CORE_PLUS,
        Condition.HEAVY_REFURB: RiskProfile.VALUE_ADD,
        Condition.DEVELOPMENT: RiskProfile.OPPORTUNISTIC,
        Condition.UNKNOWN: RiskProfile.CORE_PLUS,
    }

    implied_risk = condition_risk_map.get(condition, RiskProfile.CORE_PLUS)

    # Score based on risk alignment
    risk_levels = [RiskProfile.CORE, RiskProfile.CORE_PLUS, RiskProfile.VALUE_ADD, RiskProfile.OPPORTUNISTIC]
    mandate_level = risk_levels.index(risk_profile)
    implied_level = risk_levels.index(implied_risk)

    level_diff = implied_level - mandate_level

    if level_diff == 0:
        risk_score = 1.0
        risk_explanation = f"Risk profile matches ({risk_profile.value})"
    elif level_diff == 1:
        risk_score = 0.7
        risk_explanation = f"Slightly higher risk ({implied_risk.value}) than mandate ({risk_profile.value})"
    elif level_diff == -1:
        risk_score = 0.8
        risk_explanation = f"Slightly lower risk ({implied_risk.value}) than mandate ({risk_profile.value})"
    elif level_diff > 1:
        risk_score = 0.3
        risk_explanation = f"Significantly higher risk ({implied_risk.value}) than mandate ({risk_profile.value})"
    else:
        risk_score = 0.6
        risk_explanation = f"Lower risk ({implied_risk.value}) than mandate ({risk_profile.value})"

    factors.append(ScoreFactor(
        category=ScoreCategory.RISK,
        name="risk_profile",
        score=risk_score,
        weight=weights["risk_profile"],
        weighted_score=risk_score * weights["risk_profile"],
        explanation=risk_explanation,
    ))

    return factors


def score_listing(
    listing: Listing,
    mandate: Mandate,
    weights: Optional[dict[str, float]] = None
) -> ScoringResult:
    """
    Score a listing against a mandate.

    Args:
        listing: The property listing to score
        mandate: The investor mandate to score against
        weights: Optional custom weights override (uses mandate.scoring_weights if not provided)

    Returns:
        ScoringResult with total score, grade, and factor breakdown
    """
    # Determine weights to use (priority: explicit > mandate > defaults)
    if weights:
        active_weights = {**DEFAULT_WEIGHTS, **weights}
    else:
        # Use mandate's scoring_weights if available
        active_weights = mandate.scoring_weights.to_dict()

    factors: list[ScoreFactor] = []
    disqualification_reasons: list[str] = []

    # Check hard filters first
    passes_hard_filters = True

    # Asset class filter
    if not mandate.accepts_asset_class(listing.asset_class):
        passes_hard_filters = False
        disqualification_reasons.append(
            f"Asset class '{listing.asset_class.value}' not accepted by mandate"
        )

    # Location exclusion filter
    if not mandate.accepts_location(listing.region, listing.postcode_area):
        passes_hard_filters = False
        disqualification_reasons.append(
            f"Location '{listing.region}/{listing.postcode_area}' excluded by mandate"
        )

    # Collect scoring factors (pass weights to each scorer)
    factors.extend(_score_location(listing, mandate, active_weights))
    factors.extend(_score_price(listing, mandate, active_weights))
    factors.extend(_score_yield(listing, mandate, active_weights))
    factors.extend(_score_property(listing, mandate, active_weights))
    factors.extend(_score_risk(listing, mandate, active_weights))

    # Calculate total score
    total_weighted = sum(f.weighted_score for f in factors)
    total_weight = sum(f.weight for f in factors)

    if total_weight > 0:
        normalized_score = (total_weighted / total_weight) * 100
    else:
        normalized_score = 0.0

    # Apply penalty for failed hard filters
    if not passes_hard_filters:
        normalized_score *= 0.3

    return ScoringResult(
        listing_id=listing.listing_id,
        mandate_id=mandate.mandate_id,
        total_score=normalized_score,
        match_grade=_calculate_grade(normalized_score),
        factors=factors,
        passes_hard_filters=passes_hard_filters,
        disqualification_reasons=disqualification_reasons,
    )


def score_listings(
    listings: list[Listing],
    mandate: Mandate,
    min_score: float = 0.0
) -> list[ScoringResult]:
    """
    Score multiple listings against a mandate.

    Args:
        listings: List of property listings to score
        mandate: The investor mandate to score against
        min_score: Minimum score threshold (results below are excluded)

    Returns:
        List of ScoringResult, sorted by score descending
    """
    results = []

    for listing in listings:
        result = score_listing(listing, mandate)
        if result.total_score >= min_score:
            results.append(result)

    # Sort by score descending
    results.sort(key=lambda r: r.total_score, reverse=True)

    return results
