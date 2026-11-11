/* Current evidence is distinct from frozen selection-time evidence. */
function pickContext(frozen){
const current=report.rowIndex?.get(frozen.id),r=current||frozen,c=r.context||r.rationale?.context||{},def=c.opponent_position||{},w=c.weather||{},logs=report.player_logs?.[r.log_key]?.games||[],quoted=r.price_kind==='Observed snapshot'&&r.odds!=null;
const entries=[
['Projection',Number.isFinite(r.projection)?fmt(r.projection)+' '+r.market+' versus '+r.side+' '+fmt(r.line)+'; model '+pct(r.probability)+'.':'Projection inputs unavailable.'],
['Opportunities & form',r.rate!=null?fmt(r.rate)+' per '+esc(r.exposure_unit||'opportunity')+' × '+fmt(r.expected_exposure)+' expected opportunities. Historical clearing '+pct(r.hit_rate)+'; '+(r.sample||0)+' games.':'Rate/exposure breakdown unavailable. Historical clearing '+pct(r.hit_rate)+'; '+(r.sample||0)+' games.'],
['Offense vs defense',def.multiplier!=null?'Opponent position adjustment ×'+fmt(def.multiplier)+'; '+(def.games||0)+' observed games. '+(def.note||'Role buckets; not individual defender tracking.'):'Position matchup data unavailable; no favorable matchup is assumed.'],
['Injuries & lineup',(r.injury_status?'Player status: '+r.injury_status+'. ':'Player availability not confirmed. ')+(c.teammate_absences?.length?'Recorded teammate absences: '+c.teammate_absences.join(', ')+'. ':'No recorded teammate-absence split available. ')+'Quantified impact requires supported role/usage evidence.'],
['Home / away',c.venue?'Venue: '+c.venue+'. Venue-specific performance advantage is not established by venue alone.':'Venue/split evidence unavailable; no home or away advantage claimed.'],
['Rest',c.rest_days!=null?fmt(c.rest_days)+' days rest'+(c.back_to_back?' · back-to-back':'')+'.':'Rest information unavailable.'],
['Weather',w.indoor?'Indoor venue; outdoor weather not applied.':(w.status||'Weather evidence unavailable; no favorable adjustment assumed.')+(w.wind_mph!=null?' Wind '+fmt(w.wind_mph)+' mph.':'')],
['Sample & validation',logs.length?'Displayed logs: '+logs[0].date+' to '+logs[logs.length-1].date+'. '+(r.calibration_games||0)+' calibration groups. Current-role sample is not a complete year of all players.':'Historical date window unavailable in this snapshot. '+(r.calibration_games||0)+' calibration groups; no validated accuracy claim.'],
['Price edge',quoted?'Observed '+r.bookmaker+' '+odd(r.odds)+': model edge '+fmt(100*(r.probability-implied(r.odds)))+' pp. Quote freshness and availability must be rechecked.':'No verified market price: a favorable projection is not a demonstrated betting edge. Enter actual odds in Model logic to assess price-dependent value.'],
['Failure cases',(r.flags||[]).join('; ')||'Role changes, limited minutes/opportunities, lineup changes and model error can invalidate the projection.']
];
return actuarialMarkup(r)+decisionMarkup(r)+opportunityMarkup(r)+'<details class="pick-context"><summary>Matchup & edge evidence · all factors</summary><p class="small">'+(current?'Current refresh evidence, not a rewrite of the frozen selection.':'Frozen snapshot only; missing current inputs stay unavailable.')+'</p><dl>'+entries.map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>').join('')+'</dl></details>';
}


function opportunityMarkup(r){
 const a=(r.context||r.rationale?.context||{}).opportunity_framework;
 if(!a)return '';
 const windows=Object.entries(a.windows||{}).map(([n,x])=>`Last ${n}: ${x.games} games, average ${fmt(x.mean)}, median ${fmt(x.median)}, rate ${fmt(x.rate)}, opportunities ${fmt(x.opportunities)}`).join('; ');
 const changes=Object.entries(a.adjustments||{}).map(([k,v])=>k.replaceAll('_',' ')+' ×'+fmt(v)).join('; ');
 const splits=Object.entries(a.splits||{}).map(([k,x])=>k+': '+x.games+' games, average '+fmt(x.mean)+', opportunities '+fmt(x.opportunities)).join('; ');
 const receiving=a.receiving?`<p>Measured receiving components: ${a.receiving.games} games; catch rate ${pct(a.receiving.catch_rate)}; yards/reception ${fmt(a.receiving.yards_per_reception)}. ${esc(a.receiving.note)}</p>`:'';
 return `<details class="pick-context"><summary>Opportunity × efficiency · projection breakdown</summary><p>${esc(a.method)}</p><dl><dt>Base production</dt><dd>${fmt(r.rate)} per ${esc(a.unit)} × ${fmt(r.expected_exposure)} = ${fmt(a.base_projection)} before adjustments; final ${fmt(r.projection)} versus ${esc(r.side)} ${fmt(r.line)}.</dd><dt>Applied adjustments</dt><dd>${esc(changes)}</dd><dt>Recent windows</dt><dd>${esc(windows)}. Windows overlap and are descriptive.</dd><dt>Comparable sample</dt><dd>${a.sample?.games||0} games; median ${fmt(a.median)}, SD ${fmt(a.sd)}, range ${fmt(a.min)}–${fmt(a.max)}. Averages alone do not establish clearing probability.</dd><dt>Venue splits</dt><dd>${esc(splits)}. Small splits do not prove an advantage.</dd><dt>Advanced inputs unavailable</dt><dd>${esc((a.missing||[]).join('; '))||'No additional advanced feed connected.'}. Missing inputs are not assumed favorable.</dd></dl>${receiving}<p class="small">Adapted from your Sports Betting Metrics framework. Illustrative 30/20/20/15/10/5 weights were not fitted or used to inflate confidence. Probabilities and forward validation remain separate from descriptive history.</p></details>`;
}

function decisionMarkup(r){
 const c=r.context||r.rationale?.context||{},scenarios=c.workload_sensitivity||[],now=Date.now();
 const age=s=>s?(now-Date.parse(s))/60000:NaN;
 const feedAge=age(report.generated_at),quoteAge=age(r.odds_updated),freshFeed=Number.isFinite(feedAge)&&feedAge>=0&&feedAge<=45;
 const quoted=r.price_kind==='Observed snapshot'&&Number.isFinite(r.odds),freshQuote=quoted&&Number.isFinite(quoteAge)&&quoteAge>=0&&quoteAge<=35;
 const flags=(r.flags||[]).map(x=>x.toLowerCase()),blocked=flags.some(x=>['out','questionable','doubtful','day-to-day','starter unconfirmed','opportunity data missing','teammate usage unresolved','role changed','minutes volatility','outlier-sensitive'].includes(x));
 const p=r.probability,floor=r.probability_floor,be=freshQuote?implied(r.odds):null;
 const status=!freshFeed||blocked?'PASS':!freshQuote?'WATCH':Number.isFinite(floor)&&floor>be?'BET CANDIDATE':'PASS';
 const reason=!freshFeed?'Feed is stale or its timestamp is missing; refresh before evaluating.':blocked?'Unresolved role, availability or sample risk blocks automatic selection.':!freshQuote?'A fresh actual sportsbook price is required to establish value.':status==='PASS'?'The buffered probability does not exceed the offered price’s break-even probability.':'Buffered model probability exceeds break-even; provisional estimate requires price and availability recheck.';
 const decimal=freshQuote?(r.odds<0?1+100/Math.abs(r.odds):1+r.odds/100):null;
 const scenarioText=scenarios.map(x=>x.scenario+': '+fmt(x.opportunities)+' opportunities → '+fmt(x.projection)+' projected, '+pct(x.probability)+' clearing').join('; ');
 return `<details class="pick-context"><summary>${esc(status)} · uncertainty &amp; price check</summary><p>${esc(reason)}</p><dl><dt>Freshness</dt><dd>Feed: ${esc(report.generated_at||'unknown')}; quote: ${esc(r.odds_updated||'unavailable')}. Feed cutoff 45 minutes; quote cutoff 35 minutes. Injury and lineup source confirmation is separate and is not established by a fresh feed timestamp.</dd><dt>Probability</dt><dd>Model ${pct(p)}; heuristic buffered estimate ${pct(floor)}. Neither is a validated confidence interval.</dd><dt>Offered-price value</dt><dd>${freshQuote?'Break-even '+pct(be)+'; estimated return '+pct(p*decimal-1)+' per dollar; buffered return '+pct(floor*decimal-1)+'.':'Unavailable: model fair prices are not sportsbook offers.'}</dd><dt>Workload stress test</dt><dd>${esc(scenarioText)||'Workload history unavailable.'} Historical 20th/50th/80th percentile scenarios are sensitivity checks, not fitted likelihoods; no weighted probability is invented.</dd><dt>Validation gaps</dt><dd>No multi-book no-vig benchmark or jointly fitted parlay probability is implied. Keep independent-product parlay estimates separate from validated joint probabilities.</dd></dl></details>`;
}

function actuarialMarkup(r){
 const a=(r.context||r.rationale?.context||{}).actuarial_screen,v=report.actuarial_validation;
 if(!a)return '';
 const score=v?.by_market?.find(x=>x.sport===r.sport&&x.market===r.market);
 return `<details class="pick-context"><summary>Actuarial robustness · ${a.status==='stress-screen'?'used in selection':'insufficient inputs'}</summary><p>${esc(a.note)}</p><dl><dt>Distribution comparison</dt><dd>${a.status==='stress-screen'?esc(a.distribution)+' clearing estimate '+pct(a.comparison_probability)+'; selection floor '+pct(a.selection_floor)+'. Mean '+fmt(a.mean)+', variance '+fmt(a.variance)+'.':'Count-model comparison unavailable for this market or sample; no synthetic posterior is supplied.'}</dd><dt>Market performance</dt><dd>${score?.groups?score.groups+' event/player/market/side groups; Brier '+fmt(score.brier)+'; log loss '+fmt(score.log_loss)+'.':'No settled forecast groups available for this sport and market.'} Lower scores are better. Forecast scoring does not establish out-of-sample profitability.</dd><dt>Probability the edge is positive</dt><dd>Unavailable until a posterior model and an actual offered price are fitted and validated. A win probability or heuristic buffer cannot substitute for this quantity.</dd><dt>Parlay dependence</dt><dd>Independent-product probabilities are benchmarks. Related legs require a coherent joint game model; adding legs does not by itself improve expected return.</dd></dl></details>`;
}
