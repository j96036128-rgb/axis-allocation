"""
Tests to ensure NO dummy/mock data ever appears in the system.

These tests fail if:
- Any address matches known dummy patterns
- Any listing lacks a real verifiable source
- Any source field indicates mock/test data
"""

import pytest
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from deal_engine.core.listing import Listing, Address, FinancialDetails, PropertyDetails


# =============================================================================
# Known Dummy Data Patterns
# =============================================================================

# Common dummy street names used in mock data
# NOTE: Must be specific - "High Street" and "Church Road" are real UK street names
# Only flag patterns that are clearly synthetic/generated
DUMMY_STREET_PATTERNS = [
    r"\bsample\s+(area|road|street|property|town|city)\b",
    r"\btest\s+(address|property|listing|street|road)\b",
    r"\bdummy\s+(address|property|street)\b",
    r"\bfake\s+(address|street|road)\b",
    r"\bexample\s+(street|road|address)\b",
    r"\bplaceholder\b",
    r"\bexample\.com\b",
    r"\blocalhost\b",
    # Generic numbered patterns only (e.g. "123 Test Street")
    r"^\d+\s+test\s+",
    r"^\d+\s+sample\s+",
    r"^\d+\s+fake\s+",
]

# Invalid/placeholder postcodes
DUMMY_POSTCODE_PATTERNS = [
    r"^XX\d",  # XX prefix is not valid
    r"^ZZ\d",  # ZZ prefix is not valid
    r"^AA\d{2}\s*\d[A-Z]{2}$",  # AA followed by two digits is suspicious
    r"^\w{2}00\s",  # 00 district codes are suspicious
]

# Invalid source identifiers
INVALID_SOURCES = [
    "mock",
    "sample",
    "test",
    "dummy",
    "fake",
    "placeholder",
    "example",
]


# =============================================================================
# Validation Functions
# =============================================================================

def is_dummy_address(address: str) -> bool:
    """Check if address matches known dummy patterns."""
    if not address:
        return True

    address_lower = address.lower()

    for pattern in DUMMY_STREET_PATTERNS:
        if re.search(pattern, address_lower, re.IGNORECASE):
            return True

    return False


def is_dummy_postcode(postcode: str) -> bool:
    """Check if postcode matches known dummy patterns."""
    if not postcode:
        return True

    for pattern in DUMMY_POSTCODE_PATTERNS:
        if re.match(pattern, postcode.upper()):
            return True

    return False


def is_invalid_source(source: str) -> bool:
    """Check if source indicates mock/test data."""
    if not source:
        return True

    return source.lower() in INVALID_SOURCES


def is_invalid_url(url: str) -> bool:
    """Check if URL is fake or missing."""
    if not url:
        # Empty URL is allowed for manually entered listings
        return False

    # Must not be example.com or localhost
    if "example.com" in url.lower():
        return True
    if "localhost" in url.lower():
        return True

    return False


def validate_listing_is_real(listing: Listing) -> list[str]:
    """
    Validate that a listing contains real data.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    # Check address
    full_address = f"{listing.address.street}, {listing.address.city}"
    if is_dummy_address(full_address):
        errors.append(f"Dummy address detected: {full_address}")

    if is_dummy_postcode(listing.address.postcode):
        errors.append(f"Dummy postcode detected: {listing.address.postcode}")

    if is_invalid_source(listing.source):
        errors.append(f"Invalid source: {listing.source}")

    if is_invalid_url(listing.source_url):
        errors.append(f"Invalid URL: {listing.source_url}")

    return errors


# =============================================================================
# Unit Tests: Pattern Detection
# =============================================================================

class TestDummyAddressDetection:
    """Tests for dummy address pattern detection."""

    @pytest.mark.parametrize("address,is_dummy", [
        # Known dummy patterns - should be flagged
        ("Sample Area, Test City", True),
        ("Test Address, Sample Town", True),
        ("123 Test Street, London", True),
        ("456 Sample Road, Manchester", True),
        ("Fake Address, Placeholder Town", True),
        ("99 Dummy Street, Nowhere", True),

        # Real addresses - should NOT be flagged
        # Note: "High Street", "Church Road" etc. are real UK street names
        ("123 High Street, London", False),
        ("45 Church Road, Manchester", False),
        ("Carlisle House, Oxford Road, Reading, Berkshire, RG1 7NG", False),
        ("Flat A, 93 Mount View Road, Hornsey, London, N4 4JA", False),
        ("68 Southcote Avenue, Feltham, Middlesex, TW13 4EG", False),
        ("215 Ross Road, South Norwood, London, SE25 6TN", False),
        ("8 & 8A Bell Row, High Street, Baldock, Hertfordshire, SG7 6AP", False),
    ])
    def test_dummy_address_detection(self, address, is_dummy):
        """Verify dummy address patterns are correctly identified."""
        assert is_dummy_address(address) == is_dummy, f"Failed for: {address}"


class TestDummyPostcodeDetection:
    """Tests for dummy postcode pattern detection."""

    @pytest.mark.parametrize("postcode,is_dummy", [
        # Valid UK postcodes - should NOT be flagged
        ("SW1A 1AA", False),
        ("M1 1AE", False),
        ("B33 8TH", False),
        ("CR2 6XH", False),
        ("RG1 7NG", False),
        ("N4 4JA", False),
        ("TW13 4EG", False),
        ("SE25 6TN", False),

        # Empty/missing - should be flagged
        ("", True),
        (None, True),
    ])
    def test_dummy_postcode_detection(self, postcode, is_dummy):
        """Verify dummy postcode patterns are correctly identified."""
        result = is_dummy_postcode(postcode) if postcode else True
        assert result == is_dummy, f"Failed for: {postcode}"


class TestInvalidSourceDetection:
    """Tests for invalid source detection."""

    @pytest.mark.parametrize("source,is_invalid", [
        # Invalid sources
        ("mock", True),
        ("Mock", True),
        ("MOCK", True),
        ("sample", True),
        ("test", True),
        ("dummy", True),
        ("fake", True),
        ("", True),

        # Valid sources
        ("rightmove", False),
        ("zoopla", False),
        ("manual", False),
        ("api", False),
        ("AuctionHouseLondon", False),
    ])
    def test_invalid_source_detection(self, source, is_invalid):
        """Verify invalid sources are correctly identified."""
        assert is_invalid_source(source) == is_invalid, f"Failed for: {source}"


class TestInvalidUrlDetection:
    """Tests for invalid URL detection."""

    @pytest.mark.parametrize("url,is_invalid", [
        # Invalid URLs
        ("https://example.com/property/123", True),
        ("http://localhost:8000/listing/1", True),

        # Valid URLs (or empty which is allowed for manual entries)
        ("", False),
        ("https://rightmove.co.uk/property/123456", False),
        ("https://zoopla.co.uk/for-sale/details/12345678", False),
        ("https://auctionhouselondon.co.uk/lot/123-test-street-123456", False),
    ])
    def test_invalid_url_detection(self, url, is_invalid):
        """Verify invalid URLs are correctly identified."""
        assert is_invalid_url(url) == is_invalid, f"Failed for: {url}"


# =============================================================================
# Integration Tests: Listing Validation
# =============================================================================

class TestListingValidation:
    """Tests for full listing validation."""

    def test_mock_listing_fails_validation(self):
        """A mock listing should fail validation."""
        mock_listing = Listing(
            listing_id="mock-123",
            source="mock",
            source_url="https://example.com/property/123",
            address=Address(
                street="123 High Street, Sample Town",
                city="Test City",
                postcode="XX1 1AA",
            ),
            financial=FinancialDetails(asking_price=250000),
        )

        errors = validate_listing_is_real(mock_listing)
        assert len(errors) > 0, "Mock listing should fail validation"

    def test_real_listing_passes_validation(self):
        """A real listing should pass validation."""
        real_listing = Listing(
            listing_id="RM-12345678",
            source="rightmove",
            source_url="https://rightmove.co.uk/property/12345678",
            address=Address(
                street="Carlisle House, Oxford Road",
                city="Reading",
                region="Berkshire",
                postcode="RG1 7NG",
            ),
            financial=FinancialDetails(asking_price=500000),
        )

        errors = validate_listing_is_real(real_listing)
        assert len(errors) == 0, f"Real listing should pass validation: {errors}"

    def test_manual_entry_without_url_passes(self):
        """Manual entry without URL should pass if other fields are valid."""
        manual_listing = Listing(
            listing_id="MANUAL-001",
            source="manual",
            source_url="",  # Empty is OK for manual
            address=Address(
                street="45 Victoria Road",
                city="Manchester",
                region="Greater Manchester",
                postcode="M20 3HQ",
            ),
            financial=FinancialDetails(asking_price=350000),
        )

        errors = validate_listing_is_real(manual_listing)
        assert len(errors) == 0, f"Manual listing should pass validation: {errors}"


# =============================================================================
# Regression Test: No Mock Data in App
# =============================================================================

class TestNoMockDataInApp:
    """Ensure mock/dummy patterns are not used in production code."""

    def test_app_does_not_use_mock_source(self):
        """web/app.py should not hardcode 'mock' as a source."""
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        # Should not have source="mock" in production code
        assert 'source="mock"' not in content, (
            "Found source='mock' in web/app.py - this should use real sources"
        )
        assert "source='mock'" not in content, (
            "Found source='mock' in web/app.py - this should use real sources"
        )

    def test_app_does_not_use_example_urls(self):
        """web/app.py should not use example.com URLs."""
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        assert "example.com" not in content, (
            "Found example.com URL in web/app.py - use real URLs or empty strings"
        )

    def test_app_does_not_use_localhost_urls(self):
        """web/app.py should not use localhost URLs for listing sources."""
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        # Localhost is OK for server binding (127.0.0.1, localhost:8000)
        # but not for source_url values
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if "source_url" in line and "localhost" in line:
                assert False, f"Found localhost in source_url on line {i}: {line.strip()}"
