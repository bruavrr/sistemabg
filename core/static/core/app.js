document.querySelectorAll('[data-nav]').forEach(a=>{const p=a.dataset.nav;if(p==='/'?location.pathname==='/':location.pathname.startsWith(p))a.classList.add('active')});
const menu=document.querySelector('.menu-button');if(menu)menu.addEventListener('click',()=>{const open=document.querySelector('.sidebar').classList.toggle('open');menu.setAttribute('aria-expanded',String(open))});
document.querySelectorAll('[data-confirm]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm(f.dataset.confirm))e.preventDefault()}));
document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
const trade=document.querySelector('#id_trade'), panel=document.querySelector('#trade-panel');function syncTrade(){if(!trade||!panel)return;panel.hidden=!trade.checked;panel.querySelectorAll('input,select,textarea').forEach(el=>el.disabled=!trade.checked)}if(trade){trade.addEventListener('change',syncTrade);syncTrade()}

// Resumo em centavos inteiros. A confirmação dos valores é sempre do servidor.
const saleForm=document.querySelector('#sale-form');
const pricesElement=document.querySelector('#sale-prices');
if(saleForm&&pricesElement){
 const prices=JSON.parse(pricesElement.textContent);
 const toCents=value=>{const match=String(value??'').trim().replace(',','.').match(/^(\d+)(?:\.(\d{0,2}))?$/);return match?BigInt(match[1])*100n+BigInt((match[2]||'').padEnd(2,'0')):0n};
 const currency=cents=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(cents)/100);
 const read=name=>saleForm.querySelector(`[name="${name}"]`)?.value||'';
 const put=(id,value)=>{const el=document.getElementById(id);if(el){el.textContent=currency(value);el.classList.toggle('negative',value<0n)}};
 function summarize(){
  let gross=0n,paid=0n,fees=0n;const selected=[];
  saleForm.querySelectorAll('[name="devices"] option:checked').forEach(o=>{const p=prices.devices[o.value];if(p){gross+=BigInt(p.price);selected.push(`${p.label} · ${currency(BigInt(p.price))}`)}});
  saleForm.querySelectorAll('.accessory-row').forEach(row=>{const id=row.querySelector('select')?.value;const p=prices.accessories[id];const qty=Number(row.querySelector('input[type="number"]')?.value||0);if(p&&Number.isSafeInteger(qty)&&qty>0){gross+=BigInt(p.price)*BigInt(qty);selected.push(`${p.label} · ${qty} un. · ${currency(BigInt(p.price)*BigInt(qty))}`)}});
  saleForm.querySelectorAll('.payment-row').forEach(row=>{const method=row.querySelector('[name$="-method"]')?.value;const amount=toCents(row.querySelector('[name$="-amount"]')?.value);if(method){paid+=amount;if(method==='card'){const rate=prices.rates[row.querySelector('[name$="-card_rate"]')?.value];if(rate!==undefined)fees+=(amount*BigInt(rate)+50000n)/100000n}}});
  const total=gross-toCents(read('discount'));const tradeValue=saleForm.querySelector('[name="trade"]')?.checked?toCents(read('trade-acquisition_cost')):0n;
  put('pdv-gross',gross);put('pdv-total',total);put('pdv-trade',tradeValue);put('pdv-paid',paid);put('pdv-balance',total-tradeValue-paid);put('pdv-fee',fees);put('pdv-net',paid-fees);
  const list=document.querySelector('#cart-preview');list.replaceChildren();(selected.length?selected:['Nenhum produto selecionado.']).forEach(text=>{const li=document.createElement('li');li.textContent=text;list.appendChild(li)});
 }
 saleForm.addEventListener('input',summarize);saleForm.addEventListener('change',summarize);
 saleForm.querySelectorAll('[data-add-row]').forEach(button=>button.addEventListener('click',()=>{const prefix=button.dataset.addRow;const total=saleForm.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);const count=Number(total.value);if(count>=20){button.disabled=true;return}const template=document.getElementById(`${prefix}-empty`);const container=document.getElementById(prefix==='acc'?'accessory-extra':'payment-extra');const holder=document.createElement('div');holder.innerHTML=template.innerHTML.replaceAll('__prefix__',String(count));container.append(...holder.childNodes);total.value=String(count+1);summarize()}));
 summarize();
}
