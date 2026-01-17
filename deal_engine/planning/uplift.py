"""
Planning Upside Engine - Uplift Estimation.

Estimates potential value uplift from successful planning permission.
Uses deterministic heuristics based on development type and property characteristics.
"""

from typing import Optional

from .models import (
    PlanningContext,
    PrecedentType,
    UpliftEstimate,
)


# Typical uplift percentages by development type (low, mid, high)
# Based on general market observations - NOT guarantees
UPLIFT_RANGES: dict[PrecedentType, tuple[float, float, float]] = {
    # Extensions - value add depends on quality and location
    PrecedentType.EXTENSION_REAR: (5.0, 10.0, 15.0),
    PrecedentType.EXTENSION_SIDE: (8.0, 12.0, 18.0),
    PrecedentType.EXTENSION_LOFT: (10.0, 15.0, 22.0),
    PrecedentType.EXTENSION_BASEMENT: (12.0, 20.0, 30.0),

    # Conversions - higher potential but more cost/risk
    PrecedentType.CONVERSION_RESIDENTIAL: (15.0, 25.0, 40.0),
    PrecedentType.CONVERSION_HMO: (20.0, 35.0, 50.0),
    PrecedentType.CONVERSION_FLATS: (25.0, 40.0, 60.0),
    PrecedentType.CHANGE_OF_USE: (10.0, 20.0, 35.0),

    # Major development - highest potential but most uncertainty
    PrecedentType.NEW_BUILD: (30.0, 50.0, 80.0),
    PrecedentType.DEMOLITION_REBUILD: (25.0, 45.0, 70.0),
    PrecedentType.SUBDIVISION: (20.0, 35.0, 55.0),

    # PD - modest but more certain
    PrecedentType.PERMITTED_DEVELOPMENT: (5.0, 8.0, 12.0),

    # Other - conservative estimate
    PrecedentType.OTHER: (3.0, 7.0, 12.0),
}


# Modifiers based on constraints
CONSTRAINT_MODIFIERS = {
    "listed_building": -0.5,  # Halve uplift expectations
    "listed_grade_1": -0.8,  # 80% reduction
    "listed_grade_2_star": -0.6,  # 60% reduction
    "conservation_area": -0.2,  # 20% reduction
    "green_belt": -0.4,  # 40% reduction
    "article_4": -0.15,  # 15% reduction
    "flood_zone_3": -0.25,  # 25% reduction
    "leasehold": -0.1,  # 10% reduction (freeholder share)
}

# Positive modifiers
POSITIVE_MODIFIERS = {
    "large_plot": 0.15,  # 15% bonus
    "pd_rights": 0.1,  # 10% bonus for certainty
    "freehold": 0.05,  # 5% bonus
    "high_precedent_approval": 0.1,  # 10% bonus
}


def estimate_uplift(
    context: PlanningContext,
    current_value: int,
    precedent_approval_rate: Optional[float] = None,
) -> UpliftEstimate:
    """
    Estimate potential value uplift from planning permission.

    Args:
        context: Planning context with property details
        current_value: Current property value (GBP)
        precedent_approval_rate: Approval rate from precedent analysis (0-100)

    Returns:
        UpliftEstimate with ranges and confidence
    """
    # Get base uplift range for development type
    base_range = UPLIFT_RANGES.get(
        context.proposed_type,
        UPLIFT_RANGES[PrecedentType.OTHER]
    )

    low, mid, high = base_range

    # Apply constraint modifiers
    total_modifier = 0.0
    assumptions = []
    caveats = []

    # Negative modifiers
    if context.listed_building:
        grade = context.listed_grade.upper() if context.listed_grade else "II"
        if grade == "I":
            total_modifier += CONSTRAINT_MODIFIERS["listed_grade_1"]
            caveats.append("Grade I listing severely limits development scope")
        elif grade == "II*":
            total_modifier += CONSTRAINT_MODIFIERS["listed_grade_2_star"]
            caveats.append("Grade II* listing significantly constrains works")
        else:
            total_modifier += CONSTRAINT_MODIFIERS["listed_building"]
            caveats.append("Listed building status limits alteration scope")

    if context.conservation_area:
        total_modifier += CONSTRAINT_MODIFIERS["conservation_area"]
        caveats.append("Conservation area requires sympathetic design")

    if context.green_belt:
        total_modifier += CONSTRAINT_MODIFIERS["green_belt"]
        caveats.append("Green Belt severely restricts development")

    if context.article_4_direction:
        total_modifier += CONSTRAINT_MODIFIERS["article_4"]
        caveats.append("Article 4 removes permitted development rights")

    if context.flood_zone == 3:
        total_modifier += CONSTRAINT_MODIFIERS["flood_zone_3"]
        caveats.append("Flood Zone 3 adds cost and complexity")

    if context.tenure.lower() == "leasehold":
        total_modifier += CONSTRAINT_MODIFIERS["leasehold"]
        caveats.append("Leasehold: freeholder may share in uplift")

    # Positive modifiers
    if context.plot_size_sqft and context.plot_size_sqft > 5000:
        total_modifier += POSITIVE_MODIFIERS["large_plot"]
        assumptions.append("Large plot provides development flexibility")

    if context.tenure.lower() == "freehold":
        total_modifier += POSITIVE_MODIFIERS["freehold"]
        assumptions.append("Freehold ownership gives full control")

    # Check for PD rights potential
    has_pd_rights = (
        not context.listed_building and
        not context.article_4_direction and
        context.property_type.lower() not in ["flat", "maisonette"] and
        context.proposed_type in [
            PrecedentType.EXTENSION_REAR,
            PrecedentType.EXTENSION_LOFT,
            PrecedentType.PERMITTED_DEVELOPMENT,
        ]
    )
    if has_pd_rights:
        total_modifier += POSITIVE_MODIFIERS["pd_rights"]
        assumptions.append("Permitted development may reduce planning risk")

    if precedent_approval_rate and precedent_approval_rate >= 75:
        total_modifier += POSITIVE_MODIFIERS["high_precedent_approval"]
        assumptions.append("Strong local precedent for similar developments")

    # Apply modifiers to range
    modifier = 1.0 + total_modifier
    modifier = max(0.1, modifier)  # Floor at 10% of base

    adjusted_low = low * modifier
    adjusted_mid = mid * modifier
    adjusted_high = high * modifier

    # Calculate absolute values
    value_low = int(current_value * adjusted_low / 100)
    value_mid = int(current_value * adjusted_mid / 100)
    value_high = int(current_value * adjusted_high / 100)

    # Determine confidence level
    confidence = _calculate_confidence(context, precedent_approval_rate)

    # Add standard caveats
    caveats.extend([
        "Estimates based on general market assumptions",
        "Actual uplift depends on quality of execution",
        "Build costs not deducted from uplift figures",
        "Market conditions may vary",
    ])

    return UpliftEstimate(
        percent_low=round(adjusted_low, 1),
        percent_mid=round(adjusted_mid, 1),
        percent_high=round(adjusted_high, 1),
        value_low=value_low,
        value_mid=value_mid,
        value_high=value_high,
        confidence=confidence,
        assumptions=assumptions,
        caveats=caveats,
    )


def _calculate_confidence(
    context: PlanningContext,
    precedent_approval_rate: Optional[float],
) -> str:
    """
    Calculate confidence level in uplift estimate.

    Returns: "high", "medium", or "low"
    """
    score = 50  # Start neutral

    # Positive factors
    if precedent_approval_rate:
        if precedent_approval_rate >= 80:
            score += 20
        elif precedent_approval_rate >= 60:
            score += 10

    if context.proposed_type == PrecedentType.PERMITTED_DEVELOPMENT:
        score += 15  # More certain

    if context.tenure.lower() == "freehold":
        score += 5

    # Negative factors
    if context.listed_building:
        score -= 20  # Much more uncertainty

    if context.green_belt:
        score -= 15

    if not context.nearby_precedents:
        score -= 10  # No data = less confidence

    # Convert to label
    if score >= 65:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"


def calculate_uplift_range(
    context: PlanningContext,
    current_value: int,
) -> tuple[int, int]:
    """
    Simple helper to get just the value range.

    Returns:
        Tuple of (low_value, high_value)
    """
    estimate = estimate_uplift(context, current_value)
    return (estimate.value_low, estimate.value_high)
