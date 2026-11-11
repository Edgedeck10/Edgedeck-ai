import math,unittest
from actuarial import count_tail,assess,proper_scores
from daily_picks import estimated_singles
class ActuarialTests(unittest.TestCase):
 def test_poisson_zero_threshold(self):
  self.assertAlmostEqual(count_tail(2,2,.5),1-math.exp(-2))
 def test_negative_binomial_geometric(self):
  self.assertAlmostEqual(count_tail(1,2,1.5),.25)
 def test_integer_push_not_win(self):
  self.assertAlmostEqual(count_tail(1,1,1,'Under'),math.exp(-1))
  self.assertAlmostEqual(count_tail(1,1,1,'Over'),1-2*math.exp(-1))
 def test_floor_only_reduces(self):
  r={'market':'Threes','projection':2,'sd':2,'line':2.5,'side':'Over','probability':.8,'probability_floor':.7,'probability_margin':.1}
  a=assess(r,[0,1,2,3,4]*3)
  self.assertLessEqual(a['selection_floor'],.7);self.assertEqual(r['probability'],.8)
 def test_no_continuous_yardage_nb(self):
  self.assertEqual(assess({'market':'Receiving yards'},[-2,5]*10)['status'],'unavailable')
 def test_no_fake_small_sample(self):
  self.assertEqual(assess({'market':'Threes'},[1,2])['status'],'unavailable')
 def test_scores_group_alternates(self):
  r={'event_id':'1','player_id':'2','market':'Threes','side':'Over','probability':.8,'outcome':1}
  a=proper_scores([r,r]);self.assertEqual(a['groups'],1);self.assertAlmostEqual(a['brier'],.04);self.assertAlmostEqual(a['log_loss'],-math.log(.8))
 def test_comparison_can_block_selection(self):
  r={'sport':'NBA','player_id':'1','side':'Over','sample':20,'probability':.85,'selection_probability':.4,'hit_rate':.9,'start':'2026-11-12T00:00:00Z','flags':[]}
  self.assertEqual(estimated_singles([r],'2026-11-11T20:00:00Z'),[])
