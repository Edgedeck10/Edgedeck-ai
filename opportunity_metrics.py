"""Opportunity framework imported from the owner's shared Sports Betting Metrics chat.
No hypothetical weights, inputs or probability improvements are inferred from that chat.
"""
import statistics as st
from analytics import opportunities

SOURCE = 'https://chatgpt.com/share/6af4d7ac-2144-83ea-88a9-02d3434534d5'
REQUIRED = {
 'basketball': ['Usage rate', 'Potential assists', 'Rebound chances', 'Possessions', 'Confirmed rotation'],
 'football': ['Snap share', 'Routes run', 'Target share', 'Air yards', 'EPA', 'Pressure rate', 'Coverage scheme', 'Expected game script'],
 'hockey': ['Power-play ice time', 'Line assignment', 'Individual expected goals', 'High-danger chances', 'Confirmed starting goalie'],
 'soccer': ['Expected minutes', 'Shots per 90', 'Shots on target per 90', 'xG', 'xA', 'Possession', 'Confirmed starting lineup'],
}

def family(sport):
 return 'basketball' if sport in ('NBA','WNBA','NCAAB') else 'football' if sport in ('NFL','NCAAF') else 'hockey' if sport=='NHL' else 'soccer' if sport in ('EPL','MLS') else 'other'

def framework(pairs, market, sport, model):
 values=[v for _,v in pairs]
 def window(gs):
  vals=[v for _,v in gs]; valid=[(r,v,opportunities(market,sport,r['stats'])[1]) for r,v in gs];valid=[(r,v,x) for r,v,x in valid if x is not None and x>0]
  return {'games':len(vals),'mean':st.mean(vals) if vals else None,'median':st.median(vals) if vals else None,'sd':st.pstdev(vals) if vals else None,'opportunity_games':len(valid),'opportunities':st.mean([x for _,_,x in valid]) if valid else None,'rate':sum(v for _,v,_ in valid)/sum(x for _,_,x in valid) if valid else None}
 out={'version':'opportunity-v1','source':SOURCE,'family':family(sport),'unit':model['unit'],'windows':{str(n):window(pairs[-n:]) for n in (5,10,20)},'sample':window(pairs),'splits':{v:window([(r,x) for r,x in pairs if r.get('venue')==v]) for v in ('home','away')},'base_projection':model['base_projection'],'adjustments':dict(model['adjustments']),'median':st.median(values),'sd':st.pstdev(values),'min':min(values),'max':max(values),'missing':REQUIRED.get(family(sport),[]),'method':'Production rate × expected opportunity; existing shrunk opponent/venue/absence/rest/weather adjustments. Opportunity and matchup can overlap; no additional pace factor or arbitrary weighted confidence score is stacked.'}
 # Expose measured receiving efficiency as two components of the historical rate.
 if market=='Receiving yards':
  valid=[(r,v) for r,v in pairs if r['stats'].get('Targets',0)>0 and r['stats'].get('Receptions') is not None]
  targets=sum(r['stats']['Targets'] for r,_ in valid); catches=sum(r['stats']['Receptions'] for r,_ in valid)
  out['receiving']={'games':len(valid),'catch_rate':catches/targets if targets else None,'yards_per_reception':sum(v for _,v in valid)/catches if catches else None,'note':'Historical decomposition only; forecast uses blended yards per target, so these full-sample components are not extra multipliers.'}
 return out
