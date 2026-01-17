"""
Planning Upside Engine - Precedent Analysis.

Analyzes nearby planning precedents to assess likelihood of success.
"""

from datetime import datetime
from typing import Optional

from .models import (
    PlanningPrecedent,
    PrecedentType,
    PlanningContext,
)


# Weights for precedent scoring
RECENCY_DECAY_YEARS = 5.0  # Precedents older than this have reduced weight
MAX_DISTANCE_METERS = 500.0  # Precedents beyond this distance are less relevant
MIN_SIMILARITY_THRESHOLD = 0.3  # Minimum similarity to consider relevant


def get_relevant_precedents(
    context: PlanningContext,
    min_similarity: float = MIN_SIMILARITY_THRESHOLD,
) -> list[PlanningPrecedent]:
    """
    Filter precedents to those relevant to the proposed development.

    Args:
        context: Planning context with nearby_precedents
        min_similarity: Minimum similarity score to include

    Returns:
        List of relevant precedents, sorted by relevance
    """
    relevant = []

    for precedent in context.nearby_precedents:
        # Skip if below similarity threshold
        if precedent.similarity_score < min_similarity:
            continue

        # Skip if too old (> 10 years)
        if precedent.recency_years and precedent.recency_years > 10:
            continue

        # Skip if too far (> 1km)
        if precedent.distance_meters and precedent.distance_meters > 1000:
            continue

        # Prefer precedents of the same type
        type_match = precedent.precedent_type == context.proposed_type

        # Calculate relevance score for sorting
        relevance = _calculate_relevance(precedent, type_match)
        relevant.append((precedent, relevance))

    # Sort by relevance descending
    relevant.sort(key=lambda x: x[1], reverse=True)

    return [p for p, _ in relevant]


def _calculate_relevance(
    precedent: PlanningPrecedent,
    type_match: bool,
) -> float:
    """Calculate overall relevance score for a precedent."""
    score = precedent.similarity_score

    # Boost for type match
    if type_match:
        score *= 1.5

    # Recency bonus (more recent = more relevant)
    if precedent.recency_years is not None:
        recency_factor = max(0, 1 - (precedent.recency_years / 10))
        score *= (0.5 + 0.5 * recency_factor)

    # Distance penalty (closer = more relevant)
    if precedent.distance_meters is not None:
        distance_factor = max(0, 1 - (precedent.distance_meters / 1000))
        score *= (0.5 + 0.5 * distance_factor)

    return score


def analyze_precedents(context: PlanningContext) -> dict:
    """
    Analyze all relevant precedents for insights.

    Returns:
        Dictionary with analysis results:
        - approval_rate: Percentage of approved applications
        - recent_approvals: Count of approvals in last 3 years
        - recent_refusals: Count of refusals in last 3 years
        - common_conditions: Most frequent conditions applied
        - common_refusal_reasons: Most frequent refusal reasons
        - insights: List of human-readable insights
    """
    relevant = get_relevant_precedents(context)

    if not relevant:
        return {
            "approval_rate": None,
            "recent_approvals": 0,
            "recent_refusals": 0,
            "common_conditions": [],
            "common_refusal_reasons": [],
            "insights": ["No relevant planning precedents found in the area."],
        }

    # Calculate approval statistics
    approved = [p for p in relevant if p.approved]
    refused = [p for p in relevant if not p.approved]

    approval_rate = len(approved) / len(relevant) * 100 if relevant else 0

    # Recent activity (last 3 years)
    recent_approvals = sum(
        1 for p in approved
        if p.recency_years is not None and p.recency_years <= 3
    )
    recent_refusals = sum(
        1 for p in refused
        if p.recency_years is not None and p.recency_years <= 3
    )

    # Aggregate conditions and refusal reasons
    all_conditions = []
    for p in approved:
        all_conditions.extend(p.conditions)

    all_refusal_reasons = []
    for p in refused:
        all_refusal_reasons.extend(p.refusal_reasons)

    # Find most common
    common_conditions = _get_most_common(all_conditions, 3)
    common_refusal_reasons = _get_most_common(all_refusal_reasons, 3)

    # Generate insights
    insights = _generate_insights(
        context=context,
        relevant=relevant,
        approved=approved,
        refused=refused,
        approval_rate=approval_rate,
        common_conditions=common_conditions,
        common_refusal_reasons=common_refusal_reasons,
    )

    return {
        "approval_rate": approval_rate,
        "recent_approvals": recent_approvals,
        "recent_refusals": recent_refusals,
        "common_conditions": common_conditions,
        "common_refusal_reasons": common_refusal_reasons,
        "insights": insights,
    }


def _get_most_common(items: list[str], n: int) -> list[str]:
    """Get the n most common items from a list."""
    if not items:
        return []

    counts: dict[str, int] = {}
    for item in items:
        normalized = item.strip().lower()
        counts[normalized] = counts.get(normalized, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [item for item, _ in sorted_items[:n]]


def _generate_insights(
    context: PlanningContext,
    relevant: list[PlanningPrecedent],
    approved: list[PlanningPrecedent],
    refused: list[PlanningPrecedent],
    approval_rate: float,
    common_conditions: list[str],
    common_refusal_reasons: list[str],
) -> list[str]:
    """Generate human-readable insights from precedent analysis."""
    insights = []

    # Overall approval rate
    if approval_rate >= 80:
        insights.append(
            f"High approval rate ({approval_rate:.0f}%) for similar applications "
            f"in this area suggests a planning-friendly environment."
        )
    elif approval_rate >= 60:
        insights.append(
            f"Moderate approval rate ({approval_rate:.0f}%) indicates "
            f"reasonable prospects with appropriate design."
        )
    elif approval_rate >= 40:
        insights.append(
            f"Mixed approval rate ({approval_rate:.0f}%) suggests careful "
            f"attention to local planning policies is required."
        )
    else:
        insights.append(
            f"Low approval rate ({approval_rate:.0f}%) indicates challenging "
            f"planning environment. Professional advice strongly recommended."
        )

    # Type-specific precedents
    type_matches = [
        p for p in relevant
        if p.precedent_type == context.proposed_type
    ]
    if type_matches:
        type_approved = sum(1 for p in type_matches if p.approved)
        type_total = len(type_matches)
        insights.append(
            f"Found {type_total} precedents for {context.proposed_type.value} "
            f"applications, {type_approved} approved."
        )

    # Recent trends
    recent = [p for p in relevant if p.recency_years and p.recency_years <= 2]
    if recent:
        recent_approved = sum(1 for p in recent if p.approved)
        if recent_approved == len(recent):
            insights.append(
                f"All {len(recent)} recent applications (last 2 years) were approved, "
                f"suggesting current favorable policy."
            )
        elif recent_approved == 0:
            insights.append(
                f"All {len(recent)} recent applications were refused. "
                f"Review current local plan policies carefully."
            )

    # Common conditions warning
    if common_conditions:
        insights.append(
            f"Common conditions applied: {', '.join(common_conditions)}. "
            f"Budget for compliance."
        )

    # Refusal reasons warning
    if common_refusal_reasons:
        insights.append(
            f"Common refusal reasons: {', '.join(common_refusal_reasons)}. "
            f"Address these in any application."
        )

    return insights


def calculate_precedent_score(context: PlanningContext) -> int:
    """
    Calculate a precedent-based score (0-100).

    Higher scores indicate more favorable precedent history.

    Args:
        context: Planning context with precedent data

    Returns:
        Score from 0-100
    """
    relevant = get_relevant_precedents(context)

    if not relevant:
        # No data = neutral score
        return 50

    # Base score from approval rate
    approved_count = sum(1 for p in relevant if p.approved)
    approval_rate = approved_count / len(relevant)
    base_score = int(approval_rate * 60)  # Up to 60 points from approval rate

    # Bonus for type-specific approvals
    type_matches = [
        p for p in relevant
        if p.precedent_type == context.proposed_type and p.approved
    ]
    if type_matches:
        type_bonus = min(20, len(type_matches) * 5)  # Up to 20 points
        base_score += type_bonus

    # Bonus for recent approvals (last 3 years)
    recent_approvals = [
        p for p in relevant
        if p.approved and p.recency_years and p.recency_years <= 3
    ]
    if recent_approvals:
        recency_bonus = min(15, len(recent_approvals) * 3)  # Up to 15 points
        base_score += recency_bonus

    # Penalty for recent refusals
    recent_refusals = [
        p for p in relevant
        if not p.approved and p.recency_years and p.recency_years <= 3
    ]
    if recent_refusals:
        refusal_penalty = min(20, len(recent_refusals) * 5)
        base_score -= refusal_penalty

    # Bonus for close proximity approvals
    close_approvals = [
        p for p in relevant
        if p.approved and p.distance_meters and p.distance_meters <= 100
    ]
    if close_approvals:
        proximity_bonus = min(10, len(close_approvals) * 5)
        base_score += proximity_bonus

    return max(0, min(100, base_score))
