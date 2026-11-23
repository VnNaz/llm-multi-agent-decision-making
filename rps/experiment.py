"""Сценарии Fan (2024), независимый RPS без тяжёлой среды SmartPlay."""
import csv
import hashlib
import json
import random
import time
from pathlib import Path

from common.io import read_selection
from common.llm import LLMClient
from rps.game import (MOVES, SCENARIOS, SCENARIO_BY_NAME, choose_opponent_move,
                      payoff, outcome, parse_move, trial_seed)

FIELDS = ('player', 'model', 'scenario', 'family', 'repetition', 'round', 'seed',
          'player_move', 'opponent_move', 'result', 'payoff', 'model_response')


def select_scenarios(exp):
    """Выбирает все 12 сценариев или подмножество из YAML/CSV/JSON."""
    if exp.get('scenarios_file'):
        names = read_selection(exp['scenarios_file'], 'scenario')
    else:
        names = exp.get('scenarios', 'all')
        if names == 'all':
            return list(SCENARIOS)
    if isinstance(names, str):
        names = [s.strip() for s in names.split(',')]
    if not isinstance(names, list) or not names:
        raise ValueError('Список сценариев RPS пуст')
    if len(names) != len(set(names)) or any(x not in SCENARIO_BY_NAME for x in names):
        raise ValueError(f'Список содержит повтор или неизвестный RPS-сценарий: {names}')
    return [SCENARIO_BY_NAME[name] for name in names]


def build_messages(history):
    """Не раскрывает модели идентификатор сценария соперника."""
    rules = (
        'You are playing repeated Rock-Paper-Scissors against the same opponent. '
        'Rock beats Scissor, Scissor beats Paper, Paper beats Rock. '
        'You receive 2 points for a win, 1 for a draw, 0 for a loss. '
        'Both sides choose simultaneously. Your goal is to maximize expected points. '
        'You are not told the opponent\'s strategy. '
        'Respond ONLY with one JSON object: {"move":"Rock"}, '
        '{"move":"Paper"}, or {"move":"Scissor"}. '
        'Do not include explanations, reasoning, Markdown, or any text '
        'before or after the JSON object. '
        'Return exactly one JSON object on a single line.'
    )
    if not history:
        past = 'No earlier rounds have been played.'
    else:
        past = '\n'.join(
            f'Round {i}: you={MOVES[own]}, opponent={MOVES[opp]}, '
            f'points={payoff(own, opp)}'
            for i, (own, opp) in enumerate(history, 1)
        )
    return [{'role': 'system', 'content': rules},
            {'role': 'user', 'content': f'Completed rounds:\n{past}\n\nChoose your action for round {len(history)+1}.'}]


def choose_model_move(client, history, retries, seed):
    error = None
    for trial in range(1, retries + 2):
        try:
            raw = client.chat(build_messages(history), seed=seed)
            try:
                return parse_move(raw), raw
            except (ValueError, TypeError):
                # Вывод ответа модели при ошибке разбора JSON
                print(f"Некорректный ответ LLM: {raw[:500]!r}")
                raise
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            error = exc
            if trial <= retries:
                time.sleep(min(trial, 2))
    raise RuntimeError(f'LLM не вернула допустимый ход: {error}') from error


def load_saved(path):
    saved = {}
    if path.exists():
        with path.open(encoding='utf-8-sig', newline='') as f:
            for record in csv.DictReader(f):
                key = (record['scenario'], int(record['repetition']), int(record['round']))
                if key in saved:
                    raise ValueError(f'Повтор записи {key}')
                saved[key] = record
    return saved


def run(cfg, output):
    exp, llm = cfg['experiment'], cfg['llm']
    provider = llm['provider']
    scenarios = select_scenarios(exp)
    client = None if provider == 'random' else LLMClient(llm)
    model = 'not_used' if provider == 'random' else llm['model']
    csv_path = Path(output) / 'rounds.csv'
    saved = load_saved(csv_path)
    valid = {(s.name, test, rnd) for s in scenarios
             for test in range(1, exp['num_tests']+1)
             for rnd in range(1, exp['num_rounds']+1)}
    if set(saved) - valid:
        raise ValueError('В сохранённом CSV есть строки вне выбранной конфигурации')
    for scenario in scenarios:
        for repetition in range(1, exp['num_tests'] + 1):
            seed = trial_seed(exp['seed'], scenario.name, repetition)
            opponent_rng = random.Random(seed)
            player_rng = random.Random(seed ^ 0xBEEFFACE)
            history = []
            for rnd in range(1, exp['num_rounds'] + 1):
                key = (scenario.name, repetition, rnd)
                row = saved.get(key)
                if row is not None:
                    if (row['player'] != provider or row['model'] != model or row['seed'] != str(seed)):
                        raise ValueError(f'Несовместимый checkpoint: {key}')
                    action = parse_move(json.dumps({'move': row['player_move']}))
                    if provider == 'random' and action != player_rng.randrange(3):
                        raise ValueError(f'Нарушен порядок генератора Random: {key}')
                elif provider == 'random':
                    action, raw = player_rng.randrange(3), ''
                else:
                    # Семя опроса модели фиксируется отдельно от семени сценария.
                    digest = hashlib.sha256(f'{seed}:{rnd}'.encode()).digest()
                    action, raw = choose_model_move(client, history, llm.get('retries', 1),
                                                    int.from_bytes(digest[:4], 'big') & 0x7fffffff)
                opposite = choose_opponent_move(scenario, history, opponent_rng)
                score, result = payoff(action, opposite), outcome(action, opposite)
                if row is not None:
                    if (row['opponent_move'] != MOVES[opposite] or
                        row['payoff'] != str(score) or row['result'] != result):
                        raise ValueError(f'Сохранённая запись не воспроизводится: {key}')
                else:
                    new = {'player': provider, 'model': model, 'scenario': scenario.name,
                           'family': scenario.family, 'repetition': repetition, 'round': rnd,
                           'seed': seed, 'player_move': MOVES[action],
                           'opponent_move': MOVES[opposite], 'result': result,
                           'payoff': score, 'model_response': raw}
                    is_new = not csv_path.exists()
                    with csv_path.open('a', encoding='utf-8', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=FIELDS)
                        if is_new:
                            writer.writeheader()
                        writer.writerow(new)
                        file.flush()
                    saved[key] = {k: str(v) for k, v in new.items()}
                history.append((action, opposite))
            print(f'RPS: {scenario.name}, повтор {repetition}/{exp["num_tests"]}')
    print(f'Готово: {len(saved)} раундов, {csv_path}')
    print('Графики отдельно: python -m rps.plot --input ' + str(output))
