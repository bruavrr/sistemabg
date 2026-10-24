// Cadastros rápidos persistem no servidor e preservam o formulário e seus anexos.
(() => {
  const sale = document.querySelector('#sale-form');
  const customerElement = document.querySelector('#customer-data');
  const customers = customerElement ? JSON.parse(customerElement.textContent) : {};
  const customerSelect = sale?.querySelector('[name="customer"]');
  const notice = document.querySelector('#sale-notice');
  const announce = text => {
    if (notice) { notice.textContent = text; notice.className = 'message'; notice.hidden = false; }
  };
  const option = (select, id, label, selected = false) => {
    if (!select) return;
    let entry = Array.from(select.options).find(item => item.value === String(id));
    if (!entry) { entry = new Option(label, String(id)); select.add(entry); }
    if (selected) select.value = String(id);
  };
  const origins = entry => {
    document.querySelectorAll('select[name$="-origin"],select[name$="-supplier"]').forEach(select => option(select, entry.id, entry.label));
  };
  const renderCustomer = () => {
    const preview = document.querySelector('#customer-preview');
    if (!preview || !customerSelect) return;
    const data = customers[customerSelect.value];
    preview.replaceChildren(); preview.hidden = !data;
    if (data) [data.document, data.email, data.phone, data.discovery_label ? `Conheceu por: ${data.discovery_label}` : ''].filter(Boolean).forEach(text => {
      const span = document.createElement('span'); span.textContent = text; preview.appendChild(span);
    });
  };
  customerSelect?.addEventListener('change', renderCustomer);
  renderCustomer();
  document.querySelectorAll('[data-open-dialog]').forEach(button => button.addEventListener('click', () => {
    const dialog = document.getElementById(button.dataset.openDialog);
    if (dialog && !dialog.open) dialog.showModal();
  }));
  document.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
  const refresh = () => {
    sale?.dispatchEvent(new Event('change', { bubbles: true }));
    window.bgSummarizeSale?.();
  };
  const selectCustomer = entry => {
    customers[String(entry.id)] = entry;
    option(customerSelect, entry.id, entry.label, true);
    origins(entry); renderCustomer(); refresh();
  };
  function includeObject(entry) {
    if (entry.kind === 'customer') { selectCustomer(entry); return true; }
    if (entry.origin) origins(entry.origin);
    if (!entry.available) { announce('O cadastro foi localizado, mas o produto já não está disponível. Confira o estoque.'); return false; }
    const prices = window.bgSalePrices;
    const currency = cents => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100);
    if (entry.kind === 'device') {
      prices.devices[String(entry.id)] = { label: entry.label, price: entry.price };
      const list = document.querySelector('#id_devices');
      let input = sale.querySelector(`input[name="devices"][value="${entry.id}"]`);
      if (!input) {
        const row = document.createElement('div'); const label = document.createElement('label');
        input = document.createElement('input'); input.type = 'checkbox'; input.name = 'devices'; input.value = String(entry.id);
        label.append(input, document.createTextNode(` ${entry.label} · ${currency(entry.price)}`)); row.appendChild(label); list.appendChild(row);
      }
      input.checked = true;
      document.querySelector('#device-empty').hidden = true;
      const search = document.querySelector('#device-search'); if (search) { search.value = ''; search.dispatchEvent(new Event('input')); }
    } else {
      prices.accessories[String(entry.id)] = { label: entry.label, price: entry.price };
      const addToSelect = select => option(select, entry.id, entry.label);
      sale.querySelectorAll('.accessory-row select').forEach(addToSelect);
      const emptyTemplate = document.querySelector('#acc-empty');
      if (emptyTemplate) emptyTemplate.content.querySelectorAll('select').forEach(addToSelect);
      let target = Array.from(sale.querySelectorAll('.accessory-row')).find(row => !row.querySelector('select').value);
      if (!target) { sale.querySelector('[data-add-row="acc"]').click(); target = Array.from(sale.querySelectorAll('.accessory-row')).find(row => !row.querySelector('select').value); }
      if (target) { target.querySelector('select').value = String(entry.id); target.querySelector('input[type="number"]').value = '1'; }
      else { announce('Acessório cadastrado. As 20 linhas da venda já estão em uso; ajuste uma linha para incluí-lo.'); return false; }
    }
    refresh(); return true;
  }
  document.querySelectorAll('[data-quick-form]').forEach(form => {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (form.dataset.saving) return;
      const status = form.querySelector('.quick-status');
      const submit = form.querySelector('[type="submit"]');
      const originalText = submit.textContent;
      form.querySelectorAll('[data-error-for]').forEach(el => el.replaceChildren());
      form.querySelectorAll('[aria-invalid]').forEach(el => el.removeAttribute('aria-invalid'));
      status.replaceChildren(); status.classList.remove('success');
      form.dataset.saving = '1'; submit.disabled = true; submit.textContent = 'Salvando…';
      try {
        const response = await fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
        if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Sua sessão pode ter expirado. Abra o sistema em outra aba e entre novamente; depois volte para tentar salvar.');
        const result = await response.json();
        if (!response.ok || !result.ok) {
          status.textContent = result.message || 'Não foi possível salvar. Confira os dados.';
          Object.entries(result.errors || {}).forEach(([field, errors]) => {
            const wrapper = form.querySelector(`[data-quick-field="${field}"]`);
            const feedback = wrapper?.querySelector('[data-error-for]');
            if (feedback) feedback.textContent = errors.map(error => error.message).join(' ');
            else if (field === '__all__') status.append(document.createTextNode(' ' + errors.map(error => error.message).join(' ')));
            wrapper?.querySelector('input,select,textarea')?.setAttribute('aria-invalid', 'true');
          });
          if (result.existing) {
            const button = document.createElement('button'); button.type = 'button'; button.className = 'button secondary';
            button.textContent = `Usar cadastro de ${result.existing.label}`;
            button.addEventListener('click', () => { selectCustomer(result.existing); form.closest('dialog').close(); announce('Cliente existente selecionado. Os demais dados da venda foram preservados.'); }); status.appendChild(button);
          }
          status.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); return;
        }
        const included = includeObject(result.object);
        form.reset();
        const key = form.querySelector('[name$="-request_key"]');
        if (key && result.next_request_key) key.value = result.next_request_key;
        form.closest('dialog').close();
        if (included === false) announce('Produto cadastrado no estoque, mas não selecionado nesta venda. Confira a disponibilidade e as linhas de produtos.');
        else announce(`${result.object.kind === 'customer' ? 'Cliente cadastrado e selecionado' : 'Produto cadastrado e incluído'}. Continue a venda; seus dados foram preservados.`);
      } catch (error) {
        status.textContent = error.message || 'Não foi possível confirmar o cadastro. Tente salvar novamente sem fechar esta janela.';
      } finally { delete form.dataset.saving; submit.disabled = false; submit.textContent = originalText; }
    });
  });
  const search = document.querySelector('#device-search');
  search?.addEventListener('input', () => {
    const term = search.value.toLocaleLowerCase('pt-BR').trim();
    document.querySelectorAll('#id_devices label').forEach(label => {
      const input = label.querySelector('input'); const data = window.bgSalePrices?.devices[input?.value];
      const text = `${label.textContent} ${data?.label || ''}`.toLocaleLowerCase('pt-BR');
      label.parentElement.hidden = !!term && !text.includes(term);
    });
  });
  document.querySelectorAll('[data-logo-form]').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault(); if (form.dataset.saving) return;
    const status = form.querySelector('.quick-status'); const submit = form.querySelector('[type="submit"]');
    form.dataset.saving = '1'; submit.disabled = true; status.textContent = '';
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: { 'Accept': 'application/json' } });
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Sessão expirada. Entre novamente e tente enviar a logo.');
      const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.message || 'Imagem inválida.');
      const url = `/marca/logo/?v=${encodeURIComponent(result.logo_url)}`;
      document.querySelectorAll('[data-brand-mark]').forEach(mark => { const image = document.createElement('img'); image.src = url; image.alt = 'Logomarca BG Store'; mark.replaceChildren(image); });
      form.closest('dialog').close(); announce('Logomarca atualizada.');
    } catch (error) { status.textContent = error.message; }
    finally { delete form.dataset.saving; submit.disabled = false; }
  }));
})();
