document.querySelectorAll('[data-nav]').forEach(a=>{const p=a.dataset.nav;if(p==='/'?location.pathname==='/':location.pathname.startsWith(p))a.classList.add('active')});
const menu=document.querySelector('.menu-button');if(menu)menu.addEventListener('click',()=>{const open=document.querySelector('.sidebar').classList.toggle('open');menu.setAttribute('aria-expanded',String(open))});
document.querySelectorAll('[data-confirm]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm(f.dataset.confirm))e.preventDefault()}));
document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
const trade=document.querySelector('#id_trade'), panel=document.querySelector('#trade-panel');function syncTrade(){if(!trade||!panel)return;panel.hidden=!trade.checked;panel.querySelectorAll('input,select,textarea').forEach(el=>el.disabled=!trade.checked)}if(trade){trade.addEventListener('change',syncTrade);syncTrade()}
