import unittest
import pick_evidence as e
class Evidence(unittest.TestCase):
 def test_measured_game_thesis_and_future_exclusion(self):
  row={'event_id':'NBA:future','market':'Spread','side':'away','line':7.5,'team_id':'A','selection':'Away','sport':'NBA','start':'2026-11-11T22:00Z','probability':.65,'projection':-2,'sd':12,'odds':-110,'sample':20,'source_url':'https://example.org/stats','context':{'points_for':110,'opponent_allowed':112,'rest_days':2}}
  def game(start,final):return {'id':start,'start':start,'sport':'NBA','final':final,'home':{'id':'B','score':110,'abbr':'B'},'away':{'id':'A','score':105,'abbr':'A'}}
  ev=e.build(row,{'old':game('2026-11-01T22:00Z',True),'future':game('2026-11-12T22:00Z',True)},[],{}, {})
  self.assertEqual(ev['history']['games'],1);self.assertEqual(ev['history']['wins'],1);self.assertAlmostEqual(ev['break_even'],110/210);self.assertEqual(ev['games'][0]['value'],-5);self.assertTrue(any('not fully modeled' in r for r in ev['risks']))
 def test_no_invented_history(self):
  r={'event_id':'x','market':'Moneyline','sport':'NFL','side':'home','selection':'Team','start':'2026-11-11T22:00Z','probability':.65,'projection':2,'sd':10,'odds':-110,'sample':0}
  ev=e.build(r,{},[],{},{});self.assertEqual(ev['games'],[]);self.assertNotIn('wins',ev['history']);self.assertTrue(any('does not confirm' in x for x in ev['risks']))
if __name__=='__main__':unittest.main()
