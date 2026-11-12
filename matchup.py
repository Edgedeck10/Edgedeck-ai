"""Chronological opponent-rate adjustment. No invented advanced inputs."""
from bisect import bisect_left
from collections import defaultdict
import statistics as st
import actuarial
CACHE={}
class Index:
 def __init__(self,records,events,sport,market):
  self.groups=defaultdict(list)
  for rs in records.values():
   pairs,unit,family=actuarial.pairs_for(rs,sport,market)
   for r,y,x in pairs:
    e=events.get(r['event_id'],{});home=e.get('home',{});away=e.get('away',{})
    opponent=away.get('id') if r['team_id']==home.get('id') else home.get('id') if r['team_id']==away.get('id') else None
    if not opponent:continue
    self.groups[opponent].append((r['start'],y,x,r['event_id']))
    self.groups['*'].append((r['start'],y,x,r['event_id']))
  for key,rows in list(self.groups.items()):
   by=defaultdict(lambda:[0.,0.])
   for date,y,x,eid in rows:by[(date,eid)][0]+=y;by[(date,eid)][1]+=x
   totals=sorted((date,y,x) for (date,eid),(y,x) in by.items());dates=[];ys=[0.];xs=[0.]
   for date,y,x in totals:dates.append(date);ys.append(ys[-1]+y);xs.append(xs[-1]+x)
   self.groups[key]=(dates,ys,xs)
 def rate(self,key,before):
  if key not in self.groups:return None,0
  dates,ys,xs=self.groups[key];i=bisect_left(dates,before);lo=max(0,i-25)
  return ((ys[i]-ys[lo])/(xs[i]-xs[lo]),i-lo) if xs[i]>xs[lo] else (None,0)
 def ratio(self,opponent,before):
  a,n=self.rate(opponent,before);b,_=self.rate('*',before)
  return (a/b,n,a,b) if a is not None and b and n>=5 else (None,n,a,b)
def opponent_of(r,events):
 e=events.get(r['event_id'],{});h=e.get('home',{});a=e.get('away',{})
 return a.get('id') if h.get('id')==r['team_id'] else h.get('id') if a.get('id')==r['team_id'] else None

def evaluate(games,records,events,event,sport,market,team_id):
 # Each historical feature is queried strictly before its target game's start.
 token=(sport,market,event['start'][:10],sum(len(rs) for rs in records.values()))
 if token not in CACHE:CACHE[token]=Index(records,events,sport,market)
 index=CACHE[token];pairs,unit,family=actuarial.pairs_for(games,sport,market);pairs=pairs[-60:]
 upcoming=event['away' if event['home']['id']==team_id else 'home']['id']
 ratio,n,opp,league=index.ratio(upcoming,event['start']);origins=[]
 for i in range(10,len(pairs)):
  r,y,x=pairs[i];sample=pairs[max(0,i-20):i];base=st.mean(v for _,v,_ in sample)
  raw,_,_,_=index.ratio(opponent_of(r,events),r['start'])
  if raw is not None:origins.append((base,raw,y))
 applied=0.;selected=0.;baseline_mae=None;adjusted_mae=None;tune_n=0;hold_n=0
 if len(origins)>=10:
  split=int(len(origins)*.7);train=origins[:split];hold=origins[split:];tune_n=len(train);hold_n=len(hold)
  error=lambda rows,alpha:st.mean(abs(y-base*(1+alpha*(raw-1))) for base,raw,y in rows)
  selected=min((0.,.25,.5,1.),key=lambda a:(error(train,a),a))
  baseline_mae=error(hold,0);adjusted_mae=error(hold,selected)
  if adjusted_mae<baseline_mae:applied=selected
 multiplier=1+applied*(ratio-1) if ratio is not None else 1.
 # Unsupported signed/finite ratios are not used when the observed baseline is nonpositive.
 if multiplier<=0:multiplier=1.;applied=0.
 form={str(w):{'games':len(pairs[-w:]),'production_mean':st.mean(y for _,y,x in pairs[-w:]),'opportunity_mean':st.mean(x for _,y,x in pairs[-w:]),'rate':sum(y for _,y,x in pairs[-w:])/sum(x for _,y,x in pairs[-w:])} for w in (5,10,20,25) if pairs}
 splits={}
 for venue in ('home','away'):
  subset=[(r,y,x) for r,y,x in pairs if ('home' if events.get(r['event_id'],{}).get('home',{}).get('id')==r['team_id'] else 'away' if events.get(r['event_id'],{}).get('away',{}).get('id')==r['team_id'] else 'unknown')==venue]
  if subset:splits[venue]={'games':len(subset),'production_mean':st.mean(y for _,y,x in subset),'rate':sum(y for _,y,x in subset)/sum(x for _,y,x in subset)}
 return {'multiplier':multiplier,'opponent_rate':opp,'league_rate':league,'opponent_games':n,'opportunity_unit':unit,'selected_strength':selected,'applied_strength':applied,'tuning_games':tune_n,'holdout_games':hold_n,'baseline_holdout_mae':baseline_mae,'adjusted_holdout_mae':adjusted_mae,'status':'Applied: improved later holdout' if applied and ratio is not None else 'Not applied: missing data or no holdout improvement','scope':'Opponent allowance per opportunity across available players; not position-adjusted. Holdout is an activation gate, not an untouched accuracy test. No pace bonus is stacked onto this rate.','form_windows':form,'venue_splits':splits,'venue_adjustment_applied':False}
