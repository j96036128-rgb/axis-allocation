"""
Conviction scoring module.

Assigns conviction levels (HIGH, MEDIUM, LOW) to deal matches
based on deterministic, rule-based scoring criteria.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .mandate import Mandate
from .listing import Listing
from .scoring import ScoringResult, ScoreCategory


class ConvictionLevel(Enum):
    """Conviction level for a deal match."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"  # Does not meet minimum criteria


@dataclass
class ConvictionFactor:
    """Individual factor contributing to conviction assessment."""

    name: str
    met: bool
    weight: float  # Importance (0.0-1.0)
    reason: str


@dataclass
class ConvictionAssessment:
    """
    Complete conviction assessment for a deal match.

    Combines numeric scoring with qualitative conviction level.
    """

    listing_id: str
    mandate_id: str

    # Conviction result
    level: ConvictionLevel
    confidence_score: float  # 0.0 to 1.0

    # Supporting factors
    positive_factors: list[ConvictionFactor] = field(default_factory=list)
    negative_factors: list[ConvictionFactor] = field(default_factory=list)
    neutral_factors: list[ConvictionFactor] = field(default_factory=list)

    # Summary
    summary: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "listing_id": self.listing_id,
            "mandate_id": self.mandate_id,
            "level": self.level.value,
            "confidence_score": round(self.confidence_score, 3),
            "positive_factors": [
                {"name": f.name, "reason": f.reason, "weight": f.weight}
                for f in self.positive_factors
            ],
            "negative_factors": [
                {"name": f.name, "reason": f.reason, "weight": f.weight}
                for f in self.negative_factors
            ],
            "neutral_factors": [
                {"name": f.name, "reason": f.reason, "weight": f.weight}
                for f in self.neutral_factors
            ],
            "summary": self.summary,
            "recommendation": self.recommendation,
        }


# Default conviction thresholds (can be overridden by mandate.deal_criteria)
DEFAULT_HIGH_CONVICTION_THRESHOLD = 0.80
DEFAULT_MEDIUM_CONVICTION_THRESHOLD = 0.60
DEFAULT_LOW_CONVICTION_THRESHOLD = 0.40


def _assess_price_conviction(
    listing: Listing,
    mandate: Mandate,
    scoring_result: ScoringResult
) -> list[ConvictionFactor]:
    """Assess price-related conviction factors."""
    factors = []
    fin = mandate.financial
    price = listing.asking_price

    # Price positioning within range
    if fin.min_deal_size and fin.max_deal_size:
        range_size = fin.max_deal_size - fin.min_deal_size
        position = (price - fin.min_deal_size) / range_size if range_size > 0 else 0.5

        if 0.2 <= position <= 0.8:
            factors.append(ConvictionFactor(
                name="price_positioning",
                met=True,
                weight=0.15,
                reason=f"Price £{price:,} well-positioned in mandate range (position: {position:.0%})"
            ))
        elif position < 0.2:
            factors.append(ConvictionFactor(
                name="price_positioning",
                met=True,
                weight=0.10,
                reason=f"Price £{price:,} at lower end of range - potential value opportunity"
            ))
        else:
            factors.append(ConvictionFactor(
                name="price_positioning",
                met=False,
                weight=0.10,
                reason=f"Price £{price:,} at upper end of range - less headroom"
            ))

    # Price per sq ft assessment
    if listing.financial.price_per_sqft and fin.max_price_psf:
        psf = listing.financial.price_per_sqft
        if psf <= fin.max_price_psf * 0.85:
            factors.append(ConvictionFactor(
                name="price_psf_value",
                met=True,
                weight=0.10,
                reason=f"Price/sqft £{psf:.0f} significantly below max £{fin.max_price_psf:.0f}"
            ))
        elif psf <= fin.max_price_psf:
            factors.append(ConvictionFactor(
                name="price_psf_value",
                met=True,
                weight=0.05,
                reason=f"Price/sqft £{psf:.0f} within acceptable range"
            ))

    return factors


def _assess_yield_conviction(
    listing: Listing,
    mandate: Mandate,
    scoring_result: ScoringResult
) -> list[ConvictionFactor]:
    """Assess yield-related conviction factors."""
    factors = []
    fin = mandate.financial
    listing_yield = listing.gross_yield

    if listing_yield is None:
        factors.append(ConvictionFactor(
            name="yield_data",
            met=False,
            weight=0.15,
            reason="No yield data available - requires manual assessment"
        ))
        return factors

    # Yield vs minimum
    if fin.min_yield:
        yield_buffer = listing_yield - fin.min_yield
        if yield_buffer >= 2.0:
            factors.append(ConvictionFactor(
                name="yield_buffer",
                met=True,
                weight=0.20,
                reason=f"Yield {listing_yield:.1f}% exceeds minimum by {yield_buffer:.1f}pp - strong buffer"
            ))
        elif yield_buffer >= 1.0:
            factors.append(ConvictionFactor(
                name="yield_buffer",
                met=True,
                weight=0.15,
                reason=f"Yield {listing_yield:.1f}% exceeds minimum by {yield_buffer:.1f}pp - adequate buffer"
            ))
        elif yield_buffer >= 0:
            factors.append(ConvictionFactor(
                name="yield_buffer",
                met=True,
                weight=0.05,
                reason=f"Yield {listing_yield:.1f}% meets minimum but limited buffer"
            ))
        else:
            factors.append(ConvictionFactor(
                name="yield_buffer",
                met=False,
                weight=0.20,
                reason=f"Yield {listing_yield:.1f}% below minimum {fin.min_yield:.1f}%"
            ))

    # Yield vs target
    if fin.target_yield and listing_yield >= fin.target_yield:
        factors.append(ConvictionFactor(
            name="yield_target",
            met=True,
            weight=0.15,
            reason=f"Yield {listing_yield:.1f}% meets/exceeds target {fin.target_yield:.1f}%"
        ))

    return factors


def _assess_location_conviction(
    listing: Listing,
    mandate: Mandate,
    scoring_result: ScoringResult
) -> list[ConvictionFactor]:
    """Assess location-related conviction factors."""
    factors = []
    geo = mandate.geographic

    region = listing.region
    postcode = listing.postcode_area

    # Region match strength
    if region in geo.regions:
        factors.append(ConvictionFactor(
            name="region_match",
            met=True,
            weight=0.15,
            reason=f"Region '{region}' explicitly targeted by mandate"
        ))
    elif not geo.regions:
        factors.append(ConvictionFactor(
            name="region_match",
            met=True,
            weight=0.05,
            reason="No region restrictions - location acceptable"
        ))

    # Postcode match strength
    if geo.postcodes:
        exact_match = any(
            postcode.upper() == pc.upper()
            for pc in geo.postcodes
        )
        prefix_match = any(
            postcode.upper().startswith(pc.upper())
            for pc in geo.postcodes
        )

        if exact_match:
            factors.append(ConvictionFactor(
                name="postcode_match",
                met=True,
                weight=0.15,
                reason=f"Postcode '{postcode}' exactly matches mandate target"
            ))
        elif prefix_match:
            factors.append(ConvictionFactor(
                name="postcode_match",
                met=True,
                weight=0.10,
                reason=f"Postcode '{postcode}' within targeted area"
            ))

    return factors


def _assess_property_conviction(
    listing: Listing,
    mandate: Mandate,
    scoring_result: ScoringResult
) -> list[ConvictionFactor]:
    """Assess property-related conviction factors."""
    factors = []
    prop_mandate = mandate.property
    prop_listing = listing.property_details

    # Unit count assessment
    units = prop_listing.unit_count
    if prop_mandate.min_units and prop_mandate.max_units:
        if prop_mandate.min_units <= units <= prop_mandate.max_units:
            # Check if in sweet spot (middle 60%)
            range_size = prop_mandate.max_units - prop_mandate.min_units
            if range_size > 0:
                position = (units - prop_mandate.min_units) / range_size
                if 0.2 <= position <= 0.8:
                    factors.append(ConvictionFactor(
                        name="unit_count",
                        met=True,
                        weight=0.10,
                        reason=f"Unit count ({units}) in optimal range for mandate"
                    ))
                else:
                    factors.append(ConvictionFactor(
                        name="unit_count",
                        met=True,
                        weight=0.05,
                        reason=f"Unit count ({units}) acceptable but at edge of range"
                    ))

    # Condition assessment
    from .listing import Condition

    condition = prop_listing.condition
    if condition == Condition.TURNKEY and prop_mandate.accept_turnkey:
        factors.append(ConvictionFactor(
            name="condition_fit",
            met=True,
            weight=0.15,
            reason="Turnkey property - immediate income potential"
        ))
    elif condition == Condition.LIGHT_REFURB and prop_mandate.accept_refurbishment:
        factors.append(ConvictionFactor(
            name="condition_fit",
            met=True,
            weight=0.12,
            reason="Light refurb opportunity - value-add potential with limited risk"
        ))
    elif condition == Condition.HEAVY_REFURB and prop_mandate.accept_refurbishment:
        factors.append(ConvictionFactor(
            name="condition_fit",
            met=True,
            weight=0.08,
            reason="Heavy refurb - significant value-add but execution risk"
        ))
    elif condition == Condition.DEVELOPMENT and prop_mandate.accept_development:
        factors.append(ConvictionFactor(
            name="condition_fit",
            met=True,
            weight=0.05,
            reason="Development opportunity - high potential but high risk"
        ))
    elif condition == Condition.UNKNOWN:
        factors.append(ConvictionFactor(
            name="condition_fit",
            met=False,
            weight=0.10,
            reason="Property condition unknown - requires inspection"
        ))

    # Tenanted status
    if prop_listing.has_tenants:
        factors.append(ConvictionFactor(
            name="income_status",
            met=True,
            weight=0.10,
            reason="Property tenanted - immediate income stream"
        ))

    return factors


def _assess_risk_conviction(
    listing: Listing,
    mandate: Mandate,
    scoring_result: ScoringResult
) -> list[ConvictionFactor]:
    """Assess risk-related conviction factors."""
    factors = []
    from .listing import Tenure

    # Tenure risk
    tenure = listing.tenure
    if tenure == Tenure.FREEHOLD:
        factors.append(ConvictionFactor(
            name="tenure_security",
            met=True,
            weight=0.10,
            reason="Freehold tenure - maximum security"
        ))
    elif tenure == Tenure.SHARE_OF_FREEHOLD:
        factors.append(ConvictionFactor(
            name="tenure_security",
            met=True,
            weight=0.08,
            reason="Share of freehold - good security"
        ))
    elif tenure == Tenure.LEASEHOLD:
        remaining = listing.financial.lease_years_remaining
        if remaining and remaining >= 125:
            factors.append(ConvictionFactor(
                name="tenure_security",
                met=True,
                weight=0.08,
                reason=f"Long leasehold ({remaining} years) - acceptable security"
            ))
        elif remaining and remaining >= 80:
            factors.append(ConvictionFactor(
                name="tenure_security",
                met=True,
                weight=0.05,
                reason=f"Medium leasehold ({remaining} years) - may need extension"
            ))
        elif remaining:
            factors.append(ConvictionFactor(
                name="tenure_security",
                met=False,
                weight=0.10,
                reason=f"Short leasehold ({remaining} years) - extension required"
            ))

    return factors


def assess_conviction(
    listing: Listing,
    mandate: Mandate,
    scoring_result: ScoringResult
) -> ConvictionAssessment:
    """
    Assess conviction level for a listing-mandate match.

    Combines scoring result with rule-based conviction factors
    to determine HIGH, MEDIUM, LOW, or NONE conviction.

    Uses mandate's deal_criteria for configurable thresholds.
    """
    # Get thresholds from mandate or use defaults
    deal = mandate.deal_criteria
    high_threshold = deal.high_conviction_threshold
    medium_threshold = deal.medium_conviction_threshold
    low_threshold = deal.low_conviction_threshold

    all_factors: list[ConvictionFactor] = []

    # Gather factors from all assessment areas
    all_factors.extend(_assess_price_conviction(listing, mandate, scoring_result))
    all_factors.extend(_assess_yield_conviction(listing, mandate, scoring_result))
    all_factors.extend(_assess_location_conviction(listing, mandate, scoring_result))
    all_factors.extend(_assess_property_conviction(listing, mandate, scoring_result))
    all_factors.extend(_assess_risk_conviction(listing, mandate, scoring_result))

    # Separate into positive, negative, neutral
    positive = [f for f in all_factors if f.met and f.weight >= 0.10]
    negative = [f for f in all_factors if not f.met]
    neutral = [f for f in all_factors if f.met and f.weight < 0.10]

    # Calculate confidence score
    total_weight = sum(f.weight for f in all_factors) or 1.0
    met_weight = sum(f.weight for f in all_factors if f.met)
    confidence_score = met_weight / total_weight

    # Adjust for scoring result
    if scoring_result.passes_hard_filters:
        base_score = scoring_result.total_score / 100
        # Blend numeric score with conviction factors (70/30 split)
        final_confidence = (base_score * 0.7) + (confidence_score * 0.3)
    else:
        # Hard filter failure significantly reduces confidence
        final_confidence = confidence_score * 0.3

    # Determine conviction level using mandate thresholds
    if not scoring_result.passes_hard_filters:
        level = ConvictionLevel.NONE
    elif final_confidence >= high_threshold:
        level = ConvictionLevel.HIGH
    elif final_confidence >= medium_threshold:
        level = ConvictionLevel.MEDIUM
    elif final_confidence >= low_threshold:
        level = ConvictionLevel.LOW
    else:
        level = ConvictionLevel.NONE

    # Generate summary
    summary = _generate_summary(level, positive, negative, scoring_result)
    recommendation = _generate_recommendation(level, listing, mandate)

    return ConvictionAssessment(
        listing_id=listing.listing_id,
        mandate_id=mandate.mandate_id,
        level=level,
        confidence_score=final_confidence,
        positive_factors=positive,
        negative_factors=negative,
        neutral_factors=neutral,
        summary=summary,
        recommendation=recommendation,
    )


def _generate_summary(
    level: ConvictionLevel,
    positive: list[ConvictionFactor],
    negative: list[ConvictionFactor],
    scoring_result: ScoringResult
) -> str:
    """Generate human-readable summary."""
    if level == ConvictionLevel.HIGH:
        summary = f"Strong match ({scoring_result.match_grade} grade, {scoring_result.total_score:.0f}/100). "
        if positive:
            top_positives = sorted(positive, key=lambda f: f.weight, reverse=True)[:2]
            summary += "Key strengths: " + "; ".join(f.reason for f in top_positives) + "."
    elif level == ConvictionLevel.MEDIUM:
        summary = f"Moderate match ({scoring_result.match_grade} grade, {scoring_result.total_score:.0f}/100). "
        if positive:
            summary += f"{len(positive)} positive factors identified. "
        if negative:
            summary += f"{len(negative)} areas require attention."
    elif level == ConvictionLevel.LOW:
        summary = f"Marginal match ({scoring_result.match_grade} grade, {scoring_result.total_score:.0f}/100). "
        if negative:
            summary += "Concerns: " + "; ".join(f.reason for f in negative[:2]) + "."
    else:
        summary = "Does not meet minimum criteria. "
        if scoring_result.disqualification_reasons:
            summary += "Disqualified: " + "; ".join(scoring_result.disqualification_reasons[:2]) + "."

    return summary


def _generate_recommendation(
    level: ConvictionLevel,
    listing: Listing,
    mandate: Mandate
) -> str:
    """Generate action recommendation."""
    if level == ConvictionLevel.HIGH:
        return "RECOMMEND: Proceed to detailed due diligence and investor presentation"
    elif level == ConvictionLevel.MEDIUM:
        return "CONSIDER: Review with investment committee, clarify open items"
    elif level == ConvictionLevel.LOW:
        return "WATCH: Monitor for price reduction or changed circumstances"
    else:
        return "PASS: Does not meet mandate criteria"


def rank_by_conviction(
    assessments: list[ConvictionAssessment]
) -> dict[ConvictionLevel, list[ConvictionAssessment]]:
    """
    Group and rank assessments by conviction level.

    Returns dictionary with conviction levels as keys.
    """
    ranked: dict[ConvictionLevel, list[ConvictionAssessment]] = {
        ConvictionLevel.HIGH: [],
        ConvictionLevel.MEDIUM: [],
        ConvictionLevel.LOW: [],
        ConvictionLevel.NONE: [],
    }

    for assessment in assessments:
        ranked[assessment.level].append(assessment)

    # Sort each group by confidence score
    for level in ranked:
        ranked[level].sort(key=lambda a: a.confidence_score, reverse=True)

    return ranked
