"""EdgeDeck free scheduled moneyline research pipeline.
ESPN scoreboard + optional licensed The Odds API pricing; tracked outcomes and rolling calibration.
No claims of official live sportsbook access. Standard library only.
"""
import os,json,math,urllib.request,datetime,pathlib,statistics
from zoneinfo import ZoneInfo
from collections import defaultdict
ROOT=pathlib.Path(__file__).parent; DATA=ROOT/'data';DATA.mkdir(exist_ok=True)
SPORTS={'NBA':'basketball/nba','NFL':'football/nfl','MLB':'baseball/mlb','NHL':'hockey/nhl','NCAAF':'football/college-football','NCAAB':'basketball/mens-college-basketball'}
ODDS_SPORTS={'NBA':'basketball_nba','NFL':'americanfootball_nfl','MLB':'baseball_mlb','NHL':'icehockey_nhl','NCAAF':'americanfootball_ncaaf','NCAAB':'basketball_ncaab'}
NOW=datetime.datetime.now(datetime.timezone.utc); TODAY=NOW.astimezone(ZoneInfo('America/Indiana/Indianapolis')).date().isoformat()
def read(name,default):
 try:return json.loads((DATA/name).read_text())
 except (OSError,ValueError):return default
def write(name,value): (DATA/name).write_text(json.dumps(value,indent=2,ensure_ascii=False))
def fetch(url,headers=None):
 req=urllib.request.Request(url,headers={'User-Agent':'EdgeDeck personal research/1.0','Accept':'application/json',**(headers or {})})
 with urllib.request.urlopen(req,timeout=22) as r:return json.load(r)
def norm(s):return ''.join(c for c in (s or '').lower() if c.isalnum())
def prob_from_american(x):return abs(x)/(abs(x)+100) if x<0 else 100/(x+100)
def decimal(x):return 1+100/abs(x) if x<0 else 1+x/100
def clip(x,a=.02,b=.98):return max(a,min(b,x))
def event_id(sport,comp):return f'{sport}:{comp.get("id","")}'
def schedule(sport,day):
 url=f'https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]}/scoreboard?dates={day.replace("-","")}&limit=200'
 data=fetch(url);out=[]
 for ev in data.get('events',[]):
  comps=ev.get('competitions') or []; comp=comps[0] if comps else {}
  teams=comp.get('competitors') or []
  if len(teams)!=2:continue
  sides={t.get('homeAway'):t for t in teams}
  if not {'home','away'}<=set(sides):continue
  h,a=sides['home'],sides['away']
  status=(comp.get('status') or ev.get('status') or {}).get('type',{})
  final=bool(status.get('completed'))
  def tm(x):
   t=x.get('team',{});return {'id':str(t.get('id','')),'name':t.get('displayName') or t.get('name',''),'score':int(float(x.get('score') or 0)) if final else None,'record':next((r.get('summary','') for r in x.get('records',[]) if r.get('type')=='total'),'')}
  out.append({'id':event_id(sport,ev),'sport':sport,'event':ev.get('name',''),'start':ev.get('date'),'home':tm(h),'away':tm(a),'final':final,'status':status.get('description',''),'day':day})
 return out
def records_to_winrate(events,team,sport,before):
 games=[]
 for e in events.values():
  if e['sport']!=sport or not e.get('final') or e.get('day','')>=before:continue
  if norm(team) not in (norm(e['home']['name']),norm(e['away']['name'])):continue
  own=e['home'] if norm(team)==norm(e['home']['name']) else e['away']; opp=e['away'] if own is e['home'] else e['home']
  if own['score']==opp['score']:continue
  games.append((e['day'],int(own['score']>opp['score'])))
 games.sort(reverse=True);recent=[w for _,w in games[:25]]
 # Beta-binomial smoothing: 10 pseudo games at .5
 return ((5+sum(recent))/(10+len(recent)),len(recent))
def base_probability(events,e):
 home,n1=records_to_winrate(events,e['home']['name'],e['sport'],e['day']);away,n2=records_to_winrate(events,e['away']['name'],e['sport'],e['day'])
 # logit strength difference plus modest home-field prior
 def logit(p):return math.log(p/(1-p))
 p=clip(1/(1+math.exp(-(logit(home)-logit(away)+.14))),.1,.9)
 return p,{'home_prior_winrate':round(home,3),'away_prior_winrate':round(away,3),'home_sample':n1,'away_sample':n2,'home_advantage_logodds':.14}
def calibration(history,sport):
 # Retain historical predictions and outcomes; shrink correction to zero with small samples.
 settled=[r for r in history if r.get('sport')==sport and r.get('side')=='home' and r.get('outcome') in (0,1) and isinstance(r.get('raw_probability'),(float,int))]
 settled=settled[-500:];n=len(settled)
 if not n:return 0,0,None
 residual=sum(r['outcome']-r['raw_probability'] for r in settled)/n
 adjustment=max(-.08,min(.08,residual*n/(n+100)))
 brier=sum((r['raw_probability']-r['outcome'])**2 for r in settled)/n
 return adjustment,n,round(brier,4)
def odds_data():
 key=os.getenv('ODDS_API_KEY','');out={};errors=[]
 if not key:return out,['No ODDS_API_KEY: market prices unavailable.']
 for sport,code in ODDS_SPORTS.items():
  try:
   from urllib.parse import urlencode
   params=urlencode({'apiKey':key,'regions':'us','markets':'h2h','oddsFormat':'american'})
   data=fetch(f'https://api.the-odds-api.com/v4/sports/{code}/odds/?{params}')
   for e in data:
    # Preference FanDuel if present; otherwise transparent named bookmaker.
    books=e.get('bookmakers',[]);books.sort(key=lambda b:(b.get('key')!='fanduel',b.get('key','')))
    for book in books:
     markets=[m for m in book.get('markets',[]) if m.get('key')=='h2h']
     if not markets:continue
     for o in markets[0].get('outcomes',[]):
      if isinstance(o.get('price'),int):out[(sport,norm(e.get('home_team','')),norm(e.get('away_team','')),norm(o['name']))]={'odds':o['price'],'bookmaker':book.get('title') or book.get('key'),'updated':book.get('last_update')}
     # keep first bookmaker per event to avoid mixed-book prices
     break
  except Exception as exc:errors.append(f'{sport} odds: {type(exc).__name__}: {str(exc)[:100]}')
 return out,errors
def main():
 events=read('events.json',{});history=read('history.json',[]);errors=[]
 # Fetch yesterday, today, tomorrow to grade games and find slate; failures do not erase existing data.
 days={(datetime.date.fromisoformat(TODAY)+datetime.timedelta(days=d)).isoformat() for d in (-2,-1,0,1)}
 days.update(r['start'][:10] for r in history if r.get('outcome') is None and r.get('start'))
 for day in sorted(days):
  for sport in SPORTS:
   try:
    for e in schedule(sport,day):events[e['id']]=e
   except Exception as exc:errors.append(f'{sport} {day}: {type(exc).__name__}')
 # Grade archived moneyline picks ONLY when final; never overwrite predictions.
 for r in history:
  if r.get('outcome') is not None:continue
  e=events.get(r['event_id'])
  if not e or not e.get('final') or e['home']['score']==e['away']['score']:continue
  won=e['home']['name'] if e['home']['score']>e['away']['score'] else e['away']['name']
  r['outcome']=int(norm(won)==norm(r['selection']));r['graded_at']=NOW.isoformat()
  r['profit_units']=round((decimal(r['odds'])-1) if r['outcome'] else -1,4) if isinstance(r.get('odds'),int) else None
 prices={};errors+=['Sportsbook prices are not connected. No paid services enabled.']
 recommendations=[]
 for e in events.values():
  if e.get('day')!=TODAY or e.get('final'):continue
  try:
   if datetime.datetime.fromisoformat(e['start'].replace('Z','+00:00'))<=NOW:continue
  except (ValueError,AttributeError):continue
  raw,factors=base_probability(events,e);adj,n,brier=calibration(history,e['sport'])
  for team,rawp in [(e['home']['name'],raw),(e['away']['name'],1-raw)]:
   p=clip(rawp+(adj if team==e['home']['name'] else -adj))
   q=prices.get((e['sport'],norm(e['home']['name']),norm(e['away']['name']),norm(team)))
   odds=q['odds'] if q else None
   implied=prob_from_american(odds) if odds is not None else None
   edge=p-implied if implied is not None else None
   roi=p*decimal(odds)-1 if odds is not None else None
   # Do not claim edge where sample insufficient or no verified odds.
   qualified=bool(odds is not None and n>=100 and min(factors['home_sample'],factors['away_sample'])>=10 and edge>=.04 and roi>=.05)
   rec={'id':f'{e["id"]}:{norm(team)}','event_id':e['id'],'sport':e['sport'],'event':e['event'],'start':e['start'],'market':'moneyline','side':'home' if team==e['home']['name'] else 'away','selection':team,'raw_probability':round(rawp,5),'probability':round(p,5),'odds':odds,'bookmaker':q['bookmaker'] if q else None,'odds_updated':q['updated'] if q else None,'break_even':round(implied,5) if implied is not None else None,'edge_pp':round(edge*100,2) if edge is not None else None,'expected_roi_pct':round(roi*100,2) if roi is not None else None,'qualified':qualified,'calibration_games':n,'historical_brier':brier,'factors':factors,'reasoning':f'Prior team results: {e["home"]["name"]} {factors["home_prior_winrate"]:.1%} ({factors["home_sample"]} games), {e["away"]["name"]} {factors["away_prior_winrate"]:.1%} ({factors["away_sample"]} games); home advantage prior and sport-level calibration from {n} settled predictions. This is a simple baseline, not an injury-aware AI model.'}
   recommendations.append(rec)
   # Store immutable prediction snapshot only for events before start; no retroactive leakage.
   try:future=datetime.datetime.fromisoformat(e['start'].replace('Z','+00:00'))>NOW
   except (ValueError,AttributeError):future=False
   if future and rec['id'] not in {h['id'] for h in history}:
    history.append({k:rec[k] for k in ('id','event_id','sport','side','selection','raw_probability','probability','odds','bookmaker','start') }|{'predicted_at':NOW.isoformat(),'outcome':None})
 write('events.json',events);write('history.json',history)
 recommendations.sort(key=lambda r:(not r['qualified'],-(r['expected_roi_pct'] if r['expected_roi_pct'] is not None else -999),-r['probability']))
 settled=[h for h in history if h.get('outcome') in (0,1)];priced=[h for h in settled if h.get('profit_units') is not None]
 report={'generated_at':NOW.isoformat(),'day':TODAY,'status':'Research baseline; not validated betting advice','coverage':list(SPORTS),'source':'ESPN public scoreboard (unofficial); optional The Odds API','recommendations':recommendations,'metrics':{'tracked_predictions':len(history),'settled_predictions':len(settled),'brier_score':round(statistics.mean((h['probability']-h['outcome'])**2 for h in settled),4) if settled else None,'priced_settled':len(priced),'realized_profit_units':round(sum(h['profit_units'] for h in priced),2) if priced else None,'realized_roi_pct':round(100*sum(h['profit_units'] for h in priced)/len(priced),2) if priced else None},'errors':errors}
 write('latest.json',report)
 print(f"{TODAY}: {len(recommendations)} candidates, {len(settled)} settled, {sum(r['qualified'] for r in recommendations)} qualified; errors={len(errors)}")
if __name__=='__main__':main()
