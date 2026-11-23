import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from water_allocation.game import (PLAYERS, LEVELS, SETTINGS, Player, initial_players, supplies,
                    winners_for_day, settle, system_prompt)
from water_allocation.agents import parse_bid, MockAgent
from water_allocation.experiment import create_episode, advance_episode, run
from water_allocation.metrics import export_reports


class EngineTests(unittest.TestCase):
    def test_five_players_and_demands(self):
        ps=initial_players()
        self.assertEqual(len(ps),5)
        self.assertEqual(sum(p.requirement for p in ps.values()),50)
        self.assertEqual([p.salary for p in ps.values()],[70,75,100,120,120])
        self.assertEqual([p.hp for p in ps.values()],[8]*5)

    def test_supply_levels_exact_ranges_and_reproducible(self):
        for level,(lo,hi) in LEVELS.items():
            sample=supplies(level, 300, 40)
            self.assertEqual(sample,supplies(level, 300, 40))
            self.assertTrue(all(lo<=x<hi for x in sample))
        self.assertEqual(len(SETTINGS),6)

    def test_higher_bid_wins(self):
        p=initial_players()
        for x in p.values(): x.balance=100
        winners=winners_for_day(p,{'Alex':80,'Bob':90,'Cindy':30,'David':10,'Eric':9},19)
        self.assertEqual(winners,['Bob','Alex'])

    def test_tie_is_lower_demand_and_no_oversupply(self):
        p=initial_players()
        for x in p.values(): x.balance=100
        # При равенстве ставок побеждает участник с меньшей потребностью.
        self.assertEqual(winners_for_day(p,{n:50 for n in p},8),['Alex'])
        w=winners_for_day(p,{n:50 for n in p},17)
        self.assertEqual(w,['Alex','Bob'])
        self.assertLessEqual(sum(p[n].requirement for n in w),17)

    def test_no_underfunded_or_invalid_bids(self):
        p=initial_players()
        for x in p.values(): x.balance=10
        bids={'Alex':999,'Bob':-1,'Cindy':None,'David':10,'Eric':5}
        self.assertEqual(winners_for_day(p,bids,30),['David','Eric'])

    def test_salary_then_win_cost_and_heal(self):
        p=initial_players()
        p['Alex'].balance+=p['Alex'].salary
        settle(p,{'Alex':60},['Alex'])
        self.assertEqual(p['Alex'].hp,10)
        self.assertEqual(p['Alex'].balance,10)
        self.assertEqual(p['Alex'].no_water_days,0)
        self.assertEqual(p['Bob'].hp,7)
        self.assertEqual(p['Bob'].no_water_days,1)

    def test_failed_streak_damage_and_elimination(self):
        p={'Alex':Player('Alex',8,70)}
        for hp in [7,5,2,0]:
            settle(p, {'Alex':0},[])
            self.assertEqual(p['Alex'].hp,hp)
        self.assertFalse(p['Alex'].alive)
        self.assertEqual(p['Alex'].balance,0)

    def test_win_resets_no_water_streak(self):
        p={'Alex':Player('Alex',8,70, hp=4, balance=40, no_water_days=3)}
        settle(p,{'Alex':10},['Alex'])
        self.assertEqual(p['Alex'].no_water_days,0)
        self.assertEqual(p['Alex'].hp,6)

    def test_personas_optional_and_isolated(self):
        a=system_prompt('Alex',20,'low',True)
        b=system_prompt('Alex',20,'low',False)
        self.assertIn('Unemployed',a)
        self.assertNotIn('Unemployed',b)
        self.assertIn('Alex needs 8 water/day',a)

    def test_bid_json_strict(self):
        self.assertEqual(parse_bid('{"bid": 50, "reason":"ok"}',70),50)
        with self.assertRaises(ValueError):parse_bid('{"bid": "50"}',70)
        with self.assertRaises(ValueError):parse_bid('{"bid": 71}',70)
        with self.assertRaises(ValueError):parse_bid('{"bid": -1}',70)
        with self.assertRaises(ValueError):parse_bid('I bid 45 dollars',70)

    def test_mock_determinism_resume(self):
        m=MockAgent(12)
        kw={'setting':1,'repeat':2,'day':3,'name':'Alex'}
        a=m.choose([],70,**kw)
        b=MockAgent(12).choose([],70,**kw)
        self.assertEqual(a,b)

    def test_run_offline_and_csv_resume(self):
        with tempfile.TemporaryDirectory() as root:
            cfg={'experiment': {'game':'water_allocation', 'settings':[1], 'num_tests':1, 'num_rounds':3,'seed':2025}, 'llm': {'provider':'mock','model':'qwen2.5:7b', 'temperature':0.7}, 'output': {'directory': root}}
            self.assertIsNone(run(cfg,Path(root)))
            p=Path(root)/'episodes'/'setting_1_rep_01.json'
            first=json.loads(p.read_text(encoding='utf-8'))
            self.assertTrue(first['complete'])
            self.assertEqual(len(first['rounds']),3)
            self.assertIsNone(run(cfg,Path(root))) # Skips completed, no duplicates.
            second=json.loads(p.read_text(encoding='utf-8'))
            self.assertEqual(first,second)
            self.assertTrue((Path(root)/'rounds.csv').exists())
            self.assertTrue((Path(root)/'survival_rates.csv').exists())

    def test_mid_round_resume_no_double_salary(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'episode.json'
            state=create_episode(1,'low',False,1,2,2025,'qwen2.5:7b','mock',0.7)
            # Имитация прерывания после начисления зарплаты и сохранения первой ставки.
            players=state['players']
            for person in players.values():
                person['balance']+=person['salary']
            state['pending']={'day':1,'supply':state['supply_schedule'][0],
                              'alive_before':list(players), 'bids':{'Alex':30},
                              'raw_responses':{'Alex':'{"bid":30}'},'attempts':{'Alex':1},
                              'asked':['Alex'],
                              'before':{n: {'hp': q['hp'], 'balance':q['balance'],
                                             'no_water_days':q['no_water_days']}
                                        for n,q in players.items()}}
            players['Alex']['history'].append({'role':'user','content':'Ask day 1'})
            players['Alex']['history'].append({'role':'assistant','content':'{"bid":30}'})
            advance_episode(state,p,MockAgent(2025))
            self.assertTrue(state['complete'])
            self.assertEqual(len(state['rounds']),2)
            self.assertEqual(state['rounds'][0]['bids']['Alex'],30)
            self.assertEqual(state['rounds'][0]['before']['Alex']['balance'],70)

    def test_supply_paired_between_persona(self):
        one=create_episode(1,'low',False,3,20,1984,'qwen','ollama',0.7)
        two=create_episode(4,'low',True,3,20,1984,'qwen','ollama',0.7)
        self.assertEqual(one['supply_schedule'], two['supply_schedule'])


if __name__=='__main__':unittest.main()
