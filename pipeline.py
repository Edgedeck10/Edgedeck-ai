"""EdgeDeck v2: public scores, market snapshots, pregame team and player models.
Standard library only. No paid endpoints, keys, or automated betting.
"""
import json, math, pathlib, datetime as dt, urllib.request, statistics as st, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from zoneinfo import ZoneInfo
import analytics as an
import daily_picks as daily
import pick_evidence
import news_feed
import extra_fixtures
import copy
import record_store
import hashlib
import weather as weather_feed
ROOT=pathlib.Path(__file__).parent; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
NOW=dt.datetime.now(dt.timezone.utc); TODAY=NOW.astimezone(ZoneInfo('America/Indiana/Indianapolis')).date()
SPORTS={'NBA':'basketball/nba','NFL':'football/nfl','NHL':'hockey/nhl','MLB':'baseball/mlb','NCAAF':'football/college-football','NCAAB':'basketball/mens-college-basketball','WNBA':'basketball/wnba','EPL':'soccer/eng.1','MLS':'soccer/usa.1'}
DEFAULTS={'NBA':(112,15),'NCAAB':(74,12),'WNBA':(81,12),'NFL':(23,10),'NCAAF':(28,15),'MLB':(4.5,3),'NHL':(3,1.8),'EPL':(1.4,1.3),'MLS':(1.5,1.4)}
MODEL='4.0.0'; ERRORS=[]; CAL_CACHE={}; PLAYER_LOGS={}; MATCHUP_INDEX=None; POSITIONS={}
def read(n,d):
 try:return json.loads((DATA/n).read_text())
 except (ValueError,OSError):return d

def write(n,v): (DATA/n).write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False))
def fetch(u):
 req=urllib.request.Request(u,headers={'User-Agent':'EdgeDeck personal sports research','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=18) as r:return json.load(r)
def parallel(jobs,workers=6):
 out=[]
 with ThreadPoolExecutor(workers) as pool:
  fs={pool.submit(fn,*args):key for key,fn,args in jobs}
  for f in as_completed(fs):
   key=fs[f]
   try:out.append((key,f.result()))
   except Exception as ex:ERRORS.append(f'{key}: {type(ex).__name__}')
 return out
def num(v):
 if isinstance(v,dict):v=v.get('value',v.get('displayValue'))
 try:return float(str(v).replace(',','').replace('%',''))
 except (TypeError,ValueError):return None
def iso(v):
 try:return dt.datetime.fromisoformat(v.replace('Z','+00:00'))
 except (AttributeError,ValueError):return NOW-dt.timedelta(days=1)
def clip(v,a=.01,b=.99):return max(a,min(b,v))
def cdf(x,mu,sd):return .5*(1+math.erf((x-mu)/(max(sd,.25)*math.sqrt(2))))
def implied(odds):return abs(odds)/(abs(odds)+100) if odds<0 else 100/(odds+100)
def dec(odds):return 1+100/abs(odds) if odds<0 else 1+odds/100
def fair(p):return round(-100*p/(1-p)) if p>=.5 else round(100*(1-p)/p)
def mean(a,default=0):return st.mean(a) if a else default

def event(e,sport):
 comps=e.get('competitions') or []
 if not comps:return None
 c=comps[0];sides={t.get('homeAway'):t for t in c.get('competitors',[])}
 if not {'home','away'}<=sides.keys():return None
 status=(c.get('status') or e.get('status') or {}).get('type',{})
 def team(t):
  x=t.get('team',{});return {'id':str(x.get('id',t.get('id',''))),'name':x.get('displayName',''),'abbr':x.get('abbreviation',''),'logo':x.get('logo'),'score':num(t.get('score')),'periods':[num(z.get('value')) for z in t.get('linescores',[])],'stats':{z['name']:num(z.get('displayValue')) for z in t.get('statistics',[]) if z.get('name')},'record':next((z.get('summary') for z in t.get('records',[]) if z.get('type')=='total'),None)}
 return {'id':sport+':'+str(e['id']),'espn_id':str(e['id']),'sport':sport,'event':e.get('name',''),'start':e.get('date'),'day':iso(e.get('date')).astimezone(ZoneInfo('America/Indiana/Indianapolis')).date().isoformat(),'home':team(sides['home']),'away':team(sides['away']),'final':bool(status.get('completed')),'state':status.get('state','pre'),'status':status.get('description',''),'odds':c.get('odds',[]),'venue':{'name':c.get('venue',{}).get('fullName'),'city':c.get('venue',{}).get('address',{}).get('city'),'state':c.get('venue',{}).get('address',{}).get('state'),'indoor':c.get('venue',{}).get('indoor')},'source_url':next((x['href'] for x in e.get('links',[]) if 'summary' in x.get('rel',[])),f'https://www.espn.com/{SPORTS[sport].split("/")[1]}/game/_/gameId/{e["id"]}')}
def scoreboard(sport,day):
 d=fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/scoreboard?dates={day.replace("-","")}&limit=200')
 return [x for e in d.get('events',[]) if (x:=event(e,sport))]
def schedule(sport,team):return fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/teams/{team}/schedule')
def summary(e):return fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[e["sport"]]}/summary?event={e["espn_id"]}')
def parse_box(d,e):
 rows=[]
 for block in d.get('boxscore',{}).get('players',[]):
  tid=str(block.get('team',{}).get('id',''))
  for group in block.get('statistics',[]):
   labels=group.get('labels') or group.get('names') or [];category=group.get('name','')
   for a in group.get('athletes',[]):
    if a.get('didNotPlay'):
     athlete=a.get('athlete',{});rows.append({'player_id':str(athlete.get('id','')),'player':athlete.get('displayName',''),'position':athlete.get('position',{}).get('abbreviation'),'team_id':tid,'event_id':e['id'],'start':e['start'],'sport':e['sport'],'stats':{},'did_not_play':True});continue
    raw=dict(zip(labels,a.get('stats',[])));stats={}
    mapping={'PTS':'Points','REB':'Rebounds','AST':'Assists','STL':'Steals','BLK':'Blocks','TO':'Turnovers','SOG':'Shots on goal','SV':'Saves','G':'Goals','A':'Assists','H':'Hits','R':'Runs','RBI':'RBIs','HR':'Home runs','BB':'Walks','SO':'Strikeouts','K':'Strikeouts','REC':'Receptions'}
    for k,v in raw.items():
     if k in mapping and num(v) is not None:stats[mapping[k]]=num(v)
    for k in ('3PT','3PM','3P'):
     if k in raw and num(str(raw[k]).split('-')[0]) is not None:stats['Threes']=num(str(raw[k]).split('-')[0])
    if 'MIN' in raw:
     v=str(raw['MIN']);parts=v.split(':');stats['Minutes']=(num(parts[0]) or 0)+(num(parts[1]) or 0)/60 if len(parts)>1 else num(v)
    if 'YDS' in raw:
     key={'passing':'Passing yards','rushing':'Rushing yards','receiving':'Receiving yards'}.get(category)
     if key and num(raw['YDS']) is not None:stats[key]=num(raw['YDS'])
    if 'TD' in raw and category in ('rushing','receiving'):stats['Touchdowns']=num(raw['TD']) or 0
    if 'C/ATT' in raw:stats['Completions']=num(str(raw['C/ATT']).split('/')[0]) or 0
    for label,key in [('ATT','Rush attempts'),('CAR','Rush attempts'),('TGT','Targets'),('TGTS','Targets'),('PA','Plate appearances'),('AB','Plate appearances'),('SA','Shots faced')]:
     if label in raw and num(raw[label]) is not None:stats[key]=num(raw[label])
    if 'C/ATT' in raw:stats['Pass attempts']=num(str(raw['C/ATT']).split('/')[-1])
    if 'TOI' in raw:
     parts=str(raw['TOI']).split(':');stats['Minutes']=(num(parts[0]) or 0)+(num(parts[1]) or 0)/60 if len(parts)>1 else num(raw['TOI'])
    if 'IP' in raw and num(raw['IP']) is not None:
     text=str(raw['IP']);whole,_,partial=text.partition('.');stats['Innings']=float(whole)+(int(partial or 0)/3)
    if 'Rush attempts' in stats or 'Receptions' in stats:stats['Touches']=(stats.get('Rush attempts') or 0)+(stats.get('Receptions') or 0)
    if not stats:continue
    athlete=a.get('athlete',{});pid=str(athlete.get('id',''))
    rows.append({'player_id':pid,'player':athlete.get('displayName',''),'position':athlete.get('position',{}).get('abbreviation'),'team_id':tid,'event_id':e['id'],'start':e['start'],'sport':e['sport'],'stats':stats,'source_url':next((z['href'] for z in athlete.get('links',[]) if z.get('href','').startswith('https://')),e['source_url'])})
 # Football players can appear in multiple categories. Merge, summing TD only.
 merged={}
 for r in rows:
  key=r['player_id']
  if key not in merged:merged[key]=r
  else:
   for k,v in r['stats'].items():merged[key]['stats'][k]=merged[key]['stats'].get(k,0)+v if k=='Touchdowns' else v
 return list(merged.values())
def injury_rows(d,e):
 out=[]
 for block in d.get('injuries',[]):
  for x in block.get('injuries',[]):
   a=x.get('athlete',{});out.append({'player_id':str(a.get('id','')),'player':a.get('displayName',''),'team_id':str(block.get('team',{}).get('id','')),'status':x.get('status','Unknown'),'detail':x.get('details',{}).get('type',''),'updated':x.get('date'),'event_id':e['id']})
 return out

def team_past(events,e,tid):return sorted([g for g in events.values() if g['sport']==e['sport'] and g.get('final') and iso(g.get('start'))<iso(e['start']) and tid in (g['home']['id'],g['away']['id'])],key=lambda g:g['start'])[-50:]
def team_factors(events,e,side):
 t=e[side];o=e['away' if side=='home' else 'home'];past=team_past(events,e,t['id']);opp=team_past(events,e,o['id']);base,sd=DEFAULTS[e['sport']]
 def scores(gs,tid):
  own=[];allowed=[]
  for g in gs:
   h=g['home']['id']==tid;a,b=(g['home'],g['away']) if h else (g['away'],g['home'])
   if a.get('score') is not None and b.get('score') is not None:own.append(a['score']);allowed.append(b['score'])
  return own,allowed
 own,allowed=scores(past,t['id']);oppown,oppallow=scores(opp,o['id']);mu=(mean(own,base)+mean(oppallow,base))/2
 rest=max(0,(iso(e['start'])-iso(past[-1]['start'])).total_seconds()/86400-1) if past else None
 if e['sport'] in ('NBA','WNBA','NCAAB') and rest is not None and rest<.5:mu*=.98
 mu+=({'NBA':1.5,'NFL':1.0,'NCAAF':1.5}.get(e['sport'],.25))*(1 if side=='home' else -1)
 return mu,{'games':len(own),'points_for':round(mean(own,base),1),'points_allowed':round(mean(allowed,base),1),'opponent_allowed':round(mean(oppallow,base),1),'rest_days':round(rest,1) if rest is not None else None,'back_to_back':rest is not None and rest<.5,'last5':own[-5:],'sd':max(sd,st.pstdev(own) if len(own)>2 else sd)}

def calibrate(history,key,p):
 # One immutable first forecast per event/entity/market/direction, fit past events only.
 cache_key=(id(history),len(history),key)
 if cache_key in CAL_CACHE:
  adj,n=CAL_CACHE[cache_key];return clip(p+adj),n
 groups={}
 for h in history:
  if h.get('model_version')!=MODEL or h.get('calibration_key')!=key or h.get('outcome') not in (0,1):continue
  groups.setdefault((h['event_id'],h.get('player_id'),h.get('market'),h.get('side')),h)
 rows=list(groups.values())[-500:];n=len(rows)
 adj=clip(mean([r['outcome']-r['raw_probability'] for r in rows]),-.08,.08)*n/(n+100) if n else 0
 CAL_CACHE[cache_key]=(adj,n)
 return clip(p+adj),n

def make_row(e,market,side,line,mu,sd,history,**extra):
 if market=='Moneyline':raw=1-cdf(0,mu,sd) if side=='home' else cdf(0,mu,sd)
 elif market=='Spread':raw=1-cdf(-line,mu,sd)
 else:
  # Half-point lines and count thresholds. Continuity correction for whole-number >= lines encoded as n-.5.
  raw=1-cdf(line,mu,sd) if side=='Over' else cdf(line,mu,sd)
 raw=extra.pop('raw_override',raw)
 raw=clip(raw,.025,.975);key=e['sport']+':'+market+':'+side
 p,n=calibrate(history,key,raw);odds=extra.get('odds');priced=odds is not None and abs(odds)>=100
 identifier='|'.join(str(x) for x in (MODEL,e['id'],extra.get('player_id','team'),market,extra.get('selection',''),side,line))
 identifier=hashlib.sha256(identifier.encode()).hexdigest()[:32]
 row={'id':identifier,'event_id':e['id'],'sport':e['sport'],'event':e['event'],'start':e['start'],'day':e['day'],'market':market,'side':side,'line':line,'projection':round(mu,2),'sd':round(sd,2),'raw_probability':round(raw,5),'probability':round(p,5),'fair_odds':fair(p),'calibration_key':key,'calibration_games':n,'model_version':MODEL,'source_url':e['source_url'],'odds':None,'bookmaker':None,'price_kind':'Suggested line','observed_at':NOW.isoformat(),'sample':0,'flags':[],**extra}
 row['break_even']=round(implied(odds),5) if priced else None;row['edge_pp']=round((p-implied(odds))*100,2) if priced else None;row['expected_roi_pct']=round((p*dec(odds)-1)*100,2) if priced else None
 row['qualified']=bool(priced and n>=100 and row['sample']>=10 and row['edge_pp']>=3 and not row['flags'])
 row.update(an.value_metrics(p,odds,extra.get('probability_margin',.08 if e['sport'] in ('NFL','NCAAF') and row['sample']<10 else .05)))
 if priced and row['sample']<10:row['value_status']='Insufficient sample'
 elif priced and (row['edge_pp'] or 0)>15:row['value_status']='Review market disagreement'
 row['research_score']=round(an.research_score(p,row['probability_margin'],odds,row['sample']),3)
 row['qualified']=bool(row['value_status']=='Provisional value' and n>=100 and row['sample']>=10 and not row['flags'])
 row['gradeable']=True
 return row

def extract_prices(e):
 books=e.get('odds') or []
 if not books:return {}
 o=sorted(books,key=lambda x:x.get('provider',{}).get('name')!='DraftKings')[0];book=o.get('provider',{}).get('name','ESPN-listed book');result={}
 def add(m,side,line,price):
  v=num(price)
  if v is not None and abs(v)>=100:result[(m,side)]={'line':line,'odds':int(v),'bookmaker':book,'price_kind':'Observed snapshot','odds_updated':NOW.isoformat()}
 for side in ('home','away'):
  a=o.get('moneyline',{}).get(side,{}).get('close',{});legacy=o.get(side+'TeamOdds',{})
  add('Moneyline',side,None,a.get('odds',legacy.get('moneyLine')))
  a=o.get('pointSpread',{}).get(side,{}).get('close',{})
  l=num(a.get('line'))
  if l is None:
   l=num(o.get('spread'))
   if side=='away' and l is not None:l=-l
  add('Spread',side,l,a.get('odds',legacy.get('spreadOdds')))
 for side in ('over','under'):
  a=o.get('total',{}).get(side,{}).get('close',{});line=num(str(a.get('line','')).lstrip('ou')) or num(o.get('overUnder'));add('Total',side,line,a.get('odds',o.get(side+'Odds')))
 return result

def team_rows(events,e,history):
 h,hf=team_factors(events,e,'home');a,af=team_factors(events,e,'away');m=h-a;sd=math.sqrt(hf['sd']**2+af['sd']**2);sample=min(hf['games'],af['games']);prices=extract_prices(e);rows=[]
 for side in ('home','away'):
  t=e[side];mu=m if side=='home' else -m;ctx=hf if side=='home' else af
  common={'team_id':t['id'],'selection':t['name'],'sample':sample,'context':ctx,'reasoning':f"Scoring form + opponent points allowed; {sample} paired team games available. Rest adjustment for basketball. No position-specific defensive model.",'flags':['Small sample'] if sample<10 else []}
  if e['sport'] in ('EPL','MLS'):
   masses=lambda mu:[math.exp(-mu)*mu**k/math.factorial(k) for k in range(16)]
   ph,pa=masses(max(.05,h)),masses(max(.05,a));win=sum(ph[i]*pa[j] for i in range(16) for j in range(16) if (i>j if side=='home' else j>i));common_ml={**common,'raw_override':win}
  else:common_ml=common
  q=prices.get(('Moneyline',side),{});rows.append(make_row(e,'Moneyline',side,None,m,sd,history,**common_ml,**{k:v for k,v in q.items() if k!='line'}))
  q=prices.get(('Spread',side));line=q['line'] if q and q['line'] is not None else round(-mu*2)/2+.5
  rows.append(make_row(e,'Spread',side,line,mu,sd,history,**common,**({k:v for k,v in q.items() if k!='line'} if q else {})))
  rows.append(make_row(e,'Team total','Over',max(.5,math.floor((h if side=='home' else a))-.5),h if side=='home' else a,ctx['sd'],history,**common))
 if e['sport'] in ('EPL','MLS'):
  draw=sum(math.exp(-h-a)*(h*a)**k/(math.factorial(k)**2) for k in range(16))
  rows.append(make_row(e,'Moneyline','draw',None,m,sd,history,selection='Draw',sample=sample,raw_override=draw,flags=['Unvalidated Poisson model']))
 for side in ('Over','Under'):
  q=prices.get(('Total',side.lower()));line=q['line'] if q and q['line'] is not None else math.floor(h+a)+.5
  rows.append(make_row(e,'Total',side,line,h+a,sd,history,selection=e['event'],sample=sample,context={'home':hf,'away':af},flags=['Small sample'] if sample<10 else [],**({k:v for k,v in q.items() if k!='line'} if q else {})))
 # Period markets from real period scores; never divide full-game forecasts by 2/4 and call them measured.
 for period,count in [('1st half total',2),('1st quarter total',1)]:
  if e['sport'] not in ('NBA','NFL','NCAAF','WNBA'):continue
  values=[]
  for g in {x['id']:x for x in team_past(events,e,e['home']['id'])+team_past(events,e,e['away']['id'])}.values():
   if len(g['home'].get('periods',[]))>=count and len(g['away'].get('periods',[]))>=count:
    v=g['home']['periods'][:count]+g['away']['periods'][:count]
    if all(x is not None for x in v):values.append(sum(v))
  if len(values)>=5:
   mu=mean(values);sig=max(st.pstdev(values),3)
   for side in ('Over','Under'):rows.append(make_row(e,period,side,math.floor(mu)+.5,mu,sig,history,selection=e['event'],sample=len(values),flags=['Unvalidated period model']))
 return rows

BASKET={'Points':(5,1),'Rebounds':(2,1),'Assists':(2,1),'PRA':(5,1),'Points + rebounds':(5,1),'Points + assists':(5,1),'Rebounds + assists':(2,1),'Threes':(1,1),'Steals':(1,1),'Blocks':(1,1)}
OTHER={'Passing yards':25,'Rushing yards':10,'Receiving yards':10,'Receptions':1,'Completions':2,'Touchdowns':1,'Shots on goal':1,'Saves':2,'Goals':1,'Hits':1,'Runs':1,'RBIs':1,'Home runs':1,'Strikeouts':1}
def wilson(hits,n):
 if not n:return None,None
 z=1.96;ph=hits/n;den=1+z*z/n;center=(ph+z*z/(2*n))/den;half=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
 return round(max(0,center-half),4),round(min(1,center+half),4)

def expanded(stats):
 s=dict(stats)
 for k,parts in {'PRA':['Points','Rebounds','Assists'],'Points + rebounds':['Points','Rebounds'],'Points + assists':['Points','Assists'],'Rebounds + assists':['Rebounds','Assists']}.items():
  if all(p in s for p in parts):s[k]=sum(s[p] for p in parts)
 return s

def player_rows(events,e,box,injuries,history):
 records=defaultdict(list)
 for b in box.values():
  for r in b:
   if not r.get('did_not_play') and r['sport']==e['sport'] and iso(r['start'])<NOW and iso(r['start'])<iso(e['start']):records[r['player_id']].append(r)
 rows=[];tidset={e['home']['id'],e['away']['id']};inj={r['player_id']:r for r in injuries if r['event_id']==e['id']}
 for pid,games in records.items():
  games.sort(key=lambda x:x['start']);latest=games[-1]
  if latest['team_id'] not in tidset or (NOW-iso(latest['start'])).days>45:continue
  if e.get('roster_ids') and pid not in e['roster_ids']:continue
  status=inj.get(pid,{}).get('status','Not listed')
  if status.lower() in ('out','suspension','suspended','injured reserve'):continue
  same_season=[g for g in games if an.season_key(e['sport'],g['start'])==an.season_key(e['sport'],e['start'])];current_team=[g for g in same_season if g['team_id']==latest['team_id']];recent=(current_team if len(current_team)>=5 else same_season)[-50:];sid='home' if latest['team_id']==e['home']['id'] else 'away';opp=e['away' if sid=='home' else 'home'];_,ctx=team_factors(events,e,sid);ctx['venue']=sid
  pos=an.position_group(e['sport'],latest.get('position') or POSITIONS.get(e['sport']+':'+pid));absence=[z for z in injuries if z['event_id']==e['id'] and z['team_id']==latest['team_id'] and z['status'].lower()=='out']
  mins=[x['stats']['Minutes'] for x in recent if (x['stats'].get('Minutes') or 0)>0]
  if e['sport'] in an.BASKET and (not mins or mean(mins[-5:])<14):continue
  for market in (BASKET if e['sport'] in an.BASKET else OTHER):
   pairs=[]
   for x in recent:
    v=expanded(x['stats']).get(market)
    if v is None:continue
    g=events.get(x['event_id']);own_side='home' if g and g['home']['id']==x['team_id'] else 'away'
    pairs.append(({**x,'venue':own_side},v))
   if len(pairs)<5:continue
   audit=an.sample_audit(pairs)
   unit,_=an.opportunities(market,e['sport'],pairs[-1][0]['stats'])
   matchup=an.opponent_adjustment(MATCHUP_INDEX,e['sport'],opp['id'],pos,market,unit)
   model=an.projection(pairs,market,e['sport'],ctx,matchup,status,[z['player_id'] for z in absence],box)
   weather=e.get('weather',{});wf=weather_feed.adjustment(e['sport'],market,weather);model['mu']*=wf;model['adjustments']['weather']=wf;model['flags']+=audit['flags']
   if audit['flags']:model['sd']*=1.10;model['probability_margin']=min(.12,model['probability_margin']+.02)
   if e['sport']=='NHL' and pos=='G':model['flags'].append('Starter unconfirmed')
   projection,sig=model['mu'],model['sd'];vals=[v for _,v in pairs];baseline=mean(vals);last5=mean(vals[-5:]);step=BASKET[market][1] if market in BASKET else OTHER[market]
   # Near-even to heavy-favorite alternate targets, on both sides of the projection.
   lines={max(.5,round(projection/step)*step-.5)}
   for z in (-1.2,-.55,.55,1.2):lines.add(max(.5,round((projection+z*sig)/step)*step-.5))
   log_key=e['id']+':'+pid+':'+market;logs=[]
   for x,v in pairs:
    g=events.get(x['event_id']);other=g['away' if x['venue']=='home' else 'home'] if g else {}
    logs.append({'date':x['start'],'value':v,'opponent':other.get('abbr') or other.get('name','Unknown'),'opponent_id':other.get('id'),'venue':x['venue'],'minutes':x['stats'].get('Minutes'),'event_id':x['event_id']})
   PLAYER_LOGS[log_key]={'games':logs[-25:],'opponent_id':opp['id'],'opponent':opp['name'],'residuals':model['residuals'],'sample':len(vals)}
   for line in sorted(lines):
    for side in ('Over','Under'):
     hits=[int(v>line) if side=='Over' else int(v<line) for v in vals];streak=0
     for hit in reversed(hits):
      if not hit:break
      streak+=1
     ci_low,ci_high=wilson(sum(hits),len(hits));raw=an.tail_probability(line,side,projection,sig,model['residuals'])
     chart_context={**ctx,'position':pos,'opponent_position':matchup,'exposure_unit':model['unit'],'expected_exposure':model['exposure'],'baseline_exposure':model['baseline_exposure'],'last5_exposure':model['last5_exposure'],'baseline_rate':model['baseline_rate'],'last5_rate':model['last5_rate'],'base_projection':model['base_projection'],'adjustments':model['adjustments'],'teammate_absences':[z['player'] for z in absence],'absence_split_games':model['absence_split_games'],'sample_audit':audit,'weather':weather}
     r=make_row(e,market,side,line,projection,sig,history,raw_override=raw,player_id=pid,player=latest['player'],selection=latest['player'],team_id=latest['team_id'],position=pos,sample=len(vals),flags=list(model['flags']),source_url=latest['source_url'],injury_status=status,baseline=round(baseline,2),last5=round(last5,2),trend_pct=round((last5/baseline-1)*100,1) if baseline else 0,hit_rate=round(mean(hits),4),hit_rate_low=ci_low,hit_rate_high=ci_high,last5_hits=sum(hits[-5:]),last10_hits=sum(hits[-10:]),streak=streak,projected_minutes=round(model['exposure'],1) if model['unit']=='Minutes' and model['exposure'] else None,per_minute=round(model['rate'],4) if model['unit']=='Minutes' and model['rate'] is not None else None,rate=model['rate'],exposure_unit=model['unit'],expected_exposure=model['exposure'],probability_margin=model['probability_margin'],log_key=log_key,context=chart_context,reasoning='Projected opportunities × recent/season-window production rate × shrunk opponent allowance for the same position and stat. Venue splits require data; rest is a modest heuristic. Teammate usage only adjusts with recorded DNP split evidence. Empirical residuals and a normal tail form a provisional ensemble; uncertainty is priced explicitly.')
     neutral=an.tail_probability(line,side,baseline,max(st.pstdev(vals),.8),[v-baseline for v in vals]);market_proxy=clip(neutral*1.04,.025,.975)
     r['estimated_price']=fair(market_proxy);r['estimated_price_method']='Historical baseline probability with illustrative 4% overround; not a sportsbook-fitted quote.'
     r['conditional_edge_pp']=round((r['probability']-market_proxy)*100,2);r['conditional_roi_pct']=round((r['probability']*an.decimal(r['estimated_price'])-1)*100,2)
     if r['odds'] is None:r['research_score']=round(r['conditional_roi_pct']-r['probability_margin']*100+min(r['sample'],25)*.1,3)
     rows.append(r)
 return rows

def settle(r,e,box):
 if not e.get('final'):return None
 market=r.get('market','Moneyline');line=r.get('line');side=r.get('side');actual=None
 if r.get('player_id'):
  found=next((x for x in box.get(e['id'],[]) if x['player_id']==r['player_id']),None)
  # Missing player may be DNP or incomplete data: don't infer a loss or void.
  if not found:return None
  actual=expanded(found['stats']).get(market)
 elif market=='Moneyline':
  if e['sport'] in ('EPL','MLS'):
   if side=='draw':return int(e['home']['score']==e['away']['score'])
   return int(e[side]['score']>e['away' if side=='home' else 'home']['score'])
  if e['home']['score']==e['away']['score']:return 'push'
  if side not in ('home','away'):side='home' if r.get('selection')==e['home']['name'] else 'away'
  return int(e[side]['score']>e['away' if side=='home' else 'home']['score'])
 elif market=='Spread':actual=e[side]['score']-e['away' if side=='home' else 'home']['score']+line;line=0;side='Over'
 elif market=='Total':actual=e['home']['score']+e['away']['score']
 elif market=='Team total':actual=next((e[s]['score'] for s in ('home','away') if e[s]['id']==r.get('team_id')),None)
 elif market in ('1st half total','1st quarter total'):
  n=2 if market=='1st half total' else 1
  ps=e['home'].get('periods',[])[:n]+e['away'].get('periods',[])[:n]
  if len(ps)==2*n and all(v is not None for v in ps):actual=sum(ps)
 if actual is None or line is None:return None
 if actual==line:return 'push'
 return int(actual>line) if side=='Over' else int(actual<line)

def main():
 global MATCHUP_INDEX,POSITIONS
 events=read('events.json',{});history=record_store.read_history(DATA);shortlist=read('shortlist_history.json',[]);daily_ledger=read('daily_history.json',[]);research_ledger=read('research_ticket_history.json',[]);cache=read('cache.json',{'box':{},'schedules':{},'rosters':{}});box=cache['box']
 # Normalize legacy records; keep existing immutable forecast probabilities.
 for e in events.values():
  e.setdefault('espn_id',e['id'].split(':')[-1]);e.setdefault('state','post' if e.get('final') else 'pre');e.setdefault('source_url','https://www.espn.com');e.setdefault('odds',[])
  for side in ('home','away'):e[side].setdefault('periods',[]);e[side].setdefault('stats',{});e[side].setdefault('abbr',e[side]['name'])
 jobs=[]
 for sport in SPORTS:
  offsets=range(-1,8)
  for off in offsets:jobs.append((f'{sport}:{off}',scoreboard,(sport,(TODAY+dt.timedelta(days=off)).isoformat())))
 for key,gs in parallel(jobs):
  for e in gs:events[e['id']]=e
 # Revisit pending forecasts older than yesterday once per run by date/sport.
 pending={(r['sport'],iso(r.get('start')).date().isoformat()) for r in history if r.get('outcome') is None and iso(r.get('start'))<NOW-dt.timedelta(days=1) and r['sport'] in SPORTS}
 for _,gs in parallel([(f'pending:{s}:{d}',scoreboard,(s,d)) for s,d in pending]):
  for e in gs:events[e['id']]=e
 future=[]
 for sport in SPORTS:
  future+=sorted([e for e in events.values() if e['sport']==sport and not e.get('final') and e.get('state')=='pre' and NOW<iso(e['start'])<NOW+dt.timedelta(days=7)],key=lambda e:e['start'])[:40]
 future.sort(key=lambda e:e['start'])
 extra_events=extra_fixtures.collect(fetch,parallel,NOW,ERRORS)
 if cache.get('schedule_window_version')!=120:cache['schedules']={};cache['schedule_window_version']=120
 # Cache past team schedules daily; bootstrap real season-window samples.
 teams={(e['sport'],e[s]['id']) for e in future for s in ('home','away') if e['sport'] not in ('EPL','MLS')}
 jobs=[]
 for sport,tid in teams:
  key=sport+':'+tid
  if cache['schedules'].get(key)!=TODAY.isoformat():jobs.append((key,schedule,(sport,tid)))
 for key,d in parallel(jobs):
  sport=key.split(':')[0]
  for raw in d.get('events',[]):
   e=event(raw,sport)
   if e and e['final'] and NOW-dt.timedelta(days=120)<iso(e['start'])<NOW:events[e['id']]=e
  cache['schedules'][key]=TODAY.isoformat()
 write('cache.json',cache);write('events.json',events)
 # Current rosters prevent stale traded-player membership. Daily cache; report missing roster explicitly.
 def roster(sport,tid):return fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/teams/{tid}/roster')
 jobs=[]
 for sport,tid in teams:
  key=sport+':'+tid
  if (cache['rosters'].get(key,{}).get('day')!=TODAY.isoformat() or not cache['rosters'].get(key,{}).get('positions') or not cache['rosters'].get(key,{}).get('images')):jobs.append((key,roster,(sport,tid)))
 for key,d in parallel(jobs):
  athletes=[]
  for item in d.get('athletes',[]):
   athletes.extend(item.get('items',[])) if 'items' in item else athletes.append(item)
  ids=[str(a['id']) for a in athletes if 'id' in a];positions={str(a['id']):a.get('position',{}).get('abbreviation','Unknown') for a in athletes if 'id' in a}
  if ids:cache['rosters'][key]={'day':TODAY.isoformat(),'ids':ids,'positions':positions,'images':{str(a['id']):a.get('headshot',{}).get('href') for a in athletes if 'id' in a}}
 for key,r in cache['rosters'].items():
  sport=key.split(':')[0]
  for pid,pos in r.get('positions',{}).items():POSITIONS[sport+':'+pid]=pos
 for e in future:
  ids=sum([cache['rosters'].get(e['sport']+':'+e[s]['id'],{}).get('ids',[]) for s in ('home','away')],[])
  if ids:e['roster_ids']=ids
 # Backfill a bounded set of final boxscores; completed boxes retained, recent missing boxes retried.
 needed={}
 for e in future:
  if e['sport'] not in ('NBA','WNBA','NFL','NHL','MLB','NCAAF','NCAAB'):continue
  for side in ('home','away'):
   for g in team_past(events,e,e[side]['id'])[-50:]:
    existing=box.get(g['id'],[])
    migrate=g['sport'] in ('NFL','NCAAF','NHL','MLB') and existing and not any(x.get('schema_version')==3 for x in existing)
    if not existing or migrate:needed[g['id']]=g
 for r in history+[leg for t in daily_ledger for leg in t['legs']]:
  if r.get('outcome') is None and r.get('player_id') and r['event_id'] in events and events[r['event_id']].get('final'):needed[r['event_id']]=events[r['event_id']]
 # Prioritize NBA player model on initial backfill, then other leagues. 180 max per run.
 target=sorted(needed.values(),key=lambda e:(e['sport']!='NBA',-iso(e['start']).timestamp()))[:180]
 for key,d in parallel([(e['id'],summary,(e,)) for e in target]):
  # Keep observed period scores from the summary for first-half/quarter models.
  observed=event(d.get('header',{}),events[key]['sport']) if d.get('header',{}).get('id') else None
  if observed:
   for side in ('home','away'):
    if observed[side].get('periods'):events[key][side]['periods']=observed[side]['periods']
  rows=parse_box(d,events[key])
  if rows:
   for r in rows:r['schema_version']=3
   box[key]=rows
 write('cache.json',cache);write('events.json',events)
 # Pregame summaries supply fresh injury flags and fallback odds snapshots.
 injuries=[]
 news=news_feed.collect(SPORTS|{'PGA':'golf/pga','ATP':'tennis/atp','WTA':'tennis/wta','UFC':'mma/ufc'},fetch,parallel,NOW,cache)
 for key,d in parallel([(e['id'],summary,(e,)) for e in future]):
  e=events[key];injuries+=injury_rows(d,e)
  if not e.get('odds'):e['odds']=d.get('pickcenter',[])
 write('cache.json',cache);write('events.json',events)
 for r in history+shortlist:
  if r.get('outcome') is not None:continue
  e=events.get(r['event_id'])
  if not e:continue
  result=settle(r,e,box)
  if result is not None:
   r['outcome']=result;r['graded_at']=NOW.isoformat();r['profit_units']=0 if result=='push' else round(dec(r['odds'])-1 if result else -1,4) if r.get('odds') else None
 weather_context=weather_feed.collect(future,cache,fetch,NOW)
 for e in future:e['weather']=weather_context.get(e['id'],{'status':'Unavailable'})
 MATCHUP_INDEX=an.build_matchups(events,box,POSITIONS,expanded,NOW.isoformat())
 rows=[]
 for e in future:
  rows+=team_rows(events,e,history);rows+=player_rows(events,e,box,injuries,history)
 forecasts={}
 for r in rows:
  if r['market']=='Total':forecasts.setdefault(r['event_id'],{})['total']=r['projection']
  if r['market']=='Moneyline' and r['side']=='home':forecasts.setdefault(r['event_id'],{})['margin']=r['projection']
 scores={k:{'home':round((v['total']+v['margin'])/2,1),'away':round((v['total']-v['margin'])/2,1)} for k,v in forecasts.items() if 'total' in v and 'margin' in v}
 for r in rows:
  if daily.eligible(r,TODAY.isoformat(),NOW.isoformat()) or daily.eligible(r,TODAY.isoformat(),NOW.isoformat(),True):r['rationale']=pick_evidence.build(r,events,injuries,PLAYER_LOGS,scores)
 research=[]
 for sport in daily.SPORTS:
  candidates=[r for r in rows if r['sport']==sport and daily.in_window(r,NOW.isoformat()) and r.get('player_id') and r.get('odds') is None and r.get('sample',0)>=(8 if sport in ('NFL','NCAAF') else 10) and .8<=r['probability']<=.9 and (r.get('hit_rate') or 0)>=.8 and not any(any(term in f.lower() for term in ('questionable','doubtful','day-to-day','outlier','role changed','minutes volatility','unresolved','starter unconfirmed','opportunity data missing')) for f in r.get('flags',[]))]
  used_games=set();used_players=set()
  for r in sorted(candidates,key=lambda r:(min(r['probability_floor'],r['hit_rate']),r.get('sample',0)),reverse=True):
   if r['event_id'] in used_games or r['player_id'] in used_players:continue
   watch={k:v for k,v in r.items() if k not in ('context','reasoning','recent_values')};watch['rationale']=pick_evidence.build(r,events,injuries,PLAYER_LOGS,scores);research.append(watch);used_games.add(r['event_id']);used_players.add(r['player_id'])
   if len(used_games)>=10:break
 daily_current,daily_summary,daily_availability=daily.update(daily_ledger,rows,TODAY.isoformat(),NOW.isoformat(),events,box,settle)
 research_current,research_summary=daily.update_research(research_ledger,research,TODAY.isoformat(),NOW.isoformat(),events,box,settle)
 research_current=copy.deepcopy(research_current)
 for ticket in research_current:ticket['current_review']=news_feed.review(ticket,rows,events,injuries,news,NOW.isoformat())
 # A fresh review is separate from immutable forecast fields.
 daily_current=copy.deepcopy(daily_current)
 for ticket in daily_current:ticket['current_review']=news_feed.review(ticket,rows,events,injuries,news,NOW.isoformat())
 for r in research:r['current_review']=news_feed.review({'legs':[r]},rows,events,injuries,news,NOW.isoformat())
 # Freeze a separate recommended portfolio, one first selection per game.
 priced_candidates=[r for r in rows if r.get('value_status')=='Provisional value' and r['sample']>=8 and not any(x.lower() in ('questionable','doubtful','out','minutes volatility') for x in r['flags'])]
 unpriced_candidates=[r for r in rows if r.get('player_id') and r.get('odds') is None and r['sample']>=8 and .52<=r['probability'] and an.price_in_band(r.get('estimated_price')) and not any(x.lower() in ('questionable','doubtful','out','minutes volatility') for x in r['flags'])]
 candidates=sorted(priced_candidates,key=lambda r:r['research_score'],reverse=True)+sorted(unpriced_candidates,key=lambda r:r['research_score'],reverse=True)
 portfolio_seen={r['event_id'] for r in shortlist if r.get('model_version')==MODEL};featured=[];featured_games=set()
 for r in candidates:
  if r['event_id'] in featured_games:continue
  featured.append(r['id']);featured_games.add(r['event_id'])
  if r['event_id'] not in portfolio_seen:
   shortlist.append({k:v for k,v in r.items() if k not in ('context','reasoning','recent_values')}|{'predicted_at':NOW.isoformat(),'outcome':None});portfolio_seen.add(r['event_id'])
  if len(featured)>=10:break
 # Record one pregame forecast for each exact suggested line; never mutate it when refreshing.
 seen={r['id'] for r in history}
 for r in rows:
  if r['id'] not in seen and iso(r['start'])>NOW:
   h={k:v for k,v in r.items() if k not in ('context','reasoning','recent_values')};h['predicted_at']=NOW.isoformat();h['outcome']=None;history.append(h);seen.add(r['id'])
 settled=[r for r in history if r.get('outcome') in (0,1)];priced=[r for r in settled if r.get('profit_units') is not None]
 # Each event/player/market/side gets one equal-weight contribution to avoid counting many alternate lines as independent evidence.
 groups=defaultdict(list)
 for r in settled:groups[(r['event_id'],r.get('player_id'),r.get('market','Moneyline'),r.get('side'))].append(r)
 brier=mean([mean([(r['probability']-r['outcome'])**2 for r in rs]) for rs in groups.values()],None)
 bins=[]
 for lo in (0,.5,.6,.7,.8,.9):
  hi=.5 if lo==0 else lo+.1;rs=[r for r in settled if lo<=r['probability']<hi];bins.append({'from':lo,'to':round(hi,2),'n':len(rs),'predicted':mean([r['probability'] for r in rs],None),'actual':mean([r['outcome'] for r in rs],None)})
 featured_settled=[r for r in shortlist if r.get('outcome') in (0,1)]
 sport_metrics={};sport_bins={}
 for sport in daily.SPORTS:
  hs=[r for r in history if r['sport']==sport];ss=[r for r in hs if r.get('outcome') in (0,1)]
  sg=defaultdict(list)
  for r in ss:sg[(r['event_id'],r.get('player_id'),r.get('market'),r.get('side'))].append(r)
  sport_bins[sport]=[{'from':lo,'to':.5 if lo==0 else round(lo+.1,2),'n':len(br),'actual':mean([r['outcome'] for r in br],None)} for lo in (0,.5,.6,.7,.8,.9) for br in [[r for r in ss if lo<=r['probability']<(.5 if lo==0 else lo+.1)]]]
  sport_metrics[sport]={'independent_groups':len(sg),'tracked_predictions':len(hs),'settled_predictions':len(ss),'won':sum(r['outcome'] for r in ss),'brier_score':round(mean([mean([(r['probability']-r['outcome'])**2 for r in rs]) for rs in sg.values()]),4) if sg else None}
 profiles={}
 for key,roster_data in cache['rosters'].items():
  sport=key.split(':')[0]
  for pid,url in roster_data.get('images',{}).items():
   if url:profiles[sport+':'+pid]={'headshot':url}
 report={'extra_fixtures':extra_events,'research_tickets':research_current,'research_summary':research_summary,'news':news,'selection_window_days':7,'daily_research':research,'daily_policy':daily.POLICY,'sport_calibration_bins':sport_bins,'daily_picks':daily_current,'daily_summary':daily_summary,'daily_availability':daily_availability,'sport_metrics':sport_metrics,'player_profiles':profiles,'player_logs':PLAYER_LOGS,'ranking_policy':{'odds_min':-200,'odds_max':200,'min_edge_pp':3,'min_roi_pct':5,'description':'Actual quoted prices first; require positive buffered edge. Unpriced lines are price-check research targets, never verified bets.'},'featured_ids':featured,'portfolio_metrics':{'tracked':len(shortlist),'settled':len(featured_settled),'won':sum(r['outcome'] for r in featured_settled),'hit_ratio':mean([r['outcome'] for r in featured_settled],None),'brier':mean([(r['probability']-r['outcome'])**2 for r in featured_settled],None)},'version':MODEL,'generated_at':NOW.isoformat(),'day':TODAY.isoformat(),'refresh_minutes':15,'recommendations':rows,'games':future,'injuries':injuries,'metrics':{'tracked_predictions':len(history),'settled_predictions':len(settled),'won':sum(r['outcome'] for r in settled),'brier_score':round(brier,4) if brier is not None else None,'independent_groups':len(groups),'priced_settled':len(priced),'realized_roi_pct':round(100*sum(r['profit_units'] for r in priced)/len(priced),2) if priced else None},'calibration_bins':bins,'coverage':list(SPORTS),'source':'ESPN public scoreboards / boxscores / injury reports; DraftKings game odds where supplied by ESPN','errors':ERRORS,'backfill_remaining':max(0,len(needed)-len(target)),'limitations':['Player-prop prices are not provided by the free game feed. Suggested lines are model thresholds, not sportsbook offers.','Normal-distribution model estimates are provisional, especially for rare events. No 90% estimate is validated yet.','Position defense uses roster role buckets, not player tracking or confirmed individual matchups. Opportunity data gaps are neutral adjustments, not fabricated inputs.','No automatic odds feeds for golf, tennis or UFC; exact markets can be imported locally.','Missing player participation remains pending for review, never automatically graded as a loss.']}
 # No destructive retention of forecast history. Cache excludes bulky raw feed payloads.
 keep={'id','event_id','sport','selection','player_id','market','side','line','team_id','start','day','probability','raw_probability','odds','bookmaker','model_version','calibration_key','predicted_at','outcome','graded_at','profit_units','probability_floor','probability_margin','value_status','edge_pp','expected_roi_pct'}
 history=[{k:v for k,v in r.items() if k in keep} for r in history]
 write('events.json',events);record_store.write_history(DATA,history);record_store.write_report(DATA,report);write('cache.json',cache);write('shortlist_history.json',shortlist);write('daily_history.json',daily_ledger);write('research_ticket_history.json',research_ledger)
 print(f'{len(future)} upcoming games | {len(rows)} lines | {sum(bool(r.get("player_id")) for r in rows)} player lines | {len(settled)} settled | {len(ERRORS)} feed errors')
if __name__=='__main__':main()
