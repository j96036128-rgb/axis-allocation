"""
Planning Upside Engine for Axis Deal Engine.

Phase 6: Deterministic planning potential analysis.

DISCLAIMER: This module provides indicative planning assessments based on
heuristics and provided precedent data. It does NOT:
- Query live council planning portals
- Guarantee planning permission outcomes
- Replace professional planning advice

All outputs should be treated as preliminary indicators only.
Professional planning consultants should be engaged for actual applications.
"""

from .models import (
    PlanningPrecedent,
    PrecedentType,
    PlanningContext,
    PlanningAssessment,
    PlanningScore,
    PlanningLabel,
    UpliftEstimate,
)
from .precedent import (
    analyze_precedents,
    calculate_precedent_score,
    get_relevant_precedents,
)
from .feasibility import (
    assess_feasibility,
    FeasibilityResult,
    FeasibilityFactor,
)
from .uplift import (
    estimate_uplift,
    calculate_uplift_range,
)
from .score import (
    calculate_planning_score,
    get_planning_assessment,
)

__all__ = [
    # Models
    "PlanningPrecedent",
    "PrecedentType",
    "PlanningContext",
    "PlanningAssessment",
    "PlanningScore",
    "PlanningLabel",
    "UpliftEstimate",
    # Precedent analysis
    "analyze_precedents",
    "calculate_precedent_score",
    "get_relevant_precedents",
    # Feasibility
    "assess_feasibility",
    "FeasibilityResult",
    "FeasibilityFactor",
    # Uplift
    "estimate_uplift",
    "calculate_uplift_range",
    # Score
    "calculate_planning_score",
    "get_planning_assessment",
]
