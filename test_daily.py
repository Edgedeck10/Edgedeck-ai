import unittest,copy,datetime as dt,tempfile,json,gzip
from pathlib import Path
import daily_picks as d,record_store as store,analytics as a,weather
NOW='2026-11-11T12:00:00+00:00';DAY='2026-11-11'
def row(i=0,**kw):
 return dict(id=str(i),event_id=f'NBA:{i}',sport='NBA',selection='Team '+str(i),market='Moneyline',side='Win',line=None,start='2026-11-11T20:00:00Z',day=DAY,probability=.65,odds=-110,bookmaker='Test quote',price_kind='Observed snapshot',odds_updated=NOW,observed_at=NOW,sample=20,edge_pp=12.62,conservative_edge_pp=6,expected_roi_pct=24,conservative_roi_pct=12,flags=[],**kw)
def pool(n):
 return [row(i) for i in range(n)]+[row(i)|{'id':str(i)+'-alt','probability':.97,'probability_floor':.94,'odds':-500,'edge_pp':13.67,'conservative_edge_pp':10.67,'expected_roi_pct':16.4} for i in range(n)]
class Daily(unittest.TestCase):
 def test_quote_gates(self):
  base=row();self.assertTrue(d.eligible(base,DAY,NOW))
  for changes in [dict(price_kind='Suggested line'),dict(odds=-1500),dict(sample=9),dict(flags=['Role changed']),dict(odds_updated='2026-11-11T10:00:00Z'),dict(start='2026-11-11T12:05:00Z'),dict(edge_pp=20),dict(conservative_edge_pp=0)]:
   self.assertFalse(d.eligible(base|changes,DAY,NOW),changes)
 def test_freeze_and_all_sizes(self):
  ledger=[];rows=pool(10);cur,_,_=d.update(ledger,rows,DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual([t['leg_count'] for t in cur],list(range(1,11)));frozen=copy.deepcopy(ledger)
  d.update(ledger,rows,DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual(ledger,frozen);self.assertAlmostEqual(cur[4]['probability'],.97**5,places=6)
 def test_grade_pushes_and_denominators(self):
  ledger=[];d.update(ledger,pool(5),DAY,NOW,{}, {},lambda *x:None)
  events={f'NBA:{i}':{'i':i} for i in range(5)}
  _,s,_=d.update(ledger,[],DAY,NOW,events,{},lambda r,e,b:'push' if e['i']==0 else 0 if e['i']==3 else 1)
  self.assertEqual(ledger[0]['result'],'push');self.assertIsNone(s['NBA']['1']['win_rate']);self.assertEqual(s['NBA']['2']['win_rate'],1);self.assertEqual(s['NBA']['5']['win_rate'],0);self.assertEqual(s['NBA']['5']['profit_units'],-1)
  self.assertAlmostEqual(ledger[1]['profit_units'],100/500,places=4)
 def test_loss_with_unresolved_legs(self):
  ledger=[];d.update(ledger,pool(3),DAY,NOW,{}, {},lambda *x:None)
  d.update(ledger,[],DAY,NOW,{'NBA:0':{}},{},lambda *x:0)
  # empty event is ignored; proper completed event is necessary
  self.assertIsNone(ledger[2]['result'])
  d.update(ledger,[],DAY,NOW,{'NBA:0':{'final':True}},{},lambda *x:0)
  self.assertEqual(ledger[2]['result'],'loss')
 def test_no_filler_or_duplicate_game(self):
  ledger=[];d.update(ledger,[row(),row()|{'id':'duplicate'},row(1)|{'sport':'NFL'}],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual(len(ledger),2);self.assertTrue(all(t['leg_count']==1 for t in ledger))
 def test_low_probability_parlays_abstain(self):
  ledger=[];d.update(ledger,[row(i) for i in range(10)],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual([t['leg_count'] for t in ledger],[1])
 def test_confidence_beats_high_payout(self):
  ledger=[];d.update(ledger,[row(0)|{'probability':.45,'conservative_roi_pct':100},row(1)],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual(ledger[0]['legs'][0]['event_id'],'NBA:1')
 def test_old_policy_preserved_and_graded(self):
  old=[];d.update(old,[row()],DAY,NOW,{}, {},lambda *x:None);old[0]['policy_version']='old';prior=copy.deepcopy(old[0])
  current,_,_=d.update(old,[row(1)],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual(old[0],prior);self.assertEqual(len(old),2);self.assertEqual(len(current),1)
 def test_archive_lossless(self):
  rs=[{'id':str(i),'start':'2026-11-11T00:00Z','probability':.6,'outcome':None} for i in range(5010)]
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'history.json').write_text(json.dumps(rs));self.assertEqual(store.read_history(p),rs);store.write_history(p,rs)
   self.assertEqual(store.read_history(p),rs);self.assertEqual(len(json.loads((p/'history.json').read_text())),5000)
   first=(p/'history_archive/2026-11.json.gz').read_bytes();store.write_history(p,rs);self.assertEqual(first,(p/'history_archive/2026-11.json.gz').read_bytes())
 def test_compressed_feed(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);report={'version':'test','generated_at':NOW,'recommendations':[{'id':'a','probability':.6,'context':{'real':'data'}}],'games':[]}
   (p/'latest.json').write_text('old');store.write_report(p,report)
   self.assertFalse((p/'latest.json').exists());actual=json.loads(gzip.decompress((p/'latest.json.gz').read_bytes()))
   self.assertEqual(actual['recommendations'][0]['probability'],.6);self.assertEqual(actual['model_details']['|||']['context'],{'real':'data'})
 def test_normalization_rehydrates_models(self):
  rows=[dict(log_key='test',context={'audit':'same'},sample=20,side=s,line=l,flags=[]) for s,l in [('Over',15.5),('Under',20.5)]]
  report={'recommendations':copy.deepcopy(rows),'games':[]};store.normalize_report(report)
  self.assertEqual([{**report['model_details'][r['details_key']],**{k:v for k,v in r.items() if k!='details_key'}} for r in report['recommendations']],rows)
 def test_null_venue_state_is_safe(self):
  game={'id':'MLS:1','sport':'MLS','start':'2026-11-11T20:00:00Z','venue':{'city':'Columbus','state':None}}
  result=weather.collect([game],{},lambda u:{},dt.datetime.fromisoformat(NOW))
  self.assertEqual(result['MLS:1']['factor'],1)
 def test_role_and_weather_checks(self):
  pairs=[({'start':f'2026-11-{i+1:02}T00:00Z','stats':{'Minutes':20 if i<10 else 35}},10) for i in range(15)]
  self.assertIn('Role changed',a.sample_audit(pairs)['flags'])
  w={'roof_confirmed':True,'wind_mph':25,'precip_mm':3}
  self.assertAlmostEqual(weather.adjustment('NFL','Passing yards',w),.97*.98)
  self.assertEqual(weather.adjustment('NFL','Passing yards',w|{'indoor':True}),1)
  self.assertEqual(weather.adjustment('NFL','Passing yards',w|{'roof_confirmed':False}),1)
if __name__=='__main__':unittest.main()
