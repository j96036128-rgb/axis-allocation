"""
Filtering module for matching listings against mandates.

Applies mandate criteria as filters to eliminate non-matching
listings before scoring.
"""

from dataclasses import dataclass
from typing import Optional, Callable

from .mandate import Mandate
from .listing import Listing, Tenure


@dataclass
class FilterResult:
    """Result of filtering a single listing."""

    listing: Listing
    passed: bool
    failed_filters: list[str]


def filter_by_asset_class(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by asset class."""
    if mandate.accepts_asset_class(listing.asset_class):
        return True, ""
    return False, f"Asset class '{listing.asset_class.value}' not in mandate"


def filter_by_location(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by geographic criteria."""
    geo = mandate.geographic

    # Check exclusions
    if listing.region in geo.exclude_regions:
        return False, f"Region '{listing.region}' excluded"

    postcode_area = listing.postcode_area
    for excluded in geo.exclude_postcodes:
        if postcode_area.upper().startswith(excluded.upper()):
            return False, f"Postcode '{postcode_area}' excluded"

    # If no inclusions, pass
    if not geo.regions and not geo.postcodes:
        return True, ""

    # Check inclusions
    region_ok = not geo.regions or listing.region in geo.regions
    postcode_ok = not geo.postcodes or any(
        postcode_area.upper().startswith(pc.upper())
        for pc in geo.postcodes
    )

    if region_ok or postcode_ok:
        return True, ""

    return False, f"Location '{listing.region}/{postcode_area}' not in mandate criteria"


def filter_by_price(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by deal size."""
    fin = mandate.financial
    price = listing.asking_price

    if fin.min_deal_size and price < fin.min_deal_size:
        return False, f"Price £{price:,} below minimum £{fin.min_deal_size:,}"

    if fin.max_deal_size and price > fin.max_deal_size:
        return False, f"Price £{price:,} above maximum £{fin.max_deal_size:,}"

    return True, ""


def filter_by_yield(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by yield requirements."""
    fin = mandate.financial

    if not fin.min_yield:
        return True, ""

    listing_yield = listing.gross_yield

    if listing_yield is None:
        # Can't determine - pass through to scoring
        return True, ""

    if listing_yield < fin.min_yield:
        return False, f"Yield {listing_yield:.1f}% below minimum {fin.min_yield:.1f}%"

    return True, ""


def filter_by_tenure(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by tenure requirements."""
    prop = mandate.property

    if prop.freehold_only:
        if listing.tenure not in (Tenure.FREEHOLD, Tenure.SHARE_OF_FREEHOLD):
            return False, "Freehold required but property is leasehold"

    if prop.min_lease_years and listing.tenure == Tenure.LEASEHOLD:
        remaining = listing.financial.lease_years_remaining
        if remaining is not None and remaining < prop.min_lease_years:
            return False, f"Lease {remaining} years below minimum {prop.min_lease_years}"

    return True, ""


def filter_by_units(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by unit count."""
    prop = mandate.property
    units = listing.property_details.unit_count

    if prop.min_units and units < prop.min_units:
        return False, f"Unit count {units} below minimum {prop.min_units}"

    if prop.max_units and units > prop.max_units:
        return False, f"Unit count {units} above maximum {prop.max_units}"

    return True, ""


def filter_by_sqft(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by square footage."""
    prop = mandate.property
    sqft = listing.property_details.total_sqft

    if sqft is None:
        return True, ""  # Can't filter without data

    if prop.min_sqft and sqft < prop.min_sqft:
        return False, f"Size {sqft:,} sqft below minimum {prop.min_sqft:,}"

    if prop.max_sqft and sqft > prop.max_sqft:
        return False, f"Size {sqft:,} sqft above maximum {prop.max_sqft:,}"

    return True, ""


def filter_by_condition(listing: Listing, mandate: Mandate) -> tuple[bool, str]:
    """Filter by property condition preferences."""
    from .listing import Condition

    prop = mandate.property
    condition = listing.property_details.condition

    if condition == Condition.DEVELOPMENT and not prop.accept_development:
        return False, "Development opportunities not accepted"

    if condition in (Condition.LIGHT_REFURB, Condition.HEAVY_REFURB) and not prop.accept_refurbishment:
        return False, "Refurbishment opportunities not accepted"

    if condition == Condition.TURNKEY and not prop.accept_turnkey:
        return False, "Turnkey properties not accepted"

    return True, ""


# Default filter chain
DEFAULT_FILTERS: list[Callable[[Listing, Mandate], tuple[bool, str]]] = [
    filter_by_asset_class,
    filter_by_location,
    filter_by_price,
    filter_by_yield,
    filter_by_tenure,
    filter_by_units,
    filter_by_sqft,
    filter_by_condition,
]


def filter_listing(
    listing: Listing,
    mandate: Mandate,
    filters: Optional[list[Callable]] = None,
    fail_fast: bool = True
) -> FilterResult:
    """
    Apply filters to a single listing.

    Args:
        listing: The property listing to filter
        mandate: The investor mandate with criteria
        filters: Custom filter functions (uses DEFAULT_FILTERS if None)
        fail_fast: If True, stop on first failed filter

    Returns:
        FilterResult with pass/fail status and reasons
    """
    active_filters = filters or DEFAULT_FILTERS
    failed_filters: list[str] = []

    for filter_fn in active_filters:
        passed, reason = filter_fn(listing, mandate)
        if not passed:
            failed_filters.append(reason)
            if fail_fast:
                break

    return FilterResult(
        listing=listing,
        passed=len(failed_filters) == 0,
        failed_filters=failed_filters,
    )


def filter_listings(
    listings: list[Listing],
    mandate: Mandate,
    filters: Optional[list[Callable]] = None
) -> list[Listing]:
    """
    Filter a list of listings against a mandate.

    Args:
        listings: List of property listings to filter
        mandate: The investor mandate with criteria

    Returns:
        List of listings that pass all filters
    """
    passed = []

    for listing in listings:
        result = filter_listing(listing, mandate, filters)
        if result.passed:
            passed.append(listing)

    return passed


def filter_listings_detailed(
    listings: list[Listing],
    mandate: Mandate,
    filters: Optional[list[Callable]] = None
) -> tuple[list[Listing], list[FilterResult]]:
    """
    Filter listings with detailed results for all.

    Args:
        listings: List of property listings to filter
        mandate: The investor mandate with criteria

    Returns:
        Tuple of (passed listings, all filter results)
    """
    passed = []
    results = []

    for listing in listings:
        result = filter_listing(listing, mandate, filters, fail_fast=False)
        results.append(result)
        if result.passed:
            passed.append(listing)

    return passed, results


def get_filter_summary(results: list[FilterResult]) -> dict:
    """
    Generate summary statistics from filter results.

    Args:
        results: List of FilterResult objects

    Returns:
        Dictionary with filter statistics
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # Count failure reasons
    reason_counts: dict[str, int] = {}
    for result in results:
        for reason in result.failed_filters:
            # Extract filter type from reason
            filter_type = reason.split()[0] if reason else "Unknown"
            reason_counts[filter_type] = reason_counts.get(filter_type, 0) + 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / total * 100) if total > 0 else 0,
        "failure_reasons": reason_counts,
    }
