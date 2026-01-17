"""
Simple HTTP server for mandate management API.

Phase 5: Internal API with no authentication.
Uses Python's built-in http.server for simplicity.
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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
    generate_recommendations,
    generate_report,
)
from deal_engine.planning import PlanningContext, PlanningPrecedent, PrecedentType
from .storage import MandateStorage, create_sample_mandates


# Global storage instance
_storage: MandateStorage = None


def get_storage() -> MandateStorage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        storage_path = os.environ.get(
            "MANDATE_STORAGE_PATH",
            str(Path(__file__).parent.parent.parent / "data" / "mandates.json")
        )
        _storage = MandateStorage(storage_path)

        # Create sample mandates if storage is empty
        if _storage.count() == 0:
            create_sample_mandates(_storage)

    return _storage


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mandate API."""

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def _send_error(self, message: str, status: int = 400) -> None:
        """Send error response."""
        self._send_json({"error": message}, status)

    def _read_json(self) -> dict:
        """Read JSON body from request."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        return json.loads(body) if body else {}

    def _serve_static(self, path: str) -> None:
        """Serve static files."""
        static_dir = Path(__file__).parent / "static"

        if path == "/" or path == "":
            path = "/index.html"

        file_path = static_dir / path.lstrip("/")

        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return

        # Determine content type
        ext = file_path.suffix.lower()
        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
        }
        content_type = content_types.get(ext, "text/plain")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API routes
        if path == "/api/mandates":
            self._handle_list_mandates(query)
        elif path.startswith("/api/mandates/"):
            mandate_id = path.split("/")[-1]
            self._handle_get_mandate(mandate_id)
        elif path == "/api/enums":
            self._handle_get_enums()
        elif path == "/api/health":
            self._send_json({"status": "ok", "mandates": get_storage().count()})
        else:
            # Serve static files
            self._serve_static(path)

    def do_POST(self) -> None:
        """Handle POST requests."""
        path = urlparse(self.path).path

        if path == "/api/mandates":
            self._handle_create_mandate()
        elif path == "/api/compare":
            self._handle_compare_mandates()
        elif path == "/api/search":
            self._handle_search()
        else:
            self._send_error("Not found", 404)

    def do_PUT(self) -> None:
        """Handle PUT requests."""
        path = urlparse(self.path).path

        if path.startswith("/api/mandates/"):
            mandate_id = path.split("/")[-1]
            self._handle_update_mandate(mandate_id)
        else:
            self._send_error("Not found", 404)

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        path = urlparse(self.path).path

        if path.startswith("/api/mandates/"):
            mandate_id = path.split("/")[-1]
            self._handle_delete_mandate(mandate_id)
        else:
            self._send_error("Not found", 404)

    def _handle_list_mandates(self, query: dict) -> None:
        """List all mandates."""
        storage = get_storage()
        mandates = storage.get_all()

        # Apply filters from query params
        if "active" in query:
            is_active = query["active"][0].lower() == "true"
            mandates = [m for m in mandates if m.is_active == is_active]

        if "investor_type" in query:
            inv_type = InvestorType(query["investor_type"][0])
            mandates = [m for m in mandates if m.investor_type == inv_type]

        self._send_json({
            "mandates": [m.to_dict() for m in mandates],
            "count": len(mandates),
        })

    def _handle_get_mandate(self, mandate_id: str) -> None:
        """Get a single mandate."""
        storage = get_storage()
        mandate = storage.get(mandate_id)

        if not mandate:
            self._send_error(f"Mandate '{mandate_id}' not found", 404)
            return

        self._send_json(mandate.to_dict())

    def _handle_create_mandate(self) -> None:
        """Create a new mandate."""
        try:
            data = self._read_json()

            # Generate ID if not provided
            storage = get_storage()
            if "mandate_id" not in data:
                data["mandate_id"] = storage.generate_id()

            mandate = Mandate.from_dict(data)
            storage.create(mandate)

            self._send_json(mandate.to_dict(), 201)

        except ValueError as e:
            self._send_error(str(e))
        except KeyError as e:
            self._send_error(f"Missing required field: {e}")

    def _handle_update_mandate(self, mandate_id: str) -> None:
        """Update an existing mandate."""
        try:
            data = self._read_json()
            data["mandate_id"] = mandate_id

            mandate = Mandate.from_dict(data)
            storage = get_storage()
            storage.update(mandate)

            self._send_json(mandate.to_dict())

        except ValueError as e:
            self._send_error(str(e))

    def _handle_delete_mandate(self, mandate_id: str) -> None:
        """Delete a mandate."""
        storage = get_storage()
        if storage.delete(mandate_id):
            self._send_json({"deleted": mandate_id})
        else:
            self._send_error(f"Mandate '{mandate_id}' not found", 404)

    def _handle_get_enums(self) -> None:
        """Get available enum values for form dropdowns."""
        self._send_json({
            "asset_classes": [e.value for e in AssetClass],
            "investor_types": [e.value for e in InvestorType],
            "risk_profiles": [e.value for e in RiskProfile],
        })

    def _handle_compare_mandates(self) -> None:
        """Compare multiple mandates."""
        try:
            data = self._read_json()
            mandate_ids = data.get("mandate_ids", [])

            if len(mandate_ids) < 2:
                self._send_error("At least 2 mandate IDs required for comparison")
                return

            storage = get_storage()
            mandates = []
            for mid in mandate_ids:
                mandate = storage.get(mid)
                if mandate:
                    mandates.append(mandate)

            if len(mandates) < 2:
                self._send_error("Could not find enough mandates for comparison")
                return

            # Build comparison data
            comparison = {
                "mandates": [m.to_dict() for m in mandates],
                "comparison": self._build_comparison(mandates),
            }

            self._send_json(comparison)

        except Exception as e:
            self._send_error(str(e))

    def _build_comparison(self, mandates: list[Mandate]) -> dict:
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

    def _handle_search(self) -> None:
        """Run listings against a mandate."""
        try:
            data = self._read_json()
            mandate_id = data.get("mandate_id")
            listings_data = data.get("listings", [])
            planning_context_data = data.get("planning_context")

            if not mandate_id:
                self._send_error("mandate_id required")
                return

            storage = get_storage()
            mandate = storage.get(mandate_id)

            if not mandate:
                self._send_error(f"Mandate '{mandate_id}' not found", 404)
                return

            # Convert listing dicts to Listing objects
            listings = []
            for ld in listings_data:
                try:
                    listing = self._dict_to_listing(ld)
                    listings.append(listing)
                except Exception as e:
                    print(f"Warning: Could not parse listing: {e}")

            if not listings:
                self._send_error("No valid listings provided")
                return

            # Convert planning context if provided
            planning_contexts = None
            if planning_context_data:
                try:
                    planning_context = self._dict_to_planning_context(planning_context_data)
                    # Apply same planning context to all listings in this search
                    planning_contexts = {
                        listing.listing_id: planning_context
                        for listing in listings
                    }
                except Exception as e:
                    print(f"Warning: Could not parse planning context: {e}")

            # Generate report
            report = generate_report(listings, mandate, planning_contexts=planning_contexts)

            self._send_json(report.to_dict())

        except Exception as e:
            self._send_error(str(e))

    def _dict_to_listing(self, data: dict) -> Listing:
        """Convert a dictionary to a Listing object."""
        from deal_engine.core.listing import (
            Address, FinancialDetails, PropertyDetails,
            Tenure, Condition
        )

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

    def _dict_to_planning_context(self, data: dict) -> PlanningContext:
        """Convert a dictionary to a PlanningContext object."""
        from datetime import datetime, timedelta

        # Convert precedents
        precedents = []
        for p in data.get("nearby_precedents", []):
            # Handle recency_years -> decision_date conversion
            decision_date = None
            if p.get("decision_date"):
                decision_date = datetime.fromisoformat(p["decision_date"])
            elif p.get("recency_years") is not None:
                # Convert recency in years back to a date
                recency = float(p["recency_years"])
                decision_date = datetime.now() - timedelta(days=recency * 365.25)

            precedent = PlanningPrecedent(
                reference=p.get("reference", ""),
                address=p.get("address", ""),
                precedent_type=PrecedentType(p.get("precedent_type", "other")),
                approved=p.get("approved", True),
                decision_date=decision_date,
                distance_meters=p.get("distance_meters"),
                similarity_score=p.get("similarity_score", 0.5),
            )
            precedents.append(precedent)

        return PlanningContext(
            property_type=data.get("property_type", ""),
            tenure=data.get("tenure", ""),
            current_sqft=data.get("current_sqft"),
            plot_size_sqft=data.get("plot_size_sqft"),
            conservation_area=data.get("conservation_area", False),
            listed_building=data.get("listed_building", False),
            listed_grade=data.get("listed_grade", ""),
            article_4_direction=data.get("article_4_direction", False),
            green_belt=data.get("green_belt", False),
            flood_zone=data.get("flood_zone", 1),
            tree_preservation_orders=data.get("tree_preservation_orders", False),
            nearby_precedents=precedents,
            proposed_type=PrecedentType(data.get("proposed_type", "other")),
        )

    def log_message(self, format: str, *args) -> None:
        """Override to customize logging."""
        if "/api/" in args[0]:
            print(f"[API] {args[0]}")


def run_server(host: str = "localhost", port: int = 8080) -> None:
    """
    Run the mandate management server.

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    server_address = (host, port)
    httpd = HTTPServer(server_address, APIHandler)

    print(f"""
============================================================
  AXIS DEAL ENGINE - MANDATE MANAGEMENT
============================================================

  Server running at: http://{host}:{port}

  API Endpoints:
    GET  /api/mandates        - List all mandates
    GET  /api/mandates/:id    - Get mandate by ID
    POST /api/mandates        - Create mandate
    PUT  /api/mandates/:id    - Update mandate
    DELETE /api/mandates/:id  - Delete mandate
    GET  /api/enums           - Get enum values
    POST /api/compare         - Compare mandates
    POST /api/search          - Run listings against mandate

  Press Ctrl+C to stop.
============================================================
""")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
