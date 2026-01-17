"""
Tests for Phase 6 - Planning Upside Engine.

Tests the planning module's deterministic logic for:
- Precedent analysis
- Feasibility assessment
- Uplift estimation
- Overall planning score calculation
"""

import pytest
from datetime import datetime, timedelta

from deal_engine.planning import (
    # Models
    PlanningPrecedent,
    PrecedentType,
    PlanningContext,
    PlanningAssessment,
    PlanningScore,
    PlanningLabel,
    UpliftEstimate,
    # Precedent analysis
    analyze_precedents,
    calculate_precedent_score,
    get_relevant_precedents,
    # Feasibility
    assess_feasibility,
    FeasibilityResult,
    FeasibilityFactor,
    # Uplift
    estimate_uplift,
    calculate_uplift_range,
    # Score
    calculate_planning_score,
    get_planning_assessment,
)


# --- Test Data Fixtures ---

@pytest.fixture
def sample_precedents():
    """Create sample planning precedents for testing."""
    now = datetime.now()
    return [
        PlanningPrecedent(
            reference="APP/2023/001",
            address="10 Test Street",
            postcode="SW1A 1AA",
            precedent_type=PrecedentType.EXTENSION_LOFT,
            description="Loft conversion with dormer",
            approved=True,
            decision_date=now - timedelta(days=365),
            distance_meters=50.0,
            similarity_score=0.9,
            conditions=["materials to match existing"],
        ),
        PlanningPrecedent(
            reference="APP/2023/002",
            address="12 Test Street",
            postcode="SW1A 1AA",
            precedent_type=PrecedentType.EXTENSION_REAR,
            description="Single storey rear extension",
            approved=True,
            decision_date=now - timedelta(days=200),
            distance_meters=75.0,
            similarity_score=0.7,
            conditions=["privacy screening required"],
        ),
        PlanningPrecedent(
            reference="APP/2022/050",
            address="5 Test Road",
            postcode="SW1A 2BB",
            precedent_type=PrecedentType.EXTENSION_LOFT,
            description="Loft conversion refused",
            approved=False,
            decision_date=now - timedelta(days=500),
            distance_meters=200.0,
            similarity_score=0.8,
            refusal_reasons=["overdevelopment", "loss of light"],
        ),
    ]


@pytest.fixture
def basic_context(sample_precedents):
    """Create basic planning context."""
    return PlanningContext(
        property_type="house_terraced",
        tenure="freehold",
        current_sqft=1200,
        plot_size_sqft=2000,
        num_floors=2,
        conservation_area=False,
        listed_building=False,
        article_4_direction=False,
        green_belt=False,
        flood_zone=1,
        postcode="SW1A 1AA",
        nearby_precedents=sample_precedents,
        proposed_type=PrecedentType.EXTENSION_LOFT,
    )


@pytest.fixture
def constrained_context(sample_precedents):
    """Create planning context with multiple constraints."""
    return PlanningContext(
        property_type="house_semi",
        tenure="leasehold",
        current_sqft=1500,
        conservation_area=True,
        listed_building=True,
        listed_grade="II",
        article_4_direction=True,
        green_belt=False,
        flood_zone=2,
        postcode="SW1A 1AA",
        nearby_precedents=sample_precedents,
        proposed_type=PrecedentType.EXTENSION_REAR,
    )


# --- Model Tests ---

class TestPlanningModels:
    """Test planning data models."""

    def test_precedent_creation(self):
        """Test creating a PlanningPrecedent."""
        precedent = PlanningPrecedent(
            reference="TEST/001",
            address="123 Test St",
            precedent_type=PrecedentType.EXTENSION_LOFT,
            approved=True,
        )
        assert precedent.reference == "TEST/001"
        assert precedent.approved is True
        assert precedent.precedent_type == PrecedentType.EXTENSION_LOFT

    def test_precedent_recency(self):
        """Test recency calculation."""
        precedent = PlanningPrecedent(
            reference="TEST/001",
            decision_date=datetime.now() - timedelta(days=730),  # 2 years
        )
        assert precedent.recency_years is not None
        assert 1.9 < precedent.recency_years < 2.1

    def test_precedent_to_dict(self):
        """Test serialization to dict."""
        precedent = PlanningPrecedent(
            reference="TEST/001",
            approved=True,
            conditions=["condition 1"],
        )
        data = precedent.to_dict()
        assert data["reference"] == "TEST/001"
        assert data["approved"] is True
        assert "condition 1" in data["conditions"]

    def test_precedent_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "reference": "TEST/002",
            "approved": False,
            "precedent_type": "extension_loft",
            "refusal_reasons": ["too tall"],
        }
        precedent = PlanningPrecedent.from_dict(data)
        assert precedent.reference == "TEST/002"
        assert precedent.approved is False
        assert "too tall" in precedent.refusal_reasons

    def test_planning_context_creation(self, sample_precedents):
        """Test creating a PlanningContext."""
        context = PlanningContext(
            property_type="house_detached",
            tenure="freehold",
            conservation_area=False,
            nearby_precedents=sample_precedents,
            proposed_type=PrecedentType.EXTENSION_REAR,
        )
        assert context.property_type == "house_detached"
        assert len(context.nearby_precedents) == 3
        assert context.proposed_type == PrecedentType.EXTENSION_REAR

    def test_planning_score_labels(self):
        """Test score to label mapping."""
        assert PlanningLabel.EXCEPTIONAL.value == "exceptional"
        assert PlanningLabel.STRONG.value == "strong"
        assert PlanningLabel.MEDIUM.value == "medium"
        assert PlanningLabel.LOW.value == "low"


# --- Precedent Analysis Tests ---

class TestPrecedentAnalysis:
    """Test precedent analysis functions."""

    def test_get_relevant_precedents(self, basic_context):
        """Test filtering relevant precedents."""
        relevant = get_relevant_precedents(basic_context)
        assert len(relevant) > 0
        # All returned should meet minimum similarity
        for p in relevant:
            assert p.similarity_score >= 0.3

    def test_analyze_precedents_approval_rate(self, basic_context):
        """Test approval rate calculation."""
        analysis = analyze_precedents(basic_context)
        # 2 approved, 1 refused = ~66% approval rate
        assert analysis["approval_rate"] is not None
        assert 50 < analysis["approval_rate"] < 80

    def test_analyze_precedents_insights(self, basic_context):
        """Test insight generation."""
        analysis = analyze_precedents(basic_context)
        assert "insights" in analysis
        assert len(analysis["insights"]) > 0

    def test_calculate_precedent_score(self, basic_context):
        """Test precedent score calculation."""
        score = calculate_precedent_score(basic_context)
        assert 0 <= score <= 100
        # With 2/3 approved and good matches, should be moderate-high
        assert score >= 40

    def test_empty_precedents(self):
        """Test with no precedents."""
        context = PlanningContext(
            property_type="house_terraced",
            nearby_precedents=[],
        )
        score = calculate_precedent_score(context)
        # No data = neutral score
        assert score == 50


# --- Feasibility Tests ---

class TestFeasibility:
    """Test feasibility assessment."""

    def test_basic_feasibility(self, basic_context):
        """Test feasibility for unconstrained property."""
        result = assess_feasibility(basic_context)
        assert isinstance(result, FeasibilityResult)
        assert 0 <= result.score <= 100
        # Unconstrained should score well
        assert result.score >= 60
        assert len(result.blockers) == 0

    def test_constrained_feasibility(self, constrained_context):
        """Test feasibility for heavily constrained property."""
        result = assess_feasibility(constrained_context)
        # Should be lower due to constraints
        assert result.score < 60
        assert len(result.negative_factors) > 0

    def test_listed_building_impact(self):
        """Test listed building constraint."""
        context = PlanningContext(
            property_type="house_detached",
            tenure="freehold",
            listed_building=True,
            listed_grade="I",
        )
        result = assess_feasibility(context)
        # Grade I should be a blocker
        assert len(result.blockers) > 0
        assert result.score <= 30

    def test_conservation_area_impact(self):
        """Test conservation area constraint."""
        context = PlanningContext(
            property_type="house_terraced",
            tenure="freehold",
            conservation_area=True,
        )
        result = assess_feasibility(context)
        # Conservation area reduces score but isn't a blocker
        found_conservation = False
        for factor, desc in result.negative_factors:
            if factor == FeasibilityFactor.CONSERVATION_AREA:
                found_conservation = True
        assert found_conservation

    def test_green_belt_new_build(self):
        """Test green belt with new build proposal."""
        context = PlanningContext(
            property_type="land",
            green_belt=True,
            proposed_type=PrecedentType.NEW_BUILD,
        )
        result = assess_feasibility(context)
        # Should be a blocker
        assert len(result.blockers) > 0

    def test_flat_extension_limitation(self):
        """Test that flats can't extend."""
        context = PlanningContext(
            property_type="flat",
            proposed_type=PrecedentType.EXTENSION_REAR,
        )
        result = assess_feasibility(context)
        # Should have negative factor for property type
        assert result.score < 70

    def test_pd_rights_bonus(self):
        """Test permitted development rights boost."""
        context = PlanningContext(
            property_type="house_detached",
            tenure="freehold",
            listed_building=False,
            article_4_direction=False,
            proposed_type=PrecedentType.EXTENSION_REAR,
        )
        result = assess_feasibility(context)
        # Should have PD rights positive factor
        pd_found = False
        for factor, desc in result.positive_factors:
            if factor == FeasibilityFactor.PD_RIGHTS:
                pd_found = True
        assert pd_found


# --- Uplift Estimation Tests ---

class TestUpliftEstimation:
    """Test uplift estimation logic."""

    def test_basic_uplift_estimate(self, basic_context):
        """Test basic uplift estimation."""
        estimate = estimate_uplift(
            context=basic_context,
            current_value=500000,
        )
        assert isinstance(estimate, UpliftEstimate)
        assert estimate.percent_low > 0
        assert estimate.percent_mid > estimate.percent_low
        assert estimate.percent_high > estimate.percent_mid
        assert estimate.value_low > 0

    def test_uplift_with_constraints(self, constrained_context):
        """Test uplift is reduced with constraints."""
        estimate_constrained = estimate_uplift(
            context=constrained_context,
            current_value=500000,
        )

        # Create unconstrained version
        unconstrained = PlanningContext(
            property_type="house_semi",
            tenure="freehold",
            proposed_type=PrecedentType.EXTENSION_REAR,
        )
        estimate_unconstrained = estimate_uplift(
            context=unconstrained,
            current_value=500000,
        )

        # Constrained should have lower uplift
        assert estimate_constrained.percent_mid < estimate_unconstrained.percent_mid

    def test_different_development_types(self):
        """Test different development types have different uplifts."""
        base_context = PlanningContext(
            property_type="house_detached",
            tenure="freehold",
        )

        # Test extension vs conversion
        base_context.proposed_type = PrecedentType.EXTENSION_REAR
        extension_uplift = estimate_uplift(base_context, 500000)

        base_context.proposed_type = PrecedentType.CONVERSION_FLATS
        conversion_uplift = estimate_uplift(base_context, 500000)

        # Conversion typically has higher uplift potential
        assert conversion_uplift.percent_mid > extension_uplift.percent_mid

    def test_uplift_confidence_levels(self):
        """Test confidence level assignment."""
        # High confidence scenario
        context = PlanningContext(
            property_type="house_detached",
            tenure="freehold",
            proposed_type=PrecedentType.PERMITTED_DEVELOPMENT,
        )
        estimate = estimate_uplift(context, 500000, precedent_approval_rate=90)
        assert estimate.confidence in ["low", "medium", "high"]

    def test_calculate_uplift_range_helper(self, basic_context):
        """Test the helper function."""
        low, high = calculate_uplift_range(basic_context, 500000)
        assert low > 0
        assert high > low


# --- Planning Score Tests ---

class TestPlanningScore:
    """Test overall planning score calculation."""

    def test_calculate_planning_score(self):
        """Test score calculation from components."""
        score = calculate_planning_score(
            precedent_score=70,
            feasibility_score=80,
            uplift_percent_mid=15.0,
        )
        assert isinstance(score, PlanningScore)
        assert 0 <= score.score <= 100
        assert score.precedent_score == 70
        assert score.feasibility_score == 80

    def test_score_labels(self):
        """Test score label thresholds."""
        # Exceptional (80+)
        score_high = calculate_planning_score(90, 90, 25)
        assert score_high.label == PlanningLabel.EXCEPTIONAL

        # Strong (60-79)
        score_strong = calculate_planning_score(70, 70, 15)
        assert score_strong.label in [PlanningLabel.STRONG, PlanningLabel.EXCEPTIONAL]

        # Low (<40)
        score_low = calculate_planning_score(20, 20, 5)
        assert score_low.label == PlanningLabel.LOW

    def test_get_planning_assessment(self, basic_context):
        """Test full planning assessment."""
        assessment = get_planning_assessment(
            context=basic_context,
            current_value=500000,
        )
        assert isinstance(assessment, PlanningAssessment)
        assert assessment.planning_score is not None
        assert assessment.uplift_estimate is not None
        assert len(assessment.rationale) > 0
        assert assessment.disclaimer is not None

    def test_assessment_to_dict(self, basic_context):
        """Test assessment serialization."""
        assessment = get_planning_assessment(basic_context, 500000)
        data = assessment.to_dict()

        assert "planning_score" in data
        assert "uplift_estimate" in data
        assert "rationale" in data
        assert "disclaimer" in data

    def test_assessment_summary(self, basic_context):
        """Test summary generation."""
        assessment = get_planning_assessment(basic_context, 500000)
        summary = assessment.summary

        assert "Planning Potential:" in summary
        assert "Estimated Uplift:" in summary


# --- Integration Tests ---

class TestPlanningIntegration:
    """Test planning module integration."""

    def test_full_workflow(self, sample_precedents):
        """Test complete planning analysis workflow."""
        # Create context
        context = PlanningContext(
            property_type="house_semi",
            tenure="freehold",
            current_sqft=1400,
            plot_size_sqft=2500,
            conservation_area=False,
            listed_building=False,
            flood_zone=1,
            postcode="N1 1AA",
            nearby_precedents=sample_precedents,
            proposed_type=PrecedentType.EXTENSION_LOFT,
        )

        # Run full assessment
        assessment = get_planning_assessment(context, 600000)

        # Verify all components
        assert assessment.planning_score.score > 0
        assert assessment.uplift_estimate.percent_mid > 0
        assert len(assessment.rationale) > 0
        assert len(assessment.recommendations) > 0

    def test_context_serialization_roundtrip(self, basic_context):
        """Test context can be serialized and deserialized."""
        data = basic_context.to_dict()
        restored = PlanningContext.from_dict(data)

        assert restored.property_type == basic_context.property_type
        assert restored.conservation_area == basic_context.conservation_area
        assert len(restored.nearby_precedents) == len(basic_context.nearby_precedents)

    def test_api_input_format(self):
        """Test handling API-style input."""
        # Simulate input from API
        api_input = {
            "property_type": "house_terraced",
            "tenure": "freehold",
            "current_sqft": 1000,
            "conservation_area": False,
            "listed_building": False,
            "green_belt": False,
            "flood_zone": 1,
            "proposed_type": "extension_loft",
            "nearby_precedents": [
                {
                    "reference": "API/001",
                    "approved": True,
                    "precedent_type": "extension_loft",
                    "distance_meters": 100,
                    "similarity_score": 0.8,
                }
            ],
        }

        context = PlanningContext.from_dict(api_input)
        assessment = get_planning_assessment(context, 450000)

        assert assessment.planning_score.score > 0


# --- Edge Case Tests ---

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_current_value(self, basic_context):
        """Test handling zero property value."""
        assessment = get_planning_assessment(basic_context, 0)
        assert assessment.uplift_estimate.value_mid == 0

    def test_empty_context(self):
        """Test with minimal context."""
        context = PlanningContext()
        assessment = get_planning_assessment(context, 100000)
        # Should still produce a result, even if neutral
        assert assessment.planning_score is not None

    def test_all_refused_precedents(self):
        """Test with all precedents refused."""
        refused = [
            PlanningPrecedent(
                reference=f"REF/{i}",
                approved=False,
                similarity_score=0.8,
                decision_date=datetime.now() - timedelta(days=100*i),
            )
            for i in range(1, 5)
        ]
        context = PlanningContext(
            property_type="house_terraced",
            nearby_precedents=refused,
        )

        score = calculate_precedent_score(context)
        # With all refusals, should be low
        assert score < 40

    def test_very_old_precedents(self):
        """Test precedents that are very old get filtered."""
        old = PlanningPrecedent(
            reference="OLD/001",
            approved=True,
            similarity_score=0.9,
            decision_date=datetime.now() - timedelta(days=4000),  # ~11 years
        )
        context = PlanningContext(
            property_type="house_terraced",
            nearby_precedents=[old],
        )

        relevant = get_relevant_precedents(context)
        # Old precedent should be filtered out
        assert len(relevant) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
