"""Проверка CLI, YAML и продолжения эксперимента на локальных агентах."""
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from common.config import load_config, reserve_output, public_config
from rps.experiment import run as run_rps
from water_allocation.experiment import run as run_water

ROOT = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def test_load_yaml(self):
        cfg = load_config(ROOT/'configs/rps.yaml')
        self.assertEqual(cfg['experiment']['game'], 'rps')
        self.assertEqual(cfg['experiment']['num_tests'], 10)

    def test_rps_resume_and_paper_score(self):
        with TemporaryDirectory() as tmp:
            cfg = {'experiment': {'game':'rps', 'scenarios':['constant_rock','copy'],
                   'num_rounds':3, 'num_tests':2,'seed':2024},
                   'llm': {'provider':'random', 'model':'qwen2.5:7b'},
                   'output': {'directory': tmp}}
            run_rps(cfg, reserve_output(cfg))
            p = Path(tmp)/'rounds.csv'
            first = p.read_bytes()
            run_rps(cfg, reserve_output(cfg))
            self.assertEqual(first, p.read_bytes())
            with p.open(newline='') as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 12)
            for row in rows:
                self.assertEqual(int(row['payoff']), {'win': 2, 'draw': 1, 'loss': 0}[row['result']])

    def test_water_resume(self):
        with TemporaryDirectory() as tmp:
            cfg = {'experiment': {'game':'water_allocation', 'settings':[1,4],
                   'num_rounds':2, 'num_tests':1,'seed':2025},
                   'llm': {'provider':'mock','model':'qwen2.5:7b','temperature':0.7},
                   'output': {'directory': tmp}}
            run_water(cfg, reserve_output(cfg))
            p = Path(tmp)/'rounds.csv'
            first = p.read_bytes()
            run_water(cfg, reserve_output(cfg))
            self.assertEqual(first, p.read_bytes())
            with (Path(tmp)/'episodes.csv').open(encoding='utf-8-sig',newline='') as file:
                rows = list(csv.DictReader(file))
            self.assertEqual({int(x['setting']) for x in rows}, {1,4})

    def test_prevent_different_config_same_output(self):
        with TemporaryDirectory() as tmp:
            cfg = {'experiment': {'game':'rps', 'num_rounds':1, 'num_tests':1, 'seed':1},
                   'llm': {'provider':'random'}, 'output': {'directory':tmp}}
            reserve_output(cfg)
            cfg['experiment']['seed'] = 100
            with self.assertRaises(ValueError):
                reserve_output(cfg)

    def test_remove_inline_secrets_from_recorded_config(self):
        cfg = {'llm': {'api_key':'secret', 'token':'secret', 'provider':'openai'}}
        self.assertNotIn('secret', json.dumps(public_config(cfg)))
