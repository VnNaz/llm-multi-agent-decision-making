"""Логика Water Allocation по Mao et al. (COLING 2025).

Самостоятельная реализация правил, не дословная копия ALYMPICS.
"""
from dataclasses import dataclass, field, asdict
import random
from typing import Any

PLAYERS = {
    'Alex': (8, 70), 'Bob': (9, 75), 'Cindy': (10, 100),
    'David': (11, 120), 'Eric': (12, 120),
}
LEVELS = {'low': (10, 20), 'medium': (15, 25), 'high': (20, 30)}
SETTINGS = {
    (False, 'low'): 1, (False, 'medium'): 2, (False, 'high'): 3,
    (True, 'low'): 4, (True, 'medium'): 5, (True, 'high'): 6,
}

# Характеристики persona пересказаны по Figure 3; это не оригинальные промпты.
PERSONAS = {
    'Alex': ('Unemployed', 'Impulsive, struggles with complex reasoning and social cues.',
             'Grew up in poverty; left school early and has had difficulty finding stable work.'),
    'Bob': ('High school teacher', 'Empathetic and sociable with average analytical ability.',
            'Raised in a supportive family and became a teacher to help young people.'),
    'Cindy': ('Psychologist', 'Analytical, empathetic and highly skilled at understanding others.',
              'Volunteered in mental-health support and later qualified as a psychologist.'),
    'David': ('Mathematician', 'Very strong analytical reasoning but reserved and socially anxious.',
              'Earned a doctorate in mathematics and enjoys abstract problem solving.'),
    'Eric': ('Marketing executive', 'Persuasive, charismatic and good at reading people.',
             'Moved into marketing after business studies and has experience influencing audiences.'),
}


@dataclass
class Player:
    name: str
    requirement: int
    salary: int
    hp: int = 8
    balance: int = 0
    no_water_days: int = 0
    alive: bool = True
    history: list[dict[str, str]] = field(default_factory=list)


def initial_players() -> dict[str, Player]:
    return {name: Player(name, req, salary) for name, (req, salary) in PLAYERS.items()}


def supplies(level: str, days: int, seed: int) -> list[int]:
    """Детерминированная генерация объёма воды, правая граница не включена."""
    low, high = LEVELS[level]
    rng = random.Random(seed)
    return [rng.randrange(low, high) for _ in range(days)]


def winners_for_day(players: dict[str, Player], bids: dict[str, int | None], supply: int) -> list[str]:
    """Распределение по убыванию ставок; при равенстве первична меньшая потребность.

    Участник получает полный требуемый объём или ничего; остаток не перерасходуется.
    Недопустимые и превышающие бюджет ставки отбрасываются.
    """
    candidates = []
    for name, p in players.items():
        bid = bids.get(name)
        if p.alive and type(bid) is int and 0 <= bid <= p.balance:
            candidates.append((name, bid, p.requirement))
    candidates.sort(key=lambda it: (-it[1], it[2], it[0]))
    winners = []
    remaining = supply
    for name, bid, requirement in candidates:
        if requirement <= remaining:
            winners.append(name)
            remaining -= requirement
    assert remaining >= 0
    return winners


def settle(players: dict[str, Player], bids: dict[str, int | None], winners: list[str]):
    """Обновляет деньги и здоровье после окончания всех ставок.

    Зарплата уже начислена. При проигрыше теряется k единиц здоровья на
    k-м последовательном неудачном дне; победа восстанавливает 2 и сбрасывает k.
    При HP<=0 участник исключается, а его баланс обнуляется.
    """
    for p in players.values():
        if not p.alive:
            continue
        if p.name in winners:
            bid = bids[p.name]
            assert type(bid) is int and 0 <= bid <= p.balance
            p.balance -= bid
            p.hp = min(10, p.hp + 2)
            p.no_water_days = 0
        else:
            p.no_water_days += 1
            p.hp -= p.no_water_days
            if p.hp <= 0:
                p.alive = False
                p.hp = 0
                p.balance = 0


def get_game_rules(days: int, level: str) -> str:
    lo, hi = LEVELS[level]
    return (
        f'Water Allocation Challenge. Survive {days} days. Five players bid daily for water '
        'via sealed, simultaneous bids. Every player starts with 8 HP (maximum 10) and $0. '
        'Every day, surviving players receive salary BEFORE bidding. Each player bids once '
        'for their ENTIRE daily water requirement. Highest valid bids win first, if enough '
        'water remains; ties favor lower daily water requirements. You pay only if you win. '
        'Bids must be nonnegative whole numbers no greater than your balance. '
        'A win restores 2 HP up to 10 and resets consecutive days without water to zero. '
        'A loss removes k HP on the kth consecutive unsuccessful day; HP <= 0 eliminates a player. '
        'All players see everyone\'s bids and post-auction status after each day. '
        f'Water is randomly provided each day at {lo}..{hi - 1} inclusive units. '
        'Players: ' + ', '.join(f'{n} needs {r} water/day, earns ${s}/day' for n, (r, s) in PLAYERS.items()) + '.'
    )


def system_prompt(name: str, days: int, level: str, with_persona: bool) -> str:
    p = f'You are {name}, a resident of W-Town. Your objective is to survive.'
    if with_persona:
        profession, disposition, background = PERSONAS[name]
        p += f' Your profession: {profession}. Personality: {disposition} Background: {background}'
    return p + '\n' + get_game_rules(days, level)


def announce(day: int, supply: int, bids: dict[str, int | None],
             winners: list[str], players: dict[str, Player]) -> str:
    bids_text = ', '.join(f'{name}: ${bid if bid is not None else "INVALID"}' for name, bid in bids.items())
    status = '; '.join(f'{p.name}: balance ${p.balance}, HP {p.hp}, no-water days {p.no_water_days}, '
                       f'{"alive" if p.alive else "eliminated"}' for p in players.values())
    return (f'Day {day} public results. Supply {supply}. Submitted bids: {bids_text}. '
            f'Winners: {", ".join(winners) if winners else "none"}. '
            f'After allocation: {status}.')


def encode_players(players: dict[str, Player]) -> dict[str, Any]:
    return {n: asdict(p) for n, p in players.items()}


def decode_players(data: dict[str, Any]) -> dict[str, Player]:
    return {n: Player(**p) for n, p in data.items()}
