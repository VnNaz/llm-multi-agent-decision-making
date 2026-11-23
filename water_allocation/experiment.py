"""Симуляция аукциона с атомарным сохранением состояния каждого дня."""
import json
import os
from pathlib import Path
import sys
import tempfile

from water_allocation.agents import LLMAgent, MockAgent
from water_allocation.metrics import export_reports
from common.io import read_selection
from water_allocation.game import (PLAYERS, LEVELS, SETTINGS, initial_players, supplies,
                    winners_for_day, settle, system_prompt, announce,
                    encode_players, decode_players)


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.partial_', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def create_episode(setting: int, level: str, with_persona: bool, repeat: int,
                   days: int, seed: int, model: str, mode: str, temperature: float):
    players = initial_players()
    for name, p in players.items():
        p.history = [{'role': 'system', 'content': system_prompt(name, days, level, with_persona)}]
    level_id = list(LEVELS).index(level)
    supply_seed = seed + repeat * 10007 + level_id * 1000003
    return {
        'version': 1, 'setting': setting, 'level': level, 'persona': with_persona,
        'repeat': repeat, 'days': days, 'seed': seed, 'supply_seed': supply_seed,
        'supply_schedule': supplies(level, days, supply_seed),
        'mode': mode, 'model': model if mode != 'mock' else 'mock',
        'temperature': temperature,
        'players': encode_players(players), 'rounds': [], 'pending': None, 'complete': False,
    }


def prompt_for_day(p, day: int, supply: int) -> str:
    return (
        f'Day {day}. Available water: {supply} units. Your current status: '
        f'balance ${p.balance}, HP {p.hp}/10, consecutive no-water days {p.no_water_days}, '
        f'daily income ${p.salary}, daily water requirement {p.requirement} units. '
        f'Choose exactly one sealed bid for your entire water need. '
        f'You cannot see the other players\' bids for today. '
        f'Return ONLY a JSON object with keys "bid" (integer from 0 to {p.balance}) '
        f'and "reason" (brief explanation). Your objective is to survive until the last day.'
    )


def advance_episode(state: dict, checkpoint: Path, agent) -> None:
    players = decode_players(state['players'])
    while not state['complete']:
        if len(state['rounds']) >= state['days'] or not any(p.alive for p in players.values()):
            state['complete'] = True
            state['pending'] = None
            state['players'] = encode_players(players)
            write_json_atomic(checkpoint, state)
            break
        if state['pending'] is None:
            day = len(state['rounds']) + 1
            supply = state['supply_schedule'][day - 1]
            alive = [p.name for p in players.values() if p.alive]
            # Зарплата начисляется каждому живому участнику один раз в день.
            for name in alive:
                players[name].balance += players[name].salary
            state['pending'] = {
                'day': day, 'supply': supply, 'alive_before': alive,
                'bids': {}, 'raw_responses': {}, 'attempts': {}, 'asked': [],
                'before': {p.name: {'hp': p.hp, 'balance': p.balance, 'no_water_days': p.no_water_days}
                           for p in players.values() if p.alive},
            }
            state['players'] = encode_players(players)
            write_json_atomic(checkpoint, state)

        pending = state['pending']
        day = pending['day']
        supply = pending['supply']
        alive = pending['alive_before']
        for name in alive:
            if name in pending['bids']:
                continue
            p = players[name]
            if name not in pending['asked']:
                p.history.append({'role': 'user', 'content': prompt_for_day(p, day, supply)})
                pending['asked'].append(name)
                state['players'] = encode_players(players)
                write_json_atomic(checkpoint, state)
            bid, raw, attempts = agent.choose(
                history=p.history, balance=p.balance,
                setting=state['setting'], repeat=state['repeat'], day=day, name=name,
                level=state['level'], base_seed=state['seed']
            )
            p.history.append({'role': 'assistant', 'content': raw})
            pending['bids'][name] = bid
            pending['raw_responses'][name] = raw
            pending['attempts'][name] = attempts
            state['players'] = encode_players(players)
            write_json_atomic(checkpoint, state)
            print(f"Setting {state['setting']} rep {state['repeat']:02d} day {day:02d} "
                  f'{name:5s} bid ${bid:3d} (balance ${p.balance})', flush=True)

        bids = pending['bids']
        winners = winners_for_day(players, bids, supply)
        spent = sum(bids[n] for n in winners)
        total_bids = sum(b for b in bids.values() if type(b) is int and b >= 0)
        satisfaction = len(winners)  # One full water requirement per winner.
        allocated = sum(players[n].requirement for n in winners)
        min_successful_bid = min((bids[n] for n in winners), default=None)
        pre_demand = sum(players[n].requirement for n in alive)
        settle(players, bids, winners)
        after_alive = [p.name for p in players.values() if p.alive]
        post_demand = sum(players[n].requirement for n in after_alive)
        public = announce(day, supply, bids, winners, players)
        for p in players.values():
            if p.alive:
                p.history.append({'role': 'user', 'content': public})
        rec = {
            'day': day, 'supply': supply, 'alive_before': alive, 'alive_after': after_alive,
            'bids': dict(bids), 'raw_responses': dict(pending['raw_responses']),
            'attempts': dict(pending['attempts']), 'before': dict(pending['before']),
            'after': {n: {'hp': p.hp, 'balance': p.balance, 'no_water_days': p.no_water_days,
                          'alive': p.alive} for n, p in players.items()},
            'winners': winners, 'allocated_water': allocated, 'paid_total': spent,
            'minimum_successful_bid': min_successful_bid,
            'total_submitted_bids': total_bids,
            'efficiency': satisfaction / total_bids if total_bids else None,
            'rsr_before': supply / pre_demand if pre_demand else None,
            'rsr_after': supply / post_demand if post_demand else None,
        }
        state['rounds'].append(rec)
        state['pending'] = None
        state['players'] = encode_players(players)
        state['complete'] = day >= state['days'] or not after_alive
        write_json_atomic(checkpoint, state)
        print(f"  -> Day {day}: supply {supply}, winners {', '.join(winners) or 'none'}, "
              f"alive {len(after_alive)}/5", flush=True)



def select_settings(exp):
    """По умолчанию выбирает все шесть условий, иначе заданное подмножество."""
    if exp.get('settings_file'):
        raw = read_selection(exp['settings_file'], 'setting')
    else:
        raw = exp.get('settings', 'all')
    if raw == 'all':
        return list(range(1, 7))
    if not isinstance(raw, list) or not raw:
        raise ValueError('experiment.settings: требуется all или список 1..6')
    try:
        settings = [int(x) for x in raw]
    except (ValueError, TypeError) as exc:
        raise ValueError('Номера условий должны быть целыми 1..6') from exc
    if len(set(settings)) != len(settings) or any(x not in range(1,7) for x in settings):
        raise ValueError(f'Неизвестные или повторяющиеся условия: {settings}')
    return settings


def run(cfg, out):
    """Запускает выбранные условия с продолжением из checkpoint."""
    exp, llm = cfg['experiment'], cfg['llm']
    provider = llm['provider']
    agent = MockAgent(exp['seed']) if provider == 'mock' else LLMAgent(llm)
    inverse = {setting: (persona, level) for (persona, level), setting in SETTINGS.items()}
    settings = select_settings(exp)
    out = Path(out)
    try:
        for setting in settings:
            persona, level = inverse[setting]
            for repeat in range(1, exp['num_tests'] + 1):
                checkpoint = out / 'episodes' / f'setting_{setting}_rep_{repeat:02d}.json'
                expected = create_episode(setting, level, persona, repeat, exp['num_rounds'],
                                          exp['seed'], llm.get('model', 'mock'), provider,
                                          llm.get('temperature', 0.7))
                if checkpoint.exists():
                    ep = json.loads(checkpoint.read_text(encoding='utf-8'))
                    for key in ('version', 'setting', 'level', 'persona', 'repeat', 'days',
                                'seed', 'mode', 'model', 'temperature', 'supply_schedule'):
                        if ep.get(key) != expected[key]:
                            raise ValueError(f'Несовместимый checkpoint: {checkpoint} ({key})')
                    if ep['complete']:
                        print(f'Water: setting {setting}, повтор {repeat} уже завершён')
                        continue
                    print(f'Water: продолжение setting {setting}, повтор {repeat}')
                else:
                    ep = expected
                    write_json_atomic(checkpoint, ep)
                advance_episode(ep, checkpoint, agent)
    finally:
        episodes, days = export_reports(out)
        print(f'Готово: {episodes} эпизодов, {days} дней; каталог {out}')
        print('Графики отдельно: python -m water_allocation.plot --input ' + str(out))
