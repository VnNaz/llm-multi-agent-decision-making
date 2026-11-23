"""Импорт JSON/CSV и сохранение файлов эксперимента."""
import csv
import json
from pathlib import Path


def load_records(path):
    """Возвращает записи из JSON (объект/массив) либо CSV (таблица)."""
    path = Path(path)
    if path.suffix.lower() == '.json':
        with path.open(encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, (dict, list)):
            raise ValueError('JSON должен содержать объект или массив')
        return data
    if path.suffix.lower() == '.csv':
        with path.open(newline='', encoding='utf-8-sig') as file:
            return list(csv.DictReader(file))
    raise ValueError('Формат входного файла должен быть JSON или CSV')


def read_selection(path, field):
    """Считывает список значений из CSV или JSON без ограничения размера списка."""
    data = load_records(path)
    if isinstance(data, dict):
        data = data.get(field, [])
    if not isinstance(data, list):
        raise ValueError(f'Ожидается массив значений: {field}')
    values = []
    for item in data:
        if isinstance(item, dict):
            if field not in item:
                raise ValueError(f'В записи отсутствует поле {field}')
            values.append(item[field])
        else:
            values.append(item)
    return values


def save_json(path, obj):
    """Создаёт каталог и записывает JSON в кодировке UTF-8."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
