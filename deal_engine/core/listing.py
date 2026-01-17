"""
Listing data model.

Defines the structure for property listings that will be
matched against investor mandates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .mandate import AssetClass


class PropertyType(Enum):
    """Specific property type classification."""

    HOUSE_DETACHED = "house_detached"
    HOUSE_SEMI = "house_semi"
    HOUSE_TERRACED = "house_terraced"
    FLAT = "flat"
    MAISONETTE = "maisonette"
    BUNGALOW = "bungalow"
    LAND = "land"
    COMMERCIAL_UNIT = "commercial_unit"
    OFFICE_SPACE = "office_space"
    RETAIL_UNIT = "retail_unit"
    WAREHOUSE = "warehouse"
    MIXED_USE_BUILDING = "mixed_use_building"
    DEVELOPMENT_SITE = "development_site"
    HMO = "hmo"
    BLOCK_OF_FLATS = "block_of_flats"
    OTHER = "other"


class Tenure(Enum):
    """Property tenure type."""

    FREEHOLD = "freehold"
    LEASEHOLD = "leasehold"
    SHARE_OF_FREEHOLD = "share_of_freehold"
    COMMONHOLD = "commonhold"
    UNKNOWN = "unknown"


class ListingStatus(Enum):
    """Current status of the listing."""

    ACTIVE = "active"
    UNDER_OFFER = "under_offer"
    SOLD_STC = "sold_stc"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


class Condition(Enum):
    """Property condition assessment."""

    TURNKEY = "turnkey"  # Move-in ready, no work needed
    LIGHT_REFURB = "light_refurb"  # Cosmetic updates
    HEAVY_REFURB = "heavy_refurb"  # Significant renovation
    DEVELOPMENT = "development"  # Ground-up or major works
    UNKNOWN = "unknown"


@dataclass
class Address:
    """Property address details."""

    street: str = ""
    city: str = ""
    region: str = ""  # e.g., "Greater London", "South East"
    postcode: str = ""
    country: str = "UK"

    @property
    def postcode_area(self) -> str:
        """Extract postcode area (e.g., 'SW1' from 'SW1A 1AA')."""
        if not self.postcode:
            return ""
        parts = self.postcode.upper().split()
        if parts:
            # Return outward code (first part)
            return parts[0]
        return ""


@dataclass
class FinancialDetails:
    """Financial information for the listing."""

    asking_price: int  # GBP
    price_qualifier: str = ""  # e.g., "Guide Price", "Offers Over"

    # Yield information (if available)
    current_rent: Optional[int] = None  # Annual rent GBP
    gross_yield: Optional[float] = None  # Percentage

    # Per-unit metrics
    price_per_sqft: Optional[float] = None
    price_per_unit: Optional[float] = None

    # Lease details (for leasehold)
    ground_rent: Optional[int] = None
    service_charge: Optional[int] = None
    lease_years_remaining: Optional[int] = None


@dataclass
class PropertyDetails:
    """Physical property details."""

    property_type: PropertyType = PropertyType.OTHER
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    reception_rooms: Optional[int] = None
    total_sqft: Optional[int] = None

    # Multi-unit properties
    unit_count: int = 1

    # Condition
    condition: Condition = Condition.UNKNOWN
    epc_rating: str = ""  # A-G

    # Features
    parking: bool = False
    garden: bool = False
    has_tenants: bool = False


@dataclass
class Listing:
    """
    Property listing.

    Represents a property available for purchase that can be
    matched against investor mandates.
    """

    # Identification
    listing_id: str
    source: str  # e.g., "rightmove", "zoopla", "manual"
    source_url: str = ""

    # Classification
    asset_class: AssetClass = AssetClass.RESIDENTIAL
    tenure: Tenure = Tenure.UNKNOWN

    # Details
    address: Address = field(default_factory=Address)
    financial: FinancialDetails = field(default_factory=lambda: FinancialDetails(asking_price=0))
    property_details: PropertyDetails = field(default_factory=PropertyDetails)

    # Metadata
    title: str = ""
    description: str = ""
    images: list[str] = field(default_factory=list)
    agent_name: str = ""
    agent_phone: str = ""

    # Timestamps
    listed_date: Optional[datetime] = None
    scraped_at: Optional[datetime] = None

    # Status
    status: ListingStatus = ListingStatus.ACTIVE

    @property
    def postcode_area(self) -> str:
        """Convenience accessor for postcode area."""
        return self.address.postcode_area

    @property
    def region(self) -> str:
        """Convenience accessor for region."""
        return self.address.region

    @property
    def asking_price(self) -> int:
        """Convenience accessor for asking price."""
        return self.financial.asking_price

    @property
    def gross_yield(self) -> Optional[float]:
        """Calculate or return gross yield."""
        if self.financial.gross_yield:
            return self.financial.gross_yield
        if self.financial.current_rent and self.financial.asking_price:
            return (self.financial.current_rent / self.financial.asking_price) * 100
        return None

    def to_dict(self) -> dict:
        """Convert listing to dictionary representation."""
        return {
            "listing_id": self.listing_id,
            "source": self.source,
            "source_url": self.source_url,
            "asset_class": self.asset_class.value,
            "tenure": self.tenure.value,
            "address": {
                "street": self.address.street,
                "city": self.address.city,
                "region": self.address.region,
                "postcode": self.address.postcode,
                "country": self.address.country,
            },
            "financial": {
                "asking_price": self.financial.asking_price,
                "price_qualifier": self.financial.price_qualifier,
                "current_rent": self.financial.current_rent,
                "gross_yield": self.financial.gross_yield,
                "price_per_sqft": self.financial.price_per_sqft,
                "price_per_unit": self.financial.price_per_unit,
                "ground_rent": self.financial.ground_rent,
                "service_charge": self.financial.service_charge,
                "lease_years_remaining": self.financial.lease_years_remaining,
            },
            "property": {
                "property_type": self.property_details.property_type.value,
                "bedrooms": self.property_details.bedrooms,
                "bathrooms": self.property_details.bathrooms,
                "reception_rooms": self.property_details.reception_rooms,
                "total_sqft": self.property_details.total_sqft,
                "unit_count": self.property_details.unit_count,
                "condition": self.property_details.condition.value,
                "epc_rating": self.property_details.epc_rating,
                "parking": self.property_details.parking,
                "garden": self.property_details.garden,
                "has_tenants": self.property_details.has_tenants,
            },
            "title": self.title,
            "description": self.description,
            "images": self.images,
            "agent_name": self.agent_name,
            "agent_phone": self.agent_phone,
            "listed_date": self.listed_date.isoformat() if self.listed_date else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Listing":
        """Create listing from dictionary representation."""
        address = Address(
            street=data.get("address", {}).get("street", ""),
            city=data.get("address", {}).get("city", ""),
            region=data.get("address", {}).get("region", ""),
            postcode=data.get("address", {}).get("postcode", ""),
            country=data.get("address", {}).get("country", "UK"),
        )

        fin_data = data.get("financial", {})
        financial = FinancialDetails(
            asking_price=fin_data.get("asking_price", 0),
            price_qualifier=fin_data.get("price_qualifier", ""),
            current_rent=fin_data.get("current_rent"),
            gross_yield=fin_data.get("gross_yield"),
            price_per_sqft=fin_data.get("price_per_sqft"),
            price_per_unit=fin_data.get("price_per_unit"),
            ground_rent=fin_data.get("ground_rent"),
            service_charge=fin_data.get("service_charge"),
            lease_years_remaining=fin_data.get("lease_years_remaining"),
        )

        prop_data = data.get("property", {})
        property_details = PropertyDetails(
            property_type=PropertyType(prop_data.get("property_type", "other")),
            bedrooms=prop_data.get("bedrooms"),
            bathrooms=prop_data.get("bathrooms"),
            reception_rooms=prop_data.get("reception_rooms"),
            total_sqft=prop_data.get("total_sqft"),
            unit_count=prop_data.get("unit_count", 1),
            condition=Condition(prop_data.get("condition", "unknown")),
            epc_rating=prop_data.get("epc_rating", ""),
            parking=prop_data.get("parking", False),
            garden=prop_data.get("garden", False),
            has_tenants=prop_data.get("has_tenants", False),
        )

        listed_date = None
        if data.get("listed_date"):
            listed_date = datetime.fromisoformat(data["listed_date"])

        scraped_at = None
        if data.get("scraped_at"):
            scraped_at = datetime.fromisoformat(data["scraped_at"])

        return cls(
            listing_id=data["listing_id"],
            source=data.get("source", "unknown"),
            source_url=data.get("source_url", ""),
            asset_class=AssetClass(data.get("asset_class", "residential")),
            tenure=Tenure(data.get("tenure", "unknown")),
            address=address,
            financial=financial,
            property_details=property_details,
            title=data.get("title", ""),
            description=data.get("description", ""),
            images=data.get("images", []),
            agent_name=data.get("agent_name", ""),
            agent_phone=data.get("agent_phone", ""),
            listed_date=listed_date,
            scraped_at=scraped_at,
            status=ListingStatus(data.get("status", "active")),
        )
