"""Choose a comparable history window using equal chronological validation dates."""
import statistics as st
from analytics import opportunities

def select(pairs, market, sport):
 candidates=(8,12,16) if sport in ('NFL','NCAAF') else (10,20,30)
 n=len(pairs);eligible=[w for w in candidates if n>=w+5]
 if not eligible:return pairs,{'selected_games':n,'status':'Insufficient history to compare windows','validation_games':0}
 # All candidates predict exactly the same held-forward games, using past inputs only.
 start=max(max(eligible),n-10);scores=[]
 for w in eligible:
  errors=[]
  for i in range(start,n):
   train=pairs[i-w:i];valid=[(v,x) for r,v in train if (x:=opportunities(market,sport,r['stats'])[1]) is not None and x>0]
   if len(valid)<5:break
   rate=sum(v for v,x in valid)/sum(x for v,x in valid)
   exposure=.65*st.mean(x for v,x in valid[-5:])+.35*st.mean(x for v,x in valid)
   errors.append(abs(rate*exposure-pairs[i][1]))
  if len(errors)==n-start:scores.append({'games':w,'mae':st.mean(errors),'validation_games':len(errors)})
 if not scores:return pairs,{'selected_games':n,'status':'Opportunity data insufficient for window selection','validation_games':0}
 # Prefer the larger sample when measured error is within 5% of the best.
 best=min(x['mae'] for x in scores);chosen=max(x['games'] for x in scores if x['mae']<=best*1.05+1e-9)
 return pairs[-chosen:],{'selected_games':chosen,'available_games':n,'validation_games':n-start,'candidates':scores,'status':'Selected by rolling opportunity forecast MAE; larger window favored within 5%','limitation':'Window tuning only, not independent validation of final probabilities or betting returns.'}
