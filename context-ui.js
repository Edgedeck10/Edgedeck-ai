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
return '<details class="pick-context"><summary>Matchup & edge evidence · all factors</summary><p class="small">'+(current?'Current refresh evidence, not a rewrite of the frozen selection.':'Frozen snapshot only; missing current inputs stay unavailable.')+'</p><dl>'+entries.map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>').join('')+'</dl></details>';
}
