# EdgeDeck — The Research Playbook
Mobile-first sports research on free public GitHub Pages and standard GitHub-hosted Actions. No paid endpoints, keys, services or automated betting.

## What is included
- Player projections and suggested alternate lines: points, rebounds, assists, PRA, P+R, P+A, R+A, threes, steals and blocks. Football passing/rushing/receiving, receptions, completions and touchdowns; hockey shots, goals and saves; baseball hits, runs, RBIs, HR and strikeouts where eligible historical boxscores exist.
- Game markets: moneyline, spreads, totals, team totals, and measured first-half/first-quarter total baselines for supported leagues.
- ESPN-listed DraftKings game-line snapshots where returned, clearly separated from model suggested lines and model fair prices.
- Exact-line editor, 90% research screen, recent hit rates, L5/L10 counts, streaks, projected basketball minutes, per-minute output, recent trend, rest/back-to-back flags, injury reports and teammate absences.
- 5/8/10-leg pool generator, one selection per game, independence-only joint probability, mathematical joint bounds, and no combined price claim for unpriced lines.
- Immutable first pregame forecasts, exact-line outcome grading, push handling, grouped Brier score, reliability bands and prospective shrinkage calibration. Missing player data remains pending.
- CSV/JSON import/export for arbitrary markets, including first/last TD, golf, tennis, UFC and other unavailable automatic markets. Personal lines and manually graded outcomes stay on-device, separate from the automatic public record.
- White/ivory background, navy, gold and Irish-green accents; responsive layout and Add to Home Screen manifest.

## Refresh and deployment
Workflow `.github/workflows/refresh.yml`: every 15 minutes at :07, :22, :37 and :52 UTC; cron may be delayed. Also runs on source pushes and manual dispatch. Data-only commits do not trigger recursive runs. Standard ubuntu-latest runner; public repository. Page polls published JSON once per minute while visible. Check latest reloads published data; it does not trigger a backend collection. Cache and history are retained in Git. Only latest.json and history.json are published with the static assets. No API key is needed.

Schedule and roster caches refresh daily; final boxscores are retained. Initial historical backfill is bounded to 180 boxscores per run and prioritizes NBA, with remaining queue exposed in the UI. Some leagues may initially show game markets only. Free unofficial ESPN endpoints can fail or change; feed errors are displayed. No guaranteed live data SLA.

## Model limitations
A provisional statistical model, not a validated betting system. Basketball uses up to 20 available games, recent five-game form, minutes × per-minute production and a limited opponent team points-allowed adjustment for points only. Team scoring uses recent scoring / opponent allowance. Rest adjustment is heuristic. Injury and teammate status are flags, not a validated usage-redistribution model. Confirmed rotations, position defense, schedule strength, pace and correlated same-game pricing are not fully modeled. Rare events use a normal approximation and need a future count model. 90% is an estimate, not a demonstrated success rate. Unpriced suggested lines have no verified edge or ROI. No sportsbook player-prop prices are fabricated.

The public archive records all supported suggested thresholds, including both over and under directions. Its raw hit ratio is not the performance of a recommended bet portfolio. Alternate lines are correlated; grouped Brier scoring gives each event/entity/market/side equal weight. Calibration groups exact alternate-line forecasts to one first observation per event/entity/market/side and corrects future estimates gradually. Old predictions are never rewritten. Legacy v1 records are retained separately by model-version label.

## Tests
`python -m unittest test_pipeline.py` verifies spread/total/period/team-total settlement, pushes, player combo settlement, missing-player handling, probability complements, odds arithmetic and calibration direction. `node --check app.js` verifies JavaScript syntax. Serve locally with `python -m http.server` for interface checks.

## Privacy
Repository and automatic forecasts are public. Personal imported lines remain in localStorage on the current browser, are not uploaded, and can be exported or removed. Never import account credentials or API keys. The app opens research/sportsbook home pages; it never sends or places wagers.
