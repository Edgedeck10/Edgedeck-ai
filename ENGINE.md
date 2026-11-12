# Opportunity scenarios v4

Player projections use opportunity times production, with exposure-based peer shrinkage when a stable peer fit exists. Missing opportunity fields use a labeled per-game fallback. Unsupported matchup factors are listed, not invented.

Three workloads use the historical 10th percentile, mean, and 90th percentile. Weights 25/50/25 are explicit assumptions. One fitted distribution family per market: binomial for finite attempts, Poisson or fitted negative binomial for counts, rounded signed Gaussian for aggregate yardage. PMFs are computed directly, without random simulation. Count support is truncated at mean plus 12 standard deviations plus 20; negligible masses are dropped and remaining mass normalized.

Probabilities and push-aware fair prices use the workload mixture. The displayed probability range and minimum EV are workload sensitivity, not Bayesian credible intervals. Probability that EV is positive is deliberately unavailable. No full posterior inference, game simulation, or portfolio optimizer is implemented.

History candidates are 10, 15, 20, 25 available games, using common chronological forecast origins with complete windows. Early origins select the window and later origins evaluate it. Where there are insufficient origins, a labeled baseline window (up to 20 games) is used. Window MAE validates only the rolling baseline, not the final selection process.

Parlay probability uses multiplication only for distinct identified games with opportunity models, explicitly assuming independence. Same-game probabilities are withheld. Adding legs lowers all-win probability; sportsbook prices and settlement may differ.

Version-isolated prospective Brier/log-loss monitoring remains. Historical alternatives are correlated, so scores group by event/player/market/side. Accuracy is unvalidated. Actual sportsbook prices are required for price-based value; model fair odds are not offers. Six sport groups remain available, but data/model coverage is incomplete (including no automatic golf model). No hit-rate gate is applied.

Data uses lossless gzip, with atomic writes and preserved forecast history. The UI renders precomputed distributions; it does not fit or simulate models on the phone.


## Context v4.1
Opponent allowance per opportunity is compared with a same-sport/market baseline using only earlier games. Strength (0, .25, .5, 1) is selected on earlier player forecast origins and only activated if it improves later holdout MAE. This activation gate is not an untouched validation set. No position-specific or causal matchup claim is made. L5/L10/L20/L25 form and venue splits are shown with actual sample counts; venue differences do not automatically modify forecasts. No arbitrary pace bonus or fixed metric-weight score is stacked onto production. Missing tracking, weather, confirmed roles and price data remain unavailable, explicitly labeled. NHL regulation S shots map to shots on goal; later shootout fields cannot overwrite them. Cache schema 4 reparses older boxes progressively.
