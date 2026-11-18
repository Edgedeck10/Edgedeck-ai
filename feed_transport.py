"""Compact public transport. Durable forecast archives remain unchanged."""
import hashlib,json
PLAYER_CONTEXT={'rest_days','back_to_back','venue','defense_multiplier','teammate_absences'}
def compact(report):
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
 return out

def history_view(history):
 keys={'id','event_id','event','sport','start','day','selection','player','player_id','market','side','line','projection','sd','probability','raw_probability','push_probability','odds','fair_odds','bookmaker','predicted_at','outcome','graded_at','profit_units','model_version','calibration_key','source_url','origin','actual_value','ai_rank'}
 return [{k:v for k,v in r.items() if k in keys} for r in history]
