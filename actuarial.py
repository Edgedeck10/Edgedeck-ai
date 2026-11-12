"""Deterministic opportunity scenarios. Fitted distributions, not posterior inference."""
import math, statistics as st
from collections import defaultdict
VERSION='opportunity-context-2'
COMBOS={'PRA':['Points','Rebounds','Assists'],'Points + rebounds':['Points','Rebounds'],'Points + assists':['Points','Assists'],'Rebounds + assists':['Rebounds','Assists']}
def value(stats,market):
 if market in COMBOS:
  a=[stats.get(k) for k in COMBOS[market]]
  return sum(a) if all(x is not None for x in a) else None
 return stats.get(market)
def avg(a):return st.mean(a) if a else 0
def quantile(a,p):
 a=sorted(a);i=(len(a)-1)*p;lo=int(i);return a[lo]+(a[min(lo+1,len(a)-1)]-a[lo])*(i-lo)
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
 n=len(ps);candidates=[w for w in (10,15,20,25) if w<=n]
 origins=list(range(max(candidates,default=n),n));split=max(1,int(len(origins)*.7));train=origins[:split];hold=origins[split:]
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
 return {'selected_games':selected,'available_games':n,'candidate_mae':{str(k):round(v,3) if v is not None else None for k,v in scores.items()},'evaluation_games':len(hold),'holdout_mae':round(avg(errors),3) if errors else None,'selection_status':'Chronological comparison' if eligible else 'Insufficient chronological origins; baseline window used','scope':'Chronological opportunity-mean window comparison only; not full model or selection validation'}

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
 mus=[max(0,shrunk*x) for x in xs]
 excess=sum((y-m)**2-m for y,m in zip(ys,mus));den=sum(m*m for m in mus)
 k=den/excess if excess>0 and den>0 else None
 residual_sd=math.sqrt(avg([(y-shrunk*x)**2/max(x,1) for y,x in zip(ys,xs)]))
 # One fitted family, evaluated at three workload scenarios. No Monte Carlo.
 if family=='finite':shrunk=(sum(ys)+.5)/(sum(xs)+1)
 elif family=='count' and not prior:shrunk=(sum(ys)+.5)/sum(xs)
 workloads=[quantile(xs,.1),avg(xs),quantile(xs,.9)]
 histograms=[distribution(family,shrunk*x*adjustment,x,k,residual_sd) for x in workloads]
 mix=defaultdict(float)
 for weight,h in zip((.25,.5,.25),histograms):
  for y,p in h.items():mix[float(y)]+=weight*p
 mean=sum(y*p for y,p in mix.items());sd=math.sqrt(sum((y-mean)**2*p for y,p in mix.items()))
 def mq(q):
  total=0
  for y,p in sorted(mix.items()):
   total+=p
   if total>=q:return y
  return max(mix)
 missing=['Confirmed lineup / role changes','Position-specific defense','Weather / game-script adjustment','Closing-line history']
 if sport in ('NBA','WNBA','NCAAB'):missing+=['Potential assists / rebound chances','On-off usage / pace']
 if sport in ('NFL','NCAAF'):missing+=['Routes / snap share / air yards / EPA','Individual-play severity data; yardage variance is aggregate approximation']
 if sport in ('EPL','MLS'):missing+=['xG / xA / possession']
 if sport=='NHL':missing+=['Power-play deployment / confirmed goalie']
 evidence={'engine':VERSION,'method':{'finite':'Binomial production','signed':'Rounded signed Gaussian yardage','count':'Negative-binomial production' if k else 'Poisson production'}[family]+' with low / normal / high workload scenarios', 'opportunity_unit':unit,'expected_opportunity':round(avg(xs),3),'observed_rate':round(rate,4),'shrunk_rate':round(shrunk,4),'credibility_weight':round(z,4),'credibility_fit':prior,'history_window':window,'adjustment':round(adjustment,4),'median':mq(.5),'outcome_range_80':[mq(.1),mq(.9)],'workload_range_80':[round(workloads[0],2),round(workloads[2],2)],'workload_scenarios':[{'label':label,'opportunity':round(x,3),'weight':w} for label,x,w in zip(('Low','Normal','High'),workloads,(.25,.5,.25))],'scenario_weights':[.25,.5,.25],'negative_binomial_k':round(k,4) if k else None,'fallback':fallback,'missing_inputs':missing,'status':'Research model; not prospectively validated','uncertainty_note':'Probability range is sensitivity to three workloads, not a credible interval. Scenario weights 25/50/25 are assumptions, not learned likelihoods. Parameter uncertainty and omitted matchup factors are not quantified.','draw_histograms':histograms,'simulations_per_draw':0,'sample_games':len(ps),'training_end':ps[-1][0]['start']}
 return {'projection':mean,'sd':sd,'evidence':evidence}

def distribution(family,mu,workload,k,residual_sd):
 """Normalized discrete PMF; count tails truncated at 12 standard deviations."""
 h={}
 if family=='finite':
  n=max(0,round(workload));p=min(1-1e-12,max(1e-12,mu/max(workload,1e-12)))
  for y in range(n+1):h[str(y)]=math.exp(math.lgamma(n+1)-math.lgamma(y+1)-math.lgamma(n-y+1)+y*math.log(p)+(n-y)*math.log1p(-p))
 elif family=='signed':
  sd=residual_sd*math.sqrt(workload)
  if sd<1e-9:return {str(round(mu)):1.}
  cdf=lambda x:.5*(1+math.erf((x-mu)/(sd*math.sqrt(2))))
  for y in range(math.floor(mu-9*sd),math.ceil(mu+9*sd)+1):h[str(y)]=max(0,cdf(y+.5)-cdf(y-.5))
 else:
  mu=max(0,mu)
  if mu==0:return {'0':1.}
  sd=math.sqrt(mu+(mu*mu/k if k else 0));upper=math.ceil(mu+12*sd+20)
  for y in range(upper+1):
   logp=(math.lgamma(y+k)-math.lgamma(k)-math.lgamma(y+1)+k*math.log(k/(k+mu))+y*math.log(mu/(k+mu))) if k else (-mu+y*math.log(mu)-math.lgamma(y+1))
   h[str(y)]=math.exp(logp)
 h={y:p for y,p in h.items() if p>1e-12};total=sum(h.values())
 return {y:p/total for y,p in h.items()}

def price(evidence,line,side,odds=None):
 draws=[];pushes=[]
 for histogram in evidence['draw_histograms']:
  total=sum(histogram.values());wins=sum(n for y,n in histogram.items() if (float(y)>line if side=='Over' else float(y)<line));push=sum(n for y,n in histogram.items() if float(y)==line)
  draws.append(wins/total);pushes.append(push/total)
 weights=evidence.get('scenario_weights',[1/len(draws)]*len(draws));weighted=lambda a:sum(w*v for w,v in zip(weights,a))
 p=weighted(draws);push=weighted(pushes);loss=1-p-push;conditional=p/(p+loss) if p+loss else .5;conditional=min(.9999,max(.0001,conditional))
 fair=round(-100*conditional/(1-conditional)) if conditional>=.5 else round(100*(1-conditional)/conditional)
 evs=None
 if odds is not None and abs(odds)>=100:
  profit=100/abs(odds) if odds<0 else odds/100
  evs=[w*profit-(1-w-u) for w,u in zip(draws,pushes)]
 return {'probability':p,'push_probability':push,'probability_range_80':[min(draws),max(draws)],'fair_odds':fair,'expected_roi_pct':100*weighted(evs) if evs is not None else None,'ev_lower_80_pct':100*min(evs) if evs is not None else None,'probability_positive_ev':None,'positive_ev_scenario_weight':weighted([v>0 for v in evs]) if evs is not None else None,'uncertainty_kind':'Workload scenario sensitivity; not a posterior interval'}

def monitoring(history,version):
 def scored_p(r):return min(1-1e-9,max(1e-9,r['probability']/max(1e-9,1-r.get('push_probability',0))))
 groups=defaultdict(list)
 for r in history:
  if r.get('model_version')==version and r.get('outcome') in (0,1):groups[(r['sport'],r['market'],r['event_id'],r.get('player_id'),r['side'])].append(r)
 by=defaultdict(list)
 for key,rows in groups.items():
  by[key[:2]].append({'brier':avg([(scored_p(r)-r['outcome'])**2 for r in rows]),'log_loss':avg([-math.log(max(1e-9,min(1-1e-9,scored_p(r) if r['outcome'] else 1-scored_p(r)))) for r in rows])})
 return [{'sport':s,'market':m,'forecast_groups':len(rs),'brier':avg([r['brier'] for r in rs]),'log_loss':avg([r['log_loss'] for r in rs])} for (s,m),rs in by.items()]

