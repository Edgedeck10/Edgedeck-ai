'use strict';
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=v=>Number.isFinite(v)?(v*100).toFixed(1)+'%':'—',fmt=v=>v==null?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:1}),odd=v=>v==null?'Unpriced':(v>0?'+':'')+v;
const decimal=o=>o<0?1+100/-o:1+o/100, implied=o=>o<0?-o/(-o+100):100/(o+100),fair=p=>Math.round(p>=.5?-100*p/(1-p):100*(1-p)/p);
const date=v=>v?new Date(v).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'—';
let report={recommendations:[],metrics:{},games:[],injuries:[]},history=[],personal=[],selected=[],page=30,hpage=50,labRow=null,labOutput=null,historyLoaded=false,currentView='board',quick='all';
try{personal=JSON.parse(localStorage.getItem('edgedeck-personal-v2')||'[]');if(!Array.isArray(personal))personal=[]}catch(e){personal=[]}
function save(){try{localStorage.setItem('edgedeck-personal-v2',JSON.stringify(personal))}catch(e){toast('Device storage is unavailable. Export your picks to retain them.')}}
function toast(s){$('toast').textContent=s;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,4500)}
const all=()=>[...report.recommendations,...personal];
const active=r=>!r.start||new Date(r.start)>new Date();
function safeUrl(url){try{const u=new URL(url);return u.protocol==='https:'?esc(u.href):'#'}catch(e){return '#'}}
function go(view){currentView=view;document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==view);document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x.dataset.nav===view));if(view==='board')renderBoard();if(view==='history')loadHistory();if(view==='parlay')renderSlip();if(view==='matchups')renderGames();if(view==='touchdowns')renderTouchdowns();if(view==='data'){renderHealth();renderEngineHealth();renderCoverageStatus()}document.querySelector('.tabs').scrollIntoView({block:'start',behavior:'smooth'})}
document.querySelectorAll('[data-nav]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.nav)));
function label(r){return r.market==='Moneyline'?'Moneyline':r.market==='Spread'?'Spread '+(r.line>0?'+':'')+fmt(r.line):r.side+' '+fmt(r.line)+' '+r.market}
function setOptions(id,values,first){const old=$(id).value;$(id).innerHTML=`<option value="">${first}</option>`+[...new Set(values)].sort().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');$(id).value=values.includes(old)?old:''}
function enrich(r){if(r.odds!=null){r.break_even=implied(r.odds);r.edge_pp=(r.probability-r.break_even)*100;r.expected_roi_pct=(r.probability*(decimal(r.odds)-1)-(1-r.probability-(r.push_probability||0)))*100}return r}

const SPORT_GROUPS=[
 ['all','All sports','◈',[], 'Explore player props and game markets across the board.'],
 ['pro-football','Pro Football','🏈',['NFL','CFL','UFL'],'Passing, rushing, receiving, touchdowns and game lines.'],
 ['college-football','College Football','🏈',['NCAAF'],'College passing, rushing, receiving and game lines.'],
 ['pro-basketball','Pro Basketball','🏀',['NBA','WNBA','EUROLEAGUE'],'Points, rebounds, assists, threes and combination props.'],
 ['college-basketball','College Basketball','🏀',['NCAAB','NCAAW'],'College points, rebounds, assists and game lines.'],
 ['hockey','Hockey','🏒',['NHL'],'Shots on goal, saves, points and game totals.'],
 ['baseball','Baseball','⚾',['MLB','NPB','KBO'],'Hits, total bases, strikeouts, runs and game lines.'],
 ['golf','Golf','⛳',['PGA','LPGA','GOLF'],'Tournament finishes, round markets and head-to-heads.'],
 ['soccer','Soccer','⚽',['EPL','MLS','UCL','LALIGA','BUNDESLIGA','SERIEA','LIGUE1','NWSL'],'Goals, shots, saves and match markets.'],
];
function majorSport(r){return SPORT_GROUPS.some(g=>g[3].includes(String(r.sport||'').toUpperCase()))}
let selectedSportGroup='all';
const sportGroup=()=>SPORT_GROUPS.find(g=>g[0]===selectedSportGroup)||SPORT_GROUPS[0];
function matchesSport(r){const g=sportGroup(),code=String(r.sport||'').toUpperCase();return majorSport(r)&&(!$('sport').value||code===$('sport').value)&&(g[0]==='all'||(g[0]==='other'?!SPORT_GROUPS.some(x=>x[3].includes(code)):g[3].includes(code)))}
function sportOptions(){const g=sportGroup(),codes=g[0]==='all'?SPORT_GROUPS.flatMap(x=>x[3]):g[0]==='other'?all().map(x=>x.sport).filter(code=>!SPORT_GROUPS.some(x=>x[3].includes(code))):g[3];setOptions('sport',codes,'All leagues');}
function selectSportGroup(id){selectedSportGroup=id;$('sport').value='';$('market').value='';$('search').value='';$('lineType').value='';$('day').value='';$('positive').checked=false;$('hideFlags').checked=false;quick='all';page=30;sportOptions();renderBoard();renderGames();if(historyLoaded||pickRecord)renderHistory();}
function renderSportNavigation(){
 const g=sportGroup(),available=all().filter(r=>active(r)&&majorSport(r)),counts=new Map();for(const r of available)counts.set(r.sport,(counts.get(r.sport)||0)+1);
 $('sportsRail').innerHTML=SPORT_GROUPS.map(x=>{const n=x[0]==='all'?available.length:x[0]==='other'?available.filter(r=>!SPORT_GROUPS.some(z=>z[3].includes(r.sport))).length:x[3].reduce((n,c)=>n+(counts.get(c)||0),0);return `<button class="sport-tab ${x[0]===g[0]?'active':''}" data-sport-group="${x[0]}" aria-pressed="${x[0]===g[0]}"><span aria-hidden="true">${x[2]}</span><b>${esc(x[1])}</b><small>${n?n.toLocaleString()+' lines':'No active lines'}</small></button>`}).join('');
 const scoped=available.filter(matchesSport),markets=[...new Set(scoped.map(x=>x.market))].sort(),old=$('market').value;
 setOptions('market',markets,'All markets');if(markets.includes(old))$('market').value=old;
 $('sportTitle').textContent=g[1]+($('sport').value?' · '+$('sport').value:'')+' research';$('sportDescription').textContent=g[4];
 const automatic=g[0]==='all'?(report.coverage||[]):g[3].filter(c=>(report.coverage||[]).includes(c));
 $('sportCoverage').textContent=scoped.length?`${scoped.length.toLocaleString()} active lines · ${new Set(scoped.map(r=>r.event_id)).size} events. ${automatic.length?'Automatic feed: '+automatic.join(', ')+'.':'Imported research only.'}`:automatic.length?'No active lines for this selection. Scheduled games and usable history determine availability.':'No automatic feed connected for this selection. Add real lines through Data & model; no sample predictions are substituted.';
 $('marketRail').innerHTML=['',...markets].map(m=>`<button class="chip ${$('market').value===m?'active':''}" data-market-tab="${esc(m)}" aria-pressed="${$('market').value===m}">${esc(m||'All markets')}</button>`).join('');
 $('poolScope').textContent='Generate a pool from '+g[1]+($('sport').value?' · '+$('sport').value:'')+'. Existing manually selected legs stay in your pool.';
}
document.addEventListener('click',e=>{const sport=e.target.closest('[data-sport-group]'),market=e.target.closest('[data-market-tab]');if(sport)selectSportGroup(sport.dataset.sportGroup);if(market){$('market').value=market.dataset.marketTab;page=30;renderBoard()}});

let refreshPromise=null,lastStatusCheck=0;
const detailRequests=new Map(),loadedDetails=new Set();
function hydrateFeed(data){
 if(data.row_templates){data.recommendations=data.recommendations.map(r=>({...data.row_templates[r.row_template],...r}));delete data.row_templates}
 const models=[...Object.values(data.player_logs||{}).map(x=>x.model),...Object.values(data.ai_selections||{}).flat().map(r=>r.frozen_model),...Object.values(data.ai_models||{})];
 for(const m of models)if(m?.distribution_id){const h=data.distributions?.[m.distribution_id];if(!h)throw Error('Incomplete forecast distribution');m.draw_histograms=h}
 return data;
}
async function fetchFeed(url,compressed=false,timeout=90000){const control=new AbortController(),timer=setTimeout(()=>control.abort(),timeout);try{const r=await fetch(url,{cache:'no-store',signal:control.signal});if(!r.ok)throw Error('HTTP '+r.status);if(!compressed)return await r.json();if(typeof DecompressionStream==='undefined')throw Error('Please update your browser to load the compressed research feed.');return await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json()}finally{clearTimeout(timer)}}
async function loadData(name){return fetchFeed('./data/classic/'+name+'.gz?t='+Date.now(),true)}
async function savedFeed(value){
 if(typeof indexedDB==='undefined')return null;
 if(value)try{value=structuredClone(value)}catch(error){return null}
 return new Promise(resolve=>{
  const request=indexedDB.open('edgedeck-feed-v1',1);
  request.onupgradeneeded=()=>request.result.createObjectStore('feed');
  request.onerror=()=>resolve(null);
  request.onsuccess=()=>{
   const db=request.result,tx=db.transaction('feed',value?'readwrite':'readonly'),store=tx.objectStore('feed');
   const task=value?store.put(value,'latest'):store.get('latest');
   task.onsuccess=()=>{if(!value)resolve(task.result||null)};
   tx.oncomplete=()=>{db.close();if(value)resolve(value)};
   tx.onerror=()=>{db.close();resolve(null)};
  };
 });
}
function presentFeed(data){
 const next=hydrateFeed(data);
 if(!Array.isArray(next.recommendations)||!next.generated_at)throw Error('Invalid feed');
 report={games:[],injuries:[],calibration_bins:[],...next};
 detailRequests.clear();loadedDetails.clear();
 report.recommendations.forEach(enrich);
 sportOptions();setOptions('market',all().map(x=>x.market),'All markets');setOptions('day',all().map(x=>x.day).filter(Boolean),'Upcoming games');
 renderKpis();
 if(currentView==='board')renderBoard();
 if(currentView==='data'){renderHealth();renderEngineHealth();renderCoverageStatus()}
 if(currentView==='matchups')renderGames();
 if(currentView==='touchdowns')renderTouchdowns();
 if(currentView==='parlay')renderSlip();
 renderCalibration();if(currentView==='history')loadHistory();
}
async function load(){if(refreshPromise)return refreshPromise;refreshPromise=refreshFeed();try{return await refreshPromise}finally{refreshPromise=null}}
async function refreshFeed(){const b=$('reload');b.disabled=true;try{
 let status=null;try{status=await fetchFeed('./data/classic/status.json?t='+Date.now(),false,15000);lastStatusCheck=Date.now()}catch(e){if(report.generated_at&&Date.now()-lastStatusCheck<300000){renderKpis();return}}
 if(status?.generated_at===report.generated_at){renderKpis();return}
 const raw=await loadData('latest.json');
 // IndexedDB clones the compact payload before hydration expands shared fields.
 void savedFeed(raw);
 presentFeed(raw);
 }catch(e){$('notice').className='notice error';$('notice').textContent='Connection interrupted. Showing the last loaded board; retrying automatically. '+e.message;if(!report.recommendations.length)$('cards').innerHTML='<div class="empty"><h3>Connecting to the feed</h3><p>Automatic retry is active. Check latest can retry now.</p></div>'}finally{b.disabled=false}}
async function ensureDetails(eventId){
 if(!report.detail_files?.[eventId]||loadedDetails.has(eventId))return;
 if(detailRequests.has(eventId))return detailRequests.get(eventId);
 const generation=report.generated_at,path=report.detail_files[eventId];
 const request=(async()=>{
  const data=hydrateFeed(await fetchFeed('./data/classic/'+path,true));
  if(report.generated_at!==generation)return;
  Object.assign(report.player_logs,data.player_logs);
  Object.assign(report.game_evidence,data.game_evidence);
  for(const rows of Object.values(report.ai_selections||{}))for(const r of rows)if(data.ai_models?.[r.id])r.frozen_model=data.ai_models[r.id];
  loadedDetails.add(eventId);
 })();
 detailRequests.set(eventId,request);
 try{await request}finally{detailRequests.delete(eventId)}
}
function pickDetails(r){
 if(!report.detail_files?.[r.event_id]||loadedDetails.has(r.event_id))return projectionPanel(r)+evidencePanel(r)+propHistoryPanel(r)+lastTenLog(r);
 return '<details data-load-detail="'+esc(r.id)+'"><summary>Game history, charts &amp; projection evidence</summary><div data-loaded-detail>Open to load detailed analysis.</div></details>';
}
document.addEventListener('toggle',async e=>{
 const host=e.target;
 if(!host.matches?.('[data-load-detail]')||!host.open)return;
 const r=all().find(r=>r.id===host.dataset.loadDetail),target=host.querySelector('[data-loaded-detail]');
 if(!r)return;
 target.textContent='Loading game history and analysis…';
 try{await ensureDetails(r.event_id);if(host.isConnected)target.innerHTML=projectionPanel(r)+evidencePanel(r)+propHistoryPanel(r)+lastTenLog(r)}
 catch(error){target.textContent='Unable to load analysis. Close and reopen to retry.'}
},true);
async function startFeed(){
 const cached=await Promise.race([savedFeed(),new Promise(resolve=>setTimeout(()=>resolve(null),1500))]);
 if(cached)try{presentFeed(cached)}catch(error){}
 return load();
}
function renderKpis(){const rows=report.recommendations,m=report.metrics,props=rows.filter(x=>x.player_id),priced=rows.filter(x=>x.odds!=null),age=(Date.now()-new Date(report.generated_at))/60000;const k=[['Player-prop lines',props.length,'Points · rebounds · assists · combos'],['Observed game prices',priced.length,'Spreads, totals & moneyline'],['Player markets',new Set(props.map(x=>x.market)).size,'All estimated probabilities included'],['Forecasts graded',m.settled_predictions||0,'Prospective, immutable history'],['Refresh cadence','15 min','GitHub schedule · may run late']];$('kpis').innerHTML=k.map(([n,v,d])=>`<div class="kpi"><span>${esc(n)}</span><strong>${esc(v)}</strong><small>${esc(d)}</small></div>`).join('');$('fresh').textContent=`Updated ${date(report.generated_at)}`;$('notice').className='notice'+(age>35?' warn':'');$('notice').textContent=age>35?'Feed is '+Math.floor(age)+' minutes old. Check latest before comparing prices.':'';}
function primaryLine(r){return !r.player_id||r.line===r.base_line}
function preferredPrice(r){const o=r.odds??r.fair_odds;return Number.isFinite(o)&&o>=-200&&o<=200}
function valueRank(r){return r.odds!=null?(r.expected_roi_pct??-Infinity):-(Math.abs((r.probability/(1-(r.push_probability||0)))-.5))*100}
function filtered(){const q=$('search').value.toLowerCase(),s=$('sport').value,m=$('market').value,d=$('day').value,t=$('lineType').value;let rows=all().filter(r=>active(r)&&($('boardView').value==='all'||primaryLine(r))&&($('priceRange').value==='all'||preferredPrice(r))&&(!q||[r.selection,r.player,r.event,r.sport].join(' ').toLowerCase().includes(q))&&matchesSport(r)&&(!m||r.market===m)&&(!d||r.day===d)&&(!t||t==='props'&&r.player_id||t==='games'&&!r.player_id||t==='priced'&&r.odds!=null||t==='suggested'&&r.odds==null)&&(!$('positive').checked||r.edge_pp>0)&&(!$('hideFlags').checked||!(r.flags||[]).length));const sort=$('sort').value;rows.sort((a,b)=>sort==='value'?((b.odds!=null&&b.expected_roi_pct>0?1:0)-(a.odds!=null&&a.expected_roi_pct>0?1:0)||valueRank(b)-valueRank(a)):sort==='edge'?(b.edge_pp??-999)-(a.edge_pp??-999):sort==='prob'?b.probability-a.probability:sort==='streak'?(b.streak||0)-(a.streak||0):sort==='start'?new Date(a.start)-new Date(b.start):(Math.min(b.sample||0,20)*.015+b.probability+(b.player_id?.1:0))-(Math.min(a.sample||0,20)*.015+a.probability+(a.player_id?.1:0)));return rows}
function card(r){const inSlip=selected.includes(r.id),price=r.odds==null?'Suggested line':r.price_kind||'Observed snapshot',hasModel=r.sd!=null,context=r.context||{},flags=r.flags||[];return `<article class="pick"><div class="pick-head"><span class="tag">${esc(r.sport)} · ${r.player_id?'PLAYER PROP':'GAME MARKET'}</span><span class="tag ${r.odds==null?'gold-tag':'green-tag'}">${esc(price)}</span></div><p class="small">${r.odds==null?'Unpriced research: enter the actual sportsbook line and price before assessing value.':r.expected_roi_pct>0?'Estimated positive value at the observed price; confirm availability and matchup inputs.':'No positive estimated value at the observed price.'}</p><h3>${esc(r.player||r.selection)}</h3><div class="match">${esc(r.event)}<br>${esc(date(r.start))}</div><div class="selection">${esc(label(r))}</div><div class="numbers"><div><span>Estimated hit probability</span><b class="">${pct(r.probability)}</b></div><div><span>${r.odds==null?'Model fair price':'Observed price'}</span><b class="price">${odd(r.odds??r.fair_odds??fair(r.probability))}</b></div></div><div class="mini"><div><span>Projection</span><b>${fmt(r.projection)}</b></div><div><span>${r.hit_rate==null?'Past team games':'Recent hit rate'}</span><b>${r.hit_rate==null?fmt(r.sample):pct(r.hit_rate)}</b></div><div><span>${r.odds==null?'Current streak':'Price edge'}</span><b class="${r.edge_pp>0?'green':''}">${r.odds==null?(r.streak==null?'—':r.streak+' games'):fmt(r.edge_pp)+' pp'}</b></div></div><div class="small">${r.player_id?`${r.sample} sampled games · L5 ${r.last5_hits}/5 · ${fmt(r.projected_minutes)} projected min`:`${r.sample||0} past team games · ${r.calibration_games||0} calibration groups`}</div><div class="flags">${flags.map(x=>`<span class="tag flag">${esc(x)}</span>`).join('')}<span class="tag">${r.calibration_games>=100?'Calibration accumulating':'Unvalidated model'}</span></div><details><summary>Form, context & model notes</summary><p>${esc(r.reasoning||'User-supplied selection; probability has not been independently verified.')}</p>${r.player_id?`<p>Available baseline ${fmt(r.baseline)} · last 5 ${fmt(r.last5)} · trend ${fmt(r.trend_pct)}%<br>Per minute ${fmt(r.per_minute)} · ${esc(context.venue)} · rest ${fmt(context.rest_days)} days<br>Injury: ${esc(r.injury_status||'Not checked')}<br>Teammates listed out: ${esc((context.teammate_absences||[]).join(', ')||'None returned by feed')}</p><p>Recent values: ${(r.recent_values||[]).map(fmt).join(' · ')}</p>`:''}<p>${r.odds==null?'No sportsbook offer is attached. Fair price is model-implied, not an actual quote.':`${esc(r.bookmaker)} via ${esc(r.origin==='personal'?'your entry':'ESPN')} · observed ${esc(date(r.odds_updated||r.observed_at))}. Estimated ROI ${fmt(r.expected_roi_pct)}%. Exact availability may differ.`}</p><p>Prospective calibration samples: ${r.calibration_games||0}. No estimated edge is a guarantee of value.</p></details>${pickDetails(r)}<div class="pick-actions"><button class="white analyze" data-id="${esc(r.id)}">Analyze line</button><button class="${inSlip?'navy':'gold'} add" data-id="${esc(r.id)}">${inSlip?'✓ In studio':'+ Parlay pool'}</button></div><div class="source-line"><a href="${safeUrl(r.source_url||'https://www.espn.com/')}" target="_blank" rel="noopener">Stats & research ↗</a><a href="https://sportsbook.draftkings.com/" target="_blank" rel="noopener">DraftKings ↗</a></div></article>`}
function renderBoard(){renderSportNavigation();renderGameIndex();const rows=filtered();$('resultCount').textContent=rows.length.toLocaleString()+' matching lines';$('cards').innerHTML=rows.length?rows.slice(0,page).map(card).join(''):`<div class="empty"><h3>No matching lines</h3><p>No picks meet the current sport, league and market filters. Check the coverage note above, choose another date, or import a real selection in Data & model.</p><button class="outline" id="emptyReset">Reset filters</button></div>`;$('more').hidden=rows.length<=page;document.querySelectorAll('.analyze').forEach(b=>b.onclick=()=>openLab(b.dataset.id));document.querySelectorAll('.add').forEach(b=>b.onclick=()=>add(b.dataset.id));if($('emptyReset'))$('emptyReset').onclick=resetFilters}
function resetFilters(){$('boardView').value='main';$('priceRange').value='balanced';$('sort').value='value';selectedSportGroup='all';sportOptions();['search','sport','market','day','lineType'].forEach(id=>$(id).value='');$('positive').checked=false;$('hideFlags').checked=false;quick='all';document.querySelectorAll('[data-quick]').forEach(b=>b.classList.toggle('active',b.dataset.quick==='all'));page=30;renderBoard()}
['search','sport','market','day','lineType','sort','boardView','priceRange','positive','hideFlags'].forEach(id=>$(id).addEventListener('input',()=>{if(id==='sport'){$('market').value='';renderGames();if(historyLoaded||pickRecord)renderHistory()}page=30;renderBoard()}));$('reset').onclick=resetFilters;$('more').onclick=()=>{page+=30;renderBoard()};$('reload').onclick=load;
document.querySelectorAll('[data-quick]').forEach(b=>b.onclick=()=>{const savedGroup=selectedSportGroup,savedLeague=$('sport').value;resetFilters();selectedSportGroup=savedGroup;sportOptions();$('sport').value=savedLeague;quick=b.dataset.quick;document.querySelectorAll('[data-quick]').forEach(x=>x.classList.toggle('active',x===b));if(quick==='props')$('lineType').value='props';if(quick==='combos'){$('lineType').value='props';$('search').value='';$('market').value='PRA'}if(quick==='priced'){$('lineType').value='priced';$('sort').value='edge'}if(quick==='football'){selectedSportGroup='pro-football';sportOptions();$('sport').value='NFL';$('lineType').value='props'}renderBoard()});
// Exact-threshold normal model with transparent empirical hit rates. No invented market odds.
function erf(x){const sign=x<0?-1:1;x=Math.abs(x);const t=1/(1+.3275911*x);return sign*(1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-x*x))}
function normalCdf(x,mu,sd){return .5*(1+erf((x-mu)/(Math.max(sd,.25)*Math.sqrt(2))))}
async function openLab(id){const row=all().find(r=>r.id===id);if(!row)return;try{await ensureDetails(row.event_id)}catch(error){toast('Detailed analysis is temporarily unavailable. Please retry.');return}labRow=all().find(r=>r.id===id);if(!labRow)return;labOutput=null;$('labAdd').disabled=true;$('labSelected').textContent=labRow.selection+' · '+labRow.event+' · '+labRow.market;$('labLine').value=labRow.line??0;$('labSide').innerHTML=(labRow.market==='Moneyline'||labRow.market==='Spread')?`<option>${esc(labRow.side)}</option>`:'<option>Over</option><option>Under</option>';$('labSide').value=labRow.side;$('labOdds').value=labRow.odds??'';$('labBook').value=labRow.bookmaker||'DraftKings';$('labLine').disabled=labRow.market==='Moneyline';go('lab');calculateLab()}
function calculateLab(){if(!labRow){toast('Choose Analyze line on the bet board first.');return}const line=Number($('labLine').value),side=$('labSide').value,entered=$('labOdds').value.trim(),o=entered===''?null:Number(entered);if(!Number.isFinite(line)||o!==null&&(!Number.isFinite(o)||Math.abs(o)<100)){toast('Enter a valid line and American odds of +100 or more / -100 or less.');return}let p=labRow.probability;if(labRow.sd!=null&&labRow.market!=='Moneyline'){const c=normalCdf(labRow.market==='Spread'?-line:line,labRow.projection,labRow.sd);p=side==='Under'?c:1-c;p=Math.max(.025,Math.min(.975,p))}else if(line!==labRow.line&&labRow.market!=='Moneyline'){toast('This imported row has no statistical distribution. Its probability cannot be recalculated for a different line.');return}const vals=labRow.recent_values||[],hits=vals.map(v=>side==='Over'?v>line:v<line),rate=hits.length?hits.filter(Boolean).length/hits.length:null;labOutput=enrich({...labRow,id:'personal-'+Date.now(),line:labRow.market==='Moneyline'?null:line,side,raw_probability:p,probability:p,fair_odds:fair(p),hit_rate:rate,odds:o,bookmaker:o===null?null:$('labBook').value.trim(),price_kind:o===null?'Suggested line':'User-entered price',origin:'personal',observed_at:new Date().toISOString(),predicted_at:new Date().toISOString(),outcome:null,flags:[...(labRow.flags||[]),'Personal line'],qualified:false,calibration_games:0});const estimated=enginePrice(labOutput,line,side,o);if(estimated){Object.assign(labOutput,estimated);labOutput.raw_probability=estimated.probability;enrich(labOutput);p=estimated.probability} $('labResult').innerHTML=`<div class="mini"><div><span>Estimated hit</span><strong>${pct(p)}</strong></div><div><span>Recent hit rate</span><strong>${pct(rate)}</strong></div><div><span>Model fair price</span><strong>${odd(labOutput?.fair_odds??fair(p))}</strong></div></div><p>${esc(label(labOutput))} · ${o==null?'No actual price entered':`${odd(o)} · break-even ${pct(implied(o))} · edge ${fmt((p-implied(o))*100)} pp`}</p><p class="small">This recalculates the provisional statistical model. It does not verify that a sportsbook offers the line. ${rate==null?'No empirical sample is attached.':hits.filter(Boolean).length+'/'+hits.length+' recent games cleared this exact threshold.'}</p>`;$('labResult').innerHTML+=evidencePanel(labOutput);$('labAdd').disabled=false}
$('labCalculate').onclick=calculateLab;$('labAdd').onclick=()=>{if(!labOutput)return;personal.push({...labOutput});save();setOptions('market',all().map(x=>x.market),'All markets');renderBoard();renderPersonal();toast('Saved to your personal board on this device.');$('labAdd').disabled=true};$('go90').onclick=()=>{go('board');document.querySelector('[data-quick="props"]').click()};
function add(id){if(selected.includes(id)){selected=selected.filter(x=>x!==id)}else{const r=all().find(x=>x.id===id);if(!r||!active(r)){toast('This game has already started.');return}if(selected.length>=10){toast('The research pool supports up to 10 legs.');return}selected.push(id);toast('Added to parlay studio.')}renderSlip();renderBoard()}
function buildPool(n){const priced=$('poolType').value==='priced';let rows=all().filter(r=>active(r)&&primaryLine(r)&&preferredPrice(r)&&matchesSport(r)&&(r.sample||0)>=5&&(!(r.flags||[]).some(x=>/questionable|doubtful|volatility|out/i.test(x)))&&(!priced||r.odds!=null&&r.edge_pp>0));rows.sort((a,b)=>priced?(b.ev_lower_80_pct??b.expected_roi_pct??-Infinity)-(a.ev_lower_80_pct??a.expected_roi_pct??-Infinity):valueRank(b)-valueRank(a));selected=[];const games=new Set();for(const r of rows){if(!r.event_id||games.has(r.event_id))continue;selected.push(r.id);games.add(r.event_id);if(selected.length===n)break}$('poolNote').textContent=`Found ${selected.length} of ${n} requested legs across different games. ${selected.length<n?'Not enough eligible games passed your filters; no filler picks were added.':''} Suggested lines still require sportsbook availability checks.`;renderSlip();renderBoard()}
function renderSlip(){selected=selected.filter(id=>all().some(r=>r.id===id&&active(r)));const rows=selected.map(id=>all().find(r=>r.id===id));$('slipBadge').textContent=rows.length;$('slip').innerHTML=rows.length?rows.map(r=>`<div class="slip-leg"><div><strong>${esc(r.selection)} · ${esc(label(r))}</strong><div class="small">${esc(r.event)} · ${pct(r.probability)} estimate · ${r.odds==null?'suggested, unpriced':odd(r.odds)}</div></div><button class="white remove" data-id="${esc(r.id)}" aria-label="Remove ${esc(r.selection)}">×</button></div>`).join(''):'<div class="empty"><h3>Your research pool is empty</h3><p>Choose legs from the board, or generate a pool above.</p></div>';document.querySelectorAll('.remove').forEach(b=>b.onclick=()=>add(b.dataset.id));const supported=jointResearch(rows).available,p=supported?rows.reduce((p,r)=>p*r.probability,1):null,quoted=rows.length&&rows.every(r=>r.odds!=null),d=quoted&&new Set(rows.map(r=>r.event_id)).size===rows.length?rows.reduce((p,r)=>p*decimal(r.odds),1):null,lower=Math.max(0,rows.reduce((s,r)=>s+r.probability,0)-(rows.length-1)),upper=rows.length?Math.min(...rows.map(r=>r.probability)):0;$('combined').innerHTML=rows.length?`<div class="combined-value">${p==null?'Withheld':pct(p)}</div><div class="small">${rows.length} legs · different-game independence only</div><div class="combo-stats"><div><span>Model fair decimal</span><b>${p==null?'—':(1/p).toFixed(2)}</b></div><div><span>Quoted-leg product</span><b>${d?d.toFixed(2):'Unpriced'}</b></div><div><span>Break-even from prices</span><b>${d?pct(1/d):'—'}</b></div><div><span>Possible joint range*</span><b>${pct(lower)}–${pct(upper)}</b></div></div><p class="small">*Mathematical bounds given the individual estimates, not a confidence interval. Even different games may share model errors. ${quoted?'Prices may be repriced by the book.':'Missing prices prevent a payout or value claim.'}</p>${jointPanel(rows)}${ticketPayoutForm(rows)}`:'<div class="combined-value">—</div><p>Select up to 10 legs.</p>'}
document.querySelectorAll('[data-build]').forEach(b=>b.onclick=()=>buildPool(Number(b.dataset.build)));$('clearSlip').onclick=()=>{selected=[];renderSlip();renderBoard()};
function renderGames(){const games=(report.games||[]).filter(matchesSport);$('games').innerHTML=games.length?games.map(g=>{const rows=report.recommendations.filter(r=>r.event_id===g.id),team=rows.find(r=>r.market==='Total')?.context||{},inj=(report.injuries||[]).filter(i=>i.event_id===g.id);return `<article class="game"><span class="tag">${esc(g.sport)} · ${esc(date(g.start))}</span><h3>${esc(g.event)}</h3>${gamePickSection(g)}<div class="mini"><div><span>Home scoring</span><b>${fmt(team.home?.points_for)}</b></div><div><span>Away scoring</span><b>${fmt(team.away?.points_for)}</b></div><div><span>Model total</span><b>${fmt(rows.find(r=>r.market==='Total')?.projection)}</b></div></div><p class="small">${esc(g.home.name)}: ${fmt(team.home?.rest_days)} rest days ${team.home?.back_to_back?'· back-to-back':''}<br>${esc(g.away.name)}: ${fmt(team.away?.rest_days)} rest days ${team.away?.back_to_back?'· back-to-back':''}<br>Home allowed ${fmt(team.home?.points_allowed)} · away allowed ${fmt(team.away?.points_allowed)}</p><details><summary>Injury report (${inj.length})</summary>${inj.length?inj.map(x=>`<div class="injury-item"><b>${esc(x.player)}</b> · ${esc(x.status)}<br>${esc(x.detail)} · reported ${esc(date(x.updated))}</div>`).join(''):'<p class="small">No injury entries returned. This does not confirm that every player is available.</p>'}</details><a class="small" href="${safeUrl(g.source_url)}" target="_blank" rel="noopener">Matchup source ↗</a></article>`}).join(''):'<div class="empty">No upcoming matchups returned.</div>'}
let pickRecord=null,pickRecordRequest=null,forecastRequest=null;
function loadPickRecord(){
 if(pickRecordRequest)return pickRecordRequest;
 pickRecordRequest=loadData('pick-record.json').then(rows=>{if(!Array.isArray(rows))throw Error('Invalid record');pickRecord=rows}).finally(()=>{pickRecordRequest=null});
 return pickRecordRequest;
}
async function loadHistory(){
 try{
  if($('historySource').value==='picks'){
   await loadPickRecord();
  }else if(!historyLoaded){
   forecastRequest??=loadData('history.json').finally(()=>{forecastRequest=null});
   history=await forecastRequest;historyLoaded=true;renderCalibration();
  }
  renderHistory();renderPersonal();
 }catch(error){$('historyRows').textContent='Could not load the record. Reopen Results & calibration to retry.'}
}
const historyCategories={
 Moneyline:r=>r.market==='Moneyline',
 Spread:r=>r.market==='Spread',
 'Player props':r=>Boolean(r.player_id),
 Overs:r=>String(r.side).toLowerCase()==='over',
 Unders:r=>String(r.side).toLowerCase()==='under',
};
function historySelection(){
 const rows=$('historySource').value==='picks'?pickRecord:historyLoaded?history:null;
 const query=$('historySearch').value.trim().toLowerCase();
 const sport=$('historySport').value;
 return rows?.filter(r=>(!sport||r.sport===sport)&&[r.selection,r.player,r.event,r.market,r.sport].join(' ').toLowerCase().includes(query));
}
function renderHistory(){
 const source=$('historySource').value==='picks'?pickRecord:history;
 if(source)setOptions('historySport',source.map(r=>r.sport).filter(Boolean),'All sports');
 const scope=historySelection();
 if(!scope){$('historyRows').textContent='Loading pick records…';$('historyMore').hidden=true;return}
 const rates=Object.entries(historyCategories).map(([name,select])=>{
  const counts={wins:0,losses:0,pushes:0,pending:0};
  for(const r of scope)if(select(r))counts[r.outcome===1?'wins':r.outcome===0?'losses':r.outcome==='push'?'pushes':'pending']++;
  const settled=counts.wins+counts.losses;
  return {name,...counts,rate:settled?counts.wins/settled:null};
 }).sort((a,b)=>(b.rate??-1)-(a.rate??-1));
 $('pickRates').innerHTML='<div style="overflow-x:auto"><table><thead><tr><th>Category</th><th>Win %</th><th>Won</th><th>Lost</th><th>Push</th><th>Pending</th></tr></thead><tbody>'+rates.map(r=>`<tr><td>${esc(r.name)}</td><td><b>${pct(r.rate)}</b></td><td>${r.wins}</td><td>${r.losses}</td><td>${r.pushes}</td><td>${r.pending}</td></tr>`).join('')+'</tbody></table></div>';
 const rows=filteredHistory(scope).reverse();
 $('historyRows').innerHTML='<p class="small">'+rows.length.toLocaleString()+' matching records</p>'+rows.slice(0,hpage).map(r=>`<div class="history-row"><div><strong>${esc(r.selection)} · ${esc(label(r))}</strong><span class="small">${esc(r.event||r.sport)} · ${date(r.start)} · final ${fmt(r.actual_value)} · ${odd(r.odds)}</span></div><span class="result ${r.outcome===1?'win':r.outcome===0?'loss':''}">${r.outcome===1?'Won':r.outcome===0?'Lost':r.outcome==='push'?'Push':'Pending'}</span></div>`).join('');
 $('historyMore').hidden=rows.length<=hpage;
}
function filteredHistory(scope){
 const category=historyCategories[$('historyCategory').value],status=$('historyStatus').value;
 return scope.filter(r=>(!category||category(r))&&(!status||(status==='graded'||status==='settled'?r.outcome!=null:status==='pending'?r.outcome==null:status==='win'?r.outcome===1:status==='loss'?r.outcome===0:r.outcome==='push')));
}
function renderCalibration(){renderAiRecord();const m=report.metrics||{},bins=report.calibration_bins||[];$('calibration').innerHTML=`<div class="mini"><div><span>Settled lines</span><b>${m.settled_predictions||0}</b></div><div><span>Grouped Brier</span><b>${m.brier_score??'—'}</b></div><div><span>Hit ratio</span><b>${m.settled_predictions?pct(m.won/m.settled_predictions):'—'}</b></div></div><p class="small">${m.independent_groups||0} event/entity/market/side groups. ${m.settled_predictions?'Includes all suggested thresholds, not just recommendations or wagers.':'No settled forecasts yet. Results begin accumulating after games finish.'}</p><div class="cal-row"><b>Estimate band</b><b>Observed hits</b><b>Sample lines</b></div>`+bins.map(b=>`<div class="cal-row"><span>${Math.round(b.from*100)}–${Math.round(b.to*100)}%</span><span>${pct(b.actual)}</span><span>${b.n}</span></div>`).join('')}
function renderPersonal(){const settled=personal.filter(r=>r.outcome===0||r.outcome===1),won=settled.filter(r=>r.outcome===1).length;$('personalResults').innerHTML=`<p><b>${personal.length}</b> saved · <b>${settled.length}</b> graded · hit ratio <b>${settled.length?pct(won/settled.length):'—'}</b></p>`+personal.slice(-15).reverse().map(r=>`<div class="history-row"><div><strong>${esc(r.selection)} · ${esc(label(r))}</strong><span class="small">${pct(r.probability)} user line</span></div><select class="personal-grade" data-id="${esc(r.id)}" aria-label="Grade ${esc(r.selection)}" style="width:100px"><option value="" ${r.outcome==null?'selected':''}>Pending</option><option value="1" ${r.outcome===1?'selected':''}>Won</option><option value="0" ${r.outcome===0?'selected':''}>Lost</option><option value="push" ${r.outcome==='push'?'selected':''}>Push</option></select></div>`).join('');document.querySelectorAll('.personal-grade').forEach(el=>el.onchange=()=>{const r=personal.find(x=>x.id===el.dataset.id);r.outcome=el.value===''?null:el.value==='push'?'push':Number(el.value);r.graded_at=new Date().toISOString();save();renderPersonal()})}
for(const id of ['historyStatus','historyCategory','historySearch','historySport'])$(id).oninput=()=>{hpage=50;renderHistory()};$('historySource').onchange=()=>{hpage=50;$('pickRates').innerHTML='';renderHistory();loadHistory()};$('historyMore').onclick=()=>{hpage+=50;renderHistory()};
function renderHealth(){const rows=report.recommendations||[],coverage=report.coverage||[];$('health').innerHTML=[['Latest refresh',date(report.generated_at)],['Scheduled interval','Every 15 minutes · best effort'],['Automatic leagues',coverage.join(', ')],['Player model lines',rows.filter(r=>r.player_id).length],['Observed price snapshots',rows.filter(r=>r.odds!=null).length],['Backfill queue',report.backfill_remaining||0],['Props / golf / tennis / UFC prices','Import or enter exact lines'],['Paid services','None'],['Public record','Stored in your GitHub repository'],['Personal imports','Stored on this device only']].map(([a,b])=>`<div class="health-row"><b>${esc(a)}</b><span>${esc(b)}</span></div>`).join('');$('feedErrors').innerHTML=(report.errors||[]).length?`<details><summary>Feed issues (${report.errors.length})</summary><p class="small">${report.errors.map(esc).join('<br>')}</p></details>`:'<p class="small green">No feed errors reported in the last run.</p>'}
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function exportRows(rows,name){const keys=['sport','selection','player','event','event_id','start','market','side','line','probability','projection','sample','hit_rate','streak','odds','bookmaker','price_kind','edge_pp','fair_odds','predicted_at','outcome','source_url'];const cell=v=>{let s=String(v??'');if(/^[=+@\t\r]/.test(s)&&typeof v!=='number')s="'"+s;return '"'+s.replaceAll('"','""')+'"'};download(name,[keys,...rows.map(r=>keys.map(k=>r[k]))].map(r=>r.map(cell).join(',')).join('\r\n'),'text/csv;charset=utf-8')}
$('export').onclick=()=>exportRows(filtered(),'EdgeDeck_board.csv');$('historyExport').onclick=()=>exportRows(filteredHistory(historySelection()||[]),'EdgeDeck_pick_record.csv');$('template').onclick=()=>download('EdgeDeck_import_template.csv','sport,selection,event,event_id,start,market,side,line,probability,odds,bookmaker,source_url\n','text/csv;charset=utf-8');
function parseCsv(text){const rows=[];let row=[],v='',quote=false;for(let i=0;i<text.length;i++){let c=text[i];if(c==='"'){if(quote&&text[i+1]==='"'){v+='"';i++}else quote=!quote}else if(c===','&&!quote){row.push(v);v=''}else if((c==='\n'||c==='\r')&&!quote){if(c==='\r'&&text[i+1]==='\n')i++;row.push(v);if(row.some(x=>x!==''))rows.push(row);row=[];v=''}else v+=c}if(quote)throw Error('CSV has an unclosed quoted field');row.push(v);if(row.some(x=>x!==''))rows.push(row);const headers=rows.shift()?.map(x=>x.trim().replace(/^\uFEFF/,''))||[];return rows.map(r=>Object.fromEntries(headers.map((k,i)=>[k,r[i]??''])))}
function validateImport(x,i){const p=Number(x.probability),o=x.odds==null||String(x.odds).trim()===''?null:Number(x.odds),line=x.line==null||String(x.line).trim()===''?null:Number(x.line),start=x.start;if(!x.selection||!x.market||!x.event||!x.sport||!Number.isFinite(p)||p<=0||p>=1||!start||!Number.isFinite(Date.parse(start)))throw Error('Row '+(i+1)+': sport, selection, event, market, ISO start and probability between 0 and 1 are required');if(o!==null&&(!Number.isFinite(o)||Math.abs(o)<100))throw Error('Row '+(i+1)+': invalid American odds');if(line!==null&&!Number.isFinite(line))throw Error('Row '+(i+1)+': invalid line');if(x.market!=='Moneyline'&&line===null)throw Error('Row '+(i+1)+': an exact line is required');return enrich({id:'personal-'+Date.now()+'-'+i,origin:'personal',sport:String(x.sport).toUpperCase(),selection:String(x.selection),event:String(x.event),event_id:String(x.event_id||x.event+'|'+new Date(start).toISOString().slice(0,10)),start:new Date(start).toISOString(),day:new Date(start).toLocaleDateString('en-CA'),market:String(x.market),side:String(x.side||'Over'),line,probability:p,raw_probability:p,odds:o,bookmaker:o===null?null:String(x.bookmaker||'User entry'),price_kind:o===null?'User estimate':'User-entered price',fair_odds:fair(p),source_url:x.source_url||'https://www.espn.com/',observed_at:new Date().toISOString(),predicted_at:new Date().toISOString(),outcome:null,sample:0,flags:['User-supplied probability'],calibration_games:0,qualified:false})}
function afterImport(){save();sportOptions();setOptions('market',all().map(x=>x.market),'All markets');setOptions('day',all().map(x=>x.day).filter(Boolean),'Upcoming games');renderBoard();renderPersonal()}
$('importFile').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>5e6)throw Error('Maximum file size is 5 MB');const text=await file.text(),data=file.name.toLowerCase().endsWith('.json')?JSON.parse(text):parseCsv(text),rows=Array.isArray(data)?data:data.recommendations;if(!Array.isArray(rows)||rows.length>2000)throw Error('Import must contain an array of up to 2,000 rows');const valid=rows.map(validateImport);personal.push(...valid);afterImport();$('importStatus').textContent='Imported '+valid.length+' selections on this device. No bets were placed.'}catch(err){$('importStatus').textContent='Nothing imported: '+err.message}finally{e.target.value=''}};
$('manualSave').onclick=()=>{try{const r=validateImport({sport:$('manualSport').value,selection:$('manualName').value,event:$('manualEvent').value,event_id:$('manualEventId').value,start:$('manualStart').value,market:$('manualMarket').value,side:$('manualSide').value,line:$('manualLine').value,probability:Number($('manualP').value)/100,odds:$('manualOdds').value,bookmaker:'User entry'},0);personal.push(r);afterImport();toast('Saved your custom research selection.')}catch(e){toast(e.message)}};
$('clearPersonal').onclick=()=>{if(!personal.length)return;if(confirm('Remove your personal imported/saved board from this device? The public forecast history will remain intact.')){personal=[];save();renderBoard();renderPersonal();renderSlip();toast('Personal board removed from this device.')}};
startFeed();setInterval(()=>{if(!document.hidden)load()},60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});window.addEventListener('online',load);window.addEventListener('focus',load);

function propHistoryPanel(r){
 if(!r.player_id)return '';
 return '<section class="prop-history" data-chart-id="'+esc(r.id)+'"><div class="chart-controls"><label>Games <select data-chart-window><option>10</option><option>15</option><option>25</option></select></label><label>Matchups <select data-chart-match><option value="all">All opponents</option><option value="h2h">Upcoming opponent</option></select></label></div><div data-chart-body>'+propHistoryBody(r,10,'all')+'</div></section>';
}
function propHistoryBody(r,n,match){
 const source=report.player_logs?.[r.log_key],games=(source?.games||[]).filter(g=>match!=='h2h'||g.opponent_id===source.next_opponent_id).slice(-n);
 const prices=alternatePrices(r);
 if(!games.length)return '<p class="small">No recorded '+(match==='h2h'?'head-to-head ':'')+'game logs available for this prop.</p>'+prices;
 const low=Math.min(0,...games.map(g=>g.value)),high=Math.max(1,r.line,...games.map(g=>g.value))*1.12,span=high-low,width=Math.max(360,games.length*58),height=190,y=v=>height-(v-low)/span*height;
 const bars=games.map((g,i)=>{const x=20+i*58,hit=r.side==='Under'?g.value<r.line:g.value>r.line,color=g.value===r.line?'#b58b24':hit?'#176b4a':'#85929b';return '<rect x="'+x+'" y="'+Math.min(y(0),y(g.value))+'" width="38" height="'+Math.max(2,Math.abs(y(0)-y(g.value)))+'" rx="5" fill="'+color+'"/><text x="'+(x+19)+'" y="'+Math.max(13,y(g.value)-5)+'" text-anchor="middle">'+esc(fmt(g.value))+'</text><text x="'+(x+19)+'" y="211" text-anchor="middle">'+esc(new Date(g.date).toLocaleDateString('en-US',{month:'numeric',day:'numeric'}))+'</text><title>'+esc(g.opponent)+'</title>'}).join('');
 return '<p><b>'+esc(r.market)+' · '+esc(r.side)+' '+fmt(r.line)+'</b><br><small>'+games.length+' recorded games shown; '+(games.length<n?'fewer than '+n+' available.':'oldest → newest.')+'</small></p><div class="game-chart-scroll"><svg role="img" aria-label="'+esc(r.market+' game results with line '+r.line)+'" width="'+width+'" height="225" viewBox="0 0 '+width+' 225">'+bars+'<line x1="0" x2="'+width+'" y1="'+y(r.line)+'" y2="'+y(r.line)+'" stroke="#b58b24" stroke-width="2" stroke-dasharray="6 4"/></svg><div class="chart-opponents" style="width:'+width+'px">'+games.map(g=>'<span>'+esc((g.venue==='away'?'@ ':'vs ')+g.opponent)+'</span>').join('')+'</div><p class="small">Gold dashed line: '+fmt(r.line)+'. Green: cleared this selection; gray: missed; gold: push. Descriptive history, not a future guarantee.</p>'+prices;
}
let sportsbookAnchors={};
try{sportsbookAnchors=JSON.parse(localStorage.getItem('edgedeck-book-lines')||'{}')||{}}catch(e){}
function anchorKey(r){return [r.event_id,r.player_id,r.market].join('|')}
function alternateLadder(r,anchor){
 const base=anchor?.line??r.base_line??Math.max(.5,Math.round(r.projection)-.5),step=r.line_step||1;
 return [...new Set([base,...[1,2,3,4].map(i=>Math.max(.5,Math.ceil(base-i*step)-.5))])].filter(x=>x<=base).map(line=>{
 const prediction=enginePrice(r,line,'Over',null),probability=prediction?.probability??Math.max(.025,Math.min(.975,1-normalCdf(line,r.projection,r.sd)));
 return {line,probability,price:prediction?.fair_odds??fair(probability)};
 });
}
function alternatePrices(r){
 const anchor=sportsbookAnchors[anchorKey(r)],options=alternateLadder(r,anchor),base=options[0].line;
 return '<details class="alt-prices" open><summary>Starting line & lower alternate overs</summary><p class="small"><b>'+esc(anchor?'User-entered sportsbook line: '+fmt(base):'Sportsbook line unavailable · model reference: '+fmt(base))+'</b>'+(anchor?' · entered '+esc(date(anchor.at)):'')+'</p><label class="small">Posted sportsbook line (optional)<input data-book-line="'+esc(r.id)+'" type="number" min="0.5" step="0.5" placeholder="Enter Vegas / book line" value="'+esc(anchor?.line??'')+'"></label><p class="small">No minimum hit-rate target. Prices below are estimated fair odds from the model, not bookmaker quotes; sportsbook margin and availability can differ.</p><div class="alt-price-grid">'+options.map((x,i)=>'<div><b>'+(i===0?'Starting Over ':'Alt Over ')+fmt(x.line)+'</b><strong>'+odd(x.price)+'</strong><small>Estimated fair price · '+pct(x.probability)+' model probability</small><button class="white" data-alt-source="'+esc(r.id)+'" data-alt-line="'+x.line+'">Analyze / add</button></div>').join('')+'</div></details>';
}
document.addEventListener('change',e=>{
 if(!e.target.matches('[data-book-line]'))return;
 const r=all().find(x=>x.id===e.target.dataset.bookLine);if(!r)return;
 const value=e.target.value.trim(),line=Number(value);
 if(value&&(!Number.isFinite(line)||line<.5||line*2!==Math.round(line*2))){toast('Enter a positive whole or half-point sportsbook line.');return}
 if(value)sportsbookAnchors[anchorKey(r)]={line,at:new Date().toISOString()};else delete sportsbookAnchors[anchorKey(r)];
 try{localStorage.setItem('edgedeck-book-lines',JSON.stringify(sportsbookAnchors))}catch(e){toast('Line updated for this session; device storage unavailable.')}
 renderBoard();
});
document.addEventListener('click',async e=>{
 const button=e.target.closest('[data-alt-source]');if(!button)return;
 await openLab(button.dataset.altSource);$('labLine').value=button.dataset.altLine;$('labSide').value='Over';$('labOdds').value='';calculateLab();
});
document.addEventListener('change',e=>{if(!e.target.matches('[data-chart-window],[data-chart-match]'))return;const host=e.target.closest('[data-chart-id]'),r=all().find(x=>x.id===host.dataset.chartId);if(r)host.querySelector('[data-chart-body]').innerHTML=propHistoryBody(r,Number(host.querySelector('[data-chart-window]').value),host.querySelector('[data-chart-match]').value)});






// Per-game picks are rendered only when expanded, keeping the mobile board light.
const gameSelections=new Map(),gameOptionChoices=new Map();
function gameTopPicks(id){
 if(report.ai_selections?.[id])return report.ai_selections[id].filter(active); 
 const candidates=all().filter(r=>r.event_id===id&&active(r)&&(r.sample||0)>=5&&(r.odds!=null?r.expected_roi_pct>0:r.player_id&&r.projection>r.line&&r.probability>.5)&&(!r.player_id||r.side==='Over')&&primaryLine(r)&&preferredPrice(r)&&!((r.flags||[]).some(x=>/questionable|doubtful|suspended|injured reserve|^out$/i.test(x))));
 candidates.sort((a,b)=>(b.odds!=null&&b.expected_roi_pct>0?1:0)-(a.odds!=null&&a.expected_roi_pct>0?1:0)||(b.player_id?1:0)-(a.player_id?1:0)||((b.odds!=null?b.expected_roi_pct:0)-(a.odds!=null?a.expected_roi_pct:0))||((b.sample||0)-(a.sample||0))||b.probability-a.probability);
 const seen=new Set(),picks=[];for(const r of candidates){const key=r.player_id?'player:'+r.player_id:'market:'+r.market+':'+(r.team_id||'game');if(seen.has(key))continue;seen.add(key);picks.push(r);if(picks.length===10)break}return picks;
}
function tdOdds(value){return Number.isFinite(value)?(value>0?'+':'')+value:'—'}
function touchdownCandidates(g){
 if(!['NFL','NCAAF'].includes(g.sport))return '';
 const rows=report.td_candidates?.[g.id]||[];
 return `<div class="callout"><b>Anytime TD candidates</b>${rows.length?rows.map((r,i)=>{
  const history=r.first_td_history||[];
  return `<div><p class="small"><b>${i+1}. ${esc(r.player)} · ${pct(r.probability)} anytime</b> · ${esc(r.team)} · fair odds ${tdOdds(r.fair_odds)}<br>
  <b>First TD · ${Number.isFinite(r.first_td_probability)?pct(r.first_td_probability):'—'} · fair odds ${tdOdds(r.first_td_fair_odds)}</b><br>
  ${r.tds} TDs on ${r.touches} touches over the last ${r.games} team box scores. Opponent ${r.defense_games?'allowed '+fmt(r.opponent_td_allowed)+' offensive TDs per game over '+r.defense_games+' games':'defensive sample unavailable'}. ${r.injury_status==='Not listed'?'':esc(r.injury_status)}</p>
  <details><summary>First TD history · ${r.first_td_games?`${history.length} in ${r.first_td_games} verified team games`:'awaiting verified scoring logs'}</summary>
  ${history.length?`<ul>${history.map(x=>`<li><a href="${safeUrl(x.url)}" target="_blank" rel="noopener">${esc(date(x.date))} · ${esc(x.matchup)}</a> · period ${esc(x.period)} · ${esc(x.clock)}<br>${esc(x.description)}</li>`).join('')}</ul>`:'<p class="small">No recorded first-TD occurrences in the available sample.</p>'}</details></div>`;
 }).join(''):'<p class="small">Awaiting usable box scores.</p>'}<small>Probabilities are uncalibrated. Fair odds are estimated without sportsbook prices.</small></div>`;
}
function renderTouchdowns(){
 const league=$('tdLeague').value;
 const games=(report.games||[]).filter(g=>['NFL','NCAAF'].includes(g.sport)&&(!league||g.sport===league)&&new Date(g.start)>new Date());
 $('tdGames').innerHTML=games.length?games.map(g=>`<article class="game"><span class="tag">${g.sport==='NFL'?'NFL':'College football'} · ${esc(date(g.start))}</span><h3>${esc(g.event)}</h3>${touchdownCandidates(g)}</article>`).join(''):'<p class="empty">No upcoming games in this league.</p>';
}
$('tdLeague').addEventListener('change',renderTouchdowns);
function gamePickSection(g){return `<details class="game-picks" data-game-picks="${esc(g.id)}"><summary><b>AI picks · up to 10</b> · ${esc(g.event)} · ${report.game_coverage?.[g.id]?.ai_picks??'…'} picks</summary>${touchdownCandidates(g)}<div data-game-picks-body></div></details>`}
function renderGameIndex(){const node=$('gamePickBoard');if(!node)return;const opened=[...node.querySelectorAll('[data-game-picks][open]')].map(x=>({id:x.dataset.gamePicks,stake:x.querySelector('[data-game-stake]')?.value||'10'}));const games=(report.games||[]).filter(g=>active(g)&&matchesSport(g)&&(!$('day').value||g.day===$('day').value));node.innerHTML=`<h3>Game picks &amp; alternate lines</h3><p class="small">${esc((selectedSportGroup==='golf'?report.unsupported_coverage||[]:[]).join(' '))}</p>`+ (games.length?games.map(gamePickSection).join(''):'<p class="small">No upcoming games in this sport/date selection.</p>');for(const x of node.querySelectorAll('[data-game-picks]')){const previous=opened.find(o=>o.id===x.dataset.gamePicks);if(previous){x.querySelector('[data-game-picks-body]').innerHTML=gamePicksBody(previous.id);x.open=true;x.querySelector('[data-game-stake]').value=previous.stake;updateGameReview(x)}}}
function gameOptions(r){
 const options=[{id:r.id,line:r.line,side:r.side,probability:r.probability,price:r.odds??r.fair_odds,actual:r.odds!=null,row:r}];
 if(r.player_id&&r.side==='Over')for(const a of alternateLadder(r,sportsbookAnchors[anchorKey(r)]).filter(a=>a.line<r.line))options.push({...a,id:r.id+'|game-alt|'+a.line,side:'Over',actual:false,row:r});
 return options;
}
function chosenGameOption(r){const os=gameOptions(r);return os.find(o=>o.id===gameOptionChoices.get(r.id))||os[0]}
function gamePicksBody(id){
 const picks=gameTopPicks(id),chosen=gameSelections.get(id)||new Set();
 return `<p class="small">First-published picks are frozen for an auditable record. Ranked research: positive estimated return at observed prices first, then player props, available history and model probability. Up to 10 supported picks, with no minimum count. Priced picks require positive estimated return; unpriced overs require a supported directional projection and remain research. One pick per player. Current main-line price range −200 to +200; alternates may cost more. Unpriced picks are not verified sportsbook value.</p>${picks.length<10?`<p class="small">${picks.length} eligible picks available; ${esc(report.game_coverage?.[id]?.status||'no filler selections added')}.</p>`:''}${picks.map((r,i)=>{const option=chosenGameOption(r);return `<article class="game-pick"><label><input type="checkbox" data-game-select="${esc(r.id)}" ${chosen.has(r.id)?'checked':''}> <b>${i+1}. ${esc(r.selection)} · ${esc(label(r))}</b></label><p class="small">${esc((report.injuries||[]).filter(i=>i.event_id===r.event_id&&i.player_id===r.player_id).map(i=>'Current injury report: '+i.status+'. Snapshot remains in the audit record; confirm availability.').join(' '))}</p><p class="small">${r.ai_selected_at?'AI snapshot: '+esc(date(r.ai_selected_at)):''}</p><p>Projection <b>${fmt(r.projection)}</b> · ${r.sample||0} sampled games · ${pct(r.probability)} model win estimate</p><p class="small">${esc(r.reasoning||'See calculation evidence below.')}</p><label>Choose main / alternate line<select data-game-option="${esc(r.id)}">${gameOptions(r).map(o=>`<option value="${esc(o.id)}" ${option.id===o.id?'selected':''}>${esc(o.side)} ${o.line==null?'':fmt(o.line)} · ${odd(o.price)} ${o.actual?'observed':'estimated fair'} · ${pct(o.probability)}</option>`).join('')}</select></label><p class="small">${r.odds==null?'Enter an actual sportsbook price in Analyze line to assess expected return.':`Main-line observed-price estimated return ${fmt(r.expected_roi_pct)}%; alternate prices remain model estimates.`}</p>${buydownPanel(r)}${projectionPanel(r)}${evidencePanel(r)}<div data-pick-log>${lastTenLog({...r,line:option.line,side:option.side})}</div><button class="white" data-game-analyze="${esc(r.id)}">Analyze selected line</button></article>`}).join('')}<div class="game-basket"><label>Stake per straight bet ($)<input data-game-stake type="number" min="0" step="1" value="10"></label><div data-straight-review>${gameStraightReview(id,10)}</div><div class="actions"><button class="white" data-game-straights>Review straight bets</button><button class="gold" data-game-parlay>Build parlay from selected picks</button></div><p class="small">Research only; no bets are placed or transferred. Same-game joint probability and sportsbook parlay price are unavailable. Estimated fair prices are not offers.</p></div>`;
}
function gameStraightReview(id,stake){const chosen=gameSelections.get(id)||new Set(),rows=gameTopPicks(id).filter(r=>chosen.has(r.id));if(!rows.length)return '<p>Select the picks you want above.</p>';return `<p><b>${rows.length} straight bets · total stake $${fmt(rows.length*stake)}</b></p>`+rows.map(r=>{const o=chosenGameOption(r),quote=buydownQuotes.get(o.id),price=quote??o.price,d=Number.isFinite(price)?decimal(price):null;return `<p>${esc(r.selection)} · ${esc(o.side)} ${o.line==null?'':fmt(o.line)}: ${d?`$${(stake*(d-1)).toFixed(2)} profit / $${(stake*d).toFixed(2)} total return if won`:'Unpriced'}. <small>${quote!=null?'Calculated at your entered quote.':o.actual?'Observed price; verify availability.':'Illustrative at model fair odds; not an offered payout.'}</small></p>`}).join('')}
function updateGameReview(host){const stake=Number(host.querySelector('[data-game-stake]').value);host.querySelector('[data-straight-review]').innerHTML=gameStraightReview(host.dataset.gamePicks,Number.isFinite(stake)&&stake>=0?stake:0)}
document.addEventListener('toggle',async e=>{const host=e.target;if(!host.matches?.('[data-game-picks]')||!host.open)return;const target=host.querySelector('[data-game-picks-body]');if(target.dataset.ready)return;target.textContent='Loading picks and analysis…';try{await ensureDetails(host.dataset.gamePicks);if(host.isConnected){target.innerHTML=gamePicksBody(host.dataset.gamePicks);target.dataset.ready='true'}}catch(error){target.textContent='Unable to load analysis. Close and reopen to retry.'}},true);
document.addEventListener('change',e=>{const host=e.target.closest('[data-game-picks]');if(!host)return;const id=host.dataset.gamePicks;if(e.target.matches('[data-game-select]')){const set=gameSelections.get(id)||new Set();if(e.target.checked)set.add(e.target.dataset.gameSelect);else set.delete(e.target.dataset.gameSelect);gameSelections.set(id,set)}if(e.target.matches('[data-game-option]')){gameOptionChoices.set(e.target.dataset.gameOption,e.target.value);const r=gameTopPicks(id).find(r=>r.id===e.target.dataset.gameOption);if(r){const o=chosenGameOption(r);e.target.closest('.game-pick').querySelector('[data-pick-log]').innerHTML=lastTenLog({...r,line:o.line,side:o.side})}}updateGameReview(host)});
document.addEventListener('input',e=>{if(e.target.matches('[data-game-stake]'))updateGameReview(e.target.closest('[data-game-picks]'))});
function materializeGameOption(r){const o=chosenGameOption(r);const quote=buydownQuotes.get(o.id);if(o.id===r.id&&quote==null)return r;const ticketId=quote==null?o.id:o.id+'|quote|'+quote;let found=all().find(x=>x.id===ticketId);if(found)return found;const priced=enginePrice(r,o.line,o.side,null);found=enrich({...r,...priced,id:ticketId,line:o.line,side:o.side,probability:o.probability,fair_odds:priced?.fair_odds??r.fair_odds,odds:quote??null,bookmaker:quote==null?null:'User-entered sportsbook',price_kind:quote==null?'Estimated fair price':'User-entered quote',origin:'game-research',gradeable:false,selection_status:'Unpriced alternate research'});personal.push(found);return found}
document.addEventListener('click',e=>{const button=e.target.closest('[data-game-parlay],[data-game-straights],[data-game-analyze]');if(!button)return;const host=button.closest('[data-game-picks]'),id=host.dataset.gamePicks;if(button.matches('[data-game-straights]')){updateGameReview(host);host.querySelector('[data-straight-review]').scrollIntoView({block:'center',behavior:'smooth'});return}if(button.matches('[data-game-analyze]')){const r=gameTopPicks(id).find(r=>r.id===button.dataset.gameAnalyze);if(r)openLab(materializeGameOption(r).id);return}const chosen=gameSelections.get(id)||new Set(),rows=gameTopPicks(id).filter(r=>chosen.has(r.id));if(!rows.length){toast('Select at least one pick.');return}selected=rows.map(r=>materializeGameOption(r).id);go('parlay')});

function ticketPayoutForm(rows){return `<div><h4>Ticket payout calculator</h4><label>Sportsbook ticket odds (American)<input data-ticket-odds type="number" placeholder="Enter actual parlay quote, e.g. +350"></label><label>Ticket stake ($)<input data-ticket-stake type="number" min="0" value="10"></label><div data-ticket-payout>Enter a ticket quote. Same-game odds cannot be inferred by multiplying leg prices.</div></div>`}
document.addEventListener('input',e=>{if(!e.target.matches('[data-ticket-odds],[data-ticket-stake]'))return;const host=$('combined'),o=Number(host.querySelector('[data-ticket-odds]').value),stake=Number(host.querySelector('[data-ticket-stake]').value);host.querySelector('[data-ticket-payout]').textContent=Math.abs(o)>=100&&Number.isFinite(stake)&&stake>=0?`If won: $${(stake*(decimal(o)-1)).toFixed(2)} profit / $${(stake*decimal(o)).toFixed(2)} total return at your entered quote. No ticket win probability or edge is established.`:'Enter valid American odds (−100 or lower, +100 or higher) and a nonnegative stake.'});


function calibrationTrackingPanel(){
 const rows=report.calibration_tracking||[];
 const score=value=>Number.isFinite(value)?value.toFixed(4):'—';
 return `<details><summary>Calibration on newly published picks</summary><p class="small">Both probabilities are recorded before kickoff and scored against the same results. Lower scores are better. Pushes are omitted.</p>${rows.length?'<div style="overflow-x:auto"><table><thead><tr><th>Market</th><th>Graded / pending</th><th>Games graded</th><th>Brier original → adjusted</th><th>Log loss original → adjusted</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${esc(r.sport+' · '+r.market)}</td><td>${r.settled} / ${r.pending}</td><td>${r.games}</td><td>${score(r.original.brier)} → ${score(r.adjusted.brier)}</td><td>${score(r.original.log_loss)} → ${score(r.adjusted.log_loss)}</td></tr>`).join('')+'</tbody></table></div>':'<p>Waiting for newly published picks with an active calibration adjustment.</p>'}</details>`;
}
function renderAiRecord(){const target=$('aiRecord');if(!target)return;const a=report.ai_record||{},rows=a.records||[],diag=a.market_diagnostics||[],learning=Object.entries(report.ai_learning||{});target.innerHTML=`<h3>AI picks: sport &amp; overall record</h3><p class="small">${esc(a.scope||'Tracking starts with the first published selection snapshot.')} Pushes excluded from win %. ROI uses observed-price straight bets only. Alternatives and personal tickets are separate.</p><div style="overflow-x:auto"><table><thead><tr><th>Sport</th><th>W–L–P</th><th>Win %</th><th>Pending</th><th>Games</th><th>Priced ROI</th><th>Brier</th></tr></thead><tbody>${rows.map(r=>`<tr><td><b>${esc(r.sport)}</b></td><td>${r.wins}–${r.losses}–${r.pushes}</td><td>${pct(r.hit_rate)}</td><td>${r.pending}</td><td>${r.games}</td><td>${r.roi_pct==null?'Unpriced':fmt(r.roi_pct)+'% ('+r.priced_settled+')'}</td><td>${r.brier==null?'—':Number(r.brier).toFixed(3)}</td></tr>`).join('')}</tbody></table></div><p class="small">Compare sample sizes and pricing, not hit rate alone. These records do not establish which sport will perform best in future.</p>${trendPanel(a.trends||[])}<details><summary>Miss review &amp; learning by sport / market</summary>${diag.map(r=>`<p><b>${esc(r.sport)}</b>: ${r.wins}–${r.losses}; MAE ${fmt(r.mae)}, signed error ${fmt(r.projection_bias)}, Brier ${fmt(r.brier)}. High-confidence misses ${r.high_confidence_misses}; flagged misses ${r.flagged_misses}. ${esc(r.interpretation)}</p>`).join('')}${learning.length?learning.map(([k,v])=>`<p>${esc(k)}: ${esc(v.status)} · ${v.samples} graded picks across ${v.game_dates} dates · correction ${fmt(v.conditional_probability_offset*100)} pp. ${esc(v.scope)}</p>`).join(''):'<p>No graded AI selections yet; no learned correction is active.</p>'}<p class="small">Only future predictions may change. A small sport/market probability-bias correction activates after at least 30 graded picks across 10 dates and improved later-date Brier score and log loss. It is not a causal explanation or a guarantee of improved future accuracy. Projection errors use different units; compare within each market.</p></details>${calibrationTrackingPanel()}<details><summary>Per-game all-picks bundle record</summary><p class="small">Research bundle of every frozen pick, not a user-created or sportsbook-priced parlay. One loss loses the bundle; unresolved legs remain pending unless already lost; pushes remove legs. No parlay ROI inferred.</p>${(a.bundles||[]).map(b=>`<p>${esc(b.sport)} · ${esc(b.event)} · ${b.legs} picks · <b>${b.outcome===0?'Loss':b.outcome===1?'Win':b.outcome==='push'?'Push':'Pending'}</b></p>`).join('')}</details><details><summary>Latest graded AI picks</summary>${(report.ai_recent_results||[]).slice().reverse().map(r=>`<p>${esc(r.sport+' · '+r.event+' · '+r.selection+' · '+r.market)} ${esc(r.side)} ${fmt(r.line)} · ${r.outcome===1?'Win':r.outcome===0?'Loss':'Push'} · forecast ${fmt(r.projection)}, actual ${fmt(r.actual_value)} · ${pct(r.probability)} predicted</p>`).join('')||'<p>Pending games have not been graded yet.</p>'}</details>`}



function renderSourceAudit(target){
 const audit=report.next_gen_audit;
 if(!audit)return;
 target.insertAdjacentHTML('beforeend',`<details class="view-guide"><summary>NFL Next Gen Stats cross-check</summary><p>${audit.fields_checked.toLocaleString()} stats compared across ${audit.checked_games} games · ${audit.mismatches} discrepancies for review.</p><p>Source snapshot ${esc(audit.snapshot_date||'unavailable')}. ${audit.error?'Latest download failed. Checks use any saved snapshot.':''} The second source covers qualifying NFL players.</p>${(audit.examples||[]).map(r=>`<p class="small">${esc(r.player)} · ${esc(r.field)} · ESPN ${fmt(r.espn)} · Next Gen Stats ${fmt(r.next_gen)}</p>`).join('')}<p><a href="${safeUrl(audit.url)}" target="_blank" rel="noopener">NFL Next Gen Stats via nflverse ↗</a></p></details>`);
 const rows=Object.entries(report.ai_learning||{}).filter(([,r])=>r.price_benchmark?.picks);
 target.insertAdjacentHTML('beforeend',`<details class="view-guide"><summary>Model accuracy versus observed prices</summary><p class="small">Lower Brier scores are better. Both scores use the same graded picks. Offered odds include sportsbook margin.</p>${rows.map(([market,r])=>`<p class="small">${esc(market)} · ${r.price_benchmark.picks} picks · model ${r.price_benchmark.model_brier.toFixed(3)} · offered price ${r.price_benchmark.price_brier.toFixed(3)}</p>`).join('')}</details>`);
}
function renderCoverageStatus(){const target=$('health');if(!target)return;renderSourceAudit(target);target.insertAdjacentHTML('beforeend',`<details class="view-guide"><summary>Today’s coverage &amp; refresh status</summary><p>Generated ${esc(date(report.generated_at))}. The app checks for a new feed every minute and on return to the app or connection. GitHub’s 15-minute schedule is best-effort.</p><table><thead><tr><th>Sport</th><th>Upcoming today</th><th>Projections</th><th>AI picks</th></tr></thead><tbody>${(report.daily_coverage||[]).map(r=>`<tr><td>${esc(r.sport)}</td><td>${r.games_today}</td><td>${r.predictions_today}</td><td>${r.ai_picks_today}</td></tr>`).join('')}</tbody></table><p>${esc((report.unsupported_coverage||[]).join(' '))}</p><p class="small">No qualifying AI picks does not mean no scheduled game. Check each game’s data status; positive value is not fabricated to fill a quota.</p></details>`)}

function lastTenLog(r){
 const table=(rows,heading)=>{
  const games=rows.filter(g=>Number.isFinite(g.value)).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,10);
  const threshold=r.market==='Moneyline'?0:r.market==='Spread'?-r.line:r.line;
  const result=v=>!Number.isFinite(threshold)?'—':v===threshold?'Push':(r.side==='Under'?v<threshold:v>threshold)?'Hit':'Miss';
  const hits=games.filter(g=>result(g.value)==='Hit').length;
  return '<h4>'+esc(heading)+'</h4><p class="small">'+(games.length?games.length+' of 10 available · average '+fmt(games.reduce((s,g)=>s+g.value,0)/games.length)+(Number.isFinite(threshold)?' · '+hits+'/'+games.length+' hits at selected line':''):'No recorded stats available.')+'</p>'+(games.length?'<table><thead><tr><th>Date</th><th>Opponent</th><th>Stat</th><th>Result</th></tr></thead><tbody>'+games.map(g=>'<tr><td>'+esc(date(g.date))+'</td><td>'+esc(g.opponent)+'</td><td>'+fmt(g.value)+'</td><td>'+result(g.value)+'</td></tr>').join('')+'</tbody></table>':'');
 };
 let body;
 if(r.player_id)body=table((report.player_logs?.[r.log_key]?.games||[]).map(g=>({...g,opponent:(g.venue==='away'?'@ ':'vs ')+g.opponent})),r.market);
 else{
  const evidence=r.projection_evidence||report.game_evidence?.[r.event_id];
  const fixture=report.games?.find(g=>g.id===r.event_id);
  const teams=r.team_id?[r.team_id]:[fixture?.away?.id,fixture?.home?.id].filter(Boolean);
  const source=evidence?.home?.source_games||report.game_evidence?.[r.event_id]?.home?.source_games||[];
  body=teams.map(id=>table(source.filter(g=>g.home_id===id||g.away_id===id).map(g=>{
   const home=g.home_id===id,own=home?g.home_score:g.away_score,opp=home?g.away_score:g.home_score;
   let value=null;
   if(Number.isFinite(own)&&Number.isFinite(opp)){
    if(r.market==='Total')value=own+opp;
    if(r.market==='Team total')value=own;
    if(r.market==='Moneyline'||r.market==='Spread')value=own-opp;
    if(r.market==='1st half total'||r.market==='1st quarter total'){
     const n=r.market==='1st half total'?2:1,ps=[...(g.home_periods||[]).slice(0,n),...(g.away_periods||[]).slice(0,n)];
     if(ps.length===2*n&&ps.every(Number.isFinite))value=ps.reduce((a,b)=>a+b,0);
    }
   }
   return {date:g.date,opponent:(home?'vs ':'@ ')+(home?g.away_name:g.home_name),value};
  }),[fixture?.home,fixture?.away].find(t=>t?.id===id)?.name||r.selection)).join('')||'<p>No game log available.</p>';
 }
 return '<details class="view-guide"><summary>Last 10 games</summary><div style="overflow-x:auto">'+body+'</div></details>';
}

const buydownQuotes=new Map();
function buydownReturn(option,quote){
 const push=enginePrice(option.row,option.line,option.side,null)?.push_probability??0;
 return option.probability*decimal(quote)+push-1;
}
function buydownPanel(r){
 const options=gameOptions(r);
 if(options.length<2)return '';
 return `<details class="view-guide" data-buydown="${esc(r.id)}"><summary>Compare lower lines</summary>
 <p class="small">Enter current sportsbook odds for each exact line. The comparison favors a gain of at least 5 percentage points while retaining at least 80% of the main line's expected return. The main line needs at least 5% expected return.</p>
 ${options.map((o,i)=>`<label>${i?'Lower line':'Main line'} · Over ${fmt(o.line)} · ${pct(o.probability)}<input data-buydown-quote="${esc(o.id)}" type="number" step="1" placeholder="American odds" value="${esc(buydownQuotes.get(o.id)??'')}"></label>`).join('')}
 <button type="button" class="white" data-buydown-compare>Compare prices</button><div data-buydown-result aria-live="polite"></div></details>`;
}
document.addEventListener('click',e=>{
 const button=e.target.closest('[data-buydown-compare]');
 if(!button)return;
 const panel=button.closest('[data-buydown]'),host=panel.closest('[data-game-picks]');
 const r=gameTopPicks(host.dataset.gamePicks).find(row=>row.id===panel.dataset.buydown);
 if(!r)return;
 const result=panel.querySelector('[data-buydown-result]');
 for(const input of panel.querySelectorAll('[data-buydown-quote]')){
  const quote=Number(input.value);
  if(input.value.trim()&&(!Number.isInteger(quote)||Math.abs(quote)<100)){result.textContent='Enter valid American odds, such as −140 or +110.';return}
 }
 for(const input of panel.querySelectorAll('[data-buydown-quote]')){
  if(input.value.trim())buydownQuotes.set(input.dataset.buydownQuote,Number(input.value));
  else buydownQuotes.delete(input.dataset.buydownQuote);
 }
 const [main,...alternates]=gameOptions(r),mainQuote=buydownQuotes.get(main.id)??r.odds;
 const original=mainQuote==null?null:buydownReturn(main,mainQuote);
 const comparisons=alternates.map(o=>{
  const quote=buydownQuotes.get(o.id),gain=o.probability-main.probability;
  const ev=quote==null?null:buydownReturn(o,quote);
  const eligible=original!=null&&original>=.05-1e-9&&gain>=.05-1e-9&&ev!=null&&ev>=original*.8-1e-9;
  return {o,gain,ev,eligible};
 });
 const best=comparisons.filter(x=>x.eligible).sort((a,b)=>b.gain-a.gain||b.ev-a.ev)[0];
 result.innerHTML=`<p>${original==null?'Enter main-line odds to compare expected returns.':`Main-line estimated return ${pct(original)}.`} ${best?`Selected Over ${fmt(best.o.line)} for this ticket.`:'No lower line qualified at the supplied prices.'}</p>`+
 comparisons.map(({o,gain,ev})=>`<p>Over ${fmt(o.line)} · ${gain>=0?'+':''}${fmt(gain*100)} pp · ${ev==null?'estimated break-even '+odd(o.price):'estimated return '+pct(ev)}</p>`).join('');
 if(best){
  result.insertAdjacentText('beforeend',saveLinePair(r,main,mainQuote,best.o,buydownQuotes.get(best.o.id)));
  const select=panel.closest('.game-pick').querySelector('[data-game-option]');
  select.value=best.o.id;
  select.dispatchEvent(new Event('change',{bubbles:true}));
 }
});

const linePairKey='edgedeck-line-pairs-v1';
function readLinePairs(){
 try{const rows=JSON.parse(localStorage.getItem(linePairKey)||'[]');return Array.isArray(rows)?rows:[]}catch{return []}
}
function linePairId(r){return JSON.stringify([r.event_id,r.player_id,r.market])}
function saveLinePair(r,main,mainQuote,alt,altQuote){
 if(!Number.isFinite(Date.parse(r.start))||Date.parse(r.start)<=Date.now())return ' Pregame tracking has closed.';
 const rows=readLinePairs(),id=linePairId(r);
 if(rows.some(x=>x.id===id))return ' First qualifying comparison already tracked on this device.';
 const snapshot=(o,odds)=>({line:o.line,odds,probability:o.probability});
 rows.push({id,enteredAt:new Date().toISOString(),main:snapshot(main,mainQuote),alt:snapshot(alt,altQuote)});
 try{localStorage.setItem(linePairKey,JSON.stringify(rows));return ' Pregame comparison saved on this device.'}catch{return ' Device storage was unavailable.'}
}
function trendPanel(trends){
 const pairs=readLinePairs(),actuals=new Map();
 if(pairs.length)for(const r of history)if(Number.isFinite(r.actual_value))actuals.set(linePairId(r),r.actual_value);
 const paired=pairs.filter(p=>actuals.has(p.id));
 const sides=['main','alt'].map(side=>{
  let wins=0,losses=0,profit=0,oddsSum=0;
  for(const p of paired){
   const {line,odds}=p[side],actual=actuals.get(p.id);
   oddsSum+=decimal(odds);
   if(actual>line){wins++;profit+=decimal(odds)-1}
   if(actual<line){losses++;profit--}
  }
  return [side==='main'?'Main':'Lower',wins+'–'+losses+'–'+(paired.length-wins-losses),wins+losses?pct(wins/(wins+losses)):'—',paired.length?(oddsSum/paired.length).toFixed(2):'—',paired.length?pct(profit/paired.length):'—'];
 });
 const table=(headers,rows)=>'<div style="overflow-x:auto"><table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
 return '<details><summary>Performance by rank, sport and odds</summary><p class="small">ROI uses settled picks with recorded prices at one unit each. Average odds are decimal.</p>'+
 table(['Sport','Group','W–L–P','Win %','Priced','Avg odds','ROI'],trends.map(r=>[r.sport,r.band,r.wins+'–'+r.losses+'–'+r.pushes,pct(r.hit_rate),r.priced_settled,r.average_decimal_odds?.toFixed(2)??'—',r.roi_pct==null?'—':fmt(r.roi_pct)+'%']))+'</details>'+
 '<details><summary>Main vs. lower line results</summary><p class="small">Compare prices saves the first qualifying pair before game start on this device. Both lines use the same final stat and their recorded quotes. '+paired.length+' graded · '+(pairs.length-paired.length)+' awaiting final stats.</p>'+
 table(['Line','W–L–P','Win %','Avg odds','ROI'],sides)+'</details>';
}
