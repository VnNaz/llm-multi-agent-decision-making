"""Проверка YAML и безопасная работа с переменными окружения."""
import copy
import os
from pathlib import Path

from common.io import save_json


def load_dotenv(path='.env'):
    """Читает локальный .env, не изменяя уже заданные переменные окружения."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name.isidentifier():
            os.environ.setdefault(name, value)


def load_config(path):
    """Возвращает проверенную конфигурацию выбранной игры."""
    import yaml
    config_path = Path(path).resolve()
    with config_path.open(encoding='utf-8') as file:
        cfg = yaml.safe_load(file)
    if not isinstance(cfg, dict) or not isinstance(cfg.get('experiment'), dict) or not isinstance(cfg.get('llm'), dict):
        raise ValueError('YAML: обязательны объекты experiment и llm')
    exp, llm = cfg['experiment'], cfg['llm']
    if exp.get('game') not in {'rps', 'water_allocation'}:
        raise ValueError('experiment.game должен быть rps или water_allocation')
    for key in ('num_rounds', 'num_tests'):
        value = exp.get(key)
        if type(value) is not int or value < 1:
            raise ValueError(f'experiment.{key} должен быть целым положительным')
    if type(exp.get('seed')) is not int:
        raise ValueError('experiment.seed должен быть целым числом')
    provider = llm.get('provider')
    allowed = {'ollama', 'openai', 'anthropic', 'random'} if exp['game'] == 'rps' else {'ollama', 'openai', 'anthropic', 'mock'}
    if provider not in allowed:
        raise ValueError(f'Недопустимый llm.provider={provider!r}; допустимы {sorted(allowed)}')
    if provider not in {'random', 'mock'} and not str(llm.get('model', '')).strip():
        raise ValueError('llm.model не указан')
    temp = llm.get('temperature', 0.7)
    if type(temp) not in (float, int) or not 0 <= temp <= (1 if provider == 'anthropic' else 2):
        raise ValueError('Температура выходит за диапазон провайдера')
    for key in ('timeout', 'max_tokens'):
        value = llm.get(key, 120 if key == 'timeout' else 256)
        if type(value) is not int or value < 1:
            raise ValueError(f'llm.{key} должен быть целым положительным')
    if type(llm.get('retries', 1)) is not int or llm.get('retries', 1) < 0:
        raise ValueError('llm.retries должен быть неотрицательным целым')
    for key in ('scenarios_file','settings_file'):
        if exp.get(key):
            supplied = Path(exp[key])
            # Относительные пути вычисляются от корня проекта (рабочего каталога).
            exp[key] = str(supplied.resolve())
    output = cfg.get('output', {})
    if not isinstance(output, dict) or not output.get('directory'):
        raise ValueError('output.directory обязателен')
    return cfg


def public_config(cfg):
    """Исключает секреты перед записью конфигурации в результаты."""
    cleaned = copy.deepcopy(cfg)
    for key in ('api_key', 'token', 'secret'):
        cleaned.get('llm', {}).pop(key, None)
    return cleaned


def reserve_output(cfg):
    """Проверяет совпадение настроек при продолжении уже начатого запуска."""
    import json
    folder = Path(cfg['output']['directory']).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'config.json'
    clean = public_config(cfg)
    if path.exists():
        prev = json.loads(path.read_text(encoding='utf-8'))

        if prev != clean:
            old = json.loads(json.dumps(prev))
            new = json.loads(json.dumps(clean))

            # Разрешаем изменение лимита токенов и числа повторных попыток.
            for config in (old, new):
                config.get('llm', {}).pop('max_tokens', None)
                config.get('llm', {}).pop('retries', None)

            if old != new:
                raise ValueError(
                    f'Каталог {folder} содержит результаты с другими настройками'
                )

            print('Изменены только max_tokens/retries. Продолжаем эксперимент.')
    else:
        save_json(path, clean)
    return folder
