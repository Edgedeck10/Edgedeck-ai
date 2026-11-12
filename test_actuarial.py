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
  self.assertIsNone(x['probability_positive_ev']);self.assertEqual(x['positive_ev_scenario_weight'],1)
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
  ps=[(r,r['stats']['Points'],30) for r in self.records(range(40))]
  w=a.history_window(ps);self.assertGreater(w['evaluation_games'],0)
  # Held-out values cannot influence the selected window.
  n=len(ps);cut=25+max(1,int((n-25)*.7))
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

class ScenarioTests(unittest.TestCase):
 def test_weighted_price_and_sensitivity(self):
  e={'draw_histograms':[{'0':1},{'2':1},{'2':1}],'scenario_weights':[.25,.5,.25]}
  p=a.price(e,1,'Over',100)
  self.assertEqual(p['probability'],.75)
  self.assertEqual(p['probability_range_80'],[0,1])
  self.assertEqual(p['expected_roi_pct'],50)
  self.assertIsNone(p['probability_positive_ev'])
 def test_count_distribution_moments(self):
  for k,var in [(None,6),(6,12)]:
   h=a.distribution('count',6,30,k,0)
   mean=sum(float(y)*p for y,p in h.items())
   self.assertAlmostEqual(mean,6,places=5)
   self.assertAlmostEqual(sum((float(y)-mean)**2*p for y,p in h.items()),var,places=4)
 def test_short_history_is_not_validation(self):
  w=a.history_window([({},i,30) for i in range(8)])
  self.assertEqual(w['selected_games'],8)
  self.assertEqual(w['evaluation_games'],0)


class MatchupTests(unittest.TestCase):
 def test_opponent_index_has_no_future_leakage(self):
  import matchup
  events={};records={'p':[]}
  for i in range(12):
   date=f'2026-01-{i+1:02d}T00:00:00Z';eid=str(i)
   events[eid]={'home':{'id':'h'},'away':{'id':'a'}}
   records['p'].append({'start':date,'event_id':eid,'team_id':'h','stats':{'Minutes':30,'Points':20 if i<10 else 9999}})
  index=matchup.Index(records,events,'NBA','Points')
  rate,n=index.rate('a','2026-01-11T00:00:00Z')
  self.assertEqual(n,10);self.assertAlmostEqual(rate,20/30)
 def test_insufficient_matchup_is_neutral(self):
  import matchup
  matchup.CACHE.clear()
  e={'start':'2026-02-01','home':{'id':'h'},'away':{'id':'a'}}
  x=matchup.evaluate([],{}, {},e,'NBA','Points','h')
  self.assertEqual(x['multiplier'],1);self.assertEqual(x['holdout_games'],0)
 def test_missing_venue_is_not_assumed_away(self):
  import matchup
  matchup.CACHE.clear()
  games=[{'start':f'2026-01-{i+1:02d}','event_id':str(i),'team_id':'h','stats':{'Minutes':30,'Points':20}} for i in range(12)]
  x=matchup.evaluate(games,{'p':games},{},{'start':'2026-02-01','home':{'id':'h'},'away':{'id':'a'}},'NBA','Points','h')
  self.assertEqual(x['venue_splits'],{})
 def test_nhl_regulation_shots_not_overwritten(self):
  import pipeline
  e={'id':'NHL:1','start':'2026-01-01','sport':'NHL','source_url':'https://www.espn.com'}
  d={'boxscore':{'players':[{'team':{'id':'h'},'statistics':[{'name':'forwards','labels':['S','TOI'],'athletes':[{'athlete':{'id':'p'},'stats':['4','18:30']}]},{'name':'shootout','labels':['SOG'],'athletes':[{'athlete':{'id':'p'},'stats':['0']}]}]}]}}
  r=pipeline.parse_box(d,e)[0]
  self.assertEqual(r['stats']['Shots on goal'],4)


class ProjectionEvidenceTests(unittest.TestCase):
 def test_total_explanation_reconciles(self):
  import pipeline as p,datetime as dt
  e={'id':'NFL:next','sport':'NFL','event':'Away at Home','start':(p.NOW+dt.timedelta(days=1)).isoformat(),'day':p.TODAY.isoformat(),'home':{'id':'h','name':'Home'},'away':{'id':'a','name':'Away'},'source_url':'https://www.espn.com'}
  g={'id':'NFL:past','sport':'NFL','event':'Away at Home','start':(p.NOW-dt.timedelta(days=7)).isoformat(),'final':True,'home':{'id':'h','name':'Home','score':28},'away':{'id':'a','name':'Away','score':17},'source_url':'https://www.espn.com'}
  rows=p.team_rows({g['id']:g},e,[]);r=next(r for r in rows if r['market']=='Total');x=r['projection_evidence']
  self.assertEqual(x['home']['blend'],28)
  self.assertEqual(x['away']['blend'],17)
  self.assertAlmostEqual(x['home']['projected_score'],29)
  self.assertAlmostEqual(x['away']['projected_score'],16)
  self.assertAlmostEqual(x['total'],45)
  self.assertAlmostEqual(r['projection'],x['total'],places=2)
  self.assertEqual(x['home']['source_games'][0]['event_id'],g['id'])


class AiRecordTests(unittest.TestCase):
 def row(self,**kw):
  return {'id':'x','event_id':'e','event':'A at B','sport':'NFL','market':'Total','side':'Over','line':40.5,'projection':45,'probability':.8,'model_version':'opportunity-4.2.0','start':'2026-01-01','graded_at':'2026-01-02','sample':10,'fair_odds':-150,**kw}
 def test_records_exclude_push_pending_and_separate_sports(self):
  import ai_record as a
  rows=[self.row(outcome=1,odds=100,profit_units=1,actual_value=48),self.row(id='y',outcome=0,odds=100,profit_units=-1,actual_value=35),self.row(id='p',outcome='push'),self.row(id='z',sport='NBA',outcome=None)]
  d=a.summarize(rows);overall=d['records'][0];nfl=next(r for r in d['records'] if r['sport']=='Pro Football')
  self.assertEqual((overall['wins'],overall['losses'],overall['pushes'],overall['pending']),(1,1,1,1));self.assertEqual(overall['hit_rate'],.5);self.assertEqual(nfl['roi_pct'],0)
 def test_bundle_loss_overrides_pending(self):
  import ai_record as a
  self.assertEqual(a.summarize([self.row(outcome=0),self.row(id='y',outcome=None)])['bundles'][0]['outcome'],0)
 def test_calibration_excludes_future_and_is_holdout_gated(self):
  import ai_record as a
  rows=[self.row(id=str(i),event_id=str(i),start=f'2026-01-{i%28+1:02d}',graded_at='2026-02-01',outcome=i%2) for i in range(40)]
  self.assertEqual(a.calibration(rows,'2026-01-01'),{})
  rule=a.calibration(rows,'2026-03-01')['NFL|Total'];self.assertLess(rule['conditional_probability_offset'],0);self.assertLess(rule['adjusted_brier'],rule['baseline_brier'])
  original=rows[0]['probability'];future=self.row();a.apply(future,{'NFL|Total':rule});self.assertLess(future['probability'],original);self.assertEqual(rows[0]['probability'],original)
 def test_insufficient_learning_does_not_change_forecast(self):
  import ai_record as a
  row=self.row();a.apply(row,a.calibration([self.row(outcome=0)],'2026-03-01'));self.assertEqual(row['probability'],.8)
 def test_selection_one_player_and_main_lines(self):
  import ai_record as a
  rows=[self.row(id='alt',player_id='p',base_line=50.5),self.row(id='base',player_id='p',base_line=40.5),self.row(id='base2',player_id='p',base_line=40.5)]
  self.assertEqual(len(a.choose(rows)),1)


class UpToTenTests(unittest.TestCase):
 def test_cap_and_no_filler(self):
  import ai_record as a
  rows=[{'id':str(i),'player_id':str(i),'side':'Over','line':10.5,'base_line':10.5,'projection':12,'probability':.6,'sample':10,'fair_odds':-150,'odds':None} for i in range(14)]
  self.assertEqual(len(a.choose(rows)),10)
  self.assertEqual(len(a.choose(rows[:3])),3)
  self.assertEqual(a.choose([{**r,'projection':9} for r in rows]),[])
 def test_negative_ev_never_fills(self):
  import ai_record as a
  r={'id':'a','side':'Over','line':40.5,'projection':44,'probability':.6,'sample':10,'odds':-110,'market':'Total','expected_roi_pct':-1}
  self.assertEqual(a.choose([r]),[])
  self.assertEqual(len(a.choose([{**r,'expected_roi_pct':2}])),1)
