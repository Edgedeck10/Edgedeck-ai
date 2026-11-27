"""EdgeDeck v2: public scores, market snapshots, pregame team and player models.
Standard library only. No paid endpoints, keys, or automated betting.
"""
import gzip
import json, math, pathlib, datetime as dt, urllib.request, statistics as st, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from zoneinfo import ZoneInfo
import actuarial
import matchup
import ai_record
import nextgen
import feed_transport
import football_weather
ROOT=pathlib.Path(__file__).parent; DATA=ROOT/'data'/'classic'; DATA.mkdir(parents=True,exist_ok=True)
NOW=dt.datetime.now(dt.timezone.utc); TODAY=NOW.astimezone(ZoneInfo('America/Indiana/Indianapolis')).date()
SPORTS={'NBA':'basketball/nba','NFL':'football/nfl','NHL':'hockey/nhl','MLB':'baseball/mlb','NCAAF':'football/college-football','NCAAB':'basketball/mens-college-basketball','WNBA':'basketball/wnba','EPL':'soccer/eng.1','MLS':'soccer/usa.1'}
DEFAULTS={'NBA':(112,15),'NCAAB':(74,12),'WNBA':(81,12),'NFL':(23,10),'NCAAF':(28,15),'MLB':(4.5,3),'NHL':(3,1.8),'EPL':(1.4,1.3),'MLS':(1.5,1.4)}
BASE_MODEL='opportunity-4.2.0'
MODEL='opportunity-4.4.0'
def model_for(sport):return MODEL if sport in football_weather.SPORTS else BASE_MODEL
ERRORS=[]; CAL_CACHE={}; PLAYER_LOGS={}
COMPRESSED={'latest.json','history.json','cache.json','ai_picks.json','history-view.json','pick-record.json'}
def read(n,d):
 packed=DATA/(n+'.gz')
 if packed.exists():
  # Corrupt archives must fail the run rather than silently erase history.
  return json.loads(gzip.decompress(packed.read_bytes()))
 try:return json.loads((DATA/n).read_text())
 except FileNotFoundError:return d

def write(n,v):
 payload=json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
 target=DATA/(n+'.gz' if n in COMPRESSED else n)
 temporary=target.with_name(target.name+'.tmp')
 temporary.write_bytes(gzip.compress(payload,compresslevel=6,mtime=0) if n in COMPRESSED else payload)
 temporary.replace(target)
 if n in COMPRESSED:(DATA/n).unlink(missing_ok=True)
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
 return {'id':sport+':'+str(e['id']),'espn_id':str(e['id']),'sport':sport,'event':e.get('name',''),'start':e.get('date'),'day':iso(e.get('date')).astimezone(ZoneInfo('America/Indiana/Indianapolis')).date().isoformat(),'home':team(sides['home']),'away':team(sides['away']),'final':bool(status.get('completed')),'state':status.get('state','pre'),'status':status.get('description',''),'odds':c.get('odds',[]),'venue':football_weather.venue_fields(c.get('venue')) if sport in football_weather.SPORTS else None,'source_url':next((x['href'] for x in e.get('links',[]) if 'summary' in x.get('rel',[])),f'https://www.espn.com/{SPORTS[sport].split("/")[1]}/game/_/gameId/{e["id"]}')}
def scoreboard(sport,day):
 division="&groups=90" if sport=="NCAAF" else ""
 d=fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/scoreboard?dates={day.replace("-","")}&limit=200{division}')
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
    if a.get('didNotPlay'):continue
    raw=dict(zip(labels,a.get('stats',[])));stats={}
    mapping={'PTS':'Points','REB':'Rebounds','AST':'Assists','STL':'Steals','BLK':'Blocks','TO':'Turnovers','SOG':'Shots on goal','SV':'Saves','G':'Goals','A':'Assists','H':'Hits','R':'Runs','RBI':'RBIs','HR':'Home runs','BB':'Walks','SO':'Strikeouts','K':'Strikeouts','REC':'Receptions'}
    for k,v in raw.items():
     # REC in a football fumbles table means recoveries, not catches.
     if k=='REC' and e['sport'] in ('NFL','NCAAF') and category!='receiving':continue
     if k in mapping and num(v) is not None:stats[mapping[k]]=num(v)
    for k in ('3PT','3PM','3P'):
     if k in raw and num(str(raw[k]).split('-')[0]) is not None:stats['Threes']=num(str(raw[k]).split('-')[0])
    if 'TOI' in raw and 'MIN' not in raw:raw['MIN']=raw['TOI']
    if 'MIN' in raw:
     v=str(raw['MIN']);parts=v.split(':');stats['Minutes']=(num(parts[0]) or 0)+(num(parts[1]) or 0)/60 if len(parts)>1 else num(v)
    for source,target in [('3PT','Three attempts'),('FG','Field goal attempts'),('FT','Free throw attempts')]:
     if source in raw and '-' in str(raw[source]):stats[target]=num(str(raw[source]).split('-')[-1])
    for source,target in [('TGTS','Targets'),('TGT','Targets'),('SA','Shots faced'),('SH','Shots'),('S','Shots'),('ST','Shots on target'),('AB','At bats')]:
     if source in raw:stats[target]=num(raw[source])
    if 'ATT' in raw and category=='rushing':stats['Carries']=num(raw['ATT'])
    if 'C/ATT' in raw:stats['Pass attempts']=num(str(raw['C/ATT']).split('/')[-1])
    if 'YDS' in raw:
     key={'passing':'Passing yards','rushing':'Rushing yards','receiving':'Receiving yards'}.get(category)
     if key and num(raw['YDS']) is not None:stats[key]=num(raw['YDS'])
    if 'TD' in raw and category in ('rushing','receiving'):stats['Touchdowns']=num(raw['TD']) or 0
    if 'C/ATT' in raw:stats['Completions']=num(str(raw['C/ATT']).split('/')[0]) or 0
    if e['sport']=='NHL' and 'S' in raw and num(raw['S']) is not None:stats['Shots on goal']=num(raw['S'])
    if not stats:continue
    athlete=a.get('athlete',{});pid=str(athlete.get('id',''))
    position=(athlete.get('position') or {}).get('abbreviation')
    rows.append({'position':position,'player_id':pid,'player':athlete.get('displayName',''),'team_id':tid,'event_id':e['id'],'start':e['start'],'sport':e['sport'],'stats':stats,'source_url':next((z['href'] for z in athlete.get('links',[]) if z.get('href','').startswith('https://')),e['source_url'])})
 # Football players can appear in multiple categories. Merge, summing TD only.
 merged={}
 for r in rows:
  key=r['player_id']
  if key not in merged:merged[key]=r
  else:
   if not merged[key].get('position'):merged[key]['position']=r.get('position')
   for k,v in r['stats'].items():
    if r['sport']=='NHL' and k=='Shots on goal' and k in merged[key]['stats']:continue
    merged[key]['stats'][k]=merged[key]['stats'].get(k,0)+v if k=='Touchdowns' else v
 return list(merged.values())
def unavailable(status):
 status=re.sub(r'[^a-z]+',' ',str(status).lower()).strip()
 return status in {'out','doubtful','inactive','released','not on current roster','ir','pup','suspended','suspension','reserve injured'} or any(
  term in status for term in ('injured reserve','physically unable','reserve pup','injury reserve','out for season'))

def injury_rows(d,e):
 out=[]
 teams={e[s]['id'] for s in ('home','away')}
 for block in d.get('injuries',[]) or []:
  tid=str((block.get('team') or {}).get('id') or block.get('id',''))
  if tid not in teams:continue
  for x in block.get('injuries',[]):
   a=x.get('athlete') or {}
   player_id=a.get('id')
   if player_id is None:
    for link in a.get('links',[]):
     if 'playercard' not in link.get('rel',[]):continue
     match=re.search(r'/_/id/(\d+)(?:/|$)',link.get('href',''))
     if match:player_id=match.group(1);break
   if player_id is None:continue
   out.append({'player_id':str(player_id),'player':a.get('displayName',''),'team_id':tid,
    'position':(a.get('position') or {}).get('abbreviation',''),'status':x.get('status') or 'Unknown',
    'detail':(x.get('details') or {}).get('type',''),'updated':x.get('date'),'event_id':e['id']})
 return out

def injury_date(value):
 if not value:return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
 parsed=iso(value)
 return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)

def collect_availability(future):
 # A league-wide injury feed covers reserves omitted from individual game previews.
 def league_injuries(sport):
  return fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/injuries?limit=1000')
 league=dict(parallel([(s,league_injuries,(s,)) for s in {g['sport'] for g in future} if s in ('NFL','NBA','WNBA','NHL','MLB')]))
 previews=dict(parallel([(e['id'],summary,(e,)) for e in future]))
 all_rows=[]
 for e in future:
  d=previews.get(e['id'],{})
  if not e.get('odds'):e['odds']=d.get('pickcenter',[])
  if e['sport'] in football_weather.SPORTS:
   venue=football_weather.venue_fields((d.get('gameInfo') or {}).get('venue'))
   # Only merge fields from this game's venue, including neutral-site games.
   e['venue']={**(e.get('venue') or {}),**{k:v for k,v in venue.items() if v is not None}}
  by_player={}
  for row in injury_rows(league.get(e['sport'],{}),e)+injury_rows(d,e):
   old=by_player.get(row['player_id'])
   if old is None or injury_date(row['updated'])>injury_date(old['updated']) or (
      injury_date(row['updated'])==injury_date(old['updated']) and unavailable(row['status'])):
    by_player[row['player_id']]=row
  # Official team reports supplement a missing or delayed injury feed for this fixture.
  if e['sport']=='NFL' and e['day']=='2026-11-25' and {str(e['home']['id']),str(e['away']['id'])}=={'9','14'}:
   by_player['4426515']={'player_id':'4426515','player':'Puka Nacua','team_id':next(e[s]['id'] for s in ('home','away') if str(e[s]['id'])=='14'),'position':'WR','status':'Injured Reserve','detail':'Knee and toe injuries','updated':'2026-11-19','event_id':e['id'],'source_url':'https://www.therams.com/news/mcvay-rams-placed-puka-nacua-on-ir-because-they-needed-the-roster-spot-week-10-2026-cardinals'}
   parsons=by_player.get('4361423') or {'player_id':'4361423','player':'Micah Parsons','team_id':next(e[s]['id'] for s in ('home','away') if str(e[s]['id'])=='9'),'event_id':e['id']}
   if injury_date(parsons.get('updated'))<iso('2026-11-24T19:25Z'):
    parsons.update(status='Questionable',updated='2026-11-24T19:25Z')
   parsons.update(position='EDGE',detail='Activated from PUP; game status and snap count may differ',source_url='https://www.packers.com/news/packers-activate-micah-parsons-off-pup-nov-24-2026')
   by_player['4361423']=parsons
  all_rows.extend(by_player.values())
 return all_rows

def team_past(events,e,tid):return sorted([g for g in events.values() if g['sport']==e['sport'] and g.get('final') and iso(g.get('start'))<iso(e['start']) and tid in (g['home']['id'],g['away']['id'])],key=lambda g:g['start'])[-20:]
def football_roster(data):
 groups=data.get('athletes') or []
 players={};statuses={}
 for group in groups:
  tag=group.get('position','')
  for athlete in group.get('items',[]) if 'items' in group else [group]:
   if athlete.get('id') is None:continue
   pid=str(athlete['id'])
   players[pid]=athlete.get('displayName') or athlete.get('fullName','')
   status=(athlete.get('status') or {}).get('name','')
   if unavailable(status):statuses[pid]=(players[pid],(athlete.get('position') or {}).get('abbreviation',''),status)
 tags={group.get('position') for group in groups}
 active_count=sum(len(g.get('items',[])) for g in groups if g.get('position') in ('offense','defense'))
 # A truncated or one-sided roster cannot establish that a player is gone.
 return {'players':players,'statuses':statuses,'complete':{'offense','defense'}<=tags and active_count>=40}

def reconcile_football_availability(events, fixture, boxes, statuses):
 by_player={(r['team_id'],r['player_id']):r for r in statuses}
 for side in ('home','away'):
  tid=fixture[side]['id'];roster=fixture.get('football_rosters',{}).get(tid,{})
  def record(pid,name,position,status,detail,source=None):
   by_player[tid,pid]={'player_id':pid,'player':name,'position':position,'team_id':tid,
     'status':status,'detail':detail,'event_id':fixture['id'],'source_url':source}
  for pid,(name,position,status) in roster.get('statuses',{}).items():
   if not unavailable(by_player.get((tid,pid),{}).get('status')):
    record(pid,name,position,status,'Current ESPN team roster designation')
  if roster.get('complete'):
   for game in team_past(events,fixture,tid)[-4:]:
    for row in boxes.get(game['id'],[]):
     pid=row['player_id']
     if not pid or row['team_id']!=tid or pid in roster['players']:continue
     if not unavailable(by_player.get((tid,pid),{}).get('status')):
      record(pid,row['player'],row.get('position') or '', 'Not on current roster',
        'Recent contributor missing from the verified team roster')
  if fixture['id']=='NFL:401873083' and tid=='23':
   record('8439','Aaron Rodgers','QB','Released','Steelers released Rodgers November 25',
          'https://www.steelers.com/news/steelers-release-rodgers')
   fixture.setdefault('confirmed_qb',{})[tid]={'player_id':'3116407','player':'Mason Rudolph',
     'source_url':'https://www.steelers.com/news/statement-from-steelers-spokesman-x8902'}
   record('3116407','Mason Rudolph','QB','Active','Confirmed starting quarterback for this game',
          fixture['confirmed_qb'][tid]['source_url'])
 return list(by_player.values())

def injury_impact(events, fixture, boxes, statuses):
 """Evaluate reported absences and show when box scores cannot price an impact."""
 if fixture['sport'] not in football_weather.SPORTS:return {}
 result={}
 league_points=DEFAULTS[fixture['sport']][0]
 for side in ('home','away'):
  team=fixture[side];games=[]
  for game in team_past(events,fixture,team['id'])[-12:]:
   actual=game['home'] if game['home']['id']==team['id'] else game['away']
   offense=[r for r in boxes.get(game['id'],[]) if r['team_id']==team['id']]
   if actual.get('score') is not None and any(r['stats'].get('Pass attempts',0) for r in offense):
    games.append((actual['score'],{r['player_id']:r['stats'] for r in offense}))
  confirmed=fixture.get('confirmed_qb',{}).get(team['id'])
  effects=[]
  for row in statuses:
   if row['team_id']!=team['id'] or not unavailable(row['status']):continue
   pid=row['player_id']
   present=[(score,players[pid]) for score,players in games if pid in players and
            any(players[pid].get(key,0) for key in ('Targets','Carries','Pass attempts','Receiving yards'))]
   absent=[score for score,players in games if pid not in players]
   workload=mean([max(s.get('Targets') or 0,s.get('Receptions') or 0)+(s.get('Carries') or 0)+(s.get('Pass attempts') or 0) for _,s in present])
   is_primary=any((players.get(pid,{}).get('Pass attempts') or 0)>=12 for _,players in games[-3:])
   effect={'player':row['player'],'status':row['status'],'position':row.get('position'),
      'workload':workload,'with_games':len(present),'without_games':len(absent),
      'with_points':mean([score for score,_ in present],None),'without_points':mean(absent,None),
      'points':None,'uncertainty':0,'method':'Insufficient offensive usage or participation data'}
   if len(present)>=3 and len(absent)>=3 and workload>=3:
    shrink=min(len(present),len(absent))/(min(len(present),len(absent))+8)
    effect['points']=clip((effect['without_points']-effect['with_points'])*len(present)/len(games)*shrink/2,-3,0)
    effect['method']='Shrunk descriptive scoring split'
   elif is_primary and games:
    # A QB change weakens reliance on scoring history with the prior passer.
    # Shrink toward the league scoring prior and widen uncertainty without inventing a replacement rating.
    historical=mean([score for score,_ in games])
    effect.update(points=clip(.15*(league_points-historical),-2,2),uncertainty=.12,
      method='Prior starting QB unavailable; team scoring regressed toward league baseline')
   effects.append(effect)
  scoring=[x for x in effects if x['points'] is not None]
  qb=next((x for x in sorted(scoring,key=lambda x:-x['workload']) if x['position']=='QB' or x['uncertainty']),None)
  others=[x for x in scoring if x is not qb]
  # Downweight overlapping splits, retaining smaller effects across distinct unavailable players.
  deltas=sorted((x['points'] for x in others))
  points=(qb['points'] if qb else 0)+(deltas[0]+.35*sum(deltas[1:]) if deltas else 0)
  lead=qb or min(scoring,key=lambda x:x['points'],default={})
  result[side]={**lead,'points':clip(points,-4,3),'players':effects,'quantified':len(scoring),
     'uncertainty':max((r['uncertainty'] for r in effects),default=0),'confirmed_qb':confirmed}
 return result

def team_factors(events,e,side):
 t=e[side];o=e['away' if side=='home' else 'home'];past=team_past(events,e,t['id']);opp=team_past(events,e,o['id']);base,sd=DEFAULTS[e['sport']]
 def scores(gs,tid):
  own=[];allowed=[]
  for g in gs:
   h=g['home']['id']==tid;a,b=(g['home'],g['away']) if h else (g['away'],g['home'])
   if a.get('score') is not None and b.get('score') is not None:own.append(a['score']);allowed.append(b['score'])
  return own,allowed
 own,allowed=scores(past,t['id']);oppown,oppallow=scores(opp,o['id']);mu=(mean(own,base)+mean(oppallow,base))/2
 blend=mu
 rest=max(0,(iso(e['start'])-iso(past[-1]['start'])).total_seconds()/86400-1) if past else None
 if e['sport'] in ('NBA','WNBA','NCAAB') and rest is not None and rest<.5:mu*=.98
 rest_adjusted=mu
 venue_adjustment=({'NBA':1.5,'NFL':1.0,'NCAAF':1.5}.get(e['sport'],.25))*(1 if side=='home' else -1)
 availability=e.get('availability_impact',{}).get(side,{})
 mu+=venue_adjustment+availability.get('points',0)
 weather_points=mu*(e.get('weather',{}).get('scoring',1)-1);mu+=weather_points
 return mu,{'team_name':t['name'],'team_id':t['id'],'opponent_name':o['name'],'scoring_average':mean(own,base),'opponent_allowed_average':mean(oppallow,base),'scoring_games':len(own),'opponent_defense_games':len(oppallow),'fallback_scoring':not own,'fallback_defense':not oppallow,'fallback_value':base,'blend':blend,'rest_adjustment':rest_adjusted-blend,'venue_adjustment':venue_adjustment,'availability_impact':availability,'weather_adjustment':weather_points,'projected_score':mu,'source_games':[{'event_id':g['id'],'date':g['start'],'event':g['event'],'home_score':g['home'].get('score'),'away_score':g['away'].get('score'),'home_id':g['home']['id'],'away_id':g['away']['id'],'home_name':g['home']['name'],'away_name':g['away']['name'],'home_periods':g['home'].get('periods',[]),'away_periods':g['away'].get('periods',[]),'source_url':g.get('source_url')} for g in {x['id']:x for x in past+opp}.values()],'games':len(own),'points_for':round(mean(own,base),1),'points_allowed':round(mean(allowed,base),1),'opponent_allowed':round(mean(oppallow,base),1),'rest_days':round(rest,1) if rest is not None else None,'back_to_back':rest is not None and rest<.5,'last5':own[-5:],'sd':max(sd,st.pstdev(own) if len(own)>2 else sd)*(1+availability.get('uncertainty',0))}

def first_touchdown(summary, records):
 """Return the game's first TD, preserving unresolved scorers as unknown."""
 def clock(play):
  value=play.get('clock',{}).get('displayValue','')
  try:
   minutes,seconds=value.split(':')
   return int(minutes)*60+float(seconds)
  except ValueError:
   return None
 scores=summary.get('scoringPlays') or []
 touchdowns=[play for play in scores if (
  str(play.get('scoringType',{}).get('abbreviation','')).upper()=='TD'
  or 'touchdown' in str(play.get('type',{}).get('text','')).lower()
  or play.get('points')==6
 ) and not re.search(r'two.point|2.point',play.get('type',{}).get('text',''),re.I)]
 if not touchdowns:
  return {'no_td':True} if scores else None
 if any(not play.get('period',{}).get('number') or clock(play) is None for play in touchdowns):
  return None
 first=min(touchdowns,key=lambda play:(play['period']['number'],-clock(play)))
 description=first.get('text') or first.get('shortText') or ''
 team_id=str((first.get('team') or {}).get('id',''))
 def normalize(value):
  return re.sub(r'[^a-z0-9 ]','',value.lower().replace('.', ' '))
 normalized=normalize(description)
 matches=set()
 for row in records:
  if team_id and row['team_id']!=team_id:continue
  name=normalize(row['player']).split()
  if not name or not row['player_id']:continue
  names={' '.join(name),' '.join([name[0][0],*name[1:]])}
  if any(normalized.startswith(candidate+' ') for candidate in names):
   matches.add(row['player_id'])
 return {'player_id':next(iter(matches)) if len(matches)==1 else None,
  'period':first['period']['number'],'clock':first['clock']['displayValue'],'description':description}

def anytime_touchdowns(events, fixture, boxes, injuries, first_scores=None):
 """Rank NFL scorers using offensive TD opportunity from completed box scores."""
 ranked=[]
 first_scores=first_scores or {}
 league_prior=2.5 if fixture['sport']=='NFL' else 3.1
 team_rates=[]
 statuses={r['player_id']:r['status'] for r in injuries if r['event_id']==fixture['id']}
 for side,other in (('home','away'),('away','home')):
  team,opponent=fixture[side],fixture[other]
  def recent_offenses(team_id, allowed=False):
   samples=[]
   for game in reversed(team_past(events,fixture,team_id)):
    if iso(game['start'])>=NOW or not boxes.get(game['id']):continue
    other_id=game['away']['id'] if game['home']['id']==team_id else game['home']['id']
    offense=other_id if allowed else team_id
    records=[r for r in boxes[game['id']] if r['team_id']==offense]
    if any((r['stats'].get('Pass attempts') or 0)>0 for r in records):samples.append(records)
    if len(samples)==6:break
   return samples
  own=recent_offenses(team['id'])
  allowed=recent_offenses(opponent['id'],True)
  def td_count(records):
   return sum(r['stats'].get('Touchdowns',0) for r in records)
  own_rate=mean([td_count(rs) for rs in own],league_prior)
  allowed_rate=mean([td_count(rs) for rs in allowed],league_prior)
  scoring=(len(own)*own_rate+len(allowed)*allowed_rate+4*league_prior)/(len(own)+len(allowed)+4)
  scoring=max(.1,scoring+fixture.get('availability_impact',{}).get(side,{}).get('points',0)/7)
  scoring*=fixture.get('weather',{}).get('scoring',1)
  team_rates.append(scoring)
  if len(own)<3:continue
  history_games=[(g,first_scores[g['id']]) for g in reversed(team_past(events,fixture,team['id'])[-12:])
   if first_scores.get(g['id']) and (first_scores[g['id']].get('player_id') or first_scores[g['id']].get('no_td'))]
  usage=defaultdict(lambda:{'tds':0,'touches':0,'games':0})
  for i,records in enumerate(own):
   for row in records:
    pid=row['player_id']
    if not pid:continue
    stats=row['stats']
    x=usage[pid];x.setdefault('name',row['player']);x.setdefault('last_seen',i)
    x['tds']+=td_count([row])
    x['touches']+=(stats.get('Carries') or 0)+(stats.get('Receptions') or 0)
    x['games']+=1
  total_td=sum(x['tds'] for x in usage.values())
  total_touches=sum(x['touches'] for x in usage.values())
  if not total_touches:continue
  for pid,x in usage.items():
   status=statuses.get(pid,'Not listed')
   if unavailable(status) or x['last_seen']>1 or x['games']<2 or not x['touches']:continue
   share=(x['tds']+8*x['touches']/total_touches)/(total_td+8)
   if status.strip().lower() in {'questionable','game time decision'}:share*=.85
   rate=scoring*share
   probability=-math.expm1(-rate)
   history=[{**score,'date':g['start'],'matchup':g['event'],'url':g.get('source_url')}
    for g,score in history_games if score.get('player_id')==pid]
   ranked.append({'player':x['name'],'team':team['name'],'player_id':pid,'probability':probability,
    'fair_odds':fair(clip(probability)),'tds':x['tds'],'touches':x['touches'],'games':len(own),
    'opponent_td_allowed':round(allowed_rate,2) if allowed else None,'defense_games':len(allowed),
    'team_td_projection':round(scoring,2),'injury_status':status,
    'rate':rate,'first_td_history':history,'first_td_games':len(history_games)})
 total_rate=sum(team_rates)+.25  # Reserve chances for defense and special teams.
 for row in ranked:
  base=row.pop('rate')/total_rate*(-math.expm1(-total_rate))
  historical_blend=(20*base+len(row['first_td_history']))/(20+row['first_td_games'])
  row['first_td_probability']=min(row['probability'],historical_blend)
  row['first_td_fair_odds']=fair(clip(row['first_td_probability'],.0001,.9999))
 return sorted(ranked,key=lambda r:(-r['probability'],r['player_id']))[:2]

def calibrate(history,key,p):
 # One immutable first forecast per event/entity/market/direction, fit past events only.
 cache_key=(id(history),len(history),key)
 if cache_key in CAL_CACHE:
  adj,n=CAL_CACHE[cache_key];return clip(p+adj),n
 groups={}
 for h in history:
  if h.get('model_version')!=model_for(key.split(':',1)[0]) or h.get('calibration_key')!=key or h.get('outcome') not in (0,1):continue
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
 raw=clip(raw,.025,.975);key=e['sport']+':'+market+':'+side
 p,n=calibrate(history,key,raw);odds=extra.get('odds');priced=odds is not None and abs(odds)>=100
 identifier='|'.join(str(x) for x in (model_for(e['sport']),e['id'],extra.get('player_id','team'),market,extra.get('selection',''),side,line))
 row={'id':identifier,'event_id':e['id'],'sport':e['sport'],'event':e['event'],'start':e['start'],'day':e['day'],'market':market,'side':side,'line':line,'projection':round(mu,2),'sd':round(sd,2),'raw_probability':round(raw,5),'probability':round(p,5),'fair_odds':fair(p),'calibration_key':key,'calibration_games':n,'model_version':model_for(e['sport']),'source_url':e['source_url'],'odds':None,'bookmaker':None,'price_kind':'Suggested line','observed_at':NOW.isoformat(),'sample':0,'flags':[],**extra}
 row['break_even']=round(implied(odds),5) if priced else None;row['edge_pp']=round((p-implied(odds))*100,2) if priced else None;row['expected_roi_pct']=round((p*dec(odds)-1)*100,2) if priced else None
 row['qualified']=bool(priced and n>=100 and row['sample']>=10 and row['edge_pp']>=3 and not row['flags'])
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
  q=prices.get(('Moneyline',side),{});rows.append(make_row(e,'Moneyline',side,None,m,sd,history,**common,**{k:v for k,v in q.items() if k!='line'}))
  q=prices.get(('Spread',side));line=q['line'] if q and q['line'] is not None else round(-mu*2)/2+.5
  rows.append(make_row(e,'Spread',side,line,mu,sd,history,**common,**({k:v for k,v in q.items() if k!='line'} if q else {})))
  rows.append(make_row(e,'Team total','Over',max(.5,math.floor((h if side=='home' else a))-.5),h if side=='home' else a,ctx['sd'],history,**common))
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
   mu=mean(values)*e.get('weather',{}).get('scoring',1);sig=max(st.pstdev(values),3)
   for side in ('Over','Under'):rows.append(make_row(e,period,side,math.floor(mu)+.5,mu,sig,history,selection=e['event'],sample=len(values),projection_evidence={'kind':'period','samples':values,'mean':mu,'sd':sig,'weather_adjustment':mu-mean(values)},flags=['Unvalidated period model']))
 for r in rows:
  if 'projection_evidence' not in r:r['projection_evidence']={'kind':'team','home':hf,'away':af,'total':h+a,'home_margin':h-a,'formula':'Each team = (scoring average + opposing points allowed average) / 2 + rest adjustment + venue adjustment + eligible injury adjustment, then kickoff weather scoring adjustment where available','limitations':['Fixed venue and rest coefficients are legacy assumptions, not fitted effects.','All reported absences are reviewed. Where recent offensive scoring splits are usable, overlapping estimates are downweighted. Starting quarterback changes with thin evidence can move the forecast toward baseline and widen uncertainty. Defensive and offensive-line absence effects require participation data.','The model is not prospectively validated.']}
 return rows

BASKET={'Points':(5,1),'Rebounds':(2,1),'Assists':(2,1),'PRA':(5,1),'Points + rebounds':(5,1),'Points + assists':(5,1),'Rebounds + assists':(2,1),'Threes':(1,1),'Steals':(1,1),'Blocks':(1,1)}
OTHER={'Passing yards':25,'Rushing yards':10,'Receiving yards':10,'Receptions':1,'Completions':2,'Touchdowns':1,'Shots on goal':1,'Saves':2,'Goals':1,'Hits':1,'Runs':1,'RBIs':1,'Home runs':1,'Strikeouts':1,'Shots':1,'Shots on target':1}
def expanded(stats):
 s=dict(stats)
 for k,parts in {'PRA':['Points','Rebounds','Assists'],'Points + rebounds':['Points','Rebounds'],'Points + assists':['Points','Assists'],'Rebounds + assists':['Rebounds','Assists']}.items():
  if all(p in s for p in parts):s[k]=sum(s[p] for p in parts)
 return s

def player_rows(events,e,box,injuries,history):
 records=defaultdict(list)
 for b in box.values():
  for r in b:
   if r['sport']==e['sport'] and iso(r['start'])<NOW and iso(r['start'])<iso(e['start']):records[r['player_id']].append(r)
 rows=[];tidset={e['home']['id'],e['away']['id']};inj={r['player_id']:r for r in injuries if r['event_id']==e['id']}
 for pid,games in records.items():
  games.sort(key=lambda x:x['start']);latest=games[-1]
  if latest['team_id'] not in tidset or (NOW-iso(latest['start'])).days>45:continue
  # Most recent team is the best public-boxscore evidence, current roster gate supplied when available.
  if e.get('roster_ids') and pid not in e['roster_ids']:continue
  current=e.get('football_rosters',{}).get(latest['team_id'],{})
  if current.get('complete') and pid not in current['players']:continue
  status=inj.get(pid,{}).get('status','Not listed')
  if unavailable(status):continue
  recent=games[-25:];sid='home' if latest['team_id']==e['home']['id'] else 'away';mu_team,ctx=team_factors(events,e,sid)
  mins=[x['stats']['Minutes'] for x in recent if (x['stats'].get('Minutes') or 0)>0];expected_minutes=.65*mean(mins[-5:])+.35*mean(mins) if mins else None
  if e['sport'] in ('NBA','WNBA','NCAAB') and (expected_minutes is None or expected_minutes<14):continue
  marketset=BASKET if e['sport'] in ('NBA','WNBA','NCAAB') else OTHER
  for market in marketset:
   pairs=[(x,expanded(x['stats']).get(market)) for x in recent];pairs=[(x,v) for x,v in pairs if v is not None]
   if len(pairs)<5:continue
   log_key=e['id']+':'+pid+':'+market
   log_games=[]
   for x in games[-25:]:
    value=expanded(x['stats']).get(market)
    if value is None:continue
    past=events.get(x['event_id'],{});home=past.get('home',{});away=past.get('away',{})
    venue='home' if home.get('id')==x['team_id'] else 'away'
    opponent=away if venue=='home' else home
    log_games.append({'event_id':x['event_id'],'date':x['start'],'value':value,'opponent':opponent.get('abbr') or opponent.get('name','Unknown'),'opponent_id':opponent.get('id'),'venue':venue})
   PLAYER_LOGS[log_key]={'games':log_games,'next_opponent_id':e['away' if sid=='home' else 'home']['id']}
   vals=[v for _,v in pairs];baseline=mean(vals);last5=mean(vals[-5:]);projection=.65*last5+.35*baseline
   rate=None
   if expected_minutes and all((x['stats'].get('Minutes') or 0)>0 for x,_ in pairs):
    rate=sum(v for x,v in pairs)/sum(x['stats']['Minutes'] for x,_ in pairs);projection=.6*(rate*expected_minutes)+.4*projection
   # Team points allowed is a limited proxy, do not use it for rebounds or assists.
   defense=1
   if market=='Points':
    defense=clip(ctx['opponent_allowed']/DEFAULTS[e['sport']][0],.92,1.08);projection*=defense
   if ctx['back_to_back']:projection*=.98
   sig=max(st.pstdev(vals)*math.sqrt(1+1/len(vals)),math.sqrt(max(projection,1))*.7,1)
   # Inflate uncertainty when role/minutes changed or an injury report is unresolved.
   flag=[]
   if len(vals)<10:flag.append('Small sample')
   if status.lower() not in ('not listed','active','available','probable'):flag.append(status)
   if expected_minutes and abs(mean(mins[-3:])-mean(mins))>4:flag.append('Minutes volatility');sig*=1.15
   if flag and status.lower() not in ('not listed','active','available','probable'):sig*=1.2
   match=matchup.evaluate(games,records,events,e,e['sport'],market,latest['team_id'])
   weather=e.get('weather',{})
   position=next((g['position'] for g in reversed(games) if g['team_id']==latest['team_id'] and g.get('position')),None) if weather else None
   if e['sport'] in football_weather.SPORTS and market in matchup.FOOTBALL_ROLES:
    match=matchup.football_matchup(games,records,events,e,market,latest['team_id'],position,match)
   weather_volume,weather_rate=football_weather.market_factors(market,weather,position or '')
   engine=actuarial.fit(games,records,e['sport'],market,pid,log_key,adjustment=match['multiplier'],weather_volume=weather_volume,weather_rate=weather_rate)
   if engine:
    engine['evidence']['matchup_framework']=match
    if weather:engine['evidence']['kickoff_weather']={'status':weather['status'],'volume':weather_volume,'rate':weather_rate}
   elif weather:
    projection*=weather_volume*weather_rate
   if engine:
    projection=engine['projection'];sig=engine['sd'];rate=engine['evidence']['shrunk_rate'] if engine['evidence']['opportunity_unit']=='Minutes' else None;expected_minutes=engine['evidence']['expected_opportunity'] if engine['evidence']['opportunity_unit']=='Minutes' else None;PLAYER_LOGS[log_key]['model']=engine['evidence']
    defense=1 # Legacy ad-hoc defensive bonuses are not applied to this unvalidated engine.
   step=BASKET[market][1] if market in BASKET else OTHER[market]
   center=max(1,round(projection/step)*step)
   base_line=max(.5,center-.5)
   lines={max(.5,base_line-i*step) for i in range(4)}
   for line in sorted(lines):
    for side in (('Over','Under') if line==base_line else ('Over',)):
     hits=[int(v>line) if side=='Over' else int(v<line) for v in vals];streak=0
     for hit in reversed(hits):
      if not hit:break
      streak+=1
     r=make_row(e,market,side,line,projection,sig,history,player_id=pid,player=latest['player'],selection=latest['player'],team_id=latest['team_id'],sample=len(vals),base_line=base_line,line_step=step,base_line_source='Model projection; sportsbook line unavailable',log_key=log_key,flags=list(flag),source_url=latest['source_url'],injury_status=status,baseline=round(baseline,2),last5=round(last5,2),trend_pct=round((last5/baseline-1)*100,1) if baseline else 0,hit_rate=round(mean(hits),4),last5_hits=sum(hits[-5:]),last10_hits=sum(hits[-10:]),streak=streak,recent_values=vals[-10:],projected_minutes=round(expected_minutes,1) if expected_minutes else None,per_minute=round(rate,3) if rate is not None else None,context={**ctx,'venue':sid,'defense_multiplier':round(defense,3),'teammate_absences':[z['player'] for z in injuries if z['event_id']==e['id'] and z['team_id']==latest['team_id'] and unavailable(z['status'])]},reasoning='Recent 5 + available season-window form, minutes × per-minute production where available, basketball rest adjustment. Points use opponent team points allowed. Teammate absences flagged; usage redistribution and position-specific defense are not yet modeled.')
     if engine:
      estimates=actuarial.price(engine['evidence'],line,side,r.get('odds'));r.update(estimates);r['raw_probability']=r['probability'];r['calibration_games']=0
      r['engine_version']=actuarial.VERSION;r['model_status']='Research / unvalidated';r['qualified']=False
      r['reasoning']=f"{engine['evidence']['expected_opportunity']} expected {engine['evidence']['opportunity_unit']} × {engine['evidence']['shrunk_rate']} production per opportunity. Scenario-mixture mean {projection:.2f}. Opponent rate adjustment: {match['status']} (multiplier {match['multiplier']:.3f}). Current lineup changes remain unmodeled."
      if weather:
       r['reasoning']+=f" Kickoff weather: {weather['status']}. Workload ×{weather_volume:.3f}; production rate ×{weather_rate:.3f}."
      if 'football_defense' in match:
       rate_label=f" {match['opportunity_unit']}"
       if match['opponent_rate'] is not None and match['league_rate'] is not None:
        group=f" for listed {match['position']}s" if match['position'] else " across available positions"
        r['reasoning']+=f" Defense allowed {match['opponent_rate']:.2f} per{rate_label}{group} over {match['opponent_games']} games, versus a {match['league_rate']:.2f} league baseline. Slot alignment and defensive play calls are unavailable."
      r['selection_status']='Unpriced research' if r.get('odds') is None else 'Positive estimated value' if r['expected_roi_pct']>0 else 'Pass at this price'
     rows.append(r)
 return rows

def actual_value(r,e,box):
 market=r.get('market');side=r.get('side')
 if r.get('player_id'):
  found=next((x for x in box.get(e['id'],[]) if x['player_id']==r['player_id']),None)
  return expanded(found['stats']).get(market) if found else None
 if market=='Total':return e['home']['score']+e['away']['score']
 if market=='Team total':return e['home' if r.get('team_id')==e['home']['id'] else 'away']['score']
 if market=='Spread':return e[side]['score']-e['away' if side=='home' else 'home']['score']
 if market=='Moneyline':return e['home']['score']-e['away']['score']
 return None

def settle(r,e,box):
 if not e.get('final'):return None
 market=r.get('market','Moneyline');line=r.get('line');side=r.get('side');actual=None
 if r.get('player_id'):
  found=next((x for x in box.get(e['id'],[]) if x['player_id']==r['player_id']),None)
  # Missing player may be DNP or incomplete data: don't infer a loss or void.
  if not found:return None
  actual=expanded(found['stats']).get(market)
 elif market=='Moneyline':
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
 events=read('events.json',{});history=read('history.json',[]);ai_ledger=read('ai_picks.json',[]);cache=read('cache.json',{'box':{},'schedules':{},'rosters':{}});box=cache['box'];cache.setdefault('box_schema',{});first_scores=cache.setdefault('first_touchdowns',{})
 # Normalize legacy records; keep existing immutable forecast probabilities.
 for e in events.values():
  e.setdefault('espn_id',e['id'].split(':')[-1]);e.setdefault('state','post' if e.get('final') else 'pre');e.setdefault('source_url','https://www.espn.com');e.setdefault('odds',[])
  for side in ('home','away'):e[side].setdefault('periods',[]);e[side].setdefault('stats',{});e[side].setdefault('abbr',e[side]['name'])
 jobs=[]
 for sport in SPORTS:
  offsets=range(-1,8) if sport in ('NFL','NCAAF') else (-1,0,1,2)
  for off in offsets:jobs.append((f'{sport}:{off}',scoreboard,(sport,(TODAY+dt.timedelta(days=off)).isoformat())))
 for key,gs in parallel(jobs):
  for e in gs:events[e['id']]=e
 # Revisit pending forecasts older than yesterday once per run by date/sport.
 pending={(r['sport'],iso(r.get('start')).date().isoformat()) for r in history if r.get('outcome') is None and iso(r.get('start'))<NOW-dt.timedelta(days=1) and r['sport'] in SPORTS}
 for _,gs in parallel([(f'pending:{s}:{d}',scoreboard,(s,d)) for s,d in pending]):
  for e in gs:events[e['id']]=e
 future=sorted([e for e in events.values() if not e.get('final') and e.get('state')=='pre' and NOW<iso(e['start']) and (e['day']<=(TODAY+dt.timedelta(days=7)).isoformat() if e['sport'] in ('NFL','NCAAF') else iso(e['start'])<NOW+dt.timedelta(days=2))],key=lambda e:e['start'])
 # Cache past team schedules daily; bootstrap real season-window samples.
 teams={(e['sport'],e[s]['id']) for e in future for s in ('home','away') }
 jobs=[]
 for sport,tid in teams:
  key=sport+':'+tid
  if cache['schedules'].get(key)!=TODAY.isoformat():jobs.append((key,schedule,(sport,tid)))
 for key,d in parallel(jobs):
  sport=key.split(':')[0]
  for raw in d.get('events',[]):
   e=event(raw,sport)
   if e and e['final'] and NOW-dt.timedelta(days=60)<iso(e['start'])<NOW:events[e['id']]=e
  cache['schedules'][key]=TODAY.isoformat()
 write('cache.json',cache);write('events.json',events)
 # Current rosters prevent stale traded-player membership. Daily cache; report missing roster explicitly.
 def roster(sport,tid):return fetch(f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/teams/{tid}/roster')
 jobs=[]
 for sport,tid in teams:
  key=sport+':'+tid
  if sport in football_weather.SPORTS:
   saved=cache['rosters'].get(key,{})
   if NOW-iso(saved.get('fetched_at'))>=dt.timedelta(hours=1):jobs.append((key,roster,(sport,tid)))
  elif sport in ('NBA','WNBA','NCAAB') and cache['rosters'].get(key,{}).get('day')!=TODAY.isoformat():jobs.append((key,roster,(sport,tid)))
 for key,d in parallel(jobs):
  if key.split(':')[0] in football_weather.SPORTS:
   data=football_roster(d)
   if data['complete'] or (data['players'] and not cache['rosters'].get(key,{}).get('complete')):
    cache['rosters'][key]={**data,'fetched_at':NOW.isoformat()}
   continue
  athletes=d.get('athletes',[]);ids=[str(a['id']) for a in athletes if 'id' in a]
  if ids:cache['rosters'][key]={'day':TODAY.isoformat(),'ids':ids}
 for e in future:
  ids=sum([cache['rosters'].get(e['sport']+':'+e[s]['id'],{}).get('ids',[]) for s in ('home','away')],[])
  if ids:e['roster_ids']=ids
  if e['sport'] in football_weather.SPORTS:
   e['football_rosters']={}
   for side in ('home','away'):
    tid=e[side]['id'];saved=cache['rosters'].get(e['sport']+':'+tid,{})
    if saved.get('fetched_at') and NOW-iso(saved['fetched_at'])<dt.timedelta(hours=2):
     e['football_rosters'][tid]=saved
 # Old football reception grades used a parser that conflated catches and recoveries.
 # Preserve the original grade for audit and verify it again against a refreshed box.
 for r in history+ai_ledger:
  if r.get('market')!='Receptions' or r.get('sport') not in ('NFL','NCAAF') or not r.get('player_id'):continue
  if cache['box_schema'].get(r['event_id'])==6 or r.get('outcome') is None:continue
  r.setdefault('pre_reception_audit_grade',{k:r.get(k) for k in ('outcome','actual_value','graded_at','profit_units')})
  r.update(outcome=None,actual_value=None,graded_at=None,profit_units=None)
 # Backfill a bounded set of final boxscores; completed boxes retained, recent missing boxes retried.
 needed={}
 for e in future:
  if e['sport'] not in tuple(SPORTS):continue
  for side in ('home','away'):
   for g in team_past(events,e,e[side]['id'])[-12:]:
    football=g['sport'] in ('NFL','NCAAF')
    if not box.get(g['id']) or cache['box_schema'].get(g['id'])!=(6 if football else 4) or (football and g['id'] not in first_scores):needed[g['id']]=g
 for r in history+ai_ledger:
  if r.get('outcome') is None and r.get('player_id') and r['event_id'] in events and events[r['event_id']].get('final'):needed[r['event_id']]=events[r['event_id']]
 # Prioritize NBA player model on initial backfill, then other leagues. 180 max per run.
 queues=defaultdict(list)
 for fixture in sorted(needed.values(),key=lambda e:-iso(e['start']).timestamp()):queues[fixture['sport']].append(fixture)
 target=[]
 while queues and len(target)<180:
  for sport in list(queues):
   if len(target)<180:target.append(queues[sport].pop(0))
   if not queues[sport]:del queues[sport]
 for key,d in parallel([(e['id'],summary,(e,)) for e in target]):
  rows=parse_box(d,events[key])
  if rows:
   box[key]=rows;cache['box_schema'][key]=6 if events[key]['sport'] in ('NFL','NCAAF') else 4
   if events[key]['sport'] in ('NFL','NCAAF') and isinstance(d.get('scoringPlays'),list):
    first_scores[key]=first_touchdown(d,rows)
 write('cache.json',cache);write('events.json',events)
 injuries=collect_availability(future)
 football_weather.collect(future,cache,fetch,parallel,NOW)
 write('cache.json',cache);write('events.json',events)
 for r in history+ai_ledger:
  if r.get('outcome') is not None:continue
  e=events.get(r['event_id'])
  if not e:continue
  if r.get('market')=='Receptions' and e['sport'] in ('NFL','NCAAF') and cache['box_schema'].get(e['id'])!=6:continue
  result=settle(r,e,box)
  if result is not None:
   r['outcome']=result;r['actual_value']=actual_value(r,e,box);r['graded_at']=NOW.isoformat();r['profit_units']=0 if result=='push' else round(dec(r['odds'])-1 if result else -1,4) if r.get('odds') else None
 rows=[]
 # Old hockey parser could confuse shootout SOG with regulation shots; do not model those boxes.
 prediction_box={k:v for k,v in box.items() if not v or v[0]['sport']!='NHL' or cache['box_schema'].get(k)==4}
 for key,records in prediction_box.items():
  if records and records[0]['sport'] in ('NFL','NCAAF') and cache['box_schema'].get(key)!=6:
   prediction_box[key]=[{**r,'stats':{k:v for k,v in r['stats'].items() if k!='Receptions'}} for r in records]
 statuses=defaultdict(list)
 for row in injuries:statuses[row['event_id']].append(row)
 injuries=[row for row in injuries if row['event_id'] not in {e['id'] for e in future if e['sport'] in football_weather.SPORTS}]
 for e in future:
  if e['sport'] in football_weather.SPORTS:
   statuses[e['id']]=reconcile_football_availability(events,e,prediction_box,statuses[e['id']])
   injuries.extend(statuses[e['id']])
  e['availability_impact']=injury_impact(events,e,prediction_box,statuses[e['id']])
  rows+=team_rows(events,e,history);rows+=player_rows(events,e,prediction_box,statuses[e['id']],history)
  e.pop('football_rosters',None)
 learning=ai_record.calibration(ai_ledger,NOW.isoformat(),model_for)
 for row in rows:ai_record.apply(row,learning)
 by_event=defaultdict(list)
 for row in rows:by_event[row['event_id']].append(row)
 current_football={}
 for fixture in future:
  chosen=ai_record.choose(by_event[fixture['id']])
  if fixture['sport'] in football_weather.SPORTS:current_football[fixture['id']]=chosen
  prior=[r for r in ai_ledger if r['event_id']==fixture['id']]
  if len(prior)>=10:continue
  prior_keys={('player',r['player_id']) if r.get('player_id') else ('market',r['market'],r.get('team_id','game')) for r in prior}
  chosen=[r for r in chosen if (('player',r['player_id']) if r.get('player_id') else ('market',r['market'],r.get('team_id','game'))) not in prior_keys][:10-len(prior)]
  for rank,r in enumerate(chosen,len(prior)+1):
   snapshot={k:v for k,v in r.items() if k not in ('context','recent_values')}
   if r.get('log_key') in PLAYER_LOGS:snapshot['frozen_model']=PLAYER_LOGS[r['log_key']].get('model')
   snapshot.update({'ai_rank':rank,'ai_selected_at':NOW.isoformat(),'outcome':None,'selection_policy':'game-up-to-ten-v2','calibration_tracking':True})
   ai_ledger.append(snapshot)
 active_ids={e['id'] for e in future}
 inactive={(r['event_id'],r['player_id']) for r in injuries if unavailable(r['status'])}
 ai_selections={eid:ai_record.choose([r for r in ai_ledger if r['event_id']==eid and (eid,r.get('player_id')) not in inactive]) for eid in active_ids}
 ai_selections.update(current_football)
 ai_summary=ai_record.summarize(ai_ledger)
 write('ai_picks.json',ai_ledger)
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
 report={'ai_selections':ai_selections,'ai_record':ai_summary,'ai_learning':learning,'ai_recent_results':[{k:r.get(k) for k in ('event','sport','selection','market','side','line','probability','projection','actual_value','outcome','ai_selected_at','graded_at','flags')} for r in ai_ledger if r.get('outcome') is not None][-200:],'engine_monitoring':([r for r in actuarial.monitoring(history,BASE_MODEL) if r['sport'] not in football_weather.SPORTS]+actuarial.monitoring(history,MODEL)),'engine_status':{'version':actuarial.VERSION,'full_hierarchical_bayes':False,'full_game_simulation':False,'portfolio_optimizer':'Disabled: forecasts and joint returns not validated','coverage':'Player props with sufficient box-score data; game markets retain legacy scoring model; golf has no automatic model','method_reference':'https://mc-stan.org/docs/stan-users-guide/sampling-from-the-posterior-predictive-distribution.html'},'player_logs':PLAYER_LOGS,'version':MODEL,'generated_at':NOW.isoformat(),'day':TODAY.isoformat(),'refresh_minutes':15,'recommendations':rows,'games':future,'injuries':injuries,'metrics':{'tracked_predictions':len(history),'settled_predictions':len(settled),'won':sum(r['outcome'] for r in settled),'brier_score':round(brier,4) if brier is not None else None,'independent_groups':len(groups),'priced_settled':len(priced),'realized_roi_pct':round(100*sum(r['profit_units'] for r in priced)/len(priced),2) if priced else None},'calibration_bins':bins,'coverage':list(SPORTS),'source':'ESPN public scoreboards / boxscores / injury reports; DraftKings game odds where supplied by ESPN','errors':ERRORS,'backfill_remaining':max(0,len(needed)-len(target)),'limitations':['Player-prop prices are not provided by the free game feed. Suggested lines are model thresholds, not sportsbook offers.','Player props use deterministic opportunity/workload scenario models; game markets retain the legacy normal model. Probabilities are not validated.','Injury status and teammate absences are flags; confirmed rotations, player usage redistribution and position-specific defense are not modeled.','No automatic golf prediction or odds feed; exact markets can be imported locally.','Missing player participation remains pending for review, never automatically graded as a loss.']}
 report['calibration_tracking']=ai_record.track_calibration(ai_ledger)
 report['next_gen_audit']=nextgen.audit(TODAY,box,cache)
 write('cache.json',cache)
 report['td_candidates']={e['id']:anytime_touchdowns(events,e,prediction_box,injuries,first_scores) for e in future if e['sport'] in ('NFL','NCAAF')}
 report['game_coverage']={fixture['id']:{'sport':fixture['sport'],'predictions':sum(r['event_id']==fixture['id'] for r in rows),'ai_picks':len(ai_selections.get(fixture['id'],[])),'status':'AI picks available' if ai_selections.get(fixture['id']) else 'Projections available; no supported picks' if any(r['event_id']==fixture['id'] for r in rows) else 'Awaiting usable history / source data'} for fixture in future}
 report['daily_coverage']=[{'sport':sport,'games_today':sum(e['sport']==sport and e['day']==TODAY.isoformat() for e in future),'predictions_today':sum(r['sport']==sport and r['day']==TODAY.isoformat() for r in rows),'ai_picks_today':sum(r['sport']==sport and r['day']==TODAY.isoformat() for rs in ai_selections.values() for r in rs)} for sport in SPORTS]
 report['unsupported_coverage']=['Golf: automatic field/round projections are not connected; no golf predictions are fabricated.']
 # No destructive retention of forecast history. Cache excludes bulky raw feed payloads.
 write('events.json',events);write('history.json',history);write('cache.json',cache)
 write('history-view.json',feed_transport.history_view(history))
 write('pick-record.json',feed_transport.history_view(ai_ledger))
 write('latest.json',feed_transport.compact(report,DATA/'details'))
 write('status.json',{'generated_at':NOW.isoformat(),'day':TODAY.isoformat(),'version':MODEL,'refresh_minutes':15,'transport_version':3,'games':len(future),'recommendations':len(rows),'source_errors':len(ERRORS),'football_weather':{status:sum(e.get('weather',{}).get('status')==status for e in future) for status in sorted({e['weather']['status'] for e in future if 'weather' in e})}})
 print(f'{len(future)} upcoming games | {len(rows)} lines | {sum(bool(r.get("player_id")) for r in rows)} player lines | {len(settled)} settled | {len(ERRORS)} feed errors')
if __name__=='__main__':main()





