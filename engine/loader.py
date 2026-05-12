import json
from pathlib import Path
from .models import Plan, PhysicalCard, IntentionCard, ScoringRule

DATA_DIR = Path(__file__).parent.parent / "data"


def load_plan_cards() -> list[PhysicalCard]:
    raw = json.loads((DATA_DIR / "plan_cards.json").read_text())
    cards = []
    for c in raw:
        plans = []
        for p in c["plans"]:
            rules = [ScoringRule(**r) for r in p["scoring"]]
            plans.append(Plan(
                plan_id=p["plan_id"],
                frame_type=p["frame_type"],
                genre=p["genre"],
                content=p["content"],
                scoring=rules,
            ))
        cards.append(PhysicalCard(
            card_id=c["card_id"],
            physical_type=c["physical_type"],
            plans=plans,
        ))
    return cards


def load_intention_cards() -> list[IntentionCard]:
    raw = json.loads((DATA_DIR / "intention_cards.json").read_text())
    return [IntentionCard(**c) for c in raw]
