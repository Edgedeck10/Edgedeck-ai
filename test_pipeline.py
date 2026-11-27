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
  h={'event_id':'NBA:old','model_version':p.model_for('NBA'),'calibration_key':'NBA:Points:Over','market':'Points','side':'Over','outcome':1,'raw_probability':.6}
  result,n=p.calibrate([h],h['calibration_key'],.6);self.assertGreater(result,.6);self.assertEqual(n,1)
 def test_schedule_score_objects(self):self.assertEqual(p.num({'value':117}),117)
if __name__=='__main__':unittest.main()


class RefreshRegression(unittest.TestCase):
 def test_new_day_schedules_complete_main(self):
  from unittest.mock import patch
  import contextlib,io
  future={'id':'NFL:next','espn_id':'next','sport':'NFL','event':'Away at Home','start':(p.NOW+dt.timedelta(hours=3)).isoformat(),'day':p.TODAY.isoformat(),'home':{'id':'h','name':'Home','periods':[],'stats':{}},'away':{'id':'a','name':'Away','periods':[],'stats':{}},'final':False,'state':'pre','source_url':'https://www.espn.com','odds':[]}
  raw={'id':'past','name':'Away at Home','date':(p.NOW-dt.timedelta(days=7)).isoformat(),'competitions':[{'competitors':[{'homeAway':'home','team':{'id':'h','displayName':'Home'},'score':'28'},{'homeAway':'away','team':{'id':'a','displayName':'Away'},'score':'21'}],'status':{'type':{'completed':True,'state':'post'}}}]}
  saved={}
  with patch.object(p,'read',side_effect=lambda n,d:d),patch.object(p,'write',side_effect=lambda n,v:saved.update({n:v})),patch.object(p,'scoreboard',side_effect=lambda sport,day:[future] if sport=='NFL' and day==p.TODAY.isoformat() else []),patch.object(p,'schedule',return_value={'events':[raw]}),patch.object(p,'summary',return_value={}),contextlib.redirect_stdout(io.StringIO()):p.main()
  self.assertIn('NFL:past',saved['events.json'])
  self.assertIn('status.json',saved)
  self.assertGreater(len(saved['latest.json']['recommendations']),0)
  self.assertEqual(saved['latest.json']['transport_version'],3)
 def test_compact_transport_preserves_predictions_and_archives(self):
  import feed_transport as f
  model={'draw_histograms':[{'0':.25,'2':.75}]};r={'id':'r','event_id':'e','player_id':'p','probability':.75,'context':{'source_games':[1]*100,'venue':'home'}}
  source={'recommendations':[r],'player_logs':{'a':{'model':model},'b':{'model':model}},'ai_selections':{}}
  compact=f.compact(source)
  self.assertEqual(len(compact['distributions']),1)
  self.assertEqual(compact['recommendations'][0]['probability'],.75)
  self.assertNotIn('source_games',compact['recommendations'][0]['context'])
  self.assertEqual(len(r['context']['source_games']),100)
  self.assertEqual(f.history_view([r])[0]['probability'],.75)

class LazyFeedRegression(unittest.TestCase):
 def test_lazy_feed_preserves_probabilities_and_full_distribution(self):
  import feed_transport as f
  import gzip,json,tempfile,pathlib
  model={'draw_histograms':[{'0':.25,'2':.75}]}
  rows=[{'id':str(line),'event_id':'e','log_key':'e:p:Points','player_id':'p','line':line,'probability':.75,'context':{}} for line in (1,1.5)]
  source={'games':[{'id':'e'}],'recommendations':rows,'player_logs':{'e:p:Points':{'games':[],'model':model}},'ai_selections':{'e':[{**rows[0],'frozen_model':model}]}}
  with tempfile.TemporaryDirectory() as directory:
   path=pathlib.Path(directory)/'details'
   compact=f.compact(source,path)
   restored=[{**compact['row_templates'].get(r.get('row_template'),{}),**r} for r in compact['recommendations']]
   self.assertEqual([r['probability'] for r in restored],[r['probability'] for r in rows])
   self.assertEqual([r['line'] for r in restored],[1,1.5])
   payload=json.loads(gzip.decompress((path.parent/compact['detail_files']['e']).read_bytes()))
   mid=payload['player_logs']['e:p:Points']['model']['distribution_id']
   self.assertEqual(payload['distributions'][mid],model['draw_histograms'])
   self.assertIn('frozen_model',source['ai_selections']['e'][0])
   self.assertNotIn('frozen_model',compact['ai_selections']['e'][0])


class KickoffWeatherRegression(unittest.TestCase):
 def test_forecast_affects_both_leagues_and_keeps_unconfirmed_roofs_neutral(self):
  from datetime import datetime, timezone
  from urllib.parse import urlparse, parse_qs
  import football_weather as weather
  venue={'name':'Test Stadium','lat':42.8,'lon':-78.8,'indoor':False}
  start='2026-11-27T01:20Z'
  games=[{'id':sport,'sport':sport,'start':start,'venue':venue} for sport in ('NFL','NCAAF')]
  games += [
   {'id':'dome','sport':'NFL','start':start,'venue':{**venue,'indoor':True}},
   {'id':'retractable','sport':'NFL','start':start,'venue':{**venue,'name':'AT&T Stadium'}},
   {'id':'late','sport':'NCAAF','start':'2026-11-28T01:20Z','venue':venue},
  ]
  calls=[]
  def fetch(url):
   calls.append(url)
   self.assertIn('wind_gusts_10m',parse_qs(urlparse(url).query)['hourly'][0])
   return {'hourly':{'time':['2026-11-27T01:00','2026-11-27T02:00'],
    'temperature_2m':[38,35],'wind_speed_10m':[15,18],'wind_gusts_10m':[25,35],'precipitation':[0,2.5]}}
  cache={}
  now=datetime(2026,11,27,tzinfo=timezone.utc)
  weather.collect(games,cache,fetch,p.parallel,now)
  self.assertEqual(len(calls),1)
  for game in games[:2]:
   wx=game['weather']
   self.assertEqual((wx['status'],wx['temperature_f'],wx['wind_mph'],wx['gust_mph'],wx['precip_mm']),
                    ('Kickoff forecast used',37,16,35,2.5))
   self.assertLess(wx['pass_efficiency'],1)
   self.assertLess(weather.market_factors('Receiving yards',wx)[0],1)
   self.assertGreater(weather.market_factors('Rushing yards',wx)[0],1)
   game.update(home={'id':'h','name':'Home'},away={'id':'a','name':'Away'})
   _, evidence=p.team_factors({},game,'home')
   self.assertLess(evidence['weather_adjustment'],0)
   rows=[{'start':f'2026-11-{d:02d}T12:00Z','stats':{'Passing yards':230+d,'Pass attempts':32}}
         for d in range(1,11)]
   calm=p.actuarial.fit(rows,{},game['sport'],'Passing yards','p','p')
   wet=p.actuarial.fit(rows,{},game['sport'],'Passing yards','p','p',weather_volume=wx['pass_volume'],weather_rate=wx['pass_efficiency'])
   self.assertLess(wet['projection'],calm['projection'])
   self.assertLess(p.actuarial.price(wet['evidence'],225.5,'Over')['probability'],
                   p.actuarial.price(calm['evidence'],225.5,'Over')['probability'])
  self.assertEqual([g['weather']['roof'] for g in games[2:4]],['indoor','unknown'])
  for game in games[2:]:
   self.assertEqual(weather.market_factors('Passing yards',game['weather']),(1,1))


class FootballAvailabilityRegression(unittest.TestCase):
 def test_confirmed_release_marks_prior_starter_and_revises_team_prior(self):
  fixture={'id':'NFL:401873083','sport':'NFL','start':'2026-11-27T20:00Z',
           'home':{'id':'23','name':'Steelers'},'away':{'id':'7','name':'Broncos'}}
  events={};boxes={}
  for day in range(14,18):
   eid=f'NFL:{day}'
   events[eid]={'id':eid,'sport':'NFL','start':f'2026-11-{day}T20:00Z','final':True,'event':'Past game',
                'home':{'id':'23','name':'Steelers','score':30},'away':{'id':'7','name':'Broncos','score':20}}
   boxes[eid]=[{'team_id':'23','player_id':'8439','stats':{'Pass attempts':32}}]
  defense={'team_id':'23','player_id':'def','player':'Defensive player','position':'LB','status':'Inactive'}
  rows=p.reconcile_football_availability(events,fixture,boxes,[defense])
  effects=p.injury_impact(events,fixture,boxes,rows)
  self.assertEqual(effects['home']['confirmed_qb']['player'],'Mason Rudolph')
  self.assertEqual(effects['home']['players'][0]['status'],'Inactive')
  self.assertIsNone(effects['home']['players'][0]['points'])
  self.assertLess(effects['home']['points'],0)
  self.assertGreater(effects['home']['uncertainty'],0)
  baseline=p.team_factors(events,fixture,'home')[0]
  fixture['availability_impact']=effects
  self.assertLess(p.team_factors(events,fixture,'home')[0],baseline)
