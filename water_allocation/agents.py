"""Агенты для аукциона: детерминированный Mock и внешний LLM."""
import hashlib
import json
import random
import re
import time

from common.llm import LLMClient



def parse_bid(text, balance):
    """Извлекает единственную JSON-ставку и проверяет её тип и бюджет."""
    import json
    import re

    decoder = json.JSONDecoder()
    source = text.strip()

    try:
        obj = json.loads(source)
    except json.JSONDecodeError:
        # Поиск JSON-объекта внутри текстового ответа модели.
        candidates = []

        for match in re.finditer(r'\{', source):
            try:
                value, _ = decoder.raw_decode(source[match.start():])
            except json.JSONDecodeError:
                continue

            if isinstance(value, dict) and 'bid' in value:
                candidates.append(value)

        if len(candidates) != 1:
            raise ValueError(
                'Ожидается один JSON-объект с целым числом bid'
            )

        obj = candidates[0]

    if not isinstance(obj, dict) or type(obj.get('bid')) is not int:
        raise ValueError('В JSON ожидается целочисленное поле bid')

    bid = obj['bid']

    if not 0 <= bid <= balance:
        raise ValueError(f'Ставка {bid} вне диапазона [0, {balance}]')

    return bid



class MockAgent:
    """Детерминированные ставки для тестов, не исследовательская LLM-база."""
    def __init__(self, seed=2025):
        self.seed = seed

    def choose(self, history, balance, **kwargs):
        rng = random.Random(f'{self.seed}:{kwargs.get("setting")}:{kwargs.get("repeat")}:{kwargs.get("day")}:{kwargs.get("name")}')
        bid = rng.randint(0, min(balance, 120))
        return bid, json.dumps({'bid': bid, 'reason': 'mock'}), 1


class LLMAgent:
    """Использует общий клиент и повторяет запрос при некорректной ставке."""
    def __init__(self, llm_cfg):
        self.client = LLMClient(llm_cfg)
        self.retries = llm_cfg.get('retries', 2)

    def choose(self, history, balance, **kwargs):
        error = ''
        last_raw = None

        seed_key = (
            f"{kwargs.get('base_seed', 2025)}:"
            f"{kwargs.get('level', 'low')}:"
            f"{kwargs.get('repeat', 1)}:"
            f"{kwargs.get('day', 1)}:"
            f"{kwargs.get('name', 'agent')}"
        )
        seed = int.from_bytes(
            hashlib.sha256(seed_key.encode()).digest()[:4], 'big'
        ) & 0x7fffffff

        for trial in range(1, self.retries + 2):
            messages = list(history)

            if error:
                messages.append({
                    'role': 'user',
                    'content': (
                        'Your previous response was invalid. '
                        'Return ONLY JSON with integer '
                        f'"bid" between 0 and {balance}. '
                        f'Reason: {error[:200]}'
                    )
                })

            try:
                raw = self.client.chat(messages, seed=seed)

                # Сохраняем исходный ответ для диагностики.
                last_raw = raw

                return parse_bid(raw, balance), raw, trial

            except (RuntimeError, ValueError, TypeError) as exc:
                error = str(exc)

                if trial <= self.retries:
                    time.sleep(min(trial, 2))

        # Выводим ответ только после исчерпания всех попыток.
        tail = repr(last_raw[-1000:]) if last_raw is not None else 'Нет ответа'

        raise RuntimeError(
            f'Агент не смог создать корректную ставку после '
            f'{self.retries + 1} попыток: {error}; '
            f'последний ответ модели: {tail}'
        )

