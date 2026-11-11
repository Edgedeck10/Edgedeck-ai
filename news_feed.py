"""Public ESPN headlines; source-linked context, not an invented numerical news model."""
import datetime as dt,re

def collect(sports,fetch,parallel,now,cache):
 old=cache.get('news',{});result={};jobs=[(s,fetch,(f'https://site.api.espn.com/apis/site/v2/sports/{path}/news?limit=30',)) for s,path in sports.items()]
 returned=dict(parallel(jobs))
 for s in sports:
  if s not in returned:
   result[s]={'checked_at':now.isoformat(),'status':'Fetch failed; prior headlines retained','articles':old.get(s,{}).get('articles',[])};continue
  articles=[]
  for a in returned[s].get('articles',[]):
   url=a.get('links',{}).get('web',{}).get('href');published=a.get('published');headline=a.get('headline')
   if not url or not headline:continue
   try:
    if now-dt.datetime.fromisoformat(published.replace('Z','+00:00'))>dt.timedelta(days=7):continue
   except (ValueError,TypeError,AttributeError):continue
   teams={str(c.get('team',{}).get('id')) for c in a.get('categories',[]) if isinstance(c.get('team'),dict) and c['team'].get('id') is not None}
   articles.append({'headline':headline,'description':a.get('description',''),'published':published,'url':url,'team_ids':sorted(teams),'impact_review':bool(re.search(r'\b(injur\w*|hurt|sidelined|concussion|illness|ankle|hamstring|wrist|out|ruled|suspend\w*|trade\w*|minutes|rest|starting|lineup|return\w*|questionable|doubtful)\b',headline,re.I))})
  result[s]={'checked_at':now.isoformat(),'status':'Public feed collected','articles':articles}
 cache['news']=result;return result

def for_event(event,feed):
 teams={str(event.get(k,{}).get('id')) for k in ('home','away')};names=[event.get(k,{}).get('name','').lower() for k in ('home','away')]
 return [a for a in feed.get(event.get('sport'),{}).get('articles',[]) if teams.intersection(a['team_ids']) or any(n and n in (a['headline']+' '+a.get('description','')).lower() for n in names)][:6]

def review(ticket,rows,events,injuries,news,now):
 reviews=[]
 for leg in ticket['legs']:
  event=events.get(leg['event_id'],{});same=[r for r in rows if r.get('id')==leg['id']];latest=same[0] if same else None
  alerts=[]
  if event.get('state')!='pre':alerts.append('Event started, completed or no longer marked pregame; original forecast retained for grading.')
  if not latest:alerts.append('Original exact line is not on the current board; recheck line and price.')
  elif latest.get('odds') is None:alerts.append('No current observed quote for the original line.')
  elif latest['odds']!=leg.get('odds'):alerts.append(f"Price changed from {leg.get('odds')} to {latest['odds']}; original record is unchanged.")
  injury=[i for i in injuries if i.get('event_id')==leg['event_id']]
  if injury:alerts.append('Availability report requires review: '+', '.join(i['player']+' ('+i['status']+')' for i in injury[:8])+'. Team injury effects are not fully modeled.')
  articles=for_event(event,news)
  if any(a.get('impact_review') for a in articles):alerts.append('Potential lineup, injury or roster news: review linked reports; no unsupported numerical adjustment applied.')
  if news.get(leg['sport'],{}).get('status')!='Public feed collected':alerts.append('News collection incomplete; latest information cannot be confirmed.')
  reviews.append({'leg_id':leg['id'],'checked_at':now,'status':'Review before use' if alerts else 'Rechecked against current feeds','alerts':alerts,'articles':articles,'current_odds':latest.get('odds') if latest else None,'current_probability':latest.get('probability') if latest else None})
 return reviews
