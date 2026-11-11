"""Free Open-Meteo city-level forecasts. Context, not stadium sensor readings."""
import urllib.parse,datetime as dt
BASKET={'NBA','WNBA','NCAAB','NHL'}
def collect(games,cache,fetch,now):
 store=cache.setdefault('weather',{});geo=cache.setdefault('weather_geo',{});result={}
 for e in games:
  v=e.get('venue') or {};indoor=v.get('indoor');city=v.get('city')
  if indoor is True or e['sport'] in BASKET:
   result[e['id']]={'status':'Indoor / no weather adjustment','indoor':True,'factor':1};continue
  if e['sport'] not in ('NFL','NCAAF','MLB','EPL','MLS') or not city:
   result[e['id']]={'status':'Venue / weather unavailable','factor':1};continue
  key=city+','+(v.get('state') or '');old=store.get(key,{})
  try:
   if not old or (now-dt.datetime.fromisoformat(old['fetched_at'])).total_seconds()>3600:
    if key not in geo:
     data=fetch('https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':city,'count':10,'language':'en','format':'json'}))
     found=[r for r in data.get('results',[]) if r.get('country_code')==('GB' if e['sport']=='EPL' else 'US')]
     # Require a state match where supplied; no silent city-name guessing.
     state=(v.get('state') or '')
     if state and len(state)>2:found=[r for r in found if r.get('admin1')==state]
     if len(found)!=1:
      result[e['id']]={'status':'Ambiguous venue location; weather not applied','factor':1};continue
     geo[key]={'lat':found[0]['latitude'],'lon':found[0]['longitude']}
    g=geo[key];q={'latitude':g['lat'],'longitude':g['lon'],'hourly':'temperature_2m,wind_speed_10m,precipitation','temperature_unit':'fahrenheit','wind_speed_unit':'mph','forecast_days':8,'timezone':'GMT'}
    old={'fetched_at':now.isoformat(),'hourly':fetch('https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(q)).get('hourly',{})};store[key]=old
   h=old['hourly'];target=dt.datetime.fromisoformat(e['start'].replace('Z','+00:00')).replace(tzinfo=None);times=h.get('time',[])
   if not times:raise ValueError('No hourly forecast')
   i=min(range(len(times)),key=lambda i:abs((dt.datetime.fromisoformat(times[i])-target).total_seconds()))
   if abs((dt.datetime.fromisoformat(times[i])-target).total_seconds())>7200:raise ValueError('Outside forecast range')
   result[e['id']]={'status':'City-level forecast; roof state not confirmed' if indoor is None else 'Outdoor city-level forecast','indoor':False,'roof_confirmed':indoor is not None,'temperature_f':h['temperature_2m'][i],'wind_mph':h['wind_speed_10m'][i],'precip_mm':h['precipitation'][i],'forecast_hour_utc':times[i],'collected_at':old['fetched_at'],'city':city,'source':'Open-Meteo','source_url':'https://open-meteo.com/','factor':1}
  except Exception as exc:result[e['id']]={'status':'Weather feed unavailable: '+type(exc).__name__,'factor':1}
 return result

def adjustment(sport,market,weather):
 if weather.get('indoor') or not weather.get('roof_confirmed') or sport not in ('NFL','NCAAF') or market not in ('Passing yards','Receiving yards','Completions','Receptions'):return 1
 wind=weather.get('wind_mph') or 0;rain=weather.get('precip_mm') or 0
 return (.97 if wind>=20 else 1)*(.98 if rain>=2 else 1)
