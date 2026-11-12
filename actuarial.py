"""Empirical-Bayes/ Bayesian-bootstrap research engine. Standard library only.
Posterior intervals are approximate and conditional on plug-in dispersion/peer fits.
Not a full hierarchical Bayesian game model. No profitability guarantees.
"""
import math, random, statistics as st, hashlib
from collections import defaultdict
VERSION='opportunity-eb-1'
DRAWS=48
SIMS=32
COMBOS={'PRA':['Points','Rebounds','Assists'],'Points + rebounds':['Points','Rebounds'],'Points + assists':['Points','Assists'],'Rebounds + assists':['Rebounds','Assists']}
def value(stats,market):
 if market in COMBOS:
  a=[stats.get(k) for k in COMBOS[market]]
  return sum(a) if all(x is not None for x in a) else None
 return stats.get(market)
def avg(a):return st.mean(a) if a else 0
def quantile(a,p):
 a=sorted(a);i=(len(a)-1)*p;lo=int(i);return a[lo]+(a[min(lo+1,len(a)-1)]-a[lo])*(i-lo)
def seed(key):return int(hashlib.sha256(str(key).encode()).hexdigest()[:16],16)
def opportunity(sport,market):
 if sport in ('NBA','WNBA','NCAAB'):
  return ('Three attempts','finite') if market=='Threes' else ('Minutes','count')
 if sport in ('NFL','NCAAF'):
  return {'Passing yards':('Pass attempts','signed'),'Rushing yards':('Carries','signed'),'Receiving yards':('Receptions','signed'),'Receptions':('Targets','finite'),'Completions':('Pass attempts','finite')}.get(market,('Games','count'))
 if sport=='NHL':return ('Shots faced','finite') if market=='Saves' else ('Minutes','count')
 if sport in ('EPL','MLS'):return ('Shots','finite') if market=='Shots on target' else ('Minutes','count')
 if sport=='MLB':return ('At bats','finite') if market=='Hits' else ('Games','count')
 return ('Games','count')
def pairs_for(records,sport,market):
 unit,family=opportunity(sport,market);rows=[]
 for r in sorted(records,key=lambda x:x['start']):
  s=r['stats'];y=value(s,market);x=1 if unit=='Games' else s.get(unit)
  if y is None:continue
  if x is None or x<=0:continue
  if family=='finite' and not 0<=y<=x:continue
  rows.append((r,float(y),float(x)))
 return rows,unit,family

def credibility(peers,sport,market,exclude):
 groups=[]
 for pid,rs in peers.items():
  if pid==exclude:continue
  ps,_,_=pairs_for(rs[-25:],sport,market)
  if len(ps)<3:continue
  exposure=sum(x for _,y,x in ps);rate=sum(y for _,y,x in ps)/exposure
  within=sum(x*(y/x-rate)**2 for _,y,x in ps)/(len(ps)-1)
  groups.append((rate,within,exposure))
 if len(groups)<5:return None
 within=avg([g[1] for g in groups]);between=st.variance(g[0] for g in groups)-avg([g[1]/g[2] for g in groups])
 if between<=0 or within<=0:return None
 return {'baseline':avg([g[0] for g in groups]),'K':within/between,'peer_players':len(groups),'method':'Exposure-weighted within/between-player moment estimate; sport and market peers, not role-adjusted'}

def history_window(ps):
 """Tune windows on early chronological origins; evaluate on untouched later origins.
 This validates the rolling opportunity-mean forecaster, not the whole betting selector.
 """
 n=len(ps);candidates=[w for w in (5,10,15,20,25) if w<=n]
 origins=list(range(5,n));split=max(1,int(len(origins)*.7));train=origins[:split];hold=origins[split:]
 scores={}
 for w in candidates:
  errors=[]
  for i in train:
   p=ps[max(0,i-w):i];mu=avg([x for _,y,x in p])*sum(y for _,y,x in p)/sum(x for _,y,x in p)
   errors.append(abs(ps[i][1]-mu))
  scores[w]=avg(errors) if errors else None
 eligible=[w for w in candidates if scores[w] is not None]
 selected=min(eligible,key=lambda w:(scores[w],-w)) if eligible else min(20,n)
 errors=[]
 for i in hold:
  p=ps[max(0,i-selected):i];mu=avg([x for _,y,x in p])*sum(y for _,y,x in p)/sum(x for _,y,x in p)
  errors.append(abs(ps[i][1]-mu))
 return {'selected_games':selected,'available_games':n,'candidate_mae':{str(k):round(v,3) if v is not None else None for k,v in scores.items()},'evaluation_games':len(hold),'holdout_mae':round(avg(errors),3) if errors else None,'scope':'Chronological opportunity-mean window comparison only; not full model or selection validation'}

def poisson(rng,mu):
 # Exact sum of independent Poisson chunks avoids exp underflow.
 if mu>40:return sum(poisson(rng,min(40,mu-i)) for i in range(0,int(math.ceil(mu)),40))
 limit=math.exp(-max(0,mu));p=1;k=0
 while p>limit:k+=1;p*=rng.random()
 return max(0,k-1)
def fit(records,peers,sport,market,pid,key,adjustment=1):
 ps,unit,family=pairs_for(records,sport,market)
 fallback=False
 if len(ps)<5:
  ps=[(r,float(value(r['stats'],market)),1.) for r in sorted(records,key=lambda r:r['start']) if value(r['stats'],market) is not None]
  unit='Games';family='signed' if 'yards' in market else 'count';fallback=True
 if len(ps)<5:return None
 ps=ps[-40:];window=history_window(ps);ps=ps[-window['selected_games']:]
 ys=[y for _,y,x in ps];xs=[x for _,y,x in ps];rate=sum(ys)/sum(xs)
 prior=credibility(peers,sport,market,pid) if not fallback and family!='finite' else None
 z=sum(xs)/(sum(xs)+prior['K']) if prior else 1
 shrunk=z*rate+(1-z)*prior['baseline'] if prior else rate
 # Dispersion estimated from residuals conditional on opportunity, not raw variance.
 mus=[max(0,shrunk*x*adjustment) for x in xs]
 excess=sum((y-m)**2-m for y,m in zip(ys,mus));den=sum(m*m for m in mus)
 k=den/excess if excess>0 and den>0 else None
 residual_sd=math.sqrt(avg([(y-shrunk*x)**2/max(x,1) for y,x in zip(ys,xs)]))
 rng=random.Random(seed(key));draws=[];all_outcomes=[]
 for d in range(DRAWS):
  weights=[rng.expovariate(1) for _ in ps];total=sum(weights)
  sample_rate=sum(w*y for w,y in zip(weights,ys))/sum(w*x for w,x in zip(weights,xs))
  theta=(z*sample_rate+(1-z)*prior['baseline']) if prior else sample_rate
  if family=='count':theta=rng.gammavariate(max(.0001,sum(ys)+(max(0,prior['baseline'])*prior['K'] if prior else .5)),1/(sum(xs)+(prior['K'] if prior else 0)))
  if family=='finite':theta=rng.betavariate(.5+sum(ys),.5+sum(xs)-sum(ys))
  outcomes=[]
  for _ in range(SIMS):
   workload=rng.choices(xs,weights=weights,k=1)[0]
   if family=='finite':
    attempts=max(0,round(workload));outcome=sum(rng.random()<min(1,max(0,theta*adjustment)) for _ in range(attempts))
   elif family=='signed':outcome=round(rng.gauss(theta*workload*adjustment,residual_sd*math.sqrt(workload)))
   else:
    mu=max(0,theta*workload*adjustment);lam=rng.gammavariate(k,mu/k) if k and mu else mu;outcome=poisson(rng,lam)
   outcomes.append(outcome)
  draws.append(outcomes);all_outcomes+=outcomes
 histograms=[dict((str(y),outcomes.count(y)) for y in set(outcomes)) for outcomes in draws]
 missing=['Confirmed lineup / role changes','Position-specific defense','Weather / game-script adjustment','Closing-line history']
 if sport in ('NBA','WNBA','NCAAB'):missing+=['Potential assists / rebound chances','On-off usage / pace']
 if sport in ('NFL','NCAAF'):missing+=['Routes / snap share / air yards / EPA','Individual-play severity data; yardage variance is aggregate approximation']
 if sport in ('EPL','MLS'):missing+=['xG / xA / possession']
 if sport=='NHL':missing+=['Power-play deployment / confirmed goalie']
 evidence={'engine':VERSION,'method':{'finite':'Beta-binomial production with Bayesian-bootstrap workload','signed':'Bayesian-bootstrap rate and workload; signed Gaussian aggregate-yardage approximation','count':'Approximate gamma rate / bootstrap workload; fitted negative-binomial production' if k else 'Gamma rate posterior / bootstrap workload; Poisson production'}[family], 'opportunity_unit':unit,'expected_opportunity':round(avg(xs),3),'observed_rate':round(rate,4),'shrunk_rate':round(shrunk,4),'credibility_weight':round(z,4),'credibility_fit':prior,'history_window':window,'adjustment':round(adjustment,4),'median':round(quantile(all_outcomes,.5),2),'outcome_range_80':[round(quantile(all_outcomes,.1),2),round(quantile(all_outcomes,.9),2)],'workload_range_80':[round(quantile(xs,.1),2),round(quantile(xs,.9),2)],'negative_binomial_k':round(k,4) if k else None,'fallback':fallback,'missing_inputs':missing,'status':'Research model; not prospectively validated','uncertainty_note':'Approximate conditional intervals: peer baseline and dispersion are fitted plug-in values. Not a full hierarchical Bayesian posterior; the gamma update is approximate when residual production is negative-binomial.','draw_histograms':histograms,'simulations_per_draw':SIMS,'sample_games':len(ps),'training_end':ps[-1][0]['start']}
 return {'projection':avg(all_outcomes),'sd':st.pstdev(all_outcomes),'evidence':evidence}

def price(evidence,line,side,odds=None):
 draws=[];pushes=[]
 for histogram in evidence['draw_histograms']:
  total=sum(histogram.values());wins=sum(n for y,n in histogram.items() if (float(y)>line if side=='Over' else float(y)<line));push=sum(n for y,n in histogram.items() if float(y)==line)
  draws.append(wins/total);pushes.append(push/total)
 p=avg(draws);push=avg(pushes);loss=1-p-push;conditional=p/(p+loss) if p+loss else .5;conditional=min(.9999,max(.0001,conditional))
 fair=round(-100*conditional/(1-conditional)) if conditional>=.5 else round(100*(1-conditional)/conditional)
 evs=None
 if odds is not None and abs(odds)>=100:
  profit=100/abs(odds) if odds<0 else odds/100
  evs=[w*profit-(1-w-u) for w,u in zip(draws,pushes)]
 return {'probability':p,'push_probability':push,'probability_range_80':[quantile(draws,.1),quantile(draws,.9)],'fair_odds':fair,'expected_roi_pct':100*avg(evs) if evs is not None else None,'ev_lower_80_pct':100*quantile(evs,.1) if evs is not None else None,'probability_positive_ev':avg([v>0 for v in evs]) if evs is not None else None,'uncertainty_kind':'Conditional approximate parameter range plus finite simulation error'}

def monitoring(history,version):
 def scored_p(r):return min(1-1e-9,max(1e-9,r['probability']/max(1e-9,1-r.get('push_probability',0))))
 groups=defaultdict(list)
 for r in history:
  if r.get('model_version')==version and r.get('outcome') in (0,1):groups[(r['sport'],r['market'],r['event_id'],r.get('player_id'),r['side'])].append(r)
 by=defaultdict(list)
 for key,rows in groups.items():
  by[key[:2]].append({'brier':avg([(scored_p(r)-r['outcome'])**2 for r in rows]),'log_loss':avg([-math.log(max(1e-9,min(1-1e-9,scored_p(r) if r['outcome'] else 1-scored_p(r)))) for r in rows])})
 return [{'sport':s,'market':m,'forecast_groups':len(rs),'brier':avg([r['brier'] for r in rs]),'log_loss':avg([r['log_loss'] for r in rs])} for (s,m),rs in by.items()]
