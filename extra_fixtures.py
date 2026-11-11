"""Individual-sport fixture discovery only. No invented markets or model probabilities."""
import datetime as dt
PATHS={'PGA':'golf/pga','ATP':'tennis/atp','WTA':'tennis/wta','UFC':'mma/ufc'}
def when(v):
 try:return dt.datetime.fromisoformat(v.replace('Z','+00:00'))
 except (AttributeError,ValueError):return None

def extract(payload,sport,now):
 found={};end=now+dt.timedelta(days=7)
 def walk(d,parent=None):
  parent=parent or {}
  if isinstance(d,list):
   for v in d:walk(v,parent)
   return
  if not isinstance(d,dict):return
  current=parent|{k:d[k] for k in ('date','name','links','status','endDate') if d.get(k) is not None}
  start=when(d.get('date') or d.get('startDate') or current.get('date'));finish=when(d.get('endDate') or current.get('endDate'))
  competitors=d.get('competitors',[]);calendar='startDate' in d and 'label' in d
  if start and start<end and (start>now or finish and finish>now) and (competitors or calendar):
   names=[c.get('athlete',{}).get('displayName') or c.get('team',{}).get('displayName') for c in competitors];names=[n for n in names if n]
   name=' vs '.join(names) if len(names)==2 and sport!='PGA' else d.get('label') or current.get('name') or sport+' event'
   links=current.get('links') or [];url=next((x.get('href') for x in links if x.get('href','').startswith('https://')),f'https://www.espn.com/{PATHS[sport].split("/")[0]}/')
   state=(current.get('status') or {}).get('type',{}).get('state','pre')
   if state!='post':
    key=sport+':'+str(d.get('id') or name+start.isoformat());found[key]={'id':key,'sport':sport,'event':name,'start':start.isoformat(),'source_url':url,'checked_at':now.isoformat(),'coverage':'Schedule only; verified market prices and sport-specific projection history unavailable'}
  for k,v in d.items():
   if isinstance(v,(dict,list)) and k not in ('competitors','statistics','leaders','links'):walk(v,current)
 walk(payload);return sorted(found.values(),key=lambda x:x['start'])

def collect(fetch,parallel,now):
 jobs=[]
 for sport,path in PATHS.items():
  for i in range(8):
   day=(now+dt.timedelta(days=i)).strftime('%Y%m%d');jobs.append((sport+':'+day,fetch,(f'https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day}&limit=100',)))
 result={}
 for key,payload in parallel(jobs):
  sport=key.split(':')[0]
  for row in extract(payload,sport,now):result[row['id']]=row
 return sorted(result.values(),key=lambda x:x['start'])
