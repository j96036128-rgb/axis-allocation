"""
Tests for Phase 6 - Planning integration with recommendation engine.

Tests that planning assessment properly integrates with the existing
recommendation engine.
"""

import pytest
from datetime import datetime, timedelta

from deal_engine.core import (
    Mandate,
    AssetClass,
    InvestorType,
    RiskProfile,
    GeographicCriteria,
    FinancialCriteria,
    PropertyCriteria,
    DealCriteria,
    ScoringWeights,
    Listing,
    generate_recommendation,
    generate_report,
    RecommendationAction,
)
from deal_engine.core.listing import (
    Address,
    FinancialDetails,
    PropertyDetails,
    Tenure,
    Condition,
)
from deal_engine.planning import (
    PlanningContext,
    PlanningPrecedent,
    PrecedentType,
)


@pytest.fixture
def sample_mandate():
    """Create sample investor mandate."""
    return Mandate(
        mandate_id="TEST-001",
        investor_name="Test Fund",
        investor_type=InvestorType.FAMILY_OFFICE,
        asset_classes=[AssetClass.RESIDENTIAL],
        risk_profile=RiskProfile.CORE_PLUS,
        geographic=GeographicCriteria(
            regions=["Greater London"],
            postcodes=["SW", "N"],
        ),
        financial=FinancialCriteria(
            min_deal_size=200000,
            max_deal_size=1000000,
            min_yield=4.0,
            target_yield=6.0,
        ),
        property=PropertyCriteria(
            accept_turnkey=True,
            accept_refurbishment=True,
        ),
        deal_criteria=DealCriteria(),
        scoring_weights=ScoringWeights(),
    )


@pytest.fixture
def sample_listing():
    """Create sample property listing."""
    return Listing(
        listing_id="LST-001",
        source="test",
        title="Victorian Terrace with Development Potential",
        asset_class=AssetClass.RESIDENTIAL,
        tenure=Tenure.FREEHOLD,
        address=Address(
            street="10 Test Street",
            city="London",
            region="Greater London",
            postcode="SW1A 1AA",
        ),
        financial=FinancialDetails(
            asking_price=500000,
            current_rent=25000,
            gross_yield=5.0,
        ),
        property_details=PropertyDetails(
            unit_count=1,
            total_sqft=1200,
            condition=Condition.LIGHT_REFURB,
        ),
    )


@pytest.fixture
def sample_planning_context():
    """Create sample planning context with good potential."""
    now = datetime.now()
    precedents = [
        PlanningPrecedent(
            reference="APP/2023/001",
            address="12 Test Street",
            precedent_type=PrecedentType.EXTENSION_LOFT,
            approved=True,
            decision_date=now - timedelta(days=180),
            distance_meters=30.0,
            similarity_score=0.9,
        ),
        PlanningPrecedent(
            reference="APP/2023/002",
            address="8 Test Street",
            precedent_type=PrecedentType.EXTENSION_LOFT,
            approved=True,
            decision_date=now - timedelta(days=365),
            distance_meters=50.0,
            similarity_score=0.85,
        ),
    ]

    return PlanningContext(
        property_type="house_terraced",
        tenure="freehold",
        current_sqft=1200,
        plot_size_sqft=2000,
        conservation_area=False,
        listed_building=False,
        flood_zone=1,
        nearby_precedents=precedents,
        proposed_type=PrecedentType.EXTENSION_LOFT,
    )


class TestRecommendationWithPlanning:
    """Test recommendation engine with planning context."""

    def test_recommendation_without_planning(self, sample_listing, sample_mandate):
        """Test recommendation works without planning context."""
        rec = generate_recommendation(sample_listing, sample_mandate)
        assert rec is not None
        assert rec.planning is None
        assert "planning" not in rec.to_dict() or rec.to_dict().get("planning") is None

    def test_recommendation_with_planning(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test recommendation includes planning when context provided."""
        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=sample_planning_context,
        )
        assert rec is not None
        assert rec.planning is not None
        assert rec.planning.planning_score.score > 0

    def test_planning_included_in_dict(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test planning assessment is included in serialized output."""
        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=sample_planning_context,
        )
        data = rec.to_dict()
        assert "planning" in data
        assert data["planning"]["planning_score"]["score"] > 0
        assert "disclaimer" in data["planning"]

    def test_planning_in_summary(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test planning summary fields."""
        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=sample_planning_context,
        )
        summary = rec.to_summary()
        assert "planning_score" in summary
        assert "planning_label" in summary

    def test_has_planning_upside_property(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test has_planning_upside property."""
        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=sample_planning_context,
        )
        # With good precedents, should have upside
        assert rec.has_planning_upside is True

    def test_planning_enhances_headline(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test that strong planning upside appears in headline."""
        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=sample_planning_context,
        )
        # If planning score is high, should mention in headline
        if rec.planning.planning_score.score >= 70:
            assert "PLANNING UPSIDE" in rec.headline

    def test_planning_adds_next_steps(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test that planning adds relevant next steps."""
        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=sample_planning_context,
        )
        # Should have planning-related next step
        if rec.is_actionable:
            planning_steps = [s for s in rec.next_steps if "Planning" in s]
            assert len(planning_steps) > 0


class TestReportWithPlanning:
    """Test report generation with planning contexts."""

    def test_report_with_planning_contexts(
        self,
        sample_listing,
        sample_mandate,
        sample_planning_context,
    ):
        """Test generate_report accepts planning contexts dict."""
        listings = [sample_listing]
        planning_contexts = {sample_listing.listing_id: sample_planning_context}

        report = generate_report(
            listings,
            sample_mandate,
            planning_contexts=planning_contexts,
        )

        assert report is not None
        assert len(report.recommendations) == 1
        assert report.recommendations[0].planning is not None

    def test_report_mixed_planning_contexts(self, sample_mandate, sample_planning_context):
        """Test report handles some listings with planning, some without."""
        listing1 = Listing(
            listing_id="LST-001",
            source="test",
            title="Property 1",
            asset_class=AssetClass.RESIDENTIAL,
            tenure=Tenure.FREEHOLD,
            address=Address(region="Greater London", postcode="SW1A 1AA"),
            financial=FinancialDetails(asking_price=500000, current_rent=25000),
        )
        listing2 = Listing(
            listing_id="LST-002",
            source="test",
            title="Property 2",
            asset_class=AssetClass.RESIDENTIAL,
            tenure=Tenure.FREEHOLD,
            address=Address(region="Greater London", postcode="N1 1AA"),
            financial=FinancialDetails(asking_price=600000, current_rent=30000),
        )

        # Only provide planning context for listing 1
        planning_contexts = {"LST-001": sample_planning_context}

        report = generate_report(
            [listing1, listing2],
            sample_mandate,
            planning_contexts=planning_contexts,
        )

        # Find recommendations by listing ID
        rec1 = next(r for r in report.recommendations if r.listing_id == "LST-001")
        rec2 = next(r for r in report.recommendations if r.listing_id == "LST-002")

        assert rec1.planning is not None
        assert rec2.planning is None


class TestConstrainedPlanningIntegration:
    """Test planning integration with constrained properties."""

    def test_constrained_planning_in_risks(self, sample_listing, sample_mandate):
        """Test that planning constraints appear in risks."""
        # Create context with constraints
        context = PlanningContext(
            property_type="house_terraced",
            tenure="freehold",
            conservation_area=True,
            listed_building=True,
            listed_grade="II",
            proposed_type=PrecedentType.EXTENSION_LOFT,
        )

        rec = generate_recommendation(
            sample_listing,
            sample_mandate,
            planning_context=context,
        )

        # Should have planning-related risks
        planning_risks = [r for r in rec.risks if "Planning" in r]
        assert len(planning_risks) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
