"""
Game simulator for EDIT.

Phase A — Dérushage : 4 drafting rounds into shared chutiers. Each chutier seeded
          with 1 Plan Large. Direction card determines which chutier each player keeps.
Phase B — Tri + Intentions : player sorts hand face-down, picks 1 intention card
          every 3 cards placed (at milestones 3, 6, 9). Shared intentions revealed.
Phase C — Montage : greedy or random placement, respecting MAX_VISIBLE_PLANS = 10.
Phase D — Visionnage : scoring of plans + intentions.
"""
from __future__ import annotations
import random
import copy
from typing import Literal

from .models import PhysicalCard, Plan, PlacedCard, BancDeMontage, IntentionCard
from .scoring import score_banc
from .intentions import score_intentions, evaluate_intention
from .loader import load_plan_cards, load_intention_cards


DRAW_SIZES = {2: 19, 3: 28, 4: 37}
MAX_VISIBLE_PLANS = 10
INTENTION_TYPES = ["THEMATIQUE", "NARRATIVE", "TECHNIQUE"]


# ── Card helpers ──────────────────────────────────────────────────────────────

def card_label(card: PhysicalCard) -> str:
    if card.physical_type == "PLAN_LARGE":
        p = card.plans[0]
        return f"#{card.card_id} LARGE [{p.genre or '—'}] {' • '.join(p.content)}"
    a, b = card.plans[0], card.plans[1]
    return f"#{card.card_id} {a.frame_type}/{b.frame_type} [{a.genre or '—'}/{b.genre or '—'}]"


def plan_label(plan: Plan) -> str:
    fd = " [NOIR]" if plan.face_down else ""
    return f"{plan.plan_id} {plan.frame_type}{fd} [{plan.genre or '—'}] {' • '.join(plan.content)}"


# ── Placement helpers ─────────────────────────────────────────────────────────

def _make_vide_plan(card_id: int) -> Plan:
    """Whole-card face-down placeholder (VIDE). No scoring."""
    return Plan(
        plan_id=f"{card_id}_NOIR",
        frame_type="VIDE",
        genre=None,
        content=["VIDE"],
        scoring=[],
        face_down=True,
    )


def _make_placement_options(card: PhysicalCard) -> list[list[Plan]]:
    """
    Valid placements for a physical card:

    PLAN LARGE:
      - [plan]  — face visible (1 plan)
      - [VIDE]  — carte retournée face noire (0 plan visible)

    COMBO (GROS PLAN + PLAN MOYEN):
      - [A, B]  — les 2 plans visibles côte à côte
      - [B, A]  — idem, sens inverse
      - [A]     — seul A visible, B recouvert par une carte adjacente
      - [B]     — seul B visible, A recouvert par une carte adjacente
      - [VIDE]  — toute la carte retournée face noire

    NB: on ne peut PAS avoir un demi-VIDE + un plan visible sur la même carte
    physique — retourner face noire concerne TOUTE la carte.
    """
    vide = _make_vide_plan(card.card_id)

    if card.physical_type == "PLAN_LARGE":
        return [
            [card.plans[0]],  # face visible
            [vide],           # face cachée
        ]

    a, b = card.plans[0], card.plans[1]
    return [
        [a, b],   # 2 plans visibles, A à gauche
        [b, a],   # 2 plans visibles, B à gauche
        [a],      # seul A visible (B recouvert)
        [b],      # seul B visible (A recouvert)
        [vide],   # carte entière face cachée
    ]


def _visible_count(option: list[Plan]) -> int:
    return sum(1 for p in option if not p.face_down)


def _valid_options(card: PhysicalCard, current_visible: int) -> list[list[Plan]]:
    """Filter options so total visible plans in banc stays ≤ MAX_VISIBLE_PLANS."""
    budget = MAX_VISIBLE_PLANS - current_visible
    return [opt for opt in _make_placement_options(card) if _visible_count(opt) <= budget]


def _greedy_place(hand: list[PhysicalCard]) -> tuple[BancDeMontage, list[dict]]:
    """Place cards greedily (max score at each step), respecting 10-plan limit."""
    banc = BancDeMontage()
    remaining = list(hand)
    placement_log = []

    while remaining:
        current_visible = len([p for p in banc.visible_plans if not p.face_down])
        random.shuffle(remaining)

        best_card = best_option = None
        best_score = -1

        for card in remaining:
            for option in _valid_options(card, current_visible):
                trial = BancDeMontage(placed_cards=banc.placed_cards + [PlacedCard(card, option)])
                s = score_banc(trial)["total"]
                if s > best_score:
                    best_score = s
                    best_card = card
                    best_option = option

        banc.placed_cards.append(PlacedCard(best_card, best_option))
        remaining.remove(best_card)

        placement_log.append({
            "step": len(placement_log) + 1,
            "card_id": best_card.card_id,
            "card_label": card_label(best_card),
            "visible_plans": [plan_label(p) for p in best_option],
            "n_visible_after": len([p for p in banc.visible_plans if not p.face_down]),
            "running_score": score_banc(banc)["total"],
        })

    return banc, placement_log


def _random_place(hand: list[PhysicalCard]) -> tuple[BancDeMontage, list[dict]]:
    banc = BancDeMontage()
    shuffled = list(hand)
    random.shuffle(shuffled)
    placement_log = []

    for card in shuffled:
        current_visible = len([p for p in banc.visible_plans if not p.face_down])
        options = _valid_options(card, current_visible)
        chosen = random.choice(options)
        banc.placed_cards.append(PlacedCard(card, chosen))

        placement_log.append({
            "step": len(placement_log) + 1,
            "card_id": card.card_id,
            "card_label": card_label(card),
            "visible_plans": [plan_label(p) for p in chosen],
            "n_visible_after": len([p for p in banc.visible_plans if not p.face_down]),
            "running_score": score_banc(banc)["total"],
        })

    return banc, placement_log


# ── Phase A ───────────────────────────────────────────────────────────────────

def _simulate_phase_a(all_cards: list[PhysicalCard], n_players: int) -> dict:
    """
    Simulate the Dérushage phase.

    Chutier i is between player i and player (i+1)%n:
      - right chutier of player i   = chutier i
      - left  chutier of player i   = chutier (i-1)%n
    """
    plan_large = [c for c in all_cards if c.physical_type == "PLAN_LARGE"]
    combo = [c for c in all_cards if c.physical_type == "COMBO"]

    random.shuffle(plan_large)
    # One Plan Large seeds each chutier
    chutier_seeds = plan_large[:n_players]
    chutiers: dict[int, list[PhysicalCard]] = {i: [chutier_seeds[i]] for i in range(n_players)}

    # Remaining cards + combos → draw deck (last card = direction card)
    remaining = plan_large[n_players:] + combo
    random.shuffle(remaining)
    deck = remaining[:DRAW_SIZES[n_players]]          # includes direction card at index -1
    draw_pool = deck[:-1]                              # cards available to draw
    direction = random.choice(["gauche", "droite"])   # simulates direction card

    round_logs = []
    pool_idx = 0

    for round_num in range(4):
        actions = []
        # All players act simultaneously; we iterate sequentially for logging
        for player_idx in range(n_players):
            c1 = draw_pool[pool_idx];     pool_idx += 1
            c2 = draw_pool[pool_idx];     pool_idx += 1

            right_chutier = player_idx
            left_chutier = (player_idx - 1) % n_players

            # Naive strategy: first drawn card left, second right
            chutiers[left_chutier].append(c1)
            chutiers[right_chutier].append(c2)

            actions.append({
                "player": player_idx + 1,
                "drawn": [card_label(c1), card_label(c2)],
                "placed_left": card_label(c1),
                "placed_right": card_label(c2),
                "left_chutier": left_chutier,
                "right_chutier": right_chutier,
            })
        round_logs.append({"round": round_num + 1, "actions": actions})

    # Each player takes a chutier based on direction
    player_hands: dict[int, list[PhysicalCard]] = {}
    for player_idx in range(n_players):
        taken = (player_idx - 1) % n_players if direction == "gauche" else player_idx
        player_hands[player_idx] = list(chutiers[taken])

    return {
        "rounds": round_logs,
        "chutiers": {
            i: {
                "seed": card_label(chutiers[i][0]),
                "cards": [card_label(c) for c in chutiers[i]],
            }
            for i in range(n_players)
        },
        "direction": direction,
        "player_hands": {
            p + 1: [card_label(c) for c in hand]
            for p, hand in player_hands.items()
        },
        "_hands_raw": player_hands,
    }


# ── Phase B ───────────────────────────────────────────────────────────────────

def _pick_intention(
    piles: dict[str, list[IntentionCard]],
    visible: dict[str, IntentionCard | None],
    used: set[int],
    player_num: int,
    already_picked: list[IntentionCard],
) -> tuple[IntentionCard, str, str]:
    """Pick one intention card for a player (helper for Phase B)."""
    needed = [t for t in INTENTION_TYPES if not any(c.type == t for c in already_picked)]
    chosen_type = random.choice(needed)

    # 50% visible, 50% blind draw
    if (random.random() < 0.5
            and visible[chosen_type]
            and visible[chosen_type].card_id not in used):
        chosen = visible[chosen_type]
        method = "visible"
    else:
        candidates = [c for c in piles[chosen_type] if c.card_id not in used]
        chosen = random.choice(candidates[:3]) if candidates else visible[chosen_type]
        method = "pioche aveugle"

    used.add(chosen.card_id)
    remaining = [c for c in piles[chosen_type] if c.card_id not in used]
    visible[chosen_type] = remaining[0] if remaining else None

    return chosen, method, chosen_type


def _simulate_phase_b(
    all_intentions: list[IntentionCard],
    player_hands: dict[int, list[PhysicalCard]],
    n_players: int,
) -> dict:
    """
    Phase B — Tri + Intentions.

    Each player places their 9 cards face-down one by one (simulated as a random
    ordering). After every 3 cards placed, the player picks 1 intention card.
    Milestone triggers: after card 3 → intention 1, card 6 → intention 2, card 9 → intention 3.
    Players pick in turn order (player who hits milestone first picks first).
    """
    piles: dict[str, list[IntentionCard]] = {
        t: [c for c in all_intentions if c.type == t]
        for t in INTENTION_TYPES
    }
    for pile in piles.values():
        random.shuffle(pile)

    visible: dict[str, IntentionCard | None] = {
        t: piles[t][0] if piles[t] else None for t in INTENTION_TYPES
    }
    used: set[int] = set()

    # For each player: shuffled card order (the "tri") + milestones at 3, 6, 9
    player_card_order: dict[int, list[PhysicalCard]] = {}
    for idx, hand in player_hands.items():
        shuffled = list(hand)
        random.shuffle(shuffled)
        player_card_order[idx] = shuffled

    player_intentions: dict[int, list[IntentionCard]] = {p + 1: [] for p in range(n_players)}
    tri_log: list[dict] = []  # chronological log of all events

    # Simulate step by step (step = one card placed face-down by any player)
    # At milestones 3, 6, 9 a player picks an intention.
    # We process milestone pickings in player order when they occur simultaneously.
    cards_placed = {p + 1: 0 for p in range(n_players)}
    MILESTONES = {3, 6, 9}

    for step in range(1, 10):  # steps 1–9 (cards placed per player)
        # All players place card #step simultaneously
        for player_idx in range(n_players):
            player_num = player_idx + 1
            card = player_card_order[player_idx][step - 1]
            cards_placed[player_num] += 1
            tri_log.append({
                "event": "carte",
                "player": player_num,
                "n_placed": cards_placed[player_num],
                "card": card_label(card),
            })

        # Check milestone: if step is a milestone, each player picks an intention.
        # Order is randomized — it's a speed race, not turn-based.
        if step in MILESTONES:
            player_order = list(range(n_players))
            random.shuffle(player_order)
            for player_idx in player_order:
                player_num = player_idx + 1
                chosen, method, itype = _pick_intention(
                    piles, visible, used, player_num, player_intentions[player_num]
                )
                player_intentions[player_num].append(chosen)
                tri_log.append({
                    "event": "intention",
                    "player": player_num,
                    "milestone": step,
                    "method": method,
                    "type": itype,
                    "chosen": f"#{chosen.card_id} {chosen.title} ({chosen.type}, {chosen.points}pts)",
                })

    # 3 shared intentions (1 per type, first available)
    shared: list[IntentionCard] = []
    for t in INTENTION_TYPES:
        remaining = [c for c in piles[t] if c.card_id not in used]
        if remaining:
            shared.append(remaining[0])
            used.add(remaining[0].card_id)

    return {
        "tri_log": tri_log,
        "player_intentions": {
            p: [f"#{c.card_id} {c.title} ({c.points}pts)" for c in cards]
            for p, cards in player_intentions.items()
        },
        "shared_intentions": [f"#{c.card_id} {c.title} ({c.points}pts)" for c in shared],
        "_player_intentions_raw": player_intentions,
        "_shared_raw": shared,
    }


# ── Full game ─────────────────────────────────────────────────────────────────

def simulate_game_detailed(
    n_players: int = 2,
    strategy: Literal["random", "greedy"] = "greedy",
    seed: int | None = None,
) -> dict:
    if seed is not None:
        random.seed(seed)

    all_cards = load_plan_cards()
    all_intentions = load_intention_cards()

    # Phase A — Dérushage
    phase_a = _simulate_phase_a(all_cards, n_players)
    player_hands = phase_a["_hands_raw"]

    # Phase B — Tri + Intentions
    phase_b = _simulate_phase_b(all_intentions, player_hands, n_players)
    player_intentions_raw = phase_b["_player_intentions_raw"]
    shared_raw = phase_b["_shared_raw"]

    # Phase C — Montage
    # Simulate placement speed: each card placement takes a random time (uniform).
    # The player with the lowest total time finishes first and earns +5 pts.
    SPEED_BONUS = 5
    phase_c_players = []
    phase_d_players = []

    player_results = []
    for player_idx in range(n_players):
        hand = player_hands[player_idx]
        personal = player_intentions_raw[player_idx + 1]

        if strategy == "greedy":
            banc, placement_log = _greedy_place(hand)
        else:
            banc, placement_log = _random_place(hand)

        # Simulate placement time: random duration per card (greedy = slightly slower)
        base_time = 1.2 if strategy == "greedy" else 1.0
        total_time = sum(random.uniform(0.5, base_time) for _ in hand)

        plan_score = score_banc(banc)
        intention_score = score_intentions(personal, shared_raw, banc)

        player_results.append({
            "player_idx": player_idx,
            "player": player_idx + 1,
            "banc": banc,
            "placement_log": placement_log,
            "plan_score": plan_score,
            "intention_score": intention_score,
            "total_time": total_time,
            "n_visible": len([p for p in banc.visible_plans if not p.face_down]),
        })

    # Award speed bonus to fastest player
    fastest = min(player_results, key=lambda r: r["total_time"])
    for r in player_results:
        speed_bonus = SPEED_BONUS if r["player"] == fastest["player"] else 0
        total = r["plan_score"]["total"] + r["intention_score"]["total"] + speed_bonus

        phase_c_players.append({
            "player": r["player"],
            "placement_log": r["placement_log"],
            "n_visible": r["n_visible"],
            "total_time": round(r["total_time"], 2),
            "speed_bonus": speed_bonus,
            "first_to_finish": r["player"] == fastest["player"],
        })

        phase_d_players.append({
            "player": r["player"],
            "plan_score": r["plan_score"],
            "intention_score": r["intention_score"],
            "speed_bonus": speed_bonus,
            "total": total,
            "banc": r["banc"],
        })

    return {
        "n_players": n_players,
        "strategy": strategy,
        "phase_a": phase_a,
        "phase_b": phase_b,
        "phase_c": {"players": phase_c_players},
        "phase_d": {"players": phase_d_players},
    }


# ── Backward-compatible wrappers ──────────────────────────────────────────────

def simulate_game(
    n_players: int = 2,
    strategy: Literal["random", "greedy"] = "greedy",
    seed: int | None = None,
) -> list[dict]:
    log = simulate_game_detailed(n_players=n_players, strategy=strategy, seed=seed)
    return [
        {
            "player": r["player"],
            "strategy": strategy,
            "banc": r["banc"],
            "plan_score": r["plan_score"],
            "intention_score": r["intention_score"],
            "total": r["total"],
            "n_visible_plans": log["phase_c"]["players"][r["player"] - 1]["n_visible"],
            "personal_intentions": log["phase_b"]["_player_intentions_raw"][r["player"]],
            "shared_intentions": log["phase_b"]["_shared_raw"],
        }
        for r in log["phase_d"]["players"]
    ]


def run_simulation(
    n_games: int = 1000,
    n_players: int = 2,
    strategy: Literal["random", "greedy"] = "greedy",
) -> list[dict]:
    records = []
    for game_idx in range(n_games):
        log = simulate_game_detailed(n_players=n_players, strategy=strategy)
        for r in log["phase_d"]["players"]:
            pc = log["phase_c"]["players"][r["player"] - 1]
            records.append({
                "game": game_idx,
                "player": r["player"],
                "strategy": strategy,
                "total": r["total"],
                "plan_total": r["plan_score"]["total"],
                "intention_total": r["intention_score"]["total"],
                "speed_bonus": r["speed_bonus"],
                "first_to_finish": pc["first_to_finish"],
                "n_visible_plans": pc["n_visible"],
                "intentions_succeeded": sum(
                    1 for it in r["intention_score"]["intentions"] if it["success"]
                ),
                "intentions_attempted": len(r["intention_score"]["intentions"]),
            })
    return records
