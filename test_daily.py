import unittest,copy,datetime as dt,tempfile,json,gzip
from pathlib import Path
import daily_picks as d,record_store as store,analytics as a,weather
NOW='2026-11-11T12:00:00+00:00';DAY='2026-11-11'
def row(i=0,**kw):
 return dict(id=str(i),event_id=f'NBA:{i}',sport='NBA',selection='Team '+str(i),market='Moneyline',side='Win',line=None,start='2026-11-11T20:00:00Z',day=DAY,probability=.65,odds=-110,bookmaker='FanDuel',fanduel_verified=True,book_state='IN',quote_source_url='https://sportsbook.fanduel.com/',price_kind='Observed snapshot',odds_updated=NOW,observed_at=NOW,sample=20,edge_pp=12.62,conservative_edge_pp=6,expected_roi_pct=24,conservative_roi_pct=12,flags=[],**kw)
def pool(n):
 return [row(i) for i in range(n)]+[row(i)|{'id':str(i)+'-alt','probability':.97,'probability_floor':.94,'odds':-500,'edge_pp':13.67,'conservative_edge_pp':10.67,'expected_roi_pct':16.4} for i in range(n)]
class Daily(unittest.TestCase):
 def test_quote_gates(self):
  base=row();self.assertTrue(d.eligible(base,DAY,NOW))
  for changes in [dict(fanduel_verified=False),dict(bookmaker='DraftKings'),dict(book_state='NJ'),dict(price_kind='Suggested line'),dict(odds=-1500),dict(sample=9),dict(flags=['Role changed']),dict(odds_updated='2026-11-11T10:00:00Z'),dict(start='2026-11-11T12:05:00Z'),dict(edge_pp=20),dict(conservative_edge_pp=0)]:
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
 def test_below_target_combinations_are_transparent(self):
  ledger=[];d.update(ledger,[row(i) for i in range(10)],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual([t['leg_count'] for t in ledger],list(range(1,11)));self.assertFalse(ledger[1]['target_met']);self.assertAlmostEqual(ledger[1]['probability'],.65**2)
 def test_confidence_beats_high_payout(self):
  ledger=[];d.update(ledger,[row(0)|{'probability':.45,'conservative_roi_pct':100},row(1)],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual(ledger[0]['legs'][0]['event_id'],'NBA:1')
 def test_old_policy_preserved_and_graded(self):
  old=[];d.update(old,[row()],DAY,NOW,{}, {},lambda *x:None);old[0]['policy_version']='old';prior=copy.deepcopy(old[0])
  current,_,_=d.update(old,[row(1)],DAY,NOW,{}, {},lambda *x:None)
  self.assertEqual(old[0],prior);self.assertEqual(len(old),2);self.assertEqual(len(current),1)
 def test_week_ahead_and_cutoff(self):
  self.assertTrue(d.eligible(row()|{'start':'2026-11-16T20:00:00Z','day':'2026-11-16'},DAY,NOW))
  self.assertFalse(d.eligible(row()|{'start':'2026-11-19T20:00:00Z','day':'2026-11-19'},DAY,NOW))
 def test_unpriced_research_records_no_roi(self):
  ledger=[];rs=[row(i)|{'odds':None,'player_id':str(i),'probability':.85} for i in range(3)]
  tickets,_=d.update_research(ledger,rs,DAY,NOW,{}, {},lambda *x:None);self.assertEqual(len(tickets),2)
  old=copy.deepcopy(ledger);d.update_research(ledger,rs,DAY,NOW,{}, {},lambda *x:None);self.assertEqual(ledger,old)
  _,s=d.update_research(ledger,[],DAY,NOW,{f'NBA:{i}':{'final':True} for i in range(3)}, {},lambda *x:1)
  self.assertEqual(s['NBA']['2']['win_rate'],1);self.assertIsNone(ledger[0]['profit_units'])
 def test_perfect_sizes_rank_freeze_and_grade(self):
  ledger=[];rs=[row(i)|{'odds':None,'player_id':str(i),'probability':.95,'hit_rate':1} for i in range(12)]
  ts,_=d.update_research(ledger,rs,DAY,NOW,{}, {},lambda *x:None,sizes=(5,7,9),policy='perfect-history-v1')
  self.assertEqual([t['leg_count'] for t in ts],[5,7,9]);self.assertTrue(all(len({r['event_id'] for r in t['legs']})==t['leg_count'] for t in ts))
  old=copy.deepcopy(ledger);d.update_research(ledger,list(reversed(rs)),DAY,NOW,{}, {},lambda *x:None,sizes=(5,7,9),policy='perfect-history-v1');self.assertEqual(ledger,old)
  _,summary=d.update_research(ledger,[],DAY,NOW,{f'NBA:{i}':{'final':True} for i in range(12)}, {},lambda r,e,b:0 if r['player_id']=='8' else 1,sizes=(5,7,9),policy='perfect-history-v1')
  self.assertEqual(summary['NBA']['5']['win_rate'],1);self.assertEqual(summary['NBA']['9']['win_rate'],0);self.assertTrue(all(t['profit_units'] is None for t in ledger))
 def test_estimated_single_screen_and_frozen_evidence(self):
  good=row()|{'odds':None,'side':'Over','player_id':'p','hit_rate':.7,'probability_floor':.60,'rationale':{'notes':['Original evidence']}}
  self.assertEqual(d.estimated_singles([good],NOW),[good])
  for change in [{'side':'Under'},{'probability':.85},{'hit_rate':.4},{'flags':['Role changed']},{'sample':9},{'odds':-110}]:
   self.assertEqual(d.estimated_singles([good|change],NOW),[])
  ledger=[];ts,_=d.update_research(ledger,[good],DAY,NOW,{}, {},lambda *x:None,sizes=(1,),policy='estimated-best-v1')
  self.assertEqual(ts[0]['legs'][0]['rationale'],good['rationale']);old=copy.deepcopy(ledger)
  d.update_research(ledger,[good|{'line':99}],DAY,NOW,{}, {},lambda *x:None,sizes=(1,),policy='estimated-best-v1');self.assertEqual(ledger,old)
  _,m=d.update_research(ledger,[],DAY,NOW,{good['event_id']:{'final':True}}, {},lambda *x:1,sizes=(1,),policy='estimated-best-v1')
  self.assertEqual(m['NBA']['1']['win_rate'],1);self.assertIsNone(ledger[0]['profit_units'])
 def test_over_policy_replaces_display_not_history(self):
  ledger=[];under=row()|{'player_id':'p','side':'Under','odds':None};over=row(1)|{'player_id':'q','side':'Over','odds':None}
  old,_=d.update_research(ledger,[under],DAY,NOW,{}, {},lambda *x:None,sizes=(1,),policy='old')
  frozen=copy.deepcopy(old[0]);current,_=d.update_research(ledger,[under,over],DAY,NOW,{}, {},lambda *x:None,sizes=(1,),policy='overs-v2',over_only=True)
  self.assertEqual(ledger[0],frozen);self.assertEqual(len(current),1);self.assertEqual(current[0]['legs'][0]['side'],'Over')
  d.update_research(ledger,[],DAY,NOW,{under['event_id']:{'final':True}}, {},lambda *x:0,sizes=(1,),policy='overs-v2',over_only=True)
  self.assertEqual(ledger[0]['result'],'loss')
 def test_daily_slate_and_sunday_release(self):
  rs=[row()|{'sport':'NBA'},row(1)|{'sport':'NBA','start':'2026-11-12T20:00:00Z'},row(2)|{'sport':'NFL','start':'2026-11-12T20:00:00Z'},row(3)|{'sport':'NFL','start':'2026-11-15T20:00:00Z'}]
  days=d.selection_days(rs,NOW);self.assertEqual(days['NBA'],DAY);self.assertEqual(days['NFL'],'2026-11-12');self.assertFalse(d.in_selection_day(rs[1],days))
  sunday=[rs[-1]];self.assertIsNone(d.selection_days(sunday,'2026-11-13T12:00:00Z')['NFL']);self.assertEqual(d.selection_days(sunday,'2026-11-14T12:00:00Z')['NFL'],'2026-11-15')
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
