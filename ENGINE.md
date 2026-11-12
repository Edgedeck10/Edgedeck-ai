# EdgeDeck opportunity engine v3

This release is a research implementation, not evidence of profitable predictions.
It retains the six-sport UI, free Actions/Pages hosting, existing immutable history,
and no minimum predicted hit-rate selection target.

## Active implementation

- Opportunity parsing adds basketball shot attempts, football attempts/carries/targets,
  hockey ice time/shots faced, and available soccer/baseball opportunity fields.
  Existing box-score cache is refreshed in bounded batches. Missing opportunity
  fields trigger an explicitly labeled per-game fallback.
- Available historical windows are compared chronologically. Early prediction
  origins choose a window; later origins evaluate that rolling-mean baseline.
  This is not an out-of-sample test of the entire final engine or bet selector.
- Exposure-weighted within/between-player moments estimate credibility K when
  enough peer variation is available. Peers share sport and market, not necessarily
  position or role. No fitted K is claimed when it cannot be estimated.
- Production families: beta-binomial for finite makes/attempts; gamma-rate Poisson
  or fitted negative-binomial for counts; a signed aggregate-yardage approximation
  for yards. Receiving yards can be negative.
- Bayesian-bootstrap workload scenarios and parameter draws produce outcome and
  probability ranges. Negative-binomial dispersion and peer priors are plug-in
  fits; their uncertainty is not fully propagated. Gamma rate updates in the
  negative-binomial case are approximate. This is not a full hierarchical posterior.
- Prices include pushes. Fair odds use win probability conditional on non-push;
  expected return uses win, loss and refund probabilities. Actual-price EV and
  probability of positive EV require entered/observed odds. No odds are fabricated.
- Brier and log loss are grouped by sport/market and event/player/direction, isolated
  to this model version. Pushes are excluded and probabilities conditioned on a
  non-push for those binary scoring rules. Scores begin accumulating prospectively.
- Parlay research uses aligned historical-game ranks with updated marginal
  distributions. It preserves an empirical dependence structure, not a coherent
  full-game statistical accounting model. Same-player combinations are withheld;
  other same-game combinations require at least five aligned games. Different
  games are assumed independent. Finite simulation error and dependence estimation
  error remain. It is not a validated joint parlay forecast or optimizer.

## Not implemented or not established

Full hierarchical player/team/role posterior inference; coherent team-plays to
passes/targets/receptions/yards simulation; opponent position defense, weather,
confirmed lineup/usage adjustments; play-level severity; closing-line value;
price shopping; full selector walk-forward tests; correction validated for parlay
search selection; risk-constrained portfolio allocation. No automatic golf model.
Soccer player models depend on available parsed history; this release does not
promise coverage of every sport/team/player. Game markets retain the legacy model.

Do not activate portfolio sizing or claim model accuracy based on deployment.
The UI lists missing inputs and labels approximate and unvalidated outputs.

## Verification

`python -m unittest test_pipeline.py test_actuarial.py`
`node --check app.js && node --check engine-ui.js`

Probability/production reference definitions:
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.betabinom.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.nbinom.html
- https://mc-stan.org/docs/stan-users-guide/sampling-from-the-posterior-predictive-distribution.html

These references describe mathematical methods, not evidence for EdgeDeck accuracy.
