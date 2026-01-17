#!/usr/bin/env python3
"""
Axis Deal Engine - Phase 1 & 2 Demo

Demonstrates the core functionality:

Phase 1:
- Mandate data model and validation
- Listing data model
- Filtering listings by mandate criteria
- Scoring listings against mandates

Phase 2:
- Conviction scoring (HIGH/MEDIUM/LOW)
- Rejection criteria with clear reasons
- Review state machine (NEW → REVIEWING → ACCEPTED/DECLINED)
- Deal recommendation engine

Run with: python run.py
"""

import json
from datetime import datetime

# Phase 1 imports
from deal_engine.core import (
    Mandate,
    AssetClass,
    InvestorType,
    Listing,
    PropertyType,
    ValidationError,
    validate_mandate,
    validate_listing,
    filter_listings,
    filter_listings_detailed,
    get_filter_summary,
    score_listing,
    score_listings,
    ScoringResult,
)

# Phase 2 imports
from deal_engine.core import (
    ConvictionLevel,
    assess_conviction,
    rank_by_conviction,
    evaluate_rejection,
    get_rejection_summary,
    ReviewState,
    ReviewAction,
    DealReview,
    ReviewQueue,
    create_review,
    InvalidTransitionError,
    RecommendationAction,
    generate_recommendation,
    generate_recommendations,
    generate_report,
    get_actionable_recommendations,
)

from deal_engine.core.mandate import (
    GeographicCriteria,
    FinancialCriteria,
    PropertyCriteria,
    RiskProfile,
)
from deal_engine.core.listing import (
    Address,
    FinancialDetails,
    PropertyDetails,
    Tenure,
    Condition,
    ListingStatus,
)


def create_sample_mandate() -> Mandate:
    """Create a sample institutional mandate for demonstration."""
    return Mandate(
        mandate_id="MND-2024-001",
        investor_name="Acme Capital Partners",
        investor_type=InvestorType.INSTITUTIONAL,
        asset_classes=[AssetClass.RESIDENTIAL, AssetClass.BTR, AssetClass.HMO],
        risk_profile=RiskProfile.CORE_PLUS,
        geographic=GeographicCriteria(
            regions=["Greater London", "South East"],
            postcodes=["SW", "SE", "E", "N"],
            exclude_postcodes=["SE28"],  # Exclude Thamesmead
        ),
        financial=FinancialCriteria(
            min_deal_size=500_000,
            max_deal_size=5_000_000,
            total_allocation=25_000_000,
            min_yield=5.0,
            target_yield=7.0,
            max_ltv=75.0,
        ),
        property=PropertyCriteria(
            min_units=1,
            max_units=20,
            accept_refurbishment=True,
            accept_development=False,
            accept_turnkey=True,
            freehold_only=False,
            min_lease_years=80,
        ),
        is_active=True,
        priority=1,
        notes="Focus on yield-driven residential in Zone 2-4",
    )


def create_sample_listings() -> list[Listing]:
    """Create sample property listings for demonstration."""
    listings = []

    # Listing 1: Good match - BTR block in SE London
    listings.append(Listing(
        listing_id="RM-12345",
        source="rightmove",
        source_url="https://www.rightmove.co.uk/properties/12345",
        asset_class=AssetClass.BTR,
        tenure=Tenure.FREEHOLD,
        address=Address(
            street="45 Tower Bridge Road",
            city="London",
            region="Greater London",
            postcode="SE1 4TW",
            country="UK",
        ),
        financial=FinancialDetails(
            asking_price=2_500_000,
            price_qualifier="Guide Price",
            current_rent=175_000,
            gross_yield=7.0,
            price_per_sqft=450,
        ),
        property_details=PropertyDetails(
            property_type=PropertyType.BLOCK_OF_FLATS,
            bedrooms=12,
            total_sqft=5500,
            unit_count=6,
            condition=Condition.TURNKEY,
            epc_rating="C",
            has_tenants=True,
        ),
        title="Prime BTR Block - 6 Units - SE1",
        agent_name="Knight Frank",
        listed_date=datetime(2024, 1, 15),
        scraped_at=datetime.now(),
        status=ListingStatus.ACTIVE,
    ))

    # Listing 2: Partial match - Price too high
    listings.append(Listing(
        listing_id="RM-12346",
        source="rightmove",
        asset_class=AssetClass.RESIDENTIAL,
        tenure=Tenure.FREEHOLD,
        address=Address(
            street="100 Kensington High Street",
            city="London",
            region="Greater London",
            postcode="W8 5SA",
        ),
        financial=FinancialDetails(
            asking_price=8_500_000,
            current_rent=280_000,
            gross_yield=3.3,
        ),
        property_details=PropertyDetails(
            property_type=PropertyType.HOUSE_DETACHED,
            bedrooms=6,
            total_sqft=4500,
            unit_count=1,
            condition=Condition.TURNKEY,
        ),
        title="Stunning Kensington Family Home",
        listed_date=datetime(2024, 1, 10),
        status=ListingStatus.ACTIVE,
    ))

    # Listing 3: Good match - HMO in East London
    listings.append(Listing(
        listing_id="RM-12347",
        source="rightmove",
        asset_class=AssetClass.HMO,
        tenure=Tenure.LEASEHOLD,
        address=Address(
            street="78 Mile End Road",
            city="London",
            region="Greater London",
            postcode="E1 4UN",
        ),
        financial=FinancialDetails(
            asking_price=850_000,
            current_rent=72_000,
            gross_yield=8.5,
            lease_years_remaining=115,
        ),
        property_details=PropertyDetails(
            property_type=PropertyType.HMO,
            bedrooms=7,
            total_sqft=2200,
            unit_count=7,
            condition=Condition.LIGHT_REFURB,
            epc_rating="D",
            has_tenants=True,
        ),
        title="Licensed 7-Bed HMO - Strong Yield",
        listed_date=datetime(2024, 1, 20),
        status=ListingStatus.ACTIVE,
    ))

    # Listing 4: No match - Wrong region
    listings.append(Listing(
        listing_id="RM-12348",
        source="rightmove",
        asset_class=AssetClass.RESIDENTIAL,
        tenure=Tenure.FREEHOLD,
        address=Address(
            street="15 Deansgate",
            city="Manchester",
            region="North West",
            postcode="M3 2BA",
        ),
        financial=FinancialDetails(
            asking_price=1_200_000,
            current_rent=84_000,
            gross_yield=7.0,
        ),
        property_details=PropertyDetails(
            property_type=PropertyType.BLOCK_OF_FLATS,
            bedrooms=8,
            unit_count=4,
            condition=Condition.TURNKEY,
        ),
        title="Manchester City Centre Block",
        listed_date=datetime(2024, 1, 18),
        status=ListingStatus.ACTIVE,
    ))

    # Listing 5: Partial match - Development (not accepted)
    listings.append(Listing(
        listing_id="RM-12349",
        source="rightmove",
        asset_class=AssetClass.RESIDENTIAL,
        tenure=Tenure.FREEHOLD,
        address=Address(
            street="Former Warehouse, Bermondsey Street",
            city="London",
            region="Greater London",
            postcode="SE1 3UW",
        ),
        financial=FinancialDetails(
            asking_price=3_500_000,
        ),
        property_details=PropertyDetails(
            property_type=PropertyType.DEVELOPMENT_SITE,
            total_sqft=8000,
            unit_count=1,
            condition=Condition.DEVELOPMENT,
        ),
        title="Development Opportunity - PP for 12 Units",
        listed_date=datetime(2024, 1, 5),
        status=ListingStatus.ACTIVE,
    ))

    # Listing 6: Good match - Refurb opportunity
    listings.append(Listing(
        listing_id="RM-12350",
        source="rightmove",
        asset_class=AssetClass.RESIDENTIAL,
        tenure=Tenure.FREEHOLD,
        address=Address(
            street="22 Brixton Road",
            city="London",
            region="Greater London",
            postcode="SW9 6BU",
        ),
        financial=FinancialDetails(
            asking_price=1_100_000,
            price_qualifier="Offers Over",
        ),
        property_details=PropertyDetails(
            property_type=PropertyType.HOUSE_TERRACED,
            bedrooms=5,
            total_sqft=2800,
            unit_count=1,
            condition=Condition.HEAVY_REFURB,
            epc_rating="E",
        ),
        title="Unmodernised Victorian - Huge Potential",
        listed_date=datetime(2024, 1, 22),
        status=ListingStatus.ACTIVE,
    ))

    return listings


# =============================================================================
# Phase 1 Demos
# =============================================================================

def demo_validation():
    """Demonstrate mandate and listing validation."""
    print("\n" + "=" * 60)
    print("PHASE 1: VALIDATION DEMO")
    print("=" * 60)

    # Valid mandate
    mandate = create_sample_mandate()
    result = validate_mandate(mandate)
    print(f"\nMandate '{mandate.mandate_id}' validation:")
    print(f"  Valid: {result.is_valid}")
    if result.warnings:
        print(f"  Warnings: {len(result.warnings)}")
        for w in result.warnings:
            print(f"    - {w}")

    # Invalid mandate example
    print("\n--- Testing invalid mandate ---")
    invalid_mandate = Mandate(
        mandate_id="",  # Invalid: empty
        investor_name="Test",
        investor_type=InvestorType.INSTITUTIONAL,
        financial=FinancialCriteria(
            min_deal_size=5_000_000,
            max_deal_size=1_000_000,  # Invalid: min > max
            min_yield=150,  # Invalid: > 100%
        ),
        priority=15,  # Invalid: > 10
    )
    result = validate_mandate(invalid_mandate)
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    for err in result.errors:
        print(f"    - {err.field}: {err.message}")


def demo_filtering():
    """Demonstrate filtering listings by mandate criteria."""
    print("\n" + "=" * 60)
    print("PHASE 1: FILTERING DEMO")
    print("=" * 60)

    mandate = create_sample_mandate()
    listings = create_sample_listings()

    print(f"\nMandate: {mandate.investor_name} ({mandate.mandate_id})")
    print(f"  Asset classes: {[ac.value for ac in mandate.asset_classes]}")
    print(f"  Regions: {mandate.geographic.regions}")
    print(f"  Deal size: £{mandate.financial.min_deal_size:,} - £{mandate.financial.max_deal_size:,}")
    print(f"  Min yield: {mandate.financial.min_yield}%")

    # Filter with detailed results
    passed, all_results = filter_listings_detailed(listings, mandate)

    print(f"\n--- Filtering {len(listings)} listings ---\n")

    for result in all_results:
        listing = result.listing
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {listing.listing_id}: {listing.title}")
        print(f"       Location: {listing.address.region}, {listing.address.postcode}")
        print(f"       Price: £{listing.asking_price:,}")
        if not result.passed:
            for reason in result.failed_filters:
                print(f"       Reason: {reason}")
        print()

    # Summary
    summary = get_filter_summary(all_results)
    print(f"--- Summary ---")
    print(f"  Total: {summary['total']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Pass rate: {summary['pass_rate']:.1f}%")


def demo_scoring():
    """Demonstrate scoring listings against mandate."""
    print("\n" + "=" * 60)
    print("PHASE 1: SCORING DEMO")
    print("=" * 60)

    mandate = create_sample_mandate()
    listings = create_sample_listings()

    print(f"\nScoring all {len(listings)} listings against mandate...")

    # Score all listings
    results = score_listings(listings, mandate)

    print("\n--- Results (sorted by score) ---\n")

    for result in results:
        # Find the listing
        listing = next(l for l in listings if l.listing_id == result.listing_id)

        print(f"[{result.match_grade}] {result.total_score:.1f}/100 - {listing.title}")
        print(f"    ID: {result.listing_id}")
        print(f"    Match: {'Yes' if result.is_match else 'No'}")

        if result.disqualification_reasons:
            print(f"    Disqualified: {', '.join(result.disqualification_reasons)}")

        # Show top factors
        top_factors = sorted(result.factors, key=lambda f: f.weighted_score, reverse=True)[:3]
        print(f"    Top factors:")
        for f in top_factors:
            print(f"      - {f.name}: {f.score:.2f} ({f.explanation})")
        print()


# =============================================================================
# Phase 2 Demos
# =============================================================================

def demo_conviction():
    """Demonstrate conviction scoring."""
    print("\n" + "=" * 60)
    print("PHASE 2: CONVICTION SCORING DEMO")
    print("=" * 60)

    mandate = create_sample_mandate()
    listings = create_sample_listings()

    print(f"\nAssessing conviction for {len(listings)} listings...\n")

    assessments = []
    for listing in listings:
        scoring = score_listing(listing, mandate)
        conviction = assess_conviction(listing, mandate, scoring)
        assessments.append((listing, conviction))

    # Show results
    for listing, conviction in assessments:
        level_icon = {
            ConvictionLevel.HIGH: "+++",
            ConvictionLevel.MEDIUM: "+ +",
            ConvictionLevel.LOW: "+  ",
            ConvictionLevel.NONE: "---",
        }.get(conviction.level, "???")

        print(f"[{level_icon}] {conviction.level.value.upper():6} - {listing.title}")
        print(f"      Confidence: {conviction.confidence_score:.1%}")
        print(f"      Summary: {conviction.summary}")
        print(f"      Recommendation: {conviction.recommendation}")

        if conviction.positive_factors:
            print(f"      Positives: {len(conviction.positive_factors)}")
            for f in conviction.positive_factors[:2]:
                print(f"        + {f.reason}")
        if conviction.negative_factors:
            print(f"      Negatives: {len(conviction.negative_factors)}")
            for f in conviction.negative_factors[:2]:
                print(f"        - {f.reason}")
        print()

    # Rank by conviction
    print("--- Ranked by Conviction ---")
    ranked = rank_by_conviction([c for _, c in assessments])
    for level in [ConvictionLevel.HIGH, ConvictionLevel.MEDIUM, ConvictionLevel.LOW, ConvictionLevel.NONE]:
        print(f"  {level.value.upper()}: {len(ranked[level])} deals")


def demo_rejection():
    """Demonstrate rejection criteria."""
    print("\n" + "=" * 60)
    print("PHASE 2: REJECTION CRITERIA DEMO")
    print("=" * 60)

    mandate = create_sample_mandate()
    listings = create_sample_listings()

    print(f"\nEvaluating rejection criteria for {len(listings)} listings...\n")

    results = []
    for listing in listings:
        result = evaluate_rejection(listing, mandate)
        results.append((listing, result))

    for listing, result in results:
        status = "REJECTED" if result.rejected else "PASSED"
        print(f"[{status}] {listing.listing_id}: {listing.title}")
        print(f"         Hard rejections: {len(result.hard_rejections)}")
        print(f"         Soft rejections: {len(result.soft_rejections)}")

        for reason in result.hard_rejections:
            print(f"         [HARD] {reason.code}: {reason.title}")
            print(f"                {reason.explanation}")
            print(f"                Remedy: {reason.remedy}")

        for reason in result.soft_rejections[:2]:  # Limit to 2
            print(f"         [SOFT] {reason.code}: {reason.title}")
        print()

    # Summary
    summary = get_rejection_summary([r for _, r in results])
    print("--- Rejection Summary ---")
    print(f"  Total: {summary['total']}")
    print(f"  Rejected: {summary['rejected']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Rejection rate: {summary['rejection_rate']:.1f}%")
    print(f"  Top reasons: {summary['top_rejection_reasons']}")


def demo_review_states():
    """Demonstrate review state machine."""
    print("\n" + "=" * 60)
    print("PHASE 2: REVIEW STATE MACHINE DEMO")
    print("=" * 60)

    # Create a review
    review = create_review(
        listing_id="RM-12345",
        mandate_id="MND-2024-001",
        priority=1,
        assigned_to="analyst@acme.com"
    )

    print(f"\nCreated review: {review.review_id}")
    print(f"  State: {review.state.value}")
    print(f"  Valid actions: {[a.value for a in review.get_valid_actions()]}")

    # Transition through states
    print("\n--- State Transitions ---\n")

    # Start review
    review.start_review(actor="analyst@acme.com", notes="Beginning due diligence")
    print(f"1. Started review")
    print(f"   State: {review.state.value}")
    print(f"   Valid actions: {[a.value for a in review.get_valid_actions()]}")

    # Accept the deal
    review.accept(
        actor="manager@acme.com",
        notes="Strong fit, recommend to IC"
    )
    print(f"\n2. Accepted deal")
    print(f"   State: {review.state.value}")
    print(f"   Decision notes: {review.decision_notes}")

    # Show audit trail
    print("\n--- Audit Trail ---")
    for i, transition in enumerate(review.history, 1):
        print(f"  {i}. {transition.from_state.value} → {transition.to_state.value}")
        print(f"     Action: {transition.action.value}")
        print(f"     Actor: {transition.actor}")
        print(f"     Time: {transition.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if transition.notes:
            print(f"     Notes: {transition.notes}")

    # Demonstrate invalid transition
    print("\n--- Invalid Transition Test ---")
    try:
        review.start_review(actor="test")  # Can't start review when already accepted
    except InvalidTransitionError as e:
        print(f"  Caught expected error: {e}")

    # Demonstrate review queue
    print("\n--- Review Queue Demo ---")
    queue = ReviewQueue()

    # Add some reviews
    for i, listing_id in enumerate(["RM-12345", "RM-12346", "RM-12347"]):
        r = create_review(listing_id, "MND-2024-001", priority=i+1)
        if i == 0:
            r.start_review("analyst@acme.com")
        queue.add(r)

    stats = queue.stats()
    print(f"  Total reviews: {stats['total']}")
    print(f"  By state: {stats['by_state']}")
    print(f"  Pending: {stats['pending_count']}")


def demo_recommendations():
    """Demonstrate deal recommendation engine."""
    print("\n" + "=" * 60)
    print("PHASE 2: RECOMMENDATION ENGINE DEMO")
    print("=" * 60)

    mandate = create_sample_mandate()
    listings = create_sample_listings()

    print(f"\nGenerating recommendations for {len(listings)} listings...\n")

    # Generate full report
    report = generate_report(listings, mandate)

    print(f"Report for: {report.mandate_name}")
    print(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n--- Summary ---")
    print(f"  PURSUE: {report.pursue_count}")
    print(f"  CONSIDER: {report.consider_count}")
    print(f"  WATCH: {report.watch_count}")
    print(f"  PASS: {report.pass_count}")

    print("\n--- Recommendations (by priority) ---\n")

    for rec in report.recommendations:
        action_icon = {
            RecommendationAction.PURSUE: "[>>>]",
            RecommendationAction.CONSIDER: "[ > ]",
            RecommendationAction.WATCH: "[ - ]",
            RecommendationAction.PASS: "[ X ]",
        }.get(rec.action, "[???]")

        print(f"{action_icon} {rec.headline}")
        print(f"       Priority: {rec.priority_rank}")
        print(f"       Score: {rec.scoring.total_score:.0f}/100 ({rec.scoring.match_grade})")
        print(f"       Conviction: {rec.conviction.level.value}")
        print(f"       Rationale: {rec.rationale}")

        if rec.next_steps:
            print(f"       Next steps:")
            for step in rec.next_steps[:2]:
                print(f"         - {step}")

        if rec.risks:
            print(f"       Risks:")
            for risk in rec.risks[:2]:
                print(f"         ! {risk}")
        print()

    # Actionable only
    actionable = get_actionable_recommendations(report.recommendations)
    print(f"--- Actionable Deals: {len(actionable)} ---")
    for rec in actionable:
        print(f"  - {rec.listing_id}: {rec.action.value.upper()}")


def demo_full_phase2_pipeline():
    """Demonstrate complete Phase 2 pipeline with JSON output."""
    print("\n" + "=" * 60)
    print("PHASE 2: FULL PIPELINE (JSON OUTPUT)")
    print("=" * 60)

    mandate = create_sample_mandate()
    listings = create_sample_listings()

    # Generate report
    report = generate_report(listings, mandate)

    # Output as JSON (summary)
    print("\n--- Report JSON (summary) ---")
    print(json.dumps(report.to_dict(), indent=2))


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  AXIS DEAL ENGINE - PHASE 1 & 2 DEMO")
    print("=" * 60)

    # Phase 1 demos
    demo_validation()
    demo_filtering()
    demo_scoring()

    # Phase 2 demos
    demo_conviction()
    demo_rejection()
    demo_review_states()
    demo_recommendations()
    demo_full_phase2_pipeline()

    print("\n" + "=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60)
    print("\nPhase 1 modules:")
    print("  - deal_engine.core.mandate: Mandate data model")
    print("  - deal_engine.core.listing: Listing data model")
    print("  - deal_engine.core.validation: Input validation")
    print("  - deal_engine.core.filtering: Mandate-based filtering")
    print("  - deal_engine.core.scoring: Multi-factor scoring")
    print("\nPhase 2 modules:")
    print("  - deal_engine.core.conviction: Conviction scoring (HIGH/MEDIUM/LOW)")
    print("  - deal_engine.core.rejection: Rejection criteria with reasons")
    print("  - deal_engine.core.review: Review state machine")
    print("  - deal_engine.core.recommendation: Deal recommendation engine")
    print("\nRun with: python run.py")
    print()


if __name__ == "__main__":
    main()
