"""
Planning Upside Engine - Feasibility Assessment.

Evaluates planning feasibility based on property characteristics
and planning constraints using deterministic heuristics.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .models import PlanningContext, PrecedentType


class FeasibilityFactor(Enum):
    """Factors affecting planning feasibility."""

    LISTED_BUILDING = "listed_building"
    CONSERVATION_AREA = "conservation_area"
    GREEN_BELT = "green_belt"
    FLOOD_ZONE = "flood_zone"
    ARTICLE_4 = "article_4_direction"
    TREE_PRESERVATION = "tree_preservation_orders"
    PROPERTY_TYPE = "property_type"
    TENURE = "tenure"
    PLOT_SIZE = "plot_size"
    PD_RIGHTS = "permitted_development_rights"


@dataclass
class FeasibilityResult:
    """Result of feasibility assessment."""

    # Overall score (0-100)
    score: int

    # Factor breakdown
    positive_factors: list[tuple[FeasibilityFactor, str]] = field(default_factory=list)
    negative_factors: list[tuple[FeasibilityFactor, str]] = field(default_factory=list)
    neutral_factors: list[tuple[FeasibilityFactor, str]] = field(default_factory=list)

    # Blockers (factors that make development very unlikely)
    blockers: list[str] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "score": self.score,
            "positive_factors": [
                {"factor": f.value, "description": d}
                for f, d in self.positive_factors
            ],
            "negative_factors": [
                {"factor": f.value, "description": d}
                for f, d in self.negative_factors
            ],
            "neutral_factors": [
                {"factor": f.value, "description": d}
                for f, d in self.neutral_factors
            ],
            "blockers": self.blockers,
            "recommendations": self.recommendations,
        }


def assess_feasibility(context: PlanningContext) -> FeasibilityResult:
    """
    Assess planning feasibility based on property constraints.

    Uses deterministic heuristics to evaluate likelihood of
    planning success based on known constraints.

    Args:
        context: Planning context with property information

    Returns:
        FeasibilityResult with score and factor breakdown
    """
    positive: list[tuple[FeasibilityFactor, str]] = []
    negative: list[tuple[FeasibilityFactor, str]] = []
    neutral: list[tuple[FeasibilityFactor, str]] = []
    blockers: list[str] = []
    recommendations: list[str] = []

    # Start with base score
    score = 70  # Neutral starting point

    # Assess each factor
    score = _assess_listed_building(context, score, positive, negative, blockers, recommendations)
    score = _assess_conservation_area(context, score, positive, negative, blockers, recommendations)
    score = _assess_green_belt(context, score, positive, negative, blockers, recommendations)
    score = _assess_flood_zone(context, score, positive, negative, neutral, recommendations)
    score = _assess_article_4(context, score, positive, negative, neutral, recommendations)
    score = _assess_tpo(context, score, positive, negative, recommendations)
    score = _assess_property_type(context, score, positive, negative, neutral, recommendations)
    score = _assess_tenure(context, score, positive, negative, neutral, recommendations)
    score = _assess_plot_size(context, score, positive, negative, neutral, recommendations)
    score = _assess_pd_rights(context, score, positive, negative, recommendations)

    # Clamp score
    score = max(0, min(100, score))

    # Severe penalty for blockers
    if blockers:
        score = min(score, 20)

    return FeasibilityResult(
        score=score,
        positive_factors=positive,
        negative_factors=negative,
        neutral_factors=neutral,
        blockers=blockers,
        recommendations=recommendations,
    )


def _assess_listed_building(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    blockers: list,
    recommendations: list,
) -> int:
    """Assess impact of listed building status."""
    if not context.listed_building:
        positive.append((
            FeasibilityFactor.LISTED_BUILDING,
            "Property is not listed - no heritage constraints"
        ))
        return score + 5

    # Listed building - significant constraint
    grade = context.listed_grade.upper() if context.listed_grade else "II"

    if grade == "I":
        blockers.append(
            "Grade I listed building - development extremely unlikely "
            "without exceptional circumstances"
        )
        negative.append((
            FeasibilityFactor.LISTED_BUILDING,
            f"Grade I listed building - highest level of protection"
        ))
        recommendations.append(
            "Grade I listing: Consult Historic England and specialist "
            "heritage architect before any works"
        )
        return score - 40

    elif grade == "II*":
        negative.append((
            FeasibilityFactor.LISTED_BUILDING,
            f"Grade II* listed building - significant heritage constraints"
        ))
        recommendations.append(
            "Grade II* listing: Any alterations require Listed Building Consent "
            "and must preserve character"
        )
        return score - 25

    else:  # Grade II
        negative.append((
            FeasibilityFactor.LISTED_BUILDING,
            "Grade II listed building - heritage constraints apply"
        ))
        recommendations.append(
            "Grade II listing: Internal works may be possible with "
            "sympathetic design. Consult conservation officer."
        )
        return score - 15


def _assess_conservation_area(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    blockers: list,
    recommendations: list,
) -> int:
    """Assess impact of conservation area status."""
    if not context.conservation_area:
        positive.append((
            FeasibilityFactor.CONSERVATION_AREA,
            "Not in conservation area - standard planning rules apply"
        ))
        return score + 3

    negative.append((
        FeasibilityFactor.CONSERVATION_AREA,
        "Located in conservation area - design must preserve character"
    ))
    recommendations.append(
        "Conservation area: Extensions should match existing materials "
        "and respect local character. Pre-application advice recommended."
    )
    return score - 10


def _assess_green_belt(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    blockers: list,
    recommendations: list,
) -> int:
    """Assess impact of green belt status."""
    if not context.green_belt:
        return score

    # Green belt is a major constraint
    negative.append((
        FeasibilityFactor.GREEN_BELT,
        "Property in Green Belt - very limited development potential"
    ))

    # Check what type of development is proposed
    if context.proposed_type in [
        PrecedentType.NEW_BUILD,
        PrecedentType.DEMOLITION_REBUILD,
        PrecedentType.SUBDIVISION,
    ]:
        blockers.append(
            "Green Belt location: New buildings are inappropriate development "
            "and very unlikely to be approved"
        )
        return score - 40
    elif context.proposed_type in [
        PrecedentType.EXTENSION_REAR,
        PrecedentType.EXTENSION_SIDE,
        PrecedentType.EXTENSION_LOFT,
    ]:
        recommendations.append(
            "Green Belt: Limited extensions may be acceptable if not "
            "disproportionate. Check local plan policies."
        )
        return score - 20
    else:
        recommendations.append(
            "Green Belt: Development must demonstrate very special circumstances. "
            "Professional planning advice essential."
        )
        return score - 25


def _assess_flood_zone(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    neutral: list,
    recommendations: list,
) -> int:
    """Assess impact of flood zone status."""
    flood_zone = context.flood_zone

    if flood_zone == 1:
        positive.append((
            FeasibilityFactor.FLOOD_ZONE,
            "Flood Zone 1 - lowest flood risk"
        ))
        return score + 2

    elif flood_zone == 2:
        neutral.append((
            FeasibilityFactor.FLOOD_ZONE,
            "Flood Zone 2 - medium flood risk, may need FRA"
        ))
        recommendations.append(
            "Flood Zone 2: Flood Risk Assessment likely required for "
            "significant development"
        )
        return score - 5

    else:  # Zone 3
        negative.append((
            FeasibilityFactor.FLOOD_ZONE,
            "Flood Zone 3 - high flood risk, Sequential Test required"
        ))
        recommendations.append(
            "Flood Zone 3: Sequential and Exception Tests required. "
            "Flood mitigation measures will be needed."
        )
        return score - 15


def _assess_article_4(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    neutral: list,
    recommendations: list,
) -> int:
    """Assess impact of Article 4 Direction."""
    if not context.article_4_direction:
        return score

    negative.append((
        FeasibilityFactor.ARTICLE_4,
        "Article 4 Direction in place - permitted development rights removed"
    ))
    recommendations.append(
        "Article 4: Planning permission required for works that would "
        "normally be permitted development. Check scope of direction."
    )
    return score - 10


def _assess_tpo(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    recommendations: list,
) -> int:
    """Assess impact of Tree Preservation Orders."""
    if not context.tree_preservation_orders:
        return score

    negative.append((
        FeasibilityFactor.TREE_PRESERVATION,
        "Tree Preservation Orders on site may constrain development"
    ))
    recommendations.append(
        "TPO: Arboricultural survey recommended. Tree works require "
        "council consent."
    )
    return score - 5


def _assess_property_type(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    neutral: list,
    recommendations: list,
) -> int:
    """Assess feasibility based on property type."""
    prop_type = context.property_type.lower()
    proposed = context.proposed_type

    # Houses generally have more development potential
    if "house" in prop_type or "bungalow" in prop_type:
        if proposed in [
            PrecedentType.EXTENSION_LOFT,
            PrecedentType.EXTENSION_REAR,
            PrecedentType.EXTENSION_SIDE,
        ]:
            positive.append((
                FeasibilityFactor.PROPERTY_TYPE,
                "House/bungalow suitable for extension works"
            ))
            return score + 5

    # Flats have limited potential
    if prop_type == "flat":
        if proposed in [
            PrecedentType.EXTENSION_LOFT,
            PrecedentType.EXTENSION_REAR,
            PrecedentType.EXTENSION_SIDE,
            PrecedentType.EXTENSION_BASEMENT,
        ]:
            negative.append((
                FeasibilityFactor.PROPERTY_TYPE,
                "Flat - limited scope for physical extension"
            ))
            recommendations.append(
                "Flat: Extensions typically not possible. Consider "
                "internal reconfiguration or change of use."
            )
            return score - 15

    # Terraced houses - side extensions unlikely
    if "terraced" in prop_type:
        if proposed == PrecedentType.EXTENSION_SIDE:
            negative.append((
                FeasibilityFactor.PROPERTY_TYPE,
                "Terraced property - no scope for side extension"
            ))
            return score - 20

    neutral.append((
        FeasibilityFactor.PROPERTY_TYPE,
        f"Property type: {prop_type}"
    ))
    return score


def _assess_tenure(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    neutral: list,
    recommendations: list,
) -> int:
    """Assess feasibility based on tenure."""
    tenure = context.tenure.lower()

    if tenure == "freehold":
        positive.append((
            FeasibilityFactor.TENURE,
            "Freehold - full control over development decisions"
        ))
        return score + 3

    elif tenure == "leasehold":
        negative.append((
            FeasibilityFactor.TENURE,
            "Leasehold - freeholder consent required for alterations"
        ))
        recommendations.append(
            "Leasehold: Check lease terms for alteration clauses. "
            "Freeholder consent will be needed alongside planning."
        )
        return score - 10

    neutral.append((
        FeasibilityFactor.TENURE,
        "Tenure not specified"
    ))
    return score


def _assess_plot_size(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    neutral: list,
    recommendations: list,
) -> int:
    """Assess feasibility based on plot size."""
    plot_size = context.plot_size_sqft
    current_sqft = context.current_sqft

    if not plot_size:
        neutral.append((
            FeasibilityFactor.PLOT_SIZE,
            "Plot size unknown"
        ))
        return score

    # Check plot to building ratio
    if current_sqft:
        ratio = current_sqft / plot_size
        if ratio < 0.3:
            positive.append((
                FeasibilityFactor.PLOT_SIZE,
                f"Large plot relative to building ({ratio:.0%} coverage) - "
                f"good extension potential"
            ))
            return score + 10
        elif ratio > 0.6:
            negative.append((
                FeasibilityFactor.PLOT_SIZE,
                f"High plot coverage ({ratio:.0%}) - limited room for extension"
            ))
            recommendations.append(
                "High plot coverage: Loft conversion or basement may be "
                "only expansion options"
            )
            return score - 10

    # Absolute plot size
    if plot_size > 5000:  # Large plot
        positive.append((
            FeasibilityFactor.PLOT_SIZE,
            f"Large plot ({plot_size:,} sqft) offers development flexibility"
        ))
        return score + 5
    elif plot_size < 1000:  # Small plot
        neutral.append((
            FeasibilityFactor.PLOT_SIZE,
            f"Compact plot ({plot_size:,} sqft)"
        ))
        return score - 3

    return score


def _assess_pd_rights(
    context: PlanningContext,
    score: int,
    positive: list,
    negative: list,
    recommendations: list,
) -> int:
    """Assess permitted development rights availability."""
    # PD rights are removed by:
    # - Listed buildings
    # - Article 4 directions
    # - Some conservation areas (for certain classes)
    # - Flats (no PD for extensions)

    has_pd_rights = (
        not context.listed_building and
        not context.article_4_direction and
        context.property_type.lower() not in ["flat", "maisonette"]
    )

    if has_pd_rights:
        # Check if proposed type is suitable for PD
        pd_types = [
            PrecedentType.EXTENSION_REAR,
            PrecedentType.EXTENSION_LOFT,
            PrecedentType.PERMITTED_DEVELOPMENT,
        ]
        if context.proposed_type in pd_types:
            positive.append((
                FeasibilityFactor.PD_RIGHTS,
                "Permitted development rights may apply - check limits"
            ))
            recommendations.append(
                "PD rights: Rear extensions up to 3m (attached) or 4m (detached) "
                "may not need planning permission. Verify with council."
            )
            return score + 8

    return score
