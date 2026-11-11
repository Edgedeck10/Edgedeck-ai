"""Pure projection and value utilities. Heuristic adjustments remain explicitly provisional."""
import math,statistics as st
from collections import defaultdict
BASKET={'NBA','WNBA','NCAAB'}
PRICE_LADDER=[100,-110,-150,-200,-300,-500,-750,-1000,-1500]
def clamp(x,a,b):return max(a,min(b,x))
def avg(v,default=0):return st.mean(v) if v else default
def position_group(sport,pos):
 p=(pos or '').upper().replace(' ','')
 if sport in BASKET:
  if p in ('PG','SG','G','G-F','GF'):return 'G'
  if p in ('SF','PF','F','F-G','F-C','FC'):return 'F'
  if p in ('C','C-F'):return 'C'
 if sport=='NHL':return 'F' if p in ('C','LW','RW','W','F') else p
 return p or 'Unknown'
def opportunities(market,sport,stats):
 if sport in BASKET:return 'Minutes',stats.get('Minutes')
 keys={'Passing yards':'Pass attempts','Completions':'Pass attempts','Rushing yards':'Rush attempts','Receiving yards':'Targets','Receptions':'Targets','Touchdowns':'Touches','Shots on goal':'Minutes','Goals':'Minutes','Assists':'Minutes','Saves':'Shots faced','Strikeouts':'Innings','Hits':'Plate appearances','Home runs':'Plate appearances','Runs':'Plate appearances','RBIs':'Plate appearances'}
 unit=keys.get(market,'Games');return unit,stats.get(unit) if unit!='Games' else 1

def build_matchups(events,box,positions,expand,now):
 """Allowed production / actual position-minutes (or opportunities), vs same-role league rate.
 Current roster positions fill legacy box rows. These are role buckets, not on-ball assignments.
 """
 league=defaultdict(lambda:[0.,0.,set()]);defense=defaultdict(lambda:[0.,0.,set()]);coverage=defaultdict(lambda:[0,0])
 for eid,rows in box.items():
  e=events.get(eid)
  if not e or not e.get('final') or not e.get('start') or e['start']>=now:continue
  sport=e['sport']
  for r in rows:
   stats=expand(r['stats']);pos=position_group(sport,r.get('position') or positions.get(sport+':'+r['player_id']));coverage[sport][1]+=1
   if pos=='Unknown':continue
   coverage[sport][0]+=1
   opp=e['away']['id'] if r['team_id']==e['home']['id'] else e['home']['id']
   for market,val in stats.items():
    if market in ('Minutes','Pass attempts','Rush attempts','Targets','Touches','Innings','Plate appearances','Shots faced'):continue
    unit,exposure=opportunities(market,sport,stats)
    if not isinstance(val,(int,float)) or not exposure or exposure<=0 or unit=='Games':continue
    key=(sport,pos,market,unit)
    for bucket in (league[key],defense[(opp,)+key]):bucket[0]+=val;bucket[1]+=exposure;bucket[2].add(eid)
 return league,defense,coverage

def opponent_adjustment(index,sport,opp,pos,market,unit):
 league,defense,coverage=index;key=(sport,pos,market,unit);base=league.get(key);allow=defense.get((opp,)+key)
 missing={'available':False,'position':pos,'unit':unit,'multiplier':1,'opponent_rate':None,'league_rate':None,'games':0,'exposure':0,'note':'Insufficient position/opportunity data; no defensive adjustment applied.'}
 if not base or not allow or base[1]<=0 or allow[1]<=0 or len(allow[2])<3 or base[0]<=0:return missing
 lr=base[0]/base[1];dr=allow[0]/allow[1];prior=480 if unit=='Minutes' else 100
 weight=allow[1]/(allow[1]+prior);ratio=dr/lr;factor=clamp(1+(ratio-1)*weight,.85,1.15)
 return {'available':True,'position':pos,'unit':unit,'multiplier':round(factor,4),'opponent_rate':round(dr,4),'league_rate':round(lr,4),'games':len(allow[2]),'exposure':round(allow[1],1),'coverage':round(coverage[sport][0]/max(1,coverage[sport][1]),3),'note':'Current/historical roster position bucket, not individual defender tracking. Rate includes observed pace; no separate pace multiplier is stacked.'}

def projection(pairs,market,sport,context,matchup,status,absence_ids,box):
 """Production rate × expected minutes/opportunities, shrunk contextual split effects."""
 vals=[v for r,v in pairs];n=len(vals);baseline=avg(vals);last5=avg(vals[-5:]);unit,unused=opportunities(market,sport,pairs[-1][0]['stats'])
 usable=[(r,v,opportunities(market,sport,r['stats'])[1]) for r,v in pairs];usable=[(r,v,x) for r,v,x in usable if x and x>0]
 rates=[v/x for r,v,x in usable];exp=[x for r,v,x in usable];rate=None;expected=None;flags=[];adjustments={}
 if len(usable)>=5:
  recent=usable[-5:];full_rate=sum(v for r,v,x in usable)/sum(x for r,v,x in usable);recent_rate=sum(v for r,v,x in recent)/sum(x for r,v,x in recent)
  rate=.60*recent_rate+.40*full_rate;expected=.65*avg(exp[-5:])+.35*avg(exp)
  if unit=='Minutes' and sport in BASKET:expected=clamp(expected,0,40)
  base=rate*expected;vol=st.pstdev(exp) if len(exp)>1 else 0
  if unit=='Minutes' and abs(avg(exp[-3:])-avg(exp))>4:flags.append('Minutes volatility')
 else:unit='Games';base=.65*last5+.35*baseline;vol=0;flags.append('Opportunity data missing')
 # Venue split effects require at least three observations in each split and shrink to neutral.
 same=[];other=[]
 for r,v in pairs:
  venue=r.get('venue')
  if venue is None:continue
  (same if venue==context.get('venue') else other).append(v)
 venue_factor=1
 if len(same)>=3 and len(other)>=3 and baseline>0:venue_factor=clamp(1+(avg(same)/baseline-1)*len(same)/(len(same)+12),.95,1.05)
 adjustments['venue']=round(venue_factor,4)
 # Teammate absence: only learn a small effect if the named teammate is recorded as a DNP in past boxes.
 without=[];with_team=[]
 for r,v in pairs:
  b=box.get(r['event_id'],[]);found={x['player_id']:x for x in b}
  known_out=any(pid in found and found[pid].get('did_not_play') for pid in absence_ids)
  known_in=all(pid in found and not found[pid].get('did_not_play') for pid in absence_ids) if absence_ids else False
  if known_out:without.append(v)
  elif known_in:with_team.append(v)
 absence_factor=1
 if len(without)>=3 and len(with_team)>=3 and avg(with_team)>0:absence_factor=clamp(1+(avg(without)/avg(with_team)-1)*len(without)/(len(without)+15),.94,1.06)
 elif absence_ids:flags.append('Teammate usage unresolved')
 adjustments['teammate_absence']=round(absence_factor,4)
 # Rest is a modest explicit heuristic, not a fitted causal coefficient.
 rest=.98 if context.get('back_to_back') and sport in BASKET else 1;adjustments['rest']=rest
 if status.lower() not in ('not listed','available','active','probable'):flags.append(status)
 defense=matchup['multiplier'] if matchup.get('available') else 1
 if not matchup.get('available'):flags.append('Position matchup unavailable')
 mu=max(0,base*defense*venue_factor*absence_factor*rest)
 # Recenter the observed residual distribution instead of calling a sample mean a guaranteed forecast.
 residuals=[v-baseline for v in vals];emp_sd=st.pstdev(vals) if n>1 else math.sqrt(max(mu,1));minute_sd=(rate*vol*.35) if rate is not None else 0
 sd=math.sqrt(max(emp_sd,.65*math.sqrt(max(mu,1)))**2*(1+1/n)+minute_sd**2)
 if any(x in flags for x in ('Questionable','Doubtful','Minutes volatility','Teammate usage unresolved')):sd*=1.12
 adjustment_uncertainty=abs(defense-1)+abs(venue_factor-1)+abs(absence_factor-1)
 margin=clamp(.025+.055/math.sqrt(n)+.02*sd/max(mu,1)+adjustment_uncertainty*.03,.03,.12)
 return {'mu':mu,'sd':max(sd,.8),'unit':unit,'rate':rate,'exposure':expected,'baseline_exposure':avg(exp) if exp else None,'last5_exposure':avg(exp[-5:]) if exp else None,'baseline_rate':(sum(v for r,v,x in usable)/sum(x for r,v,x in usable)) if usable else None,'last5_rate':(sum(v for r,v,x in usable[-5:])/sum(x for r,v,x in usable[-5:])) if usable else None,'base_projection':base,'adjustments':adjustments,'defense':matchup,'flags':flags+(['Small sample'] if n<10 else []),'probability_margin':margin,'residuals':residuals,'absence_split_games':len(without)}

def tail_probability(line,side,mu,sd,residuals):
 """Regularized normal + smoothed empirical residual tail. Avoids overconfident small-sample tails."""
 normal=.5*(1+math.erf((line-mu)/(max(sd,.25)*math.sqrt(2))));normal=1-normal if side=='Over' else normal
 empirical=(sum((mu+r>line) if side=='Over' else (mu+r<line) for r in residuals)+1)/(len(residuals)+2)
 return clamp(.7*normal+.3*empirical,.025,.975)
def american(decimal):return round((decimal-1)*100) if decimal>=2 else round(-100/(decimal-1))
def break_even(o):return abs(o)/(abs(o)+100) if o<0 else 100/(o+100)
def decimal(o):return 1+100/abs(o) if o<0 else 1+o/100
def price_in_band(o):return o is not None and (o==100 or -1500<=o<=-100)
def value_metrics(p,odds,margin=.04):
 conservative=max(.01,p-margin);minimum_decimal=max(1.05/max(p,.01),1/max(.01,p-.03),1/conservative)
 result={'probability_floor':round(conservative,5),'probability_margin':round(margin,5),'entry_price_limit':american(minimum_decimal),'scenario_prices':PRICE_LADDER}
 if odds is None:return result|{'edge_pp':None,'expected_roi_pct':None,'conservative_edge_pp':None,'conservative_roi_pct':None,'value_status':'Price needed','value_reason':'Enter an actual quote to verify value; use the target-price table for conditional comparisons.'}
 be=break_even(odds);edge=p-be;roi=p*decimal(odds)-1;ce=conservative-be;cr=conservative*decimal(odds)-1
 status='Outside price range' if not price_in_band(odds) else 'Provisional value' if edge>=.03 and roi>=.05 and ce>0 else 'Thin / uncertain edge' if edge>0 and roi>0 else 'Pass at this price'
 return result|{'edge_pp':round(edge*100,2),'expected_roi_pct':round(roi*100,2),'conservative_edge_pp':round(ce*100,2),'conservative_roi_pct':round(cr*100,2),'value_status':status,'value_reason':f'Model {p:.1%}, break-even {be:.1%}; edge {edge*100:+.1f} pp, estimated ROI {roi*100:+.1f}%. After a {margin*100:.1f} pp model-risk buffer: {ce*100:+.1f} pp edge.'}
def research_score(p,margin,odds,sample):
 if odds is not None:
  m=value_metrics(p,odds,margin);return (m['conservative_roi_pct'] or 0)+.25*(m['edge_pp'] or 0)
 # Unpriced targets near a plausible -150 price are research priorities, never verified edges.
 return 10-abs(p-.68)*30+min(sample,25)*.1-margin*30
