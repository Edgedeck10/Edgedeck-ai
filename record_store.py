"""Lossless monthly forecast archives; small phone payload, no raw-file size ceiling."""
import json,gzip,pathlib

def read_history(data):
 manifest=data/'history_manifest.json'
 if not manifest.exists():
  p=data/'history.json';return json.loads(p.read_text()) if p.exists() else []
 info=json.loads(manifest.read_text());rows=[]
 for item in info['archives']:
  rows.extend(json.loads(gzip.decompress((data/item['path']).read_bytes())))
 return rows

def write_history(data,rows):
 groups={}
 for r in rows:
  month=str(r.get('start') or r.get('predicted_at') or 'undated')[:7]
  if not (len(month)==7 and month[4]=='-'):month='undated'
  groups.setdefault(month,[]).append(r)
 folder=data/'history_archive';folder.mkdir(exist_ok=True);items=[]
 for month,rs in sorted(groups.items()):
  relative='history_archive/'+month+'.json.gz';payload=json.dumps(rs,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();(data/relative).write_bytes(gzip.compress(payload,mtime=0))
  items.append({'month':month,'path':relative,'count':len(rs)})
 manifest={'format':'gzip-json-array','total_forecasts':len(rows),'recent_payload':min(5000,len(rows)),'archives':items}
 (data/'history_manifest.json').write_text(json.dumps(manifest,separators=(',',':')))
 (data/'history.json').write_text(json.dumps(rows[-5000:],ensure_ascii=False,separators=(',',':'),allow_nan=False))
 return manifest

def normalize_report(report):
 fields={'event','event_id','sport','selection','player','player_id','start','day','market','projection','sd','log_key','context','reasoning','source_url','baseline','last5','trend_pct','projected_minutes','per_minute','rate','expected_exposure','exposure_unit','injury_status','position','team_id','model_version','sample','probability_margin','estimated_price_method','flags'}
 details={};rows=[]
 for r in report['recommendations']:
  key=r.get('log_key') or '|'.join(str(r.get(k,'')) for k in ('event_id','market','selection','side'))
  details.setdefault(key,{k:v for k,v in r.items() if k in fields});rows.append({k:v for k,v in r.items() if k not in fields}|{'details_key':key})
 report['model_details']=details;report['recommendations']=rows
 for e in report.get('games',[]):e.pop('odds',None);e.pop('roster_ids',None)
 return report


def write_report(data,report):
 payload=json.dumps(normalize_report(report),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
 zipped=gzip.compress(payload,mtime=0)
 (data/'latest.json.gz').write_bytes(zipped)
 # The compressed feed is authoritative; avoid GitHub's 100 MB per-file ceiling.
 (data/'latest.json').unlink(missing_ok=True)
 (data/'feed_status.json').write_text(json.dumps({'version':report['version'],'generated_at':report['generated_at'],'recommendations':len(report['recommendations']),'uncompressed_bytes':len(payload),'download_bytes':len(zipped),'daily_picks':len(report.get('daily_picks',[]))},separators=(',',':')))
 return len(payload),len(zipped)
