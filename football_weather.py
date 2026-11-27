"""Kickoff forecasts for the NFL and college football board."""
from datetime import datetime, timedelta, timezone
from math import isfinite
from urllib.parse import urlencode

SPORTS = {'NFL', 'NCAAF'}
SOURCE = 'Open-Meteo'
SOURCE_URL = 'https://open-meteo.com/en/docs'
FIELDS = ('temperature_2m', 'wind_speed_10m', 'wind_gusts_10m', 'precipitation')
STATES = dict(zip(
    'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split(),
    'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia'.split('|'),
))
# ESPN's indoor boolean alone cannot establish the game-day roof state at these venues.
RETRACTABLE = ('at&t stadium', 'state farm stadium', 'mercedes-benz stadium',
               'lucas oil stadium', 'nrg stadium', 'reliant stadium',
               'rogers centre')


def venue_fields(raw):
    raw = raw or {}
    address = raw.get('address') or {}
    point = raw.get('coordinates') or {}
    return {
        'name': raw.get('fullName') or raw.get('name'),
        'indoor': raw.get('indoor'),
        'roof': raw.get('roof') or raw.get('roofType'),
        'city': address.get('city'), 'state': address.get('state'),
        'country': address.get('country'),
        'lat': point.get('latitude', raw.get('latitude')),
        'lon': point.get('longitude', raw.get('longitude')),
    }


def roof_status(venue):
    roof = str(venue.get('roof') or '').strip().lower()
    if roof in {'open', 'outdoor', 'outdoors', 'open air', 'open-air'}:
        return 'outdoor'
    if roof in {'closed', 'fixed', 'dome', 'indoor', 'indoors'}:
        return 'indoor'
    if 'retract' in roof or any(name in (venue.get('name') or '').lower() for name in RETRACTABLE):
        return 'unknown'
    if venue.get('indoor') is True:
        return 'indoor'
    if venue.get('indoor') is False:
        return 'outdoor'
    return 'unknown'


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def number(x):
    return isinstance(x, (float, int)) and isfinite(x)


def locate(venue, fetch):
    lat, lon = venue.get('lat'), venue.get('lon')
    if number(lat) and number(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
        return (lat, lon, 'venue coordinates')
    city = (venue.get('city') or '').strip()
    state = (venue.get('state') or '').strip()
    state = STATES.get(state.upper(), state)
    country = (venue.get('country') or '').strip().casefold()
    is_us_state = state.casefold() in {name.casefold() for name in STATES.values()}
    us = country in {'usa', 'us', 'united states', 'united states of america'} or (not country and is_us_state)
    if not city or (us and not is_us_state) or (not us and not country):
        return None
    query = urlencode({'name': city, 'count': 50, 'language': 'en', **({'countryCode': 'US'} if us else {})})
    results = fetch('https://geocoding-api.open-meteo.com/v1/search?' + query).get('results', [])
    matches = [
        r for r in results
        if r.get('name', '').casefold() == city.casefold()
        and (r.get('country_code') == 'US' and r.get('admin1', '').casefold() == state.casefold()
             if us else country in {r.get('country', '').casefold(), r.get('country_code', '').casefold()})
        and number(r.get('latitude')) and number(r.get('longitude'))
    ]
    # Exclude same-name subdivisions or unpopulated entries when the city is unique.
    cities = [r for r in matches if r.get('population', 0) and
              r.get('feature_code') in {'PPL', 'PPLC', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4'}]
    points = {(r['latitude'], r['longitude']) for r in (cities or matches)}
    if len(points) == 1:
        lat, lon = points.pop()
        return lat, lon, 'city-level estimate'



def forecast(location, fetch):
    lat, lon, _ = location
    query = urlencode({'latitude': lat, 'longitude': lon, 'hourly': ','.join(FIELDS),
                       'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph',
                       'forecast_days': 9, 'timezone': 'GMT'})
    return fetch('https://api.open-meteo.com/v1/forecast?' + query)['hourly']


def kickoff_fields(hourly, start):
    kickoff = utc(start)
    # Precipitation and gusts describe the hour ending at the API timestamp.
    end = kickoff.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    i = hourly['time'].index(end.strftime('%Y-%m-%dT%H:%M'))
    prev = i - 1
    if prev < 0 or hourly['time'][prev] != (end - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'):
        raise ValueError('Incomplete kickoff hour')
    fraction = (kickoff - (end - timedelta(hours=1))).total_seconds() / 3600
    def interpolate(field):
        return hourly[field][prev] * (1 - fraction) + hourly[field][i] * fraction
    values = (interpolate(FIELDS[0]), interpolate(FIELDS[1]), hourly[FIELDS[2]][i], hourly[FIELDS[3]][i])
    if not all(number(x) for x in values) or min(values[1:]) < 0:
        raise ValueError('Invalid forecast values')
    temp, wind, gust, precip = (round(v, 1) for v in values)
    return {'forecast_hour_ending': end.isoformat(), 'temperature_f': temp, 'wind_mph': wind,
            'gust_mph': gust, 'precip_mm': precip}


def collect(fixtures, cache, fetch, parallel, now):
    geo = cache.setdefault('football_venue_geo', {})
    hourly = cache.setdefault('football_hourly_weather', {})
    groups = {}
    for game in fixtures:
        if game['sport'] not in SPORTS:
            continue
        venue = game.get('venue') or {}
        roof = roof_status(venue)
        game['weather'] = {'roof': roof, 'venue': venue.get('name'), 'kickoff': game['start'],
                           'status': {'indoor': 'Indoor or closed roof', 'unknown': 'Roof status unconfirmed',
                                      'outdoor': 'Outdoor kickoff forecast unavailable'}[roof]}
        if roof == 'outdoor':
            key = '|'.join(str(venue.get(field) or '') for field in ('city', 'state', 'country', 'lat', 'lon'))
            groups.setdefault(key, []).append(game)
    geo_jobs = [(key, locate, (games[0]['venue'], fetch)) for key, games in groups.items() if key not in geo]
    for key, result in parallel(geo_jobs, workers=6):
        if result is not None:
            geo[key] = result
    locations = {'|'.join(map(str, geo[key][:2])): geo[key] for key in groups if key in geo}
    fresh_until = now - timedelta(minutes=30)
    hourly = {key: value for key, value in hourly.items()
              if key in locations and utc(value['fetched_at']) > fresh_until}
    jobs = [(key, forecast, (location, fetch)) for key, location in locations.items() if key not in hourly]
    for key, result in parallel(jobs, workers=6):
        hourly[key] = {'fetched_at': now.isoformat(), 'hourly': result}
    cache['football_hourly_weather'] = hourly
    for key, games in groups.items():
        location = geo.get(key)
        for game in games:
            weather = game['weather']
            if not location:
                weather['status'] = 'Venue location could not be verified'
                continue
            saved = hourly.get('|'.join(map(str, location[:2])))
            try:
                if not saved:
                    continue
                weather.update(kickoff_fields(saved['hourly'], game['start']))
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            weather.update(status='Kickoff forecast used', source=SOURCE, source_url=SOURCE_URL,
                           location_precision=location[2], fetched_at=saved['fetched_at'])
            weather.update(factors(weather))


def factors(weather):
    # Provisional response curves. Gusts matter, but count less than sustained wind.
    effective_wind = max(weather['wind_mph'], .65 * weather['gust_mph'])
    wind_load = min(1, max(0, (effective_wind - 12) / 18))
    wet_load = min(1, weather['precip_mm'] / 3)
    pressure = min(1, .75 * wind_load + .45 * wet_load)
    return {'pass_volume': round(1 - .07 * pressure, 4), 'rush_volume': round(1 + .09 * pressure, 4),
            'pass_efficiency': round(1 - .10 * pressure, 4), 'scoring': round(1 - .06 * pressure, 4),
            'method': 'Provisional weather response; coefficients not fitted or validated'}


def market_factors(market, weather, role=''):
    if weather.get('status') != 'Kickoff forecast used':
        return 1, 1
    passing = weather['pass_efficiency']
    volume = weather['pass_volume']
    if market == 'Passing yards':
        return volume, passing
    if market == 'Receiving yards':
        return volume, 1 - .8 * (1 - passing)
    if market == 'Receptions':
        short_role = role.upper() in {'RB', 'FB', 'HB', 'TE'}
        return 1 - .5 * (1 - volume) if short_role else volume, 1 - .2 * (1 - passing)
    if market == 'Completions':
        return volume, 1 - .35 * (1 - passing)
    if market == 'Rushing yards':
        return weather['rush_volume'], 1
    if market == 'Touchdowns':
        return 1, weather['scoring']
    return 1, 1
