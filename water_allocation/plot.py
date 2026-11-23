"""Строит графики Water Allocation по сохранённым CSV (matplotlib)."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_csv(path):
    if not path.exists():
        raise SystemExit(f'Missing {path}. Run experiments first.')
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def draw(out: Path):
    import matplotlib.pyplot as plt
    episodes = read_csv(out / 'episodes.csv')
    rounds = read_csv(out / 'rounds.csv')
    if not episodes:
        raise SystemExit('No completed episodes in episodes.csv. Finish at least one run.')
    figures = out / 'figures'
    figures.mkdir(exist_ok=True)
    all_settings = sorted({int(e['setting']) for e in episodes})
    names = ('Alex', 'Bob', 'Cindy', 'David', 'Eric')
    # График 1: доля выживаний каждого участника в каждом условии.
    fig, ax = plt.subplots(figsize=(11, 5.5))
    width = 0.15
    for i, name in enumerate(names):
        ys=[]
        for setting in all_settings:
            sub=[e for e in episodes if int(e['setting']) == setting]
            ys.append(sum(int(e['survived_'+name]) for e in sub)/len(sub))
        ax.bar([x+(i-2)*width for x in all_settings], ys, width=width, label=name)
    ax.set_xticks(all_settings, [str(s) for s in all_settings])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel('Survival rate')
    ax.set_xlabel('Setting (1-3 without persona, 4-6 with persona)')
    ax.set_title('ALYMPICS - Survival rate by player and setting')
    ax.legend(ncol=5, loc='upper center')
    fig.tight_layout()
    fig.savefig(figures/'survival_by_player.png', dpi=160)
    plt.close(fig)

    # График 2: динамика минимальной успешной ставки.
    series = defaultdict(list)
    for r in rounds:
        if r['minimum_successful_bid'] != '':
            series[(int(r['setting']), int(r['day']))].append(float(r['minimum_successful_bid']))
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for setting in all_settings:
        points=sorted((day, sum(vals)/len(vals)) for (s,day),vals in series.items() if s==setting)
        if points:
            ax.plot([p[0] for p in points], [p[1] for p in points], marker='o',
                    markersize=3, label=f'Setting {setting}')
    ax.set_xlabel('Day')
    ax.set_ylabel('Mean of minimum successful bid ($)')
    ax.set_title('ALYMPICS - Bidding price trend')
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figures/'minimum_successful_bid.png', dpi=160)
    plt.close(fig)

    # График 3: среднее число выживших (отдельная шкала измерений).
    fig, ax = plt.subplots(figsize=(9, 5))
    values=[]
    for setting in all_settings:
        sub=[e for e in episodes if int(e['setting'])==setting]
        values.append(sum(int(e['survivor_count']) for e in sub)/len(sub))
    ax.bar(all_settings,values)
    ax.set_xticks(all_settings)
    ax.set_ylim(0,5.2)
    ax.set_xlabel('Setting')
    ax.set_ylabel('Average number of survivors')
    ax.set_title('ALYMPICS - Survivors after the game')
    fig.tight_layout()
    fig.savefig(figures/'survivors_by_setting.png', dpi=160)
    plt.close(fig)

    print(f'Saved figures to {figures.resolve()}')
    for p in sorted(figures.glob('*.png')):
        print('  ', p.name)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', required=True, type=Path, help='Directory containing episodes.csv and rounds.csv')
    draw(ap.parse_args().input)
