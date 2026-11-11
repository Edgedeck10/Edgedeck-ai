"""Immutable daily model-selection ledger. Singles and each parlay size graded separately."""
import math,datetime as dt
from collections import defaultdict
POLICY='daily-v1-quoted-200';SPORTS=['NBA','NFL','NHL','MLB','NCAAB','NCAAF','WNBA','EPL','MLS','PGA','ATP','WTA','UFC']
def timestamp(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def decimal(o):return 1+100/abs(o) if o<0 else 1+o/100
def odds_from_decimal(d):return round((d-1)*100) if d>=2 else round(-100/(d-1))
def price_band(o):return isinstance(o,(int,float)) and 100<=abs(o)<=200
def wilson(w,n):
 if not n:return [None,None]
 z=1.96;den=1+z*z/n;c=(w/n+z*z/(2*n))/den;h=z*math.sqrt((w/n)*(1-w/n)/n+z*z/(4*n*n))/den;return [max(0,c-h),min(1,c+h)]
def eligible(r,day,now):
 if r.get('day')!=day or not price_band(r.get('odds')) or r.get('sample',0)<10:return False
 if r.get('price_kind')!='Observed snapshot':return False
 if any(x.lower() in ('questionable','doubtful','out','minutes volatility','role changed','outlier-sensitive','starter unconfirmed','opportunity data missing') for x in r.get('flags',[])):return False
 try:
  if timestamp(r['start'])<=timestamp(now)+dt.timedelta(minutes=10):return False
  if not dt.timedelta(0)<=timestamp(now)-timestamp(r.get('odds_updated') or r['observed_at'])<=dt.timedelta(minutes=35):return False
 except (ValueError,KeyError,TypeError):return False
 return (r.get('conservative_edge_pp') or 0)>0 and 3<=(r.get('edge_pp') or 0)<=15 and (r.get('expected_roi_pct') or 0)>=5

def freeze_leg(r):
 keys=['id','event_id','sport','market','side','line','selection','event','player_id','team_id','start','day','probability','raw_probability','probability_floor','odds','bookmaker','odds_updated','observed_at','edge_pp','conservative_edge_pp','expected_roi_pct','model_version','sample','price_kind','source_url']
 return {k:r[k] for k in keys if k in r}|{'outcome':None}

def update(records,rows,day,now,events,box,settle):
 # Never overwrite selection, odds, forecast or original timestamp of an existing ticket.
 for ticket in records:
  if ticket.get('result') is not None:continue
  for leg in ticket['legs']:
   if leg.get('outcome') is not None:continue
   event=events.get(leg['event_id'])
   if event:
    outcome=settle(leg,event,box)
    if outcome is not None:leg['outcome']=outcome;leg['graded_at']=now
  outcomes=[r.get('outcome') for r in ticket['legs']]
  if 0 in outcomes:result='loss'
  elif any(x is None for x in outcomes):continue
  elif all(x=='push' for x in outcomes):result='push'
  else:result='win'
  ticket['result']=result;ticket['graded_at']=now
  active=[r for r in ticket['legs'] if r['outcome']!='push'];d=math.prod(decimal(r['odds']) for r in active)
  ticket['profit_units']=-1 if result=='loss' else 0 if result=='push' else round(d-1,4)
  ticket['settled_leg_product_decimal']=round(d,4)
 current=[];seen={(r['day'],r['sport'],r['leg_count']) for r in records};availability={}
 for sport in SPORTS:
  pool=sorted([r for r in rows if r['sport']==sport and eligible(r,day,now)],key=lambda r:(r.get('conservative_roi_pct') or 0,r.get('conservative_edge_pp') or 0,r.get('sample',0)),reverse=True)
  diverse=[];games=set();players=set()
  for r in pool:
   if r['event_id'] in games or r.get('player_id') and r['player_id'] in players:continue
   diverse.append(r);games.add(r['event_id'])
   if r.get('player_id'):players.add(r['player_id'])
  availability[sport]={'eligible_games':len(diverse),'reason':'Qualified quoted selections with 10+ samples, +200 to -200 odds, positive risk-buffered edge and 10+ minutes before start.' if diverse else 'No qualified quoted selection at +200 to -200 yet. No estimated prices or filler selections are used for the official daily record.'}
  for size in range(1,11):
   key=(day,sport,size)
   if key in seen or len(diverse)<size:continue
   legs=[freeze_leg(r) for r in diverse[:size]];p=math.prod(r['probability'] for r in legs);d=math.prod(decimal(r['odds']) for r in legs)
   ticket={'id':f'{day}:{sport}:{size}','policy_version':POLICY,'day':day,'sport':sport,'leg_count':size,'created_at':now,'legs':legs,'probability':round(p,6),'probability_method':'Single forecast' if size==1 else 'Independent leg product; not correlation adjusted','display_odds':legs[0]['odds'] if size==1 else odds_from_decimal(d),'leg_product_decimal':round(d,5),'price_type':'Observed single quote' if size==1 else 'Quoted-leg product estimate, not a sportsbook parlay quote','result':None,'profit_units':None,'model_version':legs[0].get('model_version'),'selection_method':'Ranked by buffered expected return; one selection per event, no repeated player. Not an exhaustive optimizer.'}
   records.append(ticket);seen.add(key)
 current=[r for r in records if r['day']==day]
 summaries={}
 for sport in SPORTS:
  summaries[sport]={}
  for size in range(1,11):
   ts=[r for r in records if r['sport']==sport and r['leg_count']==size];won=sum(r.get('result')=='win' for r in ts);lost=sum(r.get('result')=='loss' for r in ts);push=sum(r.get('result')=='push' for r in ts);settled=won+lost
   summaries[sport][str(size)]={'tracked':len(ts),'wins':won,'losses':lost,'pushes':push,'pending':sum(r.get('result') is None for r in ts),'win_rate':won/settled if settled else None,'ci95':wilson(won,settled),'profit_units':round(sum(r.get('profit_units') or 0 for r in ts),4),'roi_pct':round(100*sum(r.get('profit_units') or 0 for r in ts)/settled,2) if settled else None,'sample_status':'Too early to judge' if settled<30 else 'Sample accumulating; inspect uncertainty','goal':[.85,.90] if size==1 else [.65,.80]}
 return current,summaries,availability
