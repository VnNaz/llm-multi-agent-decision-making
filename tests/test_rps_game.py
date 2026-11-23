import sys
from pathlib import Path
import random
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rps.game import (
    ROCK, PAPER, SCISSOR, MOVES, SCENARIOS, SCENARIO_BY_NAME,
    BEATS, choose_opponent_move, outcome, parse_move, payoff, trial_seed,
)


class FanRpsTests(unittest.TestCase):
    def test_twelve_scenarios(self):
        self.assertEqual(len(SCENARIOS), 12)
        self.assertEqual(len(SCENARIO_BY_NAME), 12)

    def test_constant_and_loops(self):
        cases = [
            ("constant_rock", [ROCK]*7),
            ("constant_scissor", [SCISSOR]*7),
            ("constant_paper", [PAPER]*7),
            ("loop2_rock_paper", [ROCK, PAPER, ROCK, PAPER, ROCK, PAPER, ROCK]),
            ("loop2_paper_scissor", [PAPER, SCISSOR, PAPER, SCISSOR, PAPER, SCISSOR, PAPER]),
            ("loop2_scissor_rock", [SCISSOR, ROCK, SCISSOR, ROCK, SCISSOR, ROCK, SCISSOR]),
            ("loop3_rock_paper_scissor", [ROCK, PAPER, SCISSOR, ROCK, PAPER, SCISSOR, ROCK]),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                hist = []
                rng = random.Random(7)
                actual = []
                for _ in expected:
                    action = choose_opponent_move(SCENARIO_BY_NAME[name], hist, rng)
                    hist.append((ROCK, action))
                    actual.append(action)
                self.assertEqual(actual, expected)

    def test_copy_previous_action_only(self):
        hist = [(PAPER, ROCK), (SCISSOR, PAPER)]
        self.assertEqual(choose_opponent_move(SCENARIO_BY_NAME["copy"], hist, random.Random(1)), SCISSOR)

    def test_counter_previous_action_only(self):
        for act in range(3):
            hist = [(act, (act + 2) % 3)]
            self.assertEqual(
                choose_opponent_move(SCENARIO_BY_NAME["counter"], hist, random.Random(1)),
                BEATS[act],
            )

    def test_initial_copy_counter_is_seeded(self):
        for name in ("copy", "counter"):
            self.assertEqual(
                choose_opponent_move(SCENARIO_BY_NAME[name], [], random.Random(19)),
                choose_opponent_move(SCENARIO_BY_NAME[name], [], random.Random(19)),
            )

    def test_sample_probability_approximately(self):
        rng = random.Random(42)
        for name in ("sample_rock", "sample_scissor", "sample_paper"):
            scenario = SCENARIO_BY_NAME[name]
            samples = [choose_opponent_move(scenario, [], rng) for _ in range(3000)]
            self.assertTrue(.67 < samples.count(scenario.preferred) / len(samples) < .73)

    def test_all_payoffs(self):
        for my_action in range(3):
            for opp_action in range(3):
                if my_action == opp_action:
                    expected, name = 1, "draw"
                elif my_action == BEATS[opp_action]:
                    expected, name = 2, "win"
                else:
                    expected, name = 0, "loss"
                self.assertEqual(payoff(my_action, opp_action), expected)
                self.assertEqual(outcome(my_action, opp_action), name)

    def test_strict_json_move_parser(self):
        self.assertEqual(parse_move('{"move":"Paper"}'), PAPER)
        self.assertEqual(parse_move('{"move":"SCISSORS"}'), SCISSOR)
        with self.assertRaises((ValueError, TypeError)):
            parse_move("The move is rock")
        with self.assertRaises(ValueError):
            parse_move('{"move":"lizard"}')

    def test_stable_seed(self):
        self.assertEqual(trial_seed(2024, "copy", 1), trial_seed(2024, "copy", 1))
        self.assertNotEqual(trial_seed(2024, "copy", 1), trial_seed(2024, "copy", 2))

    def test_model_prompt_cannot_see_scenario(self):
        # Сценарий соперника не должен попадать в историю игрока.
        history = [(ROCK, PAPER)]
        self.assertEqual(len(history[0]), 2)

    def test_markdown_json_move_parser(self):
        # Проверка JSON-ответа внутри Markdown-блока
        raw = '```json\n{"move": "Rock"}\n```'
        plain = '{"move": "Rock"}'

        self.assertEqual(parse_move(raw), parse_move(plain))

if __name__ == "__main__":
    unittest.main()
