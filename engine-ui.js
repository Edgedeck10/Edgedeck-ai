/* Opportunity evidence and approximate empirical-dependence parlay research. */
function engineFor(r){return report.player_logs?.[r.log_key]?.model||null}
function enginePrice(r,line=r.line,side=r.side,odds=r.odds){
 const model=engineFor(r);if(!model)return null;
 const ps=[],pushes=[],evs=[];
 for(const h of model.draw_histograms){let total=0,w=0,u=0;for(const [y,n] of Object.entries(h)){total+=n;if(Number(y)===line)u+=n;else if(side==='Under'?Number(y)<line:Number(y)>line)w+=n}ps.push(w/total);pushes.push(u/total);if(odds!=null)evs.push(w/total*(decimal(odds)-1)-(1-w/total-u/total))}
 const avg=a=>a.reduce((x,y)=>x+y,0)/a.length,q=(a,p)=>{a=[...a].sort((x,y)=>x-y);return a[Math.floor((a.length-1)*p)]},p=avg(ps),push=avg(pushes),conditional=Math.max(.0001,Math.min(.9999,p/(1-push)||.5));
 return {probability:p,push_probability:push,fair_odds:fair(conditional),probability_range_80:[q(ps,.1),q(ps,.9)],expected_roi_pct:evs.length?100*avg(evs):null,ev_lower_80_pct:evs.length?100*q(evs,.1):null,probability_positive_ev:evs.length?avg(evs.map(x=>x>0?1:0)):null};
}
function evidencePanel(r){
 const m=engineFor(r);if(!m)return '<details><summary>Model coverage</summary><p class="small">Legacy game model or user-supplied estimate. The opportunity engine has not been applied to this selection.</p></details>';
 const priced=enginePrice(r),range=priced.probability_range_80;
 return `<details class="view-guide"><summary>Opportunity, uncertainty & value</summary><p><b>${esc(r.selection_status||'Research estimate')}</b> · ${esc(m.status)}</p><div class="mini"><div><span>Median / 80% outcome range</span><b>${fmt(m.median)} · ${m.outcome_range_80.map(fmt).join('–')}</b></div><div><span>Conditional probability range</span><b>${range.map(pct).join('–')}</b></div><div><span>Push probability</span><b>${pct(priced.push_probability)}</b></div></div><p><b>Opportunity:</b> ${fmt(m.expected_opportunity)} ${esc(m.opportunity_unit)}; workload range ${m.workload_range_80.map(fmt).join('–')}.<br><b>Production:</b> ${fmt(m.shrunk_rate)} per opportunity. Player credibility ${pct(m.credibility_weight)}${m.credibility_fit?' · K '+fmt(m.credibility_fit.K)+' fitted from '+m.credibility_fit.peer_players+' peer players':' · insufficient peer fit; no fitted shrinkage claimed'}.<br><b>Distribution:</b> ${esc(m.method)}.</p><p><b>History:</b> ${m.history_window.selected_games} selected games of ${m.history_window.available_games} available. Chronological holdout MAE ${fmt(m.history_window.holdout_mae)} across ${m.history_window.evaluation_games} games. This evaluates the window baseline, not the full model or betting strategy.</p><p><b>Actual-price value:</b> ${r.odds==null?'Unavailable until you enter an actual sportsbook price. A favorable projection alone is not evidence of value.':`Expected return ${fmt(priced.expected_roi_pct)}%; lower estimate ${fmt(priced.ev_lower_80_pct)}%; probability estimated EV is positive ${pct(priced.probability_positive_ev)}. These differ from the ticket win probability.`}</p><p><b>What can invalidate this estimate:</b> ${esc(m.missing_inputs.join('; '))}. ${m.fallback?'Opportunity fields missing: this selection uses a per-game fallback.':''}</p><p class="small">${esc(m.uncertainty_note)} No validated accuracy or guaranteed edge is implied. Last training game: ${esc(date(m.training_end))}.</p></details>`;
}
function jointResearch(rows){
 if(!rows.length||rows.some(r=>!engineFor(r)))return {available:false,reason:'Joint research requires an opportunity distribution for every leg.'};
 const groups=new Map();for(const r of rows){if(!groups.has(r.event_id))groups.set(r.event_id,[]);groups.get(r.event_id).push(r)}
 const blocks=[];
 for(const legs of groups.values()){
  // Composite and component markets for one player require a coherent generative model.
  if(new Set(legs.map(r=>r.player_id)).size!==legs.length)return {available:false,reason:'Multiple legs for one player require a coherent component simulation; joint probability withheld.'};
  let shared=null;
  for(const r of legs){const gs=report.player_logs[r.log_key].games;const ids=gs.map(g=>g.event_id).filter(Boolean);shared=shared===null?ids:shared.filter(id=>ids.includes(id))}
  if(legs.length>1&&shared.length<5)return {available:false,reason:'Fewer than five aligned historical games for related legs. Joint probability withheld.'};
  blocks.push({legs,shared});
 }
 let state=2166136261;for(const c of rows.map(r=>r.id).join('|'))state=Math.imul(state^c.charCodeAt(0),16777619)>>>0;
 const rand=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296};
 const quant=(h,u)=>{const entries=Object.entries(h).map(([v,n])=>[Number(v),n]).sort((a,b)=>a[0]-b[0]);const total=entries.reduce((n,x)=>n+x[1],0);let sum=0;for(const [v,n] of entries){sum+=n;if(sum>u*total)return v}return entries.at(-1)[0]};
 let wins=0,simulations=1536;
 for(let i=0;i<simulations;i++){
  let won=true;
  for(const block of blocks){const chosen=block.shared[Math.floor(rand()*block.shared.length)];for(const r of block.legs){let u=rand();if(block.legs.length>1){const gs=report.player_logs[r.log_key].games.filter(g=>block.shared.includes(g.event_id));const y=gs.find(g=>g.event_id===chosen).value;u=(gs.filter(g=>g.value<y).length+rand()*gs.filter(g=>g.value===y).length)/gs.length}const m=engineFor(r),h=m.draw_histograms[Math.floor(rand()*m.draw_histograms.length)],y=quant(h,u);if(!(r.side==='Under'?y<r.line:y>r.line))won=false}}
  if(won)wins++;
 }
 return {available:true,p:wins/simulations,simulations,related_groups:blocks.filter(b=>b.legs.length>1).length,shared_players:rows.length-new Set(rows.map(r=>r.player_id)).size};
}
function jointPanel(rows){const x=jointResearch(rows);return `<div class="callout"><b>Dependence & exposure</b><p>${x.available?`${pct(x.p)} estimated all-leg win probability from ${x.simulations} scenarios. Related game groups: ${x.related_groups}.` :esc(x.reason)}</p><p class="small">Research-only empirical dependence model: aligned historical games supply joint ranks, current opportunity distributions supply outcomes. Different games are assumed independent. This is not a coherent play-by-play game simulation, a calibrated parlay forecast or an optimizer. Same-player combinations are withheld. Adding legs does not establish better value.</p><p class="small">Exposure: ${new Set(rows.map(r=>r.event_id)).size} games / ${rows.length} legs. Portfolio staking optimization is disabled until forecasts and joint returns are validated.</p></div>`}
function renderEngineHealth(){
 const target=document.getElementById('health'),rows=report.engine_monitoring||[];
 target.insertAdjacentHTML('beforeend',`<details class="view-guide"><summary>Opportunity engine validation</summary><p>${esc(report.engine_status?.coverage||'Engine report unavailable')}</p><p>Credibility and dispersion are fitted approximations. Calibration monitoring is separate from model fitting. No portfolio optimizer, full hierarchical posterior, or coherent game simulation is active.</p>${rows.length?'<div style="overflow-x:auto"><table><thead><tr><th>Sport / market</th><th>Forecast groups</th><th>Brier</th><th>Log loss</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${esc(r.sport+' / '+r.market)}</td><td>${r.forecast_groups}</td><td>${Number(r.brier).toFixed(3)}</td><td>${Number(r.log_loss).toFixed(3)}</td></tr>`).join('')+'</tbody></table></div>':'<p>No graded forecasts for this engine version yet. Accuracy and calibration are not established.</p>'}<p class="small">Scores group alternate lines by event, player, market and direction. They are not independent bets. Chronological window MAE does not validate the complete pick/parlay selection process.</p></details>`);
}
