"""Conservative model-disagreement screening, not a fitted Bayesian model."""
import math,statistics as st
from collections import defaultdict
COUNT_MARKETS={'Threes','Rebounds','Assists','Receptions','Completions','Shots on goal','Saves'}

def count_tail(mu, variance, line, side='Over'):
 """Moment-matched NB when overdispersed; otherwise Poisson. Strict settlement tails."""
 if not all(math.isfinite(x) for x in (mu,variance,line)) or mu<0:return None
 if mu==0:return float(0>line if side=='Over' else 0<line)
 end=math.floor(line) if side=='Over' else math.ceil(line)-1
 if end<0:return 1. if side=='Over' else 0.
 if end>10000:return None
 k=mu*mu/(variance-mu) if variance>mu+1e-8 else None
 logs=[]
 for y in range(end+1):
  if k is None:lp=-mu+y*math.log(mu)-math.lgamma(y+1)
  else:lp=math.lgamma(y+k)-math.lgamma(k)-math.lgamma(y+1)+k*math.log(k/(k+mu))+y*math.log(mu/(k+mu))
  logs.append(lp)
 top=max(logs);cdf=min(1.,math.exp(top)*sum(math.exp(x-top) for x in logs))
 return max(0.,1-cdf) if side=='Over' else cdf

def assess(row, values):
 out={'version':'distribution-screen-v1','status':'unavailable','note':'No fitted Bayesian posterior or joint-game simulation; probability of positive EV remains unavailable.'}
 if row.get('market') not in COUNT_MARKETS or len(values)<10:return out
 if any(not isinstance(x,(float,int)) or not math.isfinite(x) or x<0 or x!=int(x) for x in values):return out
 mu=row.get('projection');sd=row.get('sd')
 if not isinstance(mu,(float,int)) or not isinstance(sd,(float,int)) or mu<0 or sd<=0:return out
 variance=max(sd*sd,mu);p=count_tail(mu,variance,row['line'],row['side'])
 if p is None:return out
 margin=row.get('probability_margin',.08);existing=row.get('probability_floor',max(0,row['probability']-margin))
 return dict(out,status='stress-screen',distribution='Negative binomial' if variance>mu+1e-8 else 'Poisson',mean=mu,variance=variance,sample_variance=st.variance(values),comparison_probability=p,selection_floor=max(0,min(existing,p-margin)),note='Moment-matched count-model stress test. Selection uses the lower buffered estimate; original win probability stays unchanged. This is a heuristic robustness screen, not posterior confidence or validated calibration.')

def proper_scores(rows):
 groups=defaultdict(list)
 for r in rows:
  if r.get('outcome') not in (0,1) or not isinstance(r.get('probability'),(float,int)):continue
  groups[(r.get('event_id'),r.get('player_id'),r.get('market'),r.get('side'))].append(r)
 if not groups:return {'groups':0,'brier':None,'log_loss':None}
 bs=[];ls=[]
 for rs in groups.values():
  bs.append(st.mean((r['probability']-r['outcome'])**2 for r in rs))
  ls.append(st.mean(-(r['outcome']*math.log(max(1e-12,min(1-1e-12,r['probability'])))+(1-r['outcome'])*math.log(1-max(1e-12,min(1-1e-12,r['probability'])))) for r in rs))
 return {'groups':len(groups),'brier':st.mean(bs),'log_loss':st.mean(ls)}

def validation_report(rows):
 groups=defaultdict(list)
 for r in rows:groups[(r.get('sport','Unknown'),r.get('market','Unknown'))].append(r)
 return {'overall':proper_scores(rows),'by_market':[{ 'sport':s,'market':m,**proper_scores(rs)} for (s,m),rs in sorted(groups.items())], 'method':'Event/player/market/side groups receive equal weight; alternate lines within a group are averaged. This is forecast scoring, not an untouched walk-forward validation of the selection optimizer.'}
