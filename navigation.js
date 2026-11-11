/* Dedicated views; capture routing prevents old scroll-only handlers competing. */
(()=>{
const main=document.querySelector('main');
for(const [id,title] of [['aiparlays','AI projection parlays'],['trends','Historical hit trends']]){const section=document.createElement('section');section.id=id;section.className='view';section.hidden=true;section.innerHTML='<div class="section-head"><h2>'+title+'</h2></div>';main.append(section)}
document.getElementById('aiparlays').append(document.getElementById('dailyParlays'));
document.getElementById('trends').append(document.getElementById('perfectProps'));
document.getElementById('mobileParlays').dataset.nav='aiparlays';
go=function(view){
const target=document.getElementById(view);
if(!target||!target.classList.contains('view')){toast('This section is unavailable. Please refresh.');return}
currentView=view;document.body.dataset.view=view;document.body.dataset.discover='all';
document.querySelectorAll('.view').forEach(el=>el.hidden=el!==target);
document.querySelectorAll('[data-nav]').forEach(b=>b.classList.toggle('active',b.dataset.nav===view));
target.scrollIntoView({block:'start',behavior:'auto'});
requestAnimationFrame(()=>{try{
if(view==='allpicks')renderPicksHub();
if(view==='history'){if(!historyLoaded)loadHistory();else renderHistory();if(!dailyLoaded)loadDailyRecords();else renderDailyRecords()}
if(view==='parlay')renderSlip();if(view==='matchups')renderGames();if(view==='data')renderHealth();
}catch(error){toast('This section could not render. Try Check latest. '+error.message);console.error(error)}})
};
document.addEventListener('click',e=>{const b=e.target.closest('[data-nav],#mobileParlays,[data-discover]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();const v=b.dataset.nav||({all:'allpicks',picks:'allpicks',parlays:'aiparlays',trends:'trends'}[b.dataset.discover]);go(v)},true);
})();
