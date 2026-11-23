"""Cross-check NFL box scores with weekly NFL Next Gen Stats via nflverse."""
import csv
import gzip
import io
import urllib.request
from collections import Counter

BASE = 'https://github.com/nflverse/nflverse-data/releases/download/'
SCHEDULE = 'https://github.com/nflverse/nfldata/raw/master/data/games.csv'
SOURCE = 'https://nflreadr.nflverse.com/reference/load_nextgen_stats.html'
FIELDS = {
    'receiving': {'receptions': 'Receptions', 'targets': 'Targets', 'yards': 'Receiving yards'},
    'rushing': {'rush_attempts': 'Carries', 'rush_yards': 'Rushing yards'},
}


def csv_rows(url):
    with urllib.request.urlopen(url, timeout=12) as response:
        payload = response.read()
    if url.endswith('.gz'):
        payload = gzip.decompress(payload)
    return csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))


def snapshot(day):
    seasons = {str(day.year), str(day.year - 1)} if day.month < 4 else {str(day.year)}
    schedule = {}
    for game in csv_rows(SCHEDULE):
        if game['season'] not in seasons or not game['espn'] or not game['home_score']:
            continue
        season_type = 'REG' if game['game_type'] == 'REG' else 'POST'
        for team in (game['away_team'], game['home_team']):
            schedule[(game['season'], season_type, int(game['week']), team)] = 'NFL:' + game['espn']
    ids = {}
    for player in csv_rows(BASE + 'players/players.csv'):
        if player['gsis_id'] and player['espn_id'].isdigit():
            ids[player['gsis_id']] = player['espn_id']
    values = {}
    latest = None
    for category, fields in FIELDS.items():
        for row in csv_rows(BASE + f'nextgen_stats/ngs_{category}.csv.gz'):
            if row['season'] not in seasons or row['week'] in ('', '0'):
                continue
            event = schedule.get((row['season'], row['season_type'], int(row['week']), row['team_abbr']))
            player = ids.get(row['player_gsis_id'])
            if not event or not player:
                continue
            stats = {field: int(row[key]) for key, field in fields.items()
                     if row[key].lstrip('-').isdigit()}
            if stats:
                values.setdefault(event, {}).setdefault(player, {}).update(stats)
                latest = max(latest or 0, int(row['season']) * 100 + int(row['week']))
    if not values:
        raise ValueError('No NFL games matched to Next Gen Stats')
    return {'day': day.isoformat(), 'values': values, 'latest_season_week': latest}


def audit(day, boxes, cache):
    feed = cache.get('nextgen', {})
    error = None
    if boxes and feed.get('day') != day.isoformat():
        try:
            feed = snapshot(day)
            cache['nextgen'] = feed
        except (OSError, ValueError, KeyError, csv.Error) as exc:
            error = str(exc)
    totals = Counter()
    examples = []
    checked_games = 0
    for event, players in feed.get('values', {}).items():
        count = 0
        for player in boxes.get(event, []):
            reference = players.get(player['player_id'], {})
            for field, expected in reference.items():
                actual = player['stats'].get(field)
                if actual is None:
                    continue
                count += 1
                totals['fields_checked'] += 1
                if actual != expected:
                    totals['mismatches'] += 1
                    examples.append({'event_id': event, 'player': player['player'], 'field': field,
                                     'espn': actual, 'next_gen': expected})
        checked_games += bool(count)
    examples.sort(key=lambda item: item['event_id'], reverse=True)
    return {'source': 'NFL Next Gen Stats via nflverse', 'url': SOURCE, 'checked_games': checked_games,
            'fields_checked': totals['fields_checked'], 'mismatches': totals['mismatches'],
            'examples': examples[:20], 'snapshot_date': feed.get('day'),
            'latest_season_week': feed.get('latest_season_week'), 'error': error}
