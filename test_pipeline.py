import unittest, datetime as dt
import pipeline as p
class PipelineTest(unittest.TestCase):
 def setUp(self):
  self.e={'id':'NBA:t','espn_id':'t','sport':'NBA','event':'Away at Home','start':(p.NOW+dt.timedelta(hours=3)).isoformat(),'day':p.TODAY.isoformat(),'home':{'id':'h','name':'Home','score':100,'periods':[25,25,25,25]},'away':{'id':'a','name':'Away','score':90,'periods':[20,20,25,25]},'final':True,'source_url':'https://www.espn.com','odds':[]}
 def test_grade_exact_markets(self):
  e=self.e
  self.assertEqual(p.settle({'market':'Spread','side':'home','line':-9.5},e,{}),1)
  self.assertEqual(p.settle({'market':'Spread','side':'away','line':10},e,{}),'push')
  self.assertEqual(p.settle({'market':'Total','side':'Under','line':190.5},e,{}),1)
  self.assertEqual(p.settle({'market':'1st half total','side':'Over','line':89.5},e,{}),1)
  self.assertEqual(p.settle({'market':'Team total','team_id':'a','side':'Under','line':90},e,{}),'push')
 def test_player_combo_and_missing_not_loss(self):
  r={'player_id':'1','market':'PRA','side':'Over','line':29.5}
  self.assertIsNone(p.settle(r,self.e,{}))
  box={self.e['id']:[{'player_id':'1','stats':{'Points':20,'Rebounds':6,'Assists':5}}]}
  self.assertEqual(p.settle(r,self.e,box),1)
 def test_no_unpriced_edge(self):
  r=p.make_row(self.e,'Points','Over',9.5,20,5,[],sample=15)
  self.assertIsNone(r['edge_pp']);self.assertFalse(r['qualified']);self.assertGreater(r['probability'],.9)
 def test_probability_and_price_math(self):
  a=p.make_row(self.e,'Points','Over',10.5,20,5,[]);b=p.make_row(self.e,'Points','Under',10.5,20,5,[])
  self.assertAlmostEqual(a['probability']+b['probability'],1)
  self.assertAlmostEqual(p.implied(-150),.6);self.assertEqual(p.fair(.5),-100)
 def test_calibration(self):
  h={'event_id':'NBA:old','model_version':p.MODEL,'calibration_key':'NBA:Points:Over','market':'Points','side':'Over','outcome':1,'raw_probability':.6}
  result,n=p.calibrate([h],h['calibration_key'],.6);self.assertGreater(result,.6);self.assertEqual(n,1)
 def test_soccer_draw_is_a_separate_outcome(self):
  e={**self.e,'sport':'EPL'};e['home']={**e['home'],'score':1};e['away']={**e['away'],'score':1}
  self.assertEqual(p.settle({'market':'Moneyline','side':'draw'},e,{}),1)
  self.assertEqual(p.settle({'market':'Moneyline','side':'home'},e,{}),0)
 def test_small_sample_interval_not_certainty(self):
  low,high=p.wilson(5,5);self.assertLess(low,.6);self.assertEqual(high,1)
 def test_schedule_score_objects(self):self.assertEqual(p.num({'value':117}),117)
if __name__=='__main__':unittest.main()
