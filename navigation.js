/* Dedicated views; capture routing prevents old scroll-only handlers competing. */
(()=>{
const main=document.querySelector('main');
for(const [id,title] of [['aiparlays','AI projection parlays'],['trends','Historical hit trends']]){const section=document.createElement('section');section.id=id;section.className='view';section.hidden=true;section.innerHTML='<div class="section-head"><h2>'+title+'</h2></div>';main.append(section)}
document.getElementById('aiparlays').append(document.getElementById('dailyParlays'));
document.getElementById('trends').append(document.getElementById('perfectProps'));
document.getElementById('mobileParlays').dataset.nav='aiparlays';
const oldGo=go;
go=function(view){const target=document.getElementById(view);if(!target||!target.classList.contains('view')){toast('This section is unavailable. Please refresh the app.');return}document.body.dataset.discover='all';oldGo(view);target.scrollIntoView({behavior:'smooth',block:'start'});if(view==='aiparlays'&&!document.getElementById('dailyParlays').textContent.trim())document.getElementById('dailyParlays').innerHTML='<p class="fd-status">Loading projection-based parlays. If the feed is unavailable, use Check latest; no sample picks are substituted.</p>';};
document.addEventListener('click',e=>{const b=e.target.closest('[data-nav],#mobileParlays,[data-discover]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();const v=b.dataset.nav||({all:'allpicks',picks:'allpicks',parlays:'aiparlays',trends:'trends'}[b.dataset.discover]);go(v)},true);
})();
