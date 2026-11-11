"""Measured selection evidence. Historical cover rates are descriptive, never a backtest."""
import math,statistics as st

def implied(o):return abs(o)/(abs(o)+100) if o<0 else 100/(o+100)
def mean(xs):return st.mean(xs) if xs else None

def build(r,events,injuries,player_logs,forecasts):
 e=events.get(r['event_id'],{});market=r['market'];line=r.get('line');side=r.get('side');notes=[];risks=[];games=[];ctx=r.get('context') or {};weather=e.get('weather') or {}
 if r.get('player_id'):
  games=(player_logs.get(r.get('log_key'),{}).get('games') or [])[-25:]
  d=ctx.get('opponent_position') or {}
  notes.append(f"Production model: {r.get('rate')} per {r.get('exposure_unit','opportunity')} × {r.get('expected_exposure')} projected opportunities; projected {r.get('projection')} {market}.")
  notes.append(f"Opponent position multiplier {d.get('multiplier',1)} using {d.get('games',0)} observed opponent games; position buckets, not individual defender tracking.")
  if r.get('hit_rate') is not None:notes.append(f"Observed full sample: {r['hit_rate']:.1%} cleared this threshold across {r.get('sample',0)} games; this is not next-game probability.")
  risks+=r.get('flags',[])
 else:
  scores=forecasts.get(r['event_id'],{})
  if scores:notes.append(f"Projected score: {e.get('away',{}).get('name','Away')} {scores.get('away')} — {e.get('home',{}).get('name','Home')} {scores.get('home')}. Derived from scoring form, opponent allowance, home advantage and the stated rest adjustment.")
  if market in ('Moneyline','Spread'):
   notes.append(f"Projected scoring margin for {r['selection']}: {(-r['projection'] if market=='Moneyline' and side=='away' else r.get('projection'))} points/goals/runs; market {'spread '+str(line) if market=='Spread' else 'requires an outright win'}. Distribution spread (SD): {r.get('sd')}.")
  elif market=='Total':notes.append(f"Projected combined score {r.get('projection')} versus {side} {line}; distribution SD {r.get('sd')}.")
  if ctx.get('points_for') is not None:notes.append(f"Team scoring average {ctx['points_for']}; opponent allowance {ctx.get('opponent_allowed')}; rest {ctx.get('rest_days')} days.")
  elif ctx.get('home'):notes.append(f"Home scored/allowed {ctx['home'].get('points_for')}/{ctx['home'].get('points_allowed')}; away scored/allowed {ctx.get('away',{}).get('points_for')}/{ctx.get('away',{}).get('points_allowed')}.")
  tid=r.get('team_id');ids={e.get('home',{}).get('id'),e.get('away',{}).get('id')}
  for g in sorted(events.values(),key=lambda g:g.get('start','')):
   if g.get('sport')!=r['sport'] or not g.get('final') or g.get('start','')>=r['start']:continue
   home,away=g.get('home',{}),g.get('away',{});hs,aws=home.get('score'),away.get('score')
   if hs is None or aws is None:continue
   if market=='Total' and ids.intersection({home.get('id'),away.get('id')}):v=hs+aws;opp=str(away.get('abbr') or away.get('name') or '?')+' / '+str(home.get('abbr') or home.get('name') or '?')
   elif market in ('Moneyline','Spread') and tid in (home.get('id'),away.get('id')):
    v=hs-aws if tid==home.get('id') else aws-hs;opp=(away if tid==home.get('id') else home).get('abbr')
   else:continue
   threshold=-line if market=='Spread' else 0 if market=='Moneyline' else line
   hit='push' if v==threshold else int(v<threshold if side=='Under' else v>threshold)
   games.append({'date':g['start'],'opponent':opp,'value':v,'outcome':hit,'event_id':g['id']})
  games=games[-25:]
  risks.append('Basic team scoring model: schedule strength, confirmed rotations and validated injury impact are not fully modeled.')
 relevant=[i for i in injuries if i.get('event_id')==r['event_id']]
 if relevant:
  notes.append('Availability feed: '+', '.join(i['player']+' ('+i['status']+')' for i in relevant[:8])+'.')
  risks.append('Availability is a feed snapshot; recheck lineups before start. Team injury effects are not quantitatively validated.')
 else:risks.append('No injury entries returned does not confirm healthy or available starters.')
 notes.append('Weather: '+weather.get('status','Unavailable; no weather adjustment')+(f"; wind {weather['wind_mph']} mph, {weather.get('temperature_f')}°F" if weather.get('wind_mph') is not None else '')+'.')
 if market in ('Moneyline','Spread','Total') and games:
  graded=[g for g in games if g['outcome']!='push'];wins=sum(g['outcome']==1 for g in graded)
  history={'games':len(games),'wins':wins,'losses':len(graded)-wins,'pushes':len(games)-len(graded),'rate':wins/len(graded) if graded else None,'label':'Descriptive previous-game results at this exact threshold, against different opponents; not an out-of-sample forecast test.'}
 else:history={'games':len(games),'rate':r.get('hit_rate'),'label':'Actual player production at the selected threshold; not a forecast backtest.'}
 p=r['probability'];floor=r.get('probability_floor',p-r.get('probability_margin',.05));o=r.get('odds');be=implied(o) if o else None
 risks.append('Probability is a provisional statistical estimate, not a demonstrated hit rate. The risk buffer is heuristic, not a confidence interval.')
 return {'version':'evidence-v1','projection':r.get('projection'),'sd':r.get('sd'),'sample':r.get('sample',0),'probability':p,'buffered_probability':floor,'break_even':be,'edge_pp':r.get('edge_pp'),'buffered_edge_pp':r.get('conservative_edge_pp'),'notes':notes,'risks':list(dict.fromkeys(risks)),'history':history,'games':games,'source_url':r.get('source_url'),'quote_collected_at':r.get('odds_updated') or r.get('observed_at'),'price_limit':r.get('entry_price_limit'),'calibration_groups':r.get('calibration_games',0),'context':ctx if r.get('player_id') else {k:v for k,v in ctx.items() if k in ('games','points_for','points_allowed','opponent_allowed','rest_days','back_to_back','home','away')}}
