"""
Axis Deal Engine - FastAPI Web Application

Phase 5: Internal API with mandate management
Phase 7: Planning Context Input + UI Surfacing
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from deal_engine.core import (
    Mandate,
    AssetClass,
    InvestorType,
    RiskProfile,
    Listing,
    generate_report,
)
from deal_engine.core.listing import Address, FinancialDetails, PropertyDetails, Tenure, Condition
from deal_engine.planning import PlanningContext, PlanningPrecedent, PrecedentType
from deal_engine.api.storage import MandateStorage, create_sample_mandates


# Initialize FastAPI app
app = FastAPI(
    title="Axis Deal Engine",
    description="Mandate Management and Deal Scoring API",
    version="0.7.0",
)

# Setup paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Global storage instance
_storage: Optional[MandateStorage] = None


def get_storage() -> MandateStorage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        storage_path = os.environ.get(
            "MANDATE_STORAGE_PATH",
            str(Path(__file__).parent.parent / "data" / "mandates.json")
        )
        _storage = MandateStorage(storage_path)

        # Create sample mandates if storage is empty
        if _storage.count() == 0:
            create_sample_mandates(_storage)

    return _storage


# Pydantic models for request/response
class MandateCreate(BaseModel):
    investor_name: str
    investor_type: str
    asset_classes: list[str]
    risk_profile: str = "moderate"
    priority: int = 1
    is_active: bool = True
    notes: str = ""
    geographic: dict = {}
    financial: dict = {}
    property: dict = {}
    scoring_weights: dict = {}
    deal_criteria: dict = {}


class MandateCompare(BaseModel):
    mandate_ids: list[str]


class PrecedentInput(BaseModel):
    reference: str = ""
    address: str = ""
    precedent_type: str = "other"
    approved: bool = True
    decision_date: Optional[str] = None
    recency_years: Optional[float] = None
    distance_meters: Optional[float] = None
    similarity_score: float = 0.5


class PlanningContextInput(BaseModel):
    property_type: str = ""
    tenure: str = ""
    current_sqft: Optional[int] = None
    plot_size_sqft: Optional[int] = None
    conservation_area: bool = False
    listed_building: bool = False
    listed_grade: str = ""
    article_4_direction: bool = False
    green_belt: bool = False
    flood_zone: int = 1
    tree_preservation_orders: bool = False
    proposed_type: str = "other"
    nearby_precedents: list[PrecedentInput] = []


class SearchRequest(BaseModel):
    mandate_id: str
    listings: list[dict]
    planning_context: Optional[PlanningContextInput] = None


# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "mandates": get_storage().count()}


@app.get("/api/enums")
async def get_enums():
    """Get available enum values for form dropdowns."""
    return {
        "asset_classes": [e.value for e in AssetClass],
        "investor_types": [e.value for e in InvestorType],
        "risk_profiles": [e.value for e in RiskProfile],
    }


@app.get("/api/mandates")
async def list_mandates(active: Optional[bool] = None, investor_type: Optional[str] = None):
    """List all mandates with optional filtering."""
    storage = get_storage()
    mandates = storage.get_all()

    if active is not None:
        mandates = [m for m in mandates if m.is_active == active]

    if investor_type:
        inv_type = InvestorType(investor_type)
        mandates = [m for m in mandates if m.investor_type == inv_type]

    return {
        "mandates": [m.to_dict() for m in mandates],
        "count": len(mandates),
    }


@app.get("/api/mandates/{mandate_id}")
async def get_mandate(mandate_id: str):
    """Get a single mandate by ID."""
    storage = get_storage()
    mandate = storage.get(mandate_id)

    if not mandate:
        raise HTTPException(status_code=404, detail=f"Mandate '{mandate_id}' not found")

    return mandate.to_dict()


@app.post("/api/mandates")
async def create_mandate(data: MandateCreate):
    """Create a new mandate."""
    try:
        storage = get_storage()
        mandate_data = data.model_dump()

        # Generate ID if not provided
        if "mandate_id" not in mandate_data:
            mandate_data["mandate_id"] = storage.generate_id()

        mandate = Mandate.from_dict(mandate_data)
        storage.create(mandate)

        return JSONResponse(content=mandate.to_dict(), status_code=201)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {e}")


@app.put("/api/mandates/{mandate_id}")
async def update_mandate(mandate_id: str, data: MandateCreate):
    """Update an existing mandate."""
    try:
        mandate_data = data.model_dump()
        mandate_data["mandate_id"] = mandate_id

        mandate = Mandate.from_dict(mandate_data)
        storage = get_storage()
        storage.update(mandate)

        return mandate.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/mandates/{mandate_id}")
async def delete_mandate(mandate_id: str):
    """Delete a mandate."""
    storage = get_storage()
    if storage.delete(mandate_id):
        return {"deleted": mandate_id}
    else:
        raise HTTPException(status_code=404, detail=f"Mandate '{mandate_id}' not found")


@app.post("/api/compare")
async def compare_mandates(data: MandateCompare):
    """Compare multiple mandates."""
    mandate_ids = data.mandate_ids

    if len(mandate_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 mandate IDs required for comparison")

    storage = get_storage()
    mandates = []
    for mid in mandate_ids:
        mandate = storage.get(mid)
        if mandate:
            mandates.append(mandate)

    if len(mandates) < 2:
        raise HTTPException(status_code=400, detail="Could not find enough mandates for comparison")

    comparison = _build_comparison(mandates)

    return {
        "mandates": [m.to_dict() for m in mandates],
        "comparison": comparison,
    }


@app.post("/api/search")
async def search_listings(data: SearchRequest):
    """Run listings against a mandate with optional planning context."""
    mandate_id = data.mandate_id
    listings_data = data.listings
    planning_context_data = data.planning_context

    if not mandate_id:
        raise HTTPException(status_code=400, detail="mandate_id required")

    storage = get_storage()
    mandate = storage.get(mandate_id)

    if not mandate:
        raise HTTPException(status_code=404, detail=f"Mandate '{mandate_id}' not found")

    # Convert listing dicts to Listing objects
    listings = []
    for ld in listings_data:
        try:
            listing = _dict_to_listing(ld)
            listings.append(listing)
        except Exception as e:
            print(f"Warning: Could not parse listing: {e}")

    if not listings:
        raise HTTPException(status_code=400, detail="No valid listings provided")

    # Convert planning context if provided
    planning_contexts = None
    if planning_context_data:
        try:
            planning_context = _dict_to_planning_context(planning_context_data)
            # Apply same planning context to all listings in this search
            planning_contexts = {
                listing.listing_id: planning_context
                for listing in listings
            }
        except Exception as e:
            print(f"Warning: Could not parse planning context: {e}")

    # Generate report
    report = generate_report(listings, mandate, planning_contexts=planning_contexts)

    return report.to_dict()


# Helper functions

def _build_comparison(mandates: list[Mandate]) -> dict:
    """Build comparison summary between mandates."""
    comparison = {
        "price_ranges": [],
        "yield_requirements": [],
        "locations": [],
        "asset_classes": [],
        "risk_profiles": [],
        "scoring_weights": [],
    }

    for m in mandates:
        comparison["price_ranges"].append({
            "mandate_id": m.mandate_id,
            "investor": m.investor_name,
            "min": m.financial.min_deal_size,
            "max": m.financial.max_deal_size,
        })

        comparison["yield_requirements"].append({
            "mandate_id": m.mandate_id,
            "investor": m.investor_name,
            "min_yield": m.financial.min_yield,
            "target_yield": m.financial.target_yield,
        })

        comparison["locations"].append({
            "mandate_id": m.mandate_id,
            "investor": m.investor_name,
            "regions": m.geographic.regions,
            "postcodes": m.geographic.postcodes,
            "excludes": m.geographic.exclude_postcodes + m.geographic.exclude_regions,
        })

        comparison["asset_classes"].append({
            "mandate_id": m.mandate_id,
            "investor": m.investor_name,
            "classes": [ac.value for ac in m.asset_classes],
        })

        comparison["risk_profiles"].append({
            "mandate_id": m.mandate_id,
            "investor": m.investor_name,
            "profile": m.risk_profile.value,
        })

        comparison["scoring_weights"].append({
            "mandate_id": m.mandate_id,
            "investor": m.investor_name,
            "weights": m.scoring_weights.to_dict(),
        })

    return comparison


def _dict_to_listing(data: dict) -> Listing:
    """Convert a dictionary to a Listing object."""
    address = Address(
        street=data.get("address", {}).get("street", ""),
        city=data.get("address", {}).get("city", ""),
        region=data.get("address", {}).get("region", ""),
        postcode=data.get("address", {}).get("postcode", ""),
    )

    financial = FinancialDetails(
        asking_price=data.get("financial", {}).get("asking_price", 0),
        current_rent=data.get("financial", {}).get("current_rent"),
        gross_yield=data.get("financial", {}).get("gross_yield"),
        price_per_sqft=data.get("financial", {}).get("price_per_sqft"),
    )

    property_details = PropertyDetails(
        unit_count=data.get("property_details", {}).get("unit_count", 1),
        total_sqft=data.get("property_details", {}).get("total_sqft"),
        condition=Condition(data.get("property_details", {}).get("condition", "unknown")),
        has_tenants=data.get("property_details", {}).get("has_tenants", False),
    )

    return Listing(
        listing_id=data.get("listing_id", ""),
        source=data.get("source", "api"),
        title=data.get("title", ""),
        asset_class=AssetClass(data.get("asset_class", "residential")),
        tenure=Tenure(data.get("tenure", "unknown")),
        address=address,
        financial=financial,
        property_details=property_details,
    )


def _dict_to_planning_context(data: PlanningContextInput) -> PlanningContext:
    """Convert a PlanningContextInput to a PlanningContext object."""
    # Convert precedents
    precedents = []
    for p in data.nearby_precedents:
        # Handle recency_years -> decision_date conversion
        decision_date = None
        if p.decision_date:
            decision_date = datetime.fromisoformat(p.decision_date)
        elif p.recency_years is not None:
            # Convert recency in years back to a date
            recency = float(p.recency_years)
            decision_date = datetime.now() - timedelta(days=recency * 365.25)

        precedent = PlanningPrecedent(
            reference=p.reference or "",
            address=p.address or "",
            precedent_type=PrecedentType(p.precedent_type or "other"),
            approved=p.approved,
            decision_date=decision_date,
            distance_meters=p.distance_meters,
            similarity_score=p.similarity_score,
        )
        precedents.append(precedent)

    return PlanningContext(
        property_type=data.property_type or "",
        tenure=data.tenure or "",
        current_sqft=data.current_sqft,
        plot_size_sqft=data.plot_size_sqft,
        conservation_area=data.conservation_area,
        listed_building=data.listed_building,
        listed_grade=data.listed_grade or "",
        article_4_direction=data.article_4_direction,
        green_belt=data.green_belt,
        flood_zone=data.flood_zone,
        tree_preservation_orders=data.tree_preservation_orders,
        nearby_precedents=precedents,
        proposed_type=PrecedentType(data.proposed_type or "other"),
    )


# Run with: uvicorn web.app:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
