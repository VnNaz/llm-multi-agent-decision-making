"""Экспорт метрик Water Allocation в табличный формат CSV."""
import csv
import json
import os
import tempfile
from pathlib import Path
from water_allocation.game import PLAYERS, LEVELS

def save_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Атомарная запись предотвращает повреждение CSV при прерывании процесса.
    fd, tmp = tempfile.mkstemp(prefix='.partial_', suffix='.csv', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def export_reports(out: Path) -> tuple[int, int]:
    episodes = []
    for path in sorted((out / 'episodes').glob('setting_*_rep_*.json')):
        with path.open(encoding='utf-8') as f:
            episodes.append(json.load(f))
    bids_rows, rounds_rows, episode_rows = [], [], []
    for ep in episodes:
        base = {k: ep[k] for k in ('setting', 'level', 'persona', 'repeat', 'model', 'seed')}
        for r in ep['rounds']:
            rounds_rows.append({**base, 'day': r['day'], 'supply': r['supply'],
                'alive_before': len(r['alive_before']), 'alive_after': len(r['alive_after']),
                'winner_names': ';'.join(r['winners']), 'allocated_water': r['allocated_water'],
                'total_paid': r['paid_total'], 'total_submitted_bids': r['total_submitted_bids'],
                'minimum_successful_bid': r['minimum_successful_bid'],
                'efficiency': r['efficiency'], 'rsr_before': r['rsr_before'],
                'rsr_after': r['rsr_after']})
            for name in r['alive_before']:
                before, after = r['before'][name], r['after'][name]
                bids_rows.append({**base, 'day': r['day'], 'supply': r['supply'],
                    'player': name, 'requirement': PLAYERS[name][0], 'salary': PLAYERS[name][1],
                    'bid': r['bids'][name], 'won': int(name in r['winners']),
                    'balance_before': before['balance'], 'balance_after': after['balance'],
                    'hp_before': before['hp'], 'hp_after': after['hp'],
                    'no_water_before': before['no_water_days'], 'no_water_after': after['no_water_days'],
                    'alive_after': int(after['alive']),
                    'attempts': r['attempts'][name],
                    'raw_response': r['raw_responses'][name]})
        if ep['complete']:
            alive = [n for n, p in ep['players'].items() if p['alive']]
            # Номинальные значения доступных ресурсов по уровням: 15/20/25.
            # Реальные средние при дискретном равномерном распределении: 14,5/19,5/24,5.
            nominal_supply = sum(LEVELS[ep['level']]) / 2
            start_rsr = nominal_supply / sum(r for r, _ in PLAYERS.values())
            final_demand = sum(PLAYERS[n][0] for n in alive)
            efficiencies = [r['efficiency'] for r in ep['rounds'] if r['efficiency'] is not None]
            winning_bids = [r['minimum_successful_bid'] for r in ep['rounds'] if r['minimum_successful_bid'] is not None]
            episode_rows.append({**base, 'days_completed': len(ep['rounds']),
                'survivor_count': len(alive), 'survival_fraction': len(alive) / len(PLAYERS),
                'survivors': ';'.join(alive),
                'rsr_start': start_rsr, 'rsr_end': nominal_supply / final_demand if final_demand else None,
                'mean_efficiency': sum(efficiencies) / len(efficiencies) if efficiencies else None,
                'mean_min_successful_bid': sum(winning_bids) / len(winning_bids) if winning_bids else None,
                **{f'survived_{n}': int(n in alive) for n in PLAYERS}})
    save_csv(out / 'bids.csv', ['setting', 'level', 'persona', 'repeat', 'model', 'seed', 'day',
              'supply', 'player', 'requirement', 'salary', 'bid', 'won', 'balance_before',
              'balance_after', 'hp_before', 'hp_after', 'no_water_before', 'no_water_after',
              'alive_after', 'attempts', 'raw_response'], bids_rows)
    save_csv(out / 'rounds.csv', ['setting', 'level', 'persona', 'repeat', 'model', 'seed', 'day',
              'supply', 'alive_before', 'alive_after', 'winner_names', 'allocated_water', 'total_paid',
              'total_submitted_bids', 'minimum_successful_bid', 'efficiency', 'rsr_before', 'rsr_after'], rounds_rows)
    save_csv(out / 'episodes.csv', ['setting', 'level', 'persona', 'repeat', 'model', 'seed',
              'days_completed', 'survivor_count', 'survival_fraction', 'survivors',
              'rsr_start', 'rsr_end', 'mean_efficiency', 'mean_min_successful_bid',
              *[f'survived_{n}' for n in PLAYERS]], episode_rows)
    survival_rows = []
    for setting in range(1, 7):
        subset = [e for e in episode_rows if e['setting'] == setting]
        if not subset:
            continue
        for name in PLAYERS:
            survival_rows.append({'setting': setting, 'level': subset[0]['level'],
                    'persona': subset[0]['persona'], 'player': name, 'completed_episodes': len(subset),
                    'survival_rate': sum(e[f'survived_{name}'] for e in subset) / len(subset)})
    save_csv(out / 'survival_rates.csv', ['setting', 'level', 'persona', 'player',
              'completed_episodes', 'survival_rate'], survival_rows)
    return len(episode_rows), len(rounds_rows)

