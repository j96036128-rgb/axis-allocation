"""
Planning Upside Engine - Score Calculation.

Combines precedent analysis, feasibility assessment, and uplift estimation
into a single Planning Potential Score (0-100).
"""

from typing import Optional

from .models import (
    PlanningContext,
    PlanningAssessment,
    PlanningScore,
    PlanningLabel,
    UpliftEstimate,
)
from .precedent import analyze_precedents, calculate_precedent_score
from .feasibility import assess_feasibility
from .uplift import estimate_uplift


# Score thresholds for labels
EXCEPTIONAL_THRESHOLD = 80
STRONG_THRESHOLD = 60
MEDIUM_THRESHOLD = 40

# Component weights
PRECEDENT_WEIGHT = 0.35
FEASIBILITY_WEIGHT = 0.40
UPLIFT_WEIGHT = 0.25


def calculate_planning_score(
    precedent_score: int,
    feasibility_score: int,
    uplift_percent_mid: float,
) -> PlanningScore:
    """
    Calculate the overall planning potential score.

    Args:
        precedent_score: Score from precedent analysis (0-100)
        feasibility_score: Score from feasibility assessment (0-100)
        uplift_percent_mid: Mid-point uplift percentage estimate

    Returns:
        PlanningScore with overall score and label
    """
    # Normalize uplift percentage to 0-100 scale
    # Assume 30% uplift = 100 score (very high)
    uplift_score = min(100, int(uplift_percent_mid / 30 * 100))

    # Calculate weighted score
    weighted_score = (
        precedent_score * PRECEDENT_WEIGHT +
        feasibility_score * FEASIBILITY_WEIGHT +
        uplift_score * UPLIFT_WEIGHT
    )

    overall_score = int(weighted_score)

    # Determine label
    if overall_score >= EXCEPTIONAL_THRESHOLD:
        label = PlanningLabel.EXCEPTIONAL
    elif overall_score >= STRONG_THRESHOLD:
        label = PlanningLabel.STRONG
    elif overall_score >= MEDIUM_THRESHOLD:
        label = PlanningLabel.MEDIUM
    else:
        label = PlanningLabel.LOW

    return PlanningScore(
        score=overall_score,
        label=label,
        precedent_score=precedent_score,
        feasibility_score=feasibility_score,
        uplift_score=uplift_score,
    )


def get_planning_assessment(
    context: PlanningContext,
    current_value: int,
) -> PlanningAssessment:
    """
    Generate a complete planning potential assessment.

    This is the main entry point for the planning engine.

    Args:
        context: Planning context with all property information
        current_value: Current property value (GBP) for uplift calculation

    Returns:
        PlanningAssessment with score, uplift estimate, and rationale
    """
    # Run component analyses
    precedent_analysis = analyze_precedents(context)
    precedent_score = calculate_precedent_score(context)

    feasibility_result = assess_feasibility(context)
    feasibility_score = feasibility_result.score

    # Get approval rate for uplift estimation
    approval_rate = precedent_analysis.get("approval_rate")

    uplift_estimate = estimate_uplift(
        context=context,
        current_value=current_value,
        precedent_approval_rate=approval_rate,
    )

    # Calculate overall score
    planning_score = calculate_planning_score(
        precedent_score=precedent_score,
        feasibility_score=feasibility_score,
        uplift_percent_mid=uplift_estimate.percent_mid,
    )

    # Build rationale
    rationale = _build_rationale(
        planning_score=planning_score,
        precedent_analysis=precedent_analysis,
        feasibility_result=feasibility_result,
        uplift_estimate=uplift_estimate,
        context=context,
    )

    # Collect positive/negative factors
    positive_factors = []
    negative_factors = []

    # From feasibility
    for factor, description in feasibility_result.positive_factors:
        positive_factors.append(description)
    for factor, description in feasibility_result.negative_factors:
        negative_factors.append(description)

    # From precedent
    if approval_rate and approval_rate >= 70:
        positive_factors.append(
            f"High local approval rate ({approval_rate:.0f}%)"
        )
    elif approval_rate and approval_rate < 40:
        negative_factors.append(
            f"Low local approval rate ({approval_rate:.0f}%)"
        )

    # From uplift
    if uplift_estimate.percent_mid >= 20:
        positive_factors.append(
            f"Strong uplift potential ({uplift_estimate.percent_mid:.0f}%)"
        )

    # Build recommendations
    recommendations = list(feasibility_result.recommendations)

    # Add blockers as warnings
    if feasibility_result.blockers:
        for blocker in feasibility_result.blockers:
            negative_factors.insert(0, f"BLOCKER: {blocker}")

    # Add general recommendations based on score
    if planning_score.score >= EXCEPTIONAL_THRESHOLD:
        recommendations.append(
            "Strong planning potential - consider engaging planning "
            "consultant for pre-application"
        )
    elif planning_score.score >= STRONG_THRESHOLD:
        recommendations.append(
            "Good planning potential - research local plan policies "
            "and consider pre-application advice"
        )
    elif planning_score.score >= MEDIUM_THRESHOLD:
        recommendations.append(
            "Moderate planning potential - thorough due diligence "
            "recommended before purchase"
        )
    else:
        recommendations.append(
            "Limited planning potential - factor into valuation "
            "and do not over-pay for perceived upside"
        )

    return PlanningAssessment(
        planning_score=planning_score,
        uplift_estimate=uplift_estimate,
        rationale=rationale,
        positive_factors=positive_factors[:5],  # Limit to top 5
        negative_factors=negative_factors[:5],
        recommendations=recommendations[:5],
    )


def _build_rationale(
    planning_score: PlanningScore,
    precedent_analysis: dict,
    feasibility_result,
    uplift_estimate: UpliftEstimate,
    context: PlanningContext,
) -> list[str]:
    """Build human-readable rationale for the assessment."""
    rationale = []

    # Overall assessment
    label = planning_score.label.value.upper()
    score = planning_score.score
    rationale.append(
        f"Overall planning potential assessed as {label} ({score}/100)."
    )

    # Precedent summary
    approval_rate = precedent_analysis.get("approval_rate")
    if approval_rate is not None:
        recent_approvals = precedent_analysis.get("recent_approvals", 0)
        recent_refusals = precedent_analysis.get("recent_refusals", 0)
        rationale.append(
            f"Precedent analysis: {approval_rate:.0f}% approval rate "
            f"({recent_approvals} recent approvals, {recent_refusals} refusals)."
        )
    else:
        rationale.append(
            "No relevant planning precedents found in provided data."
        )

    # Add precedent insights
    insights = precedent_analysis.get("insights", [])
    rationale.extend(insights[:2])  # Top 2 insights

    # Feasibility summary
    if feasibility_result.blockers:
        rationale.append(
            f"IMPORTANT: {len(feasibility_result.blockers)} significant "
            f"constraint(s) identified that may block development."
        )
    else:
        rationale.append(
            f"Feasibility score: {feasibility_result.score}/100 "
            f"based on property constraints."
        )

    # Uplift summary
    rationale.append(
        f"Estimated uplift: {uplift_estimate.percent_low:.0f}%-"
        f"{uplift_estimate.percent_high:.0f}% "
        f"({uplift_estimate.confidence} confidence)."
    )

    if uplift_estimate.value_mid > 0:
        rationale.append(
            f"Potential value add: {uplift_estimate.value_low:,}-"
            f"{uplift_estimate.value_high:,} GBP."
        )

    return rationale
