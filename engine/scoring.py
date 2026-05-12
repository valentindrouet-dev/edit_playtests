from .models import BancDeMontage, Plan, ScoringRule


def score_plan(plan: Plan, idx: int, banc: BancDeMontage) -> dict:
    """Calculate points earned by a single visible plan at position idx."""
    plans = banc.visible_plans
    breakdown = {}

    if plan.face_down:
        return breakdown

    for rule in plan.scoring:
        if rule.type == "GAUCHE":
            if idx > 0 and plans[idx - 1].has(rule.attribute):
                breakdown[f"GAUCHE_{rule.attribute}"] = rule.points
        elif rule.type == "DROITE":
            if idx < len(plans) - 1 and plans[idx + 1].has(rule.attribute):
                breakdown[f"DROITE_{rule.attribute}"] = rule.points
        elif rule.type == "COUNT_ALL":
            count = banc.count_attribute(rule.attribute)
            if count > 0:
                breakdown[f"COUNT_{rule.attribute}"] = rule.points * count

    return breakdown


def score_banc(banc: BancDeMontage) -> dict:
    """Calculate total plan scores for the entire banc de montage."""
    plans = banc.visible_plans
    total = 0
    per_plan = []

    for i, plan in enumerate(plans):
        breakdown = score_plan(plan, i, banc)
        pts = sum(breakdown.values())
        per_plan.append({
            "plan_id": plan.plan_id,
            "frame_type": plan.frame_type,
            "genre": plan.genre,
            "content": plan.content,
            "face_down": plan.face_down,
            "points": pts,
            "breakdown": breakdown,
        })
        total += pts

    return {"total": total, "per_plan": per_plan}
