"""Правила соперника и начисление очков по Fan et al. (AAAI 2024)."""
from dataclasses import dataclass
import hashlib
import random
from typing import Sequence

ROCK = 0
PAPER = 1
SCISSOR = 2
MOVES = ("Rock", "Paper", "Scissor")

# Ответный ход, побеждающий указанный: Paper побеждает Rock.
BEATS = {ROCK: PAPER, PAPER: SCISSOR, SCISSOR: ROCK}

@dataclass(frozen=True)
class Scenario:
    name: str
    family: str
    kind: str
    sequence: tuple[int, ...] = ()
    preferred: int | None = None

SCENARIOS = (
    Scenario("constant_rock", "constant", "sequence", (ROCK,)),
    Scenario("constant_scissor", "constant", "sequence", (SCISSOR,)),
    Scenario("constant_paper", "constant", "sequence", (PAPER,)),
    Scenario("loop2_rock_paper", "loop-2", "sequence", (ROCK, PAPER)),
    Scenario("loop2_paper_scissor", "loop-2", "sequence", (PAPER, SCISSOR)),
    Scenario("loop2_scissor_rock", "loop-2", "sequence", (SCISSOR, ROCK)),
    Scenario("loop3_rock_paper_scissor", "loop-3", "sequence", (ROCK, PAPER, SCISSOR)),
    Scenario("copy", "copy", "copy"),
    Scenario("counter", "counter", "counter"),
    Scenario("sample_rock", "sample", "sample", preferred=ROCK),
    Scenario("sample_scissor", "sample", "sample", preferred=SCISSOR),
    Scenario("sample_paper", "sample", "sample", preferred=PAPER),
)
SCENARIO_BY_NAME = {s.name: s for s in SCENARIOS}
FAMILY_ORDER = ("constant", "loop-2", "loop-3", "copy", "counter", "sample")


def trial_seed(base_seed: int, scenario: str, repetition: int) -> int:
    """Воспроизводимое семя независимо от запуска интерпретатора."""
    encoded = f"{base_seed}:{scenario}:{repetition}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def choose_opponent_move(
    scenario: Scenario, history: Sequence[tuple[int, int]], rng: random.Random
) -> int:
    """История включает только завершённые раунды (свой ход, чужой ход)."""
    turn = len(history)
    if scenario.kind == "sequence":
        return scenario.sequence[turn % len(scenario.sequence)]
    if scenario.kind in ("copy", "counter"):
        if not history:
            # В статье не определён начальный ход для стратегий copy/counter.
            # Для первого хода применяется равномерный генератор с фиксированным семенем.
            return rng.randrange(3)
        last_player_move = history[-1][0]
        return last_player_move if scenario.kind == "copy" else BEATS[last_player_move]
    if scenario.kind == "sample":
        # Два других хода получают вероятность по 0,15 каждый.
        # Предпочитаемый ход скрыт от LLM, доступна только история наблюдений.
        weights = [0.15, 0.15, 0.15]
        weights[scenario.preferred] = 0.70
        return rng.choices(range(3), weights=weights, k=1)[0]
    raise ValueError(f"Unknown policy: {scenario.kind}")


def payoff(player: int, opponent: int) -> int:
    """Победа — 2, ничья — 1, проигрыш — 0 очков."""
    if player == opponent:
        return 1
    return 2 if BEATS[opponent] == player else 0


def outcome(player: int, opponent: int) -> str:
    return ("loss", "draw", "win")[payoff(player, opponent)]



def parse_move(content: str) -> int:
    """Извлекает допустимый ход из JSON-ответа модели."""
    import json
    import re

    text = content.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Поиск JSON-объекта внутри текстового ответа
        candidates = []

        for match in re.finditer(r'\{[^{}]*\}', text):
            try:
                obj = json.loads(match.group())
                if isinstance(obj, dict) and "move" in obj:
                    candidates.append(obj)
            except json.JSONDecodeError:
                continue

        # Не допускаем неоднозначных ответов
        if len(candidates) != 1:
            raise ValueError(
                f"Не найден однозначный JSON-ход: {content[:200]!r}"
            )

        data = candidates[0]

    if not isinstance(data, dict) or not isinstance(data.get("move"), str):
        raise ValueError("Ожидается JSON-объект со строковым полем move")

    word = data["move"].strip().lower()

    if word == "scissors":
        word = "scissor"

    for idx, label in enumerate(MOVES):
        if label.lower() == word:
            return idx

    raise ValueError(f"Недопустимый ход RPS: {word!r}")

