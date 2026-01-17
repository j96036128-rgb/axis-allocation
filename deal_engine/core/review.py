"""
Review state machine module.

Manages the lifecycle of deal reviews through defined states:
NEW → REVIEWING → ACCEPTED | DECLINED

Includes audit trail and state transition validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReviewState(Enum):
    """Possible states for a deal review."""

    NEW = "new"  # Initial state, awaiting review
    REVIEWING = "reviewing"  # Under active review
    ACCEPTED = "accepted"  # Approved for investor presentation
    DECLINED = "declined"  # Rejected, with reasons


class ReviewAction(Enum):
    """Actions that can transition review state."""

    START_REVIEW = "start_review"
    ACCEPT = "accept"
    DECLINE = "decline"
    RESET = "reset"  # Return to NEW (admin only)


# Valid state transitions
VALID_TRANSITIONS: dict[ReviewState, dict[ReviewAction, ReviewState]] = {
    ReviewState.NEW: {
        ReviewAction.START_REVIEW: ReviewState.REVIEWING,
    },
    ReviewState.REVIEWING: {
        ReviewAction.ACCEPT: ReviewState.ACCEPTED,
        ReviewAction.DECLINE: ReviewState.DECLINED,
        ReviewAction.RESET: ReviewState.NEW,
    },
    ReviewState.ACCEPTED: {
        ReviewAction.RESET: ReviewState.NEW,
    },
    ReviewState.DECLINED: {
        ReviewAction.RESET: ReviewState.NEW,
    },
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_state: ReviewState, action: ReviewAction):
        self.current_state = current_state
        self.action = action
        super().__init__(
            f"Cannot perform '{action.value}' from state '{current_state.value}'"
        )


@dataclass
class StateTransition:
    """Record of a state transition in the audit trail."""

    from_state: ReviewState
    to_state: ReviewState
    action: ReviewAction
    timestamp: datetime
    actor: str  # Who performed the action
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "action": self.action.value,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "notes": self.notes,
        }


@dataclass
class DealReview:
    """
    Review record for a listing-mandate match.

    Tracks the review state and maintains an audit trail
    of all state transitions.
    """

    # Identifiers
    review_id: str
    listing_id: str
    mandate_id: str

    # Current state
    state: ReviewState = ReviewState.NEW

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Review details
    assigned_to: Optional[str] = None
    priority: int = 3  # 1=highest, 5=lowest

    # Decision details (populated on ACCEPT/DECLINE)
    decision_notes: str = ""
    decline_reasons: list[str] = field(default_factory=list)

    # Audit trail
    history: list[StateTransition] = field(default_factory=list)

    def can_transition(self, action: ReviewAction) -> bool:
        """Check if a transition is valid from current state."""
        valid_actions = VALID_TRANSITIONS.get(self.state, {})
        return action in valid_actions

    def get_valid_actions(self) -> list[ReviewAction]:
        """Get list of valid actions from current state."""
        return list(VALID_TRANSITIONS.get(self.state, {}).keys())

    def transition(
        self,
        action: ReviewAction,
        actor: str,
        notes: str = ""
    ) -> "DealReview":
        """
        Perform a state transition.

        Args:
            action: The action to perform
            actor: Who is performing the action
            notes: Optional notes about the transition

        Returns:
            Self (for chaining)

        Raises:
            InvalidTransitionError: If transition is not valid
        """
        if not self.can_transition(action):
            raise InvalidTransitionError(self.state, action)

        new_state = VALID_TRANSITIONS[self.state][action]
        now = datetime.now()

        # Record the transition
        transition = StateTransition(
            from_state=self.state,
            to_state=new_state,
            action=action,
            timestamp=now,
            actor=actor,
            notes=notes,
        )
        self.history.append(transition)

        # Update state
        self.state = new_state
        self.updated_at = now

        return self

    def start_review(self, actor: str, notes: str = "") -> "DealReview":
        """Start reviewing this deal."""
        return self.transition(ReviewAction.START_REVIEW, actor, notes)

    def accept(self, actor: str, notes: str = "") -> "DealReview":
        """Accept this deal for investor presentation."""
        self.decision_notes = notes
        return self.transition(ReviewAction.ACCEPT, actor, notes)

    def decline(
        self,
        actor: str,
        reasons: list[str],
        notes: str = ""
    ) -> "DealReview":
        """Decline this deal with reasons."""
        self.decline_reasons = reasons
        self.decision_notes = notes
        return self.transition(ReviewAction.DECLINE, actor, notes)

    def reset(self, actor: str, notes: str = "") -> "DealReview":
        """Reset to NEW state (admin action)."""
        return self.transition(ReviewAction.RESET, actor, notes)

    @property
    def is_pending(self) -> bool:
        """Check if review is still pending decision."""
        return self.state in (ReviewState.NEW, ReviewState.REVIEWING)

    @property
    def is_decided(self) -> bool:
        """Check if review has been decided."""
        return self.state in (ReviewState.ACCEPTED, ReviewState.DECLINED)

    @property
    def time_in_review(self) -> Optional[float]:
        """Get time spent in review (hours), if applicable."""
        if not self.history:
            return None

        # Find when review started
        review_start = None
        review_end = None

        for transition in self.history:
            if transition.action == ReviewAction.START_REVIEW:
                review_start = transition.timestamp
            elif transition.action in (ReviewAction.ACCEPT, ReviewAction.DECLINE):
                review_end = transition.timestamp

        if review_start and review_end:
            delta = review_end - review_start
            return delta.total_seconds() / 3600

        return None

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "review_id": self.review_id,
            "listing_id": self.listing_id,
            "mandate_id": self.mandate_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "assigned_to": self.assigned_to,
            "priority": self.priority,
            "decision_notes": self.decision_notes,
            "decline_reasons": self.decline_reasons,
            "is_pending": self.is_pending,
            "is_decided": self.is_decided,
            "valid_actions": [a.value for a in self.get_valid_actions()],
            "history": [t.to_dict() for t in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DealReview":
        """Create review from dictionary representation."""
        review = cls(
            review_id=data["review_id"],
            listing_id=data["listing_id"],
            mandate_id=data["mandate_id"],
            state=ReviewState(data.get("state", "new")),
            assigned_to=data.get("assigned_to"),
            priority=data.get("priority", 3),
            decision_notes=data.get("decision_notes", ""),
            decline_reasons=data.get("decline_reasons", []),
        )

        if data.get("created_at"):
            review.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            review.updated_at = datetime.fromisoformat(data["updated_at"])

        # Reconstruct history
        for h in data.get("history", []):
            transition = StateTransition(
                from_state=ReviewState(h["from_state"]),
                to_state=ReviewState(h["to_state"]),
                action=ReviewAction(h["action"]),
                timestamp=datetime.fromisoformat(h["timestamp"]),
                actor=h["actor"],
                notes=h.get("notes", ""),
            )
            review.history.append(transition)

        return review


class ReviewQueue:
    """
    Manages a queue of deal reviews.

    Provides filtering, sorting, and batch operations.
    """

    def __init__(self):
        self._reviews: dict[str, DealReview] = {}

    def add(self, review: DealReview) -> None:
        """Add a review to the queue."""
        self._reviews[review.review_id] = review

    def get(self, review_id: str) -> Optional[DealReview]:
        """Get a review by ID."""
        return self._reviews.get(review_id)

    def remove(self, review_id: str) -> Optional[DealReview]:
        """Remove and return a review."""
        return self._reviews.pop(review_id, None)

    def all(self) -> list[DealReview]:
        """Get all reviews."""
        return list(self._reviews.values())

    def by_state(self, state: ReviewState) -> list[DealReview]:
        """Get reviews in a specific state."""
        return [r for r in self._reviews.values() if r.state == state]

    def by_mandate(self, mandate_id: str) -> list[DealReview]:
        """Get reviews for a specific mandate."""
        return [r for r in self._reviews.values() if r.mandate_id == mandate_id]

    def pending(self) -> list[DealReview]:
        """Get all pending reviews (NEW or REVIEWING)."""
        return [r for r in self._reviews.values() if r.is_pending]

    def decided(self) -> list[DealReview]:
        """Get all decided reviews (ACCEPTED or DECLINED)."""
        return [r for r in self._reviews.values() if r.is_decided]

    def by_priority(self, max_priority: int = 3) -> list[DealReview]:
        """Get reviews at or above priority threshold."""
        return sorted(
            [r for r in self._reviews.values() if r.priority <= max_priority],
            key=lambda r: r.priority
        )

    def stats(self) -> dict:
        """Get queue statistics."""
        reviews = list(self._reviews.values())
        return {
            "total": len(reviews),
            "by_state": {
                state.value: len([r for r in reviews if r.state == state])
                for state in ReviewState
            },
            "pending_count": len([r for r in reviews if r.is_pending]),
            "decided_count": len([r for r in reviews if r.is_decided]),
            "avg_priority": (
                sum(r.priority for r in reviews) / len(reviews)
                if reviews else 0
            ),
        }

    def to_dict(self) -> dict:
        """Convert queue to dictionary representation."""
        return {
            "reviews": [r.to_dict() for r in self._reviews.values()],
            "stats": self.stats(),
        }


def create_review(
    listing_id: str,
    mandate_id: str,
    priority: int = 3,
    assigned_to: Optional[str] = None
) -> DealReview:
    """
    Factory function to create a new deal review.

    Args:
        listing_id: The listing being reviewed
        mandate_id: The mandate being matched against
        priority: Review priority (1=highest, 5=lowest)
        assigned_to: Optional reviewer assignment

    Returns:
        New DealReview in NEW state
    """
    import uuid

    review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"

    return DealReview(
        review_id=review_id,
        listing_id=listing_id,
        mandate_id=mandate_id,
        priority=priority,
        assigned_to=assigned_to,
    )
