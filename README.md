# LLM в задачах принятия решений: RPS и Water Allocation

Учебный проект по исследованию принятия решений большими языковыми моделями (LLM) в двух игровых средах:

- **Rock–Paper–Scissors (RPS)** — адаптация эксперимента по мотивам Fan et al. (2024): 12 стратегий противника, оценка результата каждого раунда по шкале 0/1/2.
- **Water Allocation** — адаптация эксперимента по мотивам Mao et al. (2025): аукцион воды между пятью агентами, шесть условий (три уровня доступности ресурса × наличие/отсутствие persona).

В экспериментах используются **Qwen2.5:7b**, **Qwen3.5:9b** (локально через Ollama) и **Claude Sonnet 4.6** (Anthropic API). Игры запускаются независимо друг от друга. 

## 1. Установка

Требуется **Python 3.10+**. Команды ниже выполняются из корневой директории проекта.

**Windows / PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Если PowerShell запрещает активацию виртуального окружения, в текущем окне выполните:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 2. Проверка без моделей и API-ключей

В проекте предусмотрены короткие демонстрационные конфигурации: RPS использует случайного агента, Water Allocation — Mock-агентов.

```powershell
python run.py --config configs/rps_smoke.yaml
python run.py --config configs/water_smoke.yaml
python -m unittest discover -s tests -v
```

Эти команды не требуют подключения к Ollama или Anthropic и не расходуют платные API-токены.

## 3. Подключение LLM

### Локальные модели через Ollama

Установите и запустите [Ollama](https://ollama.com/). Убедитесь, что API доступен по адресу `http://127.0.0.1:11434`.

Модель Qwen2.5 в конфигурациях обозначена как `qwen2.5:7b`:

```powershell
ollama pull qwen2.5:7b
```

Для Qwen3.5 используется конкретный тег модели из Hugging Face, загруженный в Ollama:

```powershell
ollama pull hf.co/Canfield/Qwen3.5-9B-Q4_K_M-GGUF:Q4_K_M
ollama list
```

Имена моделей в Ollama должны совпадать со значениями `llm.model` в соответствующих YAML-файлах. Если сервис не запущен автоматически, его можно запустить командой `ollama serve` в отдельном терминале.

### Claude Sonnet через Anthropic API

Создайте локальный файл `.env` на основе образца:

```powershell
Copy-Item .env.example .env
```

Впишите свой ключ в `.env`:

```dotenv
ANTHROPIC_API_KEY=your_key_here
```

Для других совместимых конфигураций клиента предусмотрена переменная `OPENAI_API_KEY`, но основные воспроизведённые запуски этого проекта используют Ollama и Anthropic. Ключи **не нужно** добавлять в YAML, код или репозиторий GitHub. Запуск Claude использует платные API-запросы.

## 4. Эксперимент 1 — Rock–Paper–Scissors

Во всех основных конфигурациях используются 12 сценариев и 10 повторов каждого сценария. Параметры серии:

| Серия | Temperature | Раундов в повторе |
|---|---:|---:|
| BASE | 0.7 | 10 |
| T01 | 0.0 | 10 |
| T02 | 0.3 | 10 |
| T03 | 1.0 | 10 |
| R01 | 0.7 | 5 |
| R02 | 0.7 | 20 |
| R03 | 0.7 | 40 |

**Один базовый запуск для каждой модели:**

```powershell
# Qwen2.5:7b
python run.py --config configs/rps_BASE.yaml

# Qwen3.5:9b
python run.py --config configs/rps35_BASE.yaml

# Claude Sonnet 4.6
python run.py --config configs/rps_claude_BASE.yaml
```

Для остальных серий замените `BASE` на `T01`, `T02`, `T03`, `R01`, `R02` или `R03`. Например:

```powershell
python run.py --config configs/rps_T01.yaml
python run.py --config configs/rps35_R02.yaml
python run.py --config configs/rps_claude_R03.yaml
```

Результат каждого запуска сохраняется в папке `output.directory`, указанной в YAML. Основной файл для анализа — `rounds.csv`.

**Графики RPS:**

```powershell
python -m rps.plot --input results/rps/BASE
python -m rps.plot --input results/rps/BASE results/rps/qwen35_BASE results/rps/claude_BASE
```

## 5. Эксперимент 2 — Water Allocation

В каждом запуске: **5 агентов, 6 settings, 3 повтора для каждого setting, максимум 20 дней на эпизод**. Settings 1–3 выполняются без persona, settings 4–6 — с persona; в каждой тройке рассматриваются Low, Medium и High уровни доступности воды.

Для этой игры используется только серия BASE:

```powershell
# Qwen2.5:7b
python run.py --config configs/water_qwen25_BASE.yaml

# Qwen3.5:9b
python run.py --config configs/water_qwen35_BASE.yaml

# Claude Sonnet 4.6
python run.py --config configs/water_claude_BASE.yaml
```

Результаты сохраняются в `results/water/qwen25_BASE3/`, `results/water/qwen35_BASE3/`, `results/water/claude_BASE3/`. Основные файлы: `episodes.csv`, `rounds.csv`, `bids.csv`, `survival_rates.csv`. Подробные состояния эпизодов находятся в `episodes/*.json`.

**Построение графиков:**

```powershell
python -m water_allocation.plot --input results/water/qwen25_BASE3
python -m water_allocation.plot --input results/water/qwen35_BASE3
python -m water_allocation.plot --input results/water/claude_BASE3
```

## 6. Конфигурация и повторное выполнение

Эксперимент выбирается командой `python run.py --config <файл.yaml>`. В YAML:

- `experiment.num_rounds` — число раундов RPS или максимальное число дней Water Allocation;
- `experiment.num_tests` — число повторов каждого сценария / setting;
- `llm` — провайдер, идентификатор модели, температура, ограничение выходных токенов, таймаут и попытки;
- `output.directory` — каталог сохранения результатов.

Эксперименты сохраняют `config.json` и поддерживают продолжение прерванного запуска из сохранённых данных. Чтобы не смешивать разные запуски, при самостоятельном изменении настроек рекомендуется задавать новый `output.directory`. Графики строятся отдельными командами и не запускаются автоматически.

## 7. Структура проекта

```text
common/             Загрузка настроек, HTTP-клиент LLM, операции ввода-вывода
rps/                Логика игры RPS, эксперимент, метрики, графики
water_allocation/   Правила аукциона, агенты, эксперимент, метрики, графики
configs/            YAML-конфигурации моделей и экспериментов
examples/           Примеры входных и ожидаемых данных
tests/              Автоматические тесты
results/            Сохранённые результаты (если включены в репозиторий)
run.py              Точка входа
requirements.txt    Зависимости Python
.env.example        Образец переменных окружения без секретов
```

## 8. Безопасность при публикации

Настоящие API-ключи хранятся только в локальном `.env`. Файл `.gitignore` исключает `.env`, виртуальные окружения, временные файлы и архивы; `.env.example` разрешено публиковать.

Никогда не публикуйте реальные API-ключи и токены.
