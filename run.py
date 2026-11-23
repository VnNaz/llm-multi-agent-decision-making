"""Запускает выбранную игру по YAML-конфигурации."""
import argparse
from pathlib import Path
from common.config import load_config, load_dotenv, reserve_output


def main(argv=None):
    parser = argparse.ArgumentParser(description='Эксперименты LLM: RPS / Water Allocation')
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        load_dotenv()
        cfg = load_config(args.config)
        output = reserve_output(cfg)
        if cfg['experiment']['game'] == 'rps':
            from rps.experiment import run
        else:
            from water_allocation.experiment import run
        run(cfg, output)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(2, f'Ошибка: {exc}\n')


if __name__ == '__main__':
    main()
