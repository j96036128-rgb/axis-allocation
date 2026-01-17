"""
Rejection criteria module.

Defines clear, deterministic rejection rules with
human-readable reasons for why deals are rejected.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from .mandate import Mandate
from .listing import Listing, Tenure, Condition


class RejectionCategory(Enum):
    """Categories of rejection reasons."""

    PRICE = "price"
    LOCATION = "location"
    YIELD = "yield"
    ASSET_CLASS = "asset_class"
    PROPERTY = "property"
    TENURE = "tenure"
    RISK = "risk"
    DATA_QUALITY = "data_quality"


class RejectionSeverity(Enum):
    """Severity of rejection - hard vs soft."""

    HARD = "hard"  # Absolute disqualification
    SOFT = "soft"  # Strong concern but potentially negotiable


@dataclass
class RejectionReason:
    """
    Detailed rejection reason.

    Provides clear explanation for why a deal was rejected
    and what would need to change for acceptance.
    """

    category: RejectionCategory
    severity: RejectionSeverity
    code: str  # Machine-readable code
    title: str  # Short title
    explanation: str  # Detailed explanation
    remedy: str  # What would fix this

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "code": self.code,
            "title": self.title,
            "explanation": self.explanation,
            "remedy": self.remedy,
        }


@dataclass
class RejectionResult:
    """
    Complete rejection assessment for a listing-mandate pair.
    """

    listing_id: str
    mandate_id: str
    rejected: bool
    reasons: list[RejectionReason] = field(default_factory=list)

    @property
    def hard_rejections(self) -> list[RejectionReason]:
        """Get only hard rejection reasons."""
        return [r for r in self.reasons if r.severity == RejectionSeverity.HARD]

    @property
    def soft_rejections(self) -> list[RejectionReason]:
        """Get only soft rejection reasons."""
        return [r for r in self.reasons if r.severity == RejectionSeverity.SOFT]

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "listing_id": self.listing_id,
            "mandate_id": self.mandate_id,
            "rejected": self.rejected,
            "hard_rejections": len(self.hard_rejections),
            "soft_rejections": len(self.soft_rejections),
            "reasons": [r.to_dict() for r in self.reasons],
        }


# =============================================================================
# Rejection Rules
# =============================================================================

def check_price_too_high(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if price exceeds maximum deal size."""
    max_size = mandate.financial.max_deal_size
    price = listing.asking_price

    if max_size and price > max_size:
        excess_pct = ((price - max_size) / max_size) * 100
        return RejectionReason(
            category=RejectionCategory.PRICE,
            severity=RejectionSeverity.HARD if excess_pct > 20 else RejectionSeverity.SOFT,
            code="PRICE_EXCEEDS_MAX",
            title="Price exceeds maximum",
            explanation=f"Asking price £{price:,} exceeds mandate maximum of £{max_size:,} by {excess_pct:.0f}%.",
            remedy=f"Price would need to reduce to £{max_size:,} or below ({excess_pct:.0f}% reduction required)."
        )
    return None


def check_price_too_low(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if price is below minimum deal size."""
    min_size = mandate.financial.min_deal_size
    price = listing.asking_price

    if min_size and price < min_size:
        shortfall_pct = ((min_size - price) / min_size) * 100
        return RejectionReason(
            category=RejectionCategory.PRICE,
            severity=RejectionSeverity.HARD if shortfall_pct > 30 else RejectionSeverity.SOFT,
            code="PRICE_BELOW_MIN",
            title="Price below minimum",
            explanation=f"Asking price £{price:,} is below mandate minimum of £{min_size:,} by {shortfall_pct:.0f}%.",
            remedy="Deal too small for mandate - consider aggregating with adjacent opportunities."
        )
    return None


def check_location_excluded(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if location is in exclusion list."""
    geo = mandate.geographic
    region = listing.region
    postcode = listing.postcode_area

    # Check region exclusion
    if region in geo.exclude_regions:
        return RejectionReason(
            category=RejectionCategory.LOCATION,
            severity=RejectionSeverity.HARD,
            code="REGION_EXCLUDED",
            title="Region excluded",
            explanation=f"Region '{region}' is explicitly excluded from this mandate.",
            remedy="This location cannot be considered under the current mandate terms."
        )

    # Check postcode exclusion
    for excluded in geo.exclude_postcodes:
        if postcode.upper().startswith(excluded.upper()):
            return RejectionReason(
                category=RejectionCategory.LOCATION,
                severity=RejectionSeverity.HARD,
                code="POSTCODE_EXCLUDED",
                title="Postcode excluded",
                explanation=f"Postcode '{postcode}' falls within excluded area '{excluded}'.",
                remedy="This location cannot be considered under the current mandate terms."
            )

    return None


def check_location_outside_target(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if location is outside target areas."""
    geo = mandate.geographic

    # If no target areas specified, location is acceptable
    if not geo.regions and not geo.postcodes:
        return None

    region = listing.region
    postcode = listing.postcode_area

    region_match = not geo.regions or region in geo.regions
    postcode_match = not geo.postcodes or any(
        postcode.upper().startswith(pc.upper())
        for pc in geo.postcodes
    )

    if not region_match and not postcode_match:
        target_areas = []
        if geo.regions:
            target_areas.extend(geo.regions)
        if geo.postcodes:
            target_areas.extend(geo.postcodes)

        return RejectionReason(
            category=RejectionCategory.LOCATION,
            severity=RejectionSeverity.SOFT,
            code="LOCATION_NOT_TARGET",
            title="Outside target location",
            explanation=f"Location '{region}/{postcode}' is not within mandate target areas: {', '.join(target_areas[:5])}.",
            remedy="Mandate would need to be amended to include this location, or deal presented as exception."
        )

    return None


def check_yield_insufficient(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if yield is below minimum."""
    min_yield = mandate.financial.min_yield
    listing_yield = listing.gross_yield

    if min_yield and listing_yield is not None and listing_yield < min_yield:
        shortfall = min_yield - listing_yield
        return RejectionReason(
            category=RejectionCategory.YIELD,
            severity=RejectionSeverity.HARD if shortfall > 2.0 else RejectionSeverity.SOFT,
            code="YIELD_BELOW_MIN",
            title="Yield below minimum",
            explanation=f"Gross yield of {listing_yield:.1f}% is below mandate minimum of {min_yield:.1f}% (shortfall: {shortfall:.1f}pp).",
            remedy=f"Would require price reduction of ~{(shortfall/listing_yield)*100:.0f}% to achieve target yield, or rent increase."
        )
    return None


def check_asset_class_mismatch(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if asset class is not accepted."""
    if mandate.asset_classes and listing.asset_class not in mandate.asset_classes:
        accepted = [ac.value for ac in mandate.asset_classes]
        return RejectionReason(
            category=RejectionCategory.ASSET_CLASS,
            severity=RejectionSeverity.HARD,
            code="ASSET_CLASS_MISMATCH",
            title="Asset class not accepted",
            explanation=f"Asset class '{listing.asset_class.value}' is not in mandate-accepted classes: {', '.join(accepted)}.",
            remedy="This asset class cannot be considered under the current mandate."
        )
    return None


def check_tenure_unacceptable(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if tenure doesn't meet requirements."""
    prop = mandate.property

    if prop.freehold_only and listing.tenure not in (Tenure.FREEHOLD, Tenure.SHARE_OF_FREEHOLD):
        return RejectionReason(
            category=RejectionCategory.TENURE,
            severity=RejectionSeverity.HARD,
            code="FREEHOLD_REQUIRED",
            title="Freehold required",
            explanation=f"Mandate requires freehold, but property is {listing.tenure.value}.",
            remedy="Cannot proceed unless freehold is acquired or mandate terms are amended."
        )

    if prop.min_lease_years and listing.tenure == Tenure.LEASEHOLD:
        remaining = listing.financial.lease_years_remaining
        if remaining is not None and remaining < prop.min_lease_years:
            return RejectionReason(
                category=RejectionCategory.TENURE,
                severity=RejectionSeverity.HARD if remaining < 80 else RejectionSeverity.SOFT,
                code="LEASE_TOO_SHORT",
                title="Lease too short",
                explanation=f"Lease has {remaining} years remaining, below mandate minimum of {prop.min_lease_years} years.",
                remedy=f"Would require lease extension of at least {prop.min_lease_years - remaining} years before acquisition."
            )

    return None


def check_condition_unacceptable(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if property condition is not accepted."""
    prop = mandate.property
    condition = listing.property_details.condition

    if condition == Condition.DEVELOPMENT and not prop.accept_development:
        return RejectionReason(
            category=RejectionCategory.PROPERTY,
            severity=RejectionSeverity.HARD,
            code="DEVELOPMENT_NOT_ACCEPTED",
            title="Development not accepted",
            explanation="Property requires development, which is not accepted under this mandate.",
            remedy="Mandate does not permit development risk. Consider alternative mandates with development appetite."
        )

    if condition in (Condition.LIGHT_REFURB, Condition.HEAVY_REFURB) and not prop.accept_refurbishment:
        return RejectionReason(
            category=RejectionCategory.PROPERTY,
            severity=RejectionSeverity.SOFT,
            code="REFURB_NOT_ACCEPTED",
            title="Refurbishment not accepted",
            explanation=f"Property requires {condition.value.replace('_', ' ')}, which is not preferred under this mandate.",
            remedy="Consider if works can be minimized or if mandate can accommodate limited refurbishment."
        )

    return None


def check_unit_count(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if unit count is within range."""
    prop = mandate.property
    units = listing.property_details.unit_count

    if prop.min_units and units < prop.min_units:
        return RejectionReason(
            category=RejectionCategory.PROPERTY,
            severity=RejectionSeverity.SOFT,
            code="UNITS_BELOW_MIN",
            title="Too few units",
            explanation=f"Property has {units} units, below mandate minimum of {prop.min_units}.",
            remedy="Consider aggregating with adjacent properties or presenting as exception for smaller lot."
        )

    if prop.max_units and units > prop.max_units:
        return RejectionReason(
            category=RejectionCategory.PROPERTY,
            severity=RejectionSeverity.SOFT,
            code="UNITS_ABOVE_MAX",
            title="Too many units",
            explanation=f"Property has {units} units, above mandate maximum of {prop.max_units}.",
            remedy="Consider partial acquisition or presenting as exception for larger lot."
        )

    return None


def check_data_quality(listing: Listing, mandate: Mandate) -> Optional[RejectionReason]:
    """Check if essential data is missing."""
    missing = []

    if not listing.address.postcode:
        missing.append("postcode")
    if not listing.address.region:
        missing.append("region")
    if listing.financial.asking_price <= 0:
        missing.append("valid price")
    if listing.property_details.condition == Condition.UNKNOWN:
        missing.append("property condition")

    if missing:
        return RejectionReason(
            category=RejectionCategory.DATA_QUALITY,
            severity=RejectionSeverity.SOFT,
            code="MISSING_DATA",
            title="Incomplete data",
            explanation=f"Missing essential data: {', '.join(missing)}. Cannot fully assess against mandate.",
            remedy="Obtain missing information before proceeding with formal assessment."
        )

    return None


# All rejection rules in order of evaluation
REJECTION_RULES: list[Callable[[Listing, Mandate], Optional[RejectionReason]]] = [
    check_asset_class_mismatch,
    check_location_excluded,
    check_price_too_high,
    check_price_too_low,
    check_yield_insufficient,
    check_tenure_unacceptable,
    check_condition_unacceptable,
    check_location_outside_target,
    check_unit_count,
    check_data_quality,
]


def evaluate_rejection(
    listing: Listing,
    mandate: Mandate,
    rules: Optional[list[Callable]] = None,
    stop_on_hard: bool = False
) -> RejectionResult:
    """
    Evaluate all rejection criteria for a listing-mandate pair.

    Args:
        listing: The property listing to evaluate
        mandate: The investor mandate with criteria
        rules: Optional custom rules (uses REJECTION_RULES if None)
        stop_on_hard: If True, stop evaluation on first hard rejection

    Returns:
        RejectionResult with all identified reasons
    """
    active_rules = rules or REJECTION_RULES
    reasons: list[RejectionReason] = []

    for rule in active_rules:
        reason = rule(listing, mandate)
        if reason:
            reasons.append(reason)
            if stop_on_hard and reason.severity == RejectionSeverity.HARD:
                break

    # Rejected if any hard rejections exist
    has_hard_rejection = any(r.severity == RejectionSeverity.HARD for r in reasons)

    return RejectionResult(
        listing_id=listing.listing_id,
        mandate_id=mandate.mandate_id,
        rejected=has_hard_rejection,
        reasons=reasons,
    )


def get_rejection_summary(results: list[RejectionResult]) -> dict:
    """
    Generate summary statistics from rejection results.

    Args:
        results: List of RejectionResult objects

    Returns:
        Dictionary with rejection statistics
    """
    total = len(results)
    rejected = sum(1 for r in results if r.rejected)
    passed = total - rejected

    # Count reasons by code
    reason_counts: dict[str, int] = {}
    for result in results:
        for reason in result.reasons:
            reason_counts[reason.code] = reason_counts.get(reason.code, 0) + 1

    # Sort by frequency
    top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total": total,
        "rejected": rejected,
        "passed": passed,
        "rejection_rate": (rejected / total * 100) if total > 0 else 0,
        "top_rejection_reasons": dict(top_reasons),
    }
