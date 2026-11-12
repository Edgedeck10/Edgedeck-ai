"""Prospective per-game AI selections and cautious, holdout-gated calibration."""
import math,statistics as st
from collections import defaultdict
GROUPS={'NFL':'Pro Football','CFL':'Pro Football','UFL':'Pro Football','NCAAF':'College Football','NBA':'Pro Basketball','WNBA':'Pro Basketball','NCAAB':'College Basketball','NCAAW':'College Basketball','NHL':'Hockey','MLB':'Baseball','EPL':'Soccer','MLS':'Soccer','PGA':'Golf','LPGA':'Golf'}
def mean(xs):return st.mean(xs) if xs else None
def choose(rows):
 candidates=[r for r in rows if (not r.get('player_id') or r['side']=='Over' and r['line']==r.get('base_line')) and -200<=(r.get('odds') if r.get('odds') is not None else r.get('fair_odds',-99999))<=200 and not any(str(f).lower() in ('out','suspended','injured reserve','questionable','doubtful') for f in r.get('flags',[]))]
 candidates.sort(key=lambda r:(-(r.get('odds') is not None and (r.get('expected_roi_pct') or 0)>0),-bool(r.get('player_id')),-(r.get('expected_roi_pct') or 0) if r.get('odds') is not None else 0,-r.get('sample',0),-r['probability']))
 seen=set();result=[]
 for r in candidates:
  key=('player',r['player_id']) if r.get('player_id') else ('market',r['market'],r.get('team_id','game'))
  if key in seen:continue
  seen.add(key);result.append(r)
  if len(result)==5:break
 return result

def calibration(ledger,before):
 groups=defaultdict(list)
 for r in ledger:
  if r.get('outcome') in (0,1) and r.get('graded_at','')<before and r.get('model_version')=='opportunity-4.2.0':groups[(r['sport'],r['market'])].append(r)
 output={}
 for (sport,market),rs in groups.items():
  rs.sort(key=lambda r:r['start']);days=sorted(set(r['start'][:10] for r in rs));applied=0.;train_n=0;hold_n=0;raw=None;adjusted=None
  if len(rs)>=30 and len(days)>=10:
   cut=days[max(1,int(len(days)*.7))];train=[r for r in rs if r['start'][:10]<cut];hold=[r for r in rs if r['start'][:10]>=cut];train_n=len(train);hold_n=len(hold)
   p=lambda r:r.get('raw_ai_probability',r['probability'])/max(1e-9,1-r.get('push_probability',0))
   bias=max(-.05,min(.05,st.mean(r['outcome']-p(r) for r in train)*len(train)/(len(train)+100)))
   clamp=lambda p:max(.001,min(.999,p))
   raw=mean([(p(r)-r['outcome'])**2 for r in hold]);adjusted=mean([(clamp(p(r)+bias)-r['outcome'])**2 for r in hold])
   if adjusted<raw:applied=bias
  output[sport+'|'+market]={'conditional_probability_offset':applied,'samples':len(rs),'game_dates':len(days),'training_picks':train_n,'holdout_picks':hold_n,'baseline_brier':raw,'adjusted_brier':adjusted,'status':'Active: later-date Brier improved' if applied else 'Monitoring: insufficient evidence or no holdout improvement','scope':'Bias correction only, maximum 5 percentage points. Activation holdout is not an untouched accuracy test; no causal diagnosis.'}
 return output

def apply(row,learning):
 rule=learning.get(row['sport']+'|'+row['market']);row['raw_ai_probability']=row['probability'];row['learning_offset']=0.
 if not rule or not rule['conditional_probability_offset']:return
 push=row.get('push_probability',0);old=row['probability'];q=old/max(1e-9,1-push);q=max(.001,min(.999,q+rule['conditional_probability_offset']));p=q*(1-push)
 row['learning_offset']=p-old;row['probability']=p;row['learning_evidence']=rule
 row['fair_odds']=round(-100*q/(1-q)) if q>=.5 else round(100*(1-q)/q)
 if row.get('odds') is not None:
  odds=row['odds'];profit=100/abs(odds) if odds<0 else odds/100
  row['expected_roi_pct']=100*(p*profit-(1-p-push));row['edge_pp']=100*(q-(abs(odds)/(abs(odds)+100) if odds<0 else 100/(odds+100)))

def summarize(ledger):
 groups=defaultdict(list)
 for r in ledger:
  groups['Overall'].append(r);groups[GROUPS.get(r['sport'],r['sport'])].append(r)
 def summary(label,rs):
  settled=[r for r in rs if r.get('outcome') in (0,1)];priced=[r for r in settled if r.get('odds') is not None];pushes=sum(r.get('outcome')=='push' for r in rs);wins=sum(r['outcome'] for r in settled)
  actual=[r for r in settled if r.get('actual_value') is not None and r.get('projection') is not None]
  residual=[r['actual_value']-r['projection'] for r in actual]
  return {'sport':label,'wins':wins,'losses':len(settled)-wins,'pushes':pushes,'pending':sum(r.get('outcome') is None for r in rs),'hit_rate':wins/len(settled) if settled else None,'games':len(set(r['event_id'] for r in rs)),'priced_settled':len(priced),'profit_units':sum(r.get('profit_units',0) or 0 for r in priced),'roi_pct':100*sum(r.get('profit_units',0) or 0 for r in priced)/len(priced) if priced else None,'brier':mean([(r['probability']/max(1e-9,1-r.get('push_probability',0))-r['outcome'])**2 for r in settled]),'mae':mean([abs(x) for x in residual]),'projection_bias':mean(residual),'mae_note':'Mixed units across markets; use market diagnostics for comparable errors.'}
 records=[summary(label,groups.get(label,[])) for label in ['Overall',*dict.fromkeys(GROUPS.values())]]
 bundles=[];events=defaultdict(list)
 for r in ledger:events[r['event_id']].append(r)
 for eid,rs in events.items():
  outcomes=[r.get('outcome') for r in rs];result=0 if 0 in outcomes else None if None in outcomes else 'push' if all(o=='push' for o in outcomes) else 1
  bundles.append({'event':rs[0]['event'],'sport':GROUPS.get(rs[0]['sport'],rs[0]['sport']),'legs':len(rs),'outcome':result})
 diagnostics=[];markets=defaultdict(list)
 for r in ledger:markets[(r['sport'],r['market'])].append(r)
 for (sport,market),rs in markets.items():
  x=summary(sport+' · '+market,rs);loss=[r for r in rs if r.get('outcome')==0];x['high_confidence_misses']=sum(r['probability']>=.7 for r in loss);x['flagged_misses']=sum(bool(r.get('flags')) for r in loss);x['interpretation']='Review calibration, workload and missing inputs; losses alone do not identify their cause.';diagnostics.append(x)
 return {'records':records,'market_diagnostics':diagnostics,'bundles':bundles,'scope':'First published AI top picks per game, prospectively frozen. Not all alternate thresholds or user tickets. No retrospective top-pick reconstruction.'}
