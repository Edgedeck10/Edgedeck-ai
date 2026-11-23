"""Compact public transport. Durable forecast archives remain unchanged."""
import gzip,hashlib,json
PLAYER_CONTEXT={'rest_days','back_to_back','venue','defense_multiplier','teammate_absences'}
def compact(report, detail_dir=None):
 pools={};game_evidence={}
 def model(m):
  if not m or 'draw_histograms' not in m:return m
  x=dict(m);h=x.pop('draw_histograms');encoded=json.dumps(h,sort_keys=True,separators=(',',':'));key=hashlib.sha256(encoded.encode()).hexdigest()[:24]
  pools.setdefault(key,h);x['distribution_id']=key;return x
 def row(r):
  x=dict(r)
  if x.get('player_id'):x['context']={k:v for k,v in x.get('context',{}).items() if k in PLAYER_CONTEXT}
  else:
   c=x.get('context',{});x['context']={k:({a:b for a,b in v.items() if a!='source_games'} if isinstance(v,dict) else v) for k,v in c.items() if k!='source_games'}
  evidence=x.get('projection_evidence')
  if evidence and evidence.get('kind')=='team':
   key=x['event_id'];game_evidence.setdefault(key,evidence);x.pop('projection_evidence');x['projection_evidence_ref']=key
  if x.get('frozen_model'):x['frozen_model']=model(x['frozen_model'])
  return x
 out=dict(report);out['recommendations']=[row(r) for r in report['recommendations']]
 out['ai_selections']={k:[row(r) for r in rs] for k,rs in report.get('ai_selections',{}).items()}
 out['player_logs']={k:{**v,'model':model(v.get('model'))} for k,v in report.get('player_logs',{}).items()}
 out['game_evidence']=game_evidence;out['distributions']=pools;out['transport_version']=2
 if detail_dir is None:return out
 # Content-addressed event files keep a cached board compatible across deploys.
 detail_dir.mkdir(parents=True,exist_ok=True)
 previous=set()
 try:
  prior=json.loads(gzip.decompress((detail_dir.parent/'latest.json.gz').read_bytes()))
  previous={path.rsplit('/',1)[-1] for path in prior.get('detail_files',{}).values()}
 except (OSError,ValueError):pass
 files={}
 for event in report['games']:
  eid=event['id']
  logs={k:v for k,v in out['player_logs'].items() if k.startswith(eid+':')}
  frozen={r['id']:r['frozen_model'] for r in out['ai_selections'].get(eid,[]) if r.get('frozen_model')}
  ids={m['distribution_id'] for m in [*[v.get('model') for v in logs.values()],*frozen.values()] if m and m.get('distribution_id')}
  payload={'player_logs':logs,'ai_models':frozen,'game_evidence':{eid:game_evidence[eid]} if eid in game_evidence else {},'distributions':{k:pools[k] for k in ids}}
  encoded=json.dumps(payload,separators=(',',':')).encode()
  name=hashlib.sha256(encoded).hexdigest()[:24]+'.json.gz'
  path=detail_dir/name
  if not path.exists():path.write_bytes(gzip.compress(encoded,compresslevel=6,mtime=0))
  files[eid]='details/'+name
 # Retain the previous generation for tabs that are already open.
 keep=previous|{path.rsplit('/',1)[-1] for path in files.values()}
 for path in detail_dir.glob('*.json.gz'):
  if path.name not in keep:path.unlink()
 out['player_logs']={};out['game_evidence']={};out['distributions']={}
 for rs in out['ai_selections'].values():
  for r in rs:r.pop('frozen_model',None)
 templates={}
 groups={}
 for row in out['recommendations']:
  key=row.get('log_key') or row['id']
  groups.setdefault(key,[]).append(row)
 for key,rows in groups.items():
  if len(rows)<2:continue
  common={k:v for k,v in rows[0].items() if k!='id' and all(k in r and r[k]==v for r in rows[1:])}
  templates[key]=common
  for r in rows:
   for k in common:r.pop(k)
   r['row_template']=key
 out['row_templates']=templates;out['detail_files']=files;out['transport_version']=3
 return out

def history_view(history):
 keys={'id','event_id','event','sport','start','day','selection','player','player_id','market','side','line','projection','sd','probability','raw_probability','push_probability','odds','fair_odds','bookmaker','predicted_at','outcome','graded_at','profit_units','model_version','calibration_key','source_url','origin','actual_value','ai_rank'}
 return [{k:v for k,v in r.items() if k in keys} for r in history]
