import unittest, actuarial as a
class EngineTests(unittest.TestCase):
 def records(self,ys,unit='Minutes',xs=None):
  return [{'start':f'2026-01-{i+1:02d}', 'stats':{'Points':y,unit:(xs[i] if xs else 30)}} for i,y in enumerate(ys)]
 def test_count_uncertainty_and_reproducibility(self):
  rs=self.records([0]*8)
  x=a.fit(rs,{},'NBA','Points','1','seed')
  self.assertEqual(x,a.fit(rs,{},'NBA','Points','1','seed'))
  self.assertGreater(x['projection'],0)
  self.assertGreater(a.price(x['evidence'],.5,'Over')['probability'],0)
 def test_price_push_and_positive_edge(self):
  e={'draw_histograms':[{'0':1,'1':1,'2':2}]*4}
  x=a.price(e,1,'Over',100)
  self.assertEqual(x['probability'],.5);self.assertEqual(x['push_probability'],.25)
  self.assertAlmostEqual(x['expected_roi_pct'],25)
  self.assertEqual(x['probability_positive_ev'],1)
  self.assertIsNone(a.price(e,1,'Over')['expected_roi_pct'])
 def test_finite_attempts(self):
  rs=[{'start':f'2026-01-{i+1:02d}','stats':{'Threes':i%3,'Three attempts':3}} for i in range(12)]
  x=a.fit(rs,{},'NBA','Threes','1','finite')
  self.assertTrue(all(0<=float(y)<=3 for h in x['evidence']['draw_histograms'] for y in h))
 def test_signed_yardage(self):
  rs=[{'start':f'2026-01-{i+1:02d}','stats':{'Receiving yards':y,'Receptions':1}} for i,y in enumerate([-8,-5,-1,0,1,2,4,7])]
  x=a.fit(rs,{},'NFL','Receiving yards','1','signed')
  self.assertTrue(any(float(y)<0 for h in x['evidence']['draw_histograms'] for y in h))
 def test_nested_window_holdout(self):
  ps=[(r,r['stats']['Points'],30) for r in self.records(range(25))]
  w=a.history_window(ps);self.assertGreater(w['evaluation_games'],0)
  # Held-out values cannot influence the selected window.
  n=len(ps);cut=5+max(1,int((n-5)*.7))
  changed=[(r,999999 if i>=cut else y,x) for i,(r,y,x) in enumerate(ps)]
  self.assertEqual(w['selected_games'],a.history_window(changed)['selected_games'])
 def test_log_loss_version_isolation(self):
  rows=[{'model_version':'new','sport':'NBA','market':'Points','event_id':'e','player_id':'1','side':'Over','probability':.8,'outcome':0}]
  self.assertGreater(a.monitoring(rows,'new')[0]['log_loss'],1)
  self.assertEqual(a.monitoring(rows,'old'),[])
if __name__=='__main__':unittest.main()

class PipelineIntegration(unittest.TestCase):
 def test_opportunity_parser(self):
  import pipeline as p
  e={'id':'NFL:1','start':'2026-01-01T00:00:00Z','sport':'NFL','source_url':'https://www.espn.com'}
  data={'boxscore':{'players':[{'team':{'id':'h'},'statistics':[{'name':'passing','labels':['C/ATT','YDS'],'athletes':[{'athlete':{'id':'p'},'stats':['20/30','220']}]},{'name':'receiving','labels':['REC','TGTS','YDS'],'athletes':[{'athlete':{'id':'r'},'stats':['5','8','-2']}]}]}]}}
  rows=p.parse_box(data,e)
  self.assertEqual(rows[0]['stats']['Pass attempts'],30)
  self.assertEqual(rows[1]['stats']['Targets'],8)
  self.assertEqual(rows[1]['stats']['Receiving yards'],-2)
 def test_end_to_end_player_rows(self):
  import pipeline as p,datetime as dt
  e={'id':'NBA:next','sport':'NBA','event':'H at A','start':(p.NOW+dt.timedelta(days=1)).isoformat(),'day':p.TODAY.isoformat(),'home':{'id':'h','name':'H'},'away':{'id':'a','name':'A'},'source_url':'https://www.espn.com'}
  box={}
  for i in range(12):
   box[str(i)]=[{'player_id':'p','player':'Player','sport':'NBA','event_id':'NBA:'+str(i),'start':(p.NOW-dt.timedelta(days=12-i)).isoformat(),'team_id':'h','stats':{'Minutes':30,'Points':20+i%4},'source_url':'https://www.espn.com'}]
  rows=p.player_rows({},e,box,[],[])
  self.assertGreater(len(rows),0)
  self.assertTrue(all('probability_range_80' in r for r in rows))
  self.assertTrue(all(r['engine_version']==a.VERSION for r in rows))
  self.assertTrue(all(r['side']=='Over' or r['line']==r['base_line'] for r in rows))
