"""
Game simulator for EDIT.

Simplifications vs full rules:
- Phase A (Dérushage): players draft cards into chutiers randomly.
- Phase D (Montage): greedy or random placement of all 9 cards.
- COMBO cards: player chooses orientation and whether to hide one plan.
- Face-down (Plan Noir) cards: placed randomly with configurable probability.
"""
from __future__ import annotations
import random
import copy
from typing import Literal

from .models import (
    PhysicalCard, Plan, PlacedCard, BancDeMontage, IntentionCard
)
from .scoring import score_banc
from .intentions import score_intentions
from .loader import load_plan_cards, load_intention_cards


PLAN_LARGE_COUNT = 12  # cards 1-12 used as chutier seed cards
DRAW_SIZES = {2: 19, 3: 28, 4: 37}


def _all_plan_large(cards: list[PhysicalCard]) -> list[PhysicalCard]:
    return [c for c in cards if c.physical_type == "PLAN_LARGE"]


def _non_plan_large(cards: list[PhysicalCard]) -> list[PhysicalCard]:
    return [c for c in cards if c.physical_type != "PLAN_LARGE"]


def _make_placement_options(card: PhysicalCard) -> list[list[Plan]]:
    """Return all possible visible_plans configurations for a physical card."""
    if card.physical_type == "PLAN_LARGE":
        return [list(card.plans)]
    # COMBO: A+B, B+A, A only (face down B), B only (face down A)
    a, b = card.plans[0], card.plans[1]

    b_down = copy.copy(b)
    b_down.face_down = True
    a_down = copy.copy(a)
    a_down.face_down = True

    return [
        [a, b],           # A left, B right
        [b, a],           # B left, A right
        [a, b_down],      # show A, B face down
        [b, a_down],      # show B, A face down
        [a_down, b],      # A face down, show B
        [b_down, a],      # B face down, show A
    ]


def _greedy_place(hand: list[PhysicalCard], intentions: list[IntentionCard]) -> BancDeMontage:
    """Place cards one by one, picking the option that maximises current score."""
    banc = BancDeMontage()
    remaining = list(hand)

    while remaining:
        best_card = None
        best_option = None
        best_score = -1

        random.shuffle(remaining)  # shuffle to break ties randomly
        for card in remaining:
            for option in _make_placement_options(card):
                trial = BancDeMontage(
                    placed_cards=banc.placed_cards + [PlacedCard(card, option)]
                )
                s = score_banc(trial)["total"]
                if s > best_score:
                    best_score = s
                    best_card = card
                    best_option = option

        banc.placed_cards.append(PlacedCard(best_card, best_option))
        remaining.remove(best_card)

    return banc


def _random_place(hand: list[PhysicalCard]) -> BancDeMontage:
    """Place cards in random order with random orientation."""
    banc = BancDeMontage()
    shuffled = list(hand)
    random.shuffle(shuffled)

    for card in shuffled:
        options = _make_placement_options(card)
        chosen = random.choice(options)
        banc.placed_cards.append(PlacedCard(card, chosen))

    return banc


def simulate_game(
    n_players: int = 2,
    strategy: Literal["random", "greedy"] = "greedy",
    seed: int | None = None,
) -> list[dict]:
    if seed is not None:
        random.seed(seed)

    all_cards = load_plan_cards()
    all_intentions = load_intention_cards()

    plan_large = _all_plan_large(all_cards)
    combo_cards = _non_plan_large(all_cards)

    # --- Phase A: build chutiers ---
    # Each player contributes 2 cards per round × 4 rounds = 8 cards
    # plus the initial Plan Large placed between players = 1 per chutier
    # Simplification: deal 9 cards randomly per chutier from the main deck
    deck_size = DRAW_SIZES[n_players]
    deck = plan_large + combo_cards
    random.shuffle(deck)
    draw_deck = deck[:deck_size]
    random.shuffle(draw_deck)

    # Distribute 9 cards per player
    player_hands = []
    for i in range(n_players):
        hand = draw_deck[i * 9: (i + 1) * 9]
        player_hands.append(hand)

    # --- Phase C: deal intentions ---
    intention_piles = {
        "THEMATIQUE": [c for c in all_intentions if c.type == "THEMATIQUE"],
        "NARRATIVE": [c for c in all_intentions if c.type == "NARRATIVE"],
        "TECHNIQUE": [c for c in all_intentions if c.type == "TECHNIQUE"],
    }
    for pile in intention_piles.values():
        random.shuffle(pile)

    player_intentions = []
    shared_intentions = []
    used_intention_ids = set()

    for _ in range(n_players):
        personal = []
        for pile in intention_piles.values():
            for card in pile:
                if card.card_id not in used_intention_ids:
                    personal.append(card)
                    used_intention_ids.add(card.card_id)
                    break
        player_intentions.append(personal)

    for pile in intention_piles.values():
        for card in pile:
            if card.card_id not in used_intention_ids:
                shared_intentions.append(card)
                used_intention_ids.add(card.card_id)
                break

    # --- Phase D+E: montage + scoring ---
    results = []
    for i in range(n_players):
        hand = player_hands[i]
        personal = player_intentions[i]

        if strategy == "greedy":
            banc = _greedy_place(hand, personal + shared_intentions)
        else:
            banc = _random_place(hand)

        plan_score = score_banc(banc)
        intention_score = score_intentions(personal, shared_intentions, banc)
        total = plan_score["total"] + intention_score["total"]

        results.append({
            "player": i + 1,
            "strategy": strategy,
            "banc": banc,
            "plan_score": plan_score,
            "intention_score": intention_score,
            "total": total,
            "n_visible_plans": len(banc.visible_plans),
            "personal_intentions": personal,
            "shared_intentions": shared_intentions,
        })

    return results


def run_simulation(
    n_games: int = 1000,
    n_players: int = 2,
    strategy: Literal["random", "greedy"] = "greedy",
) -> list[dict]:
    """Run multiple games and return flat stat records."""
    records = []
    for game_idx in range(n_games):
        game_results = simulate_game(n_players=n_players, strategy=strategy)
        for r in game_results:
            records.append({
                "game": game_idx,
                "player": r["player"],
                "strategy": r["strategy"],
                "total": r["total"],
                "plan_total": r["plan_score"]["total"],
                "intention_total": r["intention_score"]["total"],
                "n_visible_plans": r["n_visible_plans"],
                "intentions_succeeded": sum(
                    1 for it in r["intention_score"]["intentions"] if it["success"]
                ),
                "intentions_attempted": len(r["intention_score"]["intentions"]),
            })
    return records
