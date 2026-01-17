"""
Planning Upside Engine - Data Models.

Defines structured data models for planning potential assessment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PrecedentType(Enum):
    """Types of planning precedents."""

    EXTENSION_REAR = "extension_rear"
    EXTENSION_SIDE = "extension_side"
    EXTENSION_LOFT = "extension_loft"
    EXTENSION_BASEMENT = "extension_basement"
    CONVERSION_RESIDENTIAL = "conversion_residential"
    CONVERSION_HMO = "conversion_hmo"
    CONVERSION_FLATS = "conversion_flats"
    CHANGE_OF_USE = "change_of_use"
    NEW_BUILD = "new_build"
    DEMOLITION_REBUILD = "demolition_rebuild"
    SUBDIVISION = "subdivision"
    PERMITTED_DEVELOPMENT = "permitted_development"
    OTHER = "other"


class PlanningLabel(Enum):
    """Planning potential labels."""

    EXCEPTIONAL = "exceptional"  # 80-100: Very strong indicators
    STRONG = "strong"  # 60-79: Good potential
    MEDIUM = "medium"  # 40-59: Some opportunity
    LOW = "low"  # 0-39: Limited potential


@dataclass
class PlanningPrecedent:
    """
    A planning precedent (approval or refusal) used for analysis.

    Represents historical planning decisions in the area that can
    inform likelihood of success for similar applications.
    """

    # Identification
    reference: str  # Planning application reference
    address: str = ""
    postcode: str = ""

    # Classification
    precedent_type: PrecedentType = PrecedentType.OTHER
    description: str = ""

    # Outcome
    approved: bool = True
    decision_date: Optional[datetime] = None

    # Relevance factors
    distance_meters: Optional[float] = None  # Distance from subject property
    similarity_score: float = 0.5  # 0-1 how similar to proposed works

    # Additional details
    conditions: list[str] = field(default_factory=list)
    refusal_reasons: list[str] = field(default_factory=list)

    @property
    def recency_years(self) -> Optional[float]:
        """Calculate how many years ago the decision was made."""
        if not self.decision_date:
            return None
        delta = datetime.now() - self.decision_date
        return delta.days / 365.25

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "reference": self.reference,
            "address": self.address,
            "postcode": self.postcode,
            "precedent_type": self.precedent_type.value,
            "description": self.description,
            "approved": self.approved,
            "decision_date": self.decision_date.isoformat() if self.decision_date else None,
            "distance_meters": self.distance_meters,
            "similarity_score": self.similarity_score,
            "conditions": self.conditions,
            "refusal_reasons": self.refusal_reasons,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanningPrecedent":
        """Create from dictionary representation."""
        decision_date = None
        if data.get("decision_date"):
            decision_date = datetime.fromisoformat(data["decision_date"])

        return cls(
            reference=data.get("reference", ""),
            address=data.get("address", ""),
            postcode=data.get("postcode", ""),
            precedent_type=PrecedentType(data.get("precedent_type", "other")),
            description=data.get("description", ""),
            approved=data.get("approved", True),
            decision_date=decision_date,
            distance_meters=data.get("distance_meters"),
            similarity_score=data.get("similarity_score", 0.5),
            conditions=data.get("conditions", []),
            refusal_reasons=data.get("refusal_reasons", []),
        )


@dataclass
class PlanningContext:
    """
    Context information about a property's planning situation.

    This is the input data required for planning assessment.
    All fields are optional to allow partial analysis.
    """

    # Property characteristics
    property_type: str = ""  # e.g., "house_terraced", "flat"
    tenure: str = ""  # "freehold" or "leasehold"
    current_sqft: Optional[int] = None
    plot_size_sqft: Optional[int] = None
    num_floors: Optional[int] = None
    year_built: Optional[int] = None

    # Planning constraints
    conservation_area: bool = False
    listed_building: bool = False
    listed_grade: str = ""  # I, II*, II
    article_4_direction: bool = False  # Removes PD rights
    green_belt: bool = False
    flood_zone: int = 1  # 1 (low risk) to 3 (high risk)
    tree_preservation_orders: bool = False

    # Local context
    postcode: str = ""
    local_authority: str = ""

    # Nearby precedents (provided externally)
    nearby_precedents: list[PlanningPrecedent] = field(default_factory=list)

    # Proposed development type (what we're assessing)
    proposed_type: PrecedentType = PrecedentType.OTHER

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "property_type": self.property_type,
            "tenure": self.tenure,
            "current_sqft": self.current_sqft,
            "plot_size_sqft": self.plot_size_sqft,
            "num_floors": self.num_floors,
            "year_built": self.year_built,
            "conservation_area": self.conservation_area,
            "listed_building": self.listed_building,
            "listed_grade": self.listed_grade,
            "article_4_direction": self.article_4_direction,
            "green_belt": self.green_belt,
            "flood_zone": self.flood_zone,
            "tree_preservation_orders": self.tree_preservation_orders,
            "postcode": self.postcode,
            "local_authority": self.local_authority,
            "nearby_precedents": [p.to_dict() for p in self.nearby_precedents],
            "proposed_type": self.proposed_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanningContext":
        """Create from dictionary representation."""
        precedents = [
            PlanningPrecedent.from_dict(p)
            for p in data.get("nearby_precedents", [])
        ]

        return cls(
            property_type=data.get("property_type", ""),
            tenure=data.get("tenure", ""),
            current_sqft=data.get("current_sqft"),
            plot_size_sqft=data.get("plot_size_sqft"),
            num_floors=data.get("num_floors"),
            year_built=data.get("year_built"),
            conservation_area=data.get("conservation_area", False),
            listed_building=data.get("listed_building", False),
            listed_grade=data.get("listed_grade", ""),
            article_4_direction=data.get("article_4_direction", False),
            green_belt=data.get("green_belt", False),
            flood_zone=data.get("flood_zone", 1),
            tree_preservation_orders=data.get("tree_preservation_orders", False),
            postcode=data.get("postcode", ""),
            local_authority=data.get("local_authority", ""),
            nearby_precedents=precedents,
            proposed_type=PrecedentType(data.get("proposed_type", "other")),
        )


@dataclass
class UpliftEstimate:
    """
    Estimated value uplift from planning potential.

    Provides ranges to reflect uncertainty.
    """

    # Percentage uplift on current value
    percent_low: float = 0.0
    percent_mid: float = 0.0
    percent_high: float = 0.0

    # Absolute value uplift (GBP)
    value_low: int = 0
    value_mid: int = 0
    value_high: int = 0

    # Confidence and caveats
    confidence: str = "low"  # low, medium, high
    assumptions: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "percent_range": {
                "low": self.percent_low,
                "mid": self.percent_mid,
                "high": self.percent_high,
            },
            "value_range": {
                "low": self.value_low,
                "mid": self.value_mid,
                "high": self.value_high,
            },
            "confidence": self.confidence,
            "assumptions": self.assumptions,
            "caveats": self.caveats,
        }


@dataclass
class PlanningScore:
    """
    Planning potential score (0-100).

    Combines precedent analysis, feasibility factors, and
    uplift potential into a single comparable score.
    """

    score: int  # 0-100
    label: PlanningLabel

    # Component scores
    precedent_score: int = 0  # Based on nearby approvals
    feasibility_score: int = 0  # Based on constraints
    uplift_score: int = 0  # Based on potential value add

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "score": self.score,
            "label": self.label.value,
            "components": {
                "precedent_score": self.precedent_score,
                "feasibility_score": self.feasibility_score,
                "uplift_score": self.uplift_score,
            },
        }


@dataclass
class PlanningAssessment:
    """
    Complete planning potential assessment.

    This is the main output of the planning engine.
    """

    # Overall score
    planning_score: PlanningScore

    # Detailed analysis
    uplift_estimate: UpliftEstimate

    # Rationale
    rationale: list[str] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Metadata
    assessed_at: datetime = field(default_factory=datetime.now)

    # Legal disclaimer
    disclaimer: str = (
        "This assessment is indicative only and based on heuristics and "
        "provided precedent data. It does not constitute professional planning "
        "advice and should not be relied upon for investment decisions. "
        "Always consult a qualified planning consultant before making any "
        "planning applications or purchase decisions based on planning potential."
    )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "planning_score": self.planning_score.to_dict(),
            "uplift_estimate": self.uplift_estimate.to_dict(),
            "rationale": self.rationale,
            "positive_factors": self.positive_factors,
            "negative_factors": self.negative_factors,
            "recommendations": self.recommendations,
            "assessed_at": self.assessed_at.isoformat(),
            "disclaimer": self.disclaimer,
        }

    @property
    def summary(self) -> str:
        """Generate a human-readable summary."""
        score = self.planning_score
        uplift = self.uplift_estimate

        summary_parts = [
            f"Planning Potential: {score.label.value.upper()} ({score.score}/100)",
            f"Estimated Uplift: {uplift.percent_low:.0f}%-{uplift.percent_high:.0f}%",
        ]

        if self.positive_factors:
            summary_parts.append(f"Key Positives: {', '.join(self.positive_factors[:2])}")

        if self.negative_factors:
            summary_parts.append(f"Key Concerns: {', '.join(self.negative_factors[:2])}")

        return " | ".join(summary_parts)
