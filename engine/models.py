from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


CHARACTERS = {"HEROINE", "ENNEMI", "ALLIE"}
ELEMENTS = {"ARME", "OBJET", "VOITURE"}
GENRES = {"Action", "Policier", "Suspense"}
FRAME_TYPES = {"PLAN_LARGE", "PLAN_MOYEN", "GROS_PLAN"}


@dataclass
class ScoringRule:
    type: str           # "GAUCHE", "DROITE", "COUNT_ALL"
    attribute: str      # what to check or count
    points: int


@dataclass
class Plan:
    plan_id: str
    frame_type: str                         # PLAN_LARGE | PLAN_MOYEN | GROS_PLAN
    genre: Optional[str]                    # Action | Policier | Suspense | None
    content: list[str]                      # characters + elements present
    scoring: list[ScoringRule]
    face_down: bool = False                 # placed as Plan Noir (face cachée)

    def shares_with(self, other: "Plan") -> bool:
        """True if this plan and other share any character, element, or genre."""
        self_tags = set(self.content) | ({self.genre} if self.genre else set())
        other_tags = set(other.content) | ({other.genre} if other.genre else set())
        return bool(self_tags & other_tags)

    def has(self, attribute: str) -> bool:
        """Check if this plan has the given attribute (content, frame_type, genre-based)."""
        if attribute == "VIDE":
            return self.face_down or "VIDE" in self.content
        if attribute in ("PLAN_LARGE", "PLAN_MOYEN", "GROS_PLAN"):
            return self.frame_type == attribute
        if attribute == "PLAN_ACTION":
            return self.genre == "Action"
        if attribute == "PLAN_SUSPENSE":
            return self.genre == "Suspense"
        if attribute == "PLAN_POLICIER":
            return self.genre == "Policier"
        return attribute in self.content


@dataclass
class PhysicalCard:
    card_id: int
    physical_type: str      # PLAN_LARGE | COMBO
    plans: list[Plan]       # 1 plan for PLAN_LARGE, 2 for COMBO


@dataclass
class PlacedCard:
    """A physical card placed in the banc de montage with chosen orientation."""
    physical_card: PhysicalCard
    # For COMBO: which plans are visible (can be 1 or 2), in left-to-right order
    # For PLAN_LARGE: always [plans[0]]
    visible_plans: list[Plan]


@dataclass
class BancDeMontage:
    """The player's editing timeline: an ordered list of visible plans."""
    placed_cards: list[PlacedCard] = field(default_factory=list)

    @property
    def visible_plans(self) -> list[Plan]:
        plans = []
        for pc in self.placed_cards:
            plans.extend(pc.visible_plans)
        return plans

    def count_attribute(self, attribute: str) -> int:
        return sum(1 for p in self.visible_plans if p.has(attribute))


@dataclass
class IntentionCard:
    card_id: int
    type: str           # THEMATIQUE | TECHNIQUE | NARRATIVE
    title: str
    genre: Optional[str]
    points: int
    icon: Optional[str]
    condition: str
    description: str
