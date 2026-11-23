"""Эталонные тесты на фиксированных входных данных без вызова LLM."""
import unittest
from pathlib import Path

from common.io import load_records, read_selection
from rps.game import parse_move, payoff, outcome
from water_allocation.game import initial_players, winners_for_day
from rps.experiment import select_scenarios
from water_allocation.experiment import select_settings

ROOT = Path(__file__).resolve().parents[1]


class ReferenceTests(unittest.TestCase):
    def test_rps_reference(self):
        inp = load_records(ROOT / 'examples/rps/input.json')
        exp = load_records(ROOT / 'examples/rps/expected_output.json')
        player = parse_move('{"move": "' + inp['player'] + '"}')
        opponent = parse_move('{"move": "' + inp['opponent'] + '"}')
        self.assertEqual({'outcome': outcome(player, opponent), 'reward': payoff(player, opponent)}, exp)

    def test_water_reference(self):
        inp = load_records(ROOT / 'examples/water/input.json')
        exp = load_records(ROOT / 'examples/water/expected_output.json')
        players = initial_players()
        for name, balance in inp['balances'].items():
            players[name].balance = balance
        winners = winners_for_day(players, inp['bids'], inp['supply'])
        self.assertEqual({'winners': winners, 'allocated_water': sum(players[n].requirement for n in winners)}, exp)

    def test_csv_import(self):
        exp = {'scenarios_file': str(ROOT / 'examples/rps/scenarios.csv')}
        self.assertEqual([s.name for s in select_scenarios(exp)], ['constant_rock', 'loop2_rock_paper'])

    def test_json_import(self):
        exp = {'settings_file': str(ROOT / 'examples/water/settings.json')}
        self.assertEqual(select_settings(exp), [1,4])

    def test_full_scenarios_default(self):
        self.assertEqual(len(select_scenarios({})), 12)
        self.assertEqual(len(select_settings({})), 6)
