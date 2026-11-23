"""Единый HTTP-клиент Ollama, OpenAI и Anthropic без сторонних SDK."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMError(RuntimeError):
    """Ошибка обращения к LLM-провайдеру."""


class LLMClient:
    """Отправляет историю сообщений и возвращает текст модели."""

    URLS = {
        'ollama': 'http://127.0.0.1:11434',
        'openai': 'https://api.openai.com',
        'anthropic': 'https://api.anthropic.com',
    }

    # Схемы относятся только к Anthropic; для Ollama используется format=json.
    STRUCTURED_SCHEMAS = {
        'rps': {
            'type': 'object',
            'properties': {
                'move': {'type': 'string', 'enum': ['Rock', 'Paper', 'Scissor']},
            },
            'required': ['move'],
            'additionalProperties': False,
        },
        'water_allocation': {
            'type': 'object',
            'properties': {
                'bid': {'type': 'integer'},
                'reason': {'type': 'string'},
            },
            'required': ['bid', 'reason'],
            'additionalProperties': False,
        },
    }

    def __init__(self, config):
        self.provider = config['provider']
        if self.provider not in self.URLS:
            raise ValueError('Клиент работает только с llm.provider=ollama/openai/anthropic')
        self.model = config['model']
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 256)
        self.timeout = config.get('timeout', 120)
        self.url = (config.get('base_url') or self.URLS[self.provider]).rstrip('/')

        self.rps_structured_output = config.get('rps_structured_output', False)
        self.water_structured_output = config.get('water_structured_output', False)
        if self.rps_structured_output and self.water_structured_output:
            raise ValueError('Нельзя одновременно включать схемы RPS и Water Allocation')

        self.api_key = None
        if self.provider != 'ollama':
            env = config.get('api_key_env') or (
                'OPENAI_API_KEY' if self.provider == 'openai' else 'ANTHROPIC_API_KEY'
            )
            self.api_key = os.environ.get(env)
            if not self.api_key:
                raise LLMError(f'Переменная окружения {env} не установлена')

    def chat(self, messages, seed=None):
        """Отправляет сообщения, сохраняя протоколы трёх провайдеров."""
        headers = {'Content-Type': 'application/json'}

        if self.provider == 'ollama':
            url = self.url + '/api/chat'
            opts = {'temperature': self.temperature, 'num_predict': self.max_tokens}
            if seed is not None:
                opts['seed'] = seed
            payload = {
                'model': self.model,
                'stream': False,
                # 'think': False,
                'format': 'json',
                'messages': messages,
                'options': opts
            }

        elif self.provider == 'openai':
            url = self.url + '/v1/chat/completions'
            headers['Authorization'] = 'Bearer ' + self.api_key
            payload = {
                'model': self.model,
                'messages': messages,
                'temperature': self.temperature,
                'max_completion_tokens': self.max_tokens,
            }
            # Параметр seed не навязывается: поддержка зависит от модели.

        else:
            url = self.url + '/v1/messages'
            headers['x-api-key'] = self.api_key
            headers['anthropic-version'] = '2023-06-01'
            system = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
            other = []
            for msg in messages:
                if msg['role'] == 'system':
                    continue
                # Объединяем последовательные сообщения одной роли для Anthropic.
                if other and other[-1]['role'] == msg['role']:
                    other[-1]['content'] += '\n' + msg['content']
                else:
                    other.append({'role': msg['role'], 'content': msg['content']})

            payload = {
                'model': self.model,
                'system': system,
                'messages': other,
                'temperature': self.temperature,
                'max_tokens': self.max_tokens,
            }

            # Для каждого эксперимента используется собственная JSON-схема.
            schema = None
            if self.rps_structured_output:
                schema = self.STRUCTURED_SCHEMAS['rps']
            elif self.water_structured_output:
                schema = self.STRUCTURED_SCHEMAS['water_allocation']
            if schema is not None:
                payload['output_config'] = {
                    'format': {'type': 'json_schema', 'schema': schema}
                }

        request = Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)

            if self.provider == 'ollama':
                return data['message']['content']
            if self.provider == 'openai':
                return data['choices'][0]['message']['content']

            # Обрезанный ответ нельзя использовать для решения агента.
            if data.get('stop_reason') == 'max_tokens':
                raise LLMError('anthropic: ответ обрезан по лимиту токенов')
            if data.get('stop_reason') == 'refusal':
                raise LLMError('anthropic: модель отказалась отвечать')

            result = ''.join(
                block.get('text', '')
                for block in data['content']
                if block.get('type') == 'text'
            )
            if not result.strip():
                raise LLMError('anthropic: пустой текстовый ответ')
            return result

        except HTTPError as exc:
            # Тело ошибки не логируется: оно может содержать пользовательские данные.
            raise LLMError(f'{self.provider}: HTTP {exc.code}') from None
        except (URLError, TimeoutError, OSError, KeyError, ValueError, TypeError, IndexError) as exc:
            raise LLMError(
                f'{self.provider}: ошибка запроса или формата ответа '
                f'({type(exc).__name__})'
            ) from None
