import unittest
from opportunity_metrics import workload_sensitivity
from daily_picks import estimated_singles
class WorkloadTests(unittest.TestCase):
 def test_sensitivity_does_not_mutate_forecast(self):
  pairs=[({'stats':{'Minutes':x}},x*.6) for x in range(20,40)]
  model={'exposure':32,'rate':.6,'mu':19.2,'sd':5,'residuals':[-4,0,4]}
  before=dict(model);out=workload_sensitivity(pairs,'Points','NBA',model,18.5,'Over')
  self.assertEqual(model,before);self.assertEqual(len(out),3)
  self.assertLess(out[0]['probability'],out[-1]['probability'])
  self.assertTrue(all('weight' not in x for x in out))
 def test_missing_workload(self):
  self.assertEqual(workload_sensitivity([],'Points','NBA',{},10,'Over'),[])
 def test_no_unresolved_usage_fallback(self):
  r={'sport':'NBA','player_id':'1','side':'Over','odds':None,'sample':20,'probability':.85,'hit_rate':.9,'start':'2026-11-12T00:00:00Z','flags':['Teammate usage unresolved']}
  self.assertEqual(estimated_singles([r],'2026-11-11T20:00:00Z'),[])
