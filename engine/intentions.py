from .models import BancDeMontage, IntentionCard, Plan


def _visible(banc: BancDeMontage) -> list[Plan]:
    return banc.visible_plans


def _count_content(plans: list[Plan], attr: str) -> int:
    return sum(1 for p in plans if attr in p.content)


def _count_genre(plans: list[Plan], genre: str) -> int:
    return sum(1 for p in plans if p.genre == genre)


def _distinct_genres(plans: list[Plan]) -> set:
    return {p.genre for p in plans if p.genre is not None}


def evaluate_intention(card: IntentionCard, banc: BancDeMontage) -> bool:
    plans = _visible(banc)
    if not plans:
        return False

    cond = card.condition

    # --- THÉMATIQUES ---
    if cond == "max_genres_2":
        return len(_distinct_genres(plans)) <= 2

    if cond == "min_genres_3":
        return len(_distinct_genres(plans)) >= 3

    if cond == "no_allie":
        return all("ALLIE" not in p.content for p in plans)

    if cond == "no_arme":
        return all("ARME" not in p.content for p in plans)

    if cond == "no_ennemi":
        return all("ENNEMI" not in p.content for p in plans)

    if cond == "no_voiture":
        return all("VOITURE" not in p.content for p in plans)

    if cond == "no_suspense_genre":
        return all(p.genre != "Suspense" for p in plans)

    if cond == "heroine_strict_majority_character":
        h = _count_content(plans, "HEROINE")
        e = _count_content(plans, "ENNEMI")
        a = _count_content(plans, "ALLIE")
        return h > 0 and h > e and h > a

    if cond == "ennemi_strict_majority_character":
        h = _count_content(plans, "HEROINE")
        e = _count_content(plans, "ENNEMI")
        a = _count_content(plans, "ALLIE")
        return e > 0 and e > h and e > a

    if cond == "objet_strict_majority_element":
        o = _count_content(plans, "OBJET")
        ar = _count_content(plans, "ARME")
        v = _count_content(plans, "VOITURE")
        return o > 0 and o > ar and o > v

    if cond == "voiture_strict_majority_element":
        o = _count_content(plans, "OBJET")
        ar = _count_content(plans, "ARME")
        v = _count_content(plans, "VOITURE")
        return v > 0 and v > ar and v > o

    if cond == "arme_strict_majority_element":
        o = _count_content(plans, "OBJET")
        ar = _count_content(plans, "ARME")
        v = _count_content(plans, "VOITURE")
        return ar > 0 and ar > o and ar > v

    # --- TECHNIQUES ---
    if cond == "faux_raccord_1":
        # At least 1 adjacent pair shares nothing
        for i in range(1, len(plans)):
            if not plans[i - 1].face_down and not plans[i].face_down:
                if not plans[i].shares_with(plans[i - 1]):
                    return True
        return False

    if cond == "faux_raccord_3":
        # At least 3 plans each share nothing with their predecessor
        count = 0
        for i in range(1, len(plans)):
            if not plans[i - 1].face_down and not plans[i].face_down:
                if not plans[i].shares_with(plans[i - 1]):
                    count += 1
        return count >= 3

    if cond == "all_adjacent_share_element":
        # Every adjacent pair shares at least one character/element/genre
        for i in range(1, len(plans)):
            p, q = plans[i - 1], plans[i]
            if p.face_down or q.face_down:
                continue
            if not p.shares_with(q):
                return False
        return True

    if cond == "no_adjacent_same_frame":
        for i in range(1, len(plans)):
            if plans[i - 1].frame_type == plans[i].frame_type:
                return False
        return True

    if cond == "zoom_sequence":
        # PLAN_LARGE → PLAN_MOYEN → GROS_PLAN somewhere in sequence
        sequence = [p.frame_type for p in plans]
        for i in range(len(sequence) - 2):
            if (sequence[i] == "PLAN_LARGE"
                    and sequence[i + 1] == "PLAN_MOYEN"
                    and sequence[i + 2] == "GROS_PLAN"):
                return True
        return False

    if cond == "dezoom_sequence":
        # GROS_PLAN → PLAN_MOYEN → PLAN_LARGE
        sequence = [p.frame_type for p in plans]
        for i in range(len(sequence) - 2):
            if (sequence[i] == "GROS_PLAN"
                    and sequence[i + 1] == "PLAN_MOYEN"
                    and sequence[i + 2] == "PLAN_LARGE"):
                return True
        return False

    if cond == "noir_between_two_plans":
        # A face-down plan exists between two face-up plans (not at start/end)
        for i in range(1, len(plans) - 1):
            if plans[i].face_down and not plans[i - 1].face_down and not plans[i + 1].face_down:
                return True
        return False

    if cond == "noir_at_start_and_end":
        return (len(plans) >= 2
                and plans[0].face_down
                and plans[-1].face_down)

    # --- NARRATIVES ---
    if cond == "heroine_ennemi_same_plan_2":
        count = sum(1 for p in plans if "HEROINE" in p.content and "ENNEMI" in p.content)
        return count >= 2

    if cond == "ennemi_allie_never_same_plan":
        return all(not ("ENNEMI" in p.content and "ALLIE" in p.content) for p in plans)

    if cond == "heroine_survives_last":
        visible_face_up = [p for p in plans if not p.face_down]
        return bool(visible_face_up) and "HEROINE" in visible_face_up[-1].content

    if cond == "3_consecutive_voiture":
        return _has_n_consecutive_with(plans, "VOITURE", 3)

    if cond == "3_consecutive_objet":
        return _has_n_consecutive_with(plans, "OBJET", 3)

    if cond == "3_consecutive_arme":
        return _has_n_consecutive_with(plans, "ARME", 3)

    if cond == "ennemi_appears_2_then_gone":
        # ENNEMI appears exactly 2 times total, anywhere in the montage
        return _count_content(plans, "ENNEMI") == 2

    if cond == "heroine_allie_same_plan_2":
        count = sum(1 for p in plans if "HEROINE" in p.content and "ALLIE" in p.content)
        return count >= 2

    if cond == "allie_isolated":
        # ALLIE appears but never in the same plan as HEROINE or ENNEMI
        has_allie = any("ALLIE" in p.content for p in plans)
        if not has_allie:
            return False
        return all(
            not ("ALLIE" in p.content and ("HEROINE" in p.content or "ENNEMI" in p.content))
            for p in plans
        )

    raise ValueError(f"Unknown condition: {cond}")


def _has_n_consecutive_with(plans: list[Plan], attr: str, n: int) -> bool:
    run = 0
    for p in plans:
        if attr in p.content:
            run += 1
            if run >= n:
                return True
        else:
            run = 0
    return False


def score_intentions(
    personal: list[IntentionCard],
    shared: list[IntentionCard],
    banc: BancDeMontage,
) -> dict:
    results = []
    total = 0

    for card in personal + shared:
        success = evaluate_intention(card, banc)
        pts = card.points if success else 0
        total += pts
        results.append({
            "card_id": card.card_id,
            "title": card.title,
            "type": card.type,
            "points": card.points,
            "earned": pts,
            "success": success,
            "shared": card in shared,
        })

    return {"total": total, "intentions": results}
