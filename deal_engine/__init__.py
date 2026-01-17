"""
Axis Deal Engine

Core modules for mandate matching and property deal scoring.

Phases:
  1. Core data models and scoring
  2. Conviction, rejection, review, recommendations
  4. Configurable deal criteria and per-mandate weights
  5. Internal mandate management API
  6. Planning upside engine

Usage:
    from deal_engine.core import Mandate, Listing, generate_report
    from deal_engine.planning import PlanningContext, get_planning_assessment
"""

__version__ = "0.7.0"
