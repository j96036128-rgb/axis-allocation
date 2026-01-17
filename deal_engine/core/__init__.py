"""
Core modules for Axis Deal Engine.

Phase 1:
- mandate: Investor mandate data model and schema
- listing: Property listing data model
- validation: Input validation rules
- filtering: Filter listings by mandate criteria
- scoring: Score listings against mandates

Phase 2:
- conviction: Conviction level assessment (HIGH/MEDIUM/LOW)
- rejection: Rejection criteria with clear reasons
- review: Review state machine (NEW → REVIEWING → ACCEPTED/DECLINED)
- recommendation: Deal recommendation engine

Phase 6:
- recommendation: Now supports optional planning upside integration
  via PlanningContext parameter (from deal_engine.planning module)
"""

# Phase 1 imports
from .mandate import (
    Mandate,
    AssetClass,
    InvestorType,
    RiskProfile,
    GeographicCriteria,
    FinancialCriteria,
    PropertyCriteria,
    # Phase 4 additions
    DealCriteria,
    ScoringWeights,
)
from .listing import Listing, PropertyType
from .validation import ValidationError, validate_mandate, validate_listing
from .filtering import filter_listings, filter_listings_detailed, get_filter_summary
from .scoring import score_listing, score_listings, ScoringResult

# Phase 2 imports
from .conviction import (
    ConvictionLevel,
    ConvictionAssessment,
    assess_conviction,
    rank_by_conviction,
)
from .rejection import (
    RejectionCategory,
    RejectionSeverity,
    RejectionReason,
    RejectionResult,
    evaluate_rejection,
    get_rejection_summary,
)
from .review import (
    ReviewState,
    ReviewAction,
    DealReview,
    ReviewQueue,
    create_review,
    InvalidTransitionError,
)
from .recommendation import (
    RecommendationAction,
    DealRecommendation,
    RecommendationReport,
    generate_recommendation,
    generate_recommendations,
    generate_report,
    get_actionable_recommendations,
)

__all__ = [
    # Phase 1 - Data models
    "Mandate",
    "AssetClass",
    "InvestorType",
    "RiskProfile",
    "GeographicCriteria",
    "FinancialCriteria",
    "PropertyCriteria",
    "Listing",
    "PropertyType",
    # Phase 4 - Configurable parameters
    "DealCriteria",
    "ScoringWeights",
    # Phase 1 - Validation
    "ValidationError",
    "validate_mandate",
    "validate_listing",
    # Phase 1 - Filtering
    "filter_listings",
    "filter_listings_detailed",
    "get_filter_summary",
    # Phase 1 - Scoring
    "score_listing",
    "score_listings",
    "ScoringResult",
    # Phase 2 - Conviction
    "ConvictionLevel",
    "ConvictionAssessment",
    "assess_conviction",
    "rank_by_conviction",
    # Phase 2 - Rejection
    "RejectionCategory",
    "RejectionSeverity",
    "RejectionReason",
    "RejectionResult",
    "evaluate_rejection",
    "get_rejection_summary",
    # Phase 2 - Review
    "ReviewState",
    "ReviewAction",
    "DealReview",
    "ReviewQueue",
    "create_review",
    "InvalidTransitionError",
    # Phase 2 - Recommendation
    "RecommendationAction",
    "DealRecommendation",
    "RecommendationReport",
    "generate_recommendation",
    "generate_recommendations",
    "generate_report",
    "get_actionable_recommendations",
]
