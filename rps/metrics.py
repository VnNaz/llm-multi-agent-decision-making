"""Расчёт показателей выигрыша RPS из файлов завершённых раундов."""
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean


def summarize(paths):
    """Возвращает средние выигрыши по стратегии и номеру раунда."""
    by_family_round = defaultdict(list)
    by_scenario = defaultdict(list)
    seen = set()
    for path in paths:
        with Path(path).open(newline='', encoding='utf-8-sig') as file:
            for row in csv.DictReader(file):
                label = 'Random' if row['player'] == 'random' else row['model']
                # Файлы отдельных запусков с той же моделью учитываются отдельно.
                key = (str(path), row['scenario'], row['repetition'], row['round'])
                if key in seen:
                    raise ValueError(f'Повтор раунда внутри файла {key}')
                seen.add(key)
                value = int(row['payoff'])
                by_family_round[(label, row['family'], int(row['round']))].append(value)
                by_scenario[(label, row['scenario'], row['family'])].append(value)
    if not seen:
        raise ValueError('В результатах отсутствуют раунды')
    return by_family_round, by_scenario
