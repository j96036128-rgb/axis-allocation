"""
Input validation rules for mandates and listings.

Provides comprehensive validation to ensure data integrity
before processing through filtering and scoring.
"""

import re
from dataclasses import dataclass
from typing import Optional

from .mandate import Mandate, AssetClass, InvestorType
from .listing import Listing, PropertyType, Tenure


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str, value: any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"{field}: {message}")


@dataclass
class ValidationResult:
    """Result of validation operation."""

    is_valid: bool
    errors: list[ValidationError]
    warnings: list[str]

    def __bool__(self) -> bool:
        return self.is_valid


# UK postcode regex pattern (full postcode)
UK_POSTCODE_PATTERN = re.compile(
    r"^([A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}|[A-Z]{1,2}[0-9]{1,2})$",
    re.IGNORECASE
)

# Postcode area/district pattern (partial postcode for filtering)
# Matches: "SW", "SW1", "SW1A", "E", "EC", "EC1", etc.
POSTCODE_AREA_PATTERN = re.compile(
    r"^[A-Z]{1,2}[0-9]{0,2}[A-Z]?$",
    re.IGNORECASE
)


def validate_postcode(postcode: str, allow_area_only: bool = True) -> bool:
    """
    Validate UK postcode format.

    Args:
        postcode: The postcode to validate
        allow_area_only: If True, accepts partial postcodes like 'SW1'
    """
    if not postcode:
        return True  # Empty is valid (means no restriction)

    postcode = postcode.strip().upper()

    if allow_area_only and POSTCODE_AREA_PATTERN.match(postcode):
        return True

    return bool(UK_POSTCODE_PATTERN.match(postcode))


def validate_mandate(mandate: Mandate) -> ValidationResult:
    """
    Validate a mandate for correctness and completeness.

    Returns ValidationResult with any errors found.
    """
    errors: list[ValidationError] = []
    warnings: list[str] = []

    # Required fields
    if not mandate.mandate_id:
        errors.append(ValidationError("mandate_id", "Mandate ID is required"))
    elif len(mandate.mandate_id) > 64:
        errors.append(ValidationError(
            "mandate_id",
            "Mandate ID must be 64 characters or less",
            mandate.mandate_id
        ))

    if not mandate.investor_name:
        errors.append(ValidationError("investor_name", "Investor name is required"))
    elif len(mandate.investor_name) > 256:
        errors.append(ValidationError(
            "investor_name",
            "Investor name must be 256 characters or less",
            mandate.investor_name
        ))

    # Investor type validation
    if not isinstance(mandate.investor_type, InvestorType):
        errors.append(ValidationError(
            "investor_type",
            f"Invalid investor type: {mandate.investor_type}"
        ))

    # Asset class validation
    for ac in mandate.asset_classes:
        if not isinstance(ac, AssetClass):
            errors.append(ValidationError(
                "asset_classes",
                f"Invalid asset class: {ac}"
            ))

    # Geographic validation
    for postcode in mandate.geographic.postcodes:
        if not validate_postcode(postcode, allow_area_only=True):
            errors.append(ValidationError(
                "geographic.postcodes",
                f"Invalid postcode format: {postcode}",
                postcode
            ))

    for postcode in mandate.geographic.exclude_postcodes:
        if not validate_postcode(postcode, allow_area_only=True):
            errors.append(ValidationError(
                "geographic.exclude_postcodes",
                f"Invalid postcode format: {postcode}",
                postcode
            ))

    # Financial validation
    fin = mandate.financial

    if fin.min_deal_size is not None:
        if fin.min_deal_size < 0:
            errors.append(ValidationError(
                "financial.min_deal_size",
                "Minimum deal size cannot be negative",
                fin.min_deal_size
            ))
        if fin.min_deal_size < 10000:
            warnings.append("Minimum deal size below £10,000 is unusual for institutional mandates")

    if fin.max_deal_size is not None:
        if fin.max_deal_size < 0:
            errors.append(ValidationError(
                "financial.max_deal_size",
                "Maximum deal size cannot be negative",
                fin.max_deal_size
            ))

    if fin.min_deal_size and fin.max_deal_size:
        if fin.min_deal_size > fin.max_deal_size:
            errors.append(ValidationError(
                "financial",
                "Minimum deal size cannot exceed maximum deal size",
                {"min": fin.min_deal_size, "max": fin.max_deal_size}
            ))

    # Yield validation (percentages)
    if fin.min_yield is not None:
        if fin.min_yield < 0 or fin.min_yield > 100:
            errors.append(ValidationError(
                "financial.min_yield",
                "Yield must be between 0 and 100 percent",
                fin.min_yield
            ))

    if fin.target_yield is not None:
        if fin.target_yield < 0 or fin.target_yield > 100:
            errors.append(ValidationError(
                "financial.target_yield",
                "Yield must be between 0 and 100 percent",
                fin.target_yield
            ))

    if fin.min_yield and fin.target_yield:
        if fin.min_yield > fin.target_yield:
            warnings.append("Minimum yield exceeds target yield - verify this is intentional")

    # IRR validation
    if fin.min_irr is not None:
        if fin.min_irr < -100 or fin.min_irr > 1000:
            errors.append(ValidationError(
                "financial.min_irr",
                "IRR must be between -100 and 1000 percent",
                fin.min_irr
            ))

    # LTV validation
    if fin.max_ltv is not None:
        if fin.max_ltv < 0 or fin.max_ltv > 100:
            errors.append(ValidationError(
                "financial.max_ltv",
                "LTV must be between 0 and 100 percent",
                fin.max_ltv
            ))

    if fin.preferred_ltv is not None:
        if fin.preferred_ltv < 0 or fin.preferred_ltv > 100:
            errors.append(ValidationError(
                "financial.preferred_ltv",
                "LTV must be between 0 and 100 percent",
                fin.preferred_ltv
            ))

    # Property criteria validation
    prop = mandate.property

    if prop.min_units is not None and prop.min_units < 1:
        errors.append(ValidationError(
            "property.min_units",
            "Minimum units must be at least 1",
            prop.min_units
        ))

    if prop.max_units is not None and prop.max_units < 1:
        errors.append(ValidationError(
            "property.max_units",
            "Maximum units must be at least 1",
            prop.max_units
        ))

    if prop.min_units and prop.max_units:
        if prop.min_units > prop.max_units:
            errors.append(ValidationError(
                "property",
                "Minimum units cannot exceed maximum units",
                {"min": prop.min_units, "max": prop.max_units}
            ))

    if prop.min_sqft is not None and prop.min_sqft < 0:
        errors.append(ValidationError(
            "property.min_sqft",
            "Square footage cannot be negative",
            prop.min_sqft
        ))

    if prop.min_lease_years is not None:
        if prop.min_lease_years < 0:
            errors.append(ValidationError(
                "property.min_lease_years",
                "Lease years cannot be negative",
                prop.min_lease_years
            ))
        if prop.min_lease_years > 999:
            warnings.append("Minimum lease years over 999 is unusual")

    # Priority validation
    if mandate.priority < 1 or mandate.priority > 10:
        errors.append(ValidationError(
            "priority",
            "Priority must be between 1 and 10",
            mandate.priority
        ))

    # Logical warnings
    if not mandate.asset_classes:
        warnings.append("No asset classes specified - mandate will match all asset types")

    if not mandate.geographic.regions and not mandate.geographic.postcodes:
        warnings.append("No geographic criteria specified - mandate will match all locations")

    if not fin.min_deal_size and not fin.max_deal_size:
        warnings.append("No deal size constraints specified")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_listing(listing: Listing) -> ValidationResult:
    """
    Validate a listing for correctness and completeness.

    Returns ValidationResult with any errors found.
    """
    errors: list[ValidationError] = []
    warnings: list[str] = []

    # Required fields
    if not listing.listing_id:
        errors.append(ValidationError("listing_id", "Listing ID is required"))

    if not listing.source:
        errors.append(ValidationError("source", "Source is required"))

    # Price validation
    if listing.financial.asking_price <= 0:
        errors.append(ValidationError(
            "financial.asking_price",
            "Asking price must be positive",
            listing.financial.asking_price
        ))

    if listing.financial.asking_price > 1_000_000_000:  # £1 billion
        warnings.append("Asking price exceeds £1 billion - verify this is correct")

    # Postcode validation
    if listing.address.postcode:
        if not validate_postcode(listing.address.postcode, allow_area_only=False):
            errors.append(ValidationError(
                "address.postcode",
                f"Invalid postcode format: {listing.address.postcode}",
                listing.address.postcode
            ))

    # Asset class validation
    if not isinstance(listing.asset_class, AssetClass):
        errors.append(ValidationError(
            "asset_class",
            f"Invalid asset class: {listing.asset_class}"
        ))

    # Property type validation
    if not isinstance(listing.property.property_type, PropertyType):
        errors.append(ValidationError(
            "property.property_type",
            f"Invalid property type: {listing.property.property_type}"
        ))

    # Tenure validation
    if not isinstance(listing.tenure, Tenure):
        errors.append(ValidationError(
            "tenure",
            f"Invalid tenure: {listing.tenure}"
        ))

    # Bedroom validation
    if listing.property.bedrooms is not None:
        if listing.property.bedrooms < 0:
            errors.append(ValidationError(
                "property.bedrooms",
                "Bedrooms cannot be negative",
                listing.property.bedrooms
            ))
        if listing.property.bedrooms > 100:
            warnings.append("More than 100 bedrooms is unusual - verify this is correct")

    # Square footage validation
    if listing.property.total_sqft is not None:
        if listing.property.total_sqft < 0:
            errors.append(ValidationError(
                "property.total_sqft",
                "Square footage cannot be negative",
                listing.property.total_sqft
            ))
        if listing.property.total_sqft < 50:
            warnings.append("Property under 50 sq ft is unusually small")
        if listing.property.total_sqft > 1_000_000:
            warnings.append("Property over 1 million sq ft is unusual - verify")

    # Unit count validation
    if listing.property.unit_count < 1:
        errors.append(ValidationError(
            "property.unit_count",
            "Unit count must be at least 1",
            listing.property.unit_count
        ))

    # Yield validation
    if listing.financial.gross_yield is not None:
        if listing.financial.gross_yield < 0 or listing.financial.gross_yield > 100:
            errors.append(ValidationError(
                "financial.gross_yield",
                "Gross yield must be between 0 and 100 percent",
                listing.financial.gross_yield
            ))
        if listing.financial.gross_yield > 30:
            warnings.append("Gross yield over 30% is unusual - verify accuracy")

    # Lease validation
    if listing.financial.lease_years_remaining is not None:
        if listing.financial.lease_years_remaining < 0:
            errors.append(ValidationError(
                "financial.lease_years_remaining",
                "Lease years cannot be negative",
                listing.financial.lease_years_remaining
            ))
        if listing.tenure == Tenure.FREEHOLD:
            warnings.append("Lease years specified but tenure is freehold")

    # EPC validation
    if listing.property.epc_rating:
        valid_ratings = ["A", "B", "C", "D", "E", "F", "G"]
        if listing.property.epc_rating.upper() not in valid_ratings:
            errors.append(ValidationError(
                "property.epc_rating",
                f"Invalid EPC rating: {listing.property.epc_rating}",
                listing.property.epc_rating
            ))

    # Completeness warnings
    if not listing.address.postcode:
        warnings.append("No postcode specified - geographic matching may be limited")

    if not listing.address.region:
        warnings.append("No region specified - geographic matching may be limited")

    if listing.property.total_sqft is None:
        warnings.append("No square footage specified - some filters may not apply")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_mandate_dict(data: dict) -> ValidationResult:
    """
    Validate raw mandate dictionary before conversion.

    Useful for validating input before creating Mandate object.
    """
    errors: list[ValidationError] = []
    warnings: list[str] = []

    # Check required fields exist
    if "mandate_id" not in data:
        errors.append(ValidationError("mandate_id", "Field is required"))

    if "investor_name" not in data:
        errors.append(ValidationError("investor_name", "Field is required"))

    if "investor_type" not in data:
        errors.append(ValidationError("investor_type", "Field is required"))
    else:
        # Validate investor type is valid enum value
        valid_types = [t.value for t in InvestorType]
        if data["investor_type"] not in valid_types:
            errors.append(ValidationError(
                "investor_type",
                f"Must be one of: {', '.join(valid_types)}",
                data["investor_type"]
            ))

    # Validate asset classes if present
    if "asset_classes" in data:
        valid_classes = [ac.value for ac in AssetClass]
        for ac in data["asset_classes"]:
            if ac not in valid_classes:
                errors.append(ValidationError(
                    "asset_classes",
                    f"Invalid asset class '{ac}'. Must be one of: {', '.join(valid_classes)}",
                    ac
                ))

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_listing_dict(data: dict) -> ValidationResult:
    """
    Validate raw listing dictionary before conversion.

    Useful for validating input before creating Listing object.
    """
    errors: list[ValidationError] = []
    warnings: list[str] = []

    # Check required fields exist
    if "listing_id" not in data:
        errors.append(ValidationError("listing_id", "Field is required"))

    if "source" not in data:
        errors.append(ValidationError("source", "Field is required"))

    # Check financial data
    financial = data.get("financial", {})
    if "asking_price" not in financial:
        errors.append(ValidationError("financial.asking_price", "Field is required"))
    elif not isinstance(financial["asking_price"], (int, float)):
        errors.append(ValidationError(
            "financial.asking_price",
            "Must be a number",
            financial["asking_price"]
        ))

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
