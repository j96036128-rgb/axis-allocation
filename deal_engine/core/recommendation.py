"""
Deal recommendation engine.

Combines scoring, conviction, and rejection analysis to produce
actionable recommendations for deal-mandate matches.

Phase 6: Adds optional planning upside integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from .mandate import Mandate
from .listing import Listing
from .scoring import score_listing, ScoringResult
from .conviction import assess_conviction, ConvictionAssessment, ConvictionLevel
from .rejection import evaluate_rejection, RejectionResult
from .review import create_review, DealReview, ReviewState

# Planning module import (optional - may not be available)
try:
    from deal_engine.planning import (
        PlanningContext,
        PlanningAssessment,
        get_planning_assessment,
    )
    PLANNING_AVAILABLE = True
except ImportError:
    PLANNING_AVAILABLE = False
    PlanningContext = None
    PlanningAssessment = None


class RecommendationAction(Enum):
    """Recommended action for a deal."""

    PURSUE = "pursue"  # Strong recommendation to proceed
    CONSIDER = "consider"  # Worth reviewing with caveats
    WATCH = "watch"  # Monitor for changes
    PASS = "pass"  # Do not pursue


@dataclass
class DealRecommendation:
    """
    Complete recommendation for a listing-mandate match.

    Aggregates all analysis into a single actionable output.
    """

    # Identifiers
    listing_id: str
    mandate_id: str

    # Recommendation
    action: RecommendationAction
    priority_rank: int  # 1 = highest priority

    # Component results
    scoring: ScoringResult
    conviction: ConvictionAssessment
    rejection: RejectionResult

    # Summary
    headline: str
    rationale: str
    next_steps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    # Phase 6: Optional planning assessment
    planning: Optional["PlanningAssessment"] = None

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def is_actionable(self) -> bool:
        """Check if recommendation suggests action."""
        return self.action in (RecommendationAction.PURSUE, RecommendationAction.CONSIDER)

    @property
    def has_planning_upside(self) -> bool:
        """Check if planning assessment indicates upside potential."""
        if not self.planning:
            return False
        return self.planning.planning_score.score >= 60

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "listing_id": self.listing_id,
            "mandate_id": self.mandate_id,
            "action": self.action.value,
            "priority_rank": self.priority_rank,
            "is_actionable": self.is_actionable,
            "headline": self.headline,
            "rationale": self.rationale,
            "next_steps": self.next_steps,
            "risks": self.risks,
            "scoring": self.scoring.to_dict(),
            "conviction": self.conviction.to_dict(),
            "rejection": self.rejection.to_dict(),
            "generated_at": self.generated_at.isoformat(),
        }

        # Include planning if available
        if self.planning:
            result["planning"] = self.planning.to_dict()
            result["has_planning_upside"] = self.has_planning_upside

        return result

    def to_summary(self) -> dict:
        """Convert to brief summary format."""
        summary = {
            "listing_id": self.listing_id,
            "action": self.action.value,
            "priority_rank": self.priority_rank,
            "score": round(self.scoring.total_score, 1),
            "grade": self.scoring.match_grade,
            "conviction": self.conviction.level.value,
            "headline": self.headline,
        }

        # Include planning summary if available
        if self.planning:
            summary["planning_score"] = self.planning.planning_score.score
            summary["planning_label"] = self.planning.planning_score.label.value
            summary["has_planning_upside"] = self.has_planning_upside

        return summary


def _determine_action(
    scoring: ScoringResult,
    conviction: ConvictionAssessment,
    rejection: RejectionResult,
    mandate: Mandate
) -> RecommendationAction:
    """
    Determine recommended action based on analysis.

    Uses mandate's deal_criteria thresholds for configurable decision-making.
    """
    deal = mandate.deal_criteria

    # Hard rejection = PASS
    if rejection.rejected:
        return RecommendationAction.PASS

    # High conviction + score >= pursue threshold = PURSUE
    if conviction.level == ConvictionLevel.HIGH and scoring.total_score >= deal.pursue_score_threshold:
        return RecommendationAction.PURSUE

    # Medium conviction or score >= consider threshold = CONSIDER
    if conviction.level == ConvictionLevel.MEDIUM:
        return RecommendationAction.CONSIDER
    if conviction.level == ConvictionLevel.HIGH and scoring.total_score >= deal.consider_score_threshold:
        return RecommendationAction.CONSIDER

    # Low conviction but passes filters and meets minimum score = WATCH
    if conviction.level == ConvictionLevel.LOW and scoring.passes_hard_filters:
        if scoring.total_score >= deal.min_overall_score:
            return RecommendationAction.WATCH

    # Default to PASS
    return RecommendationAction.PASS


def _calculate_priority(
    action: RecommendationAction,
    scoring: ScoringResult,
    conviction: ConvictionAssessment,
    mandate: Mandate
) -> int:
    """
    Calculate priority rank (1 = highest).

    Considers action type, score, conviction, and mandate priority.
    """
    # Base priority by action
    action_base = {
        RecommendationAction.PURSUE: 1,
        RecommendationAction.CONSIDER: 2,
        RecommendationAction.WATCH: 3,
        RecommendationAction.PASS: 4,
    }

    base = action_base.get(action, 4)

    # Adjust within band based on score (0-9 adjustment)
    score_adjustment = int((100 - scoring.total_score) / 10)

    # Factor in mandate priority (1-10)
    mandate_factor = mandate.priority - 1  # 0-9

    # Combine: base * 100 + score_adjustment * 10 + mandate_factor
    return base * 100 + score_adjustment * 10 + mandate_factor


def _generate_headline(
    listing: Listing,
    action: RecommendationAction,
    scoring: ScoringResult,
    conviction: ConvictionAssessment
) -> str:
    """Generate attention-grabbing headline."""
    if action == RecommendationAction.PURSUE:
        return f"STRONG MATCH: {listing.title} ({scoring.match_grade} grade, {conviction.level.value} conviction)"
    elif action == RecommendationAction.CONSIDER:
        return f"REVIEW: {listing.title} - {scoring.total_score:.0f}/100 score, {conviction.level.value} conviction"
    elif action == RecommendationAction.WATCH:
        return f"MONITOR: {listing.title} - potential if conditions change"
    else:
        return f"PASS: {listing.title} - does not meet criteria"


def _generate_rationale(
    action: RecommendationAction,
    scoring: ScoringResult,
    conviction: ConvictionAssessment,
    rejection: RejectionResult,
    mandate: Optional[Mandate] = None
) -> str:
    """
    Generate explanation for the recommendation with threshold transparency.

    Includes mandate thresholds in explanations when available.
    """
    deal = mandate.deal_criteria if mandate else None

    if action == RecommendationAction.PURSUE:
        positives = conviction.positive_factors[:2]
        reasons = [f.reason for f in positives]
        threshold_info = ""
        if deal:
            threshold_info = f" Score {scoring.total_score:.0f}/100 exceeds pursue threshold ({deal.pursue_score_threshold:.0f})."
        return f"Strong alignment with mandate criteria.{threshold_info} {'. '.join(reasons)}"

    elif action == RecommendationAction.CONSIDER:
        summary = conviction.summary
        threshold_info = ""
        if deal:
            threshold_info = f" Score {scoring.total_score:.0f}/100 meets consider threshold ({deal.consider_score_threshold:.0f})."
        if rejection.soft_rejections:
            concerns = [r.title for r in rejection.soft_rejections[:2]]
            return f"{summary}{threshold_info} Concerns to address: {', '.join(concerns)}."
        return f"{summary}{threshold_info}"

    elif action == RecommendationAction.WATCH:
        negatives = conviction.negative_factors[:2]
        threshold_info = ""
        if deal:
            threshold_info = f" Score {scoring.total_score:.0f}/100 above minimum ({deal.min_overall_score:.0f}) but below consider threshold ({deal.consider_score_threshold:.0f})."
        if negatives:
            issues = [f.reason for f in negatives]
            return f"Marginal fit.{threshold_info} Issues: {'. '.join(issues)}"
        return f"Marginal fit with current criteria.{threshold_info} Monitor for price or condition changes."

    else:
        if rejection.hard_rejections:
            reasons = [r.title for r in rejection.hard_rejections[:2]]
            return f"Rejected due to: {', '.join(reasons)}."
        threshold_info = ""
        if deal:
            threshold_info = f" Score {scoring.total_score:.0f}/100 below minimum threshold ({deal.min_overall_score:.0f})."
        return f"Does not meet minimum mandate criteria.{threshold_info}"


def _generate_next_steps(
    action: RecommendationAction,
    listing: Listing,
    conviction: ConvictionAssessment,
    rejection: RejectionResult
) -> list[str]:
    """Generate actionable next steps."""
    steps = []

    if action == RecommendationAction.PURSUE:
        steps.append("Request detailed property information pack")
        steps.append("Schedule site visit / virtual tour")
        steps.append("Prepare investment committee memo")
        if listing.property_details.has_tenants:
            steps.append("Request tenancy schedule and rent roll")

    elif action == RecommendationAction.CONSIDER:
        if rejection.soft_rejections:
            for r in rejection.soft_rejections[:2]:
                steps.append(f"Investigate: {r.remedy}")
        steps.append("Gather additional due diligence information")
        steps.append("Assess if concerns can be mitigated")

    elif action == RecommendationAction.WATCH:
        steps.append("Set price alert for this listing")
        steps.append("Monitor for status changes (price reduction, etc.)")
        if conviction.negative_factors:
            steps.append("Re-evaluate if market conditions change")

    return steps


def _generate_risks(
    listing: Listing,
    conviction: ConvictionAssessment,
    rejection: RejectionResult
) -> list[str]:
    """Generate risk factors to consider."""
    risks = []

    # From conviction negative factors
    for factor in conviction.negative_factors:
        risks.append(factor.reason)

    # From soft rejections
    for reason in rejection.soft_rejections:
        risks.append(f"{reason.title}: {reason.explanation}")

    return risks[:5]  # Limit to top 5


def generate_recommendation(
    listing: Listing,
    mandate: Mandate,
    planning_context: Optional["PlanningContext"] = None,
) -> DealRecommendation:
    """
    Generate a complete recommendation for a listing-mandate pair.

    Runs all analysis and synthesizes into actionable output.
    Uses mandate's deal_criteria for configurable thresholds.

    Args:
        listing: Property listing to evaluate
        mandate: Investor mandate to match against
        planning_context: Optional planning context for upside analysis

    Returns:
        DealRecommendation with all analysis results
    """
    # Run all analysis
    scoring = score_listing(listing, mandate)
    conviction = assess_conviction(listing, mandate, scoring)
    rejection = evaluate_rejection(listing, mandate)

    # Determine action and priority (now using mandate thresholds)
    action = _determine_action(scoring, conviction, rejection, mandate)
    priority = _calculate_priority(action, scoring, conviction, mandate)

    # Generate narrative elements with enhanced transparency
    headline = _generate_headline(listing, action, scoring, conviction)
    rationale = _generate_rationale(action, scoring, conviction, rejection, mandate)
    next_steps = _generate_next_steps(action, listing, conviction, rejection)
    risks = _generate_risks(listing, conviction, rejection)

    # Phase 6: Optional planning assessment
    planning = None
    if PLANNING_AVAILABLE and planning_context:
        try:
            current_value = listing.financial.asking_price
            planning = get_planning_assessment(planning_context, current_value)

            # Enhance recommendation with planning insights
            headline, rationale, next_steps, risks = _enhance_with_planning(
                planning=planning,
                headline=headline,
                rationale=rationale,
                next_steps=next_steps,
                risks=risks,
                action=action,
            )

            # Boost priority if strong planning upside
            if planning.planning_score.score >= 70:
                priority = max(1, priority - 50)  # Boost priority
        except Exception:
            # Planning analysis failed - continue without it
            planning = None

    return DealRecommendation(
        listing_id=listing.listing_id,
        mandate_id=mandate.mandate_id,
        action=action,
        priority_rank=priority,
        scoring=scoring,
        conviction=conviction,
        rejection=rejection,
        headline=headline,
        rationale=rationale,
        next_steps=next_steps,
        risks=risks,
        planning=planning,
    )


def _enhance_with_planning(
    planning: "PlanningAssessment",
    headline: str,
    rationale: str,
    next_steps: list[str],
    risks: list[str],
    action: RecommendationAction,
) -> tuple[str, str, list[str], list[str]]:
    """Enhance recommendation outputs with planning insights."""
    score = planning.planning_score
    uplift = planning.uplift_estimate

    # Enhance headline for strong planning upside
    if score.score >= 70:
        headline = f"{headline} | PLANNING UPSIDE: {score.label.value.upper()}"

    # Add planning rationale
    if score.score >= 60:
        planning_note = (
            f" Planning potential: {score.label.value} ({score.score}/100) "
            f"with estimated {uplift.percent_low:.0f}%-{uplift.percent_high:.0f}% uplift."
        )
        rationale = rationale + planning_note

    # Add planning next steps
    if action in (RecommendationAction.PURSUE, RecommendationAction.CONSIDER):
        if planning.recommendations:
            next_steps = list(next_steps)  # Copy
            next_steps.append(f"Planning: {planning.recommendations[0]}")

    # Add planning risks
    if planning.negative_factors:
        risks = list(risks)  # Copy
        for neg in planning.negative_factors[:2]:
            if neg.startswith("BLOCKER:"):
                risks.insert(0, f"Planning: {neg}")
            else:
                risks.append(f"Planning: {neg}")

    return headline, rationale, next_steps, risks


def generate_recommendations(
    listings: list[Listing],
    mandate: Mandate,
    planning_contexts: Optional[dict[str, "PlanningContext"]] = None,
) -> list[DealRecommendation]:
    """
    Generate recommendations for multiple listings.

    Args:
        listings: List of property listings
        mandate: Investor mandate to match against
        planning_contexts: Optional dict mapping listing_id to PlanningContext

    Returns:
        List sorted by priority rank (best first).
    """
    recommendations = []
    for listing in listings:
        # Get planning context if available for this listing
        planning_ctx = None
        if planning_contexts:
            planning_ctx = planning_contexts.get(listing.listing_id)

        rec = generate_recommendation(listing, mandate, planning_ctx)
        recommendations.append(rec)

    # Sort by priority rank
    recommendations.sort(key=lambda r: r.priority_rank)

    return recommendations


def get_actionable_recommendations(
    recommendations: list[DealRecommendation]
) -> list[DealRecommendation]:
    """Filter to only actionable recommendations (PURSUE or CONSIDER)."""
    return [r for r in recommendations if r.is_actionable]


@dataclass
class RecommendationReport:
    """
    Summary report of recommendations for a mandate.
    """

    mandate_id: str
    mandate_name: str
    generated_at: datetime
    total_listings: int
    recommendations: list[DealRecommendation]

    @property
    def pursue_count(self) -> int:
        return sum(1 for r in self.recommendations if r.action == RecommendationAction.PURSUE)

    @property
    def consider_count(self) -> int:
        return sum(1 for r in self.recommendations if r.action == RecommendationAction.CONSIDER)

    @property
    def watch_count(self) -> int:
        return sum(1 for r in self.recommendations if r.action == RecommendationAction.WATCH)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.recommendations if r.action == RecommendationAction.PASS)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "mandate_id": self.mandate_id,
            "mandate_name": self.mandate_name,
            "generated_at": self.generated_at.isoformat(),
            "total_listings": self.total_listings,
            "summary": {
                "pursue": self.pursue_count,
                "consider": self.consider_count,
                "watch": self.watch_count,
                "pass": self.pass_count,
            },
            "actionable_count": self.pursue_count + self.consider_count,
            "recommendations": [r.to_summary() for r in self.recommendations],
        }

    def to_detailed_dict(self) -> dict:
        """Convert to detailed dictionary with full recommendation data."""
        result = self.to_dict()
        result["recommendations"] = [r.to_dict() for r in self.recommendations]
        return result


def generate_report(
    listings: list[Listing],
    mandate: Mandate,
    planning_contexts: Optional[dict[str, "PlanningContext"]] = None,
) -> RecommendationReport:
    """
    Generate a complete recommendation report for a mandate.

    Args:
        listings: List of property listings
        mandate: Investor mandate to match against
        planning_contexts: Optional dict mapping listing_id to PlanningContext

    Returns:
        RecommendationReport with all recommendations
    """
    recommendations = generate_recommendations(listings, mandate, planning_contexts)

    return RecommendationReport(
        mandate_id=mandate.mandate_id,
        mandate_name=mandate.investor_name,
        generated_at=datetime.now(),
        total_listings=len(listings),
        recommendations=recommendations,
    )
