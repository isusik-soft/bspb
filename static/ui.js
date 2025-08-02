(function () {
  const dashboard = document.getElementById('dashboard');
  const editor = document.getElementById('editor');
  const statementsBody = document.querySelector('#statementsTable tbody');
  const newBtn = document.getElementById('newStatementBtn');
  const backBtn = document.getElementById('backToDashboard');
  const addOpBtn = document.getElementById('addOperation');
  const saveBtn = document.getElementById('saveDraft');
  const pdfBtn = document.getElementById('generatePdf');
  const saveStatus = document.getElementById('saveStatus');

  const accountInput = document.getElementById('accountInput');
  const ownerInput = document.getElementById('ownerInput');
  const startInput = document.getElementById('periodStart');
  const endInput = document.getElementById('periodEnd');
  const openingInput = document.getElementById('openingBalance');
  const bankSelect = document.getElementById('bankSelect');
  const incomingEl = document.getElementById('totalIncoming');
  const outgoingEl = document.getElementById('totalOutgoing');
  const closingEl = document.getElementById('closingBalance');
  const opsBody = document.querySelector('#operationsTable tbody');
  const searchInput = document.getElementById('searchInput');

  // Templates
  const templateModal = document.getElementById('templateModal');
  const templateTitle = document.getElementById('templateTitle');
  const templateSelect = document.getElementById('templateSelect');
  const templateText = document.getElementById('templateText');
  const templateUseBtn = document.getElementById('templateUse');
  const templateSaveBtn = document.getElementById('templateSaveBtn');
  const templateDeleteBtn = document.getElementById('templateDelete');
  const templateCloseBtn = document.getElementById('templateClose');

  const TEMPLATE_KEYS = {
    counterparty: 'templates_counterparty',
    description: 'templates_description'
  };

  let currentTemplateField = null;
  let currentTemplateInput = null;

  function loadTemplates(field) {
    const raw = localStorage.getItem(TEMPLATE_KEYS[field]);
    return raw ? JSON.parse(raw) : [];
  }

  function saveTemplates(field, arr) {
    localStorage.setItem(TEMPLATE_KEYS[field], JSON.stringify(arr));
  }

  function renderTemplateList() {
    if (!currentTemplateField) return;
    const templates = loadTemplates(currentTemplateField);
    templateSelect.innerHTML = '';
    templates.forEach((t, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = t;
      templateSelect.appendChild(opt);
    });
  }

  function openTemplateModal(field, inputEl) {
    currentTemplateField = field;
    currentTemplateInput = inputEl;
    templateTitle.textContent = field === 'counterparty'
      ? 'Шаблоны: Плательщик / Получатель'
      : 'Шаблоны: Операция';
    templateText.value = '';
    renderTemplateList();
    templateModal.classList.remove('d-none');
  }

  function closeTemplateModal() {
    templateModal.classList.add('d-none');
    currentTemplateField = null;
    currentTemplateInput = null;
    templateText.value = '';
  }

  templateCloseBtn.addEventListener('click', closeTemplateModal);

  templateSelect.addEventListener('change', () => {
    const idx = templateSelect.value;
    const templates = loadTemplates(currentTemplateField);
    templateText.value = templates[idx] || '';
  });

  templateSaveBtn.addEventListener('click', () => {
    if (!currentTemplateField) return;
    const text = templateText.value.trim();
    if (!text) return;
    const templates = loadTemplates(currentTemplateField);
    const idx = templateSelect.value;
    let newIndex = idx;
    if (idx !== '' && templates[idx] !== undefined) {
      templates[idx] = text;
    } else {
      templates.push(text);
      newIndex = templates.length - 1;
    }
    saveTemplates(currentTemplateField, templates);
    renderTemplateList();
    templateSelect.value = newIndex;
    templateText.value = '';
  });

  templateDeleteBtn.addEventListener('click', () => {
    if (!currentTemplateField) return;
    const idx = templateSelect.value;
    if (idx === '') return;
    const templates = loadTemplates(currentTemplateField);
    templates.splice(idx, 1);
    saveTemplates(currentTemplateField, templates);
    renderTemplateList();
    templateSelect.value = '';
    templateText.value = '';
  });

  templateUseBtn.addEventListener('click', () => {
    if (!currentTemplateField || !currentTemplateInput) return;
    const idx = templateSelect.value;
    const templates = loadTemplates(currentTemplateField);
    const value = idx !== '' ? templates[idx] : templateText.value.trim();
    if (value) {
      currentTemplateInput.value = value;
      currentTemplateInput.dispatchEvent(new Event('input'));
    }
    closeTemplateModal();
  });

  let saveTimeout = null;

  function showDashboard() {
    editor.classList.add('d-none');
    dashboard.classList.remove('d-none');
    refreshStatements();
  }

  function showEditor() {
    dashboard.classList.add('d-none');
    editor.classList.remove('d-none');
    loadDraft();
    updateTotals();
  }

  newBtn.addEventListener('click', () => {
    localStorage.removeItem('statementDraft');
    showEditor();
  });
  backBtn.addEventListener('click', showDashboard);

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase();
    Array.from(statementsBody.querySelectorAll('tr')).forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });

  function refreshStatements() {
    fetch('/statements').then(r => r.ok ? r.json() : []).then(data => {
      statementsBody.innerHTML = '';
      data.forEach(st => {
        const tr = document.createElement('tr');
        const period = `${st.period_start} - ${st.period_end}`;
        const created = new Date(st.generated_at).toLocaleString('ru-RU');
        tr.innerHTML =
          `<td>${st.id}</td>` +
          `<td>${st.account_number}</td>` +
          `<td>${st.owner || ''}</td>` +
          `<td>${period}</td>` +
          `<td>${st.status || 'сгенерирована'}</td>` +
          `<td>${created}</td>` +
          `<td><a class="btn btn-sm btn-outline-secondary" href="/statement/${st.id}.pdf" target="_blank">PDF</a></td>`;
        statementsBody.appendChild(tr);
      });
    });
  }

  function addOperation(op = {}) {
    const tr = document.createElement('tr');
    const amountValue = op.amount != null ? op.amount : '';
    tr.innerHTML = `
      <td><input type="date" class="form-control form-control-sm op-date" value="${op.date || ''}"></td>
      <td>
        <div class="input-group input-group-sm">
          <input type="text" class="form-control op-counterparty" value="${op.counterparty || ''}">
          <button type="button" class="btn btn-outline-secondary template-btn" data-field="counterparty">+</button>
        </div>
      </td>
      <td>
        <div class="input-group input-group-sm">
          <input type="text" class="form-control op-description" value="${op.description || ''}">
          <button type="button" class="btn btn-outline-secondary template-btn" data-field="description">+</button>
        </div>
      </td>
      <td><input type="number" step="0.01" class="form-control form-control-sm op-amount" value="${amountValue}"></td>
      <td class="text-nowrap">
        <button class="btn btn-sm btn-outline-secondary duplicate" title="Дублировать">⧉</button>
        <button class="btn btn-sm btn-outline-danger delete" title="Удалить">✕</button>
      </td>`;
    opsBody.appendChild(tr);

    const inputs = tr.querySelectorAll('input');
    inputs.forEach(inp => inp.addEventListener('input', updateTotalsAndSave));

    tr.querySelectorAll('.template-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const field = btn.dataset.field;
        const inputEl = btn.parentElement.querySelector('input');
        openTemplateModal(field, inputEl);
      });
    });

    tr.querySelector('.delete').addEventListener('click', () => {
      tr.remove();
      updateTotalsAndSave();
    });
    tr.querySelector('.duplicate').addEventListener('click', () => {
      const data = getRowData(tr);
      addOperation(data);
      updateTotalsAndSave();
    });
  }

  function getNumber(input) {
    const raw = input.value.replace(/\s+/g, '').replace(',', '.');
    const val = parseFloat(raw);
    return Number.isNaN(val) ? 0 : val;
  }

  function getRowData(tr) {
    return {
      date: tr.querySelector('.op-date').value,
      counterparty: tr.querySelector('.op-counterparty').value,
      description: tr.querySelector('.op-description').value,
      amount: getNumber(tr.querySelector('.op-amount'))
    };
  }

  function gatherData() {
    const operations = Array.from(opsBody.querySelectorAll('tr')).map(tr => getRowData(tr));
    return {
      bank: bankSelect.value,
      account: accountInput.value.trim(),
      fio: ownerInput.value.trim(),
      from: startInput.value,
      to: endInput.value,
      opening_balance: getNumber(openingInput),
      operations
    };
  }

  function updateTotals() {
    let incoming = 0, outgoing = 0;
    Array.from(opsBody.querySelectorAll('tr')).forEach(tr => {
      const val = getNumber(tr.querySelector('.op-amount'));
      if (val >= 0) incoming += val; else outgoing += val;
    });
    const opening = getNumber(openingInput);
    const closing = opening + incoming + outgoing;
    incomingEl.textContent = incoming.toFixed(2);
    outgoingEl.textContent = outgoing.toFixed(2);
    closingEl.textContent = closing.toFixed(2);
  }

  function updateTotalsAndSave() {
    updateTotals();
    saveDraftDebounced();
  }

  openingInput.addEventListener('input', updateTotalsAndSave);
  accountInput.addEventListener('input', saveDraftDebounced);
  ownerInput.addEventListener('input', saveDraftDebounced);
  startInput.addEventListener('input', saveDraftDebounced);
  endInput.addEventListener('input', saveDraftDebounced);
  bankSelect.addEventListener('input', saveDraftDebounced);

  addOpBtn.addEventListener('click', () => {
    addOperation();
    saveDraftDebounced();
  });

  function saveDraft() {
    const data = gatherData();
    localStorage.setItem('statementDraft', JSON.stringify(data));
    saveStatus.textContent = 'Сохранено';
  }

  function saveDraftDebounced() {
    saveStatus.textContent = 'Сохранение...';
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveDraft, 1500);
  }

  saveBtn.addEventListener('click', saveDraft);

  function loadDraft() {
    const raw = localStorage.getItem('statementDraft');
    opsBody.innerHTML = '';
    if (raw) {
      try {
        const data = JSON.parse(raw);
        bankSelect.value = data.bank || 'BSPB';
        accountInput.value = data.account || '';
        ownerInput.value = data.fio || '';
        startInput.value = data.from || '';
        endInput.value = data.to || '';
        openingInput.value = data.opening_balance != null ? data.opening_balance : 0;
        (data.operations || []).forEach(addOperation);
      } catch (e) {
        addOperation();
      }
    } else {
      addOperation();
    }
    updateTotals();
    saveStatus.textContent = '';
  }

  pdfBtn.addEventListener('click', async () => {
    const data = gatherData();
    const payload = {
      bank: data.bank,
      fio: data.fio,
      account: data.account,
      from: data.from,
      to: data.to,
      opening_balance: data.opening_balance,
      operations: data.operations
    };
    const resp = await fetch('/statement/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) {
      alert('Ошибка генерации');
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'statement.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  refreshStatements();
})();

